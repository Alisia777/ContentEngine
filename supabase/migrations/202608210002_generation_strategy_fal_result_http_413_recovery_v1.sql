begin;

-- 202608210002_generation_strategy_fal_result_http_413_recovery_v1
--
-- A completed fal request can expose both a provider-owned response_url ending
-- in /response and the generic documented bare request result route. The Edge
-- reader used to strip the provider-owned suffix before its first GET. For one
-- already-submitted and settled Product Swap request that bare app-root GET
-- returned HTTP 413, which was incorrectly recorded as a terminal model
-- failure. This migration broadens the existing append-only result correction
-- by exactly one machine code. It preserves the 405 contract, requires a
-- code-specific 413 confirmation, and cannot submit, charge or rewrite history.

do $replace_fal_result_recovery_transition$
declare
  constraint_name_value text;
  constraint_definition_value text;
  v2_count_value integer;
  v3_count_value integer;
begin
  select
    count(*) filter (
      where constraint_row.conname =
        'generation_strategy_provider_status_transition_v2_check'
    )::integer,
    count(*) filter (
      where constraint_row.conname =
        'generation_strategy_provider_status_transition_v3_check'
    )::integer
    into v2_count_value, v3_count_value
  from pg_constraint constraint_row
  where constraint_row.conrelid =
      'content_factory.generation_strategy_provider_status_events'::regclass
    and constraint_row.contype = 'c'
    and constraint_row.conname in (
      'generation_strategy_provider_status_transition_v2_check',
      'generation_strategy_provider_status_transition_v3_check'
    );

  if v2_count_value = 0 and v3_count_value = 1 then
    select pg_get_constraintdef(constraint_row.oid, true)
      into constraint_definition_value
    from pg_constraint constraint_row
    where constraint_row.conrelid =
        'content_factory.generation_strategy_provider_status_events'::regclass
      and constraint_row.conname =
        'generation_strategy_provider_status_transition_v3_check';
    if position(
       'provider_result_http_405' in constraint_definition_value
     ) > 0
     and position(
       'provider_result_http_413' in constraint_definition_value
     ) > 0 then
      return;
    end if;
    raise exception using message =
      'provider_result_route_recovery_transition_v3_invalid';
  end if;

  if v2_count_value <> 1 or v3_count_value <> 0 then
    raise exception using message =
      'provider_result_route_recovery_transition_cardinality_invalid';
  end if;

  select constraint_row.conname, pg_get_constraintdef(constraint_row.oid, true)
    into constraint_name_value, constraint_definition_value
  from pg_constraint constraint_row
  where constraint_row.conrelid =
      'content_factory.generation_strategy_provider_status_events'::regclass
    and constraint_row.conname =
      'generation_strategy_provider_status_transition_v2_check';

  if position(
       'provider_result_http_405' in constraint_definition_value
     ) = 0
     or position(
       'generation-strategy-provider-result-recovery-v1'
         in constraint_definition_value
     ) = 0 then
    raise exception using message =
      'provider_result_route_recovery_transition_anchor_invalid';
  end if;

  execute format(
    'alter table content_factory.generation_strategy_provider_status_events ' ||
    'drop constraint %I',
    constraint_name_value
  );

  execute $ddl$
    alter table content_factory.generation_strategy_provider_status_events
      add constraint generation_strategy_provider_status_transition_v3_check
      check (
        (
          transition_ordinal = 1
          and previous_status is null
          and provider_status = 'submitted'
        )
        or (
          transition_ordinal > 1
          and previous_status in ('submitted', 'processing')
          and provider_status in (
            'processing', 'succeeded', 'failed', 'cancelled'
          )
          and previous_status <> provider_status
        )
        or (
          transition_ordinal > 1
          and previous_status = 'failed'
          and provider_status = 'succeeded'
          and idempotency_key like 'strategy-result-recovery:%'
          and (output_snapshot ->> 'recovery_version') is not distinct from
            'generation-strategy-provider-result-recovery-v1'
          and (
            (output_snapshot ->> 'recovered_failure_code') is not distinct from
              'provider_result_http_405'
            or (output_snapshot ->> 'recovered_failure_code') is not distinct from
              'provider_result_http_413'
          )
        )
      )
  $ddl$;
end;
$replace_fal_result_recovery_transition$;

