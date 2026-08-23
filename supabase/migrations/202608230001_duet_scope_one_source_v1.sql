begin;

-- 202608230001_duet_scope_one_source_v1
--
-- «Дуэт»: проверяющий ОБЪЁМА РАБОТЫ учится видеть один исходник.
--
-- ЗАЧЕМ. Миграции 202608220014 и 202608220015 привели к новой форме выбор и
-- подготовку ТЗ, но проверяющий объёма остался прежним — и он отвергает дуэт
-- ДВАЖДЫ, каждый раз по своей причине:
--
--   1. КАДР. Развилка `if strategy_id_value = 'viral_product_swap'` уводит дуэт
--      в ветку соотношения сторон. У дуэта ключа `ratio` в выборе больше нет
--      (202608220014), поэтому `expected_ratio_value` становится NULL, за ним
--      NULL становится и ожидаемое разрешение — и сверка с объёмом проваливается.
--
--   2. ЦЕЛЬ РАБОТЫ. Набор целевых медиа собирается ТОЛЬКО из ролей
--      `product_image` и `new_product_image`. У дуэта их нет вовсе, набор пуст,
--      и `primary_media_id` не совпадает ни с чем.
--
-- Обойти это версией v2 нельзя: `generation_strategy_spec_scope_v2` переводит
-- объём в старую форму и делегирует ВСЮ проверку сюда же. Пока эта функция не
-- знает дуэта, у него не будет ни спеки, ни квитанции, ни цены.
--
-- ЧТО ИМЕННО МЕНЯЕТСЯ И ЧЕГО НЕ МЕНЯЕТСЯ.
--
-- Кадр: к «Копии» присоединяется «Дуэт». Обе правки готового ролика кадр не
-- выбирают — он приходит из исходника, и снимок называет его словом "source".
-- Это ТО ЖЕ решение, которое 202608220014 уже записал в проверяющий выбора и в
-- расчёт цены; здесь оно лишь доводится до третьего места, где спрашивают об
-- одном и том же.
--
-- Цель работы: у дуэта ею становится САМ КОММЕНТИРУЕМЫЙ РОЛИК — то же решение
-- владельца, что 202608220015 записал в `creator_prepare_generation_strategy_spec`.
-- Условие добавлено ветвлением ПО СТРАТЕГИИ, а не расширением списка ролей:
-- `source_video` есть и у «Копии», и у «Создания», и для них он целью НЕ
-- является. Расширить список значило бы молча переопределить, про что делаются
-- их ролики.
--
-- Приём — pg_get_functiondef + replace + execute со счётом вхождений якоря:
-- якорь, встретившийся не один раз, останавливает миграцию, а не правится
-- наугад.

do $duet_scope_one_source$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_strategy_spec_scope_legacy_v1(jsonb)'
      ::regprocedure
  );
  -- Повторный прогон обязан быть тихим. Признак — ветвление по стратегии в
  -- отборе целевых медиа, которого в прежней редакции быть не могло. Проверка
  -- идёт ДО якорей: иначе второй прогон падал бы на пропавшем якоре, а это
  -- неотличимо от настоящей поломки.
  if position('and asset.value ->> ''role'' = ''source_video''' in source_text) > 0
  then
    return;
  end if;
  patched_text := source_text;

  -- 1. Кадр приходит из исходника у ОБЕИХ правок готового видео.
  anchor := E'  if strategy_id_value = ''viral_product_swap'' then\n'
         || E'    expected_resolution_value := selection_value ->> ''resolution'';\n'
         || E'    expected_ratio_value := ''source'';\n'
         || E'  else';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_scope_anchor_frame_branch';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  if strategy_id_value in (''viral_product_swap'', ''viral_avatar_ugc'') then\n'
      || E'    expected_resolution_value := selection_value ->> ''resolution'';\n'
      || E'    expected_ratio_value := ''source'';\n'
      || E'  else'
  );

  -- 2. Цель работы «Дуэта» — сам комментируемый ролик.
  anchor := E'    where asset.value ->> ''role'' in (''product_image'', ''new_product_image'');';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_scope_anchor_target_roles';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    where asset.value ->> ''role'' in (''product_image'', ''new_product_image'')\n'
      || E'       or (\n'
      || E'         strategy_id_value = ''viral_avatar_ugc''\n'
      || E'         and asset.value ->> ''role'' = ''source_video''\n'
      || E'       );'
  );

  if patched_text = source_text then
    raise exception using message = 'duet_scope_unchanged';
  end if;
  execute patched_text;
