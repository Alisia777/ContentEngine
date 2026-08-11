begin;

-- Files is a project-scoped workflow surface. Older projects may predate the
-- five canonical lifecycle folders, so repair them before enforcing exact
-- project destinations in the browser write commands.
create or replace function
  content_factory_private.repair_workspace_project_system_folders(
    p_organization_id uuid,
    p_project_id uuid
  )
returns integer
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  project_row content_factory.workspace_folders%rowtype;
  repaired_count integer := 0;
  changed_count integer := 0;
begin
  perform pg_advisory_xact_lock(
    hashtext(p_organization_id::text),
    hashtext('workspace_structure')
  );

  select project.*
    into project_row
  from content_factory.workspace_folders project
  where project.organization_id = p_organization_id
    and project.id = p_project_id
    and project.kind = 'project'
    and project.status = 'active'
  for update;

  if project_row.id is null then
    raise exception using
      errcode = 'P0002', message = 'workspace_project_not_found';
  end if;

  -- A canonical-name child from the early project release is the same folder,
  -- not a second copy. Promote it before inserting genuinely missing roles.
  with roles(system_role, name, position) as (
    values
      ('sources'::text, 'Исходники'::text, 5120::bigint),
      ('drafts', 'Черновики', 4096::bigint),
      ('review', 'На проверке', 3072::bigint),
      ('ready', 'Готово', 2048::bigint),
      ('published', 'Опубликовано', 1024::bigint)
  ), promoted as (
    update content_factory.workspace_folders folder
    set system_role = role.system_role,
        position = role.position,
        updated_by = project_row.updated_by
    from roles role
    where folder.organization_id = project_row.organization_id
      and folder.parent_id = project_row.id
      and folder.kind = 'folder'
      and folder.status = 'active'
      and folder.system_role is null
      and lower(btrim(folder.name)) = lower(role.name)
      and not exists (
        select 1
        from content_factory.workspace_folders existing
        where existing.organization_id = project_row.organization_id
          and existing.parent_id = project_row.id
          and existing.kind = 'folder'
          and existing.status = 'active'
          and existing.system_role = role.system_role
      )
    returning 1
  )
  select count(*)::integer into changed_count from promoted;
  repaired_count := repaired_count + changed_count;

  with roles(system_role, name, position) as (
    values
      ('sources'::text, 'Исходники'::text, 5120::bigint),
      ('drafts', 'Черновики', 4096::bigint),
      ('review', 'На проверке', 3072::bigint),
      ('ready', 'Готово', 2048::bigint),
      ('published', 'Опубликовано', 1024::bigint)
  )
  insert into content_factory.workspace_folders (
    organization_id, parent_id, name, color_token, kind, system_role,
    status, position, created_by, updated_by
  )
  select
    project_row.organization_id,
    project_row.id,
    role.name,
    project_row.color_token,
    'folder',
    role.system_role,
    'active',
    role.position,
    project_row.created_by,
    project_row.updated_by
  from roles role
  where not exists (
    select 1
    from content_factory.workspace_folders existing
    where existing.organization_id = project_row.organization_id
      and existing.parent_id = project_row.id
      and existing.kind = 'folder'
      and existing.status = 'active'
      and existing.system_role = role.system_role
  );
  get diagnostics changed_count = row_count;
  return repaired_count + changed_count;
end;
$$;

revoke all on function
  content_factory_private.repair_workspace_project_system_folders(uuid, uuid)
  from public, anon, authenticated;
grant execute on function
  content_factory_private.repair_workspace_project_system_folders(uuid, uuid)
  to service_role;

create or replace function
  content_factory_private.repair_workspace_classified_media_locations(
    p_organization_id uuid,
    p_project_id uuid
  )
returns integer
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  media_row record;
  destination_folder_id uuid;
  current_folder_id uuid;
  current_system_role text;
  current_project_id uuid;
  location_exists boolean;
  repaired_count integer := 0;
