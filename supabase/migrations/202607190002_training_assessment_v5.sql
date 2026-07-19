begin;

-- Assessment v5 replaces click-through mini quizzes with scenario work.
-- Correct and critical answers stay in the private schema; the browser receives
-- only the case, response options and the requirement to explain the decision.
alter table content_factory_private.training_answer_keys
  add column if not exists critical_answers jsonb not null default '[]'::jsonb;

alter table content_factory_private.training_answer_keys
  drop constraint if exists training_answer_keys_critical_answers_check;

alter table content_factory_private.training_answer_keys
  add constraint training_answer_keys_critical_answers_check check (
    jsonb_typeof(critical_answers) = 'array'
    and jsonb_array_length(critical_answers) <= 12
  );

alter table content_factory.training_attempts
  add column if not exists rationales jsonb not null default '{}'::jsonb;

alter table content_factory.training_attempts
  add column if not exists assessment_version integer not null default 1;

alter table content_factory.training_attempts
  drop constraint if exists training_attempts_assessment_version_check;

alter table content_factory.training_attempts
  add constraint training_attempts_assessment_version_check check (
    assessment_version between 1 and 100
  );

alter table content_factory.training_attempts
  drop constraint if exists training_attempts_rationales_check;

alter table content_factory.training_attempts
  add constraint training_attempts_rationales_check check (
    jsonb_typeof(rationales) = 'object'
    and length(rationales::text) <= 16000
  );

create temporary table training_assessment_v5_catalog (
  module_code text primary key,
  title text not null,
  role_hint text not null,
  pass_score integer not null,
  questions jsonb not null
) on commit drop;

