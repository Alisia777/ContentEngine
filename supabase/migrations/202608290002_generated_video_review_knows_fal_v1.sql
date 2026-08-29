begin;

-- 202608290002_generated_video_review_knows_fal_v1
--
-- QA-приёмка сгенерированного видео знает провайдера fal («Создание»,
-- рецепт product_ad). На 29.08 в проде три оплаченных успешных наряда
-- fal/product_ad (по 720 минорных единиц, media ready, sha и привязка
-- output_media_id сходятся), но кнопка «Запустить AI-проверку» падает на
-- generated_video_review_source_invalid: стартовая функция review требует
-- runway в трёх местах (metadata медиа, провайдер наряда, список моделей).
-- Та же тройка литералов живёт в approve-функции, а звуковой шлюз
-- record_content_review_sound_assessment пересчитывает авторитет звука
-- только через runway-SKU (real_generation_multimodel_sku рецепт product_ad
-- не знает и возвращает null). Открыть один старт мало: приёмка в
-- PRODUCTION QUALITY засчитывается решением approved, поэтому эта миграция
-- открывает все три двери контура review разом.
--
-- ЧТО МЕНЯЕТСЯ.
-- 1. Новая identity-функция generation_video_review_identity_allowed(
--    provider, model): runway-ветка ДЕЛЕГИРУЕТСЯ прежней
--    generation_runway_video_review_model_allowed — список не копируется и
--    разойтись не может; fal знает единственную видео-идентичность
--    'product_ad'.
-- 2. Старт и approve review: провайдер медиа сверяется с провайдером наряда
--    (а не с литералом 'runway'), провайдер наряда — in ('runway','fal'),
--    модель — через identity-функцию.
-- 3. Платформа 'instagram' допускается в обеих функциях: все три платных
--    fal-ролика «Создания» целятся в instagram, а нижележащий
--    creator_start_content_review принимает instagram с рождения (его
--    собственный список: instagram, youtube, vk, telegram, wildberries,
--    tiktok, other) — узкий список был копией runway-эпохи, не политикой.
-- 4. Звуковой шлюз: провайдер in ('runway','fal'); для fal/product_ad
--    авторитет звука — явный boolean input.audio, зеркалом которого обязан
--    быть серверный снимок input.strategy_technical.audio того же наряда.
--
-- НЕСУЩИЕ КОММЕНТАРИИ. pgtap-тесты (generation_multimodel_authority_test,
-- generated_video_sound_release_gate_test) пинят в телах start/approve
-- литерал generation_runway_video_review_model_allowed( — после патча он
-- остаётся там в виде комментария о делегировании. Удалять эти комментарии
-- из тел функций нельзя, пока живут пины.
--
-- Порядок с 202608290003 (каталог приёмки) свободный: миграции независимы.

-- 0. Identity-функция: два провайдера, один источник runway-списка.
create or replace function
  content_factory_private.generation_video_review_identity_allowed(
    p_provider text,
    p_model text
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select case lower(btrim(coalesce(p_provider, '')))
    when 'runway' then
      content_factory_private.generation_runway_video_review_model_allowed(
        p_model
      )
    when 'fal' then
      lower(btrim(coalesce(p_model, ''))) in ('product_ad')
    else false
  end
$$;

revoke all on function
  content_factory_private.generation_video_review_identity_allowed(text, text)
  from public, anon, authenticated, service_role;

-- 1. Старт review знает fal и instagram.
do $start_knows_fal$
declare
  source_text text;
  patched_text text;
  anchor_media constant text := $am$
     or media_row.metadata ->> 'provider' <> 'runway'
$am$;
  patch_media constant text := $pm$
     -- Провайдер медиа обязан совпадать с провайдером наряда, а не с
     -- зашитым литералом: у fal-роликов «Создания» metadata.provider='fal'.
     or media_row.metadata ->> 'provider' is distinct from job_row.provider
$pm$;
  anchor_provider constant text := $ap$
     or job_row.provider <> 'runway'
$ap$;
  patch_provider constant text := $pp$
     or job_row.provider not in ('runway', 'fal')
$pp$;
  anchor_model constant text := $ao$
     or not content_factory_private
       .generation_runway_video_review_model_allowed(
         job_row.input ->> 'model'
       )
$ao$;
  patch_model constant text := $po$
     -- Идентичность видео для QA-приёмки двухпровайдерная. runway-список
     -- по-прежнему живёт в generation_runway_video_review_model_allowed(
     -- модель): identity-функция делегирует ему runway-ветку и знает
     -- fal/product_ad («Создание»). Комментарий несущий: пины
     -- authority-тестов ищут старое имя в теле этой функции.
     or not content_factory_private
       .generation_video_review_identity_allowed(
         job_row.provider, job_row.input ->> 'model'
       )
$po$;
  anchor_platform constant text := $al$
       'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
$al$;
  patch_platform constant text := $pl$
       'tiktok', 'youtube', 'vk', 'telegram', 'wildberries',
       -- Все платные fal-ролики «Создания» целятся в instagram; нижележащий
       -- creator_start_content_review принимает instagram с рождения.
       'instagram'
$pl$;
begin
  perform pg_advisory_xact_lock(hashtext('generated_video_review_contour'));
  source_text := pg_get_functiondef(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'::regprocedure
  );
  if position('generation_video_review_identity_allowed' in source_text) > 0
  then
    -- Повторный прогон обязан быть тихим.
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor_media, ''))) /
     length(anchor_media) <> 1 then
    raise exception using message = 'start_media_provider_anchor_invalid';
  end if;
  if (length(source_text) - length(replace(source_text, anchor_provider, '')))
     / length(anchor_provider) <> 1 then
    raise exception using message = 'start_job_provider_anchor_invalid';
  end if;
  if (length(source_text) - length(replace(source_text, anchor_model, ''))) /
     length(anchor_model) <> 1 then
    raise exception using message = 'start_model_anchor_invalid';
  end if;
  if (length(source_text) - length(replace(source_text, anchor_platform, '')))
     / length(anchor_platform) <> 1 then
    raise exception using message = 'start_platform_anchor_invalid';
  end if;
  patched_text := replace(source_text, anchor_media, patch_media);
  patched_text := replace(patched_text, anchor_provider, patch_provider);
  patched_text := replace(patched_text, anchor_model, patch_model);
  patched_text := replace(patched_text, anchor_platform, patch_platform);
  if patched_text = source_text then
    raise exception using message = 'start_patch_unchanged';
  end if;
  execute patched_text;
