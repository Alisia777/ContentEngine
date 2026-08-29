begin;
-- 202608290005_publishing_jobs_queue_v1
--
-- Фаза 1 контура публикаций, шаг 1а (ТЗ
-- docs/PUBLISHING_ACCOUNTS_CONTOUR_2026-08-23.md §4.2, §8): очередь
-- публикаций и её неизменяемый журнал.
--
-- Принципы (те же, что у media_preparation_jobs из 202608270003 и очередей
-- system_claim_*): секретов в таблицах нет и быть не может (правило
-- sanitize_payload legacy перенесено в SQL-CHECK через существующий
-- content_factory_private.notification_payload_sensitive_v491); RLS включён,
-- браузерных грантов нет — браузер ходит только через creator_* RPC
-- (202608290006); воркер — только через system_* от service_role; журнал
-- переходов append-only (guard-триггер запрещает update/delete).
--
-- Один наряд — одна публикация: unique (organization_id, placement_id).
-- ERID обязателен на уровне таблицы: «без рекламы» — это literal ORGANIC,
-- пустой маркировки не существует; не-ORGANIC требует рекламодателя в
-- marking (подпись собирается автосборкой в enqueue).

create table if not exists content_factory.publishing_jobs (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid,
  placement_id uuid not null,
  managed_account_id uuid not null,
  media_object_id uuid not null,
  platform text not null check (platform in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram',
    'wildberries', 'ozon', 'rutube', 'other'
  )),
  caption text not null
    check (length(btrim(caption)) between 1 and 4000),
  hashtags text
    check (hashtags is null or length(btrim(hashtags)) between 1 and 500),
  marking jsonb not null default '{}'::jsonb
    check (jsonb_typeof(marking) = 'object' and length(marking::text) <= 2048),
  erid text not null check (erid ~ '^[A-Z0-9-]{4,64}$'),
  scheduled_at timestamptz not null,
  status text not null default 'queued' check (status in (
    'queued', 'claimed', 'uploading', 'published', 'failed',
    'cancelled', 'manual_required'
  )),
  attempts integer not null default 0 check (attempts between 0 and 10),
  next_attempt_at timestamptz not null default now(),
  provider_post_id text check (provider_post_id is null
    or length(btrim(provider_post_id)) between 1 and 240),
  final_url text check (final_url is null or final_url ~ '^https://'),
  last_error_code text check (last_error_code is null
    or last_error_code ~ '^[a-z][a-z0-9_]{2,99}$'),
  last_error_detail text check (last_error_detail is null or (
    length(last_error_detail) <= 2000
    and not content_factory_private.notification_payload_sensitive_v491(
      to_jsonb(last_error_detail)
    )
  )),
  idempotency_key text not null
    check (length(idempotency_key) between 12 and 180),
  created_by uuid not null,
  lease_token uuid,
  leased_until timestamptz,
  manual_required_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint publishing_jobs_org_id_uq unique (organization_id, id),
  constraint publishing_jobs_placement_uq unique (organization_id, placement_id),
  constraint publishing_jobs_idempotency_uq
    unique (organization_id, idempotency_key),
  constraint publishing_jobs_organization_fk foreign key (organization_id)
    references content_factory.organizations (id) on delete cascade,
  constraint publishing_jobs_placement_fk
    foreign key (organization_id, placement_id)
    references content_factory.placements (organization_id, id),
  constraint publishing_jobs_account_fk
    foreign key (organization_id, managed_account_id)
    references content_factory.managed_accounts (organization_id, id),
  constraint publishing_jobs_media_fk
    foreign key (organization_id, media_object_id)
    references content_factory.media_objects (organization_id, id),
  constraint publishing_jobs_created_by_fk
    foreign key (organization_id, created_by)
    references content_factory.memberships (organization_id, profile_id),
  -- Пустой маркировки не бывает: либо ERID рекламы с рекламодателем, либо
  -- literal ORGANIC.
  constraint publishing_jobs_marking_advertiser_check check (
    erid = 'ORGANIC'
    or nullif(btrim(coalesce(marking ->> 'advertiser', '')), '') is not null
  ),
  -- Аренда существует ровно у claimed/uploading (лестница
  -- generation_strategy_worker_leases, аренда <= 5 минут задаётся в RPC).
  constraint publishing_jobs_lease_state_check check (
    (status in ('claimed', 'uploading')
      and lease_token is not null and leased_until is not null)
    or (status in ('queued', 'published', 'failed', 'cancelled',
      'manual_required')
      and lease_token is null and leased_until is null)
  ),
  -- Факт публикации приносит площадка: без post id и ссылки статуса
  -- published не бывает (§5.5 ТЗ).
  constraint publishing_jobs_published_proof_check check (
    status <> 'published'
    or (provider_post_id is not null and final_url is not null)
  )
);

