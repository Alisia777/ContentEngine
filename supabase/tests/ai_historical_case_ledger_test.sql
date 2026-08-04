begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select ok(
  to_regclass('content_factory.ai_historical_case_import_batches') is not null
  and to_regclass('content_factory.ai_historical_case_events') is not null
  and to_regclass('content_factory.ai_historical_case_decisions') is not null,
  'historical batches, case events, and decision events have immutable ledgers'
);

select ok(
  to_regclass(
    'content_factory.ai_historical_case_product_sku_lookup_idx'
  ) is not null
  and to_regclass(
    'content_factory.ai_historical_case_semantic_identity_idx'
  ) is not null
  and to_regclass(
    'content_factory.ai_historical_case_marketplace_sku_lookup_idx'
  ) is not null
  and to_regclass(
    'content_factory.products_org_current_wb_article_lookup_idx'
  ) is not null
  and (
    select count(*)
    from pg_index index_metadata
    where index_metadata.indexrelid in (
      'content_factory.ai_historical_case_product_sku_lookup_idx'::regclass,
      'content_factory.ai_historical_case_marketplace_sku_lookup_idx'::regclass,
      'content_factory.products_org_current_wb_article_lookup_idx'::regclass
    )
      and index_metadata.indpred is not null
  ) = 3,
  'semantic dedupe and late exact-SKU binding have tenant lookup indexes'
);

select ok(
  (select class.relrowsecurity and class.relforcerowsecurity
   from pg_class class
   where class.oid =
     'content_factory.ai_historical_case_import_batches'::regclass)
  and (select class.relrowsecurity and class.relforcerowsecurity
   from pg_class class
   where class.oid = 'content_factory.ai_historical_case_events'::regclass)
  and (select class.relrowsecurity and class.relforcerowsecurity
   from pg_class class
   where class.oid =
     'content_factory.ai_historical_case_decisions'::regclass),
  'all three historical ledgers enable and force RLS'
);

select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.ai_historical_case_import_batches',
    'select'
  )
  and not has_table_privilege(
    'authenticated', 'content_factory.ai_historical_case_events', 'insert'
  )
  and not has_table_privilege(
    'service_role', 'content_factory.ai_historical_case_events', 'select'
  )
  and not has_table_privilege(
    'service_role', 'content_factory.ai_historical_case_decisions', 'insert'
  ),
  'browser and service roles have no direct ledger privileges'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'public.creator_import_ai_historical_case_batch(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.creator_decide_ai_historical_case(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.creator_import_ai_historical_case_batch(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.creator_authorize_ai_historical_case_import(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.creator_authorize_ai_historical_case_import(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.creator_decide_ai_historical_case(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.ai_historical_product_case_evidence(uuid,text,uuid)',
    'execute'
  ),
  'historical authorization and import are service-only while decisions stay narrow'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger
    where trigger.tgrelid =
      'content_factory.ai_historical_case_import_batches'::regclass
      and trigger.tgname = 'ai_historical_batch_append_only'
      and not trigger.tgisinternal
  )
  and exists (
    select 1
    from pg_trigger trigger
    where trigger.tgrelid =
      'content_factory.ai_historical_case_events'::regclass
      and trigger.tgname = 'ai_historical_case_event_append_only'
      and not trigger.tgisinternal
  )
  and exists (
    select 1
    from pg_trigger trigger
    where trigger.tgrelid =
      'content_factory.ai_historical_case_decisions'::regclass
      and trigger.tgname = 'ai_historical_case_decision_append_only'
      and not trigger.tgisinternal
  ),
  'batch, case, and decision history is guarded append-only'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values
