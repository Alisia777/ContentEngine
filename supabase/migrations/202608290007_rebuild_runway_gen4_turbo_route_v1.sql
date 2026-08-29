begin;

-- 202608290007_rebuild_runway_gen4_turbo_route_v1
--
-- «Создание» (viral_rebuild, рецепт product_ad) получает движок Runway
-- Gen-4 Turbo — для честного сравнения с Seedance и остальными fal-моделями.
--
-- ЧТО НАБЛЮДАЛОСЬ. Владелец спросил «почему убрали самый сильный движок
-- ранвей». Убрали честно: прежняя пара runway/gen4_turbo вела на
-- /v1/recipes/product_ad, которого у провайдера НЕ СУЩЕСТВУЕТ (проверено по
-- фильтру Request History 17.08.2026), и была снята из списка исполнимых
-- (202608230021), чтобы не лгать замку 202608230010.
--
-- ЧТО ЗАВОДИТСЯ. Настоящий маршрут: POST /v1/image_to_video, model
-- gen4_turbo — первое фото товара становится ПЕРВЫМ КАДРОМ ролика, сцену
-- описывает серверное указание. Цена ОФИЦИАЛЬНОГО API: 5 кредитов/с,
-- 1 кредит = $0.01 → $0.05/с, то есть 25/50 кредитов за 5/10 секунд
-- (docs.dev.runwayml.com/guides/pricing, сверено 29.08.2026). Это
-- ПОСЕКУНДНАЯ ставка, а не ступени рецепта, поэтому строка несёт
-- price_kind = 'usd_minor_per_second' и ставку 5 центов: рунвеевская
-- арифметика base+incremental (200/216 + 36/40) описывает НЕ эту модель.
--
-- РЕШЁТКА ДЛИТЕЛЬНОСТИ. Параметр duration у Gen-4 Turbo принимает РОВНО 5
-- или 10 секунд. Окно min/max реестра дискретность не выражает, поэтому цена
-- отказывает значениям вне решётки (маркер gen4_turbo_duration_lattice) —
-- ДО резерва денег, а не отказом провайдера после. Та же решётка стоит в
-- адаптере отправки и в панели секунд.
--
-- ПОРЯДОК ВЫКЛАДКИ. Сначала edge и веб (версия прайса в словарях, ветка
-- image_to_video, решётка секунд), затем эта миграция: включённая строка при
-- старом edge означала бы 503 без имени причины на привязке с этим движком.

-- 1. Словари версий прайса: одиннадцатая версия.
alter table content_factory.generation_strategy_readiness_receipts
  drop constraint generation_strategy_readiness_receipts_pricing_version_check;
alter table content_factory.generation_strategy_readiness_receipts
  add constraint generation_strategy_readiness_receipts_pricing_version_check
  check (pricing_version = any (array[
    'runway-recipe-credits-2026-08-14.v1',
    'fal-usd-per-run-2026-08-18.v1',
    'fal-usd-per-second-2026-08-18.v1',
    'heygen-usd-per-second-2026-08-22.v1',
    'fal-usd-per-second-kling-standard-2026-08-23.v1',
    'fal-usd-per-second-happy-horse-2026-08-23.v1',
    'fal-usd-per-second-bytedance-2-5-2026-08-23.v1',
    'fal-usd-per-second-minimax-h3-2026-08-23.v1',
    'fal-usd-per-second-grok-imagine-2026-08-23.v1',
    'fal-usd-per-second-happy-horse-reference-2026-08-23.v1',
    'runway-usd-per-second-gen4-turbo-2026-08-29.v1'
  ]));

alter table content_factory.generation_strategy_binding_selections
  drop constraint generation_strategy_binding_selections_pricing_version_check;
alter table content_factory.generation_strategy_binding_selections
  add constraint generation_strategy_binding_selections_pricing_version_check
  check (pricing_version = any (array[
    'runway-recipe-credits-2026-08-14.v1',
    'fal-usd-per-run-2026-08-18.v1',
    'fal-usd-per-second-2026-08-18.v1',
    'heygen-usd-per-second-2026-08-22.v1',
    'fal-usd-per-second-kling-standard-2026-08-23.v1',
    'fal-usd-per-second-happy-horse-2026-08-23.v1',
    'fal-usd-per-second-bytedance-2-5-2026-08-23.v1',
    'fal-usd-per-second-minimax-h3-2026-08-23.v1',
    'fal-usd-per-second-grok-imagine-2026-08-23.v1',
    'fal-usd-per-second-happy-horse-reference-2026-08-23.v1',
    'runway-usd-per-second-gen4-turbo-2026-08-29.v1'
  ]));

