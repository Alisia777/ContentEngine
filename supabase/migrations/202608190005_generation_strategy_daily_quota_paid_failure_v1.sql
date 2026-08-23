begin;

-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и любой комментарий перед BEGIN
-- отвергает не только этот файл, но и всю цепочку миграций разом. Поэтому
-- «почему» живёт внутри транзакции.
--
-- 202608190005_generation_strategy_daily_quota_paid_failure_v1
--
-- Суточный потолок платных запусков перестаёт обходиться неудачами, за
-- которые уже заплачено.
--
-- ЧТО НАБЛЮДАЛОСЬ. 202608180001 вывела из счётчиков суточных лимитов ВСЕ
-- наряды со статусом failed. Обоснование записано прямо в теле функции: «у
-- неудачи нет задачи у провайдера, а резерв возвращает сверка». Для той
-- неудачи, которую тогда чинили, это верно — отказ случался ДО отправки
-- провайдеру. Но это не единственная форма неудачи, и утверждение оказалось
-- шире факта.
--
-- ПОЧЕМУ ЭТО ДЫРА. system_record_generation_strategy_provider_status на ответ
-- провайдера failed/cancelled ставит наряду actual_cost_minor =
-- estimated_cost_minor и пишет provider_billing_outcome = 'unknown'. То есть
-- задача у провайдера БЫЛА, деньги с высокой вероятностью списаны, и сверка
-- такой наряд не возвращает, а замораживает: record_real_generation_spend_
-- lifecycle пишет по нему строку 'frozen' с reason_code
-- 'provider_billing_outcome_unknown', а не 'released'. Каждая такая неудача
-- выпадала из суточного счётчика целиком. Десять оплаченных неудач подряд не
-- приближали пользователя к потолку 10, а организацию — к потолку 50: потолок
-- суток, который существует ради денег, переставал существовать ровно в том
-- случае, ради которого он поставлен. Обойти его при этом не нужно было
-- ничего подламывать — достаточно, чтобы провайдер отвечал отказом.
--
-- ЧТО ИМЕННО ПРАВИТСЯ. Из счётчика выпадает не «неудача», а ДОКАЗАННО
-- неоплаченная неудача. Доказательств ровно два, оба читаются из самого
-- наряда и оба — те же самые факты, по которым журнал трат решает, вернуть
-- резерв или заморозить:
--
--   * отказ до отправки: у наряда нет провайдерской задачи
--     (output.provider_task_id пуст), по нему ничего не списано
--     (actual_cost_minor = 0), итог биллинга не проставлен вовсе и сверка не
--     открыта. Так выглядят обе формы дособытийного отказа — 'rejected'
--     (запрос отвергнут до создания задачи) и 'confirmed_not_submitted'
--     (сверка подтвердила, что задача не создавалась). Журнал пишет по ним
--     'released';
--   * возврат: провайдер вернул деньги, и это записано словом
--     provider_billing_outcome = 'refundable' — тем же, по которому журнал
--     пишет компенсирующую строку 'refunded'.
--
-- Всё остальное считается: 'non_refundable' (списано и не вернут), 'unknown'
-- (итог неизвестен, наряд заморожен) и любая неудача с открытой сверкой
-- (reconciliation_required). Неизвестность не может быть доказательством
-- невиновности: именно на ней потолок и обходился.
--
-- ЧТО НАМЕРЕННО НЕ ТРОГАЕТСЯ. Статус 'cancelled' как считался, так и
-- считается: 202608180001 его не исключала, и расширять исключение заодно с
-- починкой — значит открыть вторую дверь вместо закрытия первой. Проверки
-- одновременности (assignee_open_jobs, organization_open_jobs) не менялись
-- вовсе: они и раньше видели каждый открытый наряд.
--
-- ПОЧЕМУ НЕ ПО ЖУРНАЛУ ТРАТ, ХОТЯ ОН И ЕСТЬ ИСТОЧНИК ИСТИНЫ О ДЕНЬГАХ.
-- record_real_generation_spend_lifecycle до сих пор входит в работу только
-- при provider in ('runway', 'google') — второй движок (fal) не оставляет в
-- журнале ни одной строки. Правило, читающее журнал, для маршрута fal
-- отвечало бы «доказательств нет» на любой наряд, то есть считало бы даже
-- отказ до отправки. Поэтому доказательство читается из самого наряда: те же
-- поля, что читает журнал, но одинаково для обоих движков.
--
-- ПОЧЕМУ ОТДЕЛЬНОЙ МИГРАЦИЕЙ, А НЕ ПРАВКОЙ 202608180001/202608180005. Обе уже
-- применены, их sha256 записан в contentengine_deploy.schema_migrations, и
-- загрузчик падает на расхождении контрольной суммы ДО первой записи — то
-- есть правка на месте блокирует не эту строку, а весь деплой. Применённый
-- файл неизменен по определению.
--
-- ПОЧЕМУ ЯКОРЯ ЗАМЕНЫ ОДНОСТРОЧНЫЕ. pg_get_functiondef отдаёт тело теми
-- байтами, какими его записала миграция-родитель. Многострочный якорь с
-- одними \n не совпадает НИ РАЗУ, если в теле оказались \r, — молча, без
-- диагностики; на этом уже падали миграции. Однострочный якорь к переводам
-- строк нечувствителен, а тело всё равно нормализуется перед заменой.