(
  'fa000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'historical-case-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Historical Case Owner"}'::jsonb,
  now(), now()
),
(
  'fa000000-0000-4000-8000-000000000002',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'historical-case-reviewer@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Historical Case Reviewer"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'fa100000-0000-4000-8000-000000000001',
  'Historical Case pgTAP',
  'historical-case-pgtap',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
(
  'fa100000-0000-4000-8000-000000000001',
  'fa000000-0000-4000-8000-000000000001',
  'owner', 'active'
),
(
  'fa100000-0000-4000-8000-000000000001',
  'fa000000-0000-4000-8000-000000000002',
  'reviewer', 'active'
);

insert into content_factory.products (
  id, organization_id, sku, title, current_wb_article,
  status, created_by
) values (
  'fa200000-0000-4000-8000-000000000001',
  'fa100000-0000-4000-8000-000000000001',
  'HIST-PROD-1', 'Runtime product', '12345678',
  'active', 'fa000000-0000-4000-8000-000000000001'
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
) values (
  'fa300000-0000-4000-8000-000000000001',
  'fa100000-0000-4000-8000-000000000001',
  'fa000000-0000-4000-8000-000000000001',
  'fa200000-0000-4000-8000-000000000001',
  'contentengine-private',
  'fa100000-0000-4000-8000-000000000001/fa000000-0000-4000-8000-000000000001/uploads/historical-product.jpg',
  'image/jpeg', 2048, repeat('3', 64), 'ready',
  '{"kind":"product_photo","rights_confirmed":true}'::jsonb,
  'historical-case-media-0001'
);

insert into content_factory.ai_category_knowledge_sources (
  id, organization_id, product_category, source_kind, owner_id,
  title, bucket_id, object_name, original_filename, mime_type,
  size_bytes, sha256, rights_confirmed, status,
  source_hash, request_hash, idempotency_key
) values (
  'fa400000-0000-4000-8000-000000000001',
  'fa100000-0000-4000-8000-000000000001',
  'baa', 'file', 'fa000000-0000-4000-8000-000000000001',
  'Historical workbook', 'contentengine-knowledge',
  'fa100000-0000-4000-8000-000000000001/fa000000-0000-4000-8000-000000000001/ai-knowledge/historical-cases.xlsx',
  'historical-cases.xlsx',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  4096, repeat('4', 64), true, 'active',
  repeat('5', 64), repeat('6', 64), 'historical-source-0001'
), (
  'fa400000-0000-4000-8000-000000000002',
  'fa100000-0000-4000-8000-000000000001',
  'baa', 'file', 'fa000000-0000-4000-8000-000000000001',
  'Historical workbook duplicate', 'contentengine-knowledge',
  'fa100000-0000-4000-8000-000000000001/fa000000-0000-4000-8000-000000000001/ai-knowledge/historical-cases-copy.xlsx',
  'historical-cases.xlsx',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  4096, repeat('4', 64), true, 'active',
  repeat('a', 64), repeat('b', 64), 'historical-source-copy-0001'
), (
  'fa400000-0000-4000-8000-000000000003',
  'fa100000-0000-4000-8000-000000000001',
  'baa', 'file', 'fa000000-0000-4000-8000-000000000001',
  'Historical workbook independent row', 'contentengine-knowledge',
  'fa100000-0000-4000-8000-000000000001/fa000000-0000-4000-8000-000000000001/ai-knowledge/historical-cases-independent.xlsx',
  'historical-cases-independent.xlsx',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  4096, repeat('4', 64), true, 'active',
  repeat('d', 64), repeat('e', 64), 'historical-source-independent-0001'
);

create or replace function pg_temp.set_historical_actor(p_actor_id uuid)
returns void
language plpgsql
as $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config('request.jwt.claim.sub', p_actor_id::text, true);
end;
$$;

create or replace function pg_temp.call_historical_import(
  p_payload jsonb,
  p_actor_id uuid default 'fa000000-0000-4000-8000-000000000001'
)
returns jsonb
language plpgsql
as $$
declare
  previous_claim_role text := current_setting(
    'request.jwt.claim.role', true
  );
  result_value jsonb;
begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
  begin
    result_value := public.creator_import_ai_historical_case_batch(
      p_payload || jsonb_build_object('actor_profile_id', p_actor_id)
    );
  exception when others then
    perform set_config(
      'request.jwt.claim.role', coalesce(previous_claim_role, ''), true
    );
    raise;
  end;
  perform set_config(
    'request.jwt.claim.role', coalesce(previous_claim_role, ''), true
  );
  return result_value;
end;
$$;

create or replace function pg_temp.call_historical_authorization(
  p_source_id uuid default 'fa400000-0000-4000-8000-000000000001',
  p_product_category text default 'baa',
  p_actor_id uuid default 'fa000000-0000-4000-8000-000000000001'
)
returns jsonb
language plpgsql
as $$
declare
  previous_claim_role text := current_setting(
    'request.jwt.claim.role', true
  );
  result_value jsonb;
begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
  begin
    result_value := public.creator_authorize_ai_historical_case_import(
      jsonb_build_object(
        'organization_id', 'fa100000-0000-4000-8000-000000000001',
        'actor_profile_id', p_actor_id,
        'source_id', p_source_id,
        'product_category', p_product_category
      )
    );
  exception when others then
    perform set_config(
      'request.jwt.claim.role', coalesce(previous_claim_role, ''), true
    );
    raise;
  end;
  perform set_config(
    'request.jwt.claim.role', coalesce(previous_claim_role, ''), true
  );
  return result_value;
end;
$$;

create or replace function pg_temp.historical_import_payload(
  p_idempotency_key text
)
returns jsonb
language sql
stable
as $$
  select jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'schema_version', 'ai_historical_cases.v1',
    'product_category', 'baa',
    'source_id', 'fa400000-0000-4000-8000-000000000001',
    'original_filename', 'historical-cases.xlsx',
    'source_sha256', repeat('4', 64),
    'parser_version', 'xlsx-v1',
    'manifest_sha256', repeat('8', 64),
    'idempotency_key', p_idempotency_key,
    'batch_index', 1,
    'batch_count', 2,
    'parsed_row_count', 13,
    'parser_quarantined_row_count', 2,
    'parser_quarantine_summary', jsonb_build_object(
      'formula_result_invalid', 1,
      'status_projection_invalid', 1
    ),
    'cases', jsonb_build_array(
      jsonb_build_object(
        'external_case_id', 'baa-good-1',
        'product_category', 'baa',
        'product_id', 'fa200000-0000-4000-8000-000000000001',
        'product_sku', 'HIST-PROD-1',
        'marketplace_sku', '12345678',
        'product_title', 'IMPORTED-RAW-TITLE-SENTINEL',
        'brand', 'IMPORTED-RAW-BRAND-SENTINEL',
        'platform', 'wildberries', 'channel', 'organic',
        'period_start', '2026-05-01', 'period_end', '2026-05-31',
        'outcome', 'good', 'outcome_dimension', 'content_conversion',
        'status_label', 'IMPORTED-RAW-STATUS-SENTINEL',
        'metrics', jsonb_build_object('sales', 10, 'conversion_rate', 0.10),
        'confidence', 0.95, 'creative_angle', 'product_focus',
        'provenance', jsonb_build_object(
          'sheet', 'Harley', 'row', 10, 'row_hash', repeat('a', 64)
        )
      ),
      jsonb_build_object(
        'external_case_id', 'baa-good-2',
        'product_category', 'baa',
        'product_id', 'fa200000-0000-4000-8000-000000000001',
        'product_sku', 'HIST-PROD-1',
        'marketplace_sku', '12345678',
        'product_title', 'IMPORTED-RAW-TITLE-SENTINEL',
        'brand', 'IMPORTED-RAW-BRAND-SENTINEL',
        'platform', 'instagram', 'channel', 'content',
        'period_start', '2026-06-01', 'period_end', '2026-06-30',
        'outcome', 'good', 'outcome_dimension', 'purchase_transition',
        'status_label', 'confirmed_leader',
        'metrics', jsonb_build_object('sales', 12, 'sale_per_view', 0.0755),
        'confidence', 0.90, 'creative_angle', 'product_focus',
        'provenance', jsonb_build_object(
          'sheet', 'Harley', 'row', 11, 'row_hash', repeat('b', 64)
        )
      ),
      jsonb_build_object(
        'external_case_id', 'baa-bad-1',
        'product_category', 'baa',
        'product_id', 'fa200000-0000-4000-8000-000000000001',
        'product_sku', 'HIST-PROD-1',
        'product_title', 'Runtime product', 'brand', 'QEEP',
        'platform', 'ozon', 'channel', 'marketplace',
        'period_start', '2026-05-01', 'period_end', '2026-07-29',
        'outcome', 'bad', 'outcome_dimension', 'buyout',
        'status_label', 'fix_buyout',
        'metrics', jsonb_build_object('buyout_rate', 0.5904),
        'confidence', 0.88, 'creative_angle', 'demonstration',
        'provenance', jsonb_build_object(
          'sheet', 'Ozon_funnel', 'row', 15, 'row_hash', repeat('c', 64)
        )
      ),
      jsonb_build_object(
        'external_case_id', 'baa-external-sku',
        'product_category', 'baa',
        'product_sku', 'QEEP-EXTERNAL-ONLY',
        'product_title', 'External QEEP SKU', 'brand', 'QEEP',
        'platform', 'wildberries', 'channel', 'marketplace',
        'period_start', '2026-05-01', 'period_end', '2026-07-29',
        'outcome', 'good', 'outcome_dimension', 'overall_performance',
        'status_label', 'superstar',
        'metrics', jsonb_build_object('orders', 100, 'buyout_rate', 0.85),
        'confidence', 0.80, 'creative_angle', 'product_focus',
        'provenance', jsonb_build_object(
          'sheet', 'WB_funnel', 'row', 20, 'row_hash', repeat('d', 64)
        )
      ),
      jsonb_build_object(
        'external_case_id', 'baa-bad-2',
        'product_category', 'baa',
        'product_id', 'fa200000-0000-4000-8000-000000000001',
        'product_sku', 'HIST-PROD-1',
        'product_title', 'Runtime product', 'brand', 'QEEP',
        'platform', 'wildberries', 'channel', 'marketplace',
        'period_start', '2026-06-01', 'period_end', '2026-07-29',
        'outcome', 'bad', 'outcome_dimension', 'product_card_conversion',
        'status_label', 'weak_conversion',
        'metrics', jsonb_build_object('visit_to_order_rate', 0.01),
        'confidence', 0.86, 'creative_angle', 'demonstration',
        'provenance', jsonb_build_object(
          'sheet', 'WB_funnel', 'row', 21, 'row_hash', repeat('1', 64)
        )
      ),
      jsonb_build_object(
        'external_case_id', 'baa-external-sku-2',
        'product_category', 'baa',
        'product_sku', 'QEEP-EXTERNAL-ONLY',
        'product_title', 'External QEEP SKU', 'brand', 'QEEP',
        'platform', 'ozon', 'channel', 'marketplace',
        'period_start', '2026-06-01', 'period_end', '2026-07-29',
        'outcome', 'good', 'outcome_dimension', 'organic_growth',
        'status_label', 'organic_growth',
        'metrics', jsonb_build_object('organic_share', 0.72),
        'confidence', 0.82, 'creative_angle', 'product_focus',
        'provenance', jsonb_build_object(
          'sheet', 'Ozon_funnel', 'row', 22, 'row_hash', repeat('2', 64)
        )
      ),
      jsonb_build_object(
        'external_case_id', 'baa-external-comparison',
        'product_category', 'baa',
        'product_sku', 'QEEP-EXTERNAL-ONLY',
        'product_title', 'External QEEP SKU', 'brand', 'QEEP',
        'platform', 'instagram', 'channel', 'content',
        'period_start', '2026-07-01', 'period_end', '2026-07-29',
        'outcome', 'good', 'outcome_dimension', 'content_conversion',
        'status_label', 'comparison_candidate',
        'metrics', jsonb_build_object('orders', 4),
        'confidence', 0.78, 'creative_angle', 'comparison',
        'provenance', jsonb_build_object(
          'sheet', 'Harley', 'row', 24, 'row_hash', repeat('7', 64)
        )
      ),
      jsonb_build_object(
        'external_case_id', 'baa-semantic-duplicate',
        'product_category', 'baa',
        'product_id', 'fa200000-0000-4000-8000-000000000001',
        'product_sku', 'HIST-PROD-1',
        'product_title', 'Runtime product', 'brand', 'QEEP',
        'platform', 'instagram', 'channel', 'content',
        'period_start', '2026-06-01', 'period_end', '2026-06-30',
        'outcome', 'good', 'outcome_dimension', 'content_conversion',
        'status_label', 'semantic_duplicate_candidate',
        'metrics', jsonb_build_object('orders', 3),
        'confidence', 0.75, 'creative_angle', 'comparison',
        'provenance', jsonb_build_object(
          'sheet', 'Harley', 'row', 23, 'row_hash', repeat('3', 64)
        )
      ),
      jsonb_build_object(
        'external_case_id', 'cosmetics-external-sku',
        'product_category', 'cosmetics',
        'marketplace_sku', '87654321',
        'product_title', 'External cosmetics SKU', 'brand', 'Harley',
        'platform', 'wildberries', 'channel', 'instagram',
        'period_start', '2026-06-01', 'period_end', '2026-06-30',
        'outcome', 'review', 'outcome_dimension', 'attribution_window',
        'status_label', 'needs_attribution_review',
        'metrics', jsonb_build_object('views', 68, 'orders', 0),
        'confidence', 0.40,
        'provenance', jsonb_build_object(
          'sheet', 'Content_dashboard', 'row', 25, 'row_hash', repeat('e', 64)
        )
      ),
      jsonb_build_object(
        'external_case_id', 'baa-partial-reference',
        'product_category', 'baa',
        'product_id', 'fa200000-0000-4000-8000-000000000001',
        'product_sku', 'UNKNOWN-PARTIAL-SKU',
        'product_title', 'Partial identity', 'brand', 'QEEP',
        'platform', 'ozon', 'channel', 'marketplace',
        'period_start', '2026-07-01', 'period_end', '2026-07-29',
        'outcome', 'review', 'outcome_dimension', 'product_mapping',
        'status_label', 'partial_mapping_requires_review',
        'metrics', jsonb_build_object('rows', 1),
        'confidence', 0.25,
        'provenance', jsonb_build_object(
          'sheet', 'Control', 'row', 9, 'row_hash', repeat('6', 64)
        )
      ),
      jsonb_build_object(
        'external_case_id', 'baa-missing-product',
        'product_category', 'baa',
        'product_title', 'Missing product identity', 'brand', 'QEEP',
        'platform', 'ozon', 'channel', 'marketplace',
        'period_start', '2026-05-01', 'period_end', '2026-05-31',
        'outcome', 'review', 'outcome_dimension', 'product_mapping',
        'status_label', 'mapping_required',
        'metrics', jsonb_build_object('rows', 1),
        'confidence', 0.20,
        'provenance', jsonb_build_object(
          'sheet', 'Control', 'row', 7, 'row_hash', repeat('f', 64)
        )
      )
    )
  );