-- 2. Список исполнимых пар: + viral_rebuild/runway/gen4_turbo. Точечная
--    вставка по якорю, а не переписывание целиком: на проде уже замечена
--    строка kling i2v чужой недовыложенной ветки, и полный rewrite стёр бы
--    чужую работу молча.
do $route_allowed_gen4$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text := E'    else false\n  end, false);';
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_strategy_provider_route_allowed';
  if definition_value is null then
    raise exception using message = 'route_allowed_missing';
  end if;
  if position('runway-usd-per-second-gen4-turbo-2026-08-29.v1'
       in definition_value) > 0 then
    return;
  end if;
  anchor_hits := (
    length(definition_value)
    - length(replace(definition_value, anchor_text, ''))
  ) / length(anchor_text);
  if anchor_hits <> 1 then
    raise exception using
      message = 'route_allowed_anchor_not_unique:' || anchor_hits::text;
  end if;
  patched_value := replace(
    definition_value,
    anchor_text,
    $r$    -- «Создание» на Runway (Gen-4 Turbo), 29.08.2026: настоящий адрес
    -- /v1/image_to_video, посекундный прайс официального API ($0.05/с).
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'runway'
     and p_model_key = 'gen4_turbo'
      then p_provider_path = '/v1/image_to_video'
       and p_poll_kind = 'runway_task'
       and p_pricing_version =
         'runway-usd-per-second-gen4-turbo-2026-08-29.v1'
$r$ || anchor_text
  );
  if position('runway-usd-per-second-gen4-turbo-2026-08-29.v1'
       in patched_value) = 0 then
    raise exception using message = 'route_allowed_patch_failed';
  end if;
  execute patched_value;
end;
$route_allowed_gen4$;

-- 3. Решётка длительности в цене ЗАПРОШЕННОГО маршрута: duration вне {5,10}
--    для версии прайса gen4_turbo — отказ до резерва.
do $route_price_gen4_lattice$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text :=
    $f$  if route_row.price_kind = 'runway_credit_tiers' then$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_strategy_route_price';
  if definition_value is null then
    raise exception using message = 'route_price_missing';
  end if;
  if position('gen4_turbo_duration_lattice' in definition_value) > 0 then
    return;
  end if;
  anchor_hits := (
    length(definition_value)
    - length(replace(definition_value, anchor_text, ''))
  ) / length(anchor_text);
  if anchor_hits <> 1 then
    raise exception using
      message = 'route_price_anchor_not_unique:' || anchor_hits::text;
  end if;
  patched_value := replace(
    definition_value,
    anchor_text,
    $r$  -- gen4_turbo_duration_lattice: параметр duration у Runway Gen-4 Turbo
  -- принимает РОВНО 5 или 10 секунд. Окно 5–10 реестра дискретность не
  -- выражает, а цена вне решётки означала бы резерв под запрос, который
  -- провайдер отвергнет уже ПОСЛЕ брони.
  if route_row.pricing_version =
       'runway-usd-per-second-gen4-turbo-2026-08-29.v1'
     and p_duration_seconds not in (5, 10) then
    return null;
  end if;
$r$ || anchor_text
  );
  if position('gen4_turbo_duration_lattice' in patched_value) = 0 then
    raise exception using message = 'route_price_patch_failed';
  end if;
  execute patched_value;
end;
$route_price_gen4_lattice$;

