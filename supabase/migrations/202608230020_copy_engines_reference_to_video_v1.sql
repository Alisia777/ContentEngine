begin;

-- 202608230020_copy_engines_reference_to_video_v1
--
-- Движки «Копии» — отдельными строками реестра. Четыре новых движка fal.
--
-- ЗАЧЕМ. Владелец нашёл на fal целый класс моделей «видео + фото товара»,
-- которых у нас не было. Движок в этой системе — это строка реестра
-- content_factory.generation_strategy_provider_routes: она называет модель,
-- цену, способ счёта, пределы длительности и кто задаёт длительность. Кода
-- движок касается ровно в трёх местах, и все три — словари: форма тела
-- (каталог), исполнимый маршрут (edge-контракт) и эта миграция. Общее у
-- движков — только реестр и ИИ-центр, который советует, какой выбрать.
--
-- ЧТО ЗАВОДИТСЯ (цены сверены по страницам моделей fal 23.08.2026, схемы
-- входа — по OpenAPI очереди fal; всё пересчитано в центы за секунду
-- результата, округление ВВЕРХ — резерв обязан быть не меньше списания):
--
--   fal-ai/kling-video/o3/standard/video-to-video/edit  $0.126/с → 13¢
--     Та же правка видео, что у Kling O3 Pro, уровнем ниже. Вход: видео
--     3–15 с, обе стороны ≥720px, до 4 фото (@Image1…), звук исходника
--     сохраняется.
--   alibaba/happy-horse/video-edit                       $0.14/с (720p) → 14¢
--     Правка готового ролика по описанию с опорой на фото (@Image1…@Image5).
--     Вход: видео 3–60 с, короткая сторона ≥320px, длинная ≤2160px; результат
--     той же длины, но не длиннее 15 с; исходный звук сохраняется
--     (audio_setting = origin). Раньше отбракован за расхождение цены на двух
--     страницах fal; 23.08 страница модели называет одну цену.
--   bytedance/seedance-2.5/reference-to-video             ≈$0.555/с → 58¢
--     Страница обещает «замени объект, сохранив движение и камеру». Цена по
--     токенам: h·w·(вход + выход)·24/1024 × $0.0214/1000, ×0.6 при видео-
--     референсе. При 720p (921 600 px) и выходе той же длины, что вход:
--     21 600 × 2 × 0.0214/1000 × 0.6 = $0.5547 за секунду результата.
--     Округлено до 58¢ с запасом на кадрирование 9:16 (736×1280). Это самый
--     дорогой движок «Копии»: 12 секунд ≈ $7. Уровень premium.
--   minimax/h3/reference-to-video                         $0.06/с (768P) → 6¢
--     ПЕРЕСБОРКА, а не правка: исходник — референс движения (Video 1), товар —
--     с фото (Image 1…, первые пять бесплатны). Длительность выбирает ОПЕРАТОР
--     (5–15 с, предел модели), поэтому duration_source = operator_choice.
--     Для «Копии» это второй эшелон; ИИ-центр должен советовать его тогда,
--     когда правка кадра заведомо не удержит товар.
--
-- НЕ ЗАВОДЯТСЯ (и почему, чтобы не возвращаться):
--   luma/agent/ray/v3.2/image-to-video, …/text-to-video — видео на вход не
--     берут; alibaba/happy-horse/reference-to-video, xai/grok-imagine-video/
--     reference-to-video — тоже только картинки; bytedance/seedance-2.0(/fast)
--     — вход не выше ~720p и суммарно ≤15 с, то есть вертикальный 1080×1920
--     исходник пришлось бы ужимать до отправки; luma …/video-to-video —
--     редактор без слотов под фото товара и $1.08 за 5 с.
--
-- ДВА НОВЫХ СВОЙСТВА У СТРОКИ РЕЕСТРА. Чтобы экран и ИИ-центр могли
-- объяснить движок человеку, не зная литералов моделей:
--   engine_family — 'edit' (меняет объект в готовом кадре), 'regenerate'
--     (собирает ролик заново по референсу), 'overlay' (накладывает поверх
--     нетронутого ролика — «Дуэт»).
--   input_profile — что движок принимает: окно длительности и размеры видео,
--     сколько фото и как они называются в указании, сохраняется ли звук.
--     Форма проверяется функцией, как quality_modes.
--
-- ВЕРСИЯ ПРАЙСА — У КАЖДОГО ДВИЖКА СВОЯ. Пара (provider, pricing_version)
-- среди включённых строк уникальна (индекс …_signature_key из 202608190006):
-- по ней опрос восстанавливает модель оплаченной задачи. Поэтому имя версии
-- называет и способ счёта, и движок. Словарь версий стоит в CHECK двух
-- таблиц и в трёх наборах кода (каталог, runtime портала, app.js) — все
-- расширяются в этом же заходе.
--
-- ПОРЯДОК ПРИМЕНЕНИЯ ВАЖЕН. Список исполнимых пар generation_strategy_provider_
-- route_allowed переписывается целиком (как в 202608220011). Применять эту
-- миграцию раньше 202608220011 нельзя: та перезапишет список без этих
-- движков. Загрузчик применяет по номеру, и номер здесь больше.