insert into training_assessment_v5_catalog (
  module_code,
  title,
  role_hint,
  pass_score,
  questions
) values
(
  'factory_basics',
  'Рабочая смена в портале: решения под риском',
  'Шесть связанных ситуаций. Нужно выбрать точный маршрут, а затем своими словами назвать риск, проверку и следующий шаг.',
  5,
  $factory_questions$
  [
    {
      "id": "course_check_factory_basics_portal_registration",
      "question_type": "multi_select",
      "prompt": "У новичка истекло приглашение, а форма восстановления пишет, что адрес не найден. В задаче руководителя указан рабочий адрес, отличающийся одной буквой от введённого. Какие действия обязательны до новой попытки входа?",
      "rationale_prompt": "Объясните, как вы исключите дубль учётки и передачу доступа не тому человеку.",
      "requires_rationale": true,
      "options": [
        {"value": "invalidate_old", "label": "Считать старую ссылку недействительной и использовать только последнюю подтверждённую отправку"},
        {"value": "shared_password", "label": "Попросить коллегу открыть портал под своей учёткой только на время сверки назначения, не меняя данные"},
        {"value": "verify_exact_email", "label": "Сверить посимвольно рабочий адрес в назначении и в форме входа"},
        {"value": "duplicate_account", "label": "Завести временную учётку на личный адрес, а после смены попросить поддержку объединить её с рабочей"},
        {"value": "manager_reissue", "label": "Попросить руководителя проверить членство и перевыпустить управляемую ссылку на тот же подтверждённый адрес"}
      ],
      "lesson_id": "first_access_route",
      "remediation": "Повторите маршрут управляемого доступа: точный адрес, одна учётка, личный пароль и перевыпуск через руководителя."
    },
    {
      "id": "course_check_factory_basics_source_location",
      "question_type": "multi_select",
      "prompt": "В «Материалах» лежат фото шоколадного протеина, ванильного протеина и старой упаковки. Задача просит шоколад 900 г, но файл называется просто final.webp. Что нужно сделать до создания ролика?",
      "rationale_prompt": "Опишите, по каким признакам свяжете задачу, товар и конкретный исходник.",
      "requires_rationale": true,
      "options": [
        {"value": "preview_source", "label": "Просмотреть исходник целиком и подтвердить, что этикетка относится к точному варианту"},
        {"value": "open_task_product", "label": "Открыть карточку задачи и сверить код, вкус, массу и актуальную упаковку"},
        {"value": "record_source", "label": "Выбрать подтверждённый файл в «Материалах», сохранив его связь с задачей"},
        {"value": "guess_product", "label": "Взять самый новый final.webp по дате файла и отложить проверку варианта до готового превью"},
        {"value": "mix_sources", "label": "Использовать крупный план нужного вкуса вместе с общим планом старой упаковки, скрыв различия кадрированием"}
      ],
      "lesson_id": "interface_map",
      "remediation": "Вернитесь к карте интерфейса и соберите непрерывную связь «задача → точный товар → разрешённый исходник»."
    },
    {
      "id": "course_check_factory_basics_paid_start",
      "question_type": "single_choice",
      "prompt": "Платный запуск на 148 ₽ готов, но на превью этикетка обрезана, а длительность стоит 10 секунд вместо 8. Руководитель написал «срочно» без отдельного подтверждения изменённой стоимости. Какое одно решение рабочее?",
      "rationale_prompt": "Назовите, что именно блокирует списание и какие параметры должны быть подтверждены повторно.",
      "requires_rationale": true,
      "options": [
        {"value": "verbal_ok", "label": "Считать «срочно» подтверждением, если стоимость не превышает ранее обсуждавшийся бюджет задачи"},
        {"value": "launch_anyway", "label": "Запустить показанную конфигурацию за 148 ₽ и после результата локально обрезать ролик до 8 секунд"},
        {"value": "stop_correct_confirm", "label": "Остановить запуск, заменить/кадрировать исходник, вернуть 8 секунд и получить подтверждение итоговой конфигурации и цены"},
        {"value": "change_after", "label": "Поставить 10 секунд в очередь как черновик и запросить подтверждение уже после появления задания у провайдера"}
      ],
      "lesson_id": "generation_modes",
      "remediation": "Повторите платный контроль: товар, исходник, режим, длительность, звук, цена и явное подтверждение до списания."
    },
    {
      "id": "course_check_factory_basics_timeout_recovery",
      "question_type": "single_choice",
      "prompt": "После нажатия платного запуска сеть оборвалась. Кнопка снова активна, но неизвестно, создалась ли задача и произошло ли списание. Что делать первым?",
      "rationale_prompt": "Объясните, как не создать дубль списания и какое доказательство будете искать.",
      "requires_rationale": true,
      "options": [
        {"value": "repeat_paid", "label": "Повторить запуск один раз с теми же параметрами: одинаковая конфигурация позволит системе объединить дубли"},
        {"value": "check_receipt", "label": "Не повторять запуск; проверить «Последние запуски», квитанцию/стоимость и статус, затем передать идентификатор руководителю при неопределённости"},
        {"value": "new_product", "label": "Создать копию задания с новой внутренней меткой и запустить её, пока первая попытка уточняется"},
        {"value": "refresh_forget", "label": "Обновить вкладку и повторить, если кнопка активна: доступность кнопки считать доказательством отсутствия списания"}
      ],
      "lesson_id": "generation_modes",
      "remediation": "Разберите восстановление после сетевого сбоя: не повторять платную команду без проверки серверной квитанции."
    },
    {
      "id": "course_check_factory_basics_quality_gate",
      "question_type": "multi_select",
      "prompt": "Генерация получила статус «Готово». При полном просмотре в середине ролика меняется цвет крышки, а финальный кадр содержит нечитаемую этикетку. Какие действия входят в правильный контроль?",
      "rationale_prompt": "Разделите технический статус файла и решение о качестве результата.",
      "requires_rationale": true,
      "options": [
        {"value": "manager_route", "label": "Передать решение по повторному платному запуску ответственному, если он нужен"},
        {"value": "publish_succeeded", "label": "Передать дальше с пометкой о дефектах: технический статус «Готово» позволяет не блокировать очередь"},
        {"value": "retain_evidence", "label": "Сохранить связь с запуском и контрольные кадры для исправления/повтора"},
        {"value": "crop_defect", "label": "Локально вырезать смену цвета и закрыть нечитаемую этикетку титром, не возвращая запуск на проверку"},
        {"value": "mark_rejected", "label": "Не передавать ролик дальше и зафиксировать конкретные дефекты качества"}
      ],
      "lesson_id": "status_and_quality",
      "remediation": "Повторите разницу между завершённой генерацией и принятым после полного просмотра результатом."
    },
    {
      "id": "course_check_factory_basics_handoff_receipt",
      "question_type": "multi_select",
      "prompt": "Смена заканчивается, а ролик ещё на проверке. Что должно остаться в портале, чтобы следующий сотрудник продолжил без догадок?",
      "rationale_prompt": "Опишите минимальную проверяемую квитанцию передачи незавершённой работы.",
      "requires_rationale": true,
      "options": [
        {"value": "next_action", "label": "Однозначный следующий шаг и сохранённые доказательства проверки"},
        {"value": "personal_notes", "label": "Скриншот экрана и пояснение в личном сообщении следующему сотруднику без записи в задаче"},
        {"value": "current_status", "label": "Текущий статус, найденные дефекты и кто принимает следующее решение"},
        {"value": "linked_ids", "label": "Точная задача, товар, исходник и идентификатор запуска"},
        {"value": "chat_only", "label": "Сводка в рабочем чате с названием товара и текущим статусом, но без идентификатора запуска"}
      ],
      "lesson_id": "factory_map",
      "remediation": "Соберите квитанцию смены внутри портала: связанные идентификаторы, статус, доказательства и следующий шаг."
    }
  ]
  $factory_questions$::jsonb
),
(
  'video_quality',
  'Съёмка и контроль ролика: практическая аттестация',
  'В каждом кейсе есть несколько правдоподобных способов «успеть». Засчитывается только воспроизводимый контроль качества и прав.',
  5,
  $video_questions$
  [
    {
      "id": "course_check_video_quality_phone_setup",
      "question_type": "multi_select",
      "prompt": "Перед съёмкой 8-секундного исходника телефон стоит вертикально, но линза в отпечатках, окно пересвечивает этикетку, холодильник гудит, а рука дрожит. Что нужно исправить до дубля?",
      "rationale_prompt": "Объясните, как каждая выбранная проверка влияет на пригодность исходника для монтажа или генерации.",
      "requires_rationale": true,
      "options": [
        {"value": "zoom_digital", "label": "Увеличить цифровой зум до заполнения кадра товаром, чтобы пересвет и фон занимали меньше площади"},
        {"value": "fix_in_filter", "label": "Снять один тестовый дубль как есть и заложить стабилизацию, шумоподавление и восстановление резкости на постобработку"},
        {"value": "soft_light", "label": "Переставить товар в мягкий ровный свет без бликов и пересвета"},
        {"value": "stabilize_audio", "label": "Зафиксировать телефон и записать короткий тест изображения и звука"},
        {"value": "clean_lens", "label": "Очистить линзу и проверить резкость на этикетке"}
      ],
      "lesson_id": "shoot_vertical_source",
      "remediation": "Повторите подготовку телефона: линза, 9:16, мягкий свет, устойчивость, фон и тест звука."
    },
    {
      "id": "course_check_video_quality_eight_seconds",
      "question_type": "single_choice",
      "prompt": "Нужно показать сыворотку за 8 секунд без медицинских обещаний. Какой сценарий лучше всего удерживает одну понятную мысль и сохраняет товар?",
      "rationale_prompt": "Разложите выбранный сценарий по времени: крючок, действие с товаром, доказуемый финал.",
      "requires_rationale": true,
      "options": [
        {"value": "logo_only", "label": "0–4 с: узнаваемый брендовый кадр; 4–8 с: флакон и общий призыв попробовать без названия варианта"},
        {"value": "six_claims", "label": "0–3 с: три свойства состава; 3–7 с: крупный план флакона; 7–8 с: цена и призыв — всё поддержать мелкими оговорками"},
        {"value": "hook_action_finish", "label": "0–2 с: проблема ухода без диагноза; 2–6 с: флакон и текстура; 6–8 с: точное название и безопасный призыв свериться с инструкцией"},
        {"value": "miracle_claim", "label": "0–2 с: выразительное «до»; 2–6 с: нанесение; 6–8 с: заметное «после» с подписью «результат индивидуален»"}
      ],
      "lesson_id": "eight_second_storyboard",
      "remediation": "Снова соберите 8 секунд: один крючок, одно действие с точным товаром и одно проверяемое завершение."
    },
    {
      "id": "course_check_video_quality_succeeded_status",
      "question_type": "single_choice",
      "prompt": "Файл технически воспроизводится и имеет статус succeeded, но на 4-й секунде у блогера появляется лишний палец, а речь обрывается до названия товара. Как классифицировать результат?",
      "rationale_prompt": "Объясните, почему техническая готовность не заменяет просмотр всего файла и проверку смысла.",
      "requires_rationale": true,
      "options": [
        {"value": "mute_only", "label": "Заменить оборванную речь субтитром и выбрать обложку до появления дефекта, сохранив текущий файл"},
        {"value": "reject_with_timestamps", "label": "Не принимать; указать таймкоды двух дефектов и вернуть на исправление/решение о повторе"},
        {"value": "publish_status", "label": "Принять технически, но приложить замечания редактору: succeeded подтверждает пригодность файла к доработке"},
        {"value": "rename_file", "label": "Сохранить версию как final_reviewed, добавить два таймкода в комментарий и передать на публикацию с предупреждением"}
      ],
      "lesson_id": "full_video_qa",
      "remediation": "Просмотрите весь ролик со звуком и зафиксируйте дефекты по таймкоду до любого допуска."
    },
    {
      "id": "course_check_video_quality_source_fidelity",
      "question_type": "multi_select",
      "prompt": "В задаче шоколадный протеин 900 г. Съёмка резкая, но на одном плане видна ванильная этикетка, а на другом старая банка 1 кг. Какие решения обязательны?",
      "rationale_prompt": "Перечислите признаки, по которым докажете совпадение продукта во всех кадрах.",
      "requires_rationale": true,
      "options": [
        {"value": "stop_mismatch", "label": "Заблокировать сборку: вкус и масса не совпадают с назначенным вариантом"},
        {"value": "use_wrong_variant", "label": "Оставить общий план банки 1 кг, если в финальном титре и ссылке указан шоколад 900 г"},
        {"value": "document_version", "label": "Зафиксировать актуальную упаковку и код товара в истории задачи"},
        {"value": "hide_label", "label": "Заменить спорные планы нейтральным крупным планом текстуры, не запрашивая новый исходник товара"},
        {"value": "replace_exact", "label": "Получить/выбрать точные исходники шоколада 900 г и повторно проверить этикетку"}
      ],
      "lesson_id": "product_fidelity",
      "remediation": "Повторите контроль идентичности товара во всех кадрах: вариант, масса, упаковка, код и читаемая этикетка."
    },
    {
      "id": "course_check_video_quality_rights_and_captions",
      "question_type": "multi_select",
      "prompt": "Речь блогера понятна, но монтажёр предлагает популярный трек из чужого ролика. Часть аудитории смотрит без звука. Что входит в готовый безопасный вариант?",
      "rationale_prompt": "Объясните отдельно проверку прав и доступность смысла без звука.",
      "requires_rationale": true,
      "options": [
        {"value": "licensed_audio", "label": "Использовать только музыку/звук с подтверждёнными правами для нужной площадки и задачи"},
        {"value": "accurate_captions", "label": "Добавить и дословно проверить субтитры, тайминг и читаемость на мобильном экране"},
        {"value": "borrow_audio", "label": "Использовать короткий трендовый звук из библиотеки другой площадки, указав автора в описании"},
        {"value": "auto_captions", "label": "Оставить автосубтитры и проверить только название товара вручную — остальные ошибки не влияют на смысл"},
        {"value": "audio_mix", "label": "Проверить, что музыка не перекрывает речь, а обязательная информация остаётся понятной"}
      ],
      "lesson_id": "sound_and_captions",
      "remediation": "Вернитесь к проверке прав на звук, баланса речи и дословных субтитров с мобильным таймингом."
    },
    {
      "id": "course_check_video_quality_full_qa",
      "question_type": "multi_select",
      "prompt": "Перед сдачей ролик хорошо выглядит на большом мониторе. Какие проверки всё равно нужны, чтобы решение было воспроизводимым?",
      "rationale_prompt": "Соберите финальный протокол просмотра, который другой проверяющий сможет повторить.",
      "requires_rationale": true,
      "options": [
        {"value": "control_frames", "label": "Сверить контрольные кадры, речь/субтитры и сохранить конкретные замечания"},
        {"value": "mobile_check", "label": "Проверить 9:16, безопасные зоны, текст и продукт на мобильном размере"},
        {"value": "memory_compare", "label": "Сверить этикетку с последним принятым роликом того же бренда вместо повторного открытия карточки задачи"},
        {"value": "full_playback", "label": "Полностью воспроизвести файл от первого до последнего кадра со звуком"},
        {"value": "skip_watch", "label": "Проверить обложку, первые и последние две секунды, полагаясь на автоматический отчёт для середины ролика"}
      ],
      "lesson_id": "full_video_qa",
      "remediation": "Повторите полный протокол QA, включая мобильный просмотр, контрольные кадры, звук и точную карточку товара."
    }
  ]
  $video_questions$::jsonb
),
(
  'publishing_funnel',
  'Публикация в Instagram, YouTube и VK: решения без права на угадывание',
  'Сценарии проверяют доступ, безопасный запуск аккаунта, права, рекламный контроль, публичную ссылку и доказательства результата.',
  5,
  $publishing_questions$
  [
    {
      "id": "course_check_publishing_funnel_social_access",
      "question_type": "multi_select",
      "prompt": "Задача назначена на брендовый YouTube-канал. У сотрудника есть личный Google-аккаунт, но роли на канале нет; коллега предлагает общий пароль владельца. Что нужно сделать?",
      "rationale_prompt": "Опишите безопасную границу между личной учёткой, ролью на канале и рабочей задачей.",
      "requires_rationale": true,
      "options": [
        {"value": "request_official_role", "label": "Запросить у владельца штатное приглашение с минимально нужными правами"},
        {"value": "verify_channel", "label": "После выдачи доступа сверить название, владельца и возможность создать черновик без публичного выпуска"},
        {"value": "stop_no_role", "label": "Остановить публикацию до появления адресной роли именно на назначенном канале"},
        {"value": "personal_channel", "label": "Подготовить ролик на своём канале в режиме доступа по ссылке, а после выдачи роли перенести публикацию"},
        {"value": "shared_password", "label": "Попросить владельца лично войти на рабочем устройстве и оставить сессию открытой без передачи пароля"}
      ],
      "lesson_id": "social_account_access",
      "remediation": "Повторите адресный доступ через штатную роль и проверку точного аккаунта до подготовки публикации."
    },
    {
      "id": "course_check_publishing_funnel_safe_new_account",
      "question_type": "multi_select",
      "prompt": "Новый рабочий Instagram-профиль оформлен сегодня. Какие действия допустимы в первые дни без обещаний «гарантированного прогрева»?",
      "rationale_prompt": "Объясните, почему естественная работа отличается от имитации активности и обхода ограничений.",
      "requires_rationale": true,
      "options": [
        {"value": "gradual_original", "label": "Постепенно размещать собственный релевантный контент и отвечать реальным людям"},
        {"value": "observe_limits", "label": "Следить за уведомлениями площадки и снижать активность при ограничениях, не пытаясь их обходить"},
        {"value": "truthful_profile", "label": "Заполнить правдивые данные, восстановление доступа и двухфакторную защиту"},
        {"value": "buy_engagement", "label": "Подключить небольшой пакет стартовых просмотров с плавной выдачей, чтобы алгоритм получил первичную выборку"},
        {"value": "mass_actions", "label": "Заранее составить одинаковый дневной лимит подписок и содержательных комментариев, не превышая его"}
      ],
      "lesson_id": "new_account_safe_start",
      "remediation": "Повторите честный запуск нового аккаунта и отличите его от накрутки, массовых действий и обхода ограничений."
    },
    {
      "id": "course_check_publishing_funnel_advertising_gate",
      "question_type": "single_choice",
      "prompt": "Ролик выделяет конкретный товар и формирует интерес. Оплаты и промокода нет, но внутреннее решение о рекламном статусе не зафиксировано, а требования площадки на дату выхода не проверены. Как поступить?",
      "rationale_prompt": "Объясните, почему отсутствие оплаты не даёт автоматического разрешения на публикацию.",
      "requires_rationale": true,
      "options": [
        {"value": "hide_signs", "label": "Сделать текст нейтральным, убрать цену и прямой призыв, затем опубликовать без отдельного решения"},
        {"value": "stop_classify", "label": "Не публиковать; передать на датированную внутреннюю классификацию и проверку обязательных реквизитов/настроек площадки"},
        {"value": "publish_unknown", "label": "Выпустить как обычный обзор, если автор не получил прямую оплату, и уточнить классификацию после первых суток"},
        {"value": "badge_only", "label": "Включить стандартное раскрытие площадки как более осторожный вариант, не фиксируя основание и обязательные реквизиты"}
      ],
      "lesson_id": "advertising_classification_and_labeling",
      "remediation": "Вернитесь к стоп-гейту: при неопределённой классификации материал не публикуется и передаётся ответственному."
    },
    {
      "id": "course_check_publishing_funnel_final_url",
      "question_type": "multi_select",
      "prompt": "Instagram Reels опубликован. В приложении автора он виден, но по ссылке в приватном окне появляется ошибка. Что требуется до передачи результата?",
      "rationale_prompt": "Опишите, как доказать, что конкретный материал доступен проверяющему, а не только автору.",
      "requires_rationale": true,
      "options": [
        {"value": "profile_link", "label": "Вернуть ссылку на профиль и приложить скриншот нужного Reels: это переживёт изменение адреса публикации"},
        {"value": "check_visibility", "label": "Проверить видимость, ограничения и открытие конкретного Reels как обычный зритель"},
        {"value": "fake_link", "label": "Сохранить ссылку из редактора публикации и контрольный скриншот, даже если зрительская ссылка пока не открывается"},
        {"value": "copy_permalink", "label": "После исправления сохранить постоянную ссылку именно на этот материал"},
        {"value": "capture_time", "label": "Зафиксировать площадку, время проверки и контрольный скриншот в назначенной задаче"}
      ],
      "lesson_id": "three_urls",
      "remediation": "Повторите проверку постоянной ссылки на конкретный пост из зрительской сессии и фиксацию доказательства."
    },
    {
      "id": "course_check_publishing_funnel_vk_finish",
      "question_type": "single_choice",
      "prompt": "VK Клип загружен в нужное сообщество, но описание содержит старый артикул, а счётчик ещё не появился. Какой следующий шаг правильный?",
      "rationale_prompt": "Разделите исправление публикации, проверку доступности и первый замер результата.",
      "requires_rationale": true,
      "options": [
        {"value": "delete_after", "label": "Скрыть Клип, сохранить доказательство первоначального размещения и отметить техническую часть задачи завершённой"},
        {"value": "edit_metrics", "label": "Зафиксировать нулевые метрики с текущим временем и заменить их расчётным значением в конце отчётного окна"},
        {"value": "correct_verify_measure", "label": "Не сдавать результат; согласованно исправить описание, открыть Клип как зритель, сохранить точную ссылку и снять метрики с временем, когда они доступны"},
        {"value": "submit_now", "label": "Сдать рабочую ссылку сейчас, а исправленное описание и метрики добавить отдельным комментарием после обновления статистики"}
      ],
      "lesson_id": "vk_clips_step_by_step",
      "remediation": "Повторите финал VK Клипа: точные данные, зрительская доступность, ссылка и измерение с временем."
    },
    {
      "id": "course_check_publishing_funnel_cross_platform_release",
      "question_type": "multi_select",
      "prompt": "Один одобренный ролик нужно выпустить в Instagram Reels, YouTube Shorts и VK Клипы. Что проверяется отдельно для каждой площадки перед массовой передачей результата?",
      "rationale_prompt": "Объясните, какие части можно переиспользовать, а какие требуют отдельного контроля на каждой площадке.",
      "requires_rationale": true,
      "options": [
        {"value": "publish_all_unreviewed", "label": "Сначала создать непубличные/ограниченные версии везде, а итоговую сверку провести одним пакетом после получения адресов"},
        {"value": "same_everywhere", "label": "Одна карточка контроля общего MP4 и отдельные ссылки площадок; подписи считать производными от утверждённого сценария"},
        {"value": "viewer_link", "label": "Отдельная зрительская ссылка на каждый конкретный пост и доказательство его доступности"},
        {"value": "platform_fields", "label": "Текстовые поля, видимость, права/настройки раскрытия и назначенный аккаунт конкретной площадки"},
        {"value": "task_receipt", "label": "Связь каждой публикации с задачей, временем и соответствующими метриками"}
      ],
      "lesson_id": "instagram_reels_step_by_step",
      "remediation": "Повторите отдельный предпросмотр и квитанцию для Instagram, YouTube и VK, даже если исходный MP4 общий."
    }
  ]
  $publishing_questions$::jsonb
),
(
  'security_wb',
  'Подменный артикул, расчёт и безопасность: контрольные ситуации',
  'Здесь проверяется не запоминание термина, а способность остановить неверный товар, мошеннический запрос и неподтверждённую выплату.',
  5,
  $security_questions$
  [
    {
      "id": "course_check_security_wb_substitute_article",
      "question_type": "multi_select",
      "prompt": "В задаче указан подменный артикул WB. Карточка открывает товар того же бренда и объёма, но на фото другой вкус и новая формула. Что обязательно проверить до работы?",
      "rationale_prompt": "Объясните, почему бренд и объём сами по себе не доказывают эквивалентность товара.",
      "requires_rationale": true,
      "options": [
        {"value": "check_alias_history", "label": "Проверить, что связь артикулов создана руководителем, действует сейчас и относится к этой задаче"},
        {"value": "stop_on_difference", "label": "При любом существенном расхождении остановить работу и запросить подтверждение/исправление"},
        {"value": "compare_attributes", "label": "Сверить название, вариант/вкус, объём, состав, упаковку и назначенный основной товар"},
        {"value": "edit_card", "label": "Выбрать из карточки ближайший активный артикул и зафиксировать замену в комментарии для последующей проверки"},
        {"value": "similar_is_enough", "label": "Принять связь, если совпадают бренд, объём и категория, а различие варианта не видно в ролике"}
      ],
      "lesson_id": "wb_alias_history",
      "remediation": "Повторите доказательство эквивалентности подменного артикула и обязательный стоп при расхождении варианта."
    },
    {
      "id": "course_check_security_wb_variant_mismatch",
      "question_type": "single_choice",
      "prompt": "После съёмки выяснилось, что подменный артикул в задаче устарел и теперь ведёт на другую комплектацию. Видео ещё не опубликовано. Какой маршрут единственно допустим?",
      "rationale_prompt": "Опишите, какие записи нужно сохранить и кто имеет право изменить связь артикулов.",
      "requires_rationale": true,
      "options": [
        {"value": "hide_variant", "label": "Заменить кадры комплектации на нейтральные и оставить прежнюю ссылку, поскольку основной товар не изменился"},
        {"value": "publish_old", "label": "Использовать отснятый вариант, если на момент съёмки связь была действующей, а изменение произошло позже"},
        {"value": "freeze_correct_recheck", "label": "Заморозить задачу, сохранить доказательство расхождения, передать руководителю на исправление связи и заново проверить товар до продолжения"},
        {"value": "override_task", "label": "Временно вернуть прежний артикул в результате, приложив историю изменения карточки и уведомив руководителя"}
      ],
      "lesson_id": "wb_alias_history",
      "remediation": "Разберите остановку задачи при устаревшей связи и повторную проверку после исправления руководителем."
    },
    {
      "id": "course_check_security_wb_payout_amount",
      "question_type": "single_choice",
      "prompt": "У участника три задачи: 800 ₽ принята; 1 000 ₽ возвращена на доработку; 600 ₽ принята, но начисление ещё не создано. Какая сумма уже входит в подтверждённое начисление сейчас?",
      "rationale_prompt": "Покажите расчёт и назовите, какие статусы ещё не дают прибавлять сумму.",
      "requires_rationale": true,
      "options": [
        {"value": "2400", "label": "2 400 ₽ — вся назначенная стоимость за период до удержаний и статусов приёмки"},
        {"value": "1400", "label": "1 400 ₽ — сумма двух принятых задач; начисление считать технической задержкой реестра"},
        {"value": "800", "label": "800 ₽ — только сумма принятой задачи, по которой уже существует начисление"},
        {"value": "1800", "label": "1 800 ₽ — начисленная задача плюс работа на доработке, поскольку результат уже передан"}
      ],
      "lesson_id": "calculation_and_payout",
      "remediation": "Повторите цепочку «результат принят → начисление создано → одобрено → внешняя выплата подтверждена»."
    },
    {
      "id": "course_check_security_wb_paid_status",
      "question_type": "multi_select",
      "prompt": "В портале начисление имеет статус «Одобрено», а сотрудник говорит, что перевод уже сделал и просит вручную поставить «Выплачено». Что требуется?",
      "rationale_prompt": "Объясните различие между одобрением начисления и доказанным внешним переводом.",
      "requires_rationale": true,
      "options": [
        {"value": "keep_approved", "label": "Не менять статус до подтверждения фактического перевода по утверждённому процессу"},
        {"value": "audit_paid", "label": "Зафиксировать «Выплачено» только отдельным разрешённым действием с аудиторским следом"},
        {"value": "verify_payment", "label": "Сверить получателя, сумму, внешний идентификатор/доказательство и полномочия фиксирующего"},
        {"value": "edit_amount", "label": "Скорректировать сумму до фактически названной в чате и сохранить скриншот как основание изменения"},
        {"value": "manual_paid", "label": "Отметить «Выплачено» по сообщению руководителя и позднее прикрепить банковское подтверждение"}
      ],
      "lesson_id": "calculation_and_payout",
      "remediation": "Повторите раздельные статусы начисления и фактической выплаты, включая доказательство внешнего перевода."
    },
    {
      "id": "course_check_security_wb_credential_request",
      "question_type": "multi_select",
      "prompt": "В чате человек с похожим именем руководителя просит код из SMS и ссылку восстановления, обещая «разблокировать выплату». Что делать?",
      "rationale_prompt": "Опишите проверку личности и безопасный канал эскалации без раскрытия секретов.",
      "requires_rationale": true,
      "options": [
        {"value": "secure_account", "label": "При уже раскрытых данных немедленно сменить пароль/сессии и уведомить ответственного"},
        {"value": "send_nothing", "label": "Не передавать пароль, SMS-код, токен или ссылку восстановления"},
        {"value": "send_code", "label": "Сначала позвонить руководителю по номеру из подписи, затем продиктовать одноразовый код при подтверждении запроса"},
        {"value": "verify_separate", "label": "Проверить запрос через известный официальный канал и сообщить о подозрительной попытке"},
        {"value": "forward_link", "label": "Переслать ссылку восстановления в закрытый рабочий чат после устной проверки личности — пароль при этом не раскрывается"}
      ],
      "lesson_id": "safe_access",
      "remediation": "Повторите защиту учётки: секреты не передаются, личность проверяется по отдельному известному каналу."
    },
    {
      "id": "course_check_security_wb_dispute_evidence",
      "question_type": "multi_select",
      "prompt": "Участник оспаривает сумму: у него есть ссылка на принятый ролик, а в реестре указана меньшая ставка. Какие данные нужны для решения без переписывания истории?",
      "rationale_prompt": "Соберите проверяемую цепочку от задачи до начисления и выплаты.",
      "requires_rationale": true,
      "options": [
        {"value": "edit_history", "label": "Обновить старую запись до согласованной суммы и приложить сообщение, где изменение было подтверждено"},
        {"value": "chat_memory", "label": "Собрать единое подтверждение из сообщений участников и считать его достаточным без отдельных событий реестра"},
        {"value": "acceptance_receipt", "label": "Результат, решение о приёмке, время и ответственный"},
        {"value": "task_terms", "label": "Исходная задача, согласованная ставка и её версия до начала работы"},
        {"value": "payout_events", "label": "Начисление, изменения статуса и доказательство внешнего перевода, если он был"}
      ],
      "lesson_id": "calculation_and_payout",
      "remediation": "Восстановите аудиторскую цепочку выплаты: условия задачи, приёмка, начисление, решения и внешний перевод."
    }
  ]
  $security_questions$::jsonb
);

