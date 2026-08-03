begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select has_function(
  'public', 'creator_research_outcome_learning_scopes', array['jsonb'],
  'read-only exact outcome scope registry RPC exists'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_research_outcome_learning_scopes(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_research_outcome_learning_scopes(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.creator_research_outcome_learning_scopes(jsonb)',
    'execute'
  ),
  'only authenticated callers receive the registry RPC grant'
);
select is(
  (
    select procedure.provolatile::text
    from pg_proc procedure
    where procedure.oid =
      'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  ),
  's',
  'scope discovery is declared STABLE and therefore read-only'
);
select ok(
  (
    select procedure.prosecdef
    from pg_proc procedure
    where procedure.oid =
      'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  ),
  'scope discovery is a narrow SECURITY DEFINER boundary'
);
select ok(
  pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  ) !~* '\m(insert|update|delete|merge|truncate)\M'
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'begin_command') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'finish_command') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'pg_advisory') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'perform content_factory_private.current_profile_id') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'creator_refresh_research_outcome_learning') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'creator_decide_research_outcome_learning') = 0,
  'registry definition has no mutation, profile upsert, command, lock, refresh, or decision path'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'research_stage_decisions') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'scenario_approval.decision = ''approved''') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'category_binding.candidate_hash') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'research_outcome_lineage_snapshots') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'research_outcome_learning_candidates') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'research_outcome_learning_memory_versions') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_outcome_learning_scopes(jsonb)'::regprocedure
  )), 'limit limit_value + 1') > 0,
  'definition keeps exact approval, category hash, three-ledger union, and limit+1 guards'
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
  ('e7000000-0000-4000-8000-000000000001', 'scope-owner@example.test', 'Scope Owner'),
  ('e7000000-0000-4000-8000-000000000002', 'scope-reviewer@example.test', 'Scope Reviewer'),
  ('e7000000-0000-4000-8000-000000000003', 'scope-viewer@example.test', 'Scope Viewer'),
  ('e7000000-0000-4000-8000-000000000004', 'other-scope-owner@example.test', 'Other Scope Owner')
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  ('e7100000-0000-4000-8000-000000000001', 'Scope Registry Tenant', 'scope-registry-test', 'active'),
  ('e7100000-0000-4000-8000-000000000002', 'Other Scope Tenant', 'other-scope-registry-test', 'active');
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  ('e7100000-0000-4000-8000-000000000001', 'e7000000-0000-4000-8000-000000000001', 'owner', 'active'),
  ('e7100000-0000-4000-8000-000000000001', 'e7000000-0000-4000-8000-000000000002', 'reviewer', 'active'),
  ('e7100000-0000-4000-8000-000000000001', 'e7000000-0000-4000-8000-000000000003', 'viewer', 'active'),
  ('e7100000-0000-4000-8000-000000000002', 'e7000000-0000-4000-8000-000000000004', 'owner', 'active');
insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
)
values
  (
    'e7200000-0000-4000-8000-000000000001',
    'e7100000-0000-4000-8000-000000000001',
    'SCOPE-TARGET', 'Exact Scope Target', 'active',
    'e7000000-0000-4000-8000-000000000001'
  ),
  (
    'e7200000-0000-4000-8000-000000000002',
    'e7100000-0000-4000-8000-000000000001',
    'SCOPE-UNRELATED', 'Unrelated Scope Product', 'active',
    'e7000000-0000-4000-8000-000000000001'
  ),
  (
    'e7200000-0000-4000-8000-000000000003',
    'e7100000-0000-4000-8000-000000000001',
    'SCOPE-NO-APPROVAL', 'No Stage Approval Product', 'active',
    'e7000000-0000-4000-8000-000000000001'
  ),
  (
    'e7200000-0000-4000-8000-000000000004',
    'e7100000-0000-4000-8000-000000000002',
    'SCOPE-OTHER-TENANT', 'Other Tenant Scope Product', 'active',
    'e7000000-0000-4000-8000-000000000004'
  );

create temporary table scope_registry_context (
  response jsonb,
  baseline_counts jsonb
) on commit drop;
insert into scope_registry_context default values;

-- Fixture setup bypasses append-only capture triggers, but all CHECK and
-- uniqueness constraints remain active. Runtime RPC calls below use origin.
set local session_replication_role = replica;

insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at,
  created_at, updated_at
)
values
  (
    'e7300000-0000-4000-8000-000000000001',
    'e7100000-0000-4000-8000-000000000001',
    'e7200000-0000-4000-8000-000000000001',
    'e7000000-0000-4000-8000-000000000001', 'completed',
    '{"fixture":true}'::jsonb, '{}'::jsonb, repeat('1', 64), repeat('2', 64),
    'scope-registry-target-run', now() - interval '9 days',
    now() - interval '10 days', now() - interval '9 days'
  ),
  (
    'e7300000-0000-4000-8000-000000000002',
    'e7100000-0000-4000-8000-000000000001',
    'e7200000-0000-4000-8000-000000000002',
    'e7000000-0000-4000-8000-000000000001', 'completed',
    '{"fixture":true}'::jsonb, '{}'::jsonb, repeat('3', 64), repeat('4', 64),
    'scope-registry-unrelated-run', now() - interval '9 days',
    now() - interval '10 days', now() - interval '9 days'
  ),
  (
    'e7300000-0000-4000-8000-000000000003',
    'e7100000-0000-4000-8000-000000000001',
    'e7200000-0000-4000-8000-000000000003',
    'e7000000-0000-4000-8000-000000000001', 'completed',
    '{"fixture":true}'::jsonb, '{}'::jsonb, repeat('5', 64), repeat('6', 64),
    'scope-registry-no-approval-run', now() - interval '9 days',
    now() - interval '10 days', now() - interval '9 days'
  ),
  (
    'e7300000-0000-4000-8000-000000000004',
    'e7100000-0000-4000-8000-000000000002',
    'e7200000-0000-4000-8000-000000000004',
    'e7000000-0000-4000-8000-000000000004', 'completed',
    '{"fixture":true}'::jsonb, '{}'::jsonb, repeat('7', 64), repeat('8', 64),
    'scope-registry-other-tenant-run', now() - interval '9 days',
    now() - interval '10 days', now() - interval '9 days'
  );

insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, previous_draft_id, created_by,
  origin, version, status, title, brief, source_ids, task_blueprint,
  content_hash, approved_by, approved_at, created_at
)
values
  (
    'e7400000-0000-4000-8000-000000000001',
    'e7100000-0000-4000-8000-000000000001',
    'e7300000-0000-4000-8000-000000000001',
    'e7200000-0000-4000-8000-000000000001', null,
    'e7000000-0000-4000-8000-000000000001', 'human', 1, 'approved',
    'Approved exact scenarios',
    jsonb_build_object(
      'category_analysis', jsonb_build_object(
        'category_name', 'Exact styling tools',
        'definition', 'Exact structural category approved by the user.'
      ),
      'creative_potential', jsonb_build_object(
        'recommended_scenario_position', 2
      ),
      'scenarios', jsonb_build_array(
        jsonb_build_object(
          'title', 'SECRET_APPROVED_SCENARIO_ONE',
          'platform', 'youtube',
          'recommended_generation_mode', 'real_seedance'
        ),
        jsonb_build_object(
          'title', 'SECRET_APPROVED_SCENARIO_TWO',
          'platform', 'instagram',
          'recommended_generation_mode', 'real_gen4'
        ),
        jsonb_build_object(
          'title', 'Unsupported marketplace scenario',
          'platform', 'ozon',
          'recommended_generation_mode', 'real_photo'
        )
      )
    ),
    jsonb_build_array('e7f00000-0000-4000-8000-000000000001'),
    jsonb_build_array(jsonb_build_object('title', 'Exact task')),
    repeat('9', 64), 'e7000000-0000-4000-8000-000000000001',
    now() - interval '8 days', now() - interval '10 days'
  ),
  (
    'e7400000-0000-4000-8000-000000000002',
    'e7100000-0000-4000-8000-000000000001',
    'e7300000-0000-4000-8000-000000000001',
    'e7200000-0000-4000-8000-000000000001',
    'e7400000-0000-4000-8000-000000000001',
    'e7000000-0000-4000-8000-000000000001', 'human', 2, 'draft',
    'Latest but unapproved scenarios',
    jsonb_build_object(
      'category_analysis', jsonb_build_object(
        'category_name', 'Historical styling tools',
        'definition', 'A different category which was never approved with scenarios.'
      ),
      'creative_potential', jsonb_build_object(
        'recommended_scenario_position', 1
      ),
      'scenarios', jsonb_build_array(
        jsonb_build_object(
          'title', 'SECRET_UNAPPROVED_SCENARIO',
          'platform', 'vk',
          'recommended_generation_mode', 'real_photo'
        ),
        jsonb_build_object(
          'title', 'Legacy fallback must stay excluded',
          'platform', 'youtube',
          'generation_mode', 'real_photo'
        )
      )
    ),
    jsonb_build_array('e7f00000-0000-4000-8000-000000000002'),
    jsonb_build_array(jsonb_build_object('title', 'Unapproved task')),
    repeat('a', 64), null, null, now() - interval '7 days'
  ),
  (
    'e7400000-0000-4000-8000-000000000003',
    'e7100000-0000-4000-8000-000000000001',
    'e7300000-0000-4000-8000-000000000003',
    'e7200000-0000-4000-8000-000000000003', null,
    'e7000000-0000-4000-8000-000000000001', 'human', 1, 'approved',
    'Approved draft without approved stage ledger',
    jsonb_build_object(
      'category_analysis', jsonb_build_object(
        'category_name', 'No stage approval category',
        'definition', 'An exact category with no approved scenario decision.'
      ),
      'creative_potential', jsonb_build_object(
        'recommended_scenario_position', 1
      ),
      'scenarios', jsonb_build_array(jsonb_build_object(
        'title', 'Must not be discovered',
        'platform', 'instagram',
        'recommended_generation_mode', 'real_photo'
      ))
    ),
    jsonb_build_array('e7f00000-0000-4000-8000-000000000003'),
    jsonb_build_array(jsonb_build_object('title', 'No approval task')),
    repeat('b', 64), 'e7000000-0000-4000-8000-000000000001',
    now() - interval '8 days', now() - interval '10 days'
  );

