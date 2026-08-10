begin;

-- The AI Center remains an organization-level surface, but research training
-- is project data.  Browser callers must name one exact project and may only
-- see or decide receipts from that project's explicit membership boundary.

create or replace function public.contentengine_ai_research_training_queue(
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
  organization_id_value uuid;
  project_id_value uuid;
  snapshot_value jsonb;
  queue_value jsonb := '[]'::jsonb;
  learned_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.require_workspace_project(
    organization_id_value,
    project_id_value
  );

  -- The creator_* implementation applies the exact project predicate before
  -- either LIMIT.  The JSON filter below is a second fail-closed boundary, not
  -- the primary selector, so noisy sibling projects cannot starve this queue.
  snapshot_value := public.creator_ai_research_training_queue(
    p_payload
  );

  select coalesce(
    jsonb_agg(entry.value order by entry.ordinality),
    '[]'::jsonb
  )
  into queue_value
  from jsonb_array_elements(
    coalesce(snapshot_value -> 'queue', '[]'::jsonb)
  ) with ordinality entry(value, ordinality)
  where entry.value ->> 'project_id' = project_id_value::text;

  select coalesce(
    jsonb_agg(entry.value order by entry.ordinality),
    '[]'::jsonb
  )
  into learned_value
  from jsonb_array_elements(
    coalesce(snapshot_value -> 'learned', '[]'::jsonb)
  ) with ordinality entry(value, ordinality)
  where entry.value ->> 'project_id' = project_id_value::text;

  return snapshot_value || jsonb_build_object(
    'version', 'ai-research-training-queue-v3-project-scoped',
    'project_id', project_id_value,
    'queue', queue_value,
    'learned', learned_value,
    'contract', coalesce(snapshot_value -> 'contract', '{}'::jsonb)
      || jsonb_build_object('project_scoped', true)
  );
end;
$$;

revoke all on function
  public.contentengine_ai_research_training_queue(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_ai_research_training_queue(jsonb)
  to authenticated, service_role;

-- Reassert the internal-only grant in the final migration.  Older database
-- histories briefly granted this creator_* name to authenticated callers.
revoke all on function public.creator_ai_research_training_queue(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_ai_research_training_queue(jsonb)
  to service_role;

-- Preserve the already audited append-only decision implementation behind a
-- private alias.  The public wrapper below checks project ACL and receipt
-- lineage first, strips only project_id for the legacy allowlist, and replaces
-- its organization-wide replay snapshot with the scoped queue above.
do $$
begin
  if to_regprocedure(
    'content_factory_private.contentengine_decide_ai_research_training_unscoped_v1(jsonb)'
  ) is null then
    if to_regprocedure(
      'public.contentengine_decide_ai_research_training(jsonb)'
    ) is null then
      raise exception using
        errcode = '42883',
        message = 'contentengine_ai_research_training_decision_dependency_missing';
    end if;
    execute 'alter function public.contentengine_decide_ai_research_training(jsonb) set schema content_factory_private';
    execute 'alter function content_factory_private.contentengine_decide_ai_research_training(jsonb) rename to contentengine_decide_ai_research_training_unscoped_v1';
  end if;
end;
$$;

revoke all on function
  content_factory_private.contentengine_decide_ai_research_training_unscoped_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.contentengine_decide_ai_research_training(
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
  organization_id_value uuid;
  project_id_value uuid;
  receipt_id_value uuid;
  category_value text;
  result_value jsonb;
  snapshot_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  receipt_id_value := content_factory_private.require_uuid(
    p_payload,
    'receipt_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value,
    project_id_value
  );

  -- Fail closed before the append-only mutation.  A valid receipt from a
  -- different project is deliberately indistinguishable from a stale receipt.
  if not exists (
    select 1
    from content_factory.ai_research_evidence_receipts receipt
    where receipt.organization_id = organization_id_value
      and receipt.id = receipt_id_value
      and receipt.project_id = project_id_value
  ) then
    raise exception using
      errcode = '40001',
      message = 'ai_research_training_receipt_stale';
  end if;

  result_value :=
    content_factory_private.contentengine_decide_ai_research_training_unscoped_v1(
      p_payload - 'project_id'
    );
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  snapshot_value := public.contentengine_ai_research_training_queue(
    jsonb_build_object(
      'organization_id', organization_id_value,
      'project_id', project_id_value,
      'product_category', category_value,
      'limit', 30
    )
  );

  return jsonb_set(
    result_value,
    '{snapshot}',
    snapshot_value,
    true
  ) || jsonb_build_object('project_id', project_id_value);
end;
$$;

revoke all on function
  public.contentengine_decide_ai_research_training(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_decide_ai_research_training(jsonb)
  to authenticated, service_role;

-- The legacy control room still carries organization-wide knowledge and
-- metrics.  Preserve those global views, but remove the superseded unscoped
-- research inbox/decision projection from its browser response.
do $$
begin
  if to_regprocedure(
    'content_factory_private.creator_ai_learning_control_room_unscoped_research_v1(jsonb)'
  ) is null then
    if to_regprocedure(
      'public.creator_ai_learning_control_room(jsonb)'
    ) is null then
      raise exception using
        errcode = '42883',
        message = 'creator_ai_learning_control_room_dependency_missing';
    end if;
    execute 'alter function public.creator_ai_learning_control_room(jsonb) set schema content_factory_private';
    execute 'alter function content_factory_private.creator_ai_learning_control_room(jsonb) rename to creator_ai_learning_control_room_unscoped_research_v1';
  end if;
end;
$$;

revoke all on function
  content_factory_private.creator_ai_learning_control_room_unscoped_research_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_ai_learning_control_room(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  base_value jsonb;
begin
  base_value := content_factory_private
    .creator_ai_learning_control_room_pre_research_inbox_v1(p_payload);
  return base_value || jsonb_build_object(
    'research_inbox', '[]'::jsonb,
    'research_decisions', '[]'::jsonb,
    'category_detail', coalesce(base_value -> 'category_detail', '{}'::jsonb)
      || jsonb_build_object(
        'research_inbox', '[]'::jsonb,
        'research_decisions', '[]'::jsonb,
        'research_inbox_count', 0,
        'research_decision_count', 0
      ),
    'capabilities', coalesce(base_value -> 'capabilities', '{}'::jsonb)
      || jsonb_build_object(
        'can_read_research_inbox', false,
        'can_decide_research_inbox', false
      ),
    'guidance', coalesce(base_value -> 'guidance', '{}'::jsonb)
      || jsonb_build_object('research_inbox_next_action', null)
  );
end;
$$;

revoke all on function public.creator_ai_learning_control_room(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_ai_learning_control_room(jsonb)
  to authenticated, service_role;

-- The governed project-scoped decision above supersedes this older receipt
-- disposition command.  Keep it for trusted migrations/callbacks only; a
-- browser JWT must not mutate a receipt by organization-wide UUID lookup.
revoke all on function public.creator_decide_ai_research_receipt(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_decide_ai_research_receipt(jsonb)
  to service_role;

comment on function public.contentengine_ai_research_training_queue(jsonb) is
  'Exact-project AI research training queue. Browser callers require explicit project membership; organization membership alone is insufficient.';
comment on function public.contentengine_decide_ai_research_training(jsonb) is
  'Append-only AI research training decision constrained to one explicitly accessible project and exact receipt lineage.';

notify pgrst, 'reload schema';

commit;
