begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select has_function(
  'public',
  'system_recover_generation_strategy_provider_result',
  array['jsonb'],
  'provider-result recovery RPC remains installed'
);

select ok(
  position(
    '(job_row.input #>> ''{strategy_execution,strategy_id}'')' || E'\n' ||
    '       is distinct from receipt_row.strategy_id'
    in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '(job_row.input ->> ''strategy_id'') is distinct from'
    in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) = 0,
  'RPC reads canonical nested strategy identity and no stale top-level key'
);

with production_shape(input_value, receipt_strategy_id) as (
  values (
    jsonb_build_object(
      'provider', 'fal',
      'strategy_recipe', 'product_swap',
      'strategy_execution', jsonb_build_object(
        'version', 'generation-strategy-execution-snapshot-v1',
        'strategy_id', 'viral_product_swap'
      )
    ),
    'viral_product_swap'::text
  )
)
select ok(
  input_value ->> 'strategy_id' is null
  and input_value ->> 'provider' = 'fal'
  and input_value ->> 'strategy_recipe' = 'product_swap'
  and input_value #>> '{strategy_execution,strategy_id}' =
    receipt_strategy_id
  and not (
    (input_value #>> '{strategy_execution,strategy_id}')
      is distinct from receipt_strategy_id
  ),
  'exact production input shape satisfies the canonical strategy guard'
)
from production_shape;

select ok(
  (
    jsonb_build_object(
      'provider', 'fal',
      'strategy_recipe', 'product_swap',
      'strategy_execution', jsonb_build_object(
        'version', 'generation-strategy-execution-snapshot-v1'
      )
    ) #>> '{strategy_execution,strategy_id}'
  ) is distinct from 'viral_product_swap',
  'missing canonical strategy identity still fails closed'
);

select ok(
  (
    jsonb_build_object(
      'provider', 'fal',
      'strategy_recipe', 'product_swap',
      'strategy_execution', jsonb_build_object(
        'version', 'generation-strategy-execution-snapshot-v1',
        'strategy_id', null
      )
    ) #>> '{strategy_execution,strategy_id}'
  ) is distinct from 'viral_product_swap',
  'JSON null canonical strategy identity still fails closed'
);

select ok(
  position(
    '(job_row.input ->> ''provider'') is distinct from ''fal'''
    in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '(job_row.input ->> ''strategy_recipe'') is distinct from ''product_swap'''
    in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '(job_row.input #>> ''{strategy_execution,version}'') is distinct from'
    in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'provider, recipe and execution-version guards remain unchanged'
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
  'CREATE OR REPLACE preserves the service-role-only authority boundary'
);

select ok(
  position(
    'generation-strategy-provider-result-recovery-response-v1'
    in pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
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
  ) = 0,
  'response and immutable-ledger recovery contract remain unchanged'
);

select * from finish();
rollback;
