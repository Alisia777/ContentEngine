begin;

-- Keep one project-scoped archive feed.  The immutable launch table is the
-- only provider/model authority for new rows; historical batches deliberately
-- retain NULL metadata instead of being reinterpreted from batch.input or the
-- current catalog.
create or replace function public.creator_generation_archive(
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
  actor_role text;
  team_scope boolean;
  period_value text := '4w';
  status_value text := 'all';
  provider_value text := 'all';
  model_value text := 'all';
  content_kind_value text := 'all';
  selection_source_value text := 'all';
  quality_status_value text := 'all';
  query_value text := '';
  page_size integer := 50;
  cursor_at timestamptz;
  cursor_id uuid;
  period_cutoff timestamptz;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();

  if p_payload - array[
       'organization_id', 'project_id', 'period', 'status', 'provider',
       'model', 'content_kind', 'selection_source', 'quality_status',
       'query', 'page_size', 'cursor'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'generation_archive_payload_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  team_scope := actor_role = any(array[
    'owner', 'admin', 'producer', 'reviewer'
  ]);

  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );

  if p_payload ? 'period' then
    if jsonb_typeof(p_payload -> 'period') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_period_invalid';
    end if;
    period_value := lower(btrim(p_payload ->> 'period'));
  end if;
  if period_value not in ('week', '4w', '12w', 'all') then
    raise exception using
      errcode = '22023', message = 'generation_archive_period_invalid';
  end if;

  if p_payload ? 'status' then
    if jsonb_typeof(p_payload -> 'status') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_status_invalid';
    end if;
    status_value := lower(btrim(p_payload ->> 'status'));
  end if;
  if status_value not in ('all', 'active', 'ready', 'issue') then
    raise exception using
      errcode = '22023', message = 'generation_archive_status_invalid';
  end if;

  if p_payload ? 'provider' then
    if jsonb_typeof(p_payload -> 'provider') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_provider_invalid';
    end if;
    provider_value := lower(btrim(p_payload ->> 'provider'));
  end if;
  if provider_value not in ('all', 'runway', 'google') then
    raise exception using
      errcode = '22023', message = 'generation_archive_provider_invalid';
  end if;

  if p_payload ? 'model' then
    if jsonb_typeof(p_payload -> 'model') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_model_invalid';
    end if;
    model_value := lower(btrim(p_payload ->> 'model'));
  end if;
  if model_value <> 'all'
     and model_value !~ '^[a-z0-9][a-z0-9._-]{0,79}$' then
    raise exception using
      errcode = '22023', message = 'generation_archive_model_invalid';
  end if;

  if p_payload ? 'content_kind' then
    if jsonb_typeof(p_payload -> 'content_kind') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'generation_archive_content_kind_invalid';
    end if;
    content_kind_value := lower(btrim(p_payload ->> 'content_kind'));
  end if;
  if content_kind_value not in ('all', 'photo', 'video') then
    raise exception using
      errcode = '22023',
      message = 'generation_archive_content_kind_invalid';
  end if;

  if p_payload ? 'selection_source' then
    if jsonb_typeof(p_payload -> 'selection_source') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'generation_archive_selection_source_invalid';
    end if;
    selection_source_value :=
      lower(btrim(p_payload ->> 'selection_source'));
  end if;
  if selection_source_value not in (
       'all', 'system_recommendation', 'research_recommendation',
       'performance_recommendation', 'manual_choice',
       'alternative_after_block'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_archive_selection_source_invalid';
  end if;

  if p_payload ? 'quality_status' then
    if jsonb_typeof(p_payload -> 'quality_status') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'generation_archive_quality_status_invalid';
    end if;
    quality_status_value := lower(btrim(p_payload ->> 'quality_status'));
  end if;
  if quality_status_value not in (
       'all', 'accepted', 'needs_revalidation', 'unproven'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_archive_quality_status_invalid';
  end if;

  if p_payload ? 'query' then
    if jsonb_typeof(p_payload -> 'query') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_query_invalid';
    end if;
    query_value := btrim(p_payload ->> 'query');
  end if;
  if length(query_value) > 120 or query_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023', message = 'generation_archive_query_invalid';
  end if;

  if p_payload ? 'page_size' then
    if jsonb_typeof(p_payload -> 'page_size') <> 'number'
       or coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'generation_archive_page_size_invalid';
    end if;
    begin
      page_size := (p_payload ->> 'page_size')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023', message = 'generation_archive_page_size_invalid';
    end;
  end if;
  if page_size not between 1 and 100 then
    raise exception using
      errcode = '22023', message = 'generation_archive_page_size_invalid';
  end if;

  if p_payload ? 'cursor' then
    if jsonb_typeof(p_payload -> 'cursor') <> 'object' then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end if;
    if exists (
      select 1
      from jsonb_object_keys(p_payload -> 'cursor') cursor_key
      where cursor_key <> all(array['at', 'id'])
    ) then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end if;
    if jsonb_typeof(p_payload #> '{cursor,at}') <> 'string'
       or jsonb_typeof(p_payload #> '{cursor,id}') <> 'string'
       or nullif(btrim(coalesce(p_payload #>> '{cursor,at}', '')), '') is null
       or nullif(btrim(coalesce(p_payload #>> '{cursor,id}', '')), '') is null
    then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end if;
    begin
      cursor_at := (p_payload #>> '{cursor,at}')::timestamptz;
      cursor_id := (p_payload #>> '{cursor,id}')::uuid;
    exception
      when invalid_text_representation
        or invalid_datetime_format
        or datetime_field_overflow then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end;
  end if;

  period_cutoff := case period_value
    when 'week' then date_trunc('week', now())
    when '4w' then date_trunc('week', now()) - interval '3 weeks'
    when '12w' then date_trunc('week', now()) - interval '11 weeks'
    else null
  end;

  with candidates as materialized (
    select
      batch.id,
      batch.project_id,
      batch.name,
      batch.mode,
      batch.status,
      batch.total_requested,
      batch.total_created,
      batch.input,
      batch.created_at,
      product.sku,
      product.title as product_name,
      launch.selection_snapshot as generation_selection_snapshot,
      launch.snapshot_version as generation_selection_snapshot_version,
      launch.snapshot_hash as generation_selection_snapshot_hash,
      launch.provider,
      launch.model,
      launch.selection_snapshot ->> 'model_public_label'
        as model_public_label,
      launch.content_kind,
      launch.selection_source,
      launch.quality_status,
      launch.catalog_version,
      launch.pricing_version,
      launch.estimated_cost_minor,
      launch.estimated_credits
    from content_factory.generation_batches batch
    join content_factory.products product
      on product.organization_id = batch.organization_id
     and product.id = batch.product_id
    left join content_factory.generation_job_selection_snapshots launch
      on launch.organization_id = batch.organization_id
     and launch.project_id = batch.project_id
     and launch.batch_id = batch.id
    where batch.organization_id = organization_id
      and batch.project_id = project_id_value
      and batch.archived_at is null
      and (team_scope or batch.created_by = user_id)
      and (period_cutoff is null or batch.created_at >= period_cutoff)
      and (
        status_value = 'all'
        or (
          status_value = 'active'
          and batch.status in ('queued', 'starting', 'submitted', 'processing')
        )
        or (
          status_value = 'ready'
          and batch.status in ('mock_ready', 'succeeded')
        )
        or (
          status_value = 'issue'
          and batch.status in ('failed', 'cancelled')
        )
      )
      and (provider_value = 'all' or launch.provider = provider_value)
      and (model_value = 'all' or lower(launch.model) = model_value)
      and (
        content_kind_value = 'all'
        or launch.content_kind = content_kind_value
      )
      and (
        selection_source_value = 'all'
        or launch.selection_source = selection_source_value
      )
      and (
        quality_status_value = 'all'
        or launch.quality_status = quality_status_value
      )
      and (
        query_value = ''
        or position(
          lower(query_value) in lower(concat_ws(
            ' ', batch.name, batch.id::text, product.sku, product.title,
            launch.model,
            launch.selection_snapshot ->> 'model_public_label'
          ))
        ) > 0
      )
      and (
        cursor_at is null
        or (batch.created_at, batch.id) < (cursor_at, cursor_id)
      )
    order by batch.created_at desc, batch.id desc
    limit page_size + 1
  ),
  page as materialized (
    select candidate.*
    from candidates candidate
    order by candidate.created_at desc, candidate.id desc
    limit page_size
  ),
  page_stats as (
    select count(*) > page_size as has_more
    from candidates
  ),
  last_row as (
    select page.created_at, page.id
    from page
    order by page.created_at asc, page.id asc
    limit 1
  )
  select jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'batches', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', page.id,
        'public_id', page.id,
        'project_id', page.project_id,
        'name', page.name,
        'sku', page.sku,
        'product_name', page.product_name,
        'mode', page.mode,
        'status', page.status,
        'total_requested', page.total_requested,
        'total_created', page.total_created,
        'total_accepted', page.total_created,
        'parameters', page.input,
        'provider', page.provider,
        'model', page.model,
        'model_public_label', page.model_public_label,
        'content_kind', page.content_kind,
        'selection_source', page.selection_source,
        'quality_status', page.quality_status,
        'catalog_version', page.catalog_version,
        'pricing_version', page.pricing_version,
        'estimated_cost_minor', page.estimated_cost_minor,
        'estimated_credits', page.estimated_credits,
        'generation_selection_snapshot', page.generation_selection_snapshot,
        'generation_selection_snapshot_version',
          page.generation_selection_snapshot_version,
        'generation_selection_snapshot_hash',
          page.generation_selection_snapshot_hash,
        'created_at', page.created_at,
        '_cursor', jsonb_build_object(
          'at', page.created_at,
          'id', page.id
        )
      ) order by page.created_at desc, page.id desc)
      from page
    ), '[]'::jsonb),
    '_meta', jsonb_build_object(
      'page_size', page_size,
      'has_more', page_stats.has_more,
      'next_cursor', case
        when page_stats.has_more then jsonb_build_object(
          'at', last_row.created_at,
          'id', last_row.id
        )
        else null
      end,
      'period', period_value,
      'status', status_value,
      'provider', provider_value,
      'model', model_value,
      'content_kind', content_kind_value,
      'selection_source', selection_source_value,
      'quality_status', quality_status_value,
      'query', query_value,
      'cursor_mode', 'keyset_created_at_id'
    )
  )
  into result
  from page_stats
  left join last_row on true;

  return result;
end;
$$;

revoke all on function public.creator_generation_archive(jsonb)
  from public, anon;
grant execute on function public.creator_generation_archive(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
