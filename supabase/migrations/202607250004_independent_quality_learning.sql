begin;

-- Preserve the already-audited performance + bounded-exploration resolver and
-- add an intermediate learning tier.  Independent review results are
-- available before a creator connects platform analytics, so they can improve
-- generation quality autonomously while business-performance evidence is
-- still sparse.  Mature published metrics always remain the highest-priority
-- signal.
alter function public.creator_generation_learning_policy(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_learning_policy(jsonb)
  rename to creator_generation_learning_policy_exploration_v2;

revoke all on function
  content_factory_private.creator_generation_learning_policy_exploration_v2(
    jsonb
  )
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
  quality_evidence_count integer := 0;
  quality_angle_count integer := 0;
  preferred_angle_value text;
  preferred_score_value numeric;
  second_score_value numeric;
  avoid_angle_value text;
  avoid_score_value numeric;
  preferred_patterns_value jsonb := '[]'::jsonb;
  preferred_source_ids_value jsonb := '[]'::jsonb;
  quality_benchmark_value jsonb := '{}'::jsonb;
  quality_confidence_value text := 'none';
  policy_without_hash jsonb;
  policy_hash_value text;
  requested_model_value text;
begin
  base_policy :=
    content_factory_private
      .creator_generation_learning_policy_exploration_v2(p_payload);
  if base_policy ->> 'selection_mode' = 'performance' then
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

  with quality_observations as (
    select
      signal.generation_job_id,
      signal.creative_angle,
      signal.hook_patterns,
      quality.decision,
      quality.overall_score,
      quality.blockers_count,
      (
        (case when quality.decision = 'approved' then 1 else 0 end)
          * 0.50
        + quality.overall_score / 100.0 * 0.35
        + (case when quality.blockers_count = 0 then 1 else 0 end)
          * 0.15
      )::numeric as quality_score
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
      select
        decision.decision,
        (review.result ->> 'overall_score')::numeric as overall_score,
        coalesce(
          (review.result ->> 'blockers_count')::integer,
          0
        ) as blockers_count
      from content_factory.content_review_runs review
      join content_factory.content_review_decisions decision
        on decision.organization_id = review.organization_id
       and decision.review_id = review.id
       and decision.review_completion_hash = review.completion_hash
       and decision.media_sha256_snapshot =
         review.media_sha256_snapshot
       and decision.decided_by <> job.requested_by
       and decision.decided_by <> job.assigned_to
      where review.organization_id = job.organization_id
        and review.media_object_id = media.id
        and review.status = 'completed'
        and coalesce(review.result ->> 'overall_score', '')
          ~ '^[0-9]{1,3}$'
        and (review.result ->> 'overall_score')::integer
          between 0 and 100
        and coalesce(review.result ->> 'blockers_count', '0')
          ~ '^[0-9]{1,3}$'
      order by decision.created_at desc, review.created_at desc
      limit 1
    ) quality on true
    where signal.organization_id = organization_id
      and signal.product_id = product_id_value
      and signal.platform = platform_value
      and signal.model = model_value
    order by signal.created_at desc, signal.generation_job_id
    limit 100
  ),
  eligible_angles as (
    select creative_angle
    from quality_observations
    group by creative_angle
    having count(*) >= 3
  ),
  eligible_observations as (
    select observation.*
    from quality_observations observation
    join eligible_angles using (creative_angle)
  ),
  angle_scores as (
    select
      creative_angle,
      count(*)::integer as observation_count,
      avg(quality_score) as score,
      row_number() over (
        order by avg(quality_score) desc, creative_angle
      ) as best_rank,
      row_number() over (
        order by avg(quality_score), creative_angle
      ) as worst_rank
    from eligible_observations
    group by creative_angle
  ),
  summary as (
    select
      (select count(*)::integer from eligible_observations)
        as evidence_count,
      (select count(*)::integer from eligible_angles)
        as angle_count,
      max(creative_angle) filter (where best_rank = 1)
        as preferred_angle,
      max(score) filter (where best_rank = 1) as preferred_score,
      max(score) filter (where best_rank = 2) as second_score,
      max(creative_angle) filter (where worst_rank = 1) as avoid_angle,
      max(score) filter (where worst_rank = 1) as avoid_score
    from angle_scores
  )
  select
    summary.evidence_count,
    summary.angle_count,
    summary.preferred_angle,
    summary.preferred_score,
    summary.second_score,
    summary.avoid_angle,
    summary.avoid_score
  into
    quality_evidence_count,
    quality_angle_count,
    preferred_angle_value,
    preferred_score_value,
    second_score_value,
    avoid_angle_value,
    avoid_score_value
  from summary;

  quality_evidence_count := coalesce(quality_evidence_count, 0);
  quality_angle_count := coalesce(quality_angle_count, 0);
  if quality_evidence_count >= 12 and quality_angle_count >= 2 then
    quality_confidence_value := 'high';
  elsif quality_evidence_count >= 6 and quality_angle_count >= 2 then
    quality_confidence_value := 'medium';
  elsif quality_evidence_count > 0 then
    quality_confidence_value := 'low';
  end if;

  if quality_confidence_value not in ('medium', 'high')
     or preferred_score_value < 0.75
     or preferred_score_value - coalesce(second_score_value, 1) < 0.12 then
    return base_policy;
  end if;
  if avoid_score_value > 0.55
     or preferred_score_value - avoid_score_value < 0.20 then
    avoid_angle_value := null;
  end if;

  with preferred_observations as (
    select
      signal.generation_job_id,
      signal.hook_patterns,
      quality.decision,
      quality.overall_score,
      quality.blockers_count
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
      select
        decision_row.decision,
        (review_row.result ->> 'overall_score')::numeric
          as overall_score,
        coalesce(
          (review_row.result ->> 'blockers_count')::integer,
          0
        ) as blockers_count
      from content_factory.content_review_runs review_row
      join content_factory.content_review_decisions decision_row
        on decision_row.organization_id = review_row.organization_id
       and decision_row.review_id = review_row.id
       and decision_row.review_completion_hash =
         review_row.completion_hash
       and decision_row.media_sha256_snapshot =
         review_row.media_sha256_snapshot
       and decision_row.decided_by <> job.requested_by
       and decision_row.decided_by <> job.assigned_to
      where review_row.organization_id = job.organization_id
        and review_row.media_object_id = media.id
        and review_row.status = 'completed'
        and coalesce(review_row.result ->> 'overall_score', '')
          ~ '^[0-9]{1,3}$'
        and (review_row.result ->> 'overall_score')::integer
          between 0 and 100
        and coalesce(review_row.result ->> 'blockers_count', '0')
          ~ '^[0-9]{1,3}$'
      order by decision_row.created_at desc, review_row.created_at desc
      limit 1
    ) quality on true
    where signal.organization_id = organization_id
      and signal.product_id = product_id_value
      and signal.platform = platform_value
      and signal.model = model_value
      and signal.creative_angle = preferred_angle_value
    order by signal.created_at desc, signal.generation_job_id
    limit 50
  ),
  pattern_counts as (
    select pattern.value as pattern, count(*)::integer as uses
    from preferred_observations observation
    cross join lateral jsonb_array_elements_text(
      observation.hook_patterns
    ) pattern(value)
    group by pattern.value
    order by uses desc, pattern.value
    limit 4
  )
  select
    coalesce(
      (
        select jsonb_agg(pattern order by uses desc, pattern)
        from pattern_counts
      ),
      '[]'::jsonb
    ),
    coalesce(
      (
        select jsonb_agg(
          generation_job_id order by generation_job_id
        )
        from preferred_observations
      ),
      '[]'::jsonb
    ),
    coalesce(
      (
        select jsonb_build_object(
          'approval_rate',
            avg(case when decision = 'approved' then 1 else 0 end),
          'average_review_score', avg(overall_score),
          'blocker_free_rate',
            avg(case when blockers_count = 0 then 1 else 0 end),
          'minimum_observations_per_angle', 3
        )
        from preferred_observations
      ),
      '{}'::jsonb
    )
  into
    preferred_patterns_value,
    preferred_source_ids_value,
    quality_benchmark_value;

  policy_without_hash :=
    (base_policy - 'policy_hash' - 'requested_model')
    || jsonb_build_object(
      'version', 'generation-learning-v3',
      'applied', true,
      'confidence', quality_confidence_value,
      'selection_mode', 'quality',
      'evidence_count', quality_evidence_count,
      'scope', 'product_platform_model',
      'preferred_angle', preferred_angle_value,
      'avoid_angle', avoid_angle_value,
      'preferred_hook_patterns', preferred_patterns_value,
      'selected_angle', preferred_angle_value,
      'selected_hook_patterns', preferred_patterns_value,
      'reason_codes',
        jsonb_build_array('stable_independent_quality_signal'),
      'benchmark', quality_benchmark_value,
      'source_job_ids', preferred_source_ids_value,
      'quality', jsonb_build_object(
        'eligible_angle_count', quality_angle_count,
        'minimum_score', 0.75,
        'minimum_separation', 0.12,
        'approval_weight', 0.50,
        'review_score_weight', 0.35,
        'blocker_free_weight', 0.15
      ),
      'safety',
        coalesce(base_policy -> 'safety', '{}'::jsonb)
        || jsonb_build_object(
          'human_decision_is_independent', true,
          'raw_review_copy_never_learned', true,
          'performance_evidence_has_priority', true
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
