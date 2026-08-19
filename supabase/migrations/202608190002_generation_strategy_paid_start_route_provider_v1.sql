begin;

-- 202608190002_generation_strategy_paid_start_route_provider_v1
--
-- Платный старт стратегии перестаёт требовать слово «runway».
--
-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и комментарий перед BEGIN отвергается
-- вместе со всей цепочкой. Поэтому «почему» живёт внутри транзакции.
--
-- ЧТО НАБЛЮДАЛОСЬ. Бесплатная часть маршрута fal работает целиком: каталог
-- отдаёт «Копию», привязка считается по 47 центов, квитанция готовности
-- пишется с provider = 'fal' и ready = true. Платный запуск при этом отвечает
-- общим отказом generation_unavailable (503) — без кода, без объяснения, без
-- следа в журнале. Ни одного клейма после появления квитанций fal не
-- появилось: деньги не резервировались, значит отказ случается ДО них.
--
-- ПОЧЕМУ ИМЕННО 503. Клейм вставляет батч с provider = receipt_row.provider,
-- то есть 'fal' (202608180005). Триггер BEFORE INSERT
-- content_factory_private.guard_generation_batch_contract видит в ветке
-- стратегии new.provider <> 'runway' и поднимает
-- generation_strategy_batch_contract_invalid с кодом 42501. Разбор ошибок в
-- creator-generate пропускает шаблон generation_strategy_*, но суффикса
-- _invalid нет ни в одном списке 409/422/403, поэтому наружу уходит ровно
-- { code: "generation_unavailable", status: 503 }. Отказ общий не потому, что
-- причина неизвестна, а потому что её некуда положить.
--
-- ЧТО ИМЕННО ПРАВИТСЯ. Провайдер перестаёт быть словом и становится свойством
-- маршрута. Ни одна проверка не снимается:
--
--   * снимок исполнения обязан назвать ТОТ ЖЕ движок, что подписан в квитанции
--     готовности вместе с ценой (раньше сверялся с литералом, то есть с
--     движком, которого в квитанции могло не быть вовсе);
--   * этот движок обязан быть включённым маршрутом реестра для своей стратегии
--     И со своей версией прайса — пара «провайдер + версия прайса» различает
--     два маршрута fal (Pika за ролик и Kling за секунду), поэтому подменить
--     один другим мимо цены нельзя;
--   * батч, наряд и переход в отправку обязаны назвать ТОТ ЖЕ движок, что и
--     снимок исполнения.
--
-- Для provider = 'runway' поведение остаётся прежним до буквы: квитанция
-- называет runway, маршрут «Копии» с этим провайдером включён, у «Аватара» и
-- «Пересборки» маршрутов в реестре нет вовсе — для них помощник намеренно
-- отдаёт прежний инвариант «только runway». Это не задел на будущее, а защита
-- настоящего: без такой развилки две работающие стратегии умерли бы молча.
--
-- ОТДЕЛЬНО — ДЫРА, КОТОРУЮ ЗАКРЫВАЕМ ЗАОДНО. Сторож привязки наряда к
-- утверждённой спецификации (bind_generation_spec_to_paid_job) выходил из
-- проверки сразу, если провайдер не runway и не google. Для fal это означало
-- не отказ, а МОЛЧАЛИВЫЙ ПРОПУСК: платный наряд второго движка не сверялся со
-- спецификацией вообще. Снять привязку к слову и оставить пропуск было бы
-- ослаблением, поэтому ветка стратегии теперь достижима при любом провайдере.
--
-- И ЕЩЁ ОДНА, БЕЗ КОТОРОЙ ПОЧИНКА БЫЛА БЫ ОПАСНЕЕ БОЛЕЗНИ. Ответ
-- system_mark_generation_strategy_dispatch_attempt не нёс провайдера. Функция
-- отправки в creator-generate читает attempt.provider и при его отсутствии
-- берёт "runway" по умолчанию. То есть стоило снять запрет в сторожах — и
-- запуск, оплаченный по прайсу fal (47 центов), ушёл бы POST-запросом в
-- Runway. Провайдер добавлен в ответ отправки из той же квитанции.
--
-- Тела функций правятся точечной заменой известного фрагмента: полные тела
-- живут в 202608130007, и переписывать их целиком ради одной строки означало
-- бы рисковать остальным содержимым. Каждый якорь проверяется на
-- единственность ДО замены, иначе миграция падает с именем якоря.


