begin;

create table if not exists content_factory.workspace_folders (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    parent_id uuid,
    name text not null check (
      length(btrim(name)) between 1 and 120
      and name !~ '[[:cntrl:]]'
    ),
    color_token text not null default 'emerald'
      check (color_token in (
        'emerald', 'gold', 'rose', 'blue', 'violet', 'slate'
      )),
    status text not null default 'active'
      check (status in ('active', 'archived')),
    position bigint not null default 0 check (position >= 0),
    version bigint not null default 1 check (version >= 1),
    created_by uuid not null,
    updated_by uuid not null,
    archived_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, parent_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, updated_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, id),
    check (parent_id is null or parent_id <> id),
    check (
      (status = 'active' and archived_at is null)
      or (status = 'archived' and archived_at is not null)
    )
);

create unique index if not exists workspace_folders_active_sibling_name_uq
  on content_factory.workspace_folders (
    organization_id, parent_id, lower(btrim(name))
  )
  nulls not distinct
  where status = 'active';

create index if not exists workspace_folders_tree_idx
  on content_factory.workspace_folders (
    organization_id, parent_id, position desc, id desc
  )
  where status = 'active';

create table if not exists content_factory.workspace_media_locations (
    organization_id uuid not null,
    media_object_id uuid not null,
    folder_id uuid,
    position bigint not null default 0 check (position >= 0),
    version bigint not null default 1 check (version >= 1),
    moved_by uuid not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (organization_id, media_object_id),
    foreign key (organization_id, media_object_id)
      references content_factory.media_objects(organization_id, id)
      on delete cascade,
    foreign key (organization_id, folder_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, moved_by)
      references content_factory.memberships(organization_id, profile_id)
);

create index if not exists workspace_media_locations_folder_idx
  on content_factory.workspace_media_locations (
    organization_id, folder_id, position desc, media_object_id desc
  );

create table if not exists content_factory.workspace_task_locations (
    organization_id uuid not null,
    task_id uuid not null,
    folder_id uuid,
    position bigint not null default 0 check (position >= 0),
    version bigint not null default 1 check (version >= 1),
    moved_by uuid not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (organization_id, task_id),
    foreign key (organization_id, task_id)
      references content_factory.creator_tasks(organization_id, id)
      on delete cascade,
    foreign key (organization_id, folder_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, moved_by)
      references content_factory.memberships(organization_id, profile_id)
);

create index if not exists workspace_task_locations_folder_idx
  on content_factory.workspace_task_locations (
    organization_id, folder_id, position desc, task_id desc
  );

alter table content_factory.workspace_folders enable row level security;
alter table content_factory.workspace_media_locations enable row level security;
alter table content_factory.workspace_task_locations enable row level security;

-- Workspace organization is intentionally available only through the narrow
-- SECURITY DEFINER RPCs below. RLS remains fail-closed if the schema is ever
-- exposed through PostgREST.
revoke all on content_factory.workspace_folders
  from public, anon, authenticated;
revoke all on content_factory.workspace_media_locations
  from public, anon, authenticated;
revoke all on content_factory.workspace_task_locations
  from public, anon, authenticated;
grant all on content_factory.workspace_folders to service_role;
grant all on content_factory.workspace_media_locations to service_role;
grant all on content_factory.workspace_task_locations to service_role;

create or replace function content_factory_private.guard_workspace_folder()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  parent_found boolean;
  contains_cycle boolean;
  ancestor_depth integer;
