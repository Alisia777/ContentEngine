begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select has_table(
  'content_factory', 'research_outcome_generation_selections',
  'explicit per-auto-brief selection ledger exists'
);
select has_table(
  'content_factory', 'research_outcome_generation_assignments',
  'future paid binding provenance ledger exists'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_outcome_generation_selections'::regclass),
     ('content_factory.research_outcome_generation_assignments'::regclass)
   ) protected(table_oid)
   join pg_class relation on relation.oid = protected.table_oid
   where relation.relrowsecurity),
  2,
  'both generation-consumption ledgers have RLS enabled'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_outcome_generation_selections'::regclass),
     ('content_factory.research_outcome_generation_assignments'::regclass)
   ) protected(table_oid)
   cross join (values ('select'), ('insert'), ('update'), ('delete')) privilege(name)
   where has_table_privilege('authenticated', table_oid, privilege.name)
      or has_table_privilege('service_role', table_oid, privilege.name)),
  0,
  'authenticated and service roles have no direct ledger privileges'
);

select has_function(
  'public', 'creator_research_outcome_generation_advisory', array['jsonb'],
  'read-only explicit-consumption advisory RPC exists'
);
select has_function(
  'public', 'creator_prepare_research_outcome_generation_selection',
  array['jsonb'],
  'explicit apply/control preparation RPC exists'
);
select has_function(
  'content_factory_private', 'research_outcome_generation_advisory',
  array['uuid', 'uuid', 'text', 'text', 'text'],
  'typed fail-closed resolver exists'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_research_outcome_generation_advisory(jsonb)', 'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.creator_prepare_research_outcome_generation_selection(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.research_outcome_generation_advisory(uuid,uuid,text,text,text)',
    'execute'
  ),
  'authenticated callers reach only the two public RPC seams'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_generation_learning_policy(jsonb)'::regprocedure
  )), 'research_outcome') = 0,
  'the existing generation policy is not wrapped by this gated foundation'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_prepare_research_outcome_generation_selection(jsonb)'::regprocedure
  )), 'insert into content_factory.generation_jobs') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_prepare_research_outcome_generation_selection(jsonb)'::regprocedure
  )), 'insert into content_factory.research_outcome_generation_assignments') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_prepare_research_outcome_generation_selection(jsonb)'::regprocedure
  )), 'creator_start_real_generation') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_prepare_research_outcome_generation_selection(jsonb)'::regprocedure
  )), 'creator_start_real_photo_generation') = 0,
  'selection preparation has no generation, assignment, provider, or paid-start write path'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.research_outcome_generation_advisory(uuid,uuid,text,text,text)'::regprocedure
  )), 'creator_generation_learning_policy') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.research_outcome_generation_advisory(uuid,uuid,text,text,text)'::regprocedure
  )), 'bounded_exploration') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.research_outcome_generation_advisory(uuid,uuid,text,text,text)'::regprocedure
  )), 'research_current_eligible_outcomes') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.research_outcome_generation_advisory(uuid,uuid,text,text,text)'::regprocedure
  )), 'signal.product_category = product_category_value') > 0,
  'resolver preserves base precedence and revalidates exact live/category evidence'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.research_outcome_generation_advisory(uuid,uuid,text,text,text)'::regprocedure
  )), '''hook_patterns'', ''[]''::jsonb') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_prepare_research_outcome_generation_selection(jsonb)'::regprocedure
  )), '''generation_consumption'', ''gated_not_wired''') > 0,
  'only an empty-hook structural directive is exposed and consumption stays gated'
);
select is(
  (select array_agg(
      namespace.nspname || '.' || procedure.proname
      order by namespace.nspname, procedure.proname
    )
   from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname in ('public', 'content_factory_private')
     and procedure.prokind = 'f'
     and strpos(
       lower(pg_get_functiondef(procedure.oid)),
       'insert into content_factory.research_outcome_generation_assignments'
     ) > 0),
  array['public.creator_start_real_generation']::text[],
  'only the governed paid-start wrapper can create a bound assignment'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.validate_research_outcome_generation_assignment()'::regprocedure
  )), 'generation_job_spec_bindings') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.validate_research_outcome_generation_assignment()'::regprocedure
  )), 'generation_spec_outcome_apply_revalidation_required') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.validate_research_outcome_generation_assignment()'::regprocedure
  )), 'selection_row.selection_action <> ''control''') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.validate_research_outcome_generation_assignment()'::regprocedure
  )), 'new.final_policy_hash <> binding_row.final_policy_hash') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.validate_research_outcome_generation_assignment()'::regprocedure
  )), 'new.prompt_hash <> binding_row.prompt_hash') > 0,
  'assignment trigger accepts only an exact bound control and keeps apply fail-closed'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'e8000000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'outcome-generation-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Outcome Generation Owner"}'::jsonb,
  now(), now()
), (
  'e8000000-0000-4000-8000-000000000002'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'outcome-generation-reviewer@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Outcome Generation Reviewer"}'::jsonb,
  now(), now()
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'e8000000-0000-4000-8000-000000000001',
    true
  );
  perform set_config('request.jwt.claim.role', 'authenticated', true);