begin
  perform pg_advisory_xact_lock(
    hashtext(p_organization_id::text),
    hashtext('workspace_structure')
  );

  if not exists (
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

  for media_row in
    select media.id, media.lifecycle_stage
    from content_factory.media_objects media
    where media.organization_id = p_organization_id
      and media.project_id = p_project_id
      and media.artifact_class <> 'unclassified'
      and media.lifecycle_stage <> 'unclassified'
      and media.status <> 'deleted'
    order by media.id
  loop
    select folder.id
      into destination_folder_id
    from content_factory.workspace_folders folder
    where folder.organization_id = p_organization_id
      and folder.parent_id = p_project_id
      and folder.kind = 'folder'
      and folder.system_role = media_row.lifecycle_stage
      and folder.status = 'active'
    limit 1;

    if destination_folder_id is null then
      continue;
    end if;

    current_folder_id := null;
    current_system_role := null;
    current_project_id := null;
    location_exists := false;
    select
      location.folder_id,
      folder.system_role,
      content_factory_private.workspace_project_for_folder(
        location.organization_id,
        location.folder_id
      ),
      true
    into
      current_folder_id,
      current_system_role,
      current_project_id,
      location_exists
    from content_factory.workspace_media_locations location
    left join content_factory.workspace_folders folder
      on folder.organization_id = location.organization_id
     and folder.id = location.folder_id
    where location.organization_id = p_organization_id
      and location.media_object_id = media_row.id
    for update of location;

    if not location_exists or current_folder_id is null then
      if content_factory_private.sync_workspace_media_system_location(
        p_organization_id,
        media_row.id,
        false
      ) is not null then
        repaired_count := repaired_count + 1;
      end if;
      continue;
    end if;

    if current_folder_id = destination_folder_id then
      continue;
    end if;

    -- Keep an explicit custom-folder choice inside the same project. Repair
    -- stale system placements and every cross-project location.
    if current_system_role is null
       and current_project_id is not distinct from p_project_id then
      continue;
    end if;

    update content_factory.workspace_media_locations location
    set folder_id = destination_folder_id
    where location.organization_id = p_organization_id
      and location.media_object_id = media_row.id;
    repaired_count := repaired_count + 1;
  end loop;

  return repaired_count;
end;
$$;

revoke all on function
  content_factory_private.repair_workspace_classified_media_locations(uuid, uuid)
  from public, anon, authenticated;
grant execute on function
  content_factory_private.repair_workspace_classified_media_locations(uuid, uuid)
  to service_role;

do $repair_legacy_workspace_projects$
declare
  project_row record;
begin
  for project_row in
    select project.organization_id, project.id
    from content_factory.workspace_folders project
    where project.kind = 'project'
      and project.status = 'active'
    order by project.organization_id, project.id
  loop
    perform content_factory_private.repair_workspace_project_system_folders(
      project_row.organization_id,
      project_row.id
    );
    perform content_factory_private.repair_workspace_classified_media_locations(
      project_row.organization_id,
      project_row.id
    );
  end loop;
end;
$repair_legacy_workspace_projects$;

-- Keep the mature idempotency, quota, optimistic-locking and item ownership
-- implementations intact. The public adapters below add the missing exact
-- project authority boundary and then invoke those preserved commands while
-- holding the same workspace-structure transaction lock.
do $preserve_workspace_folder_writes$
begin
  if to_regprocedure(
    'content_factory_private.creator_create_workspace_folder_pre_exact_project_v429(jsonb)'
  ) is null then
    alter function public.creator_create_workspace_folder(jsonb)
      set schema content_factory_private;
    alter function
      content_factory_private.creator_create_workspace_folder(jsonb)
      rename to creator_create_workspace_folder_pre_exact_project_v429;
  end if;

  if to_regprocedure(
    'content_factory_private.creator_update_workspace_folder_pre_exact_project_v429(jsonb)'
  ) is null then
    alter function public.creator_update_workspace_folder(jsonb)
      set schema content_factory_private;
    alter function
      content_factory_private.creator_update_workspace_folder(jsonb)
      rename to creator_update_workspace_folder_pre_exact_project_v429;
  end if;

  if to_regprocedure(
    'content_factory_private.creator_move_workspace_items_pre_exact_project_v429(jsonb)'
  ) is null then
    alter function public.creator_move_workspace_items(jsonb)
      set schema content_factory_private;
    alter function
      content_factory_private.creator_move_workspace_items(jsonb)
      rename to creator_move_workspace_items_pre_exact_project_v429;
  end if;
end;
$preserve_workspace_folder_writes$;

revoke all on function
  content_factory_private.creator_create_workspace_folder_pre_exact_project_v429(jsonb)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.creator_update_workspace_folder_pre_exact_project_v429(jsonb)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.creator_move_workspace_items_pre_exact_project_v429(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_create_workspace_folder(
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
  parent_id_value uuid;
  parent_row content_factory.workspace_folders%rowtype;
  inner_payload jsonb;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'idempotency_key', 'name',
    'parent_id', 'color_token'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'workspace_folder_create_payload_invalid';
  end if;
  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id, project_id_value, user_id
  );

  if nullif(btrim(coalesce(p_payload ->> 'parent_id', '')), '') is null then
    parent_id_value := project_id_value;
  else
    parent_id_value := content_factory_private.require_uuid(
      p_payload, 'parent_id'
    );
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text), hashtext('workspace_structure')
  );
  select folder.*
    into parent_row
  from content_factory.workspace_folders folder
  where folder.organization_id = organization_id
    and folder.id = parent_id_value
    and folder.status = 'active'
  for update;
  if parent_row.id is null then
    raise exception using
      errcode = 'P0002', message = 'workspace_folder_not_found';
  end if;
  if content_factory_private.workspace_project_for_folder(
       organization_id, parent_row.id
     ) is distinct from project_id_value then
    raise exception using
      errcode = '42501', message = 'workspace_folder_project_mismatch';
  end if;
  if parent_row.system_role is not null then
    raise exception using
      errcode = '55000',
      message = 'workspace_system_folder_manual_destination_forbidden';
  end if;

  inner_payload := (p_payload - 'project_id')
    || jsonb_build_object('parent_id', parent_id_value);
  result_value := content_factory_private
    .creator_create_workspace_folder_pre_exact_project_v429(inner_payload);
  return result_value || jsonb_build_object('project_id', project_id_value);
