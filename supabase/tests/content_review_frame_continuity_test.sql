begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(10);

select ok(
  content_factory_private.valid_content_review_continuity_metrics(
    '{}'::jsonb
  ),
  'historical evidence without continuity aggregates remains readable'
);

select ok(
  content_factory_private.valid_content_review_continuity_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'continuity_scan_status', 'completed',
      'continuity_scan_strategy', 'browser_presented_frames_v1',
      'continuity_scan_callback_count', 240,
      'continuity_scan_presented_frame_count', 240,
      'continuity_scan_missed_frame_count', 0,
      'continuity_scan_first_second', 0,
      'continuity_scan_last_second', 7.9667,
      'continuity_scan_coverage_ratio', 0.9958,
      'continuity_scan_max_gap_seconds', 0.0334,
      'continuity_black_frame_ratio', 0,
      'continuity_longest_black_run_seconds', 0,
      'continuity_duplicate_transition_ratio', 0.02,
      'continuity_longest_duplicate_run_seconds', 0.0667,
      'continuity_mean_frame_difference', 0.08,
      'continuity_raw_frames_persisted', false
    )
  ),
  'bounded aggregates from every presented short-video frame are valid'
);

select ok(
  content_factory_private.valid_content_review_continuity_metrics(
    jsonb_build_object(
      'duration_seconds', 12,
      'continuity_scan_status', 'completed',
      'continuity_scan_strategy', 'browser_presented_frames_v1',
      'continuity_scan_callback_count', 360,
      'continuity_scan_presented_frame_count', 360,
      'continuity_scan_missed_frame_count', 0,
      'continuity_scan_first_second', 0,
      'continuity_scan_last_second', 11.9667,
      'continuity_scan_coverage_ratio', 0.9972,
      'continuity_scan_max_gap_seconds', 0.0334,
      'continuity_black_frame_ratio', 0,
      'continuity_longest_black_run_seconds', 0,
      'continuity_duplicate_transition_ratio', 0.02,
      'continuity_longest_duplicate_run_seconds', 0.0667,
      'continuity_mean_frame_difference', 0.08,
      'continuity_raw_frames_persisted', false
    )
  ),
  'generated video continuity remains required through twelve seconds'
);

select ok(
  not content_factory_private.valid_content_review_continuity_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'continuity_scan_status', 'completed',
      'continuity_scan_strategy', 'browser_presented_frames_v1',
      'continuity_scan_callback_count', 12,
      'continuity_scan_presented_frame_count', 240,
      'continuity_scan_missed_frame_count', 0
    )
  ),
  'forged callback coverage and missed-frame totals are rejected'
);

select ok(
  not content_factory_private.valid_content_review_continuity_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'continuity_scan_status', 'completed',
      'continuity_raw_frame_payload', 'forbidden'
    )
  ),
  'raw frame payload fields are rejected'
);

select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
        'content_factory.content_review_evidence_sets'::regclass
      and constraint_row.conname =
        'content_review_evidence_continuity_metrics_valid'
      and constraint_row.convalidated
  ),
  'validated continuity evidence constraint is installed'
);

select ok(
  to_regprocedure(
    'public.creator_commit_content_review_evidence(jsonb)'
  ) is not null,
  'public evidence commit remains available through the continuity gate'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_commit_content_review_evidence_without_continuity_gate_v4(jsonb)'
  ) is not null,
  'the previous evidence implementation is private behind the continuity gate'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_commit_content_review_evidence(jsonb)',
    'execute'
  ),
  'authenticated creators may execute the public continuity-gated commit'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_commit_content_review_evidence_without_continuity_gate_v4(jsonb)',
    'execute'
  ),
  'browser sessions cannot bypass the continuity evidence gate'
);

select * from finish();

rollback;
