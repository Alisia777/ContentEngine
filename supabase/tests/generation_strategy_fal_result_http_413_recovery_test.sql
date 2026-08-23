begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select has_function(
  'public',
  'system_recover_generation_strategy_provider_result',
  array['jsonb'],
  'the append-only fal result-route recovery RPC remains installed'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_recover_generation_strategy_provider_result(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_recover_generation_strategy_provider_result(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_recover_generation_strategy_provider_result(jsonb)',
    'execute'
  ),
  'result-route recovery remains service-role only'
);

-- pgTAP не имеет ни has_constraint, ни hasnt_constraint — таких функций в нём
-- нет вовсе, и определений в проекте тоже нет. Эти два утверждения никогда не
-- выполнялись: файл падал на четвёртой строке с «function does not exist», и
-- весь остаток проверок за ними не исполнялся ни разу.
--
-- Спрашиваем каталог напрямую. Смысл сохранён дословно: ограничение v3 стоит,
-- вытесненное v2 снято.
select ok(
  exists (
    select 1
    from pg_constraint c
    join pg_class t on t.oid = c.conrelid
    join pg_namespace n on n.oid = t.relnamespace
    where n.nspname = 'content_factory'
      and t.relname = 'generation_strategy_provider_status_events'
      and c.conname = 'generation_strategy_provider_status_transition_v3_check'
  ),
  'the v3 provider transition constraint is installed'
);

select ok(
  not exists (
    select 1
    from pg_constraint c
    join pg_class t on t.oid = c.conrelid
    join pg_namespace n on n.oid = t.relnamespace
    where n.nspname = 'content_factory'
      and t.relname = 'generation_strategy_provider_status_events'
      and c.conname = 'generation_strategy_provider_status_transition_v2_check'
  ),
  'the superseded v2 provider transition constraint is absent'
);

select ok(
  position('previous_status = ''failed''' in pg_get_constraintdef(c.oid)) > 0
  and position('provider_status = ''succeeded''' in pg_get_constraintdef(c.oid)) > 0
  and position('provider_result_http_405' in pg_get_constraintdef(c.oid)) > 0
  and position('provider_result_http_413' in pg_get_constraintdef(c.oid)) > 0
  and position(
    'generation-strategy-provider-result-recovery-v1'
      in pg_get_constraintdef(c.oid)
  ) > 0
  and position('strategy-result-recovery:' in pg_get_constraintdef(c.oid)) > 0,
  'only a marked 405/413 failed-to-succeeded correction is admitted'
)
from pg_constraint c
where c.conrelid =
    'content_factory.generation_strategy_provider_status_events'::regclass
  and c.conname =
    'generation_strategy_provider_status_transition_v3_check';

select ok(
  position(
    '''FAL_RESULT_HTTP_405_RECOVERY_VERIFIED'''
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '''FAL_RESULT_HTTP_413_RECOVERY_VERIFIED'''
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    'latest_event_row.failure_code = ''provider_result_http_413'''
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '(input_payload ->> ''confirmation'') is not distinct from' || chr(10) ||
    '           ''FAL_RESULT_HTTP_413_RECOVERY_VERIFIED'''
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0,
  'the immutable 413 failure code is bound to its exact confirmation'
);

select ok(
  position(
    '(event_row.output_snapshot ->> ''recovered_failure_code'')'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '''recovered_failure_code'', latest_event_row.failure_code'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '(event_row.output_snapshot ->> ''recovered_failure_code'')' || chr(10) ||
    '             is not distinct from ''provider_result_http_413'''
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0,
  'replay rechecks the persisted recovered code and matching confirmation'
);

select ok(
  position(
    '(job_row.input #>> ''{strategy_execution,strategy_id}'')' || chr(10) ||
    '       is distinct from receipt_row.strategy_id'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '(job_row.output ->> ''failure_code'') is distinct from' || chr(10) ||
    '       latest_event_row.failure_code'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '(task_row.result ->> ''failure_code'') is distinct from' || chr(10) ||
    '       latest_event_row.failure_code'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0,
  'receipt, job, task and immutable latest event remain code-bound'
);

select ok(
  position(
    'ledger_hash_after_value is distinct from ledger_hash_before_value'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    'insert into content_factory.generation_spend_ledger'
      in lower(pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      ))
  ) = 0
  and position(
    'update content_factory.generation_spend_ledger'
      in lower(pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      ))
  ) = 0
  and position(
    'delete from content_factory.generation_spend_ledger'
      in lower(pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      ))
  ) = 0,
  '413 correction proves the ledger unchanged and cannot write spend'
);

select ok(
  position(
    'insert into content_factory.generation_strategy_provider_status_events'
      in lower(pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      ))
  ) > 0
  and position(
    'update content_factory.generation_strategy_provider_status_events'
      in lower(pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      ))
  ) = 0
  and position(
    'delete from content_factory.generation_strategy_provider_status_events'
      in lower(pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      ))
  ) = 0,
  'the failed 413 event is preserved and recovery appends one success event'
);

