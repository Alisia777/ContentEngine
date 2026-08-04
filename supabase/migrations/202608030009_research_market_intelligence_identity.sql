begin;

-- Additive, provider-free identity for market categories and structural trend
-- signals. Existing compliance product_category metadata and v2 research JSON
-- remain unchanged.

create or replace function content_factory_private.research_market_identity_key(
  value text
)
returns text
language sql
immutable
set search_path = ''
as $$
  select btrim(lower(regexp_replace(
    btrim(coalesce($1, '')),
    '[[:space:][:punct:]]+',
    ' ',
    'g'
  )))
$$;

create table if not exists content_factory.research_market_categories (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    canonical_name text not null,
    normalized_name text not null,
    definition text not null,
    status text not null default 'active' check (status in ('active', 'retired')),
    created_by uuid not null,
    created_at timestamptz not null default now(),
    constraint research_market_categories_org_id_uq
      unique (organization_id, id),
    constraint research_market_categories_org_name_uq
      unique (organization_id, normalized_name),
    foreign key (organization_id)
      references content_factory.organizations(id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    check (length(btrim(canonical_name)) between 2 and 160),
    check (length(btrim(definition)) between 10 and 2000),
    check (
      normalized_name =
        content_factory_private.research_market_identity_key(canonical_name)
      and length(normalized_name) between 2 and 160
    )
);

create index if not exists research_market_categories_org_created_idx
  on content_factory.research_market_categories
  (organization_id, created_at desc, id desc);

create table if not exists content_factory.research_market_category_aliases (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    category_id uuid not null,
    alias_value text not null,
    normalized_alias text not null,
    created_by uuid not null,
    created_at timestamptz not null default now(),
    constraint research_market_category_aliases_org_id_uq
      unique (organization_id, id),
    constraint research_market_category_aliases_org_key_uq
      unique (organization_id, normalized_alias),
    foreign key (organization_id, category_id)
      references content_factory.research_market_categories(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    check (length(btrim(alias_value)) between 2 and 160),
    check (
      normalized_alias =
        content_factory_private.research_market_identity_key(alias_value)
      and length(normalized_alias) between 2 and 160
    )
);

create index if not exists research_market_category_aliases_category_idx
  on content_factory.research_market_category_aliases
  (organization_id, category_id, normalized_alias, id);

create table if not exists content_factory.research_product_market_category_bindings (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    product_id uuid not null,
    category_id uuid not null,
    previous_binding_id uuid,
    binding_version integer not null check (binding_version between 1 and 100000),
    decision_action text not null check (decision_action in (
      'bind_existing', 'create_and_bind', 'reclassify',
      'create_and_reclassify'
    )),
    source_run_id uuid not null,
    source_draft_id uuid not null,
    candidate_hash text not null check (candidate_hash ~ '^[0-9a-f]{64}$'),
    reason text check (reason is null or length(btrim(reason)) between 3 and 500),
    confirmed_by uuid not null,
    confirmed_at timestamptz not null default now(),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    constraint research_product_market_bindings_org_id_uq
      unique (organization_id, id),
    constraint research_product_market_bindings_org_product_id_uq
      unique (organization_id, product_id, id),
    constraint research_product_market_bindings_org_product_category_id_uq
      unique (organization_id, product_id, id, category_id),
    constraint research_product_market_bindings_org_product_version_uq
      unique (organization_id, product_id, binding_version),
    constraint research_product_market_bindings_org_key_uq
      unique (organization_id, idempotency_key),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, category_id)
      references content_factory.research_market_categories(organization_id, id),
    foreign key (organization_id, product_id, previous_binding_id)
      references content_factory.research_product_market_category_bindings(
        organization_id, product_id, id
      ),
    foreign key (organization_id, product_id, source_run_id)
      references content_factory.product_research_runs(
        organization_id, product_id, id
      ),
    foreign key (organization_id, source_run_id, source_draft_id)
      references content_factory.creative_brief_drafts(
        organization_id, run_id, id
      ),
    foreign key (organization_id, confirmed_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (binding_version = 1 and previous_binding_id is null)
      or (binding_version > 1 and previous_binding_id is not null)
    )
);

create index if not exists research_product_market_bindings_current_idx
  on content_factory.research_product_market_category_bindings
  (organization_id, product_id, binding_version desc, id desc);

create table if not exists content_factory.research_structural_trend_signal_types (
    signal_key text primary key check (
      signal_key ~ '^[a-z][a-z0-9_]*[.][a-z][a-z0-9_.]*$'
      and length(signal_key) between 3 and 100
    ),
    family text not null check (family in ('hook', 'format', 'proof', 'offer', 'channel')),
    canonical_label text not null check (length(btrim(canonical_label)) between 2 and 160),
    definition text not null check (length(btrim(definition)) between 10 and 1000),
    status text not null default 'active' check (status in ('active', 'deprecated')),
    replacement_signal_key text references
      content_factory.research_structural_trend_signal_types(signal_key),
    catalog_version integer not null default 1 check (catalog_version between 1 and 100000),
    content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    check (replacement_signal_key is null or replacement_signal_key <> signal_key),
    check (status = 'deprecated' or replacement_signal_key is null)
);

insert into content_factory.research_structural_trend_signal_types (
  signal_key, family, canonical_label, definition, content_hash
)
select seed.signal_key, seed.family, seed.canonical_label, seed.definition,
       content_factory_private.json_hash(jsonb_build_object(
         'signal_key', seed.signal_key,
         'family', seed.family,
         'canonical_label', seed.canonical_label,
         'definition', seed.definition,
         'catalog_version', 1
       ))
from (values
  ('hook.problem_first', 'hook', 'Проблема в начале',
   'Абстрактный хук, который сначала обозначает задачу или боль аудитории.'),
  ('hook.result_first', 'hook', 'Результат в начале',
   'Абстрактный хук, который сначала показывает проверяемый итог или целевое состояние.'),
  ('format.single_action_demo', 'format', 'Демонстрация одного действия',
   'Формат с одним ясным действием и одним наблюдаемым результатом без копирования чужого сценария.'),
  ('format.step_by_step', 'format', 'Пошаговый формат',
   'Формат, который объясняет задачу через короткую последовательность обобщённых шагов.'),
  ('format.comparison', 'format', 'Сравнение',
   'Формат сравнения двух подходов, состояний или вариантов по заранее понятному критерию.'),
  ('format.unboxing', 'format', 'Распаковка',
   'Формат первого знакомства с комплектацией и назначением продукта без чужих фраз или кадров.'),
  ('format.creator_explainer', 'format', 'Объяснение автора',
   'Формат, где автор своими словами кратко объясняет сценарий использования или выбора.'),
  ('proof.product_in_use', 'proof', 'Продукт в использовании',
   'Доказательная структура, показывающая продукт в реальном безопасном сценарии применения.'),
  ('proof.before_after', 'proof', 'До и после',
   'Структура сопоставления исходного и итогового состояния с явными ограничениями достоверности.'),
  ('proof.social_proof', 'proof', 'Социальное доказательство',
   'Структура, которая обобщает проверяемый опыт пользователей без копирования отзывов или имён.'),
  ('offer.bundle', 'offer', 'Набор',
   'Структура предложения, где несколько совместимых элементов объединены в один понятный сценарий.'),
  ('offer.price_anchor', 'offer', 'Ценовой якорь',
   'Структура предложения, которая даёт проверяемый контекст цены без манипулятивных или ложных сравнений.'),
  ('channel.marketplace_native_video', 'channel', 'Нативное видео маркетплейса',
   'Канальный сигнал о роликах, созданных для нативного карточного или ленточного формата маркетплейса.'),
  ('channel.short_vertical_video', 'channel', 'Короткое вертикальное видео',
   'Канальный сигнал о коротком вертикальном формате, адаптированном к быстрому мобильному просмотру.')
) seed(signal_key, family, canonical_label, definition)
on conflict (signal_key) do nothing;

create table if not exists content_factory.research_watchlist_snapshot_trend_signals (
    organization_id uuid not null,
    snapshot_id uuid not null,
    run_id uuid not null,
    product_id uuid not null,
    binding_id uuid,
    market_category_id uuid,
    signal_key text not null,
    signal_catalog_version integer not null check (
      signal_catalog_version between 1 and 100000
    ),
    direction text not null check (
      direction in ('emerging', 'growing', 'stable', 'declining', 'unclear')
    ),
    confidence text not null check (confidence in ('low', 'medium', 'high')),
    recommended_use text not null check (
      recommended_use in ('test', 'monitor', 'avoid')
    ),
    evidence_hash text not null check (evidence_hash ~ '^[0-9a-f]{64}$'),
    source_ids_hash text not null check (source_ids_hash ~ '^[0-9a-f]{64}$'),
    observed_at timestamptz not null,
    created_at timestamptz not null default now(),
    primary key (organization_id, snapshot_id, signal_key),
    constraint research_snapshot_trends_org_snapshot_signal_run_uq
      unique (organization_id, snapshot_id, signal_key, run_id),
    foreign key (organization_id, snapshot_id, run_id)
      references content_factory.research_watchlist_snapshots(
        organization_id, id, run_id
      ),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, product_id, binding_id, market_category_id)
      references content_factory.research_product_market_category_bindings(
        organization_id, product_id, id, category_id
      ),
    foreign key (signal_key)
      references content_factory.research_structural_trend_signal_types(signal_key),
    check ((binding_id is null) = (market_category_id is null))
);

