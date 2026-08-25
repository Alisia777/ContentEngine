begin;
-- 202608260001_input_profile_start_frame_v1
--
-- Kling O3 Standard image-to-video входит в «Создание»: модель берёт РОВНО
-- одно фото товара стартовым кадром, а в указании фото называется словами
-- «the start frame» — без @-ссылок. Словарь стилей input_profile знал только
-- none/region/at_refs/named_refs, а связка «none ⇔ 0 фото» не позволяла
-- честно описать «одно фото без ссылок». Добавляем стиль start_frame со своей
-- связкой «ровно одно фото»; остальные правила не меняются.

create or replace function content_factory_private.generation_strategy_input_profile_valid(p_profile jsonb)
 returns boolean
 language sql
 immutable
 set search_path to ''
as $function$
  -- coalesce обязателен: у пустого объекта нет ключей, array_agg даёт NULL,
  -- сравнение с NULL даёт NULL, а CHECK с NULL ПРОПУСКАЕТ строку. Без этого
  -- профиль `{"video": {}, "images": {}, …}` прошёл бы в реестр.
  select coalesce(jsonb_typeof(p_profile) = 'object'
    and (select array_agg(key order by key) from jsonb_object_keys(p_profile) key)
        = array['images', 'keeps_source_audio', 'video']
    and jsonb_typeof(p_profile -> 'keeps_source_audio') = 'boolean'
    -- Видео: окно длительности в целых секундах и пределы размера в пикселях
    -- (null — предел не объявлен провайдером).
    and jsonb_typeof(p_profile -> 'video') = 'object'
    and (select array_agg(key order by key)
         from jsonb_object_keys(p_profile -> 'video') key)
        = array['max_long_side_px', 'max_seconds', 'min_seconds',
                'min_short_side_px']
    and (p_profile -> 'video' ->> 'min_seconds') ~ '^[0-9]{1,3}$'
    and (p_profile -> 'video' ->> 'max_seconds') ~ '^[0-9]{1,3}$'
    and (p_profile -> 'video' ->> 'min_seconds')::integer between 1 and 600
    and (p_profile -> 'video' ->> 'max_seconds')::integer between 1 and 600
    and (p_profile -> 'video' ->> 'min_seconds')::integer
        <= (p_profile -> 'video' ->> 'max_seconds')::integer
    and (jsonb_typeof(p_profile -> 'video' -> 'min_short_side_px') = 'null'
         or ((p_profile -> 'video' ->> 'min_short_side_px') ~ '^[0-9]{1,5}$'
             and (p_profile -> 'video' ->> 'min_short_side_px')::integer
                 between 1 and 10000))
    and (jsonb_typeof(p_profile -> 'video' -> 'max_long_side_px') = 'null'
         or ((p_profile -> 'video' ->> 'max_long_side_px') ~ '^[0-9]{1,5}$'
             and (p_profile -> 'video' ->> 'max_long_side_px')::integer
                 between 1 and 10000))
    -- Фото товара: сколько принимает и как называет в указании.
    and jsonb_typeof(p_profile -> 'images') = 'object'
    and (select array_agg(key order by key)
         from jsonb_object_keys(p_profile -> 'images') key)
        = array['max', 'style']
    and (p_profile -> 'images' ->> 'max') ~ '^[0-9]{1,2}$'
    and (p_profile -> 'images' ->> 'max')::integer between 0 and 30
    and (p_profile -> 'images' ->> 'style')
        in ('none', 'region', 'at_refs', 'named_refs', 'start_frame')
    -- Без фото нет и ссылок; со ссылками должно быть хоть одно фото.
    and (((p_profile -> 'images' ->> 'max')::integer = 0)
         = ((p_profile -> 'images' ->> 'style') = 'none'))
    -- Стартовый кадр — ровно одно фото: модель не принимает больше.
    and ((p_profile -> 'images' ->> 'style') <> 'start_frame'
         or (p_profile -> 'images' ->> 'max')::integer = 1), false);
$function$;

commit;
