begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

create or replace function pg_temp.stage_brief(
  next_step text,
  first_source_ref text default 'source-main-1',
  second_source_ref text default 'source-main-2'
)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'summary', 'Bounded category research fixture',
    'category_analysis', jsonb_build_object(
      'category_name', 'Hair styling',
      'maturity', 'growing',
      'source_ids', jsonb_build_array(first_source_ref)
    ),
    'competitor_analysis', jsonb_build_object(
      'coverage', 'sufficient',
      'competitors', jsonb_build_array(jsonb_build_object(
        'name', 'Competitor A',
        'source_ids', jsonb_build_array(second_source_ref)
      ))
    ),
    'trend_analysis', jsonb_build_object(
      'as_of', '2026-08-03',
      'signals', jsonb_build_array(jsonb_build_object(
        'signal', 'demonstration hook',
        'direction', 'growing',
        'source_ids', jsonb_build_array(first_source_ref, second_source_ref)
      ))
    ),
    'guidance', jsonb_build_object(
      'status', 'ready_for_brief',
      'recommended_next_step', next_step,
      'reason', 'Independent evidence is available'
    ),
    'facts', jsonb_build_array(jsonb_build_object('statement', 'fixture fact')),
    'audience', jsonb_build_array(jsonb_build_object('name', 'home stylists')),
    'scenarios', jsonb_build_array(jsonb_build_object(
      'title', 'Demonstration',
      'hook', 'Show the structure without copying source prose'
    )),
    'task_blueprint', jsonb_build_object('title', 'Produce bounded experiment'),
    'creative_potential', jsonb_build_object(
      'method', 'prepublication_heuristic_not_probability',
      'score', 60
    )
  )
$$;

-- TEST-ONLY authorization fixture for exercising the real approval RPC.
create or replace function pg_temp.grant_refreshed_course_gate(
  p_organization_id uuid,
  p_profile_id uuid,
  p_key_prefix text
)
returns void
language plpgsql
set search_path = ''
as $course_gate_fixture$
#variable_conflict use_variable
declare
  module_row record;
  attempt_id_value uuid;
  answers_value jsonb;
begin
  for module_row in
    select module.code,
      jsonb_array_length(module.content #> '{knowledge_check,questions}') as question_count
    from content_factory.training_modules module
    where module.module_type = 'course' and module.is_active
    order by module.order_index
  loop
    select coalesce(jsonb_object_agg(
      question.code, answer_key.correct_answers order by question.order_index
    ), '{}'::jsonb)
      into answers_value
    from content_factory.training_questions question
    join content_factory_private.training_answer_keys answer_key
      on answer_key.question_code = question.code
    where question.module_code = module_row.code
      and question.order_index between 901 and 1000
      and strpos(question.code, 'course_check_' || module_row.code || '_') = 1;

    if module_row.question_count < 1
       or (select count(*) from pg_catalog.jsonb_object_keys(answers_value))
         <> module_row.question_count then
      raise exception using
        errcode = '55000', message = 'test_course_gate_fixture_invalid';
    end if;

    insert into content_factory.training_attempts (
      organization_id, profile_id, module_code, status, score,
      correct_count, answered_count, question_count, passed, answers,
      request_hash, idempotency_key
    ) values (
      p_organization_id, p_profile_id, module_row.code, 'completed', 1,
      module_row.question_count, module_row.question_count,
      module_row.question_count, true, answers_value,
      content_factory_private.json_hash(jsonb_build_object(
        'module_code', module_row.code, 'answers', answers_value
      )),
      left('course-check:' || p_key_prefix || ':' || module_row.code, 180)
    )
    on conflict (organization_id, profile_id, idempotency_key) do update set
      module_code = excluded.module_code,
      status = excluded.status,
      score = excluded.score,
      correct_count = excluded.correct_count,
      answered_count = excluded.answered_count,
      question_count = excluded.question_count,
      passed = excluded.passed,
      answers = excluded.answers,
      request_hash = excluded.request_hash,
      completed_at = now()
    returning id into attempt_id_value;

    insert into content_factory.training_certifications (
      organization_id, profile_id, module_code, attempt_id, status
    ) values (
      p_organization_id, p_profile_id, module_row.code, attempt_id_value, 'passed'
    )
    on conflict on constraint training_certifications_org_profile_module_uq
    do update set
      attempt_id = excluded.attempt_id,
      status = 'passed',
      granted_at = now(),
      expires_at = null;
  end loop;
end;
$course_gate_fixture$;

select has_table(
  'content_factory', 'research_stage_artifacts',
  'research stage artifacts table exists'
);
select has_table(
  'content_factory', 'research_stage_draft_bindings',
  'draft to artifact bindings table exists'
);
select has_table(
  'content_factory', 'research_stage_binding_evidence',
  'binding evidence table exists'
);
select has_table(
  'content_factory', 'research_stage_decisions',
  'append-only stage decisions table exists'
);

select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_stage_artifacts'::regclass),
     ('content_factory.research_stage_draft_bindings'::regclass),
     ('content_factory.research_stage_binding_evidence'::regclass),
     ('content_factory.research_stage_decisions'::regclass)
   ) protected(table_oid)
   join pg_class relation on relation.oid = protected.table_oid
   where relation.relrowsecurity),
  4,
  'every ledger table has RLS enabled'
);

select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_stage_artifacts'::regclass),
     ('content_factory.research_stage_draft_bindings'::regclass),
     ('content_factory.research_stage_binding_evidence'::regclass),
     ('content_factory.research_stage_decisions'::regclass)
   ) protected(table_oid)
   where has_table_privilege('authenticated', table_oid, 'select')),
  0,
  'authenticated has no direct ledger reads'
);

select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_stage_artifacts'::regclass),
     ('content_factory.research_stage_draft_bindings'::regclass),
     ('content_factory.research_stage_binding_evidence'::regclass),
     ('content_factory.research_stage_decisions'::regclass)
   ) protected(table_oid)
   cross join (values ('insert'), ('update'), ('delete')) action(privilege_name)
   where has_table_privilege('authenticated', table_oid, privilege_name)),
  0,
  'authenticated has no direct ledger writes'
);

