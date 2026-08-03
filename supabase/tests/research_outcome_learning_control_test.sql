begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select has_table(
  'content_factory', 'research_outcome_lineage_snapshots',
  'immutable outcome lineage ledger exists'
);
select has_table(
  'content_factory', 'research_outcome_learning_candidates',
  'bounded learning candidate ledger exists'
);
select has_table(
  'content_factory', 'research_outcome_learning_candidate_evidence',
  'candidate-to-lineage evidence junction exists'
);
select has_table(
  'content_factory', 'research_outcome_learning_decisions',
  'explicit learning decision ledger exists'
);
select has_table(
  'content_factory', 'research_outcome_learning_memory_versions',
  'versioned advisory memory ledger exists'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_outcome_lineage_snapshots'::regclass),
     ('content_factory.research_outcome_learning_candidates'::regclass),
     ('content_factory.research_outcome_learning_candidate_evidence'::regclass),
     ('content_factory.research_outcome_learning_decisions'::regclass),
     ('content_factory.research_outcome_learning_memory_versions'::regclass)
   ) protected(table_oid)
   join pg_class relation on relation.oid = protected.table_oid
   where relation.relrowsecurity),
  5,
  'all five outcome-learning ledgers have RLS enabled'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_outcome_lineage_snapshots'::regclass),
     ('content_factory.research_outcome_learning_candidates'::regclass),
     ('content_factory.research_outcome_learning_candidate_evidence'::regclass),
     ('content_factory.research_outcome_learning_decisions'::regclass),
     ('content_factory.research_outcome_learning_memory_versions'::regclass)
   ) protected(table_oid)
   cross join (values ('select'), ('insert'), ('update'), ('delete')) privilege(name)
   where has_table_privilege('authenticated', table_oid, privilege.name)
      or has_table_privilege('service_role', table_oid, privilege.name)),
  0,
  'authenticated and service roles have no direct ledger privileges'
);

select has_function(
  'public', 'creator_refresh_research_outcome_learning', array['jsonb'],
  'explicit provider-free refresh RPC exists'
);
select has_function(
  'public', 'creator_decide_research_outcome_learning', array['jsonb'],
  'explicit candidate decision RPC exists'
);
select has_function(
  'public', 'creator_research_outcome_learning_status', array['jsonb'],
  'read-only outcome-learning status RPC exists'
);
select has_function(
  'content_factory_private', 'research_current_eligible_outcomes',
  array['uuid', 'uuid', 'text', 'text'],
  'refresh and activation share one exact live eligibility selector'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.research_current_eligible_outcomes(uuid,uuid,text,text)',
    'execute'
  ) and not has_function_privilege(
    'service_role',
    'content_factory_private.research_current_eligible_outcomes(uuid,uuid,text,text)',
    'execute'
  ),
  'the shared live eligibility selector remains private'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_refresh_research_outcome_learning(jsonb)', 'execute'
  ) and has_function_privilege(
    'authenticated',
    'public.creator_decide_research_outcome_learning(jsonb)', 'execute'
  ) and has_function_privilege(
    'authenticated',
    'public.creator_research_outcome_learning_status(jsonb)', 'execute'
  ),
  'authenticated users reach the control plane only through RPCs'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_refresh_research_outcome_learning(jsonb)'::regprocedure
  )), 'insert into content_factory.generation_jobs') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_refresh_research_outcome_learning(jsonb)'::regprocedure
  )), 'insert into content_factory.placements') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_refresh_research_outcome_learning(jsonb)'::regprocedure
  )), 'insert into content_factory.metric_snapshots') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_refresh_research_outcome_learning(jsonb)'::regprocedure
  )), 'creator_start_product_research') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'creator_start_real_generation') = 0,
  'refresh and decisions have no provider, generation, publication, or metric write path'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_refresh_research_outcome_learning(jsonb)'::regprocedure
  )), 'research_current_eligible_outcomes') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'research_current_eligible_outcomes') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'research_outcome_refresh_required') > 0,
  'refresh and activation cannot drift from the exact live source selector'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'limit 10000') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'select current_outcomes.id from current_outcomes') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'select candidate_evidence.id from candidate_evidence') > 0,
  'the independent top-10k bidirectional candidate evidence guard remains present'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'monitor_effectiveness_and_keep_rollback_ready') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'review_next_pending_candidate') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'collect_additional_evidence_before_reconsideration') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'review_rollback_target_or_wait_for_new_candidate') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_outcome_learning(jsonb)'::regprocedure
  )), 'monitor_restored_memory_and_keep_rollback_ready') > 0,
  'decision guidance defines a bounded recommended next step for all five actions'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
select fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated', fixture.email,
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name), now(), now()
from (values
  ('d5000000-0000-4000-8000-000000000001', 'learning-owner@example.test', 'Learning Owner'),
  ('d5000000-0000-4000-8000-000000000002', 'learning-producer@example.test', 'Learning Producer'),
  ('d5000000-0000-4000-8000-000000000003', 'learning-reviewer@example.test', 'Learning Reviewer'),
  ('d5000000-0000-4000-8000-000000000004', 'other-learning-owner@example.test', 'Other Learning Owner')
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  ('d5100000-0000-4000-8000-000000000001', 'Learning Tenant', 'learning-tenant-test', 'active'),
  ('d5100000-0000-4000-8000-000000000002', 'Other Learning Tenant', 'other-learning-test', 'active');
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  ('d5100000-0000-4000-8000-000000000001', 'd5000000-0000-4000-8000-000000000001', 'owner', 'active'),
  ('d5100000-0000-4000-8000-000000000001', 'd5000000-0000-4000-8000-000000000002', 'producer', 'active'),
  ('d5100000-0000-4000-8000-000000000001', 'd5000000-0000-4000-8000-000000000003', 'reviewer', 'active'),
  ('d5100000-0000-4000-8000-000000000002', 'd5000000-0000-4000-8000-000000000004', 'owner', 'active');
insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
)
values
(
  'd5200000-0000-4000-8000-000000000001',
  'd5100000-0000-4000-8000-000000000001',
  'LEARNING-1', 'Outcome Learning Product', 'active',
  'd5000000-0000-4000-8000-000000000001'
),
(
  'd5200000-0000-4000-8000-000000000002',
  'd5100000-0000-4000-8000-000000000001',
  'LEARNING-2', 'Second Outcome Learning Product', 'active',
  'd5000000-0000-4000-8000-000000000001'
);

create temporary table outcome_learning_context (
  category_id uuid,
  empty_category_id uuid,
  run_id uuid,
  draft_id uuid,
  scenario_artifact_id uuid,
  category_binding_id uuid,
  refresh_v1 jsonb,
  candidate_v1_id uuid,
  candidate_v1_hash text,
  candidate_v1_version integer,
  activate_v1 jsonb,
  memory_v1_id uuid,
  candidate_v2_id uuid,
  candidate_v2_hash text,
  activate_v2 jsonb,
  deactivate_v2 jsonb,
  revert_v1 jsonb,
  candidate_v3_id uuid,
  candidate_v3_hash text,
  candidate_v4_id uuid,
  candidate_v4_hash text,
  candidate_v5_id uuid,
  candidate_v5_hash text,
  freshness_refresh jsonb,
  candidate_v6_id uuid,
  candidate_v6_hash text,
  candidate_v6_version integer,
  activate_v6 jsonb,
  domain_counts jsonb
) on commit drop;
insert into outcome_learning_context default values;

set local session_replication_role = replica;

