begin;

-- The policy-snapshot wrapper uses #variable_conflict use_variable. Bare
-- column names in ON CONFLICT can therefore resolve as PL/pgSQL variables and
-- fail constraint inference. Give the existing composite key a stable name
-- and target that constraint directly.
do $stabilize_learning_policy_snapshot_constraint$
declare
  stable_constraint_name constant text :=
    'generation_learning_policy_snapshots_scope_uq';
  current_constraint_name text;
begin
  select constraint_row.conname
    into current_constraint_name
  from pg_constraint constraint_row
  where constraint_row.conrelid =
          'content_factory.generation_learning_policy_snapshots'::regclass
    and constraint_row.contype = 'u'
    and pg_catalog.pg_get_constraintdef(constraint_row.oid) =
          'UNIQUE (organization_id, product_id, platform, model, policy_hash)'
  order by
    (constraint_row.conname = stable_constraint_name) desc,
    constraint_row.conname
  limit 1;

  if current_constraint_name is null then
    alter table content_factory.generation_learning_policy_snapshots
      add constraint generation_learning_policy_snapshots_scope_uq
      unique (organization_id, product_id, platform, model, policy_hash);
  elsif current_constraint_name <> stable_constraint_name
        and not exists (
          select 1
          from pg_constraint constraint_row
          where constraint_row.conrelid =
                  'content_factory.generation_learning_policy_snapshots'::regclass
            and constraint_row.conname = stable_constraint_name
        ) then
    execute format(
      'alter table content_factory.generation_learning_policy_snapshots rename constraint %I to %I',
      current_constraint_name,
      stable_constraint_name
    );
  end if;
end;
$stabilize_learning_policy_snapshot_constraint$;

do $patch_learning_policy_snapshot_conflict_target$
declare
  function_signature regprocedure :=
    'content_factory_private.creator_start_real_generation_pre_mode_prompt_v10(jsonb)'::regprocedure;
  function_definition text;
  patched_definition text;
begin
  function_definition := pg_catalog.pg_get_functiondef(function_signature);
  if strpos(
       function_definition,
       'on conflict on constraint generation_learning_policy_snapshots_scope_uq'
     ) > 0 then
    return;
  end if;

  patched_definition := replace(
    function_definition,
    'on conflict (
    organization_id,
    product_id,
    platform,
    model,
    policy_hash
  ) do nothing;',
    'on conflict on constraint generation_learning_policy_snapshots_scope_uq do nothing;'
  );
  if patched_definition = function_definition then
    raise exception using
      errcode = '55000',
      message = 'generation_learning_policy_snapshot_conflict_patch_failed';
  end if;
  execute patched_definition;
end;
$patch_learning_policy_snapshot_conflict_target$;

do $verify_learning_policy_snapshot_conflict_target$
begin
  if not exists (
       select 1
       from pg_constraint constraint_row
       where constraint_row.conrelid =
               'content_factory.generation_learning_policy_snapshots'::regclass
         and constraint_row.contype = 'u'
         and constraint_row.conname =
               'generation_learning_policy_snapshots_scope_uq'
         and pg_catalog.pg_get_constraintdef(constraint_row.oid) =
               'UNIQUE (organization_id, product_id, platform, model, policy_hash)'
     )
     or strpos(
       pg_catalog.pg_get_functiondef(
         'content_factory_private.creator_start_real_generation_pre_mode_prompt_v10(jsonb)'::regprocedure
       ),
       'on conflict on constraint generation_learning_policy_snapshots_scope_uq'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'generation_learning_policy_snapshot_conflict_contract_invalid';
  end if;
end;
$verify_learning_policy_snapshot_conflict_target$;

notify pgrst, 'reload schema';

commit;