select has_function(
  'public', 'creator_research_stage_ledger', array['jsonb'],
  'tenant-safe stage ledger read RPC exists'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.creator_research_stage_ledger(jsonb)', 'execute'
  ),
  'authenticated may execute the read RPC'
);
select ok(
  not has_function_privilege(
    'anon', 'public.creator_research_stage_ledger(jsonb)', 'execute'
  ),
  'anon may not execute the read RPC'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'content_factory_private'
     and procedure.proname in (
       'capture_research_stage_draft',
       'record_research_stage_decisions'
     )
     and has_function_privilege('authenticated', procedure.oid, 'execute')),
  0,
  'authenticated cannot call private ledger writers'
);
select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.research_stage_decisions'::regclass
      and constraint_row.contype = 'c'
      and pg_get_constraintdef(constraint_row.oid) like '%generated%'
      and pg_get_constraintdef(constraint_row.oid) like '%patched%'
      and pg_get_constraintdef(constraint_row.oid) like '%approved%'
      and pg_get_constraintdef(constraint_row.oid) like '%rejected%'
      and pg_get_constraintdef(constraint_row.oid) like '%reverted%'
  ),
  'decision vocabulary includes generated patched approved rejected and reverted'
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
  ('98000000-0000-4000-8000-000000000001', 'stage-owner@example.test', 'Stage Owner'),
  ('98000000-0000-4000-8000-000000000002', 'stage-admin@example.test', 'Stage Admin'),
  ('98000000-0000-4000-8000-000000000003', 'stage-producer@example.test', 'Stage Producer'),
  ('98000000-0000-4000-8000-000000000004', 'stage-reviewer@example.test', 'Stage Reviewer'),
  ('98000000-0000-4000-8000-000000000005', 'stage-viewer@example.test', 'Stage Viewer')
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  ('98100000-0000-4000-8000-000000000001', 'Stage Ledger Main', 'stage-ledger-main', 'active'),
  ('98100000-0000-4000-8000-000000000002', 'Stage Ledger Other', 'stage-ledger-other', 'active');

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  ('98100000-0000-4000-8000-000000000001', '98000000-0000-4000-8000-000000000001', 'owner', 'active'),
  ('98100000-0000-4000-8000-000000000001', '98000000-0000-4000-8000-000000000002', 'admin', 'active'),
  ('98100000-0000-4000-8000-000000000001', '98000000-0000-4000-8000-000000000003', 'producer', 'active'),
  ('98100000-0000-4000-8000-000000000001', '98000000-0000-4000-8000-000000000004', 'reviewer', 'active'),
  ('98100000-0000-4000-8000-000000000001', '98000000-0000-4000-8000-000000000005', 'viewer', 'active'),
  ('98100000-0000-4000-8000-000000000002', '98000000-0000-4000-8000-000000000001', 'owner', 'active');

do $$
declare
  attempt_id_value uuid;
begin
  perform pg_temp.grant_refreshed_course_gate(
    '98100000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'stage-ledger-owner'
  );
  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  ) values (
    '98100000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'operator_final_exam', 'completed', 1, 12, 12, 12, true, '{}'::jsonb,
    repeat('e', 64), 'stage-ledger-final-exam'
  ) returning id into attempt_id_value;
  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code, attempt_id, status
  ) values (
    '98100000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'operator_final_exam', attempt_id_value, 'passed'
  );
end;
$$;

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
values
  (
    '98200000-0000-4000-8000-000000000001',
    '98100000-0000-4000-8000-000000000001',
    'STAGE-LEDGER-1', 'Stage ledger product', 'active', '{}'::jsonb,
    '98000000-0000-4000-8000-000000000001'
  ),
  (
    '98200000-0000-4000-8000-000000000002',
    '98100000-0000-4000-8000-000000000002',
    'STAGE-LEDGER-2', 'Other tenant product', 'active', '{}'::jsonb,
    '98000000-0000-4000-8000-000000000001'
  );

insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at
)
values
  (
    '98300000-0000-4000-8000-000000000001',
    '98100000-0000-4000-8000-000000000001',
    '98200000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'completed', '{"objective":"stage ledger fixture"}'::jsonb,
    '{}'::jsonb, repeat('1', 64), repeat('2', 64),
    'stage-ledger-run-main', now()
  ),
  (
    '98300000-0000-4000-8000-000000000002',
    '98100000-0000-4000-8000-000000000002',
    '98200000-0000-4000-8000-000000000002',
    '98000000-0000-4000-8000-000000000001',
    'completed', '{"objective":"other tenant fixture"}'::jsonb,
    '{}'::jsonb, repeat('3', 64), repeat('4', 64),
    'stage-ledger-run-other', now()
  );

insert into content_factory.product_research_sources (
  id, organization_id, run_id, product_id, created_by, source_type,
  title, content_hash, trust_level, extracted_facts, metadata, fetched_at
)
values
  (
    '98400000-0000-4000-8000-000000000001',
    '98100000-0000-4000-8000-000000000001',
    '98300000-0000-4000-8000-000000000001',
    '98200000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'user_input', 'Main source one', repeat('5', 64), 'first_party',
    '[]'::jsonb, '{"model_source_id":"source-main-1"}'::jsonb, now()
  ),
  (
    '98400000-0000-4000-8000-000000000002',
    '98100000-0000-4000-8000-000000000001',
    '98300000-0000-4000-8000-000000000001',
    '98200000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'user_input', 'Main source two', repeat('6', 64), 'first_party',
    '[]'::jsonb, '{"model_source_id":"source-main-2"}'::jsonb, now()
  ),
  (
    '98400000-0000-4000-8000-000000000003',
    '98100000-0000-4000-8000-000000000002',
    '98300000-0000-4000-8000-000000000002',
    '98200000-0000-4000-8000-000000000002',
    '98000000-0000-4000-8000-000000000001',
    'user_input', 'Other tenant source', repeat('7', 64), 'first_party',
    '[]'::jsonb, '{"model_source_id":"source-other-1"}'::jsonb, now()
  );

insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, previous_draft_id, created_by,
  origin, version, status, title, brief, source_ids, task_blueprint, content_hash
)
values (
  '98500000-0000-4000-8000-000000000001',
  '98100000-0000-4000-8000-000000000001',
  '98300000-0000-4000-8000-000000000001',
  '98200000-0000-4000-8000-000000000001',
  null,
  '98000000-0000-4000-8000-000000000001',
  'ai', 1, 'draft', 'Stage ledger brief',
  pg_temp.stage_brief('Review the corroborated trend'),
  jsonb_build_array(
    '98400000-0000-4000-8000-000000000001'::text,
    '98400000-0000-4000-8000-000000000002'::text
  ),
  jsonb_build_array(jsonb_build_object('title', 'Create scenario')),
  repeat('8', 64)
);

