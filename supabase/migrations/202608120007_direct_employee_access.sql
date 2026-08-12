begin;

-- Trusted, atomic finalization for an already provisioned employee.  The
-- caller must create/confirm the Auth user first; this RPC only connects that
-- identity to durable organization and project access.
create or replace function public.system_admin_finalize_employee_access(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  target_user_id uuid;
  changed_by_id uuid;
  display_name_value text;
  current_display_name text;
  finalized_display_name text;
  reason_value text;
  idempotency_key_value text;
  password_dispatch_id_value text;
  waiver_idempotency_key text;
  request_payload jsonb;
  replay jsonb;
  waiver_result jsonb;
  result jsonb;
  actor_role text;
  target_role text;
  target_membership_id uuid;
  active_project_count bigint := 0;
  active_project_membership_count bigint := 0;
  projects_granted_or_reactivated bigint := 0;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception using errcode = '42501', message = 'service_role_required';
  end if;

  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.require_admin_keys(
    p_payload,
    array[
      'organization_id', 'user_id', 'changed_by', 'display_name', 'reason',
      'idempotency_key', 'password_dispatch_id'
    ],
    array[
      'organization_id', 'user_id', 'changed_by', 'display_name', 'reason',
      'idempotency_key', 'password_dispatch_id'
    ]
  );

  organization_id := content_factory_private.require_uuid(
    p_payload,
    'organization_id'
  );
  target_user_id := content_factory_private.require_uuid(p_payload, 'user_id');
  changed_by_id := content_factory_private.require_uuid(
    p_payload,
    'changed_by'
  );
  display_name_value := content_factory_private.require_text(
    p_payload,
    'display_name',
    1,
    180
  );
  reason_value := content_factory_private.require_text(
    p_payload,
    'reason',
    10,
    1000
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    12,
    180
  );
  password_dispatch_id_value := content_factory_private.require_text(
    p_payload,
    'password_dispatch_id',
    8,
    200
  );
  if password_dispatch_id_value !~ '^[A-Za-z0-9._:-]+$' then
    raise exception using
      errcode = '22023',
      message = 'password_dispatch_id_invalid';
  end if;

  request_payload := jsonb_build_object(
    'organization_id', organization_id,
    'user_id', target_user_id,
    'changed_by', changed_by_id,
    'display_name', display_name_value,
    'reason', reason_value,
    'password_dispatch_id', password_dispatch_id_value
  );
  waiver_idempotency_key :=
    'admin-finalize-waiver:' || content_factory_private.json_hash(
      jsonb_build_object('idempotency_key', idempotency_key_value)
    );

  -- This is the first concurrency lock.  Offboarding, account binding, and
  -- project access grants use the same barrier for this organization/member.
  perform content_factory_private.lock_admin_member(
    organization_id,
    target_user_id
  );

  if not exists (
    select 1
    from content_factory.organizations organization
    where organization.id = organization_id
      and organization.status = 'active'
  ) then
    raise exception using errcode = '42501', message = 'organization_not_active';
  end if;

  select member.role into actor_role
  from content_factory.memberships member
  join content_factory.profiles profile
    on profile.id = member.profile_id
   and profile.status = 'active'
  join auth.users auth_user
    on auth_user.id = member.profile_id
   and auth_user.email_confirmed_at is not null
   and auth_user.deleted_at is null
   and (
     auth_user.banned_until is null
     or auth_user.banned_until <= now()
   )
  where member.organization_id = organization_id
    and member.profile_id = changed_by_id
    and member.status = 'active'
    and member.role in ('owner', 'admin');

  if actor_role is null then
    raise exception using
      errcode = '42501',
      message = 'employee_access_actor_not_authorized';
  end if;

  -- Lock the profile/Auth identity without locking the membership yet.  The
  -- waiver RPC owns its advisory lock before it locks the membership; keeping
  -- that ordering prevents a cycle with a concurrent waiver operation.
  select member.role, profile.display_name
    into target_role, current_display_name
  from content_factory.memberships member
  join content_factory.profiles profile
    on profile.id = member.profile_id
   and profile.status = 'active'
  join auth.users auth_user
    on auth_user.id = member.profile_id
   and auth_user.email_confirmed_at is not null
   and nullif(btrim(coalesce(auth_user.encrypted_password, '')), '') is not null
   and lower(auth_user.email) = 'v.klimov1313@gmail.com'
   and auth_user.created_at =
     timestamptz '2026-08-11 18:31:57.031658+00'
   and auth_user.last_sign_in_at is null
   and auth_user.raw_user_meta_data = jsonb_build_object(
     'invited_by', changed_by_id::text,
     'intended_role', 'trainee',
     'organization_id', organization_id::text,
     'email_verified', true
   )
   and auth_user.deleted_at is null
   and (
     auth_user.banned_until is null
     or auth_user.banned_until <= now()
   )
   and auth_user.raw_app_meta_data = jsonb_build_object(
     'provider', 'email',
     'providers', jsonb_build_array('email'),
     'contentengine_password_change_required', true,
     'contentengine_password_change_completed', false,
     'contentengine_password_dispatch_id', password_dispatch_id_value,
     'contentengine_klimov_direct_access_v1', true
   )
  where member.organization_id = organization_id
    and member.profile_id = target_user_id
    and member.status = 'active'
    and member.role in ('trainee', 'operator')
  for update of profile, auth_user;

  if target_role is null then
    raise exception using
      errcode = '42501',
      message = 'employee_access_target_not_eligible';
  end if;
  if not exists (
    select 1
    from content_factory.member_password_dispatches dispatch
    where dispatch.dispatch_id = password_dispatch_id_value
      and dispatch.account_slot = 'klimov'
      and dispatch.status in ('identity_applied', 'completed')
  ) then
    raise exception using
      errcode = '42501',
      message = 'employee_password_dispatch_not_applied';
  end if;
  if current_display_name is not null
     and btrim(current_display_name) <> ''
     and current_display_name <> display_name_value then
    raise exception using
      errcode = '23505',
      message = 'employee_display_name_conflict';
  end if;

  replay := content_factory_private.begin_command(
    organization_id,
    'system_admin_finalize_employee_access',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  -- Hold the same organization-wide structure lock as project create/archive
  -- while taking the project snapshot and installing memberships.  A project
  -- therefore cannot appear or disappear between the grant and count checks.
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('workspace_structure')
  );

  waiver_result := public.system_set_training_access_waiver(
    jsonb_build_object(
      'organization_id', organization_id,
      'user_id', target_user_id,
      'changed_by', changed_by_id,
      'action', 'grant',
      'reason', reason_value,
      'role', 'operator',
      'idempotency_key', waiver_idempotency_key
    )
  );
  if waiver_result -> 'waiver_active' is distinct from 'true'::jsonb
     or waiver_result ->> 'role' is distinct from 'operator' then
    raise exception using
      errcode = '55000',
      message = 'employee_access_waiver_not_granted';
  end if;

  select member.id, member.role
    into target_membership_id, target_role
  from content_factory.memberships member
  where member.organization_id = organization_id
    and member.profile_id = target_user_id
    and member.status = 'active'
  for update;

  if target_membership_id is null or target_role <> 'operator' then
    raise exception using
      errcode = '55000',
      message = 'employee_access_operator_role_not_active';
  end if;
  if not exists (
    select 1
    from content_factory.training_access_waivers waiver
    where waiver.organization_id = organization_id
      and waiver.profile_id = target_user_id
      and waiver.status = 'active'
      and waiver.scope = 'workspace_generation'
      and waiver.previous_role = 'trainee'
      and waiver.granted_role = 'operator'
      and waiver.grant_reason = reason_value
      and waiver.granted_by = changed_by_id
  ) then
    raise exception using
      errcode = '55000',
      message = 'employee_access_waiver_not_active';
  end if;

  update content_factory.profiles profile
  set
    display_name = display_name_value,
    updated_at = now()
  where profile.id = target_user_id
    and (
      profile.display_name is null
      or btrim(profile.display_name) = ''
      or profile.display_name = display_name_value
    )
  returning profile.display_name into finalized_display_name;

  if finalized_display_name is null then
    raise exception using
      errcode = '23505',
      message = 'employee_display_name_conflict';
  end if;

  insert into content_factory.workspace_project_memberships as project_member (
    organization_id,
    project_id,
    profile_id,
    access_role,
    status,
    granted_by,
    updated_by
  )
  select
    project.organization_id,
    project.id,
    target_user_id,
    'member',
    'active',
    changed_by_id,
    changed_by_id
  from content_factory.workspace_folders project
  where project.organization_id = organization_id
    and project.kind = 'project'
    and project.status = 'active'
  order by project.id
  on conflict on constraint workspace_project_memberships_pkey do update
  set
    status = 'active',
    access_role = 'member',
    updated_by = excluded.updated_by,
    updated_at = now()
  where project_member.status = 'revoked';
  get diagnostics projects_granted_or_reactivated = row_count;

  select count(*) into active_project_count
  from content_factory.workspace_folders project
  where project.organization_id = organization_id
    and project.kind = 'project'
    and project.status = 'active';

  select count(*) into active_project_membership_count
  from content_factory.workspace_project_memberships project_member
  join content_factory.workspace_folders project
    on project.organization_id = project_member.organization_id
   and project.id = project_member.project_id
   and project.kind = 'project'
   and project.status = 'active'
  where project_member.organization_id = organization_id
    and project_member.profile_id = target_user_id
    and project_member.status = 'active'
    and project_member.access_role = 'member';

  if active_project_count <> active_project_membership_count then
    raise exception using
      errcode = '55000',
      message = 'employee_access_project_memberships_incomplete',
      detail = jsonb_build_object(
        'active_project_count', active_project_count,
        'active_project_membership_count', active_project_membership_count
      )::text;
  end if;

  result := jsonb_build_object(
    'ok', true,
    'organization_id', organization_id,
    'user_id', target_user_id,
    'role', 'operator',
    'waiver_active', true,
    'active_project_count', active_project_count,
    'active_project_membership_count', active_project_membership_count,
    'projects_granted_or_reactivated', projects_granted_or_reactivated
  );

  perform content_factory_private.emit_event(
    organization_id,
    changed_by_id,
    'admin_employee_access_finalized',
    'membership',
    target_membership_id::text,
    jsonb_build_object(
      'target_user_id', target_user_id,
      'display_name', finalized_display_name,
      'role', 'operator',
      'waiver_active', true,
      'active_project_count', active_project_count,
      'active_project_membership_count', active_project_membership_count,
      'projects_granted_or_reactivated', projects_granted_or_reactivated,
      'reason', reason_value
    ),
    'admin-employee-access-finalized:' || content_factory_private.json_hash(
      jsonb_build_object('idempotency_key', idempotency_key_value)
    ),
    'system'
  );

  return content_factory_private.finish_command(
    organization_id,
    changed_by_id,
    'system_admin_finalize_employee_access',
    idempotency_key_value,
    request_payload,
    result
  );
end;
$$;

revoke all on function public.system_admin_finalize_employee_access(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_admin_finalize_employee_access(jsonb)
  to service_role;

notify pgrst, 'reload schema';

commit;