-- 4. Цена ДЕЙСТВУЮЩЕГО маршрута: ветвление «runway ⇒ ступени» заменяется на
--    «версия прайса рецепта ⇒ ступени». Иначе перенос recommended на строку
--    gen4_turbo молча посчитал бы её кредитными ступенями 200/216+36/40.
--    Для fal и heygen поведение не меняется: их версии прайса не рецептные.
do $recipe_price_gen4$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text := $f$  if provider_value <> 'runway' then$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_strategy_recipe_price';
  if definition_value is null then
    raise exception using message = 'recipe_price_missing';
  end if;
  if position('gen4_turbo_duration_lattice' in definition_value) > 0 then
    return;
  end if;
  anchor_hits := (
    length(definition_value)
    - length(replace(definition_value, anchor_text, ''))
  ) / length(anchor_text);
  if anchor_hits <> 1 then
    raise exception using
      message = 'recipe_price_anchor_not_unique:' || anchor_hits::text;
  end if;
  patched_value := replace(
    definition_value,
    anchor_text,
    $r$  -- Ступени кредитов принадлежат ПРАЙСУ рецепта, а не провайдеру:
  -- gen4_turbo «Создания» считается посекундно.
  if pricing_version_value <> 'runway-recipe-credits-2026-08-14.v1' then
    -- gen4_turbo_duration_lattice: та же решётка, что в цене запрошенного
    -- маршрута, — duration только 5 или 10 секунд.
    if pricing_version_value =
         'runway-usd-per-second-gen4-turbo-2026-08-29.v1'
       and p_duration_seconds not in (5, 10) then
      return null;
    end if;
$r$
  );
  if position('gen4_turbo_duration_lattice' in patched_value) = 0 then
    raise exception using message = 'recipe_price_patch_failed';
  end if;
  execute patched_value;
end;
$recipe_price_gen4$;

-- 5. Строка реестра. Рубильник generation_provider_launch_enabled УЖЕ знает
--    пару runway:gen4_turbo (это проверяется ниже поведением, а не верой).
insert into content_factory.generation_strategy_provider_routes (
  strategy_id, provider, model_key, provider_path, poll_kind,
  pricing_version, price_kind, price_rate_minor,
  min_duration_seconds, max_duration_seconds, tier,
  quality_modes, duration_source, engine_family, input_profile,
  recommended, enabled, verified_rate_at, notes
)
values (
  'viral_rebuild', 'runway', 'gen4_turbo',
  '/v1/image_to_video', 'runway_task',
  'runway-usd-per-second-gen4-turbo-2026-08-29.v1',
  'usd_minor_per_second', 5,
  5, 10, 'premium',
  '[{"code": "source", "label": "720p", "resolution": "720p"}]'::jsonb,
  'operator_choice', 'regenerate',
  '{"video": {"min_seconds": 1, "max_seconds": 60, "min_short_side_px": null, "max_long_side_px": null}, "images": {"max": 1, "style": "start_frame"}, "keeps_source_audio": false}'::jsonb,
  false, true, now(),
  'Runway Gen-4 Turbo image_to_video для «Создания»: первое фото товара — стартовый кадр, сцену описывает серверное указание. $0.05/с = 5 кредитов/с официального API (docs.dev.runwayml.com/guides/pricing, 29.08.2026); duration только 5 или 10 с — решётку держат цена (gen4_turbo_duration_lattice), адаптер и панель секунд. Кадры 720p: 1280:720, 720:1280, 960:960; 834:1112 отправляется как 832:1104. Ролик-референс провайдеру не уходит, звук не генерируется.'
)
on conflict (strategy_id, provider, model_key) do nothing;

-- 6. ПРОВЕРКА ПОВЕДЕНИЕМ.
do $runway_gen4_verify$
declare
  route_count integer;
  recommended_count integer;
  enabled_count integer;
  signatures integer;
  launch_ok boolean;
