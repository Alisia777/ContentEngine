begin;

-- New video reviews retain four independent control frames and one fifth JPEG
-- containing a chronological contact sheet of the bounded full-duration scan.
-- Historical evidence remains readable, while the authenticated commit path
-- requires the complete atlas contract for every newly prepared video.
create or replace function content_factory_private
  .valid_content_review_timeline_atlas_metrics(p_metrics jsonb)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  duration_value numeric;
  frame_count_value numeric;
  atlas_count_value numeric;
  first_second_value numeric;
  last_second_value numeric;
  coverage_value numeric;
  max_gap_value numeric;
  sample_rate_value numeric;
  columns_value numeric;
  rows_value numeric;
  computed_max_gap numeric;
  sampled_values numeric[];
  dense_short_value boolean;
begin
  if jsonb_typeof(p_metrics) is distinct from 'object' then
    return false;
  end if;

  if not (p_metrics ? 'timeline_atlas_status') then
    return not exists (
      select 1
      from jsonb_object_keys(p_metrics) as key_name
      where key_name like 'timeline\_atlas\_%' escape '\'
    );
  end if;

  if p_metrics ->> 'timeline_atlas_status' <> 'completed'
     or p_metrics ->> 'timeline_atlas_version'
          <> 'dense_full_duration_v1'
     or p_metrics ->> 'timeline_atlas_order'
          <> 'row_major_chronological'
     or jsonb_typeof(p_metrics -> 'duration_seconds')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'frame_count')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'sampled_at_seconds')
          is distinct from 'array'
     or jsonb_array_length(p_metrics -> 'sampled_at_seconds') <> 5
     or exists (
       select 1
       from jsonb_array_elements(
         p_metrics -> 'sampled_at_seconds'
       ) as sampled(item)
       where jsonb_typeof(sampled.item) is distinct from 'number'
     )
     or jsonb_typeof(p_metrics -> 'timeline_atlas_frame_ordinal')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'timeline_atlas_frame_count')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'timeline_atlas_first_second')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'timeline_atlas_last_second')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'timeline_atlas_coverage_ratio')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'timeline_atlas_max_gap_seconds')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'timeline_atlas_sample_rate_fps')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'timeline_atlas_columns')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'timeline_atlas_rows')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'timeline_atlas_dense_short_video')
          is distinct from 'boolean'
     or exists (
       select 1
       from jsonb_object_keys(p_metrics) as key_name
       where key_name like 'timeline\_atlas\_%' escape '\'
         and key_name <> all(array[
           'timeline_atlas_status',
           'timeline_atlas_version',
           'timeline_atlas_frame_ordinal',
           'timeline_atlas_frame_count',
           'timeline_atlas_first_second',
           'timeline_atlas_last_second',
           'timeline_atlas_coverage_ratio',
           'timeline_atlas_max_gap_seconds',
           'timeline_atlas_sample_rate_fps',
           'timeline_atlas_columns',
           'timeline_atlas_rows',
           'timeline_atlas_order',
           'timeline_atlas_dense_short_video'
         ])
     ) then
    return false;
  end if;

  duration_value := (p_metrics ->> 'duration_seconds')::numeric;
  frame_count_value := (p_metrics ->> 'frame_count')::numeric;
  atlas_count_value := (
    p_metrics ->> 'timeline_atlas_frame_count'
  )::numeric;
  first_second_value := (
    p_metrics ->> 'timeline_atlas_first_second'
  )::numeric;
  last_second_value := (
    p_metrics ->> 'timeline_atlas_last_second'
  )::numeric;
  coverage_value := (
    p_metrics ->> 'timeline_atlas_coverage_ratio'
  )::numeric;
  max_gap_value := (
    p_metrics ->> 'timeline_atlas_max_gap_seconds'
  )::numeric;
  sample_rate_value := (
    p_metrics ->> 'timeline_atlas_sample_rate_fps'
  )::numeric;
  columns_value := (
    p_metrics ->> 'timeline_atlas_columns'
  )::numeric;
  rows_value := (p_metrics ->> 'timeline_atlas_rows')::numeric;
  dense_short_value := (
    p_metrics ->> 'timeline_atlas_dense_short_video'
  )::boolean;
  select array_agg(
    (sampled.item #>> '{}')::numeric
    order by sampled.ordinality
  )
  into sampled_values
  from jsonb_array_elements(p_metrics -> 'sampled_at_seconds')
    with ordinality as sampled(item, ordinality);

  if atlas_count_value <= 1 then
    return false;
  end if;
  computed_max_gap := greatest(
    first_second_value,
    duration_value - last_second_value,
    (last_second_value - first_second_value) /
      (atlas_count_value - 1)
  );

  return duration_value between 0.01 and 3600
    and frame_count_value = 5
    and (p_metrics ->> 'timeline_atlas_frame_ordinal')::numeric = 5
    and atlas_count_value = trunc(atlas_count_value)
    and atlas_count_value between 12 and 24
    and atlas_count_value = (
      p_metrics ->> 'temporal_scan_frame_count'
    )::numeric
    and first_second_value between 0 and duration_value
    and last_second_value > first_second_value
    and last_second_value <= duration_value
    and abs(
      first_second_value -
        (p_metrics ->> 'temporal_scan_first_second')::numeric
    ) <= 0.002
    and abs(
      last_second_value -
        (p_metrics ->> 'temporal_scan_last_second')::numeric
    ) <= 0.002
    and coverage_value between 0.9 and 1
    and abs(
      coverage_value -
        (p_metrics ->> 'temporal_scan_coverage_ratio')::numeric
    ) <= 0.002
    and abs(
      (last_second_value - first_second_value) / duration_value -
        coverage_value
    ) <= 0.02
    and max_gap_value between 0.001 and duration_value
    and abs(max_gap_value - computed_max_gap) <= 0.002
    and sample_rate_value > 0
    and sample_rate_value <= 2400
    and abs(
      sample_rate_value - atlas_count_value / duration_value
    ) <= 0.02
    and columns_value = trunc(columns_value)
    and columns_value between 2 and 8
    and rows_value = trunc(rows_value)
    and rows_value between 2 and 8
    and columns_value * rows_value >= atlas_count_value
    and columns_value * (rows_value - 1) < atlas_count_value
    and dense_short_value = (
      duration_value <= 10
      and coverage_value >= 0.9
      and max_gap_value <= 0.5
    )
    and sampled_values[1] >= 0
    and sampled_values[2] > sampled_values[1]
    and sampled_values[3] > sampled_values[2]
    and sampled_values[4] > sampled_values[3]
    and sampled_values[5] > sampled_values[4]
    and sampled_values[5] <= duration_value
    and abs(sampled_values[5] - last_second_value) <= 0.002;
exception
  when numeric_value_out_of_range or invalid_text_representation
    or division_by_zero then
    return false;
end;
$$;

alter table content_factory.content_review_evidence_sets
  add constraint content_review_evidence_timeline_atlas_metrics_valid
  check (
    content_factory_private.valid_content_review_timeline_atlas_metrics(
      technical_metrics
    )
  ) not valid;

alter table content_factory.content_review_evidence_sets
  validate constraint
    content_review_evidence_timeline_atlas_metrics_valid;

alter function public.creator_commit_content_review_evidence(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_commit_content_review_evidence(
  jsonb
)
  rename to
    creator_commit_content_review_evidence_without_atlas_gate_v3;
revoke all on function
  content_factory_private
    .creator_commit_content_review_evidence_without_atlas_gate_v3(
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
begin
  p_payload := content_factory_private.require_payload(p_payload);
  technical_metrics_value := coalesce(
    p_payload -> 'technical_metrics',
    '{}'::jsonb
  );
  if coalesce(technical_metrics_value ->> 'source_type', '') <> 'video'
     or coalesce(
       technical_metrics_value ->> 'timeline_atlas_status',
       ''
     ) <> 'completed'
     or not content_factory_private
       .valid_content_review_timeline_atlas_metrics(
         technical_metrics_value
       ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_timeline_atlas_metrics_invalid';
  end if;
  return content_factory_private
    .creator_commit_content_review_evidence_without_atlas_gate_v3(
      p_payload
    );
end;
$$;

revoke all on function
  content_factory_private
    .valid_content_review_timeline_atlas_metrics(jsonb)
  from public, anon, authenticated;
grant execute on function
  content_factory_private
    .valid_content_review_timeline_atlas_metrics(jsonb)
  to service_role;
revoke all on function public.creator_commit_content_review_evidence(jsonb)
  from public, anon;
grant execute on function public.creator_commit_content_review_evidence(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
