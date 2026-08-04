begin;

-- Keep project selection fast even in organizations with a long production history.
-- The selected project still receives the exact truth-based snapshot.  The
-- project chooser receives lightweight folder records and calculates the exact
-- next action only after the user selects one project.

create or replace function public.creator_project_flow(
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
  actor_role text;
  project_id_value uuid;
  include_projects boolean := true;
  selected_snapshot jsonb;
  projects_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'include_projects'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'project_flow_payload_invalid';
  end if;
  if p_payload ? 'include_projects' then
    if jsonb_typeof(p_payload -> 'include_projects') <> 'boolean' then
      raise exception using errcode = '22023', message = 'project_flow_include_projects_invalid';
    end if;
    include_projects := (p_payload ->> 'include_projects')::boolean;
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );

  if nullif(btrim(coalesce(p_payload ->> 'project_id', '')), '') is not null then
    project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
    perform content_factory_private.require_workspace_project(
      organization_id,
      project_id_value
    );
    selected_snapshot := content_factory_private.project_flow_snapshot(
      organization_id,
      project_id_value,
      user_id,
      actor_role
    );
  end if;

  if include_projects then
    select coalesce(
      jsonb_agg(
        case
          when project.id = project_id_value and selected_snapshot is not null then
            (selected_snapshot -> 'project')
            || jsonb_build_object('catalog_state', 'exact')
          else jsonb_build_object(
            'id', project.id,
            'name', project.name,
            'color_token', project.color_token,
            'status', project.status,
            'version', project.version,
            'updated_at', project.updated_at,
            'current_stage', null,
            'progress_percent', 0,
            'catalog_state', 'summary',
            'next_action', jsonb_build_object(
              'label', 'Открыть проект',
              'stage', 'files',
              'route', '/workspace/home?project_id=' || project.id::text,
              'project_id', project.id,
              'entity_type', 'workspace_project',
              'entity_id', project.id
            )
          )
        end
        order by project.updated_at desc, project.id desc
      ),
      '[]'::jsonb
    )
    into projects_value
    from content_factory.workspace_folders project
    where project.organization_id = organization_id
      and project.kind = 'project'
      and project.status = 'active';
  end if;

  return jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'projects', projects_value,
    'project', selected_snapshot -> 'project',
    'stages', coalesce(selected_snapshot -> 'stages', '[]'::jsonb),
    'next_action', selected_snapshot -> 'next_action',
    'counts', coalesce(selected_snapshot -> 'counts', jsonb_build_object(
      'files', 0,
      'generation_jobs', 0,
      'reviews', 0,
      'actionable_tasks', 0,
      'placements', 0,
      'metric_snapshots', 0,
      'queue', 0
    ))
  );
end;
$$;

revoke all on function public.creator_project_flow(jsonb)
  from public, anon;
grant execute on function public.creator_project_flow(jsonb)
  to authenticated;

comment on function public.creator_project_flow(jsonb) is
  'Returns one exact selected-project flow plus a lightweight project chooser catalog.';

notify pgrst, 'reload schema';

commit;
