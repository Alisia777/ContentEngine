begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(27);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values
  (
    'd1000000-0000-4000-8000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated',
    'authenticated',
    'selected-waiver-owner@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Selected Waiver Owner"}'::jsonb,
    now(),
    now()
  ),
  (
    'd1000000-0000-4000-8000-000000000002'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated',
    'authenticated',
    'selected-waiver-viewer@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Selected Waiver Viewer"}'::jsonb,
    now(),
    now()
  ),
  (
    'd1000000-0000-4000-8000-000000000003'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated',
    'authenticated',
    'selected-waiver-trainee@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Selected Waiver Trainee"}'::jsonb,
    now(),
    now()
  );

insert into content_factory.organizations (
  id, name, slug, status
) values (
  'd1100000-0000-4000-8000-000000000001'::uuid,
  'Selected Waiver pgTAP',
  'selected-waiver-pgtap',
  'active'
);

insert into content_factory.profiles (
  id, email, display_name, status
) values
  (
    'd1000000-0000-4000-8000-000000000001'::uuid,
    'selected-waiver-owner@example.test',
    'Selected Waiver Owner',
    'active'
  ),
  (
    'd1000000-0000-4000-8000-000000000002'::uuid,
    'selected-waiver-viewer@example.test',
    'Selected Waiver Viewer',
    'active'
  ),
  (
    'd1000000-0000-4000-8000-000000000003'::uuid,
    'selected-waiver-trainee@example.test',
    'Selected Waiver Trainee',
    'active'
  );

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    'd1100000-0000-4000-8000-000000000001'::uuid,
    'd1000000-0000-4000-8000-000000000001'::uuid,
    'owner',
    'active'
  ),
  (
    'd1100000-0000-4000-8000-000000000001'::uuid,
    'd1000000-0000-4000-8000-000000000002'::uuid,
    'viewer',
    'active'
  ),
  (
    'd1100000-0000-4000-8000-000000000001'::uuid,
    'd1000000-0000-4000-8000-000000000003'::uuid,
    'trainee',
    'active'
  );

-- The first two targets are valid and are processed before the intentionally
-- invalid owner transition. The exception must roll their changes back too.
select throws_ok(
  $$select public.system_grant_training_access_waiver_batch(jsonb_build_object(
    'organization_id', 'd1100000-0000-4000-8000-000000000001'::uuid,
    'changed_by', 'd1000000-0000-4000-8000-000000000001'::uuid,
    'reason', 'TEST-ONLY rollback proof for selected workspace waivers.',
    'idempotency_key', 'pgtap-selected-waiver-invalid-0001',
    'targets', jsonb_build_array(
      jsonb_build_object(
        'user_id', 'd1000000-0000-4000-8000-000000000002'::uuid,
        'role', 'operator'
      ),
      jsonb_build_object(
        'user_id', 'd1000000-0000-4000-8000-000000000003'::uuid,
        'role', 'operator'
      ),
      jsonb_build_object(
        'user_id', 'd1000000-0000-4000-8000-000000000001'::uuid,
        'role', 'operator'
      )
    )
  ))$$,
  '42501',
  'training_access_waiver_batch_role_not_allowed',
  'a bad third target rejects the complete batch'
);

select is(
  (
    select membership.role
    from content_factory.memberships membership
    where membership.profile_id =
      'd1000000-0000-4000-8000-000000000002'::uuid
  ),
  'viewer'::text,
  'failed batch leaves the first viewer unchanged'
);

select is(
  (
    select membership.role
    from content_factory.memberships membership
    where membership.profile_id =
      'd1000000-0000-4000-8000-000000000003'::uuid
  ),
  'trainee'::text,
  'failed batch leaves the second trainee unchanged'
);

select is(
  (
    select membership.role
    from content_factory.memberships membership
    where membership.profile_id =
      'd1000000-0000-4000-8000-000000000001'::uuid
  ),
  'owner'::text,
  'failed batch leaves the owner unchanged'
);

select is(
  (
    select count(*)
    from content_factory.training_access_waivers waiver
    where waiver.organization_id =
      'd1100000-0000-4000-8000-000000000001'::uuid
  ),
  0::bigint,
  'failed batch rolls back every waiver row'
);

select is(
  (
    select count(*)
    from content_factory.factory_events event
    where event.organization_id =
      'd1100000-0000-4000-8000-000000000001'::uuid
      and event.event_name in (
        'membership_role_changed_for_training_waiver',
        'training_access_waiver_granted'
      )
  ),
  0::bigint,
  'failed batch rolls back every audit event'
);

create temporary table selected_waiver_batch_result (
  result jsonb not null
) on commit drop;

insert into selected_waiver_batch_result (result)
select public.system_grant_training_access_waiver_batch(jsonb_build_object(
  'organization_id', 'd1100000-0000-4000-8000-000000000001'::uuid,
  'changed_by', 'd1000000-0000-4000-8000-000000000001'::uuid,
  'reason', 'TEST-ONLY successful selected workspace waiver batch.',
  'idempotency_key', 'pgtap-selected-waiver-success-0001',
  'targets', jsonb_build_array(
    jsonb_build_object(
      'user_id', 'd1000000-0000-4000-8000-000000000002'::uuid,
      'role', 'operator'
    ),
    jsonb_build_object(
      'user_id', 'd1000000-0000-4000-8000-000000000003'::uuid,
      'role', 'operator'
    ),
    jsonb_build_object(
      'user_id', 'd1000000-0000-4000-8000-000000000001'::uuid,
      'role', 'owner'
    )
  )
));

