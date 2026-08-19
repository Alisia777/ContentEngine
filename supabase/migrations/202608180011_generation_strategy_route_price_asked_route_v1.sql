begin;

-- 202608180011_generation_strategy_route_price_asked_route_v1
--
-- Маршрутная цена начинает считать тот маршрут, который у неё спросили.
--
-- Обёртка begin/commit открывает файл первой же строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет
-- обёртку регулярным выражением от начала файла, и комментарий перед begin он
-- за обёртку не считает. Поэтому «почему» живёт внутри транзакции.
--
-- ЧТО БЫЛО СЛОМАНО. Диспетчер
-- content_factory_private.generation_strategy_route_price (202608180004) для
-- provider = 'runway' не считал ничего сам, а немедленно перенаправлял вызов в
-- generation_strategy_recipe_price. Та с 202608180006 отдаёт цену
-- ДЕЙСТВУЮЩЕГО маршрута стратегии, а не спрошенного. Пока действующим был
-- Runway, подмена совпадала с правдой и была невидима. После 202608180010
-- действующим стал Pika, и вопрос «сколько стоит десять секунд на Runway?»
-- стал получать ответ «47 центов, провайдер fal» вместо «428 центов, провайдер
-- runway». Это не просто заниженное число: подменённый снимок цены целиком
-- непротиворечив — он называет чужого провайдера, чужую версию прайса и чужую
-- строку подтверждения, — поэтому ни одна сверка ниже по течению его не
-- отвергнет. Резерв, посчитанный по такому снимку, в девять раз меньше
-- фактического списания провайдера. Это прямая дыра в бюджете, и молчаливая.
--
-- ЧТО ДЕЛАЕТ ЭТА МИГРАЦИЯ. Функция перестаёт спрашивать, кто сейчас
-- действующий, и начинает искать строку реестра ровно по тройке
-- (strategy_id, provider, model_key) — то есть по тому, что у неё спросили, —
-- и считать по price_kind и price_rate_minor НАЙДЕННОЙ строки. Отметка
-- recommended в расчёте больше не участвует ни одним условием: цена запасного
-- уровня обязана быть его собственной ценой и тогда, когда по умолчанию
-- выбран другой движок.
--
-- ПОЧЕМУ СТУПЕНИ RUNWAY ОСТАЮТСЯ ПРЕЖНЕЙ АРИФМЕТИКОЙ. У Runway прайс
-- ступенчатый: база за первые четыре секунды плюс надбавка за каждую
-- следующую, и единая ставка за секунду его не описывает — поэтому в реестре у
-- этой строки price_kind = 'runway_credit_tiers' и price_rate_minor = null
-- (ограничение generation_strategy_provider_routes_rate_shape_check). Формула
-- переносится сюда ЦИФРА В ЦИФРУ из 202608180006: ни одно число не изменено,
-- и verify-блок в конце файла сверяет результат с сегодняшними значениями до
-- цента. Ветка ступеней достаётся только рунвеевскому маршруту: приложить
-- прайс Runway к чужому провайдеру значило бы назвать его цену наугад.
--
-- ПОЧЕМУ ОТКАЗ, А НЕ ЗАПАСНАЯ ЦЕНА. Если спрошенного маршрута нет в реестре
-- или он выключен, функция возвращает null. Отказ останавливает запуск громко
-- и до денег; любая «разумная» подстановка чужой цены — это ровно тот же
-- дефект, который здесь чинится, только с другим значением по умолчанию.
--
-- ЧЕГО ЭТА МИГРАЦИЯ СОЗНАТЕЛЬНО НЕ ТРОГАЕТ. generation_strategy_recipe_price
-- остаётся ценой ДЕЙСТВУЮЩЕГО маршрута, и это правильно: она отвечает на
-- другой вопрос — «сколько стоит стратегия сейчас», — и на этом ответе висят
-- привязка, снимок выбора, квитанция готовности и клейм. Смешать два вопроса в
-- одной функции нельзя, поэтому маршрутный вопрос и получает собственный
-- честный расчёт.

