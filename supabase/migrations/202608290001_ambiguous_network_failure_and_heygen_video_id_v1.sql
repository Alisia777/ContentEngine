begin;

-- 202608290001_ambiguous_network_failure_and_heygen_video_id_v1
--
-- Две дочистки разбора сбойных платных стартов, найденные аудитом 24.08 рядом
-- с орг-фризом «Дуэта» (202608230030) и подтверждённые боевым днём 29.08.
--
-- ПЕРВАЯ. Обрыв связи ПОСЛЕ отправки к провайдеру. Классификатор edge честно
-- называет такие исходы `provider_network_<имя_ошибки>` (lowercase,
-- [a-z0-9_], до 40 знаков; пустое имя подменяется словом unknown) — и это
-- ambiguous-исход: запрос МОГ дойти. Но ветка записи ambiguous-результата в
-- system_record_generation_strategy_dispatch_result требовала РОВНО
-- `provider_submission_ambiguous`: запись падала на 22023, наряд оставался
-- `starting` с provider_post_started = true, без строки результата и без
-- штатного выхода. Ветка расширяется на сетевые коды; NULL остаётся
-- запрещённым, как и был.
--
-- ВТОРАЯ. Ручная сверка «Дуэта» с привязкой задачи. У fal идентификатор
-- запроса — uuidv7, и сверка проверяет его формат и время. У HeyGen
-- идентификатор ролика — непрозрачная строка без времени; до этой миграции
-- сверка не проверяла его вовсе (только общую длину 8..240 на входе payload).
-- Добавляется зеркальная edge-проверке (isHeygenVideoId) рамка формата:
-- ^[A-Za-z0-9_-]{8,128}$. Временной кросс-чек для heygen невозможен —
-- идентификатор времени не несёт; общие окна от starting_at и глобальная
-- неповторность provider_task_id уже провайдеро-независимы и остаются.
--
-- ПОРЯДОК. Эта миграция обязана применяться ПОСЛЕ 202608230030: обе
-- переписывают system_reconcile_generation_strategy_dispatch, и проверка
-- поведением ниже требует словаря heygen из той миграции — при нарушении
-- порядка файл падает, это желаемое поведение.

-- 1. Ambiguous-ветка записи результата принимает сетевые коды.
do $ambiguous_network$
declare
  source_text text;
  patched_text text;
  anchor constant text :=
    E'         or failure_code_value is distinct from\n'
    || E'              ''provider_submission_ambiguous''\n';
begin
  perform pg_advisory_xact_lock(hashtext('generation_spend_budget'));
  source_text := pg_get_functiondef(
    'public.system_record_generation_strategy_dispatch_result(jsonb)'::regprocedure
  );
  if position('provider_network_' in source_text) > 0 then
    -- Повторный прогон обязан быть тихим.
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'ambiguous_anchor_invalid';
  end if;
  patched_text := replace(
    source_text,
    anchor,
    E'         or failure_code_value is null\n'
      || E'         -- Сетевой обрыв ПОСЛЕ отправки — тоже ambiguous: запрос\n'
      || E'         -- мог дойти. Код называет класс ошибки (edge режет имя до\n'
      || E'         -- [a-z0-9_]{1,40}); прежнее требование ровно одного\n'
      || E'         -- литерала роняло запись, и наряд повисал в starting без\n'
      || E'         -- строки результата и без штатного выхода.\n'
      || E'         or not (\n'
      || E'           failure_code_value = ''provider_submission_ambiguous''\n'
      || E'           or failure_code_value ~ ''^provider_network_[a-z0-9_]{1,40}$''\n'
      || E'         )\n'
  );
  if patched_text = source_text then
    raise exception using message = 'ambiguous_patch_unchanged';
  end if;
  execute patched_text;
end;
$ambiguous_network$;

-- 2. Формат идентификатора ролика HeyGen при привязке задачи.
do $heygen_video_id$
declare
  source_text text;
  patched_text text;
  anchor constant text :=
    E'    begin\n'
    || E'      starting_at_value := (job_row.output ->> ''starting_at'')::timestamptz;';
begin
  source_text := pg_get_functiondef(
    'public.system_reconcile_generation_strategy_dispatch(jsonb)'::regprocedure
  );
  if position('receipt_row.provider = ''heygen''' in source_text) > 0 then
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'heygen_anchor_invalid';
  end if;
  patched_text := replace(
    source_text,
    anchor,
    E'    if receipt_row.provider = ''heygen''\n'
      || E'       and resolution_value = ''provider_task_attached'' then\n'
      || E'      -- Идентификатор ролика HeyGen: та же граница, что у edge\n'
      || E'      -- (isHeygenVideoId) — непрозрачная строка, проверяем рамки,\n'
      || E'      -- не смысл. Времени идентификатор не несёт, поэтому\n'
      || E'      -- кросс-чека времени, как у fal, здесь нет.\n'
      || E'      if provider_task_id_value is null\n'
      || E'         or provider_task_id_value !~ ''^[A-Za-z0-9_-]{8,128}$'' then\n'
      || E'        raise exception using errcode = ''55000'',\n'
      || E'          message =\n'
      || E'            ''generation_strategy_dispatch_reconciliation_not_current'';\n'
      || E'      end if;\n'
      || E'    end if;\n'
      || E'    begin\n'
      || E'      starting_at_value := (job_row.output ->> ''starting_at'')::timestamptz;'
  );
  if patched_text = source_text then
    raise exception using message = 'heygen_patch_unchanged';
  end if;
  execute patched_text;
end;
$heygen_video_id$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  body_text text;
begin
  -- 1. Ambiguous-ветка знает сетевые коды и не потеряла прежний литерал.
  body_text := pg_get_functiondef(
    'public.system_record_generation_strategy_dispatch_result(jsonb)'::regprocedure
  );
  if position('provider_network_' in body_text) = 0
     or position('provider_submission_ambiguous' in body_text) = 0 then
    raise exception using message = 'ambiguous_network_missing';
  end if;
  if position(E'or failure_code_value is null' in body_text) = 0 then
    raise exception using message = 'ambiguous_null_gate_lost';
  end if;

  -- 2. Сверка знает и heygen-формат, и прежний fal-блок (не вытеснен).
  body_text := pg_get_functiondef(
    'public.system_reconcile_generation_strategy_dispatch(jsonb)'::regprocedure
  );
  if position('receipt_row.provider = ''heygen''' in body_text) = 0 then
    raise exception using message = 'heygen_format_missing';
  end if;
  if position('receipt_row.provider = ''fal''' in body_text) = 0
     or position('fal_request_epoch_ms_value' in body_text) = 0 then
    raise exception using message = 'fal_block_lost';
  end if;

  -- 3. Порядок с 202608230030: словарь heygen обязан уже существовать.
  if not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'heygen', 'provider_task_attached', 'HEYGEN_VIDEO_ID_VERIFIED') then
    raise exception using message = 'heygen_dictionary_missing_apply_202608230030_first';
  end if;
end;
$verify$;

commit;