create index if not exists research_snapshot_trends_timeline_idx
  on content_factory.research_watchlist_snapshot_trend_signals
  (organization_id, product_id, signal_key, observed_at desc, snapshot_id desc);

create table if not exists content_factory.research_watchlist_snapshot_trend_signal_sources (
    organization_id uuid not null,
    snapshot_id uuid not null,
    signal_key text not null,
    run_id uuid not null,
    source_id uuid not null,
    ordinal integer not null check (ordinal between 1 and 100),
    created_at timestamptz not null default now(),
    primary key (organization_id, snapshot_id, signal_key, source_id),
    unique (organization_id, snapshot_id, signal_key, ordinal),
    foreign key (organization_id, snapshot_id, signal_key, run_id)
      references content_factory.research_watchlist_snapshot_trend_signals(
        organization_id, snapshot_id, signal_key, run_id
      ),
    foreign key (organization_id, run_id, source_id)
      references content_factory.product_research_sources(
        organization_id, run_id, id
      )
);

create index if not exists research_snapshot_trend_sources_source_idx
  on content_factory.research_watchlist_snapshot_trend_signal_sources
  (organization_id, run_id, source_id, snapshot_id, signal_key);

alter table content_factory.research_market_categories enable row level security;
alter table content_factory.research_market_category_aliases enable row level security;
alter table content_factory.research_product_market_category_bindings enable row level security;
alter table content_factory.research_structural_trend_signal_types enable row level security;
alter table content_factory.research_watchlist_snapshot_trend_signals enable row level security;
alter table content_factory.research_watchlist_snapshot_trend_signal_sources enable row level security;

