begin;

create table if not exists content_factory.workspace_trash_items (
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    entity_type text not null
      check (entity_type in ('media', 'task')),
    entity_id uuid not null,
    original_folder_id uuid,
    original_position bigint not null default 0
      check (original_position >= 0),
    original_status text not null
      check (length(original_status) between 2 and 40),
    original_submitted_at timestamptz,
    original_completed_at timestamptz,
    status text not null default 'trashed'
      check (status in ('trashed', 'purged')),
    version bigint not null default 1 check (version >= 1),
    trashed_by uuid not null,
    trashed_at timestamptz not null default now(),
    purged_by uuid,
    purged_at timestamptz,
    metadata jsonb not null default '{}'::jsonb
      check (jsonb_typeof(metadata) = 'object'),
    primary key (organization_id, entity_type, entity_id),
    foreign key (organization_id, trashed_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, purged_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (status = 'trashed' and purged_by is null and purged_at is null)
      or (status = 'purged' and purged_by is not null and purged_at is not null)
    )
);

create index if not exists workspace_trash_active_idx
  on content_factory.workspace_trash_items (
    organization_id, trashed_at desc, entity_type desc, entity_id desc
  )
  where status = 'trashed';

create index if not exists workspace_trash_actor_idx
  on content_factory.workspace_trash_items (
    organization_id, trashed_by, status, trashed_at desc
  );

create table if not exists content_factory.workspace_storage_cleanup_queue (
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    media_object_id uuid not null,
    bucket_id text not null check (bucket_id = 'contentengine-private'),
    object_name text not null check (length(object_name) between 10 and 1000),
    owner_id uuid not null,
    requested_by uuid not null,
    status text not null default 'pending'
      check (status in ('pending', 'removed')),
    requested_at timestamptz not null default now(),
    removed_at timestamptz,
    version bigint not null default 1 check (version >= 1),
    primary key (organization_id, media_object_id),
    unique (bucket_id, object_name),
    foreign key (organization_id, owner_id)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, requested_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (status = 'pending' and removed_at is null)
      or (status = 'removed' and removed_at is not null)
    )
);

create index if not exists workspace_storage_cleanup_pending_idx
  on content_factory.workspace_storage_cleanup_queue (
    organization_id, requested_at, media_object_id
  )
  where status = 'pending';

alter table content_factory.workspace_trash_items enable row level security;
alter table content_factory.workspace_storage_cleanup_queue enable row level security;

revoke all on content_factory.workspace_trash_items
  from public, anon, authenticated;
revoke all on content_factory.workspace_storage_cleanup_queue
  from public, anon, authenticated;
grant all on content_factory.workspace_trash_items to service_role;
grant all on content_factory.workspace_storage_cleanup_queue to service_role;

create or replace function content_factory_private.require_workspace_item_array(
  p_items jsonb,
  p_maximum integer default 100
)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  normalized jsonb;
begin
  if p_maximum < 1 or p_maximum > 500 then
    raise exception using
      errcode = '22023',
      message = 'workspace_items_invalid';
  end if;
  if jsonb_typeof(p_items) <> 'array'
     or jsonb_array_length(p_items) not between 1 and p_maximum
     or exists (
       select 1
       from jsonb_array_elements(p_items) element(value)
       where jsonb_typeof(element.value) <> 'object'
          or element.value - array['type', 'id']::text[] <> '{}'::jsonb
          or coalesce(element.value ->> 'type', '') not in ('media', 'task')
          or coalesce(element.value ->> 'id', '') !~* (
            '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
            || '[0-9a-f]{4}-[0-9a-f]{12}$'
          )
     ) then
    raise exception using
      errcode = '22023',
      message = 'workspace_items_invalid';
  end if;
  if (
    select count(*)
    from (
      select
        element.value ->> 'type' as entity_type,
        lower(element.value ->> 'id') as entity_id
      from jsonb_array_elements(p_items) element(value)
      group by element.value ->> 'type', lower(element.value ->> 'id')
      having count(*) > 1
    ) duplicate_items
  ) > 0 then
    raise exception using
      errcode = '22023',
      message = 'workspace_items_duplicate';
  end if;

  select jsonb_agg(
    jsonb_build_object(
      'type', element.value ->> 'type',
      'id', lower(element.value ->> 'id')
    )
    order by element.ordinality
  )
  into normalized
  from jsonb_array_elements(p_items)
    with ordinality element(value, ordinality);

  return normalized;
end;
$$;

