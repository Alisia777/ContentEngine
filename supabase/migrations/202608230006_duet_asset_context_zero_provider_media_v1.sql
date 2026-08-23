begin;

-- 202608230006_duet_asset_context_zero_provider_media_v1
--
-- «Дуэт»: контекст ассетов честно говорит «провайдеру не уходит ничего».
--
-- ЗАДАЧА. Провайдер «Дуэта» не получает НИ ОДНОГО медиа: он делает только
-- говорящего ведущего, а соединение с роликом происходит у нас. Но исходник
-- обязан быть в контексте наряда — это его собственный входной файл: по нему
-- считается длительность, из него берётся имя объекта, и он же нужен сборке.
--
-- ПОЧЕМУ ПУСТОЙ МАССИВ — НЕВЕРНЫЙ ОТВЕТ. Три независимых препятствия, каждого
-- достаточно:
--   • `system_claim_generation_strategy_start` требует непустой набор ссылок и
--     непустое имя входного объекта;
--   • триггер `guard_generation_job_contract` требует `input_object_name`
--     длиннее десяти знаков — пустой контекст оставил бы его пустым;
--   • edge отвергает пустой массив раньше всех.
-- Ослабить эти проверки ради дуэта значило бы снять единственную защиту от
-- «контекст пуст, потому что медиа уехало» — у ВСЕХ стратегий сразу.
--
-- ВЕРНЫЙ ОТВЕТ: ассет есть, а места в теле запроса у него нет. Утверждение
-- «провайдеру ничего не уходит» выражается ПОЛОЖИТЕЛЬНО — `provider_field`
-- равен null — и потому проверяемо. Edge этого уже ждёт: для дуэта он требует
-- ровно один `source_video` с пустым полем провайдера.
--
-- ФИЛЬТР СУЖАЕТСЯ, А НЕ СНИМАЕТСЯ. Он выглядит как исключение для «Аватара», но
-- обслуживает и «Создание»: у `viral_rebuild` `source_video` есть в выборе и
-- НЕТ в реестре вложений, а его ветка счётчика (`… - 1`) существует именно
-- поэтому. Снять фильтр целиком значило бы молча сломать «Создание» — все его
-- запуски начали бы падать на `generation_strategy_asset_context_invalid`.
--
-- СЧЁТЧИК: НЕ 1, А ДЛИНА ПОДПИСАННОГО ВЫБОРА. Двойка была магическим числом,
-- которое пережило смену смысла стратегии и никого не разбудило. Единица прожила
-- бы ровно до следующей смены. Длина `selection_snapshot -> 'assets'` — величина
-- подписанная квитанцией, и разойтись с формой выбора незаметно она не может:
-- расхождение и есть то, что проверка ищет.

do $duet_asset_context$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_strategy_asset_context(uuid,uuid)'
      ::regprocedure
  );
  if position('when ''viral_avatar_ugc'' then null' in source_text) > 0 then
    return;
  end if;
  patched_text := source_text;

  -- 1. У исходника «Дуэта» нет места в теле запроса.
  anchor := E'      when ''source_video'' then ''referenceVideo''';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_context_anchor_provider_field';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'      when ''source_video'' then case receipt.strategy_id\n'
      || E'        when ''viral_avatar_ugc'' then null\n'
      || E'        else ''referenceVideo'' end'
  );

  -- 2. Исходник «Дуэта» остаётся в контексте: это вход НАРЯДА, а не провайдера.
  anchor := E'    and (\n'
         || E'      receipt.strategy_id = ''viral_product_swap''\n'
         || E'      or selected.value ->> ''role'' <> ''source_video''\n'
         || E'    )';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_context_anchor_source_filter';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    and (\n'
      || E'      receipt.strategy_id in (''viral_product_swap'', ''viral_avatar_ugc'')\n'
      || E'      or selected.value ->> ''role'' <> ''source_video''\n'
      || E'    )'
  );

  if patched_text = source_text then
    raise exception using message = 'duet_asset_context_unchanged';
  end if;
  execute patched_text;
end;
$duet_asset_context$;

-- Счётчик ассетов в двух живых функциях. Правка одинаковая, поэтому идёт
-- циклом: разойтись эти две проверки не должны даже на один деплой.
do $duet_asset_counts$
declare
  target text;
  source_text text;
  patched_text text;
  anchor constant text := E'when ''viral_avatar_ugc'' then 2';
  replacement constant text :=
    E'when ''viral_avatar_ugc'' then\n'
    || E'         jsonb_array_length(receipt_row.selection_snapshot -> ''assets'')';
  hits integer;
