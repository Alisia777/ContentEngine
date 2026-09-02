begin;
-- 202609030014_client_intake_v1
--
-- Ступень 2 «клиент под присмотром»: вкладка «Материалы и бриф» на ТОМ ЖЕ
-- токене витрины (контракт docs/CLIENT_REVIEW_TOKEN_CONTRACT_V1.md).
-- Клиент сдаёт бриф товара и файлы (фото / СВОИ видео товара) — оператор
-- видит их в пульте ссылок, принимает в работу или возвращает. Материалы
-- клиента НИКОГДА не попадают в генерацию автоматически: регистрацию в
-- медиатеку оператор выполняет при подготовке запуска (автоматика — в
-- итерации 2). Поля брифа — только с префиксом brief_ (санитайзер Desktop
-- v4 режет name/title — задокументированная DOM-clobbering-мина).
-- Таблицы под FORCE RLS без грантов, как весь контур витрины.

create table content_factory.client_intake_uploads (
  id uuid primary key default extensions.gen_random_uuid(),
  link_id uuid not null
    references content_factory.client_review_links (id) on delete cascade,
  organization_id uuid not null,
  object_name text not null unique
    check (length(object_name) between 8 and 1024),
  original_filename text not null
    check (length(original_filename) between 1 and 255),
  mime_type text not null check (mime_type in (
    'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
  )),
  size_bytes bigint not null
    check (size_bytes between 1 and 52428800),
  rights_confirmed boolean not null default false check (rights_confirmed),
  status text not null default 'uploaded'
    check (status in ('uploaded', 'registered', 'rejected')),
  client_request_id uuid not null,
  created_at timestamptz not null default now(),
  unique (link_id, client_request_id)
);

create index client_intake_uploads_link_idx
  on content_factory.client_intake_uploads (link_id, created_at desc);

create table content_factory.client_intake_briefs (
  id uuid primary key default extensions.gen_random_uuid(),
  link_id uuid not null
    references content_factory.client_review_links (id) on delete cascade,
  organization_id uuid not null,
  brief_product text not null
    check (length(btrim(brief_product)) between 2 and 180),
  brief_audience text not null
    check (length(btrim(brief_audience)) between 3 and 600),
  brief_tone text not null
    check (length(btrim(brief_tone)) between 3 and 400),
  brief_restrictions text
    check (brief_restrictions is null
      or length(brief_restrictions) <= 800),
  brief_wishes text
    check (brief_wishes is null or length(brief_wishes) <= 1200),
  status text not null default 'submitted'
    check (status in ('submitted', 'accepted', 'returned')),
  operator_comment text
    check (operator_comment is null
      or length(operator_comment) between 3 and 1000),
  decided_by uuid,
  decided_at timestamptz,
  client_request_id uuid not null,
  created_at timestamptz not null default now(),
  unique (link_id, client_request_id),
  check (status = 'submitted' or decided_at is not null)
);

create index client_intake_briefs_link_idx
  on content_factory.client_intake_briefs (link_id, created_at desc);

do $lockdown$
declare
  probe_table text;
begin
  for probe_table in
    select unnest(array['client_intake_uploads', 'client_intake_briefs'])
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

-- Оператор включает/выключает клиентский ввод на конкретной ссылке;
-- владелец клиентских файлов по умолчанию — выдавший ссылку.
create or replace function public.creator_configure_client_review_intake(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  enabled_value boolean;
  link_row content_factory.client_review_links%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  enabled_value := coalesce(
    (p_payload ->> 'intake_enabled')::boolean, false
  );

  update content_factory.client_review_links link
  set intake_enabled = enabled_value,
      intake_owner_profile_id = coalesce(
        link.intake_owner_profile_id, link.created_by
      ),
      updated_at = now()
  where link.organization_id = organization_id
    and link.id = content_factory_private.require_uuid(p_payload, 'link_id')
  returning * into link_row;
  if link_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'client_review_link_not_found';
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-intake-v1',
    'link', jsonb_build_object(
      'id', link_row.id,
      'intake_enabled', link_row.intake_enabled
    )
  );
end;
$$;

