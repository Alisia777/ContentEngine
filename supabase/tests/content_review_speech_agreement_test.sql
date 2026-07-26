begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(8);

create or replace function pg_temp.review_result_with_speech(
  p_speech jsonb
)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select jsonb_build_object(
    'overall_score', 82,
    'scores', '{}'::jsonb,
    'compliance_status', 'pass_with_warnings',
    'blockers_count', 0,
    'warnings_count', 0,
    'strengths', '[]'::jsonb,
    'findings', '[]'::jsonb,
    'recommendations', '[]'::jsonb,
    'comparison', '{}'::jsonb,
    'speech_analysis', p_speech
  )
$$;

select is(
  content_factory_private.generated_video_spoken_script(
    'План. Реплика героя дословно: «Точный товар уже в кадре». Финал.'
  ),
  'Точный товар уже в кадре',
  'the exact generated spoken line is derived from the immutable prompt'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    where trigger_row.tgrelid =
        'content_factory.media_objects'::regclass
      and trigger_row.tgname = 'bind_generated_video_spoken_script'
      and not trigger_row.tgisinternal
  ),
  'generated media receives server-derived spoken-script metadata'
);

select lives_ok(
  $$select content_factory_private.validate_content_review_result(
    pg_temp.review_result_with_speech(jsonb_build_object(
      'status', 'completed',
      'consent_confirmed', true,
      'model', 'gpt-4o-transcribe',
      'provider_request_id', 'req_speech_fixture',
      'transcript_sha256', repeat('a', 64),
      'transcript_excerpt', 'Точный товар уже в кадре',
      'expected_word_count', 5,
      'transcript_word_count', 5,
      'matched_word_count', 5,
      'coverage_ratio', 1,
      'precision_ratio', 1,
      'similarity_ratio', 1,
      'word_error_rate', 0,
      'transcription_confidence', 0.98
    ))
  )$$,
  'a bounded consent-backed speech analysis is accepted'
);

select throws_ok(
  $$select content_factory_private.validate_content_review_result(
    pg_temp.review_result_with_speech(jsonb_build_object(
      'status', 'completed',
      'consent_confirmed', false,
      'model', 'gpt-4o-transcribe',
      'provider_request_id', null,
      'transcript_sha256', repeat('a', 64),
      'transcript_excerpt', 'Точный товар уже в кадре',
      'expected_word_count', 5,
      'transcript_word_count', 5,
      'matched_word_count', 5,
      'coverage_ratio', 1,
      'precision_ratio', 1,
      'similarity_ratio', 1,
      'word_error_rate', 0,
      'transcription_confidence', null
    ))
  )$$,
  '22023',
  'content_review_speech_analysis_invalid',
  'completed transcription cannot exist without explicit consent'
);

select lives_ok(
  $$select content_factory_private.validate_content_review_result(
    pg_temp.review_result_with_speech(jsonb_build_object(
      'status', 'not_requested',
      'consent_confirmed', false,
      'model', null,
      'provider_request_id', null,
      'transcript_sha256', null,
      'transcript_excerpt', null,
      'expected_word_count', 5,
      'transcript_word_count', 0,
      'matched_word_count', null,
      'coverage_ratio', null,
      'precision_ratio', null,
      'similarity_ratio', null,
      'word_error_rate', null,
      'transcription_confidence', null
    ))
  )$$,
  'manual speech review remains a valid opt-out path'
);

select ok(
  content_factory_private.valid_content_review_audio_metrics(
    jsonb_build_object(
      'speech_transcription_notice_version', 'openai_mp4_v1',
      'audio_expected', true,
      'audio_analyzed', false,
      'audio_analysis_status', 'unavailable'
    )
  ),
  'the versioned transcription notice coexists with bounded audio metrics'
);

select ok(
  to_regprocedure(
    'content_factory_private.validate_content_review_result_without_speech_v4(jsonb)'
  ) is not null,
  'the mature result validator remains private behind the speech envelope'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.validate_content_review_result_without_speech_v4(jsonb)',
    'execute'
  ),
  'browser sessions cannot bypass the speech-result validator'
);

select * from finish();

rollback;