begin
  perform pg_advisory_xact_lock(
    hashtext(new.organization_id::text),
    hashtext('workspace_structure')
  );

  new.name := btrim(new.name);
  new.color_token := lower(btrim(new.color_token));

  if tg_op = 'UPDATE' then
    if new.id <> old.id
       or new.organization_id <> old.organization_id
       or new.created_by <> old.created_by
       or new.created_at <> old.created_at then
      raise exception using
        errcode = '55000',
        message = 'workspace_folder_identity_immutable';
    end if;
    if old.status = 'archived' and new is distinct from old then
      raise exception using
        errcode = '55000',
        message = 'workspace_folder_archived';
    end if;
  end if;

  if new.parent_id is not null then
    select true into parent_found
    from content_factory.workspace_folders parent
    where parent.organization_id = new.organization_id
      and parent.id = new.parent_id
      and parent.status = 'active'
    for key share;

    if not coalesce(parent_found, false) then
      raise exception using
        errcode = 'P0002',
        message = 'workspace_folder_parent_not_found';
    end if;

    with recursive ancestors as (
      select parent.id, parent.parent_id, 1 as depth
      from content_factory.workspace_folders parent
      where parent.organization_id = new.organization_id
        and parent.id = new.parent_id
      union all
      select parent.id, parent.parent_id, ancestors.depth + 1
      from ancestors
      join content_factory.workspace_folders parent
        on parent.organization_id = new.organization_id
       and parent.id = ancestors.parent_id
      where ancestors.depth < 9
    )
    select
      coalesce(bool_or(ancestors.id = new.id), false),
      coalesce(max(ancestors.depth), 0)
    into contains_cycle, ancestor_depth
    from ancestors;

    if contains_cycle then
      raise exception using
        errcode = '55000',
        message = 'workspace_folder_cycle';
    end if;
    if ancestor_depth >= 8 then
      raise exception using
        errcode = '54000',
        message = 'workspace_folder_depth_exceeded';
    end if;
  end if;

  if tg_op = 'UPDATE'
     and old.status = 'active'
     and new.status = 'archived' then
    if exists (
      select 1
      from content_factory.workspace_folders child
      where child.organization_id = new.organization_id
        and child.parent_id = new.id
        and child.status = 'active'
    ) or exists (
      select 1
      from content_factory.workspace_media_locations location
      where location.organization_id = new.organization_id
        and location.folder_id = new.id
    ) or exists (
      select 1
      from content_factory.workspace_task_locations location
      where location.organization_id = new.organization_id
        and location.folder_id = new.id
    ) then
      raise exception using
        errcode = '55000',
        message = 'workspace_folder_not_empty';
    end if;
    new.archived_at := coalesce(new.archived_at, now());
  end if;

  if tg_op = 'UPDATE' then
    new.version := old.version + 1;
    new.updated_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists guard_workspace_folder
  on content_factory.workspace_folders;
create trigger guard_workspace_folder
before insert or update
on content_factory.workspace_folders
for each row execute function content_factory_private.guard_workspace_folder();

create or replace function content_factory_private.guard_workspace_location()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform pg_advisory_xact_lock(
    hashtext(new.organization_id::text),
    hashtext('workspace_structure')
  );

  if tg_op = 'UPDATE' then
    if new.organization_id <> old.organization_id then
      raise exception using
        errcode = '55000',
        message = 'workspace_location_identity_immutable';
    end if;
    if tg_table_name = 'workspace_media_locations' then
      if new.media_object_id <> old.media_object_id then
        raise exception using
          errcode = '55000',
          message = 'workspace_location_identity_immutable';
      end if;
    elsif tg_table_name = 'workspace_task_locations' then
      if new.task_id <> old.task_id then
        raise exception using
          errcode = '55000',
          message = 'workspace_location_identity_immutable';
      end if;
    end if;
  end if;

  if new.folder_id is not null and not exists (
    select 1
    from content_factory.workspace_folders folder
    where folder.organization_id = new.organization_id
      and folder.id = new.folder_id
      and folder.status = 'active'
  ) then
    raise exception using
      errcode = 'P0002',
      message = 'workspace_folder_not_found';
  end if;

  if tg_op = 'UPDATE' then
    new.version := old.version + 1;
    new.updated_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists guard_workspace_media_location
  on content_factory.workspace_media_locations;
create trigger guard_workspace_media_location
before insert or update
on content_factory.workspace_media_locations
for each row execute function content_factory_private.guard_workspace_location();

