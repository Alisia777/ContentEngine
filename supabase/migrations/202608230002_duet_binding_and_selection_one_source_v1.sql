begin;

-- 202608230002_duet_binding_and_selection_one_source_v1
--
-- «Дуэт»: два проверяющих текущей формы учатся видеть один исходник.
--
-- Обе функции отвечают на один вопрос — «привязка и выбор всё ещё описывают то,
-- за что заплатят». Поэтому они правятся ОДНИМ файлом: разойтись даже на один
-- деплой они не должны.
--
-- ЧТО ЛОМАЛОСЬ.
--
-- `generation_strategy_binding_current` отвергал дуэт ЧЕТЫРЬМЯ условиями общего
-- блока — того, что стоит ДО ветвления по стратегии и требует товарного ассета
-- от всех трёх стратегий сразу. У дуэта товарных ассетов нет по устройству.
--
-- `generation_strategy_selection_current` отвергал его ещё раньше: развилка
-- измерения уводила дуэт в ветку соотношения сторон, которого у него больше нет
-- (202608220014), и отказ наступал до всякой работы с ассетами.
--
-- ЧТО СДЕЛАНО И ПОЧЕМУ ЭТО НЕ ОСЛАБЛЕНИЕ.
--
-- Товарный блок не снят, а ПЕРЕВЕДЁН. Требование у него одно: то, ПРО ЧТО
-- сделан запуск, названо реестром вложений, а не только спекой. У «Копии» и
-- «Создания» это фотография товара в роли `product_primary`; у «Дуэта» —
-- сам комментируемый ролик в роли `source_video` (решение владельца,
-- 202608220015). Текст условий для двух прежних стратегий перенесён дословно.
--
-- Основание источника у дуэта СУЖАЕТСЯ с трёх значений до `exact_source_video`.
-- Это не новое требование, а запись уже истинного: `system_resolve_and_bind_…`
-- прибивает это значение гвоздём, а `exact_source_media_id` заполняется только
-- при нём. Без сужения сверка «исходник совпадает с реестром» давала бы NULL и
-- проходила бы молча — ровно та болезнь, что была в `selection_current`.

do $duet_binding_current$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_strategy_binding_current(uuid,uuid)'
      ::regprocedure
  );
  -- Признак повторного прогона: сравнение стратегии через `<>`, которого в
  -- прежней редакции быть не могло — дуэт там упоминался только через `=`.
  if position('binding_row.strategy_id <> ''viral_avatar_ugc''' in source_text) > 0
  then
    return;
  end if;
  patched_text := source_text;

  -- 1. Товарный блок разводится по стратегиям.
  anchor := E'     or primary_count <> 1\n'
         || E'     or not exists (\n'
         || E'       select 1\n'
         || E'       from content_factory.generation_spec_strategy_assets primary_asset\n'
         || E'       where primary_asset.organization_id = binding_row.organization_id\n'
         || E'         and primary_asset.binding_id = binding_row.id\n'
         || E'         and primary_asset.role = ''product_primary''\n'
         || E'         and primary_asset.media_object_id = spec_row.primary_media_id\n'
         || E'     )\n'
         || E'     or spec_product_asset_count <> cardinality(spec_row.media_ids)\n'
         || E'     or primary_count + product_reference_count not between\n'
         || E'          cardinality(spec_row.media_ids) and 10\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_binding_anchor_common_product_block';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'     or (\n'
      || E'       binding_row.strategy_id <> ''viral_avatar_ugc''\n'
      || E'       and (\n'
      || E'         primary_count <> 1\n'
      || E'         or not exists (\n'
      || E'           select 1\n'
      || E'           from content_factory.generation_spec_strategy_assets primary_asset\n'
      || E'           where primary_asset.organization_id = binding_row.organization_id\n'
      || E'             and primary_asset.binding_id = binding_row.id\n'
      || E'             and primary_asset.role = ''product_primary''\n'
      || E'             and primary_asset.media_object_id = spec_row.primary_media_id\n'
      || E'         )\n'
      || E'         or spec_product_asset_count <> cardinality(spec_row.media_ids)\n'
      || E'         or primary_count + product_reference_count not between\n'
      || E'              cardinality(spec_row.media_ids) and 10\n'
      || E'       )\n'
      || E'     )\n'
      || E'     or (\n'
      || E'       binding_row.strategy_id = ''viral_avatar_ugc''\n'
      || E'       and (\n'
      || E'         cardinality(spec_row.media_ids) <> 1\n'
      || E'         or spec_row.media_ids[1] is distinct from spec_row.primary_media_id\n'
      || E'         or not exists (\n'
      || E'           select 1\n'
      || E'           from content_factory.generation_spec_strategy_assets source_asset\n'
      || E'           where source_asset.organization_id = binding_row.organization_id\n'
      || E'             and source_asset.binding_id = binding_row.id\n'
      || E'             and source_asset.role = ''source_video''\n'
      || E'             and source_asset.media_object_id = spec_row.primary_media_id\n'
      || E'         )\n'
      || E'       )\n'
      || E'     )\n'
  );

  -- 2. Ветка дуэта: один ассет, и это исходник.
  anchor := E'    if binding_row.source_basis not in (\n'
         || E'         ''ai_research_recommendation'', ''operator_summary_only'',\n'
         || E'         ''exact_source_video''\n'
         || E'       )\n'
         || E'       or cardinality(spec_row.media_ids) <> 1\n'
         || E'       or asset_count <> 2\n'
         || E'       or primary_count + product_reference_count <> 1\n'
         || E'       or creator_count <> 1\n'
         || E'       or original_product_count <> 0\n'
         || E'       or source_video_count <> 0\n'
         || E'       or style_reference_count <> 0\n'
         || E'       or not binding_row.likeness_consent_confirmed then';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_binding_anchor_strategy_branch';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    if binding_row.source_basis <> ''exact_source_video''\n'
      || E'       or cardinality(spec_row.media_ids) <> 1\n'
      || E'       or asset_count <> 1\n'
      || E'       or primary_count + product_reference_count <> 0\n'
      || E'       or creator_count <> 0\n'
      || E'       or original_product_count <> 0\n'
      || E'       or source_video_count <> 1\n'
      || E'       or style_reference_count <> 0\n'
      || E'       or not binding_row.likeness_consent_confirmed\n'
      || E'       or not exists (\n'
      || E'         select 1\n'
      || E'         from content_factory.generation_spec_strategy_assets source_asset\n'
      || E'         where source_asset.organization_id = binding_row.organization_id\n'
      || E'           and source_asset.binding_id = binding_row.id\n'
      || E'           and source_asset.role = ''source_video''\n'
      || E'           and source_asset.media_object_id = exact_source_media_id\n'
      || E'       ) then'
  );

  if patched_text = source_text then
    raise exception using message = 'duet_binding_current_unchanged';
  end if;
  execute patched_text;
