begin;

-- 202608220015_duet_spec_product_and_target_v1
--
-- «Дуэт»: откуда берётся товар и что считается целью работы.
--
-- ЗАДАЧА. Версия ТЗ требует `product_id`, `primary_media_id` и непустой
-- `media_ids`. У «Копии» и «Создания» всё три берутся из ФОТОГРАФИЙ ТОВАРА:
-- товар выводится из медиа-объекта, он же становится целью. У дуэта фотографий
-- товара нет вовсе — он комментирует чужой ролик, — и вывести товар не из чего.
--
-- РЕШЕНИЕ ВЛАДЕЛЬЦА 22.08.2026: товар у дуэта остаётся и приходит ЯВНЫМ ПОЛЕМ
-- из формы. Так запуск остаётся в фильтрах архива и в разрезах бюджета по
-- товару. Альтернатива — снять NOT NULL с `product_id` в шести таблицах пути
-- стратегии — отклонена: правка больше, риск выше, а дуэт выпал бы из товарного
-- учёта.
--
-- ПОЧЕМУ ПОЛЕ ТОЛЬКО У ДУЭТА. У «Копии» и «Создания» товар уже назван
-- фотографиями, и это единственный его источник. Принимать его вторым путём
-- значило бы завести два источника одного факта — и однажды они разойдутся.
-- Поэтому ключ `product_id` ОБЯЗАТЕЛЕН для дуэта и ЗАПРЕЩЁН для остальных.
--
-- ЦЕЛЬ РАБОТЫ ДУЭТА — САМ КОММЕНТИРУЕМЫЙ РОЛИК. Он и есть то, ПРО ЧТО делается
-- запуск: ведущий приходит из библиотеки проекта и медиа-объектом формы не
-- бывает. Раньше целью считалась фотография лица, а без неё `target_media_ids`
-- оставался пустым — и проверка `primary_media_id = any(target_media_ids)`
-- становилась заведомо ложной. Путь обрывался здесь, до цены.

do $duet_prepare_spec$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );
  -- Повторный прогон обязан быть тихим: признак — имя ошибки, которого в
  -- прежней редакции быть не могло.
  if position('generation_strategy_spec_product_required' in source_text) > 0 then
    return;
  end if;
  patched_text := source_text;

  -- 1. `product_id` становится ДОПУСТИМЫМ ключом полезной нагрузки. Обязателен
  --    он не всегда, поэтому вычитается из состава, но не требуется набором
  --    `?&` — обязательность проверяется отдельно, по стратегии.
  anchor := E'     or p_payload - array[\n'
         || E'       ''version'', ''organization_id'', ''project_id'', ''platform'',\n'
         || E'       ''product_category'', ''selection'', ''editable_intent'',\n'
         || E'       ''proposed_prompt'', ''mechanics_summary'', ''confirmation'', ''reason'',\n'
         || E'       ''idempotency_key''\n'
         || E'     ]::text[] <> ''{}''::jsonb';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_prepare_payload_keys';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'     or p_payload - array[\n'
      || E'       ''version'', ''organization_id'', ''project_id'', ''platform'',\n'
      || E'       ''product_category'', ''selection'', ''editable_intent'',\n'
      || E'       ''proposed_prompt'', ''mechanics_summary'', ''confirmation'', ''reason'',\n'
      || E'       ''idempotency_key'', ''product_id''\n'
      || E'     ]::text[] <> ''{}''::jsonb'
  );

  -- 2. Обязательность ключа по стратегии. Проверка ставится сразу после
  --    разбора выбора, до всякой работы с медиа: полезная нагрузка не той формы
  --    не должна доходить до чтения ассетов.
  anchor := E'  if recipe_value in (''product_swap'', ''product_ugc'') then';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_prepare_recipe_branch';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  -- Товар «Дуэта» приходит явным полем: фотографий товара у него нет, и\n'
      || E'  -- вывести его больше неоткуда. У остальных стратегий товар уже назван\n'
      || E'  -- фотографиями, и второй источник того же факта здесь запрещён — два\n'
      || E'  -- источника однажды разойдутся, и разойдутся молча.\n'
      || E'  if strategy_id_value = ''viral_avatar_ugc'' then\n'
      || E'    if not (p_payload ? ''product_id'') then\n'
      || E'      raise exception using errcode = ''22023'',\n'
      || E'        message = ''generation_strategy_spec_product_required'';\n'
      || E'    end if;\n'
      || E'    product_id_value := content_factory_private.require_uuid(\n'
      || E'      p_payload, ''product_id''\n'
      || E'    );\n'
      || E'  elsif p_payload ? ''product_id'' then\n'
      || E'    raise exception using errcode = ''22023'',\n'
      || E'      message = ''generation_strategy_spec_product_not_accepted'';\n'
      || E'  end if;\n'
      || E'  if recipe_value in (''product_swap'', ''product_ugc'') then'
  );

  -- 3. Цель работы дуэта — сам комментируемый ролик.
  anchor := E'    elsif asset_role_value = ''source_video'' then\n'
         || E'      if media_row.mime_type <> ''video/mp4''\n'
         || E'         or media_row.metadata ->> ''kind'' <> ''source_video'' then\n'
         || E'        raise exception using errcode = ''42501'',\n'
         || E'          message = ''generation_strategy_spec_asset_invalid'';\n'
         || E'      end if;\n'
         || E'      source_media_id_value := media_row.id;';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_anchor_prepare_source_branch';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    elsif asset_role_value = ''source_video'' then\n'
      || E'      if media_row.mime_type <> ''video/mp4''\n'
      || E'         or media_row.metadata ->> ''kind'' <> ''source_video'' then\n'
      || E'        raise exception using errcode = ''42501'',\n'
      || E'          message = ''generation_strategy_spec_asset_invalid'';\n'
      || E'      end if;\n'
      || E'      -- У «Дуэта» цель работы — САМ КОММЕНТИРУЕМЫЙ РОЛИК: ведущий\n'
      || E'      -- приходит из библиотеки проекта и медиа-объектом формы не\n'
      || E'      -- бывает. У «Копии» и «Создания» исходник целью не является:\n'
      || E'      -- там ролик делается про товар.\n'
      || E'      if strategy_id_value = ''viral_avatar_ugc'' then\n'
      || E'        target_media_ids_value := array_append(\n'
      || E'          target_media_ids_value, media_row.id\n'
      || E'        );\n'
      || E'      end if;\n'
      || E'      source_media_id_value := media_row.id;'
  );

  if patched_text = source_text then
    raise exception using message = 'duet_prepare_spec_unchanged';
  end if;
  execute patched_text;