$$;

create or replace function pg_temp.historical_second_chunk_payload()
returns jsonb
language sql
stable
as $$
  select jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'schema_version', 'ai_historical_cases.v1',
    'product_category', 'baa',
    'source_id', 'fa400000-0000-4000-8000-000000000001',
    'original_filename', 'historical-cases.xlsx',
    'source_sha256', repeat('4', 64),
    'parser_version', 'xlsx-v1',
    'manifest_sha256', repeat('8', 64),
    'idempotency_key', 'historical-import-0002',
    'batch_index', 2, 'batch_count', 2,
    'parsed_row_count', 1,
    'parser_quarantined_row_count', 0,
    'parser_quarantine_summary', '{}'::jsonb,
    'cases', jsonb_build_array(jsonb_build_object(
      'external_case_id', 'baa-second-chunk-review',
      'product_category', 'baa',
      'product_sku', 'QEEP-SECOND-CHUNK',
      'product_title', 'Second chunk product', 'brand', 'QEEP',
      'platform', 'wildberries', 'channel', 'marketplace',
      'period_start', '2026-07-01', 'period_end', '2026-07-29',
      'outcome', 'review', 'outcome_dimension', 'evidence_sufficiency',
      'status_label', 'insufficient_sample',
      'metrics', jsonb_build_object('observations', 1),
      'confidence', 0.30,
      'provenance', jsonb_build_object(
        'sheet', 'Control', 'row', 8, 'row_hash', repeat('0', 64)
      )
    ))
  );
$$;

create or replace function pg_temp.historical_all_rejected_payload()
returns jsonb
language sql
stable
as $$
  select jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'schema_version', 'ai_historical_cases.v1',
    'product_category', 'baa',
    'source_id', 'fa400000-0000-4000-8000-000000000001',
    'original_filename', 'historical-cases.xlsx',
    'source_sha256', repeat('4', 64),
    'parser_version', 'xlsx-v1',
    'manifest_sha256', repeat('9', 64),
    'idempotency_key', 'historical-all-rejected-0001',
    'batch_index', 1, 'batch_count', 1,
    'parsed_row_count', 2,
    'parser_quarantined_row_count', 2,
    'parser_quarantine_summary', jsonb_build_object(
      'canonical_number_invalid', 1,
      'product_category_review_required', 1
    ),
    'cases', '[]'::jsonb
  );
$$;

create or replace function pg_temp.historical_duplicate_source_payload()
returns jsonb
language sql
stable
as $$
  select jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'schema_version', 'ai_historical_cases.v1',
    'product_category', 'baa',
    'source_id', 'fa400000-0000-4000-8000-000000000002',
    'original_filename', 'historical-cases.xlsx',
    'source_sha256', repeat('4', 64),
    'parser_version', 'xlsx-v1',
    'manifest_sha256', repeat('c', 64),
    'idempotency_key', 'historical-duplicate-source-0001',
    'batch_index', 1, 'batch_count', 1,
    'parsed_row_count', 1,
    'parser_quarantined_row_count', 0,
    'parser_quarantine_summary', '{}'::jsonb,
    'cases', jsonb_build_array(jsonb_build_object(
      'external_case_id', 'baa-semantic-duplicate',
      'product_category', 'baa',
      'product_id', 'fa200000-0000-4000-8000-000000000001',
      'product_sku', 'HIST-PROD-1',
      'product_title', 'Runtime product', 'brand', 'QEEP',
      'platform', 'instagram', 'channel', 'content',
      'period_start', '2026-06-01', 'period_end', '2026-06-30',
      'outcome', 'good', 'outcome_dimension', 'content_conversion',
      'status_label', 'semantic_duplicate_candidate',
      'metrics', jsonb_build_object('orders', 3),
      'confidence', 0.75, 'creative_angle', 'comparison',
      'provenance', jsonb_build_object(
        'sheet', 'Harley', 'row', 23, 'row_hash', repeat('3', 64)
      )
    ))
  );
$$;

create or replace function pg_temp.historical_independent_row_payload()
returns jsonb
language sql
stable
as $$
  select jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'schema_version', 'ai_historical_cases.v1',
    'product_category', 'baa',
    'source_id', 'fa400000-0000-4000-8000-000000000003',
    'original_filename', 'historical-cases-independent.xlsx',
    'source_sha256', repeat('4', 64),
    'parser_version', 'xlsx-v1',
    'manifest_sha256', repeat('d', 64),
    'idempotency_key', 'historical-independent-row-0001',
    'batch_index', 1, 'batch_count', 1,
    'parsed_row_count', 1,
    'parser_quarantined_row_count', 0,
    'parser_quarantine_summary', '{}'::jsonb,
    'cases', jsonb_build_array(jsonb_build_object(
      'external_case_id', 'baa-semantic-duplicate',
      'product_category', 'baa',
      'product_id', 'fa200000-0000-4000-8000-000000000001',
      'product_sku', 'HIST-PROD-1',
      'product_title', 'Runtime product', 'brand', 'QEEP',
      'platform', 'instagram', 'channel', 'content',
      'period_start', '2026-07-01', 'period_end', '2026-07-31',
      'outcome', 'good', 'outcome_dimension', 'content_conversion',
      'status_label', 'independent_semantic_candidate',
      'metrics', jsonb_build_object('orders', 5),
      'confidence', 0.76, 'creative_angle', 'comparison',
      'provenance', jsonb_build_object(
        'sheet', 'Harley', 'row', 30, 'row_hash', repeat('8', 64)
      )
    ))
  );
$$;

create or replace function pg_temp.historical_late_partial_payload()
returns jsonb
language sql
stable
as $$
  select jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'schema_version', 'ai_historical_cases.v1',
    'product_category', 'baa',
    'source_id', 'fa400000-0000-4000-8000-000000000003',
    'original_filename', 'historical-cases-independent.xlsx',
    'source_sha256', repeat('4', 64),
    'parser_version', 'xlsx-v1',
    'manifest_sha256', repeat('9', 64),
    'idempotency_key', 'historical-late-partial-0001',
    'batch_index', 1, 'batch_count', 1,
    'parsed_row_count', 1,
    'parser_quarantined_row_count', 0,
    'parser_quarantine_summary', '{}'::jsonb,
    'cases', jsonb_build_array(jsonb_build_object(
      'external_case_id', 'baa-late-partial-reference',
      'product_category', 'baa',
      'product_sku', 'LATE-PARTIAL-SKU',
      'marketplace_sku', '99887766',
      'product_title', 'Late partial identity', 'brand', 'QEEP',
      'platform', 'wildberries', 'channel', 'marketplace',
      'period_start', '2026-07-01', 'period_end', '2026-07-31',
      'outcome', 'review', 'outcome_dimension', 'product_mapping',
      'status_label', 'late_mapping_requires_all_refs',
      'metrics', jsonb_build_object('rows', 1),
      'confidence', 0.30,
      'provenance', jsonb_build_object(
        'sheet', 'Control', 'row', 31, 'row_hash', repeat('9', 64)
      )
    ))
  );
$$;

create or replace function pg_temp.decide_historical_case(
  p_external_case_id text,
  p_decision text,
  p_idempotency_key text,
  p_source_id uuid default null
)
returns jsonb
language plpgsql
as $$
declare
  historical_case_row content_factory.ai_historical_case_events%rowtype;
  decision_head_row content_factory.ai_historical_case_decisions%rowtype;
