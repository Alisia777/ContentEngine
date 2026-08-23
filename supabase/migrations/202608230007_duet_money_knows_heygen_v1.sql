begin;

-- 202608230007_duet_money_knows_heygen_v1
--
-- Денежный контур признаёт третьего провайдера, а цена перестаёт врать.
--
-- ЧЕТЫРЕ ПРАВКИ, И ТОЛЬКО ОДНА ИЗ НИХ ПРО ОТКАЗЫ.
--
-- 1. ШЕСТЬ СТОРОЖЕЙ. Те же самые, что чинились для fal в 202608190011, и по той
--    же причине. Опаснее всего здесь не отказ, а МОЛЧАНИЕ: при незнакомом
--    провайдере `reserve_generation_campaign_spend` и
--    `record_real_generation_spend_lifecycle` просто возвращают `new` — бронь
--    не проверяется кампанийным потолком, а расчёт по факту не наступает
--    никогда. Деньги ушли бы вне учёта и остались бы занятыми навсегда.
--
--    Это НЕ ослабление. Перечисленные списки решают, применять ли контроль
--    вообще, а не пропускать ли платёж мимо него. До правки heygen оставался
--    вне кампанийного потолка, вне сверки со спецификацией и вне журнала трат.
--
-- 2. `generation_strategy_provider_known`. Стоит в CHECK партии генераций.
--    Незнакомый провайдер даёт `23514` — нарушение ограничения, отказ без
--    имени, который портал показать не умеет. Отказ должен быть внятным.
--
-- 3. ЦЕНА. Самое дорогое здесь. Сегодня запуск БЕЗ явного движка считается по
--    каталогу рецептов, а каталог отвечает за «Дуэт» так:
--
--      provider "runway", recipe "product_ugc", $3.36 за 8 секунд,
--      spend_confirmation RUNWAY_PRODUCT_UGC_8S_720P_AUDIO_USD_3.36
--
--    Настоящий «Дуэт» — это heygen по пять центов за секунду, то есть $0.40 за
--    те же 8 секунд. Восьмикратная переплата провайдеру, которого никто не
--    вызовет: привязка ушла бы с provider='runway', а отправлять надо в heygen.
--
--    Правило становится таким: реестр маршрутов — источник истины, каталог
--    рецептов — только для стратегий, у которых реестра НЕТ вовсе («Создание»).
--    Есть строки, но нет включённой рекомендованной — цена NULL, то есть
--    громкий отказ `generation_strategy_catalog_selection_invalid` ДО денег.
--
--    «Копия» этого не почувствует, и это проверено: её каталожная цена и цена
--    рекомендованного маршрута (pika/v2/pikaswaps) совпадают побайтно — те же
--    47 центов, та же версия прайса, та же строка подтверждения. Правка меняет
--    источник числа, а не само число.
--
--    Ровно так же уже устроен `system_record_generation_strategy_readiness`:
--    там откат на каталог давно обусловлен отсутствием строк реестра. Две
--    функции считали цену по разным правилам — и это само по себе означало,
--    что проверка готовности могла не согласиться с привязкой.
--
-- 4. ИМЯ РУБИЛЬНИКА. `generation_spend_platform_control` — единственная строка,
--    гасящая ВСЮ платную генерацию: и runway, и fal, и теперь heygen. Ключ при
--    этом называется `runway_paid_generation`. Портал уже говорит правду
--    («Общий защитный рубильник платной генерации»), а база — нет. Имя, которое
--    врёт про охват аварийного выключателя, однажды приведёт к тому, что его не
--    тронут, посчитав частным.
--
--    Переименование замкнуто: ссылок нет ни в edge, ни в портале, ни в тестах —
--    только четыре тела функций и CHECK самой таблицы. Внешних ключей на неё
--    нет.
--
-- ЧЕГО ЭТА МИГРАЦИЯ НЕ ДЕЛАЕТ. Маршрут «Дуэта» остаётся ВЫКЛЮЧЕННЫМ. Ни одна
-- строка здесь не может стоить денег: включение — последний шаг всей работы, и
-- он будет отдельным файлом с отдельным решением.

-- 1. Шесть сторожей.
do $spend_guards_heygen$
declare
  target text;
  definition_value text;
  patched_value text;
  hits integer;
