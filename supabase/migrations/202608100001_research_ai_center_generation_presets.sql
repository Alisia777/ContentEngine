begin;

-- Close the durable Research -> AI Center -> Generation loop without making
-- AI advice mandatory.  The AI Center keeps immutable material/analysis
-- snapshots visible after a human decision, recommendation lookup ranks the
-- currently selected platform instead of filtering other useful variants out,
-- and an applied recommendation can be bound append-only to an exact
-- generation-spec version.

create or replace function content_factory_private.ai_research_source_snapshot(
  p_organization_id uuid,
  p_run_id uuid
)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(jsonb_agg(
    jsonb_strip_nulls(jsonb_build_object(
      'source_id', source.id,
      'source_type', source.source_type,
      'title', source.title,
      'source_url', source.source_url,
      'trust_level', source.trust_level,
      'published_at', source.published_at,
      'fetched_at', source.fetched_at,
      'media', case when media.id is not null then jsonb_strip_nulls(
        jsonb_build_object(
          'media_object_id', media.id,
          'project_id', media.project_id,
          'kind', coalesce(nullif(media.metadata ->> 'kind', ''),
                           source.source_type),
          'mime_type', media.mime_type,
          'filename', coalesce(
            nullif(media.metadata ->> 'filename', ''),
            nullif(media.metadata ->> 'original_filename', ''),
            source.title
          ),
          'status', media.status,
          'has_private_preview', media.status = 'ready'
        )
      ) else null end,
      'analysis', analysis_event.analysis,
      'analysis_version', analysis_event.analysis_version,
      'analysis_origin', analysis_event.origin,
      'analysis_created_at', analysis_event.created_at
    )) order by source.created_at, source.id
  ), '[]'::jsonb)
  from content_factory.product_research_sources source
  left join content_factory.media_objects media
    on media.organization_id = source.organization_id
   and media.id = source.media_object_id
  left join lateral (
    select ledger.id
    from content_factory.research_category_source_ledger ledger
    where ledger.organization_id = source.organization_id
      and ledger.run_id = source.run_id
      and ledger.source_id = source.id
    order by ledger.registered_at desc, ledger.id desc
    limit 1
  ) ledger on true
  left join lateral (
    select event.analysis, event.analysis_version, event.origin,
           event.created_at
    from content_factory.research_source_analysis_events event
    where event.organization_id = source.organization_id
      and event.source_ledger_id = ledger.id
    order by event.analysis_version desc, event.id desc
    limit 1
  ) analysis_event on true
  where source.organization_id = p_organization_id
    and source.run_id = p_run_id
$$;

revoke all on function
  content_factory_private.ai_research_source_snapshot(uuid, uuid)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_generation_preset(
    p_product_category text,
    p_recommendation jsonb
  )
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  recommendation_value jsonb := coalesce(p_recommendation, '{}'::jsonb);
  platform_value text;
  mode_value text;
  format_value text;
  duration_value integer;
  raw_duration text;
