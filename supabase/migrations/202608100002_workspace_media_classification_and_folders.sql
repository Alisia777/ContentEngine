begin;

-- Media status describes object availability, not its role in the content
-- workflow. Keep provenance and workflow placement as separate server-owned
-- fields so Research and Finder do not have to infer them from a filename.
alter table content_factory.media_objects
  add column if not exists artifact_class text not null default 'unclassified',
  add column if not exists lifecycle_stage text not null default 'unclassified';

comment on column content_factory.media_objects.artifact_class is
  'Server-owned media provenance: source, generated_output, or unclassified.';
comment on column content_factory.media_objects.lifecycle_stage is
  'Server-owned workflow stage projected into the matching project system folder.';

create or replace function content_factory_private.workspace_media_artifact_class(
  p_kind text
)
returns text
language sql
immutable
set search_path = ''
as $$
  select case lower(btrim(coalesce(p_kind, '')))
    when 'product_photo' then 'source'
    when 'packshot' then 'source'
    when 'creator_reference' then 'source'
    when 'source_video' then 'source'
    when 'generated_image' then 'generated_output'
    when 'generated_video' then 'generated_output'
    else 'unclassified'
  end
$$;

create or replace function content_factory_private.workspace_media_initial_stage(
  p_artifact_class text
)
returns text
language sql
immutable
set search_path = ''
as $$
  select case lower(btrim(coalesce(p_artifact_class, '')))
    when 'source' then 'sources'
    when 'generated_output' then 'drafts'
    else 'unclassified'
  end
$$;

revoke all on function
  content_factory_private.workspace_media_artifact_class(text)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.workspace_media_initial_stage(text)
  from public, anon, authenticated;
grant execute on function
  content_factory_private.workspace_media_artifact_class(text)
  to service_role;
grant execute on function
  content_factory_private.workspace_media_initial_stage(text)
  to service_role;

-- Preserve a meaningful system-folder stage when it already exists. Otherwise
-- source kinds have one deterministic stage and legacy generated outputs enter
-- the conservative drafts stage. Custom-folder placement is not used as a
-- lifecycle guess and is preserved by the location backfill below.
with classified as (
  select
    media.organization_id,
    media.id,
    content_factory_private.workspace_media_artifact_class(
      media.metadata ->> 'kind'
    ) as artifact_class,
    folder.system_role as existing_system_role
  from content_factory.media_objects media
  left join content_factory.workspace_media_locations location
    on location.organization_id = media.organization_id
   and location.media_object_id = media.id
  left join content_factory.workspace_folders folder
    on folder.organization_id = location.organization_id
   and folder.id = location.folder_id
   and folder.status = 'active'
)
update content_factory.media_objects media
set artifact_class = classified.artifact_class,
    lifecycle_stage = case classified.artifact_class
      when 'source' then 'sources'
      when 'generated_output' then case
        when classified.existing_system_role in (
          'drafts', 'review', 'ready', 'published'
        ) then classified.existing_system_role
        else 'drafts'
      end
      else 'unclassified'
    end
from classified
where media.organization_id = classified.organization_id
  and media.id = classified.id
  and media.artifact_class = 'unclassified'
  and media.lifecycle_stage = 'unclassified';

do $$
begin
  if not exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.media_objects'::regclass
      and constraint_row.conname = 'media_objects_artifact_class_check'
  ) then
    alter table content_factory.media_objects
      add constraint media_objects_artifact_class_check
      check (artifact_class in (
        'source', 'generated_output', 'unclassified'
      ));
  end if;

  if not exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.media_objects'::regclass
      and constraint_row.conname = 'media_objects_lifecycle_stage_check'
  ) then
    alter table content_factory.media_objects
      add constraint media_objects_lifecycle_stage_check
      check (lifecycle_stage in (
        'sources', 'drafts', 'review', 'ready', 'published',
        'unclassified'
      ));
  end if;

  if not exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.media_objects'::regclass
      and constraint_row.conname = 'media_objects_artifact_lifecycle_check'
  ) then
    alter table content_factory.media_objects
      add constraint media_objects_artifact_lifecycle_check
      check (
        (artifact_class = 'source' and lifecycle_stage = 'sources')
        or (
          artifact_class = 'generated_output'
          and lifecycle_stage in (
            'drafts', 'review', 'ready', 'published'
          )
        )
        or (
          artifact_class = 'unclassified'
          and lifecycle_stage = 'unclassified'
        )
      );
  end if;
end;
$$;

create index if not exists media_objects_project_artifact_stage_idx
  on content_factory.media_objects (
    organization_id, project_id, artifact_class, lifecycle_stage,
    created_at desc, id desc
  )
  where status <> 'deleted';

