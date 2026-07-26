begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(11);

select ok(
  content_factory_private.valid_content_review_audio_metrics('{}'::jsonb),
  'preparing evidence without metrics remains valid'
);

select ok(
  content_factory_private.valid_content_review_audio_metrics(
    '{"audio_analyzed":false}'::jsonb
  ),
  'legacy ready evidence remains valid'
);

select ok(
  content_factory_private.valid_content_review_audio_metrics(
    jsonb_build_object(
      'audio_expected', true,
      'audio_analyzed', false,
      'audio_analysis_status', 'unavailable'
    )
  ),
  'bounded unavailable audio analysis is valid'
);

select ok(
  content_factory_private.valid_content_review_audio_metrics(
    jsonb_build_object(
      'audio_expected', true,
      'audio_analyzed', true,
      'audio_analysis_status', 'completed',
      'audio_channel_count', 2,
      'audio_sample_rate_hz', 48000,
      'audio_duration_seconds', 8.001,
      'audio_video_duration_delta_seconds', 0.001,
      'audio_peak_dbfs', -0.5,
      'audio_rms_dbfs', -18.25,
      'audio_silence_ratio', 0.12,
      'audio_clipping_ratio', 0.0001
    )
  ),
  'complete bounded local audio metrics are valid'
);

select ok(
  not content_factory_private.valid_content_review_audio_metrics(
    jsonb_build_object(
      'audio_expected', true,
      'audio_analyzed', true,
      'audio_analysis_status', 'completed',
      'audio_channel_count', 2,
      'audio_sample_rate_hz', 48000,
      'audio_duration_seconds', 8,
      'audio_video_duration_delta_seconds', 0,
      'audio_peak_dbfs', 1,
      'audio_rms_dbfs', -18,
      'audio_silence_ratio', 0.1,
      'audio_clipping_ratio', 0
    )
  ),
  'positive dBFS peak is rejected'
);

select ok(
  not content_factory_private.valid_content_review_audio_metrics(
    jsonb_build_object(
      'audio_expected', true,
      'audio_analyzed', true,
      'audio_analysis_status', 'completed',
      'audio_channel_count', 2,
      'audio_sample_rate_hz', 48000,
      'audio_duration_seconds', 8,
      'audio_video_duration_delta_seconds', 0,
      'audio_peak_dbfs', -1,
      'audio_rms_dbfs', -18,
      'audio_silence_ratio', 1.01,
      'audio_clipping_ratio', 0
    )
  ),
  'out-of-range silence ratio is rejected'
);

select ok(
  not content_factory_private.valid_content_review_audio_metrics(
    '{"audio_expected":true,"audio_analyzed":false,"audio_analysis_status":"unavailable","audio_transcript":"invented"}'::jsonb
  ),
  'unapproved transcript-like audio fields are rejected'
);

select ok(
  not content_factory_private.valid_content_review_audio_metrics(
    '{"source_type":"video","audio_transcript":"invented"}'::jsonb
  ),
  'audio-prefixed fields cannot bypass the analysis contract'
);

select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
        'content_factory.content_review_evidence_sets'::regclass
      and constraint_row.conname =
        'content_review_evidence_audio_metrics_valid'
      and constraint_row.convalidated
  ),
  'validated evidence constraint is installed'
);

select ok(
  to_regprocedure(
    'public.creator_commit_content_review_evidence(jsonb)'
  ) is not null,
  'public evidence commit remains available through the audio gate'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_commit_content_review_evidence_without_audio_gate_v1(jsonb)'
  ) is not null,
  'legacy implementation is private behind the audio gate'
);

select * from finish();

rollback;