-- 1. Словарь версий прайса в двух таблицах.
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
    'fal-usd-per-second-minimax-h3-2026-08-23.v1'
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
    'fal-usd-per-second-minimax-h3-2026-08-23.v1'
  ]));

-- 2. Семейство движка и профиль входа.
alter table content_factory.generation_strategy_provider_routes
  add column if not exists engine_family text not null default 'edit';
alter table content_factory.generation_strategy_provider_routes
  drop constraint if exists
    generation_strategy_provider_routes_engine_family_check;
alter table content_factory.generation_strategy_provider_routes
  add constraint generation_strategy_provider_routes_engine_family_check
  check (engine_family in ('edit', 'regenerate', 'overlay'));

create or replace function
  content_factory_private.generation_strategy_input_profile_valid(
    p_profile jsonb
  )
returns boolean
language sql
immutable
set search_path to ''
as $$
  -- coalesce обязателен: у пустого объекта нет ключей, array_agg даёт NULL,
  -- сравнение с NULL даёт NULL, а CHECK с NULL ПРОПУСКАЕТ строку. Без этого
  -- профиль `{"video": {}, "images": {}, …}` прошёл бы в реестр.
  select coalesce(jsonb_typeof(p_profile) = 'object'
    and (select array_agg(key order by key) from jsonb_object_keys(p_profile) key)
        = array['images', 'keeps_source_audio', 'video']
    and jsonb_typeof(p_profile -> 'keeps_source_audio') = 'boolean'
    -- Видео: окно длительности в целых секундах и пределы размера в пикселях
    -- (null — предел не объявлен провайдером).
    and jsonb_typeof(p_profile -> 'video') = 'object'
    and (select array_agg(key order by key)
         from jsonb_object_keys(p_profile -> 'video') key)
        = array['max_long_side_px', 'max_seconds', 'min_seconds',
                'min_short_side_px']
    and (p_profile -> 'video' ->> 'min_seconds') ~ '^[0-9]{1,3}$'
    and (p_profile -> 'video' ->> 'max_seconds') ~ '^[0-9]{1,3}$'
    and (p_profile -> 'video' ->> 'min_seconds')::integer between 1 and 600
    and (p_profile -> 'video' ->> 'max_seconds')::integer between 1 and 600
    and (p_profile -> 'video' ->> 'min_seconds')::integer
        <= (p_profile -> 'video' ->> 'max_seconds')::integer
    and (jsonb_typeof(p_profile -> 'video' -> 'min_short_side_px') = 'null'
         or ((p_profile -> 'video' ->> 'min_short_side_px') ~ '^[0-9]{1,5}$'
             and (p_profile -> 'video' ->> 'min_short_side_px')::integer
                 between 1 and 10000))
    and (jsonb_typeof(p_profile -> 'video' -> 'max_long_side_px') = 'null'
         or ((p_profile -> 'video' ->> 'max_long_side_px') ~ '^[0-9]{1,5}$'
             and (p_profile -> 'video' ->> 'max_long_side_px')::integer
                 between 1 and 10000))
    -- Фото товара: сколько принимает и как называет в указании.
    and jsonb_typeof(p_profile -> 'images') = 'object'
    and (select array_agg(key order by key)
         from jsonb_object_keys(p_profile -> 'images') key)
        = array['max', 'style']
    and (p_profile -> 'images' ->> 'max') ~ '^[0-9]{1,2}$'
    and (p_profile -> 'images' ->> 'max')::integer between 0 and 30
    and (p_profile -> 'images' ->> 'style')
        in ('none', 'region', 'at_refs', 'named_refs')
    -- Без фото нет и ссылок; со ссылками должно быть хоть одно фото.
    and (((p_profile -> 'images' ->> 'max')::integer = 0)
         = ((p_profile -> 'images' ->> 'style') = 'none')), false);
$$;