insert into content_factory.research_stage_artifacts (
  id, organization_id, run_id, stage, version, parent_artifact_id,
  payload, content_hash, actor_id, origin, created_at
)
select
  fixture.id::uuid,
  'e7100000-0000-4000-8000-000000000001'::uuid,
  fixture.run_id::uuid,
  'scenarios', fixture.version, fixture.parent_id::uuid,
  jsonb_build_object('scenarios', draft.brief -> 'scenarios'),
  fixture.content_hash,
  'e7000000-0000-4000-8000-000000000001'::uuid,
  'human', draft.created_at
from (values
  (
    'e7500000-0000-4000-8000-000000000001',
    'e7300000-0000-4000-8000-000000000001', 1, null,
    repeat('c', 64), 'e7400000-0000-4000-8000-000000000001'
  ),
  (
    'e7500000-0000-4000-8000-000000000002',
    'e7300000-0000-4000-8000-000000000001', 2,
    'e7500000-0000-4000-8000-000000000001',
    repeat('d', 64), 'e7400000-0000-4000-8000-000000000002'
  ),
  (
    'e7500000-0000-4000-8000-000000000003',
    'e7300000-0000-4000-8000-000000000003', 1, null,
    repeat('e', 64), 'e7400000-0000-4000-8000-000000000003'
  )
) fixture(id, run_id, version, parent_id, content_hash, draft_id)
join content_factory.creative_brief_drafts draft
  on draft.id = fixture.draft_id::uuid;

insert into content_factory.research_stage_draft_bindings (
  organization_id, run_id, draft_id, stage, artifact_id,
  dependency_hash, actor_id, origin, bound_at
)
values
  (
    'e7100000-0000-4000-8000-000000000001',
    'e7300000-0000-4000-8000-000000000001',
    'e7400000-0000-4000-8000-000000000001', 'scenarios',
    'e7500000-0000-4000-8000-000000000001', repeat('f', 64),
    'e7000000-0000-4000-8000-000000000001', 'human',
    now() - interval '8 days'
  ),
  (
    'e7100000-0000-4000-8000-000000000001',
    'e7300000-0000-4000-8000-000000000001',
    'e7400000-0000-4000-8000-000000000002', 'scenarios',
    'e7500000-0000-4000-8000-000000000002', repeat('0', 64),
    'e7000000-0000-4000-8000-000000000001', 'human',
    now() - interval '7 days'
  ),
  (
    'e7100000-0000-4000-8000-000000000001',
    'e7300000-0000-4000-8000-000000000003',
    'e7400000-0000-4000-8000-000000000003', 'scenarios',
    'e7500000-0000-4000-8000-000000000003', repeat('1', 64),
    'e7000000-0000-4000-8000-000000000001', 'human',
    now() - interval '8 days'
  );

-- The inconsistent approval on the draft row below proves that registry
-- discovery requires both draft.status=approved and the immutable stage
-- approval. The no-stage fixture proves the inverse requirement.
insert into content_factory.research_stage_decisions (
  id, organization_id, run_id, draft_id, stage, artifact_id, decision,
  actor_id, origin, decision_hash, created_at
)
values
  (
    'e7510000-0000-4000-8000-000000000001',
    'e7100000-0000-4000-8000-000000000001',
    'e7300000-0000-4000-8000-000000000001',
    'e7400000-0000-4000-8000-000000000001', 'scenarios',
    'e7500000-0000-4000-8000-000000000001', 'approved',
    'e7000000-0000-4000-8000-000000000001', 'human', repeat('2', 64),
    now() - interval '8 days'
  ),
  (
    'e7510000-0000-4000-8000-000000000002',
    'e7100000-0000-4000-8000-000000000001',
    'e7300000-0000-4000-8000-000000000001',
    'e7400000-0000-4000-8000-000000000002', 'scenarios',
    'e7500000-0000-4000-8000-000000000002', 'approved',
    'e7000000-0000-4000-8000-000000000001', 'human', repeat('3', 64),
    now() - interval '7 days'
  );

insert into content_factory.research_market_categories (
  id, organization_id, canonical_name, normalized_name, definition,
  status, created_by, created_at
)
values
  (
    'e7600000-0000-4000-8000-000000000001',
    'e7100000-0000-4000-8000-000000000001', 'Exact styling tools',
    content_factory_private.research_market_identity_key('Exact styling tools'),
    'Exact category linked to the approved category analysis.', 'active',
    'e7000000-0000-4000-8000-000000000001', now() - interval '9 days'
  ),
  (
    'e7600000-0000-4000-8000-000000000002',
    'e7100000-0000-4000-8000-000000000001', 'Historical styling tools',
    content_factory_private.research_market_identity_key('Historical styling tools'),
    'Historical category retained only for exact ledger management.', 'retired',
    'e7000000-0000-4000-8000-000000000001', now() - interval '9 days'
  ),
  (
    'e7600000-0000-4000-8000-000000000003',
    'e7100000-0000-4000-8000-000000000001', 'Unrelated product category',
    content_factory_private.research_market_identity_key('Unrelated product category'),
    'Category bound only to an unrelated product in the same tenant.', 'active',
    'e7000000-0000-4000-8000-000000000001', now() - interval '9 days'
  ),
  (
    'e7600000-0000-4000-8000-000000000004',
    'e7100000-0000-4000-8000-000000000001', 'No stage approval category',
    content_factory_private.research_market_identity_key('No stage approval category'),
    'Category linked to a draft whose scenario stage lacks approval.', 'active',
    'e7000000-0000-4000-8000-000000000001', now() - interval '9 days'
  ),
  (
    'e7600000-0000-4000-8000-000000000005',
    'e7100000-0000-4000-8000-000000000002', 'Other tenant category',
    content_factory_private.research_market_identity_key('Other tenant category'),
    'Category and ledgers owned by a different tenant.', 'active',
    'e7000000-0000-4000-8000-000000000004', now() - interval '9 days'
  );

