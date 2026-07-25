begin;

-- A training waiver opens the operational workspace without manufacturing
-- course attempts, practical approvals, exam passes, or certifications.  The
-- grant is explicit, attributable, reversible, and deliberately limited to an
-- operator account.
create table if not exists content_factory.training_access_waivers (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  profile_id uuid not null,
  scope text not null default 'workspace_generation'
    check (scope = 'workspace_generation'),
  status text not null default 'active'
    check (status in ('active', 'revoked')),
  previous_role text not null
    check (previous_role in ('trainee', 'operator')),
  granted_role text not null default 'operator'
    check (granted_role = 'operator'),
  grant_reason text not null
    check (length(btrim(grant_reason)) between 10 and 1000),
  granted_by uuid not null references content_factory.profiles(id),
  granted_at timestamptz not null default now(),
  revoked_by uuid references content_factory.profiles(id),
  revoked_at timestamptz,
  revocation_reason text
    check (
      revocation_reason is null
      or length(btrim(revocation_reason)) between 10 and 1000
    ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (organization_id, profile_id)
    references content_factory.memberships(organization_id, profile_id),
  check (
    (
      status = 'active'
      and revoked_by is null
      and revoked_at is null
      and revocation_reason is null
    )
    or (
      status = 'revoked'
      and revoked_by is not null
      and revoked_at is not null
      and revocation_reason is not null
    )
  )
);

create unique index if not exists training_access_waivers_org_profile_uq
  on content_factory.training_access_waivers (
    organization_id, profile_id
  );
create index if not exists training_access_waivers_active_idx
  on content_factory.training_access_waivers (
    organization_id, profile_id, status
  )
  where status = 'active';

alter table content_factory.training_access_waivers enable row level security;
revoke all on content_factory.training_access_waivers
  from public, anon, authenticated;

create or replace function
  content_factory_private.training_access_waiver_active(
    organization_id uuid,
    profile_id uuid
  )
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select exists (
    select 1
    from content_factory.training_access_waivers waiver
    join content_factory.memberships membership
      on membership.organization_id = waiver.organization_id
     and membership.profile_id = waiver.profile_id
     and membership.status = 'active'
     and membership.role = waiver.granted_role
    join content_factory.organizations organization
      on organization.id = membership.organization_id
     and organization.status = 'active'
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where waiver.organization_id = $1
      and waiver.profile_id = $2
      and waiver.scope = 'workspace_generation'
      and waiver.status = 'active'
  )
$$;

revoke all on function
  content_factory_private.training_access_waiver_active(uuid, uuid)
  from public, anon, authenticated;

-- Preserve whichever complete training boundary is installed at this point.
-- Passing require_certification=false through the wrapper skips every training
-- layer owned by that boundary while retaining authentication, active-account,
-- membership, and role checks.
do $preserve_membership_role$
begin
  if to_regprocedure(
    'content_factory_private.membership_role_pre_training_waiver(uuid,boolean,text[])'
  ) is null then
    alter function content_factory_private.membership_role(
      uuid, boolean, text[]
    )
      rename to membership_role_pre_training_waiver;
  end if;
end;
$preserve_membership_role$;
revoke all on function
  content_factory_private.membership_role_pre_training_waiver(
    uuid, boolean, text[]
  )
  from public, anon, authenticated;

create or replace function content_factory_private.membership_role(
  organization_id uuid,
  require_certification boolean default false,
  allowed_roles text[] default null
)
returns text
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  target_organization_id uuid := $1;
  certification_required boolean := $2;
  role_allowlist text[] := $3;
  waiver_active boolean := false;
  actor_role text;
begin
  if auth.uid() is not null then
    waiver_active :=
      content_factory_private.training_access_waiver_active(
        target_organization_id,
        auth.uid()
      );
  end if;

  actor_role := content_factory_private.membership_role_pre_training_waiver(
    target_organization_id,
    certification_required and not waiver_active,
    role_allowlist
  );

  return actor_role;
end;
$$;

revoke all on function
  content_factory_private.membership_role(uuid, boolean, text[])
  from public, anon, authenticated;

-- Preserve the complete installed storage predicate as the non-waiver branch.
-- Storage policies retain function OIDs, so they are recreated below against
-- the public wrapper rather than left pointing at the renamed implementation.
do $preserve_storage_access$
begin
  if to_regprocedure(
    'content_factory.storage_access_allowed_pre_training_waiver(text,text,boolean)'
  ) is null then
    alter function content_factory.storage_access_allowed(
      text, text, boolean
    )
      rename to storage_access_allowed_pre_training_waiver;
  end if;
end;
$preserve_storage_access$;
revoke all on function
  content_factory.storage_access_allowed_pre_training_waiver(
    text, text, boolean
  )
  from public, anon, authenticated;

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
  select
    content_factory.storage_access_allowed_pre_training_waiver(
      p_organization_id,
      p_owner_id,
      p_allow_team_read
    )
    or (
      auth.uid() is not null
      and p_organization_id
        ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
      and exists (
        select 1
        from content_factory.memberships membership
        join content_factory.profiles profile
          on profile.id = membership.profile_id
         and profile.status = 'active'
        join content_factory.organizations organization
          on organization.id = membership.organization_id
         and organization.status = 'active'
        where membership.profile_id = auth.uid()
          and membership.status = 'active'
          and membership.organization_id::text = p_organization_id
          and content_factory_private.training_access_waiver_active(
            membership.organization_id,
            membership.profile_id
          )
          and (
            (
              p_allow_team_read
              and (
                p_owner_id = auth.uid()::text
                or membership.role in (
                  'owner', 'admin', 'producer', 'reviewer'
                )
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
    )
$$;

revoke all on function
  content_factory.storage_access_allowed(text, text, boolean)
  from public, anon;
grant execute on function
  content_factory.storage_access_allowed(text, text, boolean)
  to authenticated;

drop policy if exists contentengine_private_select on storage.objects;
create policy contentengine_private_select
on storage.objects
for select
to authenticated
using (
  bucket_id = 'contentengine-private'
  and content_factory.storage_access_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2),
    true
  )
);

drop policy if exists contentengine_private_insert on storage.objects;
create policy contentengine_private_insert
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'contentengine-private'
  and content_factory.storage_access_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2),
    false
  )
);