do $assessment_catalog_contract$
declare
  malformed_count integer;
begin
  select count(*) into malformed_count
  from training_assessment_v5_catalog catalog
  where jsonb_typeof(catalog.questions) is distinct from 'array'
    or jsonb_array_length(catalog.questions) <> 6
    or catalog.pass_score <> 5
    or exists (
      select 1
      from jsonb_array_elements(catalog.questions) question(item)
      where coalesce(question.item ->> 'id', '')
          !~ ('^course_check_' || catalog.module_code || '_[a-z0-9_]+$')
        or question.item ->> 'question_type' not in ('single_choice', 'multi_select')
        or jsonb_typeof(question.item -> 'options') is distinct from 'array'
        or jsonb_array_length(question.item -> 'options') < 4
        or coalesce(length(btrim(question.item ->> 'rationale_prompt')), 0) < 20
        or coalesce(question.item ->> 'lesson_id', '') = ''
        or coalesce(question.item ->> 'remediation', '') = ''
    );

  if malformed_count <> 0 then
    raise exception 'training assessment v5 contains % malformed course catalogs', malformed_count;
  end if;
end;
$assessment_catalog_contract$;

-- Remove the old shallow question rows before assigning the authoritative
-- 901..906 order range. Historical attempts retain their submitted JSON.
delete from content_factory.training_questions question
where question.module_code in (
  select catalog.module_code from training_assessment_v5_catalog catalog
)
  and question.order_index between 901 and 1000;

