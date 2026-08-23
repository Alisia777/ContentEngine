begin;

-- 202608200006_generation_strategy_fal_result_recovery_input_shape_v1
--
-- 200005 correctly made the paid FAL 405 correction append-only, but its
-- strategy identity guard read a non-canonical top-level input key.  Real paid
-- strategy jobs store strategy_id inside strategy_execution; provider and
-- strategy_recipe remain top-level.  Patch exactly that one guard in the
-- already-installed RPC.  No event, job, ledger or provider state is touched.

do $patch_fal_result_recovery_strategy_input$
declare
  definition_value text;
  patched_value text;
  search_value text := $search$     or (job_row.input ->> 'strategy_id') is distinct from
       'viral_product_swap'$search$;
  replacement_value text := $replacement$     or (job_row.input #>> '{strategy_execution,strategy_id}')
       is distinct from receipt_row.strategy_id$replacement$;
  hit_count_value integer;
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
      'provider_result_recovery_rpc_missing';
  end if;

  if position(replacement_value in definition_value) > 0
     and position(search_value in definition_value) = 0 then
    return;
  end if;

  hit_count_value := (
    length(definition_value)
    - length(replace(definition_value, search_value, ''))
  ) / length(search_value);
  if hit_count_value <> 1 then
    raise exception using message =
      'provider_result_recovery_strategy_guard_anchor_invalid:' ||
      hit_count_value::text;
  end if;

  patched_value := replace(
    definition_value, search_value, replacement_value
  );
  if position(search_value in patched_value) > 0
     or position(replacement_value in patched_value) = 0 then
    raise exception using message =
      'provider_result_recovery_strategy_guard_patch_failed';
  end if;
  execute patched_value;
end;
$patch_fal_result_recovery_strategy_input$;

comment on function
  public.system_recover_generation_strategy_provider_result(jsonb) is
  'Service-only append-only correction for one paid FAL provider_result_http_405 after provider completion. Canonical strategy identity is read from strategy_execution.strategy_id and tied to the readiness receipt. The RPC never resubmits or rebills and returns the recovered task to manual human review.';

do $verify_fal_result_recovery_strategy_input$
declare
  definition_value text;
begin
  select replace(
    pg_get_functiondef(
      'public.system_recover_generation_strategy_provider_result(jsonb)'
        ::regprocedure
    ),
    E'\r\n', E'\n'
  ) into definition_value;

  if definition_value is null
     or position(
       $guard$(job_row.input #>> '{strategy_execution,strategy_id}')
       is distinct from receipt_row.strategy_id$guard$
       in definition_value
     ) = 0
     or position(
       $stale$(job_row.input ->> 'strategy_id') is distinct from$stale$
       in definition_value
     ) > 0
     or position(
       $provider$(job_row.input ->> 'provider') is distinct from 'fal'$provider$
       in definition_value
     ) = 0
     or position(
       $recipe$(job_row.input ->> 'strategy_recipe') is distinct from 'product_swap'$recipe$
       in definition_value
     ) = 0
     or position(
       $version$(job_row.input #>> '{strategy_execution,version}') is distinct from$version$
       in definition_value
     ) = 0
     or position(
       'generation-strategy-provider-result-recovery-response-v1'
       in definition_value
     ) = 0
     or position(
       'ledger_hash_after_value is distinct from ledger_hash_before_value'
       in definition_value
     ) = 0 then
    raise exception using message =
      'provider_result_recovery_strategy_guard_verify_failed';
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
      'provider_result_recovery_strategy_guard_grants_changed';
  end if;
end;
$verify_fal_result_recovery_strategy_input$;

commit;
