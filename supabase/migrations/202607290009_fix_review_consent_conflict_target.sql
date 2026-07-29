begin;

-- This wrapper also uses #variable_conflict use_variable. Bind its idempotent
-- insert to a named constraint so organization_id cannot be interpreted as a
-- PL/pgSQL variable during ON CONFLICT inference.
do $stabilize_review_consent_constraint$
declare
  stable_constraint_name constant text :=
    'generation_review_autostart_consents_org_job_uq';
  current_constraint_name text;
begin
  select constraint_row.conname
    into current_constraint_name
  from pg_constraint constraint_row
  where constraint_row.conrelid =
          'content_factory.generation_review_autostart_consents'::regclass
    and constraint_row.contype = 'u'
    and pg_catalog.pg_get_constraintdef(constraint_row.oid)
          = 'UNIQUE (organization_id, generation_job_id)'
  order by
    (constraint_row.conname = stable_constraint_name) desc,
    constraint_row.conname
  limit 1;

  if current_constraint_name is null then
    alter table content_factory.generation_review_autostart_consents
      add constraint generation_review_autostart_consents_org_job_uq
      unique (organization_id, generation_job_id);
  elsif current_constraint_name <> stable_constraint_name
        and not exists (
          select 1
          from pg_constraint constraint_row
          where constraint_row.conrelid =
                  'content_factory.generation_review_autostart_consents'::regclass
            and constraint_row.conname = stable_constraint_name
        ) then
    execute format(
      'alter table content_factory.generation_review_autostart_consents rename constraint %I to %I',
      current_constraint_name,
      stable_constraint_name
    );
  end if;
end;
$stabilize_review_consent_constraint$;

do $patch_review_consent_conflict_target$
declare
  function_signature regprocedure :=
    'content_factory_private.creator_start_real_generation_pre_flexible_duration_v12(jsonb)'::regprocedure;
  function_definition text;
  patched_definition text;
begin
  function_definition := pg_catalog.pg_get_functiondef(function_signature);
  if strpos(
       function_definition,
       'on conflict on constraint generation_review_autostart_consents_org_job_uq'
     ) > 0 then
    return;
  end if;

  patched_definition := replace(
    function_definition,
    'on conflict (organization_id, generation_job_id) do nothing;',
    'on conflict on constraint generation_review_autostart_consents_org_job_uq do nothing;'
  );
  if patched_definition = function_definition then
    raise exception using
      errcode = '55000',
      message = 'generation_review_consent_conflict_patch_failed';
  end if;
  execute patched_definition;
end;
$patch_review_consent_conflict_target$;

do $verify_review_consent_conflict_target$
begin
  if not exists (
       select 1
       from pg_constraint constraint_row
       where constraint_row.conrelid =
               'content_factory.generation_review_autostart_consents'::regclass
         and constraint_row.contype = 'u'
         and constraint_row.conname =
               'generation_review_autostart_consents_org_job_uq'
         and pg_catalog.pg_get_constraintdef(constraint_row.oid)
               = 'UNIQUE (organization_id, generation_job_id)'
     )
     or strpos(
       pg_catalog.pg_get_functiondef(
         'content_factory_private.creator_start_real_generation_pre_flexible_duration_v12(jsonb)'::regprocedure
       ),
       'on conflict on constraint generation_review_autostart_consents_org_job_uq'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'generation_review_consent_conflict_contract_invalid';
  end if;
end;
$verify_review_consent_conflict_target$;

commit;
