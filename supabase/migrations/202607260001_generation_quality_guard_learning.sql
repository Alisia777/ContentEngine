begin;

-- The existing learning resolver selects a structural creative angle from
-- bounded exploration, independent QA or mature publication performance.
-- Preserve that audited decision and add a second, strictly enumerated layer:
-- recurring weak score dimensions become hard-coded prompt guards.  Raw
-- findings, recommendations, reviewer comments and generated copy never enter
-- a future prompt.
alter function public.creator_generation_learning_policy(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_learning_policy(jsonb)
  rename to creator_generation_learning_policy_independent_quality_v3;

revoke all on function
  content_factory_private
    .creator_generation_learning_policy_independent_quality_v3(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_learning_policy(
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
  base_policy jsonb;
  organization_id uuid;
  media_id_value uuid;
  product_id_value uuid;
  platform_value text;
  model_value text;
  requested_model_value text;
  observation_count_value integer := 0;
  technical_score_value numeric;
  product_fidelity_score_value numeric;
  hook_clarity_score_value numeric;
  visual_quality_score_value numeric;
  trust_score_value numeric;
  platform_fit_score_value numeric;
  source_job_ids_value jsonb := '[]'::jsonb;
  guard_codes_value jsonb := '[]'::jsonb;
  guard_confidence_value text := 'none';
  guard_benchmark_value jsonb := '{}'::jsonb;
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  base_policy :=
    content_factory_private
      .creator_generation_learning_policy_independent_quality_v3(p_payload);
  if base_policy -> 'applied' is distinct from 'true'::jsonb then
    return base_policy;
  end if;

  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  media_id_value :=
    content_factory_private.require_uuid(p_payload, 'media_id');
  platform_value :=
    lower(btrim(coalesce(p_payload ->> 'platform', '')));
  model_value :=
    lower(btrim(coalesce(p_payload ->> 'model', '')));
  requested_model_value := base_policy ->> 'requested_model';

  select media.product_id into product_id_value
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = media_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '42501',
      message = 'generation_learning_policy_media_invalid';
  end if;

  with observations as (
    select
      signal.generation_job_id,
      (quality.result #>> '{scores,technical}')::numeric
        as technical_score,
      (quality.result #>> '{scores,product_fidelity}')::numeric
        as product_fidelity_score,
      (quality.result #>> '{scores,hook_clarity}')::numeric
        as hook_clarity_score,
      (quality.result #>> '{scores,visual_quality}')::numeric
        as visual_quality_score,
      (quality.result #>> '{scores,trust}')::numeric
        as trust_score,
      (quality.result #>> '{scores,platform_fit}')::numeric
        as platform_fit_score
    from content_factory.generation_creative_signals signal
    join content_factory.generation_jobs job
      on job.organization_id = signal.organization_id
     and job.id = signal.generation_job_id
     and job.product_id = signal.product_id
     and job.status = 'succeeded'
     and job.mode = 'real'
    join content_factory.media_objects media
      on media.organization_id = job.organization_id
     and media.id::text = job.output ->> 'output_media_id'
     and media.product_id = job.product_id
     and media.status = 'ready'
     and media.metadata ->> 'kind' in (
       'generated_video', 'generated_image'
     )
    join lateral (
      select review.result
      from content_factory.content_review_runs review
      join content_factory.content_review_decisions decision
        on decision.organization_id = review.organization_id
       and decision.review_id = review.id
       and decision.review_completion_hash = review.completion_hash
       and decision.media_sha256_snapshot =
         review.media_sha256_snapshot
       and decision.decided_by is distinct from job.requested_by
       and decision.decided_by is distinct from job.assigned_to
      where review.organization_id = job.organization_id
        and review.media_object_id = media.id
        and review.status = 'completed'
        and jsonb_typeof(review.result -> 'scores') = 'object'
        and coalesce(
          review.result #>> '{scores,technical}', ''
        ) ~ '^[0-9]{1,3}$'
        and coalesce(
          review.result #>> '{scores,product_fidelity}', ''
        ) ~ '^[0-9]{1,3}$'
        and coalesce(
          review.result #>> '{scores,hook_clarity}', ''
        ) ~ '^[0-9]{1,3}$'
        and coalesce(
          review.result #>> '{scores,visual_quality}', ''
        ) ~ '^[0-9]{1,3}$'
        and coalesce(
          review.result #>> '{scores,trust}', ''
        ) ~ '^[0-9]{1,3}$'
        and coalesce(
          review.result #>> '{scores,platform_fit}', ''
        ) ~ '^[0-9]{1,3}$'
        and (review.result #>> '{scores,technical}')::integer
          between 0 and 100
        and (review.result #>> '{scores,product_fidelity}')::integer
          between 0 and 100
        and (review.result #>> '{scores,hook_clarity}')::integer
          between 0 and 100
        and (review.result #>> '{scores,visual_quality}')::integer
          between 0 and 100
        and (review.result #>> '{scores,trust}')::integer
          between 0 and 100
        and (review.result #>> '{scores,platform_fit}')::integer
          between 0 and 100
      order by decision.created_at desc, review.created_at desc
      limit 1
    ) quality on true
    where signal.organization_id = organization_id
      and signal.product_id = product_id_value
      and signal.platform = platform_value
      and signal.model = model_value
    order by signal.created_at desc, signal.generation_job_id
    limit 60
  )
  select
    count(*)::integer,
    avg(technical_score),
    avg(product_fidelity_score),
    avg(hook_clarity_score),
    avg(visual_quality_score),
    avg(trust_score),
    avg(platform_fit_score),
    coalesce(
      jsonb_agg(generation_job_id order by generation_job_id),
      '[]'::jsonb
    )
  into
    observation_count_value,
    technical_score_value,
    product_fidelity_score_value,
    hook_clarity_score_value,
    visual_quality_score_value,
    trust_score_value,
    platform_fit_score_value,
    source_job_ids_value
  from observations;

  observation_count_value := coalesce(observation_count_value, 0);
  if observation_count_value < 6 then
    return base_policy;
  end if;

  with weaknesses(code, average_score, priority) as (
    values
      (
        'product_fidelity'::text,
        product_fidelity_score_value,
        1
      ),
      ('technical_stability', technical_score_value, 2),
      ('hook_clarity', hook_clarity_score_value, 3),
      ('visual_quality', visual_quality_score_value, 4),
      ('trust', trust_score_value, 5),
      ('platform_fit', platform_fit_score_value, 6)
  ),
  selected as (
    select weakness.*
    from weaknesses weakness
    where weakness.average_score < 78
    order by weakness.average_score, weakness.priority, weakness.code
    limit 3
  )
  select coalesce(
    jsonb_agg(code order by average_score, priority, code),
    '[]'::jsonb
  )
  into guard_codes_value
  from selected;

  if jsonb_array_length(guard_codes_value) = 0 then
    return base_policy;
  end if;

  guard_confidence_value := case
    when observation_count_value >= 12 then 'high'
    else 'medium'
  end;
  guard_benchmark_value := jsonb_build_object(
    'average_technical', round(technical_score_value, 2),
    'average_product_fidelity',
      round(product_fidelity_score_value, 2),
    'average_hook_clarity', round(hook_clarity_score_value, 2),
    'average_visual_quality', round(visual_quality_score_value, 2),
    'average_trust', round(trust_score_value, 2),
    'average_platform_fit', round(platform_fit_score_value, 2),
    'guard_threshold', 78,
    'minimum_observations', 6
  );

  policy_without_hash :=
    (base_policy - 'policy_hash' - 'requested_model')
    || jsonb_build_object(
      'version', 'generation-learning-v4',
      'quality_guard_codes', guard_codes_value,
      'quality_guard_evidence_count', observation_count_value,
      'quality_guard_confidence', guard_confidence_value,
      'quality_guard_benchmark', guard_benchmark_value,
      'quality_guard_source_job_ids', source_job_ids_value,
      'reason_codes',
        coalesce(base_policy -> 'reason_codes', '[]'::jsonb)
        || '["recurring_independent_quality_weakness"]'::jsonb,
      'safety',
        coalesce(base_policy -> 'safety', '{}'::jsonb)
        || jsonb_build_object(
          'independent_human_decision_required', true,
          'structured_score_dimensions_only', true,
          'raw_review_copy_never_learned', true,
          'quality_guard_count_bounded', true,
          'provider_spend_requires_separate_confirmation', true
        )
    );
  policy_hash_value :=
    content_factory_private.json_hash(policy_without_hash);
  return policy_without_hash || jsonb_build_object(
    'policy_hash', policy_hash_value,
    'requested_model', requested_model_value
  );
end;
$$;

revoke all on function public.creator_generation_learning_policy(jsonb)
  from public, anon;
grant execute on function public.creator_generation_learning_policy(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
