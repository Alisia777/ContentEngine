begin;

-- The employee/account administration plane is deliberately separate from the
-- operational workspace.  Owners and administrators must be able to repair
-- membership access even when they have not completed operator training.
-- Every browser RPC below still requires a confirmed, non-banned Auth user,
-- active profile, active organization, and active owner/admin membership.

create table if not exists content_factory.managed_accounts (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  platform text not null
    check (
      length(platform) between 1 and 50
      and platform ~ '^[a-z0-9][a-z0-9._-]{0,49}$'
    ),
  label text not null check (length(btrim(label)) between 1 and 180),
  handle text check (
    handle is null or length(btrim(handle)) between 1 and 180
  ),
  url text check (
    url is null
    or (
      length(btrim(url)) between 8 and 2048
      and btrim(url) ~* '^https?://[^[:space:]]+$'
      and btrim(url) !~* '^https?://[^/?#[:space:]]+@'
    )
  ),
  notes text check (
    notes is null or length(btrim(notes)) between 1 and 2000
  ),
  status text not null default 'active'
    check (status in ('active', 'archived')),
  created_by uuid not null,
  archived_by uuid,
  archived_at timestamptz,
  archive_reason text check (
    archive_reason is null
    or length(btrim(archive_reason)) between 5 and 1000
  ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (organization_id)
    references content_factory.organizations(id) on delete cascade,
  foreign key (organization_id, created_by)
    references content_factory.memberships(organization_id, profile_id),
  foreign key (organization_id, archived_by)
    references content_factory.memberships(organization_id, profile_id),
  constraint managed_accounts_org_id_uq unique (organization_id, id),
  check (
    (
      status = 'active'
      and archived_by is null
      and archived_at is null
      and archive_reason is null
    )
    or (
      status = 'archived'
      and archived_by is not null
      and archived_at is not null
      and archive_reason is not null
    )
  )
);

comment on table content_factory.managed_accounts is
  'Non-secret publishing/channel account catalog. Never store passwords, tokens, cookies, recovery codes, or session material here.';
comment on column content_factory.managed_accounts.notes is
  'Operational, non-secret notes only. Credentials and authentication material are prohibited.';

create unique index if not exists managed_accounts_active_handle_uq
  on content_factory.managed_accounts (
    organization_id,
    platform,
    lower(handle)
  )
  where status = 'active' and handle is not null;

create unique index if not exists managed_accounts_active_url_uq
  on content_factory.managed_accounts (
    organization_id,
    lower(url)
  )
  where status = 'active' and url is not null;

create index if not exists managed_accounts_org_status_idx
  on content_factory.managed_accounts (
    organization_id,
    status,
    updated_at desc,
    id
  );

create table if not exists content_factory.member_account_assignments (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  account_id uuid not null,
  profile_id uuid not null,
  status text not null default 'active'
    check (status in ('active', 'revoked')),
  assigned_by uuid not null,
  assigned_at timestamptz not null default now(),
  revoked_by uuid,
  revoked_at timestamptz,
  revoke_reason text check (
    revoke_reason is null
    or length(btrim(revoke_reason)) between 3 and 1000
  ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (organization_id, account_id)
    references content_factory.managed_accounts(organization_id, id),
  foreign key (organization_id, profile_id)
    references content_factory.memberships(organization_id, profile_id),
  foreign key (organization_id, assigned_by)
    references content_factory.memberships(organization_id, profile_id),
  foreign key (organization_id, revoked_by)
    references content_factory.memberships(organization_id, profile_id),
  check (
    (
      status = 'active'
      and revoked_by is null
      and revoked_at is null
      and revoke_reason is null
    )
    or (
      status = 'revoked'
      and revoked_by is not null
      and revoked_at is not null
      and revoke_reason is not null
    )
  )
);

comment on table content_factory.member_account_assignments is
  'Append-preserving history of which employee owns each managed publishing/channel account.';

create unique index if not exists member_account_assignments_one_active_uq
  on content_factory.member_account_assignments (organization_id, account_id)
  where status = 'active';

create index if not exists member_account_assignments_member_history_idx
  on content_factory.member_account_assignments (
    organization_id,
    profile_id,
    assigned_at desc,
    id
  );

create index if not exists member_account_assignments_account_history_idx
  on content_factory.member_account_assignments (
    organization_id,
    account_id,
    assigned_at desc,
    id
  );

alter table content_factory.managed_accounts enable row level security;
alter table content_factory.managed_accounts force row level security;
alter table content_factory.member_account_assignments enable row level security;
alter table content_factory.member_account_assignments force row level security;

revoke all on content_factory.managed_accounts
  from public, anon, authenticated;
revoke all on content_factory.member_account_assignments
  from public, anon, authenticated;
grant all on content_factory.managed_accounts to service_role;
grant all on content_factory.member_account_assignments to service_role;

drop trigger if exists set_updated_at
  on content_factory.managed_accounts;
create trigger set_updated_at
before update on content_factory.managed_accounts
for each row execute function content_factory_private.set_updated_at();

drop trigger if exists set_updated_at
  on content_factory.member_account_assignments;
create trigger set_updated_at
before update on content_factory.member_account_assignments
for each row execute function content_factory_private.set_updated_at();

create or replace function content_factory_private.require_admin_keys(
  payload jsonb,
  allowed_keys text[],
  required_keys text[] default array[]::text[]
)
returns void
language plpgsql
immutable
set search_path = ''
as $$
declare
  invalid_key text;
  missing_key text;
begin
  if payload is null or jsonb_typeof(payload) <> 'object' then
    raise exception using errcode = '22023', message = 'payload_must_be_an_object';
  end if;

  select key into invalid_key
  from jsonb_object_keys(payload) key
  where not (key = any(allowed_keys))
  order by key
  limit 1;

  if invalid_key is not null then
    raise exception using
      errcode = '22023',
      message = 'payload_key_not_allowed',
      detail = invalid_key;
  end if;

  select key into missing_key
  from unnest(required_keys) key
  where not (payload ? key) or payload -> key = 'null'::jsonb
  order by key
  limit 1;

  if missing_key is not null then
    raise exception using
      errcode = '22023',
      message = 'payload_key_required',
      detail = missing_key;
  end if;
end;
$$;

revoke all on function content_factory_private.require_admin_keys(
  jsonb, text[], text[]
) from public, anon, authenticated;

create or replace function content_factory_private.admin_optional_text(
  payload jsonb,
  key_name text,
  minimum_length integer,
  maximum_length integer
)
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  result text;
begin
  if not (payload ? key_name) or payload -> key_name = 'null'::jsonb then
    return null;
  end if;
  if jsonb_typeof(payload -> key_name) <> 'string' then
    raise exception using
      errcode = '22023',
      message = key_name || '_invalid';
  end if;
  result := btrim(payload ->> key_name);
  if length(result) < minimum_length or length(result) > maximum_length then
    raise exception using
      errcode = '22023',
      message = key_name || '_invalid';
  end if;
  return result;
end;
$$;

revoke all on function content_factory_private.admin_optional_text(
  jsonb, text, integer, integer
) from public, anon, authenticated;

create or replace function content_factory_private.require_admin_actor(
  organization_id uuid
)
returns text
language plpgsql
security definer
stable
set search_path = ''
as $$
declare
  actor_id uuid := auth.uid();
  actor_role text;
begin
  if actor_id is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;

  if not exists (
    select 1
    from auth.users auth_user
    where auth_user.id = actor_id
      and auth_user.email_confirmed_at is not null
      and auth_user.deleted_at is null
      and (
        auth_user.banned_until is null
        or auth_user.banned_until <= now()
      )
  ) then
    raise exception using errcode = '42501', message = 'auth_account_not_active';
  end if;

  -- Passing false is intentional: this is the independent administration
  -- boundary and does not depend on course or final-exam completion.
  actor_role := content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin']
  );
  return actor_role;
end;
$$;

revoke all on function
  content_factory_private.require_admin_actor(uuid)
  from public, anon, authenticated;

create or replace function content_factory_private.lock_admin_member(
  organization_id uuid,
  profile_id uuid
)
returns void
language plpgsql
volatile
set search_path = ''
as $$
begin
  -- Serialize lifecycle changes and account binding for the same employee.
  -- Every participating path takes this one lock before any related row lock.
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-admin-member:'
        || organization_id::text || ':' || profile_id::text,
      0
    )
  );
