begin;

-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и любой комментарий перед BEGIN
-- отвергает не только этот файл, но и всю цепочку миграций разом. Поэтому
-- «почему» живёт внутри транзакции.
--
-- 202608190004_working_draft_revision_conflict_terminal_code_v1
--
-- Конфликт ревизии рабочего черновика перестаёт притворяться ошибкой
-- сериализации.
--
-- ПОЧЕМУ. Код 40001 зарезервирован под ошибки сериализации, и обработчик
-- запросов PostgREST повторяет такие запросы сам: считается, что при повторе
-- транзакция разойдётся с соседкой и пройдёт. Но устаревший токен
-- оптимистической блокировки — терминальный конфликт: сколько ни повторяй,
-- ревизия у клиента свежее не станет, и повтор обречён с первой же попытки.
-- Одна залипшая вкладка браузера удерживала бэкенд в бесконечном цикле
-- повторов вместо честного отказа. PT409 сохраняет для клиента ровно тот же
-- смысл конфликта, но в цикл повторов не попадает.
--
-- ПОЧЕМУ ОТДЕЛЬНОЙ МИГРАЦИЕЙ, А НЕ ПРАВКОЙ НА МЕСТЕ. Эта правка была сделана
-- прямо в 202608110006_ai_research_generation_working_draft.sql. Но та
-- миграция уже применена в проде, и её отпечаток записан в
-- contentengine_deploy.schema_migrations. Загрузчик сверяет sha256 каждого
-- применённого файла и на расхождении падает с «Immutable checksum mismatch»
-- ДО первой записи — то есть блокирует не только эту правку, а весь деплой
-- целиком. Применённый файл неизменен по определению; смысл правки
-- возвращается только вперёд, отдельной миграцией.
--
-- ПОЧЕМУ ЯКОРЬ ОПОЗНАЁТСЯ В ТРЁХ ФОРМАХ. 202608160001 уже правил живое
-- определение сплошной заменой «errcode = '40001'» на «errcode = 'PT409'» по
-- всему телу функции. Поэтому в базе функция может оказаться в одной из трёх
-- форм: исходной (40001), пропатченной (PT409 без объяснения) и целевой
-- (PT409 с объяснением). Единственность якоря доказывается по строке
-- сообщения конфликта — она в теле ровно одна и от кода ошибки не зависит;
-- форма опознаётся уже вокруг доказанного якоря. Из-за этого миграция
-- идемпотентна: повторный прогон на целевой форме не меняет ничего.
--
-- ПОЧЕМУ ОБЪЯСНЕНИЕ УЕЗЖАЕТ В ТЕЛО ФУНКЦИИ. Код ошибки без причины рядом
-- выглядит опечаткой, и следующий, кто будет переписывать этот RAISE, вернёт
-- 40001 обратно. Комментарий вписан в тело по-английски — как весь остальной
-- текст 202608110006, чтобы функция читалась на одном языке.
--
-- ПОЧЕМУ ТЕЛО НОРМАЛИЗУЕТСЯ ПО ПЕРЕВОДАМ СТРОК. pg_get_functiondef отдаёт
-- тело ровно теми байтами, какими его записала миграция-родитель. Если тот
-- файл лежал в репозитории с CRLF, в теле остаются \r, и многострочный якорь
-- с одними \n не совпадает НИ РАЗУ — молча, без диагностики. Оба родителя
-- этой функции (202608110006 и 202608160001) в LF, но полагаться на это
-- нельзя: правка кодировки соседнего файла не должна ронять миграцию.
-- Нормализация делает якорь нечувствительным к переводам строк, как это уже
-- сделано в 202608130008.

do $working_draft_conflict_terminal_code$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  -- Сообщение конфликта: единственная строка тела, по которой доказывается
  -- единственность места правки.
  conflict_anchor constant text :=
    $anchor$      message = 'generation_ai_research_working_draft_revision_conflict',$anchor$;
  -- Исходная форма из 202608110006.
  retryable_form constant text := $retryable$    raise exception using
      errcode = '40001',
      message = 'generation_ai_research_working_draft_revision_conflict',$retryable$;
  -- След 202608160001: код уже терминальный, но причина нигде не записана.
  undocumented_form constant text := $undocumented$    raise exception using
      errcode = 'PT409',
      message = 'generation_ai_research_working_draft_revision_conflict',$undocumented$;
  -- Целевая форма: терминальный код и причина рядом с ним.
  terminal_form constant text := $terminal$    raise exception using
      -- 40001 is reserved for serialization failures and is retried by the
      -- PostgREST transaction runner. A stale optimistic-concurrency token is
      -- a terminal HTTP conflict, so it must never enter that retry loop.
      errcode = 'PT409',
      message = 'generation_ai_research_working_draft_revision_conflict',$terminal$;
