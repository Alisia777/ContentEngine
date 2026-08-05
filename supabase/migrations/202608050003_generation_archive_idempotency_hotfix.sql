begin;

-- Browser mutations always carry an idempotency key. Archiving a batch is
-- naturally idempotent, so accept the transport key while keeping every
-- project, role, active-job and preservation guard from the original RPC.
create or replace function public.creator_archive_generation_batch(
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
  batch_id_value uuid;
  actor_role_value text;
  batch_row content_factory.generation_batches%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'project_id', 'batch_id', 'confirmation',
       'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'project_id', 'batch_id', 'confirmation'
     ]::text[]
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb
     or (
       p_payload ? 'idempotency_key'
       and coalesce(p_payload ->> 'idempotency_key', '') !~*
         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
     ) then
    raise exception using
      errcode = '22023', message = 'generation_batch_archive_payload_invalid';
  end if;

  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  actor_role_value := content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  batch_id_value := content_factory_private.require_uuid(
    p_payload, 'batch_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );

  select batch.* into batch_row
  from content_factory.generation_batches batch
  where batch.organization_id = organization_id_value
    and batch.project_id = project_id_value
    and batch.id = batch_id_value
  for update;

  if batch_row.id is null then
    raise exception using
      errcode = 'P0002', message = 'generation_batch_not_found';
  end if;
  if actor_role_value = 'operator'
     and batch_row.created_by <> actor_id_value then
    raise exception using
      errcode = '42501', message = 'generation_batch_archive_forbidden';
  end if;
  if batch_row.status in ('queued', 'starting', 'submitted', 'processing') then
    raise exception using
      errcode = '55000', message = 'generation_batch_archive_active';
  end if;

  if batch_row.archived_at is null then
    update content_factory.generation_batches batch
    set archived_at = clock_timestamp(),
        archived_by = actor_id_value,
        updated_at = clock_timestamp()
    where batch.organization_id = organization_id_value
      and batch.id = batch_id_value;
  end if;

  return jsonb_build_object(
    'ok', true,
    'batch_id', batch_id_value,
    'project_id', project_id_value,
    'archived', true,
    'recoverable', true,
    'source_media_preserved', true,
    'output_media_preserved', true
  );
end;
$$;

revoke all on function public.creator_archive_generation_batch(jsonb)
  from public, anon;
grant execute on function public.creator_archive_generation_batch(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
