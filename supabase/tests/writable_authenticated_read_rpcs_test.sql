begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

with expected(function_name, service_role_execute) as (
  values
    ('creator_generation_strategy_asset_candidates', false),
    ('creator_generation_strategy_repeat_data', false),
    ('creator_project_media', false),
    ('creator_project_members', false),
    ('creator_project_placement', false),
    ('contentengine_generation_video_reference_lineage', true),
    ('creator_validate_notification_action', false),
    ('workspace_trash_browser', false)
)
select is(
  (
    select procedure.provolatile::text
    from pg_catalog.pg_proc procedure
    join pg_catalog.pg_namespace namespace
      on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname = expected.function_name
      and pg_get_function_identity_arguments(procedure.oid) = 'p_payload jsonb'
  ),
  'v'::text,
  expected.function_name || ' opens a writable authenticated RPC transaction'
)
from expected;

with expected(function_name, service_role_execute) as (
  values
    ('creator_generation_strategy_asset_candidates', false),
    ('creator_generation_strategy_repeat_data', false),
    ('creator_project_media', false),
    ('creator_project_members', false),
    ('creator_project_placement', false),
    ('contentengine_generation_video_reference_lineage', true),
    ('creator_validate_notification_action', false),
    ('workspace_trash_browser', false)
)
select ok(
  has_function_privilege(
    'authenticated',
    format('%I.%I(jsonb)', 'public', expected.function_name),
    'execute'
  )
  and not has_function_privilege(
    'anon',
    format('%I.%I(jsonb)', 'public', expected.function_name),
    'execute'
  )
  and has_function_privilege(
    'service_role',
    format('%I.%I(jsonb)', 'public', expected.function_name),
    'execute'
  ) is not distinct from expected.service_role_execute,
  expected.function_name || ' preserves its authenticated-only execute ACL'
)
from expected;

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'e6400000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  'writable-read-rpcs@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Writable read RPCs"}'::jsonb,
  now(),
  now()
);

update content_factory.profiles profile
set display_name = 'Writable read RPCs', status = 'active'
where profile.id = 'e6400000-0000-4000-8000-000000000001'::uuid;

insert into content_factory.organizations (id, name, slug, status)
values (
  'e6500000-0000-4000-8000-000000000001'::uuid,
  'Writable authenticated RPC pgTAP',
  'writable-authenticated-rpc-pgtap',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'e6500000-0000-4000-8000-000000000001'::uuid,
  'e6400000-0000-4000-8000-000000000001'::uuid,
  'owner',
  'active'
);

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'e6500000-0000-4000-8000-000000000001'::uuid,
  'e6400000-0000-4000-8000-000000000001'::uuid,
  'owner',
  'owner',
  'TEST-ONLY waiver for the writable authenticated read-RPC contract.',
  'e6400000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values (
  'e6600000-0000-4000-8000-000000000001'::uuid,
  'e6500000-0000-4000-8000-000000000001'::uuid,
  null,
  'Writable authenticated RPC project',
  'emerald',
  'project',
  'active',
  1024,
  'e6400000-0000-4000-8000-000000000001'::uuid,
  'e6400000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
) values (
  'e6700000-0000-4000-8000-000000000001'::uuid,
  'e6500000-0000-4000-8000-000000000001'::uuid,
  'e6600000-0000-4000-8000-000000000001'::uuid,
  'e6400000-0000-4000-8000-000000000001'::uuid,
  'contentengine-private',
  'e6500000-0000-4000-8000-000000000001/e6400000-0000-4000-8000-000000000001/uploads/read-rpc.webp',
  'image/webp',
  100,
  repeat('6', 64),
  'ready',
  '{"kind":"creator_reference","original_filename":"read-rpc.webp","rights_confirmed":true}'::jsonb,
  'writable-authenticated-read-rpc-media-0001'
);

create temporary table writable_read_rpc_spend_baseline on commit drop as
select
  (select count(*) from content_factory.generation_spend_ledger
   where organization_id = 'e6500000-0000-4000-8000-000000000001'::uuid)
    as spend_entries,
  (select count(*) from content_factory.generation_batches
   where organization_id = 'e6500000-0000-4000-8000-000000000001'::uuid)
    as batches,
  (select count(*) from content_factory.generation_jobs
   where organization_id = 'e6500000-0000-4000-8000-000000000001'::uuid)
    as jobs;

select set_config(
  'request.jwt.claim.sub',
  'e6400000-0000-4000-8000-000000000001',
  true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

set local role authenticated;

select lives_ok(
  $$
    select public.creator_generation_strategy_asset_candidates(
      jsonb_build_object(
        'version', 'generation-strategy-asset-candidates-request-v1',
        'organization_id', 'e6500000-0000-4000-8000-000000000001',
        'project_id', 'e6600000-0000-4000-8000-000000000001',
        'kind', 'creator_reference'
      )
    )
  $$,
  'authenticated asset candidates completes without SQLSTATE 25006'
);

select lives_ok(
  $$
    select public.creator_project_media(
      jsonb_build_object(
        'organization_id', 'e6500000-0000-4000-8000-000000000001',
        'project_id', 'e6600000-0000-4000-8000-000000000001',
        'media_id', 'e6700000-0000-4000-8000-000000000001',
        'surface', 'generation'
      )
    )
  $$,
  'authenticated project media completes without SQLSTATE 25006'
);

reset role;

select is(
  (
    select jsonb_build_object(
      'spend_entries', (select count(*) from content_factory.generation_spend_ledger
        where organization_id = 'e6500000-0000-4000-8000-000000000001'::uuid),
      'batches', (select count(*) from content_factory.generation_batches
        where organization_id = 'e6500000-0000-4000-8000-000000000001'::uuid),
      'jobs', (select count(*) from content_factory.generation_jobs
        where organization_id = 'e6500000-0000-4000-8000-000000000001'::uuid)
    )
  ),
  (
    select jsonb_build_object(
      'spend_entries', spend_entries,
      'batches', batches,
      'jobs', jobs
    )
    from writable_read_rpc_spend_baseline
  ),
  'authenticated read RPCs create neither spend entries nor generation work'
);

select * from finish();

rollback;
