begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(24);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  '91919191-9191-4191-8191-919191919191'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  'generation-exploration@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Exploration Owner"}'::jsonb,
  now(),
  now()
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '91919191-9191-4191-8191-919191919191',
    true
  );
  perform set_config('request.jwt.claim.role', 'authenticated', true);
end;
$$;

select ok(
  (public.system_initialize_owner(jsonb_build_object(
    'user_id', '91919191-9191-4191-8191-919191919191',
    'idempotency_key', 'pgtap-generation-exploration-owner-0001'
  )) ->> 'ok')::boolean,
  'exploration test owner initialization succeeds'
);

create temporary table exploration_test_context (
  organization_id uuid not null,
  profile_id uuid not null,
  product_id uuid not null,
  media_id uuid not null
) on commit drop;

insert into exploration_test_context (
  organization_id, profile_id, product_id, media_id
)
select
  (bootstrap -> 'organization' ->> 'id')::uuid,
  '91919191-9191-4191-8191-919191919191'::uuid,
  '92929292-9292-4292-8292-929292929292'::uuid,
  '93939393-9393-4393-8393-939393939393'::uuid
from (select public.creator_bootstrap('{}'::jsonb) as bootstrap) response;

-- This test exercises generation policy, not training.  Use the same explicit,
-- auditable workspace waiver as production onboarding instead of fabricating
-- exam answers, certifications or practical-review evidence.
update content_factory.memberships membership
set role = 'operator'
from exploration_test_context context
where membership.organization_id = context.organization_id
  and membership.profile_id = context.profile_id;

insert into content_factory.training_access_waivers (
  organization_id, profile_id, scope, status, previous_role, granted_role,
  grant_reason, granted_by
)
select
  context.organization_id,
  context.profile_id,
  'workspace_generation',
  'active',
  'trainee',
  'operator',
  'TEST-ONLY waiver for bounded generation exploration pgTAP coverage.',
  context.profile_id
from exploration_test_context context;

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
select
  context.product_id,
  context.organization_id,
  'EXPLORE-SKU-1',
  'Exploration product',
  'active',
  '{}'::jsonb,
  context.profile_id
from exploration_test_context context;

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
)
select
  context.media_id,
  context.organization_id,
  context.profile_id,
  context.product_id,
  'contentengine-private',
  context.organization_id::text || '/' || context.profile_id::text
    || '/uploads/exploration-product.jpg',
  'image/jpeg',
  1024,
  repeat('9', 64),
  'ready',
  jsonb_build_object(
    'original_filename', 'exploration-product.jpg',
    'kind', 'product_photo',
    'rights_confirmed', true
  ),
  'pgtap-generation-exploration-media-0001'
from exploration_test_context context;

create temporary table first_exploration_policy (
  policy jsonb not null
) on commit drop;

insert into first_exploration_policy (policy)
select public.creator_generation_learning_policy(jsonb_build_object(
  'organization_id', context.organization_id,
  'media_id', context.media_id,
  'platform', 'youtube',
  'model', 'seedream5_lite'
))
from exploration_test_context context;

select is(
  (select policy ->> 'applied' from first_exploration_policy),
  'true',
  'sparse evidence activates a server-bound assignment'
);

select is(
  (select policy ->> 'selection_mode' from first_exploration_policy),
  'bounded_exploration',
  'sparse evidence is explicitly marked as bounded exploration'
);

select is(
  (select policy ->> 'preferred_angle' from first_exploration_policy),
  'product_focus',
  'the deterministic first exploration angle is product focus'
);

select is(
  (select policy -> 'preferred_hook_patterns'
    from first_exploration_policy),
  '[]'::jsonb,
  'product focus does not inherit historical copy'
);

select matches(
  (select policy ->> 'policy_hash' from first_exploration_policy),
  '^[0-9a-f]{64}$',
  'the full exploration assignment has an immutable policy hash'
);

