begin;

-- Review autostart consent belongs to the outer v12 wrapper. It must remain
-- available there for validation and durable binding, but the older paid
-- generation command has a strict payload allowlist and must never receive
-- these wrapper-only keys.
do $patch_review_consent_delegation$
declare
  function_signature regprocedure :=
    'content_factory_private.creator_start_real_generation_pre_flexible_duration_v12(jsonb)'::regprocedure;
  function_definition text;
  patched_definition text;
  legacy_call text :=
    '.creator_start_real_generation_pre_review_autostart_v11(p_payload);';
  safe_call text :=
    '.creator_start_real_generation_pre_review_autostart_v11(
      p_payload - array[
        ''review_autostart_confirmed'',
        ''review_autostart_terms_version''
      ]::text[]
    );';
begin
  function_definition := pg_catalog.pg_get_functiondef(function_signature);
  if strpos(
       function_definition,
       '''review_autostart_confirmed'',
        ''review_autostart_terms_version'''
     ) > 0 then
    return;
  end if;

  patched_definition := replace(
    function_definition,
    legacy_call,
    safe_call
  );
  if patched_definition = function_definition then
    raise exception using
      errcode = '55000',
      message = 'generation_review_consent_delegation_patch_failed';
  end if;
  execute patched_definition;
end;
$patch_review_consent_delegation$;

do $verify_review_consent_delegation$
declare
  function_definition text := pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_flexible_duration_v12(jsonb)'::regprocedure
  );
begin
  if strpos(
       function_definition,
       '''review_autostart_confirmed'',
        ''review_autostart_terms_version'''
     ) = 0
     or strpos(
       function_definition,
       'creator_start_real_generation_pre_review_autostart_v11'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'generation_review_consent_delegation_contract_invalid';
  end if;
end;
$verify_review_consent_delegation$;

notify pgrst, 'reload schema';

commit;