do $patch_fal_result_route_recovery_rpc$
declare
  definition_value text;
  patched_value text;
  search_values text[] := array[
    $search$     or (input_payload ->> 'confirmation') is distinct from
       'FAL_RESULT_HTTP_405_RECOVERY_VERIFIED'$search$,
    $search$       or (event_row.output_snapshot ->> 'recovered_failure_code')
         is distinct from
         'provider_result_http_405'$search$,
    $search$     or (job_row.output ->> 'failure_code') is distinct from
       'provider_result_http_405'$search$,
    $search$     or (job_row.output ->> 'provider_failure_code') is distinct from
       'provider_result_http_405'$search$,
    $search$     or (task_row.result ->> 'failure_code') is distinct from
       'provider_result_http_405'$search$,
    $search$     or latest_event_row.failure_code is distinct from
       'provider_result_http_405'$search$,
    $search$    'recovered_failure_code', 'provider_result_http_405',$search$,
    $search$        'recovered_failure_code', 'provider_result_http_405'$search$
  ];
  replacement_values text[] := array[
    $replacement$     or not (
       (input_payload ->> 'confirmation') is not distinct from
         'FAL_RESULT_HTTP_405_RECOVERY_VERIFIED'
       or (input_payload ->> 'confirmation') is not distinct from
         'FAL_RESULT_HTTP_413_RECOVERY_VERIFIED'
     )$replacement$,
    $replacement$       or not (
         (
           (event_row.output_snapshot ->> 'recovered_failure_code')
             is not distinct from 'provider_result_http_405'
           and (input_payload ->> 'confirmation') is not distinct from
             'FAL_RESULT_HTTP_405_RECOVERY_VERIFIED'
         )
         or (
           (event_row.output_snapshot ->> 'recovered_failure_code')
             is not distinct from 'provider_result_http_413'
           and (input_payload ->> 'confirmation') is not distinct from
             'FAL_RESULT_HTTP_413_RECOVERY_VERIFIED'
         )
       )$replacement$,
    $replacement$     or (job_row.output ->> 'failure_code') is distinct from
       latest_event_row.failure_code$replacement$,
    $replacement$     or (job_row.output ->> 'provider_failure_code') is distinct from
       latest_event_row.failure_code$replacement$,
    $replacement$     or (task_row.result ->> 'failure_code') is distinct from
       latest_event_row.failure_code$replacement$,
    $replacement$     or latest_event_row.failure_code is null
     or latest_event_row.failure_code not in (
       'provider_result_http_405', 'provider_result_http_413'
     )
     or not (
       (
         latest_event_row.failure_code = 'provider_result_http_405'
         and (input_payload ->> 'confirmation') is not distinct from
           'FAL_RESULT_HTTP_405_RECOVERY_VERIFIED'
       )
       or (
         latest_event_row.failure_code = 'provider_result_http_413'
         and (input_payload ->> 'confirmation') is not distinct from
           'FAL_RESULT_HTTP_413_RECOVERY_VERIFIED'
       )
     )$replacement$,
    $replacement$    'recovered_failure_code', latest_event_row.failure_code,$replacement$,
    $replacement$        'recovered_failure_code', latest_event_row.failure_code$replacement$
  ];
  search_value text;
  replacement_value text;
  hit_count_value integer;
  index_value integer;
