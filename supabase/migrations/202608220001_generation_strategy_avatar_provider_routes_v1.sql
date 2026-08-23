begin;

-- 202608220001_generation_strategy_avatar_provider_routes_v1
--
-- Третий шаг перевода «Аватара» на правку видео (после 202608210004 и
-- 202608210005). Заводятся строки реестра маршрутов — ровно те же три движка,
-- что у «Копии», потому что операция теперь одна и та же: заменить объект в
-- готовом ролике. У «Копии» это товар, у «Аватара» — человек.
--
-- ПОЧЕМУ СТАВКИ НЕ ТРЕБУЮТ НОВОЙ СВЕРКИ. Ставка — свойство МОДЕЛИ, а не
-- рецепта: Pika берёт за ролик целиком независимо от содержимого, Kling и Aleph
-- считают секунды результата. Модели те же самые, значит и суммы те же,
-- сверенные 18.08.2026 по страницам провайдеров. Поэтому verified_rate_at
-- заполняется честно, а не для обхода ограничения.
--
-- ВСЕ ТРИ ЗАВЕДЕНЫ ВЫКЛЮЧЕННЫМИ. Это не осторожность ради осторожности:
-- enabled = false означает, что расчёт готовности в браузере держит модуль
-- заблокированным, а платный старт недостижим. При этом каскад уже показывает
-- лестницу движков с ценами — оператор видит, что будет, и не может это
-- запустить. Включение маршрута — отдельное решение и отдельная миграция.
--
-- recommended у всех трёх тоже false: «действующим» маршрутом считается строка
-- recommended AND enabled, и пока такой нет, цена стратегии считается прежней
-- рунвеевской формулой — то есть ничего не меняется до явного включения.
--
-- МОДЕЛЬ RUNWAY — aleph2, А НЕ gen4_turbo. Точный список исполнимых пар до сих
-- пор называл для «Аватара» модель gen4_turbo, но адаптер собирает тело с
-- model: "aleph2" — это видно в buildProductUgc. Расхождение осталось от
-- рецептного прошлого и здесь устраняется: список приводится к тому, что код
-- действительно отправляет. Разойдись они — отправка отбилась бы сверкой
-- конверта уже после резервирования денег.

-- 1. Точный список исполнимых пар: у «Аватара» появляются три маршрута.
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
set search_path = ''
as $$
  select coalesce(case
    -- «Аватар»: правка готового ролика теми же тремя движками, что и «Копия».
    when p_strategy_id = 'viral_avatar_ugc'
     and p_provider = 'runway'
     and p_model_key = 'aleph2'
      then p_provider_path = '/v1/video_to_video'
       and p_poll_kind = 'runway_task'
       and p_pricing_version = 'runway-recipe-credits-2026-08-14.v1'
    when p_strategy_id = 'viral_avatar_ugc'
     and p_provider = 'fal'
     and p_model_key = 'fal-ai/pika/v2/pikaswaps'
      then p_provider_path = 'fal-ai/pika/v2/pikaswaps'
       and p_poll_kind = 'fal_request'
       and p_pricing_version = 'fal-usd-per-run-2026-08-18.v1'
    when p_strategy_id = 'viral_avatar_ugc'
     and p_provider = 'fal'
     and p_model_key =
       'fal-ai/kling-video/o3/pro/video-to-video/edit'
      then p_provider_path =
        'fal-ai/kling-video/o3/pro/video-to-video/edit'
       and p_poll_kind = 'fal_request'
       and p_pricing_version = 'fal-usd-per-second-2026-08-18.v1'
    -- «Копия» — без изменений.
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
    -- «Создание» остаётся на своём рецептном адресе: на правку видео оно не
    -- переводилось, и трогать его здесь нельзя.
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'runway'
     and p_model_key = 'gen4_turbo'
      then p_provider_path = '/v1/recipes/product_ad'
       and p_poll_kind = 'runway_task'
       and p_pricing_version = 'runway-recipe-credits-2026-08-14.v1'
    else false
  end, false);
$$;