-- Действующий маршрут исполнения: провайдер обязан быть включённой строкой
-- реестра ИМЕННО с той версией прайса, по которой посчитаны деньги. Если у
-- стратегии маршрутов нет вовсе — отдаётся прежний инвариант «только runway»,
-- иначе «Аватар» и «Пересборка» перестали бы запускаться.
create or replace function
  content_factory_private.generation_strategy_route_provider_current(
    p_strategy_id text,
    p_provider text,
    p_pricing_version text
  )
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select case
    when not exists (
      select 1
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = p_strategy_id
    ) then p_provider = 'runway'
    else exists (
      select 1
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = p_strategy_id
        and route.provider = p_provider
        and route.pricing_version = p_pricing_version
        and route.enabled
    )
  end;
$$;

comment on function
  content_factory_private.generation_strategy_route_provider_current(
    text, text, text
  ) is
  'Провайдер платного запуска обязан быть включённым маршрутом реестра со своей версией прайса. Стратегия без маршрутов сохраняет прежний инвариант «только runway».';

-- Известные исполнители стратегии. Набор повторяет ограничение колонки
-- provider таблицы квитанций готовности (202608180004): случайная строка
-- по-прежнему не пройдёт. Отдельная функция нужна потому, что табличное
-- ограничение не умеет читать реестр маршрутов, а список известных движков —
-- умеет.
create or replace function
  content_factory_private.generation_strategy_provider_known(p_provider text)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select p_provider in ('runway', 'fal');
$$;

comment on function
  content_factory_private.generation_strategy_provider_known(text) is
  'Известные исполнители стратегии генерации. Тот же набор стоит в ограничении колонки provider таблицы квитанций готовности.';

-- Инструмент времени сборки: заменяет фрагмент ровно один раз или падает.
-- Живёт только внутри этой миграции и удаляется в конце.
create or replace function content_factory_private.migration_patch_once(
  p_source text,
  p_search text,
  p_replace text,
  p_tag text
)
returns text
language plpgsql
immutable
as $$
declare
  hits integer;
begin
  if p_source is null or p_search is null or length(p_search) = 0 then
    raise exception using message = 'patch_arguments_invalid:' || p_tag;
  end if;
  hits := (length(p_source) - length(replace(p_source, p_search, '')))
    / length(p_search);
  if hits <> 1 then
    raise exception using
      message = 'patch_anchor_not_unique:' || p_tag || ':' || hits::text;
  end if;
  return replace(p_source, p_search, p_replace);
end;
$$;

-- 1. Общий валидатор снимка исполнения. Его зовут три сторожа: батча, наряда и
--    перехода в отправку. Пока провайдер сверялся с литералом, снять запрет в
--    самих сторожах было бесполезно — эта строка отвергла бы маршрут повторно.
--    Квитанция здесь уже прочитана (receipt_row), её провайдер подписан вместе
--    с ценой, поэтому сверка с ней строже прежней: раньше проходил любой
--    runway-снимок, даже если квитанция говорила о другом движке.
do $patch_execution_input_current$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_strategy_execution_input_current';
  if definition_value is null then
    raise exception using message = 'execution_input_current_missing';
  end if;

  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$     or p_input ->> 'provider' <> 'runway'$s$,
    $r$     or p_input ->> 'provider' <> receipt_row.provider
     or not content_factory_private
          .generation_strategy_route_provider_current(
            receipt_row.strategy_id, receipt_row.provider,
            receipt_row.pricing_version
          )$r$,
    'execution_input_current.provider'
  );

  execute patched_value;
end;
$patch_execution_input_current$;

-- 2. Сторож батча. Это и есть источник наблюдаемого 503: триггер BEFORE INSERT
--    срабатывает раньше табличных ограничений. Провайдер батча теперь обязан
--    совпасть с провайдером снимка исполнения, а тот строкой ниже сверяется с
--    квитанцией и реестром. Расхождение по-прежнему отвергается тем же кодом.
do $patch_batch_guard$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'guard_generation_batch_contract';
  if definition_value is null then
    raise exception using message = 'batch_guard_missing';
  end if;

  -- Якорь однострочный намеренно: многострочный фрагмент ломается о переводы
  -- строк, которыми база возвращает тело функции, и патч не находит цель.
  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$new.mode <> 'real' or new.provider <> 'runway'$s$,
    $r$new.mode <> 'real'
       or new.provider is distinct from new.input ->> 'provider'$r$,
    'batch_guard.provider'
  );

  execute patched_value;
end;
$patch_batch_guard$;

