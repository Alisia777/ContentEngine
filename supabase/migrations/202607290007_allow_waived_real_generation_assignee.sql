begin;

-- A workspace_generation waiver is the audited alternative to training
-- certification. Keep every membership, role and spend guard intact while
-- allowing a waived active member to be the assignee of a real generation.
do $allow_waived_real_generation_assignee$
declare
  function_signature regprocedure;
  function_definition text;
  patched_definition text;
  exam_guard text := $exam_guard$
      and exists (
        select 1
        from content_factory.training_certifications certification
        where certification.organization_id = membership.organization_id
          and certification.profile_id = membership.profile_id
          and certification.module_code = 'operator_final_exam'
          and certification.status = 'passed'
          and (
            certification.expires_at is null
            or certification.expires_at > now()
          )
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
          where certification.organization_id = membership.organization_id
            and certification.profile_id = membership.profile_id
            and certification.module_code = 'operator_final_exam'
            and certification.status = 'passed'
            and (
              certification.expires_at is null
              or certification.expires_at > now()
            )
        )
      )
$waiver_or_exam_guard$;
begin
  foreach function_signature in array array[
    'content_factory_private.creator_start_gen4_turbo_5s(jsonb)'::regprocedure,
    'content_factory_private.creator_start_seedance2_fast_8s(jsonb)'::regprocedure
  ]
  loop
    function_definition := pg_catalog.pg_get_functiondef(function_signature);
    if strpos(
         function_definition,
         'content_factory_private.training_access_waiver_active('
       ) > 0 then
      continue;
    end if;
    if strpos(function_definition, exam_guard) = 0 then
      raise exception using
        errcode = '55000',
        message = 'real_generation_assignee_exam_guard_changed';
    end if;

    patched_definition := replace(
      function_definition,
      exam_guard,
      waiver_or_exam_guard
    );
    if patched_definition = function_definition
       or strpos(
         patched_definition,
         'content_factory_private.training_access_waiver_active('
       ) = 0 then
      raise exception using
        errcode = '55000',
        message = 'real_generation_assignee_waiver_patch_failed';
    end if;
    execute patched_definition;
  end loop;
end;
$allow_waived_real_generation_assignee$;

do $verify_waived_real_generation_assignee$
declare
  function_signature regprocedure;
  function_definition text;
begin
  foreach function_signature in array array[
    'content_factory_private.creator_start_gen4_turbo_5s(jsonb)'::regprocedure,
    'content_factory_private.creator_start_seedance2_fast_8s(jsonb)'::regprocedure
  ]
  loop
    function_definition := pg_catalog.pg_get_functiondef(function_signature);
    if strpos(
         function_definition,
         'content_factory_private.training_access_waiver_active('
       ) = 0
       or strpos(function_definition, 'certified_assignee_required') = 0
       or strpos(function_definition, 'real_generation_spend_confirmation_required') = 0
       or strpos(function_definition, 'payout_role_not_allowed') = 0 then
      raise exception using
        errcode = '55000',
        message = 'real_generation_assignee_waiver_contract_invalid';
    end if;
  end loop;
end;
$verify_waived_real_generation_assignee$;

commit;
