begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select has_function(
  'public',
  'system_recover_generation_strategy_provider_result',
  array['jsonb'],
  'the narrow provider-result recovery RPC is installed'
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
  'recovery is service-role only'
);

select ok(
  p.prosecdef and p.provolatile = 'v'
  and pg_get_function_arguments(p.oid) =
    'input_payload jsonb DEFAULT ''{}''::jsonb'
  and pg_get_function_result(p.oid) = 'jsonb',
  'recovery has the exact SECURITY DEFINER volatile JSON contract'
)
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.proname = 'system_recover_generation_strategy_provider_result';

select ok(
  position(
    'previous_status = ''failed''' in pg_get_constraintdef(c.oid)
  ) > 0
  and position(
    'provider_status = ''succeeded''' in pg_get_constraintdef(c.oid)
  ) > 0
  and position(
    'provider_result_http_405' in pg_get_constraintdef(c.oid)
  ) > 0
  and position(
    'provider_result_http_413' in pg_get_constraintdef(c.oid)
  ) > 0
  and position(
    'generation-strategy-provider-result-recovery-v1'
      in pg_get_constraintdef(c.oid)
  ) > 0
  and position('IS DISTINCT FROM' in pg_get_constraintdef(c.oid)) > 0
  and position('NOT (' in pg_get_constraintdef(c.oid)) > 0
  and position(
    'strategy-result-recovery:' in pg_get_constraintdef(c.oid)
  ) > 0,
  'failed-to-succeeded is permitted only for a marked 405/413 correction'
)
from pg_constraint c
where c.conrelid =
    'content_factory.generation_strategy_provider_status_events'::regclass
  and c.conname =
    'generation_strategy_provider_status_transition_v3_check';

select ok(
  position(
    '''generation-strategy-provider-result-recovery-request-v1'''
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '''FAL_RESULT_HTTP_405_RECOVERY_VERIFIED'''
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '''strategy-result-recovery:'' || generation_job_id_value::text'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0,
  'request version, explicit confirmation and deterministic idempotency fail closed'
);

select ok(
  position(
    'receipt_row.provider is distinct from ''fal''' in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'receipt_row.strategy_id is distinct from ''viral_product_swap'''
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    'dispatch_row.outcome is distinct from ''submitted'''
      in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'latest_event_row.failure_code not in'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0,
  'only an exact paid FAL Product Swap 405/413 result-route state is recoverable'
);

select ok(
  position(
    'from storage.objects storage_object' in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'storage_size_value is distinct from size_bytes_value'
      in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'storage_sha256_value is distinct from sha256_value'
      in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'insert into content_factory.media_objects' in lower(pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    ))
  ) > 0,
  'the exact pre-uploaded MP4 is re-read before media registration'
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
  'the paid ledger is locked and proven byte-identical, never written'
);

