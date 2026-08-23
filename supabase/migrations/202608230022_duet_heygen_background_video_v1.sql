begin;

-- 202608230022_duet_heygen_background_video_v1
--
-- «Дуэт»: сборку делает провайдер, маршрут включается.
--
-- ЧТО НАБЛЮДАЛОСЬ. Путь «Дуэта» был построен послойно и ни разу не соединён:
--   1. сборка «ведущий в углу поверх ролика» отдана локальному ffmpeg
--      (app/services/duet_composition.py), которого негде запустить — edge
--      ffmpeg не умеет, сервера приложения в проде нет; результат HeyGen
--      (WebM) потоковый приём отвергает по типу, наряд повисал бы с резервом;
--   2. рубильник generation_provider_launch_enabled не знал heygen:avatar_v3 —
--      политика отвечала provider_configuration_disabled на любой preflight;
--   3. строка маршрута выключена и не рекомендована: замок 202608230010 не
--      пускал к деньгам, а цена без явного движка была null;
--   4. у ведущего не было вида личности у провайдера — фото-аватар и
--      видеоаватар в v2 описываются разными полями.
--
-- РЕШЕНИЕ 23.08.2026. Соединение с роликом отдано самому провайдеру: v2
-- `POST /v2/video/generate` принимает фоновое ВИДЕО (наша подписанная ссылка
-- на исходник) и ставит ведущего поверх него кружком или вырезом в указанном
-- углу. Результат — готовый MP4 1080×1920, который принимает тот же потоковый
-- приём, что и у «Копии». Срок годности: v1/v2 HeyGen живут до 31.10.2026,
-- дальше — HyperFrames (/v3/hyperframes/renders), где та же раскладка
-- описывается HTML-композицией; модуль ffmpeg остаётся эталоном раскладки.
-- Цена не меняется: $0.05/с за готовое видео ведущего — посекундная ставка
-- реестра, длительность задаёт исходник.

-- 1. Вид личности у провайдера.
alter table content_factory.generation_duet_presenters
  add column if not exists provider_avatar_kind text not null
    default 'talking_photo';
alter table content_factory.generation_duet_presenters
  drop constraint if exists generation_duet_presenters_avatar_kind_check;
alter table content_factory.generation_duet_presenters
  add constraint generation_duet_presenters_avatar_kind_check
  check (provider_avatar_kind in ('talking_photo', 'avatar'));

-- Личность для отправки несёт и вид: адаптер по нему выбирает поле
-- talking_photo_id / avatar_id и стиль кружка.
create or replace function content_factory_private.duet_presenter_identity(
  p_organization_id uuid,
  p_project_id uuid,
  p_presenter_id uuid
)
returns jsonb
language sql
stable
security definer
set search_path to ''
as $$
  select jsonb_build_object(
    'avatarId', presenter.provider_avatar_id,
    'voiceId', presenter.provider_voice_id,
    'aspectRatio', presenter.aspect_ratio,
    'avatarKind', presenter.provider_avatar_kind,
    'layout', jsonb_build_object(
      'corner', presenter.overlay_corner,
      'shape', presenter.overlay_shape,
      'widthPercent', presenter.overlay_width_percent
    )
  )
  from content_factory.generation_duet_presenters presenter
  where presenter.id = p_presenter_id
    and presenter.organization_id = p_organization_id
    and presenter.project_id = p_project_id
    and presenter.status = 'active'
    and (
      presenter.likeness_kind <> 'real_person'
      or presenter.likeness_consent_confirmed
    );
$$;

-- Регистрация ведущего принимает вид личности (по умолчанию — фото-аватар).
do $register_avatar_kind$
declare
  definition_value text;
  patched_value text;
  anchor_keys constant text :=
    $f$'provider_avatar_id', 'provider_voice_id', 'aspect_ratio', 'is_default',
       'likeness_kind', 'likeness_consent_confirmed'$f$;
  anchor_declare constant text :=
    $f$  likeness_kind_value text := 'synthetic';$f$;
  anchor_read constant text :=
    $f$  if p_payload ? 'likeness_kind' then$f$;
  anchor_insert_cols constant text :=
    $f$    provider_avatar_id, provider_voice_id, aspect_ratio, is_default, created_by,$f$;
  anchor_insert_vals constant text :=
    $f$    avatar_id_value, voice_id_value, aspect_ratio_value, make_default, user_id,$f$;