begin
  foreach target in array array[
    'public.system_claim_generation_strategy_start(jsonb)',
    'public.system_mark_generation_strategy_dispatch_attempt(jsonb)'
  ] loop
    source_text := pg_get_functiondef(target::regprocedure);
    if position(anchor in source_text) = 0 then
      -- Уже пропатчено этим же файлом: повторный прогон обязан быть тихим.
      continue;
    end if;
    hits := (length(source_text) - length(replace(source_text, anchor, '')))
            / length(anchor);
    if hits <> 1 then
      raise exception using message =
        'duet_asset_count_anchor_invalid:' || target || ':' || hits::text;
    end if;
    patched_text := replace(source_text, anchor, replacement);
    execute patched_text;
  end loop;
end;
$duet_asset_counts$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
--
-- `generation_strategy_asset_context` читает квитанцию, и без неё отдаёт пустой
-- массив — это проверяется вызовом. Соответствие формы проверяется структурно,
-- с прямым признанием почему: квитанция тянет за собой десяток таблиц, и
-- собрать её здесь значило бы проверять свою же заготовку.
do $duet_asset_context_verify$
declare
  context_body text;
  claim_body text;
  attempt_body text;
begin
  if content_factory_private.generation_strategy_asset_context(
       '11111111-1111-4111-8111-111111111111'::uuid,
       '22222222-2222-4222-8222-222222222222'::uuid
     ) is distinct from '[]'::jsonb then
    raise exception using message = 'asset_context_missing_receipt_not_empty';
  end if;

  context_body := pg_get_functiondef(
    'content_factory_private.generation_strategy_asset_context(uuid,uuid)'
      ::regprocedure
  );
  claim_body := pg_get_functiondef(
    'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
  );
  attempt_body := pg_get_functiondef(
    'public.system_mark_generation_strategy_dispatch_attempt(jsonb)'::regprocedure
  );

  -- Провайдеру «Дуэта» не уходит ничего, и это сказано положительно.
  if position('when ''viral_avatar_ugc'' then null' in context_body) = 0 then
    raise exception using message = 'duet_provider_field_not_null';
  end if;

  -- «Копия» по-прежнему отдаёт исходник провайдеру: её ссылка на него — это
  -- настоящий вход запроса, и потерять её значило бы сломать платный путь.
  if position('else ''referenceVideo'' end' in context_body) = 0 then
    raise exception using message = 'product_swap_reference_video_lost';
  end if;

  -- Фильтр СУЖЕН, а не снят: «Создание» по-прежнему не видит исходник в
  -- контексте, и его ветка счётчика «минус один» остаётся верной.
  if position(
       'receipt.strategy_id in (''viral_product_swap'', ''viral_avatar_ugc'')'
       in context_body
     ) = 0 then
    raise exception using message = 'duet_context_filter_not_narrowed';
  end if;
  if position('or selected.value ->> ''role'' <> ''source_video''' in context_body) = 0
  then
    raise exception using message = 'viral_rebuild_source_exclusion_lost';
  end if;

  -- Магическая двойка ушла из обеих функций, и обе считают одинаково.
  if position('''viral_avatar_ugc'' then 2' in claim_body) > 0
     or position('''viral_avatar_ugc'' then 2' in attempt_body) > 0 then
    raise exception using message = 'duet_asset_count_still_hardcoded';
  end if;
  if position('receipt_row.selection_snapshot -> ''assets''' in claim_body) = 0
     or position('receipt_row.selection_snapshot -> ''assets''' in attempt_body) = 0
  then
    raise exception using message = 'duet_asset_count_not_signed';
  end if;

  -- Ветка «Создания» на месте в обеих: у него ассетов на один меньше, чем в
  -- выборе, потому что исходник в контекст не попадает.
  if position(
       'else jsonb_array_length(receipt_row.selection_snapshot -> ''assets'') - 1'
       in claim_body
     ) = 0
     or position(
       'else jsonb_array_length(receipt_row.selection_snapshot -> ''assets'') - 1'
       in attempt_body
     ) = 0 then
    raise exception using message = 'viral_rebuild_asset_count_branch_lost';
  end if;
end;
$duet_asset_context_verify$;

commit;