end;
$$;

create or replace function public.creator_update_workspace_folder(
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
  folder_id_value uuid;
  parent_id_value uuid;
  folder_row content_factory.workspace_folders%rowtype;
  parent_row content_factory.workspace_folders%rowtype;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'idempotency_key', 'folder_id',
    'expected_version', 'name', 'parent_id', 'color_token', 'archive'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'workspace_folder_update_payload_invalid';
  end if;
  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id, project_id_value, user_id
  );
  folder_id_value := content_factory_private.require_uuid(
    p_payload, 'folder_id'
  );

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text), hashtext('workspace_structure')
  );
  select folder.*
    into folder_row
  from content_factory.workspace_folders folder
  where folder.organization_id = organization_id
    and folder.id = folder_id_value
    and folder.status = 'active'
  for update;
  if folder_row.id is null then
    raise exception using
      errcode = 'P0002', message = 'workspace_folder_not_found';
  end if;
  if content_factory_private.workspace_project_for_folder(
       organization_id, folder_row.id
     ) is distinct from project_id_value then
    raise exception using
      errcode = '42501', message = 'workspace_folder_project_mismatch';
  end if;
  if folder_row.system_role is not null then
    raise exception using
      errcode = '55000', message = 'workspace_system_folder_read_only';
  end if;

  if p_payload ? 'parent_id'
     and nullif(btrim(coalesce(p_payload ->> 'parent_id', '')), '') is not null then
    parent_id_value := content_factory_private.require_uuid(
      p_payload, 'parent_id'
    );
    select folder.*
      into parent_row
    from content_factory.workspace_folders folder
    where folder.organization_id = organization_id
      and folder.id = parent_id_value
      and folder.status = 'active'
    for update;
    if parent_row.id is null then
      raise exception using
        errcode = 'P0002', message = 'workspace_folder_not_found';
    end if;
    if content_factory_private.workspace_project_for_folder(
         organization_id, parent_row.id
       ) is distinct from project_id_value then
      raise exception using
        errcode = '42501', message = 'workspace_folder_project_mismatch';
    end if;
    if parent_row.system_role is not null then
      raise exception using
        errcode = '55000',
        message = 'workspace_system_folder_manual_destination_forbidden';
    end if;
  end if;

  result_value := content_factory_private
    .creator_update_workspace_folder_pre_exact_project_v429(
      p_payload - 'project_id'
    );
  return result_value || jsonb_build_object('project_id', project_id_value);
end;
$$;