begin
  foreach target in array array[
    'reserve_real_generation_spend',
    'guard_real_generation_spend_start',
    'guard_generation_campaign_spend_start',
    'guard_generation_spec_provider_start',
    'reserve_generation_campaign_spend',
    'record_real_generation_spend_lifecycle'
  ] loop
    select pg_get_functiondef(p.oid) into definition_value
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private' and p.proname = target;
    if definition_value is null then
      raise exception using message = 'spend_guard_missing:' || target;
    end if;

    -- Повторный прогон обязан быть тихим.
    if position($f$'runway','google','fal','heygen'$f$ in definition_value) > 0 then
      continue;
    end if;

    hits := (
      length(definition_value)
      - length(replace(definition_value, $f$'runway','google','fal'$f$, ''))
    ) / length($f$'runway','google','fal'$f$);
    if hits < 1 then
      raise exception using message = 'spend_guard_anchor_missing:' || target;
    end if;

    -- Заменяются ВСЕ вхождения: в guard_real_generation_spend_start списка два,
    -- и починка одного оставила бы функцию противоречащей самой себе — отказ на
    -- половине денежного пути, самый дорогой из возможных.
    patched_value := replace(
      definition_value,
      $f$'runway','google','fal'$f$,
      $f$'runway','google','fal','heygen'$f$
    );
    execute patched_value;
  end loop;
end;
$spend_guards_heygen$;

-- 2. Признание провайдера в контракте партии.
create or replace function content_factory_private.generation_strategy_provider_known(
  p_provider text
) returns boolean
language sql
immutable
set search_path to ''
as $function$
  select p_provider in ('runway', 'fal', 'heygen');
$function$;

-- 3. Цена без явного движка приходит из реестра.
do $bind_price_from_registry$
declare
  source_text text;
  patched_text text;
  anchor constant text :=
    E'  else\n'
    || E'    price_value := content_factory_private.generation_strategy_recipe_price(\n'
    || E'      strategy_id_value, duration_seconds_value, resolution_value,\n'
    || E'      ratio_value, audio_value\n'
    || E'    );\n'
    || E'  end if;';
  hits integer;
begin
  source_text := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );
  if position('registry_price_owns_the_engineless_request' in source_text) > 0 then
    return;
  end if;

  hits := (length(source_text) - length(replace(source_text, anchor, '')))
          / length(anchor);
  if hits <> 1 then
    raise exception using message = 'bind_price_anchor_invalid:' || hits::text;
  end if;

  patched_text := replace(
    source_text,
    anchor,
    E'  else\n'
      || E'    -- registry_price_owns_the_engineless_request\n'
      || E'    --\n'
      || E'    -- Реестр маршрутов — источник истины о цене. Каталог рецептов\n'
      || E'    -- остаётся только тем стратегиям, у которых реестра нет вовсе.\n'
      || E'    -- Иначе «Дуэт» считался бы по product_ugc, то есть по Runway и по\n'
      || E'    -- $3.36 за восемь секунд вместо сорока центов heygen, и уходил бы\n'
      || E'    -- в привязку с провайдером, которого никто не вызовет.\n'
      || E'    --\n'
      || E'    -- Рекомендованная строка не более одной на стратегию: это держит\n'
      || E'    -- частичный уникальный индекс\n'
      || E'    -- generation_strategy_provider_routes_recommended_key.\n'
      || E'    select content_factory_private.generation_strategy_route_price(\n'
      || E'             strategy_id_value, route.provider, route.model_key,\n'
      || E'             duration_seconds_value, resolution_value, ratio_value,\n'
      || E'             audio_value\n'
      || E'           ) into price_value\n'
      || E'    from content_factory.generation_strategy_provider_routes as route\n'
      || E'    where route.strategy_id = strategy_id_value\n'
      || E'      and route.recommended\n'
      || E'      and route.enabled\n'
      || E'      and content_factory_private\n'
      || E'        .generation_strategy_provider_route_allowed(\n'
      || E'          route.strategy_id,\n'
      || E'          route.provider,\n'
      || E'          route.model_key,\n'
      || E'          route.provider_path,\n'
      || E'          route.poll_kind,\n'
      || E'          route.pricing_version\n'
      || E'        );\n'
      || E'    -- Строк реестра нет — стратегия живёт по каталогу, как жила.\n'
      || E'    -- Строки есть, но включённой рекомендованной среди них нет — цена\n'
      || E'    -- остаётся NULL, и ниже это станет громким отказом до денег.\n'
      || E'    if not exists (\n'
      || E'      select 1\n'
      || E'      from content_factory.generation_strategy_provider_routes as route\n'
      || E'      where route.strategy_id = strategy_id_value\n'
      || E'    ) then\n'
      || E'      price_value := content_factory_private.generation_strategy_recipe_price(\n'
      || E'        strategy_id_value, duration_seconds_value, resolution_value,\n'
      || E'        ratio_value, audio_value\n'
      || E'      );\n'
      || E'    end if;\n'
      || E'  end if;'
  );
  if patched_text = source_text then
    raise exception using message = 'bind_price_unchanged';
  end if;
  execute patched_text;
