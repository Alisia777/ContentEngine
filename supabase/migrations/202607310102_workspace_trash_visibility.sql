begin;

-- Desktop Trash removes task locations immediately, but the older task and
-- publishing feeds read creator_tasks / placements directly. Add the same
-- active-Trash exclusion to those feeds so a cancelled task cannot reappear
-- after reload while it is still recoverable from the Trash app.
--
-- creator_workspace_section is currently a tracking-enrichment wrapper. Its
-- original audited feed lives behind creator_workspace_section_tracking_v1,
-- so the visibility predicate belongs in that delegated function.
do $workspace_trash_visibility$
declare
  definition text;
  updated_definition text;
  pattern text;
  replacement text;
begin
  definition := pg_get_functiondef(
    'content_factory_private.creator_workspace_section_tracking_v1(jsonb)'::regprocedure
  );
  updated_definition := definition;

  pattern := $needle$
    from content_factory.placements placement
    join content_factory.products product
      on product.organization_id = placement.organization_id
     and product.id = placement.product_id
    left join content_factory.creator_tasks task
      on task.organization_id = placement.organization_id
     and task.id = placement.task_id
    where placement.organization_id = organization_id
      and (team_scope or placement.assigned_to = user_id)
      and placement.id in ($needle$;
  replacement := $needle$
    from content_factory.placements placement
    join content_factory.products product
      on product.organization_id = placement.organization_id
     and product.id = placement.product_id
    left join content_factory.creator_tasks task
      on task.organization_id = placement.organization_id
     and task.id = placement.task_id
    where placement.organization_id = organization_id
      and (team_scope or placement.assigned_to = user_id)
      and not exists (
        select 1
        from content_factory.workspace_trash_items trash
        where trash.organization_id = placement.organization_id
          and trash.entity_type = 'task'
          and trash.entity_id = placement.task_id
          and trash.status = 'trashed'
      )
      and placement.id in ($needle$;
  if position(pattern in updated_definition) = 0 then
    raise exception using
      errcode = '55000',
      message = 'workspace_placement_visibility_outer_patch_failed';
  end if;
  updated_definition := replace(updated_definition, pattern, replacement);

  pattern := $needle$
        from content_factory.placements candidate
        where candidate.organization_id = organization_id
          and (team_scope or candidate.assigned_to = user_id)
          and ($needle$;
  replacement := $needle$
        from content_factory.placements candidate
        where candidate.organization_id = organization_id
          and (team_scope or candidate.assigned_to = user_id)
          and not exists (
            select 1
            from content_factory.workspace_trash_items trash
            where trash.organization_id = candidate.organization_id
              and trash.entity_type = 'task'
              and trash.entity_id = candidate.task_id
              and trash.status = 'trashed'
          )
          and ($needle$;
  if position(pattern in updated_definition) = 0 then
    raise exception using
      errcode = '55000',
      message = 'workspace_placement_visibility_candidate_patch_failed';
  end if;
  updated_definition := replace(updated_definition, pattern, replacement);

  pattern := $needle$
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and (team_scope or task.assignee_id = user_id)
      and task.id in ($needle$;
  replacement := $needle$
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and (team_scope or task.assignee_id = user_id)
      and not exists (
        select 1
        from content_factory.workspace_trash_items trash
        where trash.organization_id = task.organization_id
          and trash.entity_type = 'task'
          and trash.entity_id = task.id
          and trash.status = 'trashed'
      )
      and task.id in ($needle$;
  if position(pattern in updated_definition) = 0 then
    raise exception using
      errcode = '55000',
      message = 'workspace_task_visibility_outer_patch_failed';
  end if;
  updated_definition := replace(updated_definition, pattern, replacement);

  pattern := $needle$
        from content_factory.creator_tasks candidate
        where candidate.organization_id = organization_id
          and (team_scope or candidate.assignee_id = user_id)
          and ($needle$;
  replacement := $needle$
        from content_factory.creator_tasks candidate
        where candidate.organization_id = organization_id
          and (team_scope or candidate.assignee_id = user_id)
          and not exists (
            select 1
            from content_factory.workspace_trash_items trash
            where trash.organization_id = candidate.organization_id
              and trash.entity_type = 'task'
              and trash.entity_id = candidate.id
              and trash.status = 'trashed'
          )
          and ($needle$;
  if position(pattern in updated_definition) = 0 then
    raise exception using
      errcode = '55000',
      message = 'workspace_task_visibility_candidate_patch_failed';
  end if;
  updated_definition := replace(updated_definition, pattern, replacement);

  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'workspace_trash_visibility_patch_empty';
  end if;
  execute updated_definition;

  definition := pg_get_functiondef(
    'public.creator_my_work(jsonb)'::regprocedure
  );
  updated_definition := definition;

  pattern := $needle$
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.assignee_id = user_id

    union all$needle$;
  replacement := $needle$
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.assignee_id = user_id
      and not exists (
        select 1
        from content_factory.workspace_trash_items trash
        where trash.organization_id = task.organization_id
          and trash.entity_type = 'task'
          and trash.entity_id = task.id
          and trash.status = 'trashed'
      )

    union all$needle$;
  if position(pattern in updated_definition) = 0 then
    raise exception using
      errcode = '55000',
      message = 'my_work_task_visibility_patch_failed';
  end if;
  updated_definition := replace(updated_definition, pattern, replacement);

  pattern := $needle$
    where placement.organization_id = organization_id
      and placement.assigned_to = user_id

    union all$needle$;
  replacement := $needle$
    where placement.organization_id = organization_id
      and placement.assigned_to = user_id
      and not exists (
        select 1
        from content_factory.workspace_trash_items trash
        where trash.organization_id = placement.organization_id
          and trash.entity_type = 'task'
          and trash.entity_id = placement.task_id
          and trash.status = 'trashed'
      )

    union all$needle$;
  if position(pattern in updated_definition) = 0 then
    raise exception using
      errcode = '55000',
      message = 'my_work_placement_visibility_patch_failed';
  end if;
  updated_definition := replace(updated_definition, pattern, replacement);

  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'my_work_trash_visibility_patch_empty';
  end if;
  execute updated_definition;
end;
$workspace_trash_visibility$;

-- Re-created SECURITY DEFINER RPCs keep their existing ACLs. Reassert the
-- public wrapper and My Work browser boundary explicitly; the delegated feed
-- remains private and is invoked only by the wrapper owner.
revoke all on function public.creator_workspace_section(jsonb)
  from public, anon;
grant execute on function public.creator_workspace_section(jsonb)
  to authenticated;
revoke all on function
  content_factory_private.creator_workspace_section_tracking_v1(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_my_work(jsonb)
  from public, anon;
grant execute on function public.creator_my_work(jsonb)
  to authenticated;

commit;
