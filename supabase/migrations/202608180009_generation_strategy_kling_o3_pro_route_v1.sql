begin;

-- 202608180009_generation_strategy_kling_o3_pro_route_v1
--
-- Второй маршрут fal для «Копии»: Kling O3 Pro, video-to-video edit.
--
-- Обёртка begin/commit открывает файл первой же строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет
-- обёртку регулярным выражением от начала файла, и комментарий перед begin
-- он за обёртку не считает. Поэтому «почему» живёт внутри транзакции.
--
-- Ставка у Kling посекундная, и это единственная причина, по которой нельзя
-- обойтись уже заведённой версией прайса. Строка
-- 'fal-usd-per-run-2026-08-18.v1' описывает цену за ролик целиком: под этим
-- именем ролик любой длительности стоит одинаково. Версия прайса не пояснение
-- для человека — она входит в хеш-подпись строки привязки и сверяется
-- браузером точным совпадением, поэтому посекундная ставка под именем «за
-- ролик» означала бы подпись, которая утверждает не то, что было посчитано.
-- Отсюда новое значение 'fal-usd-per-second-2026-08-18.v1'.
--
-- Ограничение на колонку pricing_version в двух таблицах — белый список
-- значений, а не свободный текст: маршрут с незнакомой версией не может
-- записать ни снимок выбора, ни квитанцию готовности, то есть не может дойти
-- до денег. Поэтому список именно РАСШИРЯЕТСЯ третьим значением: оба прежних
-- остаются допустимыми, и существующие строки — снимки выбора и квитанции со
-- старой версией Runway — переживают миграцию без единой правки.
--
-- Считать цену Kling новым кодом не нужно: диспетчер маршрутов (202608180004)
-- уже умеет price_kind = 'usd_minor_per_second' и множит ставку на
-- длительность. Всё, чего ему не хватало, — строки реестра.
--
-- Ставка 16,8 цента за секунду округлена ВВЕРХ до 17. Резерв, который меньше
-- фактического списания, — это дыра в бюджете, а завышенный резерв всего лишь
-- строже к оператору; в спорной ситуации выбирается второе.
--
-- Маршрут заводится НЕ рекомендованным. Рекомендованный маршрут у стратегии
-- ровно один — за этим следит частичный уникальный индекс
-- generation_strategy_provider_routes_recommended_key, — и эта миграция не
-- имеет права его переставлять: переключение действующего маршрута меняет
-- цену «Копии», а здесь только добавляется новый движок. Кто именно сейчас
-- действующий, миграция сознательно НЕ утверждает: на чистой цепочке это
-- Runway из 202608180002, после 202608180010 — Pika. Проверяется не имя, а
-- инвариант: действующий маршрут и его цена не сдвинулись ни на цент.

-- Снимок действующего маршрута ДО единственной правки реестра. Значение живёт
-- в транзакционной переменной (третий аргумент set_config = true): она сама
-- исчезает на commit, поэтому после миграции в сессии не остаётся следов.
-- Пустая строка означает «действующего маршрута нет вовсе» — это допустимое
-- состояние (у «Аватара» и «Пересборки» маршрута нет), и его тоже надо
-- сохранить в неизменности.
select set_config(
  'contentengine.active_swap_route_before',
  coalesce(
    (
      select jsonb_build_object(
        'provider', route.provider,
        'model_key', route.model_key,
        'price_kind', route.price_kind,
        'price_rate_minor', route.price_rate_minor,
        'pricing_version', route.pricing_version,
        'price', content_factory_private.generation_strategy_recipe_price(
          'viral_product_swap', 10, '720p', 'source', false
        )
      )::text
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = 'viral_product_swap'
        and route.recommended
        and route.enabled
    ),
    ''
  ),
  true
);

-- Белый список версий прайса. Прежние два значения сохранены дословно:
-- существующие строки обязаны остаться допустимыми.
alter table content_factory.generation_strategy_binding_selections
  drop constraint if exists generation_strategy_binding_selections_pricing_version_check;