-- 3. Сторож наряда. Тот же узор; без этой правки клейм упал бы на следующей
--    же вставке, уже после того как батч создан.
do $patch_job_guard$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'guard_generation_job_contract';
  if definition_value is null then
    raise exception using message = 'job_guard_missing';
  end if;

  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$    if new.mode <> 'real' or new.provider <> 'runway'
       or not new.allow_real_spend
       or new.actual_cost_minor < 0$s$,
    $r$    if new.mode <> 'real'
       or new.provider is distinct from new.input ->> 'provider'
       or not new.allow_real_spend
       or new.actual_cost_minor < 0$r$,
    'job_guard.provider'
  );

  execute patched_value;
end;
$patch_job_guard$;

-- 4. Сторож перехода queued -> starting. Он стоит уже ПОСЛЕ резервирования
--    денег: отказ здесь оставил бы висящий резерв, поэтому слово «runway»
--    здесь опаснее всего.
do $patch_provider_start_guard$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'guard_generation_spec_provider_start';
  if definition_value is null then
    raise exception using message = 'provider_start_guard_missing';
  end if;

  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$    if new.mode <> 'real' or new.provider <> 'runway'
       or not new.allow_real_spend
       or new.output ->> 'submission_state' <> 'dispatch_reserved'$s$,
    $r$    if new.mode <> 'real'
       or new.provider is distinct from new.input ->> 'provider'
       or not new.allow_real_spend
       or new.output ->> 'submission_state' <> 'dispatch_reserved'$r$,
    'provider_start_guard.provider'
  );

  execute patched_value;
end;
$patch_provider_start_guard$;

-- 5. Привязка наряда к утверждённой спецификации. Здесь правятся ДВЕ строки, и
--    порознь их править нельзя.
--
--    Первая — вход в проверку. Список ('runway', 'google') выпускал наряд fal
--    из функции целиком: не отказ, а молчаливый пропуск платного наряда мимо
--    сверки со спецификацией. Теперь наряд со снимком исполнения стратегии
--    входит в проверку при любом провайдере; легаси-ветка не тронута.
--
--    Вторая — сам провайдер внутри ветки стратегии. Он сверяется со снимком
--    исполнения, а тот — с квитанцией.
do $patch_spec_binding$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'bind_generation_spec_to_paid_job';
  if definition_value is null then
    raise exception using message = 'spec_binding_missing';
  end if;

  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$  if new.mode <> 'real' or new.provider not in ('runway', 'google')
     or not new.allow_real_spend then
    return new;
  end if;$s$,
    $r$  if new.mode <> 'real' or not new.allow_real_spend
     or (
       new.provider not in ('runway', 'google')
       and new.input #>> '{strategy_execution,version}' is distinct from
         'generation-strategy-execution-snapshot-v1'
     ) then
    return new;
  end if;$r$,
    'spec_binding.entry'
  );

  patched_value := content_factory_private.migration_patch_once(
    patched_value,
    $s$    if new.provider <> 'runway'
       or new.product_id <> spec_row.product_id$s$,
    $r$    if new.provider is distinct from new.input ->> 'provider'
       or new.product_id <> spec_row.product_id$r$,
    'spec_binding.provider'
  );

  execute patched_value;
end;
$patch_spec_binding$;

-- 6. Провайдер отправки в ответе о зарезервированной попытке. Без него функция
--    отправки берёт "runway" по умолчанию — и запуск, оплаченный по прайсу
--    fal, ушёл бы в Runway. Категория товара нужна тому же вызову: маршрут
--    Pika требует назвать заменяемую область словами, и берётся она из уже
--    проверенной сервером категории наряда, а не из свободного текста
--    оператора.
do $patch_dispatch_attempt$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_mark_generation_strategy_dispatch_attempt';
  if definition_value is null then
    raise exception using message = 'dispatch_attempt_missing';
  end if;

  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$      'reserved_at', attempt_row.reserved_at
    ),$s$,
    $r$      'reserved_at', attempt_row.reserved_at,
      'provider', receipt_row.provider,
      'product_category', (
        select job.input ->> 'product_category'
        from content_factory.generation_jobs as job
        where job.organization_id = organization_id_value
          and job.id = claim_row.generation_job_id
      )
    ),$r$,
    'dispatch_attempt.provider'
  );

  execute patched_value;
end;
$patch_dispatch_attempt$;