create or replace function content_factory_private.classify_workspace_media()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  classified_artifact text;
begin
  if tg_op = 'INSERT' then
    classified_artifact :=
      content_factory_private.workspace_media_artifact_class(
        new.metadata ->> 'kind'
      );
    new.artifact_class := classified_artifact;
    new.lifecycle_stage :=
      content_factory_private.workspace_media_initial_stage(
        classified_artifact
      );
  elsif new.metadata ->> 'kind' is distinct from old.metadata ->> 'kind' then
    classified_artifact :=
      content_factory_private.workspace_media_artifact_class(
        new.metadata ->> 'kind'
      );
    new.artifact_class := classified_artifact;
    new.lifecycle_stage :=
      content_factory_private.workspace_media_initial_stage(
        classified_artifact
      );
  end if;
  return new;
end;
$$;

revoke all on function content_factory_private.classify_workspace_media()
  from public, anon, authenticated;

drop trigger if exists classify_workspace_media
  on content_factory.media_objects;
create trigger classify_workspace_media
before insert or update of metadata
on content_factory.media_objects
for each row execute function
  content_factory_private.classify_workspace_media();

create or replace function
  content_factory_private.sync_workspace_media_system_location(
    p_organization_id uuid,
    p_media_object_id uuid,
    p_workflow_transition boolean default false
  )
returns uuid
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  media_row content_factory.media_objects%rowtype;
  destination_folder_id uuid;
  current_folder_id uuid;
  current_location_exists boolean := false;
  actor_id uuid;
  position_value bigint;
begin
  perform pg_advisory_xact_lock(
    hashtext(p_organization_id::text),
    hashtext('workspace-media-location:' || p_media_object_id::text)
  );

  select media.*
    into media_row
  from content_factory.media_objects media
  where media.organization_id = p_organization_id
    and media.id = p_media_object_id;

  if media_row.id is null
     or media_row.project_id is null
     or media_row.lifecycle_stage = 'unclassified' then
    return null;
  end if;

  select folder.id
    into destination_folder_id
  from content_factory.workspace_folders folder
  where folder.organization_id = media_row.organization_id
    and folder.parent_id = media_row.project_id
    and folder.kind = 'folder'
    and folder.system_role = media_row.lifecycle_stage
    and folder.status = 'active'
  limit 1;

  if destination_folder_id is null then
    -- Legacy projects can temporarily lack one of the system folders. Media
    -- registration must remain available and the repair can be retried later.
    return null;
  end if;

  select location.folder_id, true
    into current_folder_id, current_location_exists
  from content_factory.workspace_media_locations location
  where location.organization_id = media_row.organization_id
    and location.media_object_id = media_row.id
  for update;

  if current_location_exists
     and current_folder_id is not null
     and not p_workflow_transition then
    -- Backfills and classification retries never overwrite an explicit user
    -- location. A real server-side lifecycle transition may do so.
    return current_folder_id;
  end if;

  if current_location_exists
     and current_folder_id is not distinct from destination_folder_id then
    return destination_folder_id;
  end if;

  select coalesce(
    (
      select membership.profile_id
      from content_factory.memberships membership
      where membership.organization_id = media_row.organization_id
        and membership.profile_id = auth.uid()
        and membership.status = 'active'
      limit 1
    ),
    media_row.owner_id
  ) into actor_id;

  position_value := greatest(
    0,
    (extract(epoch from media_row.created_at) * 1000000)::bigint
  );

  insert into content_factory.workspace_media_locations (
    organization_id, media_object_id, folder_id, position,
    moved_by, created_at, updated_at
  ) values (
    media_row.organization_id,
    media_row.id,
    destination_folder_id,
    position_value,
    actor_id,
    media_row.created_at,
    now()
  )
  on conflict (organization_id, media_object_id) do update
  set folder_id = excluded.folder_id,
      moved_by = excluded.moved_by
  where content_factory.workspace_media_locations.folder_id
    is distinct from excluded.folder_id;

  return destination_folder_id;
end;
$$;

revoke all on function
  content_factory_private.sync_workspace_media_system_location(
    uuid, uuid, boolean
  ) from public, anon, authenticated;
grant execute on function
  content_factory_private.sync_workspace_media_system_location(
    uuid, uuid, boolean
  ) to service_role;

-- The existing initializer creates a nullable location after media insertion.
-- The zz-prefix makes this trigger run after it on supported PostgreSQL
-- versions; the upsert also makes the result correct if trigger order changes.
create or replace function
  content_factory_private.sync_workspace_media_location_trigger()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  workflow_transition boolean := false;