with expanded as (
  select
    catalog.module_code,
    question.item,
    question.ordinality::integer as question_order
  from training_assessment_v5_catalog catalog
  cross join lateral jsonb_array_elements(catalog.questions)
    with ordinality as question(item, ordinality)
)
insert into content_factory.training_questions (
  code,
  module_code,
  question_type,
  prompt,
  options,
  order_index,
  updated_at
)
select
  expanded.item ->> 'id',
  expanded.module_code,
  expanded.item ->> 'question_type',
  expanded.item ->> 'prompt',
  (
    select jsonb_agg(option.item order by md5(
      (expanded.item ->> 'id') || ':' || (option.item ->> 'value')
    ))
    from jsonb_array_elements(expanded.item -> 'options') option(item)
  ),
  900 + expanded.question_order,
  now()
from expanded;

-- The data-only grading bank is injected from SUPABASE_TRAINING_KEYS_B64 by
-- the production deployer after the public schema migration is applied.

with public_catalog as (
  select
    catalog.module_code,
    catalog.title,
    catalog.role_hint,
    catalog.pass_score,
    jsonb_agg(
      jsonb_set(
        question.item
          - 'lesson_id'
          - 'remediation',
        '{options}',
        (
          select jsonb_agg(option.item order by md5(
            (question.item ->> 'id') || ':' || (option.item ->> 'value')
          ))
          from jsonb_array_elements(question.item -> 'options') option(item)
        ),
        false
      )
      order by question.ordinality
    ) as questions,
    jsonb_object_agg(
      question.item ->> 'id',
      jsonb_build_object(
        'lesson_id', question.item ->> 'lesson_id',
        'tip', question.item ->> 'remediation'
      )
    ) as remediation
  from training_assessment_v5_catalog catalog
  cross join lateral jsonb_array_elements(catalog.questions)
    with ordinality as question(item, ordinality)
  group by catalog.module_code, catalog.title, catalog.role_hint, catalog.pass_score
)
update content_factory.training_modules module
set
  content = jsonb_set(
    jsonb_set(
      jsonb_set(
        module.content,
        '{version}',
        '5'::jsonb,
        true
      ),
      '{knowledge_check}',
      jsonb_build_object(
        'title', public_catalog.title,
        'role_hint', public_catalog.role_hint,
        'pass_score', public_catalog.pass_score,
        'questions', public_catalog.questions
      ),
      true
    ),
    '{knowledge_remediation}',
    public_catalog.remediation,
    true
  ),
  updated_at = now()
