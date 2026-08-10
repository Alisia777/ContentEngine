begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

create or replace function pg_temp.stage_control_brief()
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'summary', 'Correctable stage-control fixture',
    'category_analysis', jsonb_build_object(
      'category_name', 'Hair styling',
      'maturity', 'growing',
      'source_ids', jsonb_build_array('stage-control-source-1')
    ),
    'competitor_analysis', jsonb_build_object(
      'coverage', 'sufficient',
      'competitors', jsonb_build_array(jsonb_build_object(
        'name', 'Competitor A',
        'source_ids', jsonb_build_array('stage-control-source-2')
      ))
    ),
    'trend_analysis', jsonb_build_object(
      'as_of', '2026-08-03',
      'signals', jsonb_build_array(jsonb_build_object(
        'signal', 'demonstration hook',
        'direction', 'growing',
        'source_ids', jsonb_build_array(
          'stage-control-source-1', 'stage-control-source-2'
        )
      ))
    ),
    'guidance', jsonb_build_object(
      'status', 'ready_for_brief',
      'recommended_next_step', 'Review the bounded experiment',
      'reason', 'Independent evidence is available'
    ),
    'facts', jsonb_build_array(jsonb_build_object(
      'statement', 'Fixture fact'
    )),
    'audience', jsonb_build_array(jsonb_build_object(
      'name', 'Home stylists'
    )),
    'scenarios', jsonb_build_array(jsonb_build_object(
      'title', 'Demonstration',
      'hook', 'Show the structure without copying source prose'
    )),
    'task_blueprint', jsonb_build_object(
      'title', 'Produce one bounded experiment'
    )
  )
$$;

select has_table(
  'content_factory', 'research_stage_branches',
  'versioned stage branches table exists'
);
select has_table(
  'content_factory', 'research_stage_head_events',
  'append-only stage head events table exists'
);
select has_table(
  'content_factory', 'research_stage_heads',
  'materialized exact stage heads table exists'
);
select has_table(
  'content_factory', 'research_stage_recompute_requests',
  'bounded recompute requests table exists'
);
select has_column(
  'content_factory', 'research_stage_artifacts', 'input_dependencies',
  'stage artifacts retain exact input dependencies'
);
select has_column(
  'content_factory', 'research_stage_artifacts', 'input_dependency_hash',
  'stage artifacts retain a canonical input dependency hash'
);
select has_column(
  'content_factory', 'research_stage_recompute_requests',
  'expected_branch_revision_hash',
  'saved recomputes retain the exact confirmed seven-head branch token'
);

select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_stage_branches'::regclass),
     ('content_factory.research_stage_head_events'::regclass),
     ('content_factory.research_stage_heads'::regclass),
     ('content_factory.research_stage_recompute_requests'::regclass)
   ) protected(table_oid)
   join pg_class relation on relation.oid = protected.table_oid
   where relation.relrowsecurity),
  4,
  'every stage-control table has RLS enabled'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_stage_branches'::regclass),
     ('content_factory.research_stage_head_events'::regclass),
     ('content_factory.research_stage_heads'::regclass),
     ('content_factory.research_stage_recompute_requests'::regclass)
   ) protected(table_oid)
   cross join (values ('select'), ('insert'), ('update'), ('delete')) privilege(name)
   where has_table_privilege('authenticated', table_oid, privilege.name)
      or has_table_privilege('anon', table_oid, privilege.name)),
  0,
  'browser roles have no direct access to stage-control tables'
);

select has_function(
  'public', 'creator_control_research_stage', array['jsonb'],
  'exact stage-control mutation RPC exists'
);
select has_function(
  'public', 'creator_research_stage_control_status', array['jsonb'],
  'bounded stage-control status RPC exists'
);
select has_function(
  'public', 'system_apply_research_stage_recompute', array['jsonb'],
  'service-only recompute apply RPC exists'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.creator_control_research_stage(jsonb)', 'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.creator_research_stage_control_status(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon', 'public.creator_control_research_stage(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_research_stage_control_status(jsonb)', 'execute'
  ),
  'only authenticated browser users reach the two public stage-control seams'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_apply_research_stage_recompute(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_apply_research_stage_recompute(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_apply_research_stage_recompute(jsonb)', 'execute'
  ),
  'only service_role can apply a completed recompute child'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'content_factory_private'
     and procedure.proname in (
       'write_research_stage_head_event',
       'sync_research_stage_main_heads',
       'materialize_research_stage_main_draft',
       'create_research_stage_user_input',
       'research_stage_branch_dependencies',
       'research_stage_branch_revision_hash',
       'research_stage_current_dependency_state',
       'refresh_research_stage_branch_states',
       'assert_research_stage_draft_ready'
     )
     and has_function_privilege(
       'authenticated', procedure.oid, 'execute'
     )),
  0,
  'authenticated callers cannot bypass private stage writers and approval guard'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    where trigger_row.tgrelid =
      'content_factory.research_stage_branches'::regclass
      and trigger_row.tgname = 'reject_research_stage_branch_mutation'
      and trigger_row.tgenabled <> 'D'
  )
  and exists (
    select 1
    from pg_trigger trigger_row
    where trigger_row.tgrelid =
      'content_factory.research_stage_head_events'::regclass
      and trigger_row.tgname = 'reject_research_stage_head_event_mutation'
      and trigger_row.tgenabled <> 'D'
  )
  and exists (
    select 1
    from pg_trigger trigger_row
    where trigger_row.tgrelid =
      'content_factory.research_stage_heads'::regclass
      and trigger_row.tgname = 'guard_research_stage_head_mutation'
      and trigger_row.tgenabled <> 'D'
  )
  and exists (
    select 1
    from pg_trigger trigger_row
    where trigger_row.tgrelid =
      'content_factory.research_stage_recompute_requests'::regclass
      and trigger_row.tgname = 'guard_research_stage_recompute_mutation'
      and trigger_row.tgenabled <> 'D'
  ),
  'history is append-only and mutable projections are controlled by guards'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'f9000000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'stage-control-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Stage Control Owner"}'::jsonb,
  now(), now()
), (
  'f9000000-0000-4000-8000-000000000002'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'stage-control-reviewer@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Stage Control Reviewer"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'fa000000-0000-4000-8000-000000000001',
  'Stage Control Fixture', 'stage-control-fixture', 'active'
);
insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'fa000000-0000-4000-8000-000000000001',
  'f9000000-0000-4000-8000-000000000001', 'owner', 'active'
), (
  'fa000000-0000-4000-8000-000000000001',
  'f9000000-0000-4000-8000-000000000002', 'reviewer', 'active'
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'fa500000-0000-4000-8000-000000000001',
  'fa000000-0000-4000-8000-000000000001', null,
  'Stage Control project', 'blue', 'project', null,
  'active', 1024,
  'f9000000-0000-4000-8000-000000000001',
  'f9000000-0000-4000-8000-000000000001'
), (
  'fa500000-0000-4000-8000-000000000002',
  'fa000000-0000-4000-8000-000000000001', null,
  'Unrelated stage control project', 'violet', 'project', null,
  'active', 2048,
  'f9000000-0000-4000-8000-000000000001',
  'f9000000-0000-4000-8000-000000000001'
);

