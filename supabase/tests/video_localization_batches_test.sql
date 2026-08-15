begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(44);

select has_table(
  'content_factory',
  'video_source_approvals',
  'approved owned or licensed video sources are durable'
);
select has_table(
  'content_factory',
  'video_localization_batches',
  'localization batches are durable'
);
select has_table(
  'content_factory',
  'video_localization_assignments',
  'each of ten outputs has an immutable assignment'
);
select has_table(
  'content_factory',
  'video_localization_qa_decisions',
  'wave QA decisions are durable'
);
select has_table(
  'content_factory_private',
  'video_localization_provider_operations',
  'provider receipts remain private'
);

select ok(
  (select relrowsecurity from pg_class
   where oid = 'content_factory.video_source_approvals'::regclass),
  'source approvals use RLS'
);
select ok(
  (select relrowsecurity from pg_class
   where oid = 'content_factory.video_localization_batches'::regclass),
  'localization batches use RLS'
);
select ok(
  (select relrowsecurity from pg_class
   where oid = 'content_factory.video_localization_assignments'::regclass),
  'localization assignments use RLS'
);
select ok(
  (select relrowsecurity from pg_class
   where oid = 'content_factory.video_localization_qa_decisions'::regclass),
  'localization QA decisions use RLS'
);

select is(
  (
    select count(*)::integer
    from (values
      ('content_factory.video_source_approvals'::regclass),
      ('content_factory.video_localization_batches'::regclass),
      ('content_factory.video_localization_assignments'::regclass),
      ('content_factory.video_localization_qa_decisions'::regclass),
      ('content_factory_private.video_localization_provider_operations'::regclass)
    ) protected(table_oid)
    where has_table_privilege('authenticated', table_oid, 'select')
  ),
  0,
  'browser users receive no direct localization table reads'
);
select is(
  (
    select count(*)::integer
    from (values
      ('content_factory.video_source_approvals'::regclass),
      ('content_factory.video_localization_batches'::regclass),
      ('content_factory.video_localization_assignments'::regclass),
      ('content_factory.video_localization_qa_decisions'::regclass),
      ('content_factory_private.video_localization_provider_operations'::regclass)
    ) protected(table_oid)
    where has_table_privilege('service_role', table_oid, 'select')
  ),
  5,
  'service role can operate the durable localization ledger'
);

select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname in (
        'creator_approve_video_localization_source',
        'creator_create_video_localization_batch',
        'creator_video_localization_batch',
        'creator_decide_video_localization_wave',
        'creator_cancel_video_localization_batch'
      )
      and pg_get_function_identity_arguments(procedure.oid) = 'p_payload jsonb'
  ),
  5,
  'five browser localization RPCs expose one bounded jsonb payload'
);
select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname in (
        'creator_approve_video_localization_source',
        'creator_create_video_localization_batch',
        'creator_video_localization_batch',
        'creator_decide_video_localization_wave',
        'creator_cancel_video_localization_batch'
      )
      and has_function_privilege('authenticated', procedure.oid, 'execute')
  ),
  5,
  'authenticated users can use the role-checked creator RPCs'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_update_video_localization_assignment(jsonb)',
    'execute'
  ),
  'browser users cannot write trusted provider receipts'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_update_video_localization_assignment(jsonb)',
    'execute'
  ),
  'service role can reconcile provider operations'
);

select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.video_localization_batches'::regclass
      and constraint_row.contype = 'c'
      and pg_get_constraintdef(constraint_row.oid) like '%target_count = 10%'
  ),
  'v1 batches are hard-limited to exactly ten outputs'
);
select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.video_localization_batches'::regclass
      and constraint_row.contype = 'c'
      and pg_get_constraintdef(constraint_row.oid)
        like '%qa_gate_after_sequence = 2%'
  ),
  'wave two cannot precede QA of the first two outputs'
);
select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.video_localization_assignments'::regclass
      and constraint_row.contype = 'c'
      and pg_get_constraintdef(constraint_row.oid) like '%unknown%'
  ),
  'assignment state records an ambiguous provider outcome'
);
select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory_private.video_localization_provider_operations'::regclass
      and constraint_row.contype = 'c'
      and pg_get_constraintdef(constraint_row.oid) like '%frozen%'
  ),
  'an ambiguous provider operation is frozen rather than retried'
);

select ok(
  content_factory_private.valid_video_localization_modes(
    '["subtitles", "dub_audio"]'::jsonb
  ),
  'the Harly subtitle and dubbing mode set is valid'
);
select ok(
  not content_factory_private.valid_video_localization_modes(
    '["subtitles", "subtitles"]'::jsonb
  ),
  'duplicate localization modes are rejected'
);
select ok(
  content_factory_private.valid_video_localization_checklist(
    '{
      "product_fidelity": true,
      "language_quality": true,
      "no_common_defect": true,
      "rights_ok": true
    }'::jsonb
  ),
  'the complete wave-one QA checklist is valid'
);
select ok(
  not content_factory_private.valid_video_localization_checklist(
    '{"product_fidelity": true}'::jsonb
  ),
  'partial wave QA cannot unlock the remaining eight outputs'
);

