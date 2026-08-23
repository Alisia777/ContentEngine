begin;

-- 202608190006_generation_strategy_operator_engine_choice_v1
--
-- Оператор выбирает движок, и привязка считает цену ВЫБРАННОГО движка.
--
-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и комментарий перед BEGIN отвергает
-- не только этот файл, но и всю цепочку разом. Поэтому «почему» живёт внутри
-- транзакции.
--
-- ЧТО БЫЛО. Экран «Копии» показывает каскад из трёх движков, но выбор в нём
-- ничего не исполняет: подпись под каскадом прямо говорит человеку, что
-- запуск всё равно уйдёт маршруту с отметкой «Советуем». Цену привязки
-- считает generation_strategy_recipe_price, а она с 202608180006 отвечает на
-- вопрос «сколько стоит у ДЕЙСТВУЮЩЕГО маршрута», и другого вопроса ей задать
-- нельзя. То есть каскад был витриной: три движка видно, работает один.
--
-- ЧТО ДЕЛАЕТ ЭТА МИГРАЦИЯ. Запрос привязки получает необязательное поле
-- engine = { provider, model_key }. Если оно есть — цена считается
-- generation_strategy_route_price, то есть строкой реестра именно этого
-- движка, с его ставкой, его пределами длительности и его версией прайса.
-- Если поля нет — не меняется ни один байт прежнего поведения: цена считается
-- по действующему маршруту, как считалась. Старый портал, старая привязка и
-- старые квитанции продолжают работать без правок.
--
-- ПОЧЕМУ ДВИЖОК НЕ КЛАДЁТСЯ ВНУТРЬ selection. Форму selection проверяют по
-- ТОЧНОМУ набору ключей три функции сразу (эта, selection_current,
-- selection_snapshot_valid_v1), и лишний ключ в ней означал бы отказ во всех
-- трёх. Движок при этом не теряется: он выражен в снимке цены — провайдером и
-- версией прайса, — а снимок и так сверяется всеми, кто ниже по течению.
--
-- ПОЧЕМУ ПАРА (провайдер, версия прайса) ОДНОЗНАЧНА. На неё уже опираются
-- отправка и опрос: по ней они находят строку реестра, чтобы собрать адрес
-- задачи у провайдера. Опора была на договорённость, а не на ограничение:
-- ничто не мешало завести два включённых маршрута fal с одной версией прайса,
-- и тогда «маршрут из подписи» перестал бы восстанавливаться однозначно —
-- отправка ушла бы к одной модели, а результат забирался бы у другой. Здесь
-- договорённость становится ограничением базы: частичный уникальный индекс по
-- (strategy_id, provider, pricing_version) среди включённых маршрутов.
--
-- ОТДЕЛЬНО — ПРЕДЕЛЫ KLING. В реестре у него стоит 1..10 секунд. Это неверно:
-- страница модели fal (kling-video/o3/pro/video-to-video/edit) требует входное
-- видео длиной 3–15 секунд, и длительность результата задаёт ИСХОДНИК, а не
-- параметр запроса. Ставка у маршрута посекундная, поэтому заниженный верхний
-- предел — это не «осторожность», а зарезервированная сумма меньше
-- фактического списания: пятнадцатисекундный исходник провайдер посчитает по
-- пятнадцати секундам независимо от того, что мы записали себе. Пределы
-- приводятся к 3..15 — к тому, что провайдер принимает на самом деле.
--
-- ДЕНЬГИ. Ни одна цена действующего маршрута здесь не меняется: verify-блок в
-- конце сверяет снимок цены «Копии» до и после правки до цента и падает при
-- расхождении.