do $$
declare
  organization_id_value uuid := 'd5100000-0000-4000-8000-000000000001';
  actor_id_value uuid := 'd5000000-0000-4000-8000-000000000001';
  product_id_value uuid := 'd5200000-0000-4000-8000-000000000001';
  product_two_id_value uuid := 'd5200000-0000-4000-8000-000000000002';
  run_id_value uuid := 'd5300000-0000-4000-8000-000000000001';
  run_two_id_value uuid := 'd5300000-0000-4000-8000-000000000002';
  draft_id_value uuid := 'd5400000-0000-4000-8000-000000000001';
  draft_two_id_value uuid := 'd5400000-0000-4000-8000-000000000002';
  artifact_id_value uuid := 'd5500000-0000-4000-8000-000000000001';
  artifact_two_id_value uuid := 'd5500000-0000-4000-8000-000000000002';
  category_id_value uuid := 'd5600000-0000-4000-8000-000000000001';
  empty_category_id_value uuid := 'd5600000-0000-4000-8000-000000000002';
  binding_id_value uuid := 'd5700000-0000-4000-8000-000000000001';
  binding_two_id_value uuid := 'd5700000-0000-4000-8000-000000000002';
  batch_id_value uuid := 'd5800000-0000-4000-8000-000000000001';
  campaign_id_value uuid := 'd5900000-0000-4000-8000-000000000001';
  brief_value jsonb;
  input_dependencies_value jsonb;
  input_dependency_hash_value text;
  input_dependencies_two_value jsonb;
  input_dependency_hash_two_value text;
  position integer;
  job_id_value uuid;
  media_id_value uuid;
  review_id_value uuid;
  decision_id_value uuid;
  placement_id_value uuid;
  metric_id_value uuid;
  angle_value text;
  clicks_value bigint;
  orders_value bigint;
  media_hash_value text;
  completion_hash_value text;
  outcome_product_id uuid;
  outcome_draft_id uuid;
