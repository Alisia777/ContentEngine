begin;

-- 202608190012_generation_reconciliation_provider_set_v1
--
-- Сверка платного наряда признаёт второго провайдера.
--
-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и комментарий перед BEGIN отвергает
-- вместе с ним всю цепочку. Поэтому «почему» живёт внутри транзакции.
--
-- ЧТО НАБЛЮДАЛОСЬ. Платный наряд на маршруте fal встал в статусе starting с
-- пометкой submission_state = 'ambiguous': отправка провайдеру началась, ответ
-- на создание задачи прочитать не удалось, provider_task_id не записан. Это
-- штатная ситуация — ровно для неё и существует сверка: владелец подтверждает,
-- что задачи у провайдера нет (confirm_no_submission), наряд закрывается, а
-- резерв возвращается. Но сверка на этом наряде не выполнялась ни в одном
-- виде: система отвечала real_generation_not_found — «такого наряда нет», хотя
-- наряд лежит в таблице и виден глазами.
--
-- ПОЧЕМУ. Весь контур сверки написан под единственного провайдера. Отбор
-- наряда и его партии сравнивает provider с литералом 'runway' — в двух
-- функциях-командах по два раза (наряд и партия), в чтении статуса один раз и
-- в стороже перехода один раз, всего шесть сравнений. Наряд fal не проходил
-- отбор, и обе команды отвечали «не найдено» ещё до всякой проверки прав.
-- Отказ выглядел как отсутствие данных, а был отказом опознать провайдера.
--
-- И ЭТО НЕ ТОЛЬКО ПРО ЗАКРЫТИЕ. Сторож перехода
-- guard_real_generation_reconciliation_transition — тот, кто ЗАПРЕЩАЕТ трогать
-- наряд, пока сверка не завершена, — тоже сравнивал провайдера с 'runway'.
-- Значит наряд fal под сверкой не был заморожен вовсе: его поля можно было
-- менять в обход сверки. Расширение списка здесь не ослабление, а ровно
-- обратное — оно распространяет заморозку на второго провайдера.
--
-- ЧТО ИМЕННО ПРАВИТСЯ. Шесть сравнений с одним провайдером становятся
-- сравнениями со списком ('runway','fal'). Больше ничего: роль owner/admin,
-- совпадение идентификатора инцидента, обязательная пауза в две минуты перед
-- confirm_no_submission, окно времени для attach_existing_task, единственная
-- связанная задача обзора, идемпотентность по ключу команды и хеш решения —
-- всё остаётся как есть и применяется к fal ровно так же, как к runway.
--
-- ЧЕГО ЭТА МИГРАЦИЯ НЕ ДЕЛАЕТ. Не закрывает ни одного наряда сама: закрытие
-- остаётся отдельной командой от имени владельца, с доказательством и
-- причиной. Не меняет поведение маршрута runway: он в списке первым, и все
-- прежние проверки для него дословно те же.

do $reconciliation_provider_set$
declare
  target record;
  definition_value text;
  patched_value text;
begin
  for target in
    select *
    from (values
      ('public', 'system_reconcile_real_generation'),
      ('public', 'system_mark_real_generation_reconciliation_required'),
      ('public', 'creator_real_generation_status'),
      ('content_factory_private',
       'guard_real_generation_reconciliation_transition')
    ) as t(schema_name, function_name)
  loop
    select pg_get_functiondef(p.oid) into definition_value
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = target.schema_name
      and p.proname = target.function_name;
    if definition_value is null then
      raise exception using
        message = 'reconciliation_provider_target_missing:'
          || target.function_name;
    end if;

    -- Повторный прогон ничего не меняет.
    if position($f$'runway','fal'$f$ in definition_value) > 0 then
      continue;
    end if;

    -- Все четыре формы сравнения разом: функции писались в разное время и
    -- пробелы вокруг оператора у них разные, а починка «по одной форме за
    -- миграцию» оставила бы контур наполовину расширенным.
    patched_value := definition_value;
    patched_value := replace(
      patched_value,
      $f$job_row.provider <> 'runway'$f$,
      $f$job_row.provider not in ('runway','fal')$f$
    );
    patched_value := replace(
      patched_value,
      $f$batch_row.provider <> 'runway'$f$,
      $f$batch_row.provider not in ('runway','fal')$f$
    );
    patched_value := replace(
      patched_value,
      $f$job.provider='runway'$f$,
      $f$job.provider in ('runway','fal')$f$
    );
    patched_value := replace(
      patched_value,
      $f$old.provider = 'runway'$f$,
      $f$old.provider in ('runway','fal')$f$
    );

    if patched_value = definition_value then
      raise exception using
        message = 'reconciliation_provider_anchor_missing:'
          || target.function_name;
    end if;
    execute patched_value;
  end loop;
end;
$reconciliation_provider_set$;

do $reconciliation_provider_set_verify$
declare
  target record;
  definition_value text;
begin
  for target in
    select *
    from (values
      ('public', 'system_reconcile_real_generation'),
      ('public', 'system_mark_real_generation_reconciliation_required'),
      ('public', 'creator_real_generation_status'),
      ('content_factory_private',
       'guard_real_generation_reconciliation_transition')
    ) as t(schema_name, function_name)
  loop
    select pg_get_functiondef(p.oid) into definition_value
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = target.schema_name
      and p.proname = target.function_name;

    -- 1. Второй провайдер признан.
    if definition_value is null
       or position($f$'runway','fal'$f$ in definition_value) = 0 then
      raise exception using
        message = 'reconciliation_provider_verify_failed:'
          || target.function_name;
    end if;

    -- 2. Не осталось ни одного одиночного сравнения: наполовину расширенный
    --    контур опаснее нерасширенного — часть сверки работала бы, часть нет.
    if position($f$provider <> 'runway'$f$ in definition_value) > 0
       or position($f$provider='runway'$f$ in definition_value) > 0
       or position($f$provider = 'runway'$f$ in definition_value) > 0 then
      raise exception using
        message = 'reconciliation_provider_literal_left:'
          || target.function_name;
    end if;
  end loop;

  -- 3. Сама сверка не ослабла: право, пауза и оба разрешённых исхода на месте.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_reconcile_real_generation';
  if position('real_generation_reconciliation_role_not_allowed'
       in definition_value) = 0
     or position('real_generation_reconciliation_wait_required'
       in definition_value) = 0
     or position('real_generation_reconciliation_incident_mismatch'
       in definition_value) = 0
     or position('confirm_no_submission' in definition_value) = 0
     or position('attach_existing_task' in definition_value) = 0 then
    raise exception using message = 'reconciliation_guard_lost';
  end if;

  -- 4. Заморозка наряда под сверкой по-прежнему умеет отказывать.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'guard_real_generation_reconciliation_transition';
  if position('real_generation_reconciliation_required'
       in definition_value) = 0
     or position('provider_submission_not_found' in definition_value) = 0 then
    raise exception using message = 'reconciliation_freeze_lost';
  end if;
end;
$reconciliation_provider_set_verify$;

commit;
