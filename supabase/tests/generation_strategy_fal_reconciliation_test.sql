begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(10);

select ok(
  content_factory_private
    .generation_strategy_reconciliation_confirmation_allowed(
      'runway', 'provider_task_attached', 'RUNWAY_TASK_ID_VERIFIED'
    ),
  'Runway attach keeps its exact confirmation'
);

select ok(
  content_factory_private
    .generation_strategy_reconciliation_confirmation_allowed(
      'runway', 'confirmed_not_submitted', 'RUNWAY_NO_TASK_VERIFIED'
    ),
  'Runway no-submission keeps its exact confirmation'
);

select ok(
  content_factory_private
    .generation_strategy_reconciliation_confirmation_allowed(
      'fal', 'provider_task_attached', 'FAL_REQUEST_ID_VERIFIED'
    ),
  'fal attach uses the exact request confirmation'
);

select ok(
  content_factory_private
    .generation_strategy_reconciliation_confirmation_allowed(
      'fal', 'confirmed_not_submitted', 'FAL_NO_REQUEST_VERIFIED'
    ),
  'fal no-submission uses the exact no-request confirmation'
);

select ok(
  not content_factory_private
    .generation_strategy_reconciliation_confirmation_allowed(
      'runway', 'confirmed_not_submitted', 'FAL_NO_REQUEST_VERIFIED'
    ),
  'a fal confirmation cannot resolve a Runway job'
);

select ok(
  not content_factory_private
    .generation_strategy_reconciliation_confirmation_allowed(
      'fal', 'confirmed_not_submitted', 'RUNWAY_NO_TASK_VERIFIED'
    ),
  'a Runway confirmation cannot resolve a fal job'
);

select ok(
  not content_factory_private
    .generation_strategy_reconciliation_confirmation_allowed(
      'future-provider', 'confirmed_not_submitted',
      'FAL_NO_REQUEST_VERIFIED'
    ),
  'an unknown provider fails closed'
);

select is(
  content_factory_private
    .generation_strategy_reconciliation_confirmation_allowed(null, null, null),
  false,
  'nullable provider input fails closed with boolean false'
);

select ok(
  strpos(
    pg_get_functiondef(
      'public.system_reconcile_generation_strategy_dispatch(jsonb)'
        ::regprocedure
    ),
    'receipt_row.provider is distinct from job_row.provider'
  ) > 0
  and strpos(
    pg_get_functiondef(
      'public.system_reconcile_generation_strategy_dispatch(jsonb)'
        ::regprocedure
    ),
    'receipt.receipt_hash = claim_row.receipt_hash'
  ) > 0,
  'strategy reconciliation binds provider to the signed readiness receipt'
);

select ok(
  strpos(
    pg_get_functiondef(
      'public.system_reconcile_generation_strategy_dispatch(jsonb)'
        ::regprocedure
    ),
    $v$jsonb_typeof(p_payload -> 'confirmation') <> 'string'$v$
  ) > 0
  and strpos(
    pg_get_functiondef(
      'public.system_reconcile_generation_strategy_dispatch(jsonb)'
        ::regprocedure
    ),
    $v$jsonb_typeof(p_payload -> 'resolution') <> 'string'$v$
  ) > 0
  and strpos(
    pg_get_functiondef(
      'public.system_reconcile_generation_strategy_dispatch(jsonb)'
        ::regprocedure
    ),
    $v$jsonb_typeof(p_payload -> 'version') <> 'string'$v$
  ) > 0
  and strpos(
    pg_get_functiondef(
      'public.system_reconcile_generation_strategy_dispatch(jsonb)'
        ::regprocedure
    ),
    'provider_status_value is null'
  ) > 0,
  'JSON null and empty attach status cannot bypass required fields'
);

select * from finish();
rollback;