begin
  select historical_case.*
  into historical_case_row
  from content_factory.ai_historical_case_events historical_case
  where historical_case.organization_id =
    'fa100000-0000-4000-8000-000000000001'
    and historical_case.external_case_id = p_external_case_id
    and (p_source_id is null or historical_case.source_id = p_source_id)
  order by historical_case.event_cursor desc
  limit 1;
  select decision.*
  into decision_head_row
  from content_factory.ai_historical_case_decisions decision
  where decision.organization_id = historical_case_row.organization_id
    and decision.product_category = historical_case_row.product_category
    and decision.case_id = historical_case_row.case_id
  order by decision.event_cursor desc
  limit 1;
  return public.creator_decide_ai_historical_case(jsonb_build_object(
    'organization_id', historical_case_row.organization_id,
    'product_category', historical_case_row.product_category,
    'case_id', historical_case_row.case_id,
    'event_id', coalesce(decision_head_row.id, historical_case_row.id),
    'expected_scope_version', coalesce(
      decision_head_row.resulting_scope_version, 0
    ),
    'expected_event_cursor', coalesce(
      decision_head_row.event_cursor, historical_case_row.event_cursor
    ),
    'decision', p_decision,
    'confirmation', true,
    'idempotency_key', p_idempotency_key
  ));
end;
$$;

create temporary table historical_case_test_state (
  before_snapshot jsonb,
  all_rejected_result jsonb,
  all_rejected_replay_result jsonb,
  before_policy jsonb,
  import_result jsonb,
  content_replay_result jsonb,
  pending_policy jsonb,
  first_decision jsonb,
  one_confirm_policy jsonb,
  two_confirm_policy jsonb,
  semantic_duplicate_policy jsonb,
  semantic_reject_policy jsonb,
  semantic_independent_policy jsonb,
  catalog_replay_result jsonb,
  external_confirm_snapshot jsonb,
  late_bound_snapshot jsonb,
  late_bound_policy jsonb,
  after_reject_policy jsonb,
  restored_policy jsonb,
  manual_policy jsonb,
  reviewer_snapshot jsonb,
  before_side_effect_counts jsonb
) on commit drop;

insert into historical_case_test_state (before_side_effect_counts)
values (jsonb_build_object(
  'generation_batches', (
    select count(*) from content_factory.generation_batches
    where organization_id = 'fa100000-0000-4000-8000-000000000001'
  ),
  'generation_jobs', (
    select count(*) from content_factory.generation_jobs
    where organization_id = 'fa100000-0000-4000-8000-000000000001'
  ),
  'generation_spend_ledger', (
    select count(*) from content_factory.generation_spend_ledger
    where organization_id = 'fa100000-0000-4000-8000-000000000001'
  )
));

select pg_temp.set_historical_actor(
  'fa000000-0000-4000-8000-000000000001'
);

select ok(
  (authorization_receipt -> 'ok') = 'true'::jsonb
    and authorization_receipt ->> 'actor_role' = 'owner'
    and authorization_receipt -> 'bounded_source_receipt' = 'true'::jsonb
    and authorization_receipt -> 'server_parser_authorized' = 'true'::jsonb
    and authorization_receipt #>> '{source,source_id}' =
      'fa400000-0000-4000-8000-000000000001'
    and authorization_receipt #>> '{source,bucket_id}' =
      'contentengine-knowledge'
    and authorization_receipt #>> '{source,sha256}' = repeat('4', 64)
    and not authorization_receipt ? 'sources'
    and not (authorization_receipt -> 'source') ? 'source_url'
    and not (authorization_receipt -> 'source') ? 'note',
  'service authorization returns one bounded source receipt for the Edge parser'
)
from (
  select pg_temp.call_historical_authorization() as authorization_receipt
) authorized;

select throws_ok(
  $$select pg_temp.call_historical_authorization(
    'fa400000-0000-4000-8000-000000000001',
    'baa',
    'fa000000-0000-4000-8000-000000000099'
  )$$,
  '42501',
  'ai_historical_case_actor_not_allowed',
  'source authorization cannot forge an inactive or non-member actor'
);

select throws_ok(
  $$select pg_temp.call_historical_authorization(
    'fa400000-0000-4000-8000-000000000001',
    'baa',
    'fa000000-0000-4000-8000-000000000002'
  )$$,
  '42501',
  'ai_historical_case_actor_not_allowed',
  'an active reviewer cannot authorize a server-side historical import'
);

select throws_ok(
  $$select pg_temp.call_historical_authorization(
    'fa400000-0000-4000-8000-000000000001',
    'cosmetics'
  )$$,
  'P0002',
  'ai_historical_case_import_source_not_authorized',
  'source authorization binds the receipt to its requested category'
);

select throws_ok(
  $$select pg_temp.call_historical_import(
    pg_temp.historical_all_rejected_payload(),
    'fa000000-0000-4000-8000-000000000099'
  )$$,
  '42501',
  'ai_historical_case_actor_not_allowed',
  'service parsing cannot forge an actor without an active allowed membership'
);

-- Stub only the preserved base inside this rollback-only pgTAP transaction so
-- the historical wrapper can be tested deterministically.  It still models
-- explicit teaching-card precedence from the real installed wrapper.
create or replace function content_factory_private
  .creator_generation_learning_policy_pre_historical_case_v1(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  organization_id_value uuid :=
    content_factory_private.resolve_organization(p_payload);
  category_value text := p_payload ->> 'product_category';
  manual_preferred_value text;
begin
  select policy.preferred_creative_angle
  into manual_preferred_value
  from content_factory.ai_effective_category_policies policy
  where policy.organization_id = organization_id_value
    and policy.product_category = category_value
  order by policy.scope_version desc
  limit 1;
  return jsonb_build_object(
    'version', 'pgtap-base-policy-v1',
    'product_category', category_value,
    'generation_allowed', true,
    'applied', manual_preferred_value is not null,
    'confidence', case when manual_preferred_value is null then 'none' else 'high' end,
    'preferred_angle', coalesce(manual_preferred_value, 'demonstration'),
    'avoid_angle', null,
    'preferred_hook_patterns', jsonb_build_array('base-hook-must-clear'),
    'selected_hook_patterns', jsonb_build_array('base-hook-must-clear'),
    'reason_codes', '[]'::jsonb,
    'safety', jsonb_build_object('base_guard_preserved', true),
    'ai_teaching_policy', case when manual_preferred_value is null
      then null
      else jsonb_build_object(
        'preferred_creative_angle', manual_preferred_value,
        'raw_notes_excluded', true
      )
    end,
    'policy_hash', repeat('1', 64),
    'requested_model', p_payload ->> 'model'
  );
end;
$$;

update historical_case_test_state
set before_snapshot = public.creator_ai_learning_control_room(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'product_category', 'baa'
  )
),
before_policy = public.creator_generation_learning_policy(jsonb_build_object(
  'organization_id', 'fa100000-0000-4000-8000-000000000001',
  'media_id', 'fa300000-0000-4000-8000-000000000001',
  'platform', 'youtube', 'model', 'seedream5_lite',
  'product_category', 'baa'
));

select throws_ok(
  $$select pg_temp.call_historical_import(
    jsonb_set(
      pg_temp.historical_import_payload('historical-source-sha-mismatch-0001'),
      '{source_sha256}',
      to_jsonb(repeat('7', 64))
    )
  )$$,
  '22023',
  'ai_historical_case_source_sha256_mismatch',
  'the normalized RPC rejects a hash that differs from its active file source'
);

select is(
  (select dimension ->> 'current'
   from historical_case_test_state state,
   jsonb_array_elements(
     state.before_snapshot #> '{category_detail,readiness,dimensions}'
   ) dimension
   where dimension ->> 'key' = 'analysis_coverage'),
  '0',
  'registering an XLSX alone does not claim completed analysis coverage'
);

update historical_case_test_state
set all_rejected_result = pg_temp.call_historical_import(
  pg_temp.historical_all_rejected_payload()
);

select ok(
  (select all_rejected_result -> 'ok' = 'false'::jsonb
    and all_rejected_result ->> 'status' = 'parser_rejected_all'
    and all_rejected_result -> 'batch_persisted' = 'true'::jsonb
    and (all_rejected_result ->> 'parser_quarantined_row_count')::integer = 2
   from historical_case_test_state)
  and exists (
    select 1
    from content_factory.ai_historical_case_import_batches batch
    where organization_id = 'fa100000-0000-4000-8000-000000000001'
      and batch.manifest_sha256 = repeat('9', 64)
      and batch.case_count = 0
      and batch.import_status = 'parser_rejected'
      and not exists (
        select 1
        from content_factory.ai_historical_case_events historical_case
        where historical_case.batch_id = batch.id
      )
  ),
  'all parser-rejected rows remain auditable without inventing case events'
);

update historical_case_test_state
set all_rejected_replay_result =
  pg_temp.call_historical_import(jsonb_set(
    pg_temp.historical_all_rejected_payload(),
    '{idempotency_key}',
    to_jsonb('historical-all-rejected-reload-0001'::text)
  ));

