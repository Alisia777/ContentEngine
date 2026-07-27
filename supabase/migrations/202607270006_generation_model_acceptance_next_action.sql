begin;

-- Keep the immutable acceptance verdict separate from workflow navigation.
-- This helper exposes only opaque identifiers for the newest exact paid output
-- that still lacks an independent decision. It deliberately excludes storage
-- object names, signed URLs, participant identities, prompts, and review data.
create or replace function
  content_factory_private.generation_model_acceptance_pending(
    p_organization_id uuid
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  model_row record;
  pending_row record;
  pending_value jsonb := '{}'::jsonb;
begin
  if p_organization_id is null then
    raise exception using
      errcode = '22023',
      message = 'generation_model_acceptance_organization_required';
  end if;

  for model_row in
    select *
    from (
      values
        (
          1,
          'seedream5_lite'::text,
          'generated_image'::text,
          'image/png'::text
        ),
        (
          2,
          'gen4_turbo'::text,
          'generated_video'::text,
          'video/mp4'::text
        ),
        (
          3,
          'seedance2_fast'::text,
          'generated_video'::text,
          'video/mp4'::text
        )
    ) catalog(position, model, media_kind, mime_type)
    order by position
  loop
    with exact_outputs as (
      select
        job.id as generation_job_id,
        job.product_id,
        job.requested_by,
        job.assigned_to,
        job.created_at as job_created_at,
        media.id as media_id,
        media.owner_id,
        media.sha256 as media_sha256
      from content_factory.generation_jobs job
      join content_factory.media_objects media
        on media.organization_id = job.organization_id
       and media.id::text = job.output ->> 'output_media_id'
       and media.product_id = job.product_id
       and media.status = 'ready'
       and media.mime_type = model_row.mime_type
       and media.sha256 = job.output ->> 'sha256'
       and media.metadata ->> 'kind' = model_row.media_kind
       and media.metadata ->> 'provider' = 'runway'
       and media.metadata ->> 'model' = model_row.model
       and media.metadata ->> 'generation_job_id' = job.id::text
      where job.organization_id = p_organization_id
        and job.mode = 'real'
        and job.provider = 'runway'
        and job.allow_real_spend
        and job.status = 'succeeded'
        and job.actual_cost_minor > 0
        and job.actual_cost_minor = job.estimated_cost_minor
        and job.input ->> 'model' = model_row.model
    )
    select
      output.generation_job_id,
      output.media_id,
      review.id as review_id,
      coalesce(review.status, 'not_started') as review_status,
      output.job_created_at,
      review.created_at as review_created_at
    into pending_row
    from exact_outputs output
    left join lateral (
      select
        candidate.id,
        candidate.status,
        candidate.created_at
      from content_factory.content_review_runs candidate
      where candidate.organization_id = p_organization_id
        and candidate.media_object_id = output.media_id
        and candidate.media_sha256_snapshot = output.media_sha256
        and candidate.input ->> 'generation_job_id' =
              output.generation_job_id::text
        and candidate.input -> 'ai_generated' = 'true'::jsonb
        and candidate.input -> 'external_ai_processing_confirmed' =
              'true'::jsonb
      order by candidate.created_at desc, candidate.id desc
      limit 1
    ) review on true
    where not exists (
      select 1
      from content_factory.content_review_runs decided_review
      join content_factory.content_review_decisions decision
        on decision.organization_id = decided_review.organization_id
       and decision.review_id = decided_review.id
       and decision.review_completion_hash =
             decided_review.completion_hash
       and decision.media_sha256_snapshot =
             output.media_sha256
       and decision.media_watched_confirmed
       and decision.decided_by <> output.requested_by
       and decision.decided_by <> output.assigned_to
       and decision.decided_by <> output.owner_id
      where decided_review.organization_id = p_organization_id
        and decided_review.media_object_id = output.media_id
        and decided_review.status = 'completed'
        and decided_review.completion_hash is not null
        and decided_review.media_sha256_snapshot =
              output.media_sha256
        and decided_review.model_provider is not null
        and decided_review.model_version is not null
        and decided_review.input ->> 'generation_job_id' =
              output.generation_job_id::text
        and decided_review.input -> 'ai_generated' =
              'true'::jsonb
        and decided_review.input
              -> 'external_ai_processing_confirmed' =
              'true'::jsonb
    )
    order by output.job_created_at desc, output.generation_job_id desc
    limit 1;

    pending_value := pending_value || jsonb_build_object(
      model_row.model,
      case
        when pending_row.generation_job_id is null then null
        else jsonb_build_object(
          'generation_job_id', pending_row.generation_job_id,
          'media_id', pending_row.media_id,
          'review_id', pending_row.review_id,
          'review_status', pending_row.review_status,
          'created_at', coalesce(
            pending_row.review_created_at,
            pending_row.job_created_at
          )
        )
      end
    );
  end loop;

  return pending_value;
end;
$$;

revoke all on function
  content_factory_private.generation_model_acceptance_pending(uuid)
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_model_acceptance(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  organization_id uuid;
  acceptance_value jsonb;
  pending_value jsonb;
  models_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'generation_model_acceptance_payload_invalid';
  end if;
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );

  acceptance_value :=
    content_factory_private.generation_model_acceptance(
      organization_id
    );
  pending_value :=
    content_factory_private.generation_model_acceptance_pending(
      organization_id
    );

  select coalesce(
    jsonb_agg(
      model.value || jsonb_build_object(
        'pending_review',
        pending_value -> (model.value ->> 'model')
      )
      order by model.ordinality
    ),
    '[]'::jsonb
  )
  into models_value
  from jsonb_array_elements(
    acceptance_value -> 'models'
  ) with ordinality model(value, ordinality);

  return jsonb_set(
    acceptance_value || jsonb_build_object(
      'version', 'generation-model-acceptance-v2'
    ),
    '{models}',
    models_value,
    false
  );
end;
$$;

revoke all on function
  public.creator_generation_model_acceptance(jsonb)
  from public, anon;
grant execute on function
  public.creator_generation_model_acceptance(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
