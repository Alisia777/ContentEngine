begin;

-- 202608230008_duet_presenter_signed_on_binding_v1
--
-- «Дуэт»: КТО ведущий — подписывается вместе с ценой.
--
-- РАЗДЕЛЕНИЕ, КОТОРОЕ И ЕСТЬ СУТЬ РЕШЕНИЯ.
--
--   КТО ведущий — подписывается на привязке. Подменить после подтверждения
--   цены нельзя: подпись накрывает личность.
--
--   ЧЕМ он является у провайдера (avatarId, voiceId) — читается ЗАНОВО перед
--   отправкой. Заархивированный или отозванный ведущий останавливает запуск, а
--   не воскресает из снимка недельной давности.
--
-- Этот файл делает первую половину. Вторая — отдельным файлом: чтение перед
-- отправкой.
--
-- ПОДПИСЬ МЕНЯТЬ НЕ НУЖНО, И ЭТО ПРОВЕРЕНО. `binding_hash` подписывает
-- `strategy_snapshot_hash`, а тот — весь `strategy_snapshot` целиком. Любой
-- ключ ВНУТРИ снимка подписан транзитивно, никаких правок формул хэшей не
-- требуется. Квитанция готовности не трогается вовсе: клейм уже несёт
-- `spec_strategy_binding_id` и `binding_hash`.
--
-- КЛЮЧИ ДОБАВЛЯЮТСЯ ТОЛЬКО ДУЭТУ. Безусловное добавление ключа со значением
-- null изменило бы `strategy_snapshot_hash` У ВСЕХ стратегий — а значит и
-- `binding_hash`, — и повторная привязка любого существующего запуска «Копии»
-- начала бы падать на `generation_strategy_binding_conflict`. Поэтому ключи
-- ОБЯЗАТЕЛЬНЫ дуэту и ЗАПРЕЩЕНЫ остальным: снимки «Копии» и «Создания»
-- остаются байт в байт прежними. Тот же приём, что у `product_id` в
-- 202608220015.
--
-- ПОЧЕМУ РАСКЛАДКА ХРАНИТСЯ В СНИМКЕ, А НЕ ЧИТАЕТСЯ ПО ССЫЛКЕ. Раскладку
-- ведущего можно менять (`creator_update_duet_presenter_layout`). Если бы
-- сборка читала её на момент склейки, правка раскладки задним числом сдвинула
-- бы уже подтверждённый и уже оплаченный ролик. В снимок кладётся та
-- раскладка, что действовала в момент подтверждения цены, — и она подписана.
--
-- ЧЕГО ЗДЕСЬ НЕТ. Ни личность у провайдера (avatarId, voiceId) в снимок не
-- попадает, ни маршрут не включается. Первое — намеренно: сохранённый avatarId
-- пережил бы отзыв согласия. Второе — последний шаг всей работы.

-- 1. Колонки привязки и составная ссылка на ведущего.
--
-- Ссылка составная: ведущий обязан принадлежать той же организации и тому же
-- проекту, что и привязка. Простая ссылка по `id` пропустила бы ведущего
-- чужого проекта — а он у провайдера тот же самый, и подмена прошла бы молча.
create unique index if not exists generation_duet_presenters_scope_key
  on content_factory.generation_duet_presenters (organization_id, project_id, id);

alter table content_factory.generation_spec_strategy_bindings
  add column if not exists duet_presenter_id uuid,
  add column if not exists duet_layout jsonb;

do $duet_binding_columns$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_spec_strategy_bindings_duet_presenter_fkey'
      and conrelid = 'content_factory.generation_spec_strategy_bindings'::regclass
  ) then
    alter table content_factory.generation_spec_strategy_bindings
      add constraint generation_spec_strategy_bindings_duet_presenter_fkey
      foreign key (organization_id, project_id, duet_presenter_id)
      references content_factory.generation_duet_presenters
        (organization_id, project_id, id);
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_spec_strategy_bindings_duet_presenter_check'
      and conrelid = 'content_factory.generation_spec_strategy_bindings'::regclass
  ) then
    -- Есть тогда и только тогда, когда это дуэт. Обе половины важны: у дуэта
    -- без ведущего нечего отправлять, у остальных ведущий — это лишний факт,
    -- который однажды разойдётся с тем, что действительно ушло провайдеру.
    alter table content_factory.generation_spec_strategy_bindings
      add constraint generation_spec_strategy_bindings_duet_presenter_check
      check (
        case when strategy_id = 'viral_avatar_ugc'
          then duet_presenter_id is not null and duet_layout is not null
          else duet_presenter_id is null and duet_layout is null
        end
      );
  end if;
