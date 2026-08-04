begin;

-- Historical outcome imports are a bounded, append-only evidence satellite.
-- Raw, pending, rejected, review-only, and quarantined rows never enter a
-- prompt or selection.  An explicitly confirmed, exact-product aggregate may
-- advise generation only after the bounded two-case/tie guards below; it never
-- mutates ai_effective_category_policies, starts a provider, or changes spend.

create unique index if not exists ai_knowledge_source_org_id_uq
  on content_factory.ai_category_knowledge_sources (organization_id, id);

create table if not exists content_factory.ai_historical_case_import_batches (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    source_id uuid not null,
    default_product_category text not null check (default_product_category in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )),
    original_filename text not null
      check (length(btrim(original_filename)) between 1 and 240),
    source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
    schema_version text not null check (schema_version = 'ai_historical_cases.v1'),
    parser_version text not null check (
      length(parser_version) between 1 and 80
      and parser_version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$'
    ),
    manifest_sha256 text not null check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    batch_index integer not null check (batch_index between 1 and 100),
    batch_count integer not null check (
      batch_count between 1 and 100 and batch_index <= batch_count
    ),
    parsed_row_count integer not null check (parsed_row_count between 1 and 5000000),
    parser_quarantined_row_count integer not null check (
      parser_quarantined_row_count between 0 and parsed_row_count
    ),
    parser_quarantine_summary jsonb not null check (
      jsonb_typeof(parser_quarantine_summary) = 'object'
      and pg_column_size(parser_quarantine_summary) <= 4096
    ),
    case_count integer not null check (
      case_count between 0 and 200 and parsed_row_count >= case_count
    ),
    matched_case_count integer not null check (
      matched_case_count between 0 and case_count
    ),
    quarantined_case_count integer not null check (
      quarantined_case_count between 0 and case_count
      and matched_case_count + quarantined_case_count = case_count
    ),
    good_case_count integer not null check (good_case_count between 0 and case_count),
    bad_case_count integer not null check (bad_case_count between 0 and case_count),
    review_case_count integer not null check (
      review_case_count between 0 and case_count
      and good_case_count + bad_case_count + review_case_count = case_count
    ),
    per_category_summary jsonb not null check (
      jsonb_typeof(per_category_summary) = 'object'
      and pg_column_size(per_category_summary) <= 8192
    ),
    import_status text not null check (import_status in (
      'completed', 'completed_with_quarantine', 'quarantined',
      'parser_rejected'
    )),
    imported_by uuid not null,
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null
      check (length(idempotency_key) between 8 and 180),
    event_cursor bigint not null default nextval(
      'content_factory.ai_learning_event_cursor_seq'::regclass
    ) check (event_cursor > 0),
    created_at timestamptz not null default now(),
    foreign key (organization_id, source_id)
      references content_factory.ai_category_knowledge_sources(
        organization_id, id
      ),
    foreign key (organization_id, imported_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, id),
    unique (organization_id, idempotency_key),
    unique (organization_id, source_id, manifest_sha256, batch_index),
    unique (event_cursor)
);

create index if not exists ai_historical_batch_source_page_idx
  on content_factory.ai_historical_case_import_batches (
    organization_id, source_id, event_cursor desc
  );

create table if not exists content_factory.ai_historical_case_events (
    id uuid primary key default extensions.gen_random_uuid(),
    case_id uuid not null default extensions.gen_random_uuid(),
    batch_id uuid not null,
    organization_id uuid not null,
    source_id uuid not null,
    product_category text not null check (product_category in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )),
    external_case_id text not null check (
      length(btrim(external_case_id)) between 1 and 180
      and external_case_id !~ '[[:cntrl:]]'
    ),
    product_id uuid,
    requested_product_id text check (
      requested_product_id is null
      or length(requested_product_id) between 1 and 80
    ),
    product_sku text check (
      product_sku is null or length(product_sku) between 1 and 120
    ),
    marketplace_sku text check (
      marketplace_sku is null or length(marketplace_sku) between 1 and 120
    ),
    product_title text not null check (
      length(btrim(product_title)) between 2 and 240
      and product_title !~ '[[:cntrl:]]'
    ),
    brand text not null check (
      length(btrim(brand)) between 1 and 120
      and brand !~ '[[:cntrl:]]'
    ),
    platform text not null check (
      length(platform) between 1 and 40
      and platform ~ '^[a-z0-9][a-z0-9_.:-]{0,39}$'
    ),
    channel text not null check (
      length(channel) between 1 and 60
      and channel ~ '^[a-z0-9][a-z0-9_.:-]{0,59}$'
    ),
    period_start date not null,
    period_end date not null check (
      period_end >= period_start
      and period_end <= period_start + 3660
    ),
    outcome text not null check (outcome in ('good', 'bad', 'review')),
    outcome_dimension text not null check (outcome_dimension in (
      'overall', 'overall_performance', 'sales', 'orders', 'conversion',
      'organic_growth', 'buyout', 'engagement',
      'cart_to_order', 'visit_to_cart', 'visit_to_order', 'sale_per_view',
      'revenue', 'profitability', 'ad_efficiency', 'advertising_efficiency',
      'product_card_conversion', 'inventory', 'evidence_sufficiency',
      'content_conversion', 'purchase_transition', 'attribution_window',
      'product_mapping', 'funnel', 'attribution', 'creative_angle',
      'data_quality', 'other'
    )),
    status_label text not null check (
      length(btrim(status_label)) between 1 and 80
      and status_label !~ '[[:cntrl:]]'
    ),
    metrics jsonb not null check (
      jsonb_typeof(metrics) = 'object'
      and pg_column_size(metrics) <= 4096
    ),
    confidence numeric(7,6) not null check (confidence between 0 and 1),
    creative_angle text check (creative_angle is null or creative_angle in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )),
    resolution_status text not null check (resolution_status in (
      'matched', 'quarantined'
    )),
    resolution_method text check (resolution_method is null or resolution_method in (
      'exact_product_id', 'unique_product_sku', 'unique_marketplace_sku',
      'consistent_exact_references', 'source_external_sku',
      'source_marketplace_sku'
    )),
    quarantine_reason text check (quarantine_reason is null or quarantine_reason in (
      'product_reference_missing', 'product_id_invalid', 'product_id_unmatched',
      'product_sku_unmatched', 'product_sku_ambiguous',
      'marketplace_sku_unmatched', 'marketplace_sku_ambiguous',
      'product_reference_conflict', 'product_reference_partial_match'
    )),
    source_filename text not null
      check (length(btrim(source_filename)) between 1 and 240),
    source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
    source_sheet text not null check (
      length(btrim(source_sheet)) between 1 and 180
      and source_sheet !~ '[[:cntrl:]]'
    ),
    source_row integer not null check (source_row between 1 and 1048576),
    row_hash text not null check (row_hash ~ '^[0-9a-f]{64}$'),
    schema_version text not null check (schema_version = 'ai_historical_cases.v1'),
    parser_version text not null check (
      length(parser_version) between 1 and 80
      and parser_version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$'
    ),
    case_hash text not null check (case_hash ~ '^[0-9a-f]{64}$'),
    event_cursor bigint not null default nextval(
      'content_factory.ai_learning_event_cursor_seq'::regclass
    ) check (event_cursor > 0),
    created_at timestamptz not null default now(),
    foreign key (organization_id, batch_id)
      references content_factory.ai_historical_case_import_batches(
        organization_id, id
      ),
    foreign key (organization_id, source_id)
      references content_factory.ai_category_knowledge_sources(
        organization_id, id
      ),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    unique (organization_id, product_category, case_id),
    unique (batch_id, external_case_id),
    unique (organization_id, source_id, external_case_id),
    unique (organization_id, case_hash),
    unique (event_cursor),
    check (
      (resolution_status = 'matched'
        and resolution_method is not null
        and quarantine_reason is null)
      or
      (resolution_status = 'quarantined'
        and product_id is null
        and resolution_method is null
        and quarantine_reason is not null)
    )
);

create index if not exists ai_historical_case_category_page_idx
  on content_factory.ai_historical_case_events (
    organization_id, product_category, event_cursor desc
  );
create index if not exists ai_historical_case_batch_idx
  on content_factory.ai_historical_case_events (batch_id, event_cursor);
create index if not exists ai_historical_case_semantic_identity_idx
  on content_factory.ai_historical_case_events (
    organization_id, product_category, external_case_id, row_hash,
    event_cursor desc
  );
create index if not exists ai_historical_case_product_sku_lookup_idx
  on content_factory.ai_historical_case_events (organization_id, product_sku)
  where product_sku is not null;
create index if not exists ai_historical_case_marketplace_sku_lookup_idx
  on content_factory.ai_historical_case_events (
    organization_id, marketplace_sku
  )
  where marketplace_sku is not null;
create index if not exists products_org_current_wb_article_lookup_idx
  on content_factory.products (organization_id, current_wb_article)
  where current_wb_article is not null;

create table if not exists content_factory.ai_historical_case_decisions (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    product_category text not null check (product_category in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )),
    case_id uuid not null,
    decision text not null check (decision in ('confirm', 'reject')),
    reason_code text not null check (reason_code in (
      'operator_confirmed', 'operator_rejected'
    )),
    confirmation boolean not null check (confirmation),
    expected_scope_version integer not null check (expected_scope_version >= 0),
    resulting_scope_version integer not null check (
      resulting_scope_version = expected_scope_version + 1
    ),
    expected_event_id uuid not null,
    expected_event_cursor bigint not null check (expected_event_cursor > 0),
    decided_by uuid not null,
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    decision_hash text not null check (decision_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null
      check (length(idempotency_key) between 8 and 180),
    event_cursor bigint not null default nextval(
      'content_factory.ai_learning_event_cursor_seq'::regclass
    ) check (event_cursor > 0),
    created_at timestamptz not null default now(),
    foreign key (organization_id, product_category, case_id)
      references content_factory.ai_historical_case_events(
        organization_id, product_category, case_id
      ),
    foreign key (organization_id, decided_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key),
    unique (organization_id, product_category, case_id, resulting_scope_version),
    unique (organization_id, decision_hash),
    unique (event_cursor)
);

create index if not exists ai_historical_decision_head_idx
  on content_factory.ai_historical_case_decisions (
    organization_id, product_category, case_id, event_cursor desc
  );

alter table content_factory.ai_historical_case_import_batches
  enable row level security;
alter table content_factory.ai_historical_case_import_batches
  force row level security;
alter table content_factory.ai_historical_case_events
  enable row level security;
alter table content_factory.ai_historical_case_events
  force row level security;
alter table content_factory.ai_historical_case_decisions
  enable row level security;
alter table content_factory.ai_historical_case_decisions
  force row level security;

revoke all on content_factory.ai_historical_case_import_batches
  from public, anon, authenticated, service_role;
revoke all on content_factory.ai_historical_case_events
  from public, anon, authenticated, service_role;
revoke all on content_factory.ai_historical_case_decisions
  from public, anon, authenticated, service_role;

drop trigger if exists ai_historical_batch_append_only
  on content_factory.ai_historical_case_import_batches;
create trigger ai_historical_batch_append_only
before update or delete on content_factory.ai_historical_case_import_batches
for each row execute function
  content_factory_private.guard_ai_learning_append_only();

drop trigger if exists ai_historical_case_event_append_only
  on content_factory.ai_historical_case_events;
create trigger ai_historical_case_event_append_only
before update or delete on content_factory.ai_historical_case_events
for each row execute function
  content_factory_private.guard_ai_learning_append_only();

drop trigger if exists ai_historical_case_decision_append_only
  on content_factory.ai_historical_case_decisions;
create trigger ai_historical_case_decision_append_only
before update or delete on content_factory.ai_historical_case_decisions
for each row execute function
  content_factory_private.guard_ai_learning_append_only();

comment on column content_factory.ai_historical_case_import_batches.source_sha256 is
  'SHA-256 recomputed by the trusted server parser before this normalized RPC is called.';
comment on column content_factory.ai_historical_case_import_batches.request_hash is
  'Canonical raw parser chunk identity; intentionally independent of mutable product-catalog resolution.';
comment on column content_factory.ai_historical_case_events.row_hash is
  'Parser-supplied deterministic source-row lineage hash; it is evidence identity, not a prompt instruction.';

create or replace function
  content_factory_private.normalize_ai_historical_case_metrics(p_metrics jsonb)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  metric_entry record;
  metric_number numeric;
  metric_count integer := 0;
  normalized_value jsonb := '{}'::jsonb;
