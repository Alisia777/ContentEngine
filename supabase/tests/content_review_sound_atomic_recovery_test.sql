begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(18);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    where trigger_row.tgrelid =
          'content_factory.content_review_decisions'::regclass
      and trigger_row.tgname =
          'enforce_generated_video_decision_sound_atomic'
      and trigger_row.tgdeferrable
      and trigger_row.tginitdeferred
      and not trigger_row.tgisinternal
  ),
  'generated-video decision sound invariant is deferred to transaction end'
);

select has_function(
  'public',
  'creator_recover_content_review_sound_assessment',
  array['jsonb'],
  'append-only sound recovery RPC exists'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_recover_content_review_sound_assessment(jsonb)',
    'execute'
  ),
  'authenticated employees can execute the bounded recovery command'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_recover_content_review_sound_assessment(jsonb)',
    'execute'
  ),
  'anonymous sessions cannot recover sound history'
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
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(), now()
from (values
  (
    '9a000000-0000-4000-8000-000000000001',
    'sound-recovery-actor@example.test',
    'Sound Recovery Actor'
  ),
  (
    '9a000000-0000-4000-8000-000000000002',
    'sound-recovery-other@example.test',
    'Other Sound Reviewer'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values (
  '9a100000-0000-4000-8000-000000000001',
  'Sound Recovery Test',
  'sound-recovery-test',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    '9a100000-0000-4000-8000-000000000001',
    '9a000000-0000-4000-8000-000000000001',
    'operator', 'active'
  ),
  (
    '9a100000-0000-4000-8000-000000000001',
    '9a000000-0000-4000-8000-000000000002',
    'operator', 'active'
  );

insert into content_factory.training_access_waivers (
  organization_id, profile_id, scope, status, previous_role, granted_role,
  grant_reason, granted_by
)
values
  (
    '9a100000-0000-4000-8000-000000000001',
    '9a000000-0000-4000-8000-000000000001',
    'workspace_generation', 'active', 'trainee', 'operator',
    'TEST-ONLY qualified operator waiver for sound recovery coverage.',
    '9a000000-0000-4000-8000-000000000001'
  ),
  (
    '9a100000-0000-4000-8000-000000000001',
    '9a000000-0000-4000-8000-000000000002',
    'workspace_generation', 'active', 'trainee', 'operator',
    'TEST-ONLY second operator waiver for same-actor denial coverage.',
    '9a000000-0000-4000-8000-000000000001'
  );

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
)
values
  (
    '9a110000-0000-4000-8000-000000000001',
    '9a100000-0000-4000-8000-000000000001',
    null, 'Exact sound project', 'blue', 'project', null,
    'active', 1024,
    '9a000000-0000-4000-8000-000000000001',
    '9a000000-0000-4000-8000-000000000001'
  ),
  (
    '9a110000-0000-4000-8000-000000000002',
    '9a100000-0000-4000-8000-000000000001',
    null, 'Wrong sound project', 'slate', 'project', null,
    'active', 2048,
    '9a000000-0000-4000-8000-000000000001',
    '9a000000-0000-4000-8000-000000000001'
  );

insert into content_factory.workspace_project_memberships (
  organization_id, project_id, profile_id, access_role, status,
  granted_by, updated_by
)
select
  '9a100000-0000-4000-8000-000000000001'::uuid,
  project_id::uuid,
  profile_id::uuid,
  'member', 'active',
  '9a000000-0000-4000-8000-000000000001'::uuid,
  '9a000000-0000-4000-8000-000000000001'::uuid
from (values
  (
    '9a110000-0000-4000-8000-000000000001',
    '9a000000-0000-4000-8000-000000000002'
  )
) fixture(project_id, profile_id);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
values (
  '9a120000-0000-4000-8000-000000000001',
  '9a100000-0000-4000-8000-000000000001',
  'SOUND-RECOVERY-SKU',
  'Sound recovery fixture',
  'active', '{}'::jsonb,
  '9a000000-0000-4000-8000-000000000001'
);

insert into content_factory.generation_spend_policies (
  organization_id, paid_generation_enabled,
  daily_limit_minor, monthly_limit_minor, per_request_limit_minor,
  currency, timezone, version, reason, updated_by
)
values (
  '9a100000-0000-4000-8000-000000000001', true,
  2500, 10000, 500, 'USD', 'Europe/Moscow', 1,
  'Sound recovery deterministic generation fixture policy.',
  '9a000000-0000-4000-8000-000000000001'
);

insert into content_factory.generation_batches (
  id, organization_id, product_id, created_by, project_id, name,
  mode, allow_real_spend, status, total_requested, total_created,
  input, request_hash, idempotency_key,
  provider, model, duration_seconds, audio,
  estimated_cost_minor, estimated_credits, currency
)
values (
  '9a130000-0000-4000-8000-000000000001',
  '9a100000-0000-4000-8000-000000000001',
  '9a120000-0000-4000-8000-000000000001',
  '9a000000-0000-4000-8000-000000000001',
  '9a110000-0000-4000-8000-000000000001',
  'Sound recovery generation fixture',
  'real', true, 'succeeded', 1, 1,
  jsonb_build_object(
    'job_id', '9a140000-0000-4000-8000-000000000001',
    'provider', 'runway',
    'model', 'gen4_turbo',
    'duration_seconds', 5,
    'audio', false,
    'format', '9:16',
    'ratio', '720:1280',
    'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
    'billing', jsonb_build_object(
      'currency', 'USD',
      'estimated_cost_minor', 25,
      'estimated_credits', 25
    )
  ),
  repeat('1', 64),
  'sound-recovery-batch-0001',
  'runway', 'gen4_turbo', 5, false, 25, 25, 'USD'
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
  '9a140000-0000-4000-8000-000000000001',
  '9a100000-0000-4000-8000-000000000001',
  '9a120000-0000-4000-8000-000000000001',
  '9a130000-0000-4000-8000-000000000001',
  1,
  '9a000000-0000-4000-8000-000000000001',
  '9a000000-0000-4000-8000-000000000001',
  '9a110000-0000-4000-8000-000000000001',
  'real', 'runway', true, 25, 25, 'succeeded',
  jsonb_build_object(
    'sku', 'SOUND-RECOVERY-SKU',
    'product_name', 'Sound recovery fixture',
    'provider', 'runway',
    'platform', 'instagram',
    'model', 'gen4_turbo',
    'duration_seconds', 5,
    'audio', false,
    'format', '9:16',
    'ratio', '720:1280',
    'input_object_name',
      '9a100000-0000-4000-8000-000000000001/9a000000-0000-4000-8000-000000000001/uploads/sound-recovery.webp',
    'output_object_name',
      '9a100000-0000-4000-8000-000000000001/9a000000-0000-4000-8000-000000000001/generated/sound-recovery.mp4',
    'destination_ref', 'instagram-sound-recovery-fixture',
    'prompt_text', 'Test-only sound recovery generation prompt',
    'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
    'billing', jsonb_build_object(
      'currency', 'USD',
      'estimated_cost_minor', 25,
      'estimated_credits', 25
    )
  ),
  jsonb_build_object(
    'provider_task_id', 'sound-recovery-provider-task',
    'output_object_name',
      '9a100000-0000-4000-8000-000000000001/9a000000-0000-4000-8000-000000000001/generated/sound-recovery.mp4',
    'output_media_id', '9a150000-0000-4000-8000-000000000001',
    'mime_type', 'video/mp4',
    'sha256', repeat('5', 64)
  ),
  repeat('2', 64),
  'sound-recovery-job-0001'
);

alter table content_factory.generation_jobs
  enable trigger a_generation_spec_binding_guard;

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id,
  bucket_id, object_name, mime_type, size_bytes, sha256,
  status, metadata, idempotency_key
)
values (
  '9a150000-0000-4000-8000-000000000001',
  '9a100000-0000-4000-8000-000000000001',
  '9a110000-0000-4000-8000-000000000001',
  '9a000000-0000-4000-8000-000000000001',
  '9a120000-0000-4000-8000-000000000001',
  'contentengine-private',
  '9a100000-0000-4000-8000-000000000001/9a000000-0000-4000-8000-000000000001/generated/sound-recovery.mp4',
  'video/mp4', 8192, repeat('5', 64), 'ready',
  jsonb_build_object(
    'kind', 'generated_video',
    'provider', 'runway',
    'model', 'gen4_turbo',
    'audio', false,
    'generation_job_id', '9a140000-0000-4000-8000-000000000001',
    'rights_confirmed', true
  ),
  'sound-recovery-media-0001'
);