-- Доказательство того, что за неудачу не заплачено. Читается из наряда, а не
-- из журнала трат: см. «ПОЧЕМУ НЕ ПО ЖУРНАЛУ ТРАТ» выше. Функция намеренно
-- отвечает false на всё, что не доказано, — незнание считается тратой.
create or replace function
  content_factory_private.generation_job_failure_proven_unpaid(
    p_status text,
    p_actual_cost_minor bigint,
    p_output jsonb
  )
returns boolean
language sql
immutable
parallel safe
set search_path = ''
as $$
  select p_status = 'failed'
    and not content_factory_private.real_generation_reconciliation_unresolved(
      coalesce(p_output, '{}'::jsonb)
    )
    and (
      -- Возврат: провайдер вернул деньги. То же слово, по которому журнал
      -- трат пишет компенсирующую строку 'refunded'.
      coalesce(p_output ->> 'provider_billing_outcome', '') = 'refundable'
      -- Отказ до отправки: задачи у провайдера нет, по наряду ничего не
      -- списано, итог биллинга не проставлен вовсе. Журнал трат по такому
      -- наряду пишет 'released'.
      or (
        coalesce(p_actual_cost_minor, 0) = 0
        and nullif(btrim(coalesce(p_output ->> 'provider_task_id', '')), '')
          is null
        and coalesce(p_output ->> 'provider_billing_outcome', '') = ''
      )
    );
$$;

revoke all on function
  content_factory_private.generation_job_failure_proven_unpaid(
    text, bigint, jsonb
  )
  from public, anon, authenticated;

comment on function
  content_factory_private.generation_job_failure_proven_unpaid(
    text, bigint, jsonb
  ) is
  'Доказательство, что за неудачный наряд не заплачено: отказ до отправки провайдеру либо подтверждённый возврат. Оплаченные и неизвестные по итогу неудачи не доказаны и считаются тратой.';

-- Инструмент времени сборки: заменяет фрагмент ровно один раз или падает.
-- Живёт только внутри этой миграции и удаляется в конце.
--
-- Пятый аргумент различает две породы якорей, и различие это принципиальное.
-- Якорь КОДА обязателен: не нашли — значит правим не то тело, и молчаливый
-- пропуск оставил бы суточный потолок дырявым, притворившись починкой. Якорь
-- КОММЕНТАРИЯ необязателен: тело функции в облаке пришло другим путём, чем в
-- локальной цепочке (часть правок применялась приёмом
-- pg_get_functiondef + replace), и пояснительных строк там может не быть
-- вовсе. Падать из-за отсутствующего комментария — значит не применить
-- денежную починку из-за расхождения в пояснении к ней.
create or replace function
  content_factory_private.migration_patch_quota_once(
    p_source text,
    p_search text,
    p_replace text,
    p_tag text,
    p_required boolean default true
  )
