begin;

-- Provider balance and a successful API response prove availability, not
-- production quality.  Derive model readiness only from the immutable chain:
-- real paid job -> exact stored output -> completed AI review -> independent
-- human decision.  An approval additionally needs the context-bound review
-- created by the generated-media approval RPC, a clean blocker result, and
-- an explicit minimum quality score.
create or replace function
  content_factory_private.generation_model_acceptance(
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
  evidence_row record;
  successful_runs_value integer;
  reviewed_runs_value integer;
  accepted_runs_value integer;
  pending_review_runs_value integer;
  accepted_count_value integer := 0;
  status_value text;
  reason_code_value text;
  next_action_code_value text;
  models_value jsonb := '[]'::jsonb;
  evidence_value jsonb;
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
          'photo'::text,
          'generated_image'::text,
          'image/png'::text
        ),
        (
          2,
          'gen4_turbo'::text,
          'video'::text,
          'generated_video'::text,
          'video/mp4'::text
        ),
        (
          3,
          'seedance2_fast'::text,
          'video'::text,
          'generated_video'::text,
          'video/mp4'::text
        )
    ) catalog(
      position,
      model,
      content_kind,
      media_kind,
      mime_type
    )
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
    ),
    decision_evidence as (
      select
        output.generation_job_id,
        output.media_id,
        output.media_sha256,
        review.id as review_id,
        review.parent_review_id,
        review.completion_hash,
        review.model_provider as review_model_provider,
        review.model_version as review_model_version,
        review.finished_at as review_finished_at,
        decision.id as decision_id,
        decision.decision,
        decision.decided_by,
        decision.created_at as decided_at,
        (review.result ->> 'overall_score')::integer
          as overall_score,
        coalesce(
          (review.result ->> 'blockers_count')::integer,
          0
        ) as blockers_count,
        review.result ->> 'compliance_status'
          as compliance_status,
        exists (
          select 1
          from content_factory.content_review_context_amendments amendment
          join content_factory.content_review_runs source_review
            on source_review.organization_id = amendment.organization_id
           and source_review.id = amendment.source_review_id
           and source_review.media_object_id = output.media_id
           and source_review.status = 'completed'
           and source_review.completion_hash =
                 amendment.source_completion_hash
           and source_review.media_sha256_snapshot =
                 output.media_sha256
           and source_review.model_provider is not null
           and source_review.model_version is not null
          where amendment.organization_id = p_organization_id
            and amendment.amended_review_id = review.id
            and amendment.generation_job_id =
                  output.generation_job_id
            and amendment.media_object_id = output.media_id
            and amendment.product_id = output.product_id
            and amendment.amended_completion_hash =
                  review.completion_hash
            and amendment.created_by = decision.decided_by
            and review.parent_review_id = source_review.id
            and review.input #>> '{context_amendment,source_review_id}'
                  = source_review.id::text
            and review.input
                  #>> '{context_amendment,source_completion_hash}'
                  = source_review.completion_hash
            and review.input
                  #>> '{context_amendment,external_ai_invoked}'
                  = 'false'
            and review.input
                  #>> '{context_amendment,provider_analysis_reused}'
                  = 'true'
        ) as context_bound
      from exact_outputs output
      join content_factory.content_review_runs review
        on review.organization_id = p_organization_id
       and review.media_object_id = output.media_id
       and review.status = 'completed'
       and review.completion_hash is not null
       and review.media_sha256_snapshot = output.media_sha256
       and review.model_provider is not null
       and review.model_version is not null
       and review.input ->> 'generation_job_id' =
             output.generation_job_id::text
       and review.input -> 'ai_generated' = 'true'::jsonb
       and review.input -> 'external_ai_processing_confirmed' =
             'true'::jsonb
       and coalesce(review.result ->> 'overall_score', '')
             ~ '^[0-9]{1,3}$'
       and (review.result ->> 'overall_score')::integer
             between 0 and 100
       and coalesce(review.result ->> 'blockers_count', '0')
             ~ '^[0-9]{1,3}$'
      join content_factory.content_review_decisions decision
        on decision.organization_id = review.organization_id
       and decision.review_id = review.id
       and decision.review_completion_hash = review.completion_hash
       and decision.media_sha256_snapshot = output.media_sha256
       and decision.media_watched_confirmed
       and decision.decided_by <> output.requested_by
       and decision.decided_by <> output.assigned_to
       and decision.decided_by <> output.owner_id
    )
    select
      (select count(*)::integer from exact_outputs),
      (select count(*)::integer from decision_evidence),
      (
        select count(*)::integer
        from decision_evidence evidence
        where evidence.decision = 'approved'
          and evidence.context_bound
          and evidence.overall_score >= 80
          and evidence.blockers_count = 0
          and evidence.compliance_status is not null
          and evidence.compliance_status <> 'block'
      ),
      (
        select count(*)::integer
        from exact_outputs output
        where not exists (
          select 1
          from decision_evidence evidence
          where evidence.generation_job_id =
                output.generation_job_id
        )
      )
    into
      successful_runs_value,
      reviewed_runs_value,
      accepted_runs_value,
      pending_review_runs_value;

    with exact_outputs as (
      select
        job.id as generation_job_id,
        job.product_id,
        job.requested_by,
        job.assigned_to,
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
      output.media_sha256,
      review.id as review_id,
      review.completion_hash,
      review.model_provider as review_model_provider,
      review.model_version as review_model_version,
      review.finished_at as review_finished_at,
      decision.id as decision_id,
      decision.decision,
      decision.decided_by,
      decision.created_at as decided_at,
      (review.result ->> 'overall_score')::integer
        as overall_score,
      coalesce(
        (review.result ->> 'blockers_count')::integer,
        0
      ) as blockers_count,
      review.result ->> 'compliance_status'
        as compliance_status,
      exists (
        select 1
        from content_factory.content_review_context_amendments amendment
        join content_factory.content_review_runs source_review
          on source_review.organization_id = amendment.organization_id
         and source_review.id = amendment.source_review_id
         and source_review.media_object_id = output.media_id
         and source_review.status = 'completed'
         and source_review.completion_hash =
               amendment.source_completion_hash
         and source_review.media_sha256_snapshot =
               output.media_sha256
         and source_review.model_provider is not null
         and source_review.model_version is not null
        where amendment.organization_id = p_organization_id
          and amendment.amended_review_id = review.id
          and amendment.generation_job_id =
                output.generation_job_id
          and amendment.media_object_id = output.media_id
          and amendment.product_id = output.product_id
          and amendment.amended_completion_hash =
                review.completion_hash
          and amendment.created_by = decision.decided_by
          and review.parent_review_id = source_review.id
          and review.input #>> '{context_amendment,source_review_id}'
                = source_review.id::text
          and review.input
                #>> '{context_amendment,source_completion_hash}'
                = source_review.completion_hash
          and review.input
                #>> '{context_amendment,external_ai_invoked}'
                = 'false'
          and review.input
                #>> '{context_amendment,provider_analysis_reused}'
                = 'true'
      ) as context_bound
    into evidence_row
    from exact_outputs output
    join content_factory.content_review_runs review
      on review.organization_id = p_organization_id
     and review.media_object_id = output.media_id
     and review.status = 'completed'
     and review.completion_hash is not null
     and review.media_sha256_snapshot = output.media_sha256
     and review.model_provider is not null
     and review.model_version is not null
     and review.input ->> 'generation_job_id' =
           output.generation_job_id::text
     and review.input -> 'ai_generated' = 'true'::jsonb
     and review.input -> 'external_ai_processing_confirmed' =
           'true'::jsonb
     and coalesce(review.result ->> 'overall_score', '')
           ~ '^[0-9]{1,3}$'
     and (review.result ->> 'overall_score')::integer
           between 0 and 100
     and coalesce(review.result ->> 'blockers_count', '0')
           ~ '^[0-9]{1,3}$'
    join content_factory.content_review_decisions decision
      on decision.organization_id = review.organization_id
     and decision.review_id = review.id
     and decision.review_completion_hash = review.completion_hash
     and decision.media_sha256_snapshot = output.media_sha256
     and decision.media_watched_confirmed
     and decision.decided_by <> output.requested_by
     and decision.decided_by <> output.assigned_to
     and decision.decided_by <> output.owner_id
    order by decision.created_at desc, decision.id desc
    limit 1;

    if evidence_row.decision_id is null then
      status_value := 'unproven';
      if successful_runs_value > 0 then
        reason_code_value := 'independent_review_missing';
        next_action_code_value := 'review_succeeded_output';
      else
        reason_code_value := 'real_output_missing';
        next_action_code_value := 'run_paid_smoke_and_approve';
      end if;
      evidence_value := null;
    elsif evidence_row.decision <> 'approved' then
      status_value := 'needs_revalidation';
      reason_code_value := 'latest_decision_not_approved';
      next_action_code_value := 'generate_replacement_and_approve';
    elsif not evidence_row.context_bound then
      status_value := 'needs_revalidation';
      reason_code_value := 'approval_context_not_bound';
      next_action_code_value := 'complete_context_approval';
    elsif evidence_row.blockers_count > 0 then
      status_value := 'needs_revalidation';
      reason_code_value := 'quality_blockers_present';
      next_action_code_value := 'generate_replacement_and_approve';
    elsif evidence_row.compliance_status is null
       or evidence_row.compliance_status = 'block' then
      status_value := 'needs_revalidation';
      reason_code_value := 'compliance_blocked';
      next_action_code_value := 'generate_replacement_and_approve';
    elsif evidence_row.overall_score < 80 then
      status_value := 'needs_revalidation';
      reason_code_value := 'quality_score_below_threshold';
      next_action_code_value := 'generate_replacement_and_approve';
    else
      status_value := 'accepted';
      reason_code_value := 'latest_independent_approval_accepted';
      next_action_code_value := 'none';
      accepted_count_value := accepted_count_value + 1;
    end if;

    if evidence_row.decision_id is not null then
      evidence_value := jsonb_build_object(
        'generation_job_id', evidence_row.generation_job_id,
        'media_id', evidence_row.media_id,
        'media_sha256', evidence_row.media_sha256,
        'review_id', evidence_row.review_id,
        'review_completion_hash', evidence_row.completion_hash,
        'review_model_provider', evidence_row.review_model_provider,
        'review_model_version', evidence_row.review_model_version,
        'review_finished_at', evidence_row.review_finished_at,
        'decision_id', evidence_row.decision_id,
        'decision', evidence_row.decision,
        'decided_by', evidence_row.decided_by,
        'decided_at', evidence_row.decided_at,
        'overall_score', evidence_row.overall_score,
        'blockers_count', evidence_row.blockers_count,
        'compliance_status', evidence_row.compliance_status,
        'media_watched_confirmed', true,
        'independent_reviewer', true,
        'context_bound', evidence_row.context_bound
      );
    end if;

    models_value := models_value || jsonb_build_array(
      jsonb_build_object(
        'model', model_row.model,
        'content_kind', model_row.content_kind,
        'status', status_value,
        'reason_code', reason_code_value,
        'next_action_code', next_action_code_value,
        'quality_threshold', 80,
        'successful_runs', successful_runs_value,
        'reviewed_runs', reviewed_runs_value,
        'accepted_runs', accepted_runs_value,
        'pending_review_runs', pending_review_runs_value,
        'evidence', evidence_value
      )
    );
  end loop;

  return jsonb_build_object(
    'version', 'generation-model-acceptance-v1',
    'provider', 'runway',
    'quality_threshold', 80,
    'accepted_count', accepted_count_value,
    'total_models', 3,
    'all_models_accepted', accepted_count_value = 3,
    'models', models_value,
    'evaluated_at', now()
  );
end;
$$;

revoke all on function
  content_factory_private.generation_model_acceptance(uuid)
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
  return
    content_factory_private.generation_model_acceptance(
      organization_id
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