insert into content_factory.content_review_runs (
  id, organization_id, project_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, result, ruleset_version,
  model_provider, model_version, request_hash, completion_hash,
  idempotency_key, finished_at
)
select
  review_id::uuid,
  '9a100000-0000-4000-8000-000000000001'::uuid,
  '9a110000-0000-4000-8000-000000000001'::uuid,
  '9a150000-0000-4000-8000-000000000001'::uuid,
  '9a000000-0000-4000-8000-000000000001'::uuid,
  'completed', repeat('5', 64),
  jsonb_build_object(
    'media_id', '9a150000-0000-4000-8000-000000000001',
    'generation_job_id', '9a140000-0000-4000-8000-000000000001',
    'platform', 'instagram',
    'content_kind', 'advertising'
  ),
  jsonb_build_object(
    'overall_score', 60,
    'scores', '{}'::jsonb,
    'compliance_status', 'human_review',
    'blockers_count', 0,
    'warnings_count', 1,
    'strengths', '[]'::jsonb,
    'findings', '[]'::jsonb,
    'recommendations', '[]'::jsonb,
    'comparison', '{}'::jsonb
  ),
  'sound-recovery-rules-v1',
  'test', 'sound-recovery-provider-v1',
  repeat(request_character, 64),
  repeat(completion_character, 64),
  idempotency_key,
  now()