-- Снимок действующего маршрута и его цены ДО правок. Транзакционная переменная
-- (третий аргумент set_config = true) исчезает на commit, поэтому следов в
-- сессии не остаётся. Пустая строка означает «действующего маршрута нет» —
-- допустимое состояние, его тоже надо сохранить неизменным.
select set_config(
  'contentengine.engine_choice_route_before',
  coalesce(
    (
      select jsonb_build_object(
        'provider', route.provider,
        'model_key', route.model_key,
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

-- 1. Однозначность маршрута по подписи. Индекс частичный: выключенный маршрут
--    исполнять нельзя, поэтому он и не участвует в восстановлении.
create unique index if not exists
  generation_strategy_provider_routes_signature_key
  on content_factory.generation_strategy_provider_routes(
    strategy_id, provider, pricing_version
  )
  where enabled;

-- 2. Пределы Kling по факту провайдера.
update content_factory.generation_strategy_provider_routes as route
set min_duration_seconds = 3,
    max_duration_seconds = 15,
    updated_at = now(),
    notes = 'Правка видео по описанию: держит сцену и мелкий текст лучше '
      || 'замены по фото, но платится посекундно. Провайдер берёт $0.168 за '
      || 'секунду, резервируем 17 центов за секунду. Длительность результата '
      || 'задаёт исходник: модель принимает видео 3–15 секунд.'
where route.strategy_id = 'viral_product_swap'
  and route.provider = 'fal'
  and route.model_key = 'fal-ai/kling-video/o3/pro/video-to-video/edit';

-- 3. Привязка принимает выбор движка.
do $engine_choice_bind$
declare
  definition_value text;
  patched_value text;
  keys_anchor constant text := $f$  if p_payload - array[
       'version', 'organization_id', 'project_id', 'actor_id', 'spec_id',
       'spec_version', 'spec_hash', 'selection', 'confirmation',
       'idempotency_key'
     ]::text[] <> '{}'::jsonb$f$;
  price_anchor constant text := $f$  price_value := content_factory_private.generation_strategy_recipe_price(
    strategy_id_value, duration_seconds_value, resolution_value,
    ratio_value, audio_value
  );$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname =
      'system_resolve_and_bind_generation_strategy_pre_execution_v1';
  if definition_value is null then
    raise exception using message = 'bind_pre_execution_missing';
  end if;

  -- Повторный прогон не должен патчить дважды.
  if position('engine_choice_v1' in definition_value) > 0 then
    return;
  end if;

  -- Оба якоря обязаны быть единственными: замена по неуникальному фрагменту
  -- размножила бы код молча.
  if (length(definition_value)
      - length(replace(definition_value, keys_anchor, '')))
     / length(keys_anchor) <> 1
     or (length(definition_value)
      - length(replace(definition_value, price_anchor, '')))
     / length(price_anchor) <> 1 then
    raise exception using message = 'bind_pre_execution_anchor_not_unique';
  end if;

  -- Ключ engine становится допустимым, но НЕ обязательным: в проверке наличия
  -- (?&) его нет, поэтому прежний запрос без движка остаётся правильным.
  patched_value := replace(
    definition_value,
    keys_anchor,
    $f$  if p_payload - array[
       'version', 'organization_id', 'project_id', 'actor_id', 'spec_id',
       'spec_version', 'spec_hash', 'selection', 'confirmation',
       'idempotency_key', 'engine'
     ]::text[] <> '{}'::jsonb$f$
  );

  patched_value := replace(
    patched_value,
    price_anchor,
    $f$  -- engine_choice_v1: движок, выбранный оператором. Форма проверяется
  -- целиком, а не по одному полю: половина движка — это не «почти движок», а
  -- запрос, на который нельзя ответить ценой.
  if p_payload ? 'engine'
     and (
       jsonb_typeof(p_payload -> 'engine') <> 'object'
       or (p_payload -> 'engine') - array['provider', 'model_key']::text[]
            <> '{}'::jsonb
       or not (p_payload -> 'engine') ?& array['provider', 'model_key']::text[]
       or jsonb_typeof(p_payload #> '{engine,provider}') <> 'string'
       or jsonb_typeof(p_payload #> '{engine,model_key}') <> 'string'
     ) then
    raise exception using errcode = '22023',
      message = 'generation_strategy_resolve_bind_payload_invalid';
  end if;
  if p_payload ? 'engine' then
    -- Цена спрошенного движка: его ставка, его пределы длительности, его
    -- версия прайса. Незнакомый или выключенный маршрут вернёт null, и запрос
    -- будет отвергнут ниже — отказ громкий и до денег.
    price_value := content_factory_private.generation_strategy_route_price(
      strategy_id_value,
      p_payload #>> '{engine,provider}',
      p_payload #>> '{engine,model_key}',
      duration_seconds_value, resolution_value, ratio_value, audio_value
    );
  else
    price_value := content_factory_private.generation_strategy_recipe_price(
      strategy_id_value, duration_seconds_value, resolution_value,
      ratio_value, audio_value
    );
  end if;$f$
  );

  if position('engine_choice_v1' in patched_value) = 0
     or position('generation_strategy_route_price' in patched_value) = 0 then
    raise exception using message = 'bind_pre_execution_patch_failed';
  end if;

  execute patched_value;
end;
$engine_choice_bind$;

-- Права после create or replace сохраняются, но повторяются явно.
revoke all on function
  public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)
  to service_role;

-- 4. Квитанция готовности сверяет цену ТОГО маршрута, который назван в снимке.
do $engine_choice_readiness$
declare
  definition_value text;
  patched_value text;
  price_anchor constant text := $f$  canonical_price_value := content_factory_private
    .generation_strategy_recipe_price(
      binding_row.strategy_id,
      (selection_row.selection_snapshot ->> 'duration_seconds')::integer,
      selection_row.price_snapshot ->> 'resolution',
      selection_row.price_snapshot ->> 'ratio',
      (selection_row.selection_snapshot ->> 'audio')::boolean
    );$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_record_generation_strategy_readiness';
  if definition_value is null then
    raise exception using message = 'readiness_function_missing';
  end if;

  if position('engine_choice_v1' in definition_value) > 0 then
    return;
  end if;

  if (length(definition_value)
      - length(replace(definition_value, price_anchor, '')))
     / length(price_anchor) <> 1 then
    raise exception using message = 'readiness_anchor_not_unique';
  end if;

  -- Пересчёт идёт по строке реестра, восстановленной из подписи снимка:
  -- провайдер и версия прайса вместе указывают ровно одну включённую строку
  -- (частичный уникальный индекс выше). Для Runway это та же самая арифметика
  -- ступеней, перенесённая в generation_strategy_route_price цифра в цифру
  -- миграцией 202608180011, поэтому его квитанции не сдвигаются ни на цент.
  -- Если строки нет вовсе — остаётся прежний расчёт по действующему маршруту:
  -- квитанции, выписанные до появления реестра, обязаны сверяться как прежде.
  patched_value := replace(
    definition_value,
    price_anchor,
    $f$  -- engine_choice_v1: маршрут снимка, а не действующий маршрут.
  canonical_price_value := coalesce(
    (
      select content_factory_private.generation_strategy_route_price(
        binding_row.strategy_id,
        route.provider,
        route.model_key,
        (selection_row.selection_snapshot ->> 'duration_seconds')::integer,
        selection_row.price_snapshot ->> 'resolution',
        selection_row.price_snapshot ->> 'ratio',
        (selection_row.selection_snapshot ->> 'audio')::boolean
      )
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = binding_row.strategy_id
        and route.provider = selection_row.price_snapshot ->> 'provider'
        and route.pricing_version =
          selection_row.price_snapshot ->> 'pricing_version'
        and route.enabled
    ),
    content_factory_private.generation_strategy_recipe_price(
      binding_row.strategy_id,
      (selection_row.selection_snapshot ->> 'duration_seconds')::integer,
      selection_row.price_snapshot ->> 'resolution',
      selection_row.price_snapshot ->> 'ratio',
      (selection_row.selection_snapshot ->> 'audio')::boolean
    )
  );$f$
  );

  if position('engine_choice_v1' in patched_value) = 0 then
    raise exception using message = 'readiness_patch_failed';
  end if;

  execute patched_value;
end;
$engine_choice_readiness$;

revoke all on function
  public.system_record_generation_strategy_readiness(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_record_generation_strategy_readiness(jsonb)
  to service_role;

do $engine_choice_verify$
declare
  before_text text;
  before_value jsonb;
  after_value jsonb;
  kling_row content_factory.generation_strategy_provider_routes%rowtype;
  definition_value text;
  signature_duplicates integer;
begin
  -- 1. Действующий маршрут и его цена не сдвинулись.
  before_text := current_setting(
    'contentengine.engine_choice_route_before', true
  );
  if before_text is null then
    raise exception using message = 'active_route_snapshot_missing';
  end if;
  before_value := case when before_text = '' then null
    else before_text::jsonb end;
  select jsonb_build_object(
    'provider', route.provider,
    'model_key', route.model_key,
    'pricing_version', route.pricing_version,
    'price', content_factory_private.generation_strategy_recipe_price(
      'viral_product_swap', 10, '720p', 'source', false
    )
  ) into after_value
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.recommended
    and route.enabled;
  if before_value is distinct from after_value then
    raise exception using message = 'active_route_drifted';
  end if;

  -- 2. Пределы Kling — те, что принимает провайдер.
  select route.* into kling_row
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.provider = 'fal'
    and route.model_key = 'fal-ai/kling-video/o3/pro/video-to-video/edit';
  if kling_row.id is null
     or kling_row.min_duration_seconds <> 3
     or kling_row.max_duration_seconds <> 15
     or kling_row.price_rate_minor <> 17 then
    raise exception using message = 'kling_duration_window_drifted';
  end if;

  -- 3. Маршрутная цена отвечает за каждый включённый движок отдельно, и
  --    ответы разные: витрина из трёх одинаковых цен означала бы, что выбор
  --    снова ни на что не влияет.
  if content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
       10, '720p', 'source', false
     ) ->> 'estimated_cost_minor' <> '47'
     or content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'fal',
       'fal-ai/kling-video/o3/pro/video-to-video/edit',
       10, '720p', 'source', false
     ) ->> 'estimated_cost_minor' <> '170'
     or content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'runway', 'aleph2', 10, '720p', 'source', false
     ) ->> 'estimated_cost_minor' <> '428' then
    raise exception using message = 'route_price_drifted';
  end if;

  -- 4. Kling больше не отвергает трёхсекундный исходник и отвергает
  --    двухсекундный: предел стал провайдерским, а не выдуманным.
  if content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'fal',
       'fal-ai/kling-video/o3/pro/video-to-video/edit',
       3, '720p', 'source', false
     ) ->> 'estimated_cost_minor' <> '51'
     or content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'fal',
       'fal-ai/kling-video/o3/pro/video-to-video/edit',
       2, '720p', 'source', false
     ) is not null then
    raise exception using message = 'kling_duration_bounds_broken';
  end if;

  -- 5. Подпись маршрута однозначна: ни одной пары (стратегия, провайдер,
  --    версия прайса) с двумя включёнными строками.
  select count(*) into signature_duplicates
  from (
    select 1
    from content_factory.generation_strategy_provider_routes as route
    where route.enabled
    group by route.strategy_id, route.provider, route.pricing_version
    having count(*) > 1
  ) as duplicates;
  if signature_duplicates > 0 then
    raise exception using message = 'route_signature_ambiguous';
  end if;

  -- 6. Обе пропатченные функции несут метку правки и новый расчёт.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname =
      'system_resolve_and_bind_generation_strategy_pre_execution_v1';
  if definition_value is null
     or position('engine_choice_v1' in definition_value) = 0
     or position('generation_strategy_route_price' in definition_value) = 0
     or position('generation_strategy_recipe_price' in definition_value) = 0
  then
    raise exception using message = 'bind_pre_execution_verify_failed';
  end if;

  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_record_generation_strategy_readiness';
  if definition_value is null
     or position('engine_choice_v1' in definition_value) = 0
     or position('generation_strategy_route_price' in definition_value) = 0
  then
    raise exception using message = 'readiness_verify_failed';
  end if;
end;
$engine_choice_verify$;

commit;