begin
  definition_value := pg_get_functiondef(
    'public.creator_register_duet_presenter(jsonb)'::regprocedure
  );
  if position('provider_avatar_kind' in definition_value) > 0 then
    return;
  end if;
  patched_value := definition_value;
  if (length(patched_value) - length(replace(patched_value, anchor_keys, '')))
     / length(anchor_keys) <> 1 then
    raise exception using message = 'register_anchor_keys';
  end if;
  patched_value := replace(
    patched_value,
    anchor_keys,
    anchor_keys || $r$,
       'provider_avatar_kind'$r$
  );
  if (length(patched_value) - length(replace(patched_value, anchor_declare, '')))
     / length(anchor_declare) <> 1 then
    raise exception using message = 'register_anchor_declare';
  end if;
  patched_value := replace(
    patched_value,
    anchor_declare,
    anchor_declare || $r$
  avatar_kind_value text := 'talking_photo';$r$
  );
  if (length(patched_value) - length(replace(patched_value, anchor_read, '')))
     / length(anchor_read) <> 1 then
    raise exception using message = 'register_anchor_read';
  end if;
  patched_value := replace(
    patched_value,
    anchor_read,
    $r$  if p_payload ? 'provider_avatar_kind' then
    avatar_kind_value := btrim(coalesce(p_payload ->> 'provider_avatar_kind', ''));
    if avatar_kind_value not in ('talking_photo', 'avatar') then
      raise exception using
        errcode = '22023', message = 'duet_presenter_payload_invalid';
    end if;
  end if;
$r$ || anchor_read
  );
  if (length(patched_value) - length(replace(patched_value, anchor_insert_cols, '')))
     / length(anchor_insert_cols) <> 1 then
    raise exception using message = 'register_anchor_insert_cols';
  end if;
  patched_value := replace(
    patched_value,
    anchor_insert_cols,
    anchor_insert_cols || $r$
    provider_avatar_kind,$r$
  );
  if (length(patched_value) - length(replace(patched_value, anchor_insert_vals, '')))
     / length(anchor_insert_vals) <> 1 then
    raise exception using message = 'register_anchor_insert_vals';
  end if;
  patched_value := replace(
    patched_value,
    anchor_insert_vals,
    anchor_insert_vals || $r$
    avatar_kind_value,$r$
  );
  execute patched_value;
end;
$register_avatar_kind$;

-- 2. Маршрут: настоящий адрес v2, включён и рекомендован. Ставка сверена
--    22.08.2026 ($0.05/с), verified_rate_at уже стоит.
update content_factory.generation_strategy_provider_routes as route
set provider_path = '/v2/video/generate',
    enabled = true,
    recommended = true,
    engine_family = 'overlay',
    notes = coalesce(route.notes, '')
      || ' 23.08.2026: сборка у провайдера — v2 POST /v2/video/generate с фоновым видео (исходник) и ведущим кружком/вырезом в углу; результат MP4. v1/v2 живут до 31.10.2026, дальше HyperFrames.',
    updated_at = now()
where route.strategy_id = 'viral_avatar_ugc'
  and route.provider = 'heygen'
  and route.model_key = 'avatar_v3';

-- 3. Список исполнимых пар: адрес «Дуэта» — v2. Остальные пары без изменений
--    (повторяют 202608230021).
create or replace function
  content_factory_private.generation_strategy_provider_route_allowed(
    p_strategy_id text,
    p_provider text,
    p_model_key text,
    p_provider_path text,
    p_poll_kind text,
    p_pricing_version text
  )
