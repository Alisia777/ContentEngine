begin;

-- 202608190008_generation_strategy_source_duration_price_v1
--
-- Посекундный маршрут резервирует деньги за ту длительность, которую он
-- действительно оплатит.
--
-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и комментарий перед BEGIN отвергает
-- вместе с ним всю цепочку. Поэтому «почему» живёт внутри транзакции.
--
-- ЧТО НАБЛЮДАЛОСЬ. Длительность в форме — выбор оператора, и цена считается по
-- ней. Для Runway это верно: он собирает ролик заново и делает ровно столько
-- секунд, сколько попросили. Для маршрутов правки видео это неверно в самой
-- основе: и Pika, и Kling берут готовый ролик и отдают ролик той же длины —
-- параметра длительности у них нет вовсе. У Pika это безобидно, потому что
-- платится ролик целиком. У Kling ставка ПОСЕКУНДНАЯ.
--
-- ПОЧЕМУ ЭТО ДЫРА, А НЕ НЕТОЧНОСТЬ. Оператор выбирает 5 секунд на исходнике
-- длиной 12 — резерв 85 центов, а провайдер выставит счёт за 12 секунд, то
-- есть 204. Разница не возвращается и не замечается: сверка сравнивает наряд
-- с ЕГО ЖЕ снимком цены, а снимок непротиворечив — он просто описывает не тот
-- ролик, который сделали. Дыра тем опаснее, что открывается обычной работой,
-- без единой ошибки оператора.
--
-- ЧТО ДЕЛАЕТ ЭТА МИГРАЦИЯ. У маршрута появляется свойство «кто задаёт
-- длительность»: сам оператор или исходник. А привязка для маршрута с
-- посекундной ставкой перестаёт принимать длительность на слово: она обязана
-- совпасть с длительностью исходника, ИЗМЕРЕННОЙ СЕРВЕРОМ
-- (generation_strategy_media_durations, бесплатная проверка MP4), округлённой
-- вверх до секунды. Вверх — потому что провайдер не умеет отдать меньше, чем
-- есть, и резерв обязан быть не меньше списания.
--
-- ПОЧЕМУ ОТКАЗ, А НЕ ТИХАЯ ПОДСТАНОВКА. Подставить длительность молча — значит
-- показать человеку одну цену, а списать другую. Отказ случается до денег, а
-- экран умеет выставить правильное значение сам: длительность исходника ему
-- известна из той же серверной проверки.
--
-- ЧЕГО ЭТА МИГРАЦИЯ НЕ ТРОГАЕТ. Маршрут с ценой за ролик (Pika) и ступенчатый
-- Runway ведут себя как прежде: у первого длительность на цену не влияет
-- вовсе, у второго её действительно задаёт оператор. Требование включается
-- ровно там, где секунда стоит денег.