end;
$duet_binding_columns$;

-- 2. Снимок признаёт два новых ключа — и только у дуэта.
do $snapshot_valid_duet$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_spec_strategy_snapshot_valid(jsonb)'
      ::regprocedure
  );
  if position('duet_presenter_id' in source_text) > 0 then
    return;
  end if;
  patched_text := source_text;

  anchor := E'    and p_value - array[\n'
         || E'      ''version'', ''strategy_id'', ''selection_hash'', ''source_basis'', ''spec'',\n'
         || E'      ''product_id'', ''source'', ''role_assets'', ''attestations''\n'
         || E'    ]::text[] = ''{}''::jsonb';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'snapshot_valid_anchor_allowed_keys';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    and p_value - array[\n'
      || E'      ''version'', ''strategy_id'', ''selection_hash'', ''source_basis'', ''spec'',\n'
      || E'      ''product_id'', ''source'', ''role_assets'', ''attestations'',\n'
      || E'      ''duet_presenter_id'', ''duet_layout''\n'
      || E'    ]::text[] = ''{}''::jsonb'
  );

  anchor := E'    ]::text[]\n'
         || E'    and p_value ->> ''version'' = ''generation-spec-strategy-snapshot-v1''';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'snapshot_valid_anchor_required_keys';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    ]::text[]\n'
      || E'    -- Ведущий обязателен дуэту и запрещён остальным. Запрет — не\n'
      || E'    -- придирка: снимок «Копии» с ключом ведущего означал бы, что\n'
      || E'    -- подписано то, чего в запросе к провайдеру не будет.\n'
      || E'    and (case\n'
      || E'      when p_value ->> ''strategy_id'' = ''viral_avatar_ugc'' then\n'
      || E'        p_value ?& array[''duet_presenter_id'', ''duet_layout'']::text[]\n'
      || E'        and p_value ->> ''duet_presenter_id'' ~\n'
      || E'          ''^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$''\n'
      || E'        and jsonb_typeof(p_value -> ''duet_layout'') = ''object''\n'
      || E'        and (p_value -> ''duet_layout'') - array[\n'
      || E'          ''corner'', ''shape'', ''widthPercent''\n'
      || E'        ]::text[] = ''{}''::jsonb\n'
      || E'        and (p_value -> ''duet_layout'') ?& array[\n'
      || E'          ''corner'', ''shape'', ''widthPercent''\n'
      || E'        ]::text[]\n'
      || E'        and p_value #>> ''{duet_layout,corner}'' in (\n'
      || E'          ''bottom_left'', ''bottom_right'', ''top_left'', ''top_right''\n'
      || E'        )\n'
      || E'        and p_value #>> ''{duet_layout,shape}'' in (''cutout'', ''window'')\n'
      || E'        and jsonb_typeof(p_value #> ''{duet_layout,widthPercent}'') = ''number''\n'
      || E'        and (p_value #>> ''{duet_layout,widthPercent}'')::numeric\n'
      || E'              between 20 and 50\n'
      || E'      else\n'
      || E'        not (p_value ?| array[''duet_presenter_id'', ''duet_layout'']::text[])\n'
      || E'    end)\n'
      || E'    and p_value ->> ''version'' = ''generation-spec-strategy-snapshot-v1'''
  );

  if patched_text = source_text then
    raise exception using message = 'snapshot_valid_unchanged';
  end if;
  execute patched_text;
end;
$snapshot_valid_duet$;

