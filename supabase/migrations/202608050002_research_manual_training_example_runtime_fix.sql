begin;

-- Runtime-safe replacement for the v1 registration core.  The preceding
-- migration installs the public/service RPC boundary and YouTube normalizer;
-- this revision keeps that contract while reading category binding fields into
-- scalar variables rather than mixing a composite row target with scalars.

create or replace function content_factory_private.register_research_training_example(
  p_organization_id uuid,
  p_actor_id uuid,
  p_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  project_id_value uuid;
  requested_run_id uuid;
  run_row content_factory.product_research_runs%rowtype;
  source_row content_factory.product_research_sources%rowtype;
  source_id_value uuid;
  source_content_hash text;
  canonical_url text;
  youtube_video_id text;
  compliance_category_value text;
  market_category_name_value text;
  normalized_market_category text;
  training_role_value text;
  human_summary_value text;
  idempotency_key_value text;
  source_title text;
  replay_value boolean := false;
  binding_id_value uuid;
  binding_category_id_value uuid;
  market_category_canonical_name text;
  market_category_normalized_name text;
  binding_matches boolean := false;
  source_ledger_id uuid;
  analysis_event_id uuid;
  analysis_value jsonb;
  request_hash_value text;
  event_hash_value text;
  lineage_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 32768
     or p_payload - array[
       'project_id', 'run_id', 'source_url', 'compliance_category',
       'market_category_name', 'training_role', 'human_summary',
       'public_source_ack', 'no_exact_copy_ack', 'idempotency_key'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_training_example_payload_invalid';
  end if;

  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  begin
    requested_run_id := nullif(
      btrim(coalesce(p_payload ->> 'run_id', '')), ''
    )::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '22023', message = 'research_training_example_run_invalid';
  end;

  compliance_category_value := lower(
    content_factory_private.require_text(
      p_payload, 'compliance_category', 2, 40
    )
  );
  if compliance_category_value not in (
    'cosmetics', 'baa', 'sports_food', 'food', 'household',
    'apparel', 'electronics', 'other'
  ) then
    raise exception using
      errcode = '22023', message = 'research_training_example_category_invalid';
  end if;

  market_category_name_value := content_factory_private.require_text(
    p_payload, 'market_category_name', 2, 160
  );
  normalized_market_category :=
    content_factory_private.research_market_identity_key(
      market_category_name_value
    );
  if length(normalized_market_category) not between 2 and 160 then
    raise exception using
      errcode = '22023', message = 'research_training_example_market_invalid';
  end if;

  training_role_value := lower(content_factory_private.require_text(
    p_payload, 'training_role', 3, 40
  ));
  if training_role_value not in (
    'reference', 'competitor_mechanic', 'anti_example'
  ) then
    raise exception using
      errcode = '22023', message = 'research_training_example_role_invalid';
  end if;

  human_summary_value := content_factory_private.require_text(
    p_payload, 'human_summary', 20, 1000
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if coalesce((p_payload ->> 'public_source_ack')::boolean, false) is not true
     or coalesce((p_payload ->> 'no_exact_copy_ack')::boolean, false) is not true then
    raise exception using
      errcode = '22023', message = 'research_training_example_ack_required';
  end if;

  youtube_video_id := content_factory_private.research_youtube_video_id(
    content_factory_private.require_text(p_payload, 'source_url', 20, 2048)
  );
  if youtube_video_id is null then
    raise exception using
      errcode = '22023', message = 'research_training_example_youtube_url_invalid';
  end if;
  canonical_url := 'https://www.youtube.com/watch?v=' || youtube_video_id;

  if requested_run_id is not null then
    select run.* into run_row
    from content_factory.product_research_runs run
    where run.organization_id = p_organization_id
      and run.project_id = project_id_value
      and run.id = requested_run_id
    limit 1;
  else
    select run.* into run_row
    from content_factory.product_research_runs run
    where run.organization_id = p_organization_id
      and run.project_id = project_id_value
      and lower(coalesce(run.input ->> 'product_category', ''))
        = compliance_category_value
    order by run.created_at desc, run.id desc
    limit 1;
  end if;
  if run_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_training_example_run_not_found';
  end if;
  if lower(coalesce(run_row.input ->> 'product_category', ''))
       <> compliance_category_value then
    raise exception using
      errcode = '22023', message = 'research_training_example_category_mismatch';
  end if;

  select source.* into source_row
  from content_factory.product_research_sources source
  where source.organization_id = p_organization_id
    and source.run_id = run_row.id
    and (
      source.metadata ->> 'youtube_video_id' = youtube_video_id
      or position(youtube_video_id in coalesce(source.source_url, '')) > 0
    )
  order by source.created_at desc, source.id desc
  limit 1;

  if source_row.id is not null then
    source_id_value := source_row.id;
    source_content_hash := source_row.content_hash;
    replay_value := true;
  else
    source_content_hash := content_factory_private.json_hash(
      jsonb_build_object(
        'version', 'research-training-example-v1',
        'platform', 'youtube',
        'youtube_video_id', youtube_video_id,
        'compliance_category', compliance_category_value,
        'market_category', normalized_market_category,
        'training_role', training_role_value,
        'human_summary', human_summary_value
      )
    );
    source_title := left(
      'YouTube Shorts · ' || market_category_name_value,
      300
    );
    insert into content_factory.product_research_sources (
      organization_id, run_id, product_id, created_by, source_type,
      source_url, media_object_id, title, content_hash, trust_level,
      extracted_facts, metadata, fetched_at, published_at
    ) values (
      p_organization_id, run_row.id, run_row.product_id, p_actor_id,
      'social_video', canonical_url, null, source_title,
      source_content_hash, 'public', '[]'::jsonb,
      jsonb_build_object(
        'schema_version', 'research-training-example-v1',
        'platform', 'youtube',
        'provider_key', 'user_supplied_youtube',
        'model_source_id', 'user:youtube:' || youtube_video_id,
        'youtube_video_id', youtube_video_id,
        'source_format', 'short_vertical_video',
        'training_role', training_role_value,
        'compliance_category', compliance_category_value,
        'market_category_hint', market_category_name_value,
        'human_summary', human_summary_value,
        'public_source_ack', true,
        'exact_copy_forbidden', true,
        'provider_citation_verified', false,
        'provider_call_performed', false,
        'paid_analysis_performed', false,
        'idempotency_key', idempotency_key_value
      ),
      null, null
    )
    returning * into source_row;
    source_id_value := source_row.id;
  end if;

  select binding.id,
         binding.category_id,
         category.canonical_name,
         category.normalized_name
    into binding_id_value,
         binding_category_id_value,
         market_category_canonical_name,
         market_category_normalized_name
  from content_factory.research_product_market_category_bindings binding
  join content_factory.research_market_categories category
    on category.organization_id = binding.organization_id
   and category.id = binding.category_id
   and category.status = 'active'
  where binding.organization_id = p_organization_id
    and binding.product_id = run_row.product_id
  order by binding.binding_version desc, binding.id desc
  limit 1;

  if binding_id_value is not null then
    binding_matches := market_category_normalized_name
      = normalized_market_category
      or exists (
        select 1
        from content_factory.research_market_category_aliases alias
        where alias.organization_id = p_organization_id
          and alias.category_id = binding_category_id_value
          and alias.normalized_alias = normalized_market_category
      );
  end if;

  if binding_matches then
    lineage_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'version', 'research-training-example-lineage-v1',
        'organization_id', p_organization_id,
        'project_id', project_id_value,
        'run_id', run_row.id,
        'source_id', source_id_value,
        'binding_id', binding_id_value,
        'market_category_id', binding_category_id_value,
        'source_content_hash', source_content_hash
      )
    );
    insert into content_factory.research_category_source_ledger (
      organization_id, market_category_id, product_id, binding_id, run_id,
      source_id, source_type, title, source_url, provider_key, platform,
      trust_level, source_identity_key, source_content_hash,
      fetched_at, published_at, registered_by, lineage_hash
    ) values (
      p_organization_id, binding_category_id_value, run_row.product_id,
      binding_id_value, run_row.id, source_id_value, 'social_video',
      coalesce(nullif(source_row.title, ''), 'YouTube Shorts · пример'),
      canonical_url, 'user_supplied_youtube', 'youtube', 'public',
      content_factory_private.research_source_identity_key(
        canonical_url, source_content_hash
      ),
      source_content_hash, source_row.fetched_at, source_row.published_at,
      p_actor_id, lineage_hash_value
    )
    on conflict do nothing
    returning id into source_ledger_id;

    if source_ledger_id is null then
      select ledger.id into source_ledger_id
      from content_factory.research_category_source_ledger ledger
      where ledger.organization_id = p_organization_id
        and ledger.market_category_id = binding_category_id_value
        and ledger.source_content_hash = source_content_hash
      order by ledger.registered_at desc, ledger.id desc
      limit 1;
    end if;

    select event.id into analysis_event_id
    from content_factory.research_source_analysis_events event
    where event.organization_id = p_organization_id
      and event.source_ledger_id = source_ledger_id
    order by event.analysis_version desc, event.id desc
    limit 1;

    if analysis_event_id is null then
      analysis_value := jsonb_build_object(
        'schema_version', 'research-source-interpretation-v1',
        'classification', case training_role_value
          when 'competitor_mechanic' then 'competitor'
          else 'reference'
        end,
        'relevance_score', 70,
        'confidence', 'low',
        'summary', human_summary_value,
        'structural_signal_keys', jsonb_build_array(
          'channel.short_vertical_video'
        ),
        'limitations', jsonb_build_array(
          'Содержимое ролика не прошло автоматический покадровый разбор.',
          'Источник добавлен пользователем как кандидат; точное копирование запрещено.'
        )
      );
      request_hash_value := content_factory_private.json_hash(
        jsonb_build_object(
          'version', 'research-training-example-analysis-request-v1',
          'source_ledger_id', source_ledger_id,
          'analysis', analysis_value
        )
      );
      event_hash_value := content_factory_private.json_hash(
        jsonb_build_object(
          'version', 'research-training-example-analysis-event-v1',
          'source_ledger_id', source_ledger_id,
          'analysis_version', 1,
          'origin', 'human_correction',
          'actor_id', p_actor_id,
          'analysis', analysis_value,
          'request_hash', request_hash_value
        )
      );
      insert into content_factory.research_source_analysis_events (
        organization_id, source_ledger_id, analysis_version,
        parent_event_id, expected_parent_hash, origin, actor_id,
        parser_key, parser_version, analysis, correction_reason,
        request_hash, event_hash, idempotency_key
      ) values (
        p_organization_id, source_ledger_id, 1, null, null,
        'human_correction', p_actor_id, 'manual_youtube_example',
        '2026-08-05.v2', analysis_value,
        'Пользователь добавил публичный ролик как управляемый пример.',
        request_hash_value, event_hash_value,
        'manual-youtube-example:' || source_ledger_id::text || ':v1'
      )
      returning id into analysis_event_id;
    end if;
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-training-example-v2',
    'project_id', project_id_value,
    'run_id', run_row.id,
    'run_status', run_row.status,
    'run_error_code', run_row.error_code,
    'source_id', source_id_value,
    'source_registered', true,
    'replay', replay_value,
    'canonical_url', canonical_url,
    'youtube_video_id', youtube_video_id,
    'compliance_category', compliance_category_value,
    'market_category_hint', market_category_name_value,
    'training_role', training_role_value,
    'category_binding_id', binding_id_value,
    'category_binding_name', market_category_canonical_name,
    'category_binding_matches', binding_matches,
    'source_ledger_id', source_ledger_id,
    'analysis_event_id', analysis_event_id,
    'learning_state', case
      when analysis_event_id is not null then 'linked_pending_human_review'
      else 'registered_pending_category_binding'
    end,
    'provider_call_performed', false,
    'paid_analysis_performed', false,
    'exact_copy_allowed', false
  );
end;
$$;

commit;
