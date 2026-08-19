begin;

-- Strategy paid start: generation_batches model check must accept strategy
-- recipes.  system_claim_generation_strategy_start inserts a real batch with
-- model = receipt.recipe ('product_ugc' | 'product_swap' | 'product_ad'), but
-- generation_batches_model_v48_check (202608130002) only allowed mock and
-- catalog models, so every paid strategy claim failed with 23514 before any
-- claim/job/spend row was written.  generation_jobs already carries the
-- strategy arm in generation_jobs_spend_contract_v48_check (202608130007);
-- this migration adds the matching arm for batches and nothing else.

alter table content_factory.generation_batches
  drop constraint generation_batches_model_v48_check;

alter table content_factory.generation_batches
  add constraint generation_batches_model_v48_check check (
    (provider = 'mock' and model = 'mock')
    or content_factory_private.generation_catalog_entry(provider, model)
      is not null
    or (
      provider = 'runway'
      and model = any (array['product_ugc', 'product_swap', 'product_ad'])
    )
  );

do $generation_batches_strategy_recipe_verify$
declare
  constraint_def_value text;
begin
  select pg_get_constraintdef(oid) into constraint_def_value
  from pg_constraint
  where conrelid = 'content_factory.generation_batches'::regclass
    and conname = 'generation_batches_model_v48_check';
  if constraint_def_value is null
     or constraint_def_value not like '%product_swap%'
     or constraint_def_value not like '%generation_catalog_entry%'
     or constraint_def_value not like '%mock%' then
    raise exception using errcode = 'P0001',
      message = 'generation_batches_strategy_recipe_check_invalid';
  end if;
end;
$generation_batches_strategy_recipe_verify$;

commit;
