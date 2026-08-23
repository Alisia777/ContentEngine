begin;

-- 202608220014_duet_single_asset_selection_v1
--
-- «Дуэт»: форма выбора приводится к ОДНОМУ ассету.
--
-- ЧТО БЫЛО. Серверный проверяющий выбора остался от прежнего прочтения
-- стратегии, когда «Аватар» считался заменой человека в кадре: он ждал от неё
-- ТРИ ассета (исходник, фотографию лица, фотографию товара), измерение
-- соотношением сторон и роли `avatar_image` с `product_image`.
--
-- ЧТО СТАЛО. Владелец переопределил стратегию 22.08.2026: исходный ролик НЕ
-- переписывается, поверх него врезается отдельно снятый говорящий ведущий.
-- Провайдер (HeyGen) не получает ни одной картинки — в теле запроса медиа нет
-- вовсе, а личность даёт `avatar_id` из библиотеки ведущих проекта. Значит
-- набор ассетов дуэта — РОВНО ОДИН исходник, и никаких фотографий.
--
-- ПОЧЕМУ РАЗРЕШЕНИЕ, А НЕ СООТНОШЕНИЕ СТОРОН. Кадр дуэту задаёт исходник: он
-- остаётся подложкой и определяет размер холста. Выбирать соотношение сторон
-- нечего — ровно как у «Копии», которая тот же ролик переписывает. Это НЕ
-- значит, что исходник уходит провайдеру: у «Копии» уходит, у дуэта нет.
--
-- ПОЧЕМУ ДЛИТЕЛЬНОСТЬ ИСХОДНИКА ТЕПЕРЬ ОБЯЗАТЕЛЬНА. Ведущий оплачивается
-- ПОСЕКУНДНО ($0.05/сек), и секунды берутся из комментируемого ролика. Без
-- измеренной длительности цену назвать нечем, а назвать её приблизительно
-- значит списать не ту сумму. Предел шире, чем у «Копии» (60 против 15):
-- комментировать можно длинный ролик — переписывать его никто не будет.
--
-- Правка идёт приёмом pg_get_functiondef + replace + execute с проверкой числа
-- вхождений: если якорь встретился не один раз, миграция падает, а не правит
-- наугад.

do $duet_selection_shape$
declare
  source_text text;
  patched_text text;
  anchor text;
  replacement text;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_strategy_selection_snapshot_valid_v1(jsonb)'
      ::regprocedure
  );
  -- Повторный прогон обязан быть тихим: CI применяет миграции заново и на
  -- чистой базе, и на уже накатанной. Признак — предел длительности дуэта,
  -- которого в прежней редакции быть не могло. Проверка идёт ДО якорей:
  -- иначе второй прогон падал бы на пропавшем якоре, а это неотличимо от
  -- настоящей поломки.
  if position('not between 1.8 and 60' in source_text) > 0 then
    return;
  end if;
  patched_text := source_text;

  -- 1. Нижняя граница набора: один ассет, а не два.
  anchor := 'not between 2 and 15';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_assets_length:' || anchor;
  end if;
  patched_text := replace(patched_text, anchor, 'not between 1 and 15');

  -- 2. Измерение разрешением: к «Копии» присоединяется «Дуэт».
  anchor := E'  if strategy_id_value = ''viral_product_swap'' then';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_resolution_branch';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  if strategy_id_value in (''viral_product_swap'', ''viral_avatar_ugc'') then'
  );

  -- 3. Длительность исходника обязательна и у дуэта.
  anchor := E'           strategy_id_value = ''viral_product_swap''\n'
         || E'           and not (asset_value ? ''duration_seconds'')';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_duration_required';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'           strategy_id_value in (''viral_product_swap'', ''viral_avatar_ugc'')\n'
      || E'           and not (asset_value ? ''duration_seconds'')'
  );

  -- 4. Свой предел длительности: комментарий длиннее минуты комментарием быть
  --    перестаёт, но и пятнадцатью секундами «Копии» его не ограничить.
  anchor := E'             strategy_id_value = ''viral_product_swap''\n'
         || E'             and source_duration_value not between 1.8 and 15';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_duration_range';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'             strategy_id_value = ''viral_product_swap''\n'
      || E'             and source_duration_value not between 1.8 and 15\n'
      || E'           )\n'
      || E'           or (\n'
      || E'             strategy_id_value = ''viral_avatar_ugc''\n'
      || E'             and source_duration_value not between 1.8 and 60'
  );

  -- 5. Роль фотографии лица у дуэта исчезает. Ведущего задаёт запись в
  --    библиотеке, а не медиа-объект формы.
  anchor := E'    elsif asset_role_value = ''avatar_image''\n'
         || E'          and strategy_id_value = ''viral_avatar_ugc'' then\n'
         || E'      if asset_value - array[''role'', ''media_id'']::text[] <> ''{}''::jsonb then\n'
         || E'        return false;\n'
         || E'      end if;\n'
         || E'      avatar_count := avatar_count + 1;\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_avatar_role';
  end if;
  patched_text := replace(patched_text, anchor, '');

  -- 6. Товарной роли у дуэта тоже нет.
  anchor := E'    elsif asset_role_value = ''product_image''\n'
         || E'          and strategy_id_value in (''viral_avatar_ugc'', ''viral_rebuild'') then';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_product_role';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    elsif asset_role_value = ''product_image''\n'
      || E'          and strategy_id_value = ''viral_rebuild'' then'
  );

  -- 7. Итоговый счёт: один исходник и больше ничего.
  anchor := E'      strategy_id_value = ''viral_avatar_ugc''\n'
         || E'      and avatar_count = 1 and original_count = 0\n'
         || E'      and product_count = 1 and style_count = 0\n'
         || E'      and jsonb_array_length(assets_value) = 3';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_final_counts';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'      strategy_id_value = ''viral_avatar_ugc''\n'
      || E'      and avatar_count = 0 and original_count = 0\n'
      || E'      and product_count = 0 and style_count = 0\n'
      || E'      and jsonb_array_length(assets_value) = 1'
  );

  if patched_text = source_text then
    raise exception using message = 'duet_selection_shape_unchanged';
  end if;
  execute patched_text;
