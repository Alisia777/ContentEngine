begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(12);

select has_trigger(
  'content_factory',
  'video_localization_batches',
  'guard_video_localization_batch_state',
  'batch state guard is installed'
);
select has_trigger(
  'content_factory',
  'video_localization_assignments',
  'guard_video_localization_assignment_state',
  'assignment state guard is installed'
);
select has_trigger(
  'content_factory_private',
  'video_localization_provider_operations',
  'guard_video_localization_provider_operation',
  'provider receipt state guard is installed'
);

select ok(
  not content_factory_private.valid_video_localization_modes('{}'::jsonb),
  'non-array localization modes fail closed without a type error'
);
select ok(
  not content_factory_private.valid_video_localization_checklist('[]'::jsonb),
  'non-object QA checklist fails closed without a type error'
);
select ok(
  not content_factory_private.valid_video_localization_checklist(
    '{
      "product_fidelity": true,
      "language_quality": true,
      "no_common_defect": true,
      "rights_ok": true,
      "unexpected": true
    }'::jsonb
  ),
  'QA checklist rejects extra unreviewed keys'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.guard_video_localization_batch_state()'::regprocedure
  ) like '%video_localization_batch_plan_immutable%',
  'batch plan fields are immutable after creation'
);
select ok(
  pg_get_functiondef(
    'content_factory_private.guard_video_localization_assignment_state()'::regprocedure
  ) like '%video_localization_assignment_plan_immutable%',
  'assignment plan fields are immutable after creation'
);
select ok(
  pg_get_functiondef(
    'content_factory_private.guard_video_localization_provider_operation()'::regprocedure
  ) like '%localization_provider_receipt_identity_immutable%',
  'provider receipt identity cannot change after reservation'
);
select ok(
  pg_get_functiondef(
    'content_factory_private.guard_video_localization_provider_operation()'::regprocedure
  ) like '%localization_provider_task_receipt_mismatch%',
  'provider task hash cannot silently change'
);
select ok(
  pg_get_functiondef(
    'content_factory_private.guard_video_localization_provider_operation()'::regprocedure
  ) like '%localization_provider_receipt_replay_mismatch%',
  'same-state provider updates must be byte-stable replays'
);
select ok(
  pg_get_functiondef(
    'content_factory_private.guard_video_localization_provider_operation()'::regprocedure
  ) like '%old.status in (''settled'', ''failed'', ''frozen'')%',
  'settled failed and frozen provider operations are terminal'
);

select * from finish();
rollback;