select is(
  content_factory_private.video_localization_cost_microusd(
    'internal_captions',
    8
  ),
  6667::bigint,
  'eight seconds of caption planning rounds up deterministically'
);
select is(
  content_factory_private.video_localization_cost_microusd(
    'elevenlabs_dubbing',
    8
  ),
  66667::bigint,
  'eight seconds of dubbing planning rounds up deterministically'
);
select is(
  content_factory_private.video_localization_cost_microusd(
    'heygen_lipsync_speed',
    8
  ),
  266400::bigint,
  'premium lip sync remains a separately priced option'
);

select ok(
  pg_get_functiondef(
    'public.creator_create_video_localization_batch(jsonb)'::regprocedure
  ) like '%harly_five_sources_required%',
  'Harly v1 requires five exact owned or licensed sources'
);
select ok(
  pg_get_functiondef(
    'public.creator_create_video_localization_batch(jsonb)'::regprocedure
  ) like '%harly_subtitles_and_dub_modes_required%',
  'the first Harly pilot is exactly subtitles plus dubbing'
);
select ok(
  pg_get_functiondef(
    'public.creator_create_video_localization_batch(jsonb)'::regprocedure
  ) like '%duplicate_localization_source_asset%',
  'the same source asset cannot fill multiple pilot slots'
);
select ok(
  pg_get_functiondef(
    'public.creator_create_video_localization_batch(jsonb)'::regprocedure
  ) like '%video_localization_batch_already_active%',
  'a second active batch cannot duplicate the same product work'
);
select ok(
  pg_get_functiondef(
    'public.creator_create_video_localization_batch(jsonb)'::regprocedure
  ) like '%pg_advisory_xact_lock%',
  'batch creation is serialized per product'
);
select ok(
  pg_get_functiondef(
    'public.creator_create_video_localization_batch(jsonb)'::regprocedure
  ) like '%2026-08-01.public-provider-rate-card.v2%',
  'every plan carries a versioned rate-card snapshot'
);

select ok(
  pg_get_functiondef(
    'public.creator_decide_video_localization_wave(jsonb)'::regprocedure
  ) like '%localization_wave1_outputs_incomplete%',
  'QA cannot run before both first-wave outputs exist'
);
select ok(
  pg_get_functiondef(
    'public.creator_decide_video_localization_wave(jsonb)'::regprocedure
  ) like '%localization_qa_checklist_incomplete%',
  'approval requires every product, language, defect and rights check'
);
select ok(
  pg_get_functiondef(
    'public.creator_decide_video_localization_wave(jsonb)'::regprocedure
  ) like '%wave2_ready%',
  'approved QA unlocks the remaining eight assignments'
);
select ok(
  pg_get_functiondef(
    'public.creator_decide_video_localization_wave(jsonb)'::regprocedure
  ) like '%wave1_qa_rejected%',
  'rejected QA blocks the remaining wave'
);
select ok(
  pg_get_functiondef(
    'public.creator_cancel_video_localization_batch(jsonb)'::regprocedure
  ) like '%localization_reconciliation_required%',
  'a batch with in-flight or ambiguous spend cannot be casually cancelled'
);

select ok(
  pg_get_functiondef(
    'public.system_update_video_localization_assignment(jsonb)'::regprocedure
  ) like '%localization_operation_request_mismatch%',
  'provider receipts bind one assignment to one request hash'
);
select ok(
  pg_get_functiondef(
    'public.system_update_video_localization_assignment(jsonb)'::regprocedure
  ) like '%localization_batch_has_inflight_assignment%',
  'only one paid or external operation runs in a batch at a time'
);
select ok(
  pg_get_functiondef(
    'public.system_update_video_localization_assignment(jsonb)'::regprocedure
  ) like '%localization_output_media_invalid%',
  'success requires a durable ready video for the same product'
);
select ok(
  pg_get_functiondef(
    'public.system_update_video_localization_assignment(jsonb)'::regprocedure
  ) like '%frozen%',
  'unknown external outcomes enter the frozen state'
);
select ok(
  pg_get_functiondef(
    'public.system_update_video_localization_assignment(jsonb)'::regprocedure
  ) like '%provider_outcome_replay_forbidden%',
  'unknown provider outcomes explicitly forbid automatic replay'
);
select ok(
  pg_get_functiondef(
    'public.system_update_video_localization_assignment(jsonb)'::regprocedure
  ) like '%qa_required%'
  and pg_get_functiondef(
    'public.system_update_video_localization_assignment(jsonb)'::regprocedure
  ) like '%completed%',
  'provider reconciliation advances first to QA and only later to completion'
);

select is(
  (
    select count(*)::integer
    from information_schema.columns column_row
    where column_row.table_schema = 'content_factory'
      and column_row.table_name like 'video_localization%'
      and column_row.column_name in (
        'url', 'source_url', 'caption', 'prompt',
        'transcript', 'raw_text', 'provider_prompt'
      )
  ),
  0,
  'raw competitor content and free prompt prose are absent from localization storage'
);

select * from finish();
rollback;