create or replace function public.creator_workspace_trash_browser(
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
  user_id uuid;
  organization_id uuid;
  actor_role text;
  manager_scope boolean;
  purge_scope boolean;
  empty_scope boolean;
  page_size integer := 50;
  search_value text := '';
  entity_types_value text[] := array['media', 'task'];
  cursor_at timestamptz;
  cursor_type text;
  cursor_id uuid;
  items_value jsonb;
  total_count_value integer;
  media_count_value integer;
  task_count_value integer;
  has_more boolean;
  next_cursor_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'page_size', 'search', 'entity_types', 'cursor'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'workspace_trash_browser_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  purge_scope := actor_role = any(array['owner', 'admin', 'producer']);
  empty_scope := actor_role = any(array['owner', 'admin']);

  if p_payload ? 'page_size' then
    if coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'workspace_trash_page_size_invalid';
    end if;
    begin
      page_size := (p_payload ->> 'page_size')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'workspace_trash_page_size_invalid';
    end;
  end if;
  if page_size < 1 or page_size > 100 then
    raise exception using
      errcode = '22023',
      message = 'workspace_trash_page_size_invalid';
  end if;

  search_value := btrim(coalesce(p_payload ->> 'search', ''));
  if length(search_value) > 120 or search_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023',
      message = 'workspace_trash_search_invalid';
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
        message = 'workspace_trash_entity_types_invalid';
    end if;
    select coalesce(array_agg(distinct lower(value)), array[]::text[])
      into entity_types_value
    from jsonb_array_elements_text(p_payload -> 'entity_types') item(value);
    if cardinality(entity_types_value) < 1
       or not (entity_types_value <@ array['media', 'task']::text[]) then
      raise exception using
        errcode = '22023',
        message = 'workspace_trash_entity_types_invalid';
    end if;
  end if;

  if p_payload ? 'cursor' then
    if jsonb_typeof(p_payload -> 'cursor') <> 'object'
       or (p_payload -> 'cursor') - array['at', 'type', 'id']::text[] <> '{}'::jsonb
       or coalesce(p_payload #>> '{cursor,type}', '') not in ('media', 'task')
       or coalesce(p_payload #>> '{cursor,id}', '') !~* (
         '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
         || '[0-9a-f]{4}-[0-9a-f]{12}$'
       ) then
      raise exception using
        errcode = '22023',
        message = 'workspace_trash_cursor_invalid';
    end if;
    begin
      cursor_at := (p_payload #>> '{cursor,at}')::timestamptz;
      cursor_type := p_payload #>> '{cursor,type}';
      cursor_id := (p_payload #>> '{cursor,id}')::uuid;
    exception when invalid_text_representation or datetime_field_overflow then
      raise exception using
        errcode = '22023',
        message = 'workspace_trash_cursor_invalid';
    end;
  end if;

  with visible_trash as (
    select trash.entity_type
    from content_factory.workspace_trash_items trash
    left join content_factory.media_objects media
      on trash.entity_type = 'media'
     and media.organization_id = trash.organization_id
     and media.id = trash.entity_id
    left join content_factory.creator_tasks task
      on trash.entity_type = 'task'
     and task.organization_id = trash.organization_id
     and task.id = trash.entity_id
    where trash.organization_id = organization_id
      and trash.status = 'trashed'
      and trash.entity_type = any(entity_types_value)
      and (
        manager_scope
        or (trash.entity_type = 'media' and media.owner_id = user_id)
        or (trash.entity_type = 'task' and task.assignee_id = user_id)
      )
      and (
        search_value = ''
        or trash.entity_id::text ilike '%' || search_value || '%'
        or coalesce(trash.metadata ->> 'title', '') ilike '%' || search_value || '%'
        or coalesce(trash.metadata ->> 'original_filename', '') ilike '%' || search_value || '%'
        or coalesce(trash.metadata ->> 'sku', '') ilike '%' || search_value || '%'
      )
  )
  select
    count(*)::integer,
    count(*) filter (where entity_type = 'media')::integer,
    count(*) filter (where entity_type = 'task')::integer
  into total_count_value, media_count_value, task_count_value
  from visible_trash;

  with visible_items as (
    select
      trash.trashed_at,
      trash.entity_type,
      trash.entity_id,
      jsonb_build_object(
        'type', 'media',
        'id', trash.entity_id,
        'trash_version', trash.version,
        'trashed_at', trash.trashed_at,
        'trashed_by', trash.trashed_by,
        'original_folder_id', trash.original_folder_id,
        'original_folder_name', folder.name,
        'original_position', trash.original_position,
        'original_status', trash.original_status,
        'owner_id', coalesce(media.owner_id, (trash.metadata ->> 'owner_id')::uuid),
        'product_id', media.product_id,
        'product_name', product.title,
        'sku', coalesce(product.sku, trash.metadata ->> 'sku'),
        'title', coalesce(
          media.metadata ->> 'original_filename',
          trash.metadata ->> 'original_filename',
          trash.metadata ->> 'title',
          'Материал ' || trash.entity_id::text
        ),
        'kind', coalesce(media.metadata ->> 'kind', trash.metadata ->> 'kind'),
        'mime_type', coalesce(media.mime_type, trash.metadata ->> 'mime_type'),
        'size_bytes', coalesce(media.size_bytes, (trash.metadata ->> 'size_bytes')::bigint, 0),
        'bucket_id', coalesce(media.bucket_id, trash.metadata ->> 'bucket_id'),
        'object_name', coalesce(media.object_name, trash.metadata ->> 'object_name'),
        'can_restore', true,
        'can_purge', purge_scope
      ) as item
    from content_factory.workspace_trash_items trash
    left join content_factory.media_objects media
      on media.organization_id = trash.organization_id
     and media.id = trash.entity_id
    left join content_factory.products product
      on product.organization_id = media.organization_id
     and product.id = media.product_id
    left join content_factory.workspace_folders folder
      on folder.organization_id = trash.organization_id
     and folder.id = trash.original_folder_id
    where trash.organization_id = organization_id
      and trash.status = 'trashed'
      and trash.entity_type = 'media'
      and 'media' = any(entity_types_value)
      and (manager_scope or media.owner_id = user_id)
      and (
        search_value = ''
        or trash.entity_id::text ilike '%' || search_value || '%'
        or coalesce(media.object_name, '') ilike '%' || search_value || '%'
        or coalesce(media.metadata ->> 'original_filename', '') ilike '%' || search_value || '%'
        or coalesce(media.metadata ->> 'kind', '') ilike '%' || search_value || '%'
        or coalesce(product.sku, '') ilike '%' || search_value || '%'
        or coalesce(product.title, '') ilike '%' || search_value || '%'
        or coalesce(trash.metadata ->> 'title', '') ilike '%' || search_value || '%'
      )
    union all
    select
      trash.trashed_at,
      trash.entity_type,
      trash.entity_id,
      jsonb_build_object(
        'type', 'task',
        'id', trash.entity_id,
        'trash_version', trash.version,
        'trashed_at', trash.trashed_at,
        'trashed_by', trash.trashed_by,
        'original_folder_id', trash.original_folder_id,
        'original_folder_name', folder.name,
        'original_position', trash.original_position,
        'original_status', trash.original_status,
        'assignee_id', coalesce(task.assignee_id, (trash.metadata ->> 'assignee_id')::uuid),
        'product_id', task.product_id,
        'product_name', product.title,
        'sku', coalesce(product.sku, trash.metadata ->> 'sku'),
        'title', coalesce(task.title, trash.metadata ->> 'title', 'Задача ' || trash.entity_id::text),
        'instructions', coalesce(task.instructions, trash.metadata ->> 'instructions'),
        'task_type', coalesce(task.task_type, trash.metadata ->> 'task_type'),
        'priority', task.priority,
        'can_restore', true,
        'can_purge', purge_scope
      ) as item
    from content_factory.workspace_trash_items trash
    left join content_factory.creator_tasks task
      on task.organization_id = trash.organization_id
     and task.id = trash.entity_id
    left join content_factory.products product
      on product.organization_id = task.organization_id
     and product.id = task.product_id
    left join content_factory.workspace_folders folder
      on folder.organization_id = trash.organization_id
     and folder.id = trash.original_folder_id
    where trash.organization_id = organization_id
      and trash.status = 'trashed'
      and trash.entity_type = 'task'
      and 'task' = any(entity_types_value)
      and (manager_scope or task.assignee_id = user_id)
      and (
        search_value = ''
        or trash.entity_id::text ilike '%' || search_value || '%'
        or coalesce(task.title, '') ilike '%' || search_value || '%'
        or coalesce(task.instructions, '') ilike '%' || search_value || '%'
        or coalesce(product.sku, '') ilike '%' || search_value || '%'
        or coalesce(product.title, '') ilike '%' || search_value || '%'
        or coalesce(trash.metadata ->> 'title', '') ilike '%' || search_value || '%'
      )
  ),
  candidates as materialized (
    select visible.*
    from visible_items visible
    where cursor_at is null
       or (visible.trashed_at, visible.entity_type, visible.entity_id)
          < (cursor_at, cursor_type, cursor_id)
    order by visible.trashed_at desc, visible.entity_type desc, visible.entity_id desc
    limit page_size + 1
  ),
  page as (
    select candidate.*
    from candidates candidate
    order by candidate.trashed_at desc, candidate.entity_type desc, candidate.entity_id desc
    limit page_size
  ),
  last_page_item as (
    select jsonb_build_object(
      'at', page.trashed_at,
      'type', page.entity_type,
      'id', page.entity_id
    ) as cursor_value
    from page
    order by page.trashed_at, page.entity_type, page.entity_id
    limit 1
  )
  select
    coalesce(
      (
        select jsonb_agg(
          page.item || jsonb_build_object(
            '_cursor', jsonb_build_object(
              'at', page.trashed_at,
              'type', page.entity_type,
              'id', page.entity_id
            )
          )
          order by page.trashed_at desc, page.entity_type desc, page.entity_id desc
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
    'items', items_value,
    'summary', jsonb_build_object(
      'total', coalesce(total_count_value, 0),
      'media', coalesce(media_count_value, 0),
      'tasks', coalesce(task_count_value, 0)
    ),
    'capabilities', jsonb_build_object(
      'trash_items', true,
      'restore_items', true,
      'purge_items', purge_scope,
      'empty_trash', empty_scope
    ),
    '_meta', jsonb_build_object(
      'page_size', page_size,
      'cap', 100,
      'has_more', coalesce(has_more, false),
      'next_cursor', next_cursor_value,
      'cursor_mode', 'trashed_at_type_id'
    )
  );
end;
$$;

create or replace function public.creator_trash_workspace_items(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  manager_scope boolean;
  idempotency_key text;
  normalized_items jsonb;
  item record;
  existing_trash content_factory.workspace_trash_items%rowtype;
  entity_row record;
  trashed_items jsonb := '[]'::jsonb;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'idempotency_key', 'items']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'workspace_trash_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(array['owner', 'admin', 'producer', 'reviewer']);
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  normalized_items := content_factory_private.require_workspace_item_array(
    p_payload -> 'items',
    100
  );
  request_payload := jsonb_build_object('items', normalized_items);
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_trash_workspace_items',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('workspace_trash')
  );

  for item in
    select
      element.value ->> 'type' as entity_type,
      (element.value ->> 'id')::uuid as entity_id,
      element.ordinality
    from jsonb_array_elements(normalized_items)
      with ordinality element(value, ordinality)
    order by element.value ->> 'type', (element.value ->> 'id')::uuid
  loop
    existing_trash := null;
    select trash.* into existing_trash
    from content_factory.workspace_trash_items trash
    where trash.organization_id = organization_id
      and trash.entity_type = item.entity_type
      and trash.entity_id = item.entity_id
    for update;

    if existing_trash.entity_id is not null then
      if existing_trash.status = 'purged' then
        raise exception using
          errcode = '55000',
          message = 'workspace_item_purged';
      end if;
      trashed_items := trashed_items || jsonb_build_array(jsonb_build_object(
        'type', item.entity_type,
        'id', item.entity_id,
        'already_trashed', true
      ));
      continue;
    end if;

    entity_row := null;
    if item.entity_type = 'media' then
      select
        location.folder_id,
        location.position,
        media.owner_id,
        media.product_id,
        media.status,
        media.bucket_id,
        media.object_name,
        media.mime_type,
        media.size_bytes,
        media.metadata,
        product.sku,
        product.title as product_name
      into entity_row
      from content_factory.workspace_media_locations location
      join content_factory.media_objects media
        on media.organization_id = location.organization_id
       and media.id = location.media_object_id
      left join content_factory.products product
        on product.organization_id = media.organization_id
       and product.id = media.product_id
      where location.organization_id = organization_id
        and location.media_object_id = item.entity_id
        and media.status <> 'deleted'
        and (manager_scope or media.owner_id = user_id)
      for update of location, media;

      if not found then
        raise exception using
          errcode = '42501',
          message = 'workspace_item_access_denied';
      end if;
      if entity_row.status = 'uploading' then
        raise exception using
          errcode = '55000',
          message = 'workspace_item_busy';
      end if;

      insert into content_factory.workspace_trash_items (
        organization_id, entity_type, entity_id,
        original_folder_id, original_position, original_status,
        trashed_by, metadata
      ) values (
        organization_id,
        'media',
        item.entity_id,
        entity_row.folder_id,
        entity_row.position,
        entity_row.status,
        user_id,
        jsonb_build_object(
          'owner_id', entity_row.owner_id,
          'product_id', entity_row.product_id,
          'sku', entity_row.sku,
          'product_name', entity_row.product_name,
          'title', coalesce(
            entity_row.metadata ->> 'original_filename',
            'Материал ' || item.entity_id::text
          ),
          'original_filename', entity_row.metadata ->> 'original_filename',
          'kind', entity_row.metadata ->> 'kind',
          'bucket_id', entity_row.bucket_id,
          'object_name', entity_row.object_name,
          'mime_type', entity_row.mime_type,
          'size_bytes', entity_row.size_bytes
        )
      );

      delete from content_factory.workspace_media_locations location
      where location.organization_id = organization_id
        and location.media_object_id = item.entity_id;

      update content_factory.media_objects media
      set status = 'deleted',
          updated_at = now()
      where media.organization_id = organization_id
        and media.id = item.entity_id;
    else
      select
        location.folder_id,
        location.position,
        task.assignee_id,
        task.product_id,
        task.status,
        task.submitted_at,
        task.completed_at,
        task.task_type,
        task.title,
        task.instructions,
        task.priority,
        product.sku,
        product.title as product_name
      into entity_row
      from content_factory.workspace_task_locations location
      join content_factory.creator_tasks task
        on task.organization_id = location.organization_id
       and task.id = location.task_id
      left join content_factory.products product
        on product.organization_id = task.organization_id
       and product.id = task.product_id
      where location.organization_id = organization_id
        and location.task_id = item.entity_id
        and (manager_scope or task.assignee_id = user_id)
      for update of location, task;

      if not found then
        raise exception using
          errcode = '42501',
          message = 'workspace_item_access_denied';
      end if;
      if not manager_scope and entity_row.status in ('submitted', 'review', 'done') then
        raise exception using
          errcode = '42501',
          message = 'workspace_item_access_denied';
      end if;

      insert into content_factory.workspace_trash_items (
        organization_id, entity_type, entity_id,
        original_folder_id, original_position, original_status,
        original_submitted_at, original_completed_at,
        trashed_by, metadata
      ) values (
        organization_id,
        'task',
        item.entity_id,
        entity_row.folder_id,
        entity_row.position,
        entity_row.status,
        entity_row.submitted_at,
        entity_row.completed_at,
        user_id,
        jsonb_build_object(
          'assignee_id', entity_row.assignee_id,
          'product_id', entity_row.product_id,
          'sku', entity_row.sku,
          'product_name', entity_row.product_name,
          'title', entity_row.title,
          'instructions', entity_row.instructions,
          'task_type', entity_row.task_type,
          'priority', entity_row.priority
        )
      );

      delete from content_factory.workspace_task_locations location
      where location.organization_id = organization_id
        and location.task_id = item.entity_id;

      update content_factory.creator_tasks task
      set status = 'cancelled',
          updated_at = now()
      where task.organization_id = organization_id
        and task.id = item.entity_id;
    end if;

    trashed_items := trashed_items || jsonb_build_array(jsonb_build_object(
      'type', item.entity_type,
      'id', item.entity_id,
      'already_trashed', false
    ));
  end loop;

  result := jsonb_build_object(
    'ok', true,
    'trashed_count', jsonb_array_length(trashed_items),
    'items', trashed_items
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'workspace_items_trashed',
    'workspace_trash',
    organization_id::text,
    jsonb_build_object(
      'item_count', jsonb_array_length(trashed_items),
      'entity_types', (
        select coalesce(jsonb_agg(distinct element.value ->> 'type'), '[]'::jsonb)
        from jsonb_array_elements(normalized_items) element(value)
      )
    ),
    'workspace_items_trash:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_trash_workspace_items',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_restore_workspace_items(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  manager_scope boolean;
  idempotency_key text;
  normalized_items jsonb;
  item record;
  trash_row content_factory.workspace_trash_items%rowtype;
  destination_folder_id_value uuid;
  entity_owner_id uuid;
  restored_items jsonb := '[]'::jsonb;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'idempotency_key', 'items']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'workspace_restore_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(array['owner', 'admin', 'producer', 'reviewer']);
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  normalized_items := content_factory_private.require_workspace_item_array(
    p_payload -> 'items',
    100
  );
  request_payload := jsonb_build_object('items', normalized_items);
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_restore_workspace_items',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('workspace_trash')
  );

  for item in
    select
      element.value ->> 'type' as entity_type,
      (element.value ->> 'id')::uuid as entity_id,
      element.ordinality
    from jsonb_array_elements(normalized_items)
      with ordinality element(value, ordinality)
    order by element.value ->> 'type', (element.value ->> 'id')::uuid
  loop
    trash_row := null;
    select trash.* into trash_row
    from content_factory.workspace_trash_items trash
    where trash.organization_id = organization_id
      and trash.entity_type = item.entity_type
      and trash.entity_id = item.entity_id
    for update;

    if trash_row.entity_id is null then
      raise exception using
        errcode = 'P0002',
        message = 'workspace_trash_item_not_found';
    end if;
    if trash_row.status <> 'trashed' then
      raise exception using
        errcode = '55000',
        message = 'workspace_item_purged';
    end if;

    destination_folder_id_value := null;
    if trash_row.original_folder_id is not null and exists (
      select 1
      from content_factory.workspace_folders folder
      where folder.organization_id = organization_id
        and folder.id = trash_row.original_folder_id
        and folder.status = 'active'
    ) then
      destination_folder_id_value := trash_row.original_folder_id;
    end if;

    if item.entity_type = 'media' then
      select media.owner_id into entity_owner_id
      from content_factory.media_objects media
      where media.organization_id = organization_id
        and media.id = item.entity_id
      for update;
      if not found or not (manager_scope or entity_owner_id = user_id) then
        raise exception using
          errcode = '42501',
          message = 'workspace_item_access_denied';
      end if;
      if trash_row.original_status not in ('ready', 'archived', 'failed') then
        raise exception using
          errcode = '55000',
          message = 'workspace_restore_status_invalid';
      end if;

      update content_factory.media_objects media
      set status = trash_row.original_status,
          updated_at = now()
      where media.organization_id = organization_id
        and media.id = item.entity_id;

      insert into content_factory.workspace_media_locations (
        organization_id, media_object_id, folder_id,
        position, moved_by
      ) values (
        organization_id,
        item.entity_id,
        destination_folder_id_value,
        greatest(trash_row.original_position, 0),
        user_id
      )
      on conflict (organization_id, media_object_id)
      do update set
        folder_id = excluded.folder_id,
        position = excluded.position,
        moved_by = excluded.moved_by;
    else
      select task.assignee_id into entity_owner_id
      from content_factory.creator_tasks task
      where task.organization_id = organization_id
        and task.id = item.entity_id
      for update;
      if not found or not (manager_scope or entity_owner_id = user_id) then
        raise exception using
          errcode = '42501',
          message = 'workspace_item_access_denied';
      end if;
      if trash_row.original_status not in (
        'todo', 'in_progress', 'submitted', 'review',
        'done', 'blocked', 'cancelled'
      ) then
        raise exception using
          errcode = '55000',
          message = 'workspace_restore_status_invalid';
      end if;

      update content_factory.creator_tasks task
      set status = trash_row.original_status,
          submitted_at = trash_row.original_submitted_at,
          completed_at = trash_row.original_completed_at,
          updated_at = now()
      where task.organization_id = organization_id
        and task.id = item.entity_id;

      insert into content_factory.workspace_task_locations (
        organization_id, task_id, folder_id,
        position, moved_by
      ) values (
        organization_id,
        item.entity_id,
        destination_folder_id_value,
        greatest(trash_row.original_position, 0),
        user_id
      )
      on conflict (organization_id, task_id)
      do update set
        folder_id = excluded.folder_id,
        position = excluded.position,
        moved_by = excluded.moved_by;
    end if;

    delete from content_factory.workspace_trash_items trash
    where trash.organization_id = organization_id
      and trash.entity_type = item.entity_type
      and trash.entity_id = item.entity_id;

    restored_items := restored_items || jsonb_build_array(jsonb_build_object(
      'type', item.entity_type,
      'id', item.entity_id,
      'folder_id', destination_folder_id_value
    ));
  end loop;

  result := jsonb_build_object(
    'ok', true,
    'restored_count', jsonb_array_length(restored_items),
    'items', restored_items
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'workspace_items_restored',
    'workspace_trash',
    organization_id::text,
    jsonb_build_object('item_count', jsonb_array_length(restored_items)),
    'workspace_items_restore:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_restore_workspace_items',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_purge_workspace_items(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  empty_scope boolean;
  idempotency_key text;
  purge_all boolean := false;
  normalized_items jsonb := '[]'::jsonb;
  item record;
  trash_row content_factory.workspace_trash_items%rowtype;
  media_row record;
  purged_items jsonb := '[]'::jsonb;
  cleanup_items jsonb := '[]'::jsonb;
  remaining_count_value integer;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'idempotency_key', 'items', 'all']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'workspace_purge_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer']
  );
  empty_scope := actor_role = any(array['owner', 'admin']);
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );

  if p_payload ? 'all' then
    if jsonb_typeof(p_payload -> 'all') <> 'boolean' then
      raise exception using
        errcode = '22023',
        message = 'workspace_purge_payload_invalid';
    end if;
    purge_all := (p_payload ->> 'all')::boolean;
  end if;
  if purge_all and p_payload ? 'items' then
    raise exception using
      errcode = '22023',
      message = 'workspace_purge_payload_invalid';
  end if;
  if purge_all and not empty_scope then
    raise exception using
      errcode = '42501',
      message = 'workspace_empty_trash_access_denied';
  end if;
  if not purge_all then
    normalized_items := content_factory_private.require_workspace_item_array(
      p_payload -> 'items',
      100
    );
  else
    select coalesce(jsonb_agg(jsonb_build_object(
      'type', target.entity_type,
      'id', target.entity_id
    ) order by target.trashed_at, target.entity_type, target.entity_id), '[]'::jsonb)
    into normalized_items
    from (
      select trash.entity_type, trash.entity_id, trash.trashed_at
      from content_factory.workspace_trash_items trash
      where trash.organization_id = organization_id
        and trash.status = 'trashed'
      order by trash.trashed_at, trash.entity_type, trash.entity_id
      limit 500
    ) target;
  end if;

  request_payload := jsonb_build_object(
    'all', purge_all,
    'items', normalized_items
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_purge_workspace_items',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('workspace_trash')
  );

  for item in
    select
      element.value ->> 'type' as entity_type,
      (element.value ->> 'id')::uuid as entity_id,
      element.ordinality
    from jsonb_array_elements(normalized_items)
      with ordinality element(value, ordinality)
    order by element.value ->> 'type', (element.value ->> 'id')::uuid
  loop
    trash_row := null;
    select trash.* into trash_row
    from content_factory.workspace_trash_items trash
    where trash.organization_id = organization_id
      and trash.entity_type = item.entity_type
      and trash.entity_id = item.entity_id
    for update;

    if trash_row.entity_id is null or trash_row.status <> 'trashed' then
      continue;
    end if;

    if item.entity_type = 'media' then
      media_row := null;
      select
        media.id,
        media.owner_id,
        media.bucket_id,
        media.object_name
      into media_row
      from content_factory.media_objects media
      where media.organization_id = organization_id
        and media.id = item.entity_id
      for update;

      if media_row.id is not null then
        update content_factory.media_objects media
        set status = 'deleted',
            updated_at = now()
        where media.organization_id = organization_id
          and media.id = item.entity_id;

        insert into content_factory.workspace_storage_cleanup_queue (
          organization_id, media_object_id, bucket_id,
          object_name, owner_id, requested_by,
          status, requested_at, removed_at
        ) values (
          organization_id,
          item.entity_id,
          media_row.bucket_id,
          media_row.object_name,
          media_row.owner_id,
          user_id,
          'pending',
          now(),
          null
        )
        on conflict (organization_id, media_object_id)
        do update set
          bucket_id = excluded.bucket_id,
          object_name = excluded.object_name,
          owner_id = excluded.owner_id,
          requested_by = excluded.requested_by,
          status = 'pending',
          requested_at = now(),
          removed_at = null,
          version = content_factory.workspace_storage_cleanup_queue.version + 1;

        cleanup_items := cleanup_items || jsonb_build_array(jsonb_build_object(
          'media_id', item.entity_id,
          'bucket_id', media_row.bucket_id,
          'object_name', media_row.object_name
        ));
      end if;
    else
      update content_factory.creator_tasks task
      set status = 'cancelled',
          updated_at = now()
      where task.organization_id = organization_id
        and task.id = item.entity_id;
    end if;

    update content_factory.workspace_trash_items trash
    set status = 'purged',
        purged_by = user_id,
        purged_at = now(),
        version = trash.version + 1
    where trash.organization_id = organization_id
      and trash.entity_type = item.entity_type
      and trash.entity_id = item.entity_id;

    purged_items := purged_items || jsonb_build_array(jsonb_build_object(
      'type', item.entity_type,
      'id', item.entity_id
    ));
  end loop;

  select count(*)::integer
    into remaining_count_value
  from content_factory.workspace_trash_items trash
  where trash.organization_id = organization_id
    and trash.status = 'trashed';

  result := jsonb_build_object(
    'ok', true,
    'purged_count', jsonb_array_length(purged_items),
    'items', purged_items,
    'storage_cleanup', cleanup_items,
    'remaining_count', coalesce(remaining_count_value, 0)
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    case when purge_all then 'workspace_trash_emptied' else 'workspace_items_purged' end,
    'workspace_trash',
    organization_id::text,
    jsonb_build_object(
      'item_count', jsonb_array_length(purged_items),
      'storage_cleanup_count', jsonb_array_length(cleanup_items),
      'remaining_count', coalesce(remaining_count_value, 0)
    ),
    'workspace_items_purge:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_purge_workspace_items',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_complete_workspace_storage_cleanup(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  manager_scope boolean;
  idempotency_key text;
  media_ids_value jsonb;
  normalized_ids uuid[];
  completed_count_value integer;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'idempotency_key', 'media_ids']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'workspace_storage_cleanup_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(array['owner', 'admin', 'producer']);
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  media_ids_value := p_payload -> 'media_ids';
  if jsonb_typeof(media_ids_value) <> 'array'
     or jsonb_array_length(media_ids_value) not between 1 and 100
     or exists (
       select 1
       from jsonb_array_elements(media_ids_value) item(value)
       where jsonb_typeof(item.value) <> 'string'
          or trim(both '"' from item.value::text) !~* (
            '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
            || '[0-9a-f]{4}-[0-9a-f]{12}$'
          )
     ) then
    raise exception using
      errcode = '22023',
      message = 'workspace_storage_cleanup_media_ids_invalid';
  end if;

  select array_agg(distinct value::uuid order by value::uuid)
    into normalized_ids
  from jsonb_array_elements_text(media_ids_value) item(value);

  request_payload := jsonb_build_object('media_ids', to_jsonb(normalized_ids));
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_complete_workspace_storage_cleanup',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  with completed as (
    update content_factory.workspace_storage_cleanup_queue queue
    set status = 'removed',
        removed_at = now(),
        version = queue.version + 1
    where queue.organization_id = organization_id
      and queue.media_object_id = any(normalized_ids)
      and queue.status = 'pending'
      and (manager_scope or queue.owner_id = user_id)
    returning queue.media_object_id
  )
  select count(*)::integer into completed_count_value from completed;

  update content_factory.media_objects media
  set metadata = media.metadata || jsonb_build_object(
        'storage_removed_at', now(),
        'storage_removed_by', user_id
      ),
      updated_at = now()
  where media.organization_id = organization_id
    and media.id = any(normalized_ids)
    and media.status = 'deleted';

  result := jsonb_build_object(
    'ok', true,
    'completed_count', coalesce(completed_count_value, 0),
    'media_ids', to_jsonb(normalized_ids)
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_complete_workspace_storage_cleanup',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function content_factory.storage_trash_delete_allowed(
  p_bucket_id text,
  p_object_name text
)
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select auth.uid() is not null
    and p_bucket_id = 'contentengine-private'
    and exists (
      select 1
      from content_factory.workspace_storage_cleanup_queue queue
      join content_factory.memberships membership
        on membership.organization_id = queue.organization_id
       and membership.profile_id = auth.uid()
       and membership.status = 'active'
      join content_factory.organizations organization
        on organization.id = queue.organization_id
       and organization.status = 'active'
      join content_factory.media_objects media
        on media.organization_id = queue.organization_id
       and media.id = queue.media_object_id
       and media.status = 'deleted'
      where queue.bucket_id = p_bucket_id
        and queue.object_name = p_object_name
        and queue.status = 'pending'
        and (
          queue.owner_id = auth.uid()
          or membership.role in ('owner', 'admin', 'producer')
        )
        and content_factory.storage_access_allowed(
          queue.organization_id::text,
          queue.owner_id::text,
          true
        )
    )
$$;

revoke all on function content_factory.storage_trash_delete_allowed(text, text)
  from public, anon;
grant execute on function content_factory.storage_trash_delete_allowed(text, text)
  to authenticated;

drop policy if exists contentengine_private_delete on storage.objects;
create policy contentengine_private_delete
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'contentengine-private'
  and (
    (
      content_factory.storage_access_allowed(
        split_part(storage.objects.name, '/', 1),
        split_part(storage.objects.name, '/', 2),
        false
      )
      and content_factory.storage_object_is_unregistered(
        storage.objects.bucket_id,
        storage.objects.name
      )
    )
    or content_factory.storage_trash_delete_allowed(
      storage.objects.bucket_id,
      storage.objects.name
    )
  )
);

revoke all on function public.creator_workspace_trash_browser(jsonb)
  from public, anon;
revoke all on function public.creator_trash_workspace_items(jsonb)
  from public, anon;
revoke all on function public.creator_restore_workspace_items(jsonb)
  from public, anon;
revoke all on function public.creator_purge_workspace_items(jsonb)
  from public, anon;
revoke all on function public.creator_complete_workspace_storage_cleanup(jsonb)
  from public, anon;

grant execute on function public.creator_workspace_trash_browser(jsonb)
  to authenticated;
grant execute on function public.creator_trash_workspace_items(jsonb)
  to authenticated;
grant execute on function public.creator_restore_workspace_items(jsonb)
  to authenticated;
grant execute on function public.creator_purge_workspace_items(jsonb)
  to authenticated;
grant execute on function public.creator_complete_workspace_storage_cleanup(jsonb)
  to authenticated;

revoke all on all functions in schema content_factory_private
  from public, anon, authenticated;
grant execute on all functions in schema content_factory_private
  to service_role;

commit;