from public_catalog
where module.code = public_catalog.module_code
  and module.module_type = 'course'
  and module.is_active;

-- A certification issued against the shallow pre-v5 catalogs must not hide
-- the new assessment in the UI or satisfy creator_complete_module. The final
-- exam is deliberately outside this list; migration 202607190001 separately
-- grandfathers already certified workers into the practical-work gate.
update content_factory.training_certifications certification
set
  status = 'revoked',
  expires_at = coalesce(certification.expires_at, now())
from content_factory.training_attempts attempt
where certification.attempt_id = attempt.id
  and certification.status = 'passed'
  and certification.module_code = any(array[
    'factory_basics',
    'video_quality',
    'publishing_funnel',
    'security_wb'
  ])
  and (
    attempt.assessment_version <> 5
    or attempt.question_count <> 6
    or jsonb_typeof(attempt.rationales) <> 'object'
    or (select count(*) from jsonb_object_keys(attempt.rationales)) <> 6
  );

update content_factory.training_attempts attempt
set status = 'invalidated'
where attempt.status = 'completed'
  and attempt.module_code = any(array[
    'factory_basics',
    'video_quality',
    'publishing_funnel',
    'security_wb'
  ])
  and (
    attempt.assessment_version <> 5
    or attempt.question_count <> 6
    or jsonb_typeof(attempt.rationales) <> 'object'
    or (select count(*) from jsonb_object_keys(attempt.rationales)) <> 6
  );

