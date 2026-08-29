begin;

-- 202608290003_acceptance_catalog_knows_fal_v1
--
-- Каталог приёмки PRODUCTION QUALITY знает fal/product_ad («Создание»).
-- Счётчик блока считает по generation_acceptance_catalog_v49 (до этой
-- миграции — 10 моделей: runway ×9 и google veo-3.1-lite), и fal-ролики
-- «Создания» в приёмку не попадали вовсе. Порядок правок внутри файла
-- несущий: строка каталога БЕЗ записи в generation_catalog_entry убила бы
-- весь блок — проекция generation_model_acceptance_catalog_v49 на пустую
-- запись отвечает generation_model_acceptance_catalog_drift. Поэтому
-- сначала запись справочника, потом строка каталога.
--
-- ЧТО МЕНЯЕТСЯ.
-- 1. generation_catalog_entry: запись 'fal:product_ad' (public_label,
--    content_kind='video'). Идентичность приёмки — рецепт product_ad (так
--    наряд и медиа называют модель), а не пять исполняющих движков fal.
--    Витринная pricing_version — семейство посекундного счёта fal; в
--    квитанции каждого наряда живёт своя движковая версия
--    fal-usd-per-second-<движок>-2026-08-23.v1.
-- 2. generation_acceptance_catalog_v49: одиннадцатая строка
--    (11, 'fal', 'product_ad'). Считалка exact-outputs провайдеро-generic
--    (media.metadata.provider/model = провайдер/модель наряда, оплата
--    точная) — для fal ей достаточно членства в каталоге.
-- 3. generation_model_acceptance_catalog_v49: 'fal' в массиве providers.
-- 4. generation_provider_disabled_reason: именованный отказ
--    strategy_contour_launch_only для fal/product_ad — «Создание»
--    запускается контуром стратегий (creator-generate + квитанции), а не
--    мультимодельной формой; запуск этой миграцией НЕ открывается
--    (generation_provider_launch_enabled не трогаем).
--
-- ПИНЫ ТЕСТОВ. pgtap supabase/tests/generation_multimodel_acceptance_v4_
-- test.sql пинит «ровно десять» дважды: список каталога (строки ~29–50) и
-- jsonb_array_length(models)=10 (строки ~570–575). После этой миграции обе
-- проверки надо расширить одиннадцатой строкой — иначе SQL-стадия dev-test
-- красная. pytest-двойник читает текст СТАРОГО файла 202608130004 и этой
-- миграцией не задевается; web-счётчики выводят длину массива и знаменатель
-- не пинят.
--
-- Порядок с 202608290002 (review знает fal) свободный: миграции независимы.

-- 1. Справочник generation_catalog_entry: запись fal:product_ad.
do $entry_knows_fal$
declare
  source_text text;
  patched_text text;
  anchor_tail constant text := $at$
    else null
  end
$at$;
  patch_tail constant text := $pt$
    -- «Создание» (fal, рецепт product_ad): один пункт приёмки на рецепт.
    -- Деньги считаются посекундно за выбранный движок — движковая версия
    -- прайса живёт в квитанции наряда; здесь витринная подпись семейства.
    when 'fal:product_ad' then jsonb_build_object(
      'provider','fal','model','product_ad','public_label','Product Ad (fal)',
      'content_kind','video','lifecycle','production','enabled_by_default',true,
      'pricing_version','fal-usd-per-second-2026-08-18.v1')
    else null
  end
$pt$;
begin
  perform pg_advisory_xact_lock(hashtext('generation_acceptance_catalog'));
  source_text := pg_get_functiondef(
    'content_factory_private.generation_catalog_entry(text,text)'::regprocedure
  );
  if position('fal:product_ad' in source_text) > 0 then
    -- Повторный прогон обязан быть тихим.
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor_tail, ''))) /
     length(anchor_tail) <> 1 then
    raise exception using message = 'catalog_entry_tail_anchor_invalid';
  end if;
  patched_text := replace(source_text, anchor_tail, patch_tail);
  if patched_text = source_text then
    raise exception using message = 'catalog_entry_patch_unchanged';
  end if;
  execute patched_text;
end;
$entry_knows_fal$;

-- 2. Каталог приёмки: одиннадцатая строка.
do $catalog_row_eleven$
declare
  source_text text;
  patched_text text;
  anchor_row10 constant text := $ar$
    (10, 'google'::text, 'veo-3.1-lite-generate-preview'::text)
$ar$;
  patch_row10 constant text := $pr$
    (10, 'google'::text, 'veo-3.1-lite-generate-preview'::text),
    -- Одиннадцатая строка: «Создание» на fal. Идентичность приёмки — рецепт
    -- product_ad (так наряд и медиа называют модель), а не пять движков.
    (11, 'fal'::text, 'product_ad'::text)
