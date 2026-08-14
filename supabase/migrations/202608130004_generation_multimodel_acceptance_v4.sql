begin;

-- Preserve the mature three-model public resolver byte-for-byte behind a
-- private seam before installing the one all-catalog public owner.  The seam
-- keeps historical evidence, pending-review and freshness semantics intact;
-- it is never exposed as a second application endpoint.
alter function public.creator_generation_model_acceptance(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_model_acceptance(jsonb)
  rename to creator_generation_model_acceptance_pre_multimodel_v49;

revoke all on function
  content_factory_private
    .creator_generation_model_acceptance_pre_multimodel_v49(jsonb)
  from public, anon, authenticated, service_role;

-- The identity order is presentation-stable.  Every descriptive or policy
-- field is still read from the canonical 130002 catalog functions below, so
-- this list cannot silently invent a label, lifecycle, launch state or reason.
create or replace function
  content_factory_private.generation_acceptance_catalog_v49()
returns table(catalog_position integer, provider text, model text)
language sql
immutable
set search_path = ''
as $$
  select catalog.catalog_position, catalog.provider, catalog.model
  from (values
    (1,  'runway'::text, 'seedream5_lite'::text),
    (2,  'runway'::text, 'gen4_turbo'::text),
    (3,  'runway'::text, 'seedance2_fast'::text),
    (4,  'runway'::text, 'gen4.5'::text),
    (5,  'runway'::text, 'seedance2_mini'::text),
    (6,  'runway'::text, 'veo3.1_fast'::text),
    (7,  'runway'::text, 'gemini_omni_flash'::text),
    (8,  'runway'::text, 'veo3.1'::text),
    (9,  'runway'::text, 'seedance2'::text),
    (10, 'google'::text, 'veo-3.1-lite-generate-preview'::text)
  ) catalog(catalog_position, provider, model)
  order by catalog.catalog_position
$$;

revoke all on function
  content_factory_private.generation_acceptance_catalog_v49()
  from public, anon, authenticated, service_role;

-- A ready file or a provider response is not evidence.  An exact output must
-- be linked to a real, spend-enabled, paid and succeeded job and must repeat
-- the same provider/model/job/SHA identity in immutable job and media facts.
create or replace function
  content_factory_private.generation_acceptance_exact_outputs_v49(
    p_organization_id uuid,
    p_provider text,
    p_model text
  )
returns table(
  generation_job_id uuid,
  product_id uuid,
  requested_by uuid,
  assigned_to uuid,
  job_created_at timestamptz,
  media_id uuid,
  owner_id uuid,
  media_sha256 text
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    job.id,
    job.product_id,
    job.requested_by,
    job.assigned_to,
    job.created_at,
    media.id,
    media.owner_id,
    media.sha256
  from content_factory.generation_jobs job
  join content_factory.media_objects media
    on media.organization_id = job.organization_id
   and media.id::text = job.output ->> 'output_media_id'
   and media.product_id = job.product_id
   and media.status = 'ready'
   and media.sha256 = job.output ->> 'sha256'
   and media.mime_type = case
     when content_factory_private.generation_catalog_entry(
       p_provider, p_model
     ) ->> 'content_kind' = 'photo' then 'image/png'
     else 'video/mp4'
   end
   and media.metadata ->> 'kind' = case
     when content_factory_private.generation_catalog_entry(
       p_provider, p_model
     ) ->> 'content_kind' = 'photo' then 'generated_image'
     else 'generated_video'
   end
   and media.metadata ->> 'provider' = p_provider
   and media.metadata ->> 'model' = p_model
   and media.metadata ->> 'generation_job_id' = job.id::text
  where p_organization_id is not null
    and exists (
      select 1
      from content_factory_private.generation_acceptance_catalog_v49()
        catalog
      where catalog.provider = p_provider
        and catalog.model = p_model
    )
    and job.organization_id = p_organization_id
    and job.mode = 'real'
    and job.provider = p_provider
    and job.allow_real_spend
    and job.status = 'succeeded'
    and job.actual_cost_minor > 0
    and job.actual_cost_minor = job.estimated_cost_minor
    and job.input ->> 'model' = p_model
$$;

revoke all on function
  content_factory_private.generation_acceptance_exact_outputs_v49(
    uuid, text, text
  )
  from public, anon, authenticated, service_role;

-- Only an exact completed AI-QA review with an independently watched human
-- decision can enter the evidence set.  Context binding is kept explicit so
-- an otherwise good approval remains needs_revalidation until the immutable
-- amendment chain is complete.
create or replace function
  content_factory_private.generation_acceptance_decisions_v49(
    p_organization_id uuid,
    p_provider text,
    p_model text
  )
returns table(
  generation_job_id uuid,
  media_id uuid,
  media_sha256 text,
  review_id uuid,
  parent_review_id uuid,
  completion_hash text,
  review_model_provider text,
  review_model_version text,
  review_finished_at timestamptz,
  decision_id uuid,
  decision text,
  decided_by uuid,
  decided_at timestamptz,
  overall_score integer,
  blockers_count integer,
  compliance_status text,
  context_bound boolean
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    output.generation_job_id,
    output.media_id,
    output.media_sha256,
    review.id,
    review.parent_review_id,
    review.completion_hash,
    review.model_provider,
    review.model_version,
    review.finished_at,
    human_decision.id,
    human_decision.decision,
    human_decision.decided_by,
    human_decision.created_at,
    (review.result ->> 'overall_score')::integer,
    coalesce((review.result ->> 'blockers_count')::integer, 0),
    review.result ->> 'compliance_status',
    exists (
      select 1
      from content_factory.content_review_context_amendments amendment
      join content_factory.content_review_runs source_review
        on source_review.organization_id = amendment.organization_id
       and source_review.id = amendment.source_review_id
       and source_review.media_object_id = output.media_id
       and source_review.status = 'completed'
       and source_review.completion_hash = amendment.source_completion_hash
       and source_review.media_sha256_snapshot = output.media_sha256
       and source_review.model_provider is not null
       and source_review.model_version is not null
      where amendment.organization_id = p_organization_id
        and amendment.amended_review_id = review.id
        and amendment.generation_job_id = output.generation_job_id
        and amendment.media_object_id = output.media_id
        and amendment.product_id = output.product_id
        and amendment.amended_completion_hash = review.completion_hash
        and amendment.created_by = human_decision.decided_by
        and review.parent_review_id = source_review.id
        and review.input #>> '{context_amendment,source_review_id}' =
              source_review.id::text
        and review.input #>>
              '{context_amendment,source_completion_hash}' =
              source_review.completion_hash
        and review.input #>> '{context_amendment,external_ai_invoked}' =
              'false'
        and review.input #>>
              '{context_amendment,provider_analysis_reused}' = 'true'
    )
  from content_factory_private.generation_acceptance_exact_outputs_v49(
    p_organization_id, p_provider, p_model
  ) output
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
   and review.input -> 'external_ai_processing_confirmed' = 'true'::jsonb
   and coalesce(review.result ->> 'overall_score', '') ~ '^[0-9]{1,3}$'
   and (review.result ->> 'overall_score')::integer between 0 and 100
   and coalesce(review.result ->> 'blockers_count', '0') ~ '^[0-9]{1,3}$'
  join content_factory.content_review_decisions human_decision
    on human_decision.organization_id = review.organization_id
   and human_decision.review_id = review.id
   and human_decision.review_completion_hash = review.completion_hash
   and human_decision.media_sha256_snapshot = output.media_sha256
   and human_decision.media_watched_confirmed
   and human_decision.decided_by <> output.requested_by
   and human_decision.decided_by <> output.assigned_to
   and human_decision.decided_by <> output.owner_id
$$;

revoke all on function
  content_factory_private.generation_acceptance_decisions_v49(
    uuid, text, text
  )
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_model_acceptance_v49(
    p_organization_id uuid,
    p_provider text,
    p_model text,
    p_evaluated_at timestamptz
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  evidence_max_age_days constant integer := 90;
  catalog_value jsonb;
  evidence_row record;
  pending_row record;
  successful_runs_value integer := 0;
  reviewed_runs_value integer := 0;
  accepted_runs_value integer := 0;
  pending_review_runs_value integer := 0;
  status_value text;
  reason_code_value text;
  next_action_code_value text;
  evidence_value jsonb := null;
  pending_value jsonb := null;
  expires_at_value timestamptz;
  evidence_fresh_value boolean := false;
begin
  if p_organization_id is null or p_evaluated_at is null then
    raise exception using
      errcode = '22023',
      message = 'generation_model_acceptance_organization_required';
  end if;

  select content_factory_private.generation_catalog_entry(
    catalog.provider, catalog.model
  )
  into catalog_value
  from content_factory_private.generation_acceptance_catalog_v49() catalog
  where catalog.provider = p_provider
    and catalog.model = p_model;

  if catalog_value is null then
    raise exception using
      errcode = '22023',
      message = 'generation_model_acceptance_model_unknown';
  end if;

  select
    count(*)::integer,
    count(*) filter (where exists (
      select 1
      from content_factory_private.generation_acceptance_decisions_v49(
        p_organization_id, p_provider, p_model
      ) evidence
      where evidence.generation_job_id = output.generation_job_id
    ))::integer,
    count(*) filter (where exists (
      select 1
      from content_factory_private.generation_acceptance_decisions_v49(
        p_organization_id, p_provider, p_model
      ) evidence
      where evidence.generation_job_id = output.generation_job_id
        and evidence.decision = 'approved'
        and evidence.context_bound
        and evidence.overall_score >= 80
        and evidence.blockers_count = 0
        and evidence.compliance_status is not null
        and evidence.compliance_status <> 'block'
    ))::integer,
    count(*) filter (where not exists (
      select 1
      from content_factory_private.generation_acceptance_decisions_v49(
        p_organization_id, p_provider, p_model
      ) evidence
      where evidence.generation_job_id = output.generation_job_id
    ))::integer
  into
    successful_runs_value,
    reviewed_runs_value,
    accepted_runs_value,
    pending_review_runs_value
  from content_factory_private.generation_acceptance_exact_outputs_v49(
    p_organization_id, p_provider, p_model
  ) output;

  select evidence.*
  into evidence_row
  from content_factory_private.generation_acceptance_decisions_v49(
    p_organization_id, p_provider, p_model
  ) evidence
  order by evidence.decided_at desc, evidence.decision_id desc
  limit 1;

  select
    output.generation_job_id,
    output.media_id,
    latest_review.id as review_id,
    coalesce(latest_review.status, 'not_started') as review_status,
    coalesce(latest_review.created_at, output.job_created_at) as created_at
  into pending_row
  from content_factory_private.generation_acceptance_exact_outputs_v49(
    p_organization_id, p_provider, p_model
  ) output
  left join lateral (
    select candidate.id, candidate.status, candidate.created_at
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
  ) latest_review on true
  where not exists (
    select 1
    from content_factory_private.generation_acceptance_decisions_v49(
      p_organization_id, p_provider, p_model
    ) evidence
    where evidence.generation_job_id = output.generation_job_id
  )
  order by output.job_created_at desc, output.generation_job_id desc
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
  else
    expires_at_value := evidence_row.decided_at +
      make_interval(days => evidence_max_age_days);
    evidence_fresh_value := expires_at_value > p_evaluated_at;

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
      'context_bound', evidence_row.context_bound,
      'fresh', evidence_fresh_value,
      'expires_at', expires_at_value
    );

    if evidence_row.decision <> 'approved' then
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
    elsif not evidence_fresh_value then
      status_value := 'needs_revalidation';
      reason_code_value := 'acceptance_evidence_stale';
      next_action_code_value := 'generate_replacement_and_approve';
    else
      status_value := 'accepted';
      reason_code_value := 'latest_independent_approval_accepted';
      next_action_code_value := 'none';
    end if;
  end if;

  if pending_row.generation_job_id is not null then
    pending_value := jsonb_build_object(
      'generation_job_id', pending_row.generation_job_id,
      'media_id', pending_row.media_id,
      'review_id', pending_row.review_id,
      'review_status', pending_row.review_status,
      'created_at', pending_row.created_at
    );
  end if;

  return jsonb_build_object(
    'model', p_model,
    'content_kind', catalog_value ->> 'content_kind',
    'status', status_value,
    'reason_code', reason_code_value,
    'next_action_code', next_action_code_value,
    'quality_threshold', 80,
    'evidence_max_age_days', evidence_max_age_days,
    'successful_runs', successful_runs_value,
    'reviewed_runs', reviewed_runs_value,
    'accepted_runs', accepted_runs_value,
    'pending_review_runs', pending_review_runs_value,
    'evidence', evidence_value,
    'pending_review', pending_value
  );
end;
$$;

revoke all on function
  content_factory_private.generation_model_acceptance_v49(
    uuid, text, text, timestamptz
  )
  from public, anon, authenticated, service_role;

-- Merge legacy rows without replacing any mature evidence or workflow field.
-- Catalog metadata is additive and comes only from the canonical SQL owner.
create or replace function
  content_factory_private.generation_model_acceptance_catalog_v49(
    p_organization_id uuid,
    p_evaluated_at timestamptz,
    p_legacy_acceptance jsonb
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  catalog_row record;
  catalog_value jsonb;
  model_value jsonb;
  models_value jsonb := '[]'::jsonb;
  accepted_count_value integer := 0;
  launch_enabled_value boolean;
  disabled_reason_value text;
begin
  if p_organization_id is null
     or p_evaluated_at is null
     or jsonb_typeof(p_legacy_acceptance) <> 'object'
     or jsonb_typeof(p_legacy_acceptance -> 'models') <> 'array' then
    raise exception using
      errcode = '22023',
      message = 'generation_model_acceptance_catalog_invalid';
  end if;

  for catalog_row in
    select *
    from content_factory_private.generation_acceptance_catalog_v49()
    order by catalog_position
  loop
    catalog_value := content_factory_private.generation_catalog_entry(
      catalog_row.provider, catalog_row.model
    );
    if catalog_value is null then
      raise exception using
        errcode = '55000',
        message = 'generation_model_acceptance_catalog_drift';
    end if;

    if catalog_row.provider = 'runway'
       and catalog_row.model in (
         'seedream5_lite', 'gen4_turbo', 'seedance2_fast'
       ) then
      select legacy_model.value
      into model_value
      from jsonb_array_elements(
        p_legacy_acceptance -> 'models'
      ) legacy_model(value)
      where legacy_model.value ->> 'model' = catalog_row.model
      limit 1;
      if model_value is null then
        raise exception using
          errcode = '55000',
          message = 'generation_model_acceptance_legacy_drift';
      end if;
    else
      model_value := content_factory_private.generation_model_acceptance_v49(
        p_organization_id,
        catalog_row.provider,
        catalog_row.model,
        p_evaluated_at
      );
    end if;

    launch_enabled_value := content_factory_private
      .generation_provider_launch_enabled(
        p_organization_id, catalog_row.provider, catalog_row.model
      );
    disabled_reason_value := content_factory_private
      .generation_provider_disabled_reason(
        p_organization_id, catalog_row.provider, catalog_row.model
      );

    model_value := model_value || jsonb_build_object(
      'provider', catalog_row.provider,
      'model', catalog_row.model,
      'public_label', catalog_value ->> 'public_label',
      'content_kind', catalog_value ->> 'content_kind',
      'lifecycle', catalog_value ->> 'lifecycle',
      'enabled_by_default',
        (catalog_value ->> 'enabled_by_default')::boolean,
      'enabled', launch_enabled_value,
      'launch_enabled', launch_enabled_value,
      'disabled_reason_code', disabled_reason_value,
      'feature_flag', catalog_value ->> 'feature_flag',
      'catalog_version',
        content_factory_private.generation_catalog_version(),
      'pricing_version', catalog_value ->> 'pricing_version',
      'automatic_generation', false,
      'automatic_spend', false
    );

    if model_value ->> 'status' = 'accepted' then
      accepted_count_value := accepted_count_value + 1;
    end if;
    models_value := models_value || jsonb_build_array(model_value);
  end loop;

  return jsonb_build_object(
    'version', 'generation-model-acceptance-v4',
    'provider', p_legacy_acceptance ->> 'provider',
    'providers', jsonb_build_array('runway', 'google'),
    'catalog_version', content_factory_private.generation_catalog_version(),
    'quality_threshold', 80,
    'evidence_max_age_days', 90,
    'accepted_count', accepted_count_value,
    'total_models', jsonb_array_length(models_value),
    'all_models_accepted',
      jsonb_array_length(models_value) > 0
      and accepted_count_value = jsonb_array_length(models_value),
    'models', models_value,
    'evaluated_at', p_evaluated_at,
    'automatic_generation', false,
    'automatic_spend', false
  );
end;
$$;

revoke all on function
  content_factory_private.generation_model_acceptance_catalog_v49(
    uuid, timestamptz, jsonb
  )
  from public, anon, authenticated, service_role;

-- Keep the installed paid-launch seam name, but allow every canonical model
-- to read only the real acceptance owner.  Historical models still use their
-- mature v3 resolver; new identities use the provider+model exact resolver.
create or replace function
  content_factory_private.generation_model_acceptance_status_v48(
    p_organization_id uuid,
    p_provider text,
    p_model text
  )
returns text
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  provider_value text := lower(btrim(coalesce(p_provider, '')));
  model_value text := lower(btrim(coalesce(p_model, '')));
  acceptance_value jsonb;
  status_value text;
begin
  if provider_value = 'runway'
     and model_value in (
       'seedream5_lite', 'gen4_turbo', 'seedance2_fast'
     ) then
    acceptance_value := content_factory_private
      .generation_model_acceptance_freshness(
        content_factory_private.generation_model_acceptance(
          p_organization_id
        ),
        now()
      );
    select item.value ->> 'status'
    into status_value
    from jsonb_array_elements(acceptance_value -> 'models') item(value)
    where item.value ->> 'model' = model_value
    limit 1;
  elsif content_factory_private.generation_catalog_entry(
          provider_value, model_value
        ) is not null then
    status_value := content_factory_private.generation_model_acceptance_v49(
      p_organization_id, provider_value, model_value, now()
    ) ->> 'status';
  end if;
  return coalesce(status_value, 'unproven');
end;
$$;

revoke all on function
  content_factory_private.generation_model_acceptance_status_v48(
    uuid, text, text
  )
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
  legacy_acceptance_value jsonb;
  evaluated_at_value timestamptz;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'generation_model_acceptance_payload_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );

  legacy_acceptance_value := content_factory_private
    .creator_generation_model_acceptance_pre_multimodel_v49(p_payload);
  begin
    evaluated_at_value :=
      (legacy_acceptance_value ->> 'evaluated_at')::timestamptz;
  exception
    when invalid_datetime_format or datetime_field_overflow then
      raise exception using
        errcode = '55000',
        message = 'generation_model_acceptance_legacy_drift';
  end;

  return content_factory_private.generation_model_acceptance_catalog_v49(
    organization_id,
    evaluated_at_value,
    legacy_acceptance_value
  );
end;
$$;

revoke all on function
  public.creator_generation_model_acceptance(jsonb)
  from public, anon, service_role;
grant execute on function
  public.creator_generation_model_acceptance(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
