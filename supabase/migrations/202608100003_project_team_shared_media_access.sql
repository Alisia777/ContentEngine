begin;

-- Organization membership answers who belongs to the company. Project
-- membership answers which exact production boundary that person may read.
-- Keep those scopes separate: assigning one project must never disclose every
-- project owned by the organization.
create table if not exists content_factory.workspace_project_memberships (
    organization_id uuid not null,
    project_id uuid not null,
    profile_id uuid not null,
    access_role text not null default 'member'
      check (access_role = 'member'),
    status text not null default 'active'
      check (status in ('active', 'revoked')),
    granted_by uuid not null references content_factory.profiles(id),
    updated_by uuid not null references content_factory.profiles(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (organization_id, project_id, profile_id),
    foreign key (organization_id, project_id)
      references content_factory.workspace_folders(organization_id, id)
      on delete cascade,
    foreign key (organization_id, profile_id)
      references content_factory.memberships(organization_id, profile_id)
      on delete cascade
);

create index if not exists workspace_project_memberships_profile_idx
  on content_factory.workspace_project_memberships (
    profile_id, status, organization_id, project_id
  );
create index if not exists workspace_project_memberships_project_idx
  on content_factory.workspace_project_memberships (
    organization_id, project_id, status, profile_id
  );

alter table content_factory.workspace_project_memberships
  enable row level security;
revoke all on content_factory.workspace_project_memberships
  from public, anon, authenticated;
grant all on content_factory.workspace_project_memberships to service_role;

drop trigger if exists set_updated_at
  on content_factory.workspace_project_memberships;
create trigger set_updated_at
before update on content_factory.workspace_project_memberships
for each row execute function content_factory_private.set_updated_at();

create or replace function
  content_factory_private.guard_workspace_project_membership()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' and (
    new.organization_id is distinct from old.organization_id
    or new.project_id is distinct from old.project_id
    or new.profile_id is distinct from old.profile_id
    or new.created_at is distinct from old.created_at
    or new.granted_by is distinct from old.granted_by
  ) then
    raise exception using
      errcode = '55000',
      message = 'workspace_project_membership_identity_immutable';
  end if;

  if not exists (
    select 1
    from content_factory.workspace_folders project
    where project.organization_id = new.organization_id
      and project.id = new.project_id
      and project.kind = 'project'
      and (
        project.status = 'active'
        or (new.status = 'revoked' and project.status = 'archived')
      )
  ) then
    raise exception using
      errcode = '22023',
      message = 'workspace_project_membership_project_invalid';
  end if;

  if new.status = 'active' and not exists (
    select 1
    from content_factory.memberships membership
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where membership.organization_id = new.organization_id
      and membership.profile_id = new.profile_id
      and membership.status = 'active'
      and membership.role in (
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
  content_factory_private.guard_workspace_project_membership()
  from public, anon, authenticated;

drop trigger if exists guard_workspace_project_membership
  on content_factory.workspace_project_memberships;
create trigger guard_workspace_project_membership
before insert or update
on content_factory.workspace_project_memberships
for each row execute function
  content_factory_private.guard_workspace_project_membership();

-- Existing administrators and project creators must not lose access during
-- rollout. Existing project-bound contributors are also retained, but this is
-- a one-time compatibility backfill; new collaborators require an explicit
-- owner/admin grant.
insert into content_factory.workspace_project_memberships (
  organization_id, project_id, profile_id, access_role, status,
  granted_by, updated_by
)
select
  project.organization_id,
  project.id,
  membership.profile_id,
  'member',
  'active',
  project.created_by,
  project.created_by
from content_factory.workspace_folders project
join content_factory.memberships membership
  on membership.organization_id = project.organization_id
 and membership.status = 'active'
 and membership.role in (
   'owner', 'admin', 'producer', 'reviewer', 'operator'
 )
join content_factory.profiles profile
  on profile.id = membership.profile_id
 and profile.status = 'active'
where project.kind = 'project'
  and project.status = 'active'
  and (
    membership.role in ('owner', 'admin')
    or membership.profile_id = project.created_by
  )
on conflict (organization_id, project_id, profile_id) do nothing;

with existing_contributors as (
  select media.organization_id, media.project_id, media.owner_id as profile_id
  from content_factory.media_objects media
  where media.project_id is not null
  union
  select task.organization_id, task.project_id, task.assignee_id
  from content_factory.creator_tasks task
  where task.project_id is not null
  union
  select task.organization_id, task.project_id, task.created_by
  from content_factory.creator_tasks task
  where task.project_id is not null
  union
  select batch.organization_id, batch.project_id, batch.created_by
  from content_factory.generation_batches batch
  where batch.project_id is not null
  union
  select job.organization_id, job.project_id, job.requested_by
  from content_factory.generation_jobs job
  where job.project_id is not null
  union
  select job.organization_id, job.project_id, job.assigned_to
  from content_factory.generation_jobs job
  where job.project_id is not null
  union
  select review.organization_id, review.project_id, review.requested_by
  from content_factory.content_review_runs review
  where review.project_id is not null
  union
  select research.organization_id, research.project_id, research.created_by
  from content_factory.product_research_runs research
  where research.project_id is not null
  union
  select draft.organization_id, draft.project_id, draft.created_by
  from content_factory.creative_brief_drafts draft
  where draft.project_id is not null
  union
  select placement.organization_id, placement.project_id,
         placement.assigned_to
  from content_factory.placements placement
  where placement.project_id is not null
  union
  select placement.organization_id, placement.project_id,
         placement.created_by
  from content_factory.placements placement
  where placement.project_id is not null
), eligible_contributors as (
  select contributor.organization_id, contributor.project_id,
         contributor.profile_id
  from existing_contributors contributor
  join content_factory.workspace_folders project
    on project.organization_id = contributor.organization_id
   and project.id = contributor.project_id
   and project.kind = 'project'
   and project.status = 'active'
  join content_factory.memberships membership
    on membership.organization_id = contributor.organization_id
   and membership.profile_id = contributor.profile_id
   and membership.status = 'active'
   and membership.role in (
     'owner', 'admin', 'producer', 'reviewer', 'operator'
   )
  join content_factory.profiles profile
    on profile.id = contributor.profile_id
   and profile.status = 'active'
)
insert into content_factory.workspace_project_memberships (
  organization_id, project_id, profile_id, access_role, status,
  granted_by, updated_by
)
select contributor.organization_id, contributor.project_id,
       contributor.profile_id, 'member', 'active',
       contributor.profile_id, contributor.profile_id
from eligible_contributors contributor
on conflict (organization_id, project_id, profile_id) do nothing;

create or replace function
  content_factory_private.workspace_project_access_allowed(
    p_organization_id uuid,
    p_project_id uuid,
    p_profile_id uuid
  )
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select p_profile_id is not null
    and exists (
      select 1
      from content_factory.workspace_project_memberships project_member
      join content_factory.workspace_folders project
        on project.organization_id = project_member.organization_id
       and project.id = project_member.project_id
       and project.kind = 'project'
       and project.status = 'active'
      join content_factory.memberships organization_member
        on organization_member.organization_id = project_member.organization_id
       and organization_member.profile_id = project_member.profile_id
       and organization_member.status = 'active'
       and organization_member.role in (
         'owner', 'admin', 'producer', 'reviewer', 'operator'
       )
      join content_factory.profiles profile
        on profile.id = project_member.profile_id
       and profile.status = 'active'
      where project_member.organization_id = p_organization_id
        and project_member.project_id = p_project_id
        and project_member.profile_id = p_profile_id
        and project_member.status = 'active'
    )
$$;

create or replace function
  content_factory_private.require_workspace_project_access(
    p_organization_id uuid,
    p_project_id uuid,
    p_profile_id uuid
  )
returns uuid
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  perform content_factory_private.require_workspace_project(
    p_organization_id,
    p_project_id
  );
  if not content_factory_private.workspace_project_access_allowed(
    p_organization_id,
    p_project_id,
    p_profile_id
  ) then
    raise exception using
      errcode = '42501',
      message = 'workspace_project_access_required';
  end if;
  return p_project_id;
end;
$$;

revoke all on function
  content_factory_private.workspace_project_access_allowed(uuid, uuid, uuid)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.require_workspace_project_access(uuid, uuid, uuid)
  from public, anon, authenticated;

-- Every newly created project is immediately visible to its creator and to
-- the organization's active owner/admin administrators. No other company-wide
-- role is auto-enrolled.
create or replace function
  content_factory_private.seed_workspace_project_memberships()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.kind <> 'project' or new.status <> 'active' then
    return new;
  end if;
  insert into content_factory.workspace_project_memberships (
    organization_id, project_id, profile_id, access_role, status,
    granted_by, updated_by
  )
  select new.organization_id, new.id, membership.profile_id,
         'member', 'active', new.created_by, new.created_by
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where membership.organization_id = new.organization_id
    and membership.status = 'active'
    and membership.role in (
      'owner', 'admin', 'producer', 'reviewer', 'operator'
    )
    and (
      membership.role in ('owner', 'admin')
      or membership.profile_id = new.created_by
    )
  on conflict (organization_id, project_id, profile_id) do nothing;
  return new;
end;
$$;

revoke all on function
  content_factory_private.seed_workspace_project_memberships()
  from public, anon, authenticated;

drop trigger if exists seed_workspace_project_memberships
  on content_factory.workspace_folders;
create trigger seed_workspace_project_memberships
after insert on content_factory.workspace_folders
for each row execute function
  content_factory_private.seed_workspace_project_memberships();

create or replace function public.creator_project_members(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  project_id_value uuid;
  members_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'project_members_payload_invalid';
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

  select coalesce(jsonb_agg(jsonb_build_object(
    'profile_id', project_member.profile_id,
    'display_name', profile.display_name,
    'email', profile.email,
    'organization_role', organization_member.role,
    'access_role', project_member.access_role,
    'status', project_member.status,
    'granted_by', project_member.granted_by,
    'updated_by', project_member.updated_by,
    'created_at', project_member.created_at,
    'updated_at', project_member.updated_at
  ) order by
    case project_member.status when 'active' then 0 else 1 end,
    lower(coalesce(profile.display_name, profile.email, '')),
    project_member.profile_id), '[]'::jsonb)
  into members_value
  from content_factory.workspace_project_memberships project_member
  join content_factory.memberships organization_member
    on organization_member.organization_id = project_member.organization_id
   and organization_member.profile_id = project_member.profile_id
  join content_factory.profiles profile
    on profile.id = project_member.profile_id
  where project_member.organization_id = organization_id
    and project_member.project_id = project_id_value;

  return jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'members', members_value,
    'capabilities', jsonb_build_object('manage_members', true)
  );
end;
$$;

revoke all on function public.creator_project_members(jsonb)
  from public, anon;
grant execute on function public.creator_project_members(jsonb)
  to authenticated;

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
  on conflict (organization_id, project_id, profile_id) do update
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

create or replace function public.creator_revoke_project_member(
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
  project_creator_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'profile_id', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'project_member_revoke_payload_invalid';
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
    'profile_id', target_profile_id
  );
  replay_value := content_factory_private.begin_command(
    organization_id,
    'creator_revoke_project_member',
    idempotency_key,
    request_value
  );
  if replay_value is not null then
    return replay_value;
  end if;

  select membership.role
    into target_role
  from content_factory.memberships membership
  where membership.organization_id = organization_id
    and membership.profile_id = target_profile_id;
  select project.created_by
    into project_creator_id
  from content_factory.workspace_folders project
  where project.organization_id = organization_id
    and project.id = project_id_value;
  if target_role in ('owner', 'admin')
     or target_profile_id = project_creator_id then
    raise exception using
      errcode = '42501', message = 'project_member_is_protected';
  end if;
  if not exists (
    select 1
    from content_factory.workspace_project_memberships project_member
    where project_member.organization_id = organization_id
      and project_member.project_id = project_id_value
      and project_member.profile_id = target_profile_id
      and project_member.status = 'active'
  ) then
    raise exception using
      errcode = 'P0002', message = 'project_member_not_found';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext(
      'workspace-project-member:' || project_id_value::text
      || ':' || target_profile_id::text
    )
  );
  update content_factory.workspace_project_memberships project_member
  set status = 'revoked',
      updated_by = user_id,
      updated_at = now()
  where project_member.organization_id = organization_id
    and project_member.project_id = project_id_value
    and project_member.profile_id = target_profile_id
    and project_member.status = 'active';

  result_value := jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'profile_id', target_profile_id,
    'status', 'revoked'
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'workspace_project_member_revoked',
    'workspace_project',
    project_id_value::text,
    jsonb_build_object('profile_id', target_profile_id),
    left('workspace-project-member-revoked:' || idempotency_key, 180)
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_revoke_project_member',
    idempotency_key,
    request_value,
    result_value
  );
