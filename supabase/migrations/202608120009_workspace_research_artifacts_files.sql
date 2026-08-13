begin;

-- Research ledgers remain immutable domain records.  Files receives a narrow,
-- read-only projection with no synthetic folder location and no research
-- summary, sources, brief content, notes or model-authored payloads.
create or replace function
  content_factory_private.workspace_research_artifacts_projection(
    p_organization_id uuid,
    p_project_id uuid,
    p_profile_id uuid
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  actor_role_value text;
  operator_allowed boolean := false;
  artifacts_value jsonb := '[]'::jsonb;
begin
  if p_organization_id is null
     or p_project_id is null
     or p_profile_id is null
     or not content_factory_private.workspace_project_access_allowed(
       p_organization_id, p_project_id, p_profile_id
     ) then
    return artifacts_value;
  end if;

  select membership.role
    into actor_role_value
  from content_factory.memberships membership
  join content_factory.organizations organization
    on organization.id = membership.organization_id
   and organization.status = 'active'
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where membership.organization_id = p_organization_id
    and membership.profile_id = p_profile_id
    and membership.status = 'active';

  if actor_role_value = 'operator' then
    operator_allowed := content_factory_private
      .qualified_operator_project_research_allowed(
        p_organization_id, p_project_id, p_profile_id
      );
    if not operator_allowed then
      return artifacts_value;
    end if;
  elsif actor_role_value not in ('owner', 'admin', 'producer', 'reviewer') then
    return artifacts_value;
  end if;

  select coalesce(jsonb_agg(
    jsonb_strip_nulls(jsonb_build_object(
      'type', 'research',
      'entity_type', 'research',
      'id', artifact.id,
      'project_id', artifact.project_id,
      'created_by', artifact.created_by,
      'status', artifact.run_status,
      'created_at', artifact.created_at,
      'started_at', artifact.started_at,
      'finished_at', artifact.finished_at,
      'updated_at', artifact.updated_at,
      'deep_link', '#/workspace/research?project_id='
        || artifact.project_id::text || '&run=' || artifact.id::text,
      'category_binding_id', artifact.category_binding_id,
      'ai_receipt', case when artifact.receipt_id is null then null else
        jsonb_strip_nulls(jsonb_build_object(
          'receipt_id', artifact.receipt_id,
          'status', artifact.receipt_status,
          'received_at', artifact.received_at,
          'deep_link', '#/workspace/ai?project_id='
            || artifact.project_id::text
            || '&category=' || artifact.receipt_product_category
            || '&receipt=' || artifact.receipt_id::text
        ))
      end,
      'disposition', case when artifact.disposition_id is null then null else
        jsonb_build_object(
          'disposition_id', artifact.disposition_id,
          'status', artifact.disposition_status,
          'decided_at', artifact.decided_at,
          'deep_link', '#/workspace/ai?project_id='
            || artifact.project_id::text
            || '&category=' || artifact.receipt_product_category
            || '&receipt=' || artifact.receipt_id::text
        )
      end,
      'learning_selection', case when artifact.selection_id is null then null else
        jsonb_build_object(
          'selection_id', artifact.selection_id,
          'status', artifact.selection_status,
          'selected_at', artifact.selected_at,
          'deep_link', '#/workspace/ai?project_id='
            || artifact.project_id::text
            || '&category=' || artifact.receipt_product_category
            || '&receipt=' || artifact.receipt_id::text
        )
      end,
      'read_only', true,
      'can_move', false
    )) order by artifact.created_at desc, artifact.id desc
  ), '[]'::jsonb)
  into artifacts_value
  from (
    select
      run.id,
      run.project_id,
      run.created_by,
      run.status as run_status,
      run.created_at,
      run.started_at,
      run.finished_at,
      run.updated_at,
      binding.id as category_binding_id,
      receipt.id as receipt_id,
      receipt.product_category as receipt_product_category,
      receipt.status as receipt_status,
      receipt.received_at,
      disposition.id as disposition_id,
      disposition.decision as disposition_status,
      disposition.decided_at,
      selection.id as selection_id,
      selection.decision as selection_status,
      selection.selected_at
    from content_factory.product_research_runs run
    left join content_factory.research_ai_category_bindings binding
      on binding.organization_id = run.organization_id
     and binding.project_id = run.project_id
     and binding.run_id = run.id
     and (
       actor_role_value in ('owner', 'admin', 'producer', 'reviewer')
       or binding.bound_by = p_profile_id
     )
    left join content_factory.ai_research_evidence_receipts receipt
      on receipt.organization_id = run.organization_id
     and receipt.project_id = run.project_id
     and receipt.run_id = run.id
     and (
       actor_role_value in ('owner', 'admin', 'producer', 'reviewer')
       or content_factory_private
         .qualified_operator_own_ai_research_receipt_allowed(
           receipt.organization_id, receipt.id, p_profile_id
         )
     )
    left join content_factory.ai_research_evidence_dispositions disposition
      on disposition.organization_id = receipt.organization_id
     and disposition.receipt_id = receipt.id
     and disposition.receipt_hash = receipt.receipt_hash
    left join content_factory.ai_research_learning_selections selection
      on selection.organization_id = receipt.organization_id
     and selection.project_id = receipt.project_id
     and selection.run_id = receipt.run_id
     and selection.receipt_id = receipt.id
     and selection.receipt_hash = receipt.receipt_hash
    where run.organization_id = p_organization_id
      and run.project_id = p_project_id
      and (
        actor_role_value in ('owner', 'admin', 'producer', 'reviewer')
        or (
          operator_allowed
          and run.created_by = p_profile_id
        )
      )
    order by run.created_at desc, run.id desc
    limit 50
  ) artifact;

  return artifacts_value;
end;
$$;

revoke all on function
  content_factory_private.workspace_research_artifacts_projection(
    uuid, uuid, uuid
  ) from public, anon, authenticated, service_role;

-- Preserve the mature exact-project media reader.  The Files surface is a
-- read-only adapter; Generation and Review continue through the preserved
-- implementation without any response or authorization changes.
do $preserve_project_media_for_files_v438$
begin
  if to_regprocedure(
    'content_factory_private.creator_project_media_pre_files_v438(jsonb)'
  ) is null then
    if to_regprocedure('public.creator_project_media(jsonb)') is null then
      raise exception using
        errcode = '42883', message = 'creator_project_media_missing';
    end if;
    alter function public.creator_project_media(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_project_media(jsonb)
      rename to creator_project_media_pre_files_v438;
  end if;
end;
$preserve_project_media_for_files_v438$;

revoke all on function
  content_factory_private.creator_project_media_pre_files_v438(jsonb)
  from public, anon, authenticated, service_role;

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
  surface_value text;
  delegated_payload jsonb;
  result_value jsonb;
  media_value jsonb;
  user_id uuid;
  organization_id uuid;
  project_id_value uuid;
  actor_role text;
  media_id_value uuid;
  folder_id_value uuid;
  can_move_value boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  surface_value := lower(btrim(coalesce(p_payload ->> 'surface', '')));
  if surface_value <> 'files' then
    return content_factory_private
      .creator_project_media_pre_files_v438(p_payload);
  end if;

  -- The mature Generation surface has the same all-kind, ready-media read
  -- contract needed by Files.  It still performs every exact-project gate.
  delegated_payload := jsonb_set(
    p_payload,
    '{surface}',
    to_jsonb('generation'::text),
    true
  );
  result_value := content_factory_private
    .creator_project_media_pre_files_v438(delegated_payload);
  media_value := result_value -> 'media';

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  project_id_value := (result_value ->> 'project_id')::uuid;
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id, project_id_value, user_id
  );
  media_id_value := (result_value ->> 'media_id')::uuid;

  select location.folder_id
    into folder_id_value
  from content_factory.workspace_media_locations location
  where location.organization_id = organization_id
    and location.media_object_id = media_id_value
    and (
      location.folder_id is null
      or content_factory_private.workspace_project_for_folder(
        location.organization_id, location.folder_id
      ) = project_id_value
    );

  can_move_value := actor_role in ('owner', 'admin', 'producer', 'reviewer')
    or coalesce(media_value ->> 'owner_id' = user_id::text, false);
  media_value := media_value || jsonb_build_object(
    'folder_id', folder_id_value,
    'can_move', can_move_value,
    'workspace_item_key', 'media:' || media_id_value::text
  );

  return result_value || jsonb_build_object(
    'surface', 'files',
    'media', media_value,
    'workspace_item_key', 'media:' || media_id_value::text
  );
end;
$$;

revoke all on function public.creator_project_media(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_project_media(jsonb)
  to authenticated;

-- This is the existing exact-project Files reader with three additive facts:
-- a strict provenance filter applied before keyset pagination, truthful
-- per-item move authority, and a separate read-only Research projection.
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
  item_move_manager_scope boolean;
  folder_id_value uuid;
  page_size integer := 50;
  search_value text := '';
  entity_types_value text[] := array['media', 'task'];
  media_kinds_value text[] := array[]::text[];
  artifact_classes_value text[] := array[]::text[];
  task_statuses_value text[] := array[]::text[];
  cursor_position bigint;
  cursor_type text;
  cursor_id uuid;
  folders_value jsonb;
  current_folder_value jsonb;
  items_value jsonb;
  research_artifacts_value jsonb := '[]'::jsonb;
  research_scope_value text := 'none';
  has_more boolean;
  next_cursor_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'folder_id', 'page_size', 'search',
    'entity_types', 'media_kinds', 'artifact_classes', 'task_statuses',
    'cursor'
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
  item_move_manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
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

  if p_payload ? 'artifact_classes' then
    if jsonb_typeof(p_payload -> 'artifact_classes') <> 'array'
       or jsonb_array_length(p_payload -> 'artifact_classes')
         not between 1 and 3
       or exists (
         select 1
         from jsonb_array_elements(p_payload -> 'artifact_classes') item(value)
         where jsonb_typeof(item.value) <> 'string'
            or item.value #>> '{}' not in (
              'source', 'generated_output', 'unclassified'
            )
       )
       or (
         select count(*) <> count(distinct item.value #>> '{}')
         from jsonb_array_elements(p_payload -> 'artifact_classes') item(value)
       ) then
      raise exception using
        errcode = '22023', message = 'workspace_artifact_classes_invalid';
    end if;
    select array_agg(item.value order by item.value)
      into artifact_classes_value
    from jsonb_array_elements_text(
      p_payload -> 'artifact_classes'
    ) item(value);
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

  research_artifacts_value := content_factory_private
    .workspace_research_artifacts_projection(
      organization_id, project_id_value, user_id
    );
  research_scope_value := case
    when actor_role in ('owner', 'admin', 'producer', 'reviewer') then 'project'
    when actor_role = 'operator'
      and content_factory_private.qualified_operator_project_research_allowed(
        organization_id, project_id_value, user_id
      ) then 'own'
    else 'none'
  end;

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
        'can_move', item_move_manager_scope
          or coalesce(media.owner_id = user_id, false),
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
        cardinality(artifact_classes_value) = 0
        or media.artifact_class = any(artifact_classes_value)
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
        'can_move', item_move_manager_scope
          or coalesce(task.assignee_id = user_id, false),
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
    'research_artifacts', research_artifacts_value,
    'capabilities', jsonb_build_object(
      'manage_folders', folder_manage_scope,
      'move_items', true,
      'shared_project_read', true,
      'research_artifacts', jsonb_build_object(
        'read_only', true,
        'scope', research_scope_value
      )
    ),
    '_meta', jsonb_build_object(
      'page_size', page_size,
      'cap', 100,
      'has_more', coalesce(has_more, false),
      'next_cursor', next_cursor_value,
      'cursor_mode', 'position_type_id',
      'research_artifacts_cap', 50
    )
  );
end;
$$;

revoke all on function public.creator_workspace_browser(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_workspace_browser(jsonb)
  to authenticated;

comment on function
  content_factory_private.workspace_research_artifacts_projection(
    uuid, uuid, uuid
  ) is
  'Read-only exact-project Files projection of Research run/receipt/decision IDs, statuses, timestamps and deep links; never exposes Research content or a synthetic folder.';
comment on function public.creator_workspace_browser(jsonb) is
  'Exact-project Files reader with pre-pagination media provenance filtering, truthful move authority and a separate read-only Research projection.';
comment on function public.creator_project_media(jsonb) is
  'Exact-project single-media reader; Files is a read-only deep-link surface while Generation and Review preserve their mature contract.';

notify pgrst, 'reload schema';

commit;