insert into content_factory.generation_batches (
  id, organization_id, product_id, created_by, name, mode,
  allow_real_spend, status, total_requested, total_created,
  input, request_hash, idempotency_key
)
select
  '94949494-9494-4494-8494-949494949494'::uuid,
  context.organization_id,
  context.product_id,
  context.profile_id,
  'Exploration balancing fixture',
  'mock',
  false,
  'mock_ready',
  1,
  1,
  '{}'::jsonb,
  repeat('a', 64),
  'pgtap-generation-exploration-batch-0001'
from exploration_test_context context;

insert into content_factory.generation_jobs (
  id, organization_id, product_id, batch_id, ordinal,
  requested_by, assigned_to, mode, provider, allow_real_spend,
  estimated_cost_minor, actual_cost_minor, status, input, output,
  request_hash, idempotency_key
)
select
  '95959595-9595-4595-8595-959595959595'::uuid,
  context.organization_id,
  context.product_id,
  '94949494-9494-4494-8494-949494949494'::uuid,
  1,
  context.profile_id,
  context.profile_id,
  'mock',
  'mock',
  false,
  0,
  0,
  'mock_ready',
  jsonb_build_object(
    'platform', 'youtube',
    'model', 'seedream5_lite',
    'prompt_text', 'Test-only structural prompt'
  ),
  '{}'::jsonb,
  repeat('b', 64),
  'pgtap-generation-exploration-job-0001'
from exploration_test_context context;

insert into content_factory.generation_creative_signals (
  organization_id, generation_job_id, product_id, platform, model,
  creative_angle, hook_patterns, source, compiler_version, prompt_hash
)
select
  context.organization_id,
  '95959595-9595-4595-8595-959595959595'::uuid,
  context.product_id,
  'youtube',
  'seedream5_lite',
  'product_focus',
  '[]'::jsonb,
  'baseline',
  'safe-brief-v4',
  repeat('c', 64)
from exploration_test_context context;

create temporary table second_exploration_policy (
  policy jsonb not null
) on commit drop;

insert into second_exploration_policy (policy)
select public.creator_generation_learning_policy(jsonb_build_object(
  'organization_id', context.organization_id,
  'media_id', context.media_id,
  'platform', 'youtube',
  'model', 'seedream5_lite'
))
from exploration_test_context context;

select is(
  (select policy ->> 'preferred_angle' from second_exploration_policy),
  'demonstration',
  'the next assignment balances toward the unused safe angle'
);

select is(
  (select policy -> 'preferred_hook_patterns'
    from second_exploration_policy),
  '["demonstration"]'::jsonb,
  'the demonstration assignment contains only its bounded pattern'
);

select is(
  (
    select count(*)::integer
    from content_factory.generation_jobs job
    where job.organization_id = context.organization_id
      and job.mode = 'real'
  ),
  0,
  'policy lookup creates no paid generation state'
)
from exploration_test_context context;

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_generation_learning_performance_policy_v1(jsonb)',
    'execute'
  ),
  'the mature-performance implementation remains private'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_generation_learning_policy(jsonb)',
    'execute'
  ),
  'authenticated users retain the single audited public policy RPC'
);

select ok(
  exists (
    select 1
    from pg_catalog.pg_trigger trigger_row
    join pg_catalog.pg_class table_row
      on table_row.oid = trigger_row.tgrelid
    join pg_catalog.pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'generation_jobs'
      and trigger_row.tgname = 'zz_generation_rejection_paid_guard'
      and not trigger_row.tgisinternal
  ),
  'paid generation inserts retain the database rejection guard'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.guard_generation_rejection_before_paid_job()',
    'execute'
  ),
  'the paid rejection trigger implementation remains private'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  '96969696-9696-4696-8696-969696969696'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  'generation-quality-reviewer@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Independent Quality Reviewer"}'::jsonb,
  now(),
  now()
);

-- The auth-user trigger creates the matching profile; only organization
-- membership is still required for the independent reviewer.
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
select
  context.organization_id,
  '96969696-9696-4696-8696-969696969696'::uuid,
  'reviewer',
  'active'
from exploration_test_context context;

-- Seed terminal provider/review history without invoking paid provider or
-- release triggers. Check constraints remain active; only trigger side
-- effects and foreign-key trigger timing are disabled inside this rollback.
set local session_replication_role = replica;