select is(
  (select count(*)::integer
   from content_factory.research_stage_artifacts artifact
   where artifact.organization_id = '98100000-0000-4000-8000-000000000001'
     and artifact.run_id = '98300000-0000-4000-8000-000000000001'),
  7,
  'AI insert creates exactly seven stage artifacts'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_draft_bindings binding
   where binding.organization_id = '98100000-0000-4000-8000-000000000001'
     and binding.draft_id = '98500000-0000-4000-8000-000000000001'),
  7,
  'AI draft binds every stage exactly once'
);
select is(
  (select jsonb_agg(binding.stage order by
     content_factory_private.research_stage_rank(binding.stage))
   from content_factory.research_stage_draft_bindings binding
   where binding.organization_id = '98100000-0000-4000-8000-000000000001'
     and binding.draft_id = '98500000-0000-4000-8000-000000000001'),
  '["sources","category","competitors","trends","guidance","brief","scenarios"]'::jsonb,
  'stage set and order are exact'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_binding_evidence evidence
   where evidence.organization_id = '98100000-0000-4000-8000-000000000001'
     and evidence.draft_id = '98500000-0000-4000-8000-000000000001'),
  12,
  'stage bindings snapshot their exact referenced evidence with safe fallback'
);
select is(
  (select jsonb_agg(evidence.source_id order by evidence.ordinal)
   from content_factory.research_stage_binding_evidence evidence
   where evidence.organization_id = '98100000-0000-4000-8000-000000000001'
     and evidence.draft_id = '98500000-0000-4000-8000-000000000001'
     and evidence.stage = 'category'),
  '["98400000-0000-4000-8000-000000000001"]'::jsonb,
  'category evidence maps its model source reference to one exact run source'
);
select is(
  (select jsonb_agg(evidence.source_id order by evidence.ordinal)
   from content_factory.research_stage_binding_evidence evidence
   where evidence.organization_id = '98100000-0000-4000-8000-000000000001'
     and evidence.draft_id = '98500000-0000-4000-8000-000000000001'
     and evidence.stage = 'competitors'),
  '["98400000-0000-4000-8000-000000000002"]'::jsonb,
  'competitor evidence never inherits an unrelated source'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_binding_evidence evidence
   where evidence.organization_id = '98100000-0000-4000-8000-000000000001'
     and evidence.draft_id = '98500000-0000-4000-8000-000000000001'
     and evidence.stage = 'trends'),
  2,
  'trend evidence preserves both references declared by that stage'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.draft_id = '98500000-0000-4000-8000-000000000001'
     and decision.decision = 'generated'),
  7,
  'AI insert appends generated decisions for all stages'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.draft_id = '98500000-0000-4000-8000-000000000001'
     and decision.decision = 'patched'),
  0,
  'AI insert never forges a human patched decision'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_artifacts artifact
   where artifact.organization_id = '98100000-0000-4000-8000-000000000001'
     and artifact.run_id = '98300000-0000-4000-8000-000000000001'
     and artifact.origin = 'ai'
     and artifact.actor_id = '98000000-0000-4000-8000-000000000001'),
  7,
  'artifact creation stores exact AI origin and actor'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_draft_bindings binding
   join content_factory.research_stage_artifacts artifact
     on artifact.organization_id = binding.organization_id
    and artifact.run_id = binding.run_id
    and artifact.stage = binding.stage
    and artifact.id = binding.artifact_id
   where binding.organization_id = '98100000-0000-4000-8000-000000000001'
     and binding.draft_id = '98500000-0000-4000-8000-000000000001'
     and artifact.content_hash ~ '^[0-9a-f]{64}$'
     and binding.dependency_hash ~ '^[0-9a-f]{64}$'),
  7,
  'every binding carries content and dependency hashes'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_artifacts artifact
   where artifact.organization_id = '98100000-0000-4000-8000-000000000001'
     and artifact.run_id = '98300000-0000-4000-8000-000000000001'
     and artifact.version = 1
     and artifact.parent_artifact_id is null),
  7,
  'first stage versions have no parent'
);

insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, previous_draft_id, created_by,
  origin, version, status, title, brief, source_ids, task_blueprint, content_hash
)
values (
  '98500000-0000-4000-8000-000000000002',
  '98100000-0000-4000-8000-000000000001',
  '98300000-0000-4000-8000-000000000001',
  '98200000-0000-4000-8000-000000000001',
  '98500000-0000-4000-8000-000000000001',
  '98000000-0000-4000-8000-000000000003',
  'human', 2, 'draft', 'Stage ledger brief',
  pg_temp.stage_brief('Review the corroborated trend') || jsonb_build_object(
    'human_stage_corrections', jsonb_build_object(
      'sources', '',
      'category', '',
      'competitors', '',
      'trends', '',
      'strategy', 'Ask the user to approve the bounded experiment'
    )
  ),
  jsonb_build_array(
    '98400000-0000-4000-8000-000000000001'::text,
    '98400000-0000-4000-8000-000000000002'::text
  ),
  jsonb_build_array(jsonb_build_object('title', 'Create scenario')),
  repeat('9', 64)
);

select is(
  (select count(*)::integer
   from content_factory.research_stage_artifacts artifact
   where artifact.organization_id = '98100000-0000-4000-8000-000000000001'
     and artifact.run_id = '98300000-0000-4000-8000-000000000001'),
  8,
  'changing only guidance creates only one new artifact'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_draft_bindings newer
   join content_factory.research_stage_draft_bindings older
     on older.organization_id = newer.organization_id
    and older.run_id = newer.run_id
    and older.stage = newer.stage
    and older.artifact_id = newer.artifact_id
    and older.draft_id = '98500000-0000-4000-8000-000000000001'
   where newer.organization_id = '98100000-0000-4000-8000-000000000001'
     and newer.draft_id = '98500000-0000-4000-8000-000000000002'),
  6,
  'six unchanged stage payloads reuse their original artifacts'
);
select isnt(
  (select artifact_id
   from content_factory.research_stage_draft_bindings
   where organization_id = '98100000-0000-4000-8000-000000000001'
     and draft_id = '98500000-0000-4000-8000-000000000001'
     and stage = 'guidance'),
  (select artifact_id
   from content_factory.research_stage_draft_bindings
   where organization_id = '98100000-0000-4000-8000-000000000001'
     and draft_id = '98500000-0000-4000-8000-000000000002'
     and stage = 'guidance'),
  'changed guidance binds a different artifact'
);
select ok(
  exists (
    select 1
    from content_factory.research_stage_artifacts newer
    join content_factory.research_stage_draft_bindings binding
      on binding.organization_id = newer.organization_id
     and binding.run_id = newer.run_id
     and binding.stage = newer.stage
     and binding.artifact_id = newer.id
    join content_factory.research_stage_draft_bindings older_binding
      on older_binding.organization_id = binding.organization_id
     and older_binding.run_id = binding.run_id
     and older_binding.stage = binding.stage
     and older_binding.draft_id = '98500000-0000-4000-8000-000000000001'
    where binding.organization_id = '98100000-0000-4000-8000-000000000001'
      and binding.draft_id = '98500000-0000-4000-8000-000000000002'
      and binding.stage = 'guidance'
      and newer.version = 2
      and newer.parent_artifact_id = older_binding.artifact_id
  ),
  'changed guidance records version two with exact parent lineage'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.draft_id = '98500000-0000-4000-8000-000000000002'
     and decision.decision = 'patched'
     and decision.actor_id = '98000000-0000-4000-8000-000000000003'
     and decision.origin = 'human'),
  1,
  'human insert appends a patched decision only for the corrected stage'
);
select is(
  (select decision.stage
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.draft_id = '98500000-0000-4000-8000-000000000002'
     and decision.decision = 'patched'),
  'guidance',
  'human correction is attributed to its exact stage'
);
select isnt(
  (select dependency_hash
   from content_factory.research_stage_draft_bindings
   where organization_id = '98100000-0000-4000-8000-000000000001'
     and draft_id = '98500000-0000-4000-8000-000000000001'
     and stage = 'brief'),
  (select dependency_hash
   from content_factory.research_stage_draft_bindings
   where organization_id = '98100000-0000-4000-8000-000000000001'
     and draft_id = '98500000-0000-4000-8000-000000000002'
     and stage = 'brief'),
  'binding dependency changes when an upstream guidance artifact changes'
);

insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, previous_draft_id, created_by,
  origin, version, status, title, brief, source_ids, task_blueprint, content_hash
)
values (
  '98500000-0000-4000-8000-000000000003',
  '98100000-0000-4000-8000-000000000001',
  '98300000-0000-4000-8000-000000000001',
  '98200000-0000-4000-8000-000000000001',
  '98500000-0000-4000-8000-000000000002',
  '98000000-0000-4000-8000-000000000004',
  'human', 3, 'draft', 'Stage ledger brief',
  pg_temp.stage_brief('Review the corroborated trend') || jsonb_build_object(
    'human_stage_corrections', jsonb_build_object(
      'sources', '',
      'category', '',
      'competitors', '',
      'trends', '',
      'strategy', 'Ask the user to approve the bounded experiment'
    )
  ),
  jsonb_build_array(
    '98400000-0000-4000-8000-000000000001'::text,
    '98400000-0000-4000-8000-000000000002'::text
  ),
  jsonb_build_array(jsonb_build_object('title', 'Create scenario')),
  repeat('a', 64)
);

select is(
  (select count(*)::integer
   from content_factory.research_stage_artifacts artifact
   where artifact.organization_id = '98100000-0000-4000-8000-000000000001'
     and artifact.run_id = '98300000-0000-4000-8000-000000000001'),
  8,
  'identical third draft creates no artifacts'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_draft_bindings third_binding
   join content_factory.research_stage_draft_bindings second_binding
     on second_binding.organization_id = third_binding.organization_id
    and second_binding.run_id = third_binding.run_id
    and second_binding.stage = third_binding.stage
    and second_binding.artifact_id = third_binding.artifact_id
    and second_binding.draft_id = '98500000-0000-4000-8000-000000000002'
   where third_binding.organization_id = '98100000-0000-4000-8000-000000000001'
     and third_binding.draft_id = '98500000-0000-4000-8000-000000000003'),
  7,
  'identical third draft reuses all seven artifacts'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_draft_bindings third_binding
   join content_factory.research_stage_draft_bindings second_binding
     on second_binding.organization_id = third_binding.organization_id
    and second_binding.run_id = third_binding.run_id
    and second_binding.stage = third_binding.stage
    and second_binding.dependency_hash = third_binding.dependency_hash
    and second_binding.draft_id = '98500000-0000-4000-8000-000000000002'
   where third_binding.organization_id = '98100000-0000-4000-8000-000000000001'
     and third_binding.draft_id = '98500000-0000-4000-8000-000000000003'),
  7,
  'identical third draft reproduces deterministic dependency hashes'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.draft_id = '98500000-0000-4000-8000-000000000003'
     and decision.decision = 'patched'),
  0,
  'identical human draft does not forge patched history'
);

select lives_ok(
  $$select content_factory_private.capture_research_stage_draft(draft)
    from content_factory.creative_brief_drafts draft
    where draft.id = '98500000-0000-4000-8000-000000000003'$$,
  'replaying private capture is idempotent'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_artifacts artifact
   where artifact.organization_id = '98100000-0000-4000-8000-000000000001'
     and artifact.run_id = '98300000-0000-4000-8000-000000000001'),
  8,
  'capture replay creates no artifacts'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_draft_bindings binding
   where binding.organization_id = '98100000-0000-4000-8000-000000000001'
     and binding.run_id = '98300000-0000-4000-8000-000000000001'),
  21,
  'capture replay creates no bindings'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.run_id = '98300000-0000-4000-8000-000000000001'
     and decision.decision = 'patched'),
  1,
  'capture replay creates no decisions'
);

select throws_ok(
  $$update content_factory.creative_brief_drafts
    set status = 'approved',
        approved_by = '98000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where id = '98500000-0000-4000-8000-000000000001'$$,
  '55000', 'research_v2_human_draft_required',
  'an initial AI v2 draft can never be approved directly'
);
select throws_ok(
  $$update content_factory.creative_brief_drafts
    set status = 'approved',
        approved_by = '98000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where id = '98500000-0000-4000-8000-000000000003'$$,
  '55000', 'research_stage_dependencies_stale',
  'approval rejects a human copy whose unchanged downstream stages are stale'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.draft_id = '98500000-0000-4000-8000-000000000003'
     and decision.decision = 'approved'
     and decision.actor_id = '98000000-0000-4000-8000-000000000001'
     and decision.origin = 'human'),
  0,
  'rejected stale approval appends no approval decisions'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.draft_id = '98500000-0000-4000-8000-000000000003'
     and decision.decision in ('patched', 'approved')),
  0,
  'unchanged stale human draft has neither patched nor approved decisions'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.draft_id = '98500000-0000-4000-8000-000000000002'
     and decision.stage = 'guidance'
     and decision.decision = 'patched'),
  1,
  'approval preserves the earlier exact-stage correction history'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.draft_id = '98500000-0000-4000-8000-000000000001'
     and decision.decision = 'generated'),
  7,
  'approval preserves original generated history'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.run_id = '98300000-0000-4000-8000-000000000001'),
  8,
  'decision timeline retains generated and patched events after blocked approval'
);
select lives_ok(
  $$update content_factory.creative_brief_drafts
    set status = status
    where id = '98500000-0000-4000-8000-000000000003'$$,
  'draft no-op replay is accepted by the existing draft guard'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_decisions decision
   where decision.organization_id = '98100000-0000-4000-8000-000000000001'
     and decision.draft_id = '98500000-0000-4000-8000-000000000003'
     and decision.decision = 'approved'),
  0,
  'blocked approval never creates decisions on no-op replay'
);