begin
  brief_value := jsonb_build_object(
    'summary', 'Bounded research fixture',
    'competitor_analysis', jsonb_build_object(
      'raw_copy', 'SECRET_COMPETITOR_COPY_MUST_NEVER_ENTER_MEMORY',
      'source_url', 'https://competitor.invalid/private-caption'
    ),
    'scenarios', jsonb_build_array(
      jsonb_build_object('title', 'Scenario one', 'hook', 'SECRET_RAW_PROMPT_ONE'),
      jsonb_build_object('title', 'Scenario two', 'hook', 'SECRET_RAW_PROMPT_TWO'),
      jsonb_build_object('title', 'Scenario three', 'hook', 'SECRET_RAW_PROMPT_THREE')
    )
  );
  input_dependencies_value := jsonb_build_object(
    'schema_version', 'research-stage-input-v2',
    'evidence', jsonb_build_array(jsonb_build_object(
      'source_id', 'd5a00000-0000-4000-8000-000000000001'::uuid,
      'content_hash', content_factory_private.json_hash(jsonb_build_object(
        'fixture_source_id', 'd5a00000-0000-4000-8000-000000000001'::uuid
      ))
    )),
    'upstream_artifacts', '[]'::jsonb
  );
  input_dependency_hash_value := content_factory_private.json_hash(
    input_dependencies_value - 'schema_version'
  );
  input_dependencies_two_value := jsonb_build_object(
    'schema_version', 'research-stage-input-v2',
    'evidence', jsonb_build_array(jsonb_build_object(
      'source_id', 'd5a00000-0000-4000-8000-000000000002'::uuid,
      'content_hash', content_factory_private.json_hash(jsonb_build_object(
        'fixture_source_id', 'd5a00000-0000-4000-8000-000000000002'::uuid
      ))
    )),
    'upstream_artifacts', '[]'::jsonb
  );
  input_dependency_hash_two_value := content_factory_private.json_hash(
    input_dependencies_two_value - 'schema_version'
  );

  insert into content_factory.product_research_runs (
    id, organization_id, product_id, created_by, status, input, summary,
    request_hash, completion_hash, idempotency_key, finished_at,
    created_at, updated_at
  ) values
  (
    run_id_value, organization_id_value, product_id_value, actor_id_value,
    'completed', jsonb_build_object('fixture', true), '{}'::jsonb,
    repeat('1', 64), repeat('2', 64), 'outcome-learning-run',
    now() - interval '10 days', now() - interval '11 days',
    now() - interval '10 days'
  ),
  (
    run_two_id_value, organization_id_value, product_two_id_value,
    actor_id_value, 'completed', jsonb_build_object('fixture', true),
    '{}'::jsonb, repeat('6', 64), repeat('7', 64),
    'outcome-learning-run-two', now() - interval '10 days',
    now() - interval '11 days', now() - interval '10 days'
  );
  insert into content_factory.creative_brief_drafts (
    id, organization_id, run_id, product_id, created_by, origin, version,
    status, title, brief, source_ids, task_blueprint, content_hash,
    approved_by, approved_at, created_at
  ) values
  (
    draft_id_value, organization_id_value, run_id_value, product_id_value,
    actor_id_value, 'human', 1, 'approved', 'Approved bounded research',
    brief_value,
    jsonb_build_array('d5a00000-0000-4000-8000-000000000001'),
    jsonb_build_array(jsonb_build_object('title', 'Create exact scenario')),
    content_factory_private.json_hash(brief_value), actor_id_value,
    now() - interval '10 days', now() - interval '11 days'
  ),
  (
    draft_two_id_value, organization_id_value, run_two_id_value,
    product_two_id_value, actor_id_value, 'human', 1, 'approved',
    'Second approved bounded research', brief_value,
    jsonb_build_array('d5a00000-0000-4000-8000-000000000002'),
    jsonb_build_array(jsonb_build_object('title', 'Create exact scenario')),
    content_factory_private.json_hash(
      brief_value || jsonb_build_object('product', 'two')
    ),
    actor_id_value, now() - interval '10 days', now() - interval '11 days'
  );
  insert into content_factory.research_stage_artifacts (
    id, organization_id, run_id, stage, version, payload, content_hash,
    input_dependencies, input_dependency_hash, actor_id, origin, created_at
  ) values
  (
    artifact_id_value, organization_id_value, run_id_value, 'scenarios', 1,
    brief_value -> 'scenarios',
    content_factory_private.json_hash(brief_value -> 'scenarios'),
    input_dependencies_value, input_dependency_hash_value,
    actor_id_value, 'human', now() - interval '10 days'
  ),
  (
    artifact_two_id_value, organization_id_value, run_two_id_value,
    'scenarios', 1, brief_value -> 'scenarios',
    content_factory_private.json_hash(
      (brief_value -> 'scenarios') || jsonb_build_array('product-two')
    ),
    input_dependencies_two_value, input_dependency_hash_two_value,
    actor_id_value, 'human', now() - interval '10 days'
  );
  insert into content_factory.research_stage_draft_bindings (
    organization_id, run_id, draft_id, stage, artifact_id,
    dependency_hash, actor_id, origin, bound_at
  ) values
  (
    organization_id_value, run_id_value, draft_id_value, 'scenarios',
    artifact_id_value, input_dependency_hash_value, actor_id_value, 'human',
    now() - interval '10 days'
  ),
  (
    organization_id_value, run_two_id_value, draft_two_id_value, 'scenarios',
    artifact_two_id_value, input_dependency_hash_two_value,
    actor_id_value, 'human',
    now() - interval '10 days'
  );
  insert into content_factory.research_stage_decisions (
    organization_id, run_id, draft_id, stage, artifact_id, decision,
    actor_id, origin, decision_hash, created_at
  ) values
  (
    organization_id_value, run_id_value, draft_id_value, 'scenarios',
    artifact_id_value, 'approved', actor_id_value, 'human', repeat('4', 64),
    now() - interval '10 days'
  ),
  (
    organization_id_value, run_two_id_value, draft_two_id_value, 'scenarios',
    artifact_two_id_value, 'approved', actor_id_value, 'human', repeat('9', 64),
    now() - interval '10 days'
  );
  insert into content_factory.research_market_categories (
    id, organization_id, canonical_name, normalized_name, definition,
    created_by, created_at
  ) values
  (
    category_id_value, organization_id_value, 'Fixture styling devices',
    content_factory_private.research_market_identity_key('Fixture styling devices'),
    'A bounded market category for exact first-party outcome learning.',
    actor_id_value, now() - interval '10 days'
  ),
  (
    empty_category_id_value, organization_id_value, 'Empty fixture category',
    content_factory_private.research_market_identity_key('Empty fixture category'),
    'A bounded category with deliberately absent eligible outcomes.',
    actor_id_value, now() - interval '10 days'
  );
  insert into content_factory.research_product_market_category_bindings (
    id, organization_id, product_id, category_id, binding_version,
    decision_action, source_run_id, source_draft_id, candidate_hash,
    reason, confirmed_by, confirmed_at, idempotency_key
  ) values
  (
    binding_id_value, organization_id_value, product_id_value,
    category_id_value, 1, 'bind_existing', run_id_value, draft_id_value,
    repeat('5', 64), 'Fixture category explicitly confirmed.', actor_id_value,
    now() - interval '9 days', 'outcome-learning-category-binding'
  ),
  (
    binding_two_id_value, organization_id_value, product_two_id_value,
    category_id_value, 1, 'bind_existing', run_two_id_value,
    draft_two_id_value, repeat('a', 64),
    'Second fixture product explicitly shares the exact category.',
    actor_id_value, now() - interval '9 days',
    'outcome-learning-category-binding-two'
  );

  for position in 1..6 loop
    job_id_value := extensions.gen_random_uuid();
    media_id_value := extensions.gen_random_uuid();
    review_id_value := extensions.gen_random_uuid();
    decision_id_value := extensions.gen_random_uuid();
    placement_id_value := extensions.gen_random_uuid();
    metric_id_value := extensions.gen_random_uuid();
    media_hash_value := content_factory_private.json_hash(
      jsonb_build_object('media', position)
    );
    completion_hash_value := content_factory_private.json_hash(
      jsonb_build_object('review', position)
    );
    if position <= 3 then
      angle_value := 'trust_builder';
      clicks_value := 150 - position * 10;
      orders_value := 30 - position * 3;
    else
      angle_value := 'comparison';
      clicks_value := (7 - position) * 5;
      orders_value := greatest(0, 6 - position);
    end if;
    if position in (2, 5, 6) then
      outcome_product_id := product_two_id_value;
      outcome_draft_id := draft_two_id_value;
    else
      outcome_product_id := product_id_value;
      outcome_draft_id := draft_id_value;
    end if;

    insert into content_factory.generation_jobs (
      id, organization_id, product_id, batch_id, ordinal, requested_by,
      assigned_to, mode, provider, allow_real_spend, campaign_id,
      estimated_cost_minor, actual_cost_minor, status, input, output,
      request_hash, idempotency_key, created_at, updated_at
    ) values (
      job_id_value, organization_id_value, outcome_product_id, batch_id_value,
      position, actor_id_value, actor_id_value, 'real', 'runway', true,
      campaign_id_value, 4, 4, 'succeeded',
      jsonb_build_object(
        'model', 'seedream5_lite', 'duration_seconds', 0, 'audio', false,
        'platform', 'tiktok', 'prompt_text', 'SECRET_RAW_PROMPT_JOB'
      ),
      jsonb_build_object('output_media_id', media_id_value),
      content_factory_private.json_hash(jsonb_build_object('job', position)),
      'outcome-learning-job-' || position, now() - interval '8 days',
      now() - interval '8 days'
    );
    insert into content_factory.generation_creative_signals (
      organization_id, generation_job_id, product_id, platform, model,
      creative_angle, hook_patterns, source, compiler_version,
      creative_brief_draft_id, scenario_position, prompt_hash, created_at
    ) values (
      organization_id_value, job_id_value, outcome_product_id, 'tiktok',
      'seedream5_lite', angle_value, jsonb_build_array('bounded_structure'),
      'approved_research', 'outcome-fixture-v1', outcome_draft_id,
      ((position - 1) % 3) + 1,
      content_factory_private.json_hash(jsonb_build_object('prompt', position)),
      now() - interval '8 days'
    );
    insert into content_factory.media_objects (
      id, organization_id, owner_id, product_id, object_name, mime_type,
      size_bytes, sha256, status, metadata, idempotency_key, created_at,
      updated_at
    ) values (
      media_id_value, organization_id_value, actor_id_value, outcome_product_id,
      organization_id_value::text || '/' || actor_id_value::text ||
        '/outcome-learning/' || media_id_value::text || '.png',
      'image/png', 1024, media_hash_value, 'ready',
      jsonb_build_object('kind', 'generated_image'),
      'outcome-learning-media-' || position, now() - interval '8 days',
      now() - interval '8 days'
    );
    insert into content_factory.content_review_runs (
      id, organization_id, media_object_id, requested_by, status,
      media_sha256_snapshot, input, result, moderation, ruleset_version,
      model_provider, model_version, request_hash, completion_hash,
      idempotency_key, finished_at, created_at, updated_at
    ) values (
      review_id_value, organization_id_value, media_id_value, actor_id_value,
      'completed', media_hash_value,
      jsonb_build_object('generation_job_id', job_id_value),
      jsonb_build_object(
        'overall_score', 98, 'blockers_count', 0,
        'compliance_status', 'pass'
      ),
      '{}'::jsonb, 'outcome-learning-review-v1', 'fixture', '1',
      content_factory_private.json_hash(jsonb_build_object('review_request', position)),
      completion_hash_value, 'outcome-learning-review-' || position,
      now() - interval '7 days 12 hours', now() - interval '8 days',
      now() - interval '7 days 12 hours'
    );
    insert into content_factory.content_review_decisions (
      id, organization_id, review_id, decided_by, decision, comment,
      resolved_recommendation_codes, risk_acknowledgements,
      media_watched_confirmed, review_completion_hash,
      media_sha256_snapshot, idempotency_key, created_at
    ) values (
      decision_id_value, organization_id_value, review_id_value,
      actor_id_value, 'approved', 'Independent fixture approval confirmed.',
      '[]'::jsonb, '[]'::jsonb, true, completion_hash_value,
      media_hash_value, 'outcome-learning-decision-' || position,
      now() - interval '7 days 6 hours'
    );
    insert into content_factory.placements (
      id, organization_id, product_id, generation_job_id, assigned_to,
      created_by, platform, destination_ref, status, published_at,
      request_hash, idempotency_key, metadata, created_at, updated_at
    ) values (
      placement_id_value, organization_id_value, outcome_product_id,
      job_id_value, actor_id_value, actor_id_value, 'tiktok',
      '@outcome_fixture', 'published', now() - interval '7 days',
      content_factory_private.json_hash(jsonb_build_object('placement', position)),
      'outcome-learning-placement-' || position,
      jsonb_build_object(
        'content_review_id', review_id_value,
        'content_review_decision_id', decision_id_value,
        'source_media_id', media_id_value,
        'media_sha256', media_hash_value
      ),
      now() - interval '7 days 6 hours', now() - interval '7 days'
    );
    insert into content_factory.metric_snapshots (
      id, organization_id, placement_id, collected_by, source, observed_at,
      views, clicks, orders, revenue_minor, raw, request_hash,
      idempotency_key, created_at
    ) values (
      metric_id_value, organization_id_value, placement_id_value,
      actor_id_value, 'official_api', now() - interval '3 days',
      1000, clicks_value, orders_value, orders_value * 1000,
      jsonb_build_object('raw_caption', 'SECRET_METRIC_RAW_FIELD'),
      content_factory_private.json_hash(jsonb_build_object('metric', position)),
      'outcome-learning-metric-' || position, now() - interval '3 days'
    );
  end loop;

  update outcome_learning_context
  set category_id = category_id_value,
      empty_category_id = empty_category_id_value,
      run_id = run_id_value,
      draft_id = draft_id_value,
      scenario_artifact_id = artifact_id_value,
      category_binding_id = binding_id_value,
      domain_counts = jsonb_build_object(
        'research_runs', (select count(*) from content_factory.product_research_runs),
        'generation_jobs', (select count(*) from content_factory.generation_jobs),
        'placements', (select count(*) from content_factory.placements),
        'metrics', (select count(*) from content_factory.metric_snapshots),
        'provider_authorizations', (
          select count(*) from content_factory.research_execution_authorizations
        )
      );