-- 2. Сами строки реестра. quality_modes задаются явно: колонка объявлена с
-- умолчанием '[]', а ограничение требует от одного до шести режимов, поэтому
-- вставка без явного значения упёрлась бы в CHECK.
insert into content_factory.generation_strategy_provider_routes (
  strategy_id, provider, model_key, provider_path, poll_kind,
  pricing_version, price_kind, price_rate_minor,
  min_duration_seconds, max_duration_seconds, tier,
  quality_modes, duration_source, recommended, enabled, verified_rate_at, notes
)
values
  (
    'viral_avatar_ugc', 'fal', 'fal-ai/pika/v2/pikaswaps',
    'fal-ai/pika/v2/pikaswaps', 'fal_request',
    'fal-usd-per-run-2026-08-18.v1', 'usd_minor_per_run', 47,
    1, 15, 'cheap',
    '[{"code": "source", "label": "Как в исходнике", "resolution": "720p"}]'::jsonb,
    'source_video', false, false, now(),
    'Замена человека по одному фото аватара: video_url + image_url + область словами. Ставка модели — $0.465 за ролик целиком, резервируем 47 центов. Режим «Описание аватара» этой моделью неисполним: image_url обязателен.'
  ),
  (
    'viral_avatar_ugc', 'fal',
    'fal-ai/kling-video/o3/pro/video-to-video/edit',
    'fal-ai/kling-video/o3/pro/video-to-video/edit', 'fal_request',
    'fal-usd-per-second-2026-08-18.v1', 'usd_minor_per_second', 17,
    3, 15, 'medium',
    '[{"code": "source", "label": "Как в исходнике", "resolution": "720p"}]'::jsonb,
    'source_video', false, false, now(),
    'Правка по описанию с ракурсами аватара: до четырёх изображений. Платится посекундно, поэтому длительность задаёт исходник. Режим «Описание аватара» неисполним: ссылки @ImageN должны на что-то указывать.'
  ),
  (
    'viral_avatar_ugc', 'runway', 'aleph2',
    '/v1/video_to_video', 'runway_task',
    'runway-recipe-credits-2026-08-14.v1', 'runway_credit_tiers', null,
    4, 15, 'premium',
    '[{"code": "standard", "label": "Стандарт", "resolution": "720p"}, {"code": "max", "label": "Максимум", "resolution": "1080p"}]'::jsonb,
    'operator_choice', false, false, now(),
    'Переписывает кадр по описанию. ЕДИНСТВЕННЫЙ маршрут для режима «Описание аватара»: принимает только текст, фотографию не берёт. Риск — удержание лица: тот же движок дважды не удержал мелкие детали товара.'
  )
on conflict (strategy_id, provider, model_key) do nothing;

do $avatar_routes_verify$
declare
  avatar_rows integer;
  enabled_rows integer;
  recommended_rows integer;
  swap_rows integer;
begin
  select count(*) into avatar_rows
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_avatar_ugc';
  if avatar_rows <> 3 then
    raise exception using message = 'avatar_routes_count_invalid:' || avatar_rows::text;
  end if;

  -- Ни один маршрут «Аватара» не включён и не рекомендован: платный старт по
  -- этой стратегии обязан оставаться недостижимым до отдельного решения.
  select count(*) into enabled_rows
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_avatar_ugc' and enabled;
  if enabled_rows <> 0 then
    raise exception using message = 'avatar_route_enabled_too_early';
  end if;
  select count(*) into recommended_rows
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_avatar_ugc' and recommended;
  if recommended_rows <> 0 then
    raise exception using message = 'avatar_route_recommended_too_early';
  end if;

  -- «Копия» не тронута: три строки, действующий маршрут на месте.
  select count(*) into swap_rows
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_product_swap' and enabled;
  if swap_rows <> 3 then
    raise exception using message = 'product_swap_routes_drifted:' || swap_rows::text;
  end if;
  if not exists (
    select 1 from content_factory.generation_strategy_provider_routes
    where strategy_id = 'viral_product_swap'
      and recommended and enabled
      and model_key = 'fal-ai/pika/v2/pikaswaps'
  ) then
    raise exception using message = 'product_swap_active_route_lost';
  end if;

  -- Список исполнимых пар: аватар теперь исполним всеми тремя, «Создание» —
  -- по-прежнему только своим рецептным адресом.
  if not content_factory_private.generation_strategy_provider_route_allowed(
       'viral_avatar_ugc', 'runway', 'aleph2', '/v1/video_to_video',
       'runway_task', 'runway-recipe-credits-2026-08-14.v1'
     ) then
    raise exception using message = 'avatar_runway_route_not_allowed';
  end if;
  if not content_factory_private.generation_strategy_provider_route_allowed(
       'viral_avatar_ugc', 'fal', 'fal-ai/pika/v2/pikaswaps',
       'fal-ai/pika/v2/pikaswaps', 'fal_request',
       'fal-usd-per-run-2026-08-18.v1'
     ) then
    raise exception using message = 'avatar_pika_route_not_allowed';
  end if;
  if content_factory_private.generation_strategy_provider_route_allowed(
       'viral_avatar_ugc', 'runway', 'gen4_turbo', '/v1/video_to_video',
       'runway_task', 'runway-recipe-credits-2026-08-14.v1'
     ) then
    raise exception using message = 'avatar_stale_model_still_allowed';
  end if;
  if not content_factory_private.generation_strategy_provider_route_allowed(
       'viral_rebuild', 'runway', 'gen4_turbo', '/v1/recipes/product_ad',
       'runway_task', 'runway-recipe-credits-2026-08-14.v1'
     ) then
    raise exception using message = 'rebuild_route_lost';
  end if;
end;
$avatar_routes_verify$;

commit;