$pr$;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_acceptance_catalog_v49()'::regprocedure
  );
  if position($g$'fal'::text$g$ in source_text) > 0 then
    return;
  end if;
  -- Строка каталога без записи справочника роняет весь блок приёмки —
  -- запись обязана уже существовать (блок 1 этой же транзакции).
  if content_factory_private.generation_catalog_entry('fal', 'product_ad')
       is null then
    raise exception using message = 'catalog_entry_missing_apply_block_1_first';
  end if;
  if (length(source_text) - length(replace(source_text, anchor_row10, ''))) /
     length(anchor_row10) <> 1 then
    raise exception using message = 'catalog_row10_anchor_invalid';
  end if;
  patched_text := replace(source_text, anchor_row10, patch_row10);
  if patched_text = source_text then
    raise exception using message = 'catalog_row11_patch_unchanged';
  end if;
  execute patched_text;
end;
$catalog_row_eleven$;

-- 3. Массив providers в проекции приёмки.
do $providers_know_fal$
declare
  source_text text;
  patched_text text;
  anchor_providers constant text := $av$
    'providers', jsonb_build_array('runway', 'google'),
$av$;
  patch_providers constant text := $pv$
    'providers', jsonb_build_array('runway', 'google', 'fal'),
$pv$;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_model_acceptance_catalog_v49(uuid,timestamptz,jsonb)'::regprocedure
  );
  if position($g$'runway', 'google', 'fal'$g$ in source_text) > 0 then
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor_providers, '')))
     / length(anchor_providers) <> 1 then
    raise exception using message = 'providers_anchor_invalid';
  end if;
  patched_text := replace(source_text, anchor_providers, patch_providers);
  if patched_text = source_text then
    raise exception using message = 'providers_patch_unchanged';
  end if;
  execute patched_text;
end;
$providers_know_fal$;

-- 4. Именованный отказ мультимодельного запуска (запуск НЕ открывается).
do $named_launch_refusal$
declare
  source_text text;
  patched_text text;
  anchor_else constant text := $ae$
    else 'model_launch_unsupported'
$ae$;
  patch_else constant text := $pe$
    -- «Создание» запускается контуром стратегий (creator-generate и
    -- квитанции), а не мультимодельной формой: отказ называет причину,
    -- generation_provider_launch_enabled не расширяется.
    when lower(btrim(coalesce(p_provider,'')))='fal'
     and lower(btrim(coalesce(p_model,'')))='product_ad'
      then 'strategy_contour_launch_only'
    else 'model_launch_unsupported'
$pe$;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_provider_disabled_reason(uuid,text,text)'::regprocedure
  );
  if position('strategy_contour_launch_only' in source_text) > 0 then
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor_else, ''))) /
     length(anchor_else) <> 1 then
    raise exception using message = 'disabled_reason_else_anchor_invalid';
  end if;
  patched_text := replace(source_text, anchor_else, patch_else);
  if patched_text = source_text then
    raise exception using message = 'disabled_reason_patch_unchanged';
  end if;
  execute patched_text;
end;
$named_launch_refusal$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  row_count integer;
  drift_count integer;
  entry_value jsonb;
  reason_value text;
begin
  -- 1. Каталог: одиннадцать строк, все без дрейфа справочника; одиннадцатая
  --    — ровно fal/product_ad.
  select
    count(*)::integer,
    count(*) filter (
      where content_factory_private.generation_catalog_entry(
        catalog.provider, catalog.model
      ) is null
    )::integer
  into row_count, drift_count
  from content_factory_private.generation_acceptance_catalog_v49() catalog;
  if row_count <> 11 or drift_count <> 0 then
    raise exception using message = 'acceptance_catalog_not_eleven_or_drifted';
  end if;
  if not exists (
    select 1
    from content_factory_private.generation_acceptance_catalog_v49() catalog
    where catalog.catalog_position = 11
      and catalog.provider = 'fal'
      and catalog.model = 'product_ad'
  ) then
    raise exception using message = 'catalog_row_11_missing';
  end if;

  -- 2. Запись справочника честная: видео с публичным именем.
  entry_value := content_factory_private.generation_catalog_entry(
    'fal', 'product_ad'
  );
  if entry_value ->> 'content_kind' is distinct from 'video'
     or coalesce(entry_value ->> 'public_label', '') = ''
     or coalesce(entry_value ->> 'pricing_version', '') = '' then
    raise exception using message = 'fal_catalog_entry_invalid';
  end if;

  -- 3. Мультимодельный запуск по-прежнему закрыт, но отказ именован.
  if content_factory_private.generation_provider_launch_enabled(
       '00000000-0000-0000-0000-000000000000'::uuid, 'fal', 'product_ad'
     ) then
    raise exception using message = 'fal_product_ad_launch_unexpectedly_open';
  end if;
  reason_value := content_factory_private.generation_provider_disabled_reason(
    '00000000-0000-0000-0000-000000000000'::uuid, 'fal', 'product_ad'
  );
  if reason_value is distinct from 'strategy_contour_launch_only' then
    raise exception using message = 'fal_disabled_reason_unnamed';
  end if;

  -- 4. Проекция объявляет трёх провайдеров.
  if position(
       $g$'runway', 'google', 'fal'$g$ in pg_get_functiondef(
         'content_factory_private.generation_model_acceptance_catalog_v49(uuid,timestamptz,jsonb)'::regprocedure
       )
     ) = 0 then
    raise exception using message = 'providers_array_missing_fal';
  end if;
end;
$verify$;

commit;
