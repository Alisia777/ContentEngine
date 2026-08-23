begin;

-- 202608230005_duet_bind_one_source_v1
--
-- «Дуэт»: ПРОИЗВОДИТЕЛЬ привязки собирает один исходник.
--
-- Все предыдущие файлы учили ПРОВЕРЯЮЩИХ видеть новую форму. Этот учит того,
-- кто её создаёт. До него дуэтная привязка не могла появиться вовсе, и потому
-- все ужесточения выше применялись к пустому множеству — это и делало их
-- безопасными.
--
-- ЧТО ЛОМАЛОСЬ, ПО ПОРЯДКУ ОТКАЗА.
--
-- 1. Кадр. Развилка состава ключей выбора уводила дуэт в ветку соотношения
--    сторон, которого у него больше нет (202608220014).
--
-- 2. Длительность исходника. Обязательность и предел были прописаны только для
--    «Копии». У дуэта секунды — это ЦЕНА (посекундный провайдер), и приблизить
--    их нельзя.
--
-- 3. Цель работы. Набор целевых медиа наполнялся ролями `new_product_image` и
--    `product_image`. У дуэта их нет, набор оставался пустым, и проверка
--    `spec_row.media_ids <@ target_media_ids` была заведомо ложной. Это и был
--    гарантированный тупик: спека уже называла целью исходник (202608220015), а
--    привязка не могла её подтвердить.
--
-- 4. Состав привязки. `product_primary` клался БЕЗУСЛОВНО из
--    `spec_row.primary_media_id` — а у дуэта это MP4. Ограничение
--    `generation_spec_strategy_assets_check2` требует для этой роли image-mime
--    и `media_kind_snapshot in ('product_photo','packshot')`, то есть вставка
--    была гарантированным нарушением CHECK — отказом без внятного имени.
--    Исходник же в привязку не клался вовсе: условие перечисляло две другие
--    стратегии.
--
-- 5. Роли, которых у дуэта больше нет. `avatar_image` принимался и порождал
--    `creator_avatar`; `product_image` принимался наравне с «Созданием».
--    Принять роль, которая ничего не значит, значит обещать выбор, которого
--    нет.
--
-- ОТДЕЛЬНО ПРО СЧЁТЧИК ЦЕЛЕЙ. Было `target_count <> 0`, стало
-- `target_count <> 1`. Это не ослабление и не ужесточение — это ДРУГОЙ предмет.
-- Миграция 202608210004 поставила ноль, когда у «Аватара» отняли товар и целей
-- не осталось вовсе. Теперь цель есть — сам комментируемый ролик, — и она ровно
-- одна.
--
-- ПРО МЁРТВЫЙ КОД. После снятия роли `avatar_image` переменная
-- `avatar_media_id_value` не заполняется больше нигде, и блок, который клал из
-- неё роль `creator_avatar`, становится недостижимым. Он снимается тем же
-- файлом: код, который умеет собрать ассет для платного наряда, но никогда не
-- вызывается, — это приглашение вернуть его обратно, а не безобидный остаток.