-- 3. Нижняя привязка принимает ведущего, проверяет его и подписывает.
do $low_bind_duet_presenter$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'public.system_bind_generation_spec_strategy(jsonb)'::regprocedure
  );
  if position('generation_strategy_binding_duet_presenter_required' in source_text) > 0
  then
    return;
  end if;
  patched_text := source_text;

  -- 3.1. Переменные.
  anchor := E'  approved_spec_value boolean := false;\nbegin';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'low_bind_anchor_declare';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  approved_spec_value boolean := false;\n'
      || E'  duet_presenter_id_value uuid;\n'
      || E'  duet_presenter_identity_value jsonb;\n'
      || E'  duet_layout_value jsonb;\n'
      || E'begin'
  );

  -- 3.2. Ключ становится ДОПУСТИМЫМ. Обязательным он не всегда, поэтому
  --      вычитается из состава, но не требуется набором `?&`.
  anchor := E'       ''avatar_likeness_consent_confirmed'', ''confirmation'', ''idempotency_key''\n'
         || E'     ]::text[] <> ''{}''::jsonb';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'low_bind_anchor_payload_keys';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'       ''avatar_likeness_consent_confirmed'', ''confirmation'', ''idempotency_key'',\n'
      || E'       ''duet_presenter_id''\n'
      || E'     ]::text[] <> ''{}''::jsonb'
  );

  -- 3.3. Обязательность по стратегии и проверка самого ведущего. Место
  --      выбрано осознанно: доступ к проекту уже проверен, а замок ещё не
  --      взят — отказ по чужому ведущему не должен держать блокировку спеки.
  anchor := E'  perform pg_advisory_xact_lock(\n'
         || E'    hashtext(organization_id_value::text),\n'
         || E'    hashtext(''generation-strategy:'' || spec_id_value::text)\n'
         || E'  );';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'low_bind_anchor_lock';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  -- Ведущий «Дуэта»: обязателен ему и запрещён остальным.\n'
      || E'  if strategy_id_value = ''viral_avatar_ugc'' then\n'
      || E'    if not (p_payload ? ''duet_presenter_id'') then\n'
      || E'      raise exception using errcode = ''22023'',\n'
      || E'        message = ''generation_strategy_binding_duet_presenter_required'';\n'
      || E'    end if;\n'
      || E'    duet_presenter_id_value := content_factory_private.require_uuid(\n'
      || E'      p_payload, ''duet_presenter_id''\n'
      || E'    );\n'
      || E'    -- Личность спрашивается у реестра, а не принимается на слово:\n'
      || E'    -- функция сама держит и принадлежность проекту, и активность, и\n'
      || E'    -- подтверждённое согласие на образ живого человека.\n'
      || E'    duet_presenter_identity_value :=\n'
      || E'      content_factory_private.duet_presenter_identity(\n'
      || E'        organization_id_value, project_id_value, duet_presenter_id_value\n'
      || E'      );\n'
      || E'    if duet_presenter_identity_value is null then\n'
      || E'      raise exception using errcode = ''42501'',\n'
      || E'        message = ''generation_strategy_binding_duet_presenter_invalid'';\n'
      || E'    end if;\n'
      || E'    -- В снимок уходит РАСКЛАДКА, и только она. Идентификаторы\n'
      || E'    -- ведущего у провайдера сюда не попадают: сохранённые, они\n'
      || E'    -- пережили бы отзыв согласия и архивацию, а значит их читают\n'
      || E'    -- заново перед каждой отправкой.\n'
      || E'    duet_layout_value := duet_presenter_identity_value -> ''layout'';\n'
      || E'  elsif p_payload ? ''duet_presenter_id'' then\n'
      || E'    raise exception using errcode = ''22023'',\n'
      || E'      message = ''generation_strategy_binding_duet_presenter_not_accepted'';\n'
      || E'  end if;\n'
      || E'\n'
      || E'  perform pg_advisory_xact_lock(\n'
      || E'    hashtext(organization_id_value::text),\n'
      || E'    hashtext(''generation-strategy:'' || spec_id_value::text)\n'
      || E'  );'
  );

  -- 3.4. Снимок. Ключи добавляются ТОЛЬКО дуэту: у остальных стратегий снимок
  --      обязан остаться прежним до байта, иначе их подписи разъедутся.
  anchor := E'      ''avatar_likeness_consent_confirmed'', likeness_consent_value\n'
         || E'    )\n'
         || E'  );\n'
         || E'  if not content_factory_private.generation_spec_strategy_snapshot_valid(';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'low_bind_anchor_snapshot';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'      ''avatar_likeness_consent_confirmed'', likeness_consent_value\n'
      || E'    )\n'
      || E'  ) || case when strategy_id_value = ''viral_avatar_ugc''\n'
      || E'    then jsonb_build_object(\n'
      || E'      ''duet_presenter_id'', duet_presenter_id_value,\n'
      || E'      ''duet_layout'', duet_layout_value\n'
      || E'    )\n'
      || E'    else ''{}''::jsonb\n'
      || E'  end;\n'
      || E'  if not content_factory_private.generation_spec_strategy_snapshot_valid('
  );

  -- 3.5. Хэш запроса. Ведущий — часть запроса, и повторный запрос с другим
  --      ведущим обязан отличаться уже здесь, а не только в сравнении снимков.
  anchor := E'    ''avatar_likeness_consent_confirmed'', likeness_consent_value,\n'
         || E'    ''confirmation'', true\n'
         || E'  ));';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'low_bind_anchor_request_hash';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    ''avatar_likeness_consent_confirmed'', likeness_consent_value,\n'
      || E'    ''confirmation'', true\n'
      || E'  ) || case when strategy_id_value = ''viral_avatar_ugc''\n'
      || E'    then jsonb_build_object(''duet_presenter_id'', duet_presenter_id_value)\n'
      || E'    else ''{}''::jsonb\n'
      || E'  end);'
  );

  -- 3.6. Строка привязки.
  anchor := E'      request_hash, binding_hash, idempotency_key\n'
         || E'    ) values (';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'low_bind_anchor_insert_columns';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'      request_hash, binding_hash, idempotency_key,\n'
      || E'      duet_presenter_id, duet_layout\n'
      || E'    ) values ('
  );

  anchor := E'      actor_id_value, request_hash_value, binding_hash_value,\n'
         || E'      idempotency_key_value\n'
         || E'    ) returning * into binding_row;';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'low_bind_anchor_insert_values';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'      actor_id_value, request_hash_value, binding_hash_value,\n'
      || E'      idempotency_key_value, duet_presenter_id_value, duet_layout_value\n'
      || E'    ) returning * into binding_row;'
  );

  if patched_text = source_text then
    raise exception using message = 'low_bind_unchanged';
  end if;
  execute patched_text;
