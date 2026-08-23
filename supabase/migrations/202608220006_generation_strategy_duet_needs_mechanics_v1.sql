begin;

-- 202608220006_generation_strategy_duet_needs_mechanics_v1
--
-- ОТКАТ ЧАСТИ 202608220005 ПО УТОЧНЁННОЙ ЗАДАЧЕ.
--
-- Я снял с «Аватара» обязательный разбор механики, рассудив, что он стал такой
-- же правкой готового видео, как «Копия», а значит пересказ содержимого модели
-- не нужен — она видит ролик сама.
--
-- Владелец уточнил операцию 22.08.2026: это НЕ замена человека в кадре. Это
-- ДУЭТ — исходный ролик остаётся собой, а снизу врезается сгенерированный
-- ведущий, который КОММЕНТИРУЕТ происходящее.
--
-- При таком устройстве разбор ролика нужен БОЛЬШЕ, чем раньше, а не меньше: он
-- и есть материал для речи. Комментатор, не знающий, что происходит в ролике,
-- может произнести только общие слова — а «арбитр, разбирающий ролик» именно
-- этим и ценен. Модель ведущего исходное видео вообще не получает: она делает
-- говорящего человека, и всё, что он скажет, приходит текстом.
--
-- Поэтому требование возвращается — но ТОЛЬКО «Аватару». «Копия» остаётся без
-- разбора: она правит сам ролик, и сцена доезжает до модели целиком.
--
-- ЧТО ИЗ 202608220005 СОХРАНЯЕТСЯ. Там же была исправлена настоящая ошибка:
-- ветвление по одной стратегии отправляло «Аватара» в ветку «собираем с нуля»,
-- которая читает из выбора `ratio` — а у него теперь `resolution`, и разрешение
-- выводилось из NULL. Ветка по рецепту остаётся; меняется только требование к
-- разбору, которое отделяется от неё в собственное условие.

do $duet_needs_mechanics$
declare
  definition_value text;
  patched_value text;
  -- Запрет на присланный разбор действует на обе правки видео. Оставляем его
  -- только «Копии»: у неё разбора нет и быть не должно.
  null_anchor constant text :=
    '    if p_payload -> ''mechanics_summary'' <> ''null''::jsonb then';
  null_replacement constant text :=
    '    if recipe_value = ''product_swap''' || chr(10) ||
    '       and p_payload -> ''mechanics_summary'' <> ''null''::jsonb then';
  flag_anchor constant text :=
    '''mechanics_required'', recipe_value = ''product_ad''';
  flag_replacement constant text :=
    '''mechanics_required'', recipe_value in (''product_ad'', ''product_ugc'')';
  snapshot_anchor constant text :=
    '  if recipe_value in (''product_swap'', ''product_ugc'') then' || chr(10) ||
    '    mechanics_snapshot_value := null;';
  snapshot_replacement constant text :=
    '  if recipe_value = ''product_swap'' then' || chr(10) ||
    '    mechanics_snapshot_value := null;';
  hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );

  if position(flag_replacement in definition_value) > 0 then
    return;  -- уже применено
  end if;

  -- Каждый якорь обязан встретиться ровно один раз: иначе тело функции не то,
  -- что мы читали, и молчаливая правка не туда опаснее отказа.
  hits := (length(definition_value)
    - length(replace(definition_value, null_anchor, ''))) / length(null_anchor);
  if hits <> 1 then
    raise exception using message = 'duet_null_anchor_invalid:' || hits::text;
  end if;
  hits := (length(definition_value)
    - length(replace(definition_value, flag_anchor, ''))) / length(flag_anchor);
  if hits <> 1 then
    raise exception using message = 'duet_flag_anchor_invalid:' || hits::text;
  end if;
  hits := (length(definition_value)
    - length(replace(definition_value, snapshot_anchor, ''))) / length(snapshot_anchor);
  if hits <> 1 then
    raise exception using message = 'duet_snapshot_anchor_invalid:' || hits::text;
  end if;

  patched_value := replace(definition_value, null_anchor, null_replacement);
  patched_value := replace(patched_value, flag_anchor, flag_replacement);
  patched_value := replace(patched_value, snapshot_anchor, snapshot_replacement);
  execute patched_value;
end;
$duet_needs_mechanics$;

do $duet_needs_mechanics_verify$
declare
  definition_value text;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );

  -- Разбор обязателен у «Создания» и у «Дуэта».
  if position(
       '''mechanics_required'', recipe_value in (''product_ad'', ''product_ugc'')'
       in definition_value
     ) = 0 then
    raise exception using message = 'duet_mechanics_flag_not_applied';
  end if;
  -- Запрет на присланный разбор остался только у «Копии».
  if position(
       'if recipe_value = ''product_swap''' || chr(10) ||
       '       and p_payload -> ''mechanics_summary'' <> ''null''::jsonb then'
       in definition_value
     ) = 0 then
    raise exception using message = 'duet_mechanics_null_guard_not_narrowed';
  end if;
  -- Снимок обнуляется тоже только у «Копии».
  if position(
       '  if recipe_value = ''product_swap'' then' || chr(10) ||
       '    mechanics_snapshot_value := null;'
       in definition_value
     ) = 0 then
    raise exception using message = 'duet_mechanics_snapshot_not_narrowed';
  end if;

  -- Исправление из 202608220005 сохранено: разрешение и ярлык входа
  -- по-прежнему считаются по рецепту, а не по одной стратегии.
  if position(
       'if recipe_value in (''product_swap'', ''product_ugc'') then' || chr(10) ||
       '    resolution_value := selection_value ->> ''resolution'';'
       in definition_value
     ) = 0 then
    raise exception using message = 'video_edit_branch_lost';
  end if;
end;
$duet_needs_mechanics_verify$;

commit;