end;
$$;

set local session_replication_role = origin;

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub', 'd5000000-0000-4000-8000-000000000001', true
  );
end $$;

select is(
  public.creator_research_outcome_learning_status(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', (select empty_category_id from outcome_learning_context),
    'platform', 'tiktok', 'model', 'seedream5_lite'
  )) #>> '{guidance,status}',
  'no_eligible_outcomes',
  'status gracefully guides a category with no eligible outcomes'
);

update outcome_learning_context
set refresh_v1 = public.creator_refresh_research_outcome_learning(
  jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', category_id,
    'platform', 'tiktok',
    'model', 'seedream5_lite',
    'idempotency_key', 'outcome-learning-refresh-v1'
  )
);
update outcome_learning_context
set candidate_v1_id = (refresh_v1 #>> '{candidate,candidate_id}')::uuid,
    candidate_v1_hash = refresh_v1 #>> '{candidate,candidate_hash}',
    candidate_v1_version = (refresh_v1 #>> '{candidate,candidate_version}')::integer;

select is(
  (select jsonb_agg(key.value order by key.value)
   from outcome_learning_context context,
     lateral jsonb_object_keys(context.refresh_v1) key(value)),
  '["candidate","candidate_created","captured_outcome_count","eligible_outcome_count","guidance","ok","scope","version"]'::jsonb,
  'refresh response has the exact bounded top-level contract'
);
select is(
  (select refresh_v1 ->> 'captured_outcome_count' from outcome_learning_context),
  '6',
  'refresh captures all six exact mature first-party outcomes'
);
select is(
  (select refresh_v1 ->> 'candidate_created' from outcome_learning_context),
  'true',
  'six comparable outcomes create one bounded candidate'
);
select is(
  (select refresh_v1 #>>
    '{candidate,effectiveness_evidence,preferred,total_views}'
   from outcome_learning_context),
  '3000',
  'preferred effectiveness retains the exact three-outcome view denominator'
);
select is(
  (select refresh_v1 #>>
    '{candidate,effectiveness_evidence,preferred,product_count}'
   from outcome_learning_context),
  '2',
  'preferred effectiveness requires two independent products'
);
select is(
  (select refresh_v1 #>>
    '{candidate,effectiveness_evidence,comparator,product_count}'
   from outcome_learning_context),
  '2',
  'comparator effectiveness uses the same two-product control set'
);
select is(
  (select refresh_v1 #>>
    '{candidate,effectiveness_evidence,overlapping_product_count}'
   from outcome_learning_context),
  '2',
  'candidate evidence proves exact cross-angle product overlap'
);
select is(
  (select count(*)::integer
   from content_factory.research_outcome_lineage_snapshots),
  6,
  'one immutable lineage row is stored per exact placement metric'
);
select is(
  (select count(*)::integer
   from content_factory.research_outcome_learning_candidate_evidence),
  6,
  'candidate is linked to the exact six lineage snapshots'
);
select is(
  (select count(*)::integer
   from content_factory.research_outcome_learning_memory_versions),
  0,
  'candidate creation never activates memory automatically'
);
select ok(
  not exists (
    select 1
    from content_factory.research_outcome_lineage_snapshots lineage
    join content_factory.research_product_market_category_bindings category_binding
      on category_binding.organization_id = lineage.organization_id
     and category_binding.product_id = lineage.product_id
     and category_binding.id = lineage.category_binding_id
     and category_binding.category_id = lineage.market_category_id
    join content_factory.creative_brief_drafts draft
      on draft.organization_id = lineage.organization_id
     and draft.run_id = lineage.research_run_id
     and draft.id = lineage.creative_brief_draft_id
    join content_factory.research_stage_draft_bindings scenario_binding
      on scenario_binding.organization_id = lineage.organization_id
     and scenario_binding.run_id = lineage.research_run_id
     and scenario_binding.draft_id = lineage.creative_brief_draft_id
     and scenario_binding.stage = 'scenarios'
     and scenario_binding.artifact_id = lineage.scenario_artifact_id
    join content_factory.generation_creative_signals signal
      on signal.organization_id = lineage.organization_id
     and signal.id = lineage.creative_signal_id
     and signal.generation_job_id = lineage.generation_job_id
    join content_factory.content_review_decisions decision
      on decision.organization_id = lineage.organization_id
     and decision.review_id = lineage.review_id
     and decision.id = lineage.review_decision_id
    join content_factory.metric_snapshots metric
      on metric.organization_id = lineage.organization_id
     and metric.placement_id = lineage.placement_id
     and metric.id = lineage.metric_snapshot_id
    where draft.status <> 'approved'
       or signal.source <> 'approved_research'
       or decision.decision <> 'approved'
       or not decision.media_watched_confirmed
       or metric.source not in ('manual', 'csv', 'official_api')
       or lineage.metric_observed_at <
            lineage.placement_published_at + interval '72 hours'
  ),
  'every captured row resolves exact approved research, scenario, generation, QA, placement, and mature metric lineage'
);
select ok(
  not ((
    select coalesce(jsonb_agg(jsonb_build_object(
      'structural', lineage.structural_payload,
      'effectiveness', lineage.effectiveness_evidence,
      'guards', lineage.guard_evidence
    )), '[]'::jsonb)::text
    from content_factory.research_outcome_lineage_snapshots lineage
  ) ~* 'secret_competitor|secret_raw_prompt|secret_metric|competitor[.]invalid')
  and not ((
    select jsonb_build_object(
      'payload', candidate.candidate_payload,
      'effectiveness', candidate.effectiveness_evidence,
      'guards', candidate.guard_evidence
    )::text
    from content_factory.research_outcome_learning_candidates candidate
    where candidate.id = (select candidate_v1_id from outcome_learning_context)
  ) ~* 'secret_competitor|secret_raw_prompt|secret_metric|competitor[.]invalid'),
  'raw competitor prose, prompts, captions, URLs, and metric raw fields never enter reusable memory'
);
select is(
  (select refresh_v1 #>> '{candidate,guard_evidence,generation_consumption}'
   from outcome_learning_context),
  'not_wired',
  'candidate honestly states that paid generation does not consume it yet'
);
select is(
  (select refresh_v1 #>> '{candidate,guard_evidence,automatic_activation}'
   from outcome_learning_context),
  'false',
  'candidate guard explicitly forbids automatic activation'
);

select is(
  public.creator_refresh_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', (select category_id from outcome_learning_context),
    'platform', 'tiktok', 'model', 'seedream5_lite',
    'idempotency_key', 'outcome-learning-refresh-v1'
  )),
  (select refresh_v1 from outcome_learning_context),
  'refresh idempotency replay returns the stored response'
);
select is(
  (select count(*)::integer
   from content_factory.research_outcome_learning_candidates),
  1,
  'refresh replay cannot append another candidate'
);
select throws_ok(
  $$select public.creator_refresh_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', (select category_id from outcome_learning_context),
    'platform', 'youtube', 'model', 'seedream5_lite',
    'idempotency_key', 'outcome-learning-refresh-v1'
  ))$$,
  '23505', 'idempotency_key_conflict',
  'refresh rejects conflicting reuse of an idempotency key'
);
select is(
  (select jsonb_build_object(
    'research_runs', (select count(*) from content_factory.product_research_runs),
    'generation_jobs', (select count(*) from content_factory.generation_jobs),
    'placements', (select count(*) from content_factory.placements),
    'metrics', (select count(*) from content_factory.metric_snapshots),
    'provider_authorizations', (
      select count(*) from content_factory.research_execution_authorizations
    )
  )),
  (select domain_counts from outcome_learning_context),
  'refresh creates no research, provider, generation, placement, publication, or metric side effect'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'd5000000-0000-4000-8000-000000000003', true
  );