select throws_ok(
  $call$
    select public.system_recover_generation_strategy_provider_result(
      jsonb_build_object(
        'version', 'generation-strategy-provider-result-recovery-request-v1',
        'organization_id', 'ba100000-0000-4000-8000-000000000001',
        'project_id', 'ba200000-0000-4000-8000-000000000001',
        'actor_id', 'ba300000-0000-4000-8000-000000000001',
        'generation_job_id', 'ba400000-0000-4000-8000-000000000001',
        'provider_task_id', '0198c21a-4444-7777-8888-222222222222',
        'output', jsonb_build_object(
          'output_object_name',
            'ba100000-0000-4000-8000-000000000001/' ||
            'ba300000-0000-4000-8000-000000000001/recovery/result.mp4',
          'mime_type', 'video/mp4',
          'size_bytes', 4096,
          'sha256', repeat('b', 64)
        ),
        'provider_evidence_hash', repeat('a', 64),
        'confirmation', 'FAL_RESULT_HTTP_413_RECOVERY_VERIFIED',
        'idempotency_key',
          'strategy-result-recovery:' ||
          'ba400000-0000-4000-8000-000000000001:' || repeat('a', 32)
      )
    )
  $call$,
  '55000',
  'generation_strategy_provider_result_recovery_not_current',
  'the new exact 413 confirmation passes shape validation but no identity gate'
);

select throws_ok(
  $call$
    select public.system_recover_generation_strategy_provider_result(
      jsonb_build_object(
        'version', 'generation-strategy-provider-result-recovery-request-v1',
        'organization_id', 'ba100000-0000-4000-8000-000000000001',
        'project_id', 'ba200000-0000-4000-8000-000000000001',
        'actor_id', 'ba300000-0000-4000-8000-000000000001',
        'generation_job_id', 'ba400000-0000-4000-8000-000000000001',
        'provider_task_id', '0198c21a-4444-7777-8888-222222222222',
        'output', jsonb_build_object(
          'output_object_name',
            'ba100000-0000-4000-8000-000000000001/' ||
            'ba300000-0000-4000-8000-000000000001/recovery/result.mp4',
          'mime_type', 'video/mp4',
          'size_bytes', 4096,
          'sha256', repeat('b', 64)
        ),
        'provider_evidence_hash', repeat('a', 64),
        'confirmation', 'FAL_RESULT_HTTP_499_RECOVERY_VERIFIED',
        'idempotency_key',
          'strategy-result-recovery:' ||
          'ba400000-0000-4000-8000-000000000001:' || repeat('a', 32)
      )
    )
  $call$,
  '22023',
  'generation_strategy_provider_result_recovery_payload_invalid',
  'an unreviewed result HTTP code cannot enter the recovery writer'
);

select * from finish();
rollback;
