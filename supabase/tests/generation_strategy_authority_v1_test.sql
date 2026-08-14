begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select has_table(
  'content_factory', 'generation_spec_strategy_bindings',
  'strategy bindings have an append-only authority table'
);
select has_table(
  'content_factory', 'generation_spec_strategy_assets',
  'exact strategy role assets have their own ledger'
);
select has_table(
  'content_factory', 'generation_job_strategy_snapshots',
  'every strategy job can carry one immutable launch snapshot'
);
select has_table(
  'content_factory', 'generation_strategy_status_events',
  'strategy job status changes have an append-only journal'
);
select has_view(
  'content_factory', 'generation_strategy_status_projection',
  'strategy status projection is derived from the journal'
);

select has_trigger(
  'content_factory', 'generation_spec_strategy_bindings',
  'generation_spec_strategy_binding_append_only',
  'strategy bindings reject update and delete'
);
select has_trigger(
  'content_factory', 'generation_spec_strategy_assets',
  'generation_spec_strategy_asset_append_only',
  'strategy assets reject update and delete'
);
select has_trigger(
  'content_factory', 'generation_job_strategy_snapshots',
  'generation_job_strategy_snapshot_append_only',
  'job strategy snapshots reject update and delete'
);
select has_trigger(
  'content_factory', 'generation_strategy_status_events',
  'generation_strategy_status_event_append_only',
  'strategy status events reject update and delete'
);
select has_trigger(
  'content_factory', 'generation_jobs',
  'generation_job_strategy_snapshot_capture',
  'job insert captures an exact strategy snapshot when a binding exists'
);
select has_trigger(
  'content_factory', 'generation_jobs',
  'generation_job_strategy_status_capture',
  'job status changes append strategy status events'
);

select ok(
  to_regprocedure('public.system_bind_generation_spec_strategy(jsonb)')
    is not null
  and has_function_privilege(
    'service_role',
    'public.system_bind_generation_spec_strategy(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_bind_generation_spec_strategy(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon', 'public.system_bind_generation_spec_strategy(jsonb)', 'execute'
  ),
  'low-level binder is service-only'
);
select ok(
  to_regprocedure('public.system_resolve_generation_strategy_price(jsonb)')
    is not null
  and has_function_privilege(
    'service_role',
    'public.system_resolve_generation_strategy_price(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_resolve_generation_strategy_price(jsonb)', 'execute'
  ),
  'tariff resolver is service-only'
);
select ok(
  to_regprocedure(
    'public.system_resolve_and_bind_generation_strategy(jsonb)'
  ) is not null
  and has_function_privilege(
    'service_role',
    'public.system_resolve_and_bind_generation_strategy(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_resolve_and_bind_generation_strategy(jsonb)', 'execute'
  )
  and position(
    '''browser_hashes_accepted'', false' in
    pg_get_functiondef(
      'public.system_resolve_and_bind_generation_strategy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'research_exact_youtube_media_attachments' in
    pg_get_functiondef(
      'public.system_resolve_and_bind_generation_strategy(jsonb)'::regprocedure
    )
  ) > 0,
  'browser-safe wrapper is service-only and resolves attachment/hash authority'
);
select ok(
  to_regprocedure(
    'public.system_generation_strategy_provider_policy(jsonb)'
  ) is not null
  and has_function_privilege(
    'service_role',
    'public.system_generation_strategy_provider_policy(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_generation_strategy_provider_policy(jsonb)', 'execute'
  ),
  'strategy launch policy is service-only'
);
select ok(
  to_regprocedure(
    'public.creator_generation_strategy_repeat_data(jsonb)'
  ) is not null
  and has_function_privilege(
    'authenticated',
    'public.creator_generation_strategy_repeat_data(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_generation_strategy_repeat_data(jsonb)', 'execute'
  ),
  'repeat data reader is authenticated-only'
);

select is(
  content_factory_private.generation_strategy_recipe('viral_avatar_ugc'),
  'product_ugc',
  'avatar UGC maps only to Runway product_ugc'
);
select is(
  content_factory_private.generation_strategy_recipe('viral_product_swap'),
  'product_swap',
  'product replacement maps only to Runway product_swap'
);
select is(
  content_factory_private.generation_strategy_recipe('viral_rebuild'),
  'product_ad',
  'viral rebuild maps only to Runway product_ad'
);

select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 4, '720p', '720:1280', true
  ) ->> 'estimated_credits',
  '192',
  'product_ugc 720p uses the exact four-second base tariff'
);
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 15, '1080p', '1080:1920', false
  ) ->> 'estimated_credits',
  '648',
  'product_ugc 1080p adds exactly forty credits per extra second'
);
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 4, '720p', 'source', true
  ) ->> 'estimated_credits',
  '212',
  'product_swap 720p uses the exact four-second base tariff'
);
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 15, '1080p', 'source', false
  ) ->> 'estimated_credits',
  '668',
  'product_swap 1080p adds exactly forty credits per extra second'
);
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_rebuild', 4, '720p', '1280:720', false
  ) ->> 'estimated_credits',
  '200',
  'product_ad 720p uses the exact four-second base tariff'
);
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_rebuild', 15, '1080p', '1920:1080', true
  ) ->> 'estimated_credits',
  '656',
  'product_ad 1080p adds exactly forty credits per extra second'
);
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_rebuild', 4, '1080p', '1280:720', false
  ),
  null::jsonb,
  'a ratio from the wrong resolution tier fails closed'
);

select ok(
  content_factory_private.generation_strategy_asset_snapshot_valid(
    jsonb_build_array(jsonb_build_object(
      'role', 'product_primary',
      'ordinal', 1,
      'media_object_id', 'ac900000-0000-4000-8000-000000000001',
      'sha256', repeat('a', 64),
      'kind', 'product_photo',
      'mime_type', 'image/png',
      'product_id', 'ac300000-0000-4000-8000-000000000001',
      'rights_confirmed', true,
      'likeness_consent', false
    ))
  ),
  'one exact product asset is valid for the rebuild legacy-compatible floor'
);
select ok(
  not content_factory_private.generation_strategy_asset_snapshot_valid(
    jsonb_build_array(jsonb_build_object(
      'role', 'product_primary',
      'ordinal', 1,
      'media_object_id', 'ac900000-0000-4000-8000-000000000001',
      'sha256', repeat('a', 64),
      'kind', 'product_photo',
      'mime_type', 'image/png',
      'product_id', 'ac300000-0000-4000-8000-000000000001',
      'rights_confirmed', true,
      'likeness_consent', false,
      'signed_url', 'https://forbidden.example.test/token'
    ))
  ),
  'signed URLs cannot enter an immutable role asset snapshot'
);

select ok(
  position(
    'strategy_id_value = ''all''' in
    pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'strategy_snapshot.strategy_id = strategy_id_value' in
    pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'team_scope or batch.created_by = user_id' in
    pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'batch.archived_at is null' in
    pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )
  ) > 0,
  'strategy archive filter preserves team/operator ACL and archived exclusion'
);

select ok(
  position(
    '''generation_strategy_start_path_not_integrated''' in
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''launch_enabled'', false' in
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    )
  ) > 0,
  'intermediate provider policy cannot make the UI executable by itself'
);

select * from finish();
rollback;