end $$;
select is(
  public.creator_research_outcome_learning_status(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', (select category_id from outcome_learning_context),
    'platform', 'tiktok', 'model', 'seedream5_lite'
  )) ->> 'can_decide',
  'false',
  'reviewer receives read-only status capability'
);
select throws_ok(
  $$select public.creator_refresh_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', (select category_id from outcome_learning_context),
    'platform', 'tiktok', 'model', 'seedream5_lite',
    'idempotency_key', 'reviewer-refresh-denied'
  ))$$,
  '42501', 'role_not_allowed',
  'reviewer cannot write lineage or candidates'
);
select throws_ok(
  $$select public.creator_decide_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', (select candidate_v1_id from outcome_learning_context),
    'action', 'activate',
    'candidate_version', (select candidate_v1_version from outcome_learning_context),
    'candidate_hash', (select candidate_v1_hash from outcome_learning_context),
    'expected_scope_version', 0,
    'reason', 'Reviewer cannot activate advisory memory.',
    'confirmation', true,
    'idempotency_key', 'reviewer-decision-denied'
  ))$$,
  '42501', 'role_not_allowed',
  'reviewer cannot write candidate decisions'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'd5000000-0000-4000-8000-000000000004', true
  );
end $$;
select throws_ok(
  $$select public.creator_research_outcome_learning_status(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000002',
    'market_category_id', (select category_id from outcome_learning_context),
    'platform', 'tiktok', 'model', 'seedream5_lite'
  ))$$,
  '22023', 'research_market_category_not_found',
  'another tenant cannot read this tenant category or learning status'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'd5000000-0000-4000-8000-000000000001', true
  );
end $$;
select throws_ok(
  $$select public.creator_decide_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', (select candidate_v1_id from outcome_learning_context),
    'action', 'activate',
    'candidate_version', (select candidate_v1_version from outcome_learning_context),
    'candidate_hash', (select candidate_v1_hash from outcome_learning_context),
    'expected_scope_version', 0,
    'reason', 'Explicit confirmation is mandatory.',
    'confirmation', false,
    'idempotency_key', 'candidate-no-confirmation'
  ))$$,
  '22023', 'research_outcome_decision_confirmation_required',
  'every decision requires explicit true confirmation'
);
select throws_ok(
  $$select public.creator_decide_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', (select candidate_v1_id from outcome_learning_context),
    'action', 'activate',
    'candidate_hash', (select candidate_v1_hash from outcome_learning_context),
    'expected_scope_version', 0,
    'reason', 'Missing candidate version must fail closed.',
    'confirmation', true,
    'idempotency_key', 'candidate-missing-version'
  ))$$,
  '22023', 'research_outcome_decision_version_invalid',
  'decision rejects a missing candidate version before ledger writes'
);
select throws_ok(
  $$select public.creator_decide_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', (select candidate_v1_id from outcome_learning_context),
    'action', 'activate',
    'candidate_version', (select candidate_v1_version from outcome_learning_context),
    'candidate_hash', repeat('0', 64),
    'expected_scope_version', 0,
    'reason', 'A stale candidate hash must fail.',
    'confirmation', true,
    'idempotency_key', 'candidate-stale-hash'
  ))$$,
  '55000', 'research_outcome_candidate_stale',
  'decision rejects a stale candidate hash'
);
select throws_ok(
  $$select public.creator_decide_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', (select candidate_v1_id from outcome_learning_context),
    'action', 'activate',
    'candidate_version', (select candidate_v1_version from outcome_learning_context),
    'candidate_hash', (select candidate_v1_hash from outcome_learning_context),
    'expected_scope_version', 1,
    'reason', 'A stale scope version must fail.',
    'confirmation', true,
    'idempotency_key', 'candidate-stale-scope'
  ))$$,
  '55000', 'research_outcome_scope_version_stale',
  'decision rejects a stale active-memory scope version'
);

update outcome_learning_context
set activate_v1 = public.creator_decide_research_outcome_learning(
  jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', candidate_v1_id,
    'action', 'activate',
    'candidate_version', candidate_v1_version,
    'candidate_hash', candidate_v1_hash,
    'expected_scope_version', 0,
    'reason', 'Owner explicitly activates advisory candidate one.',
    'confirmation', true,
    'idempotency_key', 'activate-candidate-v1'
  )
);
update outcome_learning_context
set memory_v1_id = (activate_v1 #>> '{memory,memory_version_id}')::uuid;
select is(
  (select jsonb_agg(key.value order by key.value)
   from outcome_learning_context context,
     lateral jsonb_object_keys(context.activate_v1) key(value)),
  '["action","decision","guidance","memory","ok","version"]'::jsonb,
  'decision response has the exact versioned top-level contract'
);
select is(
  (select activate_v1 #>> '{memory,memory_version}' from outcome_learning_context),
  '1',
  'explicit activate appends memory version one'
);
select is(
  (select activate_v1 #>> '{memory,generation_consumption}' from outcome_learning_context),
  'not_wired',
  'activated memory remains advisory and is not wired to paid generation'
);
select is(
  (select activate_v1 #>> '{guidance,recommended_next_step}'
   from outcome_learning_context),
  'monitor_effectiveness_and_keep_rollback_ready',
  'activation guidance recommends monitoring with rollback readiness'
);
select is(
  public.creator_decide_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', (select candidate_v1_id from outcome_learning_context),
    'action', 'activate',
    'candidate_version', (select candidate_v1_version from outcome_learning_context),
    'candidate_hash', (select candidate_v1_hash from outcome_learning_context),
    'expected_scope_version', 0,
    'reason', 'Owner explicitly activates advisory candidate one.',
    'confirmation', true,
    'idempotency_key', 'activate-candidate-v1'
  )),
  (select activate_v1 from outcome_learning_context),
  'decision idempotency replay returns the stored response'
);
select throws_ok(
  $$select public.creator_decide_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', (select candidate_v1_id from outcome_learning_context),
    'action', 'activate',
    'candidate_version', (select candidate_v1_version from outcome_learning_context),
    'candidate_hash', (select candidate_v1_hash from outcome_learning_context),
    'expected_scope_version', 0,
    'reason', 'Conflicting reason for the same decision key.',
    'confirmation', true,
    'idempotency_key', 'activate-candidate-v1'
  ))$$,
  '23505', 'idempotency_key_conflict',
  'decision rejects conflicting idempotency-key reuse'
);