end;
$$;

select ok(
  (public.system_initialize_owner(jsonb_build_object(
    'user_id', 'e8000000-0000-4000-8000-000000000001',
    'idempotency_key', 'outcome-generation-owner-init-0001'
  )) ->> 'ok')::boolean,
  'fixture owner initialization succeeds'
);

create temporary table outcome_generation_context (
  organization_id uuid not null,
  actor_id uuid not null,
  product_id uuid not null,
  product_two_id uuid not null,
  input_media_id uuid not null,
  category_id uuid,
  category_binding_id uuid,
  refresh_result jsonb,
  activation_result jsonb,
  advisory_result jsonb,
  apply_result jsonb,
  control_result jsonb,
  before_counts jsonb
) on commit drop;

insert into outcome_generation_context (
  organization_id, actor_id, product_id, product_two_id, input_media_id
)
select
  (bootstrap -> 'organization' ->> 'id')::uuid,
  'e8000000-0000-4000-8000-000000000001'::uuid,
  'e8200000-0000-4000-8000-000000000001'::uuid,
  'e8200000-0000-4000-8000-000000000002'::uuid,
  'e8300000-0000-4000-8000-000000000001'::uuid
from (select public.creator_bootstrap('{}'::jsonb) as bootstrap) response;

update content_factory.memberships membership
set role = 'owner'
from outcome_generation_context context
where membership.organization_id = context.organization_id
  and membership.profile_id = context.actor_id;

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
select
  context.organization_id,
  'e8000000-0000-4000-8000-000000000002'::uuid,
  'reviewer',
  'active'
from outcome_generation_context context;

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
select context.product_id, context.organization_id, 'OUTCOME-GEN-1',
  'Outcome generation product', 'active', '{}'::jsonb, context.actor_id
from outcome_generation_context context
union all
select context.product_two_id, context.organization_id, 'OUTCOME-GEN-2',
  'Second outcome generation product', 'active', '{}'::jsonb, context.actor_id
from outcome_generation_context context;

set local session_replication_role = replica;

do $$
declare
  context_row record;
  run_id_value uuid := 'e8500000-0000-4000-8000-000000000001';
  run_two_id_value uuid := 'e8500000-0000-4000-8000-000000000002';
  draft_id_value uuid := 'e8600000-0000-4000-8000-000000000001';
  draft_two_id_value uuid := 'e8600000-0000-4000-8000-000000000002';
  artifact_id_value uuid := 'e8700000-0000-4000-8000-000000000001';
  artifact_two_id_value uuid := 'e8700000-0000-4000-8000-000000000002';
  category_id_value uuid := 'e8400000-0000-4000-8000-000000000001';
  binding_id_value uuid := 'e8800000-0000-4000-8000-000000000001';
  binding_two_id_value uuid := 'e8800000-0000-4000-8000-000000000002';
  batch_id_value uuid := 'e8900000-0000-4000-8000-000000000001';
  campaign_id_value uuid := 'e8a00000-0000-4000-8000-000000000001';
  brief_value jsonb;
  input_dependencies_value jsonb;
  input_dependency_hash_value text;
  input_dependencies_two_value jsonb;
  input_dependency_hash_two_value text;
  position integer;
  job_id_value uuid;
  output_media_id_value uuid;
  review_id_value uuid;
  review_decision_id_value uuid;
  placement_id_value uuid;
  metric_id_value uuid;
  outcome_product_id uuid;
  outcome_draft_id uuid;
  angle_value text;
  clicks_value bigint;
  orders_value bigint;
  media_hash_value text;
  review_hash_value text;
