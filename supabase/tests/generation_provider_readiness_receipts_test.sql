begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(15);

select ok(
  to_regclass(
    'content_factory.generation_provider_readiness_receipts'
  ) is not null,
  'provider readiness receipts exist'
);

select ok(
  (
    select table_row.relrowsecurity
    from pg_class table_row
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname =
        'generation_provider_readiness_receipts'
  ),
  'provider readiness receipts keep RLS enabled'
);

select is(
  has_table_privilege(
    'authenticated',
    'content_factory.generation_provider_readiness_receipts',
    'select'
  ),
  false,
  'browser users cannot read provider receipts directly'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    join pg_class table_row on table_row.oid = trigger_row.tgrelid
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname =
        'generation_provider_readiness_receipts'
      and trigger_row.tgname =
        'generation_provider_readiness_receipt_append_only'
      and not trigger_row.tgisinternal
  ),
  'provider readiness receipts are append-only'
);

select ok(
  to_regprocedure(
    'public.system_record_generation_provider_readiness(jsonb)'
  ) is not null,
  'the trusted recorder exists'
);

select ok(
  exists (
    select 1
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname =
        'system_record_generation_provider_readiness'
      and function_row.prosecdef
  ),
  'the trusted recorder is SECURITY DEFINER'
);

select is(
  has_function_privilege(
    'authenticated',
    'public.system_record_generation_provider_readiness(jsonb)',
    'execute'
  ),
  false,
  'authenticated browser clients cannot write receipts'
);

select is(
  has_function_privilege(
    'service_role',
    'public.system_record_generation_provider_readiness(jsonb)',
    'execute'
  ),
  true,
  'only the trusted Edge service can record receipts'
);

select ok(
  to_regprocedure(
    'content_factory_private.generation_provider_readiness(uuid,timestamp with time zone)'
  ) is not null,
  'the bounded latest-receipt reader exists'
);

select is(
  jsonb_array_length(
    content_factory_private.generation_provider_readiness(
      'fa000000-0000-4000-8000-000000000001',
      '2026-07-28T12:00:00Z'::timestamptz
    )
  ),
  3,
  'the latest-receipt reader always returns the three production SKUs'
);

select is(
  (
    select count(*)::integer
    from jsonb_array_elements(
      content_factory_private.generation_provider_readiness(
        'fa000000-0000-4000-8000-000000000001',
        '2026-07-28T12:00:00Z'::timestamptz
      )
    ) item
    where item ->> 'status' = 'unknown'
      and item ->> 'reason_code' =
        'provider_readiness_receipt_missing'
      and item -> 'ready' = 'false'::jsonb
      and item -> 'fresh' = 'false'::jsonb
  ),
  3,
  'missing receipts fail closed for every production SKU'
);

select is(
  (
    select jsonb_agg(item ->> 'model' order by ordinal)
    from jsonb_array_elements(
      content_factory_private.generation_provider_readiness(
        'fa000000-0000-4000-8000-000000000001',
        '2026-07-28T12:00:00Z'::timestamptz
      )
    ) with ordinality rows(item, ordinal)
  ),
  '["seedream5_lite", "gen4_turbo", "seedance2_fast"]'::jsonb,
  'receipt order matches the production generation selector'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_generation_spend_overview_pre_provider_readiness_v1(jsonb)'
  ) is not null,
  'the original membership-scoped spend overview remains private'
);

select ok(
  exists (
    select 1
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname =
        'creator_generation_spend_overview'
      and function_row.prosecdef
  ),
  'the final spend overview remains SECURITY DEFINER'
);

select like(
  pg_get_functiondef(
    'public.creator_generation_spend_overview(jsonb)'::regprocedure
  ),
  '%provider_readiness%',
  'the membership-scoped spend overview includes safe readiness receipts'
);

select * from finish();
rollback;