select ok(
  (select all_rejected_replay_result -> 'ok' = 'false'::jsonb
      and all_rejected_replay_result ->> 'status' = 'parser_rejected_all'
      and all_rejected_replay_result -> 'replayed' = 'true'::jsonb
      and all_rejected_replay_result -> 'batch_persisted' = 'true'::jsonb
      and all_rejected_replay_result #>> '{batch,batch_id}' =
        all_rejected_result #>> '{batch,batch_id}'
    from historical_case_test_state)
  and (
    select count(*)
    from content_factory.ai_historical_case_import_batches batch
    where batch.organization_id =
      'fa100000-0000-4000-8000-000000000001'
      and batch.source_id = 'fa400000-0000-4000-8000-000000000001'
      and batch.manifest_sha256 = repeat('9', 64)
      and batch.batch_index = 1
  ) = 1,
  'a fresh command key replays the authoritative all-rejected receipt once'
);

update historical_case_test_state
set import_result = pg_temp.call_historical_import(
  pg_temp.historical_import_payload('historical-import-0001')
);

select ok(
  (select import_result -> 'ok' = 'true'::jsonb
    and import_result -> 'replayed' = 'false'::jsonb
    and import_result #>> '{batch,import_status}' =
      'completed_with_quarantine'
    and (import_result #>> '{batch,case_count}')::integer = 11
    and (import_result #>> '{batch,matched_case_count}')::integer = 9
    and (import_result #>> '{batch,quarantined_case_count}')::integer = 2
    and (import_result #>> '{batch,parsed_row_count}')::integer = 13
    and (import_result #>> '{batch,parser_quarantined_row_count}')::integer = 2
    and (import_result #>> '{batch,per_category_summary,baa,total}')::integer = 10
    and (import_result #>> '{batch,per_category_summary,cosmetics,total}')::integer = 1
   from historical_case_test_state),
  'one normalized batch persists authoritative SQL and parser quarantine counts'
);

select is(
  (select pg_temp.call_historical_import(
      pg_temp.historical_import_payload('historical-import-0001')
    ) #>> '{batch,batch_id}'),
  (select import_result #>> '{batch,batch_id}'
   from historical_case_test_state),
  'the original command key keeps its stored idempotent replay'
);

update historical_case_test_state
set content_replay_result = pg_temp.call_historical_import(
  pg_temp.historical_import_payload('historical-import-reload-0001')
);

select ok(
  (select content_replay_result #>> '{batch,batch_id}' =
      import_result #>> '{batch,batch_id}'
      and content_replay_result -> 'replayed' = 'true'::jsonb
      and content_replay_result #>> '{batch,request_hash}' =
        import_result #>> '{batch,request_hash}'
      and content_replay_result #>> '{batch,batch_index}' = '1'
    from historical_case_test_state)
  and (
    select count(*)
    from content_factory.ai_historical_case_import_batches batch
    where batch.organization_id =
      'fa100000-0000-4000-8000-000000000001'
      and batch.source_id = 'fa400000-0000-4000-8000-000000000001'
      and batch.manifest_sha256 = repeat('8', 64)
      and batch.batch_index = 1
  ) = 1,
  'reload with a fresh command key reuses an identical physical chunk'
);

select throws_ok(
  $$select pg_temp.call_historical_import(jsonb_set(
    pg_temp.historical_import_payload('historical-import-mismatch-0001'),
    '{cases,0,status_label}',
    to_jsonb('changed_after_reload'::text)
  ))$$,
  '23505',
  'ai_historical_case_manifest_conflict',
  'a fresh-key retry with different normalized content fails closed'
);

select lives_ok(
  $$select pg_temp.call_historical_import(
    pg_temp.historical_second_chunk_payload()
  )$$,
  'the next physical chunk appends under the same immutable manifest identity'
);

select ok(
  (select
     count(*) filter (
       where logical_import ->> 'manifest_sha256' = repeat('8', 64)
     ) = 1
     and max((logical_import ->> 'completed_batch_count')::integer) filter (
       where logical_import ->> 'manifest_sha256' = repeat('8', 64)
     ) = 2
     and max((logical_import ->> 'batch_count')::integer) filter (
       where logical_import ->> 'manifest_sha256' = repeat('8', 64)
     ) = 2
     and max((logical_import ->> 'case_count')::integer) filter (
       where logical_import ->> 'manifest_sha256' = repeat('8', 64)
     ) = 12
     and max((logical_import ->> 'parsed_row_count')::integer) filter (
       where logical_import ->> 'manifest_sha256' = repeat('8', 64)
     ) = 14
     and max((logical_import ->> 'parser_quarantined_row_count')::integer)
       filter (
         where logical_import ->> 'manifest_sha256' = repeat('8', 64)
       ) = 2
   from jsonb_array_elements(public.creator_ai_learning_control_room(
     jsonb_build_object(
       'organization_id', 'fa100000-0000-4000-8000-000000000001',
       'product_category', 'baa'
     )
   ) -> 'batches') logical_import),
  'physical chunks aggregate into one logical import without parsed-row double count'
);

select ok(
  (select resolution_status = 'matched'
      and resolution_method = 'source_external_sku'
      and product_id is null
   from content_factory.ai_historical_case_events
   where organization_id = 'fa100000-0000-4000-8000-000000000001'
     and external_case_id = 'baa-external-sku')
  and (select resolution_status = 'quarantined'
      and quarantine_reason = 'product_reference_missing'
   from content_factory.ai_historical_case_events
   where organization_id = 'fa100000-0000-4000-8000-000000000001'
     and external_case_id = 'baa-missing-product')
  and (select resolution_status = 'quarantined'
      and quarantine_reason = 'product_reference_partial_match'
   from content_factory.ai_historical_case_events
   where organization_id = 'fa100000-0000-4000-8000-000000000001'
     and external_case_id = 'baa-partial-reference'),
  'external SKU stays reviewable while missing and partial identity quarantines'
);

select ok(
  (select jsonb_array_length(import_result #> '{snapshot,historical_cases}') = 10
    and jsonb_array_length(import_result #> '{snapshot,batches}') = 2
    and import_result #>
      '{snapshot,capabilities,confirmed_historical_case_aggregate_can_affect_generation_policy}'
        = 'true'::jsonb
   from historical_case_test_state),
  'the selected-category snapshot exposes cases, batches, and truthful capability flags'
);

select is(
  (select dimension ->> 'current'
   from historical_case_test_state state,
   jsonb_array_elements(
     state.import_result #> '{snapshot,category_detail,readiness,dimensions}'
   ) dimension
   where dimension ->> 'key' = 'analysis_coverage'),
  '1',
  'a completed normalized XLSX batch advances analysis coverage once'
);

select ok(
  (select (snapshot #>> '{historical_case_summary,total}')::integer = 1
      and jsonb_array_length(snapshot -> 'batches') = 1
      and snapshot #>
        '{category_detail,readiness,historical_advisory_ready}' =
          'false'::jsonb
      and (select dimension ->> 'current'
        from jsonb_array_elements(snapshot #>
          '{category_detail,readiness,dimensions}') dimension
        where dimension ->> 'key' = 'analysis_coverage') = '0'
   from (
     select public.creator_ai_learning_control_room(jsonb_build_object(
       'organization_id', 'fa100000-0000-4000-8000-000000000001',
       'product_category', 'cosmetics'
     )) as snapshot
   ) selected),
  'unbound mixed-workbook cases stay visible without claiming readiness'
);

update historical_case_test_state
set pending_policy = public.creator_generation_learning_policy(jsonb_build_object(
  'organization_id', 'fa100000-0000-4000-8000-000000000001',
  'media_id', 'fa300000-0000-4000-8000-000000000001',
  'platform', 'youtube', 'model', 'seedream5_lite',
  'product_category', 'baa'
));

select is(
  (select pending_policy ->> 'policy_hash'
   from historical_case_test_state),
  (select before_policy ->> 'policy_hash'
   from historical_case_test_state),
  'pending imported cases have no effect on generation policy'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
    'baa-external-sku', 'confirm', 'historical-confirm-external-1'
  )$$,
  'the first external-only SKU case can be reviewed before a product exists'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
  'baa-external-sku-2', 'confirm', 'historical-confirm-external-2'
  )$$,
  'the second external-only SKU case remains reviewable without binding'
);

update historical_case_test_state
set external_confirm_snapshot = pg_temp.decide_historical_case(
  'baa-external-comparison', 'confirm',
  'historical-confirm-external-comparison-1'
);

select ok(
  (select (external_confirm_snapshot #>>
      '{snapshot,historical_case_evidence,confirmed_case_count}')::integer = 3
    and (external_confirm_snapshot #>>
      '{snapshot,historical_case_evidence,historical_learning_eligible_count}')
        ::integer = 0
    and (external_confirm_snapshot #>>
      '{snapshot,historical_case_evidence,missing_exact_product_binding_count}')
        ::integer = 3
    and jsonb_array_length(external_confirm_snapshot #>
      '{snapshot,historical_case_evidence,angles}') = 0
    and external_confirm_snapshot #>
      '{snapshot,historical_case_evidence,generation_advisory_ready}' =
        'false'::jsonb
   from historical_case_test_state)
  and (select public.creator_generation_learning_policy(jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001',
      'media_id', 'fa300000-0000-4000-8000-000000000001',
      'platform', 'youtube', 'model', 'seedream5_lite',
      'product_category', 'baa'
    )) #>> '{historical_case_evidence,considered_case_count}') = '0',
  'unbound confirmed cases remain category signal and never claim readiness'
);

update historical_case_test_state
set first_decision = pg_temp.decide_historical_case(
  'baa-good-1', 'confirm', 'historical-confirm-good-1'
);

select is(
  (select public.creator_decide_ai_historical_case(jsonb_build_object(
    'organization_id', historical_case.organization_id,
    'product_category', historical_case.product_category,
    'case_id', historical_case.case_id,
    'event_id', historical_case.id,
    'expected_scope_version', 0,
    'expected_event_cursor', historical_case.event_cursor,
    'decision', 'confirm', 'confirmation', true,
    'idempotency_key', 'historical-confirm-good-1'
  )) #>> '{decision,decision_id}'
  from content_factory.ai_historical_case_events historical_case
  where historical_case.organization_id =
    'fa100000-0000-4000-8000-000000000001'
    and historical_case.external_case_id = 'baa-good-1'),
  (select first_decision #>> '{decision,decision_id}'
   from historical_case_test_state),
  'an exact historical decision replay is idempotent after its CAS head advances'
);

select throws_ok(
  (
    select format($sql$
      select public.creator_decide_ai_historical_case(%L::jsonb)
    $sql$, jsonb_build_object(
      'organization_id', historical_case.organization_id,
      'product_category', historical_case.product_category,
      'case_id', historical_case.case_id,
      'event_id', historical_case.id,
      'expected_scope_version', 0,
      'expected_event_cursor', historical_case.event_cursor,
      'decision', 'reject', 'confirmation', true,
      'idempotency_key', 'historical-confirm-good-1'
    ))
    from content_factory.ai_historical_case_events historical_case
    where historical_case.external_case_id = 'baa-good-1'
  ),
  '23505',
  'idempotency_key_conflict',
  'one idempotency key cannot authorize a different decision'
);

select throws_ok(
  (
    select format($sql$
      select public.creator_decide_ai_historical_case(%L::jsonb)
    $sql$, jsonb_build_object(
      'organization_id', historical_case.organization_id,
      'product_category', historical_case.product_category,
      'case_id', historical_case.case_id,
      'event_id', historical_case.id,
      'expected_scope_version', 0,
      'expected_event_cursor', historical_case.event_cursor,
      'decision', 'confirm', 'confirmation', true,
      'idempotency_key', 'historical-stale-decision-0001'
    ))
    from content_factory.ai_historical_case_events historical_case
    where historical_case.external_case_id = 'baa-good-1'
  ),
  '40001',
  'ai_historical_case_refresh_required',
  'stale event id, cursor, and version cannot append a decision'
);

update historical_case_test_state
set one_confirm_policy = public.creator_generation_learning_policy(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'media_id', 'fa300000-0000-4000-8000-000000000001',
    'platform', 'youtube', 'model', 'seedream5_lite',
    'product_category', 'baa'
  )
);

select ok(
  (select one_confirm_policy #>>
      '{historical_case_advisory,preferred_creative_angle}' is null
    and one_confirm_policy #>> '{historical_case_evidence,considered_case_count}' = '1'
   from historical_case_test_state),
  'one confirmed case remains below the exact-product fallback threshold'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
    'baa-good-2', 'confirm', 'historical-confirm-good-2'
  )$$,
  'a second exact-product case can be confirmed with a fresh CAS head'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
    'baa-bad-1', 'confirm', 'historical-confirm-bad-1'
  )$$,
  'a failed historical case can be explicitly confirmed as negative evidence'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
    'baa-bad-2', 'confirm', 'historical-confirm-bad-2'
  )$$,
  'a second failed case can satisfy the bounded avoid threshold'
);

update historical_case_test_state
set two_confirm_policy = public.creator_generation_learning_policy(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'media_id', 'fa300000-0000-4000-8000-000000000001',
    'platform', 'youtube', 'model', 'seedream5_lite',
    'product_category', 'baa'
  )
);

select ok(
  (select two_confirm_policy #>> '{historical_case_advisory,applied}' = 'true'
    and two_confirm_policy ->> 'preferred_angle' = 'product_focus'
    and two_confirm_policy ->> 'avoid_angle' = 'demonstration'
    and two_confirm_policy -> 'preferred_hook_patterns' = '[]'::jsonb
    and two_confirm_policy -> 'selected_hook_patterns' = '[]'::jsonb
    and two_confirm_policy #>> '{historical_case_evidence,preferred_score}' = '2'
    and two_confirm_policy #>>
      '{historical_case_evidence,preferred_score_tie_count}' = '1'
    and two_confirm_policy #>> '{historical_case_evidence,avoid_score}' = '-2'
    and two_confirm_policy #>>
      '{historical_case_advisory,avoid_creative_angle}' = 'demonstration'
   from historical_case_test_state),
  'confirmed good and bad cases apply tie-free prefer and avoid evidence'
);

select ok(
  (select angle -> 'preferred_eligible' = 'true'::jsonb
      and angle ->> 'preferred_ready_product_count' = '1'
      and angle ->> 'best_product_preferred_net_support' = '2'
   from jsonb_array_elements(public.creator_ai_learning_control_room(
     jsonb_build_object(
       'organization_id', 'fa100000-0000-4000-8000-000000000001',
       'product_category', 'baa'
     )
   ) #> '{historical_case_evidence,angles}') angle
   where angle ->> 'creative_angle' = 'product_focus'),
  'two net-consistent cases for one exact product mark the category angle ready'
);

select ok(
  (select two_confirm_policy::text not like '%IMPORTED-RAW-TITLE-SENTINEL%'
    and two_confirm_policy::text not like '%IMPORTED-RAW-BRAND-SENTINEL%'
    and two_confirm_policy::text not like '%IMPORTED-RAW-STATUS-SENTINEL%'
    and two_confirm_policy::text not like '%conversion_rate%'
   from historical_case_test_state),
  'raw cells, bounded labels, and metric values never enter generation policy'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
    'baa-semantic-duplicate', 'confirm',
    'historical-confirm-semantic-original-1',
    'fa400000-0000-4000-8000-000000000001'
  )$$,
  'the original semantic case can be explicitly confirmed'
);

select lives_ok(
  $$select pg_temp.call_historical_import(
    pg_temp.historical_duplicate_source_payload()
  )$$,
  'a duplicate workbook can retain its own immutable provenance row'
);

select is(
  (select dimension ->> 'current'
   from jsonb_array_elements(public.creator_ai_learning_control_room(
     jsonb_build_object(
       'organization_id', 'fa100000-0000-4000-8000-000000000001',
       'product_category', 'baa'
     )
   ) #> '{category_detail,readiness,dimensions}') dimension
   where dimension ->> 'key' = 'analysis_coverage'),
  '1',
  'duplicate source rows with the same SHA count as one analyzed workbook'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
    'baa-semantic-duplicate', 'confirm',
    'historical-confirm-semantic-copy-1',
    'fa400000-0000-4000-8000-000000000002'
  )$$,
  'the copied provenance row can be reviewed independently'
);

update historical_case_test_state
set semantic_duplicate_policy = public.creator_generation_learning_policy(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'media_id', 'fa300000-0000-4000-8000-000000000001',
    'platform', 'youtube', 'model', 'seedream5_lite',
    'product_category', 'baa'
  )
);

select ok(
  (select semantic_duplicate_policy #>>
      '{historical_case_evidence,considered_case_count}' = '5'
    and exists (
      select 1
      from jsonb_array_elements(semantic_duplicate_policy #>
        '{historical_case_evidence,angles}') angle
      where angle ->> 'creative_angle' = 'comparison'
        and angle ->> 'confirmed_case_count' = '1'
        and angle ->> 'score' = '1'
    )
   from historical_case_test_state)
  and (select angle -> 'preferred_eligible' = 'false'::jsonb
      and angle ->> 'preferred_ready_product_count' = '0'
    from jsonb_array_elements(public.creator_ai_learning_control_room(
      jsonb_build_object(
        'organization_id', 'fa100000-0000-4000-8000-000000000001',
        'product_category', 'baa'
      )
    ) #> '{historical_case_evidence,angles}') angle
    where angle ->> 'creative_angle' = 'comparison'),
  'duplicate source copies collapse to one semantic vote below threshold'
);

update historical_case_test_state
set external_confirm_snapshot = public.creator_ai_learning_control_room(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'product_category', 'baa'
  )
);

select ok(
  (select (external_confirm_snapshot #>>
      '{historical_case_evidence,historical_learning_eligible_count}')
        ::integer = 5
    and (external_confirm_snapshot #>>
      '{historical_case_evidence,missing_exact_product_binding_count}')
        ::integer = 3
   from historical_case_test_state)
  and (select public.creator_generation_learning_policy(jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001',
      'media_id', 'fa300000-0000-4000-8000-000000000001',
      'platform', 'youtube', 'model', 'seedream5_lite',
      'product_category', 'baa'
    )) #>> '{historical_case_evidence,considered_case_count}') = '5',
  'external-only SKU cases stay readable but cannot enter product learning yet'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
) values (
  'fa200000-0000-4000-8000-000000000002',
  'fa100000-0000-4000-8000-000000000001',
  'QEEP-EXTERNAL-ONLY', 'External QEEP SKU', 'active',
  'fa000000-0000-4000-8000-000000000001'
);

update historical_case_test_state
set catalog_replay_result = pg_temp.call_historical_import(
  pg_temp.historical_import_payload('historical-import-post-catalog-replay')
);

select ok(
  (select catalog_replay_result #>> '{batch,batch_id}' =
      import_result #>> '{batch,batch_id}'
      and catalog_replay_result -> 'replayed' = 'true'::jsonb
    from historical_case_test_state)
  and (
    select count(*) = 3
    from content_factory.ai_historical_case_events historical_case
    where historical_case.organization_id =
      'fa100000-0000-4000-8000-000000000001'
      and historical_case.external_case_id in (
        'baa-external-sku', 'baa-external-sku-2',
        'baa-external-comparison'
      )
      and historical_case.product_id is null
      and historical_case.resolution_method = 'source_external_sku'
  ),
  'fresh-key replay is stable after catalog changes and preserves stored rows'
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
) values (
  'fa300000-0000-4000-8000-000000000002',
  'fa100000-0000-4000-8000-000000000001',
  'fa000000-0000-4000-8000-000000000001',
  'fa200000-0000-4000-8000-000000000002',
  'contentengine-private',
  'fa100000-0000-4000-8000-000000000001/fa000000-0000-4000-8000-000000000001/uploads/historical-late-bound.jpg',
  'image/jpeg', 2048, repeat('e', 64), 'ready',
  '{"kind":"product_photo","rights_confirmed":true}'::jsonb,
  'historical-case-media-0002'
);

update historical_case_test_state
set late_bound_snapshot = public.creator_ai_learning_control_room(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'product_category', 'baa'
  )
),
late_bound_policy = public.creator_generation_learning_policy(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'media_id', 'fa300000-0000-4000-8000-000000000002',
    'platform', 'youtube', 'model', 'seedream5_lite',
    'product_category', 'baa'
  )
);

select ok(
  (select
      (late_bound_snapshot #>>
        '{historical_case_evidence,historical_learning_eligible_count}')
          ::integer = 8
      and (late_bound_snapshot #>>
        '{historical_case_evidence,historical_learning_direct_product_binding_count}')
          ::integer = 5
      and (late_bound_snapshot #>>
        '{historical_case_evidence,historical_learning_late_exact_sku_binding_count}')
          ::integer = 3
      and (late_bound_snapshot #>>
        '{historical_case_evidence,missing_exact_product_binding_count}')
          ::integer = 0
      and late_bound_policy #>>
        '{historical_case_evidence,considered_case_count}' = '3'
      and late_bound_policy #>>
        '{historical_case_evidence,direct_product_binding_case_count}' = '0'
      and late_bound_policy #>>
        '{historical_case_evidence,late_exact_sku_binding_case_count}' = '3'
      and late_bound_policy #>>
        '{historical_case_evidence,preferred_score}' = '2'
      and late_bound_policy #>> '{historical_case_advisory,applied}' = 'true'
      and late_bound_policy ->> 'preferred_angle' = 'product_focus'
      and jsonb_array_length(late_bound_policy #>
        '{historical_case_evidence,bounded_case_refs}') = 3
      and not exists (
        select 1
        from jsonb_array_elements(late_bound_policy #>
          '{historical_case_evidence,bounded_case_refs}') case_ref
        where case_ref ->> 'binding_method' <>
          'late_unique_product_sku'
      )
      and exists (
        select 1
        from jsonb_array_elements(late_bound_snapshot #>
          '{historical_case_evidence,angles}') angle
        where angle ->> 'creative_angle' = 'comparison'
          and angle ->> 'confirmed_case_count' = '2'
          and angle ->> 'distinct_product_count' = '2'
          and angle ->> 'preferred_ready_product_count' = '0'
          and angle -> 'preferred_eligible' = 'false'::jsonb
      )
    from historical_case_test_state),
  'late binding learns one product while one vote on each product stays unready'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
    'baa-semantic-duplicate', 'reject',
    'historical-reject-semantic-copy-1',
    'fa400000-0000-4000-8000-000000000002'
  )$$,
  'a later decision on a duplicate provenance row can reject the semantic case'
);

