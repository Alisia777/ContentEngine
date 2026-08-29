begin;
-- 202608290004_publishing_platform_vocabulary_v1
--
-- Фаза 1 контура публикаций, шаг 0а (ТЗ
-- docs/PUBLISHING_ACCOUNTS_CONTOUR_2026-08-23.md §4.2 «placements», §8).
--
-- Словарь платформ размещений выравнивается со словарём реестра аккаунтов.
-- Хроника расхождения: placements_platform_check заведён 202607130001 на 6
-- значений (instagram, tiktok, youtube, vk, telegram, wildberries), а реестр
-- managed_accounts с фазы 0 живёт словарём из 9
-- (managed_accounts_platform_vocabulary_check: + ozon, rutube, other).
-- creator_publish_generation_result копирует platform ИЗ аккаунта в
-- placement — размещение из аккаунта ozon/rutube/other падало бы на CHECK.
--
-- Колонка placements.scheduled_at существует с 202607130001 и уже
-- проиндексирована (placements_assignee_idx), витрина «просрочено» её читает
-- (202607160005:718-732) — схему трогать не нужно; писать её начнёт
-- creator_enqueue_publishing_job (202608290006).
--
-- Идемпотентность: повторный прогон видит в ограничении слово rutube и тихо
-- выходит. Анкер: текущий текст ограничения обязан побайтно совпасть с
-- прод-снимком 29.08.2026 — при чужом тексте миграция падает, это желаемое
-- поведение (значит, словарь трогали мимо этой хроники).

do $platform_vocabulary$
declare
  constraint_def text;
  expected_def constant text := 'CHECK ((platform = ANY (ARRAY['
    || '''instagram''::text, ''tiktok''::text, ''youtube''::text, '
    || '''vk''::text, ''telegram''::text, ''wildberries''::text])))';
begin
  select pg_get_constraintdef(con.oid)
    into constraint_def
  from pg_catalog.pg_constraint con
  join pg_catalog.pg_class rel on rel.oid = con.conrelid
  join pg_catalog.pg_namespace nsp on nsp.oid = rel.relnamespace
  where nsp.nspname = 'content_factory'
    and rel.relname = 'placements'
    and con.conname = 'placements_platform_check';
  if constraint_def is null then
    raise exception using message = 'placements_platform_check_missing';
  end if;
  if position('''rutube''' in constraint_def) > 0 then
    -- Повторный прогон обязан быть тихим.
    return;
  end if;
  if constraint_def <> expected_def then
    raise exception using message =
      'placements_platform_check_anchor_invalid: ' || constraint_def;
  end if;
  alter table content_factory.placements
    drop constraint placements_platform_check;
  alter table content_factory.placements
    add constraint placements_platform_check check (
      platform in (
        'instagram', 'tiktok', 'youtube', 'vk', 'telegram',
        'wildberries', 'ozon', 'rutube', 'other'
      )
    );
end;
$platform_vocabulary$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ. Оба словаря обязаны знать все 9 платформ; расхождение
-- реестра и ведомости фактов — ровно та болезнь, которую лечит миграция.
do $verify$
declare
  placements_def text;
  accounts_def text;
  word text;
begin
  select pg_get_constraintdef(con.oid)
    into placements_def
  from pg_catalog.pg_constraint con
  join pg_catalog.pg_class rel on rel.oid = con.conrelid
  join pg_catalog.pg_namespace nsp on nsp.oid = rel.relnamespace
  where nsp.nspname = 'content_factory'
    and rel.relname = 'placements'
    and con.conname = 'placements_platform_check';
  select pg_get_constraintdef(con.oid)
    into accounts_def
  from pg_catalog.pg_constraint con
  join pg_catalog.pg_class rel on rel.oid = con.conrelid
  join pg_catalog.pg_namespace nsp on nsp.oid = rel.relnamespace
  where nsp.nspname = 'content_factory'
    and rel.relname = 'managed_accounts'
    and con.conname = 'managed_accounts_platform_vocabulary_check';
  if placements_def is null or accounts_def is null then
    raise exception using message = 'platform_vocabulary_constraint_missing';
  end if;
  foreach word in array array[
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram',
    'wildberries', 'ozon', 'rutube', 'other'
  ]
  loop
    if position('''' || word || '''' in placements_def) = 0
       or position('''' || word || '''' in accounts_def) = 0 then
      raise exception using message =
        'platform_vocabulary_mismatch: ' || word;
    end if;
  end loop;
end;
$verify$;

commit;
