begin;

-- Keep historical evidence readable, while accepting one additional honest
-- short-video continuity contract. The v2 branch is a deterministic local
-- seek grid used only when browser-presented-frame accounting is unavailable
-- or unreliable. It never claims callback, presented-frame, or missed-frame
-- counts and never persists the sampled pixels.
create or replace function content_factory_private
  .valid_content_review_continuity_metrics(p_metrics jsonb)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  duration_value numeric;
  strategy_value text;
  callback_count_value numeric;
  presented_count_value numeric;
  missed_count_value numeric;
  sample_count_value numeric;
  target_fps_value numeric;
  target_max_drift_value numeric;
  expected_sample_count numeric;
  expected_endpoint_margin numeric;
  first_second_value numeric;
  last_second_value numeric;
  coverage_value numeric;
  max_gap_value numeric;
  black_ratio_value numeric;
  black_run_value numeric;
  duplicate_ratio_value numeric;
  duplicate_run_value numeric;
  mean_difference_value numeric;
begin
  if jsonb_typeof(p_metrics) is distinct from 'object' then
    return false;
  end if;

  -- Existing rows predating the continuity gate remain valid under the table
  -- constraint. The commit gate below independently requires an exact status.
  if not (p_metrics ? 'continuity_scan_status') then
    return not exists (
      select 1
      from jsonb_object_keys(p_metrics) as key_name
      where key_name like 'continuity\_%' escape '\'
    );
  end if;

  if jsonb_typeof(p_metrics -> 'duration_seconds')
       is distinct from 'number' then
    return false;
  end if;
  duration_value := (p_metrics ->> 'duration_seconds')::numeric;
  strategy_value := p_metrics ->> 'continuity_scan_strategy';

  if p_metrics ->> 'continuity_scan_status' = 'not_applicable' then
    return coalesce(
      strategy_value = 'browser_presented_frames_v1'
      and duration_value > 15
      and duration_value <= 3600
      and p_metrics ->> 'continuity_scan_not_applicable_reason'
        = 'duration_above_short_video_limit'
      and jsonb_typeof(
        p_metrics -> 'continuity_scan_duration_limit_seconds'
      ) = 'number'
      and (
        p_metrics ->> 'continuity_scan_duration_limit_seconds'
      )::numeric = 15
      and not exists (
        select 1
        from jsonb_object_keys(p_metrics) as key_name
        where key_name like 'continuity\_%' escape '\'
          and key_name <> all(array[
            'continuity_scan_status',
            'continuity_scan_strategy',
            'continuity_scan_not_applicable_reason',
            'continuity_scan_duration_limit_seconds'
          ])
      ),
      false
    );
  end if;

  if p_metrics ->> 'continuity_scan_status' is distinct from 'completed'
     or duration_value not between 0.001 and 15
     or jsonb_typeof(p_metrics -> 'continuity_scan_first_second')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'continuity_scan_last_second')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'continuity_scan_coverage_ratio')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'continuity_scan_max_gap_seconds')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'continuity_black_frame_ratio')
          is distinct from 'number'
     or jsonb_typeof(
       p_metrics -> 'continuity_longest_black_run_seconds'
     ) is distinct from 'number'
     or jsonb_typeof(
       p_metrics -> 'continuity_duplicate_transition_ratio'
     ) is distinct from 'number'
     or jsonb_typeof(
       p_metrics -> 'continuity_longest_duplicate_run_seconds'
     ) is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'continuity_mean_frame_difference')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'continuity_raw_frames_persisted')
          is distinct from 'boolean' then
    return false;
  end if;

  first_second_value := (
    p_metrics ->> 'continuity_scan_first_second'
  )::numeric;
  last_second_value := (
    p_metrics ->> 'continuity_scan_last_second'
  )::numeric;
  coverage_value := (
    p_metrics ->> 'continuity_scan_coverage_ratio'
  )::numeric;
  max_gap_value := (
    p_metrics ->> 'continuity_scan_max_gap_seconds'
  )::numeric;
  black_ratio_value := (
    p_metrics ->> 'continuity_black_frame_ratio'
  )::numeric;
  black_run_value := (
    p_metrics ->> 'continuity_longest_black_run_seconds'
  )::numeric;
  duplicate_ratio_value := (
    p_metrics ->> 'continuity_duplicate_transition_ratio'
  )::numeric;
  duplicate_run_value := (
    p_metrics ->> 'continuity_longest_duplicate_run_seconds'
  )::numeric;
  mean_difference_value := (
    p_metrics ->> 'continuity_mean_frame_difference'
  )::numeric;

  if first_second_value not between 0 and duration_value
     or last_second_value <= first_second_value
     or last_second_value > duration_value
     or coverage_value not between 0.8 and 1
     or abs(
       (last_second_value - first_second_value) / duration_value -
         coverage_value
     ) > 0.02
     or max_gap_value not between 0 and 0.5
     or black_ratio_value not between 0 and 1
     or black_run_value not between 0 and duration_value
     or duplicate_ratio_value not between 0 and 1
     or duplicate_run_value not between 0 and duration_value
     or mean_difference_value not between 0 and 1
     or (p_metrics ->> 'continuity_raw_frames_persisted')::boolean
          is distinct from false then
    return false;
  end if;

  if strategy_value = 'browser_presented_frames_v1' then
    if jsonb_typeof(p_metrics -> 'continuity_scan_callback_count')
         is distinct from 'number'
       or jsonb_typeof(
         p_metrics -> 'continuity_scan_presented_frame_count'
       ) is distinct from 'number'
       or jsonb_typeof(p_metrics -> 'continuity_scan_missed_frame_count')
         is distinct from 'number'
       or exists (
         select 1
         from jsonb_object_keys(p_metrics) as key_name
         where key_name like 'continuity\_%' escape '\'
           and key_name <> all(array[
             'continuity_scan_status',
             'continuity_scan_strategy',
             'continuity_scan_callback_count',
             'continuity_scan_presented_frame_count',
             'continuity_scan_missed_frame_count',
             'continuity_scan_first_second',
             'continuity_scan_last_second',
             'continuity_scan_coverage_ratio',
             'continuity_scan_max_gap_seconds',
             'continuity_black_frame_ratio',
             'continuity_longest_black_run_seconds',
             'continuity_duplicate_transition_ratio',
             'continuity_longest_duplicate_run_seconds',
             'continuity_mean_frame_difference',
             'continuity_raw_frames_persisted'
           ])
       ) then
      return false;
    end if;

    callback_count_value := (
      p_metrics ->> 'continuity_scan_callback_count'
    )::numeric;
    presented_count_value := (
      p_metrics ->> 'continuity_scan_presented_frame_count'
    )::numeric;
    missed_count_value := (
      p_metrics ->> 'continuity_scan_missed_frame_count'
    )::numeric;
    return callback_count_value = trunc(callback_count_value)
      and callback_count_value between 2 and 3600
      and presented_count_value = trunc(presented_count_value)
      and presented_count_value = callback_count_value
      and presented_count_value <= 10000
      and missed_count_value = trunc(missed_count_value)
      and missed_count_value = 0;
  end if;

  if strategy_value = 'browser_dense_seek_v2' then
    if jsonb_typeof(p_metrics -> 'continuity_scan_sample_count')
         is distinct from 'number'
       or jsonb_typeof(p_metrics -> 'continuity_scan_target_fps')
         is distinct from 'number'
       or jsonb_typeof(
         p_metrics -> 'continuity_scan_target_max_drift_seconds'
       ) is distinct from 'number'
       or jsonb_typeof(p_metrics -> 'continuity_scan_fallback_reason')
         is distinct from 'string'
       or exists (
         select 1
         from jsonb_object_keys(p_metrics) as key_name
         where key_name like 'continuity\_%' escape '\'
           and key_name <> all(array[
             'continuity_scan_status',
             'continuity_scan_strategy',
             'continuity_scan_sample_count',
             'continuity_scan_target_fps',
             'continuity_scan_target_max_drift_seconds',
             'continuity_scan_fallback_reason',
             'continuity_scan_first_second',
             'continuity_scan_last_second',
             'continuity_scan_coverage_ratio',
             'continuity_scan_max_gap_seconds',
             'continuity_black_frame_ratio',
             'continuity_longest_black_run_seconds',
             'continuity_duplicate_transition_ratio',
             'continuity_longest_duplicate_run_seconds',
             'continuity_mean_frame_difference',
             'continuity_raw_frames_persisted'
           ])
       ) then
      return false;
    end if;

    sample_count_value := (
      p_metrics ->> 'continuity_scan_sample_count'
    )::numeric;
    target_fps_value := (
      p_metrics ->> 'continuity_scan_target_fps'
    )::numeric;
    target_max_drift_value := (
      p_metrics ->> 'continuity_scan_target_max_drift_seconds'
    )::numeric;
    expected_sample_count := least(
      151,
      greatest(16, ceil(duration_value * 10) + 1)
    );
    expected_endpoint_margin := least(
      0.01,
      duration_value * 0.01
    );

    return sample_count_value = trunc(sample_count_value)
      and sample_count_value = expected_sample_count
      and target_fps_value = 10
      and target_max_drift_value between 0 and 0.02
      and p_metrics ->> 'continuity_scan_fallback_reason' = any(array[
        'rvfc_unavailable',
        'rvfc_coverage_unreliable',
        'rvfc_max_gap_unreliable',
        'rvfc_missed_frames'
      ])
      and coverage_value between 0.98 and 1
      and max_gap_value between 0 and 0.125
      and abs(first_second_value - expected_endpoint_margin) <= 0.0201
      and abs(
        duration_value - last_second_value - expected_endpoint_margin
      ) <= 0.0201
      and abs(
        max_gap_value -
          (last_second_value - first_second_value) /
            (sample_count_value - 1)
      ) <= 0.04;
  end if;

  return false;
