begin;

insert into content_factory.training_modules (
  code, module_type, title, description, order_index,
  pass_score, question_count, content, is_active
)
values
(
  'factory_basics',
  'course',
  'Контент ИИ Завод: один измеримый цикл',
  'Как пройти путь от точного товара и исходников до проверенного ролика, размещения и фактической метрики.',
  10, 1, 0,
  jsonb_build_object(
    'version', 1,
    'lessons', jsonb_build_array(
      jsonb_build_object(
        'title', 'Сначала точный SKU',
        'body', 'Работа начинается только после сверки SKU, варианта, упаковки и разрешённых исходников. Похожий товар нельзя выдавать за нужный.'
      ),
      jsonb_build_object(
        'title', 'Один ролик — одна цепочка данных',
        'body', 'Товар, задача, генерация, QA, публикация, final URL, tracking и метрики должны оставаться связанными одним циклом.'
      ),
      jsonb_build_object(
        'title', 'Безопасный режим запуска',
        'body', 'Пока платный ИИ выключен, разрешены только mock и dry-run. Интерфейс не может самостоятельно включить расход.'
      )
    )
  ),
  true
),
(
  'video_quality',
  'course',
  'Качество: проверка реального видео',
  'Как смотреть весь результат, находить подмену товара, артефакты, опасные обещания и принимать воспроизводимое QA-решение.',
  20, 1, 0,
  jsonb_build_object(
    'version', 1,
    'lessons', jsonb_build_array(
      jsonb_build_object(
        'title', 'SUCCEEDED не означает APPROVED',
        'body', 'Технический успех провайдера означает только наличие файла. Человек обязан посмотреть весь MP4 и сверить товар, упаковку, смысл и CTA.'
      ),
      jsonb_build_object(
        'title', 'Подмена товара блокирует публикацию',
        'body', 'Неверная форма, цвет, маркировка или вариант — причина отклонить ролик и вернуть его на пересоздание.'
      ),
      jsonb_build_object(
        'title', 'Решение должно иметь доказательство',
        'body', 'Approve и reject привязываются к конкретному файлу и его контрольной сумме; заменённый файл требует новой проверки.'
      )
    )
  ),
  true
),
(
  'publishing_funnel',
  'course',
  'Размещение, воронка и выплаты',
  'Как публиковать только на назначенной площадке, возвращать final URL, фиксировать накопительные метрики и не путать факт работы с оплатой.',
  30, 1, 0,
  jsonb_build_object(
    'version', 1,
    'lessons', jsonb_build_array(
      jsonb_build_object(
        'title', 'Назначенная площадка обязательна',
        'body', 'Одобренный ролик публикуется только в назначенный аккаунт. Если назначения нет, задача останавливается.'
      ),
      jsonb_build_object(
        'title', 'Final URL и tracking решают разные задачи',
        'body', 'Final URL доказывает публикацию, tracking link связывает переходы и продажи с циклом. Нужны оба факта.'
      ),
      jsonb_build_object(
        'title', 'Метрики и выплаты проверяются',
        'body', 'Цифры поступают из официального API или явно помеченного ручного/CSV-снимка. Выплату подтверждает другой уполномоченный участник.'
      )
    )
  ),
  true
),
(
  'security_wb',
  'course',
  'Безопасность, площадки и подменные артикулы WB',
  'Как не передавать секреты, соблюдать правила площадок и связывать исторические или подменные артикулы Wildberries с точным товаром.',
  40, 1, 0,
  jsonb_build_object(
    'version', 1,
    'lessons', jsonb_build_array(
      jsonb_build_object(
        'title', 'Секреты не входят в рабочую задачу',
        'body', 'Пароли, OAuth-токены, API keys и service-role keys не вставляются в формы, комментарии, Git или чат.'
      ),
      jsonb_build_object(
        'title', 'Правила площадки сильнее плана публикаций',
        'body', 'Нет прав на материал, есть запрещённое обещание или неподтверждённый claim — публикация блокируется.'
      ),
      jsonb_build_object(
        'title', 'Артикул — идентификатор, а не догадка',
        'body', 'Подменный или старый WB-артикул хранится как датированная связь с каноническим товаром. Историю нельзя переписывать задним числом.'
      )
    )
  ),
  true
),
(
  'operator_final_exam',
  'exam',
  'Итоговый сценарный экзамен оператора',
  'Двенадцать сложных ситуаций по товару, качеству, размещению, данным, деньгам и безопасности. Для допуска нужно не менее 10 правильных ответов.',
  50, 10, 12,
  jsonb_build_object(
    'version', 1,
    'cooldown_minutes', 15,
    'instructions', 'Ответьте на все 12 сценариев. Правильные ответы и разбор не выдаются через браузер.'
  ),
  true
)
on conflict (code) do update set
  module_type = excluded.module_type,
  title = excluded.title,
  description = excluded.description,
  order_index = excluded.order_index,
  pass_score = excluded.pass_score,
  question_count = excluded.question_count,
  content = excluded.content,
  is_active = excluded.is_active,
  updated_at = now();

