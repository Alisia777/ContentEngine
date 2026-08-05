begin;

-- The portal is an adviser, not an approval authority. Keep every immutable
-- spec, scope, prompt and live-policy revalidation, but do not require a
-- separate human approval state before the user's explicit paid launch.
alter function content_factory_private.assert_generation_spec_current(
  uuid, uuid, integer, text, boolean, boolean
) rename to assert_generation_spec_current_pre_advisory_v1;

revoke all on function
  content_factory_private.assert_generation_spec_current_pre_advisory_v1(
    uuid, uuid, integer, text, boolean, boolean
  ) from public, anon, authenticated, service_role;

create function content_factory_private.assert_generation_spec_current(
  organization_id_value uuid,
  spec_id_value uuid,
  spec_version_value integer,
  spec_hash_value text,
  approval_required boolean default true,
  dynamic_revalidation boolean default true
)
returns content_factory.generation_spec_versions
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  return content_factory_private
    .assert_generation_spec_current_pre_advisory_v1(
      organization_id_value,
      spec_id_value,
      spec_version_value,
      spec_hash_value,
      false,
      dynamic_revalidation
    );
end;
$$;

revoke all on function content_factory_private.assert_generation_spec_current(
  uuid, uuid, integer, text, boolean, boolean
) from public, anon, authenticated, service_role;

-- Preserve the complete project-scoped learning reader, but expose its former
-- veto as advice. Existing provider/spec consumers continue to receive a
-- structurally valid policy while the browser can show the advisory signal.
alter function public.creator_generation_learning_policy(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_generation_learning_policy(jsonb)
  rename to creator_generation_learning_policy_pre_advisory_v9;

revoke all on function
  content_factory_private.creator_generation_learning_policy_pre_advisory_v9(
    jsonb
  ) from public, anon, authenticated, service_role;

create function public.creator_generation_learning_policy(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  policy_value jsonb;
begin
  policy_value := content_factory_private
    .creator_generation_learning_policy_pre_advisory_v9(p_payload);
  return policy_value || jsonb_build_object(
    'advisory_generation_allowed',
      coalesce(policy_value -> 'generation_allowed', 'true'::jsonb),
    'generation_allowed', true,
    'advisory_only', true
  );
end;
$$;

revoke all on function public.creator_generation_learning_policy(jsonb)
  from public, anon;
grant execute on function public.creator_generation_learning_policy(jsonb)
  to authenticated;

-- The historical rejection trigger used an AI score as a hard payment veto.
-- Keep the trigger and its audit-visible function name, but make it advisory:
-- provider, budget, identity and prompt guards remain in their own layers.
create or replace function
  content_factory_private.guard_generation_rejection_before_paid_job()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  return new;
end;
$$;

revoke all on function
  content_factory_private.guard_generation_rejection_before_paid_job()
  from public, anon, authenticated, service_role;

-- Generation history uses recoverable removal. Source photos and generated
-- files stay intact; only the selected launch disappears from the archive.
alter table content_factory.generation_batches
  add column if not exists archived_at timestamptz,
  add column if not exists archived_by uuid
    references content_factory.profiles(id);

create index if not exists generation_batches_visible_project_created_idx
  on content_factory.generation_batches (
    organization_id, project_id, created_at desc, id desc
  )
  where archived_at is null;

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
       'organization_id', 'project_id', 'batch_id', 'confirmation'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'project_id', 'batch_id', 'confirmation'
     ]::text[]
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb then
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

-- Patch the current project-scoped keyset archive in place so later schema
-- additions are preserved without copying its long query into this migration.
do $patch_generation_archive_visibility$
declare
  function_definition text;
  search_fragment constant text :=
    'where batch.organization_id = organization_id';
  replacement_fragment constant text :=
    'where batch.organization_id = organization_id' || e'\n' ||
    '      and batch.archived_at is null';
begin
  select pg_get_functiondef(
    'public.creator_generation_archive(jsonb)'::regprocedure
  ) into function_definition;
  if position('and batch.archived_at is null' in function_definition) = 0 then
    if (
      length(function_definition)
      - length(replace(function_definition, search_fragment, ''))
    ) / length(search_fragment) <> 1 then
      raise exception using
        errcode = '55000',
        message = 'generation_archive_visibility_patch_target_invalid';
    end if;
    function_definition := replace(
      function_definition,
      search_fragment,
      replacement_fragment
    );
    execute function_definition;
  end if;
end;
$patch_generation_archive_visibility$;

-- current_profile_id() may upsert the authenticated profile, so both archive
-- RPCs must be volatile. This repairs SQLSTATE 25006 from the project wrapper.
alter function public.creator_generation_archive(jsonb) volatile;
alter function public.creator_archive_generation_batch(jsonb) volatile;

notify pgrst, 'reload schema';

commit;
