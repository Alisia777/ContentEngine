begin;

-- The function declares organization_id as a PL/pgSQL variable and opts into
-- use_variable conflict handling.  A bare ON CONFLICT column list is therefore
-- parsed as expressions over those variables instead of the table identity
-- columns and PostgreSQL cannot infer the primary-key arbiter.  Name the
-- immutable table constraint explicitly so both first grants and reactivation
-- use the intended project-member identity.
create or replace function public.creator_grant_project_member(
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
  user_id uuid;
  organization_id uuid;
  project_id_value uuid;
  target_profile_id uuid;
  idempotency_key text;
  request_value jsonb;
  replay_value jsonb;
  result_value jsonb;
  target_role text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'profile_id', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'project_member_grant_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id,
    project_id_value
  );
  target_profile_id := content_factory_private.require_uuid(
    p_payload,
    'profile_id'
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );

  request_value := jsonb_build_object(
    'project_id', project_id_value,
    'profile_id', target_profile_id,
    'access_role', 'member'
  );
  replay_value := content_factory_private.begin_command(
    organization_id,
    'creator_grant_project_member',
    idempotency_key,
    request_value
  );
  if replay_value is not null then
    return replay_value;
  end if;

  select membership.role
    into target_role
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where membership.organization_id = organization_id
    and membership.profile_id = target_profile_id
    and membership.status = 'active'
    and membership.role in (
      'owner', 'admin', 'producer', 'reviewer', 'operator'
    );
  if target_role is null then
    raise exception using
      errcode = 'P0002', message = 'project_member_target_not_operational';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext(
      'workspace-project-member:' || project_id_value::text
      || ':' || target_profile_id::text
    )
  );
  insert into content_factory.workspace_project_memberships (
    organization_id, project_id, profile_id, access_role, status,
    granted_by, updated_by
  ) values (
    organization_id, project_id_value, target_profile_id, 'member', 'active',
    user_id, user_id
  )
  on conflict on constraint workspace_project_memberships_pkey do update
  set status = 'active',
      access_role = 'member',
      updated_by = excluded.updated_by,
      updated_at = now();

  result_value := jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'profile_id', target_profile_id,
    'organization_role', target_role,
    'access_role', 'member',
    'status', 'active'
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'workspace_project_member_granted',
    'workspace_project',
    project_id_value::text,
    jsonb_build_object('profile_id', target_profile_id),
    left('workspace-project-member-granted:' || idempotency_key, 180)
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_grant_project_member',
    idempotency_key,
    request_value,
    result_value
  );
end;
$$;

revoke all on function public.creator_grant_project_member(jsonb)
  from public, anon;
grant execute on function public.creator_grant_project_member(jsonb)
  to authenticated;

comment on function public.creator_grant_project_member(jsonb) is
  'Idempotently grants or reactivates one project membership using the explicit project-member primary-key arbiter.';

notify pgrst, 'reload schema';

commit;