insert into content_factory.training_questions (
  code, module_code, question_type, prompt, options, order_index
)
values
(
  'exam_sku_mismatch', 'operator_final_exam', 'single_choice',
  'В задаче указан SKU A, но в папке лежат фотографии похожего SKU B. Дедлайн через час. Как действовать?',
  jsonb_build_array(
    'Использовать похожие фото и отметить это после публикации',
    'Переименовать SKU B в отчёте',
    'Остановить задачу и запросить точные материалы SKU A',
    'Сделать один тестовый ролик без проверки'
  ), 10
),
(
  'exam_provider_wrong_pack', 'operator_final_exam', 'single_choice',
  'Провайдер вернул статус SUCCEEDED, но на нескольких кадрах упаковка другого варианта. Что является правильным решением?',
  jsonb_build_array(
    'Одобрить, потому что API завершился успешно',
    'Опубликовать с предупреждением в описании',
    'Отклонить конкретный файл и вернуть на пересоздание',
    'Скрыть неверные кадры обложкой'
  ), 20
),
(
  'exam_qa_requirements', 'operator_final_exam', 'multi_select',
  'Что обязательно сделать перед одобрением готового видео? Выберите все необходимые действия.',
  jsonb_build_array(
    'Посмотреть MP4 полностью',
    'Сверить товар и упаковку с точными исходниками',
    'Проверить обещания, текст и CTA',
    'Дождаться 1000 просмотров'
  ), 30
),
(
  'exam_missing_destination', 'operator_final_exam', 'single_choice',
  'Видео одобрено, но в задаче нет назначенной площадки или аккаунта. Что делать?',
  jsonb_build_array(
    'Выбрать любой доступный аккаунт',
    'Передать ролик коллеге без фиксации',
    'Остановиться и запросить назначение площадки',
    'Опубликовать в личном аккаунте'
  ), 40
),
(
  'exam_publication_evidence', 'operator_final_exam', 'multi_select',
  'Какие данные нужно вернуть в систему после ручной публикации, чтобы цикл оставался измеримым?',
  jsonb_build_array(
    'Публичный final URL поста',
    'Tracking link из назначенной задачи',
    'Пароль от социальной сети',
    'OAuth access token'
  ), 50
),
(
  'exam_metrics_source', 'operator_final_exam', 'single_choice',
  'Официальный коннектор временно недоступен, а руководителю нужны цифры сегодня. Как сохранить данные корректно?',
  jsonb_build_array(
    'Ввести накопительный ручной или CSV-снимок с явной маркировкой источника и времени',
    'Назвать приблизительные цифры результатом API',
    'Передать пароль аналитику для скрейпинга кабинета',
    'Скопировать цифры конкурента'
  ), 60
),
(
  'exam_secret_request', 'operator_final_exam', 'single_choice',
  'В комментарии к задаче попросили вставить OAuth-токен, чтобы коллега быстрее подключил площадку. Ваше действие?',
  jsonb_build_array(
    'Вставить токен и удалить комментарий позже',
    'Отправить токен личным сообщением',
    'Не передавать секрет, остановить действие и сообщить владельцу безопасного контура',
    'Сохранить токен в названии файла'
  ), 70
),
(
  'exam_real_spend_disabled', 'operator_final_exam', 'single_choice',
  'В интерфейсе появился путь запустить реального видеопровайдера, но владелец не включал платную генерацию. Что делать?',
  jsonb_build_array(
    'Запустить один ролик — это не считается расходом',
    'Остаться в mock/dry-run и запросить отдельное разрешение владельца на spend gate',
    'Разделить запуск на несколько маленьких задач',
    'Подставить личный API key'
  ), 80
),
(
  'exam_wb_alias_history', 'operator_final_exam', 'single_choice',
  'Wildberries заменил артикул карточки. Новые метрики пришли по подменному артикулу, а старые — по прежнему. Как поступить?',
  jsonb_build_array(
    'Переписать старые записи на новый артикул без истории',
    'Создать датированную alias-связь обоих артикулов с каноническим товаром',
    'Создать случайный новый SKU',
    'Сложить метрики с любым товаром того же бренда'
  ), 90
),
(
  'exam_payout_separation', 'operator_final_exam', 'single_choice',
  'Креатор завершил задачу и приложил ссылку. Когда выплату можно считать подтверждённой?',
  jsonb_build_array(
    'Сразу после отметки самого креатора',
    'После проверки доказательства и решения уполномоченного owner/admin',
    'После любого комментария в чате',
    'До публикации, если ролик выглядит хорошо'
  ), 100
),
(
  'exam_platform_claims', 'operator_final_exam', 'multi_select',
  'Какие ситуации должны остановить публикацию независимо от дедлайна? Выберите все применимые.',
  jsonb_build_array(
    'Нет подтверждённых прав на исходник',
    'В ролике есть неподтверждённое медицинское обещание',
    'Фактический товар отличается от задания',
    'В календаре свободно другое время'
  ), 110
),
(
  'exam_idempotent_retry', 'operator_final_exam', 'single_choice',
  'После сетевой ошибки неизвестно, создалась ли массовая партия. Как избежать дублей при повторе?',
  jsonb_build_array(
    'Создать новый idempotency key и повторить несколько раз',
    'Повторить тот же запрос с тем же idempotency key и проверить сохранённый результат',
    'Удалить все задачи команды',
    'Увеличить количество роликов'
  ), 120
)
on conflict (code) do update set
  module_code = excluded.module_code,
  question_type = excluded.question_type,
  prompt = excluded.prompt,
  options = excluded.options,
  order_index = excluded.order_index,
  updated_at = now();


do $catalog_contract$
declare
  course_total integer;
  exam_total integer;
begin
  select count(*) into course_total
  from content_factory.training_modules
  where module_type = 'course' and is_active;

  select count(*) into exam_total
  from content_factory.training_questions
  where module_code = 'operator_final_exam';

  if course_total <> 4 or exam_total <> 12 then
    raise exception using
      errcode = '23514',
      message = 'training_catalog_contract_failed',
      detail = format(
        'Expected 4 courses and 12 exam questions; got %s and %s.',
        course_total, exam_total
      );
  end if;
end;
$catalog_contract$;

commit;
