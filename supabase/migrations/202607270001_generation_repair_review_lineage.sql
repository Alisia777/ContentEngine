begin;

-- A repaired render must be measured against the exact independent review
-- that produced its bounded repair policy.  "Latest review for this product"
-- is not strong enough when several platforms or creative variants are active
-- at the same time.
create or replace function
  content_factory_private.generation_repair_review_lineage(
    p_organization_id uuid,
    p_media_id uuid
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  media_row content_factory.media_objects%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  signal_row content_factory.generation_repair_signals%rowtype;
  source_review_row content_factory.content_review_runs%rowtype;
  source_media_row content_factory.media_objects%rowtype;
  source_job_row content_factory.generation_jobs%rowtype;
  decision_row content_factory.content_review_decisions%rowtype;
begin
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = p_organization_id
    and media.id = p_media_id;
  if media_row.id is null then
    return null;
  end if;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = p_organization_id
    and job.output ->> 'output_media_id' = media_row.id::text
    and media_row.metadata ->> 'generation_job_id' = job.id::text;
  if job_row.id is null then
    return null;
  end if;

  select signal.* into signal_row
  from content_factory.generation_repair_signals signal
  where signal.organization_id = p_organization_id
    and signal.generation_job_id = job_row.id;
  if signal_row.id is null then
    return null;
  end if;

  select review.* into source_review_row
  from content_factory.content_review_runs review
  where review.organization_id = p_organization_id
    and review.id = signal_row.source_review_id;
  select media.* into source_media_row
  from content_factory.media_objects media
  where media.organization_id = p_organization_id
    and media.id = signal_row.source_media_id;
  select job.* into source_job_row
  from content_factory.generation_jobs job
  where job.organization_id = p_organization_id
    and job.id = signal_row.source_generation_job_id;
  select decision.* into decision_row
  from content_factory.content_review_decisions decision
  where decision.organization_id = p_organization_id
    and decision.review_id = signal_row.source_review_id;

  if job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or job_row.status <> 'succeeded'
     or job_row.product_id is distinct from signal_row.product_id
     or media_row.product_id is distinct from signal_row.product_id
     or media_row.status <> 'ready'
     or media_row.metadata ->> 'kind' not in (
       'generated_video', 'generated_image'
     )
     or source_review_row.id is null
     or source_review_row.status <> 'completed'
     or source_review_row.completion_hash is distinct from
          signal_row.source_review_completion_hash
     or source_review_row.media_object_id is distinct from
          signal_row.source_media_id
     or source_review_row.input ->> 'generation_job_id'
          is distinct from signal_row.source_generation_job_id::text
     or source_media_row.id is null
     or source_media_row.product_id is distinct from signal_row.product_id
     or source_media_row.sha256 is distinct from
          signal_row.source_media_sha256
     or source_job_row.id is null
     or source_job_row.status <> 'succeeded'
     or source_job_row.product_id is distinct from signal_row.product_id
     or source_job_row.output ->> 'output_media_id'
          is distinct from source_media_row.id::text
     or source_job_row.input ->> 'model'
          is distinct from job_row.input ->> 'model'
     or source_job_row.input ->> 'platform'
          is distinct from job_row.input ->> 'platform'
     or source_job_row.input ->> 'destination_ref'
          is distinct from job_row.input ->> 'destination_ref'
     or job_row.input ->> 'input_media_id'
          is distinct from signal_row.input_media_id::text
     or decision_row.id is null
     or decision_row.decision <> 'needs_changes'
     or not decision_row.media_watched_confirmed
     or decision_row.review_completion_hash is distinct from
          signal_row.source_review_completion_hash
     or decision_row.media_sha256_snapshot is distinct from
          signal_row.source_media_sha256 then
    raise exception using
      errcode = '55000',
      message = 'generation_repair_review_lineage_invalid';
  end if;

  return jsonb_build_object(
    'compiler_version', 'review-repair-v1',
    'generation_job_id', signal_row.generation_job_id,
    'source_review_id', signal_row.source_review_id,
    'source_generation_job_id', signal_row.source_generation_job_id,
    'policy_hash', signal_row.policy_hash
  );
end;
$$;

revoke all on function
  content_factory_private.generation_repair_review_lineage(uuid, uuid)
  from public, anon, authenticated, service_role;

-- This trigger also covers the autonomous Seedream photo queue, which inserts
-- a review directly after the provider result has been stored.
create or replace function
  content_factory_private.enforce_generation_repair_review_lineage()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  lineage jsonb;
begin
  lineage :=
    content_factory_private.generation_repair_review_lineage(
      new.organization_id,
      new.media_object_id
    );
  if lineage is null then
    return new;
  end if;
  if new.input ->> 'generation_job_id'
       is distinct from lineage ->> 'generation_job_id' then
    raise exception using
      errcode = '55000',
      message = 'generation_repair_review_job_mismatch';
  end if;
  new.parent_review_id := (lineage ->> 'source_review_id')::uuid;
  return new;
end;
$$;

revoke all on function
  content_factory_private.enforce_generation_repair_review_lineage()
  from public, anon, authenticated, service_role;

drop trigger if exists generation_repair_review_lineage_guard
  on content_factory.content_review_runs;
create trigger generation_repair_review_lineage_guard
before insert on content_factory.content_review_runs
for each row execute function
  content_factory_private.enforce_generation_repair_review_lineage();

-- The legacy start command validates a caller-supplied parent before INSERT.
-- Resolve the immutable repair parent first so an unrelated "latest product"
-- review cannot reject or redirect a valid repair review.
alter function public.creator_start_content_review(jsonb)
  rename to creator_start_content_review_pre_repair_lineage_v1;
alter function public.creator_start_content_review_pre_repair_lineage_v1(jsonb)
  set schema content_factory_private;
revoke all on function
  content_factory_private.creator_start_content_review_pre_repair_lineage_v1(
    jsonb
  )
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_content_review(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  media_id_value uuid;
  lineage jsonb;
  result_value jsonb;
  review_id_value uuid;
  review_row content_factory.content_review_runs%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );

  if p_payload ? 'media_id' then
    media_id_value :=
      content_factory_private.require_uuid(p_payload, 'media_id');
  else
    media_id_value :=
      content_factory_private.require_uuid(p_payload, 'media_object_id');
  end if;
  lineage :=
    content_factory_private.generation_repair_review_lineage(
      organization_id,
      media_id_value
    );
  if lineage is not null then
    p_payload := jsonb_set(
      p_payload,
      '{parent_review_id}',
      to_jsonb(lineage ->> 'source_review_id'),
      true
    );
  end if;

  result_value :=
    content_factory_private
      .creator_start_content_review_pre_repair_lineage_v1(p_payload);
  if lineage is null then
    return result_value;
  end if;

  review_id_value :=
    content_factory_private.require_uuid(result_value, 'review_id');
  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id
    and review.id = review_id_value;
  if review_row.id is null
     or review_row.media_object_id is distinct from media_id_value
     or review_row.parent_review_id::text
          is distinct from lineage ->> 'source_review_id' then
    raise exception using
      errcode = '55000',
      message = 'generation_repair_review_lineage_not_bound';
  end if;

  return result_value || jsonb_build_object(
    'repair_lineage',
    lineage
  );
end;
$$;

revoke all on function public.creator_start_content_review(jsonb)
  from public, anon;
grant execute on function public.creator_start_content_review(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