do $quality_observation_fixture$
declare
  context_row exploration_test_context%rowtype;
  campaign_id_value uuid;
  batch_id_value uuid;
  job_id_value uuid;
  media_id_value uuid;
  review_id_value uuid;
  position integer;
  angle_value text;
  patterns_value jsonb;
  decision_value text;
  score_value integer;
  blockers_value integer;
begin
  select * into context_row from exploration_test_context;
  select campaign.id into campaign_id_value
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = context_row.organization_id
    and campaign.kind = 'default';

  for position in 1..6 loop
    batch_id_value := extensions.gen_random_uuid();
    job_id_value := extensions.gen_random_uuid();
    media_id_value := extensions.gen_random_uuid();
    review_id_value := extensions.gen_random_uuid();
    angle_value := case
      when position <= 3 then 'product_focus'
      else 'demonstration'
    end;
    patterns_value := case
      when position <= 3 then '[]'::jsonb
      else '["demonstration"]'::jsonb
    end;
    decision_value := case
      when position <= 3 then 'approved'
      else 'rejected'
    end;
    score_value := case when position <= 3 then 92 else 55 end;
    blockers_value := case when position <= 3 then 0 else 1 end;

    insert into content_factory.generation_batches (
      id, organization_id, product_id, created_by, name,
      mode, allow_real_spend, status, total_requested, total_created,
      input, request_hash, idempotency_key, provider, model,
      duration_seconds, audio, estimated_cost_minor, estimated_credits,
      currency, campaign_id
    ) values (
      batch_id_value,
      context_row.organization_id,
      context_row.product_id,
      context_row.profile_id,
      'Quality observation ' || position::text,
      'real',
      true,
      'succeeded',
      1,
      1,
      jsonb_build_object(
        'model', 'gen4_turbo',
        'duration_seconds', 5,
        'audio', false
      ),
      repeat('1', 64),
      'pgtap-quality-batch-' || position::text || '-0001',
      'runway',
      'gen4_turbo',
      5,
      false,
      25,
      25,
      'USD',
      campaign_id_value
    );

    insert into content_factory.generation_jobs (
      id, organization_id, product_id, batch_id, ordinal,
      requested_by, assigned_to, mode, provider, allow_real_spend,
      estimated_cost_minor, actual_cost_minor, status, input, output,
      request_hash, idempotency_key, campaign_id
    ) values (
      job_id_value,
      context_row.organization_id,
      context_row.product_id,
      batch_id_value,
      1,
      context_row.profile_id,
      context_row.profile_id,
      'real',
      'runway',
      true,
      25,
      25,
      'succeeded',
      jsonb_build_object(
        'platform', 'youtube',
        'model', 'gen4_turbo',
        'duration_seconds', 5,
        'audio', false,
        'prompt_text', 'Test-only structural quality prompt'
      ),
      jsonb_build_object(
        'provider_task_id', 'quality-task-' || position::text,
        'output_media_id', media_id_value
      ),
      repeat('2', 64),
      'pgtap-quality-job-' || position::text || '-0001',
      campaign_id_value
    );

    insert into content_factory.media_objects (
      id, organization_id, owner_id, product_id, bucket_id, object_name,
      mime_type, size_bytes, sha256, status, metadata, idempotency_key
    ) values (
      media_id_value,
      context_row.organization_id,
      context_row.profile_id,
      context_row.product_id,
      'contentengine-private',
      context_row.organization_id::text || '/'
        || context_row.profile_id::text || '/generated/'
        || job_id_value::text || '.mp4',
      'video/mp4',
      1024,
      repeat('3', 64),
      'ready',
      jsonb_build_object(
        'kind', 'generated_video',
        'rights_confirmed', true
      ),
      'pgtap-quality-media-' || position::text || '-0001'
    );

    insert into content_factory.content_review_runs (
      id, organization_id, media_object_id, requested_by, status,
      media_sha256_snapshot, input, result, ruleset_version,
      model_provider, model_version, request_hash, completion_hash,
      idempotency_key, finished_at
    ) values (
      review_id_value,
      context_row.organization_id,
      media_id_value,
      context_row.profile_id,
      'completed',
      repeat('3', 64),
      '{}'::jsonb,
      jsonb_build_object(
        'overall_score', score_value,
        'blockers_count', blockers_value,
        'scores', jsonb_build_object(
          'technical', 60,
          'product_fidelity', 65,
          'hook_clarity', 70,
          'visual_quality', 85,
          'trust', 90,
          'platform_fit', 88
        )
      ),
      'pgtap-quality-v1',
      'test',
      'quality-fixture-v1',
      repeat('4', 64),
      repeat('5', 64),
      'pgtap-quality-review-' || position::text || '-0001',
      now()
    );

    insert into content_factory.content_review_decisions (
      organization_id, review_id, decided_by, decision, comment,
      media_watched_confirmed, review_completion_hash,
      media_sha256_snapshot, idempotency_key
    ) values (
      context_row.organization_id,
      review_id_value,
      '96969696-9696-4696-8696-969696969696'::uuid,
      decision_value,
      'Independent quality fixture decision ' || position::text,
      true,
      repeat('5', 64),
      repeat('3', 64),
      'pgtap-quality-decision-' || position::text || '-0001'
    );

    insert into content_factory.generation_creative_signals (
      organization_id, generation_job_id, product_id, platform, model,
      creative_angle, hook_patterns, source, compiler_version, prompt_hash
    ) values (
      context_row.organization_id,
      job_id_value,
      context_row.product_id,
      'youtube',
      'gen4_turbo',
      angle_value,
      patterns_value,
      'baseline',
      'safe-brief-v4',
      repeat('6', 64)
    );
  end loop;
