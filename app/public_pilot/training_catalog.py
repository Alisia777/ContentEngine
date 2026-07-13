"""Versioned onboarding curriculum for every cloud workspace member.

The answer key lives only on the server.  The final exam intentionally uses
scenario questions that combine portal navigation, quality, publishing,
platform policy, attribution, and money-safety rules.
"""

ONBOARDING_PREREQUISITE_CODES: tuple[str, ...] = (
    "contentengine_overview",
    "review_qa",
    "publishing_manual_upload",
    "platform_rules",
)
ONBOARDING_EXAM_CODE = "portal_operator_exam"


PUBLIC_PILOT_TRAINING_MODULES: list[dict] = [
    {
        "code": "contentengine_overview",
        "title": "Портал: от задачи до результата",
        "description": "Как работать в облачном Контент ИИ Заводе и не терять прослеживаемость.",
        "order_index": 10,
        "required_for_roles": ["owner", "admin", "producer", "reviewer", "operator", "trainee", "viewer"],
        "required_for_permissions": ["workspace_access"],
        "lessons": [
            {
                "title": "Путь одного ролика",
                "content_markdown": "Откройте свою задачу, сверьте SKU и дедлайн. Товар, исходники, генерация, QA, публикация, final URL и метрики должны оставаться одним циклом.",
            },
            {
                "title": "Что делает человек",
                "content_markdown": "ИИ помогает с материалами. Исполнитель проверяет точный товар, права, обещания, площадку и факт публикации. Опасные действия нельзя подтверждать не читая.",
            },
        ],
        "questions": [
            {
                "question_text": "Задача показывает SKU A, а в папке лежат фото SKU B. Что делать?",
                "question_type": "single_choice",
                "options": ["Взять похожие фото", "Изменить SKU в отчёте", "Остановиться и запросить точные материалы", "Запустить тестовый ролик"],
                "correct_answer": ["Остановиться и запросить точные материалы"],
                "explanation": "SKU и вариант товара нельзя подменять.",
            },
        ],
    },
    {
        "code": "review_qa",
        "title": "Качество: проверка реального MP4",
        "description": "Товар, упаковка, обещания, артефакты и решение о пересоздании.",
        "order_index": 20,
        "required_for_roles": ["owner", "admin", "producer", "reviewer", "operator", "trainee", "viewer"],
        "required_for_permissions": ["output_review", "video_approve", "video_reject", "workspace_access"],
        "lessons": [
            {
                "title": "Файл создан — ещё не значит одобрен",
                "content_markdown": "Просмотрите весь MP4. Сверьте форму, цвет, текст и геометрию товара, естественность сцены, безопасность обещаний и CTA. Любая подмена товара блокирует публикацию.",
            }
        ],
        "questions": [
            {
                "question_text": "Провайдер пометил task как SUCCEEDED, но на кадрах другая упаковка. Решение?",
                "question_type": "single_choice",
                "options": ["Одобрить", "Опубликовать с пометкой", "Вернуть на пересоздание и закрыть публикацию", "Скрыть кадр"],
                "correct_answer": ["Вернуть на пересоздание и закрыть публикацию"],
                "explanation": "Успех API не равен визуальному QA.",
            },
            {
                "question_text": "Что обязательно перед approve?",
                "question_type": "multi_select",
                "options": ["Посмотреть весь MP4", "Сверить товар и упаковку", "Проверить обещания и CTA", "Дождаться 1000 просмотров"],
                "correct_answer": ["Посмотреть весь MP4", "Сверить товар и упаковку", "Проверить обещания и CTA"],
                "explanation": "Решение о качестве принимается до публикации.",
            },
        ],
    },
    {
        "code": "publishing_manual_upload",
        "title": "Публикация: placement и прослеживаемость",
        "description": "Как опубликовать одобренный ролик на назначенную площадку и вернуть final URL.",
        "order_index": 30,
        "required_for_roles": ["owner", "admin", "producer", "reviewer", "operator", "trainee", "viewer"],
        "required_for_permissions": ["publishing_approve", "metrics_import", "workspace_access"],
        "lessons": [
            {
                "title": "Tracking link и final URL решают разные задачи",
                "content_markdown": "Tracking link из задачи считает переходы. Final URL доказывает, что пост реально опубликован на нужной площадке. Оба значения нужны для метрик и выплат.",
            }
        ],
        "questions": [
            {
                "question_text": "Ролик approved, но в задаче нет destination. Что делать?",
                "question_type": "single_choice",
                "options": ["Выбрать любой аккаунт", "Отправить коллеге", "Запросить назначение площадки", "Вставить ссылку на товар вместо tracking link"],
                "correct_answer": ["Запросить назначение площадки"],
                "explanation": "Публиковать можно только на назначенную собственную площадку.",
            },
            {
                "question_text": "Какие два факта нужно вернуть после ручной публикации?",
                "question_type": "multi_select",
                "options": ["Final URL поста", "Tracking link из задачи", "Пароль от сети", "API token"],
                "correct_answer": ["Final URL поста", "Tracking link из задачи"],
                "explanation": "Секреты не передаются через задачу.",
            },
        ],
    },
    {
        "code": "platform_rules",
        "title": "Правила площадок и безопасные данные",
        "description": "Instagram, TikTok, YouTube, Telegram, VK и marketplace: права, claims, метрики и секреты.",
        "order_index": 40,
        "required_for_roles": ["owner", "admin", "producer", "reviewer", "operator", "trainee", "viewer"],
        "required_for_permissions": ["workspace_access"],
        "lessons": [
            {
                "title": "Единый безопасный минимум",
                "content_markdown": "Используйте только одобренные материалы и свои площадки. Не публикуйте медицинские, финансовые или абсолютные обещания без подтверждённого claims review. OAuth tokens и API keys не вставляются в формы или чаты.",
            },
            {
                "title": "Откуда брать цифры",
                "content_markdown": "Приоритет — официальный API. Если адаптера нет, используйте явно помеченный CSV/ручной cumulative snapshot. Не скрапьте закрытые кабинеты и не выдавайте ручные цифры за API.",
            },
        ],
        "questions": [
            {
                "question_text": "Для Telegram нет production metrics adapter. Как внести данны?",
                "question_type": "single_choice",
                "options": ["Придумать API response", "Скрапить чужой кабинет", "Внести явно помеченный CSV/ручной снимок", "Не связывать с final URL"],
                "correct_answer": ["Внести явно помеченный CSV/ручной снимок"],
                "explanation": "Ручной fallback допустим, если его источник не скрыт.",
            },
            {
                "question_text": "Где можно вставить OAuth access token?",
                "question_type": "single_choice",
                "options": ["В комментарий задачи", "В final URL", "Только в защищённый secret store/окружение", "В название папки"],
                "correct_answer": ["Только в защищённый secret store/окружение"],
                "explanation": "Портал хранит ссылку на секрет, не сам токен.",
            },
        ],
    },
    {
        "code": ONBOARDING_EXAM_CODE,
        "title": "Итоговый экзамен оператора портала",
        "description": "12 рабочих сценариев. Нужно не менее 80%, чтобы открыть workspace.",
        "order_index": 100,
        "required_for_roles": ["owner", "admin", "producer", "reviewer", "operator", "trainee", "viewer"],
        "required_for_permissions": ["workspace_access"],
        "lessons": [
            {
                "title": "Перед экзаменом",
                "content_markdown": "Экзамен объединяет навигацию, QA, placement, правила сетей, метрики, выплаты и paid generation. Выбирайте безопасное и прослеживаемое действие, а не самое быстрое.",
            }
        ],
        "questions": [
            {
                "question_text": "1. Вам назначен ролик для шампуня 250 мл, но на фото флакон 400 мл. Ваш шаг?",
                "question_type": "single_choice",
                "options": ["Продолжить с пометкой", "Отредактировать цифру на кадре", "Заблокировать и запросить точные фото SKU", "Сменить SKU в задаче"],
                "correct_answer": ["Заблокировать и запросить точные фото SKU"],
                "explanation": "Точная идентичность товара обязательна.",
            },
            {
                "question_text": "2. Видео скачано, CV-check зелёный, но вы ещё не смотрели MP4. Можно approve?",
                "question_type": "single_choice",
                "options": ["Да", "Да, если нет OCR ошибок", "Нет, нужен полный human review", "Можно сразу publish"],
                "correct_answer": ["Нет, нужен полный human review"],
                "explanation": "Автоматический сигнал не заменяет просмотр.",
            },
            {
                "question_text": "3. Пост нужно выло разместить в Instagram, но он опубликован в TikTok. Что фиксировать?",
                "question_type": "single_choice",
                "options": ["Успех", "Новый destination задним числом", "Ошибку площадки и не завершать исходную задачу", "Только просмотры"],
                "correct_answer": ["Ошибку площадки и не завершать исходную задачу"],
                "explanation": "Destination — часть assignment.",
            },
            {
                "question_text": "4. Пост опубликован, но final URL не сохранён. Что верно?",
                "question_type": "single_choice",
                "options": ["Задача завершена", "Можно считать payout", "Нет доказательства публикации; задача не завершена", "Достаточно скриншота"],
                "correct_answer": ["Нет доказательства публикации; задача не завершена"],
                "explanation": "Final URL связывает реальный пост с задачей.",
            },
            {
                "question_text": "5. Вы вносите статистику второй раз. Как указать views?",
                "question_type": "single_choice",
                "options": ["Прибавка за день", "Накопительное значение на конец периода", "Прогноз", "Среднее по аккаунту"],
                "correct_answer": ["Накопительное значение на конец периода"],
                "explanation": "Cumulative snapshot заменяет предыдущий, а не суммируется с ним.",
            },
            {
                "question_text": "6. OAuth не настроен, но менеджер прислал CSV из кабинета. Как поступить?",
                "question_type": "single_choice",
                "options": ["Назвать его API sync", "Загрузить как явный CSV/manual source и проверить связь с постом", "Вставить token в CSV", "Отклонить любой CSV"],
                "correct_answer": ["Загрузить как явный CSV/manual source и проверить связь с постом"],
                "explanation": "Источник данных должен быть честно обозначен.",
            },
            {
                "question_text": "7. Креатив обещает «гарантированно вылечит кожу», а claims approval нет. Решение?",
                "question_type": "single_choice",
                "options": ["Опубликовать в личном аккаунте", "Убрать звук", "Заблокировать и вернуть на claims review/переписывание", "Добавить мелкий disclaimer"],
                "correct_answer": ["Заблокировать и вернуть на claims review/переписывание"],
                "explanation": "Неподтверждённые medical claims блокируют placement.",
            },
            {
                "question_text": "8. Что можно передать в комментарии задачи?",
                "question_type": "single_choice",
                "options": ["OAuth token", "API key", "Понятное описание блокера без секретов", "Пароль аккаунта"],
                "correct_answer": ["Понятное описание блокера без секретов"],
                "explanation": "Секреты хранятся только в secret store.",
            },
            {
                "question_text": "9. Paid generation уже отправлена, но ответ провайдера потерян. Что делать?",
                "question_type": "single_choice",
                "options": ["Нажать run ещё раз", "Создать новый draft", "Сверить provider task/quarantine и не делать второй paid submit", "Списать расход дважды"],
                "correct_answer": ["Сверить provider task/quarantine и не делать второй paid submit"],
                "explanation": "Неопределённый исход требует сверки, а не повтора.",
            },
            {
                "question_text": "10. Можно ли отметить payout за опубликованный пост, если нет final URL?",
                "question_type": "single_choice",
                "options": ["Да, по словам исполнителя", "Да, если есть видео", "Нет, выплате нужна точная доказательная цепочка", "Да, если сумма мала"],
                "correct_answer": ["Нет, выплате нужна точная доказательная цепочка"],
                "explanation": "Выплата должна опираться на assignment и проверяемый результат.",
            },
            {
                "question_text": "11. Какие сигналы достаточны для привязки метрик к посту?",
                "question_type": "multi_select",
                "options": ["Final/posted URL", "Tracking slug из задачи", "Только SKU", "Примерное время"],
                "correct_answer": ["Final/posted URL", "Tracking slug из задачи"],
                "explanation": "SKU и время без ссылки неоднозначны.",
            },
            {
                "question_text": "12. В задаче нет важного файла, дедлайн через 20 минут. Лучшее действие?",
                "question_type": "single_choice",
                "options": ["Заменить файл похожим", "Отметить ready", "Зафиксировать блокер и запросить нужный файл", "Опубликовать без него"],
                "correct_answer": ["Зафиксировать блокер и запросить нужный файл"],
                "explanation": "Дедлайн не отменяет точность и правила.",
            },
        ],
    },
]
