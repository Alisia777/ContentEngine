begin;

-- The Trash RPCs use a PL/pgSQL variable named organization_id. PostgreSQL can
-- therefore interpret bare ON CONFLICT column lists as variable expressions
-- instead of unique-index inference. Pin every upsert to the named primary key.
do $workspace_trash_fix$
declare
  definition text;
  updated_definition text;
begin
  definition := pg_get_functiondef(
    'public.creator_restore_workspace_items(jsonb)'::regprocedure
  );
  updated_definition := replace(
    definition,
    'ON CONFLICT (organization_id, media_object_id)',
    'ON CONFLICT ON CONSTRAINT workspace_media_locations_pkey'
  );
  updated_definition := replace(
    updated_definition,
    'on conflict (organization_id, media_object_id)',
    'on conflict on constraint workspace_media_locations_pkey'
  );
  updated_definition := replace(
    updated_definition,
    'ON CONFLICT (organization_id, task_id)',
    'ON CONFLICT ON CONSTRAINT workspace_task_locations_pkey'
  );
  updated_definition := replace(
    updated_definition,
    'on conflict (organization_id, task_id)',
    'on conflict on constraint workspace_task_locations_pkey'
  );
  if updated_definition = definition
     or updated_definition ~* 'on[[:space:]]+conflict[[:space:]]*\([[:space:]]*organization_id' then
    raise exception using
      errcode = '55000',
      message = 'workspace_restore_conflict_target_fix_failed';
  end if;
  execute updated_definition;

  definition := pg_get_functiondef(
    'public.creator_purge_workspace_items(jsonb)'::regprocedure
  );
  updated_definition := replace(
    definition,
    'ON CONFLICT (organization_id, media_object_id)',
    'ON CONFLICT ON CONSTRAINT workspace_storage_cleanup_queue_pkey'
  );
  updated_definition := replace(
    updated_definition,
    'on conflict (organization_id, media_object_id)',
    'on conflict on constraint workspace_storage_cleanup_queue_pkey'
  );
  if updated_definition = definition
     or updated_definition ~* 'on[[:space:]]+conflict[[:space:]]*\([[:space:]]*organization_id' then
    raise exception using
      errcode = '55000',
      message = 'workspace_purge_conflict_target_fix_failed';
  end if;
  execute updated_definition;
end;
$workspace_trash_fix$;

-- Private helpers are callable only by their SECURITY DEFINER owners. The
-- previous migration re-applied an old blanket service-role grant; restore the
-- repository's final fail-closed contract after adding the new helper.
revoke execute on all functions in schema content_factory_private
  from service_role;
revoke all on function
  content_factory_private.require_workspace_item_array(jsonb, integer)
  from public, anon, authenticated, service_role;

commit;
