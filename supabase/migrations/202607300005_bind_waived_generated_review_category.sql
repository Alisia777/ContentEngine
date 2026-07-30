begin;

-- A waived operator may have created an exact paid generation before a
-- manager-populated review category existed on the product. Let the first
-- review bind only the immutable category already stored on that succeeded
-- generation job, and only when it exactly matches the submitted review.
do $bind_waived_generated_review_category$
declare
  function_signature regprocedure :=
    'content_factory_private.creator_start_content_review_legacy(jsonb)'
      ::regprocedure;
  function_definition text;
  patched_definition text;
  empty_category_guard text :=
    '  if product_category_value = '''' then';
  waived_generation_binding text := $waived_generation_binding$
  if product_category_value = ''
     and generated_media_value
     and actor_role = 'operator'
     and content_factory_private.training_access_waiver_active(
       organization_id,
       user_id
     ) then
    product_category_value := lower(btrim(coalesce(
      generation_job_row.input ->> 'product_category',
      ''
    )));
    if product_category_value in (
         'cosmetics', 'baa', 'sports_food', 'food', 'household',
         'apparel', 'electronics', 'other'
       )
       and product_category_value = lower(btrim(coalesce(
         p_payload ->> 'product_category',
         ''
       ))) then
      update content_factory.products product
      set metadata = product.metadata || jsonb_build_object(
            'content_review_category', product_category_value,
            'content_review_category_confirmed_by', user_id,
            'content_review_category_confirmed_at', now(),
            'content_review_category_ruleset', ruleset_value,
            'content_review_category_confirmation_basis',
              'audited_training_waiver_generation_job',
            'content_review_category_generation_job_id',
              generation_job_row.id
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
          'product_category', product_category_value,
          'generation_job_id', generation_job_row.id,
          'confirmation_basis',
            'audited_training_waiver_generation_job'
        ),
        'waived-review-category:' || generation_job_row.id::text
      );
    else
      product_category_value := '';
    end if;
  end if;

  if product_category_value = '' then$waived_generation_binding$;
begin
  function_definition :=
    pg_catalog.pg_get_functiondef(function_signature);
  if strpos(
       function_definition,
       'audited_training_waiver_generation_job'
     ) > 0 then
    return;
  end if;
  if strpos(
       function_definition,
       'content_factory_private.resolved_content_review_category('
     ) = 0
     or strpos(function_definition, empty_category_guard) = 0
     or strpos(
       function_definition,
       'content_review_product_category_unverified'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'waived_generated_review_category_guard_changed';
  end if;

  patched_definition := replace(
    function_definition,
    empty_category_guard,
    waived_generation_binding
  );
  if patched_definition = function_definition then
    raise exception using
      errcode = '55000',
      message = 'waived_generated_review_category_patch_failed';
  end if;
  execute patched_definition;
end;
$bind_waived_generated_review_category$;

do $verify_waived_generated_review_category$
declare
  function_definition text;
begin
  function_definition := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_start_content_review_legacy(jsonb)'
      ::regprocedure
  ));
  if strpos(
       function_definition,
       'content_factory_private.training_access_waiver_active('
     ) = 0
     or strpos(
       function_definition,
       'generation_job_row.input ->> ''product_category'''
     ) = 0
     or strpos(
       function_definition,
       'audited_training_waiver_generation_job'
     ) = 0
     or strpos(
       function_definition,
       'content_review_product_category_unverified'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'waived_generated_review_category_contract_invalid';
  end if;
end;
$verify_waived_generated_review_category$;

notify pgrst, 'reload schema';

commit;