end;
$$;

revoke all on function
  content_factory_private.lock_admin_member(uuid, uuid)
  from public, anon, authenticated;

create or replace function
  content_factory_private.serialize_admin_project_membership()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  member_status text;
  member_role text;
  profile_status text;
begin
  -- Only operations that create active access need to synchronize with final
  -- offboarding.  An active -> revoked update already holds the project row;
  -- taking the member lock from that path would invert revoke_member's order
  -- (member -> project row) and could deadlock with a project-only revocation.
  if new.status <> 'active' then
    return new;
  end if;
  if tg_op = 'UPDATE' and old.status = 'active' then
    return new;
  end if;

  perform content_factory_private.lock_admin_member(
    new.organization_id,
    new.profile_id
  );

  -- SELECT FOR UPDATE rechecks the current committed membership after the
  -- advisory barrier, so an in-flight grant cannot revive project access
  -- after final offboarding has swept existing rows.
  select member.status, member.role, profile.status
    into member_status, member_role, profile_status
  from content_factory.memberships member
  join content_factory.profiles profile
    on profile.id = member.profile_id
  where member.organization_id = new.organization_id
    and member.profile_id = new.profile_id
  for update of member;

  if new.status = 'active' and (
    member_status is distinct from 'active'
    or profile_status is distinct from 'active'
    or member_role not in (
      'owner', 'admin', 'producer', 'reviewer', 'operator'
    )
  ) then
    raise exception using
      errcode = '42501',
      message = 'workspace_project_member_not_operational';
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.serialize_admin_project_membership()
  from public, anon, authenticated;

drop trigger if exists admin_serialize_workspace_project_membership
  on content_factory.workspace_project_memberships;
create trigger admin_serialize_workspace_project_membership
before insert or update on content_factory.workspace_project_memberships
for each row execute function
  content_factory_private.serialize_admin_project_membership();

create or replace function content_factory_private.guard_member_account_assignment()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' and (
    new.organization_id <> old.organization_id
    or new.account_id <> old.account_id
    or new.profile_id <> old.profile_id
    or new.assigned_by <> old.assigned_by
    or new.assigned_at <> old.assigned_at
    or new.created_at <> old.created_at
    or old.status = 'revoked'
  ) then
    raise exception using
      errcode = '55000',
      message = 'assignment_history_is_immutable';
  end if;

  -- Only an INSERT can create a new active assignment: identity fields are
  -- immutable and revoked history cannot be reactivated.  Take the employee
  -- advisory lock before that insert so final offboarding either sees and
  -- revokes this row or commits first and makes the active-member check fail.
  -- Do not take the lock for active -> revoked updates: archive/unbind already
  -- hold the assignment row, and doing so would invert the offboarding lock
  -- order (member -> assignment) and introduce a deadlock.
  if tg_op = 'INSERT' and new.status = 'active' then
    perform content_factory_private.lock_admin_member(
      new.organization_id,
      new.profile_id
    );
  end if;

  if new.status = 'active' then
    if not exists (
      select 1
      from content_factory.managed_accounts account
      where account.organization_id = new.organization_id
        and account.id = new.account_id
        and account.status = 'active'
    ) then
      raise exception using errcode = '42501', message = 'account_not_active';
    end if;
    if not exists (
      select 1
      from content_factory.memberships membership
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
      where membership.organization_id = new.organization_id
        and membership.profile_id = new.profile_id
        and membership.status = 'active'
    ) then
      raise exception using errcode = '42501', message = 'target_membership_not_active';
    end if;
  end if;

  return new;
end;
$$;

revoke all on function
  content_factory_private.guard_member_account_assignment()
  from public, anon, authenticated;

drop trigger if exists guard_member_account_assignment
  on content_factory.member_account_assignments;
create trigger guard_member_account_assignment
before insert or update on content_factory.member_account_assignments
for each row execute function
  content_factory_private.guard_member_account_assignment();

