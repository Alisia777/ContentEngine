begin;

-- Action-time authority for the existing Notification Center v4.9.1.
--
-- 202608130001 remains the sole durable feed/read owner. This additive RPC
-- never trusts the projection's historical deep_link and never mutates read
-- state. It reloads one recipient row, rechecks its current role/project
-- authority and returns one closed, structured command descriptor that the
-- existing browser command registry must validate again before navigation.

create or replace function
  content_factory_private.notification_action_blocked_v491(
    p_notification_id uuid,
    p_action_key text,
    p_reason text
  )
returns jsonb
language sql
immutable
set search_path = ''
as $function$
  select jsonb_build_object(
    'ok', false,
    'status', 'blocked',
    'notification_id', p_notification_id,
    'action_key', p_action_key,
    'reason', p_reason,
    'command', null
  )
$function$;

create or replace function public.creator_validate_notification_action(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $function$
#variable_conflict use_variable
declare
  user_id_value uuid;
  organization_id_value uuid;
  actor_role_value text;
  notification_id_value uuid;
  action_key_value text;
  project_id_value uuid;
  object_id_value uuid;
  process_id_value uuid;
  notification_row content_factory.user_notifications%rowtype;
  target_kind_value text;
  target_count_value integer := 0;
  command_target_value jsonb;
  destination_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 4096
     or p_payload - array[
       'organization_id', 'notification_id', 'action_key', 'project_id',
       'object_id', 'process_id'
     ]::text[] <> '{}'::jsonb
     or not (p_payload ?& array[
       'organization_id', 'notification_id', 'action_key', 'project_id',
       'object_id', 'process_id'
     ])
     or jsonb_typeof(p_payload -> 'action_key') <> 'string'
     or (p_payload -> 'project_id' <> 'null'::jsonb
       and jsonb_typeof(p_payload -> 'project_id') <> 'string')
     or (p_payload -> 'object_id' <> 'null'::jsonb
       and jsonb_typeof(p_payload -> 'object_id') <> 'string')
     or (p_payload -> 'process_id' <> 'null'::jsonb
       and jsonb_typeof(p_payload -> 'process_id') <> 'string') then
    raise exception using
      errcode = '22023',
      message = 'notification_action_validation_payload_invalid';
  end if;

  user_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  actor_role_value := content_factory_private.membership_role(
    organization_id_value,
    false,
    null
  );
  notification_id_value := content_factory_private.require_uuid(
    p_payload,
    'notification_id'
  );
  action_key_value := lower(content_factory_private.require_text(
    p_payload,
    'action_key',
    3,
    80
  ));
  if p_payload -> 'project_id' <> 'null'::jsonb then
    project_id_value := content_factory_private.require_uuid(
      p_payload,
      'project_id'
    );
  end if;
  if p_payload -> 'object_id' <> 'null'::jsonb then
    object_id_value := content_factory_private.require_uuid(
      p_payload,
      'object_id'
    );
  end if;
  if p_payload -> 'process_id' <> 'null'::jsonb then
    process_id_value := content_factory_private.require_uuid(
      p_payload,
      'process_id'
    );
  end if;

  if action_key_value not in (
    'ai.open-decisions', 'process.open', 'review.open-object', 'object.open'
  ) then
    return content_factory_private.notification_action_blocked_v491(
      notification_id_value,
      action_key_value,
      'unknown_action'
    );
  end if;

  select notification.* into notification_row
  from content_factory.user_notifications notification
  where notification.organization_id = organization_id_value
    and notification.recipient_id = user_id_value
    and notification.id = notification_id_value;

  if notification_row.id is null then
    return content_factory_private.notification_action_blocked_v491(
      notification_id_value,
      action_key_value,
      'notification_unavailable'
    );
  end if;
  if notification_row.contract_version <> 491 then
    return content_factory_private.notification_action_blocked_v491(
      notification_id_value,
      action_key_value,
      'legacy_action_unsupported'
    );
  end if;
  if notification_row.read_state_version <> 491 then
    return content_factory_private.notification_action_blocked_v491(
      notification_id_value,
      action_key_value,
      'notification_read_state_unsupported'
    );
  end if;
  if notification_row.expires_at <= now() then
    return content_factory_private.notification_action_blocked_v491(
      notification_id_value,
      action_key_value,
      'expired'
    );
  end if;
  if notification_row.recipient_role_ids is not null
     and not (actor_role_value = any(notification_row.recipient_role_ids)) then
    return content_factory_private.notification_action_blocked_v491(
      notification_id_value,
      action_key_value,
      'permission_denied'
    );
  end if;
  if notification_row.action_key is distinct from action_key_value
     or notification_row.project_id is distinct from project_id_value
     or notification_row.object_id is distinct from object_id_value
     or notification_row.process_id is distinct from process_id_value then
    return content_factory_private.notification_action_blocked_v491(
      notification_id_value,
      action_key_value,
      'stale_notification'
    );
  end if;

  if project_id_value is null then
    return content_factory_private.notification_action_blocked_v491(
      notification_id_value,
      action_key_value,
      'notification_action_target_unsupported'
    );
  end if;
  if not content_factory_private.workspace_project_access_allowed(
    organization_id_value,
    project_id_value,
    user_id_value
  ) then
    return content_factory_private.notification_action_blocked_v491(
      notification_id_value,
      action_key_value,
      'permission_denied'
    );
  end if;

  if action_key_value = 'ai.open-decisions' then
    if object_id_value is not null or process_id_value is not null then
      return content_factory_private.notification_action_blocked_v491(
        notification_id_value,
        action_key_value,
        'stale_notification'
      );
    end if;
    command_target_value := jsonb_build_object(
      'kind', 'internal',
      'canonicalTarget',
        'contentengine://app/ai?space=bombbar&tab=decisions'
    );
    destination_value := jsonb_build_object(
      'section', 'ai',
      'view', 'decisions',
      'surface', 'ai_decisions',
      'project_id', project_id_value
    );

  elsif action_key_value = 'object.open' then
    if object_id_value is null or process_id_value is not null then
      return content_factory_private.notification_action_blocked_v491(
        notification_id_value,
        action_key_value,
        'stale_notification'
      );
    end if;
    select count(*)::integer into target_count_value
    from content_factory.media_objects media
    join content_factory.workspace_media_locations location
      on location.organization_id = media.organization_id
     and location.media_object_id = media.id
    where media.organization_id = organization_id_value
      and media.project_id = project_id_value
      and media.id = object_id_value
      and media.status = 'ready';
    if target_count_value = 0 then
      return content_factory_private.notification_action_blocked_v491(
        notification_id_value,
        action_key_value,
        'stale_target'
      );
    end if;
    command_target_value := jsonb_build_object(
      'kind', 'object',
      'objectRef', jsonb_build_object(
        'type', 'content_object',
        'id', object_id_value
      )
    );
    destination_value := jsonb_build_object(
      'section', 'board',
      'view', 'browse',
      'entity_parameter', 'media',
      'entity_id', object_id_value,
      'project_id', project_id_value
    );

  elsif action_key_value = 'review.open-object' then
    if object_id_value is null or process_id_value is not null then
      return content_factory_private.notification_action_blocked_v491(
        notification_id_value,
        action_key_value,
        'stale_notification'
      );
    end if;
    select count(*)::integer into target_count_value
    from content_factory.media_objects media
    where media.organization_id = organization_id_value
      and media.project_id = project_id_value
      and media.id = object_id_value
      and media.status = 'ready'
      and media.mime_type in (
        'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
      );
    if target_count_value = 0 then
      return content_factory_private.notification_action_blocked_v491(
        notification_id_value,
        action_key_value,
        'stale_target'
      );
    end if;
    command_target_value := jsonb_build_object(
      'kind', 'object',
      'objectRef', jsonb_build_object(
        'type', 'content_object',
        'id', object_id_value
      )
    );
    destination_value := jsonb_build_object(
      'section', 'review',
      'view', 'new',
      'entity_parameter', 'media',
      'entity_id', object_id_value,
      'project_id', project_id_value
    );

  elsif action_key_value = 'process.open' then
    if process_id_value is null or object_id_value is not null then
      return content_factory_private.notification_action_blocked_v491(
        notification_id_value,
        action_key_value,
        'stale_notification'
      );
    end if;
    with exact_targets as (
      select 'generation_job'::text as target_kind
      from content_factory.generation_jobs job
      where job.organization_id = organization_id_value
        and job.project_id = project_id_value
        and job.id = process_id_value
        and (
          actor_role_value in ('owner', 'admin', 'producer')
          or job.requested_by = user_id_value
          or job.assigned_to = user_id_value
        )
      union all
      select 'content_review'::text
      from content_factory.content_review_runs review
      where review.organization_id = organization_id_value
        and review.project_id = project_id_value
        and review.id = process_id_value
        and (
          actor_role_value in ('owner', 'admin', 'producer', 'reviewer')
          or review.requested_by = user_id_value
        )
      union all
      select 'placement'::text
      from content_factory.placements placement
      where placement.organization_id = organization_id_value
        and placement.project_id = project_id_value
        and placement.id = process_id_value
        and (
          actor_role_value in ('owner', 'admin', 'producer')
          or placement.assigned_to = user_id_value
        )
    )
    select count(*)::integer, min(target.target_kind)
      into target_count_value, target_kind_value
    from exact_targets target;

    if target_count_value > 1 then
      return content_factory_private.notification_action_blocked_v491(
        notification_id_value,
        action_key_value,
        'target_ambiguous'
      );
    end if;
    if target_count_value = 0 then
      if exists (
        select 1
        from content_factory.product_research_runs research
        where research.organization_id = organization_id_value
          and research.project_id = project_id_value
          and research.id = process_id_value
      ) or exists (
        select 1
        from content_factory.creator_tasks task
        where task.organization_id = organization_id_value
          and task.project_id = project_id_value
          and task.id = process_id_value
      ) then
        return content_factory_private.notification_action_blocked_v491(
          notification_id_value,
          action_key_value,
          'notification_action_target_unsupported'
        );
      end if;
      return content_factory_private.notification_action_blocked_v491(
        notification_id_value,
        action_key_value,
        'stale_target'
      );
    end if;

    command_target_value := jsonb_build_object(
      'kind', 'object',
      'objectRef', jsonb_build_object(
        'type', 'process',
        'id', process_id_value
      )
    );
    destination_value := case target_kind_value
      when 'generation_job' then jsonb_build_object(
        'section', 'generation',
        'view', 'history',
        'entity_parameter', 'job',
        'entity_id', process_id_value,
        'project_id', project_id_value
      )
      when 'content_review' then jsonb_build_object(
        'section', 'review',
        'view', 'current',
        'entity_parameter', 'review',
        'entity_id', process_id_value,
        'project_id', project_id_value
      )
      when 'placement' then jsonb_build_object(
        'section', 'placement',
        'view', 'next',
        'entity_parameter', 'placement',
        'entity_id', process_id_value,
        'project_id', project_id_value
      )
      else null
    end;
  end if;

  if command_target_value is null or destination_value is null then
    return content_factory_private.notification_action_blocked_v491(
      notification_id_value,
      action_key_value,
      'notification_action_target_unsupported'
    );
  end if;

  return jsonb_build_object(
    'ok', true,
    'status', 'ready',
    'notification_id', notification_id_value,
    'action_key', action_key_value,
    'already_read', notification_row.read_at is not null,
    'validated_at', statement_timestamp(),
    'command', jsonb_build_object(
      'action_key', action_key_value,
      'target', command_target_value,
      'authority', jsonb_build_object(
        'permission', 'allowed',
        'existence', 'present',
        'freshness', 'current'
      ),
      'destination', destination_value
    ),
    'contract', jsonb_build_object(
      'version', '4.9.1',
      'read_mutated', false,
      'paid_action', false,
      'starts_analysis', false,
      'starts_generation', false,
      'arbitrary_url_returned', false
    )
  );
end;
$function$;

revoke all on function
  content_factory_private.notification_action_blocked_v491(uuid, text, text)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_validate_notification_action(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_validate_notification_action(jsonb)
  to authenticated;

comment on function public.creator_validate_notification_action(jsonb) is
  'Notification Center v4.9.1 action-time recipient/role/project/target validator. Returns one structured existing-command descriptor only; never marks read or starts paid/AI work.';

commit;