end;
$quality_observation_fixture$;

create temporary table quality_learning_policy (
  policy jsonb not null
) on commit drop;

insert into quality_learning_policy (policy)
select public.creator_generation_learning_policy(jsonb_build_object(
  'organization_id', context.organization_id,
  'media_id', context.media_id,
  'platform', 'youtube',
  'model', 'gen4_turbo'
))
from exploration_test_context context;

select is(
  (select policy ->> 'selection_mode' from quality_learning_policy),
  'quality',
  'independent repeated QA evidence activates the quality tier'
);

select is(
  (select policy ->> 'preferred_angle' from quality_learning_policy),
  'product_focus',
  'quality tier selects the independently stronger angle'
);

select is(
  (select (policy ->> 'evidence_count')::integer
    from quality_learning_policy),
  6,
  'quality tier reports only eligible repeated observations'
);

select is(
  (select policy #>> '{benchmark,approval_rate}'
    from quality_learning_policy),
  '1.00000000000000000000',
  'quality benchmark is computed from decisions rather than copy'
);

select is(
  (select policy #>> '{safety,human_decision_is_independent}'
    from quality_learning_policy),
  'true',
  'quality policy exposes the independent-review invariant'
);

select is(
  (select policy ->> 'version' from quality_learning_policy),
  'generation-learning-v6',
  'recurring structured weaknesses also pass the rejection-learning layer'
);

select is(
  (select policy -> 'quality_guard_codes' from quality_learning_policy),
  '[
    "technical_stability",
    "product_fidelity",
    "hook_clarity"
  ]'::jsonb,
  'quality guards contain only the three weakest enumerated dimensions'
);

select is(
  (select (policy ->> 'quality_guard_evidence_count')::integer
    from quality_learning_policy),
  6,
  'quality guard learning reports the exact eligible observation count'
);

select is(
  (select policy #>> '{safety,raw_review_copy_never_learned}'
    from quality_learning_policy),
  'true',
  'quality guard policy declares that raw review copy is excluded'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_generation_learning_policy_independent_quality_v3(jsonb)',
    'execute'
  ),
  'the prior quality implementation remains private behind the guard RPC'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_generation_learning_policy_exploration_v2(jsonb)',
    'execute'
  ),
  'the exploration implementation remains private behind the quality RPC'
);

select * from finish();
rollback;