select set_config(
  'contentengine.source_duration_route_before',
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

-- 1. Кто задаёт длительность у этого маршрута. Значение по умолчанию —
--    'operator_choice': оно описывает поведение, которое было до сих пор, и
--    поэтому не меняет ни одной существующей строки молча.
alter table content_factory.generation_strategy_provider_routes
  add column if not exists duration_source text not null
    default 'operator_choice';
alter table content_factory.generation_strategy_provider_routes
  drop constraint if exists
    generation_strategy_provider_routes_duration_source_check;
alter table content_factory.generation_strategy_provider_routes
  add constraint generation_strategy_provider_routes_duration_source_check
  check (duration_source in ('operator_choice', 'source_video'));

-- Правка видео отдаёт ролик той же длины, что и вход: у обеих моделей fal
-- параметра длительности нет вовсе.
update content_factory.generation_strategy_provider_routes as route
set duration_source = 'source_video',
    updated_at = now()
where route.provider = 'fal'
  and route.poll_kind = 'fal_request'
  and route.duration_source <> 'source_video';

-- 2. Привязка сверяет длительность с измеренной сервером.
do $source_duration_bind$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text := $f$  if source_attachment_row.id is null then
    raise exception using errcode = '42501',
      message = 'generation_strategy_exact_source_attachment_required';
  end if;$f$;
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

  -- Порядок в цепочке важен: эта миграция дописывает проверку в функцию,
  -- которую 202608190006 уже научила принимать движок. Без неё проверять
  -- нечего, и молчаливый пропуск был бы хуже отказа.
  if position('engine_choice_v1' in definition_value) = 0 then
    raise exception using message = 'engine_choice_migration_missing';
  end if;
  if position('source_duration_v1' in definition_value) > 0 then
    return;
  end if;

  anchor_hits := (
    length(definition_value)
    - length(replace(definition_value, anchor_text, ''))
  ) / length(anchor_text);
  if anchor_hits <> 1 then
    raise exception using
      message = 'source_duration_anchor_not_unique:' || anchor_hits::text;
  end if;

  patched_value := replace(
    definition_value,
    anchor_text,
    anchor_text || '

  -- source_duration_v1: секунда стоит денег — значит длительность обязана быть
  -- измеренной, а не заявленной. Проверка стоит здесь, а не рядом с расчётом
  -- цены: исходник становится известен только после разбора ассетов, а цена
  -- считается раньше. Отказ отменяет всю транзакцию вместе с расчётом, поэтому
  -- подписанной цены за неизмеренную длительность не существует.
  if p_payload ? ''engine'' then
    declare
      route_price_kind text;
      measured_seconds numeric;
    begin
      select route.price_kind into route_price_kind
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = strategy_id_value
        and route.provider = p_payload #>> ''{engine,provider}''
        and route.model_key = p_payload #>> ''{engine,model_key}'';
      if route_price_kind = ''usd_minor_per_second'' then
        select duration.duration_seconds into measured_seconds
        from content_factory.generation_strategy_media_durations as duration
        where duration.organization_id = organization_id_value
          and duration.media_object_id = source_media_id_value
        order by duration.verified_at desc
        limit 1;
        if measured_seconds is null
           or measured_seconds <= 0
           or duration_seconds_value <> ceil(measured_seconds)::integer then
          raise exception using errcode = ''22023'',
            message = ''generation_strategy_source_duration_mismatch'';
        end if;
      end if;
    end;
  end if;'
  );

  if position('source_duration_v1' in patched_value) = 0
     or position('generation_strategy_source_duration_mismatch' in patched_value)
        = 0 then
    raise exception using message = 'source_duration_patch_failed';
  end if;

  execute patched_value;
end;
$source_duration_bind$;

revoke all on function
  public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)
  to service_role;

-- 3. Каталог отдаёт свойство маршрута: экран обязан объяснить человеку, почему
--    у одной модели длительность выбирается, а у другой показана фактом.
do $catalog_duration_source$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text :=
    $f$'quality_modes', route.quality_modes,$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_catalog_policy';
  if definition_value is null then
    raise exception using message = 'catalog_policy_missing';
  end if;

  if position('duration_source' in definition_value) > 0 then
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
              ''duration_source'', route.duration_source,'
  );
  if position('duration_source' in patched_value) = 0 then
    raise exception using message = 'catalog_policy_patch_failed';
  end if;

  execute patched_value;
end;
$catalog_duration_source$;

revoke all on function
  public.system_generation_strategy_catalog_policy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_generation_strategy_catalog_policy(jsonb)
  to service_role;

do $source_duration_verify$
declare
  before_text text;
  before_value jsonb;
  after_value jsonb;
  definition_value text;
  drifted_routes integer;
begin
  -- 1. Действующий маршрут и его цена не сдвинулись.
  before_text := current_setting(
    'contentengine.source_duration_route_before', true
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

  -- 2. Длительность задаёт исходник ровно у правки видео, и только у неё.
  select count(*) into drifted_routes
  from content_factory.generation_strategy_provider_routes as route
  where (route.poll_kind = 'fal_request')
    is distinct from (route.duration_source = 'source_video');
  if drifted_routes > 0 then
    raise exception using
      message = 'duration_source_drifted:' || drifted_routes::text;
  end if;

  -- 3. Обе функции несут правку.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname =
      'system_resolve_and_bind_generation_strategy_pre_execution_v1';
  if definition_value is null
     or position('source_duration_v1' in definition_value) = 0
     or position('engine_choice_v1' in definition_value) = 0
     or position('generation_strategy_media_durations' in definition_value) = 0
  then
    raise exception using message = 'bind_verify_failed';
  end if;

  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_catalog_policy';
  if definition_value is null
     or position('duration_source' in definition_value) = 0
     or position('quality_modes' in definition_value) = 0
     or position('/v1/video_to_video' in definition_value) = 0 then
    raise exception using message = 'catalog_verify_failed';
  end if;
end;
$source_duration_verify$;

commit;
