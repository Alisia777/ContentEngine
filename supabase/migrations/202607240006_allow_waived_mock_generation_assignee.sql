begin;

-- Training waivers intentionally open the production workspace without
-- fabricating exam records. The mock-batch RPC had one additional, older
-- assignee check that still required a physical exam certification and made
-- the otherwise valid waiver unusable at the final submit step.
do $allow_waived_mock_generation_assignee$
declare
  function_body text;
  patched_body text;
  exam_guard text := $exam_guard$
      and exists (
        select 1
        from content_factory.training_certifications certification
        join content_factory.training_modules module
          on module.code = certification.module_code
         and module.module_type = 'exam'
         and module.is_active
        where certification.organization_id = membership.organization_id
          and certification.profile_id = membership.profile_id
          and certification.status = 'passed'
          and (certification.expires_at is null or certification.expires_at > now())
      )
$exam_guard$;
  waiver_or_exam_guard text := $waiver_or_exam_guard$
      and (
        content_factory_private.training_access_waiver_active(
          membership.organization_id,
          membership.profile_id
        )
        or exists (
          select 1
          from content_factory.training_certifications certification
          join content_factory.training_modules module
            on module.code = certification.module_code
           and module.module_type = 'exam'
           and module.is_active
          where certification.organization_id = membership.organization_id
            and certification.profile_id = membership.profile_id
            and certification.status = 'passed'
            and (certification.expires_at is null or certification.expires_at > now())
        )
      )
$waiver_or_exam_guard$;
begin
  select procedure.prosrc
    into function_body
  from pg_proc procedure
  join pg_namespace namespace
    on namespace.oid = procedure.pronamespace
  where namespace.nspname = 'public'
    and procedure.proname = 'creator_create_mock_batch'
    and pg_get_function_identity_arguments(procedure.oid) = 'p_payload jsonb';

  if function_body is null then
    raise exception 'creator_create_mock_batch_missing';
  end if;
  if strpos(function_body, exam_guard) = 0 then
    raise exception 'creator_create_mock_batch_exam_guard_changed';
  end if;
  if strpos(
    function_body,
    'content_factory_private.training_access_waiver_active('
  ) > 0 then
    raise exception 'creator_create_mock_batch_waiver_guard_already_present';
  end if;

  patched_body := replace(function_body, exam_guard, waiver_or_exam_guard);
  if patched_body = function_body
     or strpos(
       patched_body,
       'content_factory_private.training_access_waiver_active('
     ) = 0 then
    raise exception 'creator_create_mock_batch_waiver_patch_failed';
  end if;

  execute format(
    $function$
      create or replace function public.creator_create_mock_batch(
        p_payload jsonb default '{}'::jsonb
      )
      returns jsonb
      language plpgsql
      security definer
      set search_path = ''
      as %L
    $function$,
    patched_body
  );
end;
$allow_waived_mock_generation_assignee$;

do $allow_waived_mock_generation_assignee_contract$
declare
  function_definition text;
begin
  select lower(pg_get_functiondef(
    'public.creator_create_mock_batch(jsonb)'::regprocedure
  )) into function_definition;

  if function_definition is null
     or strpos(
       function_definition,
       'content_factory_private.training_access_waiver_active('
     ) = 0
     or strpos(function_definition, 'certified_assignee_required') = 0
     or strpos(function_definition, 'mock_only_required') = 0 then
    raise exception 'creator_create_mock_batch_waiver_contract_invalid';
  end if;

  if not has_function_privilege(
    'authenticated',
    'public.creator_create_mock_batch(jsonb)',
    'EXECUTE'
  ) then
    raise exception 'creator_create_mock_batch_browser_privilege_missing';
  end if;
end;
$allow_waived_mock_generation_assignee_contract$;

commit;