returns text
language plpgsql
immutable
as $$
declare
  hits integer;
begin
  if p_source is null or p_search is null or length(p_search) = 0 then
    raise exception using message = 'quota_patch_arguments_invalid:' || p_tag;
  end if;
  hits := (length(p_source) - length(replace(p_source, p_search, '')))
    / length(p_search);
  if hits = 0 and not p_required then
    return p_source;
  end if;
  if hits <> 1 then
    raise exception using
      message = 'quota_patch_anchor_not_unique:' || p_tag || ':' || hits::text;
  end if;
  return replace(p_source, p_search, p_replace);
end;
$$;

do $patch_daily_quota_paid_failure$
declare
  definition_value text;
  patched_value text;
begin
  -- Нормализация переводов строк: тело правится однострочными якорями, но
  -- вписываемый текст многострочный, и записать его нужно на LF — иначе
  -- следующая миграция наступит на смесь \r\n и \n.
  select replace(
    pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    ),
    E'\r\n',
    E'\n'
  )
  into definition_value;
  if definition_value is null then
    raise exception using message = 'claim_start_rpc_missing';
  end if;

  if position(
       'generation_job_failure_proven_unpaid' in definition_value
     ) > 0 then
    -- Уже целевая форма: повторный прогон миграции ничего не меняет и не
    -- падает о съеденный якорь.
    return;
  end if;

  -- 1. Сам счётчик. Слепое исключение неудач заменяется доказанным.
  patched_value := content_factory_private.migration_patch_quota_once(
    definition_value,
    $s$    and job.status <> 'failed'$s$,
    $r$    and not content_factory_private
          .generation_job_failure_proven_unpaid(
            job.status, job.actual_cost_minor, job.output
          )$r$,
    'daily_quota.failed_predicate'
  );

  -- 2..4. Обоснование над счётчиком. Три строки правятся порознь, потому что
  --       якорь обязан быть однострочным. Оставить их нельзя: это ровно тот
  --       текст, которым слепое исключение и было оправдано, и следующий
  --       читатель поверит комментарию, а не коду. Комментарий английский —
  --       как всё остальное тело, пришедшее из 202608130007.
  patched_value := content_factory_private.migration_patch_quota_once(
    patched_value,
    $s$  -- Failed jobs hold no provider task and their reserves are released by$s$,
    $r$  -- A failure leaves the rolling daily quotas only when it is proven to$r$,
    'daily_quota.comment_line_1',
    false
  );
  patched_value := content_factory_private.migration_patch_quota_once(
    patched_value,
    $s$  -- reconciliation, so they do not consume the rolling daily quotas; the$s$,
    $r$  -- have cost nothing: no provider task and nothing committed, or an$r$,
    'daily_quota.comment_line_2',
    false
  );
  patched_value := content_factory_private.migration_patch_quota_once(
    patched_value,
    $s$  -- concurrency checks below still see every open job.$s$,
    $r$  -- explicit provider refund. A failure that was paid for, or whose
  -- billing outcome is unknown, still consumes the quota: otherwise a run
  -- of paid failures raises the ceiling instead of reaching it. The
  -- concurrency checks below still see every open job.$r$,
    'daily_quota.comment_line_3',
    false
  );

  execute patched_value;
end;
$patch_daily_quota_paid_failure$;

drop function content_factory_private.migration_patch_quota_once(
  text, text, text, text, boolean
);