revoke all on content_factory.research_market_categories
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_market_category_aliases
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_product_market_category_bindings
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_structural_trend_signal_types
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_watchlist_snapshot_trend_signals
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_watchlist_snapshot_trend_signal_sources
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.reject_research_market_identity_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = tg_table_name || '_append_only';
end;
$$;

create trigger reject_research_market_category_mutation
before update or delete on content_factory.research_market_categories
for each row execute function
  content_factory_private.reject_research_market_identity_mutation();

create trigger reject_research_market_alias_mutation
before update or delete on content_factory.research_market_category_aliases
for each row execute function
  content_factory_private.reject_research_market_identity_mutation();

create trigger reject_research_market_binding_mutation
before update or delete on content_factory.research_product_market_category_bindings
for each row execute function
  content_factory_private.reject_research_market_identity_mutation();

create trigger reject_research_structural_signal_mutation
before update or delete on content_factory.research_structural_trend_signal_types
for each row execute function
  content_factory_private.reject_research_market_identity_mutation();

create trigger reject_research_snapshot_trend_mutation
before update or delete on content_factory.research_watchlist_snapshot_trend_signals
for each row execute function
  content_factory_private.reject_research_market_identity_mutation();

create trigger reject_research_snapshot_trend_source_mutation
before update or delete on content_factory.research_watchlist_snapshot_trend_signal_sources
for each row execute function
  content_factory_private.reject_research_market_identity_mutation();

create or replace function content_factory_private.research_market_category_candidate(
  organization_id_value uuid,
  run_id_value uuid
)
returns jsonb
language sql
stable
set search_path = ''
as $$
  select jsonb_build_object(
    'run_id', draft.run_id,
    'draft_id', draft.id,
    'candidate_hash', content_factory_private.json_hash(
      draft.brief -> 'category_analysis'
    ),
    'category_name', draft.brief #>> '{category_analysis,category_name}',
    'definition', draft.brief #>> '{category_analysis,definition}',
    'maturity', draft.brief #>> '{category_analysis,maturity}'
  )
  from content_factory.creative_brief_drafts draft
  join content_factory.product_research_runs source_run
    on source_run.organization_id = draft.organization_id
   and source_run.id = draft.run_id
  where draft.organization_id = $1
    and draft.run_id = $2
    and jsonb_typeof(draft.brief -> 'category_analysis') = 'object'
    and length(btrim(coalesce(
      draft.brief #>> '{category_analysis,category_name}', ''
    ))) between 2 and 160
    and not exists (
      select 1
      from content_factory.creative_brief_drafts newer_draft
      join content_factory.product_research_runs newer_run
        on newer_run.organization_id = newer_draft.organization_id
       and newer_run.id = newer_draft.run_id
      where newer_draft.organization_id = draft.organization_id
        and newer_run.product_id = source_run.product_id
        and (newer_draft.created_at, newer_draft.id)
          > (draft.created_at, draft.id)
    )
  order by draft.version desc, draft.created_at desc, draft.id desc
  limit 1
$$;