alter table content_factory.generation_strategy_binding_selections
  add constraint generation_strategy_binding_selections_pricing_version_check
  check (pricing_version in (
    'runway-recipe-credits-2026-08-14.v1',
    'fal-usd-per-run-2026-08-18.v1',
    'fal-usd-per-second-2026-08-18.v1'
  ));

alter table content_factory.generation_strategy_readiness_receipts
  drop constraint if exists generation_strategy_readiness_receipts_pricing_version_check;
alter table content_factory.generation_strategy_readiness_receipts
  add constraint generation_strategy_readiness_receipts_pricing_version_check
  check (pricing_version in (
    'runway-recipe-credits-2026-08-14.v1',
    'fal-usd-per-run-2026-08-18.v1',
    'fal-usd-per-second-2026-08-18.v1'
  ));

-- Белый список запуска. Без записи в нём каталог отдаёт стратегию выключенной
-- целиком, и до расчёта цены дело не доходит вовсе. Тело функции правится
-- точечной заменой известного фрагмента, как это сделано для Pika в
-- 202608180007: полное тело живёт в 202608130002, и переписывать его ради
-- одной ветки означало бы рисковать остальным содержимым. Якорь — строка
-- Pika: новая ветка встаёт рядом, и обе записи fal читаются вместе.
do $launch_gate_kling$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  if definition_value is null then
    raise exception using message = 'launch_gate_missing';
  end if;

  -- Повторный прогон не должен завести вторую, недостижимую ветку с тем же
  -- ключом: если запись уже стоит, править нечего.
  if position(
       'fal:fal-ai/kling-video/o3/pro/video-to-video/edit' in definition_value
     ) > 0 then
    return;
  end if;

  -- Якорь обязан быть единственным: замена по неуникальному фрагменту
  -- размножила бы ветки молча.
  anchor_hits := (
    length(definition_value)
    - length(replace(
        definition_value,
        $f$when 'fal:fal-ai/pika/v2/pikaswaps' then true$f$,
        ''
      ))
  ) / length($f$when 'fal:fal-ai/pika/v2/pikaswaps' then true$f$);
  if anchor_hits <> 1 then
    raise exception using
      message = 'launch_gate_anchor_not_unique:' || anchor_hits::text;
  end if;

  patched_value := replace(
    definition_value,
    $f$when 'fal:fal-ai/pika/v2/pikaswaps' then true$f$,
    $r$when 'fal:fal-ai/pika/v2/pikaswaps' then true
    when 'fal:fal-ai/kling-video/o3/pro/video-to-video/edit' then true$r$
  );
  if position(
       'fal:fal-ai/kling-video/o3/pro/video-to-video/edit' in patched_value
     ) = 0 then
    raise exception using message = 'launch_gate_patch_failed';
  end if;

  execute patched_value;
end;
$launch_gate_kling$;

-- Строка реестра. Ставка сверена со страницей модели на fal 18.08.2026:
-- $0,168 за секунду результата. Предел длительности — 10 секунд, это
-- ограничение самого Kling, а не наша осторожность. Маршрут включён: ставка
-- сверена, и ограничение
-- generation_strategy_provider_routes_enabled_requires_verified_check иначе не
-- пропустило бы enabled. recommended = false здесь не украшение, а условие
-- неизменности действующей цены: см. шапку файла.
insert into content_factory.generation_strategy_provider_routes (
  strategy_id, provider, model_key, provider_path, poll_kind,
  pricing_version, price_kind, price_rate_minor,
  min_duration_seconds, max_duration_seconds, tier,
  quality_modes, recommended, enabled, verified_rate_at, notes
)
values (
  'viral_product_swap', 'fal',
  'fal-ai/kling-video/o3/pro/video-to-video/edit',
  'fal-ai/kling-video/o3/pro/video-to-video/edit', 'fal_request',
  'fal-usd-per-second-2026-08-18.v1', 'usd_minor_per_second', 17,
  1, 10, 'medium',
  '["standard"]'::jsonb, false, true, now(),
  'Правка видео по описанию: держит сцену и мелкий текст лучше замены по фото, но платится посекундно. Провайдер берёт $0.168 за секунду, резервируем 17 центов за секунду; предел длительности — 10 секунд.'
)
on conflict (strategy_id, provider, model_key) do nothing;

