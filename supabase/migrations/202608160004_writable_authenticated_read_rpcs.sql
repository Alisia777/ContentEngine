begin;

-- These public read projections authenticate through current_profile_id().
-- That shared guard upserts the profile's last-seen state, so PostgREST must
-- open their authenticated RPC transactions as writable.  Do not recreate the
-- functions here: ALTER FUNCTION retains their body, SECURITY DEFINER setup,
-- search path, owner, and every existing grant.
alter function public.creator_generation_strategy_asset_candidates(jsonb) volatile;
alter function public.creator_generation_strategy_repeat_data(jsonb) volatile;
alter function public.creator_project_media(jsonb) volatile;
alter function public.creator_project_members(jsonb) volatile;
alter function public.creator_project_placement(jsonb) volatile;
alter function public.contentengine_generation_video_reference_lineage(jsonb) volatile;
alter function public.creator_validate_notification_action(jsonb) volatile;
alter function public.workspace_trash_browser(jsonb) volatile;

do $writable_authenticated_read_rpcs_contract$
declare
  target record;
  procedure_oid regprocedure;
  procedure_volatility "char";
begin
  for target in
    select *
    from (
      values
        ('creator_generation_strategy_asset_candidates', false),
        ('creator_generation_strategy_repeat_data', false),
        ('creator_project_media', false),
        ('creator_project_members', false),
        ('creator_project_placement', false),
        ('contentengine_generation_video_reference_lineage', true),
        ('creator_validate_notification_action', false),
        ('workspace_trash_browser', false)
    ) as expected(function_name, service_role_execute)
  loop
    procedure_oid := to_regprocedure(
      format('%I.%I(jsonb)', 'public', target.function_name)
    );
    if procedure_oid is null then
      raise exception '%_missing', target.function_name
        using errcode = '42883';
    end if;

    select procedure.provolatile
      into procedure_volatility
    from pg_catalog.pg_proc procedure
    where procedure.oid = procedure_oid;

    if procedure_volatility is distinct from 'v' then
      raise exception '%_must_be_volatile', target.function_name;
    end if;

    -- ALTER FUNCTION above must not accidentally broaden or narrow the
    -- established browser-facing ACL.  The lineage reader intentionally
    -- remains callable by service_role; all other targets remain user-only.
    if not has_function_privilege('authenticated', procedure_oid, 'execute')
       or has_function_privilege('anon', procedure_oid, 'execute')
       or has_function_privilege(
         'service_role', procedure_oid, 'execute'
       ) is distinct from target.service_role_execute then
      raise exception '%_execute_acl_changed', target.function_name;
    end if;
  end loop;
end;
$writable_authenticated_read_rpcs_contract$;

-- PostgREST caches function volatility.  Without this reload it can retain
-- the prior STABLE metadata and still run a legitimate profile sync in a
-- read-only transaction (SQLSTATE 25006).
notify pgrst, 'reload schema';

commit;