select ok(
  (
    select (batch.result ->> 'ok')::boolean
    from selected_waiver_batch_result batch
  ),
  'valid selected batch succeeds'
);

select is(
  (
    select (batch.result ->> 'target_count')::integer
    from selected_waiver_batch_result batch
  ),
  3,
  'valid selected batch reports all three targets'
);

select is(
  (
    select membership.role
    from content_factory.memberships membership
    where membership.profile_id =
      'd1000000-0000-4000-8000-000000000002'::uuid
  ),
  'operator'::text,
  'viewer is promoted to operator'
);

select is(
  (
    select membership.role
    from content_factory.memberships membership
    where membership.profile_id =
      'd1000000-0000-4000-8000-000000000003'::uuid
  ),
  'operator'::text,
  'trainee is promoted to operator'
);

select is(
  (
    select membership.role
    from content_factory.memberships membership
    where membership.profile_id =
      'd1000000-0000-4000-8000-000000000001'::uuid
  ),
  'owner'::text,
  'owner role is preserved'
);

select is(
  (
    select count(*)
    from content_factory.training_access_waivers waiver
    where waiver.organization_id =
      'd1100000-0000-4000-8000-000000000001'::uuid
      and waiver.scope = 'workspace_generation'
      and waiver.status = 'active'
  ),
  3::bigint,
  'all three targets receive active workspace waivers'
);

select is(
  (
    select count(*)
    from content_factory.memberships membership
    where membership.organization_id =
      'd1100000-0000-4000-8000-000000000001'::uuid
      and content_factory_private.training_access_waiver_active(
        membership.organization_id,
        membership.profile_id
      )
  ),
  3::bigint,
  'the effective waiver helper accepts all three resulting roles'
);

select is(
  (
    select waiver.previous_role || '>' || waiver.granted_role
    from content_factory.training_access_waivers waiver
    where waiver.profile_id =
      'd1000000-0000-4000-8000-000000000002'::uuid
  ),
  'viewer>operator'::text,
  'viewer transition remains reversible'
);

select is(
  (
    select waiver.previous_role || '>' || waiver.granted_role
    from content_factory.training_access_waivers waiver
    where waiver.profile_id =
      'd1000000-0000-4000-8000-000000000003'::uuid
  ),
  'trainee>operator'::text,
  'trainee transition remains reversible'
);

select is(
  (
    select waiver.previous_role || '>' || waiver.granted_role
    from content_factory.training_access_waivers waiver
    where waiver.profile_id =
      'd1000000-0000-4000-8000-000000000001'::uuid
  ),
  'owner>owner'::text,
  'owner waiver never demotes the owner'
);

select is(
  (
    select count(*)
    from content_factory.factory_events event
    where event.organization_id =
      'd1100000-0000-4000-8000-000000000001'::uuid
      and event.event_name = 'training_access_waiver_granted'
  ),
  3::bigint,
  'one audited waiver event is emitted per target'
);

select is(
  (
    select count(*)
    from content_factory.factory_events event
    where event.organization_id =
      'd1100000-0000-4000-8000-000000000001'::uuid
      and event.event_name =
        'membership_role_changed_for_training_waiver'
  ),
  2::bigint,
  'only viewer and trainee emit membership role changes'
);

select is(
  (
    select count(*)
    from content_factory.training_attempts attempt
    where attempt.organization_id =
      'd1100000-0000-4000-8000-000000000001'::uuid
  ),
  0::bigint,
  'batch does not fabricate training attempts'
);

select is(
  (
    select count(*)
    from content_factory.training_certifications certification
    where certification.organization_id =
      'd1100000-0000-4000-8000-000000000001'::uuid
  ),
  0::bigint,
  'batch does not fabricate training certifications'
);

select is(
  (
    select count(*)
    from content_factory.training_practical_projects project
    where project.organization_id =
      'd1100000-0000-4000-8000-000000000001'::uuid
  ),
  0::bigint,
  'batch does not fabricate practical projects'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'd1000000-0000-4000-8000-000000000001',
    true
  );
  perform set_config('request.jwt.claim.role', 'authenticated', true);
end;
$$;

create temporary table selected_waiver_bootstrap_result (
  result jsonb not null
) on commit drop;

insert into selected_waiver_bootstrap_result (result)
select public.creator_bootstrap('{}'::jsonb);

select is(
  (
    select bootstrap.result ->> 'state'
    from selected_waiver_bootstrap_result bootstrap
  ),
  'workspace'::text,
  'owner waiver opens the final bootstrap workspace state'
);

select is(
  (
    select (bootstrap.result ->> 'workspace_open')::boolean
    from selected_waiver_bootstrap_result bootstrap
  ),
  true,
  'owner waiver opens the workspace capability'
);

select is(
  (
    select (bootstrap.result #>> '{training,access_waiver,active}')::boolean
    from selected_waiver_bootstrap_result bootstrap
  ),
  true,
  'owner bootstrap projects the active waiver'
);

select is(
  (
    select bootstrap.result #>> '{training,access_waiver,scope}'
    from selected_waiver_bootstrap_result bootstrap
  ),
  'workspace_generation'::text,
  'owner bootstrap projects the bounded waiver scope'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_grant_training_access_waiver_batch(jsonb)',
    'execute'
  ),
  'authenticated cannot execute the batch grant'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_grant_training_access_waiver_batch(jsonb)',
    'execute'
  ),
  'service role can execute the batch grant'
);

select * from finish();
rollback;