insert into content_factory.research_product_market_category_bindings (
  id, organization_id, product_id, category_id, previous_binding_id,
  binding_version, decision_action, source_run_id, source_draft_id,
  candidate_hash, reason, confirmed_by, confirmed_at, idempotency_key
)
values
  (
    'e7700000-0000-4000-8000-000000000001',
    'e7100000-0000-4000-8000-000000000001',
    'e7200000-0000-4000-8000-000000000001',
    'e7600000-0000-4000-8000-000000000002', null, 1, 'bind_existing',
    'e7300000-0000-4000-8000-000000000001',
    'e7400000-0000-4000-8000-000000000002',
    content_factory_private.json_hash((
      select draft.brief -> 'category_analysis'
      from content_factory.creative_brief_drafts draft
      where draft.id = 'e7400000-0000-4000-8000-000000000002'
    )),
    'Historical category was explicitly confirmed.',
    'e7000000-0000-4000-8000-000000000001', now() - interval '7 days',
    'scope-registry-historical-binding'
  ),
  (
    'e7700000-0000-4000-8000-000000000002',
    'e7100000-0000-4000-8000-000000000001',
    'e7200000-0000-4000-8000-000000000001',
    'e7600000-0000-4000-8000-000000000001',
    'e7700000-0000-4000-8000-000000000001', 2, 'reclassify',
    'e7300000-0000-4000-8000-000000000001',
    'e7400000-0000-4000-8000-000000000001',
    content_factory_private.json_hash((
      select draft.brief -> 'category_analysis'
      from content_factory.creative_brief_drafts draft
      where draft.id = 'e7400000-0000-4000-8000-000000000001'
    )),
    'Current exact category matches the approved research evidence.',
    'e7000000-0000-4000-8000-000000000001', now() - interval '6 days',
    'scope-registry-current-binding'
  ),
  (
    'e7700000-0000-4000-8000-000000000003',
    'e7100000-0000-4000-8000-000000000001',
    'e7200000-0000-4000-8000-000000000002',
    'e7600000-0000-4000-8000-000000000003', null, 1, 'bind_existing',
    'e7300000-0000-4000-8000-000000000002',
    'e7400000-0000-4000-8000-000000000001', repeat('4', 64),
    'Unrelated product category fixture.',
    'e7000000-0000-4000-8000-000000000001', now() - interval '6 days',
    'scope-registry-unrelated-binding'
  ),
  (
    'e7700000-0000-4000-8000-000000000004',
    'e7100000-0000-4000-8000-000000000001',
    'e7200000-0000-4000-8000-000000000003',
    'e7600000-0000-4000-8000-000000000004', null, 1, 'bind_existing',
    'e7300000-0000-4000-8000-000000000003',
    'e7400000-0000-4000-8000-000000000003',
    content_factory_private.json_hash((
      select draft.brief -> 'category_analysis'
      from content_factory.creative_brief_drafts draft
      where draft.id = 'e7400000-0000-4000-8000-000000000003'
    )),
    'No-stage category fixture.',
    'e7000000-0000-4000-8000-000000000001', now() - interval '6 days',
    'scope-registry-no-stage-binding'
  ),
  (
    'e7700000-0000-4000-8000-000000000005',
    'e7100000-0000-4000-8000-000000000002',
    'e7200000-0000-4000-8000-000000000004',
    'e7600000-0000-4000-8000-000000000005', null, 1, 'bind_existing',
    'e7300000-0000-4000-8000-000000000004',
    'e7400000-0000-4000-8000-000000000001', repeat('5', 64),
    'Other tenant category fixture.',
    'e7000000-0000-4000-8000-000000000004', now() - interval '6 days',
    'scope-registry-other-tenant-binding'
  );