create or replace function public.creator_admin_snapshot(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  actor_id uuid := auth.uid();
  organization_id uuid;
  actor_role text;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.require_admin_keys(
    p_payload,
    array['organization_id']
  );
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.require_admin_actor(organization_id);

  select jsonb_build_object(
    'ok', true,
    'organization', jsonb_build_object(
      'id', organization.id,
      'name', organization.name
    ),
    'actor', jsonb_build_object(
      'profile_id', actor_id,
      'role', actor_role
    ),
    'members', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'membership_id', member.id,
        'profile_id', member.profile_id,
        'email', profile.email,
        'display_name', profile.display_name,
        'role', member.role,
        'status', member.status,
        'joined_at', member.created_at,
        'updated_at', member.updated_at,
        'auth_confirmed', coalesce(auth_user.email_confirmed_at is not null, false),
        'auth_active', coalesce(
          auth_user.id is not null
          and auth_user.deleted_at is null
          and (
            auth_user.banned_until is null
            or auth_user.banned_until <= now()
          ),
          false
        ),
        'courses_completed', (
          select count(distinct certification.module_code)
          from content_factory.training_certifications certification
          join content_factory.training_modules module
            on module.code = certification.module_code
           and module.module_type = 'course'
           and module.is_active
          where certification.organization_id = member.organization_id
            and certification.profile_id = member.profile_id
            and certification.status = 'passed'
            and (
              certification.expires_at is null
              or certification.expires_at > now()
            )
        ),
        'courses_required', (
          select count(*)
          from content_factory.training_modules module
          where module.module_type = 'course'
            and module.is_active
        ),
        'exam_passed', exists (
          select 1
          from content_factory.training_certifications certification
          where certification.organization_id = member.organization_id
            and certification.profile_id = member.profile_id
            and certification.module_code = 'operator_final_exam'
            and certification.status = 'passed'
            and (
              certification.expires_at is null
              or certification.expires_at > now()
            )
        ),
        'access_waiver_active', active_waiver.grant_reason is not null,
        'access_waiver_reason', active_waiver.grant_reason,
        'accounts', (
          select coalesce(jsonb_agg(jsonb_build_object(
            'assignment_id', assignment.id,
            'account_id', account.id,
            'platform', account.platform,
            'label', account.label,
            'handle', account.handle,
            'url', account.url,
            'assigned_at', assignment.assigned_at
          ) order by account.platform, account.label, account.id), '[]'::jsonb)
          from content_factory.member_account_assignments assignment
          join content_factory.managed_accounts account
            on account.organization_id = assignment.organization_id
           and account.id = assignment.account_id
          where assignment.organization_id = member.organization_id
            and assignment.profile_id = member.profile_id
            and assignment.status = 'active'
            and account.status = 'active'
        )
      ) order by
        case member.status
          when 'active' then 0
          when 'suspended' then 1
          else 2
        end,
        lower(coalesce(profile.display_name, profile.email, member.profile_id::text)),
        member.id), '[]'::jsonb)
      from content_factory.memberships member
      join content_factory.profiles profile
        on profile.id = member.profile_id
      left join auth.users auth_user
        on auth_user.id = member.profile_id
      left join lateral (
        select waiver.grant_reason
        from content_factory.training_access_waivers waiver
        where waiver.organization_id = member.organization_id
          and waiver.profile_id = member.profile_id
          and waiver.scope = 'workspace_generation'
          and waiver.status = 'active'
          and content_factory_private.training_access_waiver_active(
            waiver.organization_id,
            waiver.profile_id
          )
        order by waiver.granted_at desc, waiver.id desc
        limit 1
      ) active_waiver on true
      where member.organization_id = organization_id
    ),
    'accounts', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'id', account.id,
        'platform', account.platform,
        'label', account.label,
        'handle', account.handle,
        'url', account.url,
        'notes', account.notes,
        'status', account.status,
        'created_at', account.created_at,
        'updated_at', account.updated_at,
        'assigned_profile_id', assignment.profile_id,
        'assignment_id', assignment.id,
        'assigned_at', assignment.assigned_at
      ) order by
        case account.status when 'active' then 0 else 1 end,
        account.platform,
        lower(account.label),
        account.id), '[]'::jsonb)
      from content_factory.managed_accounts account
      left join content_factory.member_account_assignments assignment
        on assignment.organization_id = account.organization_id
       and assignment.account_id = account.id
       and assignment.status = 'active'
      where account.organization_id = organization_id
    )
  ) into result
  from content_factory.organizations organization
  where organization.id = organization_id;

  if result is null then
    raise exception using errcode = '42501', message = 'organization_not_active';
  end if;
  return result;
end;
$$;

