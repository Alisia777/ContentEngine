begin;

-- 202609030003_acceptance_catalog_strategy_recipes_v1
--
-- Каталог приёмки узнаёт три рецептные идентичности контура стратегий:
-- runway:product_ad («Создание» на Gen-4 Turbo, 3 платных файла),
-- runway:product_swap («Копия» premium aleph2, 10 файлов) и
-- fal:product_swap («Копия» на fal-движках, 9 файлов). Приёмка считает
-- файлы по media.metadata provider+model, а стратегийный контур пишет туда
-- РЕЦЕПТ — без этих строк платные файлы флагманских маршрутов невидимы
-- панели «Проверка качества моделей», и Алисии нечего принимать.
-- Порядок правок несущий (урок 202608290003): сначала записи справочника
-- generation_catalog_entry, потом строки каталога — строка без записи
-- роняет весь блок дрейфом. Запуск мультимодельной формой НЕ открывается:
-- отказ именуется strategy_contour_launch_only, как для fal:product_ad.

-- 1. Справочник generation_catalog_entry: три рецептные записи.
do $entry_knows_recipes$
declare
  source_text text;
  patched_text text;
  anchor_tail constant text := $at$
    else null
  end
$at$;
  patch_tail constant text := $pt$
    -- Рецептные идентичности контура стратегий: приёмка называет модель
    -- так же, как наряд и медиа (рецепт), а не исполняющий движок.
    -- Витринная pricing_version — семейство из провайдерских маршрутов;
    -- точная движковая версия живёт в квитанции каждого наряда.
    when 'runway:product_ad' then jsonb_build_object(
      'provider','runway','model','product_ad',
      'public_label','Product Ad (Runway Gen-4 Turbo)',
      'content_kind','video','lifecycle','production','enabled_by_default',true,
      'pricing_version','runway-usd-per-second-gen4-turbo-2026-08-29.v1')
    when 'runway:product_swap' then jsonb_build_object(
      'provider','runway','model','product_swap',
      'public_label','Product Swap (Runway premium)',
      'content_kind','video','lifecycle','production','enabled_by_default',true,
      'pricing_version','runway-recipe-credits-2026-08-14.v1')
    when 'fal:product_swap' then jsonb_build_object(
      'provider','fal','model','product_swap',
      'public_label','Product Swap (fal)',
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
  if position('runway:product_swap' in source_text) > 0 then
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
$entry_knows_recipes$;

-- 2. Каталог приёмки: строки двенадцать–четырнадцать.
do $catalog_rows_fourteen$
declare
  source_text text;
  patched_text text;
  anchor_row11 constant text := $ar$
    (11, 'fal'::text, 'product_ad'::text)
$ar$;
  patch_row11 constant text := $pr$
    (11, 'fal'::text, 'product_ad'::text),
    -- Рецептные идентичности стратегий: у этих строк уже есть платные
    -- файлы в проде, приёмке есть что считать.
    (12, 'runway'::text, 'product_ad'::text),
    (13, 'runway'::text, 'product_swap'::text),
    (14, 'fal'::text, 'product_swap'::text)
$pr$;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_acceptance_catalog_v49()'::regprocedure
  );
  if position($g$'product_swap'::text$g$ in source_text) > 0 then
    return;
  end if;
  -- Строки каталога без записей справочника роняют весь блок приёмки —
  -- записи обязаны уже существовать (блок 1 этой же транзакции).
  if content_factory_private.generation_catalog_entry('runway', 'product_ad')
       is null
     or content_factory_private.generation_catalog_entry(
          'runway', 'product_swap') is null
     or content_factory_private.generation_catalog_entry(
          'fal', 'product_swap') is null then
    raise exception using message = 'catalog_entry_missing_apply_block_1_first';
  end if;
  if (length(source_text) - length(replace(source_text, anchor_row11, ''))) /
     length(anchor_row11) <> 1 then
    raise exception using message = 'catalog_row11_anchor_invalid';
  end if;
  patched_text := replace(source_text, anchor_row11, patch_row11);
  if patched_text = source_text then
    raise exception using message = 'catalog_rows_12_14_patch_unchanged';
  end if;
  execute patched_text;