-- Isolated v2 run for save/approval invariants and the real browser RPC flow.
insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at
) values (
  '98300000-0000-4000-8000-000000000003',
  '98100000-0000-4000-8000-000000000001',
  '98200000-0000-4000-8000-000000000001',
  '98000000-0000-4000-8000-000000000001',
  'completed', '{"objective":"approval invariant fixture"}'::jsonb,
  '{}'::jsonb, repeat('c', 64), repeat('d', 64),
  'stage-ledger-run-approval', now()
);

insert into content_factory.product_research_sources (
  id, organization_id, run_id, product_id, created_by, source_type,
  title, content_hash, trust_level, extracted_facts, metadata, fetched_at
) values
  (
    '98400000-0000-4000-8000-000000000004',
    '98100000-0000-4000-8000-000000000001',
    '98300000-0000-4000-8000-000000000003',
    '98200000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'user_input', 'Approval source one', repeat('e', 64), 'first_party',
    '[]'::jsonb, '{"model_source_id":"source-approval-1"}'::jsonb, now()
  ),
  (
    '98400000-0000-4000-8000-000000000005',
    '98100000-0000-4000-8000-000000000001',
    '98300000-0000-4000-8000-000000000003',
    '98200000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'competitor', 'Approval source two', repeat('f', 64), 'public',
    '[]'::jsonb, '{"model_source_id":"source-approval-2"}'::jsonb, now()
  );

insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, previous_draft_id, created_by,
  origin, version, status, title, brief, source_ids, task_blueprint, content_hash
) values (
  '98500000-0000-4000-8000-000000000005',
  '98100000-0000-4000-8000-000000000001',
  '98300000-0000-4000-8000-000000000003',
  '98200000-0000-4000-8000-000000000001',
  null,
  '98000000-0000-4000-8000-000000000001',
  'ai', 1, 'draft', 'Approval invariant brief',
  jsonb_set(
    pg_temp.stage_brief(
      'Collect more evidence before the full brief',
      'source-approval-1',
      'source-approval-2'
    ),
    '{guidance,status}',
    '"needs_more_evidence"'::jsonb
  ),
  jsonb_build_array(
    '98400000-0000-4000-8000-000000000004'::text,
    '98400000-0000-4000-8000-000000000005'::text
  ),
  jsonb_build_array(jsonb_build_object('title', 'Create governed scenario')),
  repeat('1', 64)
);

create or replace function pg_temp.approval_save_payload(
  command_key text,
  brief_value jsonb,
  source_ids_value jsonb
)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'idempotency_key', command_key,
    'run_id', '98300000-0000-4000-8000-000000000003',
    'title', 'Approval invariant brief',
    'brief', brief_value,
    'source_ids', source_ids_value,
    'task_blueprint', jsonb_build_array(jsonb_build_object(
      'title', 'Create governed scenario'
    ))
  )
$$;

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub', '98000000-0000-4000-8000-000000000001', true
  );
end $$;

select throws_ok(
  $$update content_factory.creative_brief_drafts
    set status = 'approved',
        approved_by = '98000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where id = '98500000-0000-4000-8000-000000000005'$$,
  '55000', 'research_v2_human_draft_required',
  'direct approval rejects the initial AI v2 draft'
);
select throws_ok(
  $$select public.creator_approve_creative_brief(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'idempotency_key', 'stage-approve-ai-reject',
    'draft_id', '98500000-0000-4000-8000-000000000005'
  ))$$,
  '55000', 'research_v2_human_draft_required',
  'approval RPC also rejects the initial AI v2 draft'
);

select throws_ok(
  $$select public.creator_save_creative_brief_draft(
    pg_temp.approval_save_payload(
      'stage-save-drop-category',
      (select brief - 'category_analysis'
       from content_factory.creative_brief_drafts
       where id = '98500000-0000-4000-8000-000000000005'),
      (select source_ids from content_factory.creative_brief_drafts
       where id = '98500000-0000-4000-8000-000000000005')
    )
  )$$,
  '55000', 'research_v2_evidence_immutable',
  'save RPC rejects deleting category analysis from a v2 ancestor'
);
select throws_ok(
  $$select public.creator_save_creative_brief_draft(
    pg_temp.approval_save_payload(
      'stage-save-drop-guidance',
      (select brief - 'guidance'
       from content_factory.creative_brief_drafts
       where id = '98500000-0000-4000-8000-000000000005'),
      (select source_ids from content_factory.creative_brief_drafts
       where id = '98500000-0000-4000-8000-000000000005')
    )
  )$$,
  '55000', 'research_v2_evidence_immutable',
  'save RPC rejects deleting guidance from a v2 ancestor'
);
select throws_ok(
  $$select public.creator_save_creative_brief_draft(
    pg_temp.approval_save_payload(
      'stage-save-drop-all-v2',
      (select brief - array[
         'category_analysis', 'competitor_analysis', 'trend_analysis', 'guidance'
       ]::text[]
       from content_factory.creative_brief_drafts
       where id = '98500000-0000-4000-8000-000000000005'),
      (select source_ids from content_factory.creative_brief_drafts
       where id = '98500000-0000-4000-8000-000000000005')
    )
  )$$,
  '55000', 'research_v2_evidence_immutable',
  'save RPC cannot downgrade a v2 run to a legacy-looking brief'
);
select throws_ok(
  $$select public.creator_save_creative_brief_draft(
    pg_temp.approval_save_payload(
      'stage-save-rewrite-trends',
      jsonb_set(
        (select brief from content_factory.creative_brief_drafts
         where id = '98500000-0000-4000-8000-000000000005'),
        '{trend_analysis,as_of}', '"2099-01-01"'::jsonb
      ),
      (select source_ids from content_factory.creative_brief_drafts
       where id = '98500000-0000-4000-8000-000000000005')
    )
  )$$,
  '55000', 'research_v2_evidence_immutable',
  'save RPC rejects rewriting the AI trend evidence'
);
select throws_ok(
  $$select public.creator_save_creative_brief_draft(
    pg_temp.approval_save_payload(
      'stage-save-reduce-sources',
      (select brief from content_factory.creative_brief_drafts
       where id = '98500000-0000-4000-8000-000000000005'),
      jsonb_build_array('98400000-0000-4000-8000-000000000004'::text)
    )
  )$$,
  '55000', 'research_v2_evidence_immutable',
  'save RPC rejects reducing the canonical evidence set'
);

