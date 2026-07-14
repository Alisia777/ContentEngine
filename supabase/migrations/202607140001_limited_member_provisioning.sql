begin;

-- Keep Storage mutations aligned with creator_register_media. Read behavior is
-- intentionally unchanged: every certified member may read their own objects,
-- while the existing manager roles may additionally read team objects.
create or replace function content_factory.storage_access_allowed(
  p_organization_id text,
  p_owner_id text,
  p_allow_team_read boolean default false
)
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select auth.uid() is not null and exists (
    select 1
    from content_factory.memberships membership
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    join content_factory.organizations organization
      on organization.id = membership.organization_id
     and organization.status = 'active'
    join content_factory.training_certifications certification
      on certification.organization_id = membership.organization_id
     and certification.profile_id = membership.profile_id
     and certification.module_code = 'operator_final_exam'
     and certification.status = 'passed'
     and (certification.expires_at is null or certification.expires_at > now())
    where membership.profile_id = auth.uid()
      and membership.status = 'active'
      and membership.organization_id::text = p_organization_id
      and (
        (
          p_allow_team_read
          and (
            p_owner_id = auth.uid()::text
            or membership.role in ('owner', 'admin', 'producer', 'reviewer')
          )
        )
        or (
          not p_allow_team_read
          and p_owner_id = auth.uid()::text
          and membership.role in (
            'owner', 'admin', 'producer', 'reviewer', 'operator'
          )
        )
      )
  )
$$;

revoke all on function content_factory.storage_access_allowed(text, text, boolean)
  from public, anon;
grant execute on function content_factory.storage_access_allowed(text, text, boolean)
  to authenticated;

