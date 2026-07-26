begin;

-- Keep the exact spoken line next to generated-video provenance so the review
-- form can prefill it without asking an operator to copy the generation prompt.
-- The value is derived from the immutable paid job input and cannot be supplied
-- independently by a browser.
create or replace function
  content_factory_private.generated_video_spoken_script(prompt_value text)
returns text
language plpgsql
immutable
strict
set search_path = ''
as $$
declare
  matches text[];
  result_value text;
begin
  if length(prompt_value) > 30000 then
    return null;
  end if;
  matches := regexp_match(
    prompt_value,
    'Реплика героя дословно:[[:space:]]*«([^»]+)»',
    'i'
  );
  result_value := nullif(btrim(coalesce(matches[1], '')), '');
  if result_value is null or length(result_value) not between 3 and 6000 then
    return null;
  end if;
  return result_value;
end;
$$;

create or replace function
  content_factory_private.bind_generated_video_spoken_script()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  generation_job_id_value uuid;
  spoken_script_value text;
begin
  if new.metadata ->> 'kind' <> 'generated_video'
     or new.metadata ->> 'provider' <> 'runway'
     or coalesce(new.metadata ->> 'generation_job_id', '') !~
       '^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
  then
    return new;
  end if;
  generation_job_id_value :=
    (new.metadata ->> 'generation_job_id')::uuid;
  select
    content_factory_private.generated_video_spoken_script(
      job.input ->> 'prompt_text'
    )
  into spoken_script_value
  from content_factory.generation_jobs job
  where job.organization_id = new.organization_id
    and job.id = generation_job_id_value
    and job.mode = 'real'
    and job.provider = 'runway'
    and job.input ->> 'model' = 'seedance2_fast'
    and job.input -> 'audio' = 'true'::jsonb;
  if spoken_script_value is not null then
    new.metadata := new.metadata || jsonb_build_object(
      'spoken_script', spoken_script_value,
      'spoken_script_source', 'generation_job_prompt_v1'
    );
  else
    new.metadata := new.metadata - array[
      'spoken_script', 'spoken_script_source'
    ]::text[];
  end if;
  return new;
end;
$$;

drop trigger if exists bind_generated_video_spoken_script
  on content_factory.media_objects;
create trigger bind_generated_video_spoken_script
before insert or update of metadata
on content_factory.media_objects
for each row execute function
  content_factory_private.bind_generated_video_spoken_script();

update content_factory.media_objects media
set metadata = media.metadata || jsonb_build_object(
      'spoken_script',
        content_factory_private.generated_video_spoken_script(
          job.input ->> 'prompt_text'
        ),
      'spoken_script_source', 'generation_job_prompt_v1'
    ),
    updated_at = now()
from content_factory.generation_jobs job
where media.organization_id = job.organization_id
  and media.metadata ->> 'kind' = 'generated_video'
  and media.metadata ->> 'provider' = 'runway'
  and media.metadata ->> 'generation_job_id' = job.id::text
  and job.mode = 'real'
  and job.provider = 'runway'
  and job.input ->> 'model' = 'seedance2_fast'
  and job.input -> 'audio' = 'true'::jsonb
  and content_factory_private.generated_video_spoken_script(
        job.input ->> 'prompt_text'
      ) is not null
  and media.metadata ->> 'spoken_script' is distinct from
      content_factory_private.generated_video_spoken_script(
        job.input ->> 'prompt_text'
      );

-- The original validator remains the source of truth for every mature result
-- field. This narrow wrapper adds a bounded speech-analysis envelope while
-- keeping old completed runs valid and immutable.
alter function
  content_factory_private.validate_content_review_result(jsonb)
  rename to validate_content_review_result_without_speech_v4;