end;
$catalog_rows_fourteen$;

-- 3. Именованный отказ мультимодельного запуска для трёх новых
--    идентичностей (запуск НЕ открывается — контур стратегий единственный).
do $named_launch_refusals$
declare
  source_text text;
  patched_text text;
  marker_count integer;
  anchor_else constant text := $ae$
    else 'model_launch_unsupported'
$ae$;
  patch_else constant text := $pe$
    -- Рецептные идентичности запускаются контуром стратегий (creator-
    -- generate и квитанции), а не мультимодельной формой.
    when lower(btrim(coalesce(p_provider,'')))='runway'
     and lower(btrim(coalesce(p_model,'')))='product_ad'
      then 'strategy_contour_launch_only'
    when lower(btrim(coalesce(p_provider,'')))='runway'
     and lower(btrim(coalesce(p_model,'')))='product_swap'
      then 'strategy_contour_launch_only'
    when lower(btrim(coalesce(p_provider,'')))='fal'
     and lower(btrim(coalesce(p_model,'')))='product_swap'
      then 'strategy_contour_launch_only'
    else 'model_launch_unsupported'
$pe$;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.generation_provider_disabled_reason(uuid,text,text)'::regprocedure
  );
  marker_count := (
    length(source_text)
    - length(replace(source_text, 'strategy_contour_launch_only', ''))
  ) / length('strategy_contour_launch_only');
  if marker_count >= 4 then
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
$named_launch_refusals$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  row_count integer;
  drift_count integer;
  entry_value jsonb;
  identity_row record;
  reason_value text;
begin
  -- 1. Каталог: четырнадцать строк, без дрейфа справочника, новые строки
  --    на местах 12–14.
  select
    count(*)::integer,
    count(*) filter (
      where content_factory_private.generation_catalog_entry(
        catalog.provider, catalog.model
      ) is null
    )::integer
  into row_count, drift_count
  from content_factory_private.generation_acceptance_catalog_v49() catalog;
  if row_count <> 14 or drift_count <> 0 then
    raise exception using message =
      'acceptance_catalog_not_fourteen_or_drifted';
  end if;
  for identity_row in
    select * from (values
      (12, 'runway', 'product_ad'),
      (13, 'runway', 'product_swap'),
      (14, 'fal', 'product_swap')
    ) as expected(pos, provider, model)
  loop
    if not exists (
      select 1
      from content_factory_private.generation_acceptance_catalog_v49() catalog
      where catalog.catalog_position = identity_row.pos
        and catalog.provider = identity_row.provider
        and catalog.model = identity_row.model
    ) then
      raise exception using message = 'catalog_row_'
        || identity_row.pos || '_missing';
    end if;
    -- 2. Записи честные: видео с публичным именем и версией прайса.
    entry_value := content_factory_private.generation_catalog_entry(
      identity_row.provider, identity_row.model
    );
    if entry_value ->> 'content_kind' is distinct from 'video'
       or coalesce(entry_value ->> 'public_label', '') = ''
       or coalesce(entry_value ->> 'pricing_version', '') = '' then
      raise exception using message = 'recipe_catalog_entry_invalid_'
        || identity_row.provider || '_' || identity_row.model;
    end if;
    -- 3. Мультимодельный запуск закрыт, отказ именован.
    if content_factory_private.generation_provider_launch_enabled(
         '00000000-0000-0000-0000-000000000000'::uuid,
         identity_row.provider, identity_row.model
       ) then
      raise exception using message = 'recipe_launch_unexpectedly_open_'
        || identity_row.provider || '_' || identity_row.model;
    end if;
    reason_value :=
      content_factory_private.generation_provider_disabled_reason(
        '00000000-0000-0000-0000-000000000000'::uuid,
        identity_row.provider, identity_row.model
      );
    if reason_value is distinct from 'strategy_contour_launch_only' then
      raise exception using message = 'recipe_disabled_reason_unnamed_'
        || identity_row.provider || '_' || identity_row.model;
    end if;
  end loop;
end;
$verify$;

commit;