begin
  if p_metrics is not null and jsonb_typeof(p_metrics) = 'object' then
    select count(*)::integer
    into metric_count
    from jsonb_object_keys(p_metrics);
  end if;
  if p_metrics is null
     or jsonb_typeof(p_metrics) <> 'object'
     or metric_count < 1
     or metric_count > 20
     or pg_column_size(p_metrics) > 4096 then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_metrics_invalid';
  end if;

  for metric_entry in
    select metric.key, metric.value
    from jsonb_each(p_metrics) metric(key, value)
    order by metric.key
  loop
    if metric_entry.key !~ '^[a-z][a-z0-9_]{0,39}$'
       or jsonb_typeof(metric_entry.value) <> 'number' then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_metrics_invalid';
    end if;
    begin
      metric_number := (metric_entry.value #>> '{}')::numeric;
    exception when others then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_metrics_invalid';
    end;
    if abs(metric_number) > 1000000000000000 then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_metrics_invalid';
    end if;
    normalized_value := normalized_value ||
      jsonb_build_object(metric_entry.key, metric_number);
  end loop;

  return normalized_value;
end;
$$;

revoke all on function
  content_factory_private.normalize_ai_historical_case_metrics(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.normalize_ai_historical_parser_quarantine(
    p_summary jsonb
  )
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  summary_entry record;
  summary_count integer := 0;
  row_count_value integer;
  normalized_value jsonb := '{}'::jsonb;
begin
  if p_summary is not null and jsonb_typeof(p_summary) = 'object' then
    select count(*)::integer
    into summary_count
    from jsonb_object_keys(p_summary);
  end if;
  if p_summary is null
     or jsonb_typeof(p_summary) <> 'object'
     or summary_count > 30
     or pg_column_size(p_summary) > 4096 then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_parser_quarantine_invalid';
  end if;

  for summary_entry in
    select summary.key, summary.value
    from jsonb_each(p_summary) summary(key, value)
    order by summary.key
  loop
    if summary_entry.key !~ '^[a-z][a-z0-9_]{0,47}$'
       or jsonb_typeof(summary_entry.value) <> 'number'
       or (summary_entry.value #>> '{}') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_parser_quarantine_invalid';
    end if;
    begin
      row_count_value := (summary_entry.value #>> '{}')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_parser_quarantine_invalid';
    end;
    if row_count_value < 1 or row_count_value > 5000000 then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_parser_quarantine_invalid';
    end if;
    normalized_value := normalized_value ||
      jsonb_build_object(summary_entry.key, row_count_value);
  end loop;
  return normalized_value;
end;
$$;

revoke all on function
  content_factory_private.normalize_ai_historical_parser_quarantine(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_historical_case_product_binding_method(
    p_organization_id uuid,
    p_case_id uuid,
    p_product_id uuid
  )
returns text
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  historical_case_row content_factory.ai_historical_case_events%rowtype;
  product_row content_factory.products%rowtype;
  product_sku_match_count integer := 0;
  product_sku_match_id uuid;
  marketplace_match_count integer := 0;
  marketplace_match_id uuid;
  product_sku_conflict boolean := false;
  marketplace_conflict boolean := false;
begin
  select historical_case.*
  into historical_case_row
  from content_factory.ai_historical_case_events historical_case
  where historical_case.organization_id = p_organization_id
    and historical_case.case_id = p_case_id;
  select product.*
  into product_row
  from content_factory.products product
  where product.organization_id = p_organization_id
    and product.id = p_product_id;
  if historical_case_row.id is null
     or product_row.id is null
     or historical_case_row.resolution_status <> 'matched' then
    return null;
  end if;
  if historical_case_row.product_id is not null then
    return case when historical_case_row.product_id = p_product_id
      then 'exact_product_id' else null end;
  end if;
  if historical_case_row.resolution_method not in (
    'source_external_sku', 'source_marketplace_sku'
  ) then
    return null;
  end if;

  if historical_case_row.product_sku is not null then
    select count(*)::integer
    into product_sku_match_count
    from content_factory.products product
    where product.organization_id = p_organization_id
      and product.sku = historical_case_row.product_sku;
    if product_sku_match_count <> 1 then
      return null;
    end if;
    select product.id
    into product_sku_match_id
    from content_factory.products product
    where product.organization_id = p_organization_id
      and product.sku = historical_case_row.product_sku;
    select count(distinct (
      lower(other_case.product_title) || chr(31) || lower(other_case.brand)
    )) > 1
    into product_sku_conflict
    from content_factory.ai_historical_case_events other_case
    where other_case.organization_id = p_organization_id
      and other_case.resolution_status = 'matched'
      and other_case.product_sku = historical_case_row.product_sku;
  end if;

  if historical_case_row.marketplace_sku is not null then
    select count(*)::integer
    into marketplace_match_count
    from content_factory.products product
    where product.organization_id = p_organization_id
      and product.current_wb_article = historical_case_row.marketplace_sku;
    if marketplace_match_count <> 1 then
      return null;
    end if;
    select product.id
    into marketplace_match_id
    from content_factory.products product
    where product.organization_id = p_organization_id
      and product.current_wb_article = historical_case_row.marketplace_sku;
    select count(distinct (
      lower(other_case.product_title) || chr(31) || lower(other_case.brand)
    )) > 1
    into marketplace_conflict
    from content_factory.ai_historical_case_events other_case
    where other_case.organization_id = p_organization_id
      and other_case.resolution_status = 'matched'
      and other_case.marketplace_sku = historical_case_row.marketplace_sku;
  end if;

  if coalesce(product_sku_conflict, false)
     or coalesce(marketplace_conflict, false)
     or (product_sku_match_id is not null
       and product_sku_match_id <> p_product_id)
     or (marketplace_match_id is not null
       and marketplace_match_id <> p_product_id) then
    return null;
  end if;
  if product_sku_match_id = p_product_id then
    return 'late_unique_product_sku';
  end if;
  if marketplace_match_id = p_product_id then
    return 'late_unique_marketplace_sku';
  end if;
  return null;
end;
$$;

revoke all on function
  content_factory_private.ai_historical_case_product_binding_method(
    uuid, uuid, uuid
  )
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_historical_semantic_decision_heads(
    p_organization_id uuid,
    p_product_category text
  )
returns table (
  case_id uuid,
  external_case_id text,
  row_hash text,
  semantic_case_key text,
  decision text,
  decision_hash text,
  decision_event_cursor bigint
)
language sql
security definer
stable
set search_path = ''
as $$
  select distinct on (
    historical_case.external_case_id,
    historical_case.row_hash
  )
    historical_case.case_id,
    historical_case.external_case_id,
    historical_case.row_hash,
    content_factory_private.json_hash(jsonb_build_object(
      'product_category', historical_case.product_category,
      'external_case_id', historical_case.external_case_id,
      'row_hash', historical_case.row_hash
    )),
    historical_decision.decision,
    historical_decision.decision_hash,
    historical_decision.event_cursor
  from content_factory.ai_historical_case_decisions historical_decision
  join content_factory.ai_historical_case_events historical_case
    on historical_case.organization_id = historical_decision.organization_id
   and historical_case.product_category =
     historical_decision.product_category
   and historical_case.case_id = historical_decision.case_id
  where historical_decision.organization_id = p_organization_id
    and historical_decision.product_category = p_product_category
  order by
    historical_case.external_case_id,
    historical_case.row_hash,
    historical_decision.event_cursor desc;
$$;

revoke all on function
  content_factory_private.ai_historical_semantic_decision_heads(uuid, text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_historical_confirmed_learning_cases(
    p_organization_id uuid,
    p_product_category text
  )
returns table (
  case_id uuid,
  external_case_id text,
  creative_angle text,
  outcome text,
  platform text,
  bound_product_id uuid,
  binding_method text,
  case_hash text,
  decision_hash text,
  decision_event_cursor bigint
)
language sql
security definer
stable
set search_path = ''
as $$
  with semantic_heads as materialized (
    select semantic_head.*
    from content_factory_private.ai_historical_semantic_decision_heads(
      p_organization_id,
      p_product_category
    ) semantic_head
    where semantic_head.decision = 'confirm'
  )
  select
    historical_case.case_id,
    historical_case.external_case_id,
    historical_case.creative_angle,
    historical_case.outcome,
    historical_case.platform,
    binding.bound_product_id,
    binding.binding_method,
    historical_case.case_hash,
    semantic_head.decision_hash,
    semantic_head.decision_event_cursor
  from semantic_heads semantic_head
  join content_factory.ai_historical_case_events historical_case
    on historical_case.organization_id = p_organization_id
   and historical_case.product_category = p_product_category
   and historical_case.case_id = semantic_head.case_id
  cross join lateral (
    select bound_candidate.bound_product_id, bound_candidate.binding_method
    from (
      select
        candidate_product.id as bound_product_id,
        content_factory_private.ai_historical_case_product_binding_method(
          p_organization_id,
          historical_case.case_id,
          candidate_product.id
        ) as binding_method
      from content_factory.products candidate_product
      where candidate_product.organization_id = p_organization_id
        and (
          (historical_case.product_id is not null
            and candidate_product.id = historical_case.product_id)
          or (
            historical_case.product_id is null
            and (
              (historical_case.product_sku is not null
                and candidate_product.sku = historical_case.product_sku)
              or (historical_case.marketplace_sku is not null
                and candidate_product.current_wb_article =
                  historical_case.marketplace_sku)
            )
          )
        )
    ) bound_candidate
    where bound_candidate.binding_method is not null
    order by bound_candidate.bound_product_id
    limit 1
  ) binding
  where historical_case.resolution_status = 'matched'
    and historical_case.creative_angle is not null
    and historical_case.outcome in ('good', 'bad');
$$;

revoke all on function
  content_factory_private.ai_historical_confirmed_learning_cases(uuid, text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_historical_case_evidence(
    p_organization_id uuid,
    p_product_category text
  )
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  category_value text :=
    content_factory_private.require_ai_product_category(p_product_category);
  confirmed_case_count_value integer := 0;
  confirmed_good_count_value integer := 0;
  confirmed_bad_count_value integer := 0;
  distinct_product_count_value integer := 0;
  distinct_platform_count_value integer := 0;
  historical_learning_eligible_count_value integer := 0;
  historical_learning_direct_binding_count_value integer := 0;
  historical_learning_late_binding_count_value integer := 0;
  missing_exact_product_binding_count_value integer := 0;
  angles_value jsonb := '[]'::jsonb;
  preferred_angle_value text;
  avoid_angle_value text;
  evidence_hash_value text;
begin
  with semantic_heads as materialized (
    select semantic_head.*
    from content_factory_private.ai_historical_semantic_decision_heads(
      p_organization_id,
      category_value
    ) semantic_head
  ), eligible as (
    select
      historical_case.case_id,
      historical_case.creative_angle,
      historical_case.outcome,
      historical_case.platform,
      coalesce(
        historical_case.product_id::text,
        case when historical_case.product_sku is not null
          then 'source_sku:' || historical_case.product_sku end,
        case when historical_case.marketplace_sku is not null
          then 'marketplace_sku:' || historical_case.marketplace_sku end
      ) as product_identity,
      historical_case.case_hash,
      semantic_head.decision_event_cursor
    from content_factory.ai_historical_case_events historical_case
    join semantic_heads semantic_head
      on semantic_head.case_id = historical_case.case_id
     and semantic_head.decision = 'confirm'
    where historical_case.organization_id = p_organization_id
      and historical_case.product_category = category_value
      and historical_case.resolution_status = 'matched'
      and historical_case.creative_angle is not null
      and historical_case.outcome in ('good', 'bad')
  )
  select
    count(*)::integer,
    count(*) filter (where eligible.outcome = 'good')::integer,
    count(*) filter (where eligible.outcome = 'bad')::integer,
    count(distinct eligible.product_identity)::integer,
    count(distinct eligible.platform)::integer
  into
    confirmed_case_count_value,
    confirmed_good_count_value,
    confirmed_bad_count_value,
    distinct_product_count_value,
    distinct_platform_count_value
  from eligible;

  select
    count(*) filter (
      where learning_case.binding_method = 'exact_product_id'
    )::integer,
    count(*) filter (
      where learning_case.binding_method in (
        'late_unique_product_sku', 'late_unique_marketplace_sku'
      )
    )::integer
  into
    historical_learning_direct_binding_count_value,
    historical_learning_late_binding_count_value
  from content_factory_private.ai_historical_confirmed_learning_cases(
    p_organization_id,
    category_value
  ) learning_case;
  historical_learning_eligible_count_value :=
    historical_learning_direct_binding_count_value
    + historical_learning_late_binding_count_value;
  missing_exact_product_binding_count_value := greatest(
    confirmed_case_count_value - historical_learning_eligible_count_value,
    0
  );

  with eligible as materialized (
    select
      learning_case.creative_angle,
      learning_case.outcome,
      learning_case.platform,
      learning_case.bound_product_id
    from content_factory_private.ai_historical_confirmed_learning_cases(
      p_organization_id,
      category_value
    ) learning_case
  ), per_product_angle as (
    select
      eligible.creative_angle,
      eligible.bound_product_id,
      count(*)::integer as confirmed_case_count,
      count(*) filter (where eligible.outcome = 'good')::integer
        as good_case_count,
      count(*) filter (where eligible.outcome = 'bad')::integer
        as bad_case_count,
      count(distinct eligible.platform)::integer
        as distinct_platform_count
    from eligible
    group by eligible.creative_angle, eligible.bound_product_id
  ), angle_summary as (
    select
      per_product_angle.creative_angle,
      sum(per_product_angle.confirmed_case_count)::integer
        as confirmed_case_count,
      sum(per_product_angle.good_case_count)::integer as good_case_count,
      sum(per_product_angle.bad_case_count)::integer as bad_case_count,
      count(*)::integer as distinct_product_count,
      (
        select count(distinct angle_case.platform)::integer
        from eligible angle_case
        where angle_case.creative_angle =
          per_product_angle.creative_angle
      ) as distinct_platform_count,
      count(*) filter (
        where per_product_angle.good_case_count
          - per_product_angle.bad_case_count >= 2
      )::integer as preferred_ready_product_count,
      count(*) filter (
        where per_product_angle.bad_case_count
          - per_product_angle.good_case_count >= 2
      )::integer as avoid_ready_product_count,
      max(
        per_product_angle.good_case_count
          - per_product_angle.bad_case_count
      )::integer as best_product_preferred_net_support,
      max(
        per_product_angle.bad_case_count
          - per_product_angle.good_case_count
      )::integer as best_product_avoid_net_support
    from per_product_angle
    group by per_product_angle.creative_angle
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'creative_angle', angle_summary.creative_angle,
    'confirmed_case_count', angle_summary.confirmed_case_count,
    'good_case_count', angle_summary.good_case_count,
    'bad_case_count', angle_summary.bad_case_count,
    'net_support',
      angle_summary.good_case_count - angle_summary.bad_case_count,
    'distinct_product_count', angle_summary.distinct_product_count,
    'distinct_platform_count', angle_summary.distinct_platform_count,
    'preferred_ready_product_count',
      angle_summary.preferred_ready_product_count,
    'avoid_ready_product_count', angle_summary.avoid_ready_product_count,
    'best_product_preferred_net_support',
      angle_summary.best_product_preferred_net_support,
    'best_product_avoid_net_support',
      angle_summary.best_product_avoid_net_support,
    'preferred_eligible',
      angle_summary.preferred_ready_product_count > 0,
    'avoid_eligible',
      angle_summary.avoid_ready_product_count > 0
  ) order by angle_summary.creative_angle), '[]'::jsonb)
  into angles_value
  from angle_summary;

  select angle ->> 'creative_angle'
  into preferred_angle_value
  from jsonb_array_elements(angles_value) angle
  where (angle ->> 'preferred_eligible')::boolean
  order by
    (angle ->> 'best_product_preferred_net_support')::integer desc,
    (angle ->> 'net_support')::integer desc,
    (angle ->> 'good_case_count')::integer desc,
    (angle ->> 'distinct_product_count')::integer desc,
    angle ->> 'creative_angle'
  limit 1;

  select angle ->> 'creative_angle'
  into avoid_angle_value
  from jsonb_array_elements(angles_value) angle
  where (angle ->> 'avoid_eligible')::boolean
  order by
    (angle ->> 'best_product_avoid_net_support')::integer desc,
    ((angle ->> 'bad_case_count')::integer
      - (angle ->> 'good_case_count')::integer) desc,
    (angle ->> 'bad_case_count')::integer desc,
    (angle ->> 'distinct_product_count')::integer desc,
    angle ->> 'creative_angle'
  limit 1;

  evidence_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'product_category', category_value,
    'confirmed_product_bound_semantic_heads', coalesce((
      select jsonb_agg(jsonb_build_object(
        'case_hash', learning_case.case_hash,
        'decision_hash', learning_case.decision_hash,
        'event_cursor', learning_case.decision_event_cursor,
        'bound_product_id', learning_case.bound_product_id,
        'binding_method', learning_case.binding_method
      ) order by learning_case.decision_event_cursor)
      from content_factory_private.ai_historical_confirmed_learning_cases(
        p_organization_id,
        category_value
      ) learning_case
    ), '[]'::jsonb)
  ));

  return jsonb_build_object(
    'version', 'ai-historical-case-evidence-v1',
    'product_category', category_value,
    'confirmed_case_count', confirmed_case_count_value,
    'confirmed_good_count', confirmed_good_count_value,
    'confirmed_bad_count', confirmed_bad_count_value,
    'distinct_product_count', distinct_product_count_value,
    'distinct_platform_count', distinct_platform_count_value,
    'historical_learning_eligible_count',
      historical_learning_eligible_count_value,
    'historical_learning_direct_product_binding_count',
      historical_learning_direct_binding_count_value,
    'historical_learning_late_exact_sku_binding_count',
      historical_learning_late_binding_count_value,
    'missing_exact_product_binding_count',
      missing_exact_product_binding_count_value,
    'category_signal_only_unbound_count',
      missing_exact_product_binding_count_value,
    'angles', angles_value,
    'advisory_preferred_creative_angle', preferred_angle_value,
    'advisory_avoid_creative_angle', avoid_angle_value,
    'generation_advisory_ready',
      preferred_angle_value is not null or avoid_angle_value is not null,
    'generation_readiness_requires_two_net_cases_for_one_product', true,
    'unbound_confirmed_cases_are_category_signal_only', true,
    'semantic_identity', 'product_category+external_case_id+row_hash',
    'semantic_duplicate_cases_collapsed', true,
    'minimum_confirmed_cases_per_direction', 2,
    'contradictory_majority_forbidden', true,
    'evidence_hash', evidence_hash_value,
    'raw_prose_excluded', true,
    'urls_excluded', true,
    'pending_cases_excluded', true,
    'quarantined_cases_excluded', true,
    'latest_human_decision_head_only', true,
    'generation_fallback_requires_exact_product_binding', true,
    'late_binding_exact_unique_sku_only', true,
    'fuzzy_binding_forbidden', true,
    'conflicting_external_identities_excluded', true,
    'provider_action', false,
    'generation_action', false,
    'spend_action', false
  );
end;
$$;

revoke all on function
  content_factory_private.ai_historical_case_evidence(uuid, text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_historical_product_case_evidence(
    p_organization_id uuid,
    p_product_category text,
    p_product_id uuid
  )
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  category_value text :=
    content_factory_private.require_ai_product_category(p_product_category);
  eligible_total_count_value integer := 0;
  considered_count_value integer := 0;
  distinct_platform_count_value integer := 0;
  direct_product_binding_count_value integer := 0;
  late_exact_sku_binding_count_value integer := 0;
  angles_value jsonb := '[]'::jsonb;
  case_refs_value jsonb := '[]'::jsonb;
  maximum_score_value integer;
  maximum_score_tie_count integer := 0;
  minimum_score_value integer;
  minimum_score_tie_count integer := 0;
  preferred_angle_value text;
  avoid_angle_value text;
  evidence_hash_value text;
  target_product_row content_factory.products%rowtype;
begin
  select product.*
  into target_product_row
  from content_factory.products product
  where product.organization_id = p_organization_id
    and product.id = p_product_id;
  if p_product_id is null or target_product_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_product_invalid';
  end if;

  with semantic_heads as materialized (
    select semantic_head.*
    from content_factory_private.ai_historical_semantic_decision_heads(
      p_organization_id,
      category_value
    ) semantic_head
  ), candidate_cases as materialized (
    select historical_case.case_id
    from content_factory.ai_historical_case_events historical_case
    join semantic_heads semantic_head
      on semantic_head.case_id = historical_case.case_id
     and semantic_head.decision = 'confirm'
    where historical_case.organization_id = p_organization_id
      and historical_case.product_category = category_value
      and historical_case.resolution_status = 'matched'
      and historical_case.creative_angle is not null
      and historical_case.outcome in ('good', 'bad')
      and (
        historical_case.product_id = p_product_id
        or (
          historical_case.product_id is null
          and historical_case.resolution_method in (
            'source_external_sku', 'source_marketplace_sku'
          )
          and (
            historical_case.product_sku = target_product_row.sku
            or (
              target_product_row.current_wb_article is not null
              and historical_case.marketplace_sku =
                target_product_row.current_wb_article
            )
          )
        )
      )
  )
  select count(*)::integer
  into eligible_total_count_value
  from candidate_cases candidate_case
  cross join lateral (
    select content_factory_private
      .ai_historical_case_product_binding_method(
        p_organization_id,
        candidate_case.case_id,
        p_product_id
      ) as binding_method
  ) binding
  where binding.binding_method is not null;

  with semantic_heads as materialized (
    select semantic_head.*
    from content_factory_private.ai_historical_semantic_decision_heads(
      p_organization_id,
      category_value
    ) semantic_head
  ), candidate_cases as materialized (
    select
      historical_case.case_id,
      historical_case.case_hash,
      historical_case.creative_angle,
      historical_case.outcome,
      historical_case.platform,
      semantic_head.decision_hash,
      semantic_head.decision_event_cursor as event_cursor
    from content_factory.ai_historical_case_events historical_case
    join semantic_heads semantic_head
      on semantic_head.case_id = historical_case.case_id
     and semantic_head.decision = 'confirm'
    where historical_case.organization_id = p_organization_id
      and historical_case.product_category = category_value
      and historical_case.resolution_status = 'matched'
      and historical_case.creative_angle is not null
      and historical_case.outcome in ('good', 'bad')
      and (
        historical_case.product_id = p_product_id
        or (
          historical_case.product_id is null
          and historical_case.resolution_method in (
            'source_external_sku', 'source_marketplace_sku'
          )
          and (
            historical_case.product_sku = target_product_row.sku
            or (
              target_product_row.current_wb_article is not null
              and historical_case.marketplace_sku =
                target_product_row.current_wb_article
            )
          )
        )
      )
  ), eligible as materialized (
    select
      candidate_case.case_id,
      candidate_case.case_hash,
      candidate_case.creative_angle,
      candidate_case.outcome,
      candidate_case.platform,
      binding.binding_method,
      candidate_case.decision_hash,
      candidate_case.event_cursor
    from candidate_cases candidate_case
    cross join lateral (
      select content_factory_private
        .ai_historical_case_product_binding_method(
          p_organization_id,
          candidate_case.case_id,
          p_product_id
        ) as binding_method
    ) binding
    where binding.binding_method is not null
    order by candidate_case.event_cursor desc
    limit 100
  ), angle_summary as (
    select
      eligible.creative_angle,
      count(*)::integer as confirmed_case_count,
      count(*) filter (where eligible.outcome = 'good')::integer
        as good_case_count,
      count(*) filter (where eligible.outcome = 'bad')::integer
        as bad_case_count,
      count(distinct eligible.platform)::integer
        as distinct_platform_count
    from eligible
    group by eligible.creative_angle
  )
  select
    (select count(*)::integer from eligible),
    (select count(distinct eligible.platform)::integer from eligible),
    (select count(*) filter (
       where eligible.binding_method = 'exact_product_id'
     )::integer from eligible),
    (select count(*) filter (
       where eligible.binding_method in (
         'late_unique_product_sku', 'late_unique_marketplace_sku'
       )
     )::integer from eligible),
    coalesce((select jsonb_agg(jsonb_build_object(
      'creative_angle', angle_summary.creative_angle,
      'confirmed_case_count', angle_summary.confirmed_case_count,
      'good_case_count', angle_summary.good_case_count,
      'bad_case_count', angle_summary.bad_case_count,
      'score', angle_summary.good_case_count - angle_summary.bad_case_count,
      'distinct_platform_count', angle_summary.distinct_platform_count
    ) order by angle_summary.creative_angle) from angle_summary), '[]'::jsonb),
    coalesce((select jsonb_agg(jsonb_build_object(
      'case_id', bounded.case_id,
      'case_hash', bounded.case_hash,
      'decision_hash', bounded.decision_hash,
      'binding_method', bounded.binding_method,
      'decision_event_cursor', bounded.event_cursor
    ) order by bounded.event_cursor desc)
    from (
      select eligible.*
      from eligible
      order by eligible.event_cursor desc
      limit 20
    ) bounded), '[]'::jsonb)
  into
    considered_count_value,
    distinct_platform_count_value,
    direct_product_binding_count_value,
    late_exact_sku_binding_count_value,
    angles_value,
    case_refs_value;

  select max((angle ->> 'score')::integer)
  into maximum_score_value
  from jsonb_array_elements(angles_value) angle;
  if maximum_score_value is not null then
    select count(*)::integer
    into maximum_score_tie_count
    from jsonb_array_elements(angles_value) angle
    where (angle ->> 'score')::integer = maximum_score_value;
  end if;
  if maximum_score_value >= 2 and maximum_score_tie_count = 1 then
    select angle ->> 'creative_angle'
    into preferred_angle_value
    from jsonb_array_elements(angles_value) angle
    where (angle ->> 'score')::integer = maximum_score_value
    limit 1;
  end if;

  select min((angle ->> 'score')::integer)
  into minimum_score_value
  from jsonb_array_elements(angles_value) angle;
  if minimum_score_value is not null then
    select count(*)::integer
    into minimum_score_tie_count
    from jsonb_array_elements(angles_value) angle
    where (angle ->> 'score')::integer = minimum_score_value;
  end if;
  if minimum_score_value <= -2 and minimum_score_tie_count = 1 then
    select angle ->> 'creative_angle'
    into avoid_angle_value
    from jsonb_array_elements(angles_value) angle
    where (angle ->> 'score')::integer = minimum_score_value
      and angle ->> 'creative_angle' is distinct from preferred_angle_value
    limit 1;
  end if;

  evidence_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'product_category', category_value,
    'product_id', p_product_id,
    'angles', angles_value,
    'case_refs', case_refs_value,
    'maximum_cases_considered', 100
  ));

  return jsonb_build_object(
    'version', 'ai-historical-product-case-evidence-v1',
    'product_category', category_value,
    'product_id', p_product_id,
    'eligible_total_case_count', eligible_total_count_value,
    'considered_case_count', considered_count_value,
    'maximum_cases_considered', 100,
    'evidence_truncated', eligible_total_count_value > 100,
    'distinct_product_count', case when considered_count_value > 0 then 1 else 0 end,
    'distinct_platform_count', distinct_platform_count_value,
    'direct_product_binding_case_count',
      direct_product_binding_count_value,
    'late_exact_sku_binding_case_count',
      late_exact_sku_binding_count_value,
    'angles', angles_value,
    'bounded_case_refs', case_refs_value,
    'bounded_case_ref_limit', 20,
    'advisory_preferred_creative_angle', preferred_angle_value,
    'advisory_avoid_creative_angle', avoid_angle_value,
    'preferred_score', maximum_score_value,
    'preferred_score_tie_count', maximum_score_tie_count,
    'avoid_score', minimum_score_value,
    'avoid_score_tie_count', minimum_score_tie_count,
    'minimum_absolute_score', 2,
    'evidence_hash', evidence_hash_value,
    'exact_product_scope', true,
    'semantic_identity', 'product_category+external_case_id+row_hash',
    'semantic_duplicate_cases_collapsed', true,
    'latest_semantic_human_decision_only', true,
    'late_binding_exact_unique_sku_only', true,
    'fuzzy_binding_forbidden', true,
    'conflicting_external_identities_excluded', true,
    'raw_prose_excluded', true,
    'urls_excluded', true,
    'metrics_excluded', true,
    'hook_patterns', '[]'::jsonb,
    'pending_cases_excluded', true,
    'quarantined_cases_excluded', true,
    'rejected_heads_excluded', true,
    'provider_action', false,
    'generation_action', false,
    'spend_action', false
  );
end;
$$;

revoke all on function
  content_factory_private.ai_historical_product_case_evidence(uuid, text, uuid)
  from public, anon, authenticated, service_role;

-- Preserve the installed readiness calculation and narrow one previously
-- optimistic signal: registering an XLSX/CSV is not completed analysis.  Such
-- a source contributes to analysis coverage only after a normalized batch has
-- completed and produced at least one exact, non-quarantined case in the
-- selected category.
do $preserve_ai_evidence_readiness$
declare
  installed_definition text;
  cloned_definition text;
begin
  if to_regprocedure(
    'content_factory_private.ai_category_evidence_readiness_pre_historical_case_v1(uuid,text)'
  ) is null then
    installed_definition := pg_catalog.pg_get_functiondef(
      'content_factory_private.ai_category_evidence_readiness(uuid,text)'
        ::regprocedure
    );
    cloned_definition := regexp_replace(
      installed_definition,
      'FUNCTION content_factory_private\.ai_category_evidence_readiness\(',
      'FUNCTION content_factory_private.ai_category_evidence_readiness_pre_historical_case_v1(',
      'i'
    );
    if cloned_definition = installed_definition then
      raise exception using
        errcode = '55000',
        message = 'ai_historical_readiness_clone_failed';
    end if;
    execute cloned_definition;
  end if;
end;
$preserve_ai_evidence_readiness$;

revoke all on function
  content_factory_private
    .ai_category_evidence_readiness_pre_historical_case_v1(uuid, text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_category_evidence_readiness(
    p_organization_id uuid,
    p_product_category text
  )
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  category_value text :=
    content_factory_private.require_ai_product_category(p_product_category);
  base_value jsonb;
  dimensions_value jsonb;
  gaps_value jsonb;
  structured_source_count_value integer := 0;
  analysis_score_value integer := 0;
  old_weighted_points integer := 0;
  new_weighted_points integer := 0;
  readiness_score_value integer := 0;
  readiness_status_value text;
  evidence_hash_value text;
  historical_evidence_value jsonb;
begin
  base_value := content_factory_private
    .ai_category_evidence_readiness_pre_historical_case_v1(
      p_organization_id,
      category_value
    );
  historical_evidence_value :=
    content_factory_private.ai_historical_case_evidence(
      p_organization_id,
      category_value
    );

  select count(*)::integer
  into structured_source_count_value
  from (
    select distinct case
      when source.source_kind = 'file' then 'file:' || source.sha256
      else 'link:' || source.source_hash
    end as source_identity
    from content_factory.ai_category_knowledge_sources source
    where source.organization_id = p_organization_id
      and source.status = 'active'
      and (
        (source.source_kind = 'file' and source.sha256 ~ '^[0-9a-f]{64}$')
        or
        (source.source_kind = 'link'
          and source.source_hash ~ '^[0-9a-f]{64}$')
      )
      and (
        (
          source.product_category = category_value
          and (
            source.source_kind = 'link'
            or source.mime_type not in (
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
              'text/csv'
            )
          )
        )
        or (
          source.source_kind = 'file'
          and source.mime_type in (
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/csv'
          )
          and exists (
            select 1
            from content_factory.ai_historical_case_import_batches batch
            join content_factory.ai_historical_case_events historical_case
              on historical_case.organization_id = batch.organization_id
             and historical_case.batch_id = batch.id
            where batch.organization_id = p_organization_id
              and batch.source_id = source.id
              and batch.import_status in (
                'completed', 'completed_with_quarantine'
              )
              and historical_case.product_category = category_value
              and historical_case.resolution_status = 'matched'
              and (
                historical_case.product_id is not null
                or exists (
                  select 1
                  from content_factory.products product
                  where product.organization_id = p_organization_id
                    and (
                      product.sku = historical_case.product_sku
                      or product.current_wb_article =
                        historical_case.marketplace_sku
                    )
                    and content_factory_private
                      .ai_historical_case_product_binding_method(
                        p_organization_id,
                        historical_case.case_id,
                        product.id
                      ) is not null
                )
              )
          )
        )
      )
  ) completed_source;

  analysis_score_value := least(100, floor(
    least(structured_source_count_value, 8)::numeric * 100 / 8
  )::integer);
  new_weighted_points :=
    floor(15 * analysis_score_value::numeric / 100)::integer;

  select coalesce((dimension ->> 'weighted_points')::integer, 0)
  into old_weighted_points
  from jsonb_array_elements(base_value -> 'dimensions') dimension
  where dimension ->> 'key' = 'analysis_coverage'
  limit 1;

  select coalesce(jsonb_agg(
    case when dimension ->> 'key' = 'analysis_coverage' then
      dimension || jsonb_build_object(
        'current', structured_source_count_value,
        'target', 8,
        'score', analysis_score_value,
        'weighted_points', new_weighted_points,
        'missing', greatest(0, 8 - structured_source_count_value),
        'next_action',
          'Завершите серверный разбор XLSX/CSV и проверьте карантин кейсов'
      )
    else dimension end
    order by ordinal
  ), '[]'::jsonb)
  into dimensions_value
  from jsonb_array_elements(base_value -> 'dimensions') with ordinality
    as item(dimension, ordinal);

  readiness_score_value := greatest(
    0,
    least(
      100,
      (base_value ->> 'score')::integer
        - old_weighted_points
        + new_weighted_points
    )
  );
  readiness_status_value := case
    when (base_value ->> 'source_count')::integer = 0
      and (base_value ->> 'human_validation_count')::integer = 0
      and structured_source_count_value = 0 then 'cold_start'
    when readiness_score_value >= 75 then 'strong_evidence'
    when readiness_score_value >= 35 then 'developing_evidence'
    else 'insufficient_evidence'
  end;

  select coalesce(jsonb_agg(jsonb_build_object(
    'key', dimension ->> 'key',
    'missing', (dimension ->> 'missing')::integer,
    'next_action', dimension ->> 'next_action',
    'priority', case
      when (dimension ->> 'missing')::integer >= 3 then 'high'
      else 'normal'
    end
  ) order by ordinal), '[]'::jsonb)
  into gaps_value
  from jsonb_array_elements(dimensions_value) with ordinality
    as item(dimension, ordinal)
  where (dimension ->> 'missing')::integer > 0;

  evidence_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'base_evidence_hash', base_value ->> 'evidence_hash',
    'product_category', category_value,
    'historical_case_evidence_hash',
      historical_evidence_value ->> 'evidence_hash',
    'completed_historical_case_batches', coalesce((
      select jsonb_agg(jsonb_build_object(
        'batch_id', batch.id,
        'request_hash', batch.request_hash,
        'event_cursor', batch.event_cursor
      ) order by batch.event_cursor)
      from content_factory.ai_historical_case_import_batches batch
      where batch.organization_id = p_organization_id
        and batch.import_status in ('completed', 'completed_with_quarantine')
        and exists (
          select 1
          from content_factory.ai_historical_case_events historical_case
          where historical_case.organization_id = batch.organization_id
            and historical_case.batch_id = batch.id
            and historical_case.product_category = category_value
            and historical_case.resolution_status = 'matched'
        )
    ), '[]'::jsonb)
  ));

  return base_value || jsonb_build_object(
    'score', readiness_score_value,
    'status', readiness_status_value,
    'dimensions', dimensions_value,
    'gaps', gaps_value,
    'evidence_hash', evidence_hash_value,
    'structured_source_count', structured_source_count_value,
    'spreadsheet_registration_is_completed_analysis', false,
    'historical_case_evidence', historical_evidence_value,
    'historical_confirmed_case_count',
      (historical_evidence_value ->> 'confirmed_case_count')::integer,
    'historical_advisory_ready',
      historical_evidence_value ->> 'advisory_preferred_creative_angle'
        is not null
      or historical_evidence_value ->> 'advisory_avoid_creative_angle'
        is not null
  );
end;
$$;

revoke all on function
  content_factory_private.ai_category_evidence_readiness(uuid, text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_historical_case_snapshot(
    p_organization_id uuid,
    p_product_category text
  )
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  category_value text :=
    content_factory_private.require_ai_product_category(p_product_category);
  cases_value jsonb;
  summary_value jsonb;
  batches_value jsonb;
  event_cursor_value bigint := 0;
begin
  select greatest(
    coalesce((
      select max(batch.event_cursor)
      from content_factory.ai_historical_case_import_batches batch
      where batch.organization_id = p_organization_id
    ), 0),
    coalesce((
      select max(historical_case.event_cursor)
      from content_factory.ai_historical_case_events historical_case
      where historical_case.organization_id = p_organization_id
    ), 0),
    coalesce((
      select max(decision.event_cursor)
      from content_factory.ai_historical_case_decisions decision
      where decision.organization_id = p_organization_id
    ), 0)
  ) into event_cursor_value;

  select coalesce(jsonb_agg(item.payload order by item.event_cursor desc),
                  '[]'::jsonb)
  into cases_value
  from (
    select
      historical_case.event_cursor,
      jsonb_build_object(
        'case_id', historical_case.case_id,
        'event_id', historical_case.id,
        'batch_id', historical_case.batch_id,
        'source_id', historical_case.source_id,
        'external_case_id', historical_case.external_case_id,
        'product_category', historical_case.product_category,
        'product_id', historical_case.product_id,
        'product_sku', historical_case.product_sku,
        'marketplace_sku', historical_case.marketplace_sku,
        'resolved_sku', product.sku,
        'product_title', historical_case.product_title,
        'brand', historical_case.brand,
        'platform', historical_case.platform,
        'channel', historical_case.channel,
        'period_start', historical_case.period_start,
        'period_end', historical_case.period_end,
        'outcome', historical_case.outcome,
        'outcome_dimension', historical_case.outcome_dimension,
        'status_label', historical_case.status_label,
        'metrics', historical_case.metrics,
        'confidence', historical_case.confidence,
        'creative_angle', historical_case.creative_angle,
        'resolution_status', historical_case.resolution_status,
        'resolution_method', historical_case.resolution_method,
        'quarantine_reason', historical_case.quarantine_reason,
        'provenance', jsonb_build_object(
          'original_filename', historical_case.source_filename,
          'source_sha256', historical_case.source_sha256,
          'sheet', historical_case.source_sheet,
          'row', historical_case.source_row,
          'row_hash', historical_case.row_hash,
          'schema_version', historical_case.schema_version,
          'parser_version', historical_case.parser_version
        ),
        'case_hash', historical_case.case_hash,
        'decision_status', case decision_head.decision
          when 'confirm' then 'confirmed'
          when 'reject' then 'rejected'
          else 'pending'
        end,
        'case_version', coalesce(
          decision_head.resulting_scope_version, 0
        ),
        'head_event_id', coalesce(
          decision_head.id, historical_case.id
        ),
        'head_event_cursor', coalesce(
          decision_head.event_cursor, historical_case.event_cursor
        ),
        'decided_by', decision_head.decided_by,
        'decided_at', decision_head.created_at,
        'imported_at', historical_case.created_at,
        'event_cursor', historical_case.event_cursor,
        'raw_prose_excluded', true,
        'raw_historical_case_enters_prompt_automatically', false,
        'pending_case_affects_generation', false,
        'exact_product_binding_present',
          historical_case.product_id is not null,
        'late_exact_sku_binding_available',
          late_binding.binding_method is not null,
        'historical_learning_binding_status', case
          when historical_case.product_id is not null then 'direct_product_id'
          when late_binding.binding_method is not null then late_binding.binding_method
          else 'missing_exact_binding'
        end,
        'confirmed_aggregate_can_affect_generation_policy', true
      ) as payload
    from content_factory.ai_historical_case_events historical_case
    left join content_factory.products product
      on product.organization_id = historical_case.organization_id
     and product.id = historical_case.product_id
    left join lateral (
      select content_factory_private
        .ai_historical_case_product_binding_method(
          p_organization_id,
          historical_case.case_id,
          candidate_product.id
        ) as binding_method
      from content_factory.products candidate_product
      where candidate_product.organization_id = p_organization_id
        and historical_case.product_id is null
        and (
          (historical_case.product_sku is not null
            and candidate_product.sku = historical_case.product_sku)
          or (historical_case.marketplace_sku is not null
            and candidate_product.current_wb_article =
              historical_case.marketplace_sku)
        )
        and content_factory_private
          .ai_historical_case_product_binding_method(
            p_organization_id,
            historical_case.case_id,
            candidate_product.id
          ) is not null
      order by candidate_product.id
      limit 1
    ) late_binding on true
    left join lateral (
      select
        decision.id,
        decision.decision,
        decision.resulting_scope_version,
        decision.decided_by,
        decision.created_at,
        decision.event_cursor
      from content_factory.ai_historical_case_decisions decision
      where decision.organization_id = historical_case.organization_id
        and decision.product_category = historical_case.product_category
        and decision.case_id = historical_case.case_id
      order by decision.event_cursor desc
      limit 1
    ) decision_head on true
    where historical_case.organization_id = p_organization_id
      and historical_case.product_category = category_value
    order by historical_case.event_cursor desc
    limit 500
  ) item;

  with decision_heads as (
    select distinct on (decision.case_id)
      decision.case_id,
      decision.decision,
      decision.resulting_scope_version
    from content_factory.ai_historical_case_decisions decision
    where decision.organization_id = p_organization_id
      and decision.product_category = category_value
    order by decision.case_id, decision.event_cursor desc
  )
  select jsonb_build_object(
    'product_category', category_value,
    'total', count(*)::integer,
    'good', count(*) filter (
      where historical_case.outcome = 'good'
    )::integer,
    'bad', count(*) filter (
      where historical_case.outcome = 'bad'
    )::integer,
    'review', count(*) filter (
      where historical_case.outcome = 'review'
    )::integer,
    'matched', count(*) filter (
      where historical_case.resolution_status = 'matched'
    )::integer,
    'quarantined', count(*) filter (
      where historical_case.resolution_status = 'quarantined'
    )::integer,
    'pending', count(*) filter (
      where decision_head.case_id is null
    )::integer,
    'confirmed', count(*) filter (
      where decision_head.decision = 'confirm'
    )::integer,
    'rejected', count(*) filter (
      where decision_head.decision = 'reject'
    )::integer,
    'confirmed_good', count(*) filter (
      where decision_head.decision = 'confirm'
        and historical_case.outcome = 'good'
    )::integer,
    'confirmed_bad', count(*) filter (
      where decision_head.decision = 'confirm'
        and historical_case.outcome = 'bad'
    )::integer,
    'raw_prose_excluded', true,
    'raw_historical_cases_enter_prompt_automatically', false,
    'pending_historical_cases_affect_generation', false,
    'confirmed_historical_case_aggregate_can_affect_generation_policy', true,
    'exact_product_binding_required_for_generation', true
  )
  into summary_value
  from content_factory.ai_historical_case_events historical_case
  left join decision_heads decision_head
    on decision_head.case_id = historical_case.case_id
  where historical_case.organization_id = p_organization_id
    and historical_case.product_category = category_value;

  with selected_imports as (
    select distinct batch.source_id, batch.manifest_sha256
    from content_factory.ai_historical_case_import_batches batch
    where batch.organization_id = p_organization_id
      and (
        batch.default_product_category = category_value
        or exists (
          select 1
          from content_factory.ai_historical_case_events historical_case
          where historical_case.organization_id = batch.organization_id
            and historical_case.batch_id = batch.id
            and historical_case.product_category = category_value
        )
      )
  ), logical_imports as (
    select
      batch.source_id,
      batch.manifest_sha256,
      min(batch.default_product_category) as default_product_category,
      min(batch.original_filename) as original_filename,
      min(batch.source_sha256) as source_sha256,
      min(batch.schema_version) as schema_version,
      min(batch.parser_version) as parser_version,
      max(batch.batch_count)::integer as batch_count,
      count(distinct batch.batch_index)::integer as completed_batch_count,
      sum(batch.case_count)::integer as case_count,
      sum(batch.parsed_row_count)::integer as parsed_row_count,
      sum(batch.parser_quarantined_row_count)::integer
        as parser_quarantined_row_count,
      sum(batch.matched_case_count)::integer as matched_case_count,
      sum(batch.quarantined_case_count)::integer as quarantined_case_count,
      min(batch.created_at) as import_started_at,
      max(batch.created_at) as imported_at,
      max(batch.event_cursor) as event_cursor
    from content_factory.ai_historical_case_import_batches batch
    join selected_imports selected
      on selected.source_id = batch.source_id
     and selected.manifest_sha256 = batch.manifest_sha256
    where batch.organization_id = p_organization_id
    group by batch.source_id, batch.manifest_sha256
    order by max(batch.event_cursor) desc
    limit 30
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'import_id', content_factory_private.json_hash(jsonb_build_object(
      'organization_id', p_organization_id,
      'source_id', logical_import.source_id,
      'manifest_sha256', logical_import.manifest_sha256
    )),
    'source_id', logical_import.source_id,
    'default_product_category', logical_import.default_product_category,
    'original_filename', logical_import.original_filename,
    'source_sha256', logical_import.source_sha256,
    'schema_version', logical_import.schema_version,
    'parser_version', logical_import.parser_version,
    'manifest_sha256', logical_import.manifest_sha256,
    'batch_count', logical_import.batch_count,
    'completed_batch_count', logical_import.completed_batch_count,
    'case_count', logical_import.case_count,
    'parsed_row_count', logical_import.parsed_row_count,
    'parser_quarantined_row_count',
      logical_import.parser_quarantined_row_count,
    'parser_quarantine_summary', coalesce((
      select jsonb_object_agg(summary.code, summary.row_count order by summary.code)
      from (
        select quarantine.key as code,
               sum((quarantine.value #>> '{}')::integer)::integer as row_count
        from content_factory.ai_historical_case_import_batches batch_part
        cross join lateral jsonb_each(
          batch_part.parser_quarantine_summary
        ) quarantine(key, value)
        where batch_part.organization_id = p_organization_id
          and batch_part.source_id = logical_import.source_id
          and batch_part.manifest_sha256 = logical_import.manifest_sha256
        group by quarantine.key
      ) summary
    ), '{}'::jsonb),
    'matched_case_count', logical_import.matched_case_count,
    'quarantined_case_count', logical_import.quarantined_case_count,
    'import_status', case
      when logical_import.completed_batch_count < logical_import.batch_count
        then 'in_progress'
      when logical_import.case_count = 0
        and logical_import.parser_quarantined_row_count > 0
        then 'parser_rejected'
      when logical_import.matched_case_count = 0 then 'quarantined'
      when logical_import.quarantined_case_count > 0
        or logical_import.parser_quarantined_row_count > 0
        then 'completed_with_quarantine'
      else 'completed'
    end,
    'per_category_summary', coalesce((
      select jsonb_object_agg(
        category_summary.product_category,
        jsonb_build_object(
          'total', category_summary.total_count,
          'matched', category_summary.matched_count,
          'quarantined', category_summary.quarantined_count,
          'good', category_summary.good_count,
          'bad', category_summary.bad_count,
          'review', category_summary.review_count
        ) order by category_summary.product_category
      )
      from (
        select
          category.key as product_category,
          sum((category.value ->> 'total')::integer)::integer as total_count,
          sum((category.value ->> 'matched')::integer)::integer as matched_count,
          sum((category.value ->> 'quarantined')::integer)::integer
            as quarantined_count,
          sum((category.value ->> 'good')::integer)::integer as good_count,
          sum((category.value ->> 'bad')::integer)::integer as bad_count,
          sum((category.value ->> 'review')::integer)::integer as review_count
        from content_factory.ai_historical_case_import_batches batch_part
        cross join lateral jsonb_each(
          batch_part.per_category_summary
        ) category(key, value)
        where batch_part.organization_id = p_organization_id
          and batch_part.source_id = logical_import.source_id
          and batch_part.manifest_sha256 = logical_import.manifest_sha256
        group by category.key
      ) category_summary
    ), '{}'::jsonb),
    'selected_category_summary', coalesce((
      select jsonb_build_object(
        'total', sum((category.value ->> 'total')::integer)::integer,
        'matched', sum((category.value ->> 'matched')::integer)::integer,
        'quarantined',
          sum((category.value ->> 'quarantined')::integer)::integer,
        'good', sum((category.value ->> 'good')::integer)::integer,
        'bad', sum((category.value ->> 'bad')::integer)::integer,
        'review', sum((category.value ->> 'review')::integer)::integer
      )
      from content_factory.ai_historical_case_import_batches batch_part
      cross join lateral jsonb_each(
        batch_part.per_category_summary
      ) category(key, value)
      where batch_part.organization_id = p_organization_id
        and batch_part.source_id = logical_import.source_id
        and batch_part.manifest_sha256 = logical_import.manifest_sha256
        and category.key = category_value
    ), '{}'::jsonb),
    'import_started_at', logical_import.import_started_at,
    'imported_at', logical_import.imported_at,
    'event_cursor', logical_import.event_cursor,
    'raw_prose_excluded', true
  ) order by logical_import.event_cursor desc), '[]'::jsonb)
  into batches_value
  from logical_imports logical_import;

  return jsonb_build_object(
    'historical_cases', cases_value,
    'historical_case_summary', summary_value,
    'historical_case_evidence',
      content_factory_private.ai_historical_case_evidence(
        p_organization_id,
        category_value
      ),
    'batches', batches_value,
    'event_cursor', event_cursor_value,
    'raw_prose_excluded', true,
    'raw_historical_cases_enter_prompt_automatically', false,
    'pending_historical_cases_affect_generation', false,
    'confirmed_historical_case_aggregate_can_affect_generation_policy', true,
    'exact_product_binding_required_for_generation', true
  );
end;
$$;

revoke all on function
  content_factory_private.ai_historical_case_snapshot(uuid, text)
  from public, anon, authenticated, service_role;

-- Extend the existing control-room snapshot without replacing its public RPC
-- or changing any generation-policy dependency.
do $preserve_ai_control_room_snapshot$
declare
  installed_definition text;
  cloned_definition text;
begin
  if to_regprocedure(
    'content_factory_private.ai_learning_control_room_snapshot_pre_historical_case_v1(uuid,text,uuid,text)'
  ) is null then
    installed_definition := pg_catalog.pg_get_functiondef(
      'content_factory_private.ai_learning_control_room_snapshot(uuid,text,uuid,text)'
        ::regprocedure
    );
    cloned_definition := regexp_replace(
      installed_definition,
      'FUNCTION content_factory_private\.ai_learning_control_room_snapshot\(',
      'FUNCTION content_factory_private.ai_learning_control_room_snapshot_pre_historical_case_v1(',
      'i'
    );
    if cloned_definition = installed_definition then
      raise exception using
        errcode = '55000',
        message = 'ai_historical_control_room_clone_failed';
    end if;
    execute cloned_definition;
  end if;
end;
$preserve_ai_control_room_snapshot$;

revoke all on function
  content_factory_private
    .ai_learning_control_room_snapshot_pre_historical_case_v1(
      uuid, text, uuid, text
    )
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_learning_control_room_snapshot(
    p_organization_id uuid,
    p_product_category text,
    p_actor_id uuid,
    p_actor_role text
  )
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  category_value text :=
    content_factory_private.require_ai_product_category(p_product_category);
  base_value jsonb;
  historical_value jsonb;
  category_detail_value jsonb;
  categories_value jsonb;
  capabilities_value jsonb;
  guidance_value jsonb;
  event_cursor_value bigint;
  can_mutate boolean := p_actor_role = any(array['owner', 'admin', 'producer']);
begin
  base_value := content_factory_private
    .ai_learning_control_room_snapshot_pre_historical_case_v1(
      p_organization_id,
      category_value,
      p_actor_id,
      p_actor_role
    );
  historical_value := content_factory_private.ai_historical_case_snapshot(
    p_organization_id,
    category_value
  );

  event_cursor_value := greatest(
    coalesce((base_value ->> 'event_cursor')::bigint, 0),
    coalesce((historical_value ->> 'event_cursor')::bigint, 0)
  );
  category_detail_value :=
    coalesce(base_value -> 'category_detail', '{}'::jsonb) ||
    jsonb_build_object(
      'historical_cases', historical_value -> 'historical_cases',
      'historical_case_summary',
        historical_value -> 'historical_case_summary',
      'historical_case_evidence',
        historical_value -> 'historical_case_evidence',
      'batches', historical_value -> 'batches',
      'historical_case_event_cursor',
        (historical_value ->> 'event_cursor')::bigint,
      'confirmed_historical_case_aggregate_can_affect_generation_policy', true,
      'pending_historical_cases_affect_generation', false,
      'exact_product_binding_required_for_generation', true,
      'historical_case_raw_prose_excluded', true
    );

  select coalesce(jsonb_agg(
    category_item || jsonb_build_object(
      'historical_case_count', (
        select count(*)::integer
        from content_factory.ai_historical_case_events historical_case
        where historical_case.organization_id = p_organization_id
          and historical_case.product_category =
            category_item ->> 'product_category'
      ),
      'historical_case_pending_count', (
        select count(*)::integer
        from content_factory.ai_historical_case_events historical_case
        where historical_case.organization_id = p_organization_id
          and historical_case.product_category =
            category_item ->> 'product_category'
          and not exists (
            select 1
            from content_factory.ai_historical_case_decisions decision
            where decision.organization_id = historical_case.organization_id
              and decision.product_category = historical_case.product_category
              and decision.case_id = historical_case.case_id
          )
      )
    ) order by ordinal
  ), '[]'::jsonb)
  into categories_value
  from jsonb_array_elements(base_value -> 'categories') with ordinality
    as category(category_item, ordinal);

  capabilities_value := coalesce(base_value -> 'capabilities', '{}'::jsonb) ||
    jsonb_build_object(
      'can_import_historical_cases', can_mutate,
      'can_decide_historical_case', can_mutate,
      'can_read_historical_cases', true,
      'historical_case_batch_limit', 200,
      'historical_case_snapshot_limit', 500,
      'historical_case_metric_limit', 20,
      'confirmed_historical_case_aggregate_can_affect_generation_policy', true,
      'pending_historical_cases_affect_generation', false,
      'exact_product_binding_required_for_generation', true,
      'cross_category_case_inference_forbidden', true
    );
  guidance_value := coalesce(base_value -> 'guidance', '{}'::jsonb) ||
    jsonb_build_object(
      'raw_historical_cases_enter_prompt_automatically', false,
      'confirmed_historical_case_aggregate_can_affect_generation_policy', true,
      'pending_historical_cases_affect_generation', false,
      'exact_product_binding_required_for_generation', true,
      'historical_case_raw_prose_excluded', true,
      'historical_learning_eligible_count',
        (historical_value #>>
          '{historical_case_evidence,historical_learning_eligible_count}')
            ::integer,
      'historical_learning_missing_exact_product_binding_count',
        (historical_value #>>
          '{historical_case_evidence,missing_exact_product_binding_count}')
            ::integer,
      'historical_learning_next_action', case
        when (historical_value #>>
          '{historical_case_evidence,missing_exact_product_binding_count}')
            ::integer > 0
          then 'Привяжите внешний SKU к точному внутреннему товару'
        else null
      end
    );

  return base_value || jsonb_build_object(
    'state_version', event_cursor_value,
    'event_cursor', event_cursor_value,
    'categories', categories_value,
    'category_detail', category_detail_value,
    'historical_cases', historical_value -> 'historical_cases',
    'historical_case_summary',
      historical_value -> 'historical_case_summary',
    'historical_case_evidence',
      historical_value -> 'historical_case_evidence',
    'batches', historical_value -> 'batches',
    'capabilities', capabilities_value,
    'guidance', guidance_value
  );
end;
$$;

revoke all on function
  content_factory_private.ai_learning_control_room_snapshot(
    uuid, text, uuid, text
  )
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.require_ai_historical_import_actor(
    p_organization_id uuid,
    p_actor_profile_id uuid
  )
returns text
language plpgsql
security definer
stable
set search_path = ''
as $$
declare
  actor_role_value text;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception using
      errcode = '42501',
      message = 'ai_historical_case_service_role_required';
  end if;
  if p_organization_id is null or p_actor_profile_id is null then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_actor_context_invalid';
  end if;
  select membership.role
  into actor_role_value
  from content_factory.memberships membership
  join content_factory.organizations organization
    on organization.id = membership.organization_id
   and organization.status = 'active'
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where membership.organization_id = p_organization_id
    and membership.profile_id = p_actor_profile_id
    and membership.status = 'active'
    and membership.role = any(array['owner', 'admin', 'producer']);
  if actor_role_value is null then
    raise exception using
      errcode = '42501',
      message = 'ai_historical_case_actor_not_allowed';
  end if;
  return actor_role_value;
end;
$$;

revoke all on function
  content_factory_private.require_ai_historical_import_actor(uuid, uuid)
  from public, anon, authenticated, service_role;

create or replace function
  public.creator_authorize_ai_historical_case_import(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  actor_profile_id_value uuid;
  source_id_value uuid;
  category_value text;
  actor_role_value text;
  source_row content_factory.ai_category_knowledge_sources%rowtype;
  source_receipt_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'actor_profile_id', 'source_id',
      'product_category'
    ])
  )
  or jsonb_typeof(p_payload -> 'organization_id') <> 'string'
  or jsonb_typeof(p_payload -> 'actor_profile_id') <> 'string'
  or jsonb_typeof(p_payload -> 'source_id') <> 'string' then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_authorization_payload_invalid';
  end if;
  begin
    organization_id_value := (p_payload ->> 'organization_id')::uuid;
    actor_profile_id_value := (p_payload ->> 'actor_profile_id')::uuid;
    source_id_value := (p_payload ->> 'source_id')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_authorization_payload_invalid';
  end;
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  actor_role_value := content_factory_private
    .require_ai_historical_import_actor(
      organization_id_value,
      actor_profile_id_value
    );

  select source.*
  into source_row
  from content_factory.ai_category_knowledge_sources source
  where source.organization_id = organization_id_value
    and source.id = source_id_value
    and source.product_category = category_value
    and source.source_kind = 'file'
    and source.status = 'active'
    and source.rights_confirmed
    and source.bucket_id = 'contentengine-knowledge'
    and source.object_name is not null
    and source.original_filename is not null
    and source.mime_type in (
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/csv'
    )
    and source.size_bytes between 1 and 26214400
    and source.sha256 ~ '^[0-9a-f]{64}$';
  if source_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'ai_historical_case_import_source_not_authorized';
  end if;

  source_receipt_value := jsonb_build_object(
    'source_id', source_row.id,
    'product_category', source_row.product_category,
    'bucket_id', source_row.bucket_id,
    'object_name', source_row.object_name,
    'original_filename', source_row.original_filename,
    'mime_type', source_row.mime_type,
    'size_bytes', source_row.size_bytes,
    'sha256', source_row.sha256,
    'rights_confirmed', source_row.rights_confirmed,
    'event_cursor', source_row.event_cursor
  );
  return jsonb_build_object(
    'ok', true,
    'organization_id', organization_id_value,
    'actor_profile_id', actor_profile_id_value,
    'actor_role', actor_role_value,
    'source', source_receipt_value,
    'source_receipt_hash',
      content_factory_private.json_hash(source_receipt_value),
    'server_parser_authorized', true,
    'bounded_source_receipt', true
  );