end;
$low_bind_duet_presenter$;

-- 4. Верхняя привязка принимает ведущего от портала и передаёт вниз.
do $resolve_bind_duet_presenter$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );
  if position('duet_presenter_id' in source_text) > 0 then
    return;
  end if;
  patched_text := source_text;

  -- 4.1. Ключ допустим, но не обязателен всем: обязательность держит нижняя
  --      привязка, там же где и запрет для остальных стратегий. Дублировать
  --      правило здесь значило бы завести два его источника.
  anchor := E'  if p_payload - array[\n'
         || E'       ''version'', ''organization_id'', ''project_id'', ''actor_id'', ''spec_id'',\n'
         || E'       ''spec_version'', ''spec_hash'', ''selection'', ''confirmation'',\n'
         || E'       ''idempotency_key'', ''engine''\n'
         || E'     ]::text[] <> ''{}''::jsonb';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'resolve_bind_anchor_payload_keys';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  if p_payload - array[\n'
      || E'       ''version'', ''organization_id'', ''project_id'', ''actor_id'', ''spec_id'',\n'
      || E'       ''spec_version'', ''spec_hash'', ''selection'', ''confirmation'',\n'
      || E'       ''idempotency_key'', ''engine'', ''duet_presenter_id''\n'
      || E'     ]::text[] <> ''{}''::jsonb'
  );

  -- 4.2. Передача вниз. Ключ добавляется только когда он пришёл: безусловное
  --      добавление со значением null сделало бы его «переданным» для «Копии»
  --      и упёрлось бы в запрет нижней привязки.
  anchor := E'      ''confirmation'', true,\n'
         || E'      ''idempotency_key'', idempotency_key_value\n'
         || E'    )\n'
         || E'  );';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'resolve_bind_anchor_delegation';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'      ''confirmation'', true,\n'
      || E'      ''idempotency_key'', idempotency_key_value\n'
      || E'    ) || case when p_payload ? ''duet_presenter_id''\n'
      || E'      then jsonb_build_object(\n'
      || E'        ''duet_presenter_id'', p_payload -> ''duet_presenter_id''\n'
      || E'      )\n'
      || E'      else ''{}''::jsonb\n'
      || E'    end\n'
      || E'  );'
  );

  if patched_text = source_text then
    raise exception using message = 'resolve_bind_unchanged';
  end if;
  execute patched_text;