end;
$bind_price_from_registry$;

-- 4. Рубильник называется тем, чем является.
do $platform_control_rename$
declare
  target text;
  definition_value text;
begin
  if exists (
    select 1
    from content_factory_private.generation_spend_platform_control
    where control_key = 'platform_paid_generation'
  ) then
    return;
  end if;

  alter table content_factory_private.generation_spend_platform_control
    drop constraint generation_spend_platform_control_control_key_check;
  update content_factory_private.generation_spend_platform_control
    set control_key = 'platform_paid_generation'
  where control_key = 'runway_paid_generation';
  alter table content_factory_private.generation_spend_platform_control
    add constraint generation_spend_platform_control_control_key_check
    check (control_key = 'platform_paid_generation');

  foreach target in array array[
    'content_factory_private.reserve_real_generation_spend()',
    'content_factory_private.guard_real_generation_spend_start()',
    'content_factory_private.generation_spend_organization_overview(uuid)',
    'public.system_update_generation_spend_control(jsonb)'
  ] loop
    definition_value := pg_get_functiondef(target::regprocedure);
    if position($k$'runway_paid_generation'$k$ in definition_value) = 0 then
      raise exception using message = 'platform_control_key_absent:' || target;
    end if;
    execute replace(
      definition_value,
      $k$'runway_paid_generation'$k$,
      $k$'platform_paid_generation'$k$
    );
  end loop;
end;
$platform_control_rename$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $money_knows_heygen_verify$
declare
  target text;
  definition_value text;
  remaining integer;
  duet_price jsonb;
  copy_price jsonb;
  rebuild_price jsonb;
