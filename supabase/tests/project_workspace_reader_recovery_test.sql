begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(18);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'e6000000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  'project-reader-recovery@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Project reader recovery"}'::jsonb,
  now(),
  now()
);

insert into content_factory.organizations (
  id, name, slug, status
) values (
  'e6100000-0000-4000-8000-000000000001'::uuid,
  'Project Reader Recovery pgTAP',
  'project-reader-recovery-pgtap',
  'active'
);

update content_factory.profiles profile
set display_name = 'Project reader recovery', status = 'active'
where profile.id = 'e6000000-0000-4000-8000-000000000001'::uuid;

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'e6100000-0000-4000-8000-000000000001'::uuid,
  'e6000000-0000-4000-8000-000000000001'::uuid,
  'owner',
  'active'
);

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'e6100000-0000-4000-8000-000000000001'::uuid,
  'e6000000-0000-4000-8000-000000000001'::uuid,
  'owner',
  'owner',
  'TEST-ONLY waiver for the project reader recovery contract.',
  'e6000000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values
  (
    'e6200000-0000-4000-8000-000000000001'::uuid,
    'e6100000-0000-4000-8000-000000000001'::uuid,
    null,
    'Empty selected project',
    'emerald',
    'project',
    'active',
    2048,
    'e6000000-0000-4000-8000-000000000001'::uuid,
    'e6000000-0000-4000-8000-000000000001'::uuid
  ),
  (
    'e6200000-0000-4000-8000-000000000002'::uuid,
    'e6100000-0000-4000-8000-000000000001'::uuid,
    null,
    'Populated neighbor project',
    'gold',
    'project',
    'active',
    1024,
    'e6000000-0000-4000-8000-000000000001'::uuid,
    'e6000000-0000-4000-8000-000000000001'::uuid
  );

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
) values (
  'e6300000-0000-4000-8000-000000000001'::uuid,
  'e6100000-0000-4000-8000-000000000001'::uuid,
  'e6200000-0000-4000-8000-000000000002'::uuid,
  'e6000000-0000-4000-8000-000000000001'::uuid,
  'contentengine-private',
  'e6100000-0000-4000-8000-000000000001/e6000000-0000-4000-8000-000000000001/uploads/neighbor.webp',
  'image/webp',
  100,
  repeat('6', 64),
  'ready',
  '{"kind":"creator_reference","original_filename":"neighbor.webp"}'::jsonb,
  'project-reader-neighbor-media-0001'
);

create temp table project_reader_profile_baseline on commit drop as
select profile.updated_at
from content_factory.profiles profile
where profile.id = 'e6000000-0000-4000-8000-000000000001'::uuid;

select is(
  (
    select procedure.provolatile::text
    from pg_proc procedure
    where procedure.oid = 'public.creator_workspace_browser(jsonb)'::regprocedure
  ),
  's'::text,
  'Finder remains declared STABLE'
);

select is(
  (
    select procedure.provolatile::text
    from pg_proc procedure
    where procedure.oid = 'public.creator_workspace_section(jsonb)'::regprocedure
  ),
  'v'::text,
  'workspace section preserves multiplexer volatility'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_workspace_browser(jsonb)',
    'execute'
  ),
  'authenticated users retain Finder execute access'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_workspace_browser(jsonb)',
    'execute'
  ),
  'anonymous users retain no Finder execute access'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_workspace_section(jsonb)',
    'execute'
  ),
  'authenticated users retain workspace-section execute access'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_workspace_section(jsonb)',
    'execute'
  ),
  'anonymous users retain no workspace-section execute access'
);

select ok(
  position(
    'current_profile_id' in pg_get_functiondef(
      'public.creator_workspace_browser(jsonb)'::regprocedure
    )
  ) = 0
  and position(
    'creator_workspace_browser_pre_project_v47' in pg_get_functiondef(
      'public.creator_workspace_browser(jsonb)'::regprocedure
    )
  ) = 0,
  'Finder performs neither profile writes nor legacy organization scans'
);