end;
$duet_scope_one_source$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
--
-- Функция чистая: она не читает ни одной строки и зависит только от аргумента.
-- Значит проверяется по-настоящему — вызовом на собранных здесь же входах, а не
-- чтением собственного текста.
--
-- Разбор механики у «Дуэта» ОБЯЗАТЕЛЕН (решение владельца, миграция
-- 202608220006): модель ведущего исходного ролика не получает вовсе, и разбор —
-- единственный источник того, о чём комментатор будет говорить. Поэтому здесь
-- он настоящий, а не заглушка.
do $duet_scope_verify$
declare
  source_id constant text := '11111111-1111-4111-8111-111111111111';
  original_id constant text := '22222222-2222-4222-8222-222222222222';
  product_id constant text := '33333333-3333-4333-8333-333333333333';
  attachment_id constant text := '44444444-4444-4444-8444-444444444444';
  reviewer_id constant text := '55555555-5555-4555-8555-555555555555';
  source_snapshot jsonb;
  summary_value jsonb;
  mechanics_value jsonb;
  duet_selection jsonb;
  duet_assets jsonb;
  duet_scope jsonb;
  copy_selection jsonb;
  copy_assets jsonb;
  copy_scope jsonb;
begin
  source_snapshot := jsonb_build_object(
    'version', 'generation-strategy-exact-source-snapshot-v1',
    'attachment_id', attachment_id,
    'attachment_hash', repeat('a', 64),
    'source_id', '66666666-6666-4666-8666-666666666666',
    'source_hash', repeat('b', 64),
    'media_object_id', source_id,
    'media_sha256', repeat('c', 64),
    'size_bytes', 4096,
    'duration_seconds', 8
  );

  summary_value := jsonb_build_object(
    'version', 'generation-strategy-mechanics-summary-v1',
    'hook', 'Hands reveal the problem before the product enters frame.',
    'beat_sequence', jsonb_build_array(
      'Open on the practical pain point in one readable action.',
      'Introduce the product and demonstrate the useful transformation.'
    ),
    'pacing', 'Fast opening, measured proof, then a clean close.',
    'camera_language', 'Handheld close-up followed by a stable product detail.',
    'composition', 'Keep the action central and the product label readable.',
    'audio_pattern', 'Short spoken hook with quiet demonstration sounds.',
    'cta_pattern', 'Close with one direct benefit-led invitation.'
  );

  mechanics_value := jsonb_build_object(
    'version', 'generation-strategy-mechanics-snapshot-v1',
    'strategy_id', 'viral_avatar_ugc',
    'source_attachment_id', attachment_id,
    'source_attachment_hash', repeat('a', 64),
    'source_media_id', source_id,
    'source_media_sha256', repeat('c', 64),
    'summary', summary_value,
    'reviewed_by', reviewer_id,
    'review_confirmation', true
  );

  ------------------------------------------------------------------
  -- «Дуэт»: один исходник, он же цель работы.
  ------------------------------------------------------------------
  duet_selection := jsonb_build_object(
    'version', '2026-08-14.v1',
    'strategy_id', 'viral_avatar_ugc',
    'recipe_version', '2026-06',
    'duration_seconds', 8,
    'resolution', '720p',
    'audio', true,
    'assets', jsonb_build_array(jsonb_build_object(
      'role', 'source_video',
      'media_id', source_id,
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

  duet_assets := jsonb_build_array(jsonb_build_object(
    'selection_role', 'source_video',
    'selection_ordinal', 1,
    'media_id', source_id,
    'sha256', repeat('c', 64),
    'kind', 'source_video',
    'mime_type', 'video/mp4',
    'product_id', 'null'::jsonb,
    'rights_confirmed', true
  ));

  duet_scope := jsonb_build_object(
    'version', 'generation-strategy-spec-scope-v1',
    'authority_kind', 'strategy_recipe',
    'primary_media_id', source_id,
    'media_ids', jsonb_build_array(source_id),
    'platform', 'tiktok',
    'provider', 'runway',
    'strategy_id', 'viral_avatar_ugc',
    'recipe', 'product_ugc',
    'input_mode', 'video_and_avatar_images',
    'duration_seconds', 8,
    'product_category', 'other',
    'format', 'source',
    'ratio', 'source',
    'resolution', '720p',
    'audio', true,
    'spoken_dialogue', false,
    -- Ссылок ноль: ассет один, и он же цель. Прежде здесь стояла двойка —
    -- фотография лица и фотография товара.
    'reference_count', 0,
    -- Исходник провайдеру НЕ уходит: ведущего снимают отдельно, а соединение
    -- делает наш ffmpeg. Это отличает дуэт от «Копии» при одинаковом кадре.
    'reference_video', false,
    'first_frame', false,
    'last_frame', false,
    'selection', duet_selection,
    'selection_hash', content_factory_private.json_hash(duet_selection),
    'asset_snapshot', duet_assets,
    'asset_snapshot_hash', content_factory_private.json_hash(duet_assets),
    'source', source_snapshot,
    'source_hash', content_factory_private.json_hash(source_snapshot),
    'mechanics', mechanics_value,
    'mechanics_hash', content_factory_private.json_hash(mechanics_value)
  );

  if content_factory_private.generation_strategy_spec_scope_legacy_v1(
       duet_scope
     ) is distinct from duet_scope then
    raise exception using message = 'duet_scope_rejected';
  end if;

  -- Соотношение сторон дуэту чужое: кадр приходит из исходника.
  if content_factory_private.generation_strategy_spec_scope_legacy_v1(
       duet_scope
         || jsonb_build_object('ratio', '720:1280', 'format', '720:1280')
     ) is not null then
    raise exception using message = 'duet_scope_still_takes_vertical_ratio';
  end if;

  -- Цель работы обязана совпасть с исходником. Чужой первичный медиа-объект
  -- означал бы ролик про то, чего в наряде нет.
  if content_factory_private.generation_strategy_spec_scope_legacy_v1(
       duet_scope || jsonb_build_object(
         'primary_media_id', product_id,
         'media_ids', jsonb_build_array(product_id)
       )
     ) is not null then
    raise exception using message = 'duet_scope_accepts_foreign_target';
  end if;

  ------------------------------------------------------------------
  -- «Копия» не тронута: у неё цель — товар, а исходник целью НЕ становится.
  ------------------------------------------------------------------
  copy_selection := jsonb_build_object(
    'version', '2026-08-14.v1',
    'strategy_id', 'viral_product_swap',
    'recipe_version', '2026-06',
    'duration_seconds', 8,
    'resolution', '720p',
    'audio', true,
    'assets', jsonb_build_array(
      jsonb_build_object(
        'role', 'source_video', 'media_id', source_id, 'duration_seconds', 8
      ),
      jsonb_build_object(
        'role', 'original_product_image', 'media_id', original_id
      ),
      jsonb_build_object(
        'role', 'new_product_image', 'media_id', product_id, 'view', 'front'
      )
    ),
    'attestations', jsonb_build_object(
      'source_media_rights_confirmed', true,
      'transformative_use_confirmed', true,
      'product_assets_rights_confirmed', true,
      'depicted_people_consent_confirmed', true
    )
  );

  copy_assets := jsonb_build_array(
    jsonb_build_object(
      'selection_role', 'source_video', 'selection_ordinal', 1,
      'media_id', source_id, 'sha256', repeat('c', 64),
      'kind', 'source_video', 'mime_type', 'video/mp4',
      'product_id', 'null'::jsonb, 'rights_confirmed', true
    ),
    jsonb_build_object(
      'selection_role', 'original_product_image', 'selection_ordinal', 2,
      'media_id', original_id, 'sha256', repeat('d', 64),
      'kind', 'creator_reference', 'mime_type', 'image/jpeg',
      'product_id', 'null'::jsonb, 'rights_confirmed', true
    ),
    jsonb_build_object(
      'selection_role', 'new_product_image', 'selection_ordinal', 3,
      'media_id', product_id, 'sha256', repeat('e', 64),
      'kind', 'product_photo', 'mime_type', 'image/png',
      'product_id', '77777777-7777-4777-8777-777777777777',
      'rights_confirmed', true
    )
  );

  copy_scope := jsonb_build_object(
    'version', 'generation-strategy-spec-scope-v1',
    'authority_kind', 'strategy_recipe',
    'primary_media_id', product_id,
    'media_ids', jsonb_build_array(product_id),
    'platform', 'tiktok',
    'provider', 'runway',
    'strategy_id', 'viral_product_swap',
    'recipe', 'product_swap',
    'input_mode', 'video_and_product_images',
    'duration_seconds', 8,
    'product_category', 'other',
    'format', 'source',
    'ratio', 'source',
    'resolution', '720p',
    'audio', true,
    'spoken_dialogue', false,
    'reference_count', 2,
    'reference_video', true,
    'first_frame', false,
    'last_frame', false,
    'selection', copy_selection,
    'selection_hash', content_factory_private.json_hash(copy_selection),
    'asset_snapshot', copy_assets,
    'asset_snapshot_hash', content_factory_private.json_hash(copy_assets),
    'source', source_snapshot,
    'source_hash', content_factory_private.json_hash(source_snapshot),
    -- У «Копии» разбора механики нет: она правит сам ролик, и сцена доезжает
    -- до модели целиком, а не пересказом.
    'mechanics', 'null'::jsonb,
    'mechanics_hash', 'null'::jsonb
  );

  if content_factory_private.generation_strategy_spec_scope_legacy_v1(
       copy_scope
     ) is distinct from copy_scope then
    raise exception using message = 'product_swap_scope_broke';
  end if;

  -- Самое важное утверждение про соседа: исходник «Копии» целью НЕ стал.
  -- Если бы список ролей расширили без ветвления по стратегии, этот объём
  -- прошёл бы — и «Копия» молча начала бы делать ролик про чужое видео.
  if content_factory_private.generation_strategy_spec_scope_legacy_v1(
       copy_scope || jsonb_build_object(
         'primary_media_id', source_id,
         'media_ids', jsonb_build_array(source_id)
       )
     ) is not null then
    raise exception using message = 'product_swap_target_leaked_to_source';
  end if;
end;
$duet_scope_verify$;

commit;