end;
$$;

revoke all on function public.creator_revoke_project_member(jsonb)
  from public, anon;
grant execute on function public.creator_revoke_project_member(jsonb)
  to authenticated;

-- Storage object names encode organization and uploader, but not project.
-- Resolve the exact registered media row before allowing a collaborator to
-- download it. The uploader may still read an unregistered upload while the
-- existing INSERT/DELETE policies remain owner-only and unchanged.
create or replace function content_factory.storage_project_read_allowed(
  p_bucket_id text,
  p_object_name text
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select p_bucket_id = 'contentengine-private'
    and auth.uid() is not null
    and content_factory.storage_access_allowed(
      split_part(p_object_name, '/', 1),
      auth.uid()::text,
      false
    )
    and (
      split_part(p_object_name, '/', 2) = auth.uid()::text
      or exists (
        select 1
        from content_factory.media_objects media
        where media.bucket_id = p_bucket_id
          and media.object_name = p_object_name
          and media.project_id is not null
          and media.status <> 'deleted'
          and content_factory_private.workspace_project_access_allowed(
            media.organization_id,
            media.project_id,
            auth.uid()
          )
      )
    )
$$;

revoke all on function
  content_factory.storage_project_read_allowed(text, text)
  from public, anon;
grant execute on function
  content_factory.storage_project_read_allowed(text, text)
  to authenticated;

drop policy if exists contentengine_private_select on storage.objects;
create policy contentengine_private_select
on storage.objects
for select
to authenticated
using (
  content_factory.storage_project_read_allowed(
    storage.objects.bucket_id,
    storage.objects.name
  )
);

-- Defense in depth for the append-only recommendation binding. Even if a
-- future RPC forgets the project check, an authenticated caller cannot attach
-- another project's AI selection to a generation spec.
create or replace function
  content_factory_private.guard_generation_spec_ai_research_project_access()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if coalesce(auth.role(), '') = 'service_role' then
    return new;
  end if;
  if auth.uid() is null
     or new.applied_by is distinct from auth.uid()
     or not content_factory_private.workspace_project_access_allowed(
       new.organization_id,
       new.project_id,
       auth.uid()
     ) then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_ai_research_project_access_required';
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.guard_generation_spec_ai_research_project_access()
  from public, anon, authenticated;

drop trigger if exists generation_spec_ai_research_project_access
  on content_factory.generation_spec_ai_research_bindings;
create trigger generation_spec_ai_research_project_access
before insert on content_factory.generation_spec_ai_research_bindings
for each row execute function
  content_factory_private.guard_generation_spec_ai_research_project_access();

-- Preserve the complete v2 recommendation implementation and put a small
-- project-ACL gateway in front of it. This avoids duplicating its ranking and
-- preset rules while keeping the public RPC signature unchanged.
do $preserve_generation_recommendations_before_project_acl$
begin
  if to_regprocedure(
    'content_factory_private.contentengine_generation_research_recommendations_pre_acl_v423(jsonb)'
  ) is null then
    alter function
      public.contentengine_generation_research_recommendations(jsonb)
      set schema content_factory_private;
    alter function
      content_factory_private.contentengine_generation_research_recommendations(jsonb)
      rename to
        contentengine_generation_research_recommendations_pre_acl_v423;
  end if;
end;
$preserve_generation_recommendations_before_project_acl$;

revoke all on function
  content_factory_private.contentengine_generation_research_recommendations_pre_acl_v423(
    jsonb
  ) from public, anon, authenticated;

create or replace function
  public.contentengine_generation_research_recommendations(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  user_id uuid;
  organization_id_value uuid;
  project_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value,
    project_id_value,
    user_id
  );
  return content_factory_private
    .contentengine_generation_research_recommendations_pre_acl_v423(
      p_payload
    );
end;
$$;

revoke all on function
  public.contentengine_generation_research_recommendations(jsonb)
  from public, anon;
grant execute on function
  public.contentengine_generation_research_recommendations(jsonb)
  to authenticated, service_role;

-- Apply the same gateway to both sides of the append-only binding API. The
-- table trigger above remains the final barrier on INSERT.
do $preserve_bind_generation_ai_research_before_project_acl$
begin
  if to_regprocedure(
    'content_factory_private.contentengine_bind_generation_spec_ai_research_pre_project_acl(jsonb)'
  ) is null then
    alter function
      public.contentengine_bind_generation_spec_ai_research(jsonb)
      set schema content_factory_private;
    alter function
      content_factory_private.contentengine_bind_generation_spec_ai_research(jsonb)
      rename to
        contentengine_bind_generation_spec_ai_research_pre_project_acl;
  end if;
end;
$preserve_bind_generation_ai_research_before_project_acl$;

revoke all on function
  content_factory_private.contentengine_bind_generation_spec_ai_research_pre_project_acl(
    jsonb
  ) from public, anon, authenticated;

create or replace function
  public.contentengine_bind_generation_spec_ai_research(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  user_id uuid;
  organization_id_value uuid;
  project_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value,
    project_id_value,
    user_id
  );
  return content_factory_private
    .contentengine_bind_generation_spec_ai_research_pre_project_acl(
      p_payload
    );
end;
$$;

revoke all on function
  public.contentengine_bind_generation_spec_ai_research(jsonb)
  from public, anon;
grant execute on function
  public.contentengine_bind_generation_spec_ai_research(jsonb)
  to authenticated, service_role;

do $preserve_read_generation_ai_research_before_project_acl$
begin
  if to_regprocedure(
    'content_factory_private.contentengine_generation_spec_ai_research_binding_pre_acl_v423(jsonb)'
  ) is null then
    alter function
      public.contentengine_generation_spec_ai_research_binding(jsonb)
      set schema content_factory_private;
    alter function
      content_factory_private.contentengine_generation_spec_ai_research_binding(jsonb)
      rename to
        contentengine_generation_spec_ai_research_binding_pre_acl_v423;
  end if;
end;
$preserve_read_generation_ai_research_before_project_acl$;

revoke all on function
  content_factory_private.contentengine_generation_spec_ai_research_binding_pre_acl_v423(
    jsonb
  ) from public, anon, authenticated;

create or replace function
  public.contentengine_generation_spec_ai_research_binding(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  user_id uuid;
  organization_id_value uuid;
  project_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value,
    project_id_value,
    user_id
  );
  return content_factory_private
    .contentengine_generation_spec_ai_research_binding_pre_acl_v423(
      p_payload
    );
end;
$$;

revoke all on function
  public.contentengine_generation_spec_ai_research_binding(jsonb)
  from public, anon;
grant execute on function
  public.contentengine_generation_spec_ai_research_binding(jsonb)
  to authenticated, service_role;

-- Hide unrelated projects in the chooser and make the selected flow snapshot
-- team-readable for every explicit project member, including an operator.
create or replace function public.creator_project_flow(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  profile_status text;
  organization_id uuid;
  actor_role text;
  snapshot_role text;
  project_id_value uuid;
  include_projects boolean := true;
  selected_snapshot jsonb;
  projects_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'include_projects'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'project_flow_payload_invalid';
  end if;
  if p_payload ? 'include_projects' then
    if jsonb_typeof(p_payload -> 'include_projects') <> 'boolean' then
      raise exception using
        errcode = '22023',
        message = 'project_flow_include_projects_invalid';
    end if;
    include_projects := (p_payload ->> 'include_projects')::boolean;
  end if;

  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  if not exists (
    select 1
    from auth.users auth_user
    where auth_user.id = user_id
      and auth_user.email is not null
  ) then
    raise exception using
      errcode = '42501', message = 'verified_email_required';
  end if;
  select profile.status
    into profile_status
  from content_factory.profiles profile
  where profile.id = user_id;
  if profile_status is not null and profile_status <> 'active' then
    raise exception using
      errcode = '42501', message = 'profile_not_active';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  -- project_flow_snapshot uses this argument only to choose the read scope.
  -- Every explicit project member receives the complete shared snapshot.
  snapshot_role := case
    when actor_role = 'operator' then 'reviewer'
    else actor_role
  end;

  if nullif(btrim(coalesce(p_payload ->> 'project_id', '')), '') is not null then
    project_id_value := content_factory_private.require_uuid(
      p_payload,
      'project_id'
    );
    perform content_factory_private.require_workspace_project_access(
      organization_id,
      project_id_value,
      user_id
    );
    selected_snapshot := content_factory_private.project_flow_snapshot(
      organization_id,
      project_id_value,
      user_id,
      snapshot_role
    );
  end if;

  if include_projects then
    select coalesce(
      jsonb_agg(
        case
          when project.id = project_id_value
               and selected_snapshot is not null then
            (selected_snapshot -> 'project')
            || jsonb_build_object('catalog_state', 'exact')
          else jsonb_build_object(
            'id', project.id,
            'name', project.name,
            'color_token', project.color_token,
            'status', project.status,
            'version', project.version,
            'updated_at', project.updated_at,
            'current_stage', null,
            'progress_percent', 0,
            'catalog_state', 'summary',
            'next_action', jsonb_build_object(
              'label', 'Открыть проект',
              'stage', 'files',
              'route', '/workspace/home?project_id=' || project.id::text,
              'project_id', project.id,
              'entity_type', 'workspace_project',
              'entity_id', project.id
            )
          )
        end
        order by project.updated_at desc, project.id desc
      ),
      '[]'::jsonb
    )
    into projects_value
    from content_factory.workspace_folders project
    join content_factory.workspace_project_memberships project_member
      on project_member.organization_id = project.organization_id
     and project_member.project_id = project.id
     and project_member.profile_id = user_id
     and project_member.status = 'active'
    where project.organization_id = organization_id
      and project.kind = 'project'
      and project.status = 'active';
  end if;

  return jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'projects', projects_value,
    'project', selected_snapshot -> 'project',
    'stages', coalesce(selected_snapshot -> 'stages', '[]'::jsonb),
    'next_action', selected_snapshot -> 'next_action',
    'counts', coalesce(selected_snapshot -> 'counts', jsonb_build_object(
      'files', 0,
      'generation_jobs', 0,
      'reviews', 0,
      'actionable_tasks', 0,
      'placements', 0,
      'metric_snapshots', 0,
      'queue', 0
    ))
  );
end;
$$;

revoke all on function public.creator_project_flow(jsonb)
  from public, anon;
grant execute on function public.creator_project_flow(jsonb)
  to authenticated;

create or replace function public.creator_project_media(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  project_id_value uuid;
  media_id_value uuid;
  surface_value text;
  media_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'project_id', 'media_id', 'surface'
    ])
  ) then
    raise exception using
      errcode = '22023', message = 'project_media_payload_invalid';
  end if;
  surface_value := lower(btrim(coalesce(p_payload ->> 'surface', '')));
  if surface_value not in ('generation', 'review') then
    raise exception using
      errcode = '22023', message = 'project_media_surface_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id,
    project_id_value,
    user_id
  );
  media_id_value := content_factory_private.require_uuid(
    p_payload,
    'media_id'
  );
  perform content_factory_private.require_project_entity(
    organization_id,
    project_id_value,
    'media',
    media_id_value
  );

  select jsonb_build_object(
    'id', media.id,
    'public_id', media.id,
    'project_id', media.project_id,
    'owner_id', media.owner_id,
    'task_id', media.task_id,
    'product_id', media.product_id,
    'sku', product.sku,
    'product_name', product.title,
    'original_filename', media.metadata ->> 'original_filename',
    'name', coalesce(
      media.metadata ->> 'original_filename',
      media.metadata ->> 'filename',
      media.id::text
    ),
    'kind', media.metadata ->> 'kind',
    'artifact_class', media.artifact_class,
    'lifecycle_stage', media.lifecycle_stage,
    'mime_type', media.mime_type,
    'size_bytes', media.size_bytes,
    'sha256', media.sha256,
    'bucket_id', media.bucket_id,
    'object_name', media.object_name,
    'status', media.status,
    'metadata', media.metadata,
    'generation_job_id', media.metadata ->> 'generation_job_id',
    'rights_confirmed',
      media.metadata -> 'rights_confirmed' is not distinct from 'true'::jsonb,
    'identity_verified', coalesce((
      product.id is not null
      and media.metadata ->> 'kind' in ('product_photo', 'packshot')
    ), false),
    'created_at', media.created_at,
    'updated_at', media.updated_at,
    '_cursor', jsonb_build_object(
      'at', media.created_at,
      'id', media.id
    )
  )
  into media_value
  from content_factory.media_objects media
  left join content_factory.products product
    on product.organization_id = media.organization_id
   and product.id = media.product_id
   and product.status = 'active'
  where media.organization_id = organization_id
    and media.project_id = project_id_value
    and media.id = media_id_value
    and media.status = 'ready'
    and (
      surface_value <> 'review'
      or media.mime_type in (
        'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
      )
    );

  if media_value is null then
    raise exception using
      errcode = '42501', message = 'project_media_not_visible';
  end if;
  return jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'media_id', media_id_value,
    'surface', surface_value,
    'media', media_value
  );
