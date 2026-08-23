begin;

-- 202608190007_generation_strategy_route_quality_modes_v1
--
-- Уровни качества движка перестают быть словом и становятся выбором.
--
-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и комментарий перед BEGIN отвергает
-- вместе с ним всю цепочку. Поэтому «почему» живёт внутри транзакции.
--
-- ЧТО БЫЛО. Колонка quality_modes есть в реестре с самого его появления
-- (202608180002), но хранит она список голых строк ["standard"], каталог её не
-- отдаёт, а браузер про неё не знает. То есть «уровень качества» существовал
-- как намерение и не существовал как выбор.
--
-- ЧТО СТАНОВИТСЯ. Режим описывается тремя полями: код (машинное имя), надпись
-- (то, что читает человек) и разрешение, которое этот режим означает. Больше
-- ничего в режиме нет намеренно: разрешение уже входит и в цену
-- (generation_strategy_route_price принимает его отдельным аргументом), и в
-- подпись снимка, и в строку подтверждения расхода. Значит выбор режима
-- проходит весь денежный контур по уже проверенному пути, и ни одной новой
-- величины подписывать не нужно.
--
-- ПОЧЕМУ У ДВУХ МАРШРУТОВ РЕЖИМ ОДИН. Честность важнее симметрии. Pika Swaps
-- меняет названную область внутри готового кадра, Kling правит готовое видео —
-- у обоих разрешение результата задаёт ИСХОДНИК, и выбора разрешения у них нет
-- вовсе. Нарисовать им «720p / 1080p» значило бы продать человеку переключатель,
-- который ничего не переключает, и — хуже — записать в подпись цены
-- разрешение, которого в результате не будет. Поэтому у обоих ровно один режим
-- с честной надписью «Как в исходнике». Настоящий выбор разрешения есть только
-- у Runway, который собирает кадр заново, и там он и показывается — вместе с
-- разной ценой: десять секунд стоят 428 центов в 720p и 468 в 1080p.
--
-- ДЕНЬГИ. Ни одна цена здесь не меняется: ставки, пределы и версии прайса не
-- трогаются вовсе, а verify-блок сверяет цену действующего маршрута до и после
-- до цента.

