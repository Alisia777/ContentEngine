begin;

-- Older products can contain an empty content_review_category together with a
-- valid product_category. SQL COALESCE treats the empty string as present,
-- while the catalog correctly treats it as absent. Centralize the resolver so
-- every paid-generation and review boundary sees the same server-owned value.
create or replace function
  content_factory_private.resolved_content_review_category(
    product_metadata jsonb
  )
returns text
language sql
immutable
set search_path = ''
as $$
  select lower(btrim(coalesce(
    nullif(btrim(coalesce($1 ->> 'content_review_category', '')), ''),
    nullif(btrim(coalesce($1 ->> 'product_category', '')), ''),
    ''
  )))
$$;

revoke all on function
  content_factory_private.resolved_content_review_category(jsonb)
  from public, anon, authenticated;

do $patch_blank_review_category_fallback$
declare
  function_signature regprocedure;
  function_definition text;
  patched_definition text;
  legacy_resolver_pattern text :=
    $pattern$lower\([[:space:]]*btrim\([[:space:]]*coalesce\([[:space:]]*product_row\.metadata ->> 'content_review_category',[[:space:]]*product_row\.metadata ->> 'product_category',[[:space:]]*''[[:space:]]*\)[[:space:]]*\)[[:space:]]*\)$pattern$;
begin
  foreach function_signature in array array[
    'content_factory_private.creator_start_content_review_legacy(jsonb)'
      ::regprocedure,
    'public.creator_start_generated_video_review(jsonb)'::regprocedure,
    'public.creator_approve_generated_video_review_with_context(jsonb)'
      ::regprocedure,
    'content_factory_private.enforce_generated_image_review_input()'
      ::regprocedure,
    'content_factory_private.guard_video_review_content_approval()'
      ::regprocedure,
    'public.creator_approve_generated_photo_review_with_context(jsonb)'
      ::regprocedure,
    'content_factory_private.creator_start_real_generation_pre_guard_lineage_v8(jsonb)'
      ::regprocedure
  ]
  loop
    function_definition :=
      pg_catalog.pg_get_functiondef(function_signature);
    if strpos(
         function_definition,
         'content_factory_private.resolved_content_review_category('
       ) > 0 then
      continue;
    end if;

    patched_definition := regexp_replace(
      function_definition,
      legacy_resolver_pattern,
      'content_factory_private.resolved_content_review_category(product_row.metadata)',
      'g'
    );
    if patched_definition = function_definition then
      raise exception using
        errcode = '55000',
        message = 'blank_review_category_fallback_pattern_changed',
        detail = function_signature::text;
    end if;
    execute patched_definition;
  end loop;
end;
$patch_blank_review_category_fallback$;

do $verify_blank_review_category_fallback$
declare
  function_signature regprocedure;
  function_definition text;
begin
  foreach function_signature in array array[
    'content_factory_private.creator_start_content_review_legacy(jsonb)'
      ::regprocedure,
    'public.creator_start_generated_video_review(jsonb)'::regprocedure,
    'public.creator_approve_generated_video_review_with_context(jsonb)'
      ::regprocedure,
    'content_factory_private.enforce_generated_image_review_input()'
      ::regprocedure,
    'content_factory_private.guard_video_review_content_approval()'
      ::regprocedure,
    'public.creator_approve_generated_photo_review_with_context(jsonb)'
      ::regprocedure,
    'content_factory_private.creator_start_real_generation_pre_guard_lineage_v8(jsonb)'
      ::regprocedure
  ]
  loop
    function_definition :=
      lower(pg_catalog.pg_get_functiondef(function_signature));
    if strpos(
         function_definition,
         'content_factory_private.resolved_content_review_category('
       ) = 0 then
      raise exception using
        errcode = '55000',
        message = 'blank_review_category_fallback_contract_invalid',
        detail = function_signature::text;
    end if;
  end loop;
end;
$verify_blank_review_category_fallback$;

notify pgrst, 'reload schema';

commit;
