begin;
-- 202608230023_duet_prepare_scope_fixes_v1
--
-- «Дуэт» не мог подготовить точное ТЗ: сервер сам отвергал собственную
-- область подписи (generation_strategy_spec_scope_invalid), а за ней —
-- ворота проекта (generation_spec_project_scope_mismatch) и версия ТЗ
-- (generation_spec_primary_media_invalid), а при бесплатной привязке —
-- generation_strategy_spec_authority_required. Причин пять; правятся вместе.
--
-- ПРИЧИНА 1 — reference_video. 202608220003 научила creator_prepare_generation_strategy_spec
-- ставить признак «исходник уходит провайдеру» по списку рецептов:
--
--   'reference_video', recipe_value in ('product_swap', 'product_ugc')
--
-- Это отвечало пониманию «Аватар = правка готового ролика тем же путём, что и
-- Копия». Владелец отменил его тем же днём (202608220006): «Дуэт» — исходник
-- остаётся собой, провайдер делает только говорящего ведущего, а соединение —
-- наша сторона. Признак у дуэта стал false везде, где его сверяют:
--   · валидатор области generation_strategy_spec_scope_legacy_v1 ждёт
--     (strategy_id_value = 'viral_product_swap');
--   · 202608230001 проверяет область дуэта с 'reference_video', false;
--   · браузерное зеркало (PROVIDER_SOURCE_INPUT_RECIPES в spec.js) держит
--     только product_swap.
-- Не откатили только саму подготовку — и она строила область с true, которую
-- тут же отвергал валидатор. В браузер уходило 500 без имени причины.
--
-- Что с фоновым видео HeyGen v2 (202608230022): туда уходит ССЫЛКА на исходник
-- как фон сборки, но это не «референс для рецепта», который сверяют здесь;
-- подписанный признак остаётся false, как того требуют обе стороны сверки.
--
-- Якорь — только код (правило из 202608210003/202608230010: кириллица в телах
-- функций прода искажена, якорь с ней не найдётся).
do $duet_reference_video_false$
declare
  definition_value text;
  patched_value text;
  anchor constant text :=
    '''reference_video'', recipe_value in (''product_swap'', ''product_ugc'')';
  replacement constant text :=
    '''reference_video'', recipe_value = ''product_swap''';
  anchor_hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );
  -- Повторный прогон тих: замена уже на месте.
  if position(replacement in definition_value) > 0
     and position(anchor in definition_value) = 0 then
    return;
  end if;
  anchor_hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'duet_reference_video_anchor_invalid:' || anchor_hits::text;
  end if;
  patched_value := replace(definition_value, anchor, replacement);
  execute patched_value;
end;
$duet_reference_video_false$;

do $duet_reference_video_false_verify$
declare
  definition_value text;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );
  if position(
       '''reference_video'', recipe_value = ''product_swap'''
       in definition_value
     ) = 0
     or position(
       '''reference_video'', recipe_value in (''product_swap'', ''product_ugc'')'
       in definition_value
     ) > 0 then
    raise exception using message = 'duet_reference_video_not_applied';
  end if;
  -- Валидатор области по-прежнему ждёт false у всего, кроме «Копии»: если
  -- его когда-нибудь перепишут, эта проверка назовёт расхождение первой.
  if position(
       '(strategy_id_value = ''viral_product_swap'')'
       in pg_get_functiondef(
         'content_factory_private.generation_strategy_spec_scope_legacy_v1(jsonb)'
           ::regprocedure
       )
     ) = 0 then
    raise exception using message = 'duet_scope_validator_drifted';
  end if;
end;
$duet_reference_video_false_verify$;

-- ПРИЧИНА 2 — разбор механики не читался. 202608220006 вернула «Дуэту»
-- обязательный разбор (mechanics_required и снимок механики остались только
-- у «Копии» обнулёнными), но сам разбор из payload парсится лишь в ветке
-- «собираем с нуля» (else). В ветке правки готового видео, куда попадает и
-- product_ugc, mechanics_summary_value оставался NULL → в снимок уходило
-- summary: null при mechanics_required = true → валидатор отвергал область.
-- Итог: с 22.08 ни одно ТЗ «Дуэта» не могло быть подготовлено.
do $duet_mechanics_parse$
declare
  definition_value text;
  patched_value text;
  anchor constant text :=
    '    if recipe_value = ''product_swap''' || chr(10) ||
    '       and p_payload -> ''mechanics_summary'' <> ''null''::jsonb then' || chr(10) ||
    '      raise exception using errcode = ''22023'',' || chr(10) ||
    '        message = ''generation_strategy_spec_mechanics_must_be_null'';' || chr(10) ||
    '    end if;';
  replacement constant text :=
    '    if recipe_value = ''product_swap''' || chr(10) ||
    '       and p_payload -> ''mechanics_summary'' <> ''null''::jsonb then' || chr(10) ||
    '      raise exception using errcode = ''22023'',' || chr(10) ||
    '        message = ''generation_strategy_spec_mechanics_must_be_null'';' || chr(10) ||
    '    end if;' || chr(10) ||
    '    if recipe_value = ''product_ugc'' then' || chr(10) ||
    '      mechanics_summary_value := content_factory_private' || chr(10) ||
    '        .generation_strategy_mechanics_summary_v1(' || chr(10) ||
    '          p_payload -> ''mechanics_summary''' || chr(10) ||
    '        );' || chr(10) ||
    '      if mechanics_summary_value is null then' || chr(10) ||
    '        raise exception using errcode = ''22023'',' || chr(10) ||
    '          message = ''generation_strategy_spec_mechanics_required'';' || chr(10) ||
    '      end if;' || chr(10) ||
    '    end if;';
  anchor_hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );
  if position('    if recipe_value = ''product_ugc'' then' in definition_value) > 0 then
    return;  -- уже применено
  end if;
  anchor_hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'duet_mechanics_parse_anchor_invalid:' || anchor_hits::text;
  end if;
  patched_value := replace(definition_value, anchor, replacement);
  execute patched_value;