begin
  if jsonb_typeof(recommendation_value) is distinct from 'object' then
    return '{}'::jsonb;
  end if;

  platform_value := lower(btrim(coalesce(
    recommendation_value ->> 'platform', ''
  )));
  platform_value := case platform_value
    when 'instagram_reels' then 'instagram'
    when 'reels' then 'instagram'
    when 'youtube_shorts' then 'youtube'
    when 'shorts' then 'youtube'
    when 'vk_clips' then 'vk'
    when 'vk clips' then 'vk'
    else platform_value
  end;
  if platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram',
    'wildberries'
  ) then
    platform_value := '';
  end if;

  mode_value := lower(btrim(coalesce(
    recommendation_value ->> 'recommended_generation_mode',
    recommendation_value ->> 'generation_mode',
    recommendation_value ->> 'model',
    ''
  )));
  mode_value := case mode_value
    when 'seedance2_fast' then 'real_seedance'
    when 'seedance' then 'real_seedance'
    when 'ugc_video' then 'real_seedance'
    when 'gen4_turbo' then 'real_gen4'
    when 'gen4' then 'real_gen4'
    when 'product_animation' then 'real_gen4'
    when 'seedream5_lite' then 'real_photo'
    when 'seedream' then 'real_photo'
    when 'photo' then 'real_photo'
    else mode_value
  end;
  if mode_value not in ('mock', 'real_seedance', 'real_gen4', 'real_photo') then
    mode_value := '';
  end if;

  raw_duration := btrim(coalesce(
    recommendation_value ->> 'duration_seconds',
    recommendation_value ->> 'duration',
    ''
  ));
  if mode_value = 'real_gen4'
     and raw_duration ~ '^[0-9]{1,2}$'
     and raw_duration::integer in (2, 5, 8, 10) then
    duration_value := raw_duration::integer;
  elsif mode_value = 'real_seedance'
     and raw_duration ~ '^[0-9]{1,2}$'
     and raw_duration::integer in (4, 8, 12, 15) then
    duration_value := raw_duration::integer;
  elsif mode_value = 'real_seedance' then
    duration_value := 8;
  elsif mode_value = 'real_gen4' then
    duration_value := 5;
  elsif mode_value = 'real_photo' then
    duration_value := 0;
  else
    duration_value := null;
  end if;

  format_value := btrim(coalesce(
    recommendation_value ->> 'format',
    recommendation_value ->> 'aspect_ratio',
    ''
  ));
  if mode_value = 'real_seedance' then
    format_value := '9:16';
  elsif mode_value = 'real_photo' then
    format_value := '1:1';
  elsif format_value not in ('9:16', '16:9', '1:1') then
    format_value := case
      when platform_value in ('wildberries', 'ozon') then '1:1'
      when platform_value <> '' or mode_value = 'real_gen4'
        then '9:16'
      else ''
    end;
  end if;

  return jsonb_strip_nulls(jsonb_build_object(
    'product_category', p_product_category,
    'platform', nullif(platform_value, ''),
    'generation_mode', nullif(mode_value, ''),
    'duration_seconds', duration_value,
    'format', nullif(format_value, '')
  ));
end;
$$;