alter table content_factory.generation_strategy_provider_routes
  add column if not exists input_profile jsonb not null default
    '{"video": {"min_seconds": 1, "max_seconds": 60, "min_short_side_px": null, "max_long_side_px": null}, "images": {"max": 0, "style": "none"}, "keeps_source_audio": false}'::jsonb;
alter table content_factory.generation_strategy_provider_routes
  drop constraint if exists
    generation_strategy_provider_routes_input_profile_check;
alter table content_factory.generation_strategy_provider_routes
  add constraint generation_strategy_provider_routes_input_profile_check
  check (content_factory_private.generation_strategy_input_profile_valid(
    input_profile
  ));

-- Существующие строки получают честные значения.
update content_factory.generation_strategy_provider_routes as route
set engine_family = 'edit',
    input_profile = jsonb_build_object(
      'video', jsonb_build_object(
        'min_seconds', 4, 'max_seconds', 15,
        'min_short_side_px', null, 'max_long_side_px', null
      ),
      'images', jsonb_build_object('max', 0, 'style', 'none'),
      'keeps_source_audio', false
    ),
    updated_at = now()
where route.provider = 'runway' and route.model_key = 'aleph2';

update content_factory.generation_strategy_provider_routes as route
set engine_family = 'edit',
    input_profile = jsonb_build_object(
      'video', jsonb_build_object(
        'min_seconds', 1, 'max_seconds', 15,
        'min_short_side_px', null, 'max_long_side_px', null
      ),
      'images', jsonb_build_object('max', 1, 'style', 'region'),
      'keeps_source_audio', true
    ),
    updated_at = now()
where route.provider = 'fal' and route.model_key = 'fal-ai/pika/v2/pikaswaps';

update content_factory.generation_strategy_provider_routes as route
set engine_family = 'edit',
    input_profile = jsonb_build_object(
      'video', jsonb_build_object(
        'min_seconds', 3, 'max_seconds', 15,
        'min_short_side_px', 720, 'max_long_side_px', 3840
      ),
      'images', jsonb_build_object('max', 4, 'style', 'at_refs'),
      'keeps_source_audio', true
    ),
    updated_at = now()
where route.provider = 'fal'
  and route.model_key = 'fal-ai/kling-video/o3/pro/video-to-video/edit';

update content_factory.generation_strategy_provider_routes as route
set engine_family = 'overlay',
    input_profile = jsonb_build_object(
      'video', jsonb_build_object(
        'min_seconds', 3, 'max_seconds', 60,
        'min_short_side_px', null, 'max_long_side_px', null
      ),
      'images', jsonb_build_object('max', 0, 'style', 'none'),
      'keeps_source_audio', true
    ),
    updated_at = now()
where route.provider = 'heygen';

-- 3. Список исполнимых пар: четыре новых движка «Копии».
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
    -- Движки «Копии», заведённые 23.08.2026.
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
    -- «Создание» на своём рецептном адресе: на правку видео не переводилось.
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'runway'
     and p_model_key = 'gen4_turbo'
      then p_provider_path = '/v1/recipes/product_ad'
       and p_poll_kind = 'runway_task'
       and p_pricing_version = 'runway-recipe-credits-2026-08-14.v1'
    else false
  end, false);
$$;

-- 4. Рубильник платного запуска по паре provider:model. Тело функции живёт в
--    202608130002 и патчится по якорю, как в 202608180009: якорь — ветка
--    Kling O3 Pro, четыре новые ветки встают рядом.
do $launch_gate_copy_engines$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text :=
    $f$when 'fal:fal-ai/kling-video/o3/pro/video-to-video/edit' then true$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  if definition_value is null then
    raise exception using message = 'launch_gate_missing';
  end if;
  if position('fal:minimax/h3/reference-to-video' in definition_value) > 0 then
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
    when 'fal:fal-ai/kling-video/o3/standard/video-to-video/edit' then true
    when 'fal:alibaba/happy-horse/video-edit' then true
    when 'fal:bytedance/seedance-2.5/reference-to-video' then true
    when 'fal:minimax/h3/reference-to-video' then true$r$
  );
  if position('fal:minimax/h3/reference-to-video' in patched_value) = 0 then
    raise exception using message = 'launch_gate_patch_failed';
  end if;
  execute patched_value;
end;
$launch_gate_copy_engines$;