insert into content_factory.workspace_project_memberships (
  organization_id, project_id, profile_id, access_role, status,
  granted_by, updated_by
) values (
  'fa000000-0000-4000-8000-000000000001',
  'fa500000-0000-4000-8000-000000000001',
  'f9000000-0000-4000-8000-000000000002',
  'member', 'active',
  'f9000000-0000-4000-8000-000000000001',
  'f9000000-0000-4000-8000-000000000001'
);
-- This test exercises stage concurrency and correction semantics, not course
-- grading. Use the same explicit, attributable owner waiver supported by the
-- production selected-waiver workflow instead of fabricating training proof.
insert into content_factory.training_access_waivers (
  organization_id, profile_id, scope, status, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'fa000000-0000-4000-8000-000000000001',
  'f9000000-0000-4000-8000-000000000001',
  'workspace_generation', 'active', 'owner', 'owner',
  'TEST-ONLY owner waiver for research stage-control pgTAP coverage.',
  'f9000000-0000-4000-8000-000000000001'
);
insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  'fb000000-0000-4000-8000-000000000001',
  'fa000000-0000-4000-8000-000000000001',
  'STAGE-CONTROL-1', 'Stage control product', 'active', '{}'::jsonb,
  'f9000000-0000-4000-8000-000000000001'
);
insert into content_factory.product_research_runs (
  id, organization_id, project_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at
) values (
  'fc000000-0000-4000-8000-000000000001',
  'fa000000-0000-4000-8000-000000000001',
  'fa500000-0000-4000-8000-000000000001',
  'fb000000-0000-4000-8000-000000000001',
  'f9000000-0000-4000-8000-000000000001',
  'completed',
  '{"objective":"stage control fixture","marketplace_url":"https://example.test/product","source_media_ids":[],"platforms":["youtube"]}'::jsonb,
  '{}'::jsonb, repeat('1', 64), repeat('2', 64),
  'stage-control-run-0001', now()
);
insert into content_factory.product_research_sources (
  id, organization_id, run_id, product_id, created_by, source_type,
  title, content_hash, trust_level, extracted_facts, metadata, fetched_at
) values (
  'fd000000-0000-4000-8000-000000000001',
  'fa000000-0000-4000-8000-000000000001',
  'fc000000-0000-4000-8000-000000000001',
  'fb000000-0000-4000-8000-000000000001',
  'f9000000-0000-4000-8000-000000000001',
  'user_input', 'Stage control source one', repeat('3', 64), 'first_party',
  '[]'::jsonb,
  '{"model_source_id":"stage-control-source-1"}'::jsonb, now()
), (
  'fd000000-0000-4000-8000-000000000002',
  'fa000000-0000-4000-8000-000000000001',
  'fc000000-0000-4000-8000-000000000001',
  'fb000000-0000-4000-8000-000000000001',
  'f9000000-0000-4000-8000-000000000001',
  'user_input', 'Stage control source two', repeat('4', 64), 'first_party',
  '[]'::jsonb,
  '{"model_source_id":"stage-control-source-2"}'::jsonb, now()
);
insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, previous_draft_id, created_by,
  origin, version, status, title, brief, source_ids, task_blueprint, content_hash
) values (
  'fe000000-0000-4000-8000-000000000001',
  'fa000000-0000-4000-8000-000000000001',
  'fc000000-0000-4000-8000-000000000001',
  'fb000000-0000-4000-8000-000000000001', null,
  'f9000000-0000-4000-8000-000000000001',
  'ai', 1, 'draft', 'Stage control brief',
  pg_temp.stage_control_brief(),
  jsonb_build_array(
    'fd000000-0000-4000-8000-000000000001'::text,
    'fd000000-0000-4000-8000-000000000002'::text
  ),
  jsonb_build_array(jsonb_build_object(
    'title', 'Produce one bounded experiment'
  )),
  repeat('5', 64)
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'f9000000-0000-4000-8000-000000000001', true
  );
  perform set_config('request.jwt.claim.role', 'authenticated', true);
end;
$$;

