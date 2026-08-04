begin;

-- The v4.7 compatibility readers fetched organization-wide pages and filtered
-- them after the fact.  A new or sparsely populated project therefore had to
-- walk the organization's whole history before it could return an empty page.
-- Read the Finder and upload catalog from the canonical project_id indexes
-- instead.  This also keeps read-only navigation off current_profile_id(),
-- whose profile upsert needlessly serialized concurrent workspace reads.

create index if not exists media_objects_project_created_page_idx
  on content_factory.media_objects (
    organization_id, project_id, created_at desc, id desc
  )
  where project_id is not null and status <> 'deleted';

create index if not exists media_objects_project_owner_created_page_idx
  on content_factory.media_objects (
    organization_id, project_id, owner_id, created_at desc, id desc
  )
  where project_id is not null and status <> 'deleted';

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
  manager_scope boolean;
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
      errcode = '22023',
      message = 'workspace_browser_payload_invalid';
  end if;
  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;

  user_id := auth.uid();
  if user_id is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;
  if not exists (
    select 1
    from auth.users auth_user
    where auth_user.id = user_id
      and auth_user.email is not null
  ) then
    raise exception using errcode = '42501', message = 'verified_email_required';
  end if;
  select profile.status
    into profile_status
  from content_factory.profiles profile
  where profile.id = user_id;
  if profile_status is not null and profile_status <> 'active' then
    raise exception using errcode = '42501', message = 'profile_not_active';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  folder_manage_scope := actor_role = any(
    array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id,
    project_id_value
  );

  if nullif(btrim(coalesce(p_payload ->> 'folder_id', '')), '') is not null then
    folder_id_value := content_factory_private.require_uuid(
      p_payload,
      'folder_id'
    );
    if not exists (
      select 1
      from content_factory.workspace_folders folder
      where folder.organization_id = organization_id
        and folder.id = folder_id_value
        and folder.status = 'active'
    ) then
      raise exception using
        errcode = 'P0002',
        message = 'workspace_folder_not_found';
    end if;
    if content_factory_private.workspace_project_for_folder(
         organization_id,
         folder_id_value
       ) is distinct from project_id_value then
      raise exception using
        errcode = '42501',
        message = 'workspace_folder_project_mismatch';
    end if;
  end if;

  if p_payload ? 'page_size' then
    if coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'workspace_page_size_invalid';
    end if;
    begin
      page_size := (p_payload ->> 'page_size')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'workspace_page_size_invalid';
    end;
  end if;
  if page_size < 1 or page_size > 100 then
    raise exception using
      errcode = '22023',
      message = 'workspace_page_size_invalid';
  end if;

  search_value := btrim(coalesce(p_payload ->> 'search', ''));
  if length(search_value) > 120 or search_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023',
      message = 'workspace_search_invalid';
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
        errcode = '22023',
        message = 'workspace_entity_types_invalid';
    end if;
    select coalesce(array_agg(distinct lower(value)), array[]::text[])
      into entity_types_value
    from jsonb_array_elements_text(p_payload -> 'entity_types') item(value);
    if cardinality(entity_types_value) < 1
       or not (entity_types_value <@ array['media', 'task']::text[]) then
      raise exception using
        errcode = '22023',
        message = 'workspace_entity_types_invalid';
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
        errcode = '22023',
        message = 'workspace_media_kinds_invalid';
    end if;
    select coalesce(array_agg(distinct lower(value)), array[]::text[])
      into media_kinds_value
    from jsonb_array_elements_text(p_payload -> 'media_kinds') item(value);
    if not (
      media_kinds_value <@ array[
        'product_photo', 'packshot', 'creator_reference',
        'source_video', 'generated_video'
      ]::text[]
    ) then
      raise exception using
        errcode = '22023',
        message = 'workspace_media_kinds_invalid';
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
        errcode = '22023',
        message = 'workspace_task_statuses_invalid';
    end if;
    select coalesce(array_agg(distinct lower(value)), array[]::text[])
      into task_statuses_value
    from jsonb_array_elements_text(p_payload -> 'task_statuses') item(value);
    if not (
      task_statuses_value <@ array[
        'todo', 'in_progress', 'submitted', 'review',
        'done', 'blocked', 'cancelled'
      ]::text[]
    ) then
      raise exception using
        errcode = '22023',
        message = 'workspace_task_statuses_invalid';
    end if;
  end if;

  if p_payload ? 'cursor' then
    if jsonb_typeof(p_payload -> 'cursor') <> 'object'
       or (p_payload -> 'cursor') - array[
         'position', 'type', 'id'
       ]::text[] <> '{}'::jsonb
       or coalesce(p_payload #>> '{cursor,position}', '') !~ '^[0-9]+$'
       or coalesce(p_payload #>> '{cursor,type}', '') not in ('media', 'task')
       or coalesce(p_payload #>> '{cursor,id}', '') !~* (
         '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
         || '[0-9a-f]{4}-[0-9a-f]{12}$'
       ) then
      raise exception using
        errcode = '22023',
        message = 'workspace_cursor_invalid';
    end if;
    begin
      cursor_position := (p_payload #>> '{cursor,position}')::bigint;
      cursor_type := p_payload #>> '{cursor,type}';
      cursor_id := (p_payload #>> '{cursor,id}')::uuid;
    exception
      when invalid_text_representation or numeric_value_out_of_range then
        raise exception using
          errcode = '22023',
          message = 'workspace_cursor_invalid';
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
      and (manager_scope or media.owner_id = user_id)
    group by location.folder_id
  ),
  task_counts as (
    select location.folder_id, count(*)::integer as item_count
    from content_factory.creator_tasks task
    join content_factory.workspace_task_locations location
      on location.organization_id = task.organization_id
     and location.task_id = task.id
    where task.organization_id = organization_id
      and task.project_id = project_id_value
      and (manager_scope or task.assignee_id = user_id)
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
      and (
        folder_id_value is null
        or location.folder_id is not distinct from folder_id_value
      )
      and media.status <> 'deleted'
      and (manager_scope or media.owner_id = user_id)
      and 'media' = any(entity_types_value)
      and (
        cardinality(media_kinds_value) = 0
        or coalesce(media.metadata ->> 'kind', '') = any(media_kinds_value)
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
      and (
        folder_id_value is null
        or location.folder_id is not distinct from folder_id_value
      )
      and (manager_scope or task.assignee_id = user_id)
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
  ),
  candidates as materialized (
    select visible.*
    from visible_items visible
    where cursor_position is null
       or (visible.position, visible.entity_type, visible.entity_id)
          < (cursor_position, cursor_type, cursor_id)
    order by visible.position desc, visible.entity_type desc,
      visible.entity_id desc
    limit page_size + 1
  ),
  page as (
    select candidate.*
    from candidates candidate
    order by candidate.position desc, candidate.entity_type desc,
      candidate.entity_id desc
    limit page_size
  ),
  last_page_item as (
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
    coalesce(
      (
        select jsonb_agg(
          page.item || jsonb_build_object(
            '_cursor',
            jsonb_build_object(
              'position', page.position,
              'type', page.entity_type,
              'id', page.entity_id
            )
          )
          order by page.position desc, page.entity_type desc,
            page.entity_id desc
        )
        from page
      ),
      '[]'::jsonb
    ),
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
      'move_items', true
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

-- Preserve the complete v4.7 multiplexer for every non-media section.  The
-- media branch below is equivalent to its audited legacy query, with the
-- canonical project predicate applied before LIMIT instead of after up to
-- twenty organization-wide pages.
do $preserve_workspace_section_before_project_reader_recovery$
begin
  if to_regprocedure(
    'content_factory_private.creator_workspace_section_pre_project_reader_recovery_v416(jsonb)'
  ) is null then
    alter function public.creator_workspace_section(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_workspace_section(jsonb)
      rename to creator_workspace_section_pre_project_reader_recovery_v416;
  end if;
end;
$preserve_workspace_section_before_project_reader_recovery$;

revoke all on function
  content_factory_private.creator_workspace_section_pre_project_reader_recovery_v416(
    jsonb
  ) from public, anon, authenticated;

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
  actor_role text;
  team_scope boolean;
  page_size_value integer := 50;
  media_cursor_at timestamptz;
  media_cursor_id uuid;
  media_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  section_value := lower(btrim(coalesce(p_payload ->> 'section', '')));
  if section_value <> 'media' or not (p_payload ? 'project_id') then
    return content_factory_private.creator_workspace_section_pre_project_reader_recovery_v416(
      p_payload
    );
  end if;

  user_id := auth.uid();
  if user_id is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;
  if not exists (
    select 1
    from auth.users auth_user
    where auth_user.id = user_id
      and auth_user.email is not null
  ) then
    raise exception using errcode = '42501', message = 'verified_email_required';
  end if;
  select profile.status
    into profile_status
  from content_factory.profiles profile
  where profile.id = user_id;
  if profile_status is not null and profile_status <> 'active' then
    raise exception using errcode = '42501', message = 'profile_not_active';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  team_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id,
    project_id_value
  );

  if p_payload ? 'page_size' then
    if coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'workspace_page_size_invalid';
    end if;
    begin
      page_size_value := (p_payload ->> 'page_size')::integer;
    exception
      when invalid_text_representation or numeric_value_out_of_range then
        raise exception using
          errcode = '22023',
          message = 'workspace_page_size_invalid';
    end;
    if page_size_value not between 1 and 100 then
      raise exception using
        errcode = '22023',
        message = 'workspace_page_size_invalid';
    end if;
  end if;
  if p_payload ? 'cursor' and jsonb_typeof(p_payload -> 'cursor') <> 'object' then
    raise exception using errcode = '22023', message = 'workspace_cursor_invalid';
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
    'object_key', media.object_name,
    'original_filename', media.metadata ->> 'original_filename',
    'kind', media.metadata ->> 'kind',
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
      and (team_scope or candidate.owner_id = user_id)
      and (
        media_cursor_at is null
        or (candidate.created_at, candidate.id) <
          (media_cursor_at, media_cursor_id)
      )
    order by candidate.created_at desc, candidate.id desc
    limit page_size_value
  ) media;

  return jsonb_build_object(
    'media', media_value,
    'project_id', project_id_value,
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

comment on function public.creator_workspace_browser(jsonb) is
  'Reads Finder folders and objects directly inside one authorized project.';
comment on function public.creator_workspace_section(jsonb) is
  'Uses a direct project-indexed media reader and preserves the v4.7 multiplexer for other sections.';

notify pgrst, 'reload schema';

commit;