-- 5. Строки реестра. Все четыре включены: ставки сверены, формы тел и
--    исполнимые маршруты заведены в коде этим же заходом. Рекомендованный
--    маршрут не меняется — это глобальный флаг «по умолчанию», а совет под
--    конкретный ролик даёт ИИ-центр.
insert into content_factory.generation_strategy_provider_routes (
  strategy_id, provider, model_key, provider_path, poll_kind,
  pricing_version, price_kind, price_rate_minor,
  min_duration_seconds, max_duration_seconds, tier,
  quality_modes, duration_source, engine_family, input_profile,
  recommended, enabled, verified_rate_at, notes
)
values
(
  'viral_product_swap', 'fal',
  'fal-ai/kling-video/o3/standard/video-to-video/edit',
  'fal-ai/kling-video/o3/standard/video-to-video/edit', 'fal_request',
  'fal-usd-per-second-kling-standard-2026-08-23.v1', 'usd_minor_per_second', 13,
  3, 15, 'cheap',
  '[{"code": "source", "label": "Как в исходнике", "resolution": "720p"}]'::jsonb,
  'source_video', 'edit',
  '{"video": {"min_seconds": 3, "max_seconds": 15, "min_short_side_px": 720, "max_long_side_px": 3840}, "images": {"max": 4, "style": "at_refs"}, "keeps_source_audio": true}'::jsonb,
  false, true, now(),
  'Kling O3 Standard video-to-video edit: та же правка видео, что у O3 Pro, уровнем ниже. $0.126/с результата (fal.ai/models/…/o3/standard/video-to-video/edit, 23.08.2026), в реестре 13¢ — округление вверх. Вход: видео 3–15 с, обе стороны ≥720px, до 4 фото вместе с элементами.'
),
(
  'viral_product_swap', 'fal',
  'alibaba/happy-horse/video-edit',
  'alibaba/happy-horse/video-edit', 'fal_request',
  'fal-usd-per-second-happy-horse-2026-08-23.v1', 'usd_minor_per_second', 14,
  3, 15, 'medium',
  '[{"code": "source", "label": "Как в исходнике", "resolution": "720p"}]'::jsonb,
  'source_video', 'edit',
  '{"video": {"min_seconds": 3, "max_seconds": 15, "min_short_side_px": 320, "max_long_side_px": 2160}, "images": {"max": 5, "style": "at_refs"}, "keeps_source_audio": true}'::jsonb,
  false, true, now(),
  'Happy Horse video-edit: правка готового ролика по описанию с опорой на фото товара (@Image1…@Image5). $0.14/с при 720p (fal.ai/models/alibaba/happy-horse/video-edit, 23.08.2026); 1080p стоит $0.28/с и отдельной строкой не заведён. Результат не длиннее 15 с, исходный звук сохраняется.'
),
(
  'viral_product_swap', 'fal',
  'bytedance/seedance-2.5/reference-to-video',
  'bytedance/seedance-2.5/reference-to-video', 'fal_request',
  'fal-usd-per-second-bytedance-2-5-2026-08-23.v1', 'usd_minor_per_second', 58,
  4, 15, 'premium',
  '[{"code": "source", "label": "Как в исходнике", "resolution": "720p"}]'::jsonb,
  'source_video', 'edit',
  '{"video": {"min_seconds": 4, "max_seconds": 15, "min_short_side_px": 300, "max_long_side_px": 6000}, "images": {"max": 6, "style": "at_refs"}, "keeps_source_audio": false}'::jsonb,
  false, true, now(),
  'Seedance 2.5 reference-to-video: страница обещает замену объекта с сохранением движения и камеры (@Video1, @Image1…). Цена по токенам h·w·(вход+выход)·24/1024 × $0.0214/1000 × 0.6 при видео-референсе; при 720p и выходе длиной с вход ≈ $0.555/с → 58¢ с запасом. Самый дорогой движок «Копии»: 12 с ≈ $7. Звук не генерируется (generate_audio = false).'
),
(
  'viral_product_swap', 'fal',
  'minimax/h3/reference-to-video',
  'minimax/h3/reference-to-video', 'fal_request',
  'fal-usd-per-second-minimax-h3-2026-08-23.v1', 'usd_minor_per_second', 6,
  5, 15, 'cheap',
  '[{"code": "source", "label": "Как в исходнике", "resolution": "720p"}]'::jsonb,
  'operator_choice', 'regenerate',
  '{"video": {"min_seconds": 5, "max_seconds": 15, "min_short_side_px": null, "max_long_side_px": null}, "images": {"max": 5, "style": "named_refs"}, "keeps_source_audio": false}'::jsonb,
  false, true, now(),
  'MiniMax H3 reference-to-video: ПЕРЕСБОРКА ролика по движению референса (Video 1) с товаром с фото (Image 1…, первые пять бесплатны, дальше $0.08/фото). $0.06/с при 768P (fal.ai/models/minimax/h3/reference-to-video, 23.08.2026); 2K/4K — апскейл дороже, не заведены. Длительность выбирает оператор, 5–15 с.'
)
on conflict (strategy_id, provider, model_key) do nothing;

