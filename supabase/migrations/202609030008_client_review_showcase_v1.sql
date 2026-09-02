begin;
-- 202609030008_client_review_showcase_v1
--
-- Схема витрины согласования (ступень 1 гибридной лестницы): клиент без
-- входа и auth-учётки открывает токен-ссылку, смотрит ролики кампании,
-- принимает/возвращает с комментарием и просит публикацию. По образцу
-- public_recovery_receipts (202607170007): таблицы под FORCE RLS без
-- единого гранта браузерным ролям И service_role — доступ только через
-- security definer RPC (операторские creator_* в 0009, системные
-- system_* для edge в 0010). В базе живёт ТОЛЬКО sha256 токена; сырой
-- токен показывается оператору один раз при выдаче. Поля intake_enabled /
-- intake_owner_profile_id заведены сразу по контракту
-- docs/CLIENT_REVIEW_TOKEN_CONTRACT_V1.md — ступень 2 строится на этом же
-- токене без миграции схемы ссылки.

create table content_factory.client_review_links (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null
    references content_factory.organizations (id),
  campaign_id uuid not null,
  created_by uuid not null,
  client_label text not null
    check (length(btrim(client_label)) between 2 and 120),
  token_hash text not null unique
    check (token_hash ~ '^[0-9a-f]{64}$'),
  status text not null default 'active'
    check (status in ('active', 'revoked', 'expired')),
  expires_at timestamptz not null,
  view_count integer not null default 0 check (view_count >= 0),
  view_limit integer not null default 500
    check (view_limit between 1 and 100000),
  decision_count integer not null default 0 check (decision_count >= 0),
  decide_limit integer not null default 100
    check (decide_limit between 1 and 10000),
  intake_enabled boolean not null default false,
  intake_owner_profile_id uuid,
  last_viewed_at timestamptz,
  revoked_at timestamptz,
  revoked_by uuid,
  idempotency_key text not null
    check (length(idempotency_key) between 8 and 180),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, idempotency_key),
  constraint client_review_links_campaign_fk
    foreign key (organization_id, campaign_id)
    references content_factory.generation_campaigns (organization_id, id),
  constraint client_review_links_creator_fk
    foreign key (organization_id, created_by)
    references content_factory.memberships (organization_id, profile_id),
  check (expires_at > created_at),
  check (expires_at <= created_at + interval '90 days'),
  check (status <> 'revoked' or revoked_at is not null)
);

create index client_review_links_campaign_idx
  on content_factory.client_review_links (organization_id, campaign_id);

create table content_factory.client_review_link_items (
  id uuid primary key default extensions.gen_random_uuid(),
  link_id uuid not null
    references content_factory.client_review_links (id) on delete cascade,
  organization_id uuid not null,
  media_object_id uuid not null,
  position integer not null check (position between 1 and 200),
  curator_attested boolean not null default false,
  -- Заготовка ветки А публикации: заранее подготовленный оператором
  -- placement с аккаунтом и ОРД-пресетом. FK появится вместе с самой
  -- веткой А; в v1 кнопка «Опубликовать» пишет решение publish_requested.
  publish_placement_id uuid,
  created_at timestamptz not null default now(),
  unique (link_id, media_object_id),
  unique (link_id, position),
  constraint client_review_link_items_media_fk
    foreign key (organization_id, media_object_id)
    references content_factory.media_objects (organization_id, id)
);

create table content_factory.client_review_decisions (
  id uuid primary key default extensions.gen_random_uuid(),
  link_id uuid not null
    references content_factory.client_review_links (id) on delete cascade,
  item_id uuid not null
    references content_factory.client_review_link_items (id)
    on delete cascade,
  organization_id uuid not null,
  decision text not null
    check (decision in ('accepted', 'returned', 'publish_requested')),
  comment text
    check (comment is null or length(comment) between 3 and 2000),
  client_request_id uuid not null,
  created_at timestamptz not null default now(),
  unique (item_id, client_request_id),
  check (decision <> 'returned' or comment is not null)
);

create index client_review_decisions_item_idx
  on content_factory.client_review_decisions (item_id, created_at desc);

-- Журнал доступа: живёт и для несуществующих токенов (анти-энумерация и
-- cooldown считаются по нему), поэтому НИКАКИХ FK на ссылки.
create table content_factory.client_review_access_log (
  id uuid primary key default extensions.gen_random_uuid(),
  token_hash text not null check (token_hash ~ '^[0-9a-f]{64}$'),
  client_key_hash text not null
    check (client_key_hash ~ '^[0-9a-f]{16,128}$'),
  action text not null
    check (action in ('view', 'decide', 'refused')),
  created_at timestamptz not null default now()
);

create index client_review_access_log_token_idx
  on content_factory.client_review_access_log (token_hash, created_at desc);
create index client_review_access_log_client_idx
  on content_factory.client_review_access_log
    (client_key_hash, created_at desc);

-- Решения клиента append-only: правка задним числом невозможна (по
-- образцу guard_publishing_job_events).
create or replace function
  content_factory_private.guard_client_review_decision_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using errcode = '55000',
    message = 'client_review_decision_append_only';
end;
$$;

create trigger client_review_decisions_append_only
  before update or delete on content_factory.client_review_decisions
  for each row
  execute function
    content_factory_private.guard_client_review_decision_mutation();

do $lockdown$
declare
  probe_table text;
begin
  for probe_table in
    select unnest(array[
      'client_review_links', 'client_review_link_items',
      'client_review_decisions', 'client_review_access_log'
    ])
  loop
    execute format(
      'alter table content_factory.%I enable row level security', probe_table
    );
    execute format(
      'alter table content_factory.%I force row level security', probe_table
    );
    execute format(
      'revoke all on table content_factory.%I '
        || 'from public, anon, authenticated, service_role',
      probe_table
    );
  end loop;
end;
$lockdown$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  probe_table text;
begin
  for probe_table in
    select unnest(array[
      'client_review_links', 'client_review_link_items',
      'client_review_decisions', 'client_review_access_log'
    ])
  loop
    if not exists (
      select 1 from pg_catalog.pg_class cl
      join pg_catalog.pg_namespace ns on ns.oid = cl.relnamespace
      where ns.nspname = 'content_factory'
        and cl.relname = probe_table
        and cl.relrowsecurity and cl.relforcerowsecurity
    ) then
      raise exception using message =
        'client_review_force_rls_missing_' || probe_table;
    end if;
    if exists (
      select 1
      from information_schema.role_table_grants grants
      where grants.table_schema = 'content_factory'
        and grants.table_name = probe_table
        and grants.grantee in ('anon', 'authenticated', 'service_role')
    ) then
      raise exception using message =
        'client_review_grants_leak_' || probe_table;
    end if;
  end loop;
  if not exists (
    select 1 from pg_catalog.pg_trigger trg
    where trg.tgrelid = 'content_factory.client_review_decisions'::regclass
      and trg.tgname = 'client_review_decisions_append_only'
  ) then
    raise exception using message =
      'client_review_append_only_guard_missing';
  end if;
end;
$verify$;

commit;