returns boolean
language sql
immutable
set search_path to ''
as $$
  select coalesce(case
    when p_strategy_id = 'viral_avatar_ugc'
     and p_provider = 'heygen'
     and p_model_key = 'avatar_v3'
      then p_provider_path = '/v2/video/generate'
       and p_poll_kind = 'heygen_video'
       and p_pricing_version = 'heygen-usd-per-second-2026-08-22.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'runway'
     and p_model_key = 'aleph2'
      then p_provider_path = '/v1/video_to_video'
       and p_poll_kind = 'runway_task'
       and p_pricing_version = 'runway-recipe-credits-2026-08-14.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key = 'fal-ai/pika/v2/pikaswaps'
      then p_provider_path = 'fal-ai/pika/v2/pikaswaps'
       and p_poll_kind = 'fal_request'
       and p_pricing_version = 'fal-usd-per-run-2026-08-18.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key =
       'fal-ai/kling-video/o3/pro/video-to-video/edit'
      then p_provider_path =
        'fal-ai/kling-video/o3/pro/video-to-video/edit'
       and p_poll_kind = 'fal_request'
       and p_pricing_version = 'fal-usd-per-second-2026-08-18.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key =
       'fal-ai/kling-video/o3/standard/video-to-video/edit'
      then p_provider_path =
        'fal-ai/kling-video/o3/standard/video-to-video/edit'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-kling-standard-2026-08-23.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key = 'alibaba/happy-horse/video-edit'
      then p_provider_path = 'alibaba/happy-horse/video-edit'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-happy-horse-2026-08-23.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key = 'bytedance/seedance-2.5/reference-to-video'
      then p_provider_path = 'bytedance/seedance-2.5/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-bytedance-2-5-2026-08-23.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key = 'minimax/h3/reference-to-video'
      then p_provider_path = 'minimax/h3/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-minimax-h3-2026-08-23.v1'
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'fal'
     and p_model_key = 'minimax/h3/reference-to-video'
      then p_provider_path = 'minimax/h3/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-minimax-h3-2026-08-23.v1'
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'fal'
     and p_model_key = 'xai/grok-imagine-video/reference-to-video'
      then p_provider_path = 'xai/grok-imagine-video/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-grok-imagine-2026-08-23.v1'
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'fal'
     and p_model_key = 'alibaba/happy-horse/reference-to-video'
      then p_provider_path = 'alibaba/happy-horse/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-happy-horse-reference-2026-08-23.v1'
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'fal'
     and p_model_key = 'bytedance/seedance-2.5/reference-to-video'
      then p_provider_path = 'bytedance/seedance-2.5/reference-to-video'
       and p_poll_kind = 'fal_request'
       and p_pricing_version =
         'fal-usd-per-second-bytedance-2-5-2026-08-23.v1'
    else false
  end, false);
$$;

-- 4. Рубильник запуска знает heygen:avatar_v3.
do $launch_gate_heygen$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text :=
    $f$when 'fal:minimax/h3/reference-to-video' then true$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  if definition_value is null then
    raise exception using message = 'launch_gate_missing';
  end if;
  if position('heygen:avatar_v3' in definition_value) > 0 then
    return;
  end if;
  anchor_hits := (
    length(definition_value)
    - length(replace(definition_value, anchor_text, ''))
  ) / length(anchor_text);
  if anchor_hits <> 1 then
    raise exception using
      message = 'launch_gate_anchor_not_unique:' || anchor_hits::text;
  end if;
  patched_value := replace(
    definition_value,
    anchor_text,
    anchor_text || $r$
    when 'heygen:avatar_v3' then true$r$
  );
  if position('heygen:avatar_v3' in patched_value) = 0 then
    raise exception using message = 'launch_gate_patch_failed';
  end if;
  execute patched_value;
end;
$launch_gate_heygen$;

-- 5. Проверка.
do $duet_v2_verify$
declare
  route_row content_factory.generation_strategy_provider_routes%rowtype;
  gate_ok boolean;
begin
  select * into route_row
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_avatar_ugc' and provider = 'heygen';
  if route_row.id is null or not route_row.enabled or not route_row.recommended
     or route_row.provider_path <> '/v2/video/generate' then
    raise exception using message = 'duet_route_not_live';
  end if;
  if not content_factory_private.generation_strategy_provider_route_allowed(
    route_row.strategy_id, route_row.provider, route_row.model_key,
    route_row.provider_path, route_row.poll_kind, route_row.pricing_version
  ) then
    raise exception using message = 'duet_route_not_allowed';
  end if;
  if not content_factory_private.generation_strategy_executable_route_exists(
    'viral_avatar_ugc'
  ) then
    raise exception using message = 'duet_route_still_locked';
  end if;
  select pg_get_functiondef(p.oid) like '%heygen:avatar_v3%' into gate_ok
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  if not coalesce(gate_ok, false) then
    raise exception using message = 'duet_launch_gate_missing';
  end if;
  if position('provider_avatar_kind' in pg_get_functiondef(
       'public.creator_register_duet_presenter(jsonb)'::regprocedure
     )) = 0 then
    raise exception using message = 'duet_register_kind_missing';
  end if;
  -- Цена действующего маршрута: 10 секунд = 50 центов.
  if (content_factory_private.generation_strategy_recipe_price(
        'viral_avatar_ugc', 10, '720p', 'source', false
      ) ->> 'estimated_cost_minor') <> '50' then
    raise exception using message = 'duet_price_invalid';
  end if;
end;
$duet_v2_verify$;

commit;