create temporary table stage_control_context as
select branch.id as branch_id,
  head.head_event_id as original_head_event_id,
  head.artifact_id as original_artifact_id,
  artifact.content_hash as original_content_hash,
  null::jsonb as patch_result,
  null::jsonb as fork_result,
  null::jsonb as reject_result,
  null::jsonb as revert_result,
  null::jsonb as recompute_result,
  null::jsonb as cancel_result
from content_factory.research_stage_branches branch
join content_factory.research_stage_heads head
  on head.organization_id = branch.organization_id
 and head.run_id = branch.run_id
 and head.branch_id = branch.id
 and head.stage = 'category'
join content_factory.research_stage_artifacts artifact
  on artifact.organization_id = head.organization_id
 and artifact.run_id = head.run_id
 and artifact.stage = head.stage
 and artifact.id = head.artifact_id
where branch.organization_id = 'fa000000-0000-4000-8000-000000000001'
  and branch.run_id = 'fc000000-0000-4000-8000-000000000001'
  and branch.branch_key = 'main';

select is(
  (select count(*)::integer from stage_control_context), 1,
  'first v2 draft creates exactly one main branch'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_heads head
   where head.organization_id = 'fa000000-0000-4000-8000-000000000001'
     and head.run_id = 'fc000000-0000-4000-8000-000000000001'
     and head.branch_id = (select branch_id from stage_control_context)),
  7,
  'first v2 draft creates seven exact main heads'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_artifacts artifact
   where artifact.organization_id = 'fa000000-0000-4000-8000-000000000001'
     and artifact.run_id = 'fc000000-0000-4000-8000-000000000001'
     and jsonb_typeof(artifact.input_dependencies) = 'object'
     and artifact.input_dependency_hash ~ '^[0-9a-f]{64}$'),
  7,
  'all baseline artifacts bind canonical input snapshots and hashes'
);

select throws_ok(
  $$select public.creator_research_stage_control_status(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001'
  ))$$,
  '22023', 'project_id_invalid',
  'status requires the exact project identifier in every browser request'
);
select throws_ok(
  $$select public.creator_research_stage_control_status(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000002',
    'run_id', 'fc000000-0000-4000-8000-000000000001'
  ))$$,
  '42501', 'research_run_project_scope_mismatch',
  'status rejects a run from another accessible project'
);

select is(
  jsonb_array_length(public.creator_research_stage_control_status(
    jsonb_build_object(
      'organization_id', 'fa000000-0000-4000-8000-000000000001',
      'project_id', 'fa500000-0000-4000-8000-000000000001',
      'run_id', 'fc000000-0000-4000-8000-000000000001',
      'history_limit', 3
    )
  ) -> 'heads'),
  7,
  'status returns the exact seven-head projection'
);
select matches(
  public.creator_research_stage_control_status(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001'
  )) #>> '{selected_branch,branch_revision_hash}',
  '^[0-9a-f]{64}$',
  'status returns the canonical exact branch revision token'
);
select is(
  jsonb_array_length(public.creator_research_stage_control_status(
    jsonb_build_object(
      'organization_id', 'fa000000-0000-4000-8000-000000000001',
      'project_id', 'fa500000-0000-4000-8000-000000000001',
      'run_id', 'fc000000-0000-4000-8000-000000000001',
      'history_limit', 3
    )
  ) -> 'history'),
  3,
  'status history is bounded by the caller-selected server limit'
);
select throws_ok(
  $$select public.creator_research_stage_control_status(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'history_limit', 101
  ))$$,
  '22023', 'research_stage_control_history_limit_invalid',
  'status rejects unbounded history requests'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub',
    'f9000000-0000-4000-8000-000000000002', true
  );
end $$;
select lives_ok(
  $$select public.creator_research_stage_control_status(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001'
  ))$$,
  'reviewer can inspect the exact stage-control graph'
);
select throws_ok(
  $$select public.creator_control_research_stage(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'branch_id', (select branch_id from stage_control_context),
    'stage', 'category', 'action', 'reject',
    'expected_head_event_id',
      (select original_head_event_id from stage_control_context),
    'expected_artifact_id',
      (select original_artifact_id from stage_control_context),
    'expected_content_hash',
      (select original_content_hash from stage_control_context),
    'expected_branch_revision_hash',
      content_factory_private.research_stage_branch_revision_hash(
        'fa000000-0000-4000-8000-000000000001',
        'fc000000-0000-4000-8000-000000000001',
        (select branch_id from stage_control_context)
      ),
    'confirmation', true, 'reason', 'Reviewer may not mutate stages',
    'idempotency_key', 'stage-control-reviewer-reject-0001'
  ))$$,
  '42501', 'role_not_allowed',
  'reviewer cannot mutate a research stage'
);
do $$ begin
  perform set_config(
    'request.jwt.claim.sub',
    'f9000000-0000-4000-8000-000000000001', true
  );
end $$;