insert into content_factory.research_outcome_lineage_snapshots (
  id, organization_id, product_id, market_category_id, category_binding_id,
  research_run_id, research_completion_hash, creative_brief_draft_id,
  draft_content_hash, scenario_artifact_id, scenario_artifact_hash,
  scenario_dependency_hash, scenario_position, scenario_hash,
  generation_job_id, creative_signal_id, prompt_hash, media_object_id,
  media_sha256, review_id, review_completion_hash, review_decision_id,
  placement_id, platform, model, creative_angle, metric_snapshot_id,
  metric_source, metric_observed_at, placement_published_at, views, clicks,
  orders, revenue_minor, metric_is_correction, structural_payload,
  effectiveness_evidence, guard_evidence, metric_hash, lineage_hash,
  captured_by, captured_at
)
values (
  'e7b00000-0000-4000-8000-000000000001',
  'e7100000-0000-4000-8000-000000000001',
  'e7200000-0000-4000-8000-000000000001',
  'e7600000-0000-4000-8000-000000000001',
  'e7700000-0000-4000-8000-000000000002',
  'e7300000-0000-4000-8000-000000000001', repeat('6', 64),
  'e7400000-0000-4000-8000-000000000001', repeat('7', 64),
  'e7500000-0000-4000-8000-000000000001', repeat('8', 64), repeat('9', 64),
  1, repeat('a', 64),
  'e7b10000-0000-4000-8000-000000000001',
  'e7b20000-0000-4000-8000-000000000001', repeat('b', 64),
  'e7b30000-0000-4000-8000-000000000001', repeat('c', 64),
  'e7b40000-0000-4000-8000-000000000001', repeat('d', 64),
  'e7b50000-0000-4000-8000-000000000001',
  'e7b60000-0000-4000-8000-000000000001', 'tiktok', 'seedream5_lite',
  'demonstration', 'e7b70000-0000-4000-8000-000000000001',
  'official_api', now() - interval '1 day', now() - interval '5 days',
  1000, 120, 20, 20000, false,
  jsonb_build_object(
    'schema_version', 'research-outcome-structural-v1',
    'creative_angle', 'demonstration', 'platform', 'tiktok',
    'model', 'seedream5_lite', 'scenario_position', 1
  ),
  jsonb_build_object(
    'views', 1000, 'clicks', 120, 'orders', 20, 'revenue_minor', 20000,
    'ctr', 0.12, 'order_rate', 0.02, 'revenue_per_1000_views', 20000,
    'metric_source', 'official_api',
    'metric_observed_at', to_jsonb(now() - interval '1 day'),
    'placement_published_at', to_jsonb(now() - interval '5 days'),
    'maturity_hours', 96
  ),
  jsonb_build_object(
    'qa_approved', true, 'media_watched_confirmed', true,
    'review_blockers_count', 0, 'review_compliance_status', 'pass',
    'review_ruleset_version', 'scope-test-v1', 'first_party_metric', true,
    'metric_is_correction', false, 'raw_fields_excluded', true
  ),
  repeat('e', 64), repeat('f', 64),
  'e7000000-0000-4000-8000-000000000001', now() - interval '1 day'
);

insert into content_factory.research_outcome_learning_candidates (
  id, organization_id, market_category_id, platform, model, candidate_kind,
  candidate_version, candidate_payload, effectiveness_evidence,
  guard_evidence, evidence_hash, candidate_hash, created_by, created_at
)
select
  fixture.id::uuid,
  fixture.organization_id::uuid,
  fixture.category_id::uuid,
  fixture.platform,
  fixture.model,
  'creative_angle_preference', 1,
  jsonb_build_object(
    'schema_version', 'research-outcome-learning-v1',
    'candidate_kind', 'creative_angle_preference',
    'scope', jsonb_build_object(
      'market_category_id', fixture.category_id,
      'platform', fixture.platform,
      'model', fixture.model
    ),
    'preferred_creative_angle', 'demonstration',
    'avoid_creative_angle', 'comparison',
    'ruleset_version', 'scope-registry-test-v1'
  ),
  jsonb_build_object(
    'eligible_outcome_count', 6, 'eligible_angle_count', 2,
    'minimum_outcomes_per_angle', 3, 'minimum_views_per_outcome', 100,
    'minimum_maturity_hours', 72, 'maximum_outcomes_considered', 10000,
    'overlapping_product_count', 2,
    'preferred', jsonb_build_object('outcome_count', 3),
    'comparator', jsonb_build_object(
      'creative_angle', 'comparison', 'outcome_count', 3
    ),
    'absolute_deltas', jsonb_build_object('mean_ctr', 0.05),
    'views_are_not_a_rank_signal', true
  ),
  jsonb_build_object(
    'qa_approved_outcome_count', 6,
    'first_party_metric_outcome_count', 6,
    'distinct_product_count', 2,
    'market_category_exact', true,
    'tenant_scope_exact', true,
    'raw_competitor_content_excluded', true,
    'raw_prompt_caption_url_excluded', true,
    'automatic_activation', false,
    'advisory_only', true,
    'generation_consumption', 'not_wired'
  ),
  fixture.evidence_hash,
  fixture.candidate_hash,
  fixture.actor_id::uuid,
  now() - fixture.age
from (values
  (
    'e7800000-0000-4000-8000-000000000001',
    'e7100000-0000-4000-8000-000000000001',
    'e7600000-0000-4000-8000-000000000001',
    'instagram', 'gen4_turbo', repeat('1', 64), repeat('a', 64),
    'e7000000-0000-4000-8000-000000000001', interval '2 days'
  ),
  (
    'e7800000-0000-4000-8000-000000000002',
    'e7100000-0000-4000-8000-000000000001',
    'e7600000-0000-4000-8000-000000000002',
    'wildberries', 'gen4_turbo', repeat('2', 64), repeat('b', 64),
    'e7000000-0000-4000-8000-000000000001', interval '1 day'
  ),
  (
    'e7800000-0000-4000-8000-000000000003',
    'e7100000-0000-4000-8000-000000000001',
    'e7600000-0000-4000-8000-000000000001',
    'telegram', 'seedance2_fast', repeat('3', 64), repeat('c', 64),
    'e7000000-0000-4000-8000-000000000001', interval '4 days'
  ),
  (
    'e7800000-0000-4000-8000-000000000004',
    'e7100000-0000-4000-8000-000000000001',
    'e7600000-0000-4000-8000-000000000003',
    'youtube', 'seedream5_lite', repeat('4', 64), repeat('d', 64),
    'e7000000-0000-4000-8000-000000000001', interval '1 hour'
  ),
  (
    'e7800000-0000-4000-8000-000000000005',
    'e7100000-0000-4000-8000-000000000002',
    'e7600000-0000-4000-8000-000000000005',
    'instagram', 'seedream5_lite', repeat('5', 64), repeat('e', 64),
    'e7000000-0000-4000-8000-000000000004', interval '1 hour'
  )
) fixture(
  id, organization_id, category_id, platform, model, evidence_hash,
  candidate_hash, actor_id, age
);