create index if not exists publishing_jobs_due_idx
  on content_factory.publishing_jobs (scheduled_at, next_attempt_at)
  where status = 'queued';
create index if not exists publishing_jobs_lease_idx
  on content_factory.publishing_jobs (leased_until)
  where status in ('claimed', 'uploading');
create index if not exists publishing_jobs_account_idx
  on content_factory.publishing_jobs
    (organization_id, managed_account_id, status);

alter table content_factory.publishing_jobs enable row level security;
revoke all on content_factory.publishing_jobs
  from public, anon, authenticated;
grant all on content_factory.publishing_jobs to service_role;

-- Неизменяемый журнал переходов и ответов площадки. payload — без секретов
-- и подписанных URL: CHECK зовёт тот же санитайзер, что и контракт
-- уведомлений v491.
create table if not exists content_factory.publishing_job_events (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  job_id uuid not null,
  event text not null check (event ~ '^[a-z][a-z0-9_]{2,79}$'),
  payload jsonb not null default '{}'::jsonb check (
    jsonb_typeof(payload) = 'object'
    and length(payload::text) <= 8192
    and not content_factory_private.notification_payload_sensitive_v491(payload)
  ),
  actor text not null
    check (actor in ('creator', 'worker', 'dispatcher', 'system')),
  actor_profile_id uuid,
  created_at timestamptz not null default now(),
  constraint publishing_job_events_job_fk
    foreign key (organization_id, job_id)
    references content_factory.publishing_jobs (organization_id, id)
    on delete cascade,
  constraint publishing_job_events_actor_fk
    foreign key (organization_id, actor_profile_id)
    references content_factory.memberships (organization_id, profile_id)
);

create index if not exists publishing_job_events_job_idx
  on content_factory.publishing_job_events
    (organization_id, job_id, created_at);

alter table content_factory.publishing_job_events enable row level security;
revoke all on content_factory.publishing_job_events
  from public, anon, authenticated;
grant all on content_factory.publishing_job_events to service_role;

create or replace function content_factory_private.guard_publishing_job_events()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  raise exception using errcode = '55000',
    message = 'publishing_job_events_immutable';
end;
$$;

revoke all on function content_factory_private.guard_publishing_job_events()
  from public, anon, authenticated, service_role;

drop trigger if exists publishing_job_events_immutable
  on content_factory.publishing_job_events;
create trigger publishing_job_events_immutable
  before update or delete on content_factory.publishing_job_events
  for each row
  execute function content_factory_private.guard_publishing_job_events();

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
begin
  if (select count(*)
      from pg_catalog.pg_class rel
      join pg_catalog.pg_namespace nsp on nsp.oid = rel.relnamespace
      where nsp.nspname = 'content_factory'
        and rel.relname in ('publishing_jobs', 'publishing_job_events')
        and rel.relrowsecurity) <> 2 then
    raise exception using message = 'publishing_tables_rls_disabled';
  end if;
  if exists (
    select 1
    from information_schema.role_table_grants grants
    where grants.table_schema = 'content_factory'
      and grants.table_name in ('publishing_jobs', 'publishing_job_events')
      and grants.grantee in ('anon', 'authenticated')
  ) then
    raise exception using message =
      'publishing_tables_browser_grants_present';
  end if;
  if not exists (
    select 1
    from pg_catalog.pg_trigger trg
    join pg_catalog.pg_class rel on rel.oid = trg.tgrelid
    join pg_catalog.pg_namespace nsp on nsp.oid = rel.relnamespace
    where nsp.nspname = 'content_factory'
      and rel.relname = 'publishing_job_events'
      and trg.tgname = 'publishing_job_events_immutable'
      and not trg.tgisinternal
  ) then
    raise exception using message = 'publishing_events_guard_missing';
  end if;
end;
$verify$;

notify pgrst, 'reload schema';

commit;