select set_config(
  'contentengine.quality_modes_route_before',
  coalesce(
    (
      select jsonb_build_object(
        'provider', route.provider,
        'model_key', route.model_key,
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

-- 1. Новое содержимое. Записывается ДО ограничения: старые строки со списком
--    голых строк ограничению не удовлетворяют, и порядок здесь — часть смысла.
update content_factory.generation_strategy_provider_routes as route
set quality_modes = case
    when route.provider = 'runway' then jsonb_build_array(
      jsonb_build_object(
        'code', 'standard', 'label', 'Стандарт', 'resolution', '720p'
      ),
      jsonb_build_object(
        'code', 'max', 'label', 'Максимум', 'resolution', '1080p'
      )
    )
    else jsonb_build_array(
      jsonb_build_object(
        'code', 'source', 'label', 'Как в исходнике', 'resolution', '720p'
      )
    )
  end,
  updated_at = now()
where route.strategy_id in (
  'viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild'
);

-- 2. Форма режима. Ограничение описывает ровно то, на что опирается экран:
--    непустой список, у каждого режима три поля, разрешение из известных двух,
--    коды не повторяются. Список без режимов запрещён — движок, у которого
--    нечего выбрать, не должен рисовать пустую ступень.
--
--    Проверка живёт в функции, а не прямо в check: подзапросы в ограничениях
--    Postgres запрещает, а обойти это разворачиванием массива в выражении
--    нельзя. Функция immutable и не читает ни одной таблицы — она смотрит
--    только на переданное значение, поэтому годится для ограничения.
create or replace function
  content_factory_private.generation_strategy_quality_modes_valid(
    p_modes jsonb
  )
returns boolean
language sql
immutable
set search_path = ''
as $quality_modes_valid$
  select jsonb_typeof(p_modes) = 'array'
    and jsonb_array_length(p_modes) between 1 and 6
    and not exists (
      select 1
      from jsonb_array_elements(p_modes) as mode(value)
      where jsonb_typeof(mode.value) <> 'object'
        or mode.value - array['code', 'label', 'resolution']::text[]
             <> '{}'::jsonb
        or not mode.value ?& array['code', 'label', 'resolution']::text[]
        or coalesce(mode.value ->> 'code', '') !~ '^[a-z][a-z0-9_]{1,30}$'
        or length(coalesce(mode.value ->> 'label', '')) not between 2 and 40
        or coalesce(mode.value ->> 'resolution', '') not in ('720p', '1080p')
    )
    and (
      select count(distinct mode.value ->> 'code')
      from jsonb_array_elements(p_modes) as mode(value)
    ) = jsonb_array_length(p_modes);
$quality_modes_valid$;

alter table content_factory.generation_strategy_provider_routes
  drop constraint if exists generation_strategy_provider_routes_quality_check;
alter table content_factory.generation_strategy_provider_routes
  add constraint generation_strategy_provider_routes_quality_check
  check (
    content_factory_private.generation_strategy_quality_modes_valid(
      quality_modes
    )
  );

-- 3. Каталог отдаёт режимы вместе с остальными полями маршрута.
do $catalog_quality_modes$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text :=
    $f$'max_duration_seconds', route.max_duration_seconds,$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_catalog_policy';
  if definition_value is null then
    raise exception using message = 'catalog_policy_missing';
  end if;

  -- Повторный прогон не должен добавить поле второй раз.
  if position('quality_modes' in definition_value) > 0 then
    return;
  end if;

  -- Якорь обязан быть единственным: замена по неуникальному фрагменту
  -- размножила бы поле молча. Якорем взято поле из 202608190003 — если той
  -- миграции в цепочке нет, эта падает громко, а не патчит наугад.
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
              ''quality_modes'', route.quality_modes,'
  );
  if position('quality_modes' in patched_value) = 0 then
    raise exception using message = 'catalog_policy_patch_failed';
  end if;

  execute patched_value;
end;
$catalog_quality_modes$;

revoke all on function
  public.system_generation_strategy_catalog_policy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_generation_strategy_catalog_policy(jsonb)
  to service_role;

do $quality_modes_verify$
declare
  before_text text;
  before_value jsonb;
  after_value jsonb;
  definition_value text;
  catalog_value jsonb;
  organization_id_value uuid;
  mismatched_routes integer;
  runway_modes jsonb;
  fal_modes jsonb;
begin
  -- 1. Действующий маршрут и его цена не сдвинулись.
  before_text := current_setting(
    'contentengine.quality_modes_route_before', true
  );
  if before_text is null then
    raise exception using message = 'active_route_snapshot_missing';
  end if;
  before_value := case when before_text = '' then null
    else before_text::jsonb end;
  select jsonb_build_object(
    'provider', route.provider,
    'model_key', route.model_key,
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

  -- 2. У Runway два режима с разными разрешениями, у маршрутов fal — ровно
  --    один, и он не обещает выбора, которого нет.
  select route.quality_modes into runway_modes
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap' and route.provider = 'runway';
  select route.quality_modes into fal_modes
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.provider = 'fal'
    and route.model_key = 'fal-ai/pika/v2/pikaswaps';
  if runway_modes is null
     or jsonb_array_length(runway_modes) <> 2
     or runway_modes #>> '{0,resolution}' <> '720p'
     or runway_modes #>> '{1,resolution}' <> '1080p'
     or fal_modes is null
     or jsonb_array_length(fal_modes) <> 1
     or fal_modes #>> '{0,resolution}' <> '720p' then
    raise exception using message = 'quality_modes_content_drifted';
  end if;

  -- 3. Оба режима Runway имеют цену, и она разная: одинаковая означала бы, что
  --    ступень качества ничего не выбирает.
  if content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'runway', 'aleph2', 10, '720p', 'source', false
     ) ->> 'estimated_cost_minor' <> '428'
     or content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'runway', 'aleph2', 10, '1080p', 'source', false
     ) ->> 'estimated_cost_minor' <> '468' then
    raise exception using message = 'quality_mode_price_drifted';
  end if;

  -- 4. Каталог отдаёт режимы каждой строки реестра дословно, а прежние поля
  --    маршрута на месте: экран читает их все.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_catalog_policy';
  if definition_value is null
     or position('quality_modes' in definition_value) = 0
     or position('min_duration_seconds' in definition_value) = 0
     or position('/v1/video_to_video' in definition_value) = 0 then
    raise exception using message = 'catalog_policy_verify_failed';
  end if;

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
        and route_item -> 'quality_modes' = route.quality_modes
    );
    if mismatched_routes > 0 then
      raise exception using
        message = 'catalog_quality_modes_mismatch:' || mismatched_routes::text;
    end if;
  end if;
end;
$quality_modes_verify$;

commit;