select ok(
  position(
    '(input_payload ->> ''version'') is distinct from'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  -- Подтверждений стало ДВА (405 и 413), поэтому сравнение перевернулось:
  -- вместо «отказать, если отличается от единственного» стало «принять, если
  -- совпадает с одним из двух». Проверяемое свойство от этого не изменилось —
  -- оператор NULL-безопасный, и JSON null не превращается в «неизвестно»,
  -- а честно не совпадает ни с одним из разрешённых значений.
  and position(
    '(input_payload ->> ''confirmation'') is not distinct from'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '(job_row.output ->> ''failure_code'') is distinct from'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '(task_row.result ->> ''failure_code'') is distinct from'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '(media_row.metadata ->> ''provider'') is distinct from'
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0,
  'JSON null and missing critical facts fail closed instead of becoming UNKNOWN'
);

select throws_ok(
  $call$
    select public.system_recover_generation_strategy_provider_result(
      jsonb_build_object(
        'version', null,
        'organization_id', 'aa100000-0000-4000-8000-000000000001',
        'project_id', 'aa200000-0000-4000-8000-000000000001',
        'actor_id', 'aa300000-0000-4000-8000-000000000001',
        'generation_job_id', 'aa400000-0000-4000-8000-000000000001',
        'provider_task_id', '0198c21a-4444-7777-8888-111111111111',
        'output', jsonb_build_object(
          'output_object_name',
            'aa100000-0000-4000-8000-000000000001/' ||
            'aa300000-0000-4000-8000-000000000001/recovery/result.mp4',
          'mime_type', 'video/mp4',
          'size_bytes', 4096,
          'sha256', repeat('b', 64)
        ),
        'provider_evidence_hash', repeat('a', 64),
        'confirmation', 'FAL_RESULT_HTTP_405_RECOVERY_VERIFIED',
        'idempotency_key',
          'strategy-result-recovery:' ||
          'aa400000-0000-4000-8000-000000000001:' || repeat('a', 32)
      )
    )
  $call$,
  '22023',
  'generation_strategy_provider_result_recovery_payload_invalid',
  'JSON null request version is rejected before identity lookup'
);

select throws_ok(
  $call$
    select public.system_recover_generation_strategy_provider_result(
      jsonb_build_object(
        'version', 'generation-strategy-provider-result-recovery-request-v1',
        'organization_id', 'aa100000-0000-4000-8000-000000000001',
        'project_id', 'aa200000-0000-4000-8000-000000000001',
        'actor_id', 'aa300000-0000-4000-8000-000000000001',
        'generation_job_id', 'aa400000-0000-4000-8000-000000000001',
        'provider_task_id', '0198c21a-4444-7777-8888-111111111111',
        'output', jsonb_build_object(
          'output_object_name',
            'aa100000-0000-4000-8000-000000000001/' ||
            'aa300000-0000-4000-8000-000000000001/recovery/result.mp4',
          'mime_type', 'video/mp4',
          'size_bytes', 4096
        ),
        'provider_evidence_hash', repeat('a', 64),
        'confirmation', 'FAL_RESULT_HTTP_405_RECOVERY_VERIFIED',
        'idempotency_key',
          'strategy-result-recovery:' ||
          'aa400000-0000-4000-8000-000000000001:' || repeat('a', 32)
      )
    )
  $call$,
  '22023',
  'generation_strategy_provider_result_recovery_payload_invalid',
  'missing output sha256 is rejected before identity lookup'
);

select throws_ok(
  $call$
    select public.system_recover_generation_strategy_provider_result(
      jsonb_build_object(
        'version', 'generation-strategy-provider-result-recovery-request-v1',
        'organization_id', 'aa100000-0000-4000-8000-000000000001',
        'project_id', 'aa200000-0000-4000-8000-000000000001',
        'actor_id', 'aa300000-0000-4000-8000-000000000001',
        'generation_job_id', 'aa400000-0000-4000-8000-000000000001',
        'provider_task_id', '0198c21a-4444-7777-8888-111111111111',
        'output', jsonb_build_object(
          'output_object_name',
            'aa100000-0000-4000-8000-000000000001/' ||
            'aa300000-0000-4000-8000-000000000001/recovery/result.mp4',
          'mime_type', null,
          'size_bytes', 4096,
          'sha256', repeat('b', 64)
        ),
        'provider_evidence_hash', repeat('a', 64),
        'confirmation', 'FAL_RESULT_HTTP_405_RECOVERY_VERIFIED',
        'idempotency_key',
          'strategy-result-recovery:' ||
          'aa400000-0000-4000-8000-000000000001:' || repeat('a', 32)
      )
    )
  $call$,
  '22023',
  'generation_strategy_provider_result_recovery_payload_invalid',
  'JSON null output MIME type is rejected before identity lookup'
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
  'the failed provider event is preserved and correction is append-only'
);

select ok(
  position(
    'update content_factory.generation_jobs job'
      in lower(pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      ))
  ) > 0
  and position(
    'update content_factory.generation_batches batch'
      in lower(pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      ))
  ) > 0
  and position(
    'update content_factory.creator_tasks task'
      in lower(pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      ))
  ) > 0
  and position(
    '''manual_human_review''' in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'job, batch and review-task projections are restored together'
);

select ok(
  position(
    '''generation-strategy-provider-result-recovery-response-v1'''
      in pg_get_functiondef(
        'public.system_recover_generation_strategy_provider_result(jsonb)'
          ::regprocedure
      )
  ) > 0
  and position(
    '''provider_post_retried'', false' in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''ledger_mutated'', false' in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''manual_human_review_required'', true' in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'response exposes the exact no-repost, no-ledger-mutation review contract'
);

select * from finish();
rollback;