-- Trusted, deliberately narrow provisioning for accounts that do not need the
-- training-gated invitation flow. Only service_role may call this function.
create or replace function public.system_provision_limited_member(
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
  target_user_id uuid;
  provisioned_by_id uuid;
  requested_role text;
  target_email text;
  target_display_name text;
  target_email_confirmed_at timestamptz;
  target_banned_until timestamptz;
  target_deleted_at timestamptz;
  target_profile_status text;
  provisioner_role text;
  membership_row content_factory.memberships%rowtype;
  request_payload jsonb;
  stable_idempotency_key text;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id := content_factory_private.require_uuid(
    p_payload,
    'organization_id'
  );
  target_user_id := content_factory_private.require_uuid(p_payload, 'user_id');
  provisioned_by_id := content_factory_private.require_uuid(
    p_payload,
    'provisioned_by'
  );
  requested_role := lower(content_factory_private.require_text(
    p_payload,
    'role',
    3,
    20
  ));

  if requested_role not in ('viewer', 'trainee') then
    raise exception using errcode = '22023', message = 'limited_member_role_invalid';
  end if;

  request_payload := jsonb_build_object(
    'organization_id', organization_id,
    'user_id', target_user_id,
    'provisioned_by', provisioned_by_id,
    'role', requested_role
  );
  stable_idempotency_key := 'limited-member:' ||
    content_factory_private.json_hash(request_payload);

  -- Serialize all provisioning attempts for the same organization/user pair,
  -- including attempts made by different administrators or for another role.
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('system_limited_member:' || target_user_id::text)
  );

  if not exists (
    select 1
    from content_factory.organizations organization
    where organization.id = organization_id
      and organization.status = 'active'
  ) then
    raise exception using errcode = '42501', message = 'organization_not_active';
  end if;

  select membership.role into provisioner_role
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  join auth.users provisioner_auth
    on provisioner_auth.id = membership.profile_id
   and provisioner_auth.email_confirmed_at is not null
   and provisioner_auth.deleted_at is null
   and (
     provisioner_auth.banned_until is null
     or provisioner_auth.banned_until <= now()
   )
  where membership.organization_id = organization_id
    and membership.profile_id = provisioned_by_id
    and membership.status = 'active'
    and membership.role in ('owner', 'admin');

  if provisioner_role is null then
    raise exception using errcode = '42501', message = 'provisioner_not_authorized';
  end if;

  select
    lower(btrim(auth_user.email)),
    nullif(btrim(coalesce(auth_user.raw_user_meta_data ->> 'display_name', '')), ''),
    auth_user.email_confirmed_at,
    auth_user.banned_until,
    auth_user.deleted_at
  into
    target_email,
    target_display_name,
    target_email_confirmed_at,
    target_banned_until,
    target_deleted_at
  from auth.users auth_user
  where auth_user.id = target_user_id;

  if target_email is null then
    raise exception using errcode = 'P0002', message = 'target_auth_user_not_found';
  end if;
  if target_email_confirmed_at is null then
    raise exception using errcode = '42501', message = 'target_email_not_confirmed';
  end if;
  if target_deleted_at is not null
     or (target_banned_until is not null and target_banned_until > now()) then
    raise exception using errcode = '42501', message = 'target_auth_user_not_active';
  end if;

  insert into content_factory.profiles (id, email, display_name)
  values (target_user_id, target_email, target_display_name)
  on conflict (id) do update set
    email = excluded.email,
    display_name = coalesce(
      content_factory.profiles.display_name,
      excluded.display_name
    ),
    updated_at = now();

  select profile.status into target_profile_status
  from content_factory.profiles profile
  where profile.id = target_user_id;

  if target_profile_status <> 'active' then
    raise exception using errcode = '42501', message = 'target_profile_not_active';
  end if;

  select membership.* into membership_row
  from content_factory.memberships membership
  where membership.organization_id = organization_id
    and membership.profile_id = target_user_id
  for update;

  if membership_row.id is not null then
    if membership_row.status <> 'active' then
      raise exception using
        errcode = '23505',
        message = 'target_membership_history_conflict';
    end if;
    if membership_row.role <> requested_role then
      raise exception using
        errcode = '23505',
        message = 'target_membership_role_conflict';
    end if;

    replay := content_factory_private.begin_command(
      organization_id,
      'system_provision_limited_member',
      stable_idempotency_key,
      request_payload
    );
    if replay is not null then
      return replay;
    end if;

    result := jsonb_build_object(
      'ok', true,
      'organization_id', organization_id,
      'user_id', target_user_id,
      'membership_id', membership_row.id,
      'role', membership_row.role,
      'status', membership_row.status,
      'already_active', true
    );
  else
    replay := content_factory_private.begin_command(
      organization_id,
      'system_provision_limited_member',
      stable_idempotency_key,
      request_payload
    );
    if replay is not null then
      raise exception using
        errcode = '55000',
        message = 'limited_member_provisioning_state_conflict';
    end if;

    insert into content_factory.memberships (
      organization_id,
      profile_id,
      role,
      status
    ) values (
      organization_id,
      target_user_id,
      requested_role,
      'active'
    )
    returning * into membership_row;

    result := jsonb_build_object(
      'ok', true,
      'organization_id', organization_id,
      'user_id', target_user_id,
      'membership_id', membership_row.id,
      'role', membership_row.role,
      'status', membership_row.status,
      'already_active', false
    );
  end if;

  perform content_factory_private.emit_event(
    organization_id,
    provisioned_by_id,
    'limited_member_provisioned',
    'membership',
    membership_row.id::text,
    jsonb_build_object(
      'target_user_id', target_user_id,
      'role', requested_role,
      'already_active', result -> 'already_active'
    ),
    stable_idempotency_key,
    'system'
  );

  return content_factory_private.finish_command(
    organization_id,
    provisioned_by_id,
    'system_provision_limited_member',
    stable_idempotency_key,
    request_payload,
    result
  );
end;
$$;

revoke all on function public.system_provision_limited_member(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_provision_limited_member(jsonb)
  to service_role;

commit;