select throws_ok(
  $$select public.creator_control_research_stage(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'branch_id', (select branch_id from stage_control_context),
    'stage', 'category', 'action', 'patch',
    'expected_head_event_id',
      (select original_head_event_id from stage_control_context),
    'expected_artifact_id',
      (select original_artifact_id from stage_control_context),
    'expected_content_hash', repeat('0', 64),
    'expected_branch_revision_hash',
      content_factory_private.research_stage_branch_revision_hash(
        'fa000000-0000-4000-8000-000000000001',
        'fc000000-0000-4000-8000-000000000001',
        (select branch_id from stage_control_context)
      ),
    'replacement', '{"category_name":"Wrong stale write"}'::jsonb,
    'confirmation', true,
    'user_input', 'This must lose the optimistic concurrency race',
    'reason', 'Exercise exact stale-head protection',
    'idempotency_key', 'stage-control-stale-patch-0001'
  ))$$,
  '55000', 'research_stage_head_stale',
  'mutation requires the exact current event artifact and content hash'
);
select throws_ok(
  $$select public.creator_control_research_stage(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'branch_id', (select branch_id from stage_control_context),
    'stage', 'category', 'action', 'patch',
    'expected_head_event_id',
      (select original_head_event_id from stage_control_context),
    'expected_artifact_id',
      (select original_artifact_id from stage_control_context),
    'expected_content_hash',
      (select original_content_hash from stage_control_context),
    'expected_branch_revision_hash',
      content_factory_private.research_stage_branch_revision_hash(
        'fa000000-0000-4000-8000-000000000001',
        'fc000000-0000-4000-8000-000000000001',
        (select branch_id from stage_control_context)
      ),
    'replacement', '{"category_name":"Unconfirmed write"}'::jsonb,
    'confirmation', false,
    'user_input', 'This change is intentionally unconfirmed',
    'reason', 'Exercise explicit confirmation gate',
    'idempotency_key', 'stage-control-unconfirmed-patch-0001'
  ))$$,
  '22023', 'research_stage_control_invalid',
  'mutation fails closed without exact confirmation'
);
select throws_ok(
  $$select public.creator_control_research_stage(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'branch_id', (select branch_id from stage_control_context),
    'stage', 'category', 'action', 'patch',
    'expected_head_event_id',
      (select original_head_event_id from stage_control_context),
    'expected_artifact_id',
      (select original_artifact_id from stage_control_context),
    'expected_content_hash',
      (select original_content_hash from stage_control_context),
    'expected_branch_revision_hash', repeat('f', 64),
    'replacement', '{"category_name":"Stale graph write"}'::jsonb,
    'confirmation', true,
    'user_input', 'This command confirms only an obsolete seven-stage graph',
    'reason', 'Exercise exact full-branch optimistic concurrency',
    'idempotency_key', 'stage-control-stale-branch-patch-0001'
  ))$$,
  '55000', 'research_stage_branch_revision_stale',
  'mutation confirms the exact seven-head branch, not one selected head only'
);

update stage_control_context context
set patch_result = public.creator_control_research_stage(jsonb_build_object(
  'organization_id', 'fa000000-0000-4000-8000-000000000001',
  'project_id', 'fa500000-0000-4000-8000-000000000001',
  'run_id', 'fc000000-0000-4000-8000-000000000001',
  'branch_id', context.branch_id,
  'stage', 'category', 'action', 'patch',
  'expected_head_event_id', context.original_head_event_id,
  'expected_artifact_id', context.original_artifact_id,
  'expected_content_hash', context.original_content_hash,
  'expected_branch_revision_hash',
    content_factory_private.research_stage_branch_revision_hash(
      'fa000000-0000-4000-8000-000000000001',
      'fc000000-0000-4000-8000-000000000001', context.branch_id
    ),
  'replacement', (
    select artifact.payload || jsonb_build_object(
      'maturity', 'early_test',
      'user_boundary', 'Do not infer category leadership'
    )
    from content_factory.research_stage_artifacts artifact
    where artifact.organization_id =
      'fa000000-0000-4000-8000-000000000001'
      and artifact.id = context.original_artifact_id
  ),
  'confirmation', true,
  'user_input', 'Treat this category as an early test, not a mature market',
  'reason', 'Correct the category interpretation without rewriting history',
  'idempotency_key', 'stage-control-category-patch-0001'
));

select ok(
  (select (patch_result ->> 'ok')::boolean from stage_control_context)
  and (select patch_result ->> 'action' = 'patch'
       from stage_control_context),
  'exact category patch creates a durable control result'
);
select isnt(
  (select original_artifact_id from stage_control_context),
  (select (patch_result #>> '{head,artifact_id}')::uuid
   from stage_control_context),
  'patch moves the category head to a new immutable artifact'
);
select is(
  (select artifact.parent_artifact_id
   from content_factory.research_stage_artifacts artifact
   where artifact.id = (
     select (patch_result #>> '{head,artifact_id}')::uuid
     from stage_control_context
   )),
  (select original_artifact_id from stage_control_context),
  'patched artifact retains its exact parent version'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_heads head
   where head.organization_id = 'fa000000-0000-4000-8000-000000000001'
     and head.run_id = 'fc000000-0000-4000-8000-000000000001'
     and head.branch_id = (select branch_id from stage_control_context)
     and head.state = 'stale_dependency'),
  5,
  'category patch marks all five downstream heads stale without deleting them'
);
select ok(
  not exists (
    select 1
    from content_factory.research_stage_heads stale_head
    cross join lateral jsonb_array_elements_text(
      stale_head.stale_due_to_artifact_ids
    ) stale_id(value)
    where stale_head.organization_id =
      'fa000000-0000-4000-8000-000000000001'
      and stale_head.run_id = 'fc000000-0000-4000-8000-000000000001'
      and stale_head.branch_id = (select branch_id from stage_control_context)
      and not exists (
        select 1
        from content_factory.research_stage_heads current_upstream
        where current_upstream.organization_id = stale_head.organization_id
          and current_upstream.run_id = stale_head.run_id
          and current_upstream.branch_id = stale_head.branch_id
          and current_upstream.artifact_id = stale_id.value::uuid
          and content_factory_private.research_stage_rank(
            current_upstream.stage
          ) < content_factory_private.research_stage_rank(stale_head.stage)
      )
  ),
  'stale causes reference only current upstream heads, never historical unions'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_heads head
   where head.organization_id = 'fa000000-0000-4000-8000-000000000001'
     and head.run_id = 'fc000000-0000-4000-8000-000000000001'
     and head.branch_id = (select branch_id from stage_control_context)
     and head.stage in ('sources', 'category')
     and head.state = 'current'),
  2,
  'upstream source and corrected category remain current'
);

