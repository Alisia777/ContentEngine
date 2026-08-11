begin;

-- Keep the exact-source queue additive and rolling-safe.  The historical
-- `analysis_ready` field describes only attached MP4 integrity; it is retained
-- for older clients and mirrored as the unambiguous `media_ready`.  Research,
-- AI-Center review and effective recommendations are projected from their
-- authoritative append-only ledgers without starting analysis or a provider
-- call.
create index if not exists exact_youtube_research_source_lifecycle_idx
  on content_factory.research_exact_youtube_research_bindings (
    organization_id, project_id, source_id, attachment_id,
    bound_at desc, id desc
  );

create or replace function public.contentengine_exact_youtube_source_queue(
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
  actor_id_value uuid;
  organization_id_value uuid;
  project_id_value uuid;
  limit_value integer := 30;
  sources_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'limit'
  ]::text[] <> '{}'::jsonb
     or not p_payload ? 'project_id' then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_source_queue_payload_invalid';
  end if;

  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value,
    project_id_value,
    actor_id_value
  );

  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number'
       or coalesce(p_payload ->> 'limit', '') !~ '^[0-9]{1,2}$'
       or (p_payload ->> 'limit')::integer not between 1 and 50 then
      raise exception using
        errcode = '22023',
        message = 'exact_youtube_source_queue_limit_invalid';
    end if;
    limit_value := (p_payload ->> 'limit')::integer;
  end if;

  select coalesce(
    jsonb_agg(item.payload order by item.created_at desc, item.source_id desc),
    '[]'::jsonb
  )
  into sources_value
  from (
    select
      source.created_at,
      source.id as source_id,
      jsonb_build_object(
        'id', source.id,
        'project_id', source.project_id,
        'video_id', source.video_id,
        'canonical_url', source.canonical_url,
        'product_name', source.product_name,
        'product_sku', source.product_sku,
        'status', case
          when attachment.id is null then 'awaiting_media'
          else 'media_attached'
        end,
        'registered_status', source.status,
        'media_required', attachment.id is null,
        -- Deprecated compatibility alias: this has always meant media
        -- integrity/readiness, never completion of Product Research.
        'analysis_ready', coalesce(
          attachment.id is not null
          and media.status = 'ready'
          and media.sha256 = attachment.media_sha256_snapshot,
          false
        ),
        'media_ready', coalesce(
          attachment.id is not null
          and media.status = 'ready'
          and media.sha256 = attachment.media_sha256_snapshot,
          false
        ),
        'source_hash', source.source_hash,
        'created_at', source.created_at,
        'attachment', case when attachment.id is null then null else
          jsonb_build_object(
            'id', attachment.id,
            'status', attachment.status,
            'source_id', attachment.source_id,
            'media_id', attachment.media_object_id,
            'source_hash_snapshot', attachment.source_hash_snapshot,
            'media_sha256_snapshot', attachment.media_sha256_snapshot,
            'rights_confirmed', attachment.rights_confirmed,
            'media_matches_registered_source',
              attachment.media_matches_registered_source,
            'attached_by', attachment.attached_by,
            'attached_at', attachment.attached_at,
            'attachment_hash', attachment.attachment_hash
          )
        end,
        'media', case when media.id is null then null else
          jsonb_build_object(
            'id', media.id,
            'project_id', media.project_id,
            'object_key', media.object_name,
            'original_filename', media.metadata ->> 'original_filename',
            'kind', media.metadata ->> 'kind',
            'mime_type', media.mime_type,
            'size_bytes', media.size_bytes,
            'sha256', media.sha256,
            'status', media.status,
            'artifact_class', media.artifact_class,
            'lifecycle_stage', media.lifecycle_stage
          )
        end,
        'research_lifecycle', jsonb_build_object(
          'state', lifecycle_state.state,
          'next_action', case lifecycle_state.state
            when 'not_started' then 'prepare_exact_media_analysis'
            when 'analysis_in_progress' then 'open_research'
            when 'analysis_failed' then 'open_research'
            when 'completed_without_ai_receipt' then 'open_research'
            when 'awaiting_learning_selection' then 'review_ai_learning'
            when 'recommendations_ready' then 'open_generation'
            when 'excluded' then 'open_research'
          end,
          'latest', case when latest_research.binding_id is null then null else
            jsonb_strip_nulls(jsonb_build_object(
              'binding_id', latest_research.binding_id,
              'run_id', latest_research.run_id,
              'run_status', latest_research.run_status,
              'product_category', latest_research.product_category,
              'bound_at', latest_research.bound_at,
              'finished_at', latest_research.finished_at,
              'receipt_id', latest_research.receipt_id,
              'receipt_status', latest_research.receipt_status,
              'received_at', latest_research.received_at,
              'disposition_decision',
                latest_research.disposition_decision,
              'learning_selection_id', latest_research.selection_id,
              'learning_decision', latest_research.selection_decision,
              'selected_at', latest_research.selected_at
            ))
          end,
          -- This axis is intentionally independent from the latest run.  A
          -- newer failed retry must not hide an older approved recommendation
          -- that still participates in generation lookup.
          'effective', jsonb_strip_nulls(jsonb_build_object(
            'has_approved_recommendations',
              effective_learning.selection_id is not null,
            'selection_id', effective_learning.selection_id,
            'run_id', effective_learning.run_id,
            'receipt_id', effective_learning.receipt_id,
            'selected_at', effective_learning.selected_at
          ))
        ),
        'next_action', case
          when attachment.id is null then 'upload_lawful_mp4'
          when media.id is null
            or media.status <> 'ready'
            or media.sha256 <> attachment.media_sha256_snapshot
            then 'restore_attached_media'
          else 'start_exact_media_analysis'
        end,
        'files_deep_link', '#/workspace/board?project_id='
          || source.project_id::text
          || '&youtube_source=' || source.id::text
      ) as payload
    from content_factory.research_exact_youtube_sources source
    left join content_factory.research_exact_youtube_media_attachments attachment
      on attachment.organization_id = source.organization_id
     and attachment.project_id = source.project_id
     and attachment.source_id = source.id
    left join content_factory.media_objects media
      on media.organization_id = attachment.organization_id
     and media.id = attachment.media_object_id
     and media.project_id = source.project_id
    left join lateral (
      select
        binding.id as binding_id,
        binding.run_id,
        binding.product_category,
        binding.bound_at,
        run.status as run_status,
        run.finished_at,
        receipt.id as receipt_id,
        receipt.status as receipt_status,
        receipt.received_at,
        disposition.decision as disposition_decision,
        selection.id as selection_id,
        selection.decision as selection_decision,
        selection.selected_at
      from content_factory.research_exact_youtube_research_bindings binding
      join content_factory.product_research_runs run
        on run.organization_id = binding.organization_id
       and run.id = binding.run_id
       and run.product_id = binding.product_id
       and run.project_id = binding.project_id
      left join content_factory.ai_research_evidence_receipts receipt
        on receipt.organization_id = binding.organization_id
       and receipt.project_id = binding.project_id
       and receipt.run_id = binding.run_id
       and receipt.product_category = binding.product_category
      left join content_factory.ai_research_evidence_dispositions disposition
        on disposition.organization_id = receipt.organization_id
       and disposition.receipt_id = receipt.id
       and disposition.product_category = receipt.product_category
      left join content_factory.ai_research_learning_selections selection
        on selection.organization_id = receipt.organization_id
       and selection.receipt_id = receipt.id
       and selection.project_id = binding.project_id
       and selection.run_id = binding.run_id
       and selection.product_category = binding.product_category
      where binding.organization_id = source.organization_id
        and binding.project_id = source.project_id
        and binding.source_id = source.id
        and binding.attachment_id = attachment.id
      order by binding.bound_at desc, binding.id desc
      limit 1
    ) latest_research on true
    left join lateral (
      select
        selection.id as selection_id,
        selection.run_id,
        selection.receipt_id,
        selection.selected_at
      from content_factory.research_exact_youtube_research_bindings binding
      join content_factory.ai_research_evidence_receipts receipt
        on receipt.organization_id = binding.organization_id
       and receipt.project_id = binding.project_id
       and receipt.run_id = binding.run_id
       and receipt.product_category = binding.product_category
      join content_factory.ai_research_learning_selections selection
        on selection.organization_id = receipt.organization_id
       and selection.receipt_id = receipt.id
       and selection.project_id = binding.project_id
       and selection.run_id = binding.run_id
       and selection.product_category = binding.product_category
       and selection.decision = 'approve'
      where binding.organization_id = source.organization_id
        and binding.project_id = source.project_id
        and binding.source_id = source.id
        and binding.attachment_id = attachment.id
      order by selection.selected_at desc, selection.event_cursor desc,
               selection.id desc
      limit 1
    ) effective_learning on true
    left join lateral (
      select case
        when latest_research.binding_id is null then 'not_started'
        when latest_research.run_status in ('queued', 'processing')
          then 'analysis_in_progress'
        when latest_research.run_status in ('failed', 'cancelled')
          then 'analysis_failed'
        when latest_research.run_status = 'completed'
         and latest_research.selection_decision = 'approve'
          then 'recommendations_ready'
        when latest_research.run_status = 'completed'
         and (
           latest_research.selection_decision = 'reject'
           or latest_research.disposition_decision = 'reject'
         ) then 'excluded'
        when latest_research.run_status = 'completed'
         and latest_research.receipt_id is null
          then 'completed_without_ai_receipt'
        when latest_research.run_status = 'completed'
          then 'awaiting_learning_selection'
        else 'completed_without_ai_receipt'
      end as state
    ) lifecycle_state on true
    where source.organization_id = organization_id_value
      and source.project_id = project_id_value
    order by source.created_at desc, source.id desc
    limit limit_value
  ) item;

  return jsonb_build_object(
    'ok', true,
    -- Deliberately retain v2 so an older browser can ignore the additive
    -- lifecycle fields while a newer browser tolerates the previous response.
    'version', 'exact-youtube-source-queue-v2',
    'project_id', project_id_value,
    'sources', sources_value,
    'contract', jsonb_build_object(
      'url_is_video_evidence', false,
      'requires_lawful_mp4', true,
      'unattached_source_affects_learning', false,
      'unattached_source_affects_generation', false,
      'attachment_is_append_only', true,
      'attached_source_affects_learning', false,
      'attached_source_affects_generation', false,
      'attachment_starts_analysis', false,
      'source_row_mutated', false,
      'analysis_ready_is_media_ready', true,
      'research_lifecycle_projected', true,
      'research_lifecycle_read_only', true,
      'research_lifecycle_starts_analysis', false,
      'research_lifecycle_starts_provider_call', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  public.contentengine_exact_youtube_source_queue(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_exact_youtube_source_queue(jsonb)
  to authenticated, service_role;

comment on function public.contentengine_exact_youtube_source_queue(jsonb) is
  'Project-ACL exact YouTube source queue v2 with additive read-only research, AI review and effective recommendation lifecycle; starts no analysis or provider call.';

notify pgrst, 'reload schema';

commit;