create or replace function content_factory_private.generation_strategy_route_price(
  p_strategy_id text,
  p_provider text,
  p_model_key text,
  p_duration_seconds integer,
  p_resolution text,
  p_ratio text,
  p_audio boolean
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  route_row content_factory.generation_strategy_provider_routes%rowtype;
  recipe_value text;
  base_credits integer;
  incremental_credits integer;
  cost_minor_value integer;
  cost_usd_value text;
  input_mode_value text;
begin
  -- Ни один из семи входов не имеет осмысленного значения по умолчанию: пустая
  -- длительность, пустое разрешение или пустой флаг звука превратились бы в
  -- строку подтверждения, которая утверждает не то, что было спрошено. На
  -- денежном пути неполный вопрос — это отказ, а не догадка.
  if p_strategy_id is null
     or p_provider is null
     or p_model_key is null
     or p_duration_seconds is null
     or p_resolution is null
     or p_ratio is null
     or p_audio is null then
    return null;
  end if;

  -- Строка реестра именно спрошенного маршрута. Тройка
  -- (strategy_id, provider, model_key) уникальна
  -- (generation_strategy_provider_routes_identity_key), поэтому строк здесь
  -- либо одна, либо ноль. Отметка recommended не читается вовсе — в этом и
  -- состоит починка.
  select route.* into route_row
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = p_strategy_id
    and route.provider = p_provider
    and route.model_key = p_model_key;
  if route_row.id is null or route_row.enabled is not true then
    return null;
  end if;

  recipe_value := content_factory_private.generation_strategy_recipe(
    p_strategy_id
  );
  -- Допустимые сочетания разрешения и кадра перенесены из
  -- generation_strategy_recipe_price без изменений: рецепт один и тот же, каким
  -- бы движком его ни исполняли, поэтому и решётка допустимых кадров у него
  -- одна. Пределы длительности, наоборот, берутся у строки реестра: это
  -- свойство конкретной модели (у Kling это десять секунд, у Runway —
  -- пятнадцать), а не рецепта.
  if recipe_value is null
     or p_duration_seconds not between route_row.min_duration_seconds
       and route_row.max_duration_seconds
     or p_resolution not in ('720p', '1080p')
     or (
       p_strategy_id = 'viral_avatar_ugc'
       and p_ratio <> case p_resolution
         when '720p' then '720:1280' else '1080:1920' end
     )
     or (p_strategy_id = 'viral_product_swap' and p_ratio <> 'source')
     or (
       p_strategy_id = 'viral_rebuild'
       and not (
         (p_resolution = '720p' and p_ratio in (
           '1280:720', '720:1280', '960:960', '834:1112'
         ))
         or
         (p_resolution = '1080p' and p_ratio in (
           '1920:1080', '1080:1920', '1440:1440', '1248:1664'
         ))
       )
     ) then
    return null;
  end if;

  if route_row.price_kind = 'runway_credit_tiers' then
    -- Ступени существуют только у Runway. Строка реестра с этим прайсом, но
    -- другим провайдером — рассогласование данных, а не повод посчитать
    -- чью-то цену по чужой таблице: отказываем.
    if p_provider <> 'runway' then
      return null;
    end if;
    -- Собственная область определения формулы: база названа «за четыре
    -- секунды», и на трёх секундах надбавка стала бы отрицательной. Пределы
    -- реестра сегодня совпадают с этими четырьмя и пятнадцатью, но проверяются
    -- обе границы — данные могут разъехаться, арифметика не должна.
    if p_duration_seconds not between 4 and 15 then
      return null;
    end if;
    base_credits := case p_strategy_id
      when 'viral_avatar_ugc' then
        case p_resolution when '720p' then 192 else 208 end
      when 'viral_product_swap' then
        case p_resolution when '720p' then 212 else 228 end
      when 'viral_rebuild' then
        case p_resolution when '720p' then 200 else 216 end
    end;
    incremental_credits := case p_resolution
      when '720p' then 36 else 40 end;
    cost_minor_value := base_credits
      + ((p_duration_seconds - 4) * incremental_credits);
  else
    -- Маршрут с собственной ставкой: центы за ролик целиком либо центы за
    -- секунду результата. Инвариант «кредит Runway = цент» позволяет класть
    -- одно и то же число и в estimated_credits, и в estimated_cost_minor.
    cost_minor_value := case route_row.price_kind
      when 'usd_minor_per_run' then route_row.price_rate_minor
      when 'usd_minor_per_second' then
        route_row.price_rate_minor * p_duration_seconds
      else null
    end;
  end if;
  if cost_minor_value is null or cost_minor_value <= 0 then
    return null;
  end if;

  cost_usd_value := to_char(
    cost_minor_value::numeric / 100::numeric, 'FM999990.00'
  );
  input_mode_value := case p_strategy_id
    when 'viral_avatar_ugc' then 'character_and_product_images'
    when 'viral_product_swap' then 'video_and_product_images'
    when 'viral_rebuild' then 'product_images'
  end;

  return jsonb_build_object(
    'version', 'generation-strategy-price-snapshot-v1',
    'strategy_id', p_strategy_id,
    'provider', p_provider,
    'recipe', recipe_value,
    'input_mode', input_mode_value,
    'duration_seconds', p_duration_seconds,
    'resolution', p_resolution,
    'ratio', p_ratio,
    'audio', p_audio,
    'estimated_credits', cost_minor_value,
    'estimated_pre_tax_usd_minor', cost_minor_value,
    'estimated_cost_minor', cost_minor_value,
    'estimated_cost_usd', cost_usd_value,
    'currency', 'USD',
    'credit_unit_cost_minor', 1,
    'catalog_version', '2026-08-14.v1',
    -- Версия прайса — свойство спрошенной строки реестра, как и ставка. Взять
    -- её у действующего маршрута значило бы подписать снимок чужим именем:
    -- версия входит в хеш-подпись строки привязки и сверяется точным
    -- совпадением.
    'pricing_version', route_row.pricing_version,
    'recipe_version', '2026-06',
    -- Префикс подтверждения называет провайдера, которым за запуск платят:
    -- оператор и журнал списаний видят это в первой же букве строки.
    'spend_confirmation', concat(
      upper(p_provider), '_', upper(recipe_value), '_',
      p_duration_seconds::text, 'S_', upper(p_resolution), '_',
      case when p_audio then 'AUDIO' else 'SILENT' end,
      '_USD_', cost_usd_value
    )
  );
end;
$$;

revoke all on function
  content_factory_private.generation_strategy_route_price(
    text, text, text, integer, text, text, boolean
  )
  from public, anon, authenticated, service_role;

comment on function content_factory_private.generation_strategy_route_price(
  text, text, text, integer, text, text, boolean
) is
  'Цена запуска по СПРОШЕННОМУ маршруту реестра: строка ищется по (strategy_id, provider, model_key), расчёт идёт по её price_kind и price_rate_minor, ступени кредитов достаются только Runway. Отметка recommended не читается. Неизвестный или выключенный маршрут цены не имеет — возвращается null.';

do $route_price_asked_route_verify$
declare
  routes_before jsonb;
  routes_after jsonb;
  active_price_before jsonb;
  active_price_after jsonb;
  original_active_id uuid;
  candidate_model_key text;
  candidate_row content_factory.generation_strategy_provider_routes%rowtype;
  case_label text;
  snapshot_value jsonb;
  duration_value integer;
begin
  -- Снимок всего реестра ДО проверок. Ниже отметка действующего маршрута
  -- временно переставляется, и этот снимок — доказательство того, что к концу
  -- миграции реестр вернулся ровно в прежнее состояние, включая updated_at:
  -- перестановки нарочно не трогают эту колонку.
  select jsonb_agg(to_jsonb(route) order by route.id) into routes_before
  from content_factory.generation_strategy_provider_routes as route;
  active_price_before := content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 10, '720p', 'source', false
  );

  select route.id into original_active_id
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.recommended;

  -- Главное утверждение этой миграции — «цена спрошенного маршрута не зависит
  -- от того, кто действующий». Проверить его одним состоянием базы нельзя: до
  -- починки все числа тоже сходились, пока действующим стоял Runway. Поэтому
  -- весь набор проверок прогоняется ДВАЖДЫ — при действующем Pika и при
  -- действующем Runway, — а отметка переставляется прямо здесь, внутри
  -- транзакции, и возвращается на место после цикла.
  foreach candidate_model_key in array array[
    'fal-ai/pika/v2/pikaswaps', 'aleph2'
  ] loop
    select route.* into candidate_row
    from content_factory.generation_strategy_provider_routes as route
    where route.strategy_id = 'viral_product_swap'
      and route.model_key = candidate_model_key;
    if candidate_row.id is null or candidate_row.enabled is not true then
      raise exception using
        message = 'verify_candidate_route_missing:' || candidate_model_key;
    end if;
    case_label := candidate_row.provider || ':' || candidate_row.model_key;

    -- Отметка снимается со всех прежних и только потом ставится кандидату:
    -- частичный уникальный индекс
    -- generation_strategy_provider_routes_recommended_key не отложенный, и
    -- состояния «две отметки одновременно» не должно существовать ни на одно
    -- мгновение.
    update content_factory.generation_strategy_provider_routes as route
    set recommended = false
    where route.strategy_id = 'viral_product_swap'
      and route.recommended
      and route.id <> candidate_row.id;
    update content_factory.generation_strategy_provider_routes as route
    set recommended = true
    where route.id = candidate_row.id
      and not route.recommended;

    -- Перестановка обязана быть ДЕЙСТВЕННОЙ, иначе «оба случая» — пустая
    -- формальность: цена стратегии обязана называть провайдера кандидата.
    if content_factory_private.generation_strategy_recipe_price(
         'viral_product_swap', 10, '720p', 'source', false
       ) ->> 'provider' is distinct from candidate_row.provider then
      raise exception using
        message = 'verify_active_route_flip_ineffective:' || case_label;
    end if;

    -- 1. Runway на десяти секундах: 212 + 6 * 36 = 428, и строка подтверждения
    --    называет Runway. Это то самое число, которое до починки подменялось
    --    сорока семью центами Pika.
    snapshot_value := content_factory_private.generation_strategy_route_price(
      'viral_product_swap', 'runway', 'aleph2', 10, '720p', 'source', false
    );
    if snapshot_value is null
       or (snapshot_value ->> 'estimated_cost_minor')::integer <> 428
       or (snapshot_value ->> 'estimated_credits')::integer <> 428
       or (snapshot_value ->> 'estimated_pre_tax_usd_minor')::integer <> 428
       or snapshot_value ->> 'estimated_cost_usd' <> '4.28'
       or snapshot_value ->> 'provider' <> 'runway'
       or snapshot_value ->> 'pricing_version' <>
          'runway-recipe-credits-2026-08-14.v1'
       or snapshot_value ->> 'spend_confirmation' <>
          'RUNWAY_PRODUCT_SWAP_10S_720P_SILENT_USD_4.28' then
      raise exception using
        message = 'verify_runway_10s_price:' || case_label;
    end if;

    -- 2. Runway на пятнадцати секундах: 212 + 11 * 36 = 608. Ступень надбавки
    --    цела, а не только база.
    snapshot_value := content_factory_private.generation_strategy_route_price(
      'viral_product_swap', 'runway', 'aleph2', 15, '720p', 'source', false
    );
    if snapshot_value is null
       or (snapshot_value ->> 'estimated_cost_minor')::integer <> 608
       or snapshot_value ->> 'spend_confirmation' <>
          'RUNWAY_PRODUCT_SWAP_15S_720P_SILENT_USD_6.08' then
      raise exception using
        message = 'verify_runway_15s_price:' || case_label;
    end if;

    -- Границы ступенчатого прайса Runway целы с обеих сторон: три секунды и
    -- шестнадцать цены не имеют.
    if content_factory_private.generation_strategy_route_price(
         'viral_product_swap', 'runway', 'aleph2', 3, '720p', 'source', false
       ) is not null
       or content_factory_private.generation_strategy_route_price(
         'viral_product_swap', 'runway', 'aleph2', 16, '720p', 'source', false
       ) is not null then
      raise exception using
        message = 'verify_runway_duration_bounds:' || case_label;
    end if;

    -- 3. Pika берёт за ролик целиком: сорок семь центов на любой допустимой
    --    длительности, а не сорок семь за секунду.
    foreach duration_value in array array[1, 5, 10, 15] loop
      snapshot_value := content_factory_private.generation_strategy_route_price(
        'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
        duration_value, '720p', 'source', false
      );
      if snapshot_value is null
         or (snapshot_value ->> 'estimated_cost_minor')::integer <> 47
         or (snapshot_value ->> 'estimated_credits')::integer <> 47
         or snapshot_value ->> 'estimated_cost_usd' <> '0.47'
         or snapshot_value ->> 'provider' <> 'fal'
         or snapshot_value ->> 'pricing_version' <>
            'fal-usd-per-run-2026-08-18.v1' then
        raise exception using
          message = 'verify_pika_per_run_price:' || case_label || ':'
            || duration_value::text;
      end if;
    end loop;
    snapshot_value := content_factory_private.generation_strategy_route_price(
      'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
      10, '720p', 'source', false
    );
    if snapshot_value ->> 'spend_confirmation' <>
       'FAL_PRODUCT_SWAP_10S_720P_SILENT_USD_0.47' then
      raise exception using
        message = 'verify_pika_confirmation:' || case_label;
    end if;

    -- 4. Kling считается посекундно: 17 * 10 = 170 — и упирается в собственный
    --    предел в десять секунд, а не в пятнадцать Runway.
    snapshot_value := content_factory_private.generation_strategy_route_price(
      'viral_product_swap', 'fal',
      'fal-ai/kling-video/o3/pro/video-to-video/edit',
      10, '720p', 'source', false
    );
    if snapshot_value is null
       or (snapshot_value ->> 'estimated_cost_minor')::integer <> 170
       or snapshot_value ->> 'provider' <> 'fal'
       or snapshot_value ->> 'pricing_version' <>
          'fal-usd-per-second-2026-08-18.v1'
       or snapshot_value ->> 'spend_confirmation' <>
          'FAL_PRODUCT_SWAP_10S_720P_SILENT_USD_1.70' then
      raise exception using
        message = 'verify_kling_10s_price:' || case_label;
    end if;
    if content_factory_private.generation_strategy_route_price(
         'viral_product_swap', 'fal',
         'fal-ai/kling-video/o3/pro/video-to-video/edit',
         11, '720p', 'source', false
       ) is not null then
      raise exception using
        message = 'verify_kling_duration_limit:' || case_label;
    end if;

    -- 5. Несуществующего маршрута нет и цены у него нет. Две разные формы
    --    «нет»: незнакомая модель у знакомого провайдера и знакомая модель у
    --    стратегии, у которой маршрутов в реестре нет вовсе.
    if content_factory_private.generation_strategy_route_price(
         'viral_product_swap', 'fal', 'fal-ai/no-such-model',
         10, '720p', 'source', false
       ) is not null
       or content_factory_private.generation_strategy_route_price(
         'viral_avatar_ugc', 'runway', 'aleph2',
         10, '720p', '720:1280', false
       ) is not null then
      raise exception using
        message = 'verify_unknown_route_priced:' || case_label;
    end if;

    -- 6. Выключенный маршрут цены не имеет. Kling гасится и тут же
    --    возвращается: отказ до денег — это и есть смысл поля enabled.
    update content_factory.generation_strategy_provider_routes as route
    set enabled = false
    where route.strategy_id = 'viral_product_swap'
      and route.model_key = 'fal-ai/kling-video/o3/pro/video-to-video/edit';
    if content_factory_private.generation_strategy_route_price(
         'viral_product_swap', 'fal',
         'fal-ai/kling-video/o3/pro/video-to-video/edit',
         10, '720p', 'source', false
       ) is not null then
      raise exception using
        message = 'verify_disabled_route_priced:' || case_label;
    end if;
    update content_factory.generation_strategy_provider_routes as route
    set enabled = true
    where route.strategy_id = 'viral_product_swap'
      and route.model_key = 'fal-ai/kling-video/o3/pro/video-to-video/edit';

    -- 7. Когда действующим маршрутом стоит сам Runway, маршрутная цена обязана
    --    совпасть с ценой стратегии не «по числу», а целиком, полем в поле:
    --    именно этот снимок ходил по системе до починки и он же обязан ходить
    --    после неё.
    if candidate_row.provider = 'runway' then
      if content_factory_private.generation_strategy_route_price(
           'viral_product_swap', 'runway', 'aleph2', 10, '720p', 'source', false
         ) is distinct from
         content_factory_private.generation_strategy_recipe_price(
           'viral_product_swap', 10, '720p', 'source', false
         ) then
        raise exception using
          message = 'verify_runway_snapshot_drift:' || case_label;
      end if;
    end if;
  end loop;

  -- Реестр возвращается в исходное состояние: сначала отметка снимается со
  -- всех, кроме исходного маршрута, затем ставится ему. Пустой
  -- original_active_id — допустимое состояние «действующего маршрута нет», и
  -- оно тоже восстанавливается как есть.
  update content_factory.generation_strategy_provider_routes as route
  set recommended = false
  where route.strategy_id = 'viral_product_swap'
    and route.recommended
    and route.id is distinct from original_active_id;
  update content_factory.generation_strategy_provider_routes as route
  set recommended = true
  where route.id = original_active_id
    and not route.recommended;

  select jsonb_agg(to_jsonb(route) order by route.id) into routes_after
  from content_factory.generation_strategy_provider_routes as route;
  if routes_after is distinct from routes_before then
    raise exception using message = 'verify_registry_not_restored';
  end if;

  -- И цена действующего маршрута — то, что видит оператор и на чём стоит
  -- резерв, — не сдвинулась ни на цент от того, чем была до этой миграции.
  active_price_after := content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 10, '720p', 'source', false
  );
  if active_price_after is distinct from active_price_before then
    raise exception using message = 'verify_active_price_drift';
  end if;
end;
$route_price_asked_route_verify$;

commit;