from (values
  (
    '9a160000-0000-4000-8000-000000000001',
    '6', '7', 'sound-recovery-review-0001'
  ),
  (
    '9a160000-0000-4000-8000-000000000002',
    '8', '9', 'sound-recovery-review-0002'
  ),
  (
    '9a160000-0000-4000-8000-000000000003',
    'a', 'b', 'sound-recovery-review-0003'
  )
) fixture(
  review_id, request_character, completion_character, idempotency_key
);

-- Simulate the two immutable pre-fix decisions observed before the deferred
-- invariant existed.  The trigger is disabled only while assembling fixtures.
alter table content_factory.content_review_decisions
  disable trigger enforce_generated_video_decision_sound_atomic;

insert into content_factory.content_review_decisions (
  id, organization_id, review_id, decided_by, decision, comment,
  media_watched_confirmed, review_completion_hash,
  media_sha256_snapshot, idempotency_key
)
values
  (
    '9a170000-0000-4000-8000-000000000001',
    '9a100000-0000-4000-8000-000000000001',
    '9a160000-0000-4000-8000-000000000001',
    '9a000000-0000-4000-8000-000000000001',
    'needs_changes',
    'Russian words were slurred and replaced in the exact rendered video.',
    true, repeat('7', 64), repeat('5', 64),
    'sound-recovery-decision-0001'
  ),
  (
    '9a170000-0000-4000-8000-000000000002',
    '9a100000-0000-4000-8000-000000000001',
    '9a160000-0000-4000-8000-000000000002',
    '9a000000-0000-4000-8000-000000000001',
    'approved',
    'The exact rendered video was approved by the human reviewer.',
    true, repeat('9', 64), repeat('5', 64),
    'sound-recovery-decision-0002'
  );

alter table content_factory.content_review_decisions
  enable trigger enforce_generated_video_decision_sound_atomic;

create or replace function pg_temp.sound_issue_payload()
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select jsonb_build_object(
    'audio', false,
    'status', 'issues_found',
    'issue_codes', jsonb_build_array('unexpected_audio'),
    'spoken_script_heard_exactly_confirmed', false,
    'diction_clear_confirmed', false,
    'voice_style_confirmed', false,
    'audio_sync_confirmed', false,
    'silence_expected_confirmed', false,
    'note', 'Unexpected speech is audible in the silent-mode render.'
  )
$$;

