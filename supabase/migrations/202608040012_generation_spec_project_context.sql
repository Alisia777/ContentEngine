begin;

-- A generation spec predates project scope.  Its project is therefore
-- derived from every immutable media id in the exact spec version.  Products
-- remain organization-scoped, so the product anchor is the exact product
-- shared by the spec and all of those project-scoped media rows.
create or replace function
  content_factory_private.require_generation_spec_project_v48(
    p_organization_id uuid,
    p_project_id uuid,
    p_spec_id uuid,
    p_spec_version integer,
    p_spec_hash text,
    p_expected_product_id uuid default null
  )
returns uuid
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  spec_row content_factory.generation_spec_versions%rowtype;
  scoped_media_count integer;
begin
  perform content_factory_private.require_workspace_project(
    p_organization_id,
    p_project_id
  );

  select version.*
    into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = p_organization_id
    and version.spec_id = p_spec_id
    and version.spec_version = p_spec_version
    and version.spec_hash = p_spec_hash
  for share;

  if spec_row.version_id is null
     or (
       p_expected_product_id is not null
       and spec_row.product_id <> p_expected_product_id
     ) then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_project_scope_mismatch';
  end if;

  perform 1
  from content_factory.products product
  where product.organization_id = p_organization_id
    and product.id = spec_row.product_id
    and product.status = 'active'
  for share of product;
  if not found then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_project_scope_mismatch';
  end if;

  perform 1
  from unnest(spec_row.media_ids) selected(media_id)
  join content_factory.media_objects media
    on media.organization_id = p_organization_id
   and media.id = selected.media_id
   and media.product_id = spec_row.product_id
   and media.project_id = p_project_id
  for share of media;
  get diagnostics scoped_media_count = row_count;

  if scoped_media_count <> cardinality(spec_row.media_ids) then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_project_scope_mismatch';
  end if;

  return spec_row.product_id;
end;
$$;

revoke all on function
  content_factory_private.require_generation_spec_project_v48(
    uuid, uuid, uuid, integer, text, uuid
  ) from public, anon, authenticated, service_role;

-- Keep the audited effective-policy implementation byte-for-byte intact and
-- put a project-first boundary in front of it.  The wrapper deliberately does
-- not read project_payload_from_context_v47: callers must name the project.
do $preserve_generation_spec_effective_policy_v48$
begin
  if to_regprocedure(
    'content_factory_private.creator_generation_spec_effective_policy_pre_project_v48(jsonb)'
  ) is null then
    alter function public.creator_generation_spec_effective_policy(jsonb)
      rename to creator_generation_spec_effective_policy_pre_project_v48;
    alter function
      public.creator_generation_spec_effective_policy_pre_project_v48(jsonb)
      set schema content_factory_private;
  end if;
end;
$preserve_generation_spec_effective_policy_v48$;

revoke all on function
  content_factory_private.creator_generation_spec_effective_policy_pre_project_v48(
    jsonb
  ) from public, anon, authenticated, service_role;

