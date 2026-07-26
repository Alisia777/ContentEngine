begin;

-- Browser audio measurements are advisory, but once they are attached to a
-- video evidence manifest their shape must be immutable and bounded.  Legacy
-- manifests only carried audio_analyzed=false; keep those readable while
-- requiring every new completed analysis to include the full numeric set.
create or replace function content_factory_private
  .valid_content_review_audio_metrics(p_metrics jsonb)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  channel_count_value numeric;
  sample_rate_value numeric;
  duration_value numeric;
  duration_delta_value numeric;
  peak_value numeric;
  rms_value numeric;
  silence_ratio_value numeric;
  clipping_ratio_value numeric;
begin
  if jsonb_typeof(p_metrics) is distinct from 'object' then
    return false;
  end if;

  if not (p_metrics ? 'audio_analyzed')
     and not (p_metrics ? 'audio_analysis_status') then
    return not exists (
      select 1
      from jsonb_object_keys(p_metrics) as key_name
      where key_name like 'audio\_%' escape '\'
    );
  end if;

  if not (p_metrics ? 'audio_analysis_status') then
    -- Historical ready evidence used exactly this marker before local audio
    -- analysis existed.
    return p_metrics -> 'audio_analyzed' = 'false'::jsonb
      and not exists (
        select 1
        from jsonb_object_keys(p_metrics) as key_name
        where key_name like 'audio\_%' escape '\'
          and key_name <> 'audio_analyzed'
      );
  end if;

  if p_metrics ->> 'audio_analysis_status' = 'unavailable' then
    return p_metrics -> 'audio_analyzed' = 'false'::jsonb
      and p_metrics ? 'audio_expected'
      and (
        p_metrics -> 'audio_expected' = 'null'::jsonb
        or jsonb_typeof(p_metrics -> 'audio_expected') = 'boolean'
      )
      and not exists (
        select 1
        from jsonb_object_keys(p_metrics) as key_name
        where key_name like 'audio\_%' escape '\'
          and key_name <> all(array[
            'audio_expected',
            'audio_analyzed',
            'audio_analysis_status'
          ])
      );
  end if;

  if p_metrics ->> 'audio_analysis_status' <> 'completed'
     or p_metrics -> 'audio_analyzed' is distinct from 'true'::jsonb
     or not (p_metrics ? 'audio_expected')
     or not (
       p_metrics -> 'audio_expected' = 'null'::jsonb
       or jsonb_typeof(p_metrics -> 'audio_expected') = 'boolean'
     )
     or jsonb_typeof(p_metrics -> 'audio_channel_count')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'audio_sample_rate_hz')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'audio_duration_seconds')
          is distinct from 'number'
     or not (p_metrics ? 'audio_video_duration_delta_seconds')
     or not (
       p_metrics -> 'audio_video_duration_delta_seconds' = 'null'::jsonb
       or jsonb_typeof(
         p_metrics -> 'audio_video_duration_delta_seconds'
       ) = 'number'
     )
     or jsonb_typeof(p_metrics -> 'audio_peak_dbfs')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'audio_rms_dbfs')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'audio_silence_ratio')
          is distinct from 'number'
     or jsonb_typeof(p_metrics -> 'audio_clipping_ratio')
          is distinct from 'number'
     or exists (
       select 1
       from jsonb_object_keys(p_metrics) as key_name
       where key_name like 'audio\_%' escape '\'
         and key_name <> all(array[
           'audio_expected',
           'audio_analyzed',
           'audio_analysis_status',
           'audio_channel_count',
           'audio_sample_rate_hz',
           'audio_duration_seconds',
           'audio_video_duration_delta_seconds',
           'audio_peak_dbfs',
           'audio_rms_dbfs',
           'audio_silence_ratio',
           'audio_clipping_ratio'
         ])
     ) then
    return false;
  end if;

  channel_count_value := (p_metrics ->> 'audio_channel_count')::numeric;
  sample_rate_value := (p_metrics ->> 'audio_sample_rate_hz')::numeric;
  duration_value := (p_metrics ->> 'audio_duration_seconds')::numeric;
  duration_delta_value := case
    when p_metrics -> 'audio_video_duration_delta_seconds' = 'null'::jsonb
      then null
    else (
      p_metrics ->> 'audio_video_duration_delta_seconds'
    )::numeric
  end;
  peak_value := (p_metrics ->> 'audio_peak_dbfs')::numeric;
  rms_value := (p_metrics ->> 'audio_rms_dbfs')::numeric;
  silence_ratio_value := (p_metrics ->> 'audio_silence_ratio')::numeric;
  clipping_ratio_value := (p_metrics ->> 'audio_clipping_ratio')::numeric;

  return channel_count_value = trunc(channel_count_value)
    and channel_count_value between 1 and 32
    and sample_rate_value = trunc(sample_rate_value)
    and sample_rate_value between 8000 and 384000
    and duration_value between 0.001 and 3600
    and (
      duration_delta_value is null
      or duration_delta_value between 0 and 3600
    )
    and peak_value between -160 and 0
    and rms_value between -160 and 0
    and silence_ratio_value between 0 and 1
    and clipping_ratio_value between 0 and 1;
exception
  when numeric_value_out_of_range or invalid_text_representation then
    return false;
end;
$$;

alter table content_factory.content_review_evidence_sets
  add constraint content_review_evidence_audio_metrics_valid
  check (
    content_factory_private.valid_content_review_audio_metrics(
      technical_metrics
    )
  ) not valid;

alter table content_factory.content_review_evidence_sets
  validate constraint content_review_evidence_audio_metrics_valid;

alter function public.creator_commit_content_review_evidence(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_commit_content_review_evidence(
  jsonb
)
  rename to creator_commit_content_review_evidence_without_audio_gate_v1;
revoke all on function
  content_factory_private
    .creator_commit_content_review_evidence_without_audio_gate_v1(jsonb)
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
     or not (technical_metrics_value ? 'audio_expected')
     or coalesce(
       technical_metrics_value ->> 'audio_analysis_status',
       ''
     )
          not in ('completed', 'unavailable')
     or not content_factory_private.valid_content_review_audio_metrics(
       technical_metrics_value
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_audio_metrics_invalid';
  end if;
  return content_factory_private
    .creator_commit_content_review_evidence_without_audio_gate_v1(p_payload);
end;
$$;

revoke all on function
  content_factory_private.valid_content_review_audio_metrics(jsonb)
  from public, anon, authenticated;
grant execute on function
  content_factory_private.valid_content_review_audio_metrics(jsonb)
  to service_role;
revoke all on function public.creator_commit_content_review_evidence(jsonb)
  from public, anon;
grant execute on function public.creator_commit_content_review_evidence(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