create or replace function pg_temp.append_fixture_candidate(
  version_value integer,
  preferred_angle_value text
)
returns uuid
language plpgsql
set search_path = ''
as $$
declare
  candidate_id_value uuid := extensions.gen_random_uuid();
  base_row content_factory.research_outcome_learning_candidates%rowtype;
  candidate_payload_value jsonb;
  candidate_hash_value text;
begin
  select candidate.* into base_row
  from content_factory.research_outcome_learning_candidates candidate
  where candidate.id = (
    select candidate_v1_id from pg_temp.outcome_learning_context
  );
  candidate_payload_value := jsonb_set(
    base_row.candidate_payload,
    '{preferred_creative_angle}', to_jsonb(preferred_angle_value), false
  );
  candidate_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'candidate_payload', candidate_payload_value,
      'effectiveness_evidence', base_row.effectiveness_evidence,
      'guard_evidence', base_row.guard_evidence,
      'evidence_hash', base_row.evidence_hash
    )
  );
  insert into content_factory.research_outcome_learning_candidates (
    id, organization_id, market_category_id, platform, model,
    candidate_kind, candidate_version, candidate_payload,
    effectiveness_evidence, guard_evidence, evidence_hash,
    candidate_hash, created_by
  ) values (
    candidate_id_value, base_row.organization_id, base_row.market_category_id,
    base_row.platform, base_row.model, base_row.candidate_kind, version_value,
    candidate_payload_value,
    base_row.effectiveness_evidence,
    base_row.guard_evidence,
    base_row.evidence_hash,
    candidate_hash_value,
    base_row.created_by
  );
  insert into content_factory.research_outcome_learning_candidate_evidence (
    organization_id, candidate_id, lineage_snapshot_id, ordinal
  )
  select evidence.organization_id, candidate_id_value,
         evidence.lineage_snapshot_id, evidence.ordinal
  from content_factory.research_outcome_learning_candidate_evidence evidence
  where evidence.organization_id = base_row.organization_id
    and evidence.candidate_id = base_row.id;
  return candidate_id_value;
end;
$$;

set local session_replication_role = replica;
update outcome_learning_context
set candidate_v2_id = pg_temp.append_fixture_candidate(2, 'demonstration');
update outcome_learning_context context
set candidate_v2_hash = candidate.candidate_hash
from content_factory.research_outcome_learning_candidates candidate
where candidate.id = context.candidate_v2_id;
set local session_replication_role = origin;

update outcome_learning_context
set activate_v2 = public.creator_decide_research_outcome_learning(
  jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', candidate_v2_id,
    'action', 'activate', 'candidate_version', 2,
    'candidate_hash', candidate_v2_hash, 'expected_scope_version', 1,
    'reason', 'Owner explicitly activates advisory candidate two.',
    'confirmation', true, 'idempotency_key', 'activate-candidate-v2'
  )
);
update outcome_learning_context
set deactivate_v2 = public.creator_decide_research_outcome_learning(
  jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', candidate_v2_id,
    'action', 'deactivate', 'candidate_version', 2,
    'candidate_hash', candidate_v2_hash, 'expected_scope_version', 2,
    'reason', 'Owner deactivates candidate two after guard review.',
    'confirmation', true, 'idempotency_key', 'deactivate-candidate-v2'
  )
);
select is(
  (select deactivate_v2 #>> '{memory,state}' from outcome_learning_context),
  'inactive',
  'explicit deactivate appends an inactive memory version'
);
select is(
  (select deactivate_v2 #>> '{memory,memory_version}' from outcome_learning_context),
  '3',
  'deactivation preserves the prior active versions and advances scope version'
);
select is(
  (select deactivate_v2 #>> '{guidance,recommended_next_step}'
   from outcome_learning_context),
  'review_rollback_target_or_wait_for_new_candidate',
  'deactivation guidance recommends the bounded rollback-or-wait path'
);

update outcome_learning_context
set revert_v1 = public.creator_decide_research_outcome_learning(
  jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', candidate_v1_id,
    'action', 'revert', 'candidate_version', candidate_v1_version,
    'candidate_hash', candidate_v1_hash, 'expected_scope_version', 3,
    'rollback_memory_version_id', memory_v1_id,
    'reason', 'Owner restores the exact prior advisory memory version.',
    'confirmation', true, 'idempotency_key', 'revert-to-candidate-v1'
  )
);
select is(
  (select revert_v1 #>> '{memory,memory_version}' from outcome_learning_context),
  '4',
  'explicit revert appends version four without mutating prior history'
);
select is(
  (select revert_v1 #>> '{memory,candidate_id}' from outcome_learning_context),
  (select candidate_v1_id::text from outcome_learning_context),
  'revert restores the exact prior candidate'
);
select is(
  (select revert_v1 #>> '{guidance,recommended_next_step}'
   from outcome_learning_context),
  'monitor_restored_memory_and_keep_rollback_ready',
  'revert guidance recommends monitoring the restored memory'
);

set local session_replication_role = replica;
update outcome_learning_context
set candidate_v3_id = pg_temp.append_fixture_candidate(3, 'objection_handling');
update outcome_learning_context context
set candidate_v3_hash = candidate.candidate_hash
from content_factory.research_outcome_learning_candidates candidate
where candidate.id = context.candidate_v3_id;
set local session_replication_role = origin;

select is(
  (select jsonb_build_array(
     decision.value #>> '{guidance,status}',
     decision.value #>> '{guidance,recommended_next_step}'
   )
   from (select public.creator_decide_research_outcome_learning(
     jsonb_build_object(
       'organization_id', 'd5100000-0000-4000-8000-000000000001',
       'candidate_id', (select candidate_v3_id from outcome_learning_context),
       'action', 'quarantine', 'candidate_version', 3,
       'candidate_hash', (select candidate_v3_hash from outcome_learning_context),
       'expected_scope_version', 4,
       'reason', 'Candidate three needs additional guard evidence.',
       'confirmation', true, 'idempotency_key', 'quarantine-candidate-v3'
     )
   ) as value) decision),
  '["candidate_quarantined","collect_additional_evidence_before_reconsideration"]'::jsonb,
  'quarantine records its terminal state and bounded evidence-gathering path'
);

set local session_replication_role = replica;
update outcome_learning_context
set candidate_v4_id = pg_temp.append_fixture_candidate(4, 'product_focus');
update outcome_learning_context context
set candidate_v4_hash = candidate.candidate_hash
from content_factory.research_outcome_learning_candidates candidate
where candidate.id = context.candidate_v4_id;
set local session_replication_role = origin;

select is(
  (select jsonb_build_array(
     decision.value #>> '{guidance,status}',
     decision.value #>> '{guidance,recommended_next_step}'
   )
   from (select public.creator_decide_research_outcome_learning(
     jsonb_build_object(
       'organization_id', 'd5100000-0000-4000-8000-000000000001',
       'candidate_id', (select candidate_v4_id from outcome_learning_context),
       'action', 'reject', 'candidate_version', 4,
       'candidate_hash', (select candidate_v4_hash from outcome_learning_context),
       'expected_scope_version', 4,
       'reason', 'Candidate four is explicitly rejected.',
       'confirmation', true, 'idempotency_key', 'reject-candidate-v4'
     )
   ) as value) decision),
  '["candidate_rejected","review_next_pending_candidate"]'::jsonb,
  'reject records its terminal state and bounded next-candidate path'
);
select is(
  (select count(*)::integer
   from content_factory.research_outcome_learning_memory_versions),
  4,
  'reject and quarantine do not change active-memory history'
);

select is(
  public.creator_research_outcome_learning_status(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', (select category_id from outcome_learning_context),
    'platform', 'tiktok', 'model', 'seedream5_lite'
  )) #>> '{current_memory,candidate_id}',
  (select candidate_v1_id::text from outcome_learning_context),
  'status reports the exact restored active advisory memory'
);
select is(
  public.creator_research_outcome_learning_status(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', (select category_id from outcome_learning_context),
    'platform', 'tiktok', 'model', 'seedream5_lite'
  )) #>> '{rollback_target,candidate_id}',
  (select candidate_v2_id::text from outcome_learning_context),
  'status proactively exposes the prior active version as rollback target'
);
select is(
  public.creator_research_outcome_learning_status(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', (select category_id from outcome_learning_context),
    'platform', 'tiktok', 'model', 'seedream5_lite'
  )) #>> '{guidance,generation_consumption}',
  'not_wired',
  'status never implies that advisory memory controls paid generation'
);
select is(
  (select jsonb_agg(candidate.value ->> 'status' order by candidate.value ->> 'status')
   from jsonb_array_elements(
     public.creator_research_outcome_learning_status(jsonb_build_object(
       'organization_id', 'd5100000-0000-4000-8000-000000000001',
       'market_category_id', (select category_id from outcome_learning_context),
       'platform', 'tiktok', 'model', 'seedream5_lite'
     )) -> 'candidates'
   ) candidate(value)),
  '["active","deactivated","quarantined","rejected"]'::jsonb,
  'status derives active, deactivated, quarantined, and rejected candidate states from append-only history'
);
select is(
  (select jsonb_agg(key.value order by key.value)
   from jsonb_object_keys(
     public.creator_research_outcome_learning_status(jsonb_build_object(
       'organization_id', 'd5100000-0000-4000-8000-000000000001',
       'market_category_id', (select category_id from outcome_learning_context),
       'platform', 'tiktok', 'model', 'seedream5_lite'
     ))
   ) key(value)),
  '["can_decide","can_refresh","candidates","captured_current_outcome_count","current_memory","decision_history","guidance","market_category","ok","rollback_target","scope","version"]'::jsonb,
  'status response has the exact versioned read-only top-level contract'
);