begin
  if tg_op = 'UPDATE' then
    workflow_transition :=
      old.lifecycle_stage is distinct from new.lifecycle_stage;
    if not workflow_transition then
      return new;
    end if;
    if not pg_try_advisory_xact_lock(
      hashtext(new.organization_id::text),
      hashtext('workspace_structure')
    ) then
      raise exception using
        errcode = '40001',
        message = 'workspace_media_lifecycle_concurrent_move';
    end if;
  end if;
  perform content_factory_private.sync_workspace_media_system_location(
    new.organization_id,
    new.id,
    workflow_transition
  );
  return new;
end;
$$;

revoke all on function
  content_factory_private.sync_workspace_media_location_trigger()
  from public, anon, authenticated;

drop trigger if exists zz_sync_workspace_media_system_location
  on content_factory.media_objects;
create trigger zz_sync_workspace_media_system_location
after insert or update of metadata, lifecycle_stage
on content_factory.media_objects
for each row execute function
  content_factory_private.sync_workspace_media_location_trigger();

-- Only unfiled legacy rows are projected during backfill. Explicit custom and
-- system-folder choices remain intact until a later workflow transition.
do $$
declare
  media_row record;
begin
  for media_row in
    select media.organization_id, media.id
    from content_factory.media_objects media
    left join content_factory.workspace_media_locations location
      on location.organization_id = media.organization_id
     and location.media_object_id = media.id
    where media.artifact_class <> 'unclassified'
      and media.lifecycle_stage <> 'unclassified'
      and location.folder_id is null
  loop
    perform content_factory_private.sync_workspace_media_system_location(
      media_row.organization_id,
      media_row.id,
      false
    );
  end loop;
end;
$$;