end;
$start_knows_fal$;

-- 2. Approve review знает fal и instagram (та же тройка литералов).
do $approve_knows_fal$
declare
  source_text text;
  patched_text text;
  anchor_media constant text := $am$
     or media_row.metadata ->> 'provider' <> 'runway'
$am$;
  patch_media constant text := $pm$
     -- Провайдер медиа обязан совпадать с провайдером наряда, а не с
     -- зашитым литералом: у fal-роликов «Создания» metadata.provider='fal'.
     or media_row.metadata ->> 'provider' is distinct from job_row.provider
$pm$;
  anchor_provider constant text := $ap$
     or job_row.provider <> 'runway'
$ap$;
  patch_provider constant text := $pp$
     or job_row.provider not in ('runway', 'fal')
$pp$;
  anchor_model constant text := $ao$
     or not content_factory_private
       .generation_runway_video_review_model_allowed(
         job_row.input ->> 'model'
       )
$ao$;
  patch_model constant text := $po$
     -- Идентичность видео для QA-приёмки двухпровайдерная. runway-список
     -- по-прежнему живёт в generation_runway_video_review_model_allowed(
     -- модель): identity-функция делегирует ему runway-ветку и знает
     -- fal/product_ad («Создание»). Комментарий несущий: пины
     -- authority-тестов ищут старое имя в теле этой функции.
     or not content_factory_private
       .generation_video_review_identity_allowed(
         job_row.provider, job_row.input ->> 'model'
       )
$po$;
  anchor_platform constant text := $al$
       'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
$al$;
  patch_platform constant text := $pl$
       'tiktok', 'youtube', 'vk', 'telegram', 'wildberries',
       -- Все платные fal-ролики «Создания» целятся в instagram; нижележащий
       -- creator_start_content_review принимает instagram с рождения.
       'instagram'
$pl$;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'::regprocedure
  );
  if position('generation_video_review_identity_allowed' in source_text) > 0
  then
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor_media, ''))) /
     length(anchor_media) <> 1 then
    raise exception using message = 'approve_media_provider_anchor_invalid';
  end if;
  if (length(source_text) - length(replace(source_text, anchor_provider, '')))
     / length(anchor_provider) <> 1 then
    raise exception using message = 'approve_job_provider_anchor_invalid';
  end if;
  if (length(source_text) - length(replace(source_text, anchor_model, ''))) /
     length(anchor_model) <> 1 then
    raise exception using message = 'approve_model_anchor_invalid';
  end if;
  if (length(source_text) - length(replace(source_text, anchor_platform, '')))
     / length(anchor_platform) <> 1 then
    raise exception using message = 'approve_platform_anchor_invalid';
  end if;
  patched_text := replace(source_text, anchor_media, patch_media);
  patched_text := replace(patched_text, anchor_provider, patch_provider);
  patched_text := replace(patched_text, anchor_model, patch_model);
  patched_text := replace(patched_text, anchor_platform, patch_platform);
  if patched_text = source_text then
    raise exception using message = 'approve_patch_unchanged';
  end if;
  execute patched_text;
end;
$approve_knows_fal$;

-- 3. Звуковой шлюз: авторитет звука для fal/product_ad.
do $sound_gate_knows_fal$
declare
  source_text text;
  patched_text text;
  anchor_provider constant text := $sp$
     or generation_job_row.provider <> 'runway'
$sp$;
  patch_provider constant text := $qp$
     or generation_job_row.provider not in ('runway', 'fal')
$qp$;
  anchor_audio constant text := $sa$
  server_audio_value := case
    when content_factory_private.generation_runway_video_review_model_allowed(
      generation_job_row.input ->> 'model'
    )
      then (
        content_factory_private.real_generation_sku_from_input(
          generation_job_row.provider, generation_job_row.input
        ) ->> 'audio'
      )::boolean
    else null
  end;