-- Пульт оператора: брифы и файлы клиента по ссылке.
create or replace function public.creator_list_client_intake(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  link_id_value uuid;
  briefs_value jsonb;
  uploads_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  link_id_value := content_factory_private.require_uuid(
    p_payload, 'link_id'
  );

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', brief.id,
    'brief_product', brief.brief_product,
    'brief_audience', brief.brief_audience,
    'brief_tone', brief.brief_tone,
    'brief_restrictions', brief.brief_restrictions,
    'brief_wishes', brief.brief_wishes,
    'status', brief.status,
    'operator_comment', brief.operator_comment,
    'created_at', brief.created_at
  ) order by brief.created_at desc), '[]'::jsonb)
  into briefs_value
  from content_factory.client_intake_briefs brief
  where brief.organization_id = organization_id
    and brief.link_id = link_id_value;

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', upload.id,
    'object_name', upload.object_name,
    'original_filename', upload.original_filename,
    'mime_type', upload.mime_type,
    'size_bytes', upload.size_bytes,
    'status', upload.status,
    'created_at', upload.created_at
  ) order by upload.created_at desc), '[]'::jsonb)
  into uploads_value
  from content_factory.client_intake_uploads upload
  where upload.organization_id = organization_id
    and upload.link_id = link_id_value;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-intake-v1',
    'briefs', briefs_value,
    'uploads', uploads_value
  );
end;
$$;

-- Решение оператора по брифу: принять в работу или вернуть с комментарием.
create or replace function public.creator_decide_client_intake_brief(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  decision_value text;
  comment_value text;
  brief_row content_factory.client_intake_briefs%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  decision_value := coalesce(p_payload ->> 'decision', '');
  if decision_value not in ('accepted', 'returned') then
    raise exception using errcode = '22023',
      message = 'client_intake_decision_invalid';
  end if;
  comment_value := nullif(btrim(coalesce(p_payload ->> 'comment', '')), '');
  if decision_value = 'returned' and comment_value is null then
    raise exception using errcode = '22023',
      message = 'client_intake_comment_required';
  end if;

  update content_factory.client_intake_briefs brief
  set status = decision_value,
      operator_comment = comment_value,
      decided_by = user_id,
      decided_at = now()
  where brief.organization_id = organization_id
    and brief.id = content_factory_private.require_uuid(
      p_payload, 'brief_id'
    )
  returning * into brief_row;
  if brief_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'client_intake_brief_not_found';
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-intake-v1',
    'brief', jsonb_build_object(
      'id', brief_row.id, 'status', brief_row.status
    )
  );
end;
$$;

do $grants$
declare
  fn_name text;
begin
  for fn_name in
    select unnest(array[
      'creator_configure_client_review_intake',
      'creator_list_client_intake',
      'creator_decide_client_intake_brief'
    ])
  loop
    execute format(
      'revoke all on function public.%I(jsonb) '
        || 'from public, anon, service_role', fn_name
    );
    execute format(
      'grant execute on function public.%I(jsonb) to authenticated', fn_name
    );
  end loop;
end;
$grants$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ: гранты и вызов пульта под JWT владельца.
do $verify$
declare
  claims_value text;
  owner_id uuid;
  organization_value uuid;
  link_value uuid;
  intake_value jsonb;
begin
  if has_function_privilege(
       'anon', 'public.creator_list_client_intake(jsonb)', 'execute')
     or has_function_privilege(
       'anon', 'public.creator_decide_client_intake_brief(jsonb)',
       'execute') then
    raise exception using message = 'client_intake_anon_leak';
  end if;
  select link.created_by, link.organization_id, link.id
  into owner_id, organization_value, link_value
  from content_factory.client_review_links link
  order by link.created_at desc
  limit 1;
  if link_value is not null then
    claims_value := current_setting('request.jwt.claims', true);
    perform set_config(
      'request.jwt.claims',
      json_build_object('sub', owner_id, 'role', 'authenticated')::text,
      true
    );
    intake_value := public.creator_list_client_intake(jsonb_build_object(
      'organization_id', organization_value,
      'link_id', link_value
    ));
    perform set_config(
      'request.jwt.claims', coalesce(claims_value, ''), true
    );
    if intake_value ->> 'ok' is distinct from 'true' then
      raise exception using message = 'client_intake_list_broken';
    end if;
  end if;
end;
$verify$;

notify pgrst, 'reload schema';

commit;
