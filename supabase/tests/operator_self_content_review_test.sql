begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(28);

select ok(
  to_regprocedure(
    'content_factory_private.qualified_operator_own_content_review_allowed(uuid,uuid,uuid,uuid)'
  ) is not null,
  'exact operator self-review predicate exists'
);

select is(
  content_factory_private.qualified_operator_own_content_review_allowed(
    '00000000-0000-4000-8000-000000000090'::uuid,
    '00000000-0000-4000-8000-000000000091'::uuid,
    '00000000-0000-4000-8000-000000000092'::uuid,
    '00000000-0000-4000-8000-000000000093'::uuid
  ),
  false,
  'missing lineage fails closed'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.qualified_operator_own_content_review_allowed(uuid,uuid,uuid,uuid)',
    'execute'
  ),
  'browser users cannot probe the private relationship predicate'
);

select ok(
  not has_function_privilege(
    'service_role',
    'content_factory_private.qualified_operator_own_content_review_allowed(uuid,uuid,uuid,uuid)',
    'execute'
  ),
  'service role has no direct predicate endpoint'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.assign_generated_media_review(uuid,uuid)'::regprocedure
  ) like '%qualified_operator_own_content_review_allowed%',
  'assignment routes the exact qualified operator first'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.assign_generated_media_review(uuid,uuid)'::regprocedure
  ) like '%workspace_project_access_allowed%',
  'fallback assignment is project ACL scoped'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_decide_content_review_without_sound_release_gate(jsonb)'::regprocedure
  ) like '%qualified_operator_own_content_review_allowed%',
  'decision independence uses the exact operator predicate'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_decide_content_review_without_sound_release_gate(jsonb)'::regprocedure
  ) like '%if not media_watched_value then%',
  'every human decision requires a complete watch'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_approve_generated_photo_review_with_context_pre_project_v47(jsonb)'::regprocedure
  ) like '%qualified_operator_own_content_review_allowed%',
  'photo context approval uses the exact predicate'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'::regprocedure
  ) like '%qualified_operator_own_content_review_allowed%',
  'video context approval uses the exact predicate'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_generation_repair_policy_structured_scores_v1(jsonb)'::regprocedure
  ) like '%qualified_operator_own_content_review_allowed%',
  'negative self decision can reach exact repair policy'
);

select ok(
  pg_get_functiondef(
    'public.creator_content_review_status(jsonb)'::regprocedure
  ) like '%independent_assignment%',
  'exact status deep link exposes assignment truth'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_content_review_status(jsonb)',
    'execute'
  ) and not has_function_privilege(
    'anon',
    'public.creator_content_review_status(jsonb)',
    'execute'
  ),
  'status wrapper remains authenticated-only'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_decide_content_review(jsonb)',
    'execute'
  ) and not has_function_privilege(
    'anon',
    'public.creator_decide_content_review(jsonb)',
    'execute'
  ),
  'decision wrapper remains authenticated-only'
);

