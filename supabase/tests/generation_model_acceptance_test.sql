begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(15);

select ok(
  to_regprocedure(
    'public.creator_generation_model_acceptance(jsonb)'
  ) is not null,
  'authenticated model-acceptance RPC exists'
);

select ok(
  to_regprocedure(
    'content_factory_private.generation_model_acceptance(uuid)'
  ) is not null,
  'private acceptance resolver exists'
);

select ok(
  to_regprocedure(
    'content_factory_private.generation_model_acceptance_pending(uuid)'
  ) is not null,
  'private pending-review resolver exists'
);

select ok(
  (
    select function_row.prosecdef
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname =
        'creator_generation_model_acceptance'
  ),
  'public resolver is SECURITY DEFINER'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_generation_model_acceptance(jsonb)',
    'execute'
  ),
  'authenticated members may read acceptance'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_generation_model_acceptance(jsonb)',
    'execute'
  ),
  'anonymous callers cannot read acceptance'
);

select ok(
  not has_function_privilege(
    'service_role',
    'content_factory_private.generation_model_acceptance(uuid)',
    'execute'
  ),
  'the private evidence resolver is not an application endpoint'
);

select ok(
  not has_function_privilege(
    'service_role',
    'content_factory_private.generation_model_acceptance_pending(uuid)',
    'execute'
  ),
  'the private pending-review resolver is not an application endpoint'
);

select is(
  content_factory_private.generation_model_acceptance(
    '00000000-0000-4000-8000-000000000090'::uuid
  ) ->> 'version',
  'generation-model-acceptance-v1',
  'resolver returns its explicit contract version'
);

select is(
  content_factory_private.generation_model_acceptance(
    '00000000-0000-4000-8000-000000000090'::uuid
  ) ->> 'all_models_accepted',
  'false',
  'an organization without evidence fails closed'
);

select is(
  content_factory_private.generation_model_acceptance(
    '00000000-0000-4000-8000-000000000090'::uuid
  ) #>> '{models,0,model}',
  'seedream5_lite',
  'photo model is returned first'
);

select is(
  content_factory_private.generation_model_acceptance(
    '00000000-0000-4000-8000-000000000090'::uuid
  ) #>> '{models,1,model}',
  'gen4_turbo',
  'Gen-4 model is returned second'
);

select is(
  (
    select jsonb_agg(model.value ->> 'status')
    from jsonb_array_elements(
      content_factory_private.generation_model_acceptance(
        '00000000-0000-4000-8000-000000000090'::uuid
      ) -> 'models'
    ) model(value)
  ),
  '["unproven", "unproven", "unproven"]'::jsonb,
  'every model is unproven without exact paid and reviewed output'
);

select is(
  content_factory_private.generation_model_acceptance_pending(
    '00000000-0000-4000-8000-000000000090'::uuid
  ),
  jsonb_build_object(
    'seedream5_lite', null,
    'gen4_turbo', null,
    'seedance2_fast', null
  ),
  'an organization without an exact paid output exposes no pending target'
);

select throws_ok(
  $$
    select content_factory_private.generation_model_acceptance(
      null::uuid
    )
  $$,
  '22023',
  'generation_model_acceptance_organization_required',
  'missing organization fails closed'
);

select * from finish();
rollback;