end;
$duet_binding_current$;

do $duet_selection_current$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_strategy_selection_current(uuid,uuid,jsonb)'
      ::regprocedure
  );
  if position('avatar_count = 0 and product_count = 0' in source_text) > 0 then
    return;
  end if;
  patched_text := source_text;

  -- 1. Измерение разрешением: к «Копии» присоединяется «Дуэт». То же решение,
  --    что 202608220014 записал в проверяющий выбора.
  anchor := E'  if binding_row.strategy_id = ''viral_product_swap'' then';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_selection_anchor_frame_branch';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  if binding_row.strategy_id in (''viral_product_swap'', ''viral_avatar_ugc'') then'
  );

  -- 2. Посекундная сверка длительности включается и у дуэта — но по ДРУГОЙ
  --    причине, и это надо сказать вслух. «Копия» связывает измеренную
  --    длительность потому, что отдаёт MP4 провайдеру. «Дуэт» — потому что
  --    ведущий стоит $0.05 за секунду, и секунды берутся из комментируемого
  --    ролика. Одна проверка на два разных основания это нормально, но
  --    основание должно быть записано: иначе следующий читатель снимет её
  --    вместе с одним из них.
  anchor := E'    if asset_value ->> ''role'' = ''source_video''\n'
         || E'       and binding_row.strategy_id = ''viral_product_swap'' then\n'
         || E'      -- Only Product Swap forwards the source MP4 to Runway and therefore\n'
         || E'      -- binds its measured duration.  UGC/Product Ad treat the exact source\n'
         || E'      -- solely as rights-confirmed mechanics provenance; the public catalog\n'
         || E'      -- permits an optional informational duration but it is never authority.\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_selection_anchor_duration_branch';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    if asset_value ->> ''role'' = ''source_video''\n'
      || E'       and binding_row.strategy_id in (\n'
      || E'         ''viral_product_swap'', ''viral_avatar_ugc''\n'
      || E'       ) then\n'
      || E'      -- Измеренная длительность связывается у двух стратегий, но по\n'
      || E'      -- РАЗНЫМ основаниям. «Копия» отдаёт MP4 провайдеру, и он обязан\n'
      || E'      -- получить ровно тот ролик, за который заплачено. «Дуэт»\n'
      || E'      -- провайдеру исходник не отдаёт вовсе — но ведущий считается\n'
      || E'      -- ПОСЕКУНДНО, и секунды берутся отсюда. «Создание» собирает\n'
      || E'      -- ролик с нуля и длительность из исходника не наследует.\n'
  );

  -- 3. Исходник дуэта больше не обходит реестр вложений.
  --
  --    Прежняя редакция сверяла его ТОЛЬКО со снимком источника. При основании,
  --    отличном от exact_source_video, ключа media_object_id в снимке нет вовсе:
  --    сравнение давало NULL, а NULL здесь неотличим от «проверка прошла».
  --    Теперь сверок две, обе NULL-безопасные, и реестр обязан содержать ассет.
  anchor := E'    if asset_value ->> ''role'' = ''source_video''\n'
         || E'       and binding_row.strategy_id = ''viral_avatar_ugc'' then\n'
         || E'      if binding_row.source_snapshot ->> ''media_object_id'' <>\n'
         || E'           asset_id::text then\n'
         || E'        return false;\n'
         || E'      end if;\n'
         || E'    else\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_selection_anchor_ledger_bypass';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    if asset_value ->> ''role'' = ''source_video''\n'
      || E'       and binding_row.strategy_id = ''viral_avatar_ugc''\n'
      || E'       and binding_row.source_snapshot ->> ''media_object_id''\n'
      || E'             is distinct from asset_id::text then\n'
      || E'      return false;\n'
      || E'    end if;\n'
  );

  -- 3b. Закрывающая скобка прежнего ветвления снимается тем же файлом.
  --     Иначе блок остался бы несбалансированным, а «структурный остаток» вида
  --     `if true then` был бы заплаткой, смысл которой следующий читатель уже
  --     не восстановит.
  anchor := E'      if ledger_match_count <> 1 then\n'
         || E'        return false;\n'
         || E'      end if;\n'
         || E'    end if;\n'
         || E'  end loop;';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_selection_anchor_ledger_tail';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'      if ledger_match_count <> 1 then\n'
      || E'        return false;\n'
      || E'      end if;\n'
      || E'  end loop;'
  );

  -- 4. Итоговый счёт: один исходник, и он же в реестре.
  anchor := E'    return source_count = 1 and avatar_count = 1 and product_count = 1\n'
         || E'      and original_count = 0 and style_count = 0\n'
         || E'      and cardinality(seen_ids) = expected_ledger_count + 1;';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_selection_anchor_final_counts';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    -- Прежняя «+1» была поправкой на исходник, которого в реестре не\n'
      || E'    -- было. Теперь он там есть, и поправлять больше нечего.\n'
      || E'    return source_count = 1 and avatar_count = 0 and product_count = 0\n'
      || E'      and original_count = 0 and style_count = 0\n'
      || E'      and cardinality(seen_ids) = expected_ledger_count;'
  );

  if patched_text = source_text then
    raise exception using message = 'duet_selection_current_unchanged';
  end if;
  execute patched_text;
