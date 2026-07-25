begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(11);

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
  'safe-brief-v3',
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

select * from finish();
rollback;