-- 7. Происхождение готового ролика. Метаданные медиа и карточка проверки
--    вписывали провайдера словом: ролик, за который заплатили fal, был бы
--    записан как рунвеевский. Это не отказ, а ложь в учёте — по этим полям
--    потом разбирают, кому и за что платили. Значение берётся из квитанции,
--    как и в клейме (202608180005).
do $patch_provider_status$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_record_generation_strategy_provider_status';
  if definition_value is null then
    raise exception using message = 'provider_status_missing';
  end if;

  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$        or media_row.metadata ->> 'provider' <> 'runway'$s$,
    $r$        or media_row.metadata ->> 'provider' <> receipt_row.provider$r$,
    'provider_status.media_conflict'
  );

  patched_value := content_factory_private.migration_patch_once(
    patched_value,
    $s$            'kind', 'generated_video',
            'provider', 'runway',$s$,
    $r$            'kind', 'generated_video',
            'provider', receipt_row.provider,$r$,
    'provider_status.media_insert'
  );

  patched_value := content_factory_private.migration_patch_once(
    patched_value,
    $s$            'output_media_id', media_row.id,
            'provider', 'runway',$s$,
    $r$            'output_media_id', media_row.id,
            'provider', receipt_row.provider,$r$,
    'provider_status.review_task'
  );

  execute patched_value;
end;
$patch_provider_status$;

drop function content_factory_private.migration_patch_once(
  text, text, text, text
);

-- 8. Табличные ограничения. Сторожа срабатывают раньше них, поэтому без этих
--    трёх правок починка сторожей просто передвинула бы отказ на строку ниже —
--    и уже с кодом 23514 вместо 42501.
--
--    Списки провайдеров батчей и нарядов не пересматривались с 202608130002 и
--    не знают ни одного движка, кроме Runway и Google. Ограничение нарядов на
--    сумму расширили в 202608180007, а вот список провайдеров — нет.
alter table content_factory.generation_batches
  drop constraint if exists generation_batches_provider_v48_check;
alter table content_factory.generation_batches
  add constraint generation_batches_provider_v48_check
  check (provider in ('mock', 'runway', 'google', 'fal'));

alter table content_factory.generation_jobs
  drop constraint if exists generation_jobs_provider_v48_check;
alter table content_factory.generation_jobs
  add constraint generation_jobs_provider_v48_check
  check (provider in ('mock', 'runway', 'google', 'fal'));

-- Денежное ограничение батча. Ветка стратегии — третья; первые две (каталог
-- Runway и общий SKU) переписаны буква в букву из 202608130007, менять их
-- нельзя: они держат легаси-запуски. В ветке стратегии слово «runway»
-- заменено списком известных исполнителей — тем же, что стоит на колонке
-- provider таблицы квитанций. Совпадение с конкретной квитанцией проверяет
-- сторож: табличное ограничение не умеет читать другие таблицы.
alter table content_factory.generation_batches
  drop constraint if exists generation_batches_sku_contract_v48_check;

alter table content_factory.generation_batches
  add constraint generation_batches_sku_contract_v48_check check (
    (
      mode = 'mock' and provider = 'mock' and model = 'mock'
      and duration_seconds = 0 and not audio
      and estimated_cost_minor = 0 and estimated_credits = 0
    )
    or (
      mode = 'real' and allow_real_spend and (
        (
          provider = 'runway' and (
            (model = 'gen4_turbo' and duration_seconds between 2 and 10
              and not audio and estimated_cost_minor = duration_seconds * 5
              and estimated_credits = duration_seconds * 5)
            or (model = 'seedance2_fast'
              and duration_seconds between 4 and 15 and audio
              and estimated_cost_minor = duration_seconds * 29
              and estimated_credits = duration_seconds * 29)
            or (model = 'seedream5_lite' and duration_seconds = 0
              and not audio and estimated_cost_minor = 4
              and estimated_credits = 4)
          )
        )
        or (
          content_factory_private.real_generation_sku_from_input(
            provider, input
          ) is not null
          and model = content_factory_private.real_generation_sku_from_input(
            provider, input
          ) ->> 'model'
          and duration_seconds::text =
            content_factory_private.real_generation_sku_from_input(
              provider, input
            ) ->> 'duration_seconds'
          and audio = (
            content_factory_private.real_generation_sku_from_input(
              provider, input
            ) ->> 'audio'
          )::boolean
          and estimated_cost_minor::text =
            content_factory_private.real_generation_sku_from_input(
              provider, input
            ) ->> 'estimated_cost_minor'
          and to_jsonb(estimated_credits) =
            content_factory_private.real_generation_sku_from_input(
              provider, input
            ) -> 'estimated_credits'
        )
        or (
          content_factory_private.generation_strategy_provider_known(provider)
          and input #>> '{strategy_execution,version}' =
            'generation-strategy-execution-snapshot-v1'
          and input ->> 'strategy_recipe' in (
            'product_ugc', 'product_swap', 'product_ad'
          )
          and estimated_cost_minor::text =
            input #>> '{billing,estimated_cost_minor}'
          and to_jsonb(estimated_credits) =
            input #> '{billing,estimated_credits}'
          and input #>> '{billing,currency}' = 'USD'
        )
      )
    )
  );

