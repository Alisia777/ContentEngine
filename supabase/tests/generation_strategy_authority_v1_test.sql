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
    'system_resolve_and_bind_generation_strategy_pre_execution_v1' in
    pg_get_functiondef(
      'public.system_resolve_and_bind_generation_strategy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''browser_hashes_accepted'', false' in
    pg_get_functiondef(
      'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'research_exact_youtube_media_attachments' in
    pg_get_functiondef(
      'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
        ::regprocedure
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

-- «Дуэт» с 22.08.2026 кадр не выбирает: он приходит из комментируемого ролика,
-- и снимок цены называет его словом "source" — ровно как у «Копии». Прежние
-- вертикали 720:1280 и 1080:1920 были остатком измерения соотношением сторон,
-- которое владелец отменил вместе с прочтением «замена человека в кадре»
-- (миграция 202608220014).
--
-- Ступени тарифа при этом НЕ изменились: 192 и 648 — те же числа, что и были.
-- Правится проверка кадра, а не арифметика.
-- С 202608230022 действующий маршрут «Дуэта» — HeyGen, 5¢ за секунду
-- ведущего; рунвеевских ступеней у рецепта больше нет.
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 4, '720p', 'source', true
  ) ->> 'estimated_credits',
  '20',
  'duet 720p prices four seconds of presenter at twenty cents on the source frame'
);
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 15, '1080p', 'source', false
  ),
  null::jsonb,
  'duet has no 1080p quality mode: the frame is refused, not silently priced'
);
-- Отменённое измерение обязано ОТВЕРГАТЬСЯ, а не просто «больше не
-- проверяться». Без этого утверждения возврат старой формы прошёл бы молча:
-- цена посчиталась бы, а кадр оказался бы выбран там, где выбирать нечего.
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 4, '720p', '720:1280', true
  ),
  null::jsonb,
  'duet refuses the retired aspect-ratio measurement'
);
-- У «Копии» с 202608180010 действующий маршрут не Runway, а generation_strategy_
-- recipe_price отвечает про ДЕЙСТВУЮЩИЙ маршрут (202608180006). Поэтому ступени
-- Runway спрашиваются у маршрутной функции — там они и живут цифра в цифру, —
-- а у recipe_price проверяется то, за что она отвечает: её ответ обязан совпасть
-- с ценой действующей строки реестра. Прибить сюда сегодняшние 47 центов Pika
-- значило бы завязать тест на выбор, который меняется одной строкой в реестре.
select is(
  content_factory_private.generation_strategy_route_price(
    'viral_product_swap', 'runway', 'aleph2', 4, '720p', 'source', true
  ) ->> 'estimated_credits',
  '212',
  'product_swap 720p uses the exact four-second Runway base tariff'
);
select is(
  content_factory_private.generation_strategy_route_price(
    'viral_product_swap', 'runway', 'aleph2', 15, '1080p', 'source', false
  ) ->> 'estimated_credits',
  '668',
  'product_swap 1080p adds exactly forty Runway credits per extra second'
);
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 4, '720p', 'source', true
  ),
  (
    select content_factory_private.generation_strategy_route_price(
      'viral_product_swap', route.provider, route.model_key,
      4, '720p', 'source', true
    )
    from content_factory.generation_strategy_provider_routes as route
    where route.strategy_id = 'viral_product_swap'
      and route.recommended
      and route.enabled
  ),
  'product_swap recipe price is exactly the active route price'
);
-- С 23.08.2026 (202608230021) «Создание» исполняют движки fal с посекундной
-- ставкой, а действующий маршрут — MiniMax H3 (6¢/с, 5–15 с). Рунвеевских
-- ступеней у рецепта product_ad больше нет: адрес /v1/recipes/product_ad у
-- Runway не существует. Цена рецепта — цена ДЕЙСТВУЮЩЕГО маршрута.
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_rebuild', 5, '720p', '1280:720', false
  ) ->> 'estimated_credits',
  '30',
  'product_ad price is the active fal route rate times the duration'
);
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_rebuild', 4, '720p', '1280:720', false
  ),
  null::jsonb,
  'a duration below the active route window fails closed'
);
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_rebuild', 15, '1080p', '1920:1080', true
  ),
  null::jsonb,
  'product_ad has no 1080p route any more: the active engine renders 720p'
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
      'public.creator_generation_archive_pre_execution_v1(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'strategy_snapshot.strategy_id = strategy_id_value' in
    pg_get_functiondef(
      'public.creator_generation_archive_pre_execution_v1(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'team_scope or batch.created_by = user_id' in
    pg_get_functiondef(
      'public.creator_generation_archive_pre_execution_v1(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'batch.archived_at is null' in
    pg_get_functiondef(
      'public.creator_generation_archive_pre_execution_v1(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'creator_generation_archive_pre_execution_v1' in
    pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )
  ) > 0,
  'strategy archive filter preserves team/operator ACL and archived exclusion'
);

select ok(
  position(
    'generation_strategy_execution_chain_installed()' in
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'receipt_unconsumed_value' in
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    )
  ) > 0
  -- Прежде здесь пинилась целиком строка
  -- `launch_enabled_value := binding_current_value and approved_spec_value`.
  -- Миграция 202608230011 обернула вычисление в coalesce(..., false) и
  -- добавила ещё одно слагаемое — признак исполнимого маршрута. Набор
  -- обязательных условий при этом не убавился, а прибавился, поэтому
  -- проверяются сами слагаемые, а не отступы вокруг них.
  and position(
    'binding_current_value and approved_spec_value' in
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'generation_strategy_executable_route_exists(strategy_id_value)' in
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''launch_enabled'', launch_enabled_value' in
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''provider_call_started'', false' in
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    )
  ) > 0,
  'final provider policy requires exact current single-use server authority'
);

select * from finish();
rollback;