begin
  select replace(
    pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    ),
    E'\r\n', E'\n'
  ) into definition_value;

  if definition_value is null then
    raise exception using message =
      'provider_result_route_recovery_rpc_missing';
  end if;

  if position(
       'FAL_RESULT_HTTP_413_RECOVERY_VERIFIED' in definition_value
     ) > 0
     and position(
       $guard$latest_event_row.failure_code not in (
       'provider_result_http_405', 'provider_result_http_413'
     )$guard$ in definition_value
     ) > 0
     and position(
       $snapshot$'recovered_failure_code', latest_event_row.failure_code$snapshot$
       in definition_value
     ) > 0 then
    return;
  end if;

  patched_value := definition_value;
  for index_value in 1..array_length(search_values, 1) loop
    search_value := search_values[index_value];
    replacement_value := replacement_values[index_value];
    hit_count_value := (
      length(patched_value)
      - length(replace(patched_value, search_value, ''))
    ) / length(search_value);
    if hit_count_value <> 1 then
      raise exception using message =
        'provider_result_route_recovery_rpc_anchor_invalid:' ||
        index_value::text || ':' || hit_count_value::text;
    end if;
    patched_value := replace(
      patched_value, search_value, replacement_value
    );
  end loop;

  if position(
       $canonical$(job_row.input #>> '{strategy_execution,strategy_id}')
       is distinct from receipt_row.strategy_id$canonical$
       in patched_value
     ) = 0
     or position(
       $legacy$(job_row.input ->> 'strategy_id') is distinct from$legacy$
       in patched_value
     ) > 0
     or position(
       'FAL_RESULT_HTTP_413_RECOVERY_VERIFIED' in patched_value
     ) = 0
     or position(
       $snapshot$'recovered_failure_code', latest_event_row.failure_code$snapshot$
       in patched_value
     ) = 0 then
    raise exception using message =
      'provider_result_route_recovery_rpc_patch_invalid';
  end if;

  execute patched_value;
end;
$patch_fal_result_route_recovery_rpc$;

comment on function
  public.system_recover_generation_strategy_provider_result(jsonb) is
  'Service-only append-only correction for a paid FAL provider_result_http_405 or provider_result_http_413 queue-result route failure after provider completion. Confirmation is bound to the immutable latest failure code. The RPC verifies the exact uploaded MP4 and unchanged settled ledger, never resubmits or rebills, and returns the recovered task to manual human review.';

do $verify_fal_result_route_recovery$
declare
  definition_value text;
  transition_constraint_value text;
  v2_count_value integer;
  v3_count_value integer;
begin
  select replace(
    pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    ),
    E'\r\n', E'\n'
  ) into definition_value;
  select pg_get_constraintdef(constraint_row.oid, true)
    into transition_constraint_value
  from pg_constraint constraint_row
  where constraint_row.conrelid =
      'content_factory.generation_strategy_provider_status_events'::regclass
    and constraint_row.conname =
      'generation_strategy_provider_status_transition_v3_check';
  select
    count(*) filter (
      where constraint_row.conname =
        'generation_strategy_provider_status_transition_v2_check'
    )::integer,
    count(*) filter (
      where constraint_row.conname =
        'generation_strategy_provider_status_transition_v3_check'
    )::integer
    into v2_count_value, v3_count_value
  from pg_constraint constraint_row
  where constraint_row.conrelid =
      'content_factory.generation_strategy_provider_status_events'::regclass
    and constraint_row.conname in (
      'generation_strategy_provider_status_transition_v2_check',
      'generation_strategy_provider_status_transition_v3_check'
    );

  if definition_value is null
     or transition_constraint_value is null
     or v2_count_value <> 0
     or v3_count_value <> 1
     or position(
       'provider_result_http_405' in transition_constraint_value
     ) = 0
     or position(
       'provider_result_http_413' in transition_constraint_value
     ) = 0
     or position(
       'FAL_RESULT_HTTP_405_RECOVERY_VERIFIED' in definition_value
     ) = 0
     or position(
       'FAL_RESULT_HTTP_413_RECOVERY_VERIFIED' in definition_value
     ) = 0
     or position(
       $binding$latest_event_row.failure_code = 'provider_result_http_413'$binding$
       in definition_value
     ) = 0
     or position(
       $binding$(input_payload ->> 'confirmation') is not distinct from
           'FAL_RESULT_HTTP_413_RECOVERY_VERIFIED'$binding$
       in definition_value
     ) = 0
     or position(
       $job$(job_row.output ->> 'failure_code') is distinct from
       latest_event_row.failure_code$job$
       in definition_value
     ) = 0
     or position(
       $task$(task_row.result ->> 'failure_code') is distinct from
       latest_event_row.failure_code$task$
       in definition_value
     ) = 0
     or position(
       $snapshot$'recovered_failure_code', latest_event_row.failure_code$snapshot$
       in definition_value
     ) = 0
     or position(
       $canonical$(job_row.input #>> '{strategy_execution,strategy_id}')
       is distinct from receipt_row.strategy_id$canonical$
       in definition_value
     ) = 0
     or position(
       'ledger_hash_after_value is distinct from ledger_hash_before_value'
       in definition_value
     ) = 0
     or position(
       'insert into content_factory.generation_spend_ledger'
       in lower(definition_value)
     ) > 0
     or position(
       'update content_factory.generation_spend_ledger'
       in lower(definition_value)
     ) > 0
     or position(
       'delete from content_factory.generation_spend_ledger'
       in lower(definition_value)
     ) > 0
     or position(
       'update content_factory.generation_strategy_provider_status_events'
       in lower(definition_value)
     ) > 0
     or position(
       'delete from content_factory.generation_strategy_provider_status_events'
       in lower(definition_value)
     ) > 0 then
    raise exception using message =
      'provider_result_route_recovery_verify_failed';
  end if;

  if has_function_privilege(
       'authenticated',
       'public.system_recover_generation_strategy_provider_result(jsonb)',
       'execute'
     )
     or has_function_privilege(
       'anon',
       'public.system_recover_generation_strategy_provider_result(jsonb)',
       'execute'
     )
     or not has_function_privilege(
       'service_role',
       'public.system_recover_generation_strategy_provider_result(jsonb)',
       'execute'
     ) then
    raise exception using message =
      'provider_result_route_recovery_grants_changed';
  end if;
end;
$verify_fal_result_route_recovery$;

commit;