exception
  when numeric_value_out_of_range or invalid_text_representation
    or division_by_zero then
    return false;
end;
$$;

-- Project scoping moved the original continuity gate behind this private
-- alias in 202608040005. Replace that alias only: the public RPC must continue
-- to call call_project_scoped_v47 before reaching this validation layer.
create or replace function content_factory_private
  .creator_commit_content_review_evidence_pre_project_v47(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  technical_metrics_value jsonb;
  duration_value numeric;
  expected_status text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  technical_metrics_value := coalesce(
    p_payload -> 'technical_metrics',
    '{}'::jsonb
  );
  if coalesce(technical_metrics_value ->> 'source_type', '') <> 'video'
     or jsonb_typeof(technical_metrics_value -> 'duration_seconds')
          is distinct from 'number'
     or content_factory_private
       .valid_content_review_continuity_metrics(
         technical_metrics_value
       ) is distinct from true then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_continuity_metrics_invalid';
  end if;
  duration_value := (
    technical_metrics_value ->> 'duration_seconds'
  )::numeric;
  expected_status := case
    when duration_value <= 15 then 'completed'
    else 'not_applicable'
  end;
  if technical_metrics_value ->> 'continuity_scan_status'
       is distinct from expected_status then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_continuity_metrics_invalid';
  end if;
  return content_factory_private
    .creator_commit_content_review_evidence_without_continuity_gate_v4(
      p_payload
    );
end;
$$;

revoke all on function
  content_factory_private.valid_content_review_continuity_metrics(jsonb)
  from public, anon, authenticated;
grant execute on function
  content_factory_private.valid_content_review_continuity_metrics(jsonb)
  to service_role;
revoke all on function
  content_factory_private
    .creator_commit_content_review_evidence_pre_project_v47(jsonb)
  from public, anon, authenticated;

notify pgrst, 'reload schema';

commit;