create temporary table stage_control_rpc_context (
  no_marker_result jsonb,
  overlay_result jsonb,
  ready_result jsonb,
  approve_result jsonb
) on commit drop;
insert into stage_control_rpc_context (no_marker_result)
select public.creator_save_creative_brief_draft(
  pg_temp.approval_save_payload(
    'stage-save-no-marker',
    (select brief from content_factory.creative_brief_drafts
     where id = '98500000-0000-4000-8000-000000000005'),
    (select source_ids from content_factory.creative_brief_drafts
     where id = '98500000-0000-4000-8000-000000000005')
  )
);

select throws_ok(
  $$update content_factory.creative_brief_drafts
    set status = 'approved',
        approved_by = '98000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where id = (
      select (no_marker_result #>> '{draft,id}')::uuid
      from stage_control_rpc_context
    )$$,
  '55000', 'research_guidance_approval_override_required',
  'direct approval requires an explicit marker for non-ready guidance'
);
select throws_ok(
  $$select public.creator_approve_creative_brief(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'idempotency_key', 'stage-approve-no-marker',
    'draft_id', (select no_marker_result #>> '{draft,id}'
      from stage_control_rpc_context)
  ))$$,
  '55000', 'research_guidance_approval_override_required',
  'approval RPC cannot bypass the non-ready guidance marker'
);

insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, previous_draft_id, created_by,
  origin, version, status, title, brief, source_ids, task_blueprint, content_hash
)
select
  fixture.id,
  '98100000-0000-4000-8000-000000000001'::uuid,
  '98300000-0000-4000-8000-000000000003'::uuid,
  '98200000-0000-4000-8000-000000000001'::uuid,
  fixture.previous_draft_id,
  '98000000-0000-4000-8000-000000000001'::uuid,
  'human', fixture.version, 'draft', 'Malformed v2 approval candidate',
  fixture.brief,
  (select source_ids from content_factory.creative_brief_drafts
   where id = '98500000-0000-4000-8000-000000000005'),
  jsonb_build_array(jsonb_build_object('title', 'Never create this task')),
  repeat(fixture.hash_character, 64)