begin
  -- 1. Ни одного списка без heygen. Разъехавшиеся списки — отказ на половине
  --    денежного пути, поэтому считается остаток, а не наличие.
  foreach target in array array[
    'reserve_real_generation_spend',
    'guard_real_generation_spend_start',
    'guard_generation_campaign_spend_start',
    'guard_generation_spec_provider_start',
    'reserve_generation_campaign_spend',
    'record_real_generation_spend_lifecycle'
  ] loop
    select pg_get_functiondef(p.oid) into definition_value
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private' and p.proname = target;
    if definition_value is null
       or position($f$'runway','google','fal','heygen'$f$ in definition_value) = 0
    then
      raise exception using message = 'spend_guard_verify_failed:' || target;
    end if;
    remaining := (
      length(definition_value)
      - length(replace(definition_value, $f$'runway','google','fal')$f$, ''))
    ) / length($f$'runway','google','fal')$f$);
    if remaining > 0 then
      raise exception using
        message = 'spend_guard_list_missed:' || target || ':' || remaining::text;
    end if;
  end loop;

  -- 2. Сторожа не разучились отказывать: проверяются сами сообщения, а не
  --    только списки. Расширение охвата не должно снимать защиту.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'guard_real_generation_spend_start';
  if position('generation_spend_paid_job_conversion_forbidden' in definition_value) = 0
     or position('generation_spend_reservation_identity_immutable' in definition_value) = 0
  then
    raise exception using message = 'spend_guard_messages_lost';
  end if;

  -- 3. Провайдер признан контрактом партии — и признание не стало всеядным.
  if not content_factory_private.generation_strategy_provider_known('heygen')
     or not content_factory_private.generation_strategy_provider_known('fal')
     or not content_factory_private.generation_strategy_provider_known('runway')
  then
    raise exception using message = 'provider_known_missing';
  end if;
  if content_factory_private.generation_strategy_provider_known('mock')
     or content_factory_private.generation_strategy_provider_known('google')
     or content_factory_private.generation_strategy_provider_known('')
  then
    raise exception using message = 'provider_known_too_permissive';
  end if;

  -- 4. Цена. Проверяется вызовом самих ценовых функций: у «Копии» источник
  --    числа сменился, а число обязано остаться прежним.
  duet_price := content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 8, '720p', 'source', true
  );
  copy_price := content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 8, '720p', 'source', true
  );
  rebuild_price := content_factory_private.generation_strategy_recipe_price(
    'viral_rebuild', 8, '720p', '720:1280', true
  );

  -- Каталог по-прежнему отвечает за «Дуэт» по-рунвеевски — и именно поэтому
  -- привязка больше не имеет права его спрашивать. Если этот каталожный ответ
  -- однажды исчезнет сам, проверка упадёт и заставит перечитать правило.
  if duet_price ->> 'provider' <> 'runway' then
    raise exception using message = 'duet_catalog_price_changed_shape';
  end if;
  if copy_price is distinct from
       content_factory_private.generation_strategy_route_price(
         'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
         8, '720p', 'source', true
       ) then
    raise exception using message = 'copy_catalog_and_route_prices_diverged';
  end if;
  if rebuild_price is null then
    raise exception using message = 'rebuild_catalog_price_lost';
  end if;

  -- Правило записано в теле привязки, и откат на каталог обусловлен.
  definition_value := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );
  if position('registry_price_owns_the_engineless_request' in definition_value) = 0
  then
    raise exception using message = 'bind_price_rule_missing';
  end if;
  if position(
       E'    if not exists (\n      select 1\n'
       || E'      from content_factory.generation_strategy_provider_routes as route\n'
       || E'      where route.strategy_id = strategy_id_value\n    ) then'
       in definition_value
     ) = 0 then
    raise exception using message = 'bind_price_fallback_not_conditional';
  end if;

  -- «Создание» — единственная стратегия без реестра, и откат существует ради
  -- неё. Если у неё однажды заведут маршрут, это утверждение упадёт первым.
  if exists (
    select 1 from content_factory.generation_strategy_provider_routes
    where strategy_id = 'viral_rebuild'
  ) then
    raise exception using message = 'viral_rebuild_gained_a_route';
  end if;

  -- 5. Рубильник переименован во всех телах и в ограничении.
  if not exists (
    select 1 from content_factory_private.generation_spend_platform_control
    where control_key = 'platform_paid_generation'
  ) then
    raise exception using message = 'platform_control_row_missing';
  end if;
  if exists (
    select 1 from content_factory_private.generation_spend_platform_control
    where control_key = 'runway_paid_generation'
  ) then
    raise exception using message = 'platform_control_old_row_left';
  end if;
  foreach target in array array[
    'content_factory_private.reserve_real_generation_spend()',
    'content_factory_private.guard_real_generation_spend_start()',
    'content_factory_private.generation_spend_organization_overview(uuid)',
    'public.system_update_generation_spend_control(jsonb)'
  ] loop
    definition_value := pg_get_functiondef(target::regprocedure);
    if position($k$'runway_paid_generation'$k$ in definition_value) > 0 then
      raise exception using message = 'platform_control_key_stale:' || target;
    end if;
    if position($k$'platform_paid_generation'$k$ in definition_value) = 0 then
      raise exception using message = 'platform_control_key_lost:' || target;
    end if;
  end loop;

  -- Рубильник остался ОДНОСТРОЧНЫМ: ограничение по-прежнему допускает ровно
  -- одно значение ключа. Иначе переименование тихо превратило бы общий
  -- выключатель в набор частных.
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_spend_platform_control_control_key_check'
      and conrelid =
        'content_factory_private.generation_spend_platform_control'::regclass
      and pg_get_constraintdef(oid) like '%platform_paid_generation%'
  ) then
    raise exception using message = 'platform_control_check_lost';
  end if;

  -- 6. Маршрут «Дуэта» по-прежнему выключен: этот файл денег стоить не может.
  if exists (
    select 1 from content_factory.generation_strategy_provider_routes
    where strategy_id = 'viral_avatar_ugc' and (enabled or recommended)
  ) then
    raise exception using message = 'duet_route_enabled_too_early';
  end if;
end;
$money_knows_heygen_verify$;

commit;