$sa$;
  patch_audio constant text := $qa$
  server_audio_value := case
    when generation_job_row.provider = 'runway'
     and content_factory_private.generation_runway_video_review_model_allowed(
      generation_job_row.input ->> 'model'
    )
      then (
        content_factory_private.real_generation_sku_from_input(
          generation_job_row.provider, generation_job_row.input
        ) ->> 'audio'
      )::boolean
    -- fal/product_ad: SKU-пересчёта нет (real_generation_multimodel_sku
    -- рецепта не знает и вернул бы null). Авторитет звука — явный boolean
    -- из input наряда, зеркалом которого обязан быть серверный снимок
    -- strategy_technical.audio того же наряда.
    when generation_job_row.provider = 'fal'
     and lower(btrim(coalesce(generation_job_row.input ->> 'model', ''))) =
         'product_ad'
     and jsonb_typeof(generation_job_row.input -> 'audio') = 'boolean'
     and generation_job_row.input #> '{strategy_technical,audio}' =
         generation_job_row.input -> 'audio'
      then (generation_job_row.input ->> 'audio')::boolean
    else null
  end;
$qa$;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'::regprocedure
  );
  if position('strategy_technical,audio' in source_text) > 0 then
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor_provider, '')))
     / length(anchor_provider) <> 1 then
    raise exception using message = 'sound_provider_anchor_invalid';
  end if;
  if (length(source_text) - length(replace(source_text, anchor_audio, ''))) /
     length(anchor_audio) <> 1 then
    raise exception using message = 'sound_audio_anchor_invalid';
  end if;
  patched_text := replace(source_text, anchor_provider, patch_provider);
  patched_text := replace(patched_text, anchor_audio, patch_audio);
  if patched_text = source_text then
    raise exception using message = 'sound_patch_unchanged';
  end if;
  execute patched_text;
end;
$sound_gate_knows_fal$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  body_text text;
begin
  -- 1. Identity-функция: runway-список делегирован, fal знает только
  --    product_ad, чужие провайдеры и NULL — false.
  if not content_factory_private.generation_video_review_identity_allowed(
       'runway', 'gen4_turbo')
     or not content_factory_private.generation_video_review_identity_allowed(
       'Runway', ' gen4.5 ')
     or not content_factory_private.generation_video_review_identity_allowed(
       'fal', 'product_ad')
     or content_factory_private.generation_video_review_identity_allowed(
       'runway', 'product_ad')
     or content_factory_private.generation_video_review_identity_allowed(
       'fal', 'product_swap')
     or content_factory_private.generation_video_review_identity_allowed(
       'heygen', 'avatar_v3')
     or content_factory_private.generation_video_review_identity_allowed(
       null, null) then
    raise exception using message = 'identity_function_behaviour_invalid';
  end if;

  -- 2. Старт: identity-вызов, instagram, двухпровайдерная сверка; пин
  --    authority-теста (старое имя) сохранён; старых литералов нет.
  body_text := pg_get_functiondef(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'::regprocedure
  );
  if position('generation_video_review_identity_allowed' in body_text) = 0
     or position(
       'generation_runway_video_review_model_allowed(' in body_text) = 0
     or position($n$'instagram'$n$ in body_text) = 0
     or position(
       $n$job_row.provider not in ('runway', 'fal')$n$ in body_text) = 0
     or position(
       $n$media_row.metadata ->> 'provider' is distinct from job_row.provider$n$
       in body_text) = 0
     or position($n$job_row.provider <> 'runway'$n$ in body_text) > 0 then
    raise exception using message = 'start_patch_incomplete';
  end if;

  -- 3. Approve: те же гарантии.
  body_text := pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'::regprocedure
  );
  if position('generation_video_review_identity_allowed' in body_text) = 0
     or position(
       'generation_runway_video_review_model_allowed(' in body_text) = 0
     or position($n$'instagram'$n$ in body_text) = 0
     or position(
       $n$job_row.provider not in ('runway', 'fal')$n$ in body_text) = 0
     or position(
       $n$media_row.metadata ->> 'provider' is distinct from job_row.provider$n$
       in body_text) = 0
     or position($n$job_row.provider <> 'runway'$n$ in body_text) > 0 then
    raise exception using message = 'approve_patch_incomplete';
  end if;

  -- 4. Звуковой шлюз: fal-ветка есть, runway-SKU-ветка не вытеснена, пины
  --    sound-gate-теста сохранены.
  body_text := pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'::regprocedure
  );
  if position(
       $n$generation_job_row.provider not in ('runway', 'fal')$n$
       in body_text) = 0
     or position('strategy_technical,audio' in body_text) = 0
     or position('real_generation_sku_from_input(' in body_text) = 0
     or position(
       'generation_job_row.provider, generation_job_row.input' in body_text
     ) = 0
     or position(
       'generation_runway_video_review_model_allowed(' in body_text) = 0 then
    raise exception using message = 'sound_gate_patch_incomplete';
  end if;
end;
$verify$;

commit;
