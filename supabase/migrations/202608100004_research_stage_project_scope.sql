begin;

-- The stage-control loop predates project lineage. Preserve its mature,
-- append-only implementation and expose only project-scoped browser gates.
-- The guards are intentionally idempotent so a local migration retry never
-- nests the wrappers or loses the preserved implementation.
do $preserve_research_stage_status_before_project_scope_v423$
begin
  if to_regprocedure(
    'content_factory_private.creator_research_stage_control_status_pre_project_scope_v423(jsonb)'
  ) is null then
    if to_regprocedure(
      'public.creator_research_stage_control_status(jsonb)'
    ) is null then
      raise exception using
        errcode = '42883',
        message = 'creator_research_stage_control_status_missing';
    end if;
    alter function public.creator_research_stage_control_status(jsonb)
      set schema content_factory_private;
    alter function
      content_factory_private.creator_research_stage_control_status(jsonb)
      rename to
        creator_research_stage_control_status_pre_project_scope_v423;
  end if;
end;
$preserve_research_stage_status_before_project_scope_v423$;

do $preserve_research_stage_control_before_project_scope_v423$
begin
  if to_regprocedure(
    'content_factory_private.creator_control_research_stage_pre_project_scope_v423(jsonb)'
  ) is null then
    if to_regprocedure(
      'public.creator_control_research_stage(jsonb)'
    ) is null then
      raise exception using
        errcode = '42883',
        message = 'creator_control_research_stage_missing';
    end if;
    alter function public.creator_control_research_stage(jsonb)
      set schema content_factory_private;
    alter function
      content_factory_private.creator_control_research_stage(jsonb)
      rename to creator_control_research_stage_pre_project_scope_v423;
  end if;
end;
$preserve_research_stage_control_before_project_scope_v423$;

revoke all on function
  content_factory_private.creator_research_stage_control_status_pre_project_scope_v423(
    jsonb
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.creator_control_research_stage_pre_project_scope_v423(
    jsonb
  ) from public, anon, authenticated, service_role;

create or replace function public.creator_research_stage_control_status(
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
  run_id_value uuid;
  child_run_id_value uuid;
  inner_payload jsonb;
  previous_project_setting text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.resolve_organization(
    p_payload
  );
  perform content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value,
    project_id_value
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  if not exists (
    select 1
    from content_factory.product_research_runs run
    where run.organization_id = organization_id_value
      and run.project_id = project_id_value
      and run.id = run_id_value
  ) then
    raise exception using
      errcode = '42501',
      message = 'research_run_project_scope_mismatch';
  end if;

  inner_payload := (p_payload - 'project_id') || jsonb_build_object(
    'organization_id', organization_id_value
  );
  previous_project_setting := current_setting(
    'contentengine.project_id',
    true
  );
  perform set_config(
    'contentengine.project_id',
    project_id_value::text,
    true
  );
  begin
    result_value := content_factory_private
      .creator_research_stage_control_status_pre_project_scope_v423(
        inner_payload
      );
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''),
      true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''),
    true
  );

  if jsonb_typeof(result_value) <> 'object' then
    raise exception using
      errcode = '55000',
      message = 'research_stage_control_status_result_invalid';
  end if;
  result_value := result_value || jsonb_build_object(
    'project_id', project_id_value
  );
  if jsonb_typeof(result_value #> '{active_recompute,invoke}') = 'object' then
    begin
      child_run_id_value := (
        result_value #>> '{active_recompute,child_run_id}'
      )::uuid;
    exception when invalid_text_representation then
      child_run_id_value := null;
    end;
    if child_run_id_value is null or not exists (
      select 1
      from content_factory.product_research_runs child_run
      where child_run.organization_id = organization_id_value
        and child_run.project_id = project_id_value
        and child_run.id = child_run_id_value
    ) then
      raise exception using
        errcode = '42501',
        message = 'research_stage_recompute_child_project_scope_mismatch';
    end if;
    result_value := jsonb_set(
      result_value,
      '{active_recompute,invoke,project_id}',
      to_jsonb(project_id_value),
      true
    );
  end if;
  return result_value;
end;
$$;

create or replace function public.creator_control_research_stage(
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
  run_id_value uuid;
  child_run_id_value uuid;
  inner_payload jsonb;
  previous_project_setting text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.resolve_organization(
    p_payload
  );
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value,
    project_id_value
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  if not exists (
    select 1
    from content_factory.product_research_runs run
    where run.organization_id = organization_id_value
      and run.project_id = project_id_value
      and run.id = run_id_value
  ) then
    raise exception using
      errcode = '42501',
      message = 'research_run_project_scope_mismatch';
  end if;

  inner_payload := (p_payload - 'project_id') || jsonb_build_object(
    'organization_id', organization_id_value
  );
  previous_project_setting := current_setting(
    'contentengine.project_id',
    true
  );
  perform set_config(
    'contentengine.project_id',
    project_id_value::text,
    true
  );
  begin
    result_value := content_factory_private
      .creator_control_research_stage_pre_project_scope_v423(
        inner_payload
      );
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''),
      true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''),
    true
  );

  if jsonb_typeof(result_value) <> 'object' then
    raise exception using
      errcode = '55000',
      message = 'research_stage_control_result_invalid';
  end if;
  result_value := result_value || jsonb_build_object(
    'project_id', project_id_value
  );
  if jsonb_typeof(result_value #> '{recompute_request,invoke}') = 'object' then
    begin
      child_run_id_value := (
        result_value #>> '{recompute_request,child_run_id}'
      )::uuid;
    exception when invalid_text_representation then
      child_run_id_value := null;
    end;
    if child_run_id_value is null or not exists (
      select 1
      from content_factory.product_research_runs child_run
      where child_run.organization_id = organization_id_value
        and child_run.project_id = project_id_value
        and child_run.id = child_run_id_value
    ) then
      raise exception using
        errcode = '42501',
        message = 'research_stage_recompute_child_project_scope_mismatch';
    end if;
    result_value := jsonb_set(
      result_value,
      '{recompute_request,invoke,project_id}',
      to_jsonb(project_id_value),
      true
    );
  end if;
  return result_value;
end;
$$;

revoke all on function public.creator_research_stage_control_status(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_control_research_stage(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_research_stage_control_status(jsonb)
  to authenticated;
grant execute on function public.creator_control_research_stage(jsonb)
  to authenticated;

comment on function public.creator_research_stage_control_status(jsonb) is
  'Reads one research stage-control snapshot only inside its explicit project ACL and returns a project-bound recompute instruction.';
comment on function public.creator_control_research_stage(jsonb) is
  'Mutates one exact project research stage and propagates project context to any saved child recompute run.';

notify pgrst, 'reload schema';

commit;
