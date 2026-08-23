begin;

-- A paid generated-video launch can predate a manager-confirmed product
-- category: the product metadata stays {} while the immutable paid job input
-- already carries the allowlist-validated product_category from the paid
-- start. Review start then dead-ends on
-- generated_video_review_category_required forever. Bind the category from
-- that immutable job input once at review start, writing it into product
-- metadata so the approve path's product-metadata consistency check keeps
-- holding without changes. Jobs with no category anywhere keep the existing
-- explicit raise.
do $patch_generated_video_review_category_fallback$
declare
  function_signature regprocedure :=
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'
      ::regprocedure;
  function_definition text;
  patched_definition text;
  resolver_assignment text :=
    'category_value := content_factory_private.resolved_content_review_category(product_row.metadata);';
  generation_input_binding text := $generation_input_binding$category_value := content_factory_private.resolved_content_review_category(product_row.metadata);
  if category_value = '' then
    category_value := lower(btrim(coalesce(
      job_row.input ->> 'product_category',
      ''
    )));
    if category_value in (
         'cosmetics', 'baa', 'sports_food', 'food', 'household',
         'apparel', 'electronics', 'other'
       ) then
      update content_factory.products product
      set metadata = product.metadata || jsonb_build_object(
            'content_review_category', category_value,
            'content_review_category_confirmed_by', user_id,
            'content_review_category_confirmed_at', now(),
            'content_review_category_ruleset',
              'ru-content-compliance-2026-07-16.1',
            'content_review_category_confirmation_basis',
              'paid_generation_job_input',
            'content_review_category_generation_job_id', job_row.id
          ),
          updated_at = now()
      where product.organization_id = organization_id
        and product.id = product_row.id
      returning * into product_row;

      perform content_factory_private.emit_event(
        organization_id,
        user_id,
        'content_review_category_bound_from_generation',
        'product',
        product_row.id::text,
        jsonb_build_object(
          'product_category', category_value,
          'generation_job_id', job_row.id,
          'confirmation_basis', 'paid_generation_job_input'
        ),
        'generation-input-review-category:' || job_row.id::text
      );
    else
      category_value := '';
    end if;
  end if;$generation_input_binding$;
begin
  function_definition :=
    pg_catalog.pg_get_functiondef(function_signature);
  if strpos(function_definition, 'paid_generation_job_input') > 0 then
    return;
  end if;
  if strpos(function_definition, resolver_assignment) = 0
     or strpos(
       function_definition,
       'generated_video_review_category_required'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'generated_video_review_category_fallback_pattern_changed';
  end if;

  patched_definition := replace(
    function_definition,
    resolver_assignment,
    generation_input_binding
  );
  if patched_definition = function_definition then
    raise exception using
      errcode = '55000',
      message = 'generated_video_review_category_fallback_patch_failed';
  end if;
  execute patched_definition;
end;
$patch_generated_video_review_category_fallback$;

do $verify_generated_video_review_category_fallback$
declare
  function_definition text;
  approve_definition text;
begin
  function_definition := pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'
      ::regprocedure
  );
  if strpos(function_definition, 'paid_generation_job_input') = 0
     or strpos(
       function_definition,
       'job_row.input ->> ''product_category'''
     ) = 0
     or strpos(
       function_definition,
       'content_review_category_bound_from_generation'
     ) = 0
     or strpos(
       function_definition,
       'generated_video_review_category_required'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'generated_video_review_category_fallback_contract_invalid';
  end if;

  approve_definition := pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'
      ::regprocedure
  );
  if strpos(
       approve_definition,
       'resolved_content_review_category'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'generated_video_review_category_fallback_contract_invalid';
  end if;
end;
$verify_generated_video_review_category_fallback$;

notify pgrst, 'reload schema';

commit;