create or replace function content_factory_private.capture_research_snapshot_canonical_trends(
  snapshot_id_value uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  snapshot_row content_factory.research_watchlist_snapshots%rowtype;
  binding_row content_factory.research_product_market_category_bindings%rowtype;
  signal_item jsonb;
  signal_key_value text;
  direction_value text;
  confidence_value text;
  recommended_use_value text;
  evidence_value text;
  source_ids_value jsonb;
  canonical_source_ids jsonb;
  source_count_value integer;
  catalog_version_value integer;
  keyed_count integer;
  distinct_key_count integer;
begin
  select snapshot.* into snapshot_row
  from content_factory.research_watchlist_snapshots snapshot
  where snapshot.id = snapshot_id_value;
  if snapshot_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_watchlist_snapshot_not_found';
  end if;
  if jsonb_typeof(snapshot_row.trend_analysis -> 'signals') <> 'array' then
    return;
  end if;

  select count(*)::integer,
         count(distinct btrim(item.value ->> 'signal_key'))::integer
    into keyed_count, distinct_key_count
  from jsonb_array_elements(snapshot_row.trend_analysis -> 'signals') item(value)
  where item.value ? 'signal_key';
  if keyed_count <> distinct_key_count then
    raise exception using
      errcode = '22023', message = 'canonical_trend_signal_duplicate';
  end if;

  select binding.* into binding_row
  from content_factory.research_product_market_category_bindings binding
  where binding.organization_id = snapshot_row.organization_id
    and binding.product_id = snapshot_row.product_id
  order by binding.binding_version desc, binding.id desc
  limit 1;

  for signal_item in
    select item.value
    from jsonb_array_elements(snapshot_row.trend_analysis -> 'signals') item(value)
    where item.value ? 'signal_key'
  loop
    if jsonb_typeof(signal_item -> 'signal_key') <> 'string' then
      raise exception using
        errcode = '22023', message = 'canonical_trend_signal_key_invalid';
    end if;
    signal_key_value := btrim(signal_item ->> 'signal_key');
    if signal_key_value = '' then
      raise exception using
        errcode = '22023', message = 'canonical_trend_signal_key_invalid';
    end if;

    select catalog.catalog_version into catalog_version_value
    from content_factory.research_structural_trend_signal_types catalog
    where catalog.signal_key = signal_key_value
      and catalog.status = 'active';
    if catalog_version_value is null then
      raise exception using
        errcode = '22023', message = 'canonical_trend_signal_not_allowlisted';
    end if;

    direction_value := btrim(coalesce(signal_item ->> 'direction', ''));
    confidence_value := btrim(coalesce(signal_item ->> 'confidence', ''));
    recommended_use_value := btrim(coalesce(
      signal_item ->> 'recommended_use', ''
    ));
    evidence_value := btrim(coalesce(signal_item ->> 'evidence', ''));
    source_ids_value := signal_item -> 'source_ids';
    if direction_value not in (
         'emerging', 'growing', 'stable', 'declining', 'unclear'
       )
       or confidence_value not in ('low', 'medium', 'high')
       or recommended_use_value not in ('test', 'monitor', 'avoid')
       or length(evidence_value) not between 3 and 2000
       or jsonb_typeof(source_ids_value) <> 'array'
       or jsonb_array_length(source_ids_value) not between 1 and 100 then
      raise exception using
        errcode = '22023', message = 'canonical_trend_signal_payload_invalid';
    end if;
    if exists (
      select 1
      from jsonb_array_elements(source_ids_value) source_ref(value)
      where jsonb_typeof(source_ref.value) <> 'string'
    ) then
      raise exception using
        errcode = '22023', message = 'canonical_trend_signal_source_invalid';
    end if;

    begin
      perform source_ref.value::uuid
      from jsonb_array_elements_text(source_ids_value) source_ref(value);
    exception when invalid_text_representation then
      raise exception using
        errcode = '22023', message = 'canonical_trend_signal_source_invalid';
    end;
    select count(distinct source_ref.value)::integer
      into source_count_value
    from jsonb_array_elements_text(source_ids_value) source_ref(value);
    if source_count_value <> jsonb_array_length(source_ids_value) then
      raise exception using
        errcode = '22023', message = 'canonical_trend_signal_source_duplicate';
    end if;
    if exists (
      select 1
      from jsonb_array_elements_text(source_ids_value) source_ref(value)
      where not exists (
        select 1
        from jsonb_array_elements_text(snapshot_row.source_ids) snapshot_source(value)
        where snapshot_source.value = source_ref.value
      )
    ) then
      raise exception using
        errcode = '42501', message = 'canonical_trend_signal_source_mismatch';
    end if;

    select count(*)::integer,
           jsonb_agg(source.id::text order by source.id::text)
      into source_count_value, canonical_source_ids
    from jsonb_array_elements_text(source_ids_value) source_ref(value)
    join content_factory.product_research_sources source
      on source.organization_id = snapshot_row.organization_id
     and source.run_id = snapshot_row.run_id
     and source.product_id = snapshot_row.product_id
     and source.id = source_ref.value::uuid;
    if source_count_value <> jsonb_array_length(source_ids_value) then
      raise exception using
        errcode = '42501', message = 'canonical_trend_signal_source_mismatch';
    end if;

    insert into content_factory.research_watchlist_snapshot_trend_signals (
      organization_id, snapshot_id, run_id, product_id, binding_id,
      market_category_id, signal_key, signal_catalog_version, direction,
      confidence, recommended_use, evidence_hash, source_ids_hash, observed_at
    ) values (
      snapshot_row.organization_id,
      snapshot_row.id,
      snapshot_row.run_id,
      snapshot_row.product_id,
      binding_row.id,
      binding_row.category_id,
      signal_key_value,
      catalog_version_value,
      direction_value,
      confidence_value,
      recommended_use_value,
      content_factory_private.json_hash(to_jsonb(evidence_value)),
      content_factory_private.json_hash(canonical_source_ids),
      snapshot_row.observed_at
    ) on conflict (organization_id, snapshot_id, signal_key) do nothing;

    insert into content_factory.research_watchlist_snapshot_trend_signal_sources (
      organization_id, snapshot_id, signal_key, run_id, source_id, ordinal
    )
    select
      snapshot_row.organization_id,
      snapshot_row.id,
      signal_key_value,
      snapshot_row.run_id,
      source.id,
      source_ref.ordinality::integer
    from jsonb_array_elements_text(source_ids_value)
      with ordinality source_ref(value, ordinality)
    join content_factory.product_research_sources source
      on source.organization_id = snapshot_row.organization_id
     and source.run_id = snapshot_row.run_id
     and source.product_id = snapshot_row.product_id
     and source.id = source_ref.value::uuid
    order by source_ref.ordinality
    on conflict (organization_id, snapshot_id, signal_key, source_id)
      do nothing;
  end loop;
end;
$$;

create or replace function content_factory_private.capture_research_snapshot_canonical_trends_trigger()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform content_factory_private.capture_research_snapshot_canonical_trends(
    new.id
  );
  return new;
end;
$$;

create trigger capture_research_snapshot_canonical_trends
after insert on content_factory.research_watchlist_snapshots
for each row execute function
  content_factory_private.capture_research_snapshot_canonical_trends_trigger();

do $backfill$
declare
  snapshot_record record;
begin
  for snapshot_record in
    select snapshot.id
    from content_factory.research_watchlist_snapshots snapshot
    where jsonb_typeof(snapshot.trend_analysis -> 'signals') = 'array'
      and exists (
        select 1
        from jsonb_array_elements(snapshot.trend_analysis -> 'signals') item(value)
        where item.value ? 'signal_key'
      )
    order by snapshot.created_at, snapshot.id
  loop
    perform content_factory_private.capture_research_snapshot_canonical_trends(
      snapshot_record.id
    );
  end loop;
end;
$backfill$;

create or replace function public.creator_research_market_category_registry(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  actor_role text;
  organization_id uuid;
  run_id_value uuid;
  product_id_value uuid;
  query_value text;
  query_key_value text;
  limit_value integer := 20;
  timeline_limit_value integer := 24;
  numeric_value numeric;
  candidate_value jsonb;
  current_binding_value jsonb;
  categories_value jsonb := '[]'::jsonb;
  timeline_value jsonb := '[]'::jsonb;
  guidance_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'run_id', 'query', 'limit', 'timeline_limit'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_market_registry_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  if p_payload ? 'query' then
    query_value := content_factory_private.require_text(p_payload, 'query', 2, 160);
    query_key_value :=
      content_factory_private.research_market_identity_key(query_value);
  end if;
  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number' then
      raise exception using
        errcode = '22023', message = 'research_market_registry_limit_invalid';
    end if;
    begin
      numeric_value := (p_payload ->> 'limit')::numeric;
    exception when others then
      raise exception using
        errcode = '22023', message = 'research_market_registry_limit_invalid';
    end;
    if numeric_value <> trunc(numeric_value) or numeric_value not between 1 and 20 then
      raise exception using
        errcode = '22023', message = 'research_market_registry_limit_invalid';
    end if;
    limit_value := numeric_value::integer;
  end if;
  if p_payload ? 'timeline_limit' then
    if jsonb_typeof(p_payload -> 'timeline_limit') <> 'number' then
      raise exception using
        errcode = '22023', message = 'research_market_timeline_limit_invalid';
    end if;
    begin
      numeric_value := (p_payload ->> 'timeline_limit')::numeric;
    exception when others then
      raise exception using
        errcode = '22023', message = 'research_market_timeline_limit_invalid';
    end;
    if numeric_value <> trunc(numeric_value) or numeric_value not between 1 and 24 then
      raise exception using
        errcode = '22023', message = 'research_market_timeline_limit_invalid';
    end if;
    timeline_limit_value := numeric_value::integer;
  end if;

  select run.product_id into product_id_value
  from content_factory.product_research_runs run
  join content_factory.organizations organization
    on organization.id = run.organization_id
   and organization.status = 'active'
  join content_factory.memberships membership
    on membership.organization_id = run.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where run.organization_id = organization_id
    and run.id = run_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  actor_role := content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );

  candidate_value := content_factory_private.research_market_category_candidate(
    organization_id, run_id_value
  );

  select jsonb_build_object(
    'binding_id', binding.id,
    'binding_version', binding.binding_version,
    'category_key', category.id,
    'canonical_name', category.canonical_name,
    'definition', category.definition,
    'decision_action', binding.decision_action,
    'source_run_id', binding.source_run_id,
    'source_draft_id', binding.source_draft_id,
    'candidate_hash', binding.candidate_hash,
    'confirmed_by', binding.confirmed_by,
    'confirmed_at', binding.confirmed_at
  ) into current_binding_value
  from content_factory.research_product_market_category_bindings binding
  join content_factory.research_market_categories category
    on category.organization_id = binding.organization_id
   and category.id = binding.category_id
  where binding.organization_id = organization_id
    and binding.product_id = product_id_value
  order by binding.binding_version desc, binding.id desc
  limit 1;

  select coalesce(jsonb_agg(jsonb_build_object(
    'category_key', category.id,
    'canonical_name', category.canonical_name,
    'definition', category.definition,
    'status', category.status,
    'aliases', (
      select coalesce(jsonb_agg(alias.alias_value order by alias.normalized_alias), '[]'::jsonb)
      from content_factory.research_market_category_aliases alias
      where alias.organization_id = organization_id
        and alias.category_id = category.id
    ),
    'created_at', category.created_at
  ) order by category.created_at desc, category.id desc), '[]'::jsonb)
    into categories_value
  from (
    select bounded_category.*
    from content_factory.research_market_categories bounded_category
    where bounded_category.organization_id = organization_id
      and bounded_category.status = 'active'
      and (
        query_key_value is null
        or exists (
          select 1
          from content_factory.research_market_category_aliases exact_alias
          where exact_alias.organization_id = organization_id
            and exact_alias.category_id = bounded_category.id
            and exact_alias.normalized_alias = query_key_value
        )
      )
    order by bounded_category.created_at desc, bounded_category.id desc
    limit limit_value
  ) category;

  with ordered as (
    select
      observation.*,
      lag(observation.market_category_id) over (
        partition by observation.signal_key
        order by observation.observed_at, observation.snapshot_id
      ) as previous_category_id,
      lag(observation.direction) over (
        partition by observation.signal_key
        order by observation.observed_at, observation.snapshot_id
      ) as previous_direction
    from content_factory.research_watchlist_snapshot_trend_signals observation
    where observation.organization_id = organization_id
      and observation.product_id = product_id_value
  ), bounded as (
    select ordered.*
    from ordered
    order by ordered.observed_at desc, ordered.snapshot_id desc, ordered.signal_key
    limit timeline_limit_value
  ), compared as (
    select bounded.*,
      case
        when bounded.previous_direction is null then 'baseline'
        when bounded.market_category_id is null
          or bounded.previous_category_id is null then 'canonical_reset'
        when bounded.market_category_id is distinct from bounded.previous_category_id
          then 'category_reset'
        else 'comparable'
      end as comparison_mode
    from bounded
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'snapshot_id', compared.snapshot_id,
    'run_id', compared.run_id,
    'observed_at', compared.observed_at,
    'binding_id', compared.binding_id,
    'category_key', compared.market_category_id,
    'category_name', category.canonical_name,
    'signal_key', compared.signal_key,
    'signal_catalog_version', compared.signal_catalog_version,
    'canonical_label', catalog.canonical_label,
    'direction', compared.direction,
    'previous_direction', compared.previous_direction,
    'confidence', compared.confidence,
    'recommended_use', compared.recommended_use,
    'comparison_mode', compared.comparison_mode,
    'direction_changed', (
      compared.comparison_mode = 'comparable'
      and compared.previous_direction is distinct from compared.direction
    ),
    'potential_contradiction', (
      compared.comparison_mode = 'comparable'
      and (
        (compared.previous_direction in ('emerging', 'growing')
          and compared.direction = 'declining')
        or (compared.previous_direction = 'declining'
          and compared.direction in ('emerging', 'growing'))
      )
    ),
    'source_count', (
      select count(*)::integer
      from content_factory.research_watchlist_snapshot_trend_signal_sources source_link
      where source_link.organization_id = compared.organization_id
        and source_link.snapshot_id = compared.snapshot_id
        and source_link.signal_key = compared.signal_key
    )
  ) order by compared.observed_at desc, compared.snapshot_id desc, compared.signal_key), '[]'::jsonb)
    into timeline_value
  from compared
  join content_factory.research_structural_trend_signal_types catalog
    on catalog.signal_key = compared.signal_key
  left join content_factory.research_market_categories category
    on category.organization_id = compared.organization_id
   and category.id = compared.market_category_id;

  guidance_value := jsonb_build_object(
    'status', case
      when current_binding_value is null and candidate_value is null
        then 'needs_research_evidence'
      when current_binding_value is null then 'needs_user_decision'
      else 'ready'
    end,
    'recommended_next_step', case
      when current_binding_value is null and candidate_value is null
        then 'complete_product_research'
      when current_binding_value is null then 'confirm_market_category'
      else 'continue_with_bound_category'
    end,
    'category_decision_requires_confirmation', true,
    'paid_provider_action', false
  );

  return jsonb_build_object(
    'ok', true,
    'can_resolve', actor_role in ('owner', 'admin', 'producer'),
    'product_id', product_id_value,
    'current_binding', current_binding_value,
    'candidate', candidate_value,
    'categories', categories_value,
    'trend_timeline', timeline_value,
    'guidance', guidance_value
  );
