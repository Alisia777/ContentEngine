begin;

-- Content review still has a legacy operator-only exam guard behind the
-- durable-evidence and repair-lineage wrappers. A workspace_generation waiver
-- is the audited alternative to that exam everywhere else in the workspace,
-- so apply the same narrow rule here without weakening membership or role
-- checks for any other user.
do $allow_waived_content_review_operator$
declare
  function_signature regprocedure :=
    'content_factory_private.creator_start_content_review_legacy(jsonb)'
      ::regprocedure;
  function_definition text;
  patched_definition text;
  exam_guard_start text :=
    '  if actor_role = ''operator'' and not exists (';
  waiver_or_exam_guard_start text := $waiver_or_exam_guard_start$
  if actor_role = 'operator'
     and not content_factory_private.training_access_waiver_active(
       organization_id,
       user_id
     )
     and not exists ($waiver_or_exam_guard_start$;
begin
  function_definition :=
    pg_catalog.pg_get_functiondef(function_signature);

  if strpos(
       function_definition,
       'content_factory_private.training_access_waiver_active('
     ) > 0 then
    return;
  end if;
  if strpos(function_definition, exam_guard_start) = 0
     or strpos(
       function_definition,
       'content_review_certification_required'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'content_review_operator_exam_guard_changed';
  end if;

  patched_definition := replace(
    function_definition,
    exam_guard_start,
    waiver_or_exam_guard_start
  );
  if patched_definition = function_definition
     or strpos(
       patched_definition,
       'content_factory_private.training_access_waiver_active('
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'content_review_operator_waiver_patch_failed';
  end if;

  execute patched_definition;
end;
$allow_waived_content_review_operator$;

do $verify_waived_content_review_operator$
declare
  legacy_definition text;
  durable_wrapper_definition text;
  public_wrapper_definition text;
begin
  legacy_definition := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_start_content_review_legacy(jsonb)'
      ::regprocedure
  ));
  durable_wrapper_definition := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_start_content_review_pre_repair_lineage_v1(jsonb)'
      ::regprocedure
  ));
  public_wrapper_definition := lower(pg_catalog.pg_get_functiondef(
    'public.creator_start_content_review(jsonb)'::regprocedure
  ));

  if strpos(
       legacy_definition,
       'content_factory_private.training_access_waiver_active('
     ) = 0
     or strpos(
       legacy_definition,
       'certification.module_code = ''operator_final_exam'''
     ) = 0
     or strpos(
       legacy_definition,
       'content_review_certification_required'
     ) = 0
     or strpos(
       durable_wrapper_definition,
       'creator_start_content_review_legacy'
     ) = 0
     or strpos(
       public_wrapper_definition,
       'creator_start_content_review_pre_repair_lineage_v1'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'content_review_operator_waiver_contract_invalid';
  end if;
end;
$verify_waived_content_review_operator$;

notify pgrst, 'reload schema';

commit;
