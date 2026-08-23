begin;

-- 202608230021_rebuild_engines_reference_to_video_v1
--
-- Движки «Создания» (viral_rebuild): ролик с нуля по фото товара.
--
-- ЧТО НАБЛЮДАЛОСЬ. У «Создания» не было НИ ОДНОЙ строки реестра: единственный
-- «маршрут» жил только в списке исполнимых пар и вёл на /v1/recipes/product_ad,
-- которого у Runway не существует. Замок 202608230010 честно не пускал
-- стратегию к деньгам, витрина 202608230011 честно показывала «недоступно».
-- Выбора движка — ноль.
--
-- ЧТО ЗАВОДИТСЯ. Четыре модели fal класса «фото → видео». Ролик-референс
-- провайдеру НЕ уходит — так записано в каталоге стратегии
-- (source_video: forwarded_to_provider = false): его механику оператор и
-- ИИ-центр переписывают в замысел, а модель собирает новый ролик по фото
-- товара и этому описанию. Схемы входа сверены по OpenAPI очереди fal, цены —
-- по страницам моделей, 23.08.2026. Все — семейство regenerate, длительность
-- и кадр выбирает оператор (duration_source = operator_choice), разрешение —
-- 720p (1080p у моделей либо нет, либо вдвое дороже и отдельной строкой не
-- заведено).
--
--   minimax/h3/reference-to-video            $0.06/с при 768P → 6¢, 5–15 с,
--     до 5 фото (первые пять бесплатны). РЕКОМЕНДОВАН по умолчанию: дёшево,
--     родное 768P, окно длительности шире всех.
--   xai/grok-imagine-video/reference-to-video $0.07/с при 720p + $0.002/фото
--     → 8¢ с запасом, 1–10 с (в реестре 4–10 по пределу стратегии), до 5 фото.
--   alibaba/happy-horse/reference-to-video    $0.14/с при 720p → 14¢, 3–15 с,
--     1–9 фото (короткая сторона ≥400px!), до 5.
--   bytedance/seedance-2.5/reference-to-video ≈$0.473/с при 720p без видео-
--     референса (токены: h·w·выход·24/1024 × $0.0214/1000; скидка ×0.6 только
--     при видео на входе, которого здесь нет) → 48¢ с запасом, 4–15 с, premium.
--
-- ВЕРСИИ ПРАЙСА. MiniMax и Seedance повторяют версии «Копии» — подпись
-- (provider, pricing_version) уникальна ВНУТРИ стратегии, а способ счёта у
-- модели один. Grok и Happy Horse reference-to-video получают свои.
--
-- ПОРЯДОК. Как и 202608230020: список исполнимых пар переписывается целиком,
-- применять раньше цепочки «Дуэта» нельзя.

-- 1. Словарь версий прайса.
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
    'fal-usd-per-second-happy-horse-reference-2026-08-23.v1'
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
    'fal-usd-per-second-happy-horse-reference-2026-08-23.v1'
  ]));