do $duet_bind_one_source$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );
  -- Признак повторного прогона: предел длительности дуэта, которого в прежней
  -- редакции быть не могло.
  if position('and asset_duration_value not between 1.8 and 60' in source_text) > 0
  then
    return;
  end if;
  patched_text := source_text;

  -- 1. Кадр: состав ключей выбора у обеих правок готового видео одинаков.
  anchor := E'  if strategy_id_value = ''viral_product_swap'' then\n'
         || E'    if selection_value - array[\n'
         || E'         ''version'', ''strategy_id'', ''recipe_version'', ''duration_seconds'',\n'
         || E'         ''resolution'', ''audio'', ''assets'', ''attestations''\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_bind_anchor_frame_branch';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  if strategy_id_value in (''viral_product_swap'', ''viral_avatar_ugc'') then\n'
      || E'    if selection_value - array[\n'
      || E'         ''version'', ''strategy_id'', ''recipe_version'', ''duration_seconds'',\n'
      || E'         ''resolution'', ''audio'', ''assets'', ''attestations''\n'
  );

  -- 2. Длительность исходника обязательна и у дуэта: по ней считается цена.
  anchor := E'           strategy_id_value = ''viral_product_swap''\n'
         || E'           and not (asset_value ? ''duration_seconds'')';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_bind_anchor_duration_required';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'           strategy_id_value in (''viral_product_swap'', ''viral_avatar_ugc'')\n'
      || E'           and not (asset_value ? ''duration_seconds'')'
  );

  -- 3. Предел длительности — свой у каждой правки. Разные числа в двух слоях
  --    дали бы отказ, который потом никто не сможет объяснить: 202608220014
  --    уже поставил дуэту 1.8..60 в проверяющем выбора.
  anchor := E'        if asset_duration_value <= 0\n'
         || E'           or (strategy_id_value = ''viral_product_swap''\n'
         || E'             and asset_duration_value not between 1.8 and 15) then';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_bind_anchor_duration_range';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'        if asset_duration_value <= 0\n'
      || E'           or (strategy_id_value = ''viral_product_swap''\n'
      || E'             and asset_duration_value not between 1.8 and 15)\n'
      || E'           or (strategy_id_value = ''viral_avatar_ugc''\n'
      || E'             and asset_duration_value not between 1.8 and 60) then'
  );

  -- 4. Исходник становится целью работы у дуэта, а роль фотографии лица
  --    исчезает вовсе.
  anchor := E'      source_count := source_count + 1;\n'
         || E'      source_media_id_value := asset_media_id_value;\n'
         || E'    elsif asset_role_value = ''avatar_image''\n'
         || E'          and strategy_id_value = ''viral_avatar_ugc'' then\n'
         || E'      if asset_value - array[''role'', ''media_id'']::text[] <> ''{}''::jsonb then\n'
         || E'        raise exception using errcode = ''22023'',\n'
         || E'          message = ''generation_strategy_catalog_asset_invalid'';\n'
         || E'      end if;\n'
         || E'      avatar_count := avatar_count + 1;\n'
         || E'      avatar_media_id_value := asset_media_id_value;\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_bind_anchor_source_and_avatar';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'      source_count := source_count + 1;\n'
      || E'      source_media_id_value := asset_media_id_value;\n'
      || E'      -- У «Дуэта» цель работы — САМ КОММЕНТИРУЕМЫЙ РОЛИК. То же\n'
      || E'      -- решение, что 202608220015 записал в подготовку ТЗ: ведущий\n'
      || E'      -- приходит из библиотеки проекта и медиа-объектом формы не\n'
      || E'      -- бывает. Без этого набор целей оставался пуст, и проверка\n'
      || E'      -- spec_row.media_ids <@ target_media_ids была заведомо ложной.\n'
      || E'      if strategy_id_value = ''viral_avatar_ugc'' then\n'
      || E'        target_count := target_count + 1;\n'
      || E'        target_media_ids := array_append(\n'
      || E'          target_media_ids, asset_media_id_value\n'
      || E'        );\n'
      || E'      end if;\n'
  );

  -- 5. Товарная роль остаётся только у «Создания».
  anchor := E'    elsif asset_role_value = ''product_image''\n'
         || E'          and strategy_id_value in (''viral_avatar_ugc'', ''viral_rebuild'') then';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_bind_anchor_product_role';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    elsif asset_role_value = ''product_image''\n'
      || E'          and strategy_id_value = ''viral_rebuild'' then'
  );

  -- 6. Счётчики: цель ровно одна, фотографий лица нет вовсе.
  anchor := E'       and (avatar_count not between 0 and 1 or target_count <> 0';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_bind_anchor_counts';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'       and (avatar_count <> 0 or target_count <> 1'
  );

  -- 7. Товарный первичный ассет не кладётся дуэту: у него это MP4, и вставка
  --    была бы гарантированным нарушением CHECK.
  anchor := E'  select media.* into media_row\n'
         || E'  from content_factory.media_objects media\n'
         || E'  where media.organization_id = organization_id_value\n'
         || E'    and media.project_id = project_id_value\n'
         || E'    and media.id = spec_row.primary_media_id;\n'
         || E'  if media_row.id is null then\n'
         || E'    raise exception using errcode = ''42501'',\n'
         || E'      message = ''generation_strategy_catalog_asset_invalid'';\n'
         || E'  end if;\n'
         || E'  role_assets_value := role_assets_value || jsonb_build_array(\n'
         || E'    jsonb_build_object(\n'
         || E'      ''role'', ''product_primary'', ''ordinal'', 1,\n'
         || E'      ''media_object_id'', media_row.id, ''sha256'', media_row.sha256\n'
         || E'    )\n'
         || E'  );\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_bind_anchor_product_primary';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  -- У «Дуэта» первичное медиа спеки — это MP4-исходник, а роль\n'
      || E'  -- product_primary требует image-mime и вид product_photo/packshot\n'
      || E'  -- (generation_spec_strategy_assets_check2). Безусловная вставка была\n'
      || E'  -- гарантированным нарушением ограничения, то есть отказом без имени.\n'
      || E'  if strategy_id_value <> ''viral_avatar_ugc'' then\n'
      || E'    select media.* into media_row\n'
      || E'    from content_factory.media_objects media\n'
      || E'    where media.organization_id = organization_id_value\n'
      || E'      and media.project_id = project_id_value\n'
      || E'      and media.id = spec_row.primary_media_id;\n'
      || E'    if media_row.id is null then\n'
      || E'      raise exception using errcode = ''42501'',\n'
      || E'        message = ''generation_strategy_catalog_asset_invalid'';\n'
      || E'    end if;\n'
      || E'    role_assets_value := role_assets_value || jsonb_build_array(\n'
      || E'      jsonb_build_object(\n'
      || E'        ''role'', ''product_primary'', ''ordinal'', 1,\n'
      || E'        ''media_object_id'', media_row.id, ''sha256'', media_row.sha256\n'
      || E'      )\n'
      || E'    );\n'
      || E'  end if;\n'
  );

  -- 8. Мёртвый сборщик роли creator_avatar снимается: переменную больше не
  --    заполняет ни одна ветка.
  anchor := E'  if avatar_media_id_value is not null then\n'
         || E'    select media.* into media_row\n'
         || E'    from content_factory.media_objects media\n'
         || E'    where media.organization_id = organization_id_value\n'
         || E'      and media.project_id = project_id_value\n'
         || E'      and media.id = avatar_media_id_value;\n'
         || E'    if media_row.id is null then\n'
         || E'      raise exception using errcode = ''42501'',\n'
         || E'        message = ''generation_strategy_catalog_asset_invalid'';\n'
         || E'    end if;\n'
         || E'    role_assets_value := role_assets_value || jsonb_build_array(\n'
         || E'      jsonb_build_object(\n'
         || E'        ''role'', ''creator_avatar'', ''ordinal'', 1,\n'
         || E'        ''media_object_id'', media_row.id, ''sha256'', media_row.sha256\n'
         || E'      )\n'
         || E'    );\n'
         || E'  end if;\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_bind_anchor_creator_avatar_block';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  -- Сборщик роли creator_avatar снят 23.08.2026 вместе с ролью\n'
      || E'  -- avatar_image: переменную avatar_media_id_value не заполняет больше\n'
      || E'  -- ни одна ветка, и блок был недостижим. Код, который умеет собрать\n'
      || E'  -- ассет для платного наряда и никогда не вызывается, — приглашение\n'
      || E'  -- вернуть его обратно, а не безобидный остаток.\n'
  );

  -- 9. Исходник кладётся в привязку и дуэту.
  anchor := E'  if strategy_id_value in (''viral_product_swap'', ''viral_rebuild'') then';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_bind_anchor_source_composition';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  -- Исходник кладётся в реестр вложений ВСЕМ трём стратегиям. У «Копии» и\n'
      || E'  -- «Создания» он был там и раньше; у «Дуэта» он теперь единственный\n'
      || E'  -- ассет и одновременно цель работы, и без записи в реестре\n'
      || E'  -- generation_strategy_binding_current не признал бы привязку.\n'
      || E'  if strategy_id_value in (\n'
      || E'    ''viral_product_swap'', ''viral_rebuild'', ''viral_avatar_ugc''\n'
      || E'  ) then'
  );

  if patched_text = source_text then
    raise exception using message = 'duet_bind_pre_execution_unchanged';
  end if;
  execute patched_text;