create or replace function pg_temp.assert_brief_patch_preserves_staleness()
returns void
language plpgsql
as $$
declare
  branch_id_value uuid;
  brief_head content_factory.research_stage_heads%rowtype;
  brief_artifact content_factory.research_stage_artifacts%rowtype;
begin
  select context.branch_id into branch_id_value
  from stage_control_context context;
  select head.* into brief_head
  from content_factory.research_stage_heads head
  where head.organization_id = 'fa000000-0000-4000-8000-000000000001'
    and head.run_id = 'fc000000-0000-4000-8000-000000000001'
    and head.branch_id = branch_id_value
    and head.stage = 'brief';
  select artifact.* into brief_artifact
  from content_factory.research_stage_artifacts artifact
  where artifact.organization_id = brief_head.organization_id
    and artifact.run_id = brief_head.run_id
    and artifact.stage = brief_head.stage
    and artifact.id = brief_head.artifact_id;

  perform public.creator_control_research_stage(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'branch_id', branch_id_value,
    'stage', 'brief', 'action', 'patch',
    'expected_head_event_id', brief_head.head_event_id,
    'expected_artifact_id', brief_head.artifact_id,
    'expected_content_hash', brief_artifact.content_hash,
    'expected_branch_revision_hash',
      content_factory_private.research_stage_branch_revision_hash(
        'fa000000-0000-4000-8000-000000000001',
        'fc000000-0000-4000-8000-000000000001', branch_id_value
      ),
    'replacement', brief_artifact.payload || jsonb_build_object(
      'brief', (brief_artifact.payload -> 'brief') || jsonb_build_object(
        'human_boundary', 'Do not clear unresolved upstream analysis'
      )
    ),
    'confirmation', true,
    'user_input',
      'Keep the unresolved competitor, trend, and guidance dependencies visible',
    'reason', 'Regression probe for a downstream brief correction',
    'idempotency_key', 'stage-control-brief-regression-0001'
  ));

  if (
    select count(*)
    from content_factory.research_stage_heads head
    where head.organization_id = 'fa000000-0000-4000-8000-000000000001'
      and head.run_id = 'fc000000-0000-4000-8000-000000000001'
      and head.branch_id = branch_id_value
      and head.stage in ('competitors', 'trends', 'guidance')
      and head.state = 'stale_dependency'
  ) <> 3 then
    raise exception using
      errcode = 'P0001',
      message = 'brief_patch_cleared_upstream_staleness';
  end if;
  raise exception using
    errcode = 'P0001',
    message = 'brief_patch_preserves_upstream_staleness';
end;
$$;

select throws_ok(
  $$select pg_temp.assert_brief_patch_preserves_staleness()$$,
  'P0001', 'brief_patch_preserves_upstream_staleness',
  'D1 category patch then brief patch keeps competitor trend and guidance stale'
);

select is(
  (select source.source_type
   from content_factory.product_research_sources source
   where source.id = (
     select event.correction_source_id
     from content_factory.research_stage_head_events event
     where event.id = (
       select (patch_result #>> '{head,head_event_id}')::uuid
       from stage_control_context
     )
   )),
  'user_input',
  'human correction is retained as a separate first-party input source'
);

select throws_ok(
  $$update content_factory.creative_brief_drafts draft
    set status = 'approved',
        approved_by = 'f9000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where draft.id = (
      select (patch_result ->> 'draft_id')::uuid
      from stage_control_context
    )$$,
  '55000', 'research_stage_dependencies_stale',
  'approval trigger rejects a draft whose downstream heads are stale'
);

update stage_control_context context
set fork_result = public.creator_control_research_stage(jsonb_build_object(
  'organization_id', 'fa000000-0000-4000-8000-000000000001',
  'project_id', 'fa500000-0000-4000-8000-000000000001',
  'run_id', 'fc000000-0000-4000-8000-000000000001',
  'branch_id', context.branch_id,
  'stage', 'category', 'action', 'fork',
  'expected_head_event_id', context.patch_result #>> '{head,head_event_id}',
  'expected_artifact_id', context.patch_result #>> '{head,artifact_id}',
  'expected_content_hash', (
    select artifact.content_hash
    from content_factory.research_stage_artifacts artifact
    where artifact.id =
      (context.patch_result #>> '{head,artifact_id}')::uuid
  ),
  'expected_branch_revision_hash',
    content_factory_private.research_stage_branch_revision_hash(
      'fa000000-0000-4000-8000-000000000001',
      'fc000000-0000-4000-8000-000000000001', context.branch_id
    ),
  'new_branch_key', 'category-alternative',
  'confirmation', true,
  'reason', 'Compare an alternative without mutating the main branch',
  'idempotency_key', 'stage-control-fork-0001'
));
select is(
  (select count(*)::integer
   from content_factory.research_stage_heads head
   where head.organization_id = 'fa000000-0000-4000-8000-000000000001'
     and head.run_id = 'fc000000-0000-4000-8000-000000000001'
     and head.branch_id = (
       select (fork_result ->> 'branch_id')::uuid from stage_control_context
     )),
  7,
  'fork snapshots all seven exact heads into an independent branch'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_heads fork_head
   join content_factory.research_stage_heads main_head
     on main_head.organization_id = fork_head.organization_id
    and main_head.run_id = fork_head.run_id
    and main_head.stage = fork_head.stage
    and main_head.branch_id = (select branch_id from stage_control_context)
    and main_head.artifact_id = fork_head.artifact_id
   where fork_head.organization_id =
     'fa000000-0000-4000-8000-000000000001'
     and fork_head.run_id = 'fc000000-0000-4000-8000-000000000001'
     and fork_head.branch_id = (
       select (fork_result ->> 'branch_id')::uuid from stage_control_context
     )),
  7,
  'fork starts from the exact source branch artifact snapshot'
);
select ok(
  public.creator_research_stage_control_status(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'branch_id', (
      select fork_result ->> 'branch_id' from stage_control_context
    )
  )) #>> '{guidance,status}' = 'branch_comparison'
  and not exists (
    select 1
    from jsonb_array_elements(
      public.creator_research_stage_control_status(jsonb_build_object(
        'organization_id', 'fa000000-0000-4000-8000-000000000001',
        'project_id', 'fa500000-0000-4000-8000-000000000001',
        'run_id', 'fc000000-0000-4000-8000-000000000001',
        'branch_id', (
          select fork_result ->> 'branch_id' from stage_control_context
        )
      )) -> 'heads'
    ) item(value)
    where jsonb_array_length(item.value -> 'allowed_actions') <> 0
  ),
  'comparison branch status is explicit and exposes no mutations'
);