-- 2. Список исполнимых пар: «Создание» получает четыре маршрута fal. Строка
--    runway/gen4_turbo на несуществующий рецептный адрес из списка УБРАНА:
--    пары /v1/recipes/* у Runway нет, и держать её «исполнимой» значило бы
--    лгать замку 202608230010.
create or replace function
  content_factory_private.generation_strategy_provider_route_allowed(
    p_strategy_id text,
    p_provider text,
    p_model_key text,
    p_provider_path text,
    p_poll_kind text,
    p_pricing_version text
  )
returns boolean
language sql
immutable
set search_path to ''
as $$
  select coalesce(case
    when p_strategy_id = 'viral_avatar_ugc'
     and p_provider = 'heygen'
     and p_model_key = 'avatar_v3'
      then p_provider_path = '/v3/videos'
       and p_poll_kind = 'heygen_video'
       and p_pricing_version = 'heygen-usd-per-second-2026-08-22.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'runway'
     and p_model_key = 'aleph2'
      then p_provider_path = '/v1/video_to_video'
       and p_poll_kind = 'runway_task'
       and p_pricing_version = 'runway-recipe-credits-2026-08-14.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key = 'fal-ai/pika/v2/pikaswaps'
      then p_provider_path = 'fal-ai/pika/v2/pikaswaps'
       and p_poll_kind = 'fal_request'
       and p_pricing_version = 'fal-usd-per-run-2026-08-18.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key =
       'fal-ai/kling-video/o3/pro/video-to-video/edit'
      then p_provider_path =
        'fal-ai/kling-video/o3/pro/video-to-video/edit'
       and p_poll_kind = 'fal_request'
       and p_pricing_version = 'fal-usd-per-second-2026-08-18.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key =
       'fal-ai/kling-video/o3/standard/video-to-video/edit'
      then p_provider_path =
        'fal-ai/kling-video/o3/standard/video-to-video/edit'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-kling-standard-2026-08-23.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key = 'alibaba/happy-horse/video-edit'
      then p_provider_path = 'alibaba/happy-horse/video-edit'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-happy-horse-2026-08-23.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key = 'bytedance/seedance-2.5/reference-to-video'
      then p_provider_path = 'bytedance/seedance-2.5/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-bytedance-2-5-2026-08-23.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key = 'minimax/h3/reference-to-video'
      then p_provider_path = 'minimax/h3/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-minimax-h3-2026-08-23.v1'
    -- «Создание», 23.08.2026.
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'fal'
     and p_model_key = 'minimax/h3/reference-to-video'
      then p_provider_path = 'minimax/h3/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-minimax-h3-2026-08-23.v1'
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'fal'
     and p_model_key = 'xai/grok-imagine-video/reference-to-video'
      then p_provider_path = 'xai/grok-imagine-video/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-grok-imagine-2026-08-23.v1'
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'fal'
     and p_model_key = 'alibaba/happy-horse/reference-to-video'
      then p_provider_path = 'alibaba/happy-horse/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-happy-horse-reference-2026-08-23.v1'
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'fal'
     and p_model_key = 'bytedance/seedance-2.5/reference-to-video'
      then p_provider_path = 'bytedance/seedance-2.5/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-bytedance-2-5-2026-08-23.v1'
    else false
  end, false);
$$;

-- 3. Рубильник запуска: две новые пары provider:model (MiniMax и Seedance уже
--    там после 202608230020).
do $launch_gate_rebuild_engines$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text :=
    $f$when 'fal:minimax/h3/reference-to-video' then true$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  if definition_value is null then
    raise exception using message = 'launch_gate_missing';
  end if;
  if position('fal:xai/grok-imagine-video/reference-to-video' in definition_value) > 0 then
    return;
  end if;
  anchor_hits := (
    length(definition_value)
    - length(replace(definition_value, anchor_text, ''))
  ) / length(anchor_text);
  if anchor_hits <> 1 then
    raise exception using
      message = 'launch_gate_anchor_not_unique:' || anchor_hits::text;
  end if;
  patched_value := replace(
    definition_value,
    anchor_text,
    anchor_text || $r$
    when 'fal:xai/grok-imagine-video/reference-to-video' then true
    when 'fal:alibaba/happy-horse/reference-to-video' then true$r$
  );
  if position('fal:alibaba/happy-horse/reference-to-video' in patched_value) = 0 then
    raise exception using message = 'launch_gate_patch_failed';
  end if;
  execute patched_value;
end;
$launch_gate_rebuild_engines$;

-- 4. Строки реестра. Все включены, MiniMax — по умолчанию.
insert into content_factory.generation_strategy_provider_routes (
  strategy_id, provider, model_key, provider_path, poll_kind,
  pricing_version, price_kind, price_rate_minor,
  min_duration_seconds, max_duration_seconds, tier,
  quality_modes, duration_source, engine_family, input_profile,
  recommended, enabled, verified_rate_at, notes
)
values
(
  'viral_rebuild', 'fal',
  'minimax/h3/reference-to-video',
  'minimax/h3/reference-to-video', 'fal_request',
  'fal-usd-per-second-minimax-h3-2026-08-23.v1', 'usd_minor_per_second', 6,
  5, 15, 'cheap',
  '[{"code": "source", "label": "720p", "resolution": "720p"}]'::jsonb,
  'operator_choice', 'regenerate',
  '{"video": {"min_seconds": 5, "max_seconds": 15, "min_short_side_px": null, "max_long_side_px": null}, "images": {"max": 5, "style": "named_refs"}, "keeps_source_audio": false}'::jsonb,
  true, true, now(),
  'MiniMax H3 reference-to-video для «Создания»: ролик с нуля по фото товара (Image 1…, первые пять бесплатны) и описанию механики. $0.06/с при 768P (fal.ai/models/minimax/h3/reference-to-video, 23.08.2026). Длительность 5–15 с выбирает оператор, кадр — из соотношения сторон формы.'
),
(
  'viral_rebuild', 'fal',
  'xai/grok-imagine-video/reference-to-video',
  'xai/grok-imagine-video/reference-to-video', 'fal_request',
  'fal-usd-per-second-grok-imagine-2026-08-23.v1', 'usd_minor_per_second', 8,
  4, 10, 'cheap',
  '[{"code": "source", "label": "720p", "resolution": "720p"}]'::jsonb,
  'operator_choice', 'regenerate',
  '{"video": {"min_seconds": 1, "max_seconds": 10, "min_short_side_px": null, "max_long_side_px": null}, "images": {"max": 5, "style": "at_refs"}, "keeps_source_audio": false}'::jsonb,
  false, true, now(),
  'Grok Imagine reference-to-video для «Создания»: до 7 фото (@Image1…), 1–10 с, 480p/720p. $0.07/с при 720p + $0.002 за фото (fal.ai/models/xai/grok-imagine-video/reference-to-video, 23.08.2026) → 8¢ с запасом.'
),
(
  'viral_rebuild', 'fal',
  'alibaba/happy-horse/reference-to-video',
  'alibaba/happy-horse/reference-to-video', 'fal_request',
  'fal-usd-per-second-happy-horse-reference-2026-08-23.v1', 'usd_minor_per_second', 14,
  4, 15, 'medium',
  '[{"code": "source", "label": "720p", "resolution": "720p"}]'::jsonb,
  'operator_choice', 'regenerate',
  '{"video": {"min_seconds": 3, "max_seconds": 15, "min_short_side_px": null, "max_long_side_px": null}, "images": {"max": 5, "style": "at_refs"}, "keeps_source_audio": false}'::jsonb,
  false, true, now(),
  'Happy Horse reference-to-video для «Создания»: 1–9 фото (character1…, короткая сторона ≥400px), 3–15 с, 720p/1080p. $0.14/с при 720p (fal.ai/models/alibaba/happy-horse/reference-to-video, 23.08.2026); 1080p вдвое дороже и не заведён.'
),
(
  'viral_rebuild', 'fal',
  'bytedance/seedance-2.5/reference-to-video',
  'bytedance/seedance-2.5/reference-to-video', 'fal_request',
  'fal-usd-per-second-bytedance-2-5-2026-08-23.v1', 'usd_minor_per_second', 48,
  4, 15, 'premium',
  '[{"code": "source", "label": "720p", "resolution": "720p"}]'::jsonb,
  'operator_choice', 'regenerate',
  '{"video": {"min_seconds": 4, "max_seconds": 30, "min_short_side_px": null, "max_long_side_px": null}, "images": {"max": 6, "style": "at_refs"}, "keeps_source_audio": false}'::jsonb,
  false, true, now(),
  'Seedance 2.5 reference-to-video для «Создания» без видео-референса: до 6 фото (@Image1…), 4–15 с, 720p. Цена по токенам ≈$0.473/с при 720p (без видео скидки ×0.6 нет) → 48¢ с запасом. Звук не генерируется.'
)
on conflict (strategy_id, provider, model_key) do nothing;

-- 5. Цена маршрута знает его уровни качества. До этого
--    generation_strategy_route_price проверяла только решётку «разрешение ↔
--    кадр» рецепта, и движок fal с единственным режимом 720p молча отдавал
--    цену и строку подтверждения «…_1080P_…» за ролик, который он сделает в
--    720p. Разрешение обязано быть одним из quality_modes строки реестра.
do $route_price_quality_modes$
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
  if position('route_quality_mode_missing' in definition_value) > 0 then
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
    $r$  -- Разрешение обязано быть одним из уровней качества строки реестра:
  -- иначе цена и строка подтверждения описывали бы ролик, которого движок
  -- не сделает (route_quality_mode_missing).
  if not exists (
    select 1
    from jsonb_array_elements(route_row.quality_modes) as mode
    where mode ->> 'resolution' = p_resolution
  ) then
    return null;
  end if;
$r$ || anchor_text
  );
  if position('route_quality_mode_missing' in patched_value) = 0 then
    raise exception using message = 'route_price_patch_failed';
  end if;
  execute patched_value;
end;
$route_price_quality_modes$;

-- Та же проверка в цене ДЕЙСТВУЮЩЕГО маршрута: generation_strategy_recipe_price
-- повторяет арифметику и обязана повторять и отказ.
do $recipe_price_quality_modes$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text :=
    $f$  if provider_value <> 'runway' then
    if p_duration_seconds not between route_row.min_duration_seconds$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_strategy_recipe_price';
  if definition_value is null then
    raise exception using message = 'recipe_price_missing';
  end if;
  if position('route_quality_mode_missing' in definition_value) > 0 then
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
    $r$  if provider_value <> 'runway' then
    -- route_quality_mode_missing: разрешение обязано быть уровнем качества
    -- действующей строки реестра.
    if not exists (
      select 1
      from jsonb_array_elements(route_row.quality_modes) as mode
      where mode ->> 'resolution' = p_resolution
    ) then
      return null;
    end if;
    if p_duration_seconds not between route_row.min_duration_seconds$r$
  );
  if position('route_quality_mode_missing' in patched_value) = 0 then
    raise exception using message = 'recipe_price_patch_failed';
  end if;
  execute patched_value;
end;
$recipe_price_quality_modes$;

-- 6. Проверка.
do $rebuild_engines_verify$
declare
  rebuild_rows integer;
  enabled_rows integer;
  signatures integer;
  launch_ok boolean;
begin
  select count(*), count(*) filter (where enabled)
    into rebuild_rows, enabled_rows
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_rebuild';
  if rebuild_rows <> 4 or enabled_rows <> 4 then
    raise exception using message =
      'rebuild_engines_route_count_invalid:' || rebuild_rows::text || '/'
      || enabled_rows::text;
  end if;

  select count(distinct (provider, pricing_version)) into signatures
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_rebuild' and enabled;
  if signatures <> enabled_rows then
    raise exception using message =
      'rebuild_engines_signature_collision:' || signatures::text;
  end if;

  if exists (
    select 1
    from content_factory.generation_strategy_provider_routes route
    where route.strategy_id in ('viral_rebuild', 'viral_product_swap')
      and not content_factory_private.generation_strategy_provider_route_allowed(
        route.strategy_id, route.provider, route.model_key,
        route.provider_path, route.poll_kind, route.pricing_version
      )
  ) then
    raise exception using message = 'rebuild_engines_route_not_allowed';
  end if;

  if (
    select count(*) from content_factory.generation_strategy_provider_routes
    where strategy_id = 'viral_rebuild' and recommended
  ) <> 1 then
    raise exception using message = 'rebuild_engines_recommended_not_one';
  end if;

  -- Замок 202608230010 отпирается самим фактом исполнимой строки.
  if not content_factory_private.generation_strategy_executable_route_exists(
    'viral_rebuild'
  ) then
    raise exception using message = 'rebuild_engines_still_locked';
  end if;

  select pg_get_functiondef(p.oid) like '%fal:alibaba/happy-horse/reference-to-video%'
    into launch_ok
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  if not coalesce(launch_ok, false) then
    raise exception using message = 'rebuild_engines_launch_gate_missing';
  end if;

  if content_factory_private.generation_strategy_route_price(
       'viral_rebuild', 'fal', 'minimax/h3/reference-to-video',
       10, '1080p', '1920:1080', false
     ) is not null then
    raise exception using message = 'rebuild_engines_1080p_price_leak';
  end if;
  if content_factory_private.generation_strategy_route_price(
       'viral_rebuild', 'fal', 'minimax/h3/reference-to-video',
       10, '720p', '720:1280', false
     ) is null then
    raise exception using message = 'rebuild_engines_720p_price_missing';
  end if;
  if content_factory_private.generation_strategy_recipe_price(
       'viral_rebuild', 15, '1080p', '1920:1080', true
     ) is not null then
    raise exception using message = 'rebuild_engines_recipe_1080p_price_leak';
  end if;
  if (content_factory_private.generation_strategy_recipe_price(
       'viral_product_swap', 10, '720p', 'source', false
     ) ->> 'estimated_credits') <> '47' then
    raise exception using message = 'rebuild_engines_copy_price_drifted';
  end if;
end;
$rebuild_engines_verify$;

commit;
