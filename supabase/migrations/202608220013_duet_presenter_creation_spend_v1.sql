begin;

-- 202608220013_duet_presenter_creation_spend_v1
--
-- Создание ведущего — платная операция ($1.00 за вызов у HeyGen), и она обязана
-- быть видна бюджету наравне с генерацией.
--
-- ПОЧЕМУ НЕ ОТДЕЛЬНАЯ ТАБЛИЦА. Обзор трат организации считается СУММОЙ по
-- журналу `generation_spend_ledger` (generation_spend_organization_overview).
-- Своя таблица означала бы, что доллары за ведущих не попадают в бюджет вовсе:
-- деньги уходят, а лимит их не видит. Незаметная трата хуже дорогой.
--
-- ЧТО МЕШАЛО. Журнал требовал `generation_job_id` NOT NULL, а создание ведущего
-- нарядом не является: у него нет ни ролика, ни спеки, ни результата в архиве.
-- Подставлять сюда выдуманный наряд значило бы засорить архив записями о
-- несуществующих роликах и сломать смысл слова «наряд».
--
-- ЧТО СДЕЛАНО. Журнал становится журналом ПРОВАЙДЕРСКИХ трат, а не только
-- нарядных: ссылка на наряд стала необязательной, рядом появилась ссылка на
-- ведущего, и ровно одна из них обязана быть заполнена. Внешний ключ на наряды
-- составной, поэтому при NULL он просто не применяется — связь с нарядами
-- сохраняется в точности как была.
--
-- Суммирование не меняется ни в одном месте: оно идёт по организации и по датам
-- и о происхождении строки не спрашивает.

alter table content_factory.generation_spend_ledger
  alter column generation_job_id drop not null,
  add column if not exists duet_presenter_id uuid;

do $ledger_presenter_constraints$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_spend_ledger_presenter_fkey'
  ) then
    alter table content_factory.generation_spend_ledger
      add constraint generation_spend_ledger_presenter_fkey
      foreign key (duet_presenter_id)
      references content_factory.generation_duet_presenters (id)
      on delete restrict;
  end if;

  -- Ровно один источник траты. Строка без источника — трата без причины; строка
  -- с обоими — трата, посчитанная дважды в двух разных разрезах.
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_spend_ledger_single_source_check'
  ) then
    alter table content_factory.generation_spend_ledger
      add constraint generation_spend_ledger_single_source_check
      check (
        (generation_job_id is not null and duet_presenter_id is null)
        or (generation_job_id is null and duet_presenter_id is not null)
      );
  end if;
end;
$ledger_presenter_constraints$;

create index if not exists generation_spend_ledger_presenter_idx
  on content_factory.generation_spend_ledger (duet_presenter_id)
  where duet_presenter_id is not null;

-- Состояния ведущего пополняются обучением. До 22.08.2026 он мог быть только
-- сразу действующим, потому что идентификатор вписывали руками. Теперь ведущий
-- создаётся у провайдера и какое-то время учится.
alter table content_factory.generation_duet_presenters
  alter column provider_avatar_id drop not null,
  alter column provider_voice_id drop not null;

do $presenter_training_states$
begin
  alter table content_factory.generation_duet_presenters
    drop constraint if exists generation_duet_presenters_status_check;
  alter table content_factory.generation_duet_presenters
    add constraint generation_duet_presenters_status_check
    check (status = any (array[
      'training',          -- обучается у провайдера, деньги уже потрачены
      'awaiting_consent',  -- провайдер ждёт подтверждения на внешность
      'active',            -- готов, можно снимать
      'failed',            -- не вышло; деньги провайдеру уже ушли
      'archived'
    ]));

  -- Действующий ведущий обязан иметь личность у провайдера. Обучающийся — ещё
  -- нет, и требовать её от него значило бы не дать записать сам факт оплаты.
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_active_identity_check'
  ) then
    alter table content_factory.generation_duet_presenters
      add constraint generation_duet_presenters_active_identity_check
      check (
        status <> 'active'
        or (provider_avatar_id is not null and provider_voice_id is not null)
      );
  end if;
end;
$presenter_training_states$;

-- Идентификатор группы аватара у провайдера: он возвращается вместе с ведущим и
-- нужен, чтобы потом добавить тому же человеку другие ракурсы, не создавая его
-- заново за отдельный доллар.
alter table content_factory.generation_duet_presenters
  add column if not exists provider_group_id text,
  add column if not exists training_failure_code text,
  add column if not exists provider_created_at timestamptz;

do $presenter_creation_verify$
declare
  overview text;
begin
  -- Обзор трат по-прежнему суммирует журнал целиком: доллары за ведущих
  -- попадают в бюджет автоматически, без правки самого обзора.
  overview := pg_get_functiondef(
    'content_factory_private.generation_spend_organization_overview(uuid)'::regprocedure
  );
  if position('generation_spend_ledger' in overview) = 0 then
    raise exception using message = 'spend_overview_no_longer_reads_ledger';
  end if;
  if position('duet_presenter_id' in overview) > 0 then
    raise exception using message = 'spend_overview_started_filtering_by_source';
  end if;

  -- Ровно один источник — и это проверяется поведением, а не текстом.
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_spend_ledger_single_source_check'
  ) then
    raise exception using message = 'ledger_single_source_constraint_missing';
  end if;

  -- Действующий ведущий без личности невозможен.
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_active_identity_check'
  ) then
    raise exception using message = 'presenter_active_identity_constraint_missing';
  end if;
end;
$presenter_creation_verify$;

commit;
