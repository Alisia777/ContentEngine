begin;

-- 202608230030_reconciliation_knows_heygen_v1
--
-- Сбойный «Дуэт» перестаёт глушить платную генерацию всей организации.
--
-- ЧТО НАБЛЮДАЛОСЬ (аудит кода 24.08.2026, вход воспроизводим). HeyGen отвечает
-- 200, но без `data.video_id` — смена формы ответа или пустой `data`. Разбор
-- ответа даёт null, классификатор не находит 200 среди детерминированных
-- отказов и выдаёт `ambiguous`. Наряд получает `reconciliation_required`,
-- книга трат — строку `frozen`, а строка `reserved` не освобождается.
--
-- ПОЧЕМУ ЭТО НЕ «ОДНА ПОВИСШАЯ БРОНЬ». Триггер
-- `a_generation_jobs_reconciliation_freeze_guard` запрещает создать ЛЮБОЙ новый
-- платный наряд во ВСЕЙ организации, пока хоть у одного наряда признак разбора
-- не снят. Значит одна неудача останавливает «Копию», «Дуэт» и «Создание»
-- разом, а зависшая бронь продолжает съедать дневной и месячный потолок.
--
-- ВЫХОДА НЕ БЫЛО НИ ОДНОГО. Ручной разбор отвергал heygen на трёх уровнях
-- сразу: браузер по своему списку провайдеров, edge по своему, и база — вот
-- этой функцией, возвращавшей false любому не-runway и не-fal. Опрашивать было
-- нечего (идентификатора задачи не пришло), сторож зависших нарядов
-- стратегические наряды исключает, функция восстановления прибита к fal.
--
-- КОРЕНЬ. Миграция 202608230007 научила heygen'у сторожей расхода, но не
-- тронула словарь сверки. Эта асимметрия и есть дефект.
--
-- ЧЕГО ЭТА МИГРАЦИЯ НЕ ДЕЛАЕТ И ПОЧЕМУ ЭТО ВАЖНО. Она не трогает УСПЕШНЫЙ путь
-- ни одной стратегии. Все правки лежат в ветке разбора сбоя: раньше там был
-- отказ, теперь есть решение. Ни одно условие не ослаблено — расширены только
-- перечисления провайдеров, и ровно на того, кого уже признали деньги.
--
-- ЗАМОК РАСШИРЯЕТСЯ ОСОЗНАННО И ПОСЛЕДНИМ. Условие «не тратить поверх
-- нерасшитого» смотрело только на runway. Расширение делает его СТРОЖЕ, и это
-- было бы опасно, если бы в базе уже висел неразрешённый наряд другого
-- провайдера: платная генерация встала бы в момент применения. Проверено перед
-- правкой — в продакшене ноль неразрешённых нарядов из 43 платных. Порядок
-- внутри файла тоже не случаен: выход из тупика заводится ДО того, как замок
-- начинает ловить больше.

-- 1. Словарь сверки признаёт heygen.
--
--    Имена подтверждений называют, ЧТО именно проверил человек: у HeyGen
--    задача опознаётся идентификатором ролика, а не задачи, поэтому
--    VIDEO_ID/NO_VIDEO, а не TASK_ID/NO_TASK. Строка подтверждения — это
--    свидетельство человека, и она обязана называть то, на что он смотрел.
create or replace function
  content_factory_private.generation_strategy_reconciliation_confirmation_allowed(
    p_provider text, p_resolution text, p_confirmation text
  ) returns boolean
language sql
immutable parallel safe
set search_path to ''
as $function$
  select coalesce(case
    when p_provider = 'runway' and p_resolution = 'provider_task_attached'
      then p_confirmation = 'RUNWAY_TASK_ID_VERIFIED'
    when p_provider = 'runway' and p_resolution = 'confirmed_not_submitted'
      then p_confirmation = 'RUNWAY_NO_TASK_VERIFIED'
    when p_provider = 'fal' and p_resolution = 'provider_task_attached'
      then p_confirmation = 'FAL_REQUEST_ID_VERIFIED'
    when p_provider = 'fal' and p_resolution = 'confirmed_not_submitted'
      then p_confirmation = 'FAL_NO_REQUEST_VERIFIED'
    when p_provider = 'heygen' and p_resolution = 'provider_task_attached'
      then p_confirmation = 'HEYGEN_VIDEO_ID_VERIFIED'
    when p_provider = 'heygen' and p_resolution = 'confirmed_not_submitted'
      then p_confirmation = 'HEYGEN_NO_VIDEO_VERIFIED'
    else false
  end, false);
$function$;

-- 2. Разбор принимает свидетельства HeyGen.
do $reconcile_tokens$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'public.system_reconcile_generation_strategy_dispatch(jsonb)'::regprocedure
  );
  if position('HEYGEN_VIDEO_ID_VERIFIED' in source_text) > 0 then
    return;
  end if;
  patched_text := source_text;

  anchor := E'           ''RUNWAY_TASK_ID_VERIFIED'', ''FAL_REQUEST_ID_VERIFIED''\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'reconcile_anchor_attached_tokens';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'           ''RUNWAY_TASK_ID_VERIFIED'', ''FAL_REQUEST_ID_VERIFIED'',\n'
      || E'           ''HEYGEN_VIDEO_ID_VERIFIED''\n'
  );

  anchor := E'           ''RUNWAY_NO_TASK_VERIFIED'', ''FAL_NO_REQUEST_VERIFIED''\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'reconcile_anchor_not_submitted_tokens';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'           ''RUNWAY_NO_TASK_VERIFIED'', ''FAL_NO_REQUEST_VERIFIED'',\n'
      || E'           ''HEYGEN_NO_VIDEO_VERIFIED''\n'
  );

  if patched_text = source_text then
    raise exception using message = 'reconcile_tokens_unchanged';
  end if;
  execute patched_text;