end;
$duet_prepare_spec$;

-- ПРОВЕРКА.
--
-- Функция закрыта политикой доступа, и без сессии дальше проверки членства не
-- уйти. Но разбор ПОЛЕЗНОЙ НАГРУЗКИ идёт РАНЬШЕ неё — значит состав ключей
-- проверяется поведением по-настоящему, а не чтением текста.
do $duet_prepare_verify$
declare
  base jsonb;
  message_text text;
  saw_payload_refusal boolean;
begin
  base := jsonb_build_object(
    'version', 'generation-strategy-spec-prepare-request-v1',
    'organization_id', '11111111-1111-4111-8111-111111111111',
    'project_id', '22222222-2222-4222-8222-222222222222',
    'platform', 'tiktok',
    'product_category', 'other',
    'selection', jsonb_build_object(
      'version', '2026-08-14.v1',
      'strategy_id', 'viral_avatar_ugc',
      'recipe_version', '2026-06',
      'duration_seconds', 8,
      'resolution', '720p',
      'audio', true,
      'assets', jsonb_build_array(jsonb_build_object(
        'role', 'source_video',
        'media_id', '33333333-3333-4333-8333-333333333333',
        'duration_seconds', 8
      )),
      'attestations', jsonb_build_object(
        'source_media_rights_confirmed', true,
        'transformative_use_confirmed', true,
        'product_assets_rights_confirmed', true,
        'depicted_people_consent_confirmed', true,
        'avatar_likeness_consent_confirmed', true
      )
    ),
    'editable_intent', 'Прокомментировать ролик от лица ведущей.',
    'proposed_prompt', 'Смотрите, тут он показывает крепление.',
    'mechanics_summary', 'null'::jsonb,
    'confirmation', true,
    'reason', 'Подготовка технической версии дуэта.',
    'idempotency_key', 'strategy-spec:duet-1'
  );

  -- 1. Ключ `product_id` перестал быть чужим: полезная нагрузка с ним проходит
  --    разбор состава и падает уже на доступе, а не на форме.
  saw_payload_refusal := false;
  begin
    perform creator_prepare_generation_strategy_spec(
      base || jsonb_build_object(
        'product_id', '44444444-4444-4444-8444-444444444444'
      )
    );
  exception when others then
    get stacked diagnostics message_text = message_text;
    saw_payload_refusal :=
      message_text = 'generation_strategy_spec_prepare_payload_invalid';
  end;
  if saw_payload_refusal then
    raise exception using message = 'duet_prepare_still_rejects_product_key';
  end if;

  -- 2. Состав ключей не разболтался: посторонний ключ по-прежнему отвергается
  --    той же проверкой. Иначе «разрешили один ключ» незаметно превратилось бы
  --    в «перестали проверять состав».
  saw_payload_refusal := false;
  begin
    perform creator_prepare_generation_strategy_spec(
      base || jsonb_build_object('product_ids', 'x')
    );
  exception when others then
    get stacked diagnostics message_text = message_text;
    saw_payload_refusal :=
      message_text = 'generation_strategy_spec_prepare_payload_invalid';
  end;
  if not saw_payload_refusal then
    raise exception using message = 'prepare_stopped_checking_payload_keys';
  end if;
end;
$duet_prepare_verify$;

-- Остальное проверяется по тексту: до этих мест без сессии не добраться, а
-- завести её внутри миграции значит проверять не функцию, а свою же заготовку.
do $duet_prepare_structure$
declare
  body text;
begin
  body := pg_get_functiondef(
    'creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );
  if position('generation_strategy_spec_product_required' in body) = 0 then
    raise exception using message = 'duet_prepare_missing_product_requirement';
  end if;
  if position('generation_strategy_spec_product_not_accepted' in body) = 0 then
    raise exception using message = 'duet_prepare_missing_product_exclusion';
  end if;
  -- Цель работы дуэта — сам ролик. Признак: добавление в целевой набор внутри
  -- ветки исходника, под условием стратегии.
  if position(
       E'      if strategy_id_value = ''viral_avatar_ugc'' then
'
       || E'        target_media_ids_value := array_append('
       in body
     ) = 0 then
    raise exception using message = 'duet_prepare_source_is_not_the_target';
  end if;
end;
$duet_prepare_structure$;

commit;
