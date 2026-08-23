begin;

-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и любой комментарий перед BEGIN
-- отвергает не только этот файл, но и всю цепочку миграций разом. Поэтому
-- «почему» живёт внутри транзакции.
--
-- 202608190001_generation_strategy_bind_retry_idempotency_v1
--
-- Повторная привязка с новым ключом идемпотентности перестаёт быть конфликтом.
--
-- Было так: подпись запроса считается от ВСЕГО payload, включая
-- idempotency_key, а при повторной привязке требуется её совпадение. Портал
-- выдаёт новый ключ на каждый клик, поэтому первая привязка проходила, а любая
-- следующая по той же строке была обречена навсегда — наружу это выглядело как
-- «сервис временно недоступен», без объяснения и без шанса повторить.
--
-- Это переворачивает смысл идемпотентности: ключ, который должен делать повтор
-- безопасным, делал его невозможным. Содержательные поля при этом совпадали
-- буква в букву.
--
-- Стало так: конфликтом считается расхождение СОДЕРЖАНИЯ — подписи снимка,
-- выбора и цены. Ключ запроса из условия убран: он опознаёт попытку, а не
-- намерение. Если содержание совпало, возвращается прежний результат, как и
-- задумано для повторного вызова.
--
-- Денежный контур не ослаблен: привязка бесплатна, а платный шаг защищён
-- отдельно — своей квитанцией готовности, подтверждением траты и проверкой
-- контура сотрудника.

create or replace function content_factory_private.migration_patch_once(
  p_source text, p_search text, p_replace text, p_tag text
)
returns text
language plpgsql
immutable
as $$
declare
  hits integer;
begin
  hits := (length(p_source) - length(replace(p_source, p_search, '')))
    / length(p_search);
  if hits <> 1 then
    raise exception using
      message = 'patch_anchor_not_unique:' || p_tag || ':' || hits::text;
  end if;
  return replace(p_source, p_search, p_replace);
end;
$$;

do $patch_bind_retry$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_resolve_and_bind_generation_strategy';
  if definition_value is null then
    raise exception using message = 'resolve_bind_missing';
  end if;

  -- Цель правки одна: убрать сравнение ключа запроса. Но текст тела функции
  -- зависит от того, как база его вернула, поэтому вместо точного совпадения
  -- целого условия убирается ровно одна строка сравнения. Если её уже нет —
  -- работа сделана раньше, и это не ошибка, а признак повторной сборки.
  if position(
       'or existing_row.request_hash <> request_hash_value' in definition_value
     ) > 0 then
    patched_value := content_factory_private.migration_patch_once(
      definition_value,
      $s$
       or existing_row.request_hash <> request_hash_value$s$,
      $r$$r$,
      'resolve_bind.retry_conflict'
    );
    execute patched_value;
  elsif position(
      'existing_row.snapshot_hash <> snapshot_hash_value' in definition_value
    ) = 0 then
    -- Ни старой формы, ни ожидаемой — значит функция не та, что мы правим.
    raise exception using message = 'resolve_bind_shape_unknown';
  end if;
end;
$patch_bind_retry$;

drop function content_factory_private.migration_patch_once(text, text, text, text);

do $bind_retry_verify$
declare
  definition_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_resolve_and_bind_generation_strategy';

  if position('existing_row.request_hash <> request_hash_value' in definition_value) > 0 then
    raise exception using message = 'request_hash_still_in_conflict_check';
  end if;
  if position('existing_row.snapshot_hash <> snapshot_hash_value' in definition_value) = 0
     or position('existing_row.selection_snapshot <> selection_value' in definition_value) = 0
     or position('existing_row.price_snapshot <> price_value' in definition_value) = 0 then
    raise exception using message = 'content_checks_lost';
  end if;
  -- Строка запроса по-прежнему пишется: она нужна для разбора инцидентов.
  if position('request_hash_value := content_factory_private.json_hash(p_payload)' in definition_value) = 0 then
    raise exception using message = 'request_hash_no_longer_recorded';
  end if;
  if exists (
    select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private' and p.proname = 'migration_patch_once'
  ) then
    raise exception using message = 'migration_helper_left_behind';
  end if;
end;
$bind_retry_verify$;

commit;