end;
$duet_bind_one_source$;

-- ПРОВЕРКА.
--
-- Функция закрыта политикой доступа, но РАЗБОР ПОЛЕЗНОЙ НАГРУЗКИ идёт раньше
-- неё — значит состав выбора проверяется поведением по-настоящему. Всё, до чего
-- без сессии не добраться, проверяется структурно, с прямым признанием почему:
-- завести здесь фикстуру из десяти таблиц значило бы проверять не функцию, а
-- свою же заготовку.
do $duet_bind_verify$
declare
  body text;
  message_text text;
  saw_refusal boolean;
  base jsonb;
begin
  base := jsonb_build_object(
    'version', 'generation-strategy-resolve-bind-request-v1',
    'organization_id', '11111111-1111-4111-8111-111111111111',
    'project_id', '22222222-2222-4222-8222-222222222222',
    'actor_id', '33333333-3333-4333-8333-333333333333',
    'spec_id', '44444444-4444-4444-8444-444444444444',
    'spec_version', 1,
    'spec_hash', repeat('a', 64),
    'confirmation', true,
    'idempotency_key', 'duet-bind-probe-0001',
    'selection', jsonb_build_object(
      'version', '2026-08-14.v1',
      'strategy_id', 'viral_avatar_ugc',
      'recipe_version', '2026-06',
      'duration_seconds', 8,
      'resolution', '720p',
      'audio', true,
      'assets', jsonb_build_array(jsonb_build_object(
        'role', 'source_video',
        'media_id', '55555555-5555-4555-8555-555555555555',
        'duration_seconds', 8
      )),
      'attestations', jsonb_build_object(
        'source_media_rights_confirmed', true,
        'transformative_use_confirmed', true,
        'product_assets_rights_confirmed', true,
        'depicted_people_consent_confirmed', true,
        'avatar_likeness_consent_confirmed', true
      )
    )
  );

  -- Выбор новой формы проходит разбор состава и падает уже дальше — на
  -- доступе. Прежде он отбивался ЗДЕСЬ, как «каталог не принимает такой выбор».
  saw_refusal := false;
  begin
    perform public.system_resolve_and_bind_generation_strategy_pre_execution_v1(
      base
    );
  exception when others then
    get stacked diagnostics message_text = message_text;
    saw_refusal := message_text in (
      'generation_strategy_catalog_selection_invalid',
      'generation_strategy_catalog_asset_invalid',
      'generation_strategy_catalog_asset_count_invalid'
    );
  end;
  if saw_refusal then
    raise exception using message = 'duet_bind_still_rejects_one_source';
  end if;

  -- Фотография лица больше не принимается: роль ничего не значит, и обещать
  -- выбор, которого нет, нельзя.
  saw_refusal := false;
  begin
    perform public.system_resolve_and_bind_generation_strategy_pre_execution_v1(
      jsonb_set(
        base,
        '{selection,assets}',
        (base #> '{selection,assets}') || jsonb_build_array(jsonb_build_object(
          'role', 'avatar_image',
          'media_id', '66666666-6666-4666-8666-666666666666'
        ))
      )
    );
  exception when others then
    get stacked diagnostics message_text = message_text;
    saw_refusal := message_text = 'generation_strategy_catalog_asset_invalid';
  end;
  if not saw_refusal then
    raise exception using message = 'duet_bind_still_accepts_avatar_photo';
  end if;

  -- Исходник без измеренной длительности не принимается: секунды — это цена.
  saw_refusal := false;
  begin
    perform public.system_resolve_and_bind_generation_strategy_pre_execution_v1(
      jsonb_set(
        base,
        '{selection,assets}',
        jsonb_build_array(jsonb_build_object(
          'role', 'source_video',
          'media_id', '55555555-5555-4555-8555-555555555555'
        ))
      )
    );
  exception when others then
    get stacked diagnostics message_text = message_text;
    saw_refusal := message_text = 'generation_strategy_catalog_asset_invalid';
  end;
  if not saw_refusal then
    raise exception using message = 'duet_bind_accepts_unmeasured_source';
  end if;

  -- Ролик длиннее минуты комментарием быть перестаёт.
  saw_refusal := false;
  begin
    perform public.system_resolve_and_bind_generation_strategy_pre_execution_v1(
      jsonb_set(
        jsonb_set(base, '{selection,duration_seconds}', '61'::jsonb),
        '{selection,assets}',
        jsonb_build_array(jsonb_build_object(
          'role', 'source_video',
          'media_id', '55555555-5555-4555-8555-555555555555',
          'duration_seconds', 61
        ))
      )
    );
  exception when others then
    get stacked diagnostics message_text = message_text;
    saw_refusal := message_text in (
      'generation_strategy_catalog_selection_invalid',
      'generation_strategy_catalog_asset_invalid'
    );
  end;
  if not saw_refusal then
    raise exception using message = 'duet_bind_accepts_source_over_a_minute';
  end if;

  body := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );

  -- Состав привязки: товарный первичный ассет под условием, исходник у всех
  -- трёх, мёртвый сборщик лица снят.
  if position('if strategy_id_value <> ''viral_avatar_ugc'' then' in body) = 0 then
    raise exception using message = 'duet_bind_product_primary_unconditional';
  end if;
  if position('''viral_product_swap'', ''viral_rebuild'', ''viral_avatar_ugc''' in body) = 0
  then
    raise exception using message = 'duet_bind_source_not_composed';
  end if;
  if position('''role'', ''creator_avatar''' in body) > 0 then
    raise exception using message = 'duet_bind_creator_avatar_still_built';
  end if;

  -- «Копия» не тронута: её ветка счётчиков и требование исходного товара на
  -- месте, а предел пятнадцати секунд остался её пределом.
  if position('and (avatar_count <> 0 or original_product_count <> 1' in body) = 0
  then
    raise exception using message = 'product_swap_counts_lost';
  end if;
  if position('and asset_duration_value not between 1.8 and 15' in body) = 0 then
    raise exception using message = 'product_swap_duration_bound_lost';
  end if;
  -- «Создание» не тронуто: товарная роль осталась за ним.
  if position('and strategy_id_value = ''viral_rebuild'' then' in body) = 0 then
    raise exception using message = 'viral_rebuild_product_role_lost';
  end if;
end;
$duet_bind_verify$;

commit;
