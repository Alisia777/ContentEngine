begin;

-- 202608230011_provider_policy_stops_promising_availability_v1
--
-- Витрина перестаёт обещать то, чего нет.
--
-- ЗАДАЧА. Миграция 202608230010 заперла платный старт стратегии без
-- исполнимого маршрута. Но политика провайдера — та самая, по которой экран
-- решает «готово / не готово», — про этот замок не знает и продолжает отвечать
-- «доступно». Оператор видит кнопку, жмёт её и получает отказ. Отказ честный и
-- до денег, но обещание было ложным.
--
-- ПОЧЕМУ ВЫДУМАННЫЙ МАРШРУТ ОСТАЁТСЯ В ОТВЕТЕ. Хочется убрать синтез
-- runway/gen4_turbo целиком — он и есть источник лжи. Нельзя: читатель
-- ответа в edge (`creator-generate/index.ts`, разбор ответа политики) требует
-- НЕПУСТОГО провайдера и известной версии прайса У КАЖДОЙ стратегии каталога.
-- Обнулив поля «Создания», мы уронили бы чтение каталога целиком — то есть
-- сломали бы и «Копию», которая работает.
--
-- Поэтому правится не витрина, а ПОЛНОМОЧИЕ: поля описания остаются, но
-- `enabled` становится честным, а в списке помех появляется названная причина.
-- Убрать синтез можно будет только вместе с правкой читателя, и это отдельная
-- работа с отдельной проверкой.
--
-- ПРИЗНАК ТОТ ЖЕ, ЧТО У ЗАМКА. Используется та же функция
-- `generation_strategy_executable_route_exists`, что и в привязке. Два места,
-- один источник: разойтись «можно запустить» и «показано как доступное» не
-- должны, иначе экран снова начнёт обещать.

do $policy_no_false_promise$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
  );
  if position('generation_strategy_no_executable_route' in source_text) > 0 then
    return;
  end if;
  patched_text := source_text;

  -- 1. Полномочие. `coalesce` здесь не украшение: при отсутствии маршрута
  --    соседние признаки могут оказаться NULL, а `enabled` обязан остаться
  --    настоящим булевым — читатель edge требует именно boolean.
  anchor := E'  launch_enabled_value := binding_current_value and approved_spec_value\n'
         || E'    and receipt_current_value and receipt_unconsumed_value\n'
         || E'    and route_current_value\n'
         || E'    and start_path_integrated_value and sql_provider_gate_value;';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'policy_anchor_launch_enabled';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  launch_enabled_value := coalesce(\n'
      || E'    binding_current_value and approved_spec_value\n'
      || E'      and receipt_current_value and receipt_unconsumed_value\n'
      || E'      and route_current_value\n'
      || E'      and start_path_integrated_value and sql_provider_gate_value,\n'
      || E'    false\n'
      || E'  )\n'
      || E'  -- Тот же признак, что запирает привязку (202608230010). Без него\n'
      || E'  -- витрина обещала бы доступность стратегии, у которой нет ни одной\n'
      || E'  -- включённой строки реестра, — и кнопка вела бы в отказ.\n'
      || E'  and content_factory_private\n'
      || E'    .generation_strategy_executable_route_exists(strategy_id_value);'
  );

  -- 2. Названная помеха. Без неё экран знает «нельзя», но не знает почему, и
  --    оператору остаётся гадать.
  anchor := E'  if not sql_provider_gate_value then\n'
         || E'    blockers_value := blockers_value ||\n'
         || E'      jsonb_build_array(''provider_configuration_disabled'');\n'
         || E'  end if;';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'policy_anchor_blockers';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  if not content_factory_private\n'
      || E'       .generation_strategy_executable_route_exists(strategy_id_value)\n'
      || E'  then\n'
      || E'    blockers_value := blockers_value ||\n'
      || E'      jsonb_build_array(''generation_strategy_no_executable_route'');\n'
      || E'  end if;\n'
      || E'  if not sql_provider_gate_value then\n'
      || E'    blockers_value := blockers_value ||\n'
      || E'      jsonb_build_array(''provider_configuration_disabled'');\n'
      || E'  end if;'
  );

  if patched_text = source_text then
    raise exception using message = 'policy_unchanged';
  end if;
  execute patched_text;
end;
$policy_no_false_promise$;

-- ПРОВЕРКА.
do $policy_verify$
declare
  body text;
begin
  body := pg_get_functiondef(
    'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
  );

  -- 1. Полномочие опирается на тот же признак, что и замок привязки.
  if position(
       'generation_strategy_executable_route_exists(strategy_id_value)' in body
     ) = 0 then
    raise exception using message = 'policy_does_not_use_the_lock';
  end if;

  -- 2. Помеха названа.
  if position('''generation_strategy_no_executable_route''' in body) = 0 then
    raise exception using message = 'policy_blocker_missing';
  end if;

  -- 3. `enabled` остался настоящим булевым: читатель edge требует именно его,
  --    и NULL уронил бы разбор ответа целиком — вместе с «Копией».
  if position('launch_enabled_value := coalesce(' in body) = 0 then
    raise exception using message = 'policy_enabled_may_be_null';
  end if;

  -- 4. Описание маршрута НЕ обнулено. Убрать синтез можно только вместе с
  --    правкой читателя; сделав это здесь, мы сломали бы чтение каталога у
  --    всех трёх стратегий сразу.
  if position('route_model_key_value := ''gen4_turbo''' in body) = 0 then
    raise exception using message = 'policy_route_shape_removed_too_early';
  end if;

  -- 5. Замок на месте и отвечает по реестру.
  if not content_factory_private
       .generation_strategy_executable_route_exists('viral_product_swap')
     or content_factory_private
       .generation_strategy_executable_route_exists('viral_rebuild')
     or content_factory_private
       .generation_strategy_executable_route_exists('viral_avatar_ugc') then
    raise exception using message = 'executable_route_predicate_drifted';
  end if;
end;
$policy_verify$;

commit;