select ok(
  position(
    'current_profile_id' in pg_get_functiondef(
      'public.creator_workspace_section(jsonb)'::regprocedure
    )
  ) = 0
  and position(
    'candidate.project_id = project_id_value' in pg_get_functiondef(
      'public.creator_workspace_section(jsonb)'::regprocedure
    )
  ) > 0,
  'project media is read directly without a profile write'
);

select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config(
  'request.jwt.claim.sub',
  'e6000000-0000-4000-8000-000000000001',
  true
);
set local role authenticated;

select lives_ok(
  $$select public.creator_workspace_browser(jsonb_build_object(
    'organization_id', 'e6100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'e6200000-0000-4000-8000-000000000001'::uuid,
    'page_size', 100
  ))$$,
  'empty selected-project Finder returns without scanning neighbor history'
);

select is(
  jsonb_array_length(
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', 'e6100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'e6200000-0000-4000-8000-000000000001'::uuid,
      'page_size', 100
    )) -> 'items'
  ),
  0,
  'empty Finder returns an exact empty item list'
);

select is(
  jsonb_array_length(
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', 'e6100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'e6200000-0000-4000-8000-000000000001'::uuid
    )) -> 'folders'
  ),
  1,
  'empty Finder retains only its selected project root'
);

select throws_ok(
  $$select public.creator_workspace_browser(jsonb_build_object(
    'organization_id', 'e6100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'e6200000-0000-4000-8000-000000000001'::uuid,
    'folder_id', 'e6200000-0000-4000-8000-000000000002'::uuid
  ))$$,
  '42501',
  'workspace_folder_project_mismatch',
  'Finder rejects a folder from a neighboring project'
);

-- Turn the preserved v4.7 section reader into a trap inside this rolled-back
-- test transaction. A selected-project media request must never reach it.
reset role;
create or replace function
  content_factory_private.creator_workspace_section_pre_project_reader_recovery_v416(
    p_payload jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  raise exception using errcode = '55000', message = 'legacy_reader_called';
end;
$$;
set local role authenticated;

select lives_ok(
  $$select public.creator_workspace_section(jsonb_build_object(
    'organization_id', 'e6100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'e6200000-0000-4000-8000-000000000001'::uuid,
    'section', 'media'
  ))$$,
  'empty project media bypasses the trapped legacy reader'
);

select is(
  jsonb_array_length(
    public.creator_workspace_section(jsonb_build_object(
      'organization_id', 'e6100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'e6200000-0000-4000-8000-000000000001'::uuid,
      'section', 'media'
    )) -> 'media'
  ),
  0,
  'empty project media returns an exact empty collection'
);

select is(
  jsonb_array_length(
    public.creator_workspace_section(jsonb_build_object(
      'organization_id', 'e6100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'e6200000-0000-4000-8000-000000000002'::uuid,
      'section', 'media'
    )) -> 'media'
  ),
  1,
  'populated project media is returned without the trapped legacy reader'
);

select is(
  public.creator_workspace_section(jsonb_build_object(
    'organization_id', 'e6100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'e6200000-0000-4000-8000-000000000002'::uuid,
    'section', 'media'
  )) #>> '{media,0,project_id}',
  'e6200000-0000-4000-8000-000000000002'::text,
  'media result preserves the exact selected project identity'
);

select throws_ok(
  $$select public.creator_workspace_section(jsonb_build_object(
    'organization_id', 'e6100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'e6200000-0000-4000-8000-000000000001'::uuid,
    'section', 'media',
    'cursor', jsonb_build_object('wrong_collection', jsonb_build_object(
      'at', now(),
      'id', 'e6300000-0000-4000-8000-000000000001'::uuid
    ))
  ))$$,
  '22023',
  'workspace_cursor_invalid',
  'direct media reader retains strict cursor validation'
);

reset role;

select is(
  (
    select profile.updated_at
    from content_factory.profiles profile
    where profile.id = 'e6000000-0000-4000-8000-000000000001'::uuid
  ),
  (
    select baseline.updated_at
    from project_reader_profile_baseline baseline
  ),
  'Finder and media reads do not update the profile row'
);

select * from finish();
rollback;
