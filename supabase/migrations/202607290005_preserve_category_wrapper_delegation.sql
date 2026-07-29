begin;

-- The category wrapper is newer than the flexible-duration single-reference
-- implementation. Keep product_category available to the multi-reference
-- guard, but remove that wrapper-only key from the legacy payload it
-- delegates. The outer category wrapper already snapshots the category on the
-- created job and exposes it through a transaction-local setting to every
-- nested learning check.
do $patch_multi_reference_category_delegation$
declare
  function_signature regprocedure :=
    'content_factory_private.creator_start_real_generation_pre_category_learning_v14(jsonb)'::regprocedure;
  function_definition text;
  patched_definition text;
begin
  function_definition := pg_catalog.pg_get_functiondef(function_signature);
  if strpos(
       function_definition,
       'primary_payload := jsonb_set(
    p_payload - ''product_category'','
     ) > 0 then
    return;
  end if;

  patched_definition := replace(
    function_definition,
    'primary_payload := jsonb_set(
    p_payload,',
    'primary_payload := jsonb_set(
    p_payload - ''product_category'','
  );
  if patched_definition = function_definition then
    raise exception using
      errcode = '55000',
      message = 'generation_category_delegation_patch_failed';
  end if;
  execute patched_definition;
end;
$patch_multi_reference_category_delegation$;

do $verify_multi_reference_category_delegation$
declare
  function_definition text := pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_category_learning_v14(jsonb)'::regprocedure
  );
begin
  if strpos(
       function_definition,
       'primary_payload := jsonb_set(
    p_payload - ''product_category'','
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'generation_category_delegation_contract_invalid';
  end if;
end;
$verify_multi_reference_category_delegation$;

commit;
