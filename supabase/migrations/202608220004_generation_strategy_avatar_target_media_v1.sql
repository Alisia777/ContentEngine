begin;

-- 202608220004_generation_strategy_avatar_target_media_v1
--
-- «Главный медиа-объект» подписанного объёма (primary_media_id и media_ids)
-- всегда собирался из товарных ролей: product_image и new_product_image. Пока у
-- «Аватара» был товар, это работало. С 202608210004 товара у него нет, и
-- массив целей остаётся пустым: primary_media_id становится NULL, а браузерное
-- зеркало требует там UUID — подготовка ТЗ падает с text_not_canonical, и
-- стратегия не доходит даже до бесплатной проверки.
--
-- РЕШЕНИЕ. У «Аватара» цель работы — лицо, а не товар. Поэтому его целевым
-- медиа становится фотография аватара. Это не подмена смысла: media_ids всегда
-- назывались тем, ПРО ЧТО делается ролик, и для «Копии» это новый товар, для
-- «Создания» — фотографии товара, а для «Аватара» — персонаж.
--
-- РЕЖИМ «ОПИСАНИЕ АВАТАРА» ОСТАЁТСЯ ЗАКОННЫМ. Фотографии может не быть вовсе
-- (роль допускает ноль), и тогда массив целей пуст, а primary_media_id — NULL.
-- Это не дыра: набор ассетов проверяется отдельно счётчиком ролей, а пустая
-- цель у стратегии, которая по контракту может обойтись описанием, — правда, а
-- не пропущенная проверка. Браузерное зеркало приводится к тому же правилу.
--
-- Товарные роли не трогаются: у «Копии» и «Создания» цель прежняя.

do $avatar_target_media$
declare
  definition_value text;
  patched_value text;
  anchor constant text :=
E'    elsif asset_role_value in (\n'
'            ''avatar_image'', ''original_product_image'', ''style_image''\n'
'          ) then\n'
'      if media_row.mime_type not in (\n'
'           ''image/jpeg'', ''image/png'', ''image/webp''\n'
'         )\n'
'         or media_row.metadata ->> ''kind'' <> ''creator_reference'' then\n'
'        raise exception using errcode = ''42501'',\n'
'          message = ''generation_strategy_spec_asset_invalid'';\n'
'      end if;\n';
  replacement constant text :=
E'    elsif asset_role_value in (\n'
'            ''avatar_image'', ''original_product_image'', ''style_image''\n'
'          ) then\n'
'      if media_row.mime_type not in (\n'
'           ''image/jpeg'', ''image/png'', ''image/webp''\n'
'         )\n'
'         or media_row.metadata ->> ''kind'' <> ''creator_reference'' then\n'
'        raise exception using errcode = ''42501'',\n'
'          message = ''generation_strategy_spec_asset_invalid'';\n'
'      end if;\n'
'      -- У «Аватара» цель работы — лицо, а не товар: фотография аватара и есть\n'
'      -- то, про что делается ролик. Для «Копии» роль avatar_image невозможна,\n'
'      -- поэтому условие по стратегии, а не по одной роли.\n'
'      if asset_role_value = ''avatar_image''\n'
'         and strategy_id_value = ''viral_avatar_ugc'' then\n'
'        target_media_ids_value := array_append(\n'
'          target_media_ids_value, media_row.id\n'
'        );\n'
'      end if;\n';
  anchor_hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );

  if position(
       'and strategy_id_value = ''viral_avatar_ugc'' then' in definition_value
     ) > 0
     and position('target_media_ids_value, media_row.id' in definition_value) > 0
     and position(replacement in definition_value) > 0 then
    return;
  end if;

  anchor_hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'avatar_target_media_anchor_invalid:' || anchor_hits::text;
  end if;

  patched_value := replace(definition_value, anchor, replacement);
  execute patched_value;
end;
$avatar_target_media$;

do $avatar_target_media_verify$
declare
  definition_value text;
begin
  definition_value := pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  );
  if position(
       'and strategy_id_value = ''viral_avatar_ugc'' then' in definition_value
     ) = 0 then
    raise exception using message = 'avatar_target_media_not_applied';
  end if;
  -- Товарные роли по-прежнему наполняют цель: правка не должна была их задеть.
  if position(
       'if asset_role_value in (''product_image'', ''new_product_image'') then'
       in definition_value
     ) = 0 then
    raise exception using message = 'product_target_roles_drifted';
  end if;
  -- И цель по-прежнему обрезается пятью элементами.
  if position('1:least(5, cardinality(target_media_ids_value))' in definition_value) = 0
  then
    raise exception using message = 'target_media_limit_drifted';
  end if;
end;
$avatar_target_media_verify$;

commit;