create or replace function content_factory_private.valid_training_rationale(
  submitted jsonb
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  with normalized as (
    select lower(regexp_replace(
      btrim(submitted #>> '{}'),
      '\s+',
      ' ',
      'g'
    )) as body
    where jsonb_typeof(submitted) = 'string'
  ), tokens as (
    select token.value
    from normalized
    cross join lateral regexp_split_to_table(
      regexp_replace(normalized.body, '[^[:alnum:]]+', ' ', 'g'),
      '\s+'
    ) token(value)
    where token.value <> ''
  ), token_counts as (
    select
      count(*) as word_count,
      count(distinct token.value) filter (
        where char_length(token.value) >= 3
          and token.value ~ '[[:alpha:]]'
          and token.value ~ '[аеёиоуыэюяaeiouy]'
          and token.value not in (
            'это', 'как', 'для', 'что', 'или', 'при', 'без', 'под', 'над',
            'его', 'её', 'она', 'они', 'там', 'тут', 'так', 'вот', 'the',
            'and', 'for', 'with', 'this', 'that'
          )
      ) as meaningful_distinct_word_count
    from tokens token
  )
  select coalesce(
    (
      select char_length(normalized.body) between 40 and 900
        and token_counts.word_count >= 7
        and token_counts.meaningful_distinct_word_count >= 5
        and normalized.body ~
          'риск[[:space:]]*:.+(проверка|доказательство)[[:space:]]*:.+(действие|следующий шаг)[[:space:]]*:.'
      from normalized
      cross join token_counts
    ),
    false
  );
$$;

create or replace function content_factory_private.answer_hits_any(
  submitted jsonb,
  critical jsonb
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select exists (
    select 1
    from jsonb_array_elements_text(
      content_factory_private.normalize_answer(submitted)
    ) submitted_value(value)
    join jsonb_array_elements_text(
      case
        when jsonb_typeof(critical) = 'array' then critical
        else '[]'::jsonb
      end
    ) critical_value(value)
      using (value)
  );
$$;

create or replace function public.creator_submit_course_check(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  course_code text;
  idempotency_key text;
  answers jsonb;
  rationales jsonb;
  request_payload jsonb;
  replay jsonb;
  required_correct integer;
  declared_question_count integer;
  declared_assessment_version integer;
  total_count integer;
  answered_count integer;
  correct_count integer;
  critical_error_count integer;
  reasoning_count integer;
  distinct_reasoning_count integer;
  recent_attempt_count integer;
  last_attempt_at timestamptz;
  passed boolean;
  score numeric(6,5);
  attempt_id uuid;
  review_topics jsonb := '[]'::jsonb;
  feedback text;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  course_code := content_factory_private.require_text(
    p_payload,
    'module_code',
    3,
    80
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  answers := coalesce(p_payload -> 'answers', '{}'::jsonb);
  rationales := coalesce(p_payload -> 'rationales', '{}'::jsonb);

  if jsonb_typeof(answers) <> 'object'
     or jsonb_typeof(rationales) <> 'object' then
    raise exception using
      errcode = '22023',
      message = 'course_check_payload_invalid';
  end if;

  if (select count(*) from jsonb_object_keys(answers)) > 20
     or (select count(*) from jsonb_object_keys(rationales)) > 20
     or length(answers::text) > 32000
     or length(rationales::text) > 16000 then
    raise exception using
      errcode = '22023',
      message = 'course_check_answers_invalid';
  end if;

  perform content_factory_private.membership_role(
    organization_id,
    false,
    null
  );

  select
    case
      when coalesce(module.content #>> '{knowledge_check,pass_score}', '')
        ~ '^[1-9][0-9]*$'
      then (module.content #>> '{knowledge_check,pass_score}')::integer
      else null
    end,
    case
      when jsonb_typeof(module.content #> '{knowledge_check,questions}') = 'array'
      then jsonb_array_length(module.content #> '{knowledge_check,questions}')
      else null
    end,
    case
      when coalesce(module.content ->> 'version', '') ~ '^[1-9][0-9]*$'
      then (module.content ->> 'version')::integer
      else null
    end
  into required_correct, declared_question_count, declared_assessment_version
  from content_factory.training_modules module
  where module.code = course_code
    and module.module_type = 'course'
    and module.is_active;

  if required_correct is null
     or declared_question_count is null
     or declared_question_count < 1
     or required_correct > declared_question_count
     or declared_assessment_version <> 5 then
    raise exception using
      errcode = '55000',
      message = 'course_check_catalog_unavailable';
  end if;

  request_payload := jsonb_build_object(
    'module_code', course_code,
    'assessment_version', 5,
    'answers', answers,
    'rationales', rationales
  );

  replay := content_factory_private.begin_command(
    organization_id,
    'creator_submit_course_check',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('creator_course_check:' || course_code)
  );

  select count(*), max(attempt.completed_at)
  into recent_attempt_count, last_attempt_at
  from content_factory.training_attempts attempt
  where attempt.organization_id = organization_id
    and attempt.profile_id = user_id
    and attempt.module_code = course_code
    and attempt.assessment_version = 5
    and attempt.completed_at > now() - interval '24 hours';

  if last_attempt_at is not null
     and last_attempt_at > now() - interval '60 seconds' then
    raise exception using
      errcode = '55000',
      message = 'course_check_cooldown';
  end if;

  if recent_attempt_count >= 8 then
    raise exception using
      errcode = '54000',
      message = 'course_check_daily_attempt_limit';
  end if;

  if exists (
    select 1
    from jsonb_object_keys(answers) submitted(question_code)
    where not exists (
      select 1
      from content_factory.training_questions question
      where question.module_code = course_code
        and question.code = submitted.question_code
        and question.order_index between 901 and 1000
        and strpos(question.code, 'course_check_' || course_code || '_') = 1
    )
  ) or exists (
    select 1
    from jsonb_object_keys(rationales) submitted(question_code)
    where not exists (
      select 1
      from content_factory.training_questions question
      where question.module_code = course_code
        and question.code = submitted.question_code
        and question.order_index between 901 and 1000
        and strpos(question.code, 'course_check_' || course_code || '_') = 1
    )
  ) then
    raise exception using
      errcode = '22023',
      message = 'unknown_course_check_question';
  end if;

  select
    count(*),
    count(*) filter (
      where jsonb_array_length(
        content_factory_private.normalize_answer(answers -> question.code)
      ) > 0
    ),
    count(*) filter (
      where content_factory_private.normalize_answer(answers -> question.code)
        = content_factory_private.normalize_answer(answer_key.correct_answers)
    ),
    count(*) filter (
      where content_factory_private.answer_hits_any(
        answers -> question.code,
        answer_key.critical_answers
      )
    ),
    count(*) filter (
      where content_factory_private.valid_training_rationale(
        rationales -> question.code
      )
    ),
    count(distinct case
      when content_factory_private.valid_training_rationale(
        rationales -> question.code
      )
      then md5(lower(regexp_replace(
        btrim(rationales ->> question.code),
        '\s+',
        ' ',
        'g'
      )))
      else null
    end)
  into
    total_count,
    answered_count,
    correct_count,
    critical_error_count,
    reasoning_count,
    distinct_reasoning_count
  from content_factory.training_questions question
  join content_factory_private.training_answer_keys answer_key
    on answer_key.question_code = question.code
  where question.module_code = course_code
    and question.order_index between 901 and 1000
    and strpos(question.code, 'course_check_' || course_code || '_') = 1;

  if total_count = 0 or total_count <> declared_question_count then
    raise exception using
      errcode = '55000',
      message = 'course_check_catalog_unavailable';
  end if;

  passed := answered_count = total_count
    and reasoning_count = total_count
    and distinct_reasoning_count = total_count
    and correct_count >= required_correct
    and critical_error_count = 0;
  score := correct_count::numeric / total_count::numeric;

  -- Failed attempts deliberately receive no per-question diagnostics. Returning
  -- question ids, exact scores or critical flags turns the retry API into an
  -- answer-key oracle. Detailed evidence remains private in training_attempts.
  review_topics := '[]'::jsonb;

  feedback := case
    when passed then
      'Сценарная проверка пройдена: решения и обоснования приняты сервером.'
    when reasoning_count <> total_count
      or distinct_reasoning_count <> total_count then
      'Каждое решение требует отдельного содержательного обоснования: риск, проверка и следующий шаг.'
    else
      'Попытка не зачтена. Повторите весь рабочий маршрут блока и через минуту решите новый вариант самостоятельно.'
  end;

  insert into content_factory.training_attempts (
    organization_id,
    profile_id,
    module_code,
    score,
    correct_count,
    answered_count,
    question_count,
    passed,
    answers,
    rationales,
    assessment_version,
    request_hash,
    idempotency_key
  ) values (
    organization_id,
    user_id,
    course_code,
    score,
    correct_count,
    answered_count,
    total_count,
    passed,
    answers,
    rationales,
    5,
    content_factory_private.json_hash(request_payload),
    left('course-check:' || idempotency_key, 180)
  )
  returning id into attempt_id;

  result := jsonb_build_object(
    'ok', true,
    'attempt_id', attempt_id,
    'module_code', course_code,
    'question_count', total_count,
    'required_correct', required_correct,
    'passed', passed,
    'feedback', feedback
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    case
      when passed then 'training_course_check_passed'
      else 'training_course_check_failed'
    end,
    'training_attempt',
    attempt_id::text,
    jsonb_build_object(
      'module_code', course_code,
      'answered_count', answered_count,
      'correct_count', correct_count,
      'question_count', total_count,
      'reasoning_count', reasoning_count,
      'critical_error_count', critical_error_count,
      'passed', passed,
      'assessment_version', 5
    ),
    'course-check:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_submit_course_check',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

revoke all on function content_factory_private.answer_hits_any(jsonb, jsonb)
  from public, anon, authenticated;

revoke all on function content_factory_private.valid_training_rationale(jsonb)
  from public, anon, authenticated;

revoke all on function public.creator_submit_course_check(jsonb)
  from public, anon;
grant execute on function public.creator_submit_course_check(jsonb)
  to authenticated;

-- Do not let bootstrap turn a failed retry into a score-delta oracle. The
-- underlying bootstrap remains responsible for authorization and catalog
-- assembly; this final wrapper strips all grading diagnostics from the public
-- course-check receipt while preserving pass/fail and completion state.
alter function public.creator_bootstrap(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_bootstrap(jsonb)
  rename to creator_bootstrap_pre_assessment_v5_sanitize;

create or replace function public.creator_bootstrap(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  result jsonb;
  sanitized_checks jsonb;
begin
  result := content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize(
    p_payload
  );

  if jsonb_typeof(result #> '{learning,course_checks}') = 'array' then
    select coalesce(
      jsonb_agg(
        check_item.value
          - 'attempt_id'
          - 'correct_count'
          - 'critical_error_count'
          - 'score_percent'
          - 'review_topics'
        order by check_item.ordinality
      ),
      '[]'::jsonb
    )
    into sanitized_checks
    from jsonb_array_elements(result #> '{learning,course_checks}')
      with ordinality check_item(value, ordinality);

    result := jsonb_set(
      result,
      '{learning,course_checks}',
      sanitized_checks,
      false
    );
  end if;

  if jsonb_typeof(result #> '{training,course_checks}') = 'array' then
    select coalesce(
      jsonb_agg(
        check_item.value
          - 'attempt_id'
          - 'correct_count'
          - 'critical_error_count'
          - 'score_percent'
          - 'review_topics'
        order by check_item.ordinality
      ),
      '[]'::jsonb
    )
    into sanitized_checks
    from jsonb_array_elements(result #> '{training,course_checks}')
      with ordinality check_item(value, ordinality);

    result := jsonb_set(
      result,
      '{training,course_checks}',
      sanitized_checks,
      false
    );
  end if;

  return result;
end;
$$;

revoke all on function
  content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize(jsonb)
  from public, anon, authenticated;
revoke all on function public.creator_bootstrap(jsonb)
  from public, anon;
grant execute on function public.creator_bootstrap(jsonb)
  to authenticated;

-- The server progress RPC accepts only walkthroughs declared in the catalog.
-- These records mirror the six irreversible decisions in the browser labs;
-- they are filtered out of the generic walkthrough renderer and shown by the
-- dedicated Instagram / YouTube / VK simulator UI.
with platform_walkthroughs as (
  select $platform_walkthroughs$
  [
    {
      "id": "platform_publish_instagram",
      "eyebrow": "Практическая смена · Instagram",
      "title": "Instagram Reels: шесть решений до результата",
      "summary": "Сценарная аттестация доступа, запуска аккаунта, продукта, рекламного контроля, ссылки и квитанции.",
      "duration_seconds": 300,
      "reviewed_at": "2026-07-19",
      "video_url": null,
      "poster_url": null,
      "frames": [
        {"id":"platform_instagram_account","time":"00:00","title":"Доступ","body":"Проверьте адресную роль и точный назначенный профиль.","cue":"Общий пароль является критической ошибкой.","visual_label":"Проверка доступа Instagram"},
        {"id":"platform_instagram_warmup","time":"00:50","title":"Безопасный старт","body":"Отличите естественную работу от имитации активности.","cue":"Накрутка и массовые действия проваливают попытку.","visual_label":"План запуска профиля"},
        {"id":"platform_instagram_publication","time":"01:40","title":"Точный материал","body":"Сверьте товар, финальный файл и права до подготовки публикации.","cue":"Неверный вариант товара нельзя маскировать.","visual_label":"Карточка проверки Reels"},
        {"id":"platform_instagram_review","time":"02:30","title":"Стоп-гейт","body":"Зафиксируйте рекламный статус и обязательные проверки до выхода.","cue":"Неопределённость означает остановку, а не угадывание.","visual_label":"Решение ответственного"},
        {"id":"platform_instagram_link","time":"03:20","title":"Зрительская ссылка","body":"Проверьте конкретный Reels вне авторской сессии.","cue":"Профиль не заменяет ссылку на пост.","visual_label":"Публичная ссылка Reels"},
        {"id":"platform_instagram_result","time":"04:10","title":"Квитанция","body":"Свяжите ссылку, доказательство и время с назначенной задачей.","cue":"Передано на проверку не означает выплачено.","visual_label":"Квитанция результата"}
      ],
      "checklist": ["Шесть решений зафиксированы", "Каждое обоснование содержит не менее 50 знаков и 8 слов", "Итог оценивается сервером без показа ключей"],
      "transcript": [
        {"time":"00:00","text":"Начните с адресного доступа к точному профилю."},
        {"time":"00:50","text":"Новый аккаунт запускают постепенно, без накрутки."},
        {"time":"01:40","text":"До публикации сверяют точный товар, файл и права."},
        {"time":"02:30","text":"Неопределённый рекламный статус останавливает выпуск."},
        {"time":"03:20","text":"Результат проверяют по ссылке на конкретный Reels."},
        {"time":"04:10","text":"Ссылка и доказательство сохраняются в назначенной задаче."}
      ]
    },
    {
      "id": "platform_publish_youtube",
      "eyebrow": "Практическая смена · YouTube",
      "title": "YouTube Shorts: шесть решений до результата",
      "summary": "Сценарная аттестация роли на канале, безопасного старта, прав, допуска, ссылки и квитанции.",
      "duration_seconds": 300,
      "reviewed_at": "2026-07-19",
      "video_url": null,
      "poster_url": null,
      "frames": [
        {"id":"platform_youtube_account","time":"00:00","title":"Роль на канале","body":"Сверьте точный канал и минимально необходимую адресную роль.","cue":"Чужой или общий пароль недопустим.","visual_label":"Доступ YouTube"},
        {"id":"platform_youtube_warmup","time":"00:50","title":"История канала","body":"Запланируйте обычный последовательный старт без спама и накрутки.","cue":"Купленные просмотры проваливают попытку.","visual_label":"План запуска канала"},
        {"id":"platform_youtube_publication","time":"01:40","title":"Файл и права","body":"Сверьте продукт, звук, заголовок и подтверждённые права.","cue":"Чужой контент без прав является критической ошибкой.","visual_label":"Проверка Shorts"},
        {"id":"platform_youtube_review","time":"02:30","title":"Допуск","body":"Подготовьте непубличную проверку и получите требуемое решение до выпуска.","cue":"Сначала публично, потом исправить — неверный маршрут.","visual_label":"Предпубликационная проверка"},
        {"id":"platform_youtube_link","time":"03:20","title":"Ссылка зрителя","body":"Откройте конкретный Shorts без доступа к Studio.","cue":"Служебная ссылка не доказывает результат.","visual_label":"Публичная ссылка Shorts"},
        {"id":"platform_youtube_result","time":"04:10","title":"Передача","body":"Сохраните ссылку, скриншот и время в задаче.","cue":"Статус оплаты не назначается автором.","visual_label":"Квитанция YouTube"}
      ],
      "checklist": ["Шесть решений зафиксированы", "Каждое обоснование содержит не менее 50 знаков и 8 слов", "Итог оценивается сервером без показа ключей"],
      "transcript": [
        {"time":"00:00","text":"Проверьте роль на назначенном канале."},
        {"time":"00:50","text":"Не имитируйте историю канала спамом или покупкой просмотров."},
        {"time":"01:40","text":"Файл, продукт и права проверяются до выпуска."},
        {"time":"02:30","text":"Публичная аудитория не должна становиться тестовой средой."},
        {"time":"03:20","text":"Возвращают зрительскую ссылку на конкретный Shorts."},
        {"time":"04:10","text":"Портал связывает доказательство с задачей и дальнейшим решением."}
      ]
    },
    {
      "id": "platform_publish_vk",
      "eyebrow": "Практическая смена · VK",
      "title": "VK Клипы: шесть решений до результата",
      "summary": "Сценарная аттестация сообщества, безопасного старта, артикула, допуска, ссылки и квитанции.",
      "duration_seconds": 300,
      "reviewed_at": "2026-07-19",
      "video_url": null,
      "poster_url": null,
      "frames": [
        {"id":"platform_vk_account","time":"00:00","title":"Точка публикации","body":"Сверьте назначенный профиль или сообщество и адресные права.","cue":"Любое другое сообщество не подходит.","visual_label":"Доступ VK"},
        {"id":"platform_vk_warmup","time":"00:50","title":"Естественный старт","body":"Оформите страницу и наращивайте самостоятельный контент постепенно.","cue":"Рассылки и купленные реакции не являются прогревом.","visual_label":"План запуска VK"},
        {"id":"platform_vk_publication","time":"01:40","title":"Товар и артикул","body":"Сверьте точный товар, подменную связь и финальный файл.","cue":"Похожий вариант не заменяет назначенный.","visual_label":"Проверка VK Клипа"},
        {"id":"platform_vk_review","time":"02:30","title":"Допуск и раскрытия","body":"Получите решение по материалу до любого публичного размещения.","cue":"Скрытие рекламных признаков проваливает попытку.","visual_label":"Стоп-гейт VK"},
        {"id":"platform_vk_link","time":"03:20","title":"Адрес Клипа","body":"Проверьте ссылку на конкретный Клип как обычный зритель.","cue":"Панель администратора не является результатом.","visual_label":"Публичная ссылка VK"},
        {"id":"platform_vk_result","time":"04:10","title":"Результат смены","body":"Сохраните точную ссылку, доказательство и время в задаче.","cue":"Метрики не придумывают и не переписывают.","visual_label":"Квитанция VK"}
      ],
      "checklist": ["Шесть решений зафиксированы", "Каждое обоснование содержит не менее 50 знаков и 8 слов", "Итог оценивается сервером без показа ключей"],
      "transcript": [
        {"time":"00:00","text":"Публикация начинается с точного сообщества и адресных прав."},
        {"time":"00:50","text":"Безопасный старт исключает спам и накрутку."},
        {"time":"01:40","text":"Артикул, вариант и видео должны относиться к одному товару."},
        {"time":"02:30","text":"Публичный выпуск возможен только после требуемого допуска."},
        {"time":"03:20","text":"Проверяющий получает ссылку на конкретный доступный Клип."},
        {"time":"04:10","text":"Портал сохраняет доказательство и время передачи результата."}
      ]
    }
  ]
  $platform_walkthroughs$::jsonb as items
), normalized as (
  select
    coalesce(jsonb_agg(existing.item order by existing.ordinality), '[]'::jsonb)
      || platform_walkthroughs.items as walkthroughs
  from content_factory.training_modules module
  cross join platform_walkthroughs
  left join lateral jsonb_array_elements(
    case
      when jsonb_typeof(module.content -> 'interactive_walkthroughs') = 'array'
      then module.content -> 'interactive_walkthroughs'
      else '[]'::jsonb
    end
  ) with ordinality as existing(item, ordinality)
    on coalesce(existing.item ->> 'id', '') not in (
      'platform_publish_instagram',
      'platform_publish_youtube',
      'platform_publish_vk'
    )
  where module.code = 'publishing_funnel'
    and module.module_type = 'course'
    and module.is_active
  group by platform_walkthroughs.items
)
update content_factory.training_modules module
set
  content = jsonb_set(
    jsonb_set(
      module.content,
      '{interactive_walkthroughs}',
      normalized.walkthroughs,
      true
    ),
    '{mastery,required_walkthrough_ids}',
    (
      select coalesce(jsonb_agg(required.value order by required.ordinality), '[]'::jsonb)
      from (
        select existing.value, existing.ordinality
        from jsonb_array_elements_text(
          case
            when jsonb_typeof(module.content #> '{mastery,required_walkthrough_ids}') = 'array'
            then module.content #> '{mastery,required_walkthrough_ids}'
            else '[]'::jsonb
          end
        ) with ordinality as existing(value, ordinality)
        where existing.value not in (
          'platform_publish_instagram',
          'platform_publish_youtube',
          'platform_publish_vk'
        )
        union all select 'platform_publish_instagram', 1001
        union all select 'platform_publish_youtube', 1002
        union all select 'platform_publish_vk', 1003
      ) required
    ),
    true
  ),
  updated_at = now()
from normalized
where module.code = 'publishing_funnel'
  and module.module_type = 'course'
  and module.is_active;

do $training_assessment_v5_contract$
declare
  invalid_module_count integer;
  invalid_question_count integer;
  public_secret_count integer;
  invalid_platform_count integer;
  function_definition text;
begin
  select count(*) into invalid_module_count
  from content_factory.training_modules module
  where module.code = any(array[
    'factory_basics',
    'video_quality',
    'publishing_funnel',
    'security_wb'
  ])
    and (
      module.content ->> 'version' <> '5'
      or module.content #>> '{knowledge_check,pass_score}' <> '5'
      or jsonb_array_length(module.content #> '{knowledge_check,questions}') <> 6
    );

  select count(*) into invalid_question_count
  from content_factory.training_questions question
  join content_factory_private.training_answer_keys answer_key
    on answer_key.question_code = question.code
  where question.module_code = any(array[
    'factory_basics',
    'video_quality',
    'publishing_funnel',
    'security_wb'
  ])
    and question.order_index between 901 and 906
    and (
      question.question_type not in ('single_choice', 'multi_select')
      or jsonb_array_length(answer_key.correct_answers) < 1
      or jsonb_typeof(answer_key.critical_answers) <> 'array'
    );

  if invalid_question_count <> 0 or (
    select count(*)
    from content_factory.training_questions question
    where question.module_code = any(array[
      'factory_basics',
      'video_quality',
      'publishing_funnel',
      'security_wb'
    ])
      and question.order_index between 901 and 906
  ) <> 24 then
    raise exception 'training assessment v5 question contract failed';
  end if;

  select count(*) into public_secret_count
  from content_factory.training_modules module
  where module.code = any(array[
    'factory_basics',
    'video_quality',
    'publishing_funnel',
    'security_wb'
  ])
    and (
      jsonb_path_exists(module.content, '$.knowledge_check.questions[*].correct_answers')
      or jsonb_path_exists(module.content, '$.knowledge_check.questions[*].critical_answers')
      or jsonb_path_exists(module.content, '$.knowledge_check.questions[*].explanation')
    );

  select count(*) into invalid_platform_count
  from (
    values
      ('platform_publish_instagram'),
      ('platform_publish_youtube'),
      ('platform_publish_vk')
  ) expected(walkthrough_id)
  where not exists (
    select 1
    from content_factory.training_modules module
    cross join lateral jsonb_array_elements(
      module.content -> 'interactive_walkthroughs'
    ) walkthrough(item)
    where module.code = 'publishing_funnel'
      and walkthrough.item ->> 'id' = expected.walkthrough_id
      and jsonb_array_length(walkthrough.item -> 'frames') = 6
  );

  select pg_get_functiondef(
    'public.creator_submit_course_check(jsonb)'::regprocedure
  ) into function_definition;

  if invalid_module_count <> 0
     or public_secret_count <> 0
     or invalid_platform_count <> 0
     or strpos(function_definition, 'critical_error_count') = 0
     or strpos(function_definition, 'distinct_reasoning_count') = 0
     or strpos(function_definition, 'valid_training_rationale') = 0
     or strpos(function_definition, 'course_check_cooldown') = 0
     or strpos(function_definition, 'course_check_daily_attempt_limit') = 0
     or strpos(function_definition, 'assessment_version') = 0
     or strpos(function_definition, 'rationales') = 0 then
    raise exception 'training assessment v5 authoritative contract failed';
  end if;
end;
$training_assessment_v5_contract$;

comment on function public.creator_submit_course_check(jsonb) is
  'Grades six v5 work scenarios server-side; requires unique written rationales and fails the attempt on any private critical answer.';

commit;
