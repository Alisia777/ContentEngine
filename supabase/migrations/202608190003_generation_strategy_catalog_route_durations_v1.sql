begin;

-- 202608190003_generation_strategy_catalog_route_durations_v1
--
-- Каталог начинает отдавать пределы длительности маршрута.
--
-- Обёртка begin/commit открывает файл первой строкой: загрузчик миграций
-- (scripts/deploy_supabase_management_api.py) сверяет её регулярным выражением
-- от начала файла и комментарий перед begin за обёртку не считает. Поэтому
-- «почему» живёт внутри транзакции.
--
-- Реестр маршрутов (202608180002) с самого начала хранит min_duration_seconds
-- и max_duration_seconds: у Pika это 1..15, у Runway 4..15, у Kling 1..10 —
-- предел самого провайдера, а не наша осторожность. Проекция каталога
-- (202608180003) эти два поля не отдавала, и браузер про них не знал.
--
-- Экран «Копии» теперь показывает тайминги третьей ступенью каскада: выбрал
-- модель — увидел её допустимую длительность. Без этих полей ступень может
-- показать только окно самой стратегии, одинаковое для всех моделей; чтобы не
-- выдумывать числа на стороне браузера, они приходят из реестра.
--
-- Правка точечная: тело функции патчится заменой известного фрагмента, как это
-- сделано в 202608180007 и 202608180009. Полное тело живёт в 202608180003, и
-- переписывать его ради двух полей означало бы рисковать остальным
-- содержимым — включая путь /v1/video_to_video, который стоил отдельной
-- миграции 202608170006.
--
-- Деньги эта миграция не трогает вовсе: проекция каталога только читает, а
-- цену считают generation_strategy_route_price и generation_strategy_recipe_price.
-- Ни одной строки реестра здесь не записывается — за этим следит снимок ниже.

-- Снимок действующего маршрута «Копии» и его цены ДО правки. Транзакционная
-- переменная (третий аргумент set_config = true) исчезает на commit, поэтому
-- после миграции в сессии не остаётся следов. Пустая строка означает
-- «действующего маршрута нет» — допустимое состояние, его тоже надо сохранить.
select set_config(
  'contentengine.catalog_durations_route_before',
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

do $catalog_route_durations$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text := $f$'price_rate_minor', route.price_rate_minor,$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_catalog_policy';
  if definition_value is null then
    raise exception using message = 'catalog_policy_missing';
  end if;

  -- Повторный прогон не должен добавить поля второй раз.
  if position('min_duration_seconds' in definition_value) > 0 then
    return;
  end if;

  -- Якорь обязан быть единственным: замена по неуникальному фрагменту
  -- размножила бы поля молча.
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
              ''min_duration_seconds'', route.min_duration_seconds,
              ''max_duration_seconds'', route.max_duration_seconds,'
  );
  if position('min_duration_seconds' in patched_value) = 0
     or position('max_duration_seconds' in patched_value) = 0 then
    raise exception using message = 'catalog_policy_patch_failed';
  end if;

  execute patched_value;
end;
$catalog_route_durations$;

-- Права на функцию после create or replace сохраняются, но повторяются явно:
-- каталог остаётся доступен только service_role.
revoke all on function
  public.system_generation_strategy_catalog_policy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_generation_strategy_catalog_policy(jsonb)
  to service_role;

do $catalog_route_durations_verify$
declare
  definition_value text;
  catalog_value jsonb;
  organization_id_value uuid;
  before_text text;
  before_value jsonb;
  after_value jsonb;
  mismatched_routes integer;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_catalog_policy';

  -- 1. Новые поля на месте, а прежние семь никуда не делись: экран читает их
  --    все, и потеря любого превратила бы каскад в пустой список.
  if definition_value is null
     or position('min_duration_seconds' in definition_value) = 0
     or position('max_duration_seconds' in definition_value) = 0
     or position($f$'provider', route.provider$f$ in definition_value) = 0
     or position($f$'model_key', route.model_key$f$ in definition_value) = 0
     or position($f$'tier', route.tier$f$ in definition_value) = 0
     or position($f$'price_kind', route.price_kind$f$ in definition_value) = 0
     or position($f$'price_rate_minor', route.price_rate_minor$f$
          in definition_value) = 0
     or position($f$'recommended', route.recommended$f$ in definition_value) = 0
     or position($f$'enabled', route.enabled$f$ in definition_value) = 0 then
    raise exception using message = 'catalog_route_fields_incomplete';
  end if;

  -- 2. Инварианты 202608170006 целы: маршрут «Копии» — video_to_video, а старый
  --    несуществующий путь не вернулся.
  if position('/v1/video_to_video' in definition_value) = 0
     or position('/v1/recipes/product_swap' in definition_value) > 0 then
    raise exception using message = 'catalog_policy_path_drift';
  end if;

  -- 3. Ответ каталога отдаёт пределы каждой строки реестра дословно.
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
    select count(*) into mismatched_routes
    from content_factory.generation_strategy_provider_routes as route
    where not exists (
      select 1
      from jsonb_array_elements(
        catalog_value -> 'provider_routes' -> route.strategy_id
      ) as route_item
      where route_item ->> 'model_key' = route.model_key
        and route_item ->> 'provider' = route.provider
        and (route_item ->> 'min_duration_seconds')::integer
          = route.min_duration_seconds
        and (route_item ->> 'max_duration_seconds')::integer
          = route.max_duration_seconds
    );
    if mismatched_routes > 0 then
      raise exception using
        message = 'catalog_route_durations_mismatch:' || mismatched_routes::text;
    end if;
  end if;

  -- 4. Реестр не сдвинулся: действующий маршрут «Копии» и его цена те же до
  --    цента. Проверяется равенство снимку, а не имя провайдера, — миграция
  --    обязана быть нейтральной к тому, кто сейчас действующий.
  before_text := current_setting(
    'contentengine.catalog_durations_route_before', true
  );
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
end;
$catalog_route_durations_verify$;

commit;