-- Narrow contract helpers keep the root/all and media-kind rules explicit so
-- the compatibility reader below does not need to copy the current large
-- project reader.
create or replace function content_factory_private.workspace_folder_scope_matches(
  p_payload jsonb,
  p_location_folder_id uuid
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select case
    when not (coalesce(p_payload, '{}'::jsonb) ? 'folder_id') then true
    when jsonb_typeof(p_payload -> 'folder_id') = 'null'
      or nullif(btrim(coalesce(p_payload ->> 'folder_id', '')), '') is null
      then p_location_folder_id is null
    else p_location_folder_id is not distinct from
      (p_payload ->> 'folder_id')::uuid
  end
$$;

create or replace function content_factory_private.workspace_media_kind_supported(
  p_kind text
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select lower(btrim(coalesce(p_kind, ''))) = any(array[
    'product_photo', 'packshot', 'creator_reference', 'source_video',
    'generated_image', 'generated_video'
  ]::text[])
$$;

revoke all on function
  content_factory_private.workspace_folder_scope_matches(jsonb, uuid)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.workspace_media_kind_supported(text)
  from public, anon, authenticated;
grant execute on function
  content_factory_private.workspace_folder_scope_matches(jsonb, uuid)
  to service_role;
grant execute on function
  content_factory_private.workspace_media_kind_supported(text)
  to service_role;

-- Preserve the audited project reader and put a deliberately narrow adapter
-- in front of it. The adapter is active only for the two contracts the reader
-- did not previously express:
--   * omitted folder_id means every folder, explicit null means only root;
--   * generated_image is a supported media_kinds value.
-- Authentication, project visibility, search, ownership, folder validation,
-- ordering and cursor validation remain owned by the preserved reader.
do $preserve_workspace_browser_media_scope$
begin
  if to_regprocedure(
    'content_factory_private.creator_workspace_browser_pre_media_scope_v418(jsonb)'
  ) is null then
    alter function public.creator_workspace_browser(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_workspace_browser(jsonb)
      rename to creator_workspace_browser_pre_media_scope_v418;
  end if;
end;
$preserve_workspace_browser_media_scope$;

revoke all on function
  content_factory_private.creator_workspace_browser_pre_media_scope_v418(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_workspace_browser(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  root_scope_requested boolean := false;
  generated_image_filter_requested boolean := false;
  media_kinds_value text[] := array[]::text[];
  inner_payload jsonb;
  result_value jsonb;
  page_size_value integer;
  items_value jsonb := '[]'::jsonb;
  scan_payload jsonb;
  scan_result jsonb;
  scan_items jsonb;
  scan_filtered jsonb;
  scan_cursor jsonb;
  filtered_has_more boolean := false;
  filtered_next_cursor jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  root_scope_requested := (p_payload ? 'folder_id')
    and (
      jsonb_typeof(p_payload -> 'folder_id') = 'null'
      or nullif(btrim(coalesce(p_payload ->> 'folder_id', '')), '') is null
    );

  if jsonb_typeof(p_payload -> 'media_kinds') = 'array' then
    select exists (
      select 1
      from jsonb_array_elements_text(p_payload -> 'media_kinds') kind(value)
      where lower(btrim(kind.value)) = 'generated_image'
    )
    into generated_image_filter_requested;
  end if;

  -- Keep the common path byte-for-byte compatible with the recovered reader.
  if not root_scope_requested and not generated_image_filter_requested then
    return content_factory_private
      .creator_workspace_browser_pre_media_scope_v418(p_payload);
  end if;

  inner_payload := p_payload;
  if root_scope_requested then
    -- The preserved reader interprets a missing folder as all project items.
    -- That gives this adapter a complete, authorized stream to filter to root.
    inner_payload := inner_payload - 'folder_id';
  end if;
  if generated_image_filter_requested then
    -- The preserved allowlist predates generated images. Read the same
    -- authorized media stream and apply the expanded allowlist below.
    inner_payload := inner_payload - 'media_kinds';
  end if;

  -- Call before expanded-kind validation so authentication/project gates and
  -- the established payload/page/cursor checks still execute in one place.
  scan_result := content_factory_private
    .creator_workspace_browser_pre_media_scope_v418(inner_payload);
  result_value := scan_result;
  page_size_value := coalesce(
    (result_value #>> '{_meta,page_size}')::integer,
    50
  );

  if generated_image_filter_requested then
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
    if exists (
      select 1
      from jsonb_array_elements_text(p_payload -> 'media_kinds') kind(value)
      where not content_factory_private.workspace_media_kind_supported(
        kind.value
      )
    ) then
      raise exception using
        errcode = '22023',
        message = 'workspace_media_kinds_invalid';
    end if;
    select coalesce(
      array_agg(distinct lower(btrim(kind.value))),
      array[]::text[]
    )
    into media_kinds_value
    from jsonb_array_elements_text(p_payload -> 'media_kinds') kind(value);
  end if;

  -- Filtering only the first underlying page can make a populated root or a
  -- generated-image result look empty. Continue the preserved keyset stream
  -- until this filtered page has one look-ahead item or the stream is spent.
  loop
    scan_items := coalesce(scan_result -> 'items', '[]'::jsonb);
    select coalesce(
      jsonb_agg(item.value order by item.ordinality),
      '[]'::jsonb
    )
    into scan_filtered
    from jsonb_array_elements(scan_items)
      with ordinality item(value, ordinality)
    where content_factory_private.workspace_folder_scope_matches(
      p_payload,
      nullif(item.value ->> 'folder_id', '')::uuid
    )
      and (
        not generated_image_filter_requested
        or item.value ->> 'type' <> 'media'
        or lower(btrim(coalesce(item.value ->> 'kind', '')))
          = any(media_kinds_value)
      );
    items_value := items_value || scan_filtered;
    exit when jsonb_array_length(items_value) > page_size_value;

    scan_cursor := scan_result #> '{_meta,next_cursor}';
    exit when scan_cursor is null
      or scan_cursor = 'null'::jsonb
      or not coalesce(
        (scan_result #>> '{_meta,has_more}')::boolean,
        false
      );
    scan_payload := (inner_payload - 'cursor') || jsonb_build_object(
      'page_size', 100,
      'cursor', scan_cursor
    );
    scan_result := content_factory_private
      .creator_workspace_browser_pre_media_scope_v418(scan_payload);
  end loop;

  filtered_has_more :=
    jsonb_array_length(items_value) > page_size_value;
  select coalesce(
    jsonb_agg(item.value order by item.ordinality),
    '[]'::jsonb
  )
  into items_value
  from jsonb_array_elements(items_value)
    with ordinality item(value, ordinality)
  where item.ordinality <= page_size_value;

  if filtered_has_more then
    select item.value -> '_cursor'
    into filtered_next_cursor
    from jsonb_array_elements(items_value)
      with ordinality item(value, ordinality)
    order by item.ordinality desc
    limit 1;
  end if;

  result_value := jsonb_set(
    jsonb_set(
      jsonb_set(
        result_value,
        '{items}',
        items_value,
        true
      ),
      '{_meta,has_more}',
      to_jsonb(filtered_has_more),
      true
    ),
    '{_meta,next_cursor}',
    coalesce(filtered_next_cursor, 'null'::jsonb),
    true
  );
  return result_value;
end;
$$;

revoke all on function public.creator_workspace_browser(jsonb)
  from public, anon;
grant execute on function public.creator_workspace_browser(jsonb)
  to authenticated;

commit;
