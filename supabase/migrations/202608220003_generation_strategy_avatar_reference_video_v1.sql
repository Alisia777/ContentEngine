begin;

-- 202608220003_generation_strategy_avatar_reference_video_v1
--
-- Признак «исходник уходит провайдеру» был приравнен к «это Копия»:
--
--   'reference_video', strategy_id_value = 'viral_product_swap'
--
-- До 22.08.2026 это совпадало с правдой — «Копия» была единственной стратегией,
-- отдающей исходный ролик провайдеру. Теперь их две: «Аватар» тоже правит
-- готовое видео, и его исходник стал настоящим входом (202608210004 и далее).
--
-- ПОЧЕМУ ЭТО НЕ КОСМЕТИКА. Признак лежит в подписанном exact_scope и сверяется
-- браузерным зеркалом поле в поле. Расхождение даёт отказ
-- `strategy_scope_output_mismatch` на подготовке ТЗ — то есть «Аватар» не может
-- дойти даже до бесплатной проверки, не говоря о цене.
--
-- Правится через список рецептов, а не через второй литерал стратегии: так
-- следующая правка видео добавляется одной строкой, а не поиском по коду.

do $avatar_reference_video$
declare
  definition_value text;
  patched_value text;
  anchor constant text :=
    '''reference_video'', strategy_id_value = ''viral_product_swap''';
  replacement constant text :=
    '''reference_video'', recipe_value in (''product_swap'', ''product_ugc'')';
  anchor_hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );

  -- Уже применено: миграция идемпотентна.
  if position(replacement in definition_value) > 0 then
    return;
  end if;

  anchor_hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'reference_video_anchor_invalid:' || anchor_hits::text;
  end if;

  patched_value := replace(definition_value, anchor, replacement);
  execute patched_value;
end;
$avatar_reference_video$;

do $avatar_reference_video_verify$
declare
  definition_value text;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );
  if position(
       '''reference_video'', recipe_value in (''product_swap'', ''product_ugc'')'
       in definition_value
     ) = 0 then
    raise exception using message = 'reference_video_not_applied';
  end if;
  if position(
       '''reference_video'', strategy_id_value = ''viral_product_swap'''
       in definition_value
     ) > 0 then
    raise exception using message = 'reference_video_old_literal_left';
  end if;
  -- Соседние поля подписанного объёма не сдвинулись: правка одной строки не
  -- должна была задеть счётчик ссылок и признаки кадров.
  if position(
       '''reference_count'', jsonb_array_length(selection_value -> ''assets'') - 1'
       in definition_value
     ) = 0 then
    raise exception using message = 'reference_count_drifted';
  end if;
  if position('''first_frame'', false' in definition_value) = 0
     or position('''last_frame'', false' in definition_value) = 0 then
    raise exception using message = 'frame_flags_drifted';
  end if;
end;
$avatar_reference_video_verify$;

commit;