revoke all on function public.creator_admin_snapshot(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_admin_snapshot(jsonb)
  to authenticated, service_role;

create or replace function public.creator_admin_mutate(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  actor_id uuid := auth.uid();
  actor_role text;
  organization_id uuid;
  action_value text;
  idempotency_key text;
  canonical_payload jsonb;
  replay jsonb;
  result jsonb;
  event_name text;
  event_entity_type text;
  event_entity_id text;
  event_properties jsonb := '{}'::jsonb;
  target_profile_id uuid;
  target_member content_factory.memberships%rowtype;
  account_id uuid;
  account_row content_factory.managed_accounts%rowtype;
  assignment_row content_factory.member_account_assignments%rowtype;
  previous_assignment_profile_id uuid;
  previous_status text;
  reason_value text;
  confirmation_value text;
  platform_value text;
  label_value text;
  handle_value text;
  url_value text;
  notes_value text;
  expected_updated_at timestamptz;
  changed boolean := true;
  account_assignments_revoked_count integer := 0;
  project_access_revoked_count integer := 0;
  training_waivers_revoked_count integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  action_value := content_factory_private.require_text(
    p_payload,
    'action',
    3,
    40
  );

  if action_value = 'suspend_member' then
    perform content_factory_private.require_admin_keys(
      p_payload,
      array[
        'organization_id', 'action', 'idempotency_key',
        'target_profile_id', 'reason'
      ],
      array['action', 'idempotency_key', 'target_profile_id', 'reason']
    );
  elsif action_value = 'reactivate_member' then
    perform content_factory_private.require_admin_keys(
      p_payload,
      array[
        'organization_id', 'action', 'idempotency_key',
        'target_profile_id', 'reason'
      ],
      array['action', 'idempotency_key', 'target_profile_id', 'reason']
    );
  elsif action_value = 'revoke_member' then
    perform content_factory_private.require_admin_keys(
      p_payload,
      array[
        'organization_id', 'action', 'idempotency_key',
        'target_profile_id', 'reason', 'confirmation'
      ],
      array[
        'action', 'idempotency_key', 'target_profile_id',
        'reason', 'confirmation'
      ]
    );
  elsif action_value = 'create_account' then
    perform content_factory_private.require_admin_keys(
      p_payload,
      array[
        'organization_id', 'action', 'idempotency_key', 'platform',
        'label', 'handle', 'url', 'notes'
      ],
      array['action', 'idempotency_key', 'platform', 'label']
    );
  elsif action_value = 'update_account' then
    perform content_factory_private.require_admin_keys(
      p_payload,
      array[
        'organization_id', 'action', 'idempotency_key', 'account_id',
        'expected_updated_at', 'platform', 'label', 'handle', 'url', 'notes'
      ],
      array[
        'action', 'idempotency_key', 'account_id', 'expected_updated_at',
        'platform', 'label'
      ]
    );
  elsif action_value = 'archive_account' then
    perform content_factory_private.require_admin_keys(
      p_payload,
      array[
        'organization_id', 'action', 'idempotency_key', 'account_id',
        'expected_updated_at', 'reason', 'confirmation'
      ],
      array[
        'action', 'idempotency_key', 'account_id', 'expected_updated_at',
        'reason', 'confirmation'
      ]
    );
  elsif action_value = 'bind_account' then
    perform content_factory_private.require_admin_keys(
      p_payload,
      array[
        'organization_id', 'action', 'idempotency_key',
        'account_id', 'target_profile_id'
      ],
      array[
        'action', 'idempotency_key', 'account_id', 'target_profile_id'
      ]
    );
  elsif action_value = 'unbind_account' then
    perform content_factory_private.require_admin_keys(
      p_payload,
      array[
        'organization_id', 'action', 'idempotency_key', 'account_id'
      ],
      array['action', 'idempotency_key', 'account_id']
    );
  else
    raise exception using errcode = '22023', message = 'admin_action_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.require_admin_actor(organization_id);
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  canonical_payload := p_payload || jsonb_build_object(
    'organization_id', organization_id
  );

  replay := content_factory_private.begin_command(
    organization_id,
    'creator_admin_' || action_value,
    idempotency_key,
    canonical_payload
  );
  if replay is not null then
    return replay;
  end if;

  if action_value in (
    'suspend_member', 'reactivate_member', 'revoke_member'
  ) then
    target_profile_id := content_factory_private.require_uuid(
      p_payload,
      'target_profile_id'
    );
    reason_value := content_factory_private.require_text(
      p_payload,
      'reason',
      5,
      900
    );

    perform content_factory_private.lock_admin_member(
      organization_id,
      target_profile_id
    );

    select member.* into target_member
    from content_factory.memberships member
    where member.organization_id = organization_id
      and member.profile_id = target_profile_id
    for update;

    if target_member.id is null then
      raise exception using errcode = 'P0002', message = 'target_member_not_found';
    end if;
    if target_profile_id = actor_id then
      raise exception using errcode = '42501', message = 'self_membership_change_forbidden';
    end if;
    if target_member.role = 'owner' then
      raise exception using errcode = '42501', message = 'owner_membership_protected';
    end if;
    if actor_role = 'admin' and target_member.role = 'admin' then
      raise exception using errcode = '42501', message = 'admin_membership_protected';
    end if;

    previous_status := target_member.status;

    if action_value = 'suspend_member' then
      if target_member.status = 'revoked' then
        raise exception using errcode = '55000', message = 'revoked_member_cannot_be_suspended';
      elsif target_member.status = 'suspended' then
        changed := false;
      else
        update content_factory.memberships member
        set status = 'suspended'
        where member.id = target_member.id
        returning * into target_member;
      end if;
      event_name := 'admin_member_suspended';
    elsif action_value = 'reactivate_member' then
      if target_member.status = 'revoked' then
        raise exception using errcode = '55000', message = 'revoked_member_cannot_be_reactivated';
      elsif target_member.status = 'active' then
        changed := false;
      else
        if not exists (
          select 1
          from content_factory.profiles profile
          join auth.users auth_user on auth_user.id = profile.id
          where profile.id = target_profile_id
            and profile.status = 'active'
            and auth_user.email_confirmed_at is not null
            and auth_user.deleted_at is null
            and (
              auth_user.banned_until is null
              or auth_user.banned_until <= now()
            )
        ) then
          raise exception using errcode = '42501', message = 'target_account_not_active';
        end if;

        update content_factory.memberships member
        set status = 'active'
        where member.id = target_member.id
        returning * into target_member;
      end if;
      event_name := 'admin_member_reactivated';
    else
      confirmation_value := content_factory_private.require_text(
        p_payload,
        'confirmation',
        13,
        13
      );
      if confirmation_value <> 'REVOKE_MEMBER' then
        raise exception using errcode = '22023', message = 'revocation_confirmation_invalid';
      end if;

      if target_member.status = 'revoked' then
        changed := false;
      else
        -- Final offboarding closes durable project scopes and exceptional
        -- training access before revoking the organization membership.  This
        -- preserves referential integrity and leaves every revocation auditable.
        update content_factory.workspace_project_memberships project_access
        set
          status = 'revoked',
          updated_by = actor_id,
          updated_at = now()
        where project_access.organization_id = organization_id
          and project_access.profile_id = target_profile_id
          and project_access.status = 'active';
        get diagnostics project_access_revoked_count = row_count;

        update content_factory.training_access_waivers waiver
        set
          status = 'revoked',
          revoked_by = actor_id,
          revoked_at = now(),
          revocation_reason = 'Member removed from organization: ' || reason_value,
          updated_at = now()
        where waiver.organization_id = organization_id
          and waiver.profile_id = target_profile_id
          and waiver.status = 'active';
        get diagnostics training_waivers_revoked_count = row_count;

        update content_factory.member_account_assignments assignment
        set
          status = 'revoked',
          revoked_by = actor_id,
          revoked_at = now(),
          revoke_reason = 'member_revoked: ' || reason_value
        where assignment.organization_id = organization_id
          and assignment.profile_id = target_profile_id
          and assignment.status = 'active';
        get diagnostics account_assignments_revoked_count = row_count;

        update content_factory.memberships member
        set status = 'revoked'
        where member.id = target_member.id
        returning * into target_member;
      end if;
      event_name := 'admin_member_revoked';
    end if;

    result := jsonb_build_object(
      'ok', true,
      'action', action_value,
      'organization_id', organization_id,
      'changed', changed,
      'member', jsonb_build_object(
        'membership_id', target_member.id,
        'profile_id', target_member.profile_id,
        'role', target_member.role,
        'status', target_member.status,
        'updated_at', target_member.updated_at
      ),
      'closed_access', jsonb_build_object(
        'account_assignments', account_assignments_revoked_count,
        'project_memberships', project_access_revoked_count,
        'training_waivers', training_waivers_revoked_count
      )
    );
    event_entity_type := 'membership';
    event_entity_id := target_member.id::text;
    event_properties := jsonb_build_object(
      'target_profile_id', target_profile_id,
      'previous_status', previous_status,
      'status', target_member.status,
      'changed', changed,
      'account_assignments_revoked', account_assignments_revoked_count,
      'project_memberships_revoked', project_access_revoked_count,
      'training_waivers_revoked', training_waivers_revoked_count,
      'reason', reason_value,
      'actor_role', actor_role
    );

  elsif action_value in ('create_account', 'update_account') then
    platform_value := lower(content_factory_private.require_text(
      p_payload,
      'platform',
      1,
      50
    ));
    if platform_value !~ '^[a-z0-9][a-z0-9._-]{0,49}$' then
      raise exception using errcode = '22023', message = 'platform_invalid';
    end if;
    label_value := content_factory_private.require_text(
      p_payload,
      'label',
      1,
      180
    );
    handle_value := content_factory_private.admin_optional_text(
      p_payload,
      'handle',
      1,
      180
    );
    url_value := content_factory_private.admin_optional_text(
      p_payload,
      'url',
      8,
      2048
    );
    notes_value := content_factory_private.admin_optional_text(
      p_payload,
      'notes',
      1,
      2000
    );
    if url_value is not null and (
      url_value !~* '^https?://[^[:space:]]+$'
      or url_value ~* '^https?://[^/?#[:space:]]+@'
    ) then
      raise exception using errcode = '22023', message = 'url_invalid';
    end if;

    if action_value = 'create_account' then
      insert into content_factory.managed_accounts (
        organization_id,
        platform,
        label,
        handle,
        url,
        notes,
        created_by
      ) values (
        organization_id,
        platform_value,
        label_value,
        handle_value,
        url_value,
        notes_value,
        actor_id
      )
      returning * into account_row;
      event_name := 'admin_managed_account_created';
    else
      account_id := content_factory_private.require_uuid(p_payload, 'account_id');
      begin
        expected_updated_at := content_factory_private.require_text(
          p_payload,
          'expected_updated_at',
          10,
          64
        )::timestamptz;
      exception
        when invalid_datetime_format or datetime_field_overflow then
          raise exception using errcode = '22023', message = 'expected_updated_at_invalid';
      end;

      select account.* into account_row
      from content_factory.managed_accounts account
      where account.organization_id = organization_id
        and account.id = account_id
      for update;

      if account_row.id is null then
        raise exception using errcode = 'P0002', message = 'managed_account_not_found';
      end if;
      if account_row.status <> 'active' then
        raise exception using errcode = '55000', message = 'managed_account_archived';
      end if;
      if actor_role = 'admin' and exists (
        select 1
        from content_factory.member_account_assignments assignment
        join content_factory.memberships member
          on member.organization_id = assignment.organization_id
         and member.profile_id = assignment.profile_id
        where assignment.organization_id = organization_id
          and assignment.account_id = account_id
          and assignment.status = 'active'
          and member.role in ('owner', 'admin')
      ) then
        raise exception using
          errcode = '42501',
          message = 'account_assignment_protected';
      end if;
      if account_row.updated_at <> expected_updated_at then
        raise exception using errcode = '40001', message = 'managed_account_stale';
      end if;

      update content_factory.managed_accounts account
      set
        platform = platform_value,
        label = label_value,
        handle = handle_value,
        url = url_value,
        notes = notes_value
      where account.id = account_id
      returning * into account_row;
      event_name := 'admin_managed_account_updated';
    end if;

    result := jsonb_build_object(
      'ok', true,
      'action', action_value,
      'organization_id', organization_id,
      'changed', true,
      'account', jsonb_build_object(
        'id', account_row.id,
        'platform', account_row.platform,
        'label', account_row.label,
        'handle', account_row.handle,
        'url', account_row.url,
        'notes', account_row.notes,
        'status', account_row.status,
        'created_at', account_row.created_at,
        'updated_at', account_row.updated_at
      )
    );
    event_entity_type := 'managed_account';
    event_entity_id := account_row.id::text;
    event_properties := jsonb_build_object(
      'platform', account_row.platform,
      'status', account_row.status,
      'actor_role', actor_role
    );

  elsif action_value = 'archive_account' then
    account_id := content_factory_private.require_uuid(p_payload, 'account_id');
    reason_value := content_factory_private.require_text(
      p_payload,
      'reason',
      5,
      900
    );
    confirmation_value := content_factory_private.require_text(
      p_payload,
      'confirmation',
      15,
      15
    );
    if confirmation_value <> 'ARCHIVE_ACCOUNT' then
      raise exception using errcode = '22023', message = 'archive_confirmation_invalid';
    end if;
    begin
      expected_updated_at := content_factory_private.require_text(
        p_payload,
        'expected_updated_at',
        10,
        64
      )::timestamptz;
    exception
      when invalid_datetime_format or datetime_field_overflow then
        raise exception using errcode = '22023', message = 'expected_updated_at_invalid';
    end;

    select account.* into account_row
    from content_factory.managed_accounts account
    where account.organization_id = organization_id
      and account.id = account_id
    for update;

    if account_row.id is null then
      raise exception using errcode = 'P0002', message = 'managed_account_not_found';
    end if;
    if actor_role = 'admin' and exists (
      select 1
      from content_factory.member_account_assignments assignment
      join content_factory.memberships member
        on member.organization_id = assignment.organization_id
       and member.profile_id = assignment.profile_id
      where assignment.organization_id = organization_id
        and assignment.account_id = account_id
        and assignment.status = 'active'
        and member.role in ('owner', 'admin')
    ) then
      raise exception using
        errcode = '42501',
        message = 'account_assignment_protected';
    end if;
    if account_row.updated_at <> expected_updated_at then
      raise exception using errcode = '40001', message = 'managed_account_stale';
    end if;
    if account_row.status = 'archived' then
      changed := false;
    else
      update content_factory.member_account_assignments assignment
      set
        status = 'revoked',
        revoked_by = actor_id,
        revoked_at = now(),
        revoke_reason = 'account_archived: ' || reason_value
      where assignment.organization_id = organization_id
        and assignment.account_id = account_id
        and assignment.status = 'active';

      update content_factory.managed_accounts account
      set
        status = 'archived',
        archived_by = actor_id,
        archived_at = now(),
        archive_reason = reason_value
      where account.id = account_id
      returning * into account_row;
    end if;

    result := jsonb_build_object(
      'ok', true,
      'action', action_value,
      'organization_id', organization_id,
      'changed', changed,
      'account', jsonb_build_object(
        'id', account_row.id,
        'platform', account_row.platform,
        'label', account_row.label,
        'handle', account_row.handle,
        'url', account_row.url,
        'notes', account_row.notes,
        'status', account_row.status,
        'created_at', account_row.created_at,
        'updated_at', account_row.updated_at
      )
    );
    event_name := 'admin_managed_account_archived';
    event_entity_type := 'managed_account';
    event_entity_id := account_row.id::text;
    event_properties := jsonb_build_object(
      'platform', account_row.platform,
      'status', account_row.status,
      'changed', changed,
      'reason', reason_value,
      'actor_role', actor_role
    );

  elsif action_value in ('bind_account', 'unbind_account') then
    account_id := content_factory_private.require_uuid(p_payload, 'account_id');

    if action_value = 'bind_account' then
      target_profile_id := content_factory_private.require_uuid(
        p_payload,
        'target_profile_id'
      );
      perform content_factory_private.lock_admin_member(
        organization_id,
        target_profile_id
      );

      target_member := null;
      select member.* into target_member
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
        and member.profile_id = target_profile_id
        and member.status = 'active'
      for update of member;

      if target_member.id is null then
        raise exception using errcode = '42501', message = 'target_membership_not_active';
      end if;
      if actor_role = 'admin' and target_member.role in ('owner', 'admin') then
        raise exception using
          errcode = '42501',
          message = 'account_assignment_protected';
      end if;
    end if;

    select account.* into account_row
    from content_factory.managed_accounts account
    where account.organization_id = organization_id
      and account.id = account_id
    for update;

    if account_row.id is null then
      raise exception using errcode = 'P0002', message = 'managed_account_not_found';
    end if;
    if account_row.status <> 'active' then
      raise exception using errcode = '55000', message = 'managed_account_archived';
    end if;

    select assignment.* into assignment_row
    from content_factory.member_account_assignments assignment
    where assignment.organization_id = organization_id
      and assignment.account_id = account_id
      and assignment.status = 'active'
    for update;

    previous_assignment_profile_id := assignment_row.profile_id;

    if actor_role = 'admin' and assignment_row.id is not null and exists (
      select 1
      from content_factory.memberships member
      where member.organization_id = organization_id
        and member.profile_id = assignment_row.profile_id
        and member.role in ('owner', 'admin')
    ) then
      raise exception using
        errcode = '42501',
        message = 'account_assignment_protected';
    end if;

    if action_value = 'bind_account' then
      if assignment_row.id is not null
         and assignment_row.profile_id = target_profile_id then
        changed := false;
      else
        if assignment_row.id is not null then
          update content_factory.member_account_assignments assignment
          set
            status = 'revoked',
            revoked_by = actor_id,
            revoked_at = now(),
            revoke_reason = 'reassigned_by_admin'
          where assignment.id = assignment_row.id;
        end if;

        insert into content_factory.member_account_assignments (
          organization_id,
          account_id,
          profile_id,
          assigned_by
        ) values (
          organization_id,
          account_id,
          target_profile_id,
          actor_id
        )
        returning * into assignment_row;
      end if;
      event_name := 'admin_managed_account_bound';
    else
      if assignment_row.id is null then
        changed := false;
      else
        update content_factory.member_account_assignments assignment
        set
          status = 'revoked',
          revoked_by = actor_id,
          revoked_at = now(),
          revoke_reason = 'unassigned_by_admin'
        where assignment.id = assignment_row.id
        returning * into assignment_row;
      end if;
      target_profile_id := null;
      event_name := 'admin_managed_account_unbound';
    end if;

    result := jsonb_build_object(
      'ok', true,
      'action', action_value,
      'organization_id', organization_id,
      'changed', changed,
      'account_id', account_id,
      'assignment', case
        when action_value = 'unbind_account' then null
        else jsonb_build_object(
          'id', assignment_row.id,
          'account_id', assignment_row.account_id,
          'profile_id', assignment_row.profile_id,
          'status', assignment_row.status,
          'assigned_at', assignment_row.assigned_at
        )
      end
    );
    event_entity_type := 'managed_account';
    event_entity_id := account_id::text;
    event_properties := jsonb_build_object(
      'previous_profile_id', previous_assignment_profile_id,
      'target_profile_id', target_profile_id,
      'changed', changed,
      'actor_role', actor_role
    );
  end if;

  perform content_factory_private.emit_event(
    organization_id,
    actor_id,
    event_name,
    event_entity_type,
    event_entity_id,
    event_properties,
    'admin:' || action_value || ':' || content_factory_private.json_hash(
      jsonb_build_object('idempotency_key', idempotency_key)
    ),
    'server_rpc'
  );

  return content_factory_private.finish_command(
    organization_id,
    actor_id,
    'creator_admin_' || action_value,
    idempotency_key,
    canonical_payload,
    result
  );
end;
$$;

revoke all on function public.creator_admin_mutate(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_admin_mutate(jsonb)
  to authenticated, service_role;

-- Trusted provisioning for the authenticated invitation Edge Function.  The
-- supplied manager is checked again inside the database, including Auth state.
-- A new membership is always a trainee; this RPC can never grant workspace
-- certification, a waiver, or an administrative role.
create or replace function public.system_admin_provision_member(
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
  invited_by_id uuid;
  idempotency_key text;
  target_email text;
  target_display_name text;
  target_invited_at timestamptz;
  target_email_confirmed_at timestamptz;
  target_banned_until timestamptz;
  target_deleted_at timestamptz;
  target_profile_status text;
  inviter_role text;
  membership_row content_factory.memberships%rowtype;
  membership_already_active boolean := false;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception using errcode = '42501', message = 'service_role_required';
  end if;

  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.require_admin_keys(
    p_payload,
    array[
      'organization_id', 'user_id', 'invited_by', 'idempotency_key', 'role'
    ],
    array[
      'organization_id', 'user_id', 'invited_by', 'idempotency_key'
    ]
  );
  organization_id := content_factory_private.require_uuid(
    p_payload,
    'organization_id'
  );
  target_user_id := content_factory_private.require_uuid(
    p_payload,
    'user_id'
  );
  invited_by_id := content_factory_private.require_uuid(
    p_payload,
    'invited_by'
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  if p_payload ? 'role' and lower(content_factory_private.require_text(
    p_payload,
    'role',
    7,
    7
  )) <> 'trainee' then
    raise exception using errcode = '22023', message = 'admin_member_role_invalid';
  end if;
  request_payload := jsonb_build_object(
    'organization_id', organization_id,
    'user_id', target_user_id,
    'invited_by', invited_by_id,
    'role', 'trainee'
  );

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('system_admin_provision:' || target_user_id::text)
  );

  if not exists (
    select 1
    from content_factory.organizations organization
    where organization.id = organization_id
      and organization.status = 'active'
  ) then
    raise exception using errcode = '42501', message = 'organization_not_active';
  end if;

  select member.role into inviter_role
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
    and member.profile_id = invited_by_id
    and member.status = 'active'
    and member.role in ('owner', 'admin');

  if inviter_role is null then
    raise exception using errcode = '42501', message = 'inviter_not_authorized';
  end if;

  select
    lower(btrim(auth_user.email)),
    nullif(btrim(coalesce(auth_user.raw_user_meta_data ->> 'display_name', '')), ''),
    auth_user.invited_at,
    auth_user.email_confirmed_at,
    auth_user.banned_until,
    auth_user.deleted_at
  into
    target_email,
    target_display_name,
    target_invited_at,
    target_email_confirmed_at,
    target_banned_until,
    target_deleted_at
  from auth.users auth_user
  where auth_user.id = target_user_id;

  if target_email is null then
    raise exception using errcode = 'P0002', message = 'target_auth_user_not_found';
  end if;
  if target_invited_at is null and target_email_confirmed_at is null then
    raise exception using errcode = '42501', message = 'target_auth_user_not_invited';
  end if;
  if target_deleted_at is not null
     or (target_banned_until is not null and target_banned_until > now()) then
    raise exception using errcode = '42501', message = 'target_auth_user_not_active';
  end if;

  insert into content_factory.profiles (
    id,
    email,
    display_name
  ) values (
    target_user_id,
    target_email,
    target_display_name
  )
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

  select member.* into membership_row
  from content_factory.memberships member
  where member.organization_id = organization_id
    and member.profile_id = target_user_id
  for update;

  if membership_row.id is not null
     and membership_row.status <> 'active' then
    raise exception using
      errcode = '23505',
      message = 'target_membership_history_conflict';
  end if;
  membership_already_active := membership_row.id is not null;

  replay := content_factory_private.begin_command(
    organization_id,
    'system_admin_provision_member',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  if membership_row.id is null then
    insert into content_factory.memberships (
      organization_id,
      profile_id,
      role,
      status
    ) values (
      organization_id,
      target_user_id,
      'trainee',
      'active'
    )
    returning * into membership_row;
  end if;

  result := jsonb_build_object(
    'ok', true,
    'organization_id', organization_id,
    'user_id', target_user_id,
    'membership_id', membership_row.id,
    'role', membership_row.role,
    'status', membership_row.status,
    'already_active', membership_already_active
  );

  perform content_factory_private.emit_event(
    organization_id,
    invited_by_id,
    case when membership_already_active
      then 'admin_member_invite_reconciled'
      else 'admin_member_invite_provisioned'
    end,
    'membership',
    membership_row.id::text,
    jsonb_build_object(
      'target_user_id', target_user_id,
      'role', membership_row.role,
      'status', membership_row.status
    ),
    'system-admin-provision:' || content_factory_private.json_hash(
      jsonb_build_object('idempotency_key', idempotency_key)
    ),
    'system'
  );

  return content_factory_private.finish_command(
    organization_id,
    invited_by_id,
    'system_admin_provision_member',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

revoke all on function public.system_admin_provision_member(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_admin_provision_member(jsonb)
  to service_role;

-- Existing-user reconciliation reveals nothing to browser callers.  The
-- service-role Edge Function supplies an exact normalized email, and this RPC
-- accepts only one confirmed, active Auth identity before delegating to the
-- same trainee-only provisioning boundary.
create or replace function public.system_admin_reconcile_member(
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
  invited_by_id uuid;
  email_value text;
  idempotency_key text;
  target_count integer;
  target_user_id uuid;
  target_email_confirmed_at timestamptz;
  target_banned_until timestamptz;
  target_deleted_at timestamptz;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception using errcode = '42501', message = 'service_role_required';
  end if;

  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.require_admin_keys(
    p_payload,
    array[
      'organization_id', 'email', 'invited_by', 'idempotency_key'
    ],
    array[
      'organization_id', 'email', 'invited_by', 'idempotency_key'
    ]
  );
  organization_id := content_factory_private.require_uuid(
    p_payload,
    'organization_id'
  );
  invited_by_id := content_factory_private.require_uuid(
    p_payload,
    'invited_by'
  );
  email_value := lower(content_factory_private.require_text(
    p_payload,
    'email',
    3,
    320
  ));
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );

  if email_value !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then
    raise exception using errcode = '22023', message = 'email_invalid';
  end if;

  select count(*), (array_agg(auth_user.id order by auth_user.id))[1]
    into target_count, target_user_id
  from auth.users auth_user
  where lower(btrim(auth_user.email)) = email_value;

  if target_count = 0 or target_user_id is null then
    raise exception using
      errcode = 'P0002',
      message = 'reconciliation_auth_user_not_found';
  end if;
  if target_count <> 1 then
    raise exception using
      errcode = '55000',
      message = 'reconciliation_auth_user_ambiguous';
  end if;

  select
    auth_user.email_confirmed_at,
    auth_user.banned_until,
    auth_user.deleted_at
  into
    target_email_confirmed_at,
    target_banned_until,
    target_deleted_at
  from auth.users auth_user
  where auth_user.id = target_user_id;

  if target_email_confirmed_at is null then
    raise exception using
      errcode = '42501',
      message = 'reconciliation_email_not_confirmed';
  end if;
  if target_deleted_at is not null
     or (target_banned_until is not null and target_banned_until > now()) then
    raise exception using errcode = '42501', message = 'target_auth_user_not_active';
  end if;

  return public.system_admin_provision_member(jsonb_build_object(
    'organization_id', organization_id,
    'user_id', target_user_id,
    'invited_by', invited_by_id,
    'idempotency_key', idempotency_key
  ));
end;
$$;

revoke all on function public.system_admin_reconcile_member(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_admin_reconcile_member(jsonb)
  to service_role;

-- The invitation journal reservation must use the same independent admin
-- boundary.  Keeping a distinct RPC avoids changing the legacy training-gated
-- contract for any older caller while the creator-invite Edge Function moves
-- to this path.
create or replace function public.system_admin_record_invite_delivery_attempts(
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
  requested_by_id uuid;
  request_id_value uuid;
  requested_at_value timestamptz;
  results_value jsonb;
  result_item jsonb;
  email_value text;
  status_value text;
  reason_value text;
  delivery_value text;
  membership_value boolean;
  inserted_count integer := 0;
  prior_request_id uuid;
  suppressed_value jsonb := '[]'::jsonb;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception using errcode = '42501', message = 'service_role_required';
  end if;

  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.require_admin_keys(
    p_payload,
    array[
      'organization_id', 'requested_by', 'request_id',
      'requested_at', 'results'
    ],
    array[
      'organization_id', 'requested_by', 'request_id',
      'requested_at', 'results'
    ]
  );
  organization_id := content_factory_private.require_uuid(
    p_payload,
    'organization_id'
  );
  requested_by_id := content_factory_private.require_uuid(
    p_payload,
    'requested_by'
  );
  request_id_value := content_factory_private.require_uuid(
    p_payload,
    'request_id'
  );
  results_value := p_payload -> 'results';

  if jsonb_typeof(results_value) <> 'array'
     or jsonb_array_length(results_value) < 1
     or jsonb_array_length(results_value) > 50 then
    raise exception using
      errcode = '22023',
      message = 'invite_attempt_results_invalid';
  end if;
  begin
    requested_at_value := content_factory_private.require_text(
      p_payload,
      'requested_at',
      10,
      64
    )::timestamptz;
  exception
    when invalid_text_representation
      or invalid_datetime_format
      or datetime_field_overflow then
      raise exception using
        errcode = '22023',
        message = 'invite_attempt_time_invalid';
  end;
  if requested_at_value < now() - interval '15 minutes'
     or requested_at_value > now() + interval '2 minutes' then
    raise exception using
      errcode = '22023',
      message = 'invite_attempt_time_invalid';
  end if;

  if not exists (
    select 1
    from content_factory.organizations organization
    join content_factory.memberships membership
      on membership.organization_id = organization.id
     and membership.profile_id = requested_by_id
     and membership.status = 'active'
     and membership.role in ('owner', 'admin')
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
    where organization.id = organization_id
      and organization.status = 'active'
  ) then
    raise exception using errcode = '42501', message = 'inviter_not_authorized';
  end if;

  -- Serialize only the short journal transaction. External email requests are
  -- made after this call returns and therefore never hold the lock.
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-invite:' || organization_id::text,
      0
    )
  );

  for result_item in
    select item.value
    from jsonb_array_elements(results_value) item(value)
  loop
    if jsonb_typeof(result_item) <> 'object' then
      raise exception using
        errcode = '22023',
        message = 'invite_attempt_result_invalid';
    end if;
    perform content_factory_private.require_admin_keys(
      result_item,
      array[
        'email', 'status', 'reason_code',
        'delivery_status', 'membership_provisioned'
      ],
      array[
        'email', 'status', 'reason_code',
        'delivery_status', 'membership_provisioned'
      ]
    );

    email_value := lower(content_factory_private.require_text(
      result_item,
      'email',
      3,
      320
    ));
    status_value := content_factory_private.require_text(
      result_item,
      'status',
      3,
      40
    );
    reason_value := content_factory_private.require_text(
      result_item,
      'reason_code',
      3,
      80
    );
    delivery_value := content_factory_private.require_text(
      result_item,
      'delivery_status',
      3,
      40
    );

    if email_value !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
       or status_value not in (
         'invited',
         'already_exists',
         'rate_limited',
         'smtp_required',
         'pending_verification',
         'failed'
       )
       or reason_value !~ '^[a-z0-9_]{3,80}$'
       or delivery_value not in (
         'accepted_unconfirmed',
         'not_requested',
         'unknown'
       )
       or jsonb_typeof(result_item -> 'membership_provisioned') <> 'boolean' then
      raise exception using
        errcode = '22023',
        message = 'invite_attempt_result_invalid';
    end if;
    membership_value := (
      result_item ->> 'membership_provisioned'
    )::boolean;

    prior_request_id := null;
    if reason_value = 'invite_processing_started' then
      select attempt.request_id
        into prior_request_id
      from content_factory.invite_delivery_attempts attempt
      where attempt.organization_id = organization_id
        and attempt.email = email_value
        and attempt.request_id <> request_id_value
        and attempt.requested_at >= now() - interval '10 minutes'
        and (
          attempt.status = 'pending_verification'
          or attempt.delivery_status = 'accepted_unconfirmed'
        )
      order by attempt.requested_at desc, attempt.created_at desc
      limit 1;

      if prior_request_id is not null then
        status_value := 'pending_verification';
        reason_value := 'duplicate_request_suppressed';
        delivery_value := 'unknown';
        membership_value := false;
        suppressed_value := suppressed_value || jsonb_build_array(email_value);
      end if;
    end if;

    insert into content_factory.invite_delivery_attempts (
      organization_id,
      request_id,
      email,
      status,
      reason_code,
      delivery_status,
      membership_provisioned,
      requested_by,
      requested_at
    ) values (
      organization_id,
      request_id_value,
      email_value,
      status_value,
      reason_value,
      delivery_value,
      membership_value,
      requested_by_id,
      requested_at_value
    )
    on conflict on constraint invite_delivery_attempts_request_email_uq
    do update set
      status = excluded.status,
      reason_code = excluded.reason_code,
      delivery_status = excluded.delivery_status,
      membership_provisioned = excluded.membership_provisioned;
    inserted_count := inserted_count + 1;
  end loop;

  perform content_factory_private.emit_event(
    organization_id,
    requested_by_id,
    'admin_invite_delivery_attempts_recorded',
    'invite_request',
    request_id_value::text,
    jsonb_build_object('result_count', inserted_count),
    'admin-invite-delivery:' || request_id_value::text,
    'system'
  );

  return jsonb_build_object(
    'ok', true,
    'request_id', request_id_value,
    'stored', inserted_count,
    'suppressed', suppressed_value
  );
end;
$$;

revoke all on function
  public.system_admin_record_invite_delivery_attempts(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_admin_record_invite_delivery_attempts(jsonb)
  to service_role;

-- Keep the durable invitation history available to the same independent
-- owner/admin plane.  The legacy definition required operator training.
create or replace function public.creator_invite_delivery_attempts(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  latest_request_id uuid;
  latest_requested_at timestamptz;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.require_admin_keys(
    p_payload,
    array['organization_id']
  );
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.require_admin_actor(organization_id);

  select attempt.request_id, attempt.requested_at
    into latest_request_id, latest_requested_at
  from content_factory.invite_delivery_attempts attempt
  where attempt.organization_id = organization_id
  order by attempt.requested_at desc, attempt.created_at desc
  limit 1;

  if latest_request_id is null then
    return jsonb_build_object(
      'ok', true,
      'requested', 0,
      'invited', 0,
      'already_exists', 0,
      'pending_verification', 0,
      'failed', 0,
      'results', '[]'::jsonb,
      'delivery_confirmed', false,
      'persistence', 'stored'
    );
  end if;

  select jsonb_build_object(
    'ok', true,
    'request_id', latest_request_id,
    'requested_at', latest_requested_at,
    'requested', count(*),
    'invited', count(*) filter (where attempt.status = 'invited'),
    'already_exists', count(*) filter (where attempt.status = 'already_exists'),
    'pending_verification', count(*) filter (
      where attempt.status = 'pending_verification'
    ),
    'failed', count(*) filter (
      where attempt.status not in (
        'invited', 'already_exists', 'pending_verification'
      )
    ),
    'results', coalesce(jsonb_agg(jsonb_build_object(
      'email', attempt.email,
      'status', attempt.status,
      'reason_code', attempt.reason_code,
      'delivery_status', attempt.delivery_status,
      'membership_provisioned', attempt.membership_provisioned
    ) order by attempt.created_at, attempt.email), '[]'::jsonb),
    'delivery_confirmed', false,
    'persistence', 'stored'
  ) into result
  from content_factory.invite_delivery_attempts attempt
  where attempt.organization_id = organization_id
    and attempt.request_id = latest_request_id;

  return result;
end;
$$;

revoke all on function public.creator_invite_delivery_attempts(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_invite_delivery_attempts(jsonb)
  to authenticated, service_role;

revoke all on function
  content_factory_private.require_admin_keys(jsonb, text[], text[])
  from public, anon, authenticated;
revoke all on function
  content_factory_private.admin_optional_text(jsonb, text, integer, integer)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.require_admin_actor(uuid)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.lock_admin_member(uuid, uuid)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.serialize_admin_project_membership()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.guard_member_account_assignment()
  from public, anon, authenticated;

notify pgrst, 'reload schema';

commit;