update historical_case_test_state
set semantic_reject_policy = public.creator_generation_learning_policy(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'media_id', 'fa300000-0000-4000-8000-000000000001',
    'platform', 'youtube', 'model', 'seedream5_lite',
    'product_category', 'baa'
  )
);

select ok(
  (select semantic_reject_policy #>>
      '{historical_case_evidence,considered_case_count}' = '4'
    and not exists (
      select 1
      from jsonb_array_elements(semantic_reject_policy #>
        '{historical_case_evidence,angles}') angle
      where angle ->> 'creative_angle' = 'comparison'
    )
   from historical_case_test_state),
  'the newest duplicate reject shadows every older confirm of that semantic case'
);

select lives_ok(
  $$select pg_temp.call_historical_import(
    pg_temp.historical_independent_row_payload()
  )$$,
  'the same external id may carry a source-independent row with new content'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
    'baa-semantic-duplicate', 'confirm',
    'historical-confirm-semantic-independent-1',
    'fa400000-0000-4000-8000-000000000003'
  )$$,
  'the independently hashed row can be reviewed without reviving its duplicate'
);

update historical_case_test_state
set semantic_independent_policy = public.creator_generation_learning_policy(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'media_id', 'fa300000-0000-4000-8000-000000000001',
    'platform', 'youtube', 'model', 'seedream5_lite',
    'product_category', 'baa'
  )
);