end;
$duet_mechanics_parse$;

do $duet_mechanics_parse_verify$
declare
  definition_value text;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );
  if position('    if recipe_value = ''product_ugc'' then' in definition_value) = 0
     or position(
       '''mechanics_required'', recipe_value in (''product_ad'', ''product_ugc'')'
       in definition_value
     ) = 0 then
    raise exception using message = 'duet_mechanics_parse_not_applied';
  end if;
end;
$duet_mechanics_parse_verify$;

-- ПРИЧИНА 3 — ворота проекта не знают товара дуэта. После области подпись
-- уходит в creator_prepare_generation_spec, и require_generation_request_project_v49
-- выводит товар из primary_media_id: медиа-объект обязан принадлежать активному
-- товару. У дуэта цель работы — сам комментируемый ролик (202608220015 /
-- 202608230001), а загруженный исходник к товару не привязан (product_id null)
-- → generation_spec_project_scope_mismatch. Товар дуэт называет явным полем;
-- значит, исходник, про который делается дуэт, и есть медиа этого товара —
-- привязываем его к названному товару при подготовке ТЗ. Исходник, уже
-- принадлежащий ДРУГОМУ товару, отвергается: один ролик — один товар, иначе
-- архив и бюджет по товару разошлись бы молча.
do $duet_source_product_bind$
declare
  definition_value text;
  patched_value text;
  anchor constant text :=
    '      if strategy_id_value = ''viral_avatar_ugc'' then' || chr(10) ||
    '        target_media_ids_value := array_append(' || chr(10) ||
    '          target_media_ids_value, media_row.id' || chr(10) ||
    '        );' || chr(10) ||
    '      end if;' || chr(10) ||
    '      source_media_id_value := media_row.id;';
  replacement constant text :=
    '      if strategy_id_value = ''viral_avatar_ugc'' then' || chr(10) ||
    '        target_media_ids_value := array_append(' || chr(10) ||
    '          target_media_ids_value, media_row.id' || chr(10) ||
    '        );' || chr(10) ||
    '        if media_row.product_id is null then' || chr(10) ||
    '          update content_factory.media_objects source_media' || chr(10) ||
    '             set product_id = product_id_value,' || chr(10) ||
    '                 updated_at = now()' || chr(10) ||
    '           where source_media.organization_id = organization_id_value' || chr(10) ||
    '             and source_media.id = media_row.id' || chr(10) ||
    '             and source_media.product_id is null;' || chr(10) ||
    '          media_row.product_id := product_id_value;' || chr(10) ||
    '        elsif media_row.product_id <> product_id_value then' || chr(10) ||
    '          raise exception using errcode = ''42501'',' || chr(10) ||
    '            message = ''generation_strategy_spec_product_not_accepted'';' || chr(10) ||
    '        end if;' || chr(10) ||
    '      end if;' || chr(10) ||
    '      source_media_id_value := media_row.id;';
  anchor_hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );
  if position('update content_factory.media_objects source_media' in definition_value) > 0 then
    return;  -- уже применено
  end if;
  anchor_hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'duet_source_product_anchor_invalid:' || anchor_hits::text;
  end if;
  patched_value := replace(definition_value, anchor, replacement);
  execute patched_value;
end;
$duet_source_product_bind$;

do $duet_source_product_bind_verify$
begin
  if position(
       'update content_factory.media_objects source_media'
       in pg_get_functiondef(
         'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
       )
     ) = 0 then
    raise exception using message = 'duet_source_product_bind_not_applied';
  end if;
end;
$duet_source_product_bind_verify$;

-- ПРИЧИНА 4 — версия ТЗ знает целью только фотографию товара.
-- create_generation_spec_version и assert_generation_spec_current_pre_advisory_v1
-- принимают primary_media_id / media_ids только вида product_photo|packshot.
-- У дуэта цель работы — комментируемый ролик (source_video, video/mp4),
-- привязанный к товару (см. причину 3). Набор допустимых видов расширяется
-- ровно на него; товар по-прежнему обязан совпадать, rights_confirmed — стоять.
do $duet_spec_version_source_target$
declare
  definition_value text;
  patched_value text;
  kind_anchor constant text :=
    'coalesce(media.metadata ->> ''kind'', '''') in (''product_photo'', ''packshot'')';
  kind_replacement constant text :=
    'coalesce(media.metadata ->> ''kind'', '''') in (''product_photo'', ''packshot'', ''source_video'')';
  hits integer;
  target record;
begin
  for target in
    select p.oid as function_oid,
           n.nspname || '.' || p.proname as signature
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private'
      and p.proname in (
        'create_generation_spec_version',
        'assert_generation_spec_current_pre_advisory_v1'
      )
  loop
    definition_value := pg_get_functiondef(target.function_oid);
    if position(kind_replacement in definition_value) > 0 then
      continue;  -- уже применено
    end if;
    hits := (
      length(definition_value) - length(replace(definition_value, kind_anchor, ''))
    ) / length(kind_anchor);
    -- У версии ТЗ два места (цель и набор), у сверки актуальности — одно.
    if hits not between 1 and 2 then
      raise exception using message =
        'duet_spec_version_anchor_invalid:' || target.signature || ':' || hits::text;
    end if;
    patched_value := replace(definition_value, kind_anchor, kind_replacement);
    execute patched_value;
  end loop;
end;
$duet_spec_version_source_target$;

do $duet_spec_version_source_target_verify$
declare
  target record;
begin
  for target in
    select p.oid as function_oid,
           n.nspname || '.' || p.proname as signature
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private'
      and p.proname in (
        'create_generation_spec_version',
        'assert_generation_spec_current_pre_advisory_v1'
      )
  loop
    if position(
         '''product_photo'', ''packshot'', ''source_video'''
         in pg_get_functiondef(target.function_oid)
       ) = 0 then
      raise exception using message =
        'duet_spec_version_not_applied:' || target.signature;
    end if;
  end loop;
end;
$duet_spec_version_source_target_verify$;

-- ПРИЧИНА 5 — триггер подписи привязки исключает исходник дуэта из реестра.
-- enforce_generation_strategy_spec_authority (202608130008/202608210001) не
-- требовал записи source_video для дуэта и ОТВЕРГАЛ её, если она есть. Но
-- system_resolve_and_bind_generation_strategy_pre_execution_v1 с 23.08 кладёт
-- исходник в реестр всем трём стратегиям («у Дуэта он теперь единственный
-- ассет и цель работы»). Две стороны одного контракта разошлись: привязка
-- собирала реестр, триггер ронял её как generation_strategy_spec_authority_required.
-- Исключения снимаются: исходник дуэта сверяется с подписанным выбором так же,
-- как у «Копии» и «Создания».
do $duet_authority_source_ledger$
declare
  definition_value text;
  patched_value text;
  anchor_require constant text :=
    '       where not (' || chr(10) ||
    '         selected.value ->> ''role'' = ''source_video''' || chr(10) ||
    '         and new.strategy_id = ''viral_avatar_ugc''' || chr(10) ||
    '       )' || chr(10) ||
    '       and not exists (' || chr(10);
  replacement_require constant text :=
    '       where not exists (' || chr(10);
  anchor_ledger constant text :=
    '           and not (' || chr(10) ||
    '             selected.value ->> ''role'' = ''source_video''' || chr(10) ||
    '             and new.strategy_id = ''viral_avatar_ugc''' || chr(10) ||
    '           )' || chr(10) ||
    '       )' || chr(10);
  replacement_ledger constant text :=
    '       )' || chr(10);
  hits integer;
begin
  definition_value := pg_get_functiondef(
    'content_factory_private.enforce_generation_strategy_spec_authority()'
      ::regprocedure
  );
  if position(anchor_require in definition_value) = 0
     and position(anchor_ledger in definition_value) = 0 then
    return;  -- уже применено
  end if;
  hits := (
    length(definition_value) - length(replace(definition_value, anchor_require, ''))
  ) / length(anchor_require);
  if hits <> 1 then
    raise exception using message =
      'duet_authority_require_anchor_invalid:' || hits::text;
  end if;
  hits := (
    length(definition_value) - length(replace(definition_value, anchor_ledger, ''))
  ) / length(anchor_ledger);
  if hits <> 1 then
    raise exception using message =
      'duet_authority_ledger_anchor_invalid:' || hits::text;
  end if;
  patched_value := replace(definition_value, anchor_require, replacement_require);
  patched_value := replace(patched_value, anchor_ledger, replacement_ledger);
  execute patched_value;
end;
$duet_authority_source_ledger$;

do $duet_authority_source_ledger_verify$
begin
  if position(
       'and new.strategy_id = ''viral_avatar_ugc'''
       in pg_get_functiondef(
         'content_factory_private.enforce_generation_strategy_spec_authority()'
           ::regprocedure
       )
     ) > 0 then
    raise exception using message = 'duet_authority_source_ledger_not_applied';
  end if;
end;
$duet_authority_source_ledger_verify$;

commit;