end;
$duet_selection_current$;

-- ПРОВЕРКА.
--
-- Обе функции читают строки, и без фикстуры до их существа не добраться. Но
-- часть свойств проверяется поведением честно: на несуществующей привязке
-- функция обязана ответить `false`, а не упасть. Остальное — структурным
-- блоком с прямым признанием, почему так.
do $duet_binding_selection_verify$
declare
  binding_body text;
  selection_body text;
begin
  if content_factory_private.generation_strategy_binding_current(
       '11111111-1111-4111-8111-111111111111'::uuid,
       '22222222-2222-4222-8222-222222222222'::uuid
     ) is not false then
    raise exception using message = 'binding_current_missing_row_not_false';
  end if;

  binding_body := pg_get_functiondef(
    'content_factory_private.generation_strategy_binding_current(uuid,uuid)'
      ::regprocedure
  );
  selection_body := pg_get_functiondef(
    'content_factory_private.generation_strategy_selection_current(uuid,uuid,jsonb)'
      ::regprocedure
  );

  -- Дуэт: один ассет, и это исходник.
  if position('or asset_count <> 1' in binding_body) = 0
     or position('or source_video_count <> 1' in binding_body) = 0
     or position('or creator_count <> 0' in binding_body) = 0 then
    raise exception using message = 'duet_binding_counts_missing';
  end if;

  -- «Копия» не потеряла требования товарного ассета: текст условия перенесён
  -- дословно и обязан присутствовать.
  if position('primary_asset.role = ''product_primary''' in binding_body) = 0
     or position('or spec_product_asset_count <> cardinality(spec_row.media_ids)'
                 in binding_body) = 0 then
    raise exception using message = 'product_swap_primary_requirement_lost';
  end if;

  -- Основание источника у дуэта сужено до точного вложения.
  if position('binding_row.source_basis <> ''exact_source_video''' in binding_body) = 0
  then
    raise exception using message = 'duet_source_basis_not_narrowed';
  end if;

  -- Выбор: измерение разрешением у обеих правок видео.
  if position('binding_row.strategy_id in (''viral_product_swap'', ''viral_avatar_ugc'')'
              in selection_body) = 0 then
    raise exception using message = 'duet_selection_frame_branch_missing';
  end if;

  -- Итоговый счёт без поправки на отсутствующий исходник.
  if position('cardinality(seen_ids) = expected_ledger_count + 1' in selection_body) > 0
  then
    raise exception using message = 'duet_selection_still_compensates_source';
  end if;

  -- «Создание» не тронуто: его ветка счётчиков на месте.
  if position('return source_count = 1 and avatar_count = 0 and original_count = 0'
              in selection_body) = 0 then
    raise exception using message = 'viral_rebuild_selection_branch_lost';
  end if;
end;
$duet_binding_selection_verify$;

commit;
