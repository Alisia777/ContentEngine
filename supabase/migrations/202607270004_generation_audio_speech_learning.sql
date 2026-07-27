begin;

-- The visual quality loop already learns from bounded numeric scores. For
-- Seedance, audio defects lower the generic technical score and spoken-script
-- mismatches lower hook clarity, but those generic codes compile to visual
-- instructions. Preserve the existing policy and replace only those two codes
-- when exact, immutable review evidence identifies the narrower cause.
alter function public.creator_generation_learning_policy(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_learning_policy(jsonb)
  rename to creator_generation_learning_policy_quality_guards_v4;

revoke all on function
  content_factory_private
    .creator_generation_learning_policy_quality_guards_v4(jsonb)
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
  audio_evidence_count_value integer := 0;
  audio_issue_count_value integer := 0;
  speech_evidence_count_value integer := 0;
  speech_issue_count_value integer := 0;
  audio_guard boolean := false;
  speech_guard boolean := false;
  guard_codes_value jsonb := '[]'::jsonb;
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  base_policy :=
    content_factory_private
      .creator_generation_learning_policy_quality_guards_v4(p_payload);
  if base_policy -> 'applied' is distinct from 'true'::jsonb then
    return base_policy;
  end if;

  model_value := lower(btrim(coalesce(p_payload ->> 'model', '')));
  if model_value <> 'seedance2_fast'
     or jsonb_typeof(base_policy -> 'quality_guard_codes') <> 'array'
     or not (
       base_policy -> 'quality_guard_codes'
         ?| array['technical_stability', 'hook_clarity']
     ) then
    return base_policy;
  end if;

  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  media_id_value :=
    content_factory_private.require_uuid(p_payload, 'media_id');
  platform_value :=
    lower(btrim(coalesce(p_payload ->> 'platform', '')));
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

  with exact_reviews as (
    select
      signal.generation_job_id,
      review.result,
      evidence.technical_metrics
    from content_factory.generation_creative_signals signal
    join content_factory.generation_jobs job
      on job.organization_id = signal.organization_id
     and job.id = signal.generation_job_id
     and job.product_id = signal.product_id
     and job.status = 'succeeded'
     and job.mode = 'real'
     and job.provider = 'runway'
     and job.input ->> 'model' = 'seedance2_fast'
     and job.input -> 'audio' = 'true'::jsonb
    join content_factory.media_objects media
      on media.organization_id = job.organization_id
     and media.id::text = job.output ->> 'output_media_id'
     and media.product_id = job.product_id
     and media.status = 'ready'
     and media.metadata ->> 'kind' = 'generated_video'
     and media.metadata ->> 'generation_job_id' = job.id::text
    join lateral (
      select
        review_row.result,
        review_row.evidence_set_id
      from content_factory.content_review_runs review_row
      join content_factory.content_review_decisions decision
        on decision.organization_id = review_row.organization_id
       and decision.review_id = review_row.id
       and decision.review_completion_hash = review_row.completion_hash
       and decision.media_sha256_snapshot =
         review_row.media_sha256_snapshot
       and decision.decided_by is distinct from job.requested_by
       and decision.decided_by is distinct from job.assigned_to
      where review_row.organization_id = job.organization_id
        and review_row.media_object_id = media.id
        and review_row.status = 'completed'
        and review_row.media_sha256_snapshot = media.sha256
      order by decision.created_at desc, review_row.created_at desc
      limit 1
    ) review on true
    left join content_factory.content_review_evidence_sets evidence
      on evidence.organization_id = signal.organization_id
     and evidence.id = review.evidence_set_id
     and evidence.media_object_id = media.id
     and evidence.source_sha256_snapshot = media.sha256
     and evidence.status = 'consumed'
    where signal.organization_id = organization_id
      and signal.product_id = product_id_value
      and signal.platform = platform_value
      and signal.model = model_value
    order by signal.created_at desc, signal.generation_job_id
    limit 60
  ),
  classified as (
    select
      generation_job_id,
      case
        when technical_metrics -> 'audio_expected' = 'true'::jsonb
         and technical_metrics -> 'audio_analyzed' = 'true'::jsonb
         and technical_metrics ->> 'audio_analysis_status' = 'completed'
         and content_factory_private.valid_content_review_audio_metrics(
           technical_metrics
         )
          then true
        else false
      end as audio_evidence,
      case
        when technical_metrics -> 'audio_expected' = 'true'::jsonb
         and technical_metrics -> 'audio_analyzed' = 'true'::jsonb
         and technical_metrics ->> 'audio_analysis_status' = 'completed'
         and content_factory_private.valid_content_review_audio_metrics(
           technical_metrics
         )
          then
            (technical_metrics ->> 'audio_rms_dbfs')::numeric <= -45
            or (technical_metrics ->> 'audio_silence_ratio')::numeric >= 0.6
            or (technical_metrics ->> 'audio_clipping_ratio')::numeric >= 0.01
            or coalesce(
              (
                technical_metrics
                  ->> 'audio_video_duration_delta_seconds'
              )::numeric > 0.35,
              false
            )
        else false
      end as audio_issue,
      case
        when result #>> '{speech_analysis,status}' = 'completed'
         and coalesce(
           result #>> '{speech_analysis,similarity_ratio}', ''
         ) ~ '^(0|0[.][0-9]+|1([.]0+)?)$'
         and coalesce(
           result #>> '{speech_analysis,coverage_ratio}', ''
         ) ~ '^(0|0[.][0-9]+|1([.]0+)?)$'
         and coalesce(
           result #>> '{speech_analysis,word_error_rate}', ''
         ) ~ '^(0|0[.][0-9]+|1([.][0-9]+)?|2([.]0+)?)$'
         and (
           result #>> '{speech_analysis,transcription_confidence}' is null
           or (
             coalesce(
               result
                 #>> '{speech_analysis,transcription_confidence}',
               ''
             ) ~ '^(0|0[.][0-9]+|1([.]0+)?)$'
             and (
               result
                 #>> '{speech_analysis,transcription_confidence}'
             )::numeric >= 0.35
           )
         )
          then true
        else false
      end as speech_evidence,
      case
        when result #>> '{speech_analysis,status}' = 'completed'
         and coalesce(
           result #>> '{speech_analysis,similarity_ratio}', ''
         ) ~ '^(0|0[.][0-9]+|1([.]0+)?)$'
         and coalesce(
           result #>> '{speech_analysis,coverage_ratio}', ''
         ) ~ '^(0|0[.][0-9]+|1([.]0+)?)$'
         and coalesce(
           result #>> '{speech_analysis,word_error_rate}', ''
         ) ~ '^(0|0[.][0-9]+|1([.][0-9]+)?|2([.]0+)?)$'
         and (
           result #>> '{speech_analysis,transcription_confidence}' is null
           or (
             coalesce(
               result
                 #>> '{speech_analysis,transcription_confidence}',
               ''
             ) ~ '^(0|0[.][0-9]+|1([.]0+)?)$'
             and (
               result
                 #>> '{speech_analysis,transcription_confidence}'
             )::numeric >= 0.35
           )
         )
          then
            (result #>> '{speech_analysis,similarity_ratio}')::numeric < 0.75
            or (result #>> '{speech_analysis,coverage_ratio}')::numeric < 0.8
            or (result #>> '{speech_analysis,word_error_rate}')::numeric > 0.45
        else false
      end as speech_issue
    from exact_reviews
  )
  select
    count(*) filter (where audio_evidence)::integer,
    count(*) filter (where audio_evidence and audio_issue)::integer,
    count(*) filter (where speech_evidence)::integer,
    count(*) filter (where speech_evidence and speech_issue)::integer
  into
    audio_evidence_count_value,
    audio_issue_count_value,
    speech_evidence_count_value,
    speech_issue_count_value
  from classified;

  audio_guard :=
    audio_evidence_count_value >= 6
    and audio_issue_count_value * 3 >= audio_evidence_count_value;
  speech_guard :=
    speech_evidence_count_value >= 6
    and speech_issue_count_value * 3 >= speech_evidence_count_value;

  audio_guard :=
    audio_guard
    and base_policy -> 'quality_guard_codes' ? 'technical_stability';
  speech_guard :=
    speech_guard
    and base_policy -> 'quality_guard_codes' ? 'hook_clarity';
  if not audio_guard and not speech_guard then
    return base_policy;
  end if;

  select coalesce(
    jsonb_agg(
      case
        when item.value = 'technical_stability' and audio_guard
          then 'audio_quality'
        when item.value = 'hook_clarity' and speech_guard
          then 'speech_fidelity'
        else item.value
      end
      order by item.ordinality
    ),
    '[]'::jsonb
  )
  into guard_codes_value
  from jsonb_array_elements_text(
    base_policy -> 'quality_guard_codes'
  ) with ordinality as item(value, ordinality);

  policy_without_hash :=
    (base_policy - 'policy_hash' - 'requested_model')
    || jsonb_build_object(
      'version', 'generation-learning-v5',
      'quality_guard_codes', guard_codes_value,
      'quality_guard_benchmark',
        coalesce(
          base_policy -> 'quality_guard_benchmark',
          '{}'::jsonb
        )
        || jsonb_build_object(
          'audio_evidence_count', audio_evidence_count_value,
          'audio_issue_count', audio_issue_count_value,
          'speech_evidence_count', speech_evidence_count_value,
          'speech_issue_count', speech_issue_count_value,
          'specialized_issue_ratio_threshold', 0.3334,
          'specialized_minimum_observations', 6
        ),
      'reason_codes',
        coalesce(base_policy -> 'reason_codes', '[]'::jsonb)
        || '["recurring_seedance_audio_speech_weakness"]'::jsonb,
      'safety',
        coalesce(base_policy -> 'safety', '{}'::jsonb)
        || jsonb_build_object(
          'exact_review_evidence_only', true,
          'structured_audio_metrics_only', true,
          'structured_speech_ratios_only', true,
          'transcript_copy_never_learned', true,
          'seedance_audio_guards_only', true,
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

-- Keep the six audited score dimensions and upgrade only the meaning of the
-- two affected guards for the exact failed Seedance review.
alter function public.creator_generation_repair_policy(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_repair_policy(jsonb)
  rename to creator_generation_repair_policy_structured_scores_v1;

revoke all on function
  content_factory_private
    .creator_generation_repair_policy_structured_scores_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_repair_policy(
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
  review_result jsonb;
  technical_metrics_value jsonb;
  speech_value jsonb;
  audio_issue boolean := false;
  speech_issue boolean := false;
  guard_codes_value jsonb := '[]'::jsonb;
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  base_policy :=
    content_factory_private
      .creator_generation_repair_policy_structured_scores_v1(p_payload);
  if base_policy -> 'applied' is distinct from 'true'::jsonb
     or base_policy ->> 'model' <> 'seedance2_fast'
     or jsonb_typeof(base_policy -> 'guard_codes') <> 'array'
     or not (
       base_policy -> 'guard_codes'
         ?| array['technical_stability', 'hook_clarity']
     ) then
    return base_policy;
  end if;

  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  select
    review.result,
    evidence.technical_metrics
  into review_result, technical_metrics_value
  from content_factory.content_review_runs review
  left join content_factory.content_review_evidence_sets evidence
    on evidence.organization_id = review.organization_id
   and evidence.id = review.evidence_set_id
   and evidence.media_object_id = review.media_object_id
   and evidence.source_sha256_snapshot = review.media_sha256_snapshot
   and evidence.status = 'consumed'
  where review.organization_id = organization_id
    and review.id = (base_policy ->> 'source_review_id')::uuid
    and review.status = 'completed'
    and review.completion_hash =
      base_policy ->> 'source_review_completion_hash'
    and review.media_object_id =
      (base_policy ->> 'source_media_id')::uuid
    and review.media_sha256_snapshot =
      base_policy ->> 'source_media_sha256';

  if review_result is null then
    return base_policy;
  end if;

  if technical_metrics_value -> 'audio_expected' = 'true'::jsonb
     and technical_metrics_value -> 'audio_analyzed' = 'true'::jsonb
     and technical_metrics_value ->> 'audio_analysis_status' = 'completed'
     and content_factory_private.valid_content_review_audio_metrics(
       technical_metrics_value
     ) then
    audio_issue :=
      (technical_metrics_value ->> 'audio_rms_dbfs')::numeric <= -45
      or (
        technical_metrics_value ->> 'audio_silence_ratio'
      )::numeric >= 0.6
      or (
        technical_metrics_value ->> 'audio_clipping_ratio'
      )::numeric >= 0.01
      or coalesce(
        (
          technical_metrics_value
            ->> 'audio_video_duration_delta_seconds'
        )::numeric > 0.35,
        false
      );
  end if;

  speech_value := review_result -> 'speech_analysis';
  if jsonb_typeof(speech_value) = 'object'
     and speech_value ->> 'status' = 'completed'
     and coalesce(speech_value ->> 'similarity_ratio', '')
       ~ '^(0|0[.][0-9]+|1([.]0+)?)$'
     and coalesce(speech_value ->> 'coverage_ratio', '')
       ~ '^(0|0[.][0-9]+|1([.]0+)?)$'
     and coalesce(speech_value ->> 'word_error_rate', '')
       ~ '^(0|0[.][0-9]+|1([.][0-9]+)?|2([.]0+)?)$'
     and (
       speech_value ->> 'transcription_confidence' is null
       or (
         coalesce(speech_value ->> 'transcription_confidence', '')
           ~ '^(0|0[.][0-9]+|1([.]0+)?)$'
         and (
           speech_value ->> 'transcription_confidence'
         )::numeric >= 0.35
       )
     ) then
    speech_issue :=
      (speech_value ->> 'similarity_ratio')::numeric < 0.75
      or (speech_value ->> 'coverage_ratio')::numeric < 0.8
      or (speech_value ->> 'word_error_rate')::numeric > 0.45;
  end if;

  audio_issue :=
    audio_issue and base_policy -> 'guard_codes' ? 'technical_stability';
  speech_issue :=
    speech_issue and base_policy -> 'guard_codes' ? 'hook_clarity';
  if not audio_issue and not speech_issue then
    return base_policy;
  end if;

  select coalesce(
    jsonb_agg(
      case
        when item.value = 'technical_stability' and audio_issue
          then 'audio_quality'
        when item.value = 'hook_clarity' and speech_issue
          then 'speech_fidelity'
        else item.value
      end
      order by item.ordinality
    ),
    '[]'::jsonb
  )
  into guard_codes_value
  from jsonb_array_elements_text(
    base_policy -> 'guard_codes'
  ) with ordinality as item(value, ordinality);

  policy_without_hash :=
    (base_policy - 'policy_hash')
    || jsonb_build_object(
      'guard_codes', guard_codes_value,
      'reason_codes',
        coalesce(base_policy -> 'reason_codes', '[]'::jsonb)
        || '["seedance_audio_speech_repair_specialized"]'::jsonb,
      'safety',
        coalesce(base_policy -> 'safety', '{}'::jsonb)
        || jsonb_build_object(
          'exact_review_evidence_only', true,
          'structured_audio_metrics_only', true,
          'structured_speech_ratios_only', true,
          'transcript_copy_excluded', true,
          'seedance_audio_guards_only', true,
          'provider_spend_requires_separate_confirmation', true
        )
    );
  policy_hash_value :=
    content_factory_private.json_hash(policy_without_hash);
  return policy_without_hash || jsonb_build_object(
    'policy_hash', policy_hash_value
  );
end;
$$;

revoke all on function public.creator_generation_repair_policy(jsonb)
  from public, anon;
grant execute on function public.creator_generation_repair_policy(jsonb)
  to authenticated;

-- Extend both paid-boundary compilers without duplicating the already audited
-- angle, hook and visual guard mapping. Unknown codes and audio codes for any
-- model other than Seedance fail closed.
alter function
  content_factory_private.generation_learning_prompt_requirements(jsonb, text)
  rename to generation_learning_prompt_requirements_visual_v1;

revoke all on function
  content_factory_private
    .generation_learning_prompt_requirements_visual_v1(jsonb, text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_learning_prompt_requirements(
    p_policy jsonb,
    p_model text
  )
returns text[]
language plpgsql
immutable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  guard_codes jsonb;
  visual_guard_codes jsonb;
  requirements text[];
  guard_code text;
begin
  guard_codes := coalesce(
    p_policy -> 'quality_guard_codes',
    '[]'::jsonb
  );
  if jsonb_typeof(guard_codes) <> 'array'
     or jsonb_array_length(guard_codes) > 3
     or exists (
       select 1
       from jsonb_array_elements(guard_codes) item(value)
       where jsonb_typeof(item.value) <> 'string'
     )
     or (
       select count(*)
       from jsonb_array_elements_text(guard_codes)
     ) <> (
       select count(distinct item.value)
       from jsonb_array_elements_text(guard_codes) item(value)
     )
     or (
       p_model <> 'seedance2_fast'
       and guard_codes ?| array['audio_quality', 'speech_fidelity']
     ) then
    return null;
  end if;

  select coalesce(
    jsonb_agg(item.value order by item.ordinality),
    '[]'::jsonb
  )
  into visual_guard_codes
  from jsonb_array_elements_text(guard_codes)
    with ordinality as item(value, ordinality)
  where item.value not in ('audio_quality', 'speech_fidelity');

  requirements :=
    content_factory_private
      .generation_learning_prompt_requirements_visual_v1(
        jsonb_set(
          p_policy,
          '{quality_guard_codes}',
          visual_guard_codes,
          true
        ),
        p_model
      );
  if requirements is null then
    return null;
  end if;

  for guard_code in
    select item.value
    from jsonb_array_elements_text(guard_codes)
      with ordinality as item(value, ordinality)
    where item.value in ('audio_quality', 'speech_fidelity')
    order by item.ordinality
  loop
    requirements := array_append(
      requirements,
      case guard_code
        when 'audio_quality'
          then 'QA: слышимая чистая речь без тишины, клиппинга и рассинхронизации.'
        when 'speech_fidelity'
          then 'QA: реплика произносится дословно, без пропусков, замен и новых слов.'
      end
    );
  end loop;
  return requirements;
exception when others then
  return null;
end;
$$;

revoke all on function
  content_factory_private.generation_learning_prompt_requirements(jsonb, text)
  from public, anon, authenticated, service_role;

alter function
  content_factory_private.generation_repair_prompt_requirements(jsonb, text)
  rename to generation_repair_prompt_requirements_visual_v1;

revoke all on function
  content_factory_private
    .generation_repair_prompt_requirements_visual_v1(jsonb, text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_repair_prompt_requirements(
    p_guard_codes jsonb,
    p_model text
  )
returns text[]
language plpgsql
immutable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  visual_guard_codes jsonb;
  requirements text[] := array[]::text[];
  visual_requirements text[];
  guard_code text;
begin
  if jsonb_typeof(p_guard_codes) <> 'array'
     or jsonb_array_length(p_guard_codes) not between 1 and 3
     or exists (
       select 1
       from jsonb_array_elements(p_guard_codes) item(value)
       where jsonb_typeof(item.value) <> 'string'
     )
     or (
       select count(*)
       from jsonb_array_elements_text(p_guard_codes)
     ) <> (
       select count(distinct item.value)
       from jsonb_array_elements_text(p_guard_codes) item(value)
     )
     or (
       p_model <> 'seedance2_fast'
       and p_guard_codes ?| array['audio_quality', 'speech_fidelity']
     ) then
    return null;
  end if;

  select coalesce(
    jsonb_agg(item.value order by item.ordinality),
    '[]'::jsonb
  )
  into visual_guard_codes
  from jsonb_array_elements_text(p_guard_codes)
    with ordinality as item(value, ordinality)
  where item.value not in ('audio_quality', 'speech_fidelity');

  if jsonb_array_length(visual_guard_codes) > 0 then
    visual_requirements :=
      content_factory_private
        .generation_repair_prompt_requirements_visual_v1(
          visual_guard_codes,
          p_model
        );
    if visual_requirements is null then
      return null;
    end if;
    requirements := requirements || visual_requirements;
  end if;

  for guard_code in
    select item.value
    from jsonb_array_elements_text(p_guard_codes)
      with ordinality as item(value, ordinality)
    where item.value in ('audio_quality', 'speech_fidelity')
    order by item.ordinality
  loop
    requirements := array_append(
      requirements,
      case guard_code
        when 'audio_quality'
          then 'QA: слышимая чистая речь без тишины, клиппинга и рассинхронизации.'
        when 'speech_fidelity'
          then 'QA: реплика произносится дословно, без пропусков, замен и новых слов.'
      end
    );
  end loop;
  return requirements;
exception when others then
  return null;
end;
$$;

revoke all on function
  content_factory_private.generation_repair_prompt_requirements(jsonb, text)
  from public, anon, authenticated, service_role;

notify pgrst, 'reload schema';

commit;