begin
  -- Словари приняли новую версию.
  if position('runway-usd-per-second-gen4-turbo-2026-08-29.v1' in (
       select pg_get_constraintdef(oid) from pg_constraint
       where conrelid =
         'content_factory.generation_strategy_readiness_receipts'::regclass
         and conname =
           'generation_strategy_readiness_receipts_pricing_version_check'
     )) = 0 then
    raise exception using message = 'gen4_receipts_dictionary_missing';
  end if;
  if position('runway-usd-per-second-gen4-turbo-2026-08-29.v1' in (
       select pg_get_constraintdef(oid) from pg_constraint
       where conrelid =
         'content_factory.generation_strategy_binding_selections'::regclass
         and conname =
           'generation_strategy_binding_selections_pricing_version_check'
     )) = 0 then
    raise exception using message = 'gen4_selections_dictionary_missing';
  end if;

  -- Строка заведена ровно одна и ровно такой формы.
  select count(*) into route_count
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_rebuild' and provider = 'runway'
    and model_key = 'gen4_turbo'
    and provider_path = '/v1/image_to_video'
    and poll_kind = 'runway_task'
    and pricing_version = 'runway-usd-per-second-gen4-turbo-2026-08-29.v1'
    and price_kind = 'usd_minor_per_second' and price_rate_minor = 5
    and min_duration_seconds = 5 and max_duration_seconds = 10
    and tier = 'premium' and enabled and not recommended;
  if route_count <> 1 then
    raise exception using message = 'gen4_route_row_invalid';
  end if;

  -- Пара исполнима; старые пары не задеты.
  if not content_factory_private.generation_strategy_provider_route_allowed(
    'viral_rebuild', 'runway', 'gen4_turbo', '/v1/image_to_video',
    'runway_task', 'runway-usd-per-second-gen4-turbo-2026-08-29.v1'
  ) then
    raise exception using message = 'gen4_route_not_allowed';
  end if;
  if not content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'runway', 'aleph2', '/v1/video_to_video',
    'runway_task', 'runway-recipe-credits-2026-08-14.v1'
  ) or not content_factory_private.generation_strategy_provider_route_allowed(
    'viral_rebuild', 'fal', 'minimax/h3/reference-to-video',
    'minimax/h3/reference-to-video', 'fal_request',
    'fal-usd-per-second-minimax-h3-2026-08-23.v1'
  ) then
    raise exception using message = 'gen4_route_allowed_regressed';
  end if;

  -- Подпись (provider, pricing_version) уникальна среди включённых, и
  -- рекомендованный по-прежнему один.
  select count(*) filter (where enabled),
         count(distinct (provider, pricing_version)) filter (where enabled),
         count(*) filter (where recommended)
    into enabled_count, signatures, recommended_count
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_rebuild';
  if signatures <> enabled_count then
    raise exception using message = 'gen4_signature_collision';
  end if;
  if recommended_count <> 1 then
    raise exception using message = 'gen4_recommended_not_one';
  end if;

  -- Рубильник запуска уже знает пару.
  select pg_get_functiondef(p.oid) like '%runway:gen4_turbo%' into launch_ok
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  if not coalesce(launch_ok, false) then
    raise exception using message = 'gen4_launch_gate_missing';
  end if;

  -- Арифметика и решётка: 5 с = 25¢, 10 с = 50¢, 7 с и 1080p — отказ.
  if (content_factory_private.generation_strategy_route_price(
       'viral_rebuild', 'runway', 'gen4_turbo', 5, '720p', '720:1280', false
     ) ->> 'estimated_credits') is distinct from '25' then
    raise exception using message = 'gen4_price_5s_invalid';
  end if;
  if (content_factory_private.generation_strategy_route_price(
       'viral_rebuild', 'runway', 'gen4_turbo', 10, '720p', '720:1280', false
     ) ->> 'estimated_credits') is distinct from '50' then
    raise exception using message = 'gen4_price_10s_invalid';
  end if;
  if content_factory_private.generation_strategy_route_price(
       'viral_rebuild', 'runway', 'gen4_turbo', 7, '720p', '720:1280', false
     ) is not null then
    raise exception using message = 'gen4_lattice_leak_7s';
  end if;
  if content_factory_private.generation_strategy_route_price(
       'viral_rebuild', 'runway', 'gen4_turbo', 10, '1080p', '1920:1080', false
     ) is not null then
    raise exception using message = 'gen4_1080p_price_leak';
  end if;
  if (content_factory_private.generation_strategy_route_price(
       'viral_rebuild', 'runway', 'gen4_turbo', 10, '720p', '720:1280', false
     ) ->> 'spend_confirmation')
     is distinct from 'RUNWAY_PRODUCT_AD_10S_720P_SILENT_USD_0.50' then
    raise exception using message = 'gen4_confirmation_invalid';
  end if;

  -- Чужие цены не дрогнули: aleph2 по ступеням, «Копия» по Pika,
  -- рекомендованный MiniMax «Создания» по 6¢/с.
  if (content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'runway', 'aleph2', 10, '720p', 'source', false
     ) ->> 'estimated_credits') is distinct from '428' then
    raise exception using message = 'gen4_aleph2_price_drifted';
  end if;
  if (content_factory_private.generation_strategy_recipe_price(
       'viral_product_swap', 10, '720p', 'source', false
     ) ->> 'estimated_credits') is distinct from '47' then
    raise exception using message = 'gen4_copy_price_drifted';
  end if;
  if (content_factory_private.generation_strategy_recipe_price(
       'viral_rebuild', 10, '720p', '720:1280', false
     ) ->> 'estimated_credits') is distinct from '60' then
    raise exception using message = 'gen4_rebuild_recipe_price_drifted';
  end if;
end;
$runway_gen4_verify$;

commit;
