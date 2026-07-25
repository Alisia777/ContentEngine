begin;

-- Both functions use "#variable_conflict use_variable". Their original
-- column-list ON CONFLICT targets therefore resolve organization_id as the
-- PL/pgSQL variable instead of the table column, so PostgreSQL cannot infer
-- the matching unique index. Bind each upsert to an explicitly named
-- constraint without changing any surrounding authorization or validation.
do $named_constraints$
begin
  if not exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.training_walkthrough_progress'::regclass
      and constraint_row.conname =
        'training_walkthrough_progress_owner_module_walkthrough_uq'
  ) then
    alter table content_factory.training_walkthrough_progress
      add constraint
        training_walkthrough_progress_owner_module_walkthrough_uq
      unique (
        organization_id,
        profile_id,
        module_code,
        walkthrough_id
      );
  end if;

  if not exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.generation_creative_signals'::regclass
      and constraint_row.conname =
        'generation_creative_signals_org_job_uq'
  ) then
    alter table content_factory.generation_creative_signals
      add constraint generation_creative_signals_org_job_uq
      unique (organization_id, generation_job_id);
  end if;
end;
$named_constraints$;

do $repair_conflict_targets$
declare
  function_definition text;
  repaired_definition text;
begin
  select pg_get_functiondef(
    'public.creator_submit_platform_simulator(jsonb)'::regprocedure
  ) into function_definition;

  repaired_definition := regexp_replace(
    function_definition,
    'on[[:space:]]+conflict[[:space:]]*\([[:space:]]*organization_id[[:space:]]*,[[:space:]]*profile_id[[:space:]]*,[[:space:]]*module_code[[:space:]]*,[[:space:]]*walkthrough_id[[:space:]]*\)',
    'on conflict on constraint training_walkthrough_progress_owner_module_walkthrough_uq',
    'i'
  );
  if repaired_definition = function_definition then
    raise exception using
      errcode = '55000',
      message = 'platform_simulator_conflict_target_not_found';
  end if;
  execute repaired_definition;

  select pg_get_functiondef(
    'public.creator_start_real_generation(jsonb)'::regprocedure
  ) into function_definition;

  repaired_definition := regexp_replace(
    function_definition,
    'on[[:space:]]+conflict[[:space:]]*\([[:space:]]*organization_id[[:space:]]*,[[:space:]]*generation_job_id[[:space:]]*\)',
    'on conflict on constraint generation_creative_signals_org_job_uq',
    'i'
  );
  if repaired_definition = function_definition then
    raise exception using
      errcode = '55000',
      message = 'generation_learning_conflict_target_not_found';
  end if;
  execute repaired_definition;
end;
$repair_conflict_targets$;

do $conflict_target_contract$
declare
  platform_definition text;
  generation_definition text;
begin
  select lower(pg_get_functiondef(
    'public.creator_submit_platform_simulator(jsonb)'::regprocedure
  )) into platform_definition;
  select lower(pg_get_functiondef(
    'public.creator_start_real_generation(jsonb)'::regprocedure
  )) into generation_definition;

  if strpos(
       platform_definition,
       'on conflict on constraint training_walkthrough_progress_owner_module_walkthrough_uq'
     ) = 0
     or strpos(
       generation_definition,
       'on conflict on constraint generation_creative_signals_org_job_uq'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'conflict_target_repair_contract_failed';
  end if;
end;
$conflict_target_contract$;

commit;