begin
  select replace(
    pg_get_functiondef(
      'public.contentengine_generation_ai_research_working_draft(jsonb)'
        ::regprocedure
    ),
    E'\r\n',
    E'\n'
  )
  into definition_value;
  if definition_value is null then
    raise exception using message = 'working_draft_rpc_missing';
  end if;

  anchor_hits := (
    length(definition_value)
      - length(replace(definition_value, conflict_anchor, ''))
  ) / length(conflict_anchor);
  if anchor_hits <> 1 then
    raise exception using
      message = 'working_draft_conflict_anchor_not_unique:' || anchor_hits::text;
  end if;

  if position(terminal_form in definition_value) > 0 then
    -- Уже целевая форма — правка не нужна, но и падать не за что.
    patched_value := definition_value;
  elsif position(retryable_form in definition_value) > 0 then
    patched_value := replace(definition_value, retryable_form, terminal_form);
  elsif position(undocumented_form in definition_value) > 0 then
    patched_value := replace(definition_value, undocumented_form, terminal_form);
  else
    -- Тело разошлось со всеми тремя известными формами: замена вслепую
    -- опаснее отказа, поэтому миграция падает и откатывает транзакцию целиком.
    raise exception using message = 'working_draft_conflict_form_unknown';
  end if;

  if position(terminal_form in patched_value) = 0
     or position(retryable_form in patched_value) > 0 then
    raise exception using message = 'working_draft_conflict_patch_did_not_take';
  end if;

  execute patched_value;
end;
$working_draft_conflict_terminal_code$;

comment on function
  public.contentengine_generation_ai_research_working_draft(jsonb) is
  'Project-shared, CAS-protected AI research working draft. Revision conflicts return terminal HTTP 409 and never use retryable SQLSTATE 40001.';

do $working_draft_conflict_terminal_code_verify$
declare
  definition_value text;
begin
  -- Здесь тело НАМЕРЕННО не нормализуется: проверка обязана видеть ровно те
  -- байты, что легли в базу. Многострочный якорь ниже совпадёт только если
  -- записанное тело действительно на LF, — а значит и следующая миграция,
  -- которая станет его патчить, не наступит на те же \r.
  select pg_get_functiondef(
    'public.contentengine_generation_ai_research_working_draft(jsonb)'
      ::regprocedure
  )
  into definition_value;
  if definition_value is null then
    raise exception using message = 'verify_working_draft_rpc_missing';
  end if;

  -- Новый код стоит именно у конфликта ревизии, а не где-то ещё в теле.
  if position($verify_terminal$      errcode = 'PT409',
      message = 'generation_ai_research_working_draft_revision_conflict',$verify_terminal$
       in definition_value) = 0 then
    raise exception using message = 'verify_conflict_code_not_terminal';
  end if;

  -- Старого кода в теле больше нет вообще.
  if position($verify_retryable$errcode = '40001'$verify_retryable$
       in definition_value) > 0 then
    raise exception using message = 'verify_retryable_code_left';
  end if;

  -- Причина осталась рядом с кодом, а не только в этом файле.
  if position(
       'is reserved for serialization failures' in definition_value
     ) = 0
     or position(
       'must never enter that retry loop' in definition_value
     ) = 0 then
    raise exception using message = 'verify_reason_comment_missing';
  end if;

  -- Кроме кода ошибки в этом RAISE ничего не потеряно: сообщение и обе
  -- ревизии в detail по-прежнему на месте.
  if position(
       $verify_detail$'expected_revision', expected_revision_value$verify_detail$
       in definition_value
     ) = 0
     or position(
       $verify_detail$'current_revision', coalesce(current_row.revision, 0)$verify_detail$
       in definition_value
     ) = 0 then
    raise exception using message = 'verify_conflict_detail_lost';
  end if;
end;
$working_draft_conflict_terminal_code_verify$;

commit;
