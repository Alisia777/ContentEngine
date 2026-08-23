begin;

-- 202608220005_generation_strategy_avatar_no_mechanics_v1
--
-- РЕШЕНИЕ ВЛАДЕЛЬЦА 22.08.2026: «проще лучше». С «Аватара» снимается
-- обязательный разбор механики референса.
--
-- ПОЧЕМУ ЭТО ПРАВИЛЬНО, А НЕ ПРОСТО УДОБНЕЕ. Разбор механики нужен тому, кто
-- собирает ролик С НУЛЯ: у «Создания» исходник провайдеру не показывают вовсе,
-- и единственный способ донести до модели, что происходило в референсе, — это
-- серверный разбор внутри userConcept. «Копия» разбора не требует именно
-- потому, что правит сам ролик: сцена, движение и монтаж доезжают до модели
-- целиком, а не пересказом. С 22.08.2026 «Аватар» устроен так же — значит и
-- требование к нему было унаследованным, а не осмысленным.
--
-- ЗАОДНО ИСПРАВЛЯЕТСЯ БОЛЕЕ ГРУБАЯ ОШИБКА. Ветвление в этой функции сделано по
-- одной стратегии: `if strategy_id_value = 'viral_product_swap'`. Всё остальное
-- попадает в ветку «собираем с нуля», которая читает из выбора `ratio`, выводит
-- из него разрешение и требует механику. После перевода «Аватара» на правку
-- видео он ходит по этой ветке ошибочно: `ratio` у него больше нет — есть
-- `resolution`, — и разрешение выводилось из NULL.
--
-- Поэтому условие переписывается на РЕЦЕПТ и покрывает обе правки готового
-- видео. Следующая такая стратегия добавится в набор, а не новым сравнением.
--
-- Ярлык входа при этом остаётся у каждой стратегии свой: операция общая, а
-- называется вход по тому, чем заменяют.

do $avatar_no_mechanics$
declare
  definition_value text;
  patched_value text;
  anchor constant text :=
E'  if strategy_id_value = ''viral_product_swap'' then\n'
'    resolution_value := selection_value ->> ''resolution'';\n'
'    ratio_value := ''source'';\n'
'    input_mode_value := ''video_and_product_images'';\n';
  replacement constant text :=
E'  if recipe_value in (''product_swap'', ''product_ugc'') then\n'
'    resolution_value := selection_value ->> ''resolution'';\n'
'    ratio_value := ''source'';\n'
'    input_mode_value := case strategy_id_value\n'
'      when ''viral_avatar_ugc'' then ''video_and_avatar_images''\n'
'      else ''video_and_product_images'' end;\n';
  mechanics_anchor constant text :=
    '''mechanics_required'', strategy_id_value <>' || E'\n' ||
    '        ''viral_product_swap''';
  mechanics_replacement constant text :=
    '''mechanics_required'', recipe_value = ''product_ad''';
  anchor_hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );

  if position(replacement in definition_value) > 0
     and position(mechanics_replacement in definition_value) > 0 then
    return;
  end if;

  anchor_hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'mechanics_branch_anchor_invalid:' || anchor_hits::text;
  end if;
  patched_value := replace(definition_value, anchor, replacement);

  -- Второе вхождение того же литерала — там, где снимок механики обнуляется.
  -- «Аватар» разбор больше не собирает, значит и снимка у него быть не должно:
  -- иначе в подписанный объём уехал бы пустой документ вместо отсутствия.
  patched_value := replace(
    patched_value,
    '  if strategy_id_value = ''viral_product_swap'' then' || chr(10)
      || '    mechanics_snapshot_value := null;',
    '  if recipe_value in (''product_swap'', ''product_ugc'') then' || chr(10)
      || '    mechanics_snapshot_value := null;'
  );

  anchor_hits := (
    length(patched_value) - length(replace(patched_value, mechanics_anchor, ''))
  ) / length(mechanics_anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'mechanics_flag_anchor_invalid:' || anchor_hits::text;
  end if;
  patched_value := replace(patched_value, mechanics_anchor, mechanics_replacement);

  execute patched_value;
end;
$avatar_no_mechanics$;

do $avatar_no_mechanics_verify$
declare
  definition_value text;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );

  if position(
       'if recipe_value in (''product_swap'', ''product_ugc'') then'
       in definition_value
     ) = 0 then
    raise exception using message = 'video_edit_branch_not_applied';
  end if;
  if position(
       '''mechanics_required'', recipe_value = ''product_ad'''
       in definition_value
     ) = 0 then
    raise exception using message = 'mechanics_flag_not_applied';
  end if;
  if position('if strategy_id_value = ''viral_product_swap'' then' in definition_value) > 0
  then
    raise exception using message = 'old_single_strategy_branch_left';
  end if;

  -- Запрет на присланную механику в ветке правки видео сохранён: он и держит
  -- обещание «этот шаг не нужен» честным — прислать её теперь нельзя, а не
  -- «можно, но проигнорируем».
  if position(
       'generation_strategy_spec_mechanics_must_be_null' in definition_value
     ) = 0 then
    raise exception using message = 'mechanics_must_be_null_guard_lost';
  end if;
  -- «Создание» по-прежнему обязано присылать разбор.
  if position(
       'generation_strategy_spec_mechanics_required' in definition_value
     ) = 0 then
    raise exception using message = 'mechanics_required_guard_lost';
  end if;
end;
$avatar_no_mechanics_verify$;

commit;