revoke all on function
  content_factory_private.ai_research_generation_preset(text, jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_ai_research_training_queue(
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
  organization_id_value uuid;
  project_id_value uuid;
  category_value text;
  limit_value integer := 20;
  queue_value jsonb := '[]'::jsonb;
  learned_value jsonb := '[]'::jsonb;
  actor_role_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'product_category', 'limit'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'ai_research_training_queue_payload_invalid';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  actor_role_value := content_factory_private.membership_role(
    organization_id_value, true, null
  );
  if p_payload ? 'project_id' then
    project_id_value := content_factory_private.require_uuid(
      p_payload,
      'project_id'
    );
    perform content_factory_private.require_workspace_project(
      organization_id_value,
      project_id_value
    );
  end if;
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number'
       or coalesce(p_payload ->> 'limit', '') !~ '^[0-9]{1,2}$'
       or (p_payload ->> 'limit')::integer not between 1 and 50 then
      raise exception using
        errcode = '22023',
        message = 'ai_research_training_queue_limit_invalid';
    end if;
    limit_value := (p_payload ->> 'limit')::integer;
  end if;

  select coalesce(jsonb_agg(item.payload order by item.event_cursor desc),
                  '[]'::jsonb)
  into queue_value
  from (
    select receipt.event_cursor, jsonb_strip_nulls(jsonb_build_object(
      'receipt_id', receipt.id,
      'receipt_hash', receipt.receipt_hash,
      'project_id', receipt.project_id,
      'project_name', project.name,
      'run_id', receipt.run_id,
      'draft_id', receipt.draft_id,
      'product_id', run.product_id,
      'product_category', receipt.product_category,
      'product_name', product.title,
      'product_sku', coalesce(run.input ->> 'sku', ''),
      'research_title', draft.title,
      'research_summary', run.summary,
      'forecast', forecast.payload,
      'received_at', receipt.received_at,
      'source_count', receipt.source_count,
      'legacy_decision', disposition.decision,
      'review_state', case
        when disposition.decision = 'approve'
          then 'approved_waiting_for_learning_selection'
        else 'awaiting_human_review'
      end,
      'analysis', jsonb_build_object(
        'category_analysis', coalesce(
          draft.brief -> 'category_analysis', '{}'::jsonb
        ),
        'competitor_analysis', coalesce(
          draft.brief -> 'competitor_analysis', '{}'::jsonb
        ),
        'trend_analysis', coalesce(
          draft.brief -> 'trend_analysis', '{}'::jsonb
        ),
        'guidance', coalesce(draft.brief -> 'guidance', '{}'::jsonb)
      ),
      'creative_brief', jsonb_build_object(
        'audience', coalesce(draft.brief -> 'audience', '[]'::jsonb),
        'pains', coalesce(draft.brief -> 'pains', '[]'::jsonb),
        'objections', coalesce(draft.brief -> 'objections', '[]'::jsonb),
        'claims', coalesce(draft.brief -> 'claims', '[]'::jsonb),
        'facts', coalesce(draft.brief -> 'facts', '[]'::jsonb),
        'creative_potential', coalesce(
          draft.brief -> 'creative_potential', '{}'::jsonb
        )
      ),
      'scenarios', coalesce(draft.brief -> 'scenarios', '[]'::jsonb),
      'sources', content_factory_private.ai_research_source_snapshot(
        receipt.organization_id, receipt.run_id
      ),
      'deep_link', '#/workspace/research?project_id='
        || receipt.project_id::text || '&run=' || receipt.run_id::text,
      'requires_human_selection', true,
      'will_create_editable_recommendations', true
    )) as payload
    from content_factory.ai_research_evidence_receipts receipt
    join content_factory.product_research_runs run
      on run.organization_id = receipt.organization_id
     and run.id = receipt.run_id
     and run.project_id = receipt.project_id
     and run.status = 'completed'
    join content_factory.workspace_folders project
      on project.organization_id = receipt.organization_id
     and project.id = receipt.project_id
     and project.kind = 'project'
    join content_factory.products product
      on product.organization_id = run.organization_id
     and product.id = run.product_id
    join content_factory.creative_brief_drafts draft
      on draft.organization_id = receipt.organization_id
     and draft.id = receipt.draft_id
     and draft.run_id = receipt.run_id
    left join content_factory.ai_research_evidence_dispositions disposition
      on disposition.organization_id = receipt.organization_id
     and disposition.receipt_id = receipt.id
    left join lateral (
      select jsonb_strip_nulls(jsonb_build_object(
        'id', value.id,
        'kind', value.forecast_kind,
        'score', value.score,
        'confidence', value.confidence,
        'factors', value.factors,
        'limitations', value.limitations,
        'created_at', value.created_at
      )) as payload
      from content_factory.creative_forecasts value
      where value.organization_id = receipt.organization_id
        and value.run_id = receipt.run_id
        and value.draft_id = receipt.draft_id
      order by value.created_at desc, value.id desc
      limit 1
    ) forecast on true
    where receipt.organization_id = organization_id_value
      and (
        project_id_value is null
        or receipt.project_id = project_id_value
      )
      and receipt.product_category = category_value
      and receipt.status = 'awaiting_human_review'
      and coalesce(disposition.decision, 'approve') <> 'reject'
      and not exists (
        select 1
        from content_factory.ai_research_learning_selections selection
        where selection.organization_id = receipt.organization_id
          and selection.receipt_id = receipt.id
      )
    order by receipt.event_cursor desc, receipt.id desc
    limit limit_value
  ) item;

  select coalesce(jsonb_agg(item.payload order by item.event_cursor desc),
                  '[]'::jsonb)
  into learned_value
  from (
    select selection.event_cursor, jsonb_strip_nulls(jsonb_build_object(
      'selection_id', selection.id,
      'selection_hash', selection.selection_hash,
      'receipt_id', selection.receipt_id,
      'receipt_hash', selection.receipt_hash,
      'project_id', selection.project_id,
      'project_name', project.name,
      'run_id', selection.run_id,
      'draft_id', selection.draft_id,
      'product_id', selection.product_id,
      'product_category', selection.product_category,
      'product_name', selection.product_name,
      'product_sku', selection.product_sku,
      'decision', selection.decision,
      'selected_insight_keys', to_jsonb(selection.selected_insight_keys),
      'selected_scenario_positions',
        to_jsonb(selection.selected_scenario_positions),
      'analysis_snapshot', selection.analysis_snapshot,
      'source_snapshot', selection.source_snapshot,
      'material_snapshot',
        content_factory_private.ai_research_source_snapshot(
          selection.organization_id, selection.run_id
        ),
      'research_summary', run.summary,
      'forecast', forecast.payload,
      'recommendations', selection.recommendations,
      'operator_notes', selection.operator_notes,
      'selected_by', selection.selected_by,
      'selected_at', selection.selected_at,
      'event_cursor', selection.event_cursor,
      'deep_link', '#/workspace/research?project_id='
        || selection.project_id::text || '&run=' || selection.run_id::text,
      'affects_recommendations', selection.decision = 'approve',
      'recommendations_are_editable', true,
      'raw_research_enters_prompt_automatically', false
    )) as payload
    from content_factory.ai_research_learning_selections selection
    join content_factory.product_research_runs run
      on run.organization_id = selection.organization_id
     and run.id = selection.run_id
     and run.project_id = selection.project_id
    join content_factory.workspace_folders project
      on project.organization_id = selection.organization_id
     and project.id = selection.project_id
     and project.kind = 'project'
    left join lateral (
      select jsonb_strip_nulls(jsonb_build_object(
        'id', value.id,
        'kind', value.forecast_kind,
        'score', value.score,
        'confidence', value.confidence,
        'factors', value.factors,
        'limitations', value.limitations,
        'created_at', value.created_at
      )) as payload
      from content_factory.creative_forecasts value
      where value.organization_id = selection.organization_id
        and value.run_id = selection.run_id
        and value.draft_id = selection.draft_id
      order by value.created_at desc, value.id desc
      limit 1
    ) forecast on true
    where selection.organization_id = organization_id_value
      and (
        project_id_value is null
        or selection.project_id = project_id_value
      )
      and selection.product_category = category_value
    order by selection.event_cursor desc, selection.id desc
    limit limit_value
  ) item;

  return jsonb_build_object(
    'ok', true,
    'version', 'ai-research-training-queue-v2',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'product_category', category_value,
    'queue', queue_value,
    'learned', learned_value,
    'capabilities', jsonb_build_object(
      'can_read', true,
      'can_decide', actor_role_value in ('owner', 'admin', 'producer'),
      'can_edit_recommendations',
        actor_role_value in ('owner', 'admin', 'producer')
    ),
    'contract', jsonb_build_object(
      'human_selection_required', true,
      'recommendations_are_editable', true,
      'learned_snapshots_are_durable', true,
      'unreviewed_research_affects_generation', false,
      'raw_research_enters_prompt_automatically', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function public.creator_ai_research_training_queue(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_ai_research_training_queue(jsonb)
  to service_role;

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
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id_value uuid;
  project_id_value uuid;
  category_value text;
  product_name_value text := '';
  sku_value text := '';
  platform_value text := '';
  requested_platform_value text := '';
  limit_value integer := 3;
  recommendations_value jsonb := '[]'::jsonb;
  exact_match_count integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'product_category', 'product_name',
    'sku', 'platform', 'limit'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'generation_research_recommendations_payload_invalid';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  product_name_value := left(
    btrim(coalesce(p_payload ->> 'product_name', '')), 300
  );
  sku_value := left(btrim(coalesce(p_payload ->> 'sku', '')), 160);
  requested_platform_value := lower(left(
    btrim(coalesce(p_payload ->> 'platform', '')), 40
  ));
  platform_value := case requested_platform_value
    when 'instagram_reels' then 'instagram'
    when 'youtube_shorts' then 'youtube'
    when 'vk_clips' then 'vk'
    when 'gen4_turbo' then ''
    when 'seedance2_fast' then ''
    when 'seedream5_lite' then ''
    else requested_platform_value
  end;
  if platform_value <> '' and platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram',
    'wildberries', 'ozon'
  ) then
    raise exception using
      errcode = '22023',
      message = 'generation_research_recommendations_platform_invalid';
  end if;
  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number'
       or coalesce(p_payload ->> 'limit', '') !~ '^[1-3]$' then
      raise exception using
        errcode = '22023',
        message = 'generation_research_recommendations_limit_invalid';
    end if;
    limit_value := (p_payload ->> 'limit')::integer;
  end if;

  with candidates as (
    select
      selection.id as selection_id,
      selection.selection_hash,
      selection.receipt_id,
      selection.run_id,
      selection.draft_id,
      selection.product_id,
      selection.product_name as source_product_name,
      selection.product_sku as source_product_sku,
      selection.selected_at,
      selection.event_cursor,
      recommendation.value as recommendation,
      case
        when coalesce(recommendation.value ->> 'position', '') ~ '^[1-3]$'
          then (recommendation.value ->> 'position')::smallint
        else recommendation.ordinality::smallint
      end as recommendation_position,
      case
        when sku_value <> ''
         and lower(selection.product_sku) = lower(sku_value) then 3
        when product_name_value <> ''
         and lower(selection.product_name) = lower(product_name_value) then 2
        else 1
      end as match_rank,
      case when platform_value <> '' and lower(coalesce(
        recommendation.value ->> 'platform', ''
      )) = platform_value then 1 else 0 end as platform_rank
    from content_factory.ai_research_learning_selections selection
    cross join lateral jsonb_array_elements(
      selection.recommendations
    ) with ordinality recommendation(value, ordinality)
    where selection.organization_id = organization_id_value
      and selection.project_id = project_id_value
      and selection.product_category = category_value
      and selection.decision = 'approve'
  ), bounded as (
    select *
    from candidates
    order by match_rank desc, platform_rank desc, selected_at desc,
             event_cursor desc, selection_id desc,
             recommendation_position asc
    limit limit_value
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'selection_id', candidate.selection_id,
    'selection_hash', candidate.selection_hash,
    'receipt_id', candidate.receipt_id,
    'run_id', candidate.run_id,
    'draft_id', candidate.draft_id,
    'product_id', candidate.product_id,
    'source_product_name', candidate.source_product_name,
    'source_product_sku', candidate.source_product_sku,
    'recommendation_position', candidate.recommendation_position,
    'scope_match', case candidate.match_rank
      when 3 then 'exact_sku'
      when 2 then 'exact_product'
      else 'category'
    end,
    'platform_match', candidate.platform_rank = 1,
    'can_auto_apply', candidate.match_rank >= 2,
    'preset', content_factory_private.ai_research_generation_preset(
      category_value, candidate.recommendation
    ),
    'recommendation', candidate.recommendation,
    'selected_at', candidate.selected_at,
    'event_cursor', candidate.event_cursor
  ) order by candidate.match_rank desc, candidate.platform_rank desc,
             candidate.selected_at desc, candidate.recommendation_position),
  '[]'::jsonb),
  count(*) filter (where candidate.match_rank >= 2)
  into recommendations_value, exact_match_count
  from bounded candidate;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-research-recommendations-v2',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'product_category', category_value,
    'requested_product_name', product_name_value,
    'requested_sku', sku_value,
    'requested_platform', platform_value,
    'recommendations', recommendations_value,
    'auto_apply_available', exact_match_count > 0,
    'contract', jsonb_build_object(
      'recommendations_are_editable', true,
      'presets_are_advisory', true,
      'cross_platform_fallback', true,
      'human_edits_are_preserved', true,
      'spend_confirmation_is_never_applied', true,
      'unreviewed_research_affects_generation', false,
      'raw_research_enters_prompt_automatically', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  public.contentengine_generation_research_recommendations(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_generation_research_recommendations(jsonb)
  to authenticated, service_role;

create table if not exists
  content_factory.generation_spec_ai_research_bindings (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    project_id uuid not null,
    spec_id uuid not null,
    spec_version integer not null check (spec_version between 1 and 100000),
    spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
    selection_id uuid not null,
    selection_hash text not null check (selection_hash ~ '^[0-9a-f]{64}$'),
    recommendation_position smallint not null
      check (recommendation_position between 1 and 3),
    recommendation_snapshot jsonb not null check (
      jsonb_typeof(recommendation_snapshot) = 'object'
      and length(recommendation_snapshot::text) <= 65536
      and not content_factory_private.research_analysis_has_forbidden_keys(
        recommendation_snapshot
      )
    ),
    recommendation_hash text not null check (
      recommendation_hash ~ '^[0-9a-f]{64}$'
    ),
    applied_by uuid not null,
    applied_at timestamptz not null default clock_timestamp(),
    unique (organization_id, spec_id, spec_version),
    unique (organization_id, spec_id, spec_hash),
    unique (organization_id, id),
    foreign key (organization_id, project_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, spec_id, spec_version, spec_hash)
      references content_factory.generation_spec_versions(
        organization_id, spec_id, spec_version, spec_hash
      ),
    foreign key (organization_id, selection_id)
      references content_factory.ai_research_learning_selections(
        organization_id, id
      ),
    foreign key (organization_id, applied_by)
      references content_factory.memberships(organization_id, profile_id)
  );

create index if not exists generation_spec_ai_research_selection_idx
  on content_factory.generation_spec_ai_research_bindings (
    organization_id, selection_id, applied_at desc
  );

alter table content_factory.generation_spec_ai_research_bindings
  enable row level security;
revoke all on content_factory.generation_spec_ai_research_bindings
  from public, anon, authenticated;
grant all on content_factory.generation_spec_ai_research_bindings
  to service_role;

drop trigger if exists generation_spec_ai_research_binding_append_only
  on content_factory.generation_spec_ai_research_bindings;
create trigger generation_spec_ai_research_binding_append_only
before update or delete
  on content_factory.generation_spec_ai_research_bindings
for each row execute function
  content_factory_private.reject_research_ai_handoff_mutation();

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
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id_value uuid;
  project_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  selection_id_value uuid;
  position_value smallint;
  product_id_value uuid;
  spec_row content_factory.generation_spec_versions%rowtype;
  selection_row content_factory.ai_research_learning_selections%rowtype;
  recommendation_value jsonb;
  existing_row content_factory.generation_spec_ai_research_bindings%rowtype;
  binding_row content_factory.generation_spec_ai_research_bindings%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'spec_id', 'spec_version',
    'spec_hash', 'selection_id', 'recommendation_position', 'confirmation'
  ]::text[] <> '{}'::jsonb
     or not (p_payload ?& array[
       'project_id', 'spec_id', 'spec_version', 'spec_hash',
       'selection_id', 'recommendation_position', 'confirmation'
     ]::text[]) then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_payload_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'confirmation') <> 'boolean'
     or (p_payload ->> 'confirmation')::boolean is not true then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_confirmation_required';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  selection_id_value := content_factory_private.require_uuid(
    p_payload, 'selection_id'
  );
  if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
     or coalesce(p_payload ->> 'spec_version', '') !~ '^[0-9]{1,6}$'
     or (p_payload ->> 'spec_version')::integer not between 1 and 100000 then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_version_invalid';
  end if;
  spec_version_value := (p_payload ->> 'spec_version')::integer;
  spec_hash_value := lower(btrim(p_payload ->> 'spec_hash'));
  if spec_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_hash_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'recommendation_position') <> 'number'
     or coalesce(p_payload ->> 'recommendation_position', '') !~ '^[1-3]$' then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_position_invalid';
  end if;
  position_value := (p_payload ->> 'recommendation_position')::smallint;

  product_id_value :=
    content_factory_private.require_generation_spec_project_v49(
      organization_id_value,
      project_id_value,
      spec_id_value,
      spec_version_value,
      spec_hash_value,
      null
    );
  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = spec_version_value
    and version.spec_hash = spec_hash_value
  for share;

  select selection.* into selection_row
  from content_factory.ai_research_learning_selections selection
  where selection.organization_id = organization_id_value
    and selection.id = selection_id_value
  for share;
  if selection_row.id is null
     or selection_row.project_id <> project_id_value
     or selection_row.product_category <> spec_row.product_category
     or selection_row.decision <> 'approve'
     or not (position_value = any(selection_row.selected_scenario_positions)) then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_ai_research_binding_scope_mismatch';
  end if;

  select candidate.value into recommendation_value
  from jsonb_array_elements(selection_row.recommendations) candidate(value)
  where case
    when coalesce(candidate.value ->> 'position', '') ~ '^[1-3]$'
      then (candidate.value ->> 'position')::smallint
    else 0::smallint
  end = position_value
  limit 1;
  if jsonb_typeof(recommendation_value) is distinct from 'object' then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_ai_research_binding_recommendation_missing';
  end if;

  select binding.* into existing_row
  from content_factory.generation_spec_ai_research_bindings binding
  where binding.organization_id = organization_id_value
    and binding.spec_id = spec_id_value
    and binding.spec_version = spec_version_value;
  if existing_row.id is not null then
    if existing_row.spec_hash = spec_hash_value
       and existing_row.selection_id = selection_id_value
       and existing_row.recommendation_position = position_value then
      binding_row := existing_row;
    else
      raise exception using
        errcode = '23505',
        message = 'generation_spec_ai_research_binding_conflict';
    end if;
  else
    insert into content_factory.generation_spec_ai_research_bindings (
      organization_id, project_id, spec_id, spec_version, spec_hash,
      selection_id, selection_hash, recommendation_position,
      recommendation_snapshot, recommendation_hash, applied_by
    ) values (
      organization_id_value, project_id_value, spec_id_value,
      spec_version_value, spec_hash_value, selection_id_value,
      selection_row.selection_hash, position_value, recommendation_value,
      content_factory_private.json_hash(recommendation_value), user_id
    ) returning * into binding_row;
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-spec-ai-research-binding-v1',
    'binding', jsonb_build_object(
      'id', binding_row.id,
      'project_id', binding_row.project_id,
      'spec_id', binding_row.spec_id,
      'spec_version', binding_row.spec_version,
      'spec_hash', binding_row.spec_hash,
      'selection_id', binding_row.selection_id,
      'selection_hash', binding_row.selection_hash,
      'recommendation_position', binding_row.recommendation_position,
      'recommendation_hash', binding_row.recommendation_hash,
      'scope_match', case
        when selection_row.product_id = product_id_value then 'exact_product'
        else 'category'
      end,
      'applied_by', binding_row.applied_by,
      'applied_at', binding_row.applied_at
    ),
    'contract', jsonb_build_object(
      'append_only', true,
      'human_editable_spec_preserved', true,
      'provider_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  public.contentengine_bind_generation_spec_ai_research(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_bind_generation_spec_ai_research(jsonb)
  to authenticated, service_role;

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
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id_value uuid;
  project_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  binding_row content_factory.generation_spec_ai_research_bindings%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'spec_id', 'spec_version', 'spec_hash'
  ]::text[] <> '{}'::jsonb
     or not (p_payload ?& array[
       'project_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[]) then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_read_payload_invalid';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
     or coalesce(p_payload ->> 'spec_version', '') !~ '^[0-9]{1,6}$' then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_version_invalid';
  end if;
  spec_version_value := (p_payload ->> 'spec_version')::integer;
  spec_hash_value := lower(btrim(p_payload ->> 'spec_hash'));
  perform content_factory_private.require_generation_spec_project_v49(
    organization_id_value, project_id_value, spec_id_value,
    spec_version_value, spec_hash_value, null
  );

  select binding.* into binding_row
  from content_factory.generation_spec_ai_research_bindings binding
  where binding.organization_id = organization_id_value
    and binding.project_id = project_id_value
    and binding.spec_id = spec_id_value
    and binding.spec_version = spec_version_value
    and binding.spec_hash = spec_hash_value;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-spec-ai-research-binding-v1',
    'binding', case when binding_row.id is null then null else
      jsonb_build_object(
        'id', binding_row.id,
        'selection_id', binding_row.selection_id,
        'selection_hash', binding_row.selection_hash,
        'recommendation_position', binding_row.recommendation_position,
        'recommendation_hash', binding_row.recommendation_hash,
        'applied_by', binding_row.applied_by,
        'applied_at', binding_row.applied_at
      ) end,
    'contract', jsonb_build_object(
      'server_backed', true,
      'provider_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  public.contentengine_generation_spec_ai_research_binding(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_generation_spec_ai_research_binding(jsonb)
  to authenticated, service_role;

comment on function
  public.contentengine_generation_research_recommendations(jsonb) is
  'Returns human-approved project/category recommendations ranked by the current platform preference; cross-platform advisory presets remain visible and editable.';
comment on function
  public.contentengine_bind_generation_spec_ai_research(jsonb) is
  'Append-only binding between one exact generation-spec version and one human-approved AI Center recommendation. No provider or paid call is started.';

notify pgrst, 'reload schema';

commit;