end;
$duet_selection_shape$;

-- Цена «Дуэта» считается по тому же кадру, что и у «Копии»: снимок называет его
-- словом "source". Прежнее правило требовало от дуэта вертикали 720:1280 или
-- 1080:1920 — это остаток измерения соотношением сторон, и с ним ни один
-- дуэтный выбор цены бы не получил.
do $duet_price_ratio$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_strategy_recipe_price(text,integer,text,text,boolean)'
      ::regprocedure
  );
  -- Та же страховка от повторного прогона.
  if position('p_strategy_id in (''viral_avatar_ugc'', ''viral_product_swap'')'
              in source_text) > 0 then
    return;
  end if;
  anchor := E'     or (\n'
         || E'       p_strategy_id = ''viral_avatar_ugc''\n'
         || E'       and p_ratio <> case p_resolution\n'
         || E'         when ''720p'' then ''720:1280'' else ''1080:1920'' end\n'
         || E'     )\n'
         || E'     or (p_strategy_id = ''viral_product_swap'' and p_ratio <> ''source'')';
  if (length(source_text) - length(replace(source_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_price_ratio';
  end if;
  patched_text := replace(
    source_text,
    anchor,
    E'     or (\n'
      || E'       p_strategy_id in (''viral_avatar_ugc'', ''viral_product_swap'')\n'
      || E'       and p_ratio <> ''source''\n'
      || E'     )'
  );
  execute patched_text;
end;
$duet_price_ratio$;

-- Проверка ПОВЕДЕНИЕМ, а не чтением текста функций.
do $duet_selection_verify$
declare
  duet_selection jsonb;
begin
  duet_selection := jsonb_build_object(
    'version', '2026-08-14.v1',
    'strategy_id', 'viral_avatar_ugc',
    'recipe_version', '2026-06',
    'duration_seconds', 8,
    'resolution', '720p',
    'audio', true,
    'assets', jsonb_build_array(jsonb_build_object(
      'role', 'source_video',
      'media_id', '11111111-1111-4111-8111-111111111111',
      'duration_seconds', 8
    )),
    'attestations', jsonb_build_object(
      'source_media_rights_confirmed', true,
      'transformative_use_confirmed', true,
      'product_assets_rights_confirmed', true,
      'depicted_people_consent_confirmed', true,
      'avatar_likeness_consent_confirmed', true
    )
  );

  -- Один исходник — годный выбор.
  if not content_factory_private.generation_strategy_selection_snapshot_valid_v1(
       duet_selection
     ) then
    raise exception using message = 'duet_single_asset_selection_rejected';
  end if;

  -- Прежняя форма с фотографией лица больше не годится: обещать выбор,
  -- которого нет, нельзя.
  if content_factory_private.generation_strategy_selection_snapshot_valid_v1(
       jsonb_set(duet_selection, '{assets}',
         (duet_selection -> 'assets') || jsonb_build_array(jsonb_build_object(
           'role', 'avatar_image',
           'media_id', '22222222-2222-4222-8222-222222222222'
         )))
     ) then
    raise exception using message = 'duet_still_accepts_avatar_photo';
  end if;

  -- Соотношение сторон дуэту чужое.
  if content_factory_private.generation_strategy_selection_snapshot_valid_v1(
       (duet_selection - 'resolution') || jsonb_build_object('ratio', '720:1280')
     ) then
    raise exception using message = 'duet_still_accepts_ratio';
  end if;

  -- Без измеренной длительности исходника цену назвать нечем.
  if content_factory_private.generation_strategy_selection_snapshot_valid_v1(
       jsonb_set(duet_selection, '{assets}', jsonb_build_array(jsonb_build_object(
         'role', 'source_video',
         'media_id', '11111111-1111-4111-8111-111111111111'
       )))
     ) then
    raise exception using message = 'duet_accepts_source_without_duration';
  end if;

  -- Минута — предел дуэта, но не пятнадцать секунд «Копии».
  if not content_factory_private.generation_strategy_selection_snapshot_valid_v1(
       jsonb_set(duet_selection, '{assets}', jsonb_build_array(jsonb_build_object(
         'role', 'source_video',
         'media_id', '11111111-1111-4111-8111-111111111111',
         'duration_seconds', 45
       )))
     ) then
    raise exception using message = 'duet_rejects_long_source';
  end if;
  if content_factory_private.generation_strategy_selection_snapshot_valid_v1(
       jsonb_set(duet_selection, '{assets}', jsonb_build_array(jsonb_build_object(
         'role', 'source_video',
         'media_id', '11111111-1111-4111-8111-111111111111',
         'duration_seconds', 61
       )))
     ) then
    raise exception using message = 'duet_accepts_source_over_a_minute';
  end if;

  -- «Копия» не тронута: её форма из трёх ассетов по-прежнему годится, а
  -- пятнадцатисекундный предел исходника остаётся её пределом.
  if not content_factory_private.generation_strategy_selection_snapshot_valid_v1(
       jsonb_build_object(
         'version', '2026-08-14.v1',
         'strategy_id', 'viral_product_swap',
         'recipe_version', '2026-06',
         'duration_seconds', 8,
         'resolution', '720p',
         'audio', true,
         'assets', jsonb_build_array(
           jsonb_build_object(
             'role', 'source_video',
             'media_id', '11111111-1111-4111-8111-111111111111',
             'duration_seconds', 8
           ),
           jsonb_build_object(
             'role', 'original_product_image',
             'media_id', '22222222-2222-4222-8222-222222222222'
           ),
           jsonb_build_object(
             'role', 'new_product_image',
             'media_id', '33333333-3333-4333-8333-333333333333',
             'view', 'front'
           )
         ),
         'attestations', jsonb_build_object(
           'source_media_rights_confirmed', true,
           'transformative_use_confirmed', true,
           'product_assets_rights_confirmed', true,
           'depicted_people_consent_confirmed', true
         )
       )
     ) then
    raise exception using message = 'product_swap_selection_broke';
  end if;

  -- Цена дуэта считается по кадру исходника.
  if content_factory_private.generation_strategy_recipe_price(
       'viral_avatar_ugc', 8, '720p', 'source', true
     ) is null then
    raise exception using message = 'duet_price_missing_for_source_ratio';
  end if;
  if content_factory_private.generation_strategy_recipe_price(
       'viral_avatar_ugc', 8, '720p', '720:1280', true
     ) is not null then
    raise exception using message = 'duet_price_still_takes_vertical_ratio';
  end if;
  if content_factory_private.generation_strategy_recipe_price(
       'viral_product_swap', 8, '720p', 'source', true
     ) is null then
    raise exception using message = 'product_swap_price_broke';
  end if;
end;
$duet_selection_verify$;

commit;