drop trigger if exists guard_workspace_task_location
  on content_factory.workspace_task_locations;
create trigger guard_workspace_task_location
before insert or update
on content_factory.workspace_task_locations
for each row execute function content_factory_private.guard_workspace_location();

create or replace function content_factory_private.initialize_workspace_media_location()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into content_factory.workspace_media_locations (
    organization_id, media_object_id, folder_id, position,
    moved_by, created_at, updated_at
  ) values (
    new.organization_id,
    new.id,
    null,
    greatest(
      0,
      (extract(epoch from new.created_at) * 1000000)::bigint
    ),
    new.owner_id,
    new.created_at,
    new.created_at
  )
  on conflict (organization_id, media_object_id) do nothing;
  return new;
end;
$$;

drop trigger if exists initialize_workspace_media_location
  on content_factory.media_objects;
create trigger initialize_workspace_media_location
after insert
on content_factory.media_objects
for each row execute function
  content_factory_private.initialize_workspace_media_location();

create or replace function content_factory_private.initialize_workspace_task_location()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into content_factory.workspace_task_locations (
    organization_id, task_id, folder_id, position,
    moved_by, created_at, updated_at
  ) values (
    new.organization_id,
    new.id,
    null,
    greatest(
      0,
      (extract(epoch from new.created_at) * 1000000)::bigint
    ),
    new.created_by,
    new.created_at,
    new.created_at
  )
  on conflict (organization_id, task_id) do nothing;
  return new;
end;
$$;

drop trigger if exists initialize_workspace_task_location
  on content_factory.creator_tasks;
create trigger initialize_workspace_task_location
after insert
on content_factory.creator_tasks
for each row execute function
  content_factory_private.initialize_workspace_task_location();

-- Triggers are installed before the backfill so rows created during a live
-- migration cannot fall through the root workspace.
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
  media.owner_id,
  media.created_at,
  media.created_at
from content_factory.media_objects media
on conflict (organization_id, media_object_id) do nothing;

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
  task.created_by,
  task.created_at,
  task.created_at
from content_factory.creator_tasks task
on conflict (organization_id, task_id) do nothing;

