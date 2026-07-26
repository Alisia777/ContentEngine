begin;

-- A dense browser-local scan improves coverage between the four or five
-- frames retained for external AI review. Historical evidence remains
-- readable, while every new commit must bind the bounded temporal metrics.
create or replace function content_factory_private
  .valid_content_review_temporal_metrics(p_metrics jsonb)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  duration_value numeric;
  frame_count_value numeric;
  first_second_value numeric;
  last_second_value numeric;
  coverage_value numeric;
  black_ratio_value numeric;
  frozen_ratio_value numeric;
  mean_difference_value numeric;
begin
  if jsonb_typeof(p_metrics) is distinct from 'object' then
    return false;
  end if;

  if not (p_metrics ? 'temporal_scan_status') then
    return not exists (
      select 1
      from jsonb_object_keys(p_metrics) as key_name
      where key_name like 'temporal\_%' escape '\'
    );
  end if;

  if p_metrics ->> 'temporal_scan_status' <> 'completed'
     or p_metrics ->> 'temporal_scan_strategy'
          <> 'uniform_full_duration_v1'
     or jsonb_typeof(p_metrics -> 'duration_seconds')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'temporal_scan_frame_count')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'temporal_scan_first_second')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'temporal_scan_last_second')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'temporal_scan_coverage_ratio')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'temporal_black_frame_ratio')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'temporal_frozen_transition_ratio')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'temporal_mean_frame_difference')
          is distinct from 'number'
     or exists (
       select 1
       from jsonb_object_keys(p_metrics) as key_name
       where key_name like 'temporal\_%' escape '\'
         and key_name <> all(array[
           'temporal_scan_status',
           'temporal_scan_strategy',
           'temporal_scan_frame_count',
           'temporal_scan_first_second',
           'temporal_scan_last_second',
           'temporal_scan_coverage_ratio',
           'temporal_black_frame_ratio',
           'temporal_frozen_transition_ratio',
           'temporal_mean_frame_difference'
         ])
     ) then
    return false;
  end if;

  duration_value := (p_metrics ->> 'duration_seconds')::numeric;
  frame_count_value := (
    p_metrics ->> 'temporal_scan_frame_count'
  )::numeric;
  first_second_value := (
    p_metrics ->> 'temporal_scan_first_second'
  )::numeric;
  last_second_value := (
    p_metrics ->> 'temporal_scan_last_second'
  )::numeric;
  coverage_value := (
    p_metrics ->> 'temporal_scan_coverage_ratio'
  )::numeric;
  black_ratio_value := (
    p_metrics ->> 'temporal_black_frame_ratio'
  )::numeric;
  frozen_ratio_value := (
    p_metrics ->> 'temporal_frozen_transition_ratio'
  )::numeric;
  mean_difference_value := (
    p_metrics ->> 'temporal_mean_frame_difference'
  )::numeric;

  return duration_value between 0.001 and 3600
    and frame_count_value = trunc(frame_count_value)
    and frame_count_value between 12 and 24
    and first_second_value between 0 and duration_value
    and last_second_value > first_second_value
    and last_second_value <= duration_value
    and coverage_value between 0.9 and 1
    and abs(
      (last_second_value - first_second_value) / duration_value
        - coverage_value
    ) <= 0.02
    and black_ratio_value between 0 and 1
    and frozen_ratio_value between 0 and 1
    and mean_difference_value between 0 and 1;
exception
  when numeric_value_out_of_range or invalid_text_representation
    or division_by_zero then
    return false;
end;
$$;

alter table content_factory.content_review_evidence_sets
  add constraint content_review_evidence_temporal_metrics_valid
  check (
    content_factory_private.valid_content_review_temporal_metrics(
      technical_metrics
    )
  ) not valid;

alter table content_factory.content_review_evidence_sets
  validate constraint content_review_evidence_temporal_metrics_valid;

alter function public.creator_commit_content_review_evidence(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_commit_content_review_evidence(
  jsonb
)
  rename to creator_commit_content_review_evidence_without_temporal_gate_v2;
revoke all on function
  content_factory_private
    .creator_commit_content_review_evidence_without_temporal_gate_v2(jsonb)
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
begin
  p_payload := content_factory_private.require_payload(p_payload);
  technical_metrics_value := coalesce(
    p_payload -> 'technical_metrics',
    '{}'::jsonb
  );
  if coalesce(technical_metrics_value ->> 'source_type', '') <> 'video'
     or not content_factory_private.valid_content_review_audio_metrics(
       technical_metrics_value
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_audio_metrics_invalid';
  end if;
  if not content_factory_private.valid_content_review_temporal_metrics(
    technical_metrics_value
  ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_temporal_metrics_invalid';
  end if;
  return content_factory_private
    .creator_commit_content_review_evidence_without_temporal_gate_v2(
      p_payload
    );
end;
$$;

revoke all on function
  content_factory_private.valid_content_review_temporal_metrics(jsonb)
  from public, anon, authenticated;
grant execute on function
  content_factory_private.valid_content_review_temporal_metrics(jsonb)
  to service_role;
revoke all on function public.creator_commit_content_review_evidence(jsonb)
  from public, anon;
grant execute on function public.creator_commit_content_review_evidence(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