select ok(
  (select semantic_independent_policy #>>
      '{historical_case_evidence,considered_case_count}' = '5'
    and exists (
      select 1
      from jsonb_array_elements(semantic_independent_policy #>
        '{historical_case_evidence,angles}') angle
      where angle ->> 'creative_angle' = 'comparison'
        and angle ->> 'confirmed_case_count' = '1'
        and angle ->> 'score' = '1'
    )
   from historical_case_test_state)
  and (select dimension ->> 'current'
   from jsonb_array_elements(public.creator_ai_learning_control_room(
     jsonb_build_object(
       'organization_id', 'fa100000-0000-4000-8000-000000000001',
       'product_category', 'baa'
     )
   ) #> '{category_detail,readiness,dimensions}') dimension
   where dimension ->> 'key' = 'analysis_coverage') = '1',
  'different row hashes remain independent while identical SHA sources dedupe'
);

select lives_ok(
  $$select pg_temp.call_historical_import(
    pg_temp.historical_late_partial_payload()
  )$$,
  'multiple unresolved external references remain reviewable before binding'
);

select ok(
  (select historical_case.resolution_status = 'matched'
      and historical_case.resolution_method = 'source_external_sku'
      and historical_case.product_id is null
   from content_factory.ai_historical_case_events historical_case
   where historical_case.organization_id =
     'fa100000-0000-4000-8000-000000000001'
     and historical_case.external_case_id = 'baa-late-partial-reference'),
  'an all-unresolved multi-reference case does not invent a product binding'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
) values (
  'fa200000-0000-4000-8000-000000000003',
  'fa100000-0000-4000-8000-000000000001',
  'LATE-PARTIAL-SKU', 'Late partial SKU product', 'active',
  'fa000000-0000-4000-8000-000000000001'
);

select is(
  (select content_factory_private.ai_historical_case_product_binding_method(
      historical_case.organization_id,
      historical_case.case_id,
      'fa200000-0000-4000-8000-000000000003'
    )
   from content_factory.ai_historical_case_events historical_case
   where historical_case.external_case_id = 'baa-late-partial-reference'),
  null::text,
  'late binding rejects one resolved ref while another remains unresolved'
);

insert into content_factory.products (
  id, organization_id, sku, title, current_wb_article,
  status, created_by
) values (
  'fa200000-0000-4000-8000-000000000004',
  'fa100000-0000-4000-8000-000000000001',
  'LATE-PARTIAL-OTHER', 'Late conflicting marketplace product',
  '99887766', 'active',
  'fa000000-0000-4000-8000-000000000001'
);

select is(
  (select content_factory_private.ai_historical_case_product_binding_method(
      historical_case.organization_id,
      historical_case.case_id,
      'fa200000-0000-4000-8000-000000000003'
    )
   from content_factory.ai_historical_case_events historical_case
   where historical_case.external_case_id = 'baa-late-partial-reference'),
  null::text,
  'late binding rejects references that resolve uniquely to different products'
);

update content_factory.products
set current_wb_article = null
where organization_id = 'fa100000-0000-4000-8000-000000000001'
  and id = 'fa200000-0000-4000-8000-000000000004';
update content_factory.products
set current_wb_article = '99887766'
where organization_id = 'fa100000-0000-4000-8000-000000000001'
  and id = 'fa200000-0000-4000-8000-000000000003';

select is(
  (select content_factory_private.ai_historical_case_product_binding_method(
      historical_case.organization_id,
      historical_case.case_id,
      'fa200000-0000-4000-8000-000000000003'
    )
   from content_factory.ai_historical_case_events historical_case
   where historical_case.external_case_id = 'baa-late-partial-reference'),
  'late_unique_product_sku',
  'late binding succeeds only after every reference resolves to one product'
);

select throws_ok(
  $$select pg_temp.decide_historical_case(
    'baa-missing-product', 'confirm', 'historical-confirm-quarantine-1'
  )$$,
  '55000',
  'ai_historical_case_quarantined',
  'a quarantined product identity cannot be confirmed into learning'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
    'baa-good-2', 'reject', 'historical-reject-good-2'
  )$$,
  'a later reject appends a new immutable head'
);