end;
$reconcile_tokens$;

-- 3. Замок «не тратить поверх нерасшитого» перестаёт быть рунвеевским.
--
--    Провайдер здесь вообще ни при чём: условие уже требует платного наряда
--    (`mode = 'real'` и `allow_real_spend`), а нерасшитый платный наряд опасен
--    независимо от того, кто его исполнял. Фильтр по runway остался от времён,
--    когда провайдер был один.
do $freeze_guard_all_providers$
declare
  source_text text;
  patched_text text;
  anchor constant text :=
    E'      and job.mode = ''real''\n'
    || E'      and job.provider = ''runway''\n'
    || E'      and job.allow_real_spend';
begin
  source_text := pg_get_functiondef(
    'content_factory_private.guard_real_generation_spend_start()'::regprocedure
  );
  if position(anchor in source_text) = 0 then
    -- Повторный прогон обязан быть тихим.
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'freeze_guard_anchor_invalid';
  end if;
  patched_text := replace(
    source_text,
    anchor,
    E'      and job.mode = ''real''\n'
      || E'      -- Провайдер не сужается: нерасшитый ПЛАТНЫЙ наряд опасен\n'
      || E'      -- независимо от того, кто его исполнял. Прежний фильтр по\n'
      || E'      -- runway остался от времён единственного провайдера, и из-за\n'
      || E'      -- него поверх повисшего дуэта можно было набрать сколько\n'
      || E'      -- угодно новых платных запусков.\n'
      || E'      and job.allow_real_spend'
  );
  execute patched_text;
end;
$freeze_guard_all_providers$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $reconciliation_verify$
declare
  body_text text;
begin
  -- 1. Словарь: heygen признан на обоих разрешениях, и ровно своими именами.
  if not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'heygen', 'provider_task_attached', 'HEYGEN_VIDEO_ID_VERIFIED')
     or not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'heygen', 'confirmed_not_submitted', 'HEYGEN_NO_VIDEO_VERIFIED') then
    raise exception using message = 'heygen_reconciliation_still_closed';
  end if;

  -- 2. Чужое свидетельство heygen'у не годится: подтверждение называет то, на
  --    что человек смотрел, и подменять его нельзя.
  if content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'heygen', 'provider_task_attached', 'RUNWAY_TASK_ID_VERIFIED')
     or content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'heygen', 'confirmed_not_submitted', 'FAL_NO_REQUEST_VERIFIED')
     or content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'heygen', 'provider_task_attached', 'HEYGEN_NO_VIDEO_VERIFIED') then
    raise exception using message = 'heygen_accepts_foreign_confirmation';
  end if;

  -- 3. Прежние провайдеры не тронуты — ни одно разрешение не изменилось.
  if not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'runway', 'provider_task_attached', 'RUNWAY_TASK_ID_VERIFIED')
     or not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'runway', 'confirmed_not_submitted', 'RUNWAY_NO_TASK_VERIFIED')
     or not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'fal', 'provider_task_attached', 'FAL_REQUEST_ID_VERIFIED')
     or not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'fal', 'confirmed_not_submitted', 'FAL_NO_REQUEST_VERIFIED') then
    raise exception using message = 'existing_providers_broken';
  end if;

  -- 4. Всеядной функция не стала.
  if content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'google', 'provider_task_attached', 'RUNWAY_TASK_ID_VERIFIED')
     or content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'heygen', 'something_else', 'HEYGEN_VIDEO_ID_VERIFIED')
     or content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         '', '', '') then
    raise exception using message = 'reconciliation_gate_too_permissive';
  end if;

  -- 5. Разбор принимает свидетельства HeyGen на обоих разрешениях.
  body_text := pg_get_functiondef(
    'public.system_reconcile_generation_strategy_dispatch(jsonb)'::regprocedure
  );
  if position('HEYGEN_VIDEO_ID_VERIFIED' in body_text) = 0
     or position('HEYGEN_NO_VIDEO_VERIFIED' in body_text) = 0 then
    raise exception using message = 'reconcile_tokens_missing';
  end if;
  -- Прежние свидетельства на месте: расширение не должно было их вытеснить.
  if position('RUNWAY_TASK_ID_VERIFIED' in body_text) = 0
     or position('FAL_NO_REQUEST_VERIFIED' in body_text) = 0 then
    raise exception using message = 'existing_tokens_lost';
  end if;

  -- 6. Замок больше не рунвеевский, но и не ослаблен: платность осталась
  --    обязательным условием, иначе он ловил бы бесплатные наряды.
  body_text := pg_get_functiondef(
    'content_factory_private.guard_real_generation_spend_start()'::regprocedure
  );
  if position(E'and job.provider = ''runway''' in body_text) > 0 then
    raise exception using message = 'freeze_guard_still_runway_only';
  end if;
  if position(E'and job.allow_real_spend' in body_text) = 0
     or position('real_generation_reconciliation_required' in body_text) = 0 then
    raise exception using message = 'freeze_guard_weakened';
  end if;
end;
$reconciliation_verify$;

commit;