create or replace function public.creator_generation_spec_effective_policy(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  organization_id_value uuid;
  project_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  previous_project_setting text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'project_id') then
    raise exception using
      errcode = '22023', message = 'project_id_required';
  end if;
  if p_payload - array[
       'organization_id', 'project_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'project_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[] then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_effective_payload_invalid';
  end if;

  organization_id_value := content_factory_private.require_uuid(
    p_payload,
    'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  begin
    if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
       or p_payload ->> 'spec_version' !~ '^[0-9]+$' then
      raise invalid_text_representation;
    end if;
    spec_version_value := (p_payload ->> 'spec_version')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_effective_payload_invalid';
  end;
  spec_hash_value := lower(content_factory_private.require_text(
    p_payload,
    'spec_hash',
    64,
    64
  ));
  if spec_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_effective_payload_invalid';
  end if;

  -- Authenticate before resolving any spec lineage so the wrapper cannot be
  -- used as an organization/spec existence oracle.
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  perform content_factory_private.require_generation_spec_project_v48(
    organization_id_value,
    project_id_value,
    spec_id_value,
    spec_version_value,
    spec_hash_value,
    null
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
    result_value :=
      content_factory_private.creator_generation_spec_effective_policy_pre_project_v48(
        p_payload - 'project_id'
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
      errcode = '55000', message = 'project_scoped_result_invalid';
  end if;
  return result_value || jsonb_build_object('project_id', project_id_value);
end;
$$;

revoke all on function public.creator_generation_spec_effective_policy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_generation_spec_effective_policy(jsonb)
  to authenticated;

comment on function public.creator_generation_spec_effective_policy(jsonb) is
  'Returns an exact current approved handoff only for an explicit project whose complete spec media lineage matches.';

-- Provider claim is a separate service transaction, so it cannot inherit the
-- request RPC's local GUC.  Preserve the claim engine and derive the only
-- allowed context from the exact locked paid job.  A caller GUC may agree with
-- that job, but can never select or override it.
do $preserve_generation_spec_live_claim_v48$
begin
  if to_regprocedure(
    'content_factory_private.generation_spec_live_claim_snapshot_pre_project_v48(uuid,uuid,uuid,integer,text)'
  ) is null then
    alter function
      content_factory_private.generation_spec_live_claim_snapshot(
        uuid, uuid, uuid, integer, text
      ) rename to generation_spec_live_claim_snapshot_pre_project_v48;
  end if;
end;
$preserve_generation_spec_live_claim_v48$;

revoke all on function
  content_factory_private.generation_spec_live_claim_snapshot_pre_project_v48(
    uuid, uuid, uuid, integer, text
  ) from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_spec_live_claim_snapshot(
    organization_id_value uuid,
    generation_job_id_value uuid,
    spec_id_value uuid,
    spec_version_value integer,
    spec_hash_value text
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  job_row content_factory.generation_jobs%rowtype;
  project_id_value uuid;
  previous_project_setting text;
  previous_project_id uuid;
  result_value jsonb;
begin
  select job.*
    into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.id = generation_job_id_value
    and job.generation_spec_id = spec_id_value
    and job.generation_spec_version = spec_version_value
    and job.generation_spec_hash = spec_hash_value
  for share;

  project_id_value := job_row.project_id;
  if job_row.id is null or project_id_value is null then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_project_scope_mismatch';
  end if;

  perform 1
  from content_factory.generation_batches batch
  where batch.organization_id = organization_id_value
    and batch.id = job_row.batch_id
    and batch.product_id = job_row.product_id
    and batch.project_id = project_id_value
  for share of batch;
  if not found then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_project_scope_mismatch';
  end if;

  perform content_factory_private.require_generation_spec_project_v48(
    organization_id_value,
    project_id_value,
    spec_id_value,
    spec_version_value,
    spec_hash_value,
    job_row.product_id
  );

  previous_project_setting := current_setting(
    'contentengine.project_id',
    true
  );
  if nullif(previous_project_setting, '') is not null then
    begin
      previous_project_id := previous_project_setting::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '22023', message = 'project_context_invalid';
    end;
    if previous_project_id <> project_id_value then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;
  end if;

  perform set_config(
    'contentengine.project_id',
    project_id_value::text,
    true
  );
  begin
    result_value :=
      content_factory_private.generation_spec_live_claim_snapshot_pre_project_v48(
        organization_id_value,
        generation_job_id_value,
        spec_id_value,
        spec_version_value,
        spec_hash_value
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
      errcode = '55000', message = 'project_scoped_result_invalid';
  end if;
  -- Preserve the original snapshot byte-for-byte: its snapshot_hash is
  -- checked against every field except snapshot_hash itself.  Project lineage
  -- is enforced before the preserved engine runs rather than appended outside
  -- that signed payload.
  return result_value;
end;
$$;

revoke all on function
  content_factory_private.generation_spec_live_claim_snapshot(
    uuid, uuid, uuid, integer, text
  ) from public, anon, authenticated, service_role;

notify pgrst, 'reload schema';

commit;