update historical_case_test_state
set after_reject_policy = public.creator_generation_learning_policy(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'media_id', 'fa300000-0000-4000-8000-000000000001',
    'platform', 'youtube', 'model', 'seedream5_lite',
    'product_category', 'baa'
  )
);

select ok(
  (select after_reject_policy #>>
      '{historical_case_evidence,considered_case_count}' = '4'
    and after_reject_policy #>>
      '{historical_case_advisory,preferred_creative_angle}' is null
    and after_reject_policy #>>
      '{historical_case_advisory,avoid_creative_angle}' = 'demonstration'
    and after_reject_policy #>> '{historical_case_evidence,preferred_score}' = '1'
    and after_reject_policy #>> '{historical_case_evidence,avoid_score}' = '-2'
    and after_reject_policy #>> '{historical_case_advisory,applied}' = 'true'
   from historical_case_test_state),
  'the latest reject removes its positive vote while confirmed bad evidence remains'
);

select lives_ok(
  $$select pg_temp.decide_historical_case(
    'baa-good-2', 'confirm', 'historical-restore-good-2'
  )$$,
  'a fresh CAS decision can restore an explicitly reviewed case'
);

select is(
  (select count(*)::integer
   from content_factory.ai_effective_category_policies
   where organization_id = 'fa100000-0000-4000-8000-000000000001'),
  0,
  'historical decisions never mutate the explicit teaching-policy ledger'
);

select lives_ok(
  $$
    select public.creator_decide_ai_teaching_card(jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001',
      'product_category', 'baa',
      'card_id', card.id,
      'card_hash', card.card_hash,
      'card_version', card.version,
      'expected_scope_version', 0,
      'decision', 'approve',
      'reason_code', 'operator_confirmed',
      'confirmation', true,
      'idempotency_key', 'historical-manual-teaching-0001'
    ))
    from content_factory.ai_teaching_card_catalog card
    where card.creative_angle = 'comparison'
      and card.ai_judgement = 'good'
      and card.status = 'active'
    order by card.version desc
    limit 1
  $$,
  'an explicit manual teaching policy can be added independently'
);

update historical_case_test_state
set manual_policy = public.creator_generation_learning_policy(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'media_id', 'fa300000-0000-4000-8000-000000000001',
    'platform', 'youtube', 'model', 'seedream5_lite',
    'product_category', 'baa'
  )
);

select ok(
  (select manual_policy ->> 'preferred_angle' = 'comparison'
    and manual_policy #>>
      '{historical_case_advisory,shadowed_by_manual_teaching_policy}' = 'true'
    and manual_policy #>> '{historical_case_advisory,applied}' = 'false'
   from historical_case_test_state),
  'explicit teaching-card policy always wins over historical fallback'
);

select pg_temp.set_historical_actor(
  'fa000000-0000-4000-8000-000000000002'
);
update historical_case_test_state
set reviewer_snapshot = public.creator_ai_learning_control_room(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001',
    'product_category', 'baa'
  )
);

select ok(
  (select reviewer_snapshot #>>
      '{capabilities,can_read_historical_cases}' = 'true'
    and reviewer_snapshot #>>
      '{capabilities,can_import_historical_cases}' = 'false'
    and reviewer_snapshot #>>
      '{capabilities,can_decide_historical_case}' = 'false'
   from historical_case_test_state),
  'reviewers can read but control-room capabilities deny historical mutations'
);

set local role authenticated;
select throws_ok(
  $$select public.creator_authorize_ai_historical_case_import('{}'::jsonb)$$,
  '42501',
  'permission denied for function creator_authorize_ai_historical_case_import',
  'authenticated clients cannot execute the bounded source authorization RPC'
);
select throws_ok(
  $$select public.creator_import_ai_historical_case_batch('{}'::jsonb)$$,
  '42501',
  'permission denied for function creator_import_ai_historical_case_batch',
  'authenticated clients cannot execute the parser-boundary import RPC'
);
reset role;

select pg_temp.set_historical_actor(
  'fa000000-0000-4000-8000-000000000001'
);

select throws_ok(
  $$
    update content_factory.ai_historical_case_import_batches
    set import_status = 'completed'
    where organization_id = 'fa100000-0000-4000-8000-000000000001'
  $$,
  '55000',
  'ai_learning_append_only',
  'batch parse and quarantine summary cannot be rewritten'
);

select throws_ok(
  $$
    delete from content_factory.ai_historical_case_events
    where organization_id = 'fa100000-0000-4000-8000-000000000001'
      and external_case_id = 'baa-good-1'
  $$,
  '55000',
  'ai_learning_append_only',
  'imported case events cannot be deleted'
);

select throws_ok(
  $$
    update content_factory.ai_historical_case_decisions
    set decision = 'reject'
    where organization_id = 'fa100000-0000-4000-8000-000000000001'
  $$,
  '55000',
  'ai_learning_append_only',
  'historical human decisions cannot be edited in place'
);

select is(
  (select jsonb_build_object(
    'generation_batches', (
      select count(*) from content_factory.generation_batches
      where organization_id = 'fa100000-0000-4000-8000-000000000001'
    ),
    'generation_jobs', (
      select count(*) from content_factory.generation_jobs
      where organization_id = 'fa100000-0000-4000-8000-000000000001'
    ),
    'generation_spend_ledger', (
      select count(*) from content_factory.generation_spend_ledger
      where organization_id = 'fa100000-0000-4000-8000-000000000001'
    )
  )),
  (select before_side_effect_counts from historical_case_test_state),
  'imports and decisions start no provider job, generation batch, or spend entry'
);

select ok(
  position(
    'ai_historical_case_events' in lower(pg_get_functiondef(
      'content_factory_private.creator_generation_learning_policy_pre_historical_case_v1(jsonb)'
        ::regprocedure
    ))
  ) = 0
  and position(
    'generation_allowed_value :=' in lower(pg_get_functiondef(
      'public.creator_generation_learning_policy(jsonb)'::regprocedure
    ))
  ) > 0
  and position(
    'historical_fallback_allowed' in lower(pg_get_functiondef(
      'public.creator_generation_learning_policy(jsonb)'::regprocedure
    ))
  ) > 0,
  'the wrapper isolates historical evidence and preserves the base generation gate'
);

select ok(
  position(
    'candidate_cases as materialized' in lower(pg_get_functiondef(
      'content_factory_private.ai_historical_product_case_evidence(uuid,text,uuid)'
        ::regprocedure
    ))
  ) > 0
  and position(
    'historical_case.product_sku = target_product_row.sku' in
      lower(pg_get_functiondef(
        'content_factory_private.ai_historical_product_case_evidence(uuid,text,uuid)'
          ::regprocedure
      ))
  ) > 0
  and position(
    'historical_case.marketplace_sku =' in lower(pg_get_functiondef(
      'content_factory_private.ai_historical_product_case_evidence(uuid,text,uuid)'
        ::regprocedure
    ))
  ) > 0,
  'generation prefilters exact current-product candidates before late-binding helper calls'
);

select * from finish();
rollback;
