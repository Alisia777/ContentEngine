begin;

-- Short-video evidence now includes aggregates measured while the browser
-- plays every presented frame at normal speed. The extra frames never leave
-- the browser. Historical rows remain readable, while new short-video commits
-- must carry the complete, bounded continuity contract.
create or replace function content_factory_private
  .valid_content_review_continuity_metrics(p_metrics jsonb)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  duration_value numeric;
  callback_count_value numeric;
  presented_count_value numeric;
  missed_count_value numeric;
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

  if not (p_metrics ? 'continuity_scan_status') then
    return not exists (
      select 1
      from jsonb_object_keys(p_metrics) as key_name
      where key_name like 'continuity\_%' escape '\'
    );
  end if;

  if p_metrics ->> 'continuity_scan_strategy'
       <> 'browser_presented_frames_v1'
     or jsonb_typeof(p_metrics -> 'duration_seconds')
          is distinct from 'number' then
    return false;
  end if;
  duration_value := (p_metrics ->> 'duration_seconds')::numeric;

  if p_metrics ->> 'continuity_scan_status' = 'not_applicable' then
    return duration_value > 10
      and duration_value <= 3600
      and p_metrics ->> 'continuity_scan_not_applicable_reason'
        = 'duration_above_short_video_limit'
      and jsonb_typeof(
        p_metrics -> 'continuity_scan_duration_limit_seconds'
      ) = 'number'
      and (
        p_metrics ->> 'continuity_scan_duration_limit_seconds'
      )::numeric = 10
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
      );
  end if;

  if p_metrics ->> 'continuity_scan_status' <> 'completed'
     or duration_value > 10
     or jsonb_typeof(p_metrics -> 'continuity_scan_callback_count')
          is distinct from 'number'
     or jsonb_typeof(
       p_metrics -> 'continuity_scan_presented_frame_count'
     ) is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'continuity_scan_missed_frame_count')
          is distinct from 'number'
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
          is distinct from 'boolean'
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

  return duration_value between 0.001 and 10
    and callback_count_value = trunc(callback_count_value)
    and callback_count_value between 2 and 2400
    and presented_count_value = trunc(presented_count_value)
    and presented_count_value = callback_count_value
    and missed_count_value = trunc(missed_count_value)
    and missed_count_value = 0
    and first_second_value between 0 and duration_value
    and last_second_value > first_second_value
    and last_second_value <= duration_value
    and coverage_value between 0.8 and 1
    and abs(
      (last_second_value - first_second_value) / duration_value -
        coverage_value
    ) <= 0.02
    and max_gap_value between 0 and 0.5
    and black_ratio_value between 0 and 1
    and black_run_value between 0 and duration_value
    and duplicate_ratio_value between 0 and 1
    and duplicate_run_value between 0 and duration_value
    and mean_difference_value between 0 and 1
    and (p_metrics ->> 'continuity_raw_frames_persisted')::boolean
      is false;
exception
  when numeric_value_out_of_range or invalid_text_representation
    or division_by_zero then
    return false;
end;
$$;

alter table content_factory.content_review_evidence_sets
  add constraint content_review_evidence_continuity_metrics_valid
  check (
    content_factory_private.valid_content_review_continuity_metrics(
      technical_metrics
    )
  ) not valid;

alter table content_factory.content_review_evidence_sets
  validate constraint content_review_evidence_continuity_metrics_valid;

alter function public.creator_commit_content_review_evidence(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_commit_content_review_evidence(
  jsonb
)
  rename to
    creator_commit_content_review_evidence_without_continuity_gate_v4;
revoke all on function
  content_factory_private
    .creator_commit_content_review_evidence_without_continuity_gate_v4(
      jsonb
    )
  from public, anon, authenticated, service_role;

create or replace function public.creator_commit_content_review_evidence(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
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
     or not content_factory_private
       .valid_content_review_continuity_metrics(
         technical_metrics_value
       ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_continuity_metrics_invalid';
  end if;
  duration_value := (
    technical_metrics_value ->> 'duration_seconds'
  )::numeric;
  expected_status := case
    when duration_value <= 10 then 'completed'
    else 'not_applicable'
  end;
  if technical_metrics_value ->> 'continuity_scan_status'
       <> expected_status then
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
revoke all on function public.creator_commit_content_review_evidence(jsonb)
  from public, anon;
grant execute on function public.creator_commit_content_review_evidence(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
