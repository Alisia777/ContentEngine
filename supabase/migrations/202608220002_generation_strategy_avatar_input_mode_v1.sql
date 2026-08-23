begin;

-- 202608220002_generation_strategy_avatar_input_mode_v1
--
-- Последний слой перевода «Аватара» на правку видео (после 202608210004,
-- 202608210005 и 202608220001). Ярлык входа приводится к правде.
--
-- Было: input_mode = 'character_and_product_images'. Товара у стратегии нет с
-- 202608210004, значит имя называет то, чего в наборе не бывает. Ярлык не
-- декоративный — он лежит в снимке цены, который видит оператор и который
-- подписывается вместе с суммой. Неверное имя в подписанном документе хуже
-- отсутствующего: его читают как факт.
--
-- Стало: 'video_and_avatar_images' — по образцу «Копии»
-- ('video_and_product_images'), где первым назван исходник, а вторым то, чем
-- заменяют.
--
-- ПОЧЕМУ ЭТО БЕЗОПАСНО СЕЙЧАС. Ярлык входит в jsonb снимка цены и через него в
-- price_hash, поэтому переименование меняет подпись будущих квитанций. Старые
-- квитанции «Аватара» сломаться не могут: их не существует — стратегия ни разу
-- не доходила до платного пути, у неё до вчерашнего дня не было ни маршрута, ни
-- моста от формы к серверу. Проверка на это стоит ниже и остановит миграцию,
-- если в базе окажется хоть одна квитанция.
--
-- Ярлыки «Копии» и «Создания» не трогаются: их наборы входа не менялись.

do $avatar_input_mode$
declare
  avatar_receipts integer;
  target record;
  definition_value text;
  patched_value text;
  stale constant text := '''character_and_product_images''';
  fresh constant text := '''video_and_avatar_images''';
begin
  select count(*) into avatar_receipts
  from content_factory.generation_strategy_readiness_receipts
  where strategy_id = 'viral_avatar_ugc';
  if avatar_receipts <> 0 then
    raise exception using message =
      'avatar_receipts_exist_rename_unsafe:' || avatar_receipts::text;
  end if;

  for target in
    select p.oid::regprocedure::text as signature
    from pg_proc p
    where p.prokind = 'f'
      and pg_get_functiondef(p.oid) like '%character_and_product_images%'
    order by 1
  loop
    definition_value := pg_get_functiondef(target.signature::regprocedure);
    patched_value := replace(definition_value, stale, fresh);
    if patched_value = definition_value then
      raise exception using message =
        'avatar_input_mode_patch_noop:' || target.signature;
    end if;
    execute patched_value;
  end loop;
end;
$avatar_input_mode$;

do $avatar_input_mode_verify$
declare
  leftovers integer;
  price jsonb;
begin
  select count(*) into leftovers
  from pg_proc p
  where p.prokind = 'f'
    and pg_get_functiondef(p.oid) like '%character_and_product_images%';
  if leftovers <> 0 then
    raise exception using message =
      'avatar_stale_input_mode_left:' || leftovers::text;
  end if;

  -- Снимок цены «Аватара» называет свой вход правдиво.
  price := content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 8, '720p', null, true
  );
  if price->>'input_mode' <> 'video_and_avatar_images' then
    raise exception using message =
      'avatar_input_mode_not_applied:' || coalesce(price->>'input_mode', '<null>');
  end if;

  -- А «Копия» и «Создание» остались при своих: их наборы входа не менялись, и
  -- сдвинуть их этой миграцией означало бы поменять подпись работающей цены.
  price := content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 8, '720p', null, true
  );
  if price->>'input_mode' <> 'video_and_product_images' then
    raise exception using message = 'product_swap_input_mode_drifted';
  end if;
  price := content_factory_private.generation_strategy_recipe_price(
    'viral_rebuild', 8, null, '1280:720', false
  );
  if price->>'input_mode' <> 'product_images' then
    raise exception using message = 'rebuild_input_mode_drifted';
  end if;
end;
$avatar_input_mode_verify$;

commit;