insert into content_factory.research_outcome_learning_decisions (
  id, organization_id, candidate_id, action, candidate_version,
  candidate_hash, expected_scope_version, reason, confirmed_by,
  confirmation, decision_hash, idempotency_key, decided_at
)
values (
  'e7900000-0000-4000-8000-000000000001',
  'e7100000-0000-4000-8000-000000000001',
  'e7800000-0000-4000-8000-000000000003', 'activate', 1,
  repeat('c', 64), 0, 'Exact active memory fixture.',
  'e7000000-0000-4000-8000-000000000001', true, repeat('6', 64),
  'scope-registry-memory-decision', now() - interval '12 hours'
);
insert into content_factory.research_outcome_learning_memory_versions (
  id, organization_id, market_category_id, platform, model, candidate_kind,
  memory_version, previous_memory_version_id, state, action, candidate_id,
  rollback_target_memory_version_id, decision_id, activated_by, created_at
)
values (
  'e7a00000-0000-4000-8000-000000000001',
  'e7100000-0000-4000-8000-000000000001',
  'e7600000-0000-4000-8000-000000000001',
  'telegram', 'seedance2_fast', 'creative_angle_preference', 1, null,
  'active', 'activate', 'e7800000-0000-4000-8000-000000000003', null,
  'e7900000-0000-4000-8000-000000000001',
  'e7000000-0000-4000-8000-000000000001', now() - interval '12 hours'
);

set local session_replication_role = origin;

update scope_registry_context
set baseline_counts = jsonb_build_object(
  'owner_profile_updated_at', (
    select profile.updated_at
    from content_factory.profiles profile
    where profile.id = 'e7000000-0000-4000-8000-000000000001'
  ),
  'research_runs', (select count(*) from content_factory.product_research_runs),
  'drafts', (select count(*) from content_factory.creative_brief_drafts),
  'stage_artifacts', (select count(*) from content_factory.research_stage_artifacts),
  'stage_decisions', (select count(*) from content_factory.research_stage_decisions),
  'category_bindings', (
    select count(*)
    from content_factory.research_product_market_category_bindings
  ),
  'lineage', (
    select count(*) from content_factory.research_outcome_lineage_snapshots
  ),
  'candidates', (
    select count(*) from content_factory.research_outcome_learning_candidates
  ),
  'outcome_decisions', (
    select count(*) from content_factory.research_outcome_learning_decisions
  ),
  'memory', (
    select count(*)
    from content_factory.research_outcome_learning_memory_versions
  ),
  'command_receipts', (select count(*) from content_factory.command_receipts),
  'events', (select count(*) from content_factory.factory_events),
  'generation_jobs', (select count(*) from content_factory.generation_jobs),
  'placements', (select count(*) from content_factory.placements),
  'metrics', (select count(*) from content_factory.metric_snapshots),
  'provider_authorizations', (
    select count(*) from content_factory.research_execution_authorizations
  )
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub', 'e7000000-0000-4000-8000-000000000001', true
  );
end $$;

update scope_registry_context
set response = public.creator_research_outcome_learning_scopes(
  jsonb_build_object(
    'organization_id', 'e7100000-0000-4000-8000-000000000001',
    'run_id', 'e7300000-0000-4000-8000-000000000001',
    'limit', 50
  )
);