revoke all on function
  content_factory_private
    .validate_content_review_result_without_speech_v4(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.validate_content_review_result(value jsonb)
returns void
language plpgsql
immutable
set search_path = ''
as $$
declare
  speech_value jsonb;
  status_value text;
  consent_value boolean;
  expected_words integer;
  transcript_words integer;
  matched_words integer;
  numeric_key text;
  numeric_value numeric;
begin
  if value is null or jsonb_typeof(value) <> 'object' then
    raise exception using
      errcode = '22023',
      message = 'content_review_result_invalid';
  end if;
  if not (value ? 'speech_analysis') then
    perform content_factory_private
      .validate_content_review_result_without_speech_v4(value);
    return;
  end if;

  speech_value := value -> 'speech_analysis';
  if jsonb_typeof(speech_value) <> 'object'
     or length(speech_value::text) > 12000
     or speech_value - array[
       'status', 'consent_confirmed', 'model', 'provider_request_id',
       'transcript_sha256', 'transcript_excerpt',
       'expected_word_count', 'transcript_word_count',
       'matched_word_count', 'coverage_ratio', 'precision_ratio',
       'similarity_ratio', 'word_error_rate',
       'transcription_confidence'
     ]::text[] <> '{}'::jsonb
     or not (
       speech_value ?& array[
         'status', 'consent_confirmed', 'model', 'provider_request_id',
         'transcript_sha256', 'transcript_excerpt',
         'expected_word_count', 'transcript_word_count',
         'matched_word_count', 'coverage_ratio', 'precision_ratio',
         'similarity_ratio', 'word_error_rate',
         'transcription_confidence'
       ]
     )
  then
    raise exception using
      errcode = '22023',
      message = 'content_review_speech_analysis_invalid';
  end if;

  status_value := speech_value ->> 'status';
  if status_value not in (
       'not_applicable', 'not_requested', 'skipped_no_script',
       'skipped_audio_unavailable', 'skipped_file_too_large',
       'unavailable', 'completed'
     )
     or jsonb_typeof(speech_value -> 'consent_confirmed') <> 'boolean'
     or coalesce(speech_value ->> 'expected_word_count', '') !~ '^[0-9]{1,3}$'
     or coalesce(speech_value ->> 'transcript_word_count', '') !~ '^[0-9]{1,3}$'
  then
    raise exception using
      errcode = '22023',
      message = 'content_review_speech_analysis_invalid';
  end if;
  consent_value := (speech_value ->> 'consent_confirmed')::boolean;
  expected_words := (speech_value ->> 'expected_word_count')::integer;
  transcript_words := (speech_value ->> 'transcript_word_count')::integer;
  if expected_words not between 0 and 600
     or transcript_words not between 0 and 600 then
    raise exception using
      errcode = '22023',
      message = 'content_review_speech_analysis_invalid';
  end if;

  if status_value = 'completed' then
    if not consent_value
       or expected_words < 3
       or jsonb_typeof(speech_value -> 'model') <> 'string'
       or speech_value ->> 'model' not in (
         'gpt-4o-transcribe', 'gpt-4o-mini-transcribe'
       )
       or (
         speech_value -> 'provider_request_id' <> 'null'::jsonb
         and (
           jsonb_typeof(speech_value -> 'provider_request_id') <> 'string'
           or length(btrim(speech_value ->> 'provider_request_id'))
                not between 3 and 240
           or speech_value ->> 'provider_request_id' ~ '[[:cntrl:]]'
         )
       )
       or jsonb_typeof(speech_value -> 'transcript_sha256') <> 'string'
       or speech_value ->> 'transcript_sha256' !~ '^[0-9a-f]{64}$'
       or jsonb_typeof(speech_value -> 'transcript_excerpt') <> 'string'
       or length(speech_value ->> 'transcript_excerpt') > 1200
       or coalesce(speech_value ->> 'matched_word_count', '') !~ '^[0-9]{1,3}$'
    then
      raise exception using
        errcode = '22023',
        message = 'content_review_speech_analysis_invalid';
    end if;
    matched_words := (speech_value ->> 'matched_word_count')::integer;
    if matched_words < 0
       or matched_words > least(expected_words, transcript_words) then
      raise exception using
        errcode = '22023',
        message = 'content_review_speech_analysis_invalid';
    end if;
    foreach numeric_key in array array[
      'coverage_ratio', 'precision_ratio', 'similarity_ratio',
      'word_error_rate'
    ] loop
      if jsonb_typeof(speech_value -> numeric_key) <> 'number' then
        raise exception using
          errcode = '22023',
          message = 'content_review_speech_analysis_invalid';
      end if;
      numeric_value := (speech_value ->> numeric_key)::numeric;
      if numeric_value < 0
         or numeric_value > case
           when numeric_key = 'word_error_rate' then 2
           else 1
         end
      then
        raise exception using
          errcode = '22023',
          message = 'content_review_speech_analysis_invalid';
      end if;
    end loop;
    if speech_value -> 'transcription_confidence' <> 'null'::jsonb then
      if jsonb_typeof(speech_value -> 'transcription_confidence')
           <> 'number'
         or (speech_value ->> 'transcription_confidence')::numeric
              not between 0 and 1
      then
        raise exception using
          errcode = '22023',
          message = 'content_review_speech_analysis_invalid';
      end if;
    end if;
  else
    if speech_value -> 'model' <> 'null'::jsonb
       or speech_value -> 'provider_request_id' <> 'null'::jsonb
       or speech_value -> 'transcript_sha256' <> 'null'::jsonb
       or speech_value -> 'transcript_excerpt' <> 'null'::jsonb
       or transcript_words <> 0
       or speech_value -> 'matched_word_count' <> 'null'::jsonb
       or speech_value -> 'coverage_ratio' <> 'null'::jsonb
       or speech_value -> 'precision_ratio' <> 'null'::jsonb
       or speech_value -> 'similarity_ratio' <> 'null'::jsonb
       or speech_value -> 'word_error_rate' <> 'null'::jsonb
       or speech_value -> 'transcription_confidence' <> 'null'::jsonb
    then
      raise exception using
        errcode = '22023',
        message = 'content_review_speech_analysis_invalid';
    end if;
  end if;

  perform content_factory_private
    .validate_content_review_result_without_speech_v4(
      value - 'speech_analysis'
    );
end;
$$;

revoke all on function
  content_factory_private.validate_content_review_result(jsonb)
  from public, anon, authenticated;

do $content_review_speech_contract$
declare
  extracted text;
begin
  extracted := content_factory_private.generated_video_spoken_script(
    'Кадр. Реплика героя дословно: «Показываю точный товар крупно». Финал.'
  );
  if extracted <> 'Показываю точный товар крупно' then
    raise exception 'generated spoken script extraction contract failed';
  end if;
end;
$content_review_speech_contract$;

commit;
