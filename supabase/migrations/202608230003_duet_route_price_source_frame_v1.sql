begin;

-- 202608230003_duet_route_price_source_frame_v1
--
-- «Дуэт»: кадр из исходника доводится до ВТОРОГО расчёта цены.
--
-- Миграция 202608220014 починила кадр только в
-- `generation_strategy_recipe_price` — той, что отвечает про ДЕЙСТВУЮЩИЙ
-- маршрут. Но есть второй путь: `generation_strategy_route_price` отвечает про
-- маршрут, ЯВНО НАЗВАННЫЙ оператором (ключ `engine` в привязке). В ней остался
-- прежний расчёт: у дуэта требовалась вертикаль 720:1280 или 1080:1920.
--
-- Следствие, пока это не исправлено: как только маршрут «Дуэта» включат,
-- операторский выбор движка для него не заработает никогда — цена будет NULL, а
-- причина не будет названа нигде.
--
-- Замена ДОСЛОВНО повторяет ту, что уже сделана в `recipe_price`. Это её
-- главное достоинство: две функции, отвечающие на один вопрос «годится ли этот
-- кадр этой стратегии», обязаны отвечать одинаково. Расхождение между ними и
-- есть та поломка, которую чинит этот файл.

do $duet_route_price_frame$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_strategy_route_price(text,text,text,integer,text,text,boolean)'
      ::regprocedure
  );
  -- Та же страховка от повторного прогона, что и в 202608220014.
  if position('p_strategy_id in (''viral_avatar_ugc'', ''viral_product_swap'')'
              in source_text) > 0 then
    return;
  end if;

  anchor := E'     or (\n'
         || E'       p_strategy_id = ''viral_avatar_ugc''\n'
         || E'       and p_ratio <> case p_resolution\n'
         || E'         when ''720p'' then ''720:1280'' else ''1080:1920'' end\n'
         || E'     )\n'
         || E'     or (p_strategy_id = ''viral_product_swap'' and p_ratio <> ''source'')';
  if (length(source_text) - length(replace(source_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_route_price_anchor_frame';
  end if;
  patched_text := replace(
    source_text,
    anchor,
    E'     or (\n'
      || E'       p_strategy_id in (''viral_avatar_ugc'', ''viral_product_swap'')\n'
      || E'       and p_ratio <> ''source''\n'
      || E'     )'
  );
  execute patched_text;
end;
$duet_route_price_frame$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
--
-- Маршрутная цена отвечает NULL у ВЫКЛЮЧЕННОГО маршрута — и это верно само по
-- себе, но проверить кадр так нельзя: отказ придёт раньше, по другой причине.
-- Поэтому маршрут «Дуэта» включается ВНУТРИ вложенного блока, который затем
-- намеренно прерывается: строки откатываются, а значения переменных остаются.
-- Переменные PL/pgSQL не транзакционны, и это здесь используется сознательно.
--
-- Так проверяется именно то, что чинится, — кадр, — и ничего сверх того.
-- Включение маршрута остаётся отдельным решением отдельного файла.
do $duet_route_price_verify$
declare
  source_frame_ok boolean := null;
  vertical_refused boolean := null;
  duration_floor_refused boolean := null;
  duration_ceiling_refused boolean := null;
begin
  begin
    update content_factory.generation_strategy_provider_routes
      set enabled = true
    where strategy_id = 'viral_avatar_ugc'
      and provider = 'heygen'
      and model_key = 'avatar_v3';

    source_frame_ok := content_factory_private.generation_strategy_route_price(
      'viral_avatar_ugc', 'heygen', 'avatar_v3', 8, '720p', 'source', true
    ) is not null;

    vertical_refused := content_factory_private.generation_strategy_route_price(
      'viral_avatar_ugc', 'heygen', 'avatar_v3', 8, '720p', '720:1280', true
    ) is null;

    -- Пределы длительности берутся у строки реестра (3..60) и кадром не
    -- отменяются: проверяем, что починка кадра их не размыла.
    duration_floor_refused :=
      content_factory_private.generation_strategy_route_price(
        'viral_avatar_ugc', 'heygen', 'avatar_v3', 2, '720p', 'source', true
      ) is null;
    duration_ceiling_refused :=
      content_factory_private.generation_strategy_route_price(
        'viral_avatar_ugc', 'heygen', 'avatar_v3', 61, '720p', 'source', true
      ) is null;

    raise exception using errcode = '40000', message = 'duet_route_price_probe';
  exception when sqlstate '40000' then
    null;
  end;

  if source_frame_ok is not true then
    raise exception using message = 'duet_route_price_refuses_source_frame';
  end if;
  if vertical_refused is not true then
    raise exception using message = 'duet_route_price_still_takes_vertical';
  end if;
  if duration_floor_refused is not true
     or duration_ceiling_refused is not true then
    raise exception using message = 'duet_route_price_duration_bounds_lost';
  end if;

  -- Маршрут обязан остаться ВЫКЛЮЧЕННЫМ: проба его включала, но откатилась.
  -- Если это утверждение однажды упадёт, значит проба перестала откатываться —
  -- и маршрут дуэта оказался открыт файлом, который этого не обещал.
  if exists (
    select 1
    from content_factory.generation_strategy_provider_routes
    where strategy_id = 'viral_avatar_ugc' and enabled
  ) then
    raise exception using message = 'duet_route_left_enabled_by_probe';
  end if;

  -- «Копия» не тронута: её маршруты включены, кадр как был "source", так и
  -- остался, а вертикаль по-прежнему отвергается.
  if content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
       8, '720p', 'source', true
     ) is null then
    raise exception using message = 'product_swap_route_price_broke';
  end if;
  if content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
       8, '720p', '720:1280', true
     ) is not null then
    raise exception using message = 'product_swap_route_price_took_vertical';
  end if;

  -- «Создание» не тронуто: у него кадр как раз ВЫБИРАЕТСЯ, и список вертикалей
  -- обязан остаться рабочим. Строк реестра у него нет вовсе, поэтому
  -- спрашиваем рецептную функцию — ту, что отвечает про каталожный маршрут.
  if content_factory_private.generation_strategy_recipe_price(
       'viral_rebuild', 8, '720p', '720:1280', true
     ) is null then
    raise exception using message = 'viral_rebuild_price_broke';
  end if;
  if content_factory_private.generation_strategy_recipe_price(
       'viral_rebuild', 8, '720p', 'source', true
     ) is not null then
    raise exception using message = 'viral_rebuild_started_taking_source_frame';
  end if;
end;
$duet_route_price_verify$;

commit;