-- 6. Витрина каталога отдаёт новые свойства маршрута: экран объясняет
--    человеку, что движок принимает и что он делает с роликом, а ИИ-центр
--    советует по тем же полям. Патч по якорю, как в 202608190008.
do $catalog_engine_profile$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text :=
    $f$'duration_source', route.duration_source,$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_catalog_policy';
  if definition_value is null then
    raise exception using message = 'catalog_policy_missing';
  end if;
  if position('input_profile' in definition_value) > 0 then
    return;
  end if;
  anchor_hits := (
    length(definition_value)
    - length(replace(definition_value, anchor_text, ''))
  ) / length(anchor_text);
  if anchor_hits <> 1 then
    raise exception using
      message = 'catalog_policy_anchor_not_unique:' || anchor_hits::text;
  end if;
  patched_value := replace(
    definition_value,
    anchor_text,
    anchor_text || '
              ''engine_family'', route.engine_family,
              ''input_profile'', route.input_profile,'
  );
  if position('input_profile' in patched_value) = 0 then
    raise exception using message = 'catalog_policy_patch_failed';
  end if;
  execute patched_value;
end;
$catalog_engine_profile$;

revoke all on function
  public.system_generation_strategy_catalog_policy(jsonb)
  from public, anon, authenticated;
grant execute on function
  public.system_generation_strategy_catalog_policy(jsonb)
  to service_role;

revoke all on function
  content_factory_private.generation_strategy_input_profile_valid(jsonb)
  from public, anon, authenticated;

-- 7. Проверка.
do $copy_engines_verify$
declare
  swap_rows integer;
  enabled_rows integer;
  signatures integer;
  launch_ok boolean;
  policy_value jsonb;
begin
  select count(*), count(*) filter (where enabled)
    into swap_rows, enabled_rows
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_product_swap';
  if swap_rows <> 7 or enabled_rows <> 7 then
    raise exception using message =
      'copy_engines_route_count_invalid:' || swap_rows::text || '/'
      || enabled_rows::text;
  end if;

  -- Подпись маршрута (provider, pricing_version) среди включённых уникальна.
  select count(distinct (provider, pricing_version)) into signatures
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_product_swap' and enabled;
  if signatures <> enabled_rows then
    raise exception using message =
      'copy_engines_signature_collision:' || signatures::text;
  end if;

  if exists (
    select 1
    from content_factory.generation_strategy_provider_routes route
    where route.strategy_id = 'viral_product_swap'
      and not content_factory_private.generation_strategy_provider_route_allowed(
        route.strategy_id, route.provider, route.model_key,
        route.provider_path, route.poll_kind, route.pricing_version
      )
  ) then
    raise exception using message = 'copy_engines_route_not_allowed';
  end if;

  if exists (
    select 1
    from content_factory.generation_strategy_provider_routes route
    where route.recommended
    group by route.strategy_id
    having count(*) > 1
  ) then
    raise exception using message = 'copy_engines_recommended_not_unique';
  end if;

  select pg_get_functiondef(p.oid) like '%fal:minimax/h3/reference-to-video%'
    into launch_ok
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  if not coalesce(launch_ok, false) then
    raise exception using message = 'copy_engines_launch_gate_missing';
  end if;

  if position('input_profile' in pg_get_functiondef(
       'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
     )) = 0 then
    raise exception using message = 'copy_engines_catalog_policy_missing';
  end if;

  if not content_factory_private.generation_strategy_input_profile_valid(
    '{"video": {"min_seconds": 3, "max_seconds": 15, "min_short_side_px": 720, "max_long_side_px": 3840}, "images": {"max": 4, "style": "at_refs"}, "keeps_source_audio": true}'::jsonb
  ) or content_factory_private.generation_strategy_input_profile_valid(
    '{"video": {"min_seconds": 3, "max_seconds": 15, "min_short_side_px": 720, "max_long_side_px": 3840}, "images": {"max": 0, "style": "at_refs"}, "keeps_source_audio": true}'::jsonb
  ) then
    raise exception using message = 'copy_engines_input_profile_check_invalid';
  end if;
end;
$copy_engines_verify$;

commit;
