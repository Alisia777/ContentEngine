begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

-- Structure: the reactivated teaching overlay and the capability surface.
select has_function(
  'content_factory_private',
  'creator_generation_learning_policy_pre_project_v47',
  array['jsonb'],
  'the private project-scoped policy delegate exists'
);
select has_function(
  'content_factory_private',
  'ai_historical_case_product_binding_method',
  array['uuid', 'uuid', 'uuid'],
  'the historical-case product binding helper exists'
);
select has_function(
  'public', 'creator_ai_learning_control_room', array['jsonb'],
  'the AI learning control room RPC exists'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)'::regprocedure
  )), 'ai_effective_category_policies') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)'::regprocedure
  )), 'generation-learning-v9-ai-teaching') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)'::regprocedure
  )), 'creator_generation_learning_policy_pre_ai_control_room_v8') > 0,
  'the project delegate applies confirmed teaching policies over the v8 base'
);

select ok(
  has_function_privilege(
    'authenticated', 'public.creator_ai_learning_control_room(jsonb)', 'execute'
  )
  and has_function_privilege(
    'service_role', 'public.creator_ai_learning_control_room(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon', 'public.creator_ai_learning_control_room(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)',
    'execute'
  ),
  'control room stays a creator boundary and the teaching delegate stays private'
);

-- Fixture: one owner, one organization, one cosmetics knowledge source.
insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'fb000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'prompt-reactivation-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Prompt Reactivation Owner"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'fb100000-0000-4000-8000-000000000001',
  'Prompt Reactivation pgTAP',
  'prompt-reactivation-pgtap',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'fb100000-0000-4000-8000-000000000001',
  'fb000000-0000-4000-8000-000000000001',
  'owner', 'active'
);

insert into content_factory.ai_category_knowledge_sources (
  id, organization_id, product_category, source_kind, owner_id,
  title, bucket_id, object_name, original_filename, mime_type,
  size_bytes, sha256, rights_confirmed, status,
  source_hash, request_hash, idempotency_key
) values (
  'fb400000-0000-4000-8000-000000000001',
  'fb100000-0000-4000-8000-000000000001',
  'cosmetics', 'file', 'fb000000-0000-4000-8000-000000000001',
  'Harly historical workbook', 'contentengine-knowledge',
  'fb100000-0000-4000-8000-000000000001/fb000000-0000-4000-8000-000000000001/ai-knowledge/harly-cases.xlsx',
  'harly-cases.xlsx',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  4096, repeat('4', 64), true, 'active',
  repeat('5', 64), repeat('6', 64), 'reactivation-source-0001'
);

create or replace function pg_temp.set_reactivation_actor(p_actor_id uuid)
returns void
language plpgsql
as $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config('request.jwt.claim.sub', p_actor_id::text, true);
end;
$$;

create or replace function pg_temp.call_reactivation_import(p_payload jsonb)
returns jsonb
language plpgsql
as $$
declare
  previous_claim_role text := current_setting('request.jwt.claim.role', true);
  result_value jsonb;
begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
  begin
    result_value := public.creator_import_ai_historical_case_batch(
      p_payload || jsonb_build_object(
        'actor_profile_id', 'fb000000-0000-4000-8000-000000000001'
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

create or replace function pg_temp.decide_reactivation_case(
  p_external_case_id text,
  p_decision text,
  p_idempotency_key text
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
    'fb100000-0000-4000-8000-000000000001'
    and historical_case.external_case_id = p_external_case_id
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

create temporary table reactivation_test_state (
  import_result jsonb,
  advisory_policy jsonb,
  teaching_policy jsonb,
  owner_snapshot jsonb
) on commit drop;
insert into reactivation_test_state default values;

select pg_temp.set_reactivation_actor('fb000000-0000-4000-8000-000000000001');

-- Import three harly/qeep-shaped cases BEFORE any product exists, exactly like
-- the live 337-case archive: the product_sku matches nothing and the WB
-- article digits stay an unresolved source reference.
update reactivation_test_state
set import_result = pg_temp.call_reactivation_import(jsonb_build_object(
  'organization_id', 'fb100000-0000-4000-8000-000000000001',
  'schema_version', 'ai_historical_cases.v1',
  'product_category', 'cosmetics',
  'source_id', 'fb400000-0000-4000-8000-000000000001',
  'original_filename', 'harly-cases.xlsx',
  'source_sha256', repeat('4', 64),
  'parser_version', 'xlsx-v1',
  'manifest_sha256', repeat('a', 64),
  'idempotency_key', 'reactivation-import-0001',
  'batch_index', 1,
  'batch_count', 1,
  'parsed_row_count', 3,
  'parser_quarantined_row_count', 0,
  'parser_quarantine_summary', '{}'::jsonb,
  'cases', jsonb_build_array(
    jsonb_build_object(
      'external_case_id', 'cosmetics-digit-1',
      'product_category', 'cosmetics',
      'product_sku', 'HARLY-EXT-1',
      'marketplace_sku', '518413561',
      'product_title', 'Harly effect serum',
      'brand', 'Harly',
      'platform', 'wildberries', 'channel', 'marketplace',
      'period_start', '2026-05-01', 'period_end', '2026-05-31',
      'outcome', 'good', 'outcome_dimension', 'content_conversion',
      'status_label', 'confirmed_leader',
      'metrics', jsonb_build_object('orders', 40, 'buyout_rate', 0.87),
      'confidence', 0.93, 'creative_angle', 'product_focus',
      'provenance', jsonb_build_object(
        'sheet', 'Harly', 'row', 5, 'row_hash', repeat('1', 64)
      )
    ),
    jsonb_build_object(
      'external_case_id', 'cosmetics-digit-2',
      'product_category', 'cosmetics',
      'product_sku', 'HARLY-EXT-1',
      'marketplace_sku', '518413561',
      'product_title', 'Harly effect serum',
      'brand', 'Harly',
      'platform', 'instagram', 'channel', 'content',
      'period_start', '2026-06-01', 'period_end', '2026-06-30',
      'outcome', 'good', 'outcome_dimension', 'purchase_transition',
      'status_label', 'superstar',
      'metrics', jsonb_build_object('orders', 25, 'sale_per_view', 0.06),
      'confidence', 0.9, 'creative_angle', 'product_focus',
      'provenance', jsonb_build_object(
        'sheet', 'Harly', 'row', 6, 'row_hash', repeat('2', 64)
      )
    ),
    jsonb_build_object(
      'external_case_id', 'cosmetics-ambiguous',
      'product_category', 'cosmetics',
      'marketplace_sku', '777000111',
      'product_title', 'Qeep funnel booster',
      'brand', 'QEEP',
      'platform', 'ozon', 'channel', 'marketplace',
      'period_start', '2026-06-01', 'period_end', '2026-06-30',
      'outcome', 'good', 'outcome_dimension', 'overall_performance',
      'status_label', 'ambiguous_candidate',
      'metrics', jsonb_build_object('orders', 9),
      'confidence', 0.8, 'creative_angle', 'demonstration',
      'provenance', jsonb_build_object(
        'sheet', 'Qeep', 'row', 7, 'row_hash', repeat('3', 64)
      )
    )
  )
));

select ok(
  (select import_result -> 'ok' = 'true'::jsonb
     and (import_result #>> '{batch,matched_case_count}')::integer = 3
   from reactivation_test_state),
  'the harly/qeep-shaped workbook imports with all cases reviewable'
);

select ok(
  (select count(*) = 2
   from content_factory.ai_historical_case_events historical_case
   where historical_case.organization_id =
     'fb100000-0000-4000-8000-000000000001'
     and historical_case.external_case_id in (
       'cosmetics-digit-1', 'cosmetics-digit-2'
     )
     and historical_case.product_id is null
     and historical_case.resolution_status = 'matched'
     and historical_case.resolution_method = 'source_external_sku')
  and (select historical_case.product_id is null
     and historical_case.resolution_status = 'matched'
     and historical_case.resolution_method = 'source_marketplace_sku'
   from content_factory.ai_historical_case_events historical_case
   where historical_case.organization_id =
     'fb100000-0000-4000-8000-000000000001'
     and historical_case.external_case_id = 'cosmetics-ambiguous'),
  'pre-registration imports keep source references without inventing bindings'
);

select lives_ok(
  $$select pg_temp.decide_reactivation_case(
    'cosmetics-digit-1', 'confirm', 'reactivation-confirm-digit-1'
  )$$,
  'the first digit-article case can be confirmed before its product exists'
);
select lives_ok(
  $$select pg_temp.decide_reactivation_case(
    'cosmetics-digit-2', 'confirm', 'reactivation-confirm-digit-2'
  )$$,
  'the second digit-article case can be confirmed before its product exists'
);

-- The owner registers the products AFTER the import, using the raw WB article
-- digits as products.sku (live-row pattern), plus one deliberately ambiguous
-- article carried by two different products.
insert into content_factory.products (
  id, organization_id, sku, title, current_wb_article, status, created_by
) values
(
  'fb200000-0000-4000-8000-000000000001',
  'fb100000-0000-4000-8000-000000000001',
  '518413561', 'Harly effect serum', null,
  'active', 'fb000000-0000-4000-8000-000000000001'
),
(
  'fb200000-0000-4000-8000-000000000002',
  'fb100000-0000-4000-8000-000000000001',
  '777000111', 'Qeep funnel booster digit sku', null,
  'active', 'fb000000-0000-4000-8000-000000000001'
),
(
  'fb200000-0000-4000-8000-000000000003',
  'fb100000-0000-4000-8000-000000000001',
  'AMB-WB-PROD', 'Qeep funnel booster wb alias', '777000111',
  'active', 'fb000000-0000-4000-8000-000000000001'
);

-- Binding scenario: product_sku miss falls through to the marketplace key and
-- the digit-only sku binds; an ambiguous combined candidate set stays null.
select is(
  (select content_factory_private.ai_historical_case_product_binding_method(
      historical_case.organization_id,
      historical_case.case_id,
      'fb200000-0000-4000-8000-000000000001'
    )
   from content_factory.ai_historical_case_events historical_case
   where historical_case.organization_id =
     'fb100000-0000-4000-8000-000000000001'
     and historical_case.external_case_id = 'cosmetics-digit-1'),
  'late_unique_marketplace_sku',
  'a zero-match product_sku falls through and the digit sku binds the WB article'
);

select is(
  (select content_factory_private.ai_historical_case_product_binding_method(
      historical_case.organization_id,
      historical_case.case_id,
      'fb200000-0000-4000-8000-000000000002'
    )
   from content_factory.ai_historical_case_events historical_case
   where historical_case.organization_id =
     'fb100000-0000-4000-8000-000000000001'
     and historical_case.external_case_id = 'cosmetics-ambiguous'),
  null::text,
  'a WB article matching two products stays unbound for the digit-sku product'
);

select is(
  (select content_factory_private.ai_historical_case_product_binding_method(
      historical_case.organization_id,
      historical_case.case_id,
      'fb200000-0000-4000-8000-000000000003'
    )
   from content_factory.ai_historical_case_events historical_case
   where historical_case.organization_id =
     'fb100000-0000-4000-8000-000000000001'
     and historical_case.external_case_id = 'cosmetics-ambiguous'),
  null::text,
  'a WB article matching two products stays unbound for the alias product too'
);

-- Evidence scenario: both confirmed digit-article cases reach the bounded
-- exact-product evidence through the widened preselect.
select ok(
  (select (evidence ->> 'considered_case_count')::integer = 2
     and (evidence ->> 'eligible_total_case_count')::integer = 2
     and (evidence ->> 'late_exact_sku_binding_case_count')::integer = 2
     and (evidence ->> 'direct_product_binding_case_count')::integer = 0
     and evidence ->> 'advisory_preferred_creative_angle' = 'product_focus'
     and (evidence ->> 'preferred_score')::integer = 2
     and evidence ->> 'advisory_avoid_creative_angle' is null
   from (
     select content_factory_private.ai_historical_product_case_evidence(
       'fb100000-0000-4000-8000-000000000001',
       'cosmetics',
       'fb200000-0000-4000-8000-000000000001'
     ) as evidence
   ) computed),
  'two confirmed digit-article cases produce a tie-free product_focus advisory'
);

-- Project-scoped chain fixture for the live policy dispatch.
insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'fb500000-0000-4000-8000-000000000001',
  'fb100000-0000-4000-8000-000000000001',
  null, 'Prompt reactivation project', 'blue', 'project', null,
  'active', 1024,
  'fb000000-0000-4000-8000-000000000001',
  'fb000000-0000-4000-8000-000000000001'
);

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id, bucket_id,
  object_name, mime_type, size_bytes, sha256, status, metadata,
  idempotency_key
) values (
  'fb300000-0000-4000-8000-000000000001',
  'fb100000-0000-4000-8000-000000000001',
  'fb500000-0000-4000-8000-000000000001',
  'fb000000-0000-4000-8000-000000000001',
  'fb200000-0000-4000-8000-000000000001',
  'contentengine-private',
  'fb100000-0000-4000-8000-000000000001/fb000000-0000-4000-8000-000000000001/uploads/reactivation-product.jpg',
  'image/jpeg', 2048, repeat('9', 64), 'ready',
  '{"kind":"product_photo","rights_confirmed":true}'::jsonb,
  'reactivation-media-0001'
);

-- Stub ONLY the preserved v8 base inside this rollback-only transaction so the
-- restored overlay and both real advisory layers stay deterministic.  Every
-- layer above the stub (public wrapper, pre_advisory_v9,
-- pre_historical_case_v1, call_project_scoped_v47, pre_project_v47) runs the
-- real installed definition.
create or replace function content_factory_private
  .creator_generation_learning_policy_pre_ai_control_room_v8(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  return jsonb_build_object(
    'version', 'pgtap-reactivation-base-v8',
    'product_category', p_payload ->> 'product_category',
    'generation_allowed', true,
    'applied', false,
    'confidence', 'none',
    'preferred_angle', 'demonstration',
    'avoid_angle', null,
    'preferred_hook_patterns', jsonb_build_array('base-hook-must-clear'),
    'selected_hook_patterns', jsonb_build_array('base-hook-must-clear'),
    'reason_codes', '[]'::jsonb,
    'safety', jsonb_build_object('base_guard_preserved', true),
    'policy_hash', repeat('1', 64),
    'requested_model', p_payload ->> 'model'
  );
end;
$$;

-- Scenario: no manual teaching policy yet, so the confirmed historical
-- evidence applies through the digit-article late binding.
update reactivation_test_state
set advisory_policy = public.creator_generation_learning_policy(
  jsonb_build_object(
    'organization_id', 'fb100000-0000-4000-8000-000000000001',
    'project_id', 'fb500000-0000-4000-8000-000000000001',
    'media_id', 'fb300000-0000-4000-8000-000000000001',
    'platform', 'youtube', 'model', 'seedream5_lite',
    'product_category', 'cosmetics'
  )
);

select ok(
  (select advisory_policy ->> 'version' =
      'generation-learning-v10-historical-case-evidence'
    and advisory_policy -> 'reason_codes' ? 'historical_case_advisory_applied'
    and advisory_policy ->> 'preferred_angle' = 'product_focus'
    and advisory_policy ->> 'selected_angle' = 'product_focus'
    and advisory_policy #>> '{historical_case_advisory,applied}' = 'true'
    and advisory_policy #>>
      '{historical_case_advisory,preferred_creative_angle}' = 'product_focus'
    and advisory_policy #>>
      '{historical_case_evidence,considered_case_count}' = '2'
    and advisory_policy #>>
      '{historical_case_evidence,late_exact_sku_binding_case_count}' = '2'
    and advisory_policy #>> '{selection_provenance,source}' =
      'confirmed_historical_case_aggregate'
   from reactivation_test_state),
  'without manual teaching two confirmed digit-bound cases steer generation'
);

-- Scenario: an explicit teach-card decision creates a manual category policy;
-- the restored overlay applies it and the historical advisory yields.
select lives_ok(
  $$
    select public.creator_decide_ai_teaching_card(jsonb_build_object(
      'organization_id', 'fb100000-0000-4000-8000-000000000001',
      'product_category', 'cosmetics',
      'card_id', card.id,
      'card_hash', card.card_hash,
      'card_version', card.version,
      'expected_scope_version', 0,
      'decision', 'approve',
      'reason_code', 'operator_confirmed',
      'confirmation', true,
      'idempotency_key', 'reactivation-teach-0001'
    ))
    from content_factory.ai_teaching_card_catalog card
    where card.creative_angle = 'trust_builder'
      and card.ai_judgement = 'good'
      and card.status = 'active'
    order by card.version desc
    limit 1
  $$,
  'the owner can confirm an explicit trust_builder teaching card'
);

select is(
  (select policy.preferred_creative_angle
   from content_factory.ai_effective_category_policies policy
   where policy.organization_id = 'fb100000-0000-4000-8000-000000000001'
     and policy.product_category = 'cosmetics'
   order by policy.scope_version desc
   limit 1),
  'trust_builder',
  'the teach decision materializes an effective category policy head'
);

update reactivation_test_state
set teaching_policy = public.creator_generation_learning_policy(
  jsonb_build_object(
    'organization_id', 'fb100000-0000-4000-8000-000000000001',
    'project_id', 'fb500000-0000-4000-8000-000000000001',
    'media_id', 'fb300000-0000-4000-8000-000000000001',
    'platform', 'youtube', 'model', 'seedream5_lite',
    'product_category', 'cosmetics'
  )
);

select ok(
  (select teaching_policy ->> 'version' = 'generation-learning-v9-ai-teaching'
    and teaching_policy -> 'reason_codes' ? 'ai_teaching_positive_angle_applied'
    and teaching_policy -> 'reason_codes' ?
      'historical_case_advisory_shadowed_by_manual_teaching_policy'
    and teaching_policy ->> 'preferred_angle' = 'trust_builder'
    and teaching_policy ->> 'selected_angle' = 'trust_builder'
    and teaching_policy -> 'applied' = 'true'::jsonb
    and teaching_policy ->> 'confidence' = 'high'
    and teaching_policy -> 'preferred_hook_patterns' = '[]'::jsonb
    and teaching_policy -> 'selected_hook_patterns' = '[]'::jsonb
    and teaching_policy #>> '{ai_teaching_policy,preferred_creative_angle}' =
      'trust_builder'
    and teaching_policy #>> '{selection_provenance,source}' =
      'human_teaching_card_policy'
    and teaching_policy #>>
      '{historical_case_advisory,shadowed_by_manual_teaching_policy}' = 'true'
    and teaching_policy #>> '{historical_case_advisory,applied}' = 'false'
   from reactivation_test_state),
  'a confirmed teach card steers the prompt and shadows the historical advisory'
);

-- Scenario: the control room announces the reopened legacy intake while the
-- research-inbox lockdown stays intact.
update reactivation_test_state
set owner_snapshot = public.creator_ai_learning_control_room(
  jsonb_build_object(
    'organization_id', 'fb100000-0000-4000-8000-000000000001',
    'product_category', 'cosmetics'
  )
);

select ok(
  (select owner_snapshot #>> '{capabilities,legacy_intake_read_only}' = 'false'
    and owner_snapshot #>> '{capabilities,can_decide_research_inbox}' = 'false'
    and owner_snapshot #>> '{capabilities,can_read_research_inbox}' = 'false'
    and owner_snapshot -> 'research_inbox' = '[]'::jsonb
    and owner_snapshot -> 'research_decisions' = '[]'::jsonb
   from reactivation_test_state),
  'legacy intake reopens while the research inbox stays locked down'
);

select * from finish();
rollback;