-- Behavioral authorization fixture.  Keep it independent of product task
-- automation: the predicate/assignment boundary is exercised against exact
-- durable rows and every mutation is rolled back with this pgTAP transaction.
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
  ('9b000000-0000-4000-8000-000000000001', 'operator-self@example.test', 'Exact Operator'),
  ('9b000000-0000-4000-8000-000000000002', 'operator-peer@example.test', 'Peer Operator'),
  ('9b000000-0000-4000-8000-000000000003', 'operator-no-acl@example.test', 'No ACL Operator'),
  ('9b000000-0000-4000-8000-000000000004', 'operator-revoked@example.test', 'Revoked Operator')
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values (
  '9b100000-0000-4000-8000-000000000001',
  'Operator Self Review Test', 'operator-self-review-test', 'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
select
  '9b100000-0000-4000-8000-000000000001'::uuid,
  profile_id::uuid, 'operator', 'active'
from (values
  ('9b000000-0000-4000-8000-000000000001'),
  ('9b000000-0000-4000-8000-000000000002'),
  ('9b000000-0000-4000-8000-000000000003'),
  ('9b000000-0000-4000-8000-000000000004')
) fixture(profile_id);

insert into content_factory.training_access_waivers (
  organization_id, profile_id, scope, status, previous_role, granted_role,
  grant_reason, granted_by, revoked_by, revoked_at, revocation_reason
)
select
  '9b100000-0000-4000-8000-000000000001'::uuid,
  profile_id::uuid, 'workspace_generation', status,
  'trainee', 'operator', 'TEST-ONLY exact operator qualification fixture.',
  '9b000000-0000-4000-8000-000000000001'::uuid,
  case when status = 'revoked'
    then '9b000000-0000-4000-8000-000000000001'::uuid end,
  case when status = 'revoked' then now() end,
  case when status = 'revoked'
    then 'TEST-ONLY revoked qualification coverage.' end
from (values
  ('9b000000-0000-4000-8000-000000000001', 'active'),
  ('9b000000-0000-4000-8000-000000000002', 'active'),
  ('9b000000-0000-4000-8000-000000000003', 'active'),
  ('9b000000-0000-4000-8000-000000000004', 'revoked')
) fixture(profile_id, status);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
)
values
  (
    '9b110000-0000-4000-8000-000000000001',
    '9b100000-0000-4000-8000-000000000001', null,
    'Exact operator project', 'blue', 'project', null, 'active', 1024,
    '9b000000-0000-4000-8000-000000000001',
    '9b000000-0000-4000-8000-000000000001'
  ),
  (
    '9b110000-0000-4000-8000-000000000002',
    '9b100000-0000-4000-8000-000000000001', null,
    'Foreign operator project', 'slate', 'project', null, 'active', 2048,
    '9b000000-0000-4000-8000-000000000001',
    '9b000000-0000-4000-8000-000000000001'
  );

insert into content_factory.workspace_project_memberships (
  organization_id, project_id, profile_id, access_role, status,
  granted_by, updated_by
)
select
  '9b100000-0000-4000-8000-000000000001'::uuid,
  '9b110000-0000-4000-8000-000000000001'::uuid,
  profile_id::uuid, 'member', 'active',
  '9b000000-0000-4000-8000-000000000001'::uuid,
  '9b000000-0000-4000-8000-000000000001'::uuid
from (values
  ('9b000000-0000-4000-8000-000000000002'),
  ('9b000000-0000-4000-8000-000000000004')
) fixture(profile_id);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
values (
  '9b120000-0000-4000-8000-000000000001',
  '9b100000-0000-4000-8000-000000000001', 'SELF-QA-SKU',
  'Self QA fixture', 'active', '{}'::jsonb,
  '9b000000-0000-4000-8000-000000000001'
);

insert into content_factory.generation_batches (
  id, organization_id, product_id, created_by, project_id, name,
  mode, allow_real_spend, status, total_requested, total_created,
  input, request_hash, idempotency_key,
  provider, model, duration_seconds, audio,
  estimated_cost_minor, estimated_credits, currency
)
values (
  '9b130000-0000-4000-8000-000000000001',
  '9b100000-0000-4000-8000-000000000001',
  '9b120000-0000-4000-8000-000000000001',
  '9b000000-0000-4000-8000-000000000001',
  '9b110000-0000-4000-8000-000000000001', 'Self QA generation',
  'real', true, 'succeeded', 1, 1,
  jsonb_build_object('provider','runway','model','seedance2_fast','audio',true),
  repeat('1',64), 'operator-self-batch-0001',
  'runway', 'seedance2_fast', 8, true, 232, 232, 'USD'
);

alter table content_factory.generation_jobs
  disable trigger a_generation_spec_binding_guard;
insert into content_factory.generation_jobs (
  id, organization_id, product_id, batch_id, ordinal,
  requested_by, assigned_to, project_id, mode, provider, allow_real_spend,
  estimated_cost_minor, actual_cost_minor, status,
  input, output, request_hash, idempotency_key
)
values (
  '9b140000-0000-4000-8000-000000000001',
  '9b100000-0000-4000-8000-000000000001',
  '9b120000-0000-4000-8000-000000000001',
  '9b130000-0000-4000-8000-000000000001', 1,
  '9b000000-0000-4000-8000-000000000001',
  '9b000000-0000-4000-8000-000000000001',
  '9b110000-0000-4000-8000-000000000001',
  'real', 'runway', true, 232, 232, 'succeeded',
  jsonb_build_object('platform','youtube','model','seedance2_fast','audio',true),
  jsonb_build_object(
    'output_media_id','9b150000-0000-4000-8000-000000000001',
    'sha256',repeat('5',64)
  ), repeat('2',64), 'operator-self-job-0001'
);
alter table content_factory.generation_jobs
  enable trigger a_generation_spec_binding_guard;

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id,
  bucket_id, object_name, mime_type, size_bytes, sha256,
  status, metadata, idempotency_key
)
values (
  '9b150000-0000-4000-8000-000000000001',
  '9b100000-0000-4000-8000-000000000001',
  '9b110000-0000-4000-8000-000000000001',
  '9b000000-0000-4000-8000-000000000001',
  '9b120000-0000-4000-8000-000000000001',
  'contentengine-private',
  '9b100000-0000-4000-8000-000000000001/9b000000-0000-4000-8000-000000000001/generated/self-qa.mp4',
  'video/mp4', 8192, repeat('5',64), 'ready',
  jsonb_build_object(
    'kind','generated_video','provider','runway','model','seedance2_fast',
    'audio',true,
    'generation_job_id','9b140000-0000-4000-8000-000000000001'
  ), 'operator-self-media-0001'
);

