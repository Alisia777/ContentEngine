begin;

-- Preserve every existing performance, independent-QA, quality-guard and
-- audio/speech learning rule.  Add one final negative-signal layer so a
-- structure that an independent reviewer explicitly rejected is not selected
-- again merely because bounded exploration has used it fewer times.
alter function public.creator_generation_learning_policy(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_learning_policy(jsonb)
  rename to creator_generation_learning_policy_audio_speech_v5;

revoke all on function
  content_factory_private
    .creator_generation_learning_policy_audio_speech_v5(jsonb)
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
  selected_angle_value text;
  selected_patterns_value jsonb := '[]'::jsonb;
  selected_rejection_count integer := 0;
  selected_approval_count integer := 0;
  replacement_angle_value text;
  replacement_patterns_value jsonb;
  replacement_use_count integer := 0;
  approved_patterns_value jsonb := '[]'::jsonb;
  rejection_status_value text := 'clear';
  generation_allowed_value boolean := true;
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  base_policy :=
    content_factory_private
      .creator_generation_learning_policy_audio_speech_v5(p_payload);
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
  selected_angle_value := base_policy ->> 'preferred_angle';
  selected_patterns_value := coalesce(
    base_policy -> 'preferred_hook_patterns',
    '[]'::jsonb
  );

  select media.product_id into product_id_value
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = media_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '42501',
      message = 'generation_learning_policy_media_invalid';
  end if;

  -- Only the latest immutable decision for the exact generated file counts.
  -- The decision enum is learned, while comments, findings, recommendations,
  -- generated copy and transcripts are deliberately never read.
  with exact_outcomes as (
    select quality.decision
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
      select decision.decision
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
        and review.media_sha256_snapshot = media.sha256
      order by decision.created_at desc, review.created_at desc
      limit 1
    ) quality on true
    where signal.organization_id = organization_id
      and signal.product_id = product_id_value
      and signal.platform = platform_value
      and signal.model = model_value
      and signal.creative_angle = selected_angle_value
      and (
        model_value = 'seedream5_lite'
        or signal.hook_patterns = selected_patterns_value
      )
    order by signal.created_at desc, signal.generation_job_id
    limit 60
  )
  select
    count(*) filter (where decision = 'rejected')::integer,
    count(*) filter (where decision = 'approved')::integer
  into selected_rejection_count, selected_approval_count
  from exact_outcomes;

  selected_rejection_count := coalesce(selected_rejection_count, 0);
  selected_approval_count := coalesce(selected_approval_count, 0);

  if base_policy ->> 'selection_mode' = 'bounded_exploration'
     and selected_rejection_count > 0
     and selected_approval_count = 0 then
    -- The first two entries are the original conservative experiment.  The
    -- latter two are compiler-supported, claim-free recovery structures used
    -- only after an exact hard rejection.  A photo has no hook instruction.
    with candidates(angle, hook_patterns, priority) as (
      values
        ('product_focus'::text, '[]'::jsonb, 1),
        (
          'demonstration'::text,
          '["demonstration"]'::jsonb,
          2
        ),
        (
          'trust_builder'::text,
          '["first_person"]'::jsonb,
          3
        ),
        (
          'objection_handling'::text,
          '["before_buying"]'::jsonb,
          4
        )
    ),
    candidate_usage as (
      select
        candidate.angle,
        candidate.hook_patterns,
        candidate.priority,
        count(job.id)::integer as use_count
      from candidates candidate
      left join content_factory.generation_creative_signals signal
        on signal.organization_id = organization_id
       and signal.product_id = product_id_value
       and signal.platform = platform_value
       and signal.model = model_value
       and signal.creative_angle = candidate.angle
       and (
         model_value = 'seedream5_lite'
         or signal.hook_patterns = candidate.hook_patterns
       )
      left join content_factory.generation_jobs job
        on job.organization_id = signal.organization_id
       and job.id = signal.generation_job_id
       and job.status not in ('failed', 'cancelled')
      group by
        candidate.angle,
        candidate.hook_patterns,
        candidate.priority
    ),
    candidate_outcomes as (
      select
        candidate.angle,
        candidate.hook_patterns,
        quality.decision
      from candidates candidate
      join content_factory.generation_creative_signals signal
        on signal.organization_id = organization_id
       and signal.product_id = product_id_value
       and signal.platform = platform_value
       and signal.model = model_value
       and signal.creative_angle = candidate.angle
       and (
         model_value = 'seedream5_lite'
         or signal.hook_patterns = candidate.hook_patterns
       )
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
        select decision.decision
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
          and review.media_sha256_snapshot = media.sha256
        order by decision.created_at desc, review.created_at desc
        limit 1
      ) quality on true
    ),
    candidate_summary as (
      select
        usage.angle,
        usage.hook_patterns,
        usage.priority,
        usage.use_count,
        count(*) filter (
          where outcome.decision = 'rejected'
        )::integer as rejection_count,
        count(*) filter (
          where outcome.decision = 'approved'
        )::integer as approval_count
      from candidate_usage usage
      left join candidate_outcomes outcome
        on outcome.angle = usage.angle
       and outcome.hook_patterns = usage.hook_patterns
      group by
        usage.angle,
        usage.hook_patterns,
        usage.priority,
        usage.use_count
    )
    select
      candidate.angle,
      candidate.hook_patterns,
      candidate.use_count
    into
      replacement_angle_value,
      replacement_patterns_value,
      replacement_use_count
    from candidate_summary candidate
    where candidate.rejection_count = 0
       or candidate.approval_count > 0
    order by candidate.use_count, candidate.priority, candidate.angle
    limit 1;

    if replacement_angle_value is null then
      generation_allowed_value := false;
      rejection_status_value := 'blocked';
    else
      selected_angle_value := replacement_angle_value;
      selected_patterns_value := replacement_patterns_value;
      rejection_status_value := 'replaced';
    end if;
  end if;

  -- The previous quality layer counted hook patterns from every observation
  -- in its winning angle. Rebuild that small allowlisted set from approved
  -- exact QA outcomes only, so rejected and needs_changes prompts cannot leak
  -- their structure back into the next automatic brief.
  if generation_allowed_value
     and base_policy ->> 'selection_mode' = 'quality' then
    if model_value = 'seedream5_lite' then
      approved_patterns_value := '[]'::jsonb;
    else
      with approved_observations as (
        select
          signal.generation_job_id,
          signal.hook_patterns
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
          select decision.decision
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
            and review.media_sha256_snapshot = media.sha256
          order by decision.created_at desc, review.created_at desc
          limit 1
        ) quality on quality.decision = 'approved'
        where signal.organization_id = organization_id
          and signal.product_id = product_id_value
          and signal.platform = platform_value
          and signal.model = model_value
          and signal.creative_angle = selected_angle_value
        order by signal.created_at desc, signal.generation_job_id
        limit 50
      ),
      pattern_counts as (
        select pattern.value as pattern, count(*)::integer as uses
        from approved_observations observation
        cross join lateral jsonb_array_elements_text(
          observation.hook_patterns
        ) pattern(value)
        group by pattern.value
        order by uses desc, pattern.value
        limit 4
      )
      select coalesce(
        (
          select jsonb_agg(pattern order by uses desc, pattern)
          from pattern_counts
        ),
        '[]'::jsonb
      )
      into approved_patterns_value;
    end if;
    selected_patterns_value := approved_patterns_value;
  end if;

  policy_without_hash :=
    (base_policy - 'policy_hash' - 'requested_model')
    || jsonb_build_object(
      'version', 'generation-learning-v6',
      'generation_allowed', generation_allowed_value,
      'preferred_angle', selected_angle_value,
      'preferred_hook_patterns', selected_patterns_value,
      'selected_angle', selected_angle_value,
      'selected_hook_patterns', selected_patterns_value,
      'reason_codes',
        coalesce(base_policy -> 'reason_codes', '[]'::jsonb)
        || case rejection_status_value
          when 'replaced'
            then '["hard_rejected_structure_replaced"]'::jsonb
          when 'blocked'
            then '["hard_rejected_structures_exhausted"]'::jsonb
          else '[]'::jsonb
        end,
      'rejection_guard', jsonb_build_object(
        'status', rejection_status_value,
        'exact_structure_rejection_count', selected_rejection_count,
        'exact_structure_approval_count', selected_approval_count,
        'replacement_prior_use_count',
          case
            when rejection_status_value = 'replaced'
              then replacement_use_count
            else null
          end,
        'scope', 'product_platform_model_exact_structure'
      ),
      'safety',
        coalesce(base_policy -> 'safety', '{}'::jsonb)
        || jsonb_build_object(
          'latest_exact_independent_decision_only', true,
          'hard_rejected_structure_not_repeated', true,
          'quality_hooks_require_approval', true,
          'free_form_review_copy_never_learned', true,
          'safe_recovery_structures_are_server_bounded', true,
          'paid_start_fails_closed_when_structures_exhausted', true,
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

-- Edge checks the same flag, but PostgreSQL is the final paid-state boundary.
-- Run the same resolver in a BEFORE INSERT trigger after the existing command
-- has completed all payload, identity, rights, training and budget checks.
-- Raising here rolls back the batch, task and spend reservation in the same
-- transaction, and the Edge function has not contacted the provider yet.
create or replace function
  content_factory_private.guard_generation_rejection_before_paid_job()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  server_policy jsonb;
  input_media_id_value text;
  model_value text;
  platform_value text;
begin
  if new.mode <> 'real'
     or new.provider <> 'runway'
     or not new.allow_real_spend
     or auth.uid() is null
     or new.requested_by is distinct from auth.uid() then
    return new;
  end if;

  input_media_id_value := btrim(coalesce(
    new.input ->> 'input_media_id',
    ''
  ));
  model_value := lower(btrim(coalesce(new.input ->> 'model', '')));
  platform_value := lower(btrim(coalesce(
    new.input ->> 'platform',
    ''
  )));
  if input_media_id_value !~
       '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
     or model_value not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     )
     or platform_value not in (
       'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
     ) then
    return new;
  end if;

  server_policy := public.creator_generation_learning_policy(
    jsonb_build_object(
      'organization_id', new.organization_id,
      'media_id', input_media_id_value,
      'platform', platform_value,
      'model', model_value
    )
  );
  if server_policy -> 'generation_allowed' = 'false'::jsonb then
    raise exception using
      errcode = '55000',
      message = 'generation_learning_rejection_guard_blocked';
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.guard_generation_rejection_before_paid_job()
  from public, anon, authenticated, service_role;

drop trigger if exists zz_generation_rejection_paid_guard
  on content_factory.generation_jobs;
create trigger zz_generation_rejection_paid_guard
before insert on content_factory.generation_jobs
for each row execute function
  content_factory_private.guard_generation_rejection_before_paid_job();

notify pgrst, 'reload schema';

commit;
