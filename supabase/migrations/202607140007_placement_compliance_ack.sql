begin;

-- Keep the reviewed placement implementation intact, but put a mandatory
-- compliance acknowledgement in front of every browser call. The inner RPC
-- still owns authorization, task state, URL validation and idempotency; this
-- wrapper records the dated acknowledgement on the placement and its task.
alter function public.creator_confirm_placement(jsonb)
  set schema content_factory_private;

revoke all on function content_factory_private.creator_confirm_placement(jsonb)
  from public, anon, authenticated;
grant execute on function content_factory_private.creator_confirm_placement(jsonb)
  to service_role;

create or replace function public.creator_confirm_placement(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  result jsonb;
  placement_id uuid;
  task_id uuid;
  actor_id uuid;
  organization_id_value uuid;
  idempotency_key text;
  acknowledgement_key text;
  acknowledgement jsonb;
begin
  if jsonb_typeof(coalesce(p_payload, '{}'::jsonb)) is distinct from 'object'
     or jsonb_typeof(p_payload -> 'compliance_ack') is distinct from 'boolean'
     or p_payload -> 'compliance_ack' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'placement_compliance_ack_required';
  end if;

  -- Pass the acknowledgement through so it is covered by the existing
  -- idempotent request hash, then store human-readable evidence as well.
  result := content_factory_private.creator_confirm_placement(p_payload);
  placement_id := nullif(result #>> '{placement,id}', '')::uuid;
  task_id := nullif(result #>> '{placement,task_id}', '')::uuid;
  actor_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.resolve_organization(p_payload);
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  acknowledgement_key := case
    when result ->> 'action' = 'submitted_for_review'
      then 'compliance_submission_ack'
    else 'compliance_confirmation_ack'
  end;
  acknowledgement := jsonb_build_object(
    'confirmed', true,
    'confirmed_by', actor_id,
    'confirmed_at', now(),
    'checklist_version', '2026-07-14',
    'decision_source', 'task_instructions'
  );

  if placement_id is null or task_id is null then
    raise exception using
      errcode = '55000',
      message = 'placement_compliance_audit_failed';
  end if;

  update content_factory.placements placement
  set metadata = case
        when coalesce(placement.metadata, '{}'::jsonb) ? acknowledgement_key
          then placement.metadata
        else coalesce(placement.metadata, '{}'::jsonb)
          || jsonb_build_object(acknowledgement_key, acknowledgement)
      end,
      updated_at = now()
  where placement.organization_id = organization_id_value
    and placement.id = placement_id
    and not (coalesce(placement.metadata, '{}'::jsonb) ? acknowledgement_key);

  update content_factory.creator_tasks task
  set result = case
        when coalesce(task.result, '{}'::jsonb) ? acknowledgement_key
          then task.result
        else coalesce(task.result, '{}'::jsonb)
          || jsonb_build_object(acknowledgement_key, acknowledgement)
      end,
      updated_at = now()
  where task.organization_id = organization_id_value
    and task.id = task_id
    and not (coalesce(task.result, '{}'::jsonb) ? acknowledgement_key);

  perform content_factory_private.emit_event(
    organization_id_value,
    actor_id,
    'placement_compliance_acknowledged',
    'placement',
    placement_id::text,
    jsonb_build_object(
      'acknowledgement_kind', acknowledgement_key,
      'checklist_version', '2026-07-14',
      'decision_source', 'task_instructions'
    ),
    'placement-compliance:' || idempotency_key
  );

  return result;
end;
$$;

revoke all on function public.creator_confirm_placement(jsonb)
  from public, anon;
grant execute on function public.creator_confirm_placement(jsonb)
  to authenticated;

commit;