insert into content_factory.content_review_runs (
  id, organization_id, project_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, result, ruleset_version,
  model_provider, model_version, request_hash, completion_hash,
  idempotency_key, finished_at
)
values (
  '9b160000-0000-4000-8000-000000000001',
  '9b100000-0000-4000-8000-000000000001',
  '9b110000-0000-4000-8000-000000000001',
  '9b150000-0000-4000-8000-000000000001',
  '9b000000-0000-4000-8000-000000000001', 'completed', repeat('5',64),
  jsonb_build_object(
    'generation_job_id','9b140000-0000-4000-8000-000000000001',
    'ai_generated',true,'external_ai_processing_confirmed',false
  ),
  jsonb_build_object(
    'overall_score',73,'scores','{}'::jsonb,'compliance_status','human_review',
    'blockers_count',0,'warnings_count',1,
    'findings','[]'::jsonb,'recommendations','[]'::jsonb
  ), 'operator-self-rules-v1', 'test', 'test-v1',
  repeat('6',64), repeat('7',64), 'operator-self-review-0001', now()
);

select is(
  content_factory_private.qualified_operator_own_content_review_allowed(
    '9b100000-0000-4000-8000-000000000001',
    '9b110000-0000-4000-8000-000000000001',
    '9b160000-0000-4000-8000-000000000001',
    '9b000000-0000-4000-8000-000000000001'
  ), true,
  'qualified exact operator owns this review lineage'
);

select is(
  content_factory_private.qualified_operator_own_content_review_allowed(
    '9b100000-0000-4000-8000-000000000001',
    '9b110000-0000-4000-8000-000000000001',
    '9b160000-0000-4000-8000-000000000001',
    '9b000000-0000-4000-8000-000000000002'
  ), false,
  'same-project qualified non-participant cannot self review'
);

select is(
  content_factory_private.qualified_operator_own_content_review_allowed(
    '9b100000-0000-4000-8000-000000000001',
    '9b110000-0000-4000-8000-000000000001',
    '9b160000-0000-4000-8000-000000000001',
    '9b000000-0000-4000-8000-000000000003'
  ), false,
  'qualified operator without explicit project ACL cannot self review'
);

select is(
  content_factory_private.qualified_operator_own_content_review_allowed(
    '9b100000-0000-4000-8000-000000000001',
    '9b110000-0000-4000-8000-000000000001',
    '9b160000-0000-4000-8000-000000000001',
    '9b000000-0000-4000-8000-000000000004'
  ), false,
  'revoked waiver is not a current qualification'
);

select is(
  content_factory_private.qualified_operator_own_content_review_allowed(
    '9b100000-0000-4000-8000-000000000001',
    '9b110000-0000-4000-8000-000000000002',
    '9b160000-0000-4000-8000-000000000001',
    '9b000000-0000-4000-8000-000000000001'
  ), false,
  'foreign project cannot reuse exact review lineage'
);

select is(
  content_factory_private.assign_generated_media_review(
    '9b100000-0000-4000-8000-000000000001',
    '9b160000-0000-4000-8000-000000000001'
  ),
  '9b000000-0000-4000-8000-000000000001'::uuid,
  'qualified operator is assigned their exact review first'
);

select is(
  (
    select assignment.assignee_id
    from content_factory.content_review_assignments assignment
    where assignment.organization_id =
          '9b100000-0000-4000-8000-000000000001'
      and assignment.review_id =
          '9b160000-0000-4000-8000-000000000001'
      and assignment.status = 'assigned'
  ),
  '9b000000-0000-4000-8000-000000000001'::uuid,
  'operator-first assignment is durable and active'
);