do $kling_o3_pro_route_verify$
declare
  kling_row content_factory.generation_strategy_provider_routes%rowtype;
  runway_row content_factory.generation_strategy_provider_routes%rowtype;
  snapshot_value jsonb;
  catalog_value jsonb;
  definition_value text;
  constraint_name text;
  constraint_definition text;
  constraint_count integer := 0;
  organization_id_value uuid;
  before_text text;
  before_value jsonb;
  after_value jsonb;
  drifted_receipts integer;
begin
  -- 1. Строка Kling заведена ровно с теми числами, которые сверены у провайдера.
  select route.* into kling_row
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.provider = 'fal'
    and route.model_key = 'fal-ai/kling-video/o3/pro/video-to-video/edit';
  if kling_row.id is null
     or kling_row.pricing_version <> 'fal-usd-per-second-2026-08-18.v1'
     or kling_row.price_kind <> 'usd_minor_per_second'
     or kling_row.price_rate_minor <> 17
     or kling_row.min_duration_seconds <> 1
     or kling_row.max_duration_seconds <> 10
     or kling_row.poll_kind <> 'fal_request'
     or kling_row.enabled is not true
     or kling_row.recommended is not false
     or kling_row.verified_rate_at is null then
    raise exception using message = 'kling_route_missing_or_drifted';
  end if;

  -- Диспетчер маршрутов считает Kling посекундно и уважает предел в 10 секунд:
  -- цена есть на десяти секундах и отсутствует на одиннадцати. Эта цена не
  -- зависит от того, какой маршрут действующий: generation_strategy_route_price
  -- читает ставку запрошенной строки реестра.
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
    raise exception using message = 'kling_route_price_unexpected';
  end if;
  if content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'fal',
       'fal-ai/kling-video/o3/pro/video-to-video/edit',
       11, '720p', 'source', false
     ) is not null then
    raise exception using message = 'kling_route_duration_limit_ignored';
  end if;

  -- 2. Маршрут видно на экране. Каталог отдаёт реестр без фильтров
  --    (202608180003), поэтому проверяется не запрос, а сам ответ политики.
  select organization.id into organization_id_value
  from content_factory.organizations as organization
  where organization.status = 'active'
  order by organization.id
  limit 1;
  if organization_id_value is not null then
    catalog_value := public.system_generation_strategy_catalog_policy(
      jsonb_build_object(
        'version', 'generation-strategy-catalog-policy-request-v1',
        'organization_id', organization_id_value::text
      )
    );
    if not exists (
      select 1
      from jsonb_array_elements(
        catalog_value -> 'provider_routes' -> 'viral_product_swap'
      ) as route_item
      where route_item ->> 'model_key' =
        'fal-ai/kling-video/o3/pro/video-to-video/edit'
        and (route_item ->> 'enabled')::boolean
        and (route_item ->> 'price_rate_minor')::integer = 17
    ) then
      raise exception using message = 'kling_route_not_visible_in_catalog';
    end if;
    -- Белый список пропускает Kling и по-прежнему пропускает Pika.
    if content_factory_private.generation_provider_launch_enabled(
         organization_id_value, 'fal',
         'fal-ai/kling-video/o3/pro/video-to-video/edit'
       ) is not true
       or content_factory_private.generation_provider_launch_enabled(
         organization_id_value, 'fal', 'fal-ai/pika/v2/pikaswaps'
       ) is not true then
      raise exception using message = 'launch_gate_verify_failed';
    end if;
  end if;

  -- Даже без активной организации ветки в теле функции обязаны быть на месте.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  if definition_value is null
     or position(
          'fal:fal-ai/kling-video/o3/pro/video-to-video/edit'
          in definition_value
        ) = 0
     or position('fal:fal-ai/pika/v2/pikaswaps' in definition_value) = 0
     or position('runway:gen4_turbo' in definition_value) = 0 then
    raise exception using message = 'launch_gate_definition_incomplete';
  end if;

  -- 3. Действующий маршрут «Копии» не сдвинулся. Проверяется не имя провайдера,
  --    а равенство снимку, снятому в начале файла: миграция обязана быть
  --    нейтральной к тому, кто действующий, и падать ровно тогда, когда она сама
  --    что-то переставила. Прежняя редакция требовала здесь именно Pika и
  --    падала на чистой цепочке, где действующим стоит Runway из 202608180002.
  before_text := current_setting('contentengine.active_swap_route_before', true);
  if before_text is null then
    raise exception using message = 'active_route_snapshot_missing';
  end if;
  before_value := case when before_text = '' then null
    else before_text::jsonb end;

  select jsonb_build_object(
    'provider', route.provider,
    'model_key', route.model_key,
    'price_kind', route.price_kind,
    'price_rate_minor', route.price_rate_minor,
    'pricing_version', route.pricing_version,
    'price', content_factory_private.generation_strategy_recipe_price(
      'viral_product_swap', 10, '720p', 'source', false
    )
  ) into after_value
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.recommended
    and route.enabled;

  if after_value is distinct from before_value then
    raise exception using message = 'active_route_changed_by_migration';
  end if;

  -- Kling не стал действующим маршрутом: ни отметки, ни как следствие — цены
  -- «Копии» по 17 центов за секунду вместо цены прежнего движка.
  if after_value is not null
     and after_value ->> 'model_key' =
       'fal-ai/kling-video/o3/pro/video-to-video/edit' then
    raise exception using message = 'kling_became_active_route';
  end if;
  if exists (
    select 1
    from content_factory.generation_strategy_provider_routes as route
    where route.strategy_id = 'viral_product_swap'
      and route.model_key = 'fal-ai/kling-video/o3/pro/video-to-video/edit'
      and route.recommended
  ) then
    raise exception using message = 'kling_marked_recommended';
  end if;

  -- Действующим маршрутом у стратегии по-прежнему помечен ровно один движок:
  -- частичный уникальный индекс запрещает второй, а ноль означал бы, что
  -- «Копия» осталась без цены.
  if (
    select count(*)
    from content_factory.generation_strategy_provider_routes as route
    where route.strategy_id = 'viral_product_swap'
      and route.recommended
  ) <> 1 then
    raise exception using message = 'recommended_route_count_invalid';
  end if;

  -- 4. Если действующий маршрут — Runway, его цена обязана остаться прежней до
  --    цента: 212 + 6 * 36 = 428 и та самая строка подтверждения. Если
  --    действующий маршрут другой (в проде и после 202608180010 это Pika), его
  --    цена уже сверена равенством снимков выше — второй раз называть число
  --    нельзя, иначе миграция начнёт диктовать, каким должен быть маршрут.
  if after_value is not null and after_value ->> 'provider' = 'runway' then
    if (after_value -> 'price' ->> 'estimated_cost_minor')::integer <> 428
       or after_value -> 'price' ->> 'pricing_version' <>
          'runway-recipe-credits-2026-08-14.v1'
       or after_value -> 'price' ->> 'spend_confirmation' <>
          'RUNWAY_PRODUCT_SWAP_10S_720P_SILENT_USD_4.28' then
      raise exception using message = 'runway_active_price_drift';
    end if;
  end if;

  -- Строка реестра Runway цела независимо от того, действующая она сейчас или
  -- дорогой запасной уровень. Отметку recommended здесь НЕ проверяем: она
  -- законно равна true на чистой цепочке и false после 202608180010.
  select route.* into runway_row
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.provider = 'runway'
    and route.model_key = 'aleph2';
  if runway_row.id is null
     or runway_row.pricing_version <> 'runway-recipe-credits-2026-08-14.v1'
     or runway_row.price_kind <> 'runway_credit_tiers'
     or runway_row.price_rate_minor is not null
     or runway_row.min_duration_seconds <> 4
     or runway_row.max_duration_seconds <> 15
     or runway_row.enabled is not true then
    raise exception using message = 'runway_route_drift';
  end if;

  -- Ступени Runway целы и тогда, когда действующим стал не Runway: у «Аватара»
  -- рекомендованного маршрута нет вовсе, поэтому там та же формула считается
  -- вживую — 192 + 6 * 36 = 408 — и служит её сторожем.
  snapshot_value := content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 10, '720p', '720:1280', false
  );
  if (snapshot_value ->> 'estimated_cost_minor')::integer <> 408
     or snapshot_value ->> 'provider' <> 'runway'
     or snapshot_value ->> 'pricing_version' <>
        'runway-recipe-credits-2026-08-14.v1'
     or snapshot_value ->> 'spend_confirmation' <>
        'RUNWAY_PRODUCT_UGC_10S_720P_SILENT_USD_4.08' then
    raise exception using message = 'runway_credit_ladder_drift';
  end if;

  -- Квитанции оплаченных прогонов «Копии» на Runway: ни одна не должна
  -- переписаться. Наличие таких квитанций НЕ требуется — на чистой цепочке
  -- истории ещё нет, и требование «хотя бы одна» превращало бы пустую базу в
  -- ошибку. Требуется другое: если квитанция с этой строкой подтверждения
  -- есть, сумма, провайдер и версия прайса внутри неё обязаны быть теми же.
  select count(*) into drifted_receipts
  from content_factory.generation_strategy_readiness_receipts as receipt
  where receipt.price_snapshot ->> 'spend_confirmation' =
      'RUNWAY_PRODUCT_SWAP_10S_720P_SILENT_USD_4.28'
    and (
      (receipt.price_snapshot ->> 'estimated_cost_minor')::integer <> 428
      or receipt.price_snapshot ->> 'provider' <> 'runway'
      or receipt.pricing_version <> 'runway-recipe-credits-2026-08-14.v1'
    );
  if drifted_receipts > 0 then
    raise exception using message = 'runway_copy_price_history_drift';
  end if;

  -- 5. Новая версия прайса принимается обеими таблицами, и обе прежние из
  --    белого списка не выпали. Проверяется текст ограничения, а не пробная
  --    вставка: пробная строка была бы записью в боевую таблицу, а откатить её
  --    внутри миграции нечем — вложенное управление транзакцией загрузчик
  --    отвергает.
  for constraint_name, constraint_definition in
    select constraint_row.conname, pg_get_constraintdef(constraint_row.oid)
    from pg_constraint as constraint_row
    where constraint_row.conrelid in (
        'content_factory.generation_strategy_binding_selections'::regclass,
        'content_factory.generation_strategy_readiness_receipts'::regclass
      )
      and constraint_row.contype = 'c'
      and constraint_row.conname like '%_pricing_version_check'
  loop
    constraint_count := constraint_count + 1;
    if position(
         'fal-usd-per-second-2026-08-18.v1' in constraint_definition
       ) = 0
       or position(
            'fal-usd-per-run-2026-08-18.v1' in constraint_definition
          ) = 0
       or position(
            'runway-recipe-credits-2026-08-14.v1' in constraint_definition
          ) = 0 then
      raise exception using
        message = 'pricing_version_check_incomplete:' || constraint_name;
    end if;
  end loop;
  if constraint_count <> 2 then
    raise exception using
      message = 'pricing_version_check_missing:' || constraint_count::text;
  end if;
end;
$kling_o3_pro_route_verify$;

commit;
