begin;

-- 202608220011_duet_heygen_route_v1
--
-- Маршрут «Дуэта»: ведущий у HeyGen.
--
-- ЗАОДНО УБИРАЮТСЯ ТРИ ЧУЖИХ МАРШРУТА. В 202608220001 я завёл «Аватару» те же
-- три движка, что у «Копии» — Pika, Kling и Aleph. Основанием было моё тогдашнее
-- понимание задачи: замена человека в кадре. Владелец уточнил операцию — это
-- ДУЭТ: исходник остаётся собой, а снизу врезается говорящий комментатор.
--
-- Все три движка правят КАДР и ни один не добавляет комментатора. Оставить их
-- в списке исполнимых значило бы держать заряженным путь к не той операции:
-- строки выключены, но выключенное включают, а список исполнимых пар — это
-- утверждение «так можно», и оно было бы ложным.
--
-- ЦЕНА. HeyGen считает готовое видео ведущего посекундно: $0.05/сек для Photo
-- Avatar по официальному прайсу API (developers.heygen.com/docs/pricing,
-- сверено 22.08.2026). Ставка 5 центов за секунду.
--
-- ДЛИТЕЛЬНОСТЬ ЗАДАЁТ ИСХОДНИК. Комментатор говорит ровно столько, сколько идёт
-- ролик, который он комментирует. Поэтому duration_source = 'source_video', и
-- защита посекундной ставки из 202608190008 накрывает этот маршрут той же
-- проверкой, что и Kling: длительность обязана совпасть с измеренной сервером
-- длиной исходника, иначе отказ ДО денег.
--
-- МАРШРУТ ЗАВЕДЁН ВЫКЛЮЧЕННЫМ. Ключа в окружении ещё нет, ведущего в проекте
-- ещё нет, форма ещё не умеет его выбирать. Включение — отдельное решение.

-- 1. Список исполнимых пар: у «Дуэта» остаётся один маршрут вместо трёх чужих.
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
    -- «Дуэт»: ведущий у HeyGen. Модель — это движок аватара провайдера, путь
    -- отправки один на все запросы, статус забирается по идентификатору задачи.
    when p_strategy_id = 'viral_avatar_ugc'
     and p_provider = 'heygen'
     and p_model_key = 'avatar_v3'
      then p_provider_path = '/v3/videos'
       and p_poll_kind = 'heygen_video'
       and p_pricing_version = 'heygen-usd-per-second-2026-08-22.v1'
    -- «Копия» — без изменений, три сверенных движка.
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

-- 2. Прежние строки «Аватара» удаляются: они описывают не ту операцию.
-- Удаление безопасно — ни одна из них никогда не была включена и ни один запуск
-- на них не ссылается.
do $duet_route_cleanup$
declare
  used integer;
begin
  select count(*) into used
  from content_factory.generation_strategy_readiness_receipts receipt
  where receipt.strategy_id = 'viral_avatar_ugc';
  if used <> 0 then
    raise exception using message =
      'avatar_routes_referenced_by_receipts:' || used::text;
  end if;

  delete from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_avatar_ugc'
    and provider <> 'heygen';
end;
$duet_route_cleanup$;

-- 3. Строка маршрута «Дуэта».
insert into content_factory.generation_strategy_provider_routes (
  strategy_id, provider, model_key, provider_path, poll_kind,
  pricing_version, price_kind, price_rate_minor,
  min_duration_seconds, max_duration_seconds, tier,
  quality_modes, duration_source, recommended, enabled, verified_rate_at, notes
)
values (
  'viral_avatar_ugc', 'heygen', 'avatar_v3',
  '/v3/videos', 'heygen_video',
  'heygen-usd-per-second-2026-08-22.v1', 'usd_minor_per_second', 5,
  -- Ведущему нужно успеть сказать осмысленную фразу, но комментарий длиннее
  -- минуты перестаёт быть комментарием. Пределы наши, не провайдерские.
  3, 60, 'cheap',
  '[{"code": "source", "label": "Как в исходнике", "resolution": "720p"}]'::jsonb,
  'source_video', false, false, now(),
  'Говорящий ведущий для дуэта: комментатор врезается в угол, исходник не изменяется. $0.05/сек Photo Avatar. Личность закреплена avatar_id на стороне провайдера — один и тот же человек во всех роликах проекта. Отдаёт webm с прозрачным фоном.'
)
on conflict (strategy_id, provider, model_key) do nothing;

do $duet_route_verify$
declare
  avatar_rows integer;
  swap_rows integer;
begin
  select count(*) into avatar_rows
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_avatar_ugc';
  if avatar_rows <> 1 then
    raise exception using message = 'duet_route_count_invalid:' || avatar_rows::text;
  end if;

  if not exists (
    select 1 from content_factory.generation_strategy_provider_routes
    where strategy_id = 'viral_avatar_ugc'
      and provider = 'heygen' and model_key = 'avatar_v3'
      and price_kind = 'usd_minor_per_second' and price_rate_minor = 5
      and duration_source = 'source_video'
      and not enabled and not recommended
  ) then
    raise exception using message = 'duet_route_shape_invalid';
  end if;

  -- Прежние движки больше не исполнимы для «Дуэта»: список утверждает «так
  -- можно», и это утверждение обязано быть правдой.
  if content_factory_private.generation_strategy_provider_route_allowed(
       'viral_avatar_ugc', 'fal', 'fal-ai/pika/v2/pikaswaps',
       'fal-ai/pika/v2/pikaswaps', 'fal_request',
       'fal-usd-per-run-2026-08-18.v1'
     ) then
    raise exception using message = 'duet_still_allows_frame_edit_engine';
  end if;
  if not content_factory_private.generation_strategy_provider_route_allowed(
       'viral_avatar_ugc', 'heygen', 'avatar_v3', '/v3/videos',
       'heygen_video', 'heygen-usd-per-second-2026-08-22.v1'
     ) then
    raise exception using message = 'duet_route_not_allowed';
  end if;

  -- «Копия» не тронута: три включённых движка и действующий маршрут на месте.
  select count(*) into swap_rows
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_product_swap' and enabled;
  if swap_rows <> 3 then
    raise exception using message = 'product_swap_routes_drifted:' || swap_rows::text;
  end if;
  if not exists (
    select 1 from content_factory.generation_strategy_provider_routes
    where strategy_id = 'viral_product_swap'
      and recommended and enabled and model_key = 'fal-ai/pika/v2/pikaswaps'
  ) then
    raise exception using message = 'product_swap_active_route_lost';
  end if;
end;
$duet_route_verify$;

commit;