select set_config(
  'request.jwt.claim.sub',
  '9b000000-0000-4000-8000-000000000001', true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id','9b100000-0000-4000-8000-000000000001',
    'project_id','9b110000-0000-4000-8000-000000000001',
    'review_id','9b160000-0000-4000-8000-000000000001',
    'idempotency_key','operator-self-unwatched-0001',
    'decision','needs_changes',
    'reason','Russian words are distorted and require a corrected render.',
    'resolved_recommendation_codes','[]'::jsonb,
    'risk_acknowledgements','[]'::jsonb,
    'media_watched_confirmed',false,
    'sound_assessment',jsonb_build_object(
      'audio',true,'status','issues_found',
      'issue_codes',jsonb_build_array('wrong_words'),
      'spoken_script_heard_exactly_confirmed',false,
      'diction_clear_confirmed',false,'voice_style_confirmed',true,
      'audio_sync_confirmed',true,'silence_expected_confirmed',false,
      'note','Russian words are distorted in the exact rendered video.'
    )
  ))$$,
  '22023', 'content_review_media_watch_required',
  'public exact operator decision rejects an unwatched render'
);

select lives_ok(
  $$select public.creator_content_review_status(jsonb_build_object(
    'organization_id','9b100000-0000-4000-8000-000000000001',
    'project_id','9b110000-0000-4000-8000-000000000001',
    'review_id','9b160000-0000-4000-8000-000000000001'
  ))$$,
  'authorized exact status deep link remains readable'
);

select is(
  (
    public.creator_content_review_status(jsonb_build_object(
      'organization_id','9b100000-0000-4000-8000-000000000001',
      'project_id','9b110000-0000-4000-8000-000000000001',
      'review_id','9b160000-0000-4000-8000-000000000001'
    )) #>> '{run,independent_assignment,assigned_to_me}'
  )::boolean,
  true,
  'status deep link exposes assigned_to_me true'
);

select is(
  (
    public.creator_content_review_status(jsonb_build_object(
      'organization_id','9b100000-0000-4000-8000-000000000001',
      'project_id','9b110000-0000-4000-8000-000000000001',
      'review_id','9b160000-0000-4000-8000-000000000001'
    )) #>> '{run,independent_assignment,decision_eligible}'
  )::boolean,
  true,
  'status deep link exposes decision_eligible true only with assignment'
);

select lives_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id','9b100000-0000-4000-8000-000000000001',
    'project_id','9b110000-0000-4000-8000-000000000001',
    'review_id','9b160000-0000-4000-8000-000000000001',
    'idempotency_key','operator-self-needs-changes-0001',
    'decision','needs_changes',
    'reason','Russian words are distorted and require a corrected render.',
    'resolved_recommendation_codes','[]'::jsonb,
    'risk_acknowledgements','[]'::jsonb,
    'media_watched_confirmed',true,
    'sound_assessment',jsonb_build_object(
      'audio',true,'status','issues_found',
      'issue_codes',jsonb_build_array('wrong_words'),
      'spoken_script_heard_exactly_confirmed',false,
      'diction_clear_confirmed',false,'voice_style_confirmed',true,
      'audio_sync_confirmed',true,'silence_expected_confirmed',false,
      'note','Russian words are distorted in the exact rendered video.'
    )
  ))$$,
  'exact qualified operator can return their watched render for changes through the public project wrapper'
);

select is(
  (
    select decision.decided_by
    from content_factory.content_review_decisions decision
    where decision.organization_id =
          '9b100000-0000-4000-8000-000000000001'
      and decision.review_id =
          '9b160000-0000-4000-8000-000000000001'
      and decision.decision = 'needs_changes'
  ),
  '9b000000-0000-4000-8000-000000000001'::uuid,
  'immutable needs-changes decision is attributed to the assigned operator'
);

select throws_ok(
  $$update content_factory.content_review_decisions
    set comment = 'This forbidden mutation must never be stored.'
    where organization_id = '9b100000-0000-4000-8000-000000000001'
      and review_id = '9b160000-0000-4000-8000-000000000001'$$,
  '55000', 'content_review_decision_immutable',
  'operator self decision remains immutable'
);

select * from finish();
rollback;
