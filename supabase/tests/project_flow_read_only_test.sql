begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(12);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'e5000000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  'project-flow-read-only@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Project Flow Read Only"}'::jsonb,
  now(),
  now()
);

insert into content_factory.organizations (
  id, name, slug, status
) values (
  'e5100000-0000-4000-8000-000000000001'::uuid,
  'Project Flow Read Only pgTAP',
  'project-flow-read-only-pgtap',
  'active'
);

update content_factory.profiles profile
set display_name = 'Project Flow Read Only', status = 'active'
where profile.id = 'e5000000-0000-4000-8000-000000000001'::uuid;

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'e5100000-0000-4000-8000-000000000001'::uuid,
  'e5000000-0000-4000-8000-000000000001'::uuid,
  'owner',
  'active'
);

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'e5100000-0000-4000-8000-000000000001'::uuid,
  'e5000000-0000-4000-8000-000000000001'::uuid,
  'owner',
  'owner',
  'TEST-ONLY waiver for the read-only project catalog contract.',
  'e5000000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values (
  'e5200000-0000-4000-8000-000000000001'::uuid,
  'e5100000-0000-4000-8000-000000000001'::uuid,
  null,
  'Read-only catalog project',
  'emerald',
  'project',
  'active',
  1024,
  'e5000000-0000-4000-8000-000000000001'::uuid,
  'e5000000-0000-4000-8000-000000000001'::uuid
);

update content_factory.profiles profile
set updated_at = '2000-01-01 00:00:00+00'::timestamptz
where profile.id = 'e5000000-0000-4000-8000-000000000001'::uuid;

select is(
  (
    select procedure.provolatile::text
    from pg_proc procedure
    where procedure.oid = 'public.creator_project_flow(jsonb)'::regprocedure
  ),
  's'::text,
  'project flow remains declared STABLE'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_project_flow(jsonb)',
    'execute'
  ),
  'authenticated users retain project-flow execute access'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_project_flow(jsonb)',
    'execute'
  ),
  'anonymous users retain no project-flow execute access'
);

select ok(
  position(
    'current_profile_id' in pg_get_functiondef(
      'public.creator_project_flow(jsonb)'::regprocedure
    )
  ) = 0
  and position(
    'auth.uid()' in pg_get_functiondef(
      'public.creator_project_flow(jsonb)'::regprocedure
    )
  ) > 0,
  'project flow authenticates without a profile upsert'
);

select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config(
  'request.jwt.claim.sub',
  'e5000000-0000-4000-8000-000000000001',
  true
);
set local role authenticated;

select lives_ok(
  $$select public.creator_project_flow(jsonb_build_object(
    'organization_id', 'e5100000-0000-4000-8000-000000000001'::uuid
  ))$$,
  'bare project catalog works without project_id'
);

select is(
  public.creator_project_flow(jsonb_build_object(
    'organization_id', 'e5100000-0000-4000-8000-000000000001'::uuid
  )) ->> 'project_id',
  null::text,
  'bare project catalog does not invent a selected project'
);

select is(
  jsonb_array_length(
    public.creator_project_flow(jsonb_build_object(
      'organization_id', 'e5100000-0000-4000-8000-000000000001'::uuid
    )) -> 'projects'
  ),
  1,
  'bare project catalog returns the active project'
);

select is(
  public.creator_project_flow(jsonb_build_object(
    'organization_id', 'e5100000-0000-4000-8000-000000000001'::uuid
  )) #>> '{projects,0,id}',
  'e5200000-0000-4000-8000-000000000001'::text,
  'bare project catalog preserves the exact project identity'
);

select is(
  public.creator_project_flow(jsonb_build_object(
    'organization_id', 'e5100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'e5200000-0000-4000-8000-000000000001'::uuid
  )) ->> 'project_id',
  'e5200000-0000-4000-8000-000000000001'::text,
  'selected-project flow preserves its requested project_id'
);

select is(
  public.creator_project_flow(jsonb_build_object(
    'organization_id', 'e5100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'e5200000-0000-4000-8000-000000000001'::uuid
  )) #>> '{project,id}',
  'e5200000-0000-4000-8000-000000000001'::text,
  'selected-project flow still returns the exact project snapshot'
);

select is(
  public.creator_project_flow(jsonb_build_object(
    'organization_id', 'e5100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'e5200000-0000-4000-8000-000000000001'::uuid
  )) #>> '{projects,0,catalog_state}',
  'exact'::text,
  'selected project keeps its exact catalog marker'
);

reset role;

select is(
  (
    select profile.updated_at
    from content_factory.profiles profile
    where profile.id = 'e5000000-0000-4000-8000-000000000001'::uuid
  ),
  '2000-01-01 00:00:00+00'::timestamptz,
  'project catalog and selected flow do not update the profile row'
);

select * from finish();
rollback;