end;
$$;

create or replace function public.creator_resolve_research_market_category(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  run_id_value uuid;
  product_id_value uuid;
  action_value text;
  candidate_hash_value text;
  category_id_value uuid;
  canonical_name_value text;
  normalized_name_value text;
  definition_value text;
  aliases_value jsonb := '[]'::jsonb;
  reason_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  candidate_value jsonb;
  current_binding content_factory.research_product_market_category_bindings%rowtype;
  category_row content_factory.research_market_categories%rowtype;
  binding_row content_factory.research_product_market_category_bindings%rowtype;
  alias_item jsonb;
  alias_text_value text;
  alias_key_value text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'run_id', 'action', 'candidate_hash', 'category_id',
    'canonical_name', 'definition', 'aliases', 'confirmation', 'reason',
    'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_market_decision_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  action_value := content_factory_private.require_text(p_payload, 'action', 10, 24);
  if action_value not in (
    'bind_existing', 'create_and_bind', 'reclassify',
    'create_and_reclassify'
  ) then
    raise exception using
      errcode = '22023', message = 'research_market_decision_action_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'confirmation') <> 'boolean'
     or p_payload -> 'confirmation' <> 'true'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_market_decision_confirmation_required';
  end if;
  candidate_hash_value := content_factory_private.require_text(
    p_payload, 'candidate_hash', 64, 64
  );
  if candidate_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023', message = 'candidate_hash_invalid';
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if p_payload ? 'reason' then
    reason_value := content_factory_private.require_text(p_payload, 'reason', 3, 500);
  end if;

  if action_value in ('create_and_bind', 'create_and_reclassify') then
    if p_payload ? 'category_id' then
      raise exception using
        errcode = '22023', message = 'research_market_decision_action_payload_invalid';
    end if;
    canonical_name_value := content_factory_private.require_text(
      p_payload, 'canonical_name', 2, 160
    );
    definition_value := content_factory_private.require_text(
      p_payload, 'definition', 10, 2000
    );
    normalized_name_value :=
      content_factory_private.research_market_identity_key(canonical_name_value);
    if length(normalized_name_value) not between 2 and 160 then
      raise exception using
        errcode = '22023', message = 'canonical_name_invalid';
    end if;
    if p_payload ? 'aliases' then
      aliases_value := p_payload -> 'aliases';
      if jsonb_typeof(aliases_value) <> 'array'
         or jsonb_array_length(aliases_value) > 10 then
        raise exception using
          errcode = '22023', message = 'research_market_aliases_invalid';
      end if;
      for alias_item in select item.value from jsonb_array_elements(aliases_value) item(value)
      loop
        if jsonb_typeof(alias_item) <> 'string' then
          raise exception using
            errcode = '22023', message = 'research_market_aliases_invalid';
        end if;
        alias_text_value := btrim(alias_item #>> '{}');
        alias_key_value :=
          content_factory_private.research_market_identity_key(alias_text_value);
        if length(alias_text_value) not between 2 and 160
           or length(alias_key_value) not between 2 and 160 then
          raise exception using
            errcode = '22023', message = 'research_market_aliases_invalid';
        end if;
      end loop;
    end if;
  else
    if p_payload ? 'canonical_name' or p_payload ? 'definition' or p_payload ? 'aliases' then
      raise exception using
        errcode = '22023', message = 'research_market_decision_action_payload_invalid';
    end if;
    category_id_value := content_factory_private.require_uuid(
      p_payload, 'category_id'
    );
  end if;

  select run.product_id into product_id_value
  from content_factory.product_research_runs run
  join content_factory.organizations organization
    on organization.id = run.organization_id
   and organization.status = 'active'
  join content_factory.memberships membership
    on membership.organization_id = run.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where run.organization_id = organization_id
    and run.id = run_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer']
  );

  request_payload := p_payload - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_resolve_research_market_category',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('research-market-category-registry')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('research-market-product:' || product_id_value::text)
  );

  candidate_value := content_factory_private.research_market_category_candidate(
    organization_id, run_id_value
  );
  if candidate_value is null
     or candidate_value ->> 'candidate_hash' <> candidate_hash_value then
    raise exception using
      errcode = '55000', message = 'research_market_category_candidate_stale';
  end if;

  select binding.* into current_binding
  from content_factory.research_product_market_category_bindings binding
  where binding.organization_id = organization_id
    and binding.product_id = product_id_value
  order by binding.binding_version desc, binding.id desc
  limit 1
  for update;

  if action_value in ('bind_existing', 'create_and_bind')
     and current_binding.id is not null then
    raise exception using
      errcode = '55000', message = 'research_market_category_reclassify_required';
  end if;
  if action_value in ('reclassify', 'create_and_reclassify')
     and current_binding.id is null then
    raise exception using
      errcode = '55000', message = 'research_market_category_binding_required';
  end if;

  if action_value in ('create_and_bind', 'create_and_reclassify') then
    if exists (
      select 1
      from content_factory.research_market_category_aliases existing_alias
      where existing_alias.organization_id = organization_id
        and existing_alias.normalized_alias in (
          select distinct proposed.normalized_alias
          from (
            select normalized_name_value as normalized_alias
            union all
            select content_factory_private.research_market_identity_key(item.value)
            from jsonb_array_elements_text(aliases_value) item(value)
          ) proposed
        )
    ) then
      raise exception using
        errcode = '23505', message = 'research_market_category_alias_conflict';
    end if;

    insert into content_factory.research_market_categories (
      organization_id, canonical_name, normalized_name, definition, created_by
    ) values (
      organization_id, canonical_name_value, normalized_name_value,
      definition_value, user_id
    ) returning * into category_row;

    insert into content_factory.research_market_category_aliases (
      organization_id, category_id, alias_value, normalized_alias, created_by
    )
    select organization_id, category_row.id, proposed.alias_value,
           proposed.normalized_alias, user_id
    from (
      select distinct on (normalized_alias) alias_value, normalized_alias
      from (
        select canonical_name_value as alias_value,
               normalized_name_value as normalized_alias,
               0 as priority
        union all
        select btrim(item.value) as alias_value,
               content_factory_private.research_market_identity_key(item.value)
                 as normalized_alias,
               1 as priority
        from jsonb_array_elements_text(aliases_value) item(value)
      ) all_aliases
      order by normalized_alias, priority, alias_value
    ) proposed;
    category_id_value := category_row.id;
  else
    select category.* into category_row
    from content_factory.research_market_categories category
    where category.organization_id = organization_id
      and category.id = category_id_value
      and category.status = 'active';
    if category_row.id is null then
      raise exception using
        errcode = '22023', message = 'research_market_category_not_found';
    end if;
  end if;

  if action_value = 'reclassify'
     and current_binding.category_id = category_id_value then
    raise exception using
      errcode = '55000', message = 'research_market_category_unchanged';
  end if;

  insert into content_factory.research_product_market_category_bindings (
    organization_id, product_id, category_id, previous_binding_id,
    binding_version, decision_action, source_run_id, source_draft_id,
    candidate_hash, reason, confirmed_by, idempotency_key
  ) values (
    organization_id,
    product_id_value,
    category_id_value,
    current_binding.id,
    coalesce(current_binding.binding_version, 0) + 1,
    action_value,
    run_id_value,
    (candidate_value ->> 'draft_id')::uuid,
    candidate_hash_value,
    reason_value,
    user_id,
    idempotency_key_value
  ) returning * into binding_row;

  if category_row.id is null then
    select category.* into category_row
    from content_factory.research_market_categories category
    where category.organization_id = organization_id
      and category.id = category_id_value;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'category', jsonb_build_object(
      'category_key', category_row.id,
      'canonical_name', category_row.canonical_name,
      'definition', category_row.definition,
      'status', category_row.status,
      'aliases', (
        select coalesce(jsonb_agg(alias.alias_value order by alias.normalized_alias), '[]'::jsonb)
        from content_factory.research_market_category_aliases alias
        where alias.organization_id = organization_id
          and alias.category_id = category_row.id
      )
    ),
    'binding', jsonb_build_object(
      'binding_id', binding_row.id,
      'binding_version', binding_row.binding_version,
      'product_id', binding_row.product_id,
      'category_key', binding_row.category_id,
      'previous_binding_id', binding_row.previous_binding_id,
      'decision_action', binding_row.decision_action,
      'source_run_id', binding_row.source_run_id,
      'source_draft_id', binding_row.source_draft_id,
      'candidate_hash', binding_row.candidate_hash,
      'confirmed_by', binding_row.confirmed_by,
      'confirmed_at', binding_row.confirmed_at
    ),
    'guidance', jsonb_build_object(
      'status', 'bound',
      'recommended_next_step', 'continue_with_bound_category',
      'confirmation_received', true,
      'paid_provider_action', false
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'research_market_category_resolved',
    'research_market_category_binding',
    binding_row.id::text,
    jsonb_build_object(
      'action', action_value,
      'product_id', product_id_value,
      'category_key', category_id_value,
      'run_id', run_id_value,
      'candidate_hash', candidate_hash_value,
      'paid_provider_action', false
    ),
    'research-market-category:' || idempotency_key_value
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_resolve_research_market_category',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function public.creator_research_market_category_registry(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_resolve_research_market_category(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_research_market_category_registry(jsonb)
  to authenticated;
grant execute on function public.creator_resolve_research_market_category(jsonb)
  to authenticated;

revoke all on function
  content_factory_private.research_market_identity_key(text)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.reject_research_market_identity_mutation()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_market_category_candidate(uuid, uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.capture_research_snapshot_canonical_trends(uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.capture_research_snapshot_canonical_trends_trigger()
  from public, anon, authenticated, service_role;

select pg_notify('pgrst', 'reload schema');

commit;