-- A pending candidate is now followed by source changes that have not yet
-- been captured.  Invalid and non-latest rows must be ignored, while the
-- newer exact mature correction must force a refresh before activation.
set local session_replication_role = replica;
update outcome_learning_context
set candidate_v5_id = pg_temp.append_fixture_candidate(5, 'curiosity_gap');
update outcome_learning_context context
set candidate_v5_hash = candidate.candidate_hash
from content_factory.research_outcome_learning_candidates candidate
where candidate.id = context.candidate_v5_id;
set local session_replication_role = origin;

insert into content_factory.metric_snapshots (
  organization_id, placement_id, collected_by, source, observed_at,
  views, clicks, orders, revenue_minor, raw, request_hash,
  idempotency_key, created_at
)
select
  placement.organization_id,
  placement.id,
  'd5000000-0000-4000-8000-000000000001',
  'official_api',
  now() - interval '2 days',
  50,
  60,
  0,
  0,
  jsonb_build_object('fixture', 'invalid-newer-row'),
  content_factory_private.json_hash(jsonb_build_object(
    'metric', 'invalid-newer-row'
  )),
  'outcome-learning-invalid-newer-metric',
  now() - interval '2 days'
from content_factory.placements placement
where placement.organization_id = 'd5100000-0000-4000-8000-000000000001'
  and placement.idempotency_key = 'outcome-learning-placement-1';

insert into content_factory.metric_snapshots (
  organization_id, placement_id, collected_by, source, observed_at,
  views, clicks, orders, revenue_minor, raw, request_hash,
  idempotency_key, created_at
)
select
  placement.organization_id,
  placement.id,
  'd5000000-0000-4000-8000-000000000001',
  'official_api',
  now() - interval '4 days',
  1000,
  125,
  24,
  24000,
  jsonb_build_object('fixture', 'valid-but-non-latest-backfill'),
  content_factory_private.json_hash(jsonb_build_object(
    'metric', 'valid-but-non-latest-backfill'
  )),
  'outcome-learning-non-latest-backfill',
  now() - interval '1 day'
from content_factory.placements placement
where placement.organization_id = 'd5100000-0000-4000-8000-000000000001'
  and placement.idempotency_key = 'outcome-learning-placement-1';

select is(
  (select eligible.metric_snapshot_id::text
   from content_factory_private.research_current_eligible_outcomes(
     'd5100000-0000-4000-8000-000000000001',
     (select category_id from outcome_learning_context),
     'tiktok', 'seedream5_lite'
   ) eligible
   join content_factory.placements placement
     on placement.organization_id = eligible.organization_id
    and placement.id = eligible.placement_id
   where placement.idempotency_key = 'outcome-learning-placement-1'),
  (select metric.id::text
   from content_factory.metric_snapshots metric
   where metric.organization_id = 'd5100000-0000-4000-8000-000000000001'
     and metric.idempotency_key = 'outcome-learning-metric-1'),
  'invalid newer and valid non-latest metric rows do not displace the exact current metric'
);

insert into content_factory.metric_snapshots (
  organization_id, placement_id, collected_by, source, observed_at,
  views, clicks, orders, revenue_minor, is_correction, correction_reason,
  raw, request_hash, idempotency_key, created_at
)
select
  placement.organization_id,
  placement.id,
  'd5000000-0000-4000-8000-000000000001',
  'official_api',
  now() - interval '1 day',
  1000,
  160,
  31,
  31000,
  true,
  'Exact mature first-party correction.',
  jsonb_build_object('fixture', 'new-valid-correction'),
  content_factory_private.json_hash(jsonb_build_object(
    'metric', 'new-valid-correction'
  )),
  'outcome-learning-new-valid-correction',
  now() - interval '1 day'
from content_factory.placements placement
where placement.organization_id = 'd5100000-0000-4000-8000-000000000001'
  and placement.idempotency_key = 'outcome-learning-placement-1';

select is(
  (select eligible.metric_snapshot_id::text
   from content_factory_private.research_current_eligible_outcomes(
     'd5100000-0000-4000-8000-000000000001',
     (select category_id from outcome_learning_context),
     'tiktok', 'seedream5_lite'
   ) eligible
   join content_factory.placements placement
     on placement.organization_id = eligible.organization_id
    and placement.id = eligible.placement_id
   where placement.idempotency_key = 'outcome-learning-placement-1'),
  (select metric.id::text
   from content_factory.metric_snapshots metric
   where metric.organization_id = 'd5100000-0000-4000-8000-000000000001'
     and metric.idempotency_key = 'outcome-learning-new-valid-correction'),
  'newer valid mature correction becomes the exact current source row'
);