end;
$$;

revoke all on function
  public.creator_authorize_ai_historical_case_import(jsonb)
  from public, anon, authenticated;
grant execute on function
  public.creator_authorize_ai_historical_case_import(jsonb)
  to service_role;

create or replace function public.creator_import_ai_historical_case_batch(
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
  actor_role text;
  source_id_value uuid;
  source_row content_factory.ai_category_knowledge_sources%rowtype;
  default_category_value text;
  original_filename_value text;
  source_sha256_value text;
  schema_version_value text;
  parser_version_value text;
  manifest_sha256_value text;
  idempotency_key_value text;
  batch_index_value integer;
  batch_count_value integer;
  parsed_row_count_value integer;
  parser_quarantined_row_count_value integer;
  parser_quarantine_summary_value jsonb;
  parser_quarantine_summary_total integer;
  case_count_value integer;
  matched_case_count_value integer;
  quarantined_case_count_value integer;
  good_case_count_value integer;
  bad_case_count_value integer;
  review_case_count_value integer;
  import_status_value text;
  per_category_summary_value jsonb;
  normalized_cases_value jsonb := '[]'::jsonb;
  normalized_case_value jsonb;
  case_value jsonb;
  provenance_value jsonb;
  metrics_value jsonb;
  external_case_id_value text;
  case_category_value text;
  requested_product_id_value text;
  product_sku_value text;
  marketplace_sku_value text;
  product_title_value text;
  brand_value text;
  platform_value text;
  channel_value text;
  period_start_value date;
  period_end_value date;
  outcome_value text;
  outcome_dimension_value text;
  status_label_value text;
  confidence_value numeric;
  creative_angle_value text;
  source_sheet_value text;
  source_row_value integer;
  row_hash_value text;
  parsed_product_id_value uuid;
  id_product_id_value uuid;
  product_sku_product_id_value uuid;
  marketplace_product_id_value uuid;
  id_match_count integer;
  product_sku_match_count integer;
  marketplace_match_count integer;
  resolved_product_id_value uuid;
  resolution_status_value text;
  resolution_method_value text;
  quarantine_reason_value text;
  reference_count integer;
  resolved_reference_count integer;
  request_payload jsonb;
  request_hash_value text;
  replay_value jsonb;
  batch_replayed_value boolean := false;
  batch_row content_factory.ai_historical_case_import_batches%rowtype;
  snapshot_value jsonb;
  result_value jsonb;
  organization_batch_count bigint;
  organization_case_count bigint;
  source_batch_count bigint;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'actor_profile_id', 'schema_version',
      'product_category', 'source_id',
      'original_filename', 'source_sha256', 'parser_version',
      'manifest_sha256', 'idempotency_key', 'batch_index', 'batch_count',
      'parsed_row_count', 'parser_quarantined_row_count',
      'parser_quarantine_summary', 'cases'
    ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_batch_payload_invalid';
  end if;

  if jsonb_typeof(p_payload -> 'organization_id') <> 'string'
     or jsonb_typeof(p_payload -> 'actor_profile_id') <> 'string' then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_actor_context_invalid';
  end if;
  begin
    organization_id := (p_payload ->> 'organization_id')::uuid;
    user_id := (p_payload ->> 'actor_profile_id')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_actor_context_invalid';
  end;
  actor_role := content_factory_private.require_ai_historical_import_actor(
    organization_id,
    user_id
  );
  default_category_value :=
    content_factory_private.require_ai_product_category(
      p_payload ->> 'product_category'
    );

  if jsonb_typeof(p_payload -> 'source_id') <> 'string' then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_source_invalid';
  end if;
  begin
    source_id_value := (p_payload ->> 'source_id')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_source_invalid';
  end;

  select source.*
  into source_row
  from content_factory.ai_category_knowledge_sources source
  where source.organization_id = organization_id
    and source.id = source_id_value
    and source.product_category = default_category_value
    and source.source_kind = 'file'
    and source.status = 'active'
    and source.rights_confirmed
    and source.bucket_id = 'contentengine-knowledge'
    and source.object_name is not null
    and source.original_filename is not null
    and source.mime_type in (
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/csv'
    )
    and source.size_bytes between 1 and 26214400
    and source.sha256 ~ '^[0-9a-f]{64}$';
  if source_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'ai_historical_case_source_not_found';
  end if;

  if jsonb_typeof(p_payload -> 'original_filename') <> 'string'
     or jsonb_typeof(p_payload -> 'source_sha256') <> 'string'
     or jsonb_typeof(p_payload -> 'schema_version') <> 'string'
     or jsonb_typeof(p_payload -> 'parser_version') <> 'string'
     or jsonb_typeof(p_payload -> 'manifest_sha256') <> 'string' then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_provenance_invalid';
  end if;
  original_filename_value := content_factory_private.require_text(
    p_payload, 'original_filename', 1, 240
  );
  source_sha256_value := lower(content_factory_private.require_text(
    p_payload, 'source_sha256', 64, 64
  ));
  schema_version_value := content_factory_private.require_text(
    p_payload, 'schema_version', 22, 22
  );
  parser_version_value := content_factory_private.require_text(
    p_payload, 'parser_version', 1, 80
  );
  manifest_sha256_value := lower(content_factory_private.require_text(
    p_payload, 'manifest_sha256', 64, 64
  ));
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if original_filename_value <> source_row.original_filename
     or source_sha256_value !~ '^[0-9a-f]{64}$'
     or schema_version_value <> 'ai_historical_cases.v1'
     or parser_version_value !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$'
     or manifest_sha256_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_provenance_invalid';
  end if;
  if source_sha256_value is distinct from source_row.sha256 then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_source_sha256_mismatch';
  end if;

  if coalesce(p_payload ->> 'batch_index', '') !~ '^[0-9]+$'
     or coalesce(p_payload ->> 'batch_count', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_batch_bounds_invalid';
  end if;
  begin
    batch_index_value := (p_payload ->> 'batch_index')::integer;
    batch_count_value := (p_payload ->> 'batch_count')::integer;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_batch_bounds_invalid';
  end;
  if batch_count_value < 1 or batch_count_value > 100
     or batch_index_value < 1 or batch_index_value > batch_count_value
     or jsonb_typeof(p_payload -> 'cases') <> 'array'
     or jsonb_array_length(p_payload -> 'cases') > 200 then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_batch_bounds_invalid';
  end if;
  case_count_value := jsonb_array_length(p_payload -> 'cases');

  if batch_index_value = 1 and not (
       p_payload ? 'parsed_row_count'
       and p_payload ? 'parser_quarantined_row_count'
       and p_payload ? 'parser_quarantine_summary'
     ) then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_parser_quarantine_required';
  end if;
  if (p_payload ? 'parsed_row_count'
      or p_payload ? 'parser_quarantined_row_count'
      or p_payload ? 'parser_quarantine_summary')
     and not (
       p_payload ? 'parsed_row_count'
       and p_payload ? 'parser_quarantined_row_count'
       and p_payload ? 'parser_quarantine_summary'
     ) then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_parser_quarantine_invalid';
  end if;
  if p_payload ? 'parsed_row_count' then
    if coalesce(p_payload ->> 'parsed_row_count', '') !~ '^[0-9]+$'
       or coalesce(p_payload ->> 'parser_quarantined_row_count', '')
            !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_parser_quarantine_invalid';
    end if;
    begin
      parsed_row_count_value :=
        (p_payload ->> 'parsed_row_count')::integer;
      parser_quarantined_row_count_value :=
        (p_payload ->> 'parser_quarantined_row_count')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_parser_quarantine_invalid';
    end;
    parser_quarantine_summary_value := content_factory_private
      .normalize_ai_historical_parser_quarantine(
        p_payload -> 'parser_quarantine_summary'
      );
  else
    parsed_row_count_value := case_count_value;
    parser_quarantined_row_count_value := 0;
    parser_quarantine_summary_value := '{}'::jsonb;
  end if;
  select coalesce(sum((summary.value #>> '{}')::integer), 0)::integer
  into parser_quarantine_summary_total
  from jsonb_each(parser_quarantine_summary_value) summary(key, value);
  if parsed_row_count_value < greatest(1, case_count_value)
     or parsed_row_count_value > 5000000
     or parser_quarantined_row_count_value < 0
     or parser_quarantined_row_count_value > parsed_row_count_value
     or parser_quarantine_summary_total <>
       parser_quarantined_row_count_value
     or (parser_quarantined_row_count_value = 0
       and parser_quarantine_summary_value <> '{}'::jsonb)
     or (parser_quarantined_row_count_value > 0
       and parser_quarantine_summary_value = '{}'::jsonb)
     or (case_count_value = 0
       and parser_quarantined_row_count_value <> parsed_row_count_value) then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_parser_quarantine_invalid';
  end if;

  for case_value in
    select item.value
    from jsonb_array_elements(p_payload -> 'cases') with ordinality
      as item(value, ordinal)
    order by item.ordinal
  loop
    if jsonb_typeof(case_value) <> 'object'
       or exists (
         select 1
         from jsonb_object_keys(case_value) case_key
         where case_key <> all(array[
           'external_case_id', 'product_category', 'product_id',
           'product_sku', 'marketplace_sku', 'product_title', 'brand',
           'platform', 'channel', 'period_start', 'period_end', 'outcome',
           'outcome_dimension', 'status_label', 'metrics', 'confidence',
           'creative_angle', 'provenance'
         ])
       ) then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_payload_invalid';
    end if;

    external_case_id_value := content_factory_private.require_text(
      case_value, 'external_case_id', 1, 180
    );
    if external_case_id_value ~ '[[:cntrl:]]' then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_payload_invalid';
    end if;
    case_category_value :=
      content_factory_private.require_ai_product_category(
        case_value ->> 'product_category'
      );

    if jsonb_typeof(case_value -> 'product_title') <> 'string'
       or jsonb_typeof(case_value -> 'brand') <> 'string'
       or jsonb_typeof(case_value -> 'platform') <> 'string'
       or jsonb_typeof(case_value -> 'channel') <> 'string'
       or jsonb_typeof(case_value -> 'status_label') <> 'string'
       or jsonb_typeof(case_value -> 'period_start') <> 'string'
       or jsonb_typeof(case_value -> 'period_end') <> 'string'
       or jsonb_typeof(case_value -> 'outcome') <> 'string'
       or jsonb_typeof(case_value -> 'outcome_dimension') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_payload_invalid';
    end if;
    product_title_value := content_factory_private.require_text(
      case_value, 'product_title', 2, 240
    );
    brand_value := content_factory_private.require_text(
      case_value, 'brand', 1, 120
    );
    platform_value := lower(content_factory_private.require_text(
      case_value, 'platform', 1, 40
    ));
    channel_value := lower(content_factory_private.require_text(
      case_value, 'channel', 1, 60
    ));
    status_label_value := content_factory_private.require_text(
      case_value, 'status_label', 1, 80
    );
    if product_title_value ~ '[[:cntrl:]]'
       or brand_value ~ '[[:cntrl:]]'
       or status_label_value ~ '[[:cntrl:]]'
       or platform_value !~ '^[a-z0-9][a-z0-9_.:-]{0,39}$'
       or channel_value !~ '^[a-z0-9][a-z0-9_.:-]{0,59}$' then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_payload_invalid';
    end if;

    if (case_value ->> 'period_start') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
       or (case_value ->> 'period_end') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_period_invalid';
    end if;
    begin
      period_start_value := (case_value ->> 'period_start')::date;
      period_end_value := (case_value ->> 'period_end')::date;
    exception when datetime_field_overflow then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_period_invalid';
    end;
    if period_end_value < period_start_value
       or period_end_value > period_start_value + 3660 then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_period_invalid';
    end if;

    outcome_value := lower(btrim(case_value ->> 'outcome'));
    outcome_dimension_value := lower(btrim(
      case_value ->> 'outcome_dimension'
    ));
    if outcome_value not in ('good', 'bad', 'review')
       or outcome_dimension_value not in (
         'overall', 'overall_performance', 'sales', 'orders', 'conversion',
         'organic_growth', 'buyout', 'engagement', 'cart_to_order',
         'visit_to_cart', 'visit_to_order', 'sale_per_view', 'revenue',
         'profitability', 'ad_efficiency', 'advertising_efficiency',
         'product_card_conversion', 'inventory', 'evidence_sufficiency',
         'content_conversion', 'purchase_transition', 'attribution_window',
         'product_mapping', 'funnel', 'attribution', 'creative_angle',
         'data_quality', 'other'
       ) then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_outcome_invalid';
    end if;
    metrics_value := content_factory_private
      .normalize_ai_historical_case_metrics(case_value -> 'metrics');
    if jsonb_typeof(case_value -> 'confidence') <> 'number' then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_confidence_invalid';
    end if;
    begin
      confidence_value := (case_value ->> 'confidence')::numeric;
    exception when others then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_confidence_invalid';
    end;
    if confidence_value < 0 or confidence_value > 1 then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_confidence_invalid';
    end if;

    creative_angle_value := null;
    if case_value ? 'creative_angle'
       and case_value -> 'creative_angle' <> 'null'::jsonb then
      if jsonb_typeof(case_value -> 'creative_angle') <> 'string' then
        raise exception using
          errcode = '22023',
          message = 'ai_historical_case_creative_angle_invalid';
      end if;
      creative_angle_value := nullif(lower(btrim(
        case_value ->> 'creative_angle'
      )), '');
      if creative_angle_value is not null
         and creative_angle_value not in (
           'product_focus', 'trust_builder', 'demonstration', 'comparison',
           'objection_handling', 'curiosity_gap'
         ) then
        raise exception using
          errcode = '22023',
          message = 'ai_historical_case_creative_angle_invalid';
      end if;
    end if;

    if jsonb_typeof(case_value -> 'provenance') <> 'object'
       or exists (
         select 1
         from jsonb_object_keys(case_value -> 'provenance') provenance_key
         where provenance_key <> all(array['sheet', 'row', 'row_hash'])
       ) then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_provenance_invalid';
    end if;
    provenance_value := case_value -> 'provenance';
    if jsonb_typeof(provenance_value -> 'sheet') <> 'string'
       or jsonb_typeof(provenance_value -> 'row_hash') <> 'string'
       or coalesce(provenance_value ->> 'row', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_provenance_invalid';
    end if;
    source_sheet_value := content_factory_private.require_text(
      provenance_value, 'sheet', 1, 180
    );
    row_hash_value := lower(content_factory_private.require_text(
      provenance_value, 'row_hash', 64, 64
    ));
    begin
      source_row_value := (provenance_value ->> 'row')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_provenance_invalid';
    end;
    if source_sheet_value ~ '[[:cntrl:]]'
       or source_row_value < 1 or source_row_value > 1048576
       or row_hash_value !~ '^[0-9a-f]{64}$' then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_provenance_invalid';
    end if;

    requested_product_id_value := null;
    product_sku_value := null;
    marketplace_sku_value := null;
    if case_value ? 'product_id' and case_value -> 'product_id' <> 'null'::jsonb then
      if jsonb_typeof(case_value -> 'product_id') <> 'string' then
        raise exception using
          errcode = '22023',
          message = 'ai_historical_case_product_reference_invalid';
      end if;
      requested_product_id_value := nullif(btrim(
        case_value ->> 'product_id'
      ), '');
      if length(coalesce(requested_product_id_value, '')) > 80 then
        raise exception using
          errcode = '22023',
          message = 'ai_historical_case_product_reference_invalid';
      end if;
    end if;
    if case_value ? 'product_sku' and case_value -> 'product_sku' <> 'null'::jsonb then
      if jsonb_typeof(case_value -> 'product_sku') <> 'string' then
        raise exception using
          errcode = '22023',
          message = 'ai_historical_case_product_reference_invalid';
      end if;
      product_sku_value := nullif(btrim(case_value ->> 'product_sku'), '');
      if length(coalesce(product_sku_value, '')) > 120 then
        raise exception using
          errcode = '22023',
          message = 'ai_historical_case_product_reference_invalid';
      end if;
    end if;
    if case_value ? 'marketplace_sku'
       and case_value -> 'marketplace_sku' <> 'null'::jsonb then
      if jsonb_typeof(case_value -> 'marketplace_sku') <> 'string' then
        raise exception using
          errcode = '22023',
          message = 'ai_historical_case_product_reference_invalid';
      end if;
      marketplace_sku_value := nullif(btrim(
        case_value ->> 'marketplace_sku'
      ), '');
      if length(coalesce(marketplace_sku_value, '')) > 120 then
        raise exception using
          errcode = '22023',
          message = 'ai_historical_case_product_reference_invalid';
      end if;
    end if;

    id_product_id_value := null;
    product_sku_product_id_value := null;
    marketplace_product_id_value := null;
    id_match_count := 0;
    product_sku_match_count := 0;
    marketplace_match_count := 0;
    quarantine_reason_value := null;
    parsed_product_id_value := null;

    if requested_product_id_value is not null then
      begin
        parsed_product_id_value := requested_product_id_value::uuid;
      exception when invalid_text_representation then
        quarantine_reason_value := 'product_id_invalid';
      end;
      if parsed_product_id_value is not null then
        select count(*)::integer
        into id_match_count
        from content_factory.products product
        where product.organization_id = organization_id
          and product.id = parsed_product_id_value;
        if id_match_count = 1 then
          id_product_id_value := parsed_product_id_value;
        else
          quarantine_reason_value := coalesce(
            quarantine_reason_value, 'product_id_unmatched'
          );
        end if;
      end if;
    end if;

    if product_sku_value is not null then
      select count(*)::integer
      into product_sku_match_count
      from content_factory.products product
      where product.organization_id = organization_id
        and product.sku = product_sku_value;
      if product_sku_match_count = 1 then
        select product.id
        into product_sku_product_id_value
        from content_factory.products product
        where product.organization_id = organization_id
          and product.sku = product_sku_value;
      elsif product_sku_match_count > 1 then
        quarantine_reason_value := coalesce(
          quarantine_reason_value, 'product_sku_ambiguous'
        );
      end if;
    end if;

    if marketplace_sku_value is not null then
      select count(*)::integer
      into marketplace_match_count
      from content_factory.products product
      where product.organization_id = organization_id
        and product.current_wb_article = marketplace_sku_value;
      if marketplace_match_count = 1 then
        select product.id
        into marketplace_product_id_value
        from content_factory.products product
        where product.organization_id = organization_id
          and product.current_wb_article = marketplace_sku_value;
      elsif marketplace_match_count > 1 then
        quarantine_reason_value := coalesce(
          quarantine_reason_value, 'marketplace_sku_ambiguous'
        );
      end if;
    end if;

    reference_count :=
      case when requested_product_id_value is null then 0 else 1 end
      + case when product_sku_value is null then 0 else 1 end
      + case when marketplace_sku_value is null then 0 else 1 end;
    resolved_reference_count :=
      case when id_product_id_value is null then 0 else 1 end
      + case when product_sku_product_id_value is null then 0 else 1 end
      + case when marketplace_product_id_value is null then 0 else 1 end;
    resolved_product_id_value := coalesce(
      id_product_id_value,
      product_sku_product_id_value,
      marketplace_product_id_value
    );
    if quarantine_reason_value is null
       and (
         (id_product_id_value is not null
          and resolved_product_id_value <> id_product_id_value)
         or (product_sku_product_id_value is not null
          and resolved_product_id_value <> product_sku_product_id_value)
         or (marketplace_product_id_value is not null
          and resolved_product_id_value <> marketplace_product_id_value)
       ) then
      quarantine_reason_value := 'product_reference_conflict';
    end if;
    if quarantine_reason_value is null
       and resolved_product_id_value is not null
       and resolved_reference_count <> reference_count then
      quarantine_reason_value := 'product_reference_partial_match';
    end if;

    if reference_count = 0 then
      quarantine_reason_value := 'product_reference_missing';
    end if;
    if quarantine_reason_value is not null then
      resolution_status_value := 'quarantined';
      resolution_method_value := null;
      resolved_product_id_value := null;
    else
      resolution_status_value := 'matched';
      if resolved_product_id_value is not null then
        resolution_method_value := case
          when reference_count > 1 then 'consistent_exact_references'
          when id_product_id_value is not null then 'exact_product_id'
          when product_sku_product_id_value is not null then 'unique_product_sku'
          else 'unique_marketplace_sku'
        end;
      elsif product_sku_value is not null then
        resolution_method_value := 'source_external_sku';
      else
        resolution_method_value := 'source_marketplace_sku';
      end if;
    end if;

    normalized_case_value := jsonb_build_object(
      'external_case_id', external_case_id_value,
      'product_category', case_category_value,
      'requested_product_id', requested_product_id_value,
      'product_sku', product_sku_value,
      'marketplace_sku', marketplace_sku_value,
      'product_id', resolved_product_id_value,
      'product_title', product_title_value,
      'brand', brand_value,
      'platform', platform_value,
      'channel', channel_value,
      'period_start', period_start_value,
      'period_end', period_end_value,
      'outcome', outcome_value,
      'outcome_dimension', outcome_dimension_value,
      'status_label', status_label_value,
      'metrics', metrics_value,
      'confidence', confidence_value,
      'creative_angle', creative_angle_value,
      'resolution_status', resolution_status_value,
      'resolution_method', resolution_method_value,
      'quarantine_reason', quarantine_reason_value,
      'source_sheet', source_sheet_value,
      'source_row', source_row_value,
      'row_hash', row_hash_value
    );
    normalized_cases_value := normalized_cases_value ||
      jsonb_build_array(normalized_case_value);
  end loop;

  if exists (
    select 1
    from jsonb_array_elements(normalized_cases_value) item(value)
    group by item.value ->> 'external_case_id'
    having count(*) > 1
  ) then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_external_id_duplicate';
  end if;

  -- An external SKU is a stable source identity only when every occurrence in
  -- this normalized batch names the same product/brand.  Conflicting labels
  -- quarantine the identity instead of guessing which row is right.
  with conflicts as (
    select identity_key
    from (
      select
        case
          when item.value ->> 'resolution_method' = 'source_external_sku'
            then 'product:' || (item.value ->> 'product_sku')
          when item.value ->> 'resolution_method' = 'source_marketplace_sku'
            then 'marketplace:' || (item.value ->> 'marketplace_sku')
        end as identity_key,
        lower(item.value ->> 'product_title') || chr(31) ||
          lower(item.value ->> 'brand') as identity_label
      from jsonb_array_elements(normalized_cases_value) item(value)
      where item.value ->> 'resolution_method' in (
        'source_external_sku', 'source_marketplace_sku'
      )
    ) identity
    where identity_key is not null
    group by identity_key
    having count(distinct identity_label) > 1
  )
  select coalesce(jsonb_agg(
    case when exists (
      select 1
      from conflicts conflict
      where conflict.identity_key = case
        when item.value ->> 'resolution_method' = 'source_external_sku'
          then 'product:' || (item.value ->> 'product_sku')
        when item.value ->> 'resolution_method' = 'source_marketplace_sku'
          then 'marketplace:' || (item.value ->> 'marketplace_sku')
      end
    ) then item.value || jsonb_build_object(
      'product_id', null,
      'resolution_status', 'quarantined',
      'resolution_method', null,
      'quarantine_reason', 'product_reference_conflict'
    ) else item.value end
    order by item.value ->> 'external_case_id'
  ), '[]'::jsonb)
  into normalized_cases_value
  from jsonb_array_elements(normalized_cases_value) item(value);

  select coalesce(jsonb_agg(
    item.value || jsonb_build_object(
      'case_hash', content_factory_private.json_hash(jsonb_build_object(
        'organization_id', organization_id,
        'source_id', source_id_value,
        'case', item.value
      ))
    )
    order by item.value ->> 'external_case_id'
  ), '[]'::jsonb)
  into normalized_cases_value
  from jsonb_array_elements(normalized_cases_value) item(value);

  select
    count(*) filter (
      where item.value ->> 'resolution_status' = 'matched'
    )::integer,
    count(*) filter (
      where item.value ->> 'resolution_status' = 'quarantined'
    )::integer,
    count(*) filter (
      where item.value ->> 'outcome' = 'good'
    )::integer,
    count(*) filter (
      where item.value ->> 'outcome' = 'bad'
    )::integer,
    count(*) filter (
      where item.value ->> 'outcome' = 'review'
    )::integer
  into
    matched_case_count_value,
    quarantined_case_count_value,
    good_case_count_value,
    bad_case_count_value,
    review_case_count_value
  from jsonb_array_elements(normalized_cases_value) item(value);

  select jsonb_object_agg(summary.product_category, jsonb_build_object(
    'total', summary.total_count,
    'matched', summary.matched_count,
    'quarantined', summary.quarantined_count,
    'good', summary.good_count,
    'bad', summary.bad_count,
    'review', summary.review_count
  ) order by summary.product_category)
  into per_category_summary_value
  from (
    select
      item.value ->> 'product_category' as product_category,
      count(*)::integer as total_count,
      count(*) filter (
        where item.value ->> 'resolution_status' = 'matched'
      )::integer as matched_count,
      count(*) filter (
        where item.value ->> 'resolution_status' = 'quarantined'
      )::integer as quarantined_count,
      count(*) filter (
        where item.value ->> 'outcome' = 'good'
      )::integer as good_count,
      count(*) filter (
        where item.value ->> 'outcome' = 'bad'
      )::integer as bad_count,
      count(*) filter (
        where item.value ->> 'outcome' = 'review'
      )::integer as review_count
    from jsonb_array_elements(normalized_cases_value) item(value)
    group by item.value ->> 'product_category'
  ) summary;

  per_category_summary_value := coalesce(
    per_category_summary_value,
    jsonb_build_object(default_category_value, jsonb_build_object(
      'total', 0,
      'matched', 0,
      'quarantined', 0,
      'good', 0,
      'bad', 0,
      'review', 0
    ))
  );

  import_status_value := case
    when case_count_value = 0 then 'parser_rejected'
    when matched_case_count_value = 0 then 'quarantined'
    when quarantined_case_count_value = 0
      and parser_quarantined_row_count_value = 0 then 'completed'
    else 'completed_with_quarantine'
  end;
  request_payload := jsonb_build_object(
    'schema_version', schema_version_value,
    'default_product_category', default_category_value,
    'source_id', source_id_value,
    'original_filename', original_filename_value,
    'source_sha256', source_sha256_value,
    'parser_version', parser_version_value,
    'manifest_sha256', manifest_sha256_value,
    'batch_index', batch_index_value,
    'batch_count', batch_count_value,
    'parsed_row_count', parsed_row_count_value,
    'parser_quarantined_row_count',
      parser_quarantined_row_count_value,
    'parser_quarantine_summary', parser_quarantine_summary_value,
    -- Stable parser identity intentionally excludes catalog-derived product_id,
    -- resolution_method, and quarantine projections.  A later catalog change
    -- must not turn an already committed physical chunk into a conflict.
    'cases', p_payload -> 'cases'
  );
  request_hash_value := content_factory_private.json_hash(request_payload);
  replay_value := content_factory_private.begin_command(
    organization_id,
    'creator_import_ai_historical_case_batch',
    idempotency_key_value,
    request_payload
  );
  if replay_value is not null then
    return replay_value || jsonb_build_object('replayed', true);
  end if;

  -- Serialize every physical chunk for one source manifest.  This makes a
  -- reload with a fresh command key race-safe: either it observes the exact
  -- committed chunk receipt or it becomes the sole writer for that chunk.
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || source_id_value::text),
    hashtext('ai_historical_manifest:' || manifest_sha256_value)
  );

  if exists (
    select 1
    from content_factory.ai_historical_case_import_batches existing_batch
    where existing_batch.organization_id = organization_id
      and existing_batch.source_id = source_id_value
      and existing_batch.manifest_sha256 = manifest_sha256_value
      and (
        existing_batch.batch_count <> batch_count_value
        or existing_batch.original_filename <> original_filename_value
        or existing_batch.source_sha256 <> source_sha256_value
        or existing_batch.schema_version <> schema_version_value
        or existing_batch.parser_version <> parser_version_value
        or existing_batch.default_product_category <>
          default_category_value
      )
  ) then
    raise exception using
      errcode = '23505',
      message = 'ai_historical_case_manifest_conflict';
  end if;

  select existing_batch.*
  into batch_row
  from content_factory.ai_historical_case_import_batches existing_batch
  where existing_batch.organization_id = organization_id
    and existing_batch.source_id = source_id_value
    and existing_batch.manifest_sha256 = manifest_sha256_value
    and existing_batch.batch_index = batch_index_value;

  if batch_row.id is not null and (
       batch_row.batch_count is distinct from batch_count_value
       or batch_row.original_filename is distinct from original_filename_value
       or batch_row.source_sha256 is distinct from source_sha256_value
       or batch_row.schema_version is distinct from schema_version_value
       or batch_row.parser_version is distinct from parser_version_value
       or batch_row.default_product_category is distinct from
         default_category_value
       or batch_row.parsed_row_count is distinct from parsed_row_count_value
       or batch_row.parser_quarantined_row_count is distinct from
         parser_quarantined_row_count_value
       or batch_row.parser_quarantine_summary is distinct from
         parser_quarantine_summary_value
       or batch_row.case_count is distinct from case_count_value
       or batch_row.request_hash is distinct from request_hash_value
     ) then
    raise exception using
      errcode = '23505',
      message = 'ai_historical_case_manifest_conflict';
  end if;
  batch_replayed_value := batch_row.id is not null;

  if batch_row.id is null then
    if exists (
    select 1
    from jsonb_array_elements(normalized_cases_value) item(value)
    join content_factory.ai_historical_case_events historical_case
      on historical_case.organization_id = organization_id
     and historical_case.source_id = source_id_value
     and historical_case.external_case_id =
       item.value ->> 'external_case_id'
    ) then
      raise exception using
        errcode = '23505',
        message = 'ai_historical_case_already_imported';
    end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('ai_historical_case_import_quota')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || source_id_value::text),
    hashtext('ai_historical_case_source_quota')
  );
  select count(*)::bigint
  into organization_batch_count
  from content_factory.ai_historical_case_import_batches batch
  where batch.organization_id = organization_id;
  select count(*)::bigint
  into organization_case_count
  from content_factory.ai_historical_case_events historical_case
  where historical_case.organization_id = organization_id;
  select count(*)::bigint
  into source_batch_count
  from content_factory.ai_historical_case_import_batches batch
  where batch.organization_id = organization_id
    and batch.source_id = source_id_value;
  if organization_batch_count >= 10000
     or organization_case_count + case_count_value > 1000000
     or source_batch_count >= 100 then
    raise exception using
      errcode = '54000',
      message = 'ai_historical_case_quota_exceeded';
  end if;

  insert into content_factory.ai_historical_case_import_batches (
    organization_id, source_id, default_product_category,
    original_filename, source_sha256, schema_version, parser_version,
    manifest_sha256, batch_index, batch_count, case_count,
    parsed_row_count, parser_quarantined_row_count,
    parser_quarantine_summary,
    matched_case_count, quarantined_case_count,
    good_case_count, bad_case_count, review_case_count,
    per_category_summary, import_status, imported_by,
    request_hash, idempotency_key
  ) values (
    organization_id, source_id_value, default_category_value,
    original_filename_value, source_sha256_value, schema_version_value,
    parser_version_value, manifest_sha256_value, batch_index_value,
    batch_count_value, case_count_value,
    parsed_row_count_value, parser_quarantined_row_count_value,
    parser_quarantine_summary_value, matched_case_count_value,
    quarantined_case_count_value, good_case_count_value,
    bad_case_count_value, review_case_count_value,
    per_category_summary_value, import_status_value, user_id,
    request_hash_value, idempotency_key_value
  ) returning * into batch_row;

  for normalized_case_value in
    select item.value
    from jsonb_array_elements(normalized_cases_value) item(value)
    order by item.value ->> 'external_case_id'
  loop
    insert into content_factory.ai_historical_case_events (
      batch_id, organization_id, source_id, product_category,
      external_case_id, product_id, requested_product_id,
      product_sku, marketplace_sku, product_title, brand,
      platform, channel, period_start, period_end, outcome,
      outcome_dimension, status_label, metrics, confidence,
      creative_angle, resolution_status, resolution_method,
      quarantine_reason, source_filename, source_sha256,
      source_sheet, source_row, row_hash, schema_version,
      parser_version, case_hash
    ) values (
      batch_row.id,
      organization_id,
      source_id_value,
      normalized_case_value ->> 'product_category',
      normalized_case_value ->> 'external_case_id',
      nullif(normalized_case_value ->> 'product_id', '')::uuid,
      nullif(normalized_case_value ->> 'requested_product_id', ''),
      nullif(normalized_case_value ->> 'product_sku', ''),
      nullif(normalized_case_value ->> 'marketplace_sku', ''),
      normalized_case_value ->> 'product_title',
      normalized_case_value ->> 'brand',
      normalized_case_value ->> 'platform',
      normalized_case_value ->> 'channel',
      (normalized_case_value ->> 'period_start')::date,
      (normalized_case_value ->> 'period_end')::date,
      normalized_case_value ->> 'outcome',
      normalized_case_value ->> 'outcome_dimension',
      normalized_case_value ->> 'status_label',
      normalized_case_value -> 'metrics',
      (normalized_case_value ->> 'confidence')::numeric,
      nullif(normalized_case_value ->> 'creative_angle', ''),
      normalized_case_value ->> 'resolution_status',
      nullif(normalized_case_value ->> 'resolution_method', ''),
      nullif(normalized_case_value ->> 'quarantine_reason', ''),
      original_filename_value,
      source_sha256_value,
      normalized_case_value ->> 'source_sheet',
      (normalized_case_value ->> 'source_row')::integer,
      normalized_case_value ->> 'row_hash',
      schema_version_value,
      parser_version_value,
      normalized_case_value ->> 'case_hash'
    );
  end loop;

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'ai_historical_case_batch_imported',
    'ai_historical_case_import_batch',
    batch_row.id::text,
    jsonb_build_object(
      'source_id', source_id_value,
      'schema_version', schema_version_value,
      'parser_version', parser_version_value,
      'manifest_sha256', manifest_sha256_value,
      'case_count', case_count_value,
      'parsed_row_count', parsed_row_count_value,
      'parser_quarantined_row_count',
        parser_quarantined_row_count_value,
      'parser_quarantine_summary', parser_quarantine_summary_value,
      'matched_case_count', matched_case_count_value,
      'quarantined_case_count', quarantined_case_count_value,
      'per_category_summary', per_category_summary_value,
      'event_cursor', batch_row.event_cursor,
      'raw_prose_excluded', true,
      'provider_action', false,
      'generation_action', false,
      'spend_action', false
    ),
    'ai-historical-case-import:' || idempotency_key_value
  );
  end if;

  snapshot_value := content_factory_private.ai_learning_control_room_snapshot(
    organization_id,
    default_category_value,
    user_id,
    actor_role
  );
  result_value := jsonb_build_object(
    'ok', true,
    'replayed', batch_replayed_value,
    'batch', jsonb_build_object(
      'batch_id', batch_row.id,
      'source_id', batch_row.source_id,
      'import_status', batch_row.import_status,
      'batch_index', batch_row.batch_index,
      'batch_count', batch_row.batch_count,
      'case_count', batch_row.case_count,
      'parsed_row_count', batch_row.parsed_row_count,
      'parser_quarantined_row_count',
        batch_row.parser_quarantined_row_count,
      'parser_quarantine_summary', batch_row.parser_quarantine_summary,
      'matched_case_count', batch_row.matched_case_count,
      'quarantined_case_count', batch_row.quarantined_case_count,
      'per_category_summary', batch_row.per_category_summary,
      'request_hash', batch_row.request_hash,
      'event_cursor', batch_row.event_cursor
    ),
    'snapshot', snapshot_value
  );
  result_value := result_value || case
    when batch_row.case_count = 0 then jsonb_build_object(
      'ok', false,
      'status', 'parser_rejected_all',
      'source_id', batch_row.source_id,
      'parsed_row_count', batch_row.parsed_row_count,
      'parser_quarantined_row_count',
        batch_row.parser_quarantined_row_count,
      'parser_quarantine_summary', batch_row.parser_quarantine_summary,
      'retryable', true,
      'batch_persisted', true
    )
    else jsonb_build_object(
      'status', batch_row.import_status,
      'batch_persisted', true
    )
  end;
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_import_ai_historical_case_batch',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function public.creator_import_ai_historical_case_batch(jsonb)
  from public, anon, authenticated;
grant execute on function public.creator_import_ai_historical_case_batch(jsonb)
  to service_role;

create or replace function public.creator_decide_ai_historical_case(
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
  actor_role text;
  category_value text;
  case_id_value uuid;
  expected_event_id_value uuid;
  expected_scope_version_value integer;
  expected_event_cursor_value bigint;
  decision_value text;
  idempotency_key_value text;
  request_payload jsonb;
  request_hash_value text;
  replay_value jsonb;
  historical_case_row content_factory.ai_historical_case_events%rowtype;
  head_decision_row content_factory.ai_historical_case_decisions%rowtype;
  current_scope_version_value integer;
  current_event_id_value uuid;
  current_event_cursor_value bigint;
  decision_hash_value text;
  inserted_decision_row content_factory.ai_historical_case_decisions%rowtype;
  snapshot_value jsonb;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'product_category', 'case_id', 'event_id',
      'expected_scope_version', 'expected_event_cursor', 'decision',
      'confirmation', 'idempotency_key'
    ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_decision_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer']
  );
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  if jsonb_typeof(p_payload -> 'case_id') <> 'string'
     or jsonb_typeof(p_payload -> 'event_id') <> 'string'
     or jsonb_typeof(p_payload -> 'decision') <> 'string'
     or coalesce(p_payload ->> 'expected_scope_version', '') !~ '^[0-9]+$'
     or coalesce(p_payload ->> 'expected_event_cursor', '') !~ '^[0-9]+$'
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_decision_payload_invalid';
  end if;
  begin
    case_id_value := (p_payload ->> 'case_id')::uuid;
    expected_event_id_value := (p_payload ->> 'event_id')::uuid;
    expected_scope_version_value :=
      (p_payload ->> 'expected_scope_version')::integer;
    expected_event_cursor_value :=
      (p_payload ->> 'expected_event_cursor')::bigint;
  exception
    when invalid_text_representation or numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'ai_historical_case_decision_payload_invalid';
  end;
  if expected_scope_version_value < 0
     or expected_event_cursor_value < 1 then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_decision_payload_invalid';
  end if;
  decision_value := lower(btrim(p_payload ->> 'decision'));
  if decision_value not in ('confirm', 'reject') then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_decision_invalid';
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  request_payload := jsonb_build_object(
    'product_category', category_value,
    'case_id', case_id_value,
    'event_id', expected_event_id_value,
    'expected_scope_version', expected_scope_version_value,
    'expected_event_cursor', expected_event_cursor_value,
    'decision', decision_value,
    'confirmation', true
  );
  request_hash_value := content_factory_private.json_hash(request_payload);
  replay_value := content_factory_private.begin_command(
    organization_id,
    'creator_decide_ai_historical_case',
    idempotency_key_value,
    request_payload
  );
  if replay_value is not null then
    return replay_value;
  end if;

  select historical_case.*
  into historical_case_row
  from content_factory.ai_historical_case_events historical_case
  where historical_case.organization_id = organization_id
    and historical_case.product_category = category_value
    and historical_case.case_id = case_id_value
  for update;
  if historical_case_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'ai_historical_case_not_found';
  end if;

  select decision.*
  into head_decision_row
  from content_factory.ai_historical_case_decisions decision
  where decision.organization_id = organization_id
    and decision.product_category = category_value
    and decision.case_id = case_id_value
  order by decision.event_cursor desc
  limit 1;
  current_scope_version_value := coalesce(
    head_decision_row.resulting_scope_version, 0
  );
  current_event_id_value := coalesce(
    head_decision_row.id, historical_case_row.id
  );
  current_event_cursor_value := coalesce(
    head_decision_row.event_cursor, historical_case_row.event_cursor
  );
  if expected_scope_version_value <> current_scope_version_value
     or expected_event_id_value <> current_event_id_value
     or expected_event_cursor_value <> current_event_cursor_value then
    raise exception using
      errcode = '40001',
      message = 'ai_historical_case_refresh_required';
  end if;
  if decision_value = 'confirm'
     and historical_case_row.resolution_status <> 'matched' then
    raise exception using
      errcode = '55000',
      message = 'ai_historical_case_quarantined';
  end if;

  decision_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'organization_id', organization_id,
    'product_category', category_value,
    'case_id', case_id_value,
    'decision', decision_value,
    'expected_scope_version', expected_scope_version_value,
    'expected_event_id', expected_event_id_value,
    'expected_event_cursor', expected_event_cursor_value,
    'decided_by', user_id,
    'request_hash', request_hash_value
  ));
  insert into content_factory.ai_historical_case_decisions (
    organization_id, product_category, case_id, decision, reason_code,
    confirmation, expected_scope_version, resulting_scope_version,
    expected_event_id, expected_event_cursor, decided_by,
    request_hash, decision_hash, idempotency_key
  ) values (
    organization_id,
    category_value,
    case_id_value,
    decision_value,
    case decision_value
      when 'confirm' then 'operator_confirmed'
      else 'operator_rejected'
    end,
    true,
    expected_scope_version_value,
    expected_scope_version_value + 1,
    expected_event_id_value,
    expected_event_cursor_value,
    user_id,
    request_hash_value,
    decision_hash_value,
    idempotency_key_value
  ) returning * into inserted_decision_row;

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    case decision_value
      when 'confirm' then 'ai_historical_case_confirmed'
      else 'ai_historical_case_rejected'
    end,
    'ai_historical_case',
    case_id_value::text,
    jsonb_build_object(
      'product_category', category_value,
      'outcome', historical_case_row.outcome,
      'outcome_dimension', historical_case_row.outcome_dimension,
      'creative_angle', historical_case_row.creative_angle,
      'resulting_scope_version',
        inserted_decision_row.resulting_scope_version,
      'event_cursor', inserted_decision_row.event_cursor,
      'raw_prose_excluded', true,
      'provider_action', false,
      'generation_action', false,
      'spend_action', false
    ),
    'ai-historical-case-decision:' || idempotency_key_value
  );

  snapshot_value := content_factory_private.ai_learning_control_room_snapshot(
    organization_id,
    category_value,
    user_id,
    actor_role
  );
  result_value := jsonb_build_object(
    'ok', true,
    'decision', jsonb_build_object(
      'decision_id', inserted_decision_row.id,
      'case_id', case_id_value,
      'decision', decision_value,
      'scope_version', inserted_decision_row.resulting_scope_version,
      'event_id', inserted_decision_row.id,
      'event_cursor', inserted_decision_row.event_cursor,
      'decision_hash', decision_hash_value,
      'mutates_ai_effective_category_policies', false,
      'may_change_confirmed_historical_generation_advisory', true,
      'starts_generation', false,
      'spends_money', false
    ),
    'snapshot', snapshot_value
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_decide_ai_historical_case',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function public.creator_decide_ai_historical_case(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_decide_ai_historical_case(jsonb)
  to authenticated;

-- Preserve the installed v9 policy wrapper and add only bounded, aggregate
-- historical evidence.  Manual teaching-card policy wins whenever it has a
-- preferred or avoided angle.  Pending/review/quarantined/rejected cases are
-- absent from this calculation, and no raw cell, title, status label, URL, or
-- metric value enters the generation policy.
do $preserve_generation_learning_policy_for_historical_cases$
declare
  installed_definition text;
  cloned_definition text;
begin
  if to_regprocedure(
    'content_factory_private.creator_generation_learning_policy_pre_historical_case_v1(jsonb)'
  ) is null then
    installed_definition := pg_catalog.pg_get_functiondef(
      'public.creator_generation_learning_policy(jsonb)'::regprocedure
    );
    cloned_definition := regexp_replace(
      installed_definition,
      'FUNCTION public\.creator_generation_learning_policy\(',
      'FUNCTION content_factory_private.creator_generation_learning_policy_pre_historical_case_v1(',
      'i'
    );
    if cloned_definition = installed_definition then
      raise exception using
        errcode = '55000',
        message = 'ai_historical_generation_policy_clone_failed';
    end if;
    execute cloned_definition;
  end if;
end;
$preserve_generation_learning_policy_for_historical_cases$;

revoke all on function
  content_factory_private
    .creator_generation_learning_policy_pre_historical_case_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_learning_policy(
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
  base_policy jsonb;
  organization_id uuid;
  category_value text;
  media_id_value uuid;
  product_id_value uuid;
  manual_policy_row content_factory.ai_effective_category_policies%rowtype;
  historical_evidence_value jsonb;
  advisory_preferred_angle_value text;
  advisory_avoid_angle_value text;
  base_preferred_angle_value text;
  preferred_angle_value text;
  avoid_angle_value text;
  preferred_angle_changed boolean := false;
  manual_policy_active boolean := false;
  base_policy_applied boolean := false;
  advisory_available boolean := false;
  historical_fallback_allowed boolean := false;
  generation_allowed_value boolean;
  preferred_hook_patterns_value jsonb;
  selected_hook_patterns_value jsonb;
  reason_codes_value jsonb;
  safety_value jsonb;
  requested_model_value text;
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  base_policy := content_factory_private
    .creator_generation_learning_policy_pre_historical_case_v1(p_payload);
  category_value := lower(btrim(coalesce(
    base_policy ->> 'product_category',
    p_payload ->> 'product_category',
    ''
  )));
  if category_value not in (
    'cosmetics', 'baa', 'sports_food', 'food', 'household',
    'apparel', 'electronics', 'other'
  ) then
    return base_policy;
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  media_id_value := content_factory_private.require_uuid(p_payload, 'media_id');
  select media.product_id
  into product_id_value
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = media_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '42501',
      message = 'generation_learning_policy_media_invalid';
  end if;
  historical_evidence_value :=
    content_factory_private.ai_historical_product_case_evidence(
      organization_id,
      category_value,
      product_id_value
    );
  advisory_preferred_angle_value := nullif(
    historical_evidence_value ->> 'advisory_preferred_creative_angle', ''
  );
  advisory_avoid_angle_value := nullif(
    historical_evidence_value ->> 'advisory_avoid_creative_angle', ''
  );
  advisory_available := advisory_preferred_angle_value is not null
    or advisory_avoid_angle_value is not null;

  select policy.*
  into manual_policy_row
  from content_factory.ai_effective_category_policies policy
  where policy.organization_id = organization_id
    and policy.product_category = category_value
  order by policy.scope_version desc
  limit 1;
  manual_policy_active := manual_policy_row.id is not null and (
    manual_policy_row.preferred_creative_angle is not null
    or manual_policy_row.avoid_creative_angle is not null
  );
  base_policy_applied := base_policy -> 'applied' = 'true'::jsonb;
  historical_fallback_allowed :=
    not manual_policy_active
    and not base_policy_applied
    and advisory_available;

  generation_allowed_value :=
    base_policy -> 'generation_allowed' is distinct from 'false'::jsonb;
  base_preferred_angle_value := nullif(
    base_policy ->> 'preferred_angle', ''
  );
  preferred_angle_value := base_preferred_angle_value;
  avoid_angle_value := nullif(base_policy ->> 'avoid_angle', '');

  if historical_fallback_allowed then
    preferred_angle_value := coalesce(
      advisory_preferred_angle_value,
      preferred_angle_value
    );
    avoid_angle_value := coalesce(
      advisory_avoid_angle_value,
      avoid_angle_value
    );
    if preferred_angle_value is null
       or preferred_angle_value = avoid_angle_value then
      preferred_angle_value := case avoid_angle_value
        when 'product_focus' then 'trust_builder'
        else 'product_focus'
      end;
    end if;
    if avoid_angle_value is not distinct from preferred_angle_value then
      avoid_angle_value := null;
    end if;
  end if;

  preferred_angle_changed :=
    preferred_angle_value is distinct from base_preferred_angle_value;
  preferred_hook_patterns_value := case
    when preferred_angle_changed then '[]'::jsonb
    when jsonb_typeof(base_policy -> 'preferred_hook_patterns') = 'array'
      then base_policy -> 'preferred_hook_patterns'
    else '[]'::jsonb
  end;
  selected_hook_patterns_value := case
    when preferred_angle_changed then '[]'::jsonb
    when jsonb_typeof(base_policy -> 'selected_hook_patterns') = 'array'
      then base_policy -> 'selected_hook_patterns'
    else preferred_hook_patterns_value
  end;
  reason_codes_value := case
    when jsonb_typeof(base_policy -> 'reason_codes') = 'array'
      then base_policy -> 'reason_codes'
    else '[]'::jsonb
  end || jsonb_build_array(
    case
      when manual_policy_active
        then 'historical_case_advisory_shadowed_by_manual_teaching_policy'
      when base_policy_applied
        then 'historical_case_advisory_shadowed_by_applied_base_policy'
      when not advisory_available
        then 'historical_case_advisory_threshold_not_met'
      when not generation_allowed_value
        then 'historical_case_advisory_available_but_generation_blocked'
      else 'historical_case_advisory_applied'
    end,
    'historical_case_minimum_two_confirmed_cases',
    'historical_case_contradictory_majority_forbidden'
  );
  safety_value := case
    when jsonb_typeof(base_policy -> 'safety') = 'object'
      then base_policy -> 'safety'
    else '{}'::jsonb
  end || jsonb_build_object(
    'historical_case_confirmed_heads_only', true,
    'historical_case_quarantine_excluded', true,
    'historical_case_raw_prose_excluded', true,
    'historical_case_urls_excluded', true,
    'historical_case_metrics_excluded_from_prompt', true,
    'historical_case_bounded_creative_angles_only', true,
    'historical_case_manual_teaching_policy_wins', true,
    'historical_case_exact_category_scope', true,
    'generation_allowed_preserved', true,
    'rejection_guards_preserved', true,
    'provider_action', false,
    'spend_action', false
  );

  requested_model_value := base_policy ->> 'requested_model';
  policy_without_hash :=
    (base_policy - 'policy_hash' - 'requested_model') ||
    jsonb_build_object(
      'version', case
        when historical_fallback_allowed
          then 'generation-learning-v10-historical-case-evidence'
        else coalesce(base_policy ->> 'version', 'generation-learning-v10')
      end,
      'historical_case_evidence', historical_evidence_value,
      'historical_case_advisory', jsonb_build_object(
        'version', 'ai-historical-case-advisory-v1',
        'available', advisory_available,
        'applied',
          historical_fallback_allowed
          and generation_allowed_value,
        'shadowed_by_manual_teaching_policy', manual_policy_active,
        'shadowed_by_applied_base_policy', base_policy_applied,
        'exact_product_id', product_id_value,
        'preferred_creative_angle', advisory_preferred_angle_value,
        'avoid_creative_angle', advisory_avoid_angle_value,
        'minimum_confirmed_cases_per_direction', 2,
        'evidence_hash', historical_evidence_value ->> 'evidence_hash',
        'raw_prose_excluded', true
      ),
      'reason_codes', reason_codes_value,
      'safety', safety_value
    );

  if historical_fallback_allowed then
    policy_without_hash :=
      (policy_without_hash - 'exploration') || jsonb_build_object(
        'applied', generation_allowed_value and (
          base_policy -> 'applied' = 'true'::jsonb
          or advisory_available
        ),
        'confidence', case
          when (historical_evidence_value ->> 'considered_case_count')::integer
            >= 4 then 'high'
          else 'medium'
        end,
        'selection_mode', 'performance',
        'selection_provenance', jsonb_build_object(
          'schema_version', 'ai-historical-case-selection-provenance-v1',
          'source', 'confirmed_historical_case_aggregate',
          'deterministic', true,
          'product_category', category_value,
          'minimum_confirmed_cases_per_direction', 2,
          'confirmed_case_count',
            (historical_evidence_value ->> 'considered_case_count')::integer,
          'distinct_product_count',
            (historical_evidence_value ->> 'distinct_product_count')::integer,
          'distinct_platform_count',
            (historical_evidence_value ->> 'distinct_platform_count')::integer,
          'evidence_hash', historical_evidence_value ->> 'evidence_hash',
          'base_policy_version', base_policy ->> 'version'
        ),
        'preferred_angle', preferred_angle_value,
        'avoid_angle', avoid_angle_value,
        'preferred_hook_patterns', '[]'::jsonb,
        'selected_angle', preferred_angle_value,
        'selected_hook_patterns', '[]'::jsonb
      );
  end if;

  policy_hash_value :=
    content_factory_private.json_hash(policy_without_hash);
  return policy_without_hash || jsonb_build_object(
    'policy_hash', policy_hash_value,
    'requested_model', requested_model_value
  );
end;
$$;

revoke all on function public.creator_generation_learning_policy(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_generation_learning_policy(jsonb)
  to authenticated;

commit;