select set_config(
  'request.jwt.claim.sub',
  '9a000000-0000-4000-8000-000000000002',
  true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

select throws_ok(
  $$select public.creator_recover_content_review_sound_assessment(
    jsonb_build_object(
      'organization_id', '9a100000-0000-4000-8000-000000000001',
      'project_id', '9a110000-0000-4000-8000-000000000001',
      'review_id', '9a160000-0000-4000-8000-000000000001',
      'media_watched_confirmed', true,
      'sound_assessment', pg_temp.sound_issue_payload(),
      'idempotency_key', 'sound-recovery-wrong-actor-0001'
    )
  )$$,
  '42501',
  'content_review_sound_recovery_not_allowed',
  'a different qualified operator cannot amend the immutable sound history'
);

select set_config(
  'request.jwt.claim.sub',
  '9a000000-0000-4000-8000-000000000001',
  true
);

select throws_ok(
  $$select public.creator_recover_content_review_sound_assessment(
    jsonb_build_object(
      'organization_id', '9a100000-0000-4000-8000-000000000001',
      'project_id', '9a110000-0000-4000-8000-000000000002',
      'review_id', '9a160000-0000-4000-8000-000000000001',
      'media_watched_confirmed', true,
      'sound_assessment', pg_temp.sound_issue_payload(),
      'idempotency_key', 'sound-recovery-wrong-project-0001'
    )
  )$$,
  '42501',
  'content_review_sound_recovery_not_allowed',
  'the same operator cannot recover a decision through another project'
);

select throws_ok(
  $$select public.creator_recover_content_review_sound_assessment(
    jsonb_build_object(
      'organization_id', '9a100000-0000-4000-8000-000000000001',
      'project_id', '9a110000-0000-4000-8000-000000000001',
      'review_id', '9a160000-0000-4000-8000-000000000002',
      'media_watched_confirmed', true,
      'sound_assessment', pg_temp.sound_issue_payload(),
      'idempotency_key', 'sound-recovery-decision-conflict-0001'
    )
  )$$,
  '55000',
  'content_review_sound_issues_block_approval',
  'recovery assessment must remain compatible with the immutable decision'
);

update content_factory.media_objects
set status = 'deleted'
where organization_id = '9a100000-0000-4000-8000-000000000001'
  and id = '9a150000-0000-4000-8000-000000000001';

select throws_ok(
  $$select public.creator_recover_content_review_sound_assessment(
    jsonb_build_object(
      'organization_id', '9a100000-0000-4000-8000-000000000001',
      'project_id', '9a110000-0000-4000-8000-000000000001',
      'review_id', '9a160000-0000-4000-8000-000000000001',
      'media_watched_confirmed', true,
      'sound_assessment', pg_temp.sound_issue_payload(),
      'idempotency_key', 'sound-recovery-deleted-media-0001'
    )
  )$$,
  '55000',
  'content_review_sound_recovery_media_not_ready',
  'recovery rejects a deleted or otherwise inactive exact MP4 server-side'
);

update content_factory.media_objects
set status = 'ready'
where organization_id = '9a100000-0000-4000-8000-000000000001'
  and id = '9a150000-0000-4000-8000-000000000001';

select is(
  (
    public.creator_content_review_status(jsonb_build_object(
      'organization_id', '9a100000-0000-4000-8000-000000000001',
      'project_id', '9a110000-0000-4000-8000-000000000001',
      'review_id', '9a160000-0000-4000-8000-000000000001'
    )) ->> 'sound_recovery_eligible'
  )::boolean,
  true,
  'authoritative status exposes recovery only to the exact decision maker'
);

create temporary table sound_recovery_results (
  attempt integer primary key,
  result jsonb not null
) on commit drop;

insert into sound_recovery_results (attempt, result)
values (
  1,
  public.creator_recover_content_review_sound_assessment(
    jsonb_build_object(
      'organization_id', '9a100000-0000-4000-8000-000000000001',
      'project_id', '9a110000-0000-4000-8000-000000000001',
      'review_id', '9a160000-0000-4000-8000-000000000001',
      'media_watched_confirmed', true,
      'sound_assessment', pg_temp.sound_issue_payload(),
      'idempotency_key', 'sound-recovery-success-0001'
    )
  )
);

select ok(
  (
    select (result ->> 'recovered')::boolean
      and result #>> '{sound_assessment,status}' = 'issues_found'
    from sound_recovery_results
    where attempt = 1
  ),
  'same operator appends the missing sound assessment to the exact review'
);

select is(
  (
    select count(*)::integer
    from content_factory.content_review_sound_assessments assessment
    where assessment.organization_id =
          '9a100000-0000-4000-8000-000000000001'
      and assessment.review_id =
          '9a160000-0000-4000-8000-000000000001'
      and assessment.decision_id =
          '9a170000-0000-4000-8000-000000000001'
      and assessment.assessed_by =
          '9a000000-0000-4000-8000-000000000001'
  ),
  1,
  'recovery creates one provenance-bound append-only assessment'
);

insert into sound_recovery_results (attempt, result)
values (
  2,
  public.creator_recover_content_review_sound_assessment(
    jsonb_build_object(
      'organization_id', '9a100000-0000-4000-8000-000000000001',
      'project_id', '9a110000-0000-4000-8000-000000000001',
      'review_id', '9a160000-0000-4000-8000-000000000001',
      'media_watched_confirmed', true,
      'sound_assessment', pg_temp.sound_issue_payload(),
      'idempotency_key', 'sound-recovery-success-retry-0001'
    )
  )
);

select is(
  (
    select first.result #>> '{sound_assessment,id}'
    from sound_recovery_results first
    where first.attempt = 1
  ),
  (
    select retry.result #>> '{sound_assessment,id}'
    from sound_recovery_results retry
    where retry.attempt = 2
  ),
  'an exact retry returns the same immutable assessment instead of duplicating it'
);

select is(
  public.creator_content_review_status(jsonb_build_object(
    'organization_id', '9a100000-0000-4000-8000-000000000001',
    'project_id', '9a110000-0000-4000-8000-000000000001',
    'review_id', '9a160000-0000-4000-8000-000000000001'
  )) #>> '{sound_assessment,status}',
  'issues_found',
  'status reads the recovered assessment from the authoritative table'
);

select is(
  (
    public.creator_content_review_status(jsonb_build_object(
      'organization_id', '9a100000-0000-4000-8000-000000000001',
      'project_id', '9a110000-0000-4000-8000-000000000001',
      'review_id', '9a160000-0000-4000-8000-000000000001'
    )) ->> 'sound_recovery_eligible'
  )::boolean,
  false,
  'status removes recovery eligibility after the append succeeds'
);

select is(
  (
    select item.value #>> '{sound_assessment,status}'
    from jsonb_array_elements(
      public.creator_content_review_catalog(jsonb_build_object(
        'organization_id', '9a100000-0000-4000-8000-000000000001',
        'project_id', '9a110000-0000-4000-8000-000000000001',
        'limit', 50
      )) -> 'recent_reviews'
    ) item(value)
    where item.value ->> 'id' =
          '9a160000-0000-4000-8000-000000000001'
  ),
  'issues_found',
  'catalog reads the same authoritative assessment for deep-link hydration'
);

select throws_ok(
  $$do $atomic_future_decision$
  begin
    insert into content_factory.content_review_decisions (
      id, organization_id, review_id, decided_by, decision, comment,
      media_watched_confirmed, review_completion_hash,
      media_sha256_snapshot, idempotency_key
    ) values (
      '9a170000-0000-4000-8000-000000000003',
      '9a100000-0000-4000-8000-000000000001',
      '9a160000-0000-4000-8000-000000000003',
      '9a000000-0000-4000-8000-000000000001',
      'needs_changes',
      'A future generated-video decision cannot omit its sound assessment.',
      true, repeat('b', 64), repeat('5', 64),
      'sound-recovery-future-partial-0001'
    );
    set constraints enforce_generated_video_decision_sound_atomic immediate;
  end;
  $atomic_future_decision$;$$,
  '23514',
  'content_review_sound_assessment_required',
  'a future generated-video decision without sound rolls back atomically'
);

select is(
  (
    select decision || ':' || comment
    from content_factory.content_review_decisions
    where organization_id =
          '9a100000-0000-4000-8000-000000000001'
      and id = '9a170000-0000-4000-8000-000000000001'
  ),
  'needs_changes:Russian words were slurred and replaced in the exact rendered video.',
  'recovery does not rewrite the historical immutable decision'
);

select is(
  (
    select count(*)::integer
    from content_factory.generation_jobs
    where organization_id =
          '9a100000-0000-4000-8000-000000000001'
  ),
  1,
  'recovery starts no provider job, generation, or additional spend'
);

select * from finish();
rollback;