create temporary table freshness_domain_counts as
select jsonb_build_object(
  'research_runs', (select count(*) from content_factory.product_research_runs),
  'generation_jobs', (select count(*) from content_factory.generation_jobs),
  'placements', (select count(*) from content_factory.placements),
  'metrics', (select count(*) from content_factory.metric_snapshots),
  'provider_authorizations', (
    select count(*) from content_factory.research_execution_authorizations
  )
) as counts;

select throws_ok(
  $$select public.creator_decide_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', (select candidate_v5_id from outcome_learning_context),
    'action', 'activate', 'candidate_version', 5,
    'candidate_hash', (select candidate_v5_hash from outcome_learning_context),
    'expected_scope_version', 4,
    'reason', 'Live source changed after this candidate was built.',
    'confirmation', true,
    'idempotency_key', 'activate-v5-before-required-refresh'
  ))$$,
  '55000', 'research_outcome_refresh_required',
  'activation fails closed when a newer exact eligible metric lacks captured lineage'
);

update outcome_learning_context
set freshness_refresh = public.creator_refresh_research_outcome_learning(
  jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', category_id,
    'platform', 'tiktok', 'model', 'seedream5_lite',
    'idempotency_key', 'outcome-learning-refresh-after-correction'
  )
);
update outcome_learning_context
set candidate_v6_id = (freshness_refresh #>> '{candidate,candidate_id}')::uuid,
    candidate_v6_hash = freshness_refresh #>> '{candidate,candidate_hash}',
    candidate_v6_version =
      (freshness_refresh #>> '{candidate,candidate_version}')::integer;

select is(
  (select freshness_refresh ->> 'captured_outcome_count'
   from outcome_learning_context),
  '1',
  'required refresh captures exactly the newly selected correction lineage'
);
select is(
  (select candidate_v6_version from outcome_learning_context),
  6,
  'required refresh appends the next exact candidate version'
);
select throws_ok(
  $$select public.creator_decide_research_outcome_learning(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', (select candidate_v5_id from outcome_learning_context),
    'action', 'activate', 'candidate_version', 5,
    'candidate_hash', (select candidate_v5_hash from outcome_learning_context),
    'expected_scope_version', 4,
    'reason', 'The original candidate is superseded after exact refresh.',
    'confirmation', true,
    'idempotency_key', 'activate-v5-after-required-refresh'
  ))$$,
  '55000', 'research_outcome_candidate_superseded',
  'the pre-refresh candidate cannot activate after a fresher version exists'
);

update outcome_learning_context
set activate_v6 = public.creator_decide_research_outcome_learning(
  jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'candidate_id', candidate_v6_id,
    'action', 'activate', 'candidate_version', candidate_v6_version,
    'candidate_hash', candidate_v6_hash, 'expected_scope_version', 4,
    'reason', 'Owner activates only the candidate built after exact refresh.',
    'confirmation', true, 'idempotency_key', 'activate-candidate-v6'
  )
);
select is(
  (select activate_v6 #>> '{memory,memory_version}'
   from outcome_learning_context),
  '5',
  'the refreshed current candidate activates after both freshness guards pass'
);
select is(
  public.creator_research_outcome_learning_status(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', (select category_id from outcome_learning_context),
    'platform', 'tiktok', 'model', 'seedream5_lite'
  )) #>> '{current_memory,candidate_id}',
  (select candidate_v6_id::text from outcome_learning_context),
  'status exposes the refreshed candidate as current advisory memory'
);
select is(
  (select jsonb_build_object(
    'research_runs', (select count(*) from content_factory.product_research_runs),
    'generation_jobs', (select count(*) from content_factory.generation_jobs),
    'placements', (select count(*) from content_factory.placements),
    'metrics', (select count(*) from content_factory.metric_snapshots),
    'provider_authorizations', (
      select count(*) from content_factory.research_execution_authorizations
    )
  )),
  (select counts from freshness_domain_counts),
  'freshness failure, refresh, and activation write no provider, generation, placement, publication, or metric rows'
);

create temporary table outcome_status_read_counts as
select jsonb_build_object(
  'lineage', (select count(*) from content_factory.research_outcome_lineage_snapshots),
  'candidates', (select count(*) from content_factory.research_outcome_learning_candidates),
  'evidence', (select count(*) from content_factory.research_outcome_learning_candidate_evidence),
  'decisions', (select count(*) from content_factory.research_outcome_learning_decisions),
  'memory', (select count(*) from content_factory.research_outcome_learning_memory_versions),
  'research_runs', (select count(*) from content_factory.product_research_runs),
  'generation_jobs', (select count(*) from content_factory.generation_jobs),
  'placements', (select count(*) from content_factory.placements),
  'metrics', (select count(*) from content_factory.metric_snapshots),
  'provider_authorizations', (
    select count(*) from content_factory.research_execution_authorizations
  )
) as counts;
select lives_ok(
  $$select public.creator_research_outcome_learning_status(jsonb_build_object(
    'organization_id', 'd5100000-0000-4000-8000-000000000001',
    'market_category_id', (select category_id from outcome_learning_context),
    'platform', 'tiktok', 'model', 'seedream5_lite'
  ))$$,
  'status remains a read-only advisory operation'
);
select is(
  (select jsonb_build_object(
    'lineage', (select count(*) from content_factory.research_outcome_lineage_snapshots),
    'candidates', (select count(*) from content_factory.research_outcome_learning_candidates),
    'evidence', (select count(*) from content_factory.research_outcome_learning_candidate_evidence),
    'decisions', (select count(*) from content_factory.research_outcome_learning_decisions),
    'memory', (select count(*) from content_factory.research_outcome_learning_memory_versions),
    'research_runs', (select count(*) from content_factory.product_research_runs),
    'generation_jobs', (select count(*) from content_factory.generation_jobs),
    'placements', (select count(*) from content_factory.placements),
    'metrics', (select count(*) from content_factory.metric_snapshots),
    'provider_authorizations', (
      select count(*) from content_factory.research_execution_authorizations
    )
  )),
  (select counts from outcome_status_read_counts),
  'status performs no ledger, provider, spend, generation, publication, or metric write'
);

select throws_ok(
  $$update content_factory.research_outcome_lineage_snapshots
    set views = views where true$$,
  '55000', 'research_outcome_lineage_snapshots_append_only',
  'lineage snapshots reject every update'
);
select throws_ok(
  $$delete from content_factory.research_outcome_learning_candidates where true$$,
  '55000', 'research_outcome_learning_candidates_append_only',
  'candidates reject deletion'
);
select throws_ok(
  $$update content_factory.research_outcome_learning_candidate_evidence
    set ordinal = ordinal where true$$,
  '55000', 'research_outcome_learning_candidate_evidence_append_only',
  'candidate evidence rejects every update'
);
select throws_ok(
  $$delete from content_factory.research_outcome_learning_decisions where true$$,
  '55000', 'research_outcome_learning_decisions_append_only',
  'decisions reject deletion'
);
select throws_ok(
  $$update content_factory.research_outcome_learning_memory_versions
    set state = state where true$$,
  '55000', 'research_outcome_learning_memory_versions_append_only',
  'memory versions reject every update'
);

select * from finish();
rollback;