begin
  select * into context_row from outcome_generation_context;
  brief_value := jsonb_build_object(
    'summary', 'Bounded outcome generation fixture',
    'competitor_analysis', jsonb_build_object(
      'raw_copy', 'SECRET_COMPETITOR_COPY_MUST_NOT_REACH_SELECTION',
      'source_url', 'https://competitor.invalid/private-caption'
    ),
    'scenarios', jsonb_build_array(
      jsonb_build_object('title', 'One', 'hook', 'SECRET_RAW_HOOK_ONE'),
      jsonb_build_object('title', 'Two', 'hook', 'SECRET_RAW_HOOK_TWO'),
      jsonb_build_object('title', 'Three', 'hook', 'SECRET_RAW_HOOK_THREE')
    )
  );
  input_dependencies_value := jsonb_build_object(
    'schema_version', 'research-stage-input-v2',
    'evidence', jsonb_build_array(jsonb_build_object(
      'source_id', 'e8b00000-0000-4000-8000-000000000001'::uuid,
      'content_hash', content_factory_private.json_hash(jsonb_build_object(
        'fixture_source_id', 'e8b00000-0000-4000-8000-000000000001'::uuid
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
      'source_id', 'e8b00000-0000-4000-8000-000000000002'::uuid,
      'content_hash', content_factory_private.json_hash(jsonb_build_object(
        'fixture_source_id', 'e8b00000-0000-4000-8000-000000000002'::uuid
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
    run_id_value, context_row.organization_id, context_row.product_id,
    context_row.actor_id, 'completed', jsonb_build_object('fixture', true),
    '{}'::jsonb, repeat('1', 64), repeat('2', 64),
    'outcome-generation-research-run-1', now() - interval '10 days',
    now() - interval '11 days', now() - interval '10 days'
  ),
  (
    run_two_id_value, context_row.organization_id, context_row.product_two_id,
    context_row.actor_id, 'completed', jsonb_build_object('fixture', true),
    '{}'::jsonb, repeat('3', 64), repeat('4', 64),
    'outcome-generation-research-run-2', now() - interval '10 days',
    now() - interval '11 days', now() - interval '10 days'
  );

  insert into content_factory.creative_brief_drafts (
    id, organization_id, run_id, product_id, created_by, origin, version,
    status, title, brief, source_ids, task_blueprint, content_hash,
    approved_by, approved_at, created_at
  ) values
  (
    draft_id_value, context_row.organization_id, run_id_value,
    context_row.product_id, context_row.actor_id, 'human', 1, 'approved',
    'Approved outcome generation research', brief_value,
    jsonb_build_array('e8b00000-0000-4000-8000-000000000001'),
    jsonb_build_array(jsonb_build_object('title', 'Create exact scenario')),
    content_factory_private.json_hash(brief_value), context_row.actor_id,
    now() - interval '10 days', now() - interval '11 days'
  ),
  (
    draft_two_id_value, context_row.organization_id, run_two_id_value,
    context_row.product_two_id, context_row.actor_id, 'human', 1, 'approved',
    'Second approved outcome generation research', brief_value,
    jsonb_build_array('e8b00000-0000-4000-8000-000000000002'),
    jsonb_build_array(jsonb_build_object('title', 'Create exact scenario')),
    content_factory_private.json_hash(
      brief_value || jsonb_build_object('product', 'two')
    ), context_row.actor_id, now() - interval '10 days',
    now() - interval '11 days'
  );

  insert into content_factory.research_stage_artifacts (
    id, organization_id, run_id, stage, version, payload, content_hash,
    input_dependencies, input_dependency_hash, actor_id, origin, created_at
  ) values
  (
    artifact_id_value, context_row.organization_id, run_id_value,
    'scenarios', 1, brief_value -> 'scenarios',
    content_factory_private.json_hash(brief_value -> 'scenarios'),
    input_dependencies_value, input_dependency_hash_value,
    context_row.actor_id, 'human', now() - interval '10 days'
  ),
  (
    artifact_two_id_value, context_row.organization_id, run_two_id_value,
    'scenarios', 1, brief_value -> 'scenarios',
    content_factory_private.json_hash(
      (brief_value -> 'scenarios') || jsonb_build_array('product-two')
    ), input_dependencies_two_value, input_dependency_hash_two_value,
    context_row.actor_id, 'human', now() - interval '10 days'
  );

  insert into content_factory.research_stage_draft_bindings (
    organization_id, run_id, draft_id, stage, artifact_id,
    dependency_hash, actor_id, origin, bound_at
  ) values
  (
    context_row.organization_id, run_id_value, draft_id_value, 'scenarios',
    artifact_id_value, input_dependency_hash_value,
    context_row.actor_id, 'human',
    now() - interval '10 days'
  ),
  (
    context_row.organization_id, run_two_id_value, draft_two_id_value,
    'scenarios', artifact_two_id_value, input_dependency_hash_two_value,
    context_row.actor_id, 'human', now() - interval '10 days'
  );

  insert into content_factory.research_stage_decisions (
    organization_id, run_id, draft_id, stage, artifact_id, decision,
    actor_id, origin, decision_hash, created_at
  ) values
  (
    context_row.organization_id, run_id_value, draft_id_value, 'scenarios',
    artifact_id_value, 'approved', context_row.actor_id, 'human',
    repeat('7', 64), now() - interval '10 days'
  ),
  (
    context_row.organization_id, run_two_id_value, draft_two_id_value,
    'scenarios', artifact_two_id_value, 'approved', context_row.actor_id,
    'human', repeat('8', 64), now() - interval '10 days'
  );

  insert into content_factory.research_market_categories (
    id, organization_id, canonical_name, normalized_name, definition,
    created_by, created_at
  ) values (
    category_id_value, context_row.organization_id,
    'Outcome generation fixture category',
    content_factory_private.research_market_identity_key(
      'Outcome generation fixture category'
    ),
    'Exact bounded category for explicit generation-consumption coverage.',
    context_row.actor_id, now() - interval '10 days'
  );

  insert into content_factory.research_product_market_category_bindings (
    id, organization_id, product_id, category_id, binding_version,
    decision_action, source_run_id, source_draft_id, candidate_hash,
    reason, confirmed_by, confirmed_at, idempotency_key
  ) values
  (
    binding_id_value, context_row.organization_id, context_row.product_id,
    category_id_value, 1, 'bind_existing', run_id_value, draft_id_value,
    repeat('9', 64), 'Fixture category explicitly confirmed.',
    context_row.actor_id, now() - interval '9 days',
    'outcome-generation-category-binding-1'
  ),
  (
    binding_two_id_value, context_row.organization_id,
    context_row.product_two_id, category_id_value, 1, 'bind_existing',
    run_two_id_value, draft_two_id_value, repeat('a', 64),
    'Second fixture product explicitly shares this category.',
    context_row.actor_id, now() - interval '9 days',
    'outcome-generation-category-binding-2'
  );

  for position in 1..6 loop
    job_id_value := extensions.gen_random_uuid();
    output_media_id_value := extensions.gen_random_uuid();
    review_id_value := extensions.gen_random_uuid();
    review_decision_id_value := extensions.gen_random_uuid();
    placement_id_value := extensions.gen_random_uuid();
    metric_id_value := extensions.gen_random_uuid();
    media_hash_value := content_factory_private.json_hash(
      jsonb_build_object('outcome-media', position)
    );
    review_hash_value := content_factory_private.json_hash(
      jsonb_build_object('outcome-review', position)
    );
    if position <= 3 then
      angle_value := 'trust_builder';
      clicks_value := 170 - position * 10;
      orders_value := 35 - position * 3;
    else
      angle_value := 'comparison';
      clicks_value := (7 - position) * 5;
      orders_value := greatest(0, 6 - position);
    end if;
    if position in (2, 5, 6) then
      outcome_product_id := context_row.product_two_id;
      outcome_draft_id := draft_two_id_value;
    else
      outcome_product_id := context_row.product_id;
      outcome_draft_id := draft_id_value;
    end if;

    insert into content_factory.generation_jobs (
      id, organization_id, product_id, batch_id, ordinal, requested_by,
      assigned_to, mode, provider, allow_real_spend, campaign_id,
      estimated_cost_minor, actual_cost_minor, status, input, output,
      request_hash, idempotency_key, created_at, updated_at
    ) values (
      job_id_value, context_row.organization_id, outcome_product_id,
      batch_id_value, position, context_row.actor_id, context_row.actor_id,
      'real', 'runway', true, campaign_id_value, 4, 4, 'succeeded',
      jsonb_build_object(
        'model', 'seedream5_lite', 'duration_seconds', 0, 'audio', false,
        'platform', 'tiktok', 'product_category', 'household',
        'prompt_text', 'SECRET_RAW_GENERATION_PROMPT'
      ),
      jsonb_build_object('output_media_id', output_media_id_value),
      content_factory_private.json_hash(jsonb_build_object('job', position)),
      'outcome-generation-job-' || position,
      now() - interval '8 days', now() - interval '8 days'
    );

    insert into content_factory.generation_creative_signals (
      organization_id, generation_job_id, product_id, platform, model,
      creative_angle, hook_patterns, source, compiler_version,
      creative_brief_draft_id, scenario_position, prompt_hash,
      product_category, created_at
    ) values (
      context_row.organization_id, job_id_value, outcome_product_id,
      'tiktok', 'seedream5_lite', angle_value, '[]'::jsonb,
      'approved_research', 'outcome-generation-fixture-v1',
      outcome_draft_id, ((position - 1) % 3) + 1,
      content_factory_private.json_hash(jsonb_build_object('prompt', position)),
      'household', now() - interval '8 days'
    );

    insert into content_factory.media_objects (
      id, organization_id, owner_id, product_id, object_name, mime_type,
      size_bytes, sha256, status, metadata, idempotency_key, created_at,
      updated_at
    ) values (
      output_media_id_value, context_row.organization_id, context_row.actor_id,
      outcome_product_id,
      context_row.organization_id::text || '/' || context_row.actor_id::text ||
        '/outcome-generation/' || output_media_id_value::text || '.png',
      'image/png', 1024, media_hash_value, 'ready',
      jsonb_build_object('kind', 'generated_image'),
      'outcome-generation-media-' || position,
      now() - interval '8 days', now() - interval '8 days'
    );

    insert into content_factory.content_review_runs (
      id, organization_id, media_object_id, requested_by, status,
      media_sha256_snapshot, input, result, moderation, ruleset_version,
      model_provider, model_version, request_hash, completion_hash,
      idempotency_key, finished_at, created_at, updated_at
    ) values (
      review_id_value, context_row.organization_id, output_media_id_value,
      context_row.actor_id, 'completed', media_hash_value,
      jsonb_build_object(
        'generation_job_id', job_id_value,
        'product_category', 'household',
        'product_category_verified', true
      ),
      jsonb_build_object(
        'overall_score', 98, 'blockers_count', 0,
        'compliance_status', 'pass'
      ),
      '{}'::jsonb, 'outcome-generation-review-v1', 'fixture', '1',
      content_factory_private.json_hash(
        jsonb_build_object('review-request', position)
      ),
      review_hash_value, 'outcome-generation-review-' || position,
      now() - interval '7 days 12 hours', now() - interval '8 days',
      now() - interval '7 days 12 hours'
    );

    insert into content_factory.content_review_decisions (
      id, organization_id, review_id, decided_by, decision, comment,
      resolved_recommendation_codes, risk_acknowledgements,
      media_watched_confirmed, review_completion_hash,
      media_sha256_snapshot, idempotency_key, created_at
    ) values (
      review_decision_id_value, context_row.organization_id, review_id_value,
      'e8000000-0000-4000-8000-000000000002'::uuid,
      'approved', 'Independent fixture approval confirmed.',
      '[]'::jsonb, '[]'::jsonb, true, review_hash_value, media_hash_value,
      'outcome-generation-review-decision-' || position,
      now() - interval '7 days 6 hours'
    );

    insert into content_factory.placements (
      id, organization_id, product_id, generation_job_id, assigned_to,
      created_by, platform, destination_ref, status, published_at,
      request_hash, idempotency_key, metadata, created_at, updated_at
    ) values (
      placement_id_value, context_row.organization_id, outcome_product_id,
      job_id_value, context_row.actor_id, context_row.actor_id, 'tiktok',
      '@outcome_generation_fixture', 'published', now() - interval '7 days',
      content_factory_private.json_hash(
        jsonb_build_object('placement', position)
      ),
      'outcome-generation-placement-' || position,
      jsonb_build_object(
        'content_review_id', review_id_value,
        'content_review_decision_id', review_decision_id_value,
        'source_media_id', output_media_id_value,
        'media_sha256', media_hash_value
      ),
      now() - interval '7 days 6 hours', now() - interval '7 days'
    );

    insert into content_factory.metric_snapshots (
      id, organization_id, placement_id, collected_by, source, observed_at,
      views, clicks, orders, revenue_minor, raw, request_hash,
      idempotency_key, created_at
    ) values (
      metric_id_value, context_row.organization_id, placement_id_value,
      context_row.actor_id, 'official_api', now() - interval '3 days',
      1000, clicks_value, orders_value, orders_value * 1000,
      jsonb_build_object('raw_caption', 'SECRET_RAW_METRIC_CAPTION'),
      content_factory_private.json_hash(jsonb_build_object('metric', position)),
      'outcome-generation-metric-' || position, now() - interval '3 days'
    );
  end loop;

  update outcome_generation_context
  set category_id = category_id_value,
      category_binding_id = binding_id_value;
end;
$$;

set local session_replication_role = origin;

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
)
select
  context.input_media_id,
  context.organization_id,
  context.actor_id,
  context.product_id,
  'contentengine-private',
  context.organization_id::text || '/' || context.actor_id::text ||
    '/uploads/outcome-generation-product.jpg',
  'image/jpeg', 1024, repeat('e', 64), 'ready',
  jsonb_build_object(
    'original_filename', 'outcome-generation-product.jpg',
    'kind', 'product_photo',
    'rights_confirmed', true
  ),
  'outcome-generation-input-media-0001'
from outcome_generation_context context;

update outcome_generation_context context
set refresh_result = public.creator_refresh_research_outcome_learning(
  jsonb_build_object(
    'organization_id', context.organization_id,
    'market_category_id', context.category_id,
    'platform', 'tiktok',
    'model', 'seedream5_lite',
    'idempotency_key', 'outcome-generation-refresh-0001'
  )
);

select is(
  (select refresh_result ->> 'captured_outcome_count'
   from outcome_generation_context),
  '6',
  'refresh captures all six exact mature first-party outcomes'
);
select is(
  (select refresh_result ->> 'candidate_created'
   from outcome_generation_context),
  'true',
  'the bounded comparison creates a candidate'
);
select is(
  (select refresh_result #>> '{candidate,candidate_payload,preferred_creative_angle}'
   from outcome_generation_context),
  'trust_builder',
  'first-party effectiveness selects only the allowlisted stronger angle'
);

update outcome_generation_context context
set activation_result = public.creator_decide_research_outcome_learning(
  jsonb_build_object(
    'organization_id', context.organization_id,
    'candidate_id', context.refresh_result #>> '{candidate,candidate_id}',
    'action', 'activate',
    'candidate_version',
      (context.refresh_result #>> '{candidate,candidate_version}')::integer,
    'candidate_hash', context.refresh_result #>> '{candidate,candidate_hash}',
    'expected_scope_version', 0,
    'reason', 'Activate exact bounded outcome evidence for fixture coverage.',
    'confirmation', true,
    'idempotency_key', 'outcome-generation-activate-0001'
  )
);

select is(
  (select activation_result #>> '{memory,state}'
   from outcome_generation_context),
  'active',
  'the candidate requires and receives a separate explicit activation'
);

-- Generation policy requires certified access.  Switch the fixture to the
-- same explicit test-only operator waiver used by generation-policy pgTAP.
update content_factory.memberships membership
set role = 'operator'
from outcome_generation_context context
where membership.organization_id = context.organization_id
  and membership.profile_id = context.actor_id;

insert into content_factory.training_access_waivers (
  organization_id, profile_id, scope, status, previous_role, granted_role,
  grant_reason, granted_by
)
select
  context.organization_id, context.actor_id, 'workspace_generation', 'active',
  'trainee', 'operator',
  'TEST-ONLY waiver for outcome generation consumption pgTAP coverage.',
  context.actor_id
from outcome_generation_context context;

update outcome_generation_context context
set before_counts = jsonb_build_object(
  'generation_jobs', (
    select count(*) from content_factory.generation_jobs job
    where job.organization_id = context.organization_id
  ),
  'placements', (
    select count(*) from content_factory.placements placement
    where placement.organization_id = context.organization_id
  ),
  'generation_spend_ledger', (
    select count(*) from content_factory.generation_spend_ledger spend
    where spend.organization_id = context.organization_id
  ),
  'research_authorizations', (
    select count(*)
    from content_factory.research_execution_authorizations research_auth
    where research_auth.organization_id = context.organization_id
  ),
  'assignments', (
    select count(*)
    from content_factory.research_outcome_generation_assignments assignment
    where assignment.organization_id = context.organization_id
  )
);

update outcome_generation_context context
set advisory_result = public.creator_research_outcome_generation_advisory(
  jsonb_build_object(
    'organization_id', context.organization_id,
    'media_id', context.input_media_id,
    'platform', 'tiktok',
    'model', 'seedream5_lite',
    'product_category', 'household'
  )
);

select is(
  (select advisory_result ->> 'status' from outcome_generation_context),
  'ready_for_explicit_apply_or_control',
  'fresh exact evidence is ready only for an explicit per-brief choice'
);
select is(
  (select advisory_result #>> '{permissions,apply_allowed}'
   from outcome_generation_context),
  'true',
  'apply is allowed over bounded exploration'
);
select is(
  (select advisory_result #>> '{permissions,control_allowed}'
   from outcome_generation_context),
  'true',
  'control remains independently available'
);
select is(
  (select advisory_result #>> '{base_policy,selection_mode}'
   from outcome_generation_context),
  'bounded_exploration',
  'the broad outcome candidate never outranks performance or quality policy'
);
select is(
  (select advisory_result #> '{structural_directive,hook_patterns}'
   from outcome_generation_context),
  '[]'::jsonb,
  'the advisory returns no learned hook or raw copy'
);
select is(
  (select advisory_result #>> '{candidate,creative_angle}'
   from outcome_generation_context),
  'trust_builder',
  'the advisory exposes only the allowlisted candidate angle'
);
select is(
  (select advisory_result #>> '{guidance,generation_consumption}'
   from outcome_generation_context),
  'gated_not_wired',
  'advisory explicitly reports that final generation binding is absent'
);
select is(
  (select advisory_result #>> '{permissions,generation_consumption_allowed}'
   from outcome_generation_context),
  'false',
  'selection permission never masquerades as generation permission'
);
select ok(
  (select strpos(advisory_result::text, 'SECRET_') = 0
   from outcome_generation_context),
  'raw competitor, prompt, caption, and metric fixture copy never leaks'
);

update outcome_generation_context context
set apply_result = public.creator_prepare_research_outcome_generation_selection(
  jsonb_build_object(
    'organization_id', context.organization_id,
    'media_id', context.input_media_id,
    'platform', 'tiktok',
    'model', 'seedream5_lite',
    'product_category', 'household',
    'market_category_id',
      context.advisory_result #>> '{scope,market_category_id}',
    'category_binding_id',
      context.advisory_result #>> '{scope,category_binding_id}',
    'category_binding_version',
      (context.advisory_result #>> '{scope,category_binding_version}')::integer,
    'memory_version_id',
      context.advisory_result #>> '{memory,memory_version_id}',
    'memory_version',
      (context.advisory_result #>> '{memory,memory_version}')::integer,
    'candidate_id', context.advisory_result #>> '{candidate,candidate_id}',
    'candidate_version',
      (context.advisory_result #>> '{candidate,candidate_version}')::integer,
    'candidate_hash',
      context.advisory_result #>> '{candidate,candidate_hash}',
    'selection_action', 'apply',
    'confirmation', true,
    'reason', 'Apply this bounded angle to this automatic brief only.',
    'idempotency_key', 'outcome-generation-apply-0001'
  )
);

select is(
  (select apply_result #>> '{selection,selection_action}'
   from outcome_generation_context),
  'apply',
  'apply is recorded as an explicit immutable action'
);
select is(
  (select apply_result #>> '{selection,structural_directive,creative_angle}'
   from outcome_generation_context),
  'trust_builder',
  'apply stores only the selected allowlisted angle'
);
select is(
  (select apply_result #> '{selection,structural_directive,hook_patterns}'
   from outcome_generation_context),
  '[]'::jsonb,
  'prepared apply selection still contains no hooks'
);
select is(
  (select apply_result #>> '{selection,effectiveness_status}'
   from outcome_generation_context),
  'unknown',
  'assignment effectiveness is not fabricated before mature outcomes'
);
select is(
  (select apply_result #>> '{selection,generation_binding_state}'
   from outcome_generation_context),
  'gated',
  'prepared selection remains gated from actual generation'
);
select matches(
  (select apply_result #>> '{selection,selection_hash}'
   from outcome_generation_context),
  '^[0-9a-f]{64}$',
  'explicit selection has immutable provenance hash'
);
select is(
  (select count(*)::integer
   from content_factory.research_outcome_generation_selections selection
   join outcome_generation_context context
     on context.organization_id = selection.organization_id
   where selection.selection_action = 'apply'
     and selection.selected_hook_patterns = '[]'::jsonb
     and selection.effectiveness_status = 'unknown'
     and selection.generation_binding_state = 'gated'),
  1,
  'one append-only gated apply selection is persisted'
);

select is(
  (
    select public.creator_prepare_research_outcome_generation_selection(
      jsonb_build_object(
        'organization_id', context.organization_id,
        'media_id', context.input_media_id,
        'platform', 'tiktok',
        'model', 'seedream5_lite',
        'product_category', 'household',
        'market_category_id',
          context.advisory_result #>> '{scope,market_category_id}',
        'category_binding_id',
          context.advisory_result #>> '{scope,category_binding_id}',
        'category_binding_version',
          (context.advisory_result #>> '{scope,category_binding_version}')::integer,
        'memory_version_id',
          context.advisory_result #>> '{memory,memory_version_id}',
        'memory_version',
          (context.advisory_result #>> '{memory,memory_version}')::integer,
        'candidate_id', context.advisory_result #>> '{candidate,candidate_id}',
        'candidate_version',
          (context.advisory_result #>> '{candidate,candidate_version}')::integer,
        'candidate_hash',
          context.advisory_result #>> '{candidate,candidate_hash}',
        'selection_action', 'apply',
        'confirmation', true,
        'reason', 'Apply this bounded angle to this automatic brief only.',
        'idempotency_key', 'outcome-generation-apply-0001'
      )
    ) #>> '{selection,selection_hash}'
    from outcome_generation_context context
  ),
  (select apply_result #>> '{selection,selection_hash}'
   from outcome_generation_context),
  'exact idempotent replay returns the same selection'
);

update outcome_generation_context context
set control_result = public.creator_prepare_research_outcome_generation_selection(
  jsonb_build_object(
    'organization_id', context.organization_id,
    'media_id', context.input_media_id,
    'platform', 'tiktok',
    'model', 'seedream5_lite',
    'product_category', 'household',
    'market_category_id',
      context.advisory_result #>> '{scope,market_category_id}',
    'category_binding_id',
      context.advisory_result #>> '{scope,category_binding_id}',
    'category_binding_version',
      (context.advisory_result #>> '{scope,category_binding_version}')::integer,
    'memory_version_id',
      context.advisory_result #>> '{memory,memory_version_id}',
    'memory_version',
      (context.advisory_result #>> '{memory,memory_version}')::integer,
    'candidate_id', context.advisory_result #>> '{candidate,candidate_id}',
    'candidate_version',
      (context.advisory_result #>> '{candidate,candidate_version}')::integer,
    'candidate_hash', context.advisory_result #>> '{candidate,candidate_hash}',
    'selection_action', 'control',
    'confirmation', true,
    'reason', 'Keep the existing product policy for this automatic brief.',
    'idempotency_key', 'outcome-generation-control-0001'
  )
);

select is(
  (select control_result #>> '{selection,selection_action}'
   from outcome_generation_context),
  'control',
  'control is a separate explicit selection action'
);
select is(
  (select control_result #> '{selection,structural_directive,creative_angle}'
   from outcome_generation_context),
  'null'::jsonb,
  'control carries no outcome angle into the structural directive'
);
select is(
  (select count(*)::integer
   from content_factory.research_outcome_generation_assignments assignment
   join outcome_generation_context context
     on context.organization_id = assignment.organization_id),
  0,
  'no paid assignment is created by either explicit choice'
);
select is(
  (
    select jsonb_build_object(
      'generation_jobs', (
        select count(*) from content_factory.generation_jobs job
        where job.organization_id = context.organization_id
      ),
      'placements', (
        select count(*) from content_factory.placements placement
        where placement.organization_id = context.organization_id
      ),
      'generation_spend_ledger', (
        select count(*) from content_factory.generation_spend_ledger spend
        where spend.organization_id = context.organization_id
      ),
      'research_authorizations', (
        select count(*)
        from content_factory.research_execution_authorizations research_auth
        where research_auth.organization_id = context.organization_id
      ),
      'assignments', (
        select count(*)
        from content_factory.research_outcome_generation_assignments assignment
        where assignment.organization_id = context.organization_id
      )
    )
    from outcome_generation_context context
  ),
  (select before_counts from outcome_generation_context),
  'advisory and selections create no job, spend, provider, publication, or assignment side effect'
);

select throws_ok(
  $$update content_factory.research_outcome_generation_selections selection
    set reason = 'Attempted mutation must fail.'
    where selection.id = (
      select (context.apply_result #>> '{selection,selection_id}')::uuid
      from outcome_generation_context context
    )$$,
  '55000', 'research_outcome_generation_selections_append_only',
  'selection provenance is append-only'
);
select throws_ok(
  $$select public.creator_prepare_research_outcome_generation_selection(
    jsonb_build_object(
      'organization_id', context.organization_id,
      'media_id', context.input_media_id,
      'platform', 'tiktok',
      'model', 'seedream5_lite',
      'product_category', 'household',
      'market_category_id',
        context.advisory_result #>> '{scope,market_category_id}',
      'category_binding_id',
        context.advisory_result #>> '{scope,category_binding_id}',
      'category_binding_version',
        (context.advisory_result #>> '{scope,category_binding_version}')::integer,
      'memory_version_id',
        context.advisory_result #>> '{memory,memory_version_id}',
      'memory_version',
        (context.advisory_result #>> '{memory,memory_version}')::integer,
      'candidate_id', context.advisory_result #>> '{candidate,candidate_id}',
      'candidate_version',
        (context.advisory_result #>> '{candidate,candidate_version}')::integer,
      'candidate_hash', context.advisory_result #>> '{candidate,candidate_hash}',
      'selection_action', 'apply',
      'reason', 'Confirmation is deliberately missing.',
      'idempotency_key', 'outcome-generation-missing-confirmation'
    )
  ) from outcome_generation_context context$$,
  '22023', 'research_outcome_generation_selection_confirmation_required',
  'every apply/control choice requires explicit true confirmation'
);
select throws_ok(
  $$select public.creator_prepare_research_outcome_generation_selection(
    jsonb_build_object(
      'organization_id', context.organization_id,
      'media_id', context.input_media_id,
      'platform', 'tiktok',
      'model', 'seedream5_lite',
      'product_category', 'household',
      'market_category_id',
        context.advisory_result #>> '{scope,market_category_id}',
      'category_binding_id',
        context.advisory_result #>> '{scope,category_binding_id}',
      'category_binding_version',
        (context.advisory_result #>> '{scope,category_binding_version}')::integer,
      'memory_version_id',
        context.advisory_result #>> '{memory,memory_version_id}',
      'memory_version',
        (context.advisory_result #>> '{memory,memory_version}')::integer,
      'candidate_id', context.advisory_result #>> '{candidate,candidate_id}',
      'candidate_version',
        (context.advisory_result #>> '{candidate,candidate_version}')::integer,
      'candidate_hash', repeat('0', 64),
      'selection_action', 'apply',
      'confirmation', true,
      'reason', 'A stale candidate hash must fail closed.',
      'idempotency_key', 'outcome-generation-stale-hash'
    )
  ) from outcome_generation_context context$$,
  '55000', 'research_outcome_generation_selection_stale',
  'selection revalidates the exact candidate hash after both locks'
);

update content_factory.memberships membership
set role = 'owner'
from outcome_generation_context context
where membership.organization_id = context.organization_id
  and membership.profile_id = context.actor_id;

select is(
  (
    select public.creator_decide_research_outcome_learning(
      jsonb_build_object(
        'organization_id', context.organization_id,
        'candidate_id', context.refresh_result #>> '{candidate,candidate_id}',
        'action', 'deactivate',
        'candidate_version',
          (context.refresh_result #>> '{candidate,candidate_version}')::integer,
        'candidate_hash',
          context.refresh_result #>> '{candidate,candidate_hash}',
        'expected_scope_version', 1,
        'reason', 'Deactivate active memory to verify selection freshness.',
        'confirmation', true,
        'idempotency_key', 'outcome-generation-deactivate-0001'
      )
    ) #>> '{memory,state}'
    from outcome_generation_context context
  ),
  'inactive',
  'memory can be explicitly deactivated independently of prior selections'
);

update content_factory.memberships membership
set role = 'operator'
from outcome_generation_context context
where membership.organization_id = context.organization_id
  and membership.profile_id = context.actor_id;

select is(
  (
    select public.creator_research_outcome_generation_advisory(
      jsonb_build_object(
        'organization_id', context.organization_id,
        'media_id', context.input_media_id,
        'platform', 'tiktok',
        'model', 'seedream5_lite',
        'product_category', 'household'
      )
    ) ->> 'status'
    from outcome_generation_context context
  ),
  'no_active_advisory_memory',
  'deactivation immediately removes the outcome advisory from new briefs'
);
select throws_ok(
  $$select public.creator_prepare_research_outcome_generation_selection(
    jsonb_build_object(
      'organization_id', context.organization_id,
      'media_id', context.input_media_id,
      'platform', 'tiktok',
      'model', 'seedream5_lite',
      'product_category', 'household',
      'market_category_id',
        context.advisory_result #>> '{scope,market_category_id}',
      'category_binding_id',
        context.advisory_result #>> '{scope,category_binding_id}',
      'category_binding_version',
        (context.advisory_result #>> '{scope,category_binding_version}')::integer,
      'memory_version_id',
        context.advisory_result #>> '{memory,memory_version_id}',
      'memory_version',
        (context.advisory_result #>> '{memory,memory_version}')::integer,
      'candidate_id', context.advisory_result #>> '{candidate,candidate_id}',
      'candidate_version',
        (context.advisory_result #>> '{candidate,candidate_version}')::integer,
      'candidate_hash', context.advisory_result #>> '{candidate,candidate_hash}',
      'selection_action', 'apply',
      'confirmation', true,
      'reason', 'Deactivated memory must make this expected tuple stale.',
      'idempotency_key', 'outcome-generation-after-deactivate'
    )
  ) from outcome_generation_context context$$,
  '55000', 'research_outcome_generation_selection_stale',
  'prepare revalidates active memory immediately before every new selection'
);

select * from finish();
rollback;