end;
$$;

revoke all on function public.creator_project_media(jsonb)
  from public, anon;
grant execute on function public.creator_project_media(jsonb)
  to authenticated;

create or replace function public.creator_workspace_browser(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  profile_status text;
  organization_id uuid;
  project_id_value uuid;
  actor_role text;
  folder_manage_scope boolean;
  folder_id_value uuid;
  page_size integer := 50;
  search_value text := '';
  entity_types_value text[] := array['media', 'task'];
  media_kinds_value text[] := array[]::text[];
  task_statuses_value text[] := array[]::text[];
  cursor_position bigint;
  cursor_type text;
  cursor_id uuid;
  folders_value jsonb;
  current_folder_value jsonb;
  items_value jsonb;
  has_more boolean;
  next_cursor_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'folder_id', 'page_size', 'search',
    'entity_types', 'media_kinds', 'task_statuses', 'cursor'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'workspace_browser_payload_invalid';
  end if;
  if not (p_payload ? 'project_id') then
    raise exception using
      errcode = '22023', message = 'project_id_required';
  end if;

  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  if not exists (
    select 1 from auth.users auth_user
    where auth_user.id = user_id and auth_user.email is not null
  ) then
    raise exception using
      errcode = '42501', message = 'verified_email_required';
  end if;
  select profile.status into profile_status
  from content_factory.profiles profile
  where profile.id = user_id;
  if profile_status is not null and profile_status <> 'active' then
    raise exception using
      errcode = '42501', message = 'profile_not_active';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  folder_manage_scope := actor_role = any(
    array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id,
    project_id_value,
    user_id
  );

  if p_payload ? 'folder_id'
     and jsonb_typeof(p_payload -> 'folder_id') <> 'null'
     and nullif(btrim(coalesce(p_payload ->> 'folder_id', '')), '')
       is not null then
    folder_id_value := content_factory_private.require_uuid(
      p_payload,
      'folder_id'
    );
    if not exists (
      select 1 from content_factory.workspace_folders folder
      where folder.organization_id = organization_id
        and folder.id = folder_id_value
        and folder.status = 'active'
    ) then
      raise exception using
        errcode = 'P0002', message = 'workspace_folder_not_found';
    end if;
    if content_factory_private.workspace_project_for_folder(
         organization_id,
         folder_id_value
       ) is distinct from project_id_value then
      raise exception using
        errcode = '42501', message = 'workspace_folder_project_mismatch';
    end if;
  end if;

  if p_payload ? 'page_size' then
    if coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'workspace_page_size_invalid';
    end if;
    begin
      page_size := (p_payload ->> 'page_size')::integer;
    exception when invalid_text_representation or numeric_value_out_of_range then
      raise exception using
        errcode = '22023', message = 'workspace_page_size_invalid';
    end;
  end if;
  if page_size not between 1 and 100 then
    raise exception using
      errcode = '22023', message = 'workspace_page_size_invalid';
  end if;

  search_value := btrim(coalesce(p_payload ->> 'search', ''));
  if length(search_value) > 120 or search_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023', message = 'workspace_search_invalid';
  end if;

  if p_payload ? 'entity_types' then
    if jsonb_typeof(p_payload -> 'entity_types') <> 'array'
       or jsonb_array_length(p_payload -> 'entity_types') not between 1 and 2
       or exists (
         select 1
         from jsonb_array_elements(p_payload -> 'entity_types') item(value)
         where jsonb_typeof(item.value) <> 'string'
       ) then
      raise exception using
        errcode = '22023', message = 'workspace_entity_types_invalid';
    end if;
    select coalesce(array_agg(distinct lower(value)), array[]::text[])
      into entity_types_value
    from jsonb_array_elements_text(p_payload -> 'entity_types') item(value);
    if cardinality(entity_types_value) < 1
       or not (entity_types_value <@ array['media', 'task']::text[]) then
      raise exception using
        errcode = '22023', message = 'workspace_entity_types_invalid';
    end if;
  end if;

  if p_payload ? 'media_kinds' then
    if jsonb_typeof(p_payload -> 'media_kinds') <> 'array'
       or jsonb_array_length(p_payload -> 'media_kinds') > 10
       or exists (
         select 1
         from jsonb_array_elements(p_payload -> 'media_kinds') item(value)
         where jsonb_typeof(item.value) <> 'string'
       ) then
      raise exception using
        errcode = '22023', message = 'workspace_media_kinds_invalid';
    end if;
    select coalesce(array_agg(distinct lower(value)), array[]::text[])
      into media_kinds_value
    from jsonb_array_elements_text(p_payload -> 'media_kinds') item(value);
    if exists (
      select 1
      from unnest(media_kinds_value) media_kind(value)
      where not content_factory_private.workspace_media_kind_supported(
        media_kind.value
      )
    ) then
      raise exception using
        errcode = '22023', message = 'workspace_media_kinds_invalid';
    end if;
  end if;

  if p_payload ? 'task_statuses' then
    if jsonb_typeof(p_payload -> 'task_statuses') <> 'array'
       or jsonb_array_length(p_payload -> 'task_statuses') > 7
       or exists (
         select 1
         from jsonb_array_elements(p_payload -> 'task_statuses') item(value)
         where jsonb_typeof(item.value) <> 'string'
       ) then
      raise exception using
        errcode = '22023', message = 'workspace_task_statuses_invalid';
    end if;
    select coalesce(array_agg(distinct lower(value)), array[]::text[])
      into task_statuses_value
    from jsonb_array_elements_text(p_payload -> 'task_statuses') item(value);
    if not (task_statuses_value <@ array[
      'todo', 'in_progress', 'submitted', 'review',
      'done', 'blocked', 'cancelled'
    ]::text[]) then
      raise exception using
        errcode = '22023', message = 'workspace_task_statuses_invalid';
    end if;
  end if;

  if p_payload ? 'cursor' then
    if jsonb_typeof(p_payload -> 'cursor') <> 'object'
       or (p_payload -> 'cursor') - array[
         'position', 'type', 'id'
       ]::text[] <> '{}'::jsonb
       or coalesce(p_payload #>> '{cursor,position}', '') !~ '^[0-9]+$'
       or coalesce(p_payload #>> '{cursor,type}', '')
         not in ('media', 'task')
       or coalesce(p_payload #>> '{cursor,id}', '') !~* (
         '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
         || '[0-9a-f]{4}-[0-9a-f]{12}$'
       ) then
      raise exception using
        errcode = '22023', message = 'workspace_cursor_invalid';
    end if;
    begin
      cursor_position := (p_payload #>> '{cursor,position}')::bigint;
      cursor_type := p_payload #>> '{cursor,type}';
      cursor_id := (p_payload #>> '{cursor,id}')::uuid;
    exception
      when invalid_text_representation or numeric_value_out_of_range then
        raise exception using
          errcode = '22023', message = 'workspace_cursor_invalid';
    end;
  end if;

  with media_counts as (
    select location.folder_id, count(*)::integer as item_count
    from content_factory.media_objects media
    join content_factory.workspace_media_locations location
      on location.organization_id = media.organization_id
     and location.media_object_id = media.id
    where media.organization_id = organization_id
      and media.project_id = project_id_value
      and media.status <> 'deleted'
    group by location.folder_id
  ), task_counts as (
    select location.folder_id, count(*)::integer as item_count
    from content_factory.creator_tasks task
    join content_factory.workspace_task_locations location
      on location.organization_id = task.organization_id
     and location.task_id = task.id
    where task.organization_id = organization_id
      and task.project_id = project_id_value
    group by location.folder_id
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'id', folder.id,
    'project_id', project_id_value,
    'parent_id', folder.parent_id,
    'name', folder.name,
    'color_token', folder.color_token,
    'kind', folder.kind,
    'system_role', folder.system_role,
    'can_edit', folder_manage_scope and folder.system_role is null,
    'position', folder.position,
    'version', folder.version,
    'media_count', coalesce(media_counts.item_count, 0),
    'task_count', coalesce(task_counts.item_count, 0),
    'created_by', folder.created_by,
    'created_at', folder.created_at,
    'updated_at', folder.updated_at
  ) order by folder.position desc, folder.id desc), '[]'::jsonb)
  into folders_value
  from content_factory.workspace_folders folder
  left join media_counts on media_counts.folder_id = folder.id
  left join task_counts on task_counts.folder_id = folder.id
  where folder.organization_id = organization_id
    and folder.status = 'active'
    and content_factory_private.workspace_project_for_folder(
      organization_id,
      folder.id
    ) = project_id_value;

  if folder_id_value is not null then
    select jsonb_build_object(
      'id', folder.id,
      'project_id', project_id_value,
      'parent_id', folder.parent_id,
      'name', folder.name,
      'color_token', folder.color_token,
      'kind', folder.kind,
      'system_role', folder.system_role,
      'can_edit', folder_manage_scope and folder.system_role is null,
      'position', folder.position,
      'version', folder.version,
      'created_at', folder.created_at,
      'updated_at', folder.updated_at
    )
    into current_folder_value
    from content_factory.workspace_folders folder
    where folder.organization_id = organization_id
      and folder.id = folder_id_value
      and folder.status = 'active';
  end if;

  with visible_items as (
    select
      location.position,
      'media'::text as entity_type,
      media.id as entity_id,
      jsonb_build_object(
        'type', 'media',
        'id', media.id,
        'project_id', project_id_value,
        'folder_id', location.folder_id,
        'position', location.position,
        'location_version', location.version,
        'owner_id', media.owner_id,
        'task_id', media.task_id,
        'product_id', media.product_id,
        'product_name', product.title,
        'sku', product.sku,
        'wb_article', product.current_wb_article,
        'object_key', media.object_name,
        'original_filename', media.metadata ->> 'original_filename',
        'kind', media.metadata ->> 'kind',
        'artifact_class', media.artifact_class,
        'lifecycle_stage', media.lifecycle_stage,
        'mime_type', media.mime_type,
        'size_bytes', media.size_bytes,
        'sha256', media.sha256,
        'status', media.status,
        'created_at', media.created_at,
        'updated_at', media.updated_at
      ) as item
    from content_factory.media_objects media
    join content_factory.workspace_media_locations location
      on location.organization_id = media.organization_id
     and location.media_object_id = media.id
    left join content_factory.products product
      on product.organization_id = media.organization_id
     and product.id = media.product_id
    where media.organization_id = organization_id
      and media.project_id = project_id_value
      and content_factory_private.workspace_folder_scope_matches(
        p_payload,
        location.folder_id
      )
      and media.status <> 'deleted'
      and 'media' = any(entity_types_value)
      and (
        cardinality(media_kinds_value) = 0
        or coalesce(media.metadata ->> 'kind', '')
          = any(media_kinds_value)
      )
      and (
        search_value = ''
        or media.id::text ilike '%' || search_value || '%'
        or media.object_name ilike '%' || search_value || '%'
        or coalesce(media.metadata ->> 'original_filename', '') ilike
          '%' || search_value || '%'
        or coalesce(media.metadata ->> 'kind', '') ilike
          '%' || search_value || '%'
        or coalesce(product.sku, '') ilike '%' || search_value || '%'
        or coalesce(product.title, '') ilike '%' || search_value || '%'
        or coalesce(product.current_wb_article, '') ilike
          '%' || search_value || '%'
      )
    union all
    select
      location.position,
      'task'::text as entity_type,
      task.id as entity_id,
      jsonb_build_object(
        'type', 'task',
        'id', task.id,
        'project_id', project_id_value,
        'folder_id', location.folder_id,
        'position', location.position,
        'location_version', location.version,
        'task_type', task.task_type,
        'title', task.title,
        'instructions', task.instructions,
        'status', task.status,
        'priority', task.priority,
        'payout_minor', task.payout_minor,
        'due_at', task.due_at,
        'assignee_id', task.assignee_id,
        'created_by', task.created_by,
        'product_id', task.product_id,
        'product_name', product.title,
        'sku', product.sku,
        'wb_article', product.current_wb_article,
        'result', task.result,
        'submitted_at', task.submitted_at,
        'completed_at', task.completed_at,
        'created_at', task.created_at,
        'updated_at', task.updated_at
      ) as item
    from content_factory.creator_tasks task
    join content_factory.workspace_task_locations location
      on location.organization_id = task.organization_id
     and location.task_id = task.id
    left join content_factory.products product
      on product.organization_id = task.organization_id
     and product.id = task.product_id
    where task.organization_id = organization_id
      and task.project_id = project_id_value
      and content_factory_private.workspace_folder_scope_matches(
        p_payload,
        location.folder_id
      )
      and 'task' = any(entity_types_value)
      and (
        cardinality(task_statuses_value) = 0
        or task.status = any(task_statuses_value)
      )
      and (
        search_value = ''
        or task.id::text ilike '%' || search_value || '%'
        or task.title ilike '%' || search_value || '%'
        or coalesce(task.instructions, '') ilike '%' || search_value || '%'
        or coalesce(product.sku, '') ilike '%' || search_value || '%'
        or coalesce(product.title, '') ilike '%' || search_value || '%'
        or coalesce(product.current_wb_article, '') ilike
          '%' || search_value || '%'
      )
  ), candidates as materialized (
    select visible.*
    from visible_items visible
    where cursor_position is null
       or (visible.position, visible.entity_type, visible.entity_id)
          < (cursor_position, cursor_type, cursor_id)
    order by visible.position desc, visible.entity_type desc,
      visible.entity_id desc
    limit page_size + 1
  ), page as (
    select candidate.*
    from candidates candidate
    order by candidate.position desc, candidate.entity_type desc,
      candidate.entity_id desc
    limit page_size
  ), last_page_item as (
    select jsonb_build_object(
      'position', page.position,
      'type', page.entity_type,
      'id', page.entity_id
    ) as cursor_value
    from page
    order by page.position, page.entity_type, page.entity_id
    limit 1
  )
  select
    coalesce((
      select jsonb_agg(
        page.item || jsonb_build_object(
          '_cursor', jsonb_build_object(
            'position', page.position,
            'type', page.entity_type,
            'id', page.entity_id
          )
        )
        order by page.position desc, page.entity_type desc,
          page.entity_id desc
      ) from page
    ), '[]'::jsonb),
    (select count(*) > page_size from candidates),
    case
      when (select count(*) > page_size from candidates)
      then (select cursor_value from last_page_item)
      else null
    end
  into items_value, has_more, next_cursor_value;

  return jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'current_folder_id', folder_id_value,
    'current_folder', current_folder_value,
    'folders', folders_value,
    'items', items_value,
    'capabilities', jsonb_build_object(
      'manage_folders', folder_manage_scope,
      'move_items', true,
      'shared_project_read', true
    ),
    '_meta', jsonb_build_object(
      'page_size', page_size,
      'cap', 100,
      'has_more', coalesce(has_more, false),
      'next_cursor', next_cursor_value,
      'cursor_mode', 'position_type_id'
    )
  );
end;
$$;

revoke all on function public.creator_workspace_browser(jsonb)
  from public, anon;
grant execute on function public.creator_workspace_browser(jsonb)
  to authenticated;

-- The generic media section powers Research and Generation pickers. Keep its
-- legacy non-project branches intact, but make the selected-project branch use
-- the same explicit membership boundary as Finder and Storage.
create or replace function public.creator_workspace_section(
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
  section_value text;
  user_id uuid;
  profile_status text;
  organization_id uuid;
  project_id_value uuid;
  page_size_value integer := 50;
  media_cursor_at timestamptz;
  media_cursor_id uuid;
  media_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  section_value := lower(btrim(coalesce(p_payload ->> 'section', '')));
  if section_value <> 'media' or not (p_payload ? 'project_id') then
    -- Project-aware legacy sections keep their established response shape,
    -- but cannot use the legacy implementation to bypass this ACL gateway.
    if p_payload ? 'project_id' then
      user_id := auth.uid();
      if user_id is null then
        raise exception using
          errcode = '42501', message = 'authentication_required';
      end if;
      organization_id :=
        content_factory_private.resolve_organization(p_payload);
      perform content_factory_private.membership_role(
        organization_id,
        true,
        array['owner', 'admin', 'producer', 'reviewer', 'operator']
      );
      project_id_value := content_factory_private.require_uuid(
        p_payload,
        'project_id'
      );
      perform content_factory_private.require_workspace_project_access(
        organization_id,
        project_id_value,
        user_id
      );
    end if;
    return content_factory_private
      .creator_workspace_section_pre_project_reader_recovery_v416(p_payload);
  end if;

  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  if not exists (
    select 1 from auth.users auth_user
    where auth_user.id = user_id and auth_user.email is not null
  ) then
    raise exception using
      errcode = '42501', message = 'verified_email_required';
  end if;
  select profile.status into profile_status
  from content_factory.profiles profile
  where profile.id = user_id;
  if profile_status is not null and profile_status <> 'active' then
    raise exception using
      errcode = '42501', message = 'profile_not_active';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id,
    project_id_value,
    user_id
  );

  if p_payload ? 'page_size' then
    if coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'workspace_page_size_invalid';
    end if;
    begin
      page_size_value := (p_payload ->> 'page_size')::integer;
    exception
      when invalid_text_representation or numeric_value_out_of_range then
        raise exception using
          errcode = '22023', message = 'workspace_page_size_invalid';
    end;
    if page_size_value not between 1 and 100 then
      raise exception using
        errcode = '22023', message = 'workspace_page_size_invalid';
    end if;
  end if;
  if p_payload ? 'cursor'
     and jsonb_typeof(p_payload -> 'cursor') <> 'object' then
    raise exception using
      errcode = '22023', message = 'workspace_cursor_invalid';
  end if;
  perform content_factory_private.validate_workspace_cursor(
    p_payload - 'project_id',
    array['media_items']
  );
  media_cursor_at :=
    (p_payload #>> '{cursor,media_items,at}')::timestamptz;
  media_cursor_id :=
    (p_payload #>> '{cursor,media_items,id}')::uuid;

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', media.id,
    'public_id', media.id,
    'project_id', project_id_value,
    'owner_id', media.owner_id,
    'product_id', media.product_id,
    'object_key', media.object_name,
    'original_filename', media.metadata ->> 'original_filename',
    'kind', media.metadata ->> 'kind',
    'artifact_class', media.artifact_class,
    'lifecycle_stage', media.lifecycle_stage,
    'mime_type', media.mime_type,
    'size_bytes', media.size_bytes,
    'sha256', media.sha256,
    'status', media.status,
    'created_at', media.created_at,
    '_cursor', jsonb_build_object('at', media.created_at, 'id', media.id)
  ) order by media.created_at desc, media.id desc), '[]'::jsonb)
  into media_value
  from (
    select candidate.*
    from content_factory.media_objects candidate
    where candidate.organization_id = organization_id
      and candidate.project_id = project_id_value
      and candidate.status <> 'deleted'
      and (
        media_cursor_at is null
        or (candidate.created_at, candidate.id)
          < (media_cursor_at, media_cursor_id)
      )
    order by candidate.created_at desc, candidate.id desc
    limit page_size_value
  ) media;

  return jsonb_build_object(
    'media', media_value,
    'project_id', project_id_value,
    'capabilities', jsonb_build_object('shared_project_read', true),
    '_meta', jsonb_build_object(
      'page_size', page_size_value,
      'default_page_size', 50,
      'cap', 100,
      'cursor_mode', 'keyset_at_id'
    )
  );
end;
$$;

revoke all on function public.creator_workspace_section(jsonb)
  from public, anon;
grant execute on function public.creator_workspace_section(jsonb)
  to authenticated;

-- Every legacy project-scoped browser command ultimately passes through this
-- helper (research, generation spec, paid generation, review, placement,
-- metrics and folder writes).  Make explicit project membership the default
-- authority boundary instead of protecting reads only.  Trusted database
-- migrations and service-role callbacks have no end-user auth.uid() and keep
-- their existing server-side execution path; browser JWTs always fail closed.
create or replace function content_factory_private.require_workspace_project(
  p_organization_id uuid,
  p_project_id uuid
)
returns uuid
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
begin
  if p_project_id is null or not exists (
    select 1
    from content_factory.workspace_folders project
    where project.organization_id = p_organization_id
      and project.id = p_project_id
      and project.kind = 'project'
      and project.status = 'active'
  ) then
    raise exception using
      errcode = 'P0002', message = 'workspace_project_not_found';
  end if;

  if caller_id is not null
     and coalesce(auth.role(), '') <> 'service_role'
     and not content_factory_private.workspace_project_access_allowed(
       p_organization_id,
       p_project_id,
       caller_id
     ) then
    raise exception using
      errcode = '42501', message = 'workspace_project_access_required';
  end if;
  return p_project_id;
end;
$$;

revoke all on function
  content_factory_private.require_workspace_project(uuid, uuid)
  from public, anon, authenticated;
grant execute on function
  content_factory_private.require_workspace_project(uuid, uuid)
  to service_role;

comment on table content_factory.workspace_project_memberships is
  'Explicit read ACL for one workspace project; organization membership alone is insufficient.';
comment on function public.creator_project_members(jsonb) is
  'Owner/admin-only roster for one exact workspace project.';
comment on function public.creator_grant_project_member(jsonb) is
  'Idempotently grants an active operational organization member read access to one project.';
comment on function public.creator_revoke_project_member(jsonb) is
  'Idempotently revokes one non-protected project member; owners/admins and the project creator remain enrolled.';
comment on function content_factory.storage_project_read_allowed(text, text) is
  'Allows owner upload reads and registered project-member reads without widening write/delete ownership.';
comment on function
  public.contentengine_generation_research_recommendations(jsonb) is
  'Project-ACL gateway for approved AI Center recommendations; the preserved v2 implementation remains private.';
comment on function
  public.contentengine_bind_generation_spec_ai_research(jsonb) is
  'Project-ACL gateway for the append-only generation-spec recommendation binding.';
comment on function
  public.contentengine_generation_spec_ai_research_binding(jsonb) is
  'Project-ACL gateway for reading one generation-spec recommendation binding.';
comment on function
  content_factory_private.require_workspace_project(uuid, uuid) is
  'Requires an active project and, for authenticated end-user JWTs, an explicit active project membership. Trusted service callbacks remain server-scoped.';

notify pgrst, 'reload schema';

commit;