create or replace function public.creator_move_workspace_items(
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
  destination_folder_id_value uuid;
  destination_row content_factory.workspace_folders%rowtype;
  items_value jsonb;
  item record;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'idempotency_key',
    'destination_folder_id', 'items'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'workspace_move_payload_invalid';
  end if;
  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id, project_id_value, user_id
  );

  if nullif(
    btrim(coalesce(p_payload ->> 'destination_folder_id', '')), ''
  ) is not null then
    destination_folder_id_value := content_factory_private.require_uuid(
      p_payload, 'destination_folder_id'
    );
  end if;

  items_value := p_payload -> 'items';
  if jsonb_typeof(items_value) <> 'array'
     or jsonb_array_length(items_value) not between 1 and 100
     or exists (
       select 1
       from jsonb_array_elements(items_value) element(value)
       where jsonb_typeof(element.value) <> 'object'
          or element.value - array['type', 'id']::text[] <> '{}'::jsonb
          or coalesce(element.value ->> 'type', '') not in ('media', 'task')
          or coalesce(element.value ->> 'id', '') !~* (
            '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
            || '[0-9a-f]{4}-[0-9a-f]{12}$'
          )
     ) then
    raise exception using
      errcode = '22023', message = 'workspace_items_invalid';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text), hashtext('workspace_structure')
  );
  if destination_folder_id_value is not null then
    select folder.*
      into destination_row
    from content_factory.workspace_folders folder
    where folder.organization_id = organization_id
      and folder.id = destination_folder_id_value
      and folder.status = 'active'
    for update;
    if destination_row.id is null then
      raise exception using
        errcode = 'P0002', message = 'workspace_folder_not_found';
    end if;
    if content_factory_private.workspace_project_for_folder(
         organization_id, destination_row.id
       ) is distinct from project_id_value then
      raise exception using
        errcode = '42501', message = 'workspace_folder_project_mismatch';
    end if;
    if destination_row.system_role is not null then
      raise exception using
        errcode = '55000',
        message = 'workspace_system_folder_manual_destination_forbidden';
    end if;
  end if;

  -- Validate the complete exact-project batch before the preserved command
  -- locks or updates a single location. That command still applies its owner /
  -- assignee rules and duplicate/idempotency checks.
  for item in
    select
      element.value ->> 'type' as entity_type,
      (element.value ->> 'id')::uuid as entity_id
    from jsonb_array_elements(items_value) element(value)
    order by element.value ->> 'type', (element.value ->> 'id')::uuid
  loop
    if item.entity_type = 'media' then
      if not exists (
        select 1
        from content_factory.media_objects media
        where media.organization_id = organization_id
          and media.id = item.entity_id
          and media.project_id = project_id_value
          and media.status <> 'deleted'
      ) then
        raise exception using
          errcode = '42501', message = 'workspace_item_access_denied';
      end if;
      -- A few pre-Files rows can legitimately predate the logical location
      -- trigger. Materialize only the missing exact-project row so the mature
      -- ownership check in the preserved command remains authoritative.
      insert into content_factory.workspace_media_locations (
        organization_id, media_object_id, folder_id, position,
        moved_by, created_at, updated_at
      )
      select
        media.organization_id,
        media.id,
        null,
        greatest(
          0,
          (extract(epoch from media.created_at) * 1000000)::bigint
        ),
        user_id,
        media.created_at,
        now()
      from content_factory.media_objects media
      where media.organization_id = organization_id
        and media.id = item.entity_id
        and media.project_id = project_id_value
        and media.status <> 'deleted'
      on conflict on constraint workspace_media_locations_pkey do nothing;
    else
      if not exists (
        select 1
        from content_factory.creator_tasks task
        where task.organization_id = organization_id
          and task.id = item.entity_id
          and task.project_id = project_id_value
      ) then
        raise exception using
          errcode = '42501', message = 'workspace_item_access_denied';
      end if;
      insert into content_factory.workspace_task_locations (
        organization_id, task_id, folder_id, position,
        moved_by, created_at, updated_at
      )
      select
        task.organization_id,
        task.id,
        null,
        greatest(
          0,
          (extract(epoch from task.created_at) * 1000000)::bigint
        ),
        user_id,
        task.created_at,
        now()
      from content_factory.creator_tasks task
      where task.organization_id = organization_id
        and task.id = item.entity_id
        and task.project_id = project_id_value
      on conflict on constraint workspace_task_locations_pkey do nothing;
    end if;
  end loop;

  result_value := content_factory_private
    .creator_move_workspace_items_pre_exact_project_v429(
      p_payload - 'project_id'
    );
  return result_value || jsonb_build_object('project_id', project_id_value);
end;
$$;

revoke all on function public.creator_create_workspace_folder(jsonb)
  from public, anon;
revoke all on function public.creator_update_workspace_folder(jsonb)
  from public, anon;
revoke all on function public.creator_move_workspace_items(jsonb)
  from public, anon;
grant execute on function public.creator_create_workspace_folder(jsonb)
  to authenticated;
grant execute on function public.creator_update_workspace_folder(jsonb)
  to authenticated;
grant execute on function public.creator_move_workspace_items(jsonb)
  to authenticated;

comment on function public.creator_create_workspace_folder(jsonb) is
  'Creates a custom folder only inside one explicitly authorized project.';
comment on function public.creator_update_workspace_folder(jsonb) is
  'Updates a custom folder only inside one explicitly authorized project.';
comment on function public.creator_move_workspace_items(jsonb) is
  'Moves an exact-project item batch only to root or a custom folder; lifecycle system folders are server-owned.';

notify pgrst, 'reload schema';

commit;