drop policy if exists contentengine_private_delete on storage.objects;
create policy contentengine_private_delete
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'contentengine-private'
  and content_factory.storage_access_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2),
    false
  )
  and content_factory.storage_object_is_unregistered(
    storage.objects.bucket_id,
    storage.objects.name
  )
);

-- Preserve the final, assessment-sanitized bootstrap as a private
-- implementation.  This wrapper reopens only normal learning/workspace states;
-- password, membership, organization, and account locks remain fail-closed.
do $preserve_creator_bootstrap$
begin
  if to_regprocedure(
    'content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)'
  ) is null then
    if to_regprocedure(
      'public.creator_bootstrap_pre_training_waiver(jsonb)'
    ) is null then
      alter function public.creator_bootstrap(jsonb)
        rename to creator_bootstrap_pre_training_waiver;
    end if;
    alter function public.creator_bootstrap_pre_training_waiver(jsonb)
      set schema content_factory_private;
  end if;
end;
$preserve_creator_bootstrap$;
revoke all on function
  content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)
  from public, anon, authenticated, service_role;

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

  if actor_role <> 'operator'
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

-- Trusted administration endpoint.  It can only promote an active trainee to
-- operator (or preserve an existing operator), and revocation restores the
-- previous role when no later role change superseded it.
create or replace function public.system_set_training_access_waiver(
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
  changed_by_id uuid;
  action_value text;
  reason_value text;
  target_role_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  actor_role text;
  previous_role_value text;
  role_changed boolean := false;
  already_in_state boolean := false;
  membership_row content_factory.memberships%rowtype;
  waiver_row content_factory.training_access_waivers%rowtype;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id',
    'user_id',
    'changed_by',
    'action',
    'reason',
    'role',
    'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'training_access_waiver_payload_invalid';
  end if;

  organization_id := content_factory_private.require_uuid(
    p_payload,
    'organization_id'
  );
  target_user_id := content_factory_private.require_uuid(p_payload, 'user_id');
  changed_by_id := content_factory_private.require_uuid(
    p_payload,
    'changed_by'
  );
  action_value := lower(content_factory_private.require_text(
    p_payload,
    'action',
    5,
    6
  ));
  reason_value := content_factory_private.require_text(
    p_payload,
    'reason',
    10,
    1000
  );
  target_role_value := lower(nullif(btrim(coalesce(
    p_payload ->> 'role',
    ''
  )), ''));
  idempotency_key_value := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    12,
    180
  );

  if action_value not in ('grant', 'revoke') then
    raise exception using
      errcode = '22023',
      message = 'training_access_waiver_action_invalid';
  end if;
  if action_value = 'grant' and target_role_value <> 'operator' then
    raise exception using
      errcode = '22023',
      message = 'training_access_waiver_role_invalid';
  end if;
  if action_value = 'revoke' and target_role_value is not null then
    raise exception using
      errcode = '22023',
      message = 'training_access_waiver_role_unexpected';
  end if;

  request_payload := jsonb_build_object(
    'organization_id', organization_id,
    'user_id', target_user_id,
    'changed_by', changed_by_id,
    'action', action_value,
    'reason', reason_value,
    'role', target_role_value
  );

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('system_training_access_waiver:' || target_user_id::text)
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
      message = 'training_access_waiver_actor_not_authorized';
  end if;

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
      message = 'training_access_waiver_target_not_active';
  end if;

  select membership.* into membership_row
  from content_factory.memberships membership
  where membership.organization_id = organization_id
    and membership.profile_id = target_user_id
    and membership.status = 'active'
  for update;

  if membership_row.id is null then
    raise exception using
      errcode = '42501',
      message = 'training_access_waiver_membership_not_active';
  end if;

  select waiver.* into waiver_row
  from content_factory.training_access_waivers waiver
  where waiver.organization_id = organization_id
    and waiver.profile_id = target_user_id
  for update;

  replay := content_factory_private.begin_command(
    organization_id,
    'system_set_training_access_waiver',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  if action_value = 'grant' then
    if membership_row.role not in ('trainee', 'operator') then
      raise exception using
        errcode = '42501',
        message = 'training_access_waiver_target_role_not_allowed';
    end if;

    already_in_state :=
      waiver_row.id is not null and waiver_row.status = 'active';
    previous_role_value := case
      when already_in_state then waiver_row.previous_role
      else membership_row.role
    end;

    if membership_row.role <> 'operator' then
      update content_factory.memberships membership
      set
        role = 'operator',
        updated_at = now()
      where membership.id = membership_row.id;
      membership_row.role := 'operator';
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
        'operator',
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
        granted_role = 'operator',
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

    result := jsonb_build_object(
      'ok', true,
      'action', 'grant',
      'organization_id', organization_id,
      'user_id', target_user_id,
      'waiver_id', waiver_row.id,
      'waiver_active', true,
      'role', membership_row.role,
      'role_changed', role_changed,
      'already_active', already_in_state
    );

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
        'training-waiver-role:' || idempotency_key_value,
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
        'already_active', already_in_state
      ),
      'training-waiver-grant:' || idempotency_key_value,
      'system'
    );
  else
    already_in_state :=
      waiver_row.id is null or waiver_row.status <> 'active';

    if not already_in_state then
      update content_factory.training_access_waivers waiver
      set
        status = 'revoked',
        revoked_by = changed_by_id,
        revoked_at = now(),
        revocation_reason = reason_value,
        updated_at = now()
      where waiver.id = waiver_row.id
      returning * into waiver_row;

      if membership_row.role = waiver_row.granted_role
         and waiver_row.previous_role <> waiver_row.granted_role then
        update content_factory.memberships membership
        set
          role = waiver_row.previous_role,
          updated_at = now()
        where membership.id = membership_row.id;
        membership_row.role := waiver_row.previous_role;
        role_changed := true;
      end if;
    end if;

    result := jsonb_build_object(
      'ok', true,
      'action', 'revoke',
      'organization_id', organization_id,
      'user_id', target_user_id,
      'waiver_id', waiver_row.id,
      'waiver_active', false,
      'role', membership_row.role,
      'role_changed', role_changed,
      'already_inactive', already_in_state
    );

    perform content_factory_private.emit_event(
      organization_id,
      changed_by_id,
      'training_access_waiver_revoked',
      'training_access_waiver',
      coalesce(waiver_row.id::text, target_user_id::text),
      jsonb_build_object(
        'target_user_id', target_user_id,
        'role', membership_row.role,
        'role_restored', role_changed,
        'already_inactive', already_in_state
      ),
      'training-waiver-revoke:' || idempotency_key_value,
      'system'
    );
  end if;

  return content_factory_private.finish_command(
    organization_id,
    changed_by_id,
    'system_set_training_access_waiver',
    idempotency_key_value,
    request_payload,
    result
  );