end;
$resolve_bind_duet_presenter$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
--
-- Проверяющий снимка — чистая функция от одного аргумента. Его можно спросить
-- прямо, без единой строки фикстуры, и это самая ценная проверка файла: именно
-- он решает, подписан ли ведущий.
do $duet_presenter_binding_verify$
declare
  base_duet jsonb;
  base_copy jsonb;
  definition_value text;
begin
  base_copy := jsonb_build_object(
    'version', 'generation-spec-strategy-snapshot-v1',
    'strategy_id', 'viral_product_swap',
    'selection_hash', repeat('a', 64),
    'source_basis', 'exact_source_video',
    'spec', jsonb_build_object(
      'spec_id', '11111111-1111-4111-8111-111111111111',
      'spec_version', 1,
      'spec_hash', repeat('b', 64),
      'prompt_hash', repeat('c', 64)
    ),
    'product_id', '22222222-2222-4222-8222-222222222222',
    -- Снимок источника и реестр вложений разбираются собственными
    -- проверяющими, и оба требуют полной формы. Заготовка обязана быть
    -- настоящей: иначе отказ пришёл бы по чужой причине и выглядел бы как
    -- «ведущий проверяется», хотя проверялась бы форма источника.
    'source', jsonb_build_object(
      'basis', 'exact_source_video',
      'binding_id', '44444444-4444-4444-8444-444444444444',
      'binding_hash', repeat('d', 64),
      'source_id', '55555555-5555-4555-8555-555555555555',
      'source_hash', repeat('e', 64),
      'media_object_id', '66666666-6666-4666-8666-666666666666',
      'media_sha256', repeat('f', 64)
    ),
    'role_assets', jsonb_build_array(jsonb_build_object(
      'role', 'source_video',
      'ordinal', 1,
      'media_object_id', '66666666-6666-4666-8666-666666666666',
      'sha256', repeat('f', 64),
      'kind', 'source_video',
      'mime_type', 'video/mp4',
      'product_id', null,
      'rights_confirmed', true,
      'likeness_consent', false
    )),
    'attestations', jsonb_build_object(
      'version', 'generation-strategy-attestation-v1',
      'source_media_rights_confirmed', true,
      'transformative_use_confirmed', true,
      'product_assets_rights_confirmed', true,
      'depicted_people_consent_confirmed', true,
      'avatar_likeness_consent_confirmed', true
    )
  );
  base_duet := base_copy
    || jsonb_build_object('strategy_id', 'viral_avatar_ugc');

  -- 1. Дуэт без ведущего отвергается. Это главное утверждение файла: без него
  --    привязка ушла бы в оплату, не назвав, кто говорит.
  if content_factory_private.generation_spec_strategy_snapshot_valid(base_duet)
  then
    raise exception using message = 'duet_snapshot_accepted_without_presenter';
  end if;

  -- 2. Дуэт с ведущим и раскладкой проходит все прочие проверки снимка. Тут
  --    важно, что отказ выше был именно про ведущего, а не про форму вообще.
  if not content_factory_private.generation_spec_strategy_snapshot_valid(
       base_duet || jsonb_build_object(
         'duet_presenter_id', '33333333-3333-4333-8333-333333333333',
         'duet_layout', jsonb_build_object(
           'corner', 'bottom_left', 'shape', 'cutout', 'widthPercent', 34
         )
       )
     ) then
    raise exception using message = 'duet_snapshot_rejected_with_presenter';
  end if;

  -- 3. Раскладка проверяется по существу, а не по наличию.
  if content_factory_private.generation_spec_strategy_snapshot_valid(
       base_duet || jsonb_build_object(
         'duet_presenter_id', '33333333-3333-4333-8333-333333333333',
         'duet_layout', jsonb_build_object(
           'corner', 'middle', 'shape', 'cutout', 'widthPercent', 34
         )
       )
     ) then
    raise exception using message = 'duet_snapshot_took_unknown_corner';
  end if;
  if content_factory_private.generation_spec_strategy_snapshot_valid(
       base_duet || jsonb_build_object(
         'duet_presenter_id', '33333333-3333-4333-8333-333333333333',
         'duet_layout', jsonb_build_object(
           'corner', 'bottom_left', 'shape', 'cutout', 'widthPercent', 90
         )
       )
     ) then
    raise exception using message = 'duet_snapshot_took_oversized_overlay';
  end if;

  -- 4. «Копия» без ведущего — как была. Снимок обязан остаться прежним до
  --    байта, иначе разъедутся уже подписанные привязки.
  if not content_factory_private.generation_spec_strategy_snapshot_valid(base_copy)
  then
    raise exception using message = 'copy_snapshot_broke';
  end if;

  -- 5. «Копия» С ведущим — отказ. Подписанный факт, которого не будет в
  --    запросе к провайдеру, хуже отсутствующего.
  if content_factory_private.generation_spec_strategy_snapshot_valid(
       base_copy || jsonb_build_object(
         'duet_presenter_id', '33333333-3333-4333-8333-333333333333',
         'duet_layout', jsonb_build_object(
           'corner', 'bottom_left', 'shape', 'cutout', 'widthPercent', 34
         )
       )
     ) then
    raise exception using message = 'copy_snapshot_took_presenter';
  end if;

  -- 6. Колонки, ссылка и ограничение на месте.
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'content_factory'
      and table_name = 'generation_spec_strategy_bindings'
      and column_name in ('duet_presenter_id', 'duet_layout')
    having count(*) = 2
  ) then
    raise exception using message = 'duet_binding_columns_missing';
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_spec_strategy_bindings_duet_presenter_fkey'
      and conrelid = 'content_factory.generation_spec_strategy_bindings'::regclass
      and confrelid = 'content_factory.generation_duet_presenters'::regclass
      and cardinality(conkey) = 3
  ) then
    raise exception using message = 'duet_presenter_fkey_missing_or_not_scoped';
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_spec_strategy_bindings_duet_presenter_check'
      and conrelid = 'content_factory.generation_spec_strategy_bindings'::regclass
  ) then
    raise exception using message = 'duet_presenter_check_missing';
  end if;

  -- 7. Обе привязки знают про ключ, и нижняя умеет отказывать в обе стороны.
  definition_value := pg_get_functiondef(
    'public.system_bind_generation_spec_strategy(jsonb)'::regprocedure
  );
  if position('generation_strategy_binding_duet_presenter_required' in definition_value) = 0
     or position('generation_strategy_binding_duet_presenter_not_accepted' in definition_value) = 0
     or position('generation_strategy_binding_duet_presenter_invalid' in definition_value) = 0
  then
    raise exception using message = 'low_bind_duet_refusals_missing';
  end if;
  -- Идентификаторы ведущего у провайдера в снимок не попадают: их читают
  -- заново перед отправкой. Проверяется отсутствие самих колонок реестра —
  -- попасть в снимок они могли бы только отсюда.
  if position('provider_avatar_id' in definition_value) > 0
     or position('provider_voice_id' in definition_value) > 0 then
    raise exception using message = 'low_bind_snapshotted_provider_identity';
  end if;
  definition_value := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );
  if position('''duet_presenter_id''' in definition_value) = 0 then
    raise exception using message = 'resolve_bind_duet_key_missing';
  end if;

  -- 8. Маршрут «Дуэта» по-прежнему выключен.
  if exists (
    select 1 from content_factory.generation_strategy_provider_routes
    where strategy_id = 'viral_avatar_ugc' and (enabled or recommended)
  ) then
    raise exception using message = 'duet_route_enabled_too_early';
  end if;
end;
$duet_presenter_binding_verify$;

commit;
