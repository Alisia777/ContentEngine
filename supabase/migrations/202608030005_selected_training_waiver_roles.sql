begin;

-- Selected workspace waivers may preserve an owner or promote a reviewed
-- viewer/trainee to operator.  No course, practical, exam or certification
-- evidence is manufactured.  Revocation continues to restore previous_role.
alter table content_factory.training_access_waivers
  drop constraint if exists training_access_waivers_previous_role_check;
alter table content_factory.training_access_waivers
  drop constraint if exists training_access_waivers_granted_role_check;
alter table content_factory.training_access_waivers
  drop constraint if exists training_access_waivers_role_transition_check;

alter table content_factory.training_access_waivers
  add constraint training_access_waivers_previous_role_check
    check (previous_role in ('viewer', 'trainee', 'operator', 'owner')),
  add constraint training_access_waivers_granted_role_check
    check (granted_role in ('operator', 'owner')),
  add constraint training_access_waivers_role_transition_check
    check (
      (
        granted_role = 'operator'
        and previous_role in ('viewer', 'trainee', 'operator')
      )
      or (
        granted_role = 'owner'
        and previous_role = 'owner'
      )
    );

-- Keep every lock state fail-closed, while allowing the active waiver helper
-- to reopen workspace state for either a promoted operator or a preserved owner.
create or replace function public.creator_bootstrap(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  result jsonb;
  user_id uuid;
  organization_id uuid;
  actor_role text;
  waiver_row content_factory.training_access_waivers%rowtype;
begin
  result :=
    content_factory_private.creator_bootstrap_pre_training_waiver(p_payload);

  if jsonb_typeof(result) <> 'object'
     or coalesce(result ->> 'state', '') not in ('learning', 'workspace')
     or nullif(result #>> '{organization,id}', '') is null then
    return result;
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := (result #>> '{organization,id}')::uuid;

  select membership.role into actor_role
  from content_factory.memberships membership
  where membership.organization_id = organization_id
    and membership.profile_id = user_id
    and membership.status = 'active';

  if actor_role not in ('operator', 'owner')
     or not content_factory_private.training_access_waiver_active(
       organization_id,
       user_id
     ) then
    return result;
  end if;

  select waiver.* into waiver_row
  from content_factory.training_access_waivers waiver
  where waiver.organization_id = organization_id
    and waiver.profile_id = user_id
    and waiver.scope = 'workspace_generation'
    and waiver.status = 'active';

  result := jsonb_set(result, '{state}', '"workspace"'::jsonb, true);
  result := jsonb_set(result, '{workspace_open}', 'true'::jsonb, true);
  result := jsonb_set(
    result, '{capabilities,mock_generation}', 'true'::jsonb, true
  );
  result := jsonb_set(
    result, '{capabilities,real_generation}', 'true'::jsonb, true
  );
  result := jsonb_set(
    result,
    '{learning,practical_project_required}',
    'false'::jsonb,
    true
  );
  result := result || jsonb_build_object(
    'training',
    coalesce(result -> 'training', '{}'::jsonb) || jsonb_build_object(
      'access_waiver',
      jsonb_build_object(
        'active', true,
        'scope', waiver_row.scope,
        'reason', waiver_row.grant_reason,
        'granted_at', waiver_row.granted_at
      )
    )
  );

  return result;
end;
$$;

revoke all on function public.creator_bootstrap(jsonb)
  from public, anon;
grant execute on function public.creator_bootstrap(jsonb)
  to authenticated;

-- One service-only command grants the reviewed three-account set in a single
-- database transaction.  A failure for any target rolls the whole command back.
create or replace function public.system_grant_training_access_waiver_batch(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  changed_by_id uuid;
  reason_value text;
  idempotency_key_value text;
  targets_value jsonb;
  request_payload jsonb;
  replay jsonb;
  actor_role text;
  target_value jsonb;
  target_user_id uuid;
  target_role_value text;
  expected_role_value text;
  target_user_ids uuid[] := '{}'::uuid[];
  membership_row content_factory.memberships%rowtype;
  waiver_row content_factory.training_access_waivers%rowtype;
  previous_role_value text;
  role_changed boolean;
  already_in_state boolean;
  results jsonb := '[]'::jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id',
    'changed_by',
    'reason',
    'idempotency_key',
    'targets'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'training_access_waiver_batch_payload_invalid';
  end if;

  organization_id := content_factory_private.require_uuid(
    p_payload,
    'organization_id'
  );
  changed_by_id := content_factory_private.require_uuid(
    p_payload,
    'changed_by'
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
  targets_value := p_payload -> 'targets';
  if coalesce(jsonb_typeof(targets_value), '') <> 'array'
     or jsonb_array_length(targets_value) <> 3 then
    raise exception using
      errcode = '22023',
      message = 'training_access_waiver_batch_targets_invalid';
  end if;

  request_payload := jsonb_build_object(
    'organization_id', organization_id,
    'changed_by', changed_by_id,
    'reason', reason_value,
    'targets', targets_value
  );

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('system_training_access_waiver_batch')
  );

  select membership.role into actor_role
  from content_factory.memberships membership
  join content_factory.organizations organization
    on organization.id = membership.organization_id
   and organization.status = 'active'
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  join auth.users auth_user
    on auth_user.id = membership.profile_id
   and auth_user.email_confirmed_at is not null
   and auth_user.deleted_at is null
   and (
     auth_user.banned_until is null
     or auth_user.banned_until <= now()
   )
  where membership.organization_id = organization_id
    and membership.profile_id = changed_by_id
    and membership.status = 'active'
    and membership.role in ('owner', 'admin');

  if actor_role is null then
    raise exception using
      errcode = '42501',
      message = 'training_access_waiver_batch_actor_not_authorized';
  end if;

  replay := content_factory_private.begin_command(
    organization_id,
    'system_grant_training_access_waiver_batch',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  for target_value in
    select target.item
    from jsonb_array_elements(targets_value)
      with ordinality as target(item, position)
    order by target.position
  loop
    if jsonb_typeof(target_value) <> 'object'
       or target_value - array['user_id', 'role']::text[] <> '{}'::jsonb then
      raise exception using
        errcode = '22023',
        message = 'training_access_waiver_batch_target_invalid';
    end if;

    target_user_id := content_factory_private.require_uuid(
      target_value,
      'user_id'
    );
    target_role_value := lower(nullif(btrim(coalesce(
      target_value ->> 'role',
      ''
    )), ''));
    if target_user_id = any(target_user_ids) then
      raise exception using
        errcode = '22023',
        message = 'training_access_waiver_batch_target_duplicate';
    end if;
    target_user_ids := array_append(target_user_ids, target_user_id);

    if not exists (
      select 1
      from content_factory.profiles profile
      join auth.users auth_user
        on auth_user.id = profile.id
       and auth_user.email_confirmed_at is not null
       and auth_user.deleted_at is null
       and (
         auth_user.banned_until is null
         or auth_user.banned_until <= now()
       )
      where profile.id = target_user_id
        and profile.status = 'active'
    ) then
      raise exception using
        errcode = '42501',
        message = 'training_access_waiver_batch_target_not_active';
    end if;

    membership_row := null;
    select membership.* into membership_row
    from content_factory.memberships membership
    where membership.organization_id = organization_id
      and membership.profile_id = target_user_id
      and membership.status = 'active'
    for update;

    if membership_row.id is null then
      raise exception using
        errcode = '42501',
        message = 'training_access_waiver_batch_membership_not_active';
    end if;

    expected_role_value := case
      when membership_row.role in ('viewer', 'trainee', 'operator')
        then 'operator'
      when membership_row.role = 'owner'
        then 'owner'
      else null
    end;
    if expected_role_value is null
       or target_role_value is distinct from expected_role_value then
      raise exception using
        errcode = '42501',
        message = 'training_access_waiver_batch_role_not_allowed';
    end if;

    waiver_row := null;
    select waiver.* into waiver_row
    from content_factory.training_access_waivers waiver
    where waiver.organization_id = organization_id
      and waiver.profile_id = target_user_id
    for update;

    already_in_state :=
      waiver_row.id is not null and waiver_row.status = 'active';
    if already_in_state
       and waiver_row.granted_role is distinct from expected_role_value then
      raise exception using
        errcode = '55000',
        message = 'training_access_waiver_batch_state_conflict';
    end if;

    previous_role_value := case
      when already_in_state then waiver_row.previous_role
      else membership_row.role
    end;
    role_changed := false;

    if membership_row.role <> expected_role_value then
      update content_factory.memberships membership
      set
        role = expected_role_value,
        updated_at = now()
      where membership.id = membership_row.id;
      membership_row.role := expected_role_value;
      role_changed := true;
    end if;

    if waiver_row.id is null then
      insert into content_factory.training_access_waivers (
        organization_id,
        profile_id,
        status,
        previous_role,
        granted_role,
        grant_reason,
        granted_by,
        granted_at,
        revoked_by,
        revoked_at,
        revocation_reason,
        updated_at
      ) values (
        organization_id,
        target_user_id,
        'active',
        previous_role_value,
        expected_role_value,
        reason_value,
        changed_by_id,
        now(),
        null,
        null,
        null,
        now()
      )
      returning * into waiver_row;
    elsif not already_in_state then
      update content_factory.training_access_waivers waiver
      set
        status = 'active',
        previous_role = previous_role_value,
        granted_role = expected_role_value,
        grant_reason = reason_value,
        granted_by = changed_by_id,
        granted_at = now(),
        revoked_by = null,
        revoked_at = null,
        revocation_reason = null,
        updated_at = now()
      where waiver.id = waiver_row.id
      returning waiver.* into waiver_row;
    end if;

    if role_changed then
      perform content_factory_private.emit_event(
        organization_id,
        changed_by_id,
        'membership_role_changed_for_training_waiver',
        'membership',
        membership_row.id::text,
        jsonb_build_object(
          'target_user_id', target_user_id,
          'from_role', previous_role_value,
          'to_role', membership_row.role
        ),
        'training-waiver-batch-role:'
          || idempotency_key_value || ':' || target_user_id::text,
        'system'
      );
    end if;

    perform content_factory_private.emit_event(
      organization_id,
      changed_by_id,
      'training_access_waiver_granted',
      'training_access_waiver',
      waiver_row.id::text,
      jsonb_build_object(
        'target_user_id', target_user_id,
        'scope', waiver_row.scope,
        'role', membership_row.role,
        'already_active', already_in_state,
        'batch', true
      ),
      'training-waiver-batch-grant:'
        || idempotency_key_value || ':' || target_user_id::text,
      'system'
    );

    results := results || jsonb_build_array(jsonb_build_object(
      'user_id', target_user_id,
      'waiver_id', waiver_row.id,
      'waiver_active', true,
      'role', membership_row.role,
      'previous_role', previous_role_value,
      'role_changed', role_changed,
      'already_active', already_in_state
    ));
  end loop;

  result := jsonb_build_object(
    'ok', true,
    'action', 'grant',
    'organization_id', organization_id,
    'target_count', jsonb_array_length(results),
    'targets', results
  );

  return content_factory_private.finish_command(
    organization_id,
    changed_by_id,
    'system_grant_training_access_waiver_batch',
    idempotency_key_value,
    request_payload,
    result
  );
end;
$$;

revoke all on function
  public.system_grant_training_access_waiver_batch(jsonb)
  from public, anon, authenticated;
grant execute on function
  public.system_grant_training_access_waiver_batch(jsonb)
  to service_role;

do $selected_training_waiver_contract$
declare
  bootstrap_definition text;
  batch_definition text;
begin
  select pg_get_functiondef(
    'public.creator_bootstrap(jsonb)'::regprocedure
  ) into bootstrap_definition;
  select pg_get_functiondef(
    'public.system_grant_training_access_waiver_batch(jsonb)'::regprocedure
  ) into batch_definition;

  if strpos(bootstrap_definition, 'actor_role not in (''operator'', ''owner'')') = 0
     or strpos(bootstrap_definition, 'training_access_waiver_active(') = 0 then
    raise exception 'selected_training_waiver_bootstrap_invalid';
  end if;
  if strpos(batch_definition, '''viewer'', ''trainee'', ''operator''') = 0
     or strpos(batch_definition, 'when membership_row.role = ''owner''') = 0
     or strpos(batch_definition, 'jsonb_array_length(targets_value) <> 3') = 0
     or strpos(batch_definition, 'system_grant_training_access_waiver_batch') = 0 then
    raise exception 'selected_training_waiver_batch_invalid';
  end if;
  if strpos(batch_definition, 'training_certifications') > 0
     or strpos(batch_definition, 'training_attempts') > 0
     or strpos(batch_definition, 'training_practical_projects') > 0 then
    raise exception 'selected_training_waiver_fabricates_training_state';
  end if;
  if has_function_privilege(
       'authenticated',
       'public.system_grant_training_access_waiver_batch(jsonb)',
       'execute'
     )
     or has_function_privilege(
       'anon',
       'public.system_grant_training_access_waiver_batch(jsonb)',
       'execute'
     ) then
    raise exception 'selected_training_waiver_privileges_invalid';
  end if;
end;
$selected_training_waiver_contract$;

commit;