select is(
  (
    select jsonb_agg(key.value order by key.value)
    from scope_registry_context context,
      lateral jsonb_object_keys(context.response) key(value)
  ),
  '["guidance","limit","ok","product_id","returned_scope_count","run_id","scopes","suggested_scope_key","truncated","version"]'::jsonb,
  'registry response has the exact bounded top-level contract'
);
select is(
  (select response ->> 'version' from scope_registry_context),
  'research-outcome-scope-registry-v1',
  'registry response is explicitly versioned'
);
select is(
  (select (response ->> 'returned_scope_count')::integer from scope_registry_context),
  5,
  'approved and three historical ledger sources deduplicate to five exact scopes'
);
select is(
  (select response -> 'truncated' from scope_registry_context),
  'false'::jsonb,
  'full fixture registry is not truncated at the hard maximum'
);
select is(
  (
    select jsonb_agg(scope.value ->> 'scope_key' order by scope.ordinality)
    from scope_registry_context context,
      lateral jsonb_array_elements(context.response -> 'scopes')
        with ordinality scope(value, ordinality)
  ),
  '["e7600000-0000-4000-8000-000000000001:instagram:gen4_turbo","e7600000-0000-4000-8000-000000000001:telegram:seedance2_fast","e7600000-0000-4000-8000-000000000001:youtube:seedance2_fast","e7600000-0000-4000-8000-000000000001:tiktok:seedream5_lite","e7600000-0000-4000-8000-000000000002:wildberries:gen4_turbo"]'::jsonb,
  'ordering is deterministic: current, recommended, active, approved, recency, tuple'
);
select is(
  (select response ->> 'suggested_scope_key' from scope_registry_context),
  'e7600000-0000-4000-8000-000000000001:instagram:gen4_turbo',
  'the unique explicitly approved recommendation is suggested without activation'
);
select is(
  (select response #>> '{guidance,status}' from scope_registry_context),
  'scope_selection_required',
  'multiple exact scopes require an explicit user selection'
);
select is(
  (select response -> 'guidance' from scope_registry_context) - array[
    'status', 'recommended_next_step'
  ]::text[],
  '{"selection_required":true,"automatic_selection":false,"read_only":true,"provider_action":false,"spend_action":false,"generation_action":false,"publication_action":false}'::jsonb,
  'scope guidance is read-only and cannot trigger provider, spend, generation, or publication actions'
);

select is(
  (
    select scope.value -> 'sources'
    from scope_registry_context context,
      lateral jsonb_array_elements(context.response -> 'scopes') scope(value)
    where scope.value ->> 'scope_key' =
      'e7600000-0000-4000-8000-000000000001:instagram:gen4_turbo'
  ),
  '{"approved_scenario":true,"lineage":false,"candidate":true,"memory":false}'::jsonb,
  'approved and candidate provenance deduplicate without losing either source'
);
select is(
  (
    select scope.value -> 'approved_scenario_positions'
    from scope_registry_context context,
      lateral jsonb_array_elements(context.response -> 'scopes') scope(value)
    where scope.value ->> 'scope_key' =
      'e7600000-0000-4000-8000-000000000001:instagram:gen4_turbo'
  ),
  '[2]'::jsonb,
  'approved scenario provenance exposes only its structural position'
);
select is(
  (
    select scope.value -> 'sources'
    from scope_registry_context context,
      lateral jsonb_array_elements(context.response -> 'scopes') scope(value)
    where scope.value ->> 'scope_key' =
      'e7600000-0000-4000-8000-000000000001:telegram:seedance2_fast'
  ),
  '{"approved_scenario":false,"lineage":false,"candidate":true,"memory":true}'::jsonb,
  'latest memory scope retains candidate and memory provenance'
);
select is(
  (
    select jsonb_build_array(
      scope.value -> 'current_memory_state',
      scope.value -> 'current_memory_version'
    )
    from scope_registry_context context,
      lateral jsonb_array_elements(context.response -> 'scopes') scope(value)
    where scope.value ->> 'scope_key' =
      'e7600000-0000-4000-8000-000000000001:telegram:seedance2_fast'
  ),
  '["active",1]'::jsonb,
  'selector can surface an otherwise hidden active advisory memory'
);
select is(
  (
    select scope.value -> 'sources'
    from scope_registry_context context,
      lateral jsonb_array_elements(context.response -> 'scopes') scope(value)
    where scope.value ->> 'scope_key' =
      'e7600000-0000-4000-8000-000000000001:tiktok:seedream5_lite'
  ),
  '{"approved_scenario":false,"lineage":true,"candidate":false,"memory":false}'::jsonb,
  'lineage-only historical scope remains discoverable'
);
select is(
  (
    select jsonb_build_array(
      scope.value #> '{market_category,status}',
      scope.value -> 'current_product_category',
      scope.value -> 'sources'
    )
    from scope_registry_context context,
      lateral jsonb_array_elements(context.response -> 'scopes') scope(value)
    where scope.value ->> 'scope_key' =
      'e7600000-0000-4000-8000-000000000002:wildberries:gen4_turbo'
  ),
  '["retired",false,{"approved_scenario":false,"lineage":false,"candidate":true,"memory":false}]'::jsonb,
  'retired historical category remains visible for exact memory management'
);
select is(
  (
    select count(*)::integer
    from scope_registry_context context,
      lateral jsonb_array_elements(context.response -> 'scopes') scope(value)
    where scope.value ->> 'scope_key' in (
      'e7600000-0000-4000-8000-000000000002:youtube:seedance2_fast',
      'e7600000-0000-4000-8000-000000000002:instagram:gen4_turbo',
      'e7600000-0000-4000-8000-000000000002:vk:seedream5_lite',
      'e7600000-0000-4000-8000-000000000003:youtube:seedream5_lite',
      'e7600000-0000-4000-8000-000000000005:instagram:seedream5_lite'
    )
  ),
  0,
  'no category/scenario Cartesian product, unapproved fallback, unrelated product, or cross-tenant scope leaks'
);
select ok(
  strpos((select response::text from scope_registry_context), 'SECRET_') = 0
  and strpos((select response::text from scope_registry_context), 'generation_mode_reason') = 0,
  'registry never returns raw scenario, prompt, caption, URL, or actor content'
);
select is(
  (
    select count(distinct scope.value ->> 'scope_key')::integer
    from scope_registry_context context,
      lateral jsonb_array_elements(context.response -> 'scopes') scope(value)
  ),
  (select (response ->> 'returned_scope_count')::integer from scope_registry_context),
  'every returned scope key is unique'
);

select is(
  (
    select jsonb_build_object(
      'count', bounded.response -> 'returned_scope_count',
      'truncated', bounded.response -> 'truncated',
      'suggested', bounded.response -> 'suggested_scope_key',
      'status', bounded.response #> '{guidance,status}',
      'selection_required', bounded.response #> '{guidance,selection_required}',
      'keys', (
        select jsonb_agg(scope.value ->> 'scope_key' order by scope.ordinality)
        from jsonb_array_elements(bounded.response -> 'scopes')
          with ordinality scope(value, ordinality)
      )
    )
    from (
      select public.creator_research_outcome_learning_scopes(jsonb_build_object(
        'organization_id', 'e7100000-0000-4000-8000-000000000001',
        'run_id', 'e7300000-0000-4000-8000-000000000001',
        'limit', 1
      )) as response
    ) bounded
  ),
  '{"count":1,"truncated":true,"suggested":null,"status":"scope_list_truncated","selection_required":true,"keys":["e7600000-0000-4000-8000-000000000001:instagram:gen4_turbo"]}'::jsonb,
  'limit+1 exposes truncation without pretending a bounded result is unique'
);

select is(
  public.creator_research_outcome_learning_scopes(jsonb_build_object(
    'organization_id', 'e7100000-0000-4000-8000-000000000001',
    'run_id', 'e7300000-0000-4000-8000-000000000003'
  )) #> '{guidance}',
  '{"status":"no_exact_scopes","recommended_next_step":"approve_scenario_and_confirm_exact_market_category","selection_required":false,"automatic_selection":false,"read_only":true,"provider_action":false,"spend_action":false,"generation_action":false,"publication_action":false}'::jsonb,
  'approved draft without an approved scenarios-stage decision yields honest empty guidance'
);

select throws_ok(
  $$select public.creator_research_outcome_learning_scopes(jsonb_build_object(
    'organization_id', 'e7100000-0000-4000-8000-000000000001',
    'run_id', 'e7300000-0000-4000-8000-000000000001',
    'unexpected', true
  ))$$,
  '22023', 'research_outcome_scope_registry_payload_invalid',
  'unknown payload fields fail closed'
);
select throws_ok(
  $$select public.creator_research_outcome_learning_scopes(jsonb_build_object(
    'organization_id', 'e7100000-0000-4000-8000-000000000001',
    'run_id', 'e7300000-0000-4000-8000-000000000001',
    'limit', 51
  ))$$,
  '22023', 'research_outcome_scope_registry_limit_invalid',
  'scope registry hard limit rejects values above fifty'
);
select throws_ok(
  $$select public.creator_research_outcome_learning_scopes(jsonb_build_object(
    'organization_id', 'e7100000-0000-4000-8000-000000000001',
    'run_id', 'e7300000-0000-4000-8000-000000000001',
    'limit', 1.5
  ))$$,
  '22023', 'research_outcome_scope_registry_limit_invalid',
  'fractional limits fail closed'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'e7000000-0000-4000-8000-000000000002', true
  );
end $$;
select is(
  public.creator_research_outcome_learning_scopes(jsonb_build_object(
    'organization_id', 'e7100000-0000-4000-8000-000000000001',
    'run_id', 'e7300000-0000-4000-8000-000000000001'
  )) ->> 'returned_scope_count',
  '5',
  'reviewer may inspect exact structural scopes without mutation authority'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'e7000000-0000-4000-8000-000000000003', true
  );
end $$;
select throws_ok(
  $$select public.creator_research_outcome_learning_scopes(jsonb_build_object(
    'organization_id', 'e7100000-0000-4000-8000-000000000001',
    'run_id', 'e7300000-0000-4000-8000-000000000001'
  ))$$,
  '42501', 'role_not_allowed',
  'viewer role cannot inspect the outcome scope registry'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'e7000000-0000-4000-8000-000000000004', true
  );
end $$;
select throws_ok(
  $$select public.creator_research_outcome_learning_scopes(jsonb_build_object(
    'organization_id', 'e7100000-0000-4000-8000-000000000002',
    'run_id', 'e7300000-0000-4000-8000-000000000001'
  ))$$,
  '22023', 'research_run_not_found',
  'cross-tenant run UUID is indistinguishable from a missing run'
);

select is(
  (select baseline_counts from scope_registry_context),
  jsonb_build_object(
    'owner_profile_updated_at', (
      select profile.updated_at
      from content_factory.profiles profile
      where profile.id = 'e7000000-0000-4000-8000-000000000001'
    ),
    'research_runs', (select count(*) from content_factory.product_research_runs),
    'drafts', (select count(*) from content_factory.creative_brief_drafts),
    'stage_artifacts', (select count(*) from content_factory.research_stage_artifacts),
    'stage_decisions', (select count(*) from content_factory.research_stage_decisions),
    'category_bindings', (
      select count(*)
      from content_factory.research_product_market_category_bindings
    ),
    'lineage', (
      select count(*) from content_factory.research_outcome_lineage_snapshots
    ),
    'candidates', (
      select count(*) from content_factory.research_outcome_learning_candidates
    ),
    'outcome_decisions', (
      select count(*) from content_factory.research_outcome_learning_decisions
    ),
    'memory', (
      select count(*)
      from content_factory.research_outcome_learning_memory_versions
    ),
    'command_receipts', (select count(*) from content_factory.command_receipts),
    'events', (select count(*) from content_factory.factory_events),
    'generation_jobs', (select count(*) from content_factory.generation_jobs),
    'placements', (select count(*) from content_factory.placements),
    'metrics', (select count(*) from content_factory.metric_snapshots),
    'provider_authorizations', (
      select count(*) from content_factory.research_execution_authorizations
    )
  ),
  'all success, bounded, empty, invalid, reviewer, role, and tenant calls are zero-write'
);

select * from finish();
rollback;