create or replace function public.creator_workspace_browser(
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
    'organization_id', 'folder_id', 'page_size', 'search',
    'entity_types', 'media_kinds', 'task_statuses', 'cursor'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'workspace_browser_payload_invalid';
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
  folder_manage_scope := actor_role = any(
    array['owner', 'admin', 'producer']
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
    from content_factory.workspace_media_locations location
    join content_factory.media_objects media
      on media.organization_id = location.organization_id
     and media.id = location.media_object_id
    where location.organization_id = organization_id
      and media.status <> 'deleted'
      and (manager_scope or media.owner_id = user_id)
    group by location.folder_id
  ),
  task_counts as (
    select location.folder_id, count(*)::integer as item_count
    from content_factory.workspace_task_locations location
    join content_factory.creator_tasks task
      on task.organization_id = location.organization_id
     and task.id = location.task_id
    where location.organization_id = organization_id
      and (manager_scope or task.assignee_id = user_id)
    group by location.folder_id
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'id', folder.id,
    'parent_id', folder.parent_id,
    'name', folder.name,
    'color_token', folder.color_token,
    'can_edit', folder_manage_scope,
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
    and folder.status = 'active';

  if folder_id_value is not null then
    select jsonb_build_object(
      'id', folder.id,
      'parent_id', folder.parent_id,
      'name', folder.name,
      'color_token', folder.color_token,
      'can_edit', folder_manage_scope,
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
    from content_factory.workspace_media_locations location
    join content_factory.media_objects media
      on media.organization_id = location.organization_id
     and media.id = location.media_object_id
    left join content_factory.products product
      on product.organization_id = media.organization_id
     and product.id = media.product_id
    where location.organization_id = organization_id
      and (
        not (p_payload ? 'folder_id')
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
    from content_factory.workspace_task_locations location
    join content_factory.creator_tasks task
      on task.organization_id = location.organization_id
     and task.id = location.task_id
    left join content_factory.products product
      on product.organization_id = task.organization_id
     and product.id = task.product_id
    where location.organization_id = organization_id
      and (
        not (p_payload ? 'folder_id')
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
          order by page.position desc, page.entity_type desc, page.entity_id desc
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

create or replace function public.creator_create_workspace_folder(
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
  idempotency_key text;
  name_value text;
  parent_id_value uuid;
  color_token_value text := 'emerald';
  active_folder_count integer;
  total_folder_count integer;
  position_value bigint;
  request_payload jsonb;
  replay jsonb;
  folder_row content_factory.workspace_folders%rowtype;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'idempotency_key', 'name',
    'parent_id', 'color_token'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'workspace_folder_create_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer']
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  name_value := content_factory_private.require_text(
    p_payload,
    'name',
    1,
    120
  );
  if name_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023',
      message = 'workspace_folder_name_invalid';
  end if;
  if nullif(btrim(coalesce(p_payload ->> 'parent_id', '')), '') is not null then
    parent_id_value := content_factory_private.require_uuid(
      p_payload,
      'parent_id'
    );
  end if;
  if p_payload ? 'color_token' then
    color_token_value := lower(content_factory_private.require_text(
      p_payload,
      'color_token',
      3,
      20
    ));
  end if;
  if color_token_value not in (
    'emerald', 'gold', 'rose', 'blue', 'violet', 'slate'
  ) then
    raise exception using
      errcode = '22023',
      message = 'workspace_folder_color_invalid';
  end if;

  request_payload := jsonb_build_object(
    'name', name_value,
    'parent_id', parent_id_value,
    'color_token', color_token_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_create_workspace_folder',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('workspace_structure')
  );

  select
    count(*) filter (where folder.status = 'active'),
    count(*)
  into active_folder_count, total_folder_count
  from content_factory.workspace_folders folder
  where folder.organization_id = organization_id;

  if active_folder_count >= 500 then
    raise exception using
      errcode = '54000',
      message = 'workspace_active_folder_quota_exceeded';
  end if;
  if total_folder_count >= 5000 then
    raise exception using
      errcode = '54000',
      message = 'workspace_total_folder_quota_exceeded';
  end if;

  select coalesce(max(folder.position), 0)
    into position_value
  from content_factory.workspace_folders folder
  where folder.organization_id = organization_id
    and folder.parent_id is not distinct from parent_id_value
    and folder.status = 'active';
  if position_value > 9223372036854774783 then
    raise exception using
      errcode = '54000',
      message = 'workspace_position_exhausted';
  end if;
  position_value := position_value + 1024;

  begin
    insert into content_factory.workspace_folders (
      organization_id, parent_id, name, color_token,
      status, position, created_by, updated_by
    ) values (
      organization_id,
      parent_id_value,
      name_value,
      color_token_value,
      'active',
      position_value,
      user_id,
      user_id
    )
    returning * into folder_row;
  exception when unique_violation then
    raise exception using
      errcode = '23505',
      message = 'workspace_folder_name_conflict';
  end;

  result := jsonb_build_object(
    'ok', true,
    'folder', jsonb_build_object(
      'id', folder_row.id,
      'parent_id', folder_row.parent_id,
      'name', folder_row.name,
      'color_token', folder_row.color_token,
      'status', folder_row.status,
      'position', folder_row.position,
      'version', folder_row.version,
      'created_at', folder_row.created_at,
      'updated_at', folder_row.updated_at
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'workspace_folder_created',
    'workspace_folder',
    folder_row.id::text,
    jsonb_build_object(
      'parent_id', folder_row.parent_id,
      'color_token', folder_row.color_token
    ),
    'workspace_folder_create:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_create_workspace_folder',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_update_workspace_folder(
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
  idempotency_key text;
  folder_id_value uuid;
  expected_version_value bigint;
  name_value text;
  parent_id_value uuid;
  color_token_value text;
  archive_value boolean := false;
  parent_supplied boolean;
  changed_value boolean := false;
  position_value bigint;
  request_payload jsonb;
  replay jsonb;
  folder_row content_factory.workspace_folders%rowtype;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'idempotency_key', 'folder_id',
    'expected_version', 'name', 'parent_id', 'color_token', 'archive'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'workspace_folder_update_payload_invalid';
  end if;
  if not (
    p_payload ? 'name'
    or p_payload ? 'parent_id'
    or p_payload ? 'color_token'
    or p_payload ? 'archive'
  ) then
    raise exception using
      errcode = '22023',
      message = 'workspace_folder_update_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer']
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  folder_id_value := content_factory_private.require_uuid(
    p_payload,
    'folder_id'
  );
  if coalesce(p_payload ->> 'expected_version', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023',
      message = 'workspace_folder_version_invalid';
  end if;
  begin
    expected_version_value := (p_payload ->> 'expected_version')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'workspace_folder_version_invalid';
  end;
  if expected_version_value < 1 then
    raise exception using
      errcode = '22023',
      message = 'workspace_folder_version_invalid';
  end if;

  if p_payload ? 'name' then
    name_value := content_factory_private.require_text(
      p_payload,
      'name',
      1,
      120
    );
    if name_value ~ '[[:cntrl:]]' then
      raise exception using
        errcode = '22023',
        message = 'workspace_folder_name_invalid';
    end if;
  end if;
  parent_supplied := p_payload ? 'parent_id';
  if parent_supplied
     and nullif(btrim(coalesce(p_payload ->> 'parent_id', '')), '') is not null then
    parent_id_value := content_factory_private.require_uuid(
      p_payload,
      'parent_id'
    );
  end if;
  if p_payload ? 'color_token' then
    color_token_value := lower(content_factory_private.require_text(
      p_payload,
      'color_token',
      3,
      20
    ));
    if color_token_value not in (
      'emerald', 'gold', 'rose', 'blue', 'violet', 'slate'
    ) then
      raise exception using
        errcode = '22023',
        message = 'workspace_folder_color_invalid';
    end if;
  end if;
  if p_payload ? 'archive' then
    if p_payload -> 'archive' not in ('true'::jsonb, 'false'::jsonb) then
      raise exception using
        errcode = '22023',
        message = 'workspace_folder_archive_invalid';
    end if;
    archive_value := (p_payload ->> 'archive')::boolean;
    if not archive_value then
      raise exception using
        errcode = '22023',
        message = 'workspace_folder_archive_invalid';
    end if;
  end if;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_update_workspace_folder',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('workspace_structure')
  );
  select folder.* into folder_row
  from content_factory.workspace_folders folder
  where folder.organization_id = organization_id
    and folder.id = folder_id_value
  for update;

  if folder_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'workspace_folder_not_found';
  end if;
  if folder_row.status <> 'active' then
    raise exception using
      errcode = '55000',
      message = 'workspace_folder_archived';
  end if;
  if folder_row.version <> expected_version_value then
    raise exception using
      errcode = '40001',
      message = 'workspace_folder_version_conflict';
  end if;

  name_value := coalesce(name_value, folder_row.name);
  color_token_value := coalesce(color_token_value, folder_row.color_token);
  if not parent_supplied then
    parent_id_value := folder_row.parent_id;
  end if;

  changed_value :=
    name_value is distinct from folder_row.name
    or color_token_value is distinct from folder_row.color_token
    or parent_id_value is distinct from folder_row.parent_id
    or archive_value;

  if changed_value then
    position_value := folder_row.position;
    if parent_id_value is distinct from folder_row.parent_id then
      select coalesce(max(folder.position), 0)
        into position_value
      from content_factory.workspace_folders folder
      where folder.organization_id = organization_id
        and folder.parent_id is not distinct from parent_id_value
        and folder.status = 'active'
        and folder.id <> folder_id_value;
      if position_value > 9223372036854774783 then
        raise exception using
          errcode = '54000',
          message = 'workspace_position_exhausted';
      end if;
      position_value := position_value + 1024;
    end if;

    begin
      update content_factory.workspace_folders folder
      set name = name_value,
          parent_id = parent_id_value,
          color_token = color_token_value,
          status = case when archive_value then 'archived' else folder.status end,
          archived_at = case when archive_value then now() else folder.archived_at end,
          position = position_value,
          updated_by = user_id
      where folder.organization_id = organization_id
        and folder.id = folder_id_value
      returning * into folder_row;
    exception when unique_violation then
      raise exception using
        errcode = '23505',
        message = 'workspace_folder_name_conflict';
    end;

    perform content_factory_private.emit_event(
      organization_id,
      user_id,
      case
        when archive_value then 'workspace_folder_archived'
        else 'workspace_folder_updated'
      end,
      'workspace_folder',
      folder_row.id::text,
      jsonb_build_object(
        'parent_id', folder_row.parent_id,
        'color_token', folder_row.color_token,
        'status', folder_row.status,
        'version', folder_row.version
      ),
      'workspace_folder_update:' || idempotency_key
    );
  end if;

  result := jsonb_build_object(
    'ok', true,
    'changed', changed_value,
    'folder', jsonb_build_object(
      'id', folder_row.id,
      'parent_id', folder_row.parent_id,
      'name', folder_row.name,
      'color_token', folder_row.color_token,
      'status', folder_row.status,
      'position', folder_row.position,
      'version', folder_row.version,
      'archived_at', folder_row.archived_at,
      'created_at', folder_row.created_at,
      'updated_at', folder_row.updated_at
    )
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_update_workspace_folder',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_move_workspace_items(
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
  destination_folder_id_value uuid;
  items_value jsonb;
  normalized_items jsonb;
  item record;
  item_id_value uuid;
  max_position_value bigint;
  next_position_value bigint;
  moved_items jsonb := '[]'::jsonb;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'idempotency_key',
    'destination_folder_id', 'items'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'workspace_move_payload_invalid';
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
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  if nullif(
    btrim(coalesce(p_payload ->> 'destination_folder_id', '')),
    ''
  ) is not null then
    destination_folder_id_value := content_factory_private.require_uuid(
      p_payload,
      'destination_folder_id'
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
      errcode = '22023',
      message = 'workspace_items_invalid';
  end if;
  if (
    select count(*)
    from (
      select element.value ->> 'type', lower(element.value ->> 'id')
      from jsonb_array_elements(items_value) element(value)
      group by element.value ->> 'type', lower(element.value ->> 'id')
      having count(*) > 1
    ) duplicates
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
  into normalized_items
  from jsonb_array_elements(items_value)
    with ordinality element(value, ordinality);

  request_payload := jsonb_build_object(
    'destination_folder_id', destination_folder_id_value,
    'items', normalized_items
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_move_workspace_items',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('workspace_structure')
  );

  if destination_folder_id_value is not null and not exists (
    select 1
    from content_factory.workspace_folders folder
    where folder.organization_id = organization_id
      and folder.id = destination_folder_id_value
      and folder.status = 'active'
  ) then
    raise exception using
      errcode = 'P0002',
      message = 'workspace_folder_not_found';
  end if;

  -- Lock and authorize every item before any location is changed. The whole
  -- batch therefore succeeds or rolls back as one drag/drop action.
  for item in
    select
      element.value ->> 'type' as entity_type,
      (element.value ->> 'id')::uuid as entity_id,
      element.ordinality
    from jsonb_array_elements(normalized_items)
      with ordinality element(value, ordinality)
    order by element.value ->> 'type', (element.value ->> 'id')::uuid
  loop
    if item.entity_type = 'media' then
      perform 1
      from content_factory.workspace_media_locations location
      join content_factory.media_objects media
        on media.organization_id = location.organization_id
       and media.id = location.media_object_id
      where location.organization_id = organization_id
        and location.media_object_id = item.entity_id
        and media.status <> 'deleted'
        and (manager_scope or media.owner_id = user_id)
      for update of location;
      if not found then
        raise exception using
          errcode = '42501',
          message = 'workspace_item_access_denied';
      end if;
    else
      perform 1
      from content_factory.workspace_task_locations location
      join content_factory.creator_tasks task
        on task.organization_id = location.organization_id
       and task.id = location.task_id
      where location.organization_id = organization_id
        and location.task_id = item.entity_id
        and (manager_scope or task.assignee_id = user_id)
      for update of location;
      if not found then
        raise exception using
          errcode = '42501',
          message = 'workspace_item_access_denied';
      end if;
    end if;
  end loop;

  select greatest(
    coalesce((
      select max(location.position)
      from content_factory.workspace_media_locations location
      where location.organization_id = organization_id
        and location.folder_id is not distinct from destination_folder_id_value
    ), 0),
    coalesce((
      select max(location.position)
      from content_factory.workspace_task_locations location
      where location.organization_id = organization_id
        and location.folder_id is not distinct from destination_folder_id_value
    ), 0),
    greatest(
      0,
      (extract(epoch from clock_timestamp()) * 1000000)::bigint
    )
  )
  into max_position_value;

  if max_position_value > (
    9223372036854775807
    - (jsonb_array_length(normalized_items)::bigint * 1024)
  ) then
    raise exception using
      errcode = '54000',
      message = 'workspace_position_exhausted';
  end if;

  for item in
    select
      element.value ->> 'type' as entity_type,
      (element.value ->> 'id')::uuid as entity_id,
      element.ordinality
    from jsonb_array_elements(normalized_items)
      with ordinality element(value, ordinality)
    order by element.ordinality
  loop
    item_id_value := item.entity_id;
    next_position_value :=
      max_position_value + (item.ordinality::bigint * 1024);
    if item.entity_type = 'media' then
      update content_factory.workspace_media_locations location
      set folder_id = destination_folder_id_value,
          position = next_position_value,
          moved_by = user_id
      where location.organization_id = organization_id
        and location.media_object_id = item_id_value;
    else
      update content_factory.workspace_task_locations location
      set folder_id = destination_folder_id_value,
          position = next_position_value,
          moved_by = user_id
      where location.organization_id = organization_id
        and location.task_id = item_id_value;
    end if;
    moved_items := moved_items || jsonb_build_array(jsonb_build_object(
      'type', item.entity_type,
      'id', item_id_value,
      'folder_id', destination_folder_id_value,
      'position', next_position_value
    ));
  end loop;

  result := jsonb_build_object(
    'ok', true,
    'destination_folder_id', destination_folder_id_value,
    'moved_count', jsonb_array_length(moved_items),
    'items', moved_items
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'workspace_items_moved',
    'workspace_folder',
    coalesce(destination_folder_id_value::text, 'root'),
    jsonb_build_object(
      'destination_folder_id', destination_folder_id_value,
      'item_count', jsonb_array_length(moved_items),
      'entity_types', (
        select coalesce(jsonb_agg(distinct element.value ->> 'type'), '[]'::jsonb)
        from jsonb_array_elements(normalized_items) element(value)
      )
    ),
    'workspace_items_move:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_move_workspace_items',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

revoke all on function public.creator_workspace_browser(jsonb)
  from public, anon;
revoke all on function public.creator_create_workspace_folder(jsonb)
  from public, anon;
revoke all on function public.creator_update_workspace_folder(jsonb)
  from public, anon;
revoke all on function public.creator_move_workspace_items(jsonb)
  from public, anon;

grant execute on function public.creator_workspace_browser(jsonb)
  to authenticated;
grant execute on function public.creator_create_workspace_folder(jsonb)
  to authenticated;
grant execute on function public.creator_update_workspace_folder(jsonb)
  to authenticated;
grant execute on function public.creator_move_workspace_items(jsonb)
  to authenticated;

revoke all on all functions in schema content_factory_private
  from public, anon, authenticated;
grant execute on all functions in schema content_factory_private
  to service_role;

commit;