from (
  select
    '98500000-0000-4000-8000-000000000006'::uuid as id,
    (select (no_marker_result #>> '{draft,id}')::uuid
     from stage_control_rpc_context) as previous_draft_id,
    3 as version,
    (select brief - 'category_analysis'
     from content_factory.creative_brief_drafts
     where id = '98500000-0000-4000-8000-000000000005') as brief,
    '2'::text as hash_character
  union all
  select
    '98500000-0000-4000-8000-000000000007'::uuid,
    '98500000-0000-4000-8000-000000000006'::uuid,
    4,
    (select brief - 'guidance'
     from content_factory.creative_brief_drafts
     where id = '98500000-0000-4000-8000-000000000005'),
    '3'
  union all
  select
    '98500000-0000-4000-8000-000000000008'::uuid,
    '98500000-0000-4000-8000-000000000007'::uuid,
    5,
    (select brief - array[
       'category_analysis', 'competitor_analysis', 'trend_analysis', 'guidance'
     ]::text[]
     from content_factory.creative_brief_drafts
     where id = '98500000-0000-4000-8000-000000000005'),
    '4'
) fixture;

select throws_ok(
  $$update content_factory.creative_brief_drafts
    set status = 'approved',
        approved_by = '98000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where id = '98500000-0000-4000-8000-000000000006'$$,
  '55000', 'research_v2_evidence_immutable',
  'approval rejects a human draft that deleted category analysis'
);
select throws_ok(
  $$update content_factory.creative_brief_drafts
    set status = 'approved',
        approved_by = '98000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where id = '98500000-0000-4000-8000-000000000007'$$,
  '55000', 'research_v2_evidence_immutable',
  'approval rejects a human draft that deleted guidance'
);
select throws_ok(
  $$update content_factory.creative_brief_drafts
    set status = 'approved',
        approved_by = '98000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where id = '98500000-0000-4000-8000-000000000008'$$,
  '55000', 'research_v2_evidence_immutable',
  'approval cannot disguise a v2 descendant as a legacy brief'
);

update stage_control_rpc_context context
set overlay_result = public.creator_save_creative_brief_draft(
  pg_temp.approval_save_payload(
    'stage-save-valid-overlay',
    (select brief from content_factory.creative_brief_drafts
     where id = '98500000-0000-4000-8000-000000000005')
      || jsonb_build_object(
        'human_stage_corrections', jsonb_build_object(
          'sources', 'Use only the two captured sources',
          'category', 'Frame the category as an early growth test',
          'competitors', 'Do not infer market leadership',
          'trends', 'Treat the signal as directional only',
          'strategy', 'Run one bounded creative experiment'
        ),
        'human_research_decision', jsonb_build_object(
          'guidance_status', 'needs_more_evidence',
          'cold_start_override', true,
          'strategy', 'Run one bounded creative experiment'
        )
      ),
    jsonb_build_array(
      '98400000-0000-4000-8000-000000000005'::text,
      '98400000-0000-4000-8000-000000000004'::text
    )
  )
);

select is(
  (select overlay_result #>> '{draft,version}' from stage_control_rpc_context),
  '6',
  'valid human overlay is saved as the next immutable draft version'
);
select is(
  (select content_factory_private.research_v2_sections(saved.brief)
   from content_factory.creative_brief_drafts saved
   where saved.id = (select (overlay_result #>> '{draft,id}')::uuid
     from stage_control_rpc_context)),
  (select content_factory_private.research_v2_sections(ai.brief)
   from content_factory.creative_brief_drafts ai
   where ai.id = '98500000-0000-4000-8000-000000000005'),
  'valid overlay preserves all four AI v2 sections exactly'
);
select is(
  (select content_factory_private.canonical_research_source_ids(saved.source_ids)
   from content_factory.creative_brief_drafts saved
   where saved.id = (select (overlay_result #>> '{draft,id}')::uuid
     from stage_control_rpc_context)),
  (select content_factory_private.canonical_research_source_ids(ai.source_ids)
   from content_factory.creative_brief_drafts ai
   where ai.id = '98500000-0000-4000-8000-000000000005'),
  'valid overlay may reorder but never reduce or replace canonical evidence'
);
select is(
  (select jsonb_object_agg(
     binding.stage, artifact.payload -> 'human_correction'
     order by content_factory_private.research_stage_rank(binding.stage)
   )
   from content_factory.research_stage_draft_bindings binding
   join content_factory.research_stage_artifacts artifact
     on artifact.organization_id = binding.organization_id
    and artifact.run_id = binding.run_id
    and artifact.stage = binding.stage
    and artifact.id = binding.artifact_id
   where binding.organization_id = '98100000-0000-4000-8000-000000000001'
     and binding.draft_id = (select (overlay_result #>> '{draft,id}')::uuid
       from stage_control_rpc_context)
     and artifact.payload ? 'human_correction'),
  ('{"sources":"Use only the two captured sources",'
    || '"category":"Frame the category as an early growth test",'
    || '"competitors":"Do not infer market leadership",'
    || '"trends":"Treat the signal as directional only",'
    || '"guidance":"Run one bounded creative experiment"}')::jsonb,
  'UI correction keys belong to sources/category/competitors/trends/guidance only'
);
select ok(
  (select not (artifact.payload -> 'brief' ? 'human_stage_corrections')
     and not (artifact.payload -> 'brief' ? 'human_research_decision')
   from content_factory.research_stage_draft_bindings binding
   join content_factory.research_stage_artifacts artifact
     on artifact.organization_id = binding.organization_id
    and artifact.run_id = binding.run_id
    and artifact.stage = binding.stage
    and artifact.id = binding.artifact_id
   where binding.organization_id = '98100000-0000-4000-8000-000000000001'
     and binding.draft_id = (select (overlay_result #>> '{draft,id}')::uuid
       from stage_control_rpc_context)
     and binding.stage = 'brief'),
  'generic brief artifact never duplicates research correction ownership'
);
select is(
  (select artifact.payload -> 'human_research_decision'
   from content_factory.research_stage_draft_bindings binding
   join content_factory.research_stage_artifacts artifact
     on artifact.organization_id = binding.organization_id
    and artifact.run_id = binding.run_id
    and artifact.stage = binding.stage
    and artifact.id = binding.artifact_id
   where binding.organization_id = '98100000-0000-4000-8000-000000000001'
     and binding.draft_id = (select (overlay_result #>> '{draft,id}')::uuid
       from stage_control_rpc_context)
     and binding.stage = 'guidance'),
  ('{"guidance_status":"needs_more_evidence",'
    || '"cold_start_override":true,'
    || '"strategy":"Run one bounded creative experiment"}')::jsonb,
  'non-ready human decision is owned by the guidance stage'
);

select throws_ok(
  $$update content_factory.creative_brief_drafts
    set status = 'approved',
        approved_by = '98000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where id = (select (overlay_result #>> '{draft,id}')::uuid
      from stage_control_rpc_context)$$,
  '55000', 'research_stage_dependencies_stale',
  'approval blocks a human overlay whose brief and scenario stages are stale'
);

update stage_control_rpc_context context
set ready_result = public.creator_save_creative_brief_draft(
  pg_temp.approval_save_payload(
    'stage-save-ready-snapshot',
    jsonb_set(
      (select draft.brief
       from content_factory.creative_brief_drafts draft
       where draft.id = (context.overlay_result #>> '{draft,id}')::uuid)
        || jsonb_build_object(
          'human_review_snapshot',
          'Reviewed the corrected research before approval'
        ),
      '{scenarios,0,hook}',
      '"Human-reviewed bounded demonstration"'::jsonb
    ),
    (select draft.source_ids
     from content_factory.creative_brief_drafts draft
     where draft.id = (context.overlay_result #>> '{draft,id}')::uuid)
  )
);
select is(
  (select ready_result #>> '{draft,version}' from stage_control_rpc_context),
  '7',
  'human review snapshot is saved as a new immutable draft version'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_heads head
   where head.organization_id = '98100000-0000-4000-8000-000000000001'
     and head.run_id = '98300000-0000-4000-8000-000000000003'
     and head.state = 'current'
     and head.current_draft_id = (
       select (ready_result #>> '{draft,id}')::uuid
       from stage_control_rpc_context
     )),
  7,
  'human review snapshot rebuilds the stale brief and scenario dependencies'
);

savepoint stage_direct_positive;
select lives_ok(
  $$update content_factory.creative_brief_drafts
    set status = 'approved',
        approved_by = '98000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where id = (select (ready_result #>> '{draft,id}')::uuid
      from stage_control_rpc_context)$$,
  'direct approval accepts the exact seven-head human review snapshot'
);
rollback to savepoint stage_direct_positive;
release savepoint stage_direct_positive;

update stage_control_rpc_context context
set approve_result = public.creator_approve_creative_brief(jsonb_build_object(
  'organization_id', '98100000-0000-4000-8000-000000000001',
  'idempotency_key', 'stage-approve-ready-snapshot',
  'draft_id', context.ready_result #>> '{draft,id}'
));
select ok(
  (select (approve_result ->> 'ok')::boolean from stage_control_rpc_context),
  'real approval RPC accepts the exact human review snapshot'
);
select is(
  (select status
   from content_factory.creative_brief_drafts
   where id = (select (ready_result #>> '{draft,id}')::uuid
     from stage_control_rpc_context)),
  'approved',
  'human snapshot flow reaches the durable approved state'
);
select is(
  (select count(*)::integer
   from content_factory.creator_tasks task
   where task.creative_brief_draft_id = (
     select (ready_result #>> '{draft,id}')::uuid
     from stage_control_rpc_context
   )),
  1,
  'snapshot-backed approval creates the single governed blueprint task'
);

-- Legacy briefs without guidance remain compatible with the pre-v2 workflow.
insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at
) values (
  '98300000-0000-4000-8000-000000000004',
  '98100000-0000-4000-8000-000000000001',
  '98200000-0000-4000-8000-000000000001',
  '98000000-0000-4000-8000-000000000001',
  'completed', '{"objective":"legacy compatibility fixture"}'::jsonb,
  '{}'::jsonb, repeat('5', 64), repeat('6', 64),
  'stage-ledger-run-legacy', now()
);
insert into content_factory.product_research_sources (
  id, organization_id, run_id, product_id, created_by, source_type,
  title, content_hash, trust_level, extracted_facts, metadata, fetched_at
) values (
  '98400000-0000-4000-8000-000000000006',
  '98100000-0000-4000-8000-000000000001',
  '98300000-0000-4000-8000-000000000004',
  '98200000-0000-4000-8000-000000000001',
  '98000000-0000-4000-8000-000000000001',
  'user_input', 'Legacy source', repeat('7', 64), 'first_party',
  '[]'::jsonb, '{}'::jsonb, now()
);
insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, previous_draft_id, created_by,
  origin, version, status, title, brief, source_ids, task_blueprint, content_hash
) values (
  '98500000-0000-4000-8000-000000000009',
  '98100000-0000-4000-8000-000000000001',
  '98300000-0000-4000-8000-000000000004',
  '98200000-0000-4000-8000-000000000001', null,
  '98000000-0000-4000-8000-000000000001',
  'ai', 1, 'draft', 'Legacy compatible brief',
  '{"summary":"Legacy brief without research guidance"}'::jsonb,
  jsonb_build_array('98400000-0000-4000-8000-000000000006'::text),
  jsonb_build_array(jsonb_build_object('title', 'Create legacy scenario')),
  repeat('8', 64)
);
select lives_ok(
  $$update content_factory.creative_brief_drafts
    set status = 'approved',
        approved_by = '98000000-0000-4000-8000-000000000001',
        approved_at = clock_timestamp()
    where id = '98500000-0000-4000-8000-000000000009'$$,
  'legacy brief without guidance remains directly approvable'
);

select throws_ok(
  $$update content_factory.research_stage_artifacts
    set payload = payload
    where organization_id = '98100000-0000-4000-8000-000000000001'
      and run_id = '98300000-0000-4000-8000-000000000001'
      and stage = 'sources'$$,
  '55000', 'research_stage_artifacts_append_only',
  'stage artifacts cannot be updated'
);
select throws_ok(
  $$delete from content_factory.research_stage_artifacts
    where organization_id = '98100000-0000-4000-8000-000000000001'
      and run_id = '98300000-0000-4000-8000-000000000001'
      and stage = 'sources'$$,
  '55000', 'research_stage_artifacts_append_only',
  'stage artifacts cannot be deleted'
);
select throws_ok(
  $$update content_factory.research_stage_draft_bindings
    set dependency_hash = dependency_hash
    where organization_id = '98100000-0000-4000-8000-000000000001'
      and draft_id = '98500000-0000-4000-8000-000000000001'
      and stage = 'sources'$$,
  '55000', 'research_stage_draft_bindings_append_only',
  'draft bindings cannot be updated'
);
select throws_ok(
  $$delete from content_factory.research_stage_binding_evidence
    where organization_id = '98100000-0000-4000-8000-000000000001'
      and draft_id = '98500000-0000-4000-8000-000000000001'
      and stage = 'sources'$$,
  '55000', 'research_stage_binding_evidence_append_only',
  'binding evidence cannot be deleted'
);
select throws_ok(
  $$update content_factory.research_stage_decisions
    set decision = decision
    where organization_id = '98100000-0000-4000-8000-000000000001'
      and draft_id = '98500000-0000-4000-8000-000000000001'
      and stage = 'sources'$$,
  '55000', 'research_stage_decisions_append_only',
  'decisions cannot be updated'
);
select throws_ok(
  $$delete from content_factory.research_stage_decisions
    where organization_id = '98100000-0000-4000-8000-000000000001'
      and draft_id = '98500000-0000-4000-8000-000000000001'
      and stage = 'sources'$$,
  '55000', 'research_stage_decisions_append_only',
  'decisions cannot be deleted'
);

insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, previous_draft_id, created_by,
  origin, version, status, title, brief, source_ids, task_blueprint, content_hash
)
values (
  '98500000-0000-4000-8000-000000000004',
  '98100000-0000-4000-8000-000000000002',
  '98300000-0000-4000-8000-000000000002',
  '98200000-0000-4000-8000-000000000002',
  null,
  '98000000-0000-4000-8000-000000000001',
  'ai', 1, 'draft', 'Other tenant brief',
  pg_temp.stage_brief(
    'Review the corroborated trend',
    'source-other-1',
    'source-other-1'
  ),
  jsonb_build_array('98400000-0000-4000-8000-000000000003'::text),
  jsonb_build_array(jsonb_build_object('title', 'Create scenario')),
  repeat('b', 64)
);

select is(
  (select count(*)::integer
   from content_factory.research_stage_artifacts artifact
   where artifact.organization_id = '98100000-0000-4000-8000-000000000002'
     and artifact.run_id = '98300000-0000-4000-8000-000000000002'),
  7,
  'same payload in another tenant creates tenant-local artifacts'
);
select ok(
  not exists (
    select 1
    from content_factory.research_stage_draft_bindings main_binding
    join content_factory.research_stage_draft_bindings other_binding
      on other_binding.artifact_id = main_binding.artifact_id
     and other_binding.organization_id = '98100000-0000-4000-8000-000000000002'
    where main_binding.organization_id = '98100000-0000-4000-8000-000000000001'
  ),
  'artifact IDs are never shared across tenants'
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config('request.jwt.claim.sub', '98000000-0000-4000-8000-000000000001', true);
end $$;

select is(
  jsonb_array_length(public.creator_research_stage_ledger(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'run_id', '98300000-0000-4000-8000-000000000001'
  )) -> 'drafts'),
  3,
  'owner reads all and only drafts for the exact run'
);
select is(
  public.creator_research_stage_ledger(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'run_id', '98300000-0000-4000-8000-000000000001'
  )) ->> 'organization_id',
  '98100000-0000-4000-8000-000000000001',
  'read RPC returns the exact requested tenant'
);
select throws_ok(
  $$select public.creator_research_stage_ledger(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'run_id', '98300000-0000-4000-8000-000000000002'
  ))$$,
  '22023', 'research_run_not_found',
  'run from another tenant cannot be read through an allowed tenant'
);
select is(
  jsonb_array_length(public.creator_research_stage_ledger(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000002',
    'run_id', '98300000-0000-4000-8000-000000000002'
  )) -> 'drafts'),
  1,
  'multi-tenant owner can read the other tenant only when explicitly selected'
);
select throws_ok(
  $$select public.creator_research_stage_ledger(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'run_id', '98300000-0000-4000-8000-000000000001',
    'activate_learning', true
  ))$$,
  '22023', 'research_stage_ledger_payload_invalid',
  'read RPC rejects live-provider or learning activation flags'
);

do $$ begin
  perform set_config('request.jwt.claim.sub', '98000000-0000-4000-8000-000000000002', true);
end $$;
select lives_ok(
  $$select public.creator_research_stage_ledger(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'run_id', '98300000-0000-4000-8000-000000000001'
  ))$$,
  'admin can read exact-tenant stage ledger'
);

do $$ begin
  perform set_config('request.jwt.claim.sub', '98000000-0000-4000-8000-000000000003', true);
end $$;
select lives_ok(
  $$select public.creator_research_stage_ledger(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'run_id', '98300000-0000-4000-8000-000000000001'
  ))$$,
  'producer can read exact-tenant stage ledger'
);

do $$ begin
  perform set_config('request.jwt.claim.sub', '98000000-0000-4000-8000-000000000004', true);
end $$;
select lives_ok(
  $$select public.creator_research_stage_ledger(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'run_id', '98300000-0000-4000-8000-000000000001'
  ))$$,
  'reviewer can read exact-tenant stage ledger'
);

do $$ begin
  perform set_config('request.jwt.claim.sub', '98000000-0000-4000-8000-000000000005', true);
end $$;
select throws_ok(
  $$select public.creator_research_stage_ledger(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'run_id', '98300000-0000-4000-8000-000000000001'
  ))$$,
  '42501', 'role_not_allowed',
  'viewer cannot read stage ledger'
);

select * from finish();
rollback;
