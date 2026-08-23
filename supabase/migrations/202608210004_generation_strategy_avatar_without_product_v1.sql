begin;

-- 202608210004_generation_strategy_avatar_without_product_v1
--
-- РЕШЕНИЕ ВЛАДЕЛЬЦА 21.08.2026: у стратегии «Аватар» (viral_avatar_ugc) больше
-- нет товара. Модуль отвечает на вопрос «поставить нашего аватара в этот ролик»,
-- а не «снять UGC про товар с аватаром»: артикул, категория и фото товара к нему
-- не относятся.
--
-- Второе следствие того же решения: аватар задаётся ЛИБО фотографией, ЛИБО
-- описанием. Поэтому фотография становится необязательной (0..1), а не
-- обязательной. Инвариант «фото или описание» здесь намеренно НЕ выражается:
-- описание живёт в тексте замысла, а этот счётчик видит только состав ассетов и
-- проверить наличие текста не может. Проверка, которая не в состоянии увидеть
-- половину условия, была бы ложной гарантией — она живёт там, где виден текст.
--
-- ПОЧЕМУ ТОЛЬКО СЧЁТЧИК. Ярлык input_mode ('character_and_product_images')
-- остаётся прежним во всех четырёх функциях, которые его строят. Он участвует в
-- перекрёстной сверке слоёв, поэтому переименовывать его можно только вместе с
-- каталогом, адаптером и edge — одним согласованным заходом. Пока имя просто
-- неточное; расхождения между слоями оно не создаёт.
--
-- ПОРЯДОК БЕЗОПАСЕН. После этой миграции база ПРИНИМАЕТ аватара без товара, а
-- браузерный каталог его пока по-прежнему требует. То есть на этом шаге система
-- строже базы, а не наоборот: ни одна привязка, которую раньше принимали, не
-- перестаёт приниматься, и ни одна новая форма ещё не появляется.
--
-- Приём правки — pg_get_functiondef + replace + execute: тело функции огромно и
-- переписывается многими миграциями, поэтому переносить его целиком значило бы
-- откатить чужие правки. Меняется ровно одна ветка, и факт замены проверяется.

do $avatar_without_product$
declare
  definition_value text;
  patched_value text;
  anchor constant text :=
    'and (avatar_count <> 1 or target_count <> 1';
  replacement constant text :=
    'and (avatar_count not between 0 and 1 or target_count <> 0';
  anchor_hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );
  if definition_value is null then
    raise exception using message = 'strategy_bind_function_missing';
  end if;

  -- Уже применено: ветка перестроена, якоря нет. Миграция идемпотентна.
  if position(replacement in definition_value) > 0 then
    return;
  end if;

  anchor_hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'avatar_asset_count_anchor_invalid:' || anchor_hits::text;
  end if;

  patched_value := replace(definition_value, anchor, replacement);
  if patched_value = definition_value then
    raise exception using message = 'avatar_asset_count_patch_noop';
  end if;
  execute patched_value;
end;
$avatar_without_product$;

-- Проверка результата: ветка аватара обязана требовать ноль товарных ассетов и
-- допускать ноль или одну фотографию, а ветки «Копии» и «Создания» — остаться
-- нетронутыми. Последнее важнее первого: правка соседней ветки прошла бы молча.
do $avatar_without_product_verify$
declare
  definition_value text;
begin
  definition_value := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );

  if position(
       'and (avatar_count not between 0 and 1 or target_count <> 0'
       in definition_value
     ) = 0 then
    raise exception using message = 'avatar_asset_count_not_relaxed';
  end if;
  if position('and (avatar_count <> 1 or target_count <> 1' in definition_value) > 0
  then
    raise exception using message = 'avatar_asset_count_old_branch_left';
  end if;

  -- «Копия»: ровно один исходный товар и от одного до десяти новых.
  if position(
       'and (avatar_count <> 0 or original_product_count <> 1'
       in definition_value
     ) = 0 then
    raise exception using message = 'product_swap_asset_count_drifted';
  end if;
  -- «Создание»: без аватара и без исходного товара, стиль до четырёх.
  if position(
       'or style_count not between 0 and 4'
       in definition_value
     ) = 0 then
    raise exception using message = 'rebuild_asset_count_drifted';
  end if;
  -- Один исходник по-прежнему обязателен для всех трёх.
  if position('if source_count <> 1' in definition_value) = 0 then
    raise exception using message = 'source_count_guard_lost';
  end if;
end;
$avatar_without_product_verify$;

commit;