end;
$$;

revoke all on function public.system_set_training_access_waiver(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_set_training_access_waiver(jsonb)
  to service_role;

do $training_access_waiver_contract$
declare
  membership_gate_definition text;
  bootstrap_definition text;
  storage_definition text;
  system_definition text;
begin
  select lower(pg_get_functiondef(
    'content_factory_private.membership_role(uuid,boolean,text[])'
      ::regprocedure
  )) into membership_gate_definition;
  select lower(pg_get_functiondef(
    'public.creator_bootstrap(jsonb)'::regprocedure
  )) into bootstrap_definition;
  select lower(pg_get_functiondef(
    'content_factory.storage_access_allowed(text,text,boolean)'::regprocedure
  )) into storage_definition;
  select lower(pg_get_functiondef(
    'public.system_set_training_access_waiver(jsonb)'::regprocedure
  )) into system_definition;

  if membership_gate_definition is null
     or strpos(
       membership_gate_definition,
       'training_access_waiver_active('
     ) = 0
     or strpos(
       membership_gate_definition,
       'certification_required and not waiver_active'
     ) = 0
     or strpos(
       membership_gate_definition,
       'membership_role_pre_training_waiver('
     ) = 0 then
    raise exception 'training_access_waiver_membership_gate_invalid';
  end if;

  if bootstrap_definition is null
     or strpos(bootstrap_definition, 'creator_bootstrap_pre_training_waiver') = 0
     or strpos(bootstrap_definition, '''access_waiver''') = 0
     or strpos(bootstrap_definition, '''workspace_generation''') = 0
     or strpos(bootstrap_definition, '''password_change_required''') > 0 then
    raise exception 'training_access_waiver_bootstrap_invalid';
  end if;

  if storage_definition is null
     or strpos(storage_definition, 'training_access_waiver_active(') = 0
     or strpos(
       storage_definition,
       'storage_access_allowed_pre_training_waiver('
     ) = 0 then
    raise exception 'training_access_waiver_storage_gate_invalid';
  end if;

  if system_definition is null
     or strpos(system_definition, 'training_certifications') > 0
     or strpos(system_definition, 'training_attempts') > 0
     or strpos(system_definition, 'training_practical_projects') > 0 then
    raise exception 'training_access_waiver_fabricates_training_state';
  end if;

  if has_function_privilege(
    'authenticated',
    'public.system_set_training_access_waiver(jsonb)',
    'EXECUTE'
  ) or not has_function_privilege(
    'service_role',
    'public.system_set_training_access_waiver(jsonb)',
    'EXECUTE'
  ) then
    raise exception 'training_access_waiver_system_privileges_invalid';
  end if;
end;
$training_access_waiver_contract$;

commit;