select throws_ok(
  $$select public.creator_control_research_stage(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'branch_id', (select fork_result ->> 'branch_id'
                  from stage_control_context),
    'stage', 'category', 'action', 'reject',
    'expected_head_event_id', (select fork_result #>> '{head,head_event_id}'
                               from stage_control_context),
    'expected_artifact_id', (select fork_result #>> '{head,artifact_id}'
                             from stage_control_context),
    'expected_content_hash', (
      select artifact.content_hash
      from content_factory.research_stage_artifacts artifact
      where artifact.id = (
        select (fork_result #>> '{head,artifact_id}')::uuid
        from stage_control_context
      )
    ),
    'expected_branch_revision_hash', (
      select fork_result ->> 'branch_revision_hash'
      from stage_control_context
    ),
    'confirmation', true,
    'reason', 'Comparison snapshots cannot be mutated',
    'idempotency_key', 'stage-control-branch-reject-0001'
  ))$$,
  '55000', 'research_stage_comparison_branch_read_only',
  'fork is an explicitly read-only comparison snapshot'
);

update stage_control_context context
set reject_result = public.creator_control_research_stage(jsonb_build_object(
  'organization_id', 'fa000000-0000-4000-8000-000000000001',
  'project_id', 'fa500000-0000-4000-8000-000000000001',
  'run_id', 'fc000000-0000-4000-8000-000000000001',
  'branch_id', context.branch_id,
  'stage', 'category', 'action', 'reject',
  'expected_head_event_id', context.patch_result #>> '{head,head_event_id}',
  'expected_artifact_id', context.patch_result #>> '{head,artifact_id}',
  'expected_content_hash', (
    select artifact.content_hash
    from content_factory.research_stage_artifacts artifact
    where artifact.id =
      (context.patch_result #>> '{head,artifact_id}')::uuid
  ),
  'expected_branch_revision_hash',
    content_factory_private.research_stage_branch_revision_hash(
      'fa000000-0000-4000-8000-000000000001',
      'fc000000-0000-4000-8000-000000000001', context.branch_id
    ),
  'confirmation', true,
  'reason', 'Reject the current main category interpretation explicitly',
  'idempotency_key', 'stage-control-main-reject-0001'
));
select is(
  (select reject_result #>> '{head,state}' from stage_control_context),
  'rejected',
  'reject explicitly marks the selected main stage rejected'
);
select is(
  (select state
   from content_factory.research_stage_heads head
   where head.organization_id = 'fa000000-0000-4000-8000-000000000001'
     and head.run_id = 'fc000000-0000-4000-8000-000000000001'
     and head.branch_id = (
       select (fork_result ->> 'branch_id')::uuid from stage_control_context
     )
     and head.stage = 'category'),
  'current',
  'main rejection never mutates the frozen comparison snapshot'
);

update stage_control_context context
set recompute_result = public.creator_control_research_stage(
  jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'branch_id', context.branch_id,
    'stage', 'category', 'action', 'recompute',
    'expected_head_event_id', context.reject_result #>> '{head,head_event_id}',
    'expected_artifact_id', context.reject_result #>> '{head,artifact_id}',
    'expected_content_hash', (
      select artifact.content_hash
      from content_factory.research_stage_artifacts artifact
      where artifact.id =
        (context.reject_result #>> '{head,artifact_id}')::uuid
    ),
    'expected_branch_revision_hash',
      content_factory_private.research_stage_branch_revision_hash(
        'fa000000-0000-4000-8000-000000000001',
        'fc000000-0000-4000-8000-000000000001', context.branch_id
      ),
    'paid_analysis_ack', true,
    'confirmation', true,
    'user_input',
      'Recheck the rejected category with fresh independently cited evidence',
    'reason', 'Prepare one saved recompute without invoking the provider',
    'idempotency_key', 'stage-control-category-recompute-0001'
  )
);
select ok(
  (select recompute_result #>> '{recompute_request,status}' = 'queued'
   from stage_control_context)
  and (select (
    recompute_result #>> '{recompute_request,max_provider_attempts}'
  )::integer = 1 from stage_control_context),
  'recompute prepare saves one queued child with a one-attempt ceiling'
);
select ok(
  exists (
    select 1
    from content_factory.research_stage_recompute_requests request
    where request.id = (
      select (recompute_result #>> '{recompute_request,request_id}')::uuid
      from stage_control_context
    )
      and request.status = 'queued'
      and request.provider_attempt_count = 0
      and request.expected_branch_revision_hash =
        request.input_snapshot ->> 'branch_revision_hash'
  )
  and not exists (
    select 1
    from content_factory.research_run_provider_bindings binding
    where binding.run_id = (
      select (recompute_result #>> '{recompute_request,child_run_id}')::uuid
      from stage_control_context
    )
  ),
  'prepare performs no provider attempt and binds the exact branch token'
);
select ok(
  (
    public.creator_research_stage_control_status(jsonb_build_object(
      'organization_id', 'fa000000-0000-4000-8000-000000000001',
      'project_id', 'fa500000-0000-4000-8000-000000000001',
      'run_id', 'fc000000-0000-4000-8000-000000000001'
    )) #>> '{active_recompute,can_cancel}'
  )::boolean
  and public.creator_research_stage_control_status(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001'
  )) #>> '{guidance,recommended_next_action}'
    = 'invoke_saved_recompute_or_cancel',
  'queued recompute is explicitly resumable or cancellable without retry'
);

create or replace function pg_temp.assert_branch_change_suppresses_invoke()
returns void
language plpgsql
as $$
declare
  branch_id_value uuid;
  source_head content_factory.research_stage_heads%rowtype;
  status_value jsonb;
begin
  select context.branch_id into branch_id_value
  from stage_control_context context;
  select head.* into source_head
  from content_factory.research_stage_heads head
  where head.organization_id = 'fa000000-0000-4000-8000-000000000001'
    and head.run_id = 'fc000000-0000-4000-8000-000000000001'
    and head.branch_id = branch_id_value
    and head.stage = 'sources';

  perform content_factory_private.write_research_stage_head_event(
    source_head.organization_id, source_head.run_id, source_head.branch_id,
    extensions.gen_random_uuid(), source_head.stage, 'dependency_refresh',
    source_head.state, source_head.artifact_id, source_head.dependency_hash,
    source_head.stale_due_to_artifact_ids, source_head.current_draft_id,
    null, 'Simulate an independent root branch command after prepare',
    'f9000000-0000-4000-8000-000000000001', 'system', repeat('d', 64)
  );
  status_value := public.creator_research_stage_control_status(
    jsonb_build_object(
      'organization_id', 'fa000000-0000-4000-8000-000000000001',
      'project_id', 'fa500000-0000-4000-8000-000000000001',
      'run_id', 'fc000000-0000-4000-8000-000000000001'
    )
  );
  if status_value #> '{active_recompute,invoke}'
       is distinct from 'null'::jsonb then
    raise exception using
      errcode = 'P0001',
      message = 'branch_changed_recompute_exposes_invoke';
  end if;
  raise exception using
    errcode = 'P0001',
    message = 'branch_changed_recompute_suppresses_invoke';
end;
$$;

select throws_ok(
  $$select pg_temp.assert_branch_change_suppresses_invoke()$$,
  'P0001', 'branch_changed_recompute_suppresses_invoke',
  'a queued recompute never exposes invoke after the root branch changes'
);

update stage_control_context context
set cancel_result = public.creator_control_research_stage(
  jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'branch_id', context.branch_id,
    'stage', 'category', 'action', 'cancel',
    'expected_head_event_id',
      context.recompute_result #>> '{head,head_event_id}',
    'expected_artifact_id', context.recompute_result #>> '{head,artifact_id}',
    'expected_content_hash', (
      select artifact.content_hash
      from content_factory.research_stage_artifacts artifact
      where artifact.id =
        (context.recompute_result #>> '{head,artifact_id}')::uuid
    ),
    'expected_branch_revision_hash',
      context.recompute_result ->> 'branch_revision_hash',
    'confirmation', true,
    'reason', 'Cancel the saved recompute before any provider claim',
    'idempotency_key', 'stage-control-category-cancel-0001'
  )
);
select ok(
  (select cancel_result #>> '{recompute_request,status}' = 'superseded'
   from stage_control_context)
  and (select cancel_result #>> '{recompute_request,error_code}'
       = 'cancelled_by_user' from stage_control_context),
  'explicit queued cancel terminalizes the saved request without Edge'
);
select ok(
  exists (
    select 1
    from content_factory.research_stage_recompute_requests request
    join content_factory.product_research_runs child
      on child.organization_id = request.organization_id
     and child.id = request.child_run_id
    where request.id = (
      select (recompute_result #>> '{recompute_request,request_id}')::uuid
      from stage_control_context
    )
      and request.status = 'superseded'
      and request.provider_attempt_count = 0
      and child.status = 'cancelled'
  )
  and public.creator_research_stage_control_status(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001'
  )) -> 'active_recompute' = 'null'::jsonb,
  'cancel releases the active branch slot and never consumes an attempt'
);
select ok(
  exists (
    select 1
    from content_factory.research_stage_recompute_requests request
    join content_factory.research_stage_head_events expected
      on expected.organization_id = request.organization_id
     and expected.id = request.expected_head_event_id
    join content_factory.research_stage_heads head
      on head.organization_id = request.organization_id
     and head.run_id = request.run_id
     and head.branch_id = request.branch_id
     and head.stage = request.stage
    where request.id = (
      select (recompute_result #>> '{recompute_request,request_id}')::uuid
      from stage_control_context
    )
      and head.state = 'rejected'
      and head.artifact_id = expected.artifact_id
      and head.dependency_hash = expected.dependency_hash
      and head.stale_due_to_artifact_ids =
        expected.stale_due_to_artifact_ids
      and head.current_draft_id = expected.draft_id
  ),
  'pure cancel restores the exact rejected semantic head from before queue'
);

update stage_control_context context
set revert_result = public.creator_control_research_stage(jsonb_build_object(
  'organization_id', 'fa000000-0000-4000-8000-000000000001',
  'project_id', 'fa500000-0000-4000-8000-000000000001',
  'run_id', 'fc000000-0000-4000-8000-000000000001',
  'branch_id', context.branch_id,
  'stage', 'category', 'action', 'revert',
  'expected_head_event_id', context.cancel_result #>> '{head,head_event_id}',
  'expected_artifact_id', context.cancel_result #>> '{head,artifact_id}',
  'expected_content_hash', (
    select artifact.content_hash
    from content_factory.research_stage_artifacts artifact
    where artifact.id =
      (context.cancel_result #>> '{head,artifact_id}')::uuid
  ),
  'expected_branch_revision_hash',
    content_factory_private.research_stage_branch_revision_hash(
      'fa000000-0000-4000-8000-000000000001',
      'fc000000-0000-4000-8000-000000000001', context.branch_id
    ),
  'target_artifact_id', context.original_artifact_id,
  'confirmation', true,
  'reason', 'Restore the historical category artifact on editable main',
  'idempotency_key', 'stage-control-main-revert-0001'
));
select is(
  (select (revert_result #>> '{head,artifact_id}')::uuid
   from stage_control_context),
  (select original_artifact_id from stage_control_context),
  'revert moves the main head to an existing historical artifact'
);
select ok(
  exists (
    select 1
    from content_factory.research_stage_head_events event
    where event.id = (
      select (revert_result #>> '{head,head_event_id}')::uuid
      from stage_control_context
    )
      and event.action = 'revert'
      and event.prior_artifact_id = (
        select (reject_result #>> '{head,artifact_id}')::uuid
        from stage_control_context
      )
  ),
  'revert is append-only and retains the prior head lineage'
);

select throws_ok(
  $$select public.creator_control_research_stage(jsonb_build_object(
    'organization_id', 'fa000000-0000-4000-8000-000000000001',
    'project_id', 'fa500000-0000-4000-8000-000000000001',
    'run_id', 'fc000000-0000-4000-8000-000000000001',
    'branch_id', (select branch_id from stage_control_context),
    'stage', 'sources', 'action', 'recompute',
    'expected_head_event_id', (
      select head.head_event_id
      from content_factory.research_stage_heads head
      where head.organization_id =
        'fa000000-0000-4000-8000-000000000001'
        and head.run_id = 'fc000000-0000-4000-8000-000000000001'
        and head.branch_id = (select branch_id from stage_control_context)
        and head.stage = 'sources'
    ),
    'expected_artifact_id', (
      select head.artifact_id
      from content_factory.research_stage_heads head
      where head.organization_id =
        'fa000000-0000-4000-8000-000000000001'
        and head.run_id = 'fc000000-0000-4000-8000-000000000001'
        and head.branch_id = (select branch_id from stage_control_context)
        and head.stage = 'sources'
    ),
    'expected_content_hash', (
      select artifact.content_hash
      from content_factory.research_stage_heads head
      join content_factory.research_stage_artifacts artifact
        on artifact.organization_id = head.organization_id
       and artifact.run_id = head.run_id
       and artifact.stage = head.stage
       and artifact.id = head.artifact_id
      where head.organization_id =
        'fa000000-0000-4000-8000-000000000001'
        and head.run_id = 'fc000000-0000-4000-8000-000000000001'
        and head.branch_id = (select branch_id from stage_control_context)
        and head.stage = 'sources'
    ),
    'expected_branch_revision_hash',
      content_factory_private.research_stage_branch_revision_hash(
        'fa000000-0000-4000-8000-000000000001',
        'fc000000-0000-4000-8000-000000000001',
        (select branch_id from stage_control_context)
      ),
    'paid_analysis_ack', true, 'confirmation', true,
    'user_input', 'A source list must be corrected explicitly, not recomputed',
    'reason', 'Exercise the non-provider source-stage boundary',
    'idempotency_key', 'stage-control-source-recompute-0001'
  ))$$,
  '22023', 'research_stage_recompute_invalid',
  'sources cannot trigger a paid recompute child'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_recompute_requests request
   where request.organization_id =
     'fa000000-0000-4000-8000-000000000001'
     and request.status in ('queued', 'processing')),
  0,
  'rejected recompute validation leaves no active saved request'
);
select ok(
  (select count(*) = 1
     and count(*) filter (where request.status = 'superseded') = 1
   from content_factory.research_stage_recompute_requests request
   where request.organization_id =
     'fa000000-0000-4000-8000-000000000001'),
  'cancelled recompute remains as one superseded audit row and no extra child'
);

do $$ begin
  perform set_config(
    'content_factory.research_stage_control_write', 'off', true
  );
end $$;
select throws_ok(
  $$update content_factory.research_stage_heads
    set state = state
    where organization_id = 'fa000000-0000-4000-8000-000000000001'
      and run_id = 'fc000000-0000-4000-8000-000000000001'
      and branch_id = (select branch_id from stage_control_context)
      and stage = 'sources'$$,
  '55000', 'research_stage_heads_controlled_mutation_only',
  'even a no-op direct head update is rejected outside the controlled writer'
);
select throws_ok(
  $$delete from content_factory.research_stage_head_events
    where organization_id = 'fa000000-0000-4000-8000-000000000001'
      and run_id = 'fc000000-0000-4000-8000-000000000001'
      and branch_id = (select branch_id from stage_control_context)$$,
  '55000', 'research_stage_head_events_append_only',
  'head event history cannot be deleted'
);

select * from finish();
rollback;