comment on function
  public.system_claim_generation_strategy_start(jsonb) is
  'Платный старт стратегии. Провайдер берётся из квитанции готовности. Суточные лимиты пропускают только доказанно неоплаченные неудачи; оплаченные и неизвестные по итогу считаются.';

do $daily_quota_paid_failure_verify$
declare
  definition_value text;
begin
  -- 1. Таблица истинности доказательства. Каждая строка ниже — форма, которую
  --    наряд действительно принимает в этом коде, а не выдуманная.

  -- Отказ до отправки: провайдер отверг запрос, задачи нет, списаний нет.
  if not content_factory_private.generation_job_failure_proven_unpaid(
       'failed', 0,
       jsonb_build_object(
         'submission_state', 'rejected',
         'provider_post_started', false,
         'failure_code', 'provider_request_rejected'
       )
     ) then
    raise exception using message = 'verify_pre_dispatch_failure_counted';
  end if;

  -- Сверка подтвердила, что задача не создавалась: резерв возвращён.
  if not content_factory_private.generation_job_failure_proven_unpaid(
       'failed', 0,
       jsonb_build_object(
         'submission_state', 'confirmed_not_submitted',
         'reconciliation_resolution', 'confirm_no_submission',
         'failure_code', 'provider_submission_not_created'
       )
     ) then
    raise exception using message = 'verify_confirmed_not_submitted_counted';
  end if;

  -- Возврат подтверждён провайдером.
  if not content_factory_private.generation_job_failure_proven_unpaid(
       'failed', 428,
       jsonb_build_object(
         'provider_task_id', 'provider-task-1',
         'provider_billing_outcome', 'refundable'
       )
     ) then
    raise exception using message = 'verify_refunded_failure_counted';
  end if;

  -- ГЛАВНОЕ. Ответ провайдера failed: задача была, итог неизвестен, наряд
  -- заморожен. Ровно эта форма и обходила потолок.
  if content_factory_private.generation_job_failure_proven_unpaid(
       'failed', 428,
       jsonb_build_object(
         'provider_task_id', 'provider-task-1',
         'provider_billing_outcome', 'unknown',
         'failure_code', 'provider_generation_failed'
       )
     ) then
    raise exception using message = 'verify_unknown_billing_still_excluded';
  end if;

  -- Списано и не вернут.
  if content_factory_private.generation_job_failure_proven_unpaid(
       'failed', 428,
       jsonb_build_object(
         'provider_task_id', 'provider-task-1',
         'provider_billing_outcome', 'non_refundable'
       )
     ) then
    raise exception using message = 'verify_non_refundable_excluded';
  end if;

  -- Открытая сверка: отправка неоднозначна, доказательства нет.
  if content_factory_private.generation_job_failure_proven_unpaid(
       'failed', 0,
       jsonb_build_object(
         'reconciliation_required', true,
         'reconciliation_reason_code', 'provider_create_response_unknown'
       )
     ) then
    raise exception using message = 'verify_open_reconciliation_excluded';
  end if;

  -- Задача у провайдера есть, итог ещё не записан: одного нуля в
  -- actual_cost_minor мало. Эта проверка доказывает, что признак задачи
  -- несущий, а не декоративный.
  if content_factory_private.generation_job_failure_proven_unpaid(
       'failed', 0,
       jsonb_build_object('provider_task_id', 'provider-task-1')
     ) then
    raise exception using message = 'verify_provider_task_check_inert';
  end if;

  -- Списание есть, задачи в наряде не записано: одного отсутствия задачи тоже
  -- мало. Симметричная проверка второго признака.
  if content_factory_private.generation_job_failure_proven_unpaid(
       'failed', 428, '{}'::jsonb
     ) then
    raise exception using message = 'verify_committed_cost_check_inert';
  end if;

  -- Успех и отмена из счётчика не выпадают ни при каких пометках.
  if content_factory_private.generation_job_failure_proven_unpaid(
       'succeeded', 428,
       jsonb_build_object('provider_billing_outcome', 'refundable')
     )
     or content_factory_private.generation_job_failure_proven_unpaid(
       'cancelled', 0, '{}'::jsonb
     )
     or content_factory_private.generation_job_failure_proven_unpaid(
       'queued', 0, null
     ) then
    raise exception using message = 'verify_non_failed_status_excluded';
  end if;

  -- 2. Тело функции клейма. Здесь оно НАМЕРЕННО не нормализуется: проверка
  --    обязана видеть ровно те байты, что легли в базу.
  select pg_get_functiondef(
    'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
  )
  into definition_value;
  if definition_value is null then
    raise exception using message = 'verify_claim_start_rpc_missing';
  end if;

  -- Слепого исключения в теле не осталось.
  if position($c$job.status <> 'failed'$c$ in definition_value) > 0 then
    raise exception using message = 'verify_blanket_failed_exclusion_left';
  end if;
  -- И на его месте стоит доказательство.
  if position(
       'generation_job_failure_proven_unpaid' in definition_value
     ) = 0 then
    raise exception using message = 'verify_proven_unpaid_check_missing';
  end if;

  -- Многострочный якорь: совпадёт только если тело записано на LF и
  -- доказательство стоит именно в суточном счётчике, а не где-то ещё.
  if position(
       $verify_lf$    and job.mode = 'real'
    and not content_factory_private$verify_lf$ in definition_value
     ) = 0 then
    raise exception using message = 'verify_quota_predicate_misplaced';
  end if;

  -- Остальная форма суточного счётчика не тронута: окно, оба порога и
  -- разделение «свои/организация» на месте.
  if position($c$    into user_daily_jobs, organization_daily_jobs$c$
       in definition_value) = 0
     or position($c$job.created_at >= now() - interval '24 hours'$c$
       in definition_value) = 0
     or position($c$if user_daily_jobs >= 10 then$c$
       in definition_value) = 0
     or position($c$elsif organization_daily_jobs >= 50 then$c$
       in definition_value) = 0 then
    raise exception using message = 'verify_daily_quota_shape_lost';
  end if;

  -- Проверки одновременности не менялись вовсе.
  if position(
       $c$job.status in ('queued', 'starting', 'submitted', 'processing')$c$
       in definition_value) = 0
     or position($c$elsif assignee_open_jobs >= 1 then$c$
       in definition_value) = 0
     or position($c$elsif organization_open_jobs >= 3 then$c$
       in definition_value) = 0 then
    raise exception using message = 'verify_concurrency_checks_changed';
  end if;

  -- Устаревшее обоснование не пережило починку. Проверяется именно ОТСУТСТВИЕ
  -- старого текста, а не наличие нового: тело функции в облаке пришло другим
  -- путём, чем в локальной цепочке, и пояснительных строк там может не быть
  -- вовсе. Опасен здесь только оставшийся текст, которым слепое исключение
  -- неудач было оправдано, — он заставит следующего читателя поверить
  -- комментарию, а не коду. Отсутствие пояснения кода не меняет.
  if position('Failed jobs hold no provider task' in definition_value) > 0 then
    raise exception using message = 'verify_quota_reason_comment_stale';
  end if;

  -- 3. Достижения 202608180005 не откачены этой правкой: провайдер клейма
  --    по-прежнему берётся из квитанции, а не из литерала.
  if position('''runway''' in definition_value) > 0
     or position('receipt_row.provider' in definition_value) = 0 then
    raise exception using message = 'verify_claim_provider_regressed';
  end if;

  -- 4. Инструмент времени сборки не должен остаться в базе.
  if exists (
    select 1
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private'
      and p.proname = 'migration_patch_quota_once'
  ) then
    raise exception using message = 'verify_migration_helper_left_behind';
  end if;
end;
$daily_quota_paid_failure_verify$;

commit;