do $paid_start_route_provider_verify$
declare
  definition_value text;
  constraint_value text;
begin
  -- 1. Помощник маршрута. Действующий маршрут «Копии» — Pika: провайдер fal со
  --    своей версией прайса проходит, он же с чужой версией — нет.
  if not content_factory_private.generation_strategy_route_provider_current(
       'viral_product_swap', 'fal', 'fal-usd-per-run-2026-08-18.v1'
     ) then
    raise exception using message = 'route_provider_rejects_active_route';
  end if;
  if content_factory_private.generation_strategy_route_provider_current(
       'viral_product_swap', 'fal', 'runway-recipe-credits-2026-08-14.v1'
     ) then
    raise exception using message = 'route_provider_accepts_price_swap';
  end if;
  -- Runway остался включённым дорогим уровнем «Копии» и обязан проходить.
  if not content_factory_private.generation_strategy_route_provider_current(
       'viral_product_swap', 'runway', 'runway-recipe-credits-2026-08-14.v1'
     ) then
    raise exception using message = 'route_provider_rejects_runway_tier';
  end if;
  -- У «Аватара» и «Пересборки» маршрутов нет: для них прежний инвариант.
  if not content_factory_private.generation_strategy_route_provider_current(
       'viral_avatar_ugc', 'runway', 'runway-recipe-credits-2026-08-14.v1'
     )
     or content_factory_private.generation_strategy_route_provider_current(
       'viral_avatar_ugc', 'fal', 'fal-usd-per-run-2026-08-18.v1'
     ) then
    raise exception using message = 'route_provider_fallback_broken';
  end if;
  -- Незнакомый движок не проходит нигде.
  if content_factory_private.generation_strategy_route_provider_current(
       'viral_product_swap', 'openai', 'fal-usd-per-run-2026-08-18.v1'
     )
     or content_factory_private.generation_strategy_provider_known('openai')
     or not content_factory_private.generation_strategy_provider_known('fal')
     or not content_factory_private.generation_strategy_provider_known(
       'runway'
     ) then
    raise exception using message = 'unknown_provider_accepted';
  end if;

  -- 2. Валидатор снимка исполнения сверяется с квитанцией, а не со словом.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_strategy_execution_input_current';
  if position($c$p_input ->> 'provider' <> 'runway'$c$ in definition_value) > 0
  then
    raise exception using message = 'execution_input_literal_left';
  end if;
  if position(
       $c$p_input ->> 'provider' <> receipt_row.provider$c$
       in definition_value
     ) = 0
     or position(
       'generation_strategy_route_provider_current' in definition_value
     ) = 0 then
    raise exception using message = 'execution_input_receipt_check_missing';
  end if;
  -- Остальные сверки снимка обязаны остаться на месте: провайдер не заменяет
  -- их собой.
  if position($c$p_input ->> 'strategy_recipe' <> receipt_row.recipe$c$
       in definition_value) = 0
     or position($c$p_input ->> 'spend_confirmation' <>$c$
       in definition_value) = 0 then
    raise exception using message = 'execution_input_checks_lost';
  end if;

  -- 3. Три сторожа обязаны сверять провайдера со снимком исполнения.
  foreach definition_value in array array[
    'guard_generation_batch_contract',
    'guard_generation_job_contract',
    'guard_generation_spec_provider_start',
    'bind_generation_spec_to_paid_job'
  ] loop
    select pg_get_functiondef(p.oid) into constraint_value
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private'
      and p.proname = definition_value;
    if constraint_value is null then
      raise exception using message = 'guard_missing:' || definition_value;
    end if;
    if position($c$new.provider <> 'runway'$c$ in constraint_value) > 0 then
      raise exception using
        message = 'guard_provider_literal_left:' || definition_value;
    end if;
    if position(
         $c$new.provider is distinct from new.input ->> 'provider'$c$
         in constraint_value
       ) = 0 then
      raise exception using
        message = 'guard_provider_check_missing:' || definition_value;
    end if;
    -- Каждый из четырёх обязан по-прежнему звать общий валидатор снимка:
    -- именно он связывает провайдера с квитанцией.
    if position(
         'generation_strategy_execution_input_current' in constraint_value
       ) = 0 then
      raise exception using
        message = 'guard_snapshot_check_lost:' || definition_value;
    end if;
  end loop;

  -- Легаси-ветки не тронуты: список ('runway', 'google') обязан остаться там,
  -- где он держит нестратегические наряды.
  select pg_get_functiondef(p.oid) into constraint_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'guard_generation_job_contract';
  if position($c$new.provider not in ('runway', 'google')$c$
       in constraint_value) = 0 then
    raise exception using message = 'legacy_job_branch_changed';
  end if;

  -- Наряд стратегии обязан входить в сверку со спецификацией при любом
  -- провайдере: молчаливый пропуск закрыт.
  select pg_get_functiondef(p.oid) into constraint_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'bind_generation_spec_to_paid_job';
  if position(
       $c$new.provider not in ('runway', 'google')
       and new.input #>> '{strategy_execution,version}' is distinct from$c$
       in constraint_value
     ) = 0 then
    raise exception using message = 'spec_binding_entry_not_widened';
  end if;

  -- 4. Отправка знает провайдера и категорию.
  select pg_get_functiondef(p.oid) into constraint_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_mark_generation_strategy_dispatch_attempt';
  if position($c$'provider', receipt_row.provider$c$ in constraint_value) = 0
     or position($c$'product_category', ($c$ in constraint_value) = 0 then
    raise exception using message = 'dispatch_attempt_provider_missing';
  end if;

  -- 5. Происхождение ролика берётся из квитанции.
  select pg_get_functiondef(p.oid) into constraint_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_record_generation_strategy_provider_status';
  if position($c$'provider', 'runway'$c$ in constraint_value) > 0
     or position($c$metadata ->> 'provider' <> 'runway'$c$
          in constraint_value) > 0 then
    raise exception using message = 'provider_status_literal_left';
  end if;
  if position($c$'provider', receipt_row.provider$c$ in constraint_value) = 0
     or position($c$metadata ->> 'provider' <> receipt_row.provider$c$
          in constraint_value) = 0 then
    raise exception using message = 'provider_status_receipt_missing';
  end if;

  -- 6. Табличные ограничения знают второй движок и не потеряли легаси-ветки.
  select pg_get_constraintdef(c.oid) into constraint_value
  from pg_constraint c
  where c.conrelid = 'content_factory.generation_batches'::regclass
    and c.conname = 'generation_batches_provider_v48_check';
  if constraint_value is null or constraint_value not like '%fal%'
     or constraint_value not like '%runway%'
     or constraint_value not like '%google%'
     or constraint_value not like '%mock%' then
    raise exception using message = 'batch_provider_check_invalid';
  end if;

  select pg_get_constraintdef(c.oid) into constraint_value
  from pg_constraint c
  where c.conrelid = 'content_factory.generation_jobs'::regclass
    and c.conname = 'generation_jobs_provider_v48_check';
  if constraint_value is null or constraint_value not like '%fal%'
     or constraint_value not like '%runway%'
     or constraint_value not like '%google%'
     or constraint_value not like '%mock%' then
    raise exception using message = 'job_provider_check_invalid';
  end if;

  select pg_get_constraintdef(c.oid) into constraint_value
  from pg_constraint c
  where c.conrelid = 'content_factory.generation_batches'::regclass
    and c.conname = 'generation_batches_sku_contract_v48_check';
  if constraint_value is null
     or constraint_value not like '%generation_strategy_provider_known%'
     or constraint_value not like '%gen4_turbo%'
     or constraint_value not like '%seedance2_fast%'
     or constraint_value not like '%seedream5_lite%'
     or constraint_value not like '%real_generation_sku_from_input%'
     or constraint_value not like '%strategy_execution%' then
    raise exception using message = 'batch_sku_contract_invalid';
  end if;

  -- 7. Инструмент времени сборки не должен остаться в базе.
  if exists (
    select 1
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private'
      and p.proname = 'migration_patch_once'
  ) then
    raise exception using message = 'migration_helper_left_behind';
  end if;
end;
$paid_start_route_provider_verify$;

commit;
