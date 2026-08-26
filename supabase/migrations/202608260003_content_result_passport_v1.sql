begin;
-- 202608260003_content_result_passport_v1
--
-- «Паспорт ролика» (контур №2 ТЗ 26.08): одна серверная read-модель, которую
-- читают все экраны. Два RPC: реестр паспортов проекта (список готовых
-- роликов с кратким срезом) и полный паспорт одного ролика (продукт, ТЗ,
-- материалы, производство, деньги, публикации, метрики, хронология).
-- Ничего не пишет, провайдера не зовёт, денег не трогает. Гипотез в базе ещё
-- нет (контур №3) — секция отдаётся null и честно числится в missing_sections.
-- Метрики отдаются числителями/знаменателями; формулы и проценты считает
-- экран. Зрелость снимка: observed_at >= published_at + 72 часа.

create or replace function public.creator_content_passport_registry(
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
  limit_value integer;
  passports_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
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
  limit_value := least(
    greatest(coalesce((p_payload ->> 'limit')::integer, 100), 1), 200
  );

  select coalesce(
      jsonb_agg(row_value order by created_at_value desc), '[]'::jsonb
    )
    into passports_value
  from (
    select
      media.created_at as created_at_value,
      jsonb_build_object(
        'media_id', media.id,
        'media_status', media.status,
        'original_filename',
          coalesce(media.metadata ->> 'original_filename', media.object_name),
        'created_at', media.created_at,
        'generation_job_id', job.id,
        'job_status', job.status,
        'strategy_id', coalesce(
          media.metadata ->> 'strategy_id',
          strategy_snapshot.strategy_snapshot -> 'strategy' ->> 'strategy_id'
        ),
        'provider', job.provider,
        'model', media.metadata ->> 'model',
        'duration_seconds', media.metadata -> 'duration_seconds',
        'ratio', media.metadata ->> 'ratio',
        'estimated_cost_minor', job.estimated_cost_minor,
        'actual_cost_minor', job.actual_cost_minor,
        'product', case
          when product.id is null then null
          else jsonb_build_object(
            'id', product.id,
            'sku', product.sku,
            'title', product.title
          )
        end,
        'placements_count', coalesce(placement_facts.total_count, 0),
        'published_count', coalesce(placement_facts.published_count, 0),
        'latest_metrics', placement_facts.latest_metrics,
        'has_mature_metrics',
          coalesce(placement_facts.has_mature_metrics, false)
      ) as row_value
    from content_factory.media_objects media
    join content_factory.generation_jobs job
      on job.organization_id = media.organization_id
      and job.id = (media.metadata ->> 'generation_job_id')::uuid
    left join content_factory.products product
      on product.organization_id = media.organization_id
      and product.id = job.product_id
    left join content_factory.generation_job_strategy_snapshots
      strategy_snapshot
      on strategy_snapshot.organization_id = media.organization_id
      and strategy_snapshot.generation_job_id = job.id
    left join lateral (
      select
        count(*) as total_count,
        count(*) filter (where placement.status = 'published')
          as published_count,
        bool_or(
          placement.published_at is not null
          and latest.observed_at >= placement.published_at
            + interval '72 hours'
        ) as has_mature_metrics,
        case
          when count(latest.placement_id) = 0 then null
          else jsonb_build_object(
            'views', sum(latest.views),
            'clicks', sum(latest.clicks),
            'orders', sum(latest.orders),
            'revenue_minor', sum(latest.revenue_minor),
            'observed_at', max(latest.observed_at)
          )
        end as latest_metrics
      from content_factory.placements placement
      left join lateral (
        select snapshot.placement_id, snapshot.views, snapshot.clicks,
          snapshot.orders, snapshot.revenue_minor, snapshot.observed_at
        from content_factory.metric_snapshots snapshot
        where snapshot.organization_id = placement.organization_id
          and snapshot.placement_id = placement.id
        order by snapshot.observed_at desc
        limit 1
      ) latest on true
      where placement.organization_id = media.organization_id
        and placement.generation_job_id = job.id
    ) placement_facts on true
    where media.organization_id = organization_id
      and media.project_id = project_id_value
      and media.artifact_class = 'generated_output'
      and media.status in ('ready', 'archived')
      and media.metadata ? 'generation_job_id'
    order by media.created_at desc
    limit limit_value
  ) rows;

  return jsonb_build_object(
    'ok', true,
    'version', 'content-passport-registry-v1',
    'project_id', project_id_value,
    'passports', passports_value,
    'count', jsonb_array_length(passports_value),
    'contract', jsonb_build_object(
      'read_only', true,
      'provider_call_started', false,
      'spend_action_started', false
    )
  );
end;
$$;

revoke all on function public.creator_content_passport_registry(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_content_passport_registry(jsonb)
  to authenticated;

create or replace function public.creator_content_result_passport(
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
  media_row content_factory.media_objects%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  product_row content_factory.products%rowtype;
  strategy_row
    content_factory.generation_job_strategy_snapshots%rowtype;
  selection_row
    content_factory.generation_job_selection_snapshots%rowtype;
  spec_row content_factory.generation_spec_versions%rowtype;
  assets_value jsonb := '[]'::jsonb;
  sources_value jsonb := '[]'::jsonb;
  spend_value jsonb := '[]'::jsonb;
  placements_value jsonb := '[]'::jsonb;
  metrics_value jsonb := '[]'::jsonb;
  timeline_value jsonb := '[]'::jsonb;
  missing_value jsonb := '["hypothesis", "provenance_manifest"]'::jsonb;
  preliminary_value boolean := false;
  brief_value jsonb := null;
begin
  p_payload := content_factory_private.require_payload(p_payload);
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
  media_id_value := content_factory_private.require_uuid(
    p_payload, 'media_id'
  );

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.project_id = project_id_value
    and media.id = media_id_value
    and media.artifact_class = 'generated_output'
    and media.metadata ? 'generation_job_id';
  if media_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'content_result_passport_not_found';
  end if;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = (media_row.metadata ->> 'generation_job_id')::uuid;
  if job_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'content_result_passport_job_missing';
  end if;

  select product.* into product_row
  from content_factory.products product
  where product.organization_id = organization_id
    and product.id = job_row.product_id;

  select snapshot.* into strategy_row
  from content_factory.generation_job_strategy_snapshots snapshot
  where snapshot.organization_id = organization_id
    and snapshot.generation_job_id = job_row.id;

  select snapshot.* into selection_row
  from content_factory.generation_job_selection_snapshots snapshot
  where snapshot.organization_id = organization_id
    and snapshot.generation_job_id = job_row.id;

  if job_row.generation_spec_id is not null then
    select spec.* into spec_row
    from content_factory.generation_spec_versions spec
    where spec.organization_id = organization_id
      and spec.spec_id = job_row.generation_spec_id
      and spec.spec_version = job_row.generation_spec_version;
  end if;
  if spec_row.version_id is not null then
    brief_value := jsonb_build_object(
      'spec_id', spec_row.spec_id,
      'spec_version', spec_row.spec_version,
      'spec_hash', spec_row.spec_hash,
      'prompt_hash', spec_row.prompt_hash,
      'platform', spec_row.platform,
      'duration_seconds', spec_row.duration_seconds,
      'ratio', spec_row.ratio,
      'resolution', spec_row.resolution,
      'created_at', spec_row.created_at,
      'created_by', spec_row.created_by,
      'compiled_prompt', left(coalesce(spec_row.compiled_prompt, ''), 4000),
      'compiled_prompt_truncated',
        length(coalesce(spec_row.compiled_prompt, '')) > 4000
    );
  else
    missing_value := missing_value || to_jsonb('brief'::text);
  end if;

  if strategy_row.id is not null then
    select coalesce(jsonb_agg(jsonb_build_object(
        'role', asset.role,
        'ordinal', asset.ordinal,
        'media_object_id', asset.media_object_id,
        'sha256', asset.media_sha256_snapshot,
        'kind', asset.media_kind_snapshot,
        'mime_type', asset.mime_type_snapshot,
        'product_id', asset.media_product_id_snapshot,
        'rights_confirmed', asset.rights_confirmed_snapshot,
        'likeness_consent', asset.likeness_consent_snapshot,
        'original_filename', asset_media.metadata ->> 'original_filename',
        'status', asset_media.status
      ) order by asset.ordinal), '[]'::jsonb)
      into assets_value
    from content_factory.generation_spec_strategy_assets asset
    left join content_factory.media_objects asset_media
      on asset_media.organization_id = asset.organization_id
      and asset_media.id = asset.media_object_id
    where asset.organization_id = organization_id
      and asset.binding_id = strategy_row.spec_strategy_binding_id;
  else
    missing_value := missing_value || to_jsonb('assets'::text);
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
      'binding_id', binding.id,
      'canonical_url', source.canonical_url,
      'video_id', source.video_id,
      'source_hash', source.source_hash,
      'registered_at', source.created_at
    ) order by binding.id), '[]'::jsonb)
    into sources_value
  from content_factory.generation_job_video_reference_bindings binding
  left join content_factory.research_exact_youtube_sources source
    on source.organization_id = binding.organization_id
    and source.id = binding.source_id
  where binding.organization_id = organization_id
    and binding.generation_job_id = job_row.id;

  select coalesce(jsonb_agg(jsonb_build_object(
      'event_type', entry.event_type,
      'estimated_cost_minor', entry.estimated_cost_minor,
      'actual_cost_minor', entry.actual_cost_minor,
      'reserved_delta_minor', entry.reserved_delta_minor,
      'committed_delta_minor', entry.committed_delta_minor,
      'currency', entry.currency,
      'reason_code', entry.reason_code,
      'created_at', entry.created_at
    ) order by entry.created_at), '[]'::jsonb)
    into spend_value
  from (
    select ledger.*
    from content_factory.generation_spend_ledger ledger
    where ledger.organization_id = organization_id
      and ledger.generation_job_id = job_row.id
    order by ledger.created_at
    limit 20
  ) entry;

  select coalesce(jsonb_agg(jsonb_build_object(
      'placement_id', placement.id,
      'platform', placement.platform,
      'destination_ref', placement.destination_ref,
      'status', placement.status,
      'scheduled_at', placement.scheduled_at,
      'published_at', placement.published_at,
      'tracking_url', placement.tracking_url,
      'final_url', placement.final_url,
      'erid', placement.metadata ->> 'erid'
    ) order by placement.created_at), '[]'::jsonb)
    into placements_value
  from (
    select p.*
    from content_factory.placements p
    where p.organization_id = organization_id
      and p.generation_job_id = job_row.id
    order by p.created_at
    limit 20
  ) placement;

  select coalesce(jsonb_agg(jsonb_build_object(
      'placement_id', metric_group.placement_id,
      'published_at', metric_group.published_at,
      'snapshots', metric_group.snapshots
    ) order by metric_group.placement_id), '[]'::jsonb)
    into metrics_value
  from (
    select
      placement.id as placement_id,
      placement.published_at,
      coalesce((
        select jsonb_agg(jsonb_build_object(
          'views', snapshot.views,
          'clicks', snapshot.clicks,
          'orders', snapshot.orders,
          'revenue_minor', snapshot.revenue_minor,
          'observed_at', snapshot.observed_at,
          'source', snapshot.source,
          'is_correction', snapshot.is_correction,
          'mature', placement.published_at is not null
            and snapshot.observed_at >= placement.published_at
              + interval '72 hours'
        ) order by snapshot.observed_at)
        from (
          select s.*
          from content_factory.metric_snapshots s
          where s.organization_id = organization_id
            and s.placement_id = placement.id
          order by s.observed_at desc
          limit 30
        ) snapshot
      ), '[]'::jsonb) as snapshots
    from content_factory.placements placement
    where placement.organization_id = organization_id
      and placement.generation_job_id = job_row.id
    limit 20
  ) metric_group;

  select exists (
    select 1
    from content_factory.placements placement
    join content_factory.metric_snapshots snapshot
      on snapshot.organization_id = placement.organization_id
      and snapshot.placement_id = placement.id
    where placement.organization_id = organization_id
      and placement.generation_job_id = job_row.id
      and (
        placement.published_at is null
        or snapshot.observed_at
          < placement.published_at + interval '72 hours'
      )
  ) into preliminary_value;

  select coalesce(
      jsonb_agg(entry_value order by occurred_at_value), '[]'::jsonb
    )
    into timeline_value
  from (
    (
      select event.occurred_at as occurred_at_value,
        jsonb_build_object(
          'kind', 'generation',
          'event', event.event_name,
          'job_status', event.job_status,
          'occurred_at', event.occurred_at
        ) as entry_value
      from content_factory.generation_strategy_status_events event
      where event.organization_id = organization_id
        and event.generation_job_id = job_row.id
      order by event.occurred_at
      limit 100
    )
    union all
    (
      select placement.published_at,
        jsonb_build_object(
          'kind', 'placement',
          'event', 'published',
          'platform', placement.platform,
          'placement_id', placement.id,
          'occurred_at', placement.published_at
        )
      from content_factory.placements placement
      where placement.organization_id = organization_id
        and placement.generation_job_id = job_row.id
        and placement.published_at is not null
      order by placement.published_at
      limit 20
    )
    union all
    (
      select snapshot.observed_at,
        jsonb_build_object(
          'kind', 'metric',
          'event', 'metric_snapshot',
          'placement_id', snapshot.placement_id,
          'occurred_at', snapshot.observed_at
        )
      from content_factory.metric_snapshots snapshot
      join content_factory.placements placement
        on placement.organization_id = snapshot.organization_id
        and placement.id = snapshot.placement_id
      where snapshot.organization_id = organization_id
        and placement.generation_job_id = job_row.id
      order by snapshot.observed_at
      limit 30
    )
  ) events (occurred_at_value, entry_value);

  return jsonb_build_object(
    'ok', true,
    'version', 'content-result-passport-v1',
    'media', jsonb_build_object(
      'id', media_row.id,
      'original_filename',
        coalesce(media_row.metadata ->> 'original_filename',
          media_row.object_name),
      'mime_type', media_row.mime_type,
      'size_bytes', media_row.size_bytes,
      'sha256', media_row.sha256,
      'status', media_row.status,
      'created_at', media_row.created_at,
      'duration_seconds', media_row.metadata -> 'duration_seconds',
      'ratio', media_row.metadata ->> 'ratio',
      'resolution', media_row.metadata ->> 'resolution',
      'audio', media_row.metadata -> 'audio',
      'kind', media_row.metadata ->> 'kind'
    ),
    'product', case
      when product_row.id is null then null
      else jsonb_build_object(
        'id', product_row.id,
        'sku', product_row.sku,
        'title', product_row.title,
        'status', product_row.status
      )
    end,
    'hypothesis', null,
    'brief', brief_value,
    'sources', sources_value,
    'assets', assets_value,
    'execution', jsonb_build_object(
      'generation_job_id', job_row.id,
      'job_status', job_row.status,
      'strategy_id', coalesce(
        media_row.metadata ->> 'strategy_id',
        strategy_row.strategy_snapshot -> 'strategy' ->> 'strategy_id'
      ),
      'provider', job_row.provider,
      'model', coalesce(media_row.metadata ->> 'model', selection_row.model),
      'pricing_version', selection_row.pricing_version,
      'catalog_version', selection_row.catalog_version,
      'estimated_cost_minor', job_row.estimated_cost_minor,
      'actual_cost_minor', job_row.actual_cost_minor,
      'requested_by', job_row.requested_by,
      'created_at', job_row.created_at,
      'spend', spend_value
    ),
    'reviews', '[]'::jsonb,
    'placements', placements_value,
    'metrics', metrics_value,
    'timeline', timeline_value,
    '_meta', jsonb_build_object(
      'complete', spec_row.version_id is not null
        and strategy_row.id is not null,
      'legacy', strategy_row.id is null,
      'missing_sections', missing_value,
      'preliminary_metrics', preliminary_value
    ),
    'contract', jsonb_build_object(
      'read_only', true,
      'provider_call_started', false,
      'spend_action_started', false,
      'human_decision_recorded', false
    )
  );
end;
$$;

revoke all on function public.creator_content_result_passport(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_content_result_passport(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
