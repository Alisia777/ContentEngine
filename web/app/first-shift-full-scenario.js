const STATE_VERSION = 1;

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.values(value).forEach(deepFreeze);
  return Object.freeze(value);
}

export const FIRST_SHIFT_FULL_ACTIONS = deepFreeze({
  select: "first-shift-full-select",
  check: "first-shift-full-check",
  next: "first-shift-full-next",
  previous: "first-shift-full-previous",
  restart: "first-shift-full-restart",
});

export const FIRST_SHIFT_FULL_POLICY_REFERENCES = deepFreeze({
  checkedAt: "2026-07-15",
  interfaceNote: "Названия переключателей могут меняться. Если нужного раскрытия нет или решение по рекламе не записано в задаче, остановитесь и обратитесь к руководителю.",
  instagram: {
    title: "Instagram: paid partnership label",
    url: "https://www.facebook.com/help/instagram/1109894795810258/",
  },
  youtube: {
    title: "YouTube: paid promotions disclosure",
    url: "https://support.google.com/youtube/answer/154235",
  },
});

export const FIRST_SHIFT_PLATFORM_GUIDES = deepFreeze({
  instagram: {
    id: "instagram",
    label: "Instagram Reels",
    icon: "IG",
    route: ["Нажмите «+»", "Выберите Reel", "Загрузите одобренный файл", "Проверьте обложку и описание", "Примените назначенное раскрытие", "Опубликуйте и откройте сам Reel"],
    disclosure: "Если есть обмен ценностью или иная коммерческая связь, используйте назначенное раскрытие и инструменты branded content. Не убирайте бренд ради обхода метки.",
    finalEvidence: "URL конкретного Reel, открывающийся без входа, если это допускают настройки аккаунта.",
    sourceUrl: FIRST_SHIFT_FULL_POLICY_REFERENCES.instagram.url,
  },
  youtube: {
    id: "youtube",
    label: "YouTube Shorts",
    icon: "YT",
    route: ["Нажмите «Создать»", "Выберите Short", "Загрузите одобренный файл", "Укажите заголовок и аудиторию", "Отметьте paid promotion, если это назначено", "Опубликуйте и откройте сам Short"],
    disclosure: "При платном размещении, спонсорстве или иной коммерческой связи сообщите об этом YouTube в деталях видео и выполните локальные требования из задачи.",
    finalEvidence: "URL конкретного Short, а не ссылка на канал или YouTube Studio.",
    sourceUrl: FIRST_SHIFT_FULL_POLICY_REFERENCES.youtube.url,
  },
  vk: {
    id: "vk",
    label: "VK Клипы",
    icon: "VK",
    route: ["Откройте «Клипы»", "Нажмите создание клипа", "Загрузите одобренный файл", "Проверьте описание и автора", "Примените раскрытие строго из задачи", "Опубликуйте и откройте сам клип"],
    disclosure: "Не решайте рекламный статус самостоятельно. Если в задаче нет однозначного решения и готового раскрытия, публикация блокируется до ответа руководителя.",
    finalEvidence: "URL конкретного VK Клипа, а не ссылка на профиль, ленту или загруженный MP4.",
    sourceUrl: null,
  },
});

export const FIRST_SHIFT_FULL_PHASES = deepFreeze([
  { id: "task", number: "01", label: "Задача", hint: "товар, артикулы, сумма", stepIds: ["receive_task", "verify_articles_reward"] },
  { id: "materials", number: "02", label: "Материалы", hint: "только точные исходники", stepIds: ["select_sources"] },
  { id: "production", number: "03", label: "Производство", hint: "съёмка или генерация", stepIds: ["build_shot_plan", "approve_8s_brief", "choose_production_path", "paid_preflight", "paid_status_without_restart"] },
  { id: "quality", number: "04", label: "Контроль", hint: "брак не проходит дальше", stepIds: ["quality_control"] },
  { id: "publication", number: "05", label: "Публикация", hint: "площадка, раскрытие, URL", stepIds: ["choose_platform_disclosure", "return_post_url"] },
  { id: "result", number: "06", label: "Результат", hint: "метрики и выплата", stepIds: ["record_metrics", "understand_payout"] },
]);

const STEPS = [
  {
    id: "receive_task",
    phase: "task",
    eyebrow: "Получение задачи",
    title: "Сначала зафиксируйте, что именно вам выдали",
    lead: "Учебная задача: «Кровавый пилинг», 30 мл, основной артикул 930001001, подменный 930001019, VK Клипы, 800 ₽. Это учебные номера, не реальный заказ.",
    question: "Что делать первым действием?",
    input: "single",
    options: [
      { value: "compare_task", label: "Открыть карточку задачи и сверить товар, объём, оба артикула, площадку и сумму" },
      { value: "start_fast", label: "Сразу начать съёмку: детали можно уточнить после публикации" },
      { value: "pick_product", label: "Выбрать похожий товар самостоятельно, чтобы не задерживать работу" },
    ],
    correct: ["compare_task"],
    success: "Верно. Рабочий цикл начинается с точной задачи, а не с камеры или генератора.",
    retry: "Сначала нужна сверка задачи. Самостоятельная замена товара или площадки запрещена.",
    portalPath: "Задачи → карточка назначенной работы",
    evidence: "Зафиксированы товар, объём, основной и подменный артикулы, площадка и сумма.",
    stopRule: "Если хотя бы одно поле отсутствует или противоречит товару — остановитесь и сообщите руководителю.",
    visual: {
      label: "Карточка учебной задачи",
      title: "Один источник правды",
      items: [
        { label: "Товар", value: "Пилинг · 30 мл", tone: "product" },
        { label: "Основной", value: "930001001", tone: "neutral" },
        { label: "Подменный", value: "930001019", tone: "neutral" },
        { label: "Площадка", value: "VK Клипы", tone: "platform" },
        { label: "Сумма", value: "800 ₽", tone: "money" },
      ],
    },
  },
  {
    id: "verify_articles_reward",
    phase: "task",
    eyebrow: "Основной и подменный артикул",
    title: "Подменник — не другой товар и не ваша догадка",
    lead: "Подменный артикул связывает ту же товарную историю с другим назначенным номером. Он не разрешает менять объём, упаковку, состав или бренд.",
    question: "Какие три проверки обязательны?",
    input: "multi",
    options: [
      { value: "same_product", label: "Название, бренд, объём и упаковка совпадают с задачей" },
      { value: "assigned_only", label: "Оба артикула взяты из задачи, а не найдены самостоятельно" },
      { value: "fixed_reward", label: "Вознаграждение равно сумме из задачи и само не меняется от просмотров" },
      { value: "similar_ok", label: "Можно взять похожий флакон другого объёма, если цвет совпадает" },
      { value: "higher_reward", label: "Можно выбрать артикул с большей ценой и увеличить выплату" },
    ],
    correct: ["same_product", "assigned_only", "fixed_reward"],
    success: "Верно. Подменник задаёт руководитель, а сумма остаётся отдельным условием задачи.",
    retry: "Проверьте тождественность товара, источник артикула и фиксированную сумму задачи.",
    portalPath: "Задачи → Товар и расчёт",
    evidence: "Сверены обе карточки товара и записана назначенная сумма.",
    stopRule: "Похожий товар, другой объём или самостоятельно найденный артикул — стоп.",
    visual: {
      label: "Проверка подменника",
      title: "Разные номера — один точный товар",
      items: [
        { label: "930001001", value: "Пилинг · 30 мл", tone: "good" },
        { label: "930001019", value: "Пилинг · 30 мл", tone: "good" },
        { label: "930001099", value: "Похожий · 50 мл", tone: "bad" },
      ],
    },
  },
  {
    id: "select_sources",
    phase: "materials",
    eyebrow: "Выбор исходников",
    title: "В производство идут только точные и разрешённые материалы",
    lead: "Выберите все исходники, которые безопасно использовать для этой задачи.",
    question: "Какие материалы оставить?",
    input: "multi",
    options: [
      { value: "front_30", label: "Чёткое фото лицевой этикетки нужного флакона 30 мл" },
      { value: "hand_30", label: "Тот же флакон 30 мл в руке, этикетка читается" },
      { value: "back_30", label: "Фото обратной стороны того же флакона для проверки упаковки" },
      { value: "lookalike_50", label: "Красивое фото похожего флакона 50 мл" },
      { value: "watermarked", label: "Фрагмент чужого ролика с водяным знаком" },
    ],
    correct: ["front_30", "hand_30", "back_30"],
    success: "Верно. Три ракурса подтверждают точный товар и не подмешивают чужой контент.",
    retry: "Уберите похожий товар и чужой ролик. Красивый исходник не важнее точности и прав.",
    portalPath: "Материалы → Товар → Выбрать исходники",
    evidence: "Выбран минимальный набор точных фото с подтверждёнными правами.",
    stopRule: "Неясная этикетка, другой объём, водяной знак или неизвестные права — материал не используется.",
    visual: {
      label: "Стол исходников",
      title: "Точность важнее количества",
      items: [
        { label: "01", value: "Лицевая этикетка", tone: "good" },
        { label: "02", value: "Флакон в руке", tone: "good" },
        { label: "03", value: "Обратная сторона", tone: "good" },
        { label: "Стоп", value: "50 мл / водяной знак", tone: "bad" },
      ],
    },
  },
  {
    id: "build_shot_plan",
    phase: "production",
    eyebrow: "Съёмочный план",
    title: "До камеры разложите восемь секунд по кадрам",
    lead: "Даже если ролик будет сгенерирован, съёмочный план задаёт движение, крупность и смысл каждого отрезка.",
    question: "Какой план готов к работе?",
    input: "single",
    options: [
      { value: "safe_plan", label: "9:16; свет перед товаром; 0–2 сек — вопрос, 2–5 — точный флакон, 5–8 — результат и короткое действие" },
      { value: "random_plan", label: "Снять много случайных кадров, а последовательность придумать после" },
      { value: "dark_plan", label: "Снимать против окна, держать товар далеко и закрыть этикетку рукой" },
    ],
    correct: ["safe_plan"],
    success: "Верно. Вертикаль, свет и три коротких кадра дают воспроизводимый план.",
    retry: "Нужны формат 9:16, читаемый товар и заранее заданные 0–2 / 2–5 / 5–8 секунд.",
    portalPath: "Создание видео → Сценарий",
    evidence: "Сохранены формат, свет, три кадра и действие героя.",
    stopRule: "Если этикетку нельзя удержать читаемой, меняйте условия съёмки до запуска.",
    visual: {
      label: "Лента 8 секунд",
      title: "Один ролик — три понятных кадра",
      sequence: [
        { time: "0–2", title: "Вопрос", text: "Короткий хук без обещаний" },
        { time: "2–5", title: "Товар", text: "Флакон и этикетка крупно" },
        { time: "5–8", title: "Действие", text: "Одна мысль и спокойный финал" },
      ],
    },
  },
  {
    id: "approve_8s_brief",
    phase: "production",
    eyebrow: "Бриф блогера",
    title: "Одна реплика, один товар, один проверяемый смысл",
    lead: "Бриф должен удерживать внешний вид товара и не добавлять медицинских или гарантированных обещаний.",
    question: "Какой бриф отправить в производство?",
    input: "single",
    options: [
      { value: "safe_brief", label: "Блогер показывает точный флакон 30 мл и говорит: «Кислотный уход с понятным домашним ритуалом». 9:16, 8 секунд, спокойная речь" },
      { value: "medical_claim", label: "Блогер обещает навсегда вылечить акне за одно применение" },
      { value: "many_scenes", label: "Пять товаров, четыре локации и длинный текст в восьмисекундном ролике" },
    ],
    correct: ["safe_brief"],
    success: "Верно. Бриф короткий, воспроизводимый и не обещает неподтверждённый лечебный эффект.",
    retry: "Уберите неподтверждённые обещания и лишние сцены. Восемь секунд выдерживают одну мысль.",
    portalPath: "Создание видео → Бриф",
    evidence: "Зафиксированы герой, точный товар, одна реплика, формат и длительность.",
    stopRule: "Лечебные гарантии, выдуманные характеристики или другой товар — стоп до согласования.",
    visual: {
      label: "Бриф 8 секунд",
      title: "Блогер + товар + короткая речь",
      items: [
        { label: "Герой", value: "Бьюти-блогер", tone: "neutral" },
        { label: "Формат", value: "9:16 · 8 сек", tone: "platform" },
        { label: "Товар", value: "Точный флакон 30 мл", tone: "product" },
        { label: "Речь", value: "Одна проверяемая мысль", tone: "good" },
      ],
    },
  },
  {
    id: "choose_production_path",
    phase: "production",
    eyebrow: "Снять или сгенерировать",
    title: "Способ производства задают условия и разрешение задачи",
    lead: "Сейчас у вас есть точные согласованные фото, но самого товара рядом нет, безопасная съёмка не назначена, а генерация разрешена задачей.",
    question: "Какое решение принять?",
    input: "single",
    options: [
      { value: "generate_approved", label: "Сгенерировать по согласованным исходникам, сначала проверить режим, длительность и стоимость" },
      { value: "shoot_other", label: "Снять похожий товар, который оказался под рукой" },
      { value: "download_creator", label: "Скачать чужой обзор и убрать водяной знак" },
    ],
    correct: ["generate_approved"],
    success: "Верно. Генерация допустима только потому, что задача её разрешает и точные исходники уже проверены.",
    retry: "Нельзя подменять товар или брать чужой ролик. Используйте разрешённый задачей путь.",
    portalPath: "Создание видео → Режим производства",
    evidence: "Записано решение «генерация» и основание: точные исходники + разрешение задачи.",
    stopRule: "Если задача не разрешает генерацию или исходники не точные — не запускайте её.",
    visual: {
      label: "Развилка производства",
      title: "Решение должно объясняться",
      items: [
        { label: "Снять", value: "Есть точный товар и безопасные условия", tone: "neutral" },
        { label: "Сгенерировать", value: "Есть точные права и разрешение задачи", tone: "good" },
        { label: "Остановиться", value: "Нет точного и разрешённого пути", tone: "bad" },
      ],
    },
  },
  {
    id: "paid_preflight",
    phase: "production",
    eyebrow: "Платный запуск",
    title: "Перед подтверждением стоимости — четыре контрольные точки",
    lead: "Учебный снимок экрана показывает 8 секунд и ориентир ≈ $2.32. В реальной задаче действительным является только значение на текущем экране подтверждения.",
    question: "Что проверить до единственного подтверждения?",
    input: "multi",
    options: [
      { value: "exact_assets", label: "Выбран точный товар и только одобренные исходники" },
      { value: "mode_duration", label: "Режим, 9:16, 8 секунд и аудио совпадают с задачей" },
      { value: "visible_price", label: "Стоимость видна до запуска и укладывается в разрешённый лимит" },
      { value: "single_confirm", label: "Подтверждение будет нажато один раз; затем проверяется статус существующей задачи" },
      { value: "ignore_price", label: "Стоимость можно не читать: портал сам отменит лишнее списание" },
      { value: "double_click", label: "Для надёжности нужно нажать запуск дважды" },
    ],
    correct: ["exact_assets", "mode_duration", "visible_price", "single_confirm"],
    success: "Верно. Платный запуск начинается только после проверки входов, режима и видимой цены.",
    retry: "Нельзя игнорировать цену или повторять подтверждение. Повторный клик может создать отдельную платную работу.",
    portalPath: "Создание видео → Подтверждение стоимости",
    evidence: "Сохранён preflight: товар, исходники, режим, длительность, аудио, цена и одно подтверждение.",
    stopRule: "Цена не видна, превышает лимит или параметры не совпадают — запуск блокируется.",
    visual: {
      label: "Preflight перед оплатой",
      title: "Проверьте — затем подтвердите один раз",
      items: [
        { label: "Товар", value: "Совпадает", tone: "good" },
        { label: "Режим", value: "9:16 · 8 сек · аудио", tone: "good" },
        { label: "Стоимость", value: "Видна до запуска", tone: "money" },
        { label: "Кнопка", value: "Одно подтверждение", tone: "platform" },
      ],
    },
  },
  {
    id: "paid_status_without_restart",
    phase: "production",
    eyebrow: "Контроль без нового списания",
    title: "Статус проверяется у существующего запуска",
    lead: "После подтверждения экран долго показывает «Обрабатывается». Создание нового варианта не является обновлением статуса.",
    question: "Как действовать безопасно?",
    input: "single",
    options: [
      { value: "check_existing", label: "Открыть существующий запуск и нажать проверку статуса без нового запуска" },
      { value: "start_again", label: "Создать ещё один вариант, чтобы первый завершился быстрее" },
      { value: "change_assets", label: "Запустить снова с другими фото, не дожидаясь результата" },
    ],
    correct: ["check_existing"],
    success: "Верно. Проверка статуса не создаёт новую платную задачу.",
    retry: "Не запускайте новый вариант. Сначала проверьте уже созданную платную работу.",
    portalPath: "Создание видео → Последние запуски → Проверить сейчас",
    evidence: "Проверен статус существующего запуска; нового подтверждения стоимости не было.",
    stopRule: "Если существующий запуск не найден или статус противоречив — сообщите руководителю, не платите повторно.",
    visual: {
      label: "Очередь генерации",
      title: "Один запуск — одна история статусов",
      sequence: [
        { time: "1", title: "Принят", text: "Стоимость подтверждена один раз" },
        { time: "2", title: "Обрабатывается", text: "Проверяйте существующую задачу" },
        { time: "3", title: "Готов / ошибка", text: "Откройте результат или передайте блокер" },
      ],
    },
  },
  {
    id: "quality_control",
    phase: "quality",
    eyebrow: "QC результата",
    title: "Красивые первые секунды не отменяют брак в конце",
    lead: "Просмотрите весь ролик со звуком и выберите все причины отклонения.",
    question: "Что является браком?",
    input: "multi",
    options: [
      { value: "warped_label", label: "Этикетка меняет буквы и форму в последнем кадре" },
      { value: "cut_speech", label: "Реплика блогера обрывается до окончания" },
      { value: "wrong_package", label: "На секунду появляется флакон другого объёма" },
      { value: "stable_color", label: "Красный цвет жидкости остаётся стабильным во всех кадрах" },
      { value: "clear_audio", label: "Речь слышна ровно, без клиппинга и провалов" },
    ],
    correct: ["warped_label", "cut_speech", "wrong_package"],
    success: "Верно. Искажение товара, обрыв речи и подмена упаковки блокируют публикацию.",
    retry: "QC проверяет весь ролик: товар, этикетку, движение, речь и финальный кадр.",
    portalPath: "Задачи → Проверка видео",
    evidence: "Зафиксированы таймкоды и типы дефектов; брак не передан в публикацию.",
    stopRule: "Хотя бы один критичный дефект — отклонить результат и не публиковать.",
    visual: {
      label: "Контроль качества",
      title: "Пять проверок до одобрения",
      items: [
        { label: "Товар", value: "Точный во всех кадрах", tone: "product" },
        { label: "Этикетка", value: "Не плывёт", tone: "neutral" },
        { label: "Речь", value: "Не обрывается", tone: "neutral" },
        { label: "Длительность", value: "Ровно по задаче", tone: "neutral" },
        { label: "Финал", value: "Без артефактов", tone: "good" },
      ],
    },
  },
  {
    id: "choose_platform_disclosure",
    phase: "publication",
    eyebrow: "Площадка и раскрытие",
    title: "Публикуйте только там и так, как назначено",
    lead: "В учебной задаче назначены VK Клипы. Решение по рекламному статусу и готовое раскрытие должны прийти из задачи или от руководителя.",
    question: "Какой маршрут безопасен?",
    input: "single",
    options: [
      { value: "assigned_vk", label: "Выбрать VK Клипы, применить назначенное раскрытие; если решения нет — остановить публикацию" },
      { value: "crosspost", label: "Сначала выложить в Instagram: там сейчас больше аудитория" },
      { value: "hide_brand", label: "Убрать название бренда и не включать раскрытие, чтобы не появилась рекламная метка" },
      { value: "publish_unknown", label: "Опубликовать без решения, а маркировку уточнить после" },
    ],
    correct: ["assigned_vk"],
    success: "Верно. Площадка и раскрытие не выбираются по настроению исполнителя.",
    retry: "Не меняйте площадку и не пытайтесь скрыть коммерческую связь. При сомнении публикация останавливается.",
    portalPath: "Публикации → Назначенная площадка",
    evidence: "Записаны площадка, решение по раскрытию и автор публикации.",
    stopRule: "Нет однозначного решения по раскрытию или доступна не та площадка — стоп до ответа руководителя.",
    showPlatformGuides: true,
    visual: {
      label: "Маршрут размещения",
      title: "Одна задача — одна назначенная площадка",
      items: [
        { label: "Instagram", value: "Только если назначен", tone: "neutral" },
        { label: "YouTube", value: "Только если назначен", tone: "neutral" },
        { label: "VK", value: "Назначен в этой задаче", tone: "good" },
      ],
    },
  },
  {
    id: "return_post_url",
    phase: "publication",
    eyebrow: "Возврат результата",
    title: "Порталу нужна ссылка на сам пост",
    lead: "После публикации откройте ролик как зритель, проверьте доступность и скопируйте его конкретный URL.",
    question: "Какую ссылку вернуть?",
    input: "single",
    options: [
      { value: "post_url", label: "https://vk.com/clip-123_456 — URL конкретного опубликованного клипа" },
      { value: "profile_url", label: "https://vk.com/creator — ссылка на профиль автора" },
      { value: "local_file", label: "C:\\Videos\\result.mp4 — путь к файлу на компьютере" },
      { value: "studio_url", label: "Ссылка на внутренний экран редактирования или статистики" },
    ],
    correct: ["post_url"],
    success: "Верно. Конкретный URL позволяет воспроизводимо проверить публикацию.",
    retry: "Профиль, локальный файл и внутренний кабинет не подтверждают конкретный пост.",
    portalPath: "Публикации → Подтвердить размещение",
    evidence: "URL конкретного поста открыт и проверен до отправки в портал.",
    stopRule: "Ссылка не открывается или ведёт не на ролик — не подтверждайте размещение.",
    visual: {
      label: "Проверка ссылки",
      title: "Не профиль. Не файл. Сам пост.",
      items: [
        { label: "Готово", value: "vk.com/clip-123_456", tone: "good" },
        { label: "Не подходит", value: "vk.com/creator", tone: "bad" },
        { label: "Не подходит", value: "result.mp4", tone: "bad" },
      ],
    },
  },
  {
    id: "record_metrics",
    phase: "result",
    eyebrow: "Метрики",
    title: "Цифра без времени и источника не является измерением",
    lead: "Первый снимок показывает 1 240 просмотров и 37 переходов. Выберите всё, что нужно сохранить.",
    question: "Что входит в корректный снимок метрик?",
    input: "multi",
    options: [
      { value: "values", label: "Просмотры и переходы ровно с экрана площадки" },
      { value: "observed_at", label: "Дата и время, когда цифры были увидены" },
      { value: "source", label: "Источник и подтверждение: площадка, URL поста или согласованный скриншот" },
      { value: "guess", label: "Округлённая оценка на глаз, если экран медленно загружается" },
      { value: "overwrite", label: "Заменить предыдущие цифры без нового времени наблюдения" },
    ],
    correct: ["values", "observed_at", "source"],
    success: "Верно. Каждая метрика хранится вместе с моментом и источником наблюдения.",
    retry: "Не угадывайте и не перезаписывайте историю без новой даты наблюдения.",
    portalPath: "Результаты → Добавить снимок",
    evidence: "Сохранены values + observed_at + source для конкретного URL поста.",
    stopRule: "Нет доступа к источнику или цифры не относятся к этому посту — снимок не сохраняется.",
    visual: {
      label: "Снимок результата",
      title: "Цифра + время + источник",
      items: [
        { label: "Просмотры", value: "1 240", tone: "neutral" },
        { label: "Переходы", value: "37", tone: "neutral" },
        { label: "Наблюдение", value: "15.07 · 14:30", tone: "platform" },
        { label: "Источник", value: "URL VK Клипа", tone: "good" },
      ],
    },
  },
  {
    id: "understand_payout",
    phase: "result",
    eyebrow: "Расчёт и выплата",
    title: "Начислено, одобрено и выплачено — три разных состояния",
    lead: "В портале сумма 800 ₽ имеет статус «Одобрено». Это решение по начислению, но ещё не подтверждение внешнего перевода.",
    question: "Что означает этот статус?",
    input: "single",
    options: [
      { value: "approved_not_paid", label: "Сумма одобрена, но деньги считаются переведёнными только после статуса «Выплачено»" },
      { value: "already_paid", label: "Деньги уже на счёте: статус «Одобрено» равен «Выплачено»" },
      { value: "views_change", label: "Сумма автоматически вырастет после каждого нового просмотра" },
    ],
    correct: ["approved_not_paid"],
    success: "Верно. Выплата завершена только когда портал показывает отдельный статус «Выплачено».",
    retry: "Не путайте решение по начислению с фактом перевода и не пересчитывайте сумму по просмотрам самостоятельно.",
    portalPath: "Выплаты → История начислений",
    evidence: "Проверены сумма, статус и дата последнего изменения выплаты.",
    stopRule: "Статус долго не меняется или сумма отличается от задачи — передайте вопрос руководителю, не исправляйте запись сами.",
    visual: {
      label: "Линия выплаты",
      title: "Три проверяемых статуса",
      sequence: [
        { time: "1", title: "Начислено", text: "Сумма появилась в расчёте" },
        { time: "2", title: "Одобрено", text: "Руководитель подтвердил начисление" },
        { time: "3", title: "Выплачено", text: "Внешний перевод отмечен завершённым" },
      ],
    },
  },
];

export const FIRST_SHIFT_FULL_SCENARIO = deepFreeze({
  id: "first_shift_full_v1",
  version: STATE_VERSION,
  title: "Первая смена: от задачи до выплаты",
  subtitle: "Практический маршрут для человека, который впервые открыл портал",
  durationMinutes: 35,
  passRule: "Каждый шаг должен быть решён без критической ошибки",
  phases: FIRST_SHIFT_FULL_PHASES,
  steps: STEPS,
});

const STEP_BY_ID = new Map(FIRST_SHIFT_FULL_SCENARIO.steps.map((step) => [step.id, step]));

function normalizeSelection(step, values) {
  const allowed = new Set(step.options.map((option) => option.value));
  const source = Array.isArray(values) ? values : [];
  const normalized = [...new Set(source.map(String).filter((value) => allowed.has(value)))];
  return step.input === "single" ? normalized.slice(0, 1) : normalized;
}

function sameSet(left, right) {
  if (left.length !== right.length) return false;
  const expected = new Set(right);
  return left.every((value) => expected.has(value));
}

export function evaluateFirstShiftFullAnswer(stepId, selectedValues) {
  const step = STEP_BY_ID.get(String(stepId || ""));
  if (!step) return { validStep: false, correct: false, selected: [], feedback: "Шаг не найден" };
  const selected = normalizeSelection(step, selectedValues);
  const correct = sameSet(selected, step.correct);
  return {
    validStep: true,
    correct,
    selected,
    feedback: correct ? step.success : step.retry,
    canContinue: correct,
  };
}

export function createFirstShiftFullState(source = {}) {
  const rawAnswers = source?.answers && typeof source.answers === "object" ? source.answers : {};
  const answers = {};
  FIRST_SHIFT_FULL_SCENARIO.steps.forEach((step) => {
    const normalized = normalizeSelection(step, rawAnswers[step.id]);
    if (normalized.length) answers[step.id] = normalized;
  });
  const checkedSource = Array.isArray(source?.checked) ? source.checked : [];
  const checked = [...new Set(checkedSource.map(String))].filter((stepId) => {
    const step = STEP_BY_ID.get(stepId);
    return step && evaluateFirstShiftFullAnswer(stepId, answers[stepId]).correct;
  });
  const attemptedSource = Array.isArray(source?.attempted) ? source.attempted : [];
  const attempted = [...new Set([...attemptedSource.map(String), ...checked])]
    .filter((stepId) => STEP_BY_ID.has(stepId));
  const maxIndex = FIRST_SHIFT_FULL_SCENARIO.steps.length - 1;
  const stepIndex = Math.min(maxIndex, Math.max(0, Number.parseInt(source?.stepIndex, 10) || 0));
  const completed = checked.length === FIRST_SHIFT_FULL_SCENARIO.steps.length && source?.completed === true;
  return { version: STATE_VERSION, stepIndex, answers, attempted, checked, completed };
}

export function firstShiftFullProgress(source = {}) {
  const state = createFirstShiftFullState(source);
  const total = FIRST_SHIFT_FULL_SCENARIO.steps.length;
  const passed = state.checked.length;
  return {
    passed,
    total,
    percent: total ? Math.round((passed / total) * 100) : 0,
    completed: state.completed,
  };
}

export function reduceFirstShiftFullState(source, event = {}) {
  const state = createFirstShiftFullState(source);
  const current = FIRST_SHIFT_FULL_SCENARIO.steps[state.stepIndex];
  const eventType = String(event.type || "");
  if (eventType === "restart") return createFirstShiftFullState();
  if (eventType === "previous") {
    return { ...state, stepIndex: Math.max(0, state.stepIndex - 1), completed: false };
  }
  const step = STEP_BY_ID.get(String(event.stepId || current?.id || ""));
  if (!step) return state;

  if (eventType === "select") {
    const value = String(event.value || "");
    if (!step.options.some((option) => option.value === value)) return state;
    const previous = normalizeSelection(step, state.answers[step.id]);
    let selected;
    if (step.input === "single") {
      selected = [value];
    } else if (event.selected === true) {
      selected = [...new Set([...previous, value])];
    } else if (event.selected === false) {
      selected = previous.filter((item) => item !== value);
    } else {
      selected = previous.includes(value)
        ? previous.filter((item) => item !== value)
        : [...previous, value];
    }
    const answers = { ...state.answers };
    if (selected.length) answers[step.id] = selected;
    else delete answers[step.id];
    return {
      ...state,
      answers,
      attempted: state.attempted.filter((stepId) => stepId !== step.id),
      checked: state.checked.filter((stepId) => stepId !== step.id),
      completed: false,
    };
  }

  if (eventType === "check") {
    const evaluation = evaluateFirstShiftFullAnswer(step.id, state.answers[step.id]);
    return {
      ...state,
      attempted: [...new Set([...state.attempted, step.id])],
      checked: evaluation.correct
        ? [...new Set([...state.checked, step.id])]
        : state.checked.filter((stepId) => stepId !== step.id),
      completed: false,
    };
  }

  if (eventType === "next") {
    const passed = state.checked.includes(current.id)
      && evaluateFirstShiftFullAnswer(current.id, state.answers[current.id]).correct;
    if (!passed) return state;
    if (state.stepIndex === FIRST_SHIFT_FULL_SCENARIO.steps.length - 1) {
      const allPassed = FIRST_SHIFT_FULL_SCENARIO.steps.every((item) => state.checked.includes(item.id));
      return { ...state, completed: allPassed };
    }
    return { ...state, stepIndex: state.stepIndex + 1, completed: false };
  }

  return state;
}

export function firstShiftFullScenarioMarkup(source = {}) {
  const state = createFirstShiftFullState(source);
  const progress = firstShiftFullProgress(state);
  if (state.completed) return completionMarkup(state, progress);
  const step = FIRST_SHIFT_FULL_SCENARIO.steps[state.stepIndex];
  const selected = state.answers[step.id] || [];
  const wasChecked = state.attempted.includes(step.id) || Boolean(source?.showFeedback);
  const evaluation = wasChecked ? evaluateFirstShiftFullAnswer(step.id, selected) : null;
  const phase = FIRST_SHIFT_FULL_PHASES.find((item) => item.id === step.phase);
  const canContinue = state.checked.includes(step.id) && evaluateFirstShiftFullAnswer(step.id, selected).correct;

  return `
    <section class="first-shift-full" aria-labelledby="first-shift-full-title" data-first-shift-version="${STATE_VERSION}">
      <header class="first-shift-full__hero">
        <div>
          <p class="first-shift-full__eyebrow">Учебная смена · ${FIRST_SHIFT_FULL_SCENARIO.durationMinutes} минут</p>
          <h1 id="first-shift-full-title" tabindex="-1">${escapeHtml(FIRST_SHIFT_FULL_SCENARIO.title)}</h1>
          <p>${escapeHtml(FIRST_SHIFT_FULL_SCENARIO.subtitle)}</p>
        </div>
        <div class="first-shift-full__progress-copy"><strong>${progress.passed}/${progress.total}</strong><span>решений принято</span></div>
      </header>
      <div class="first-shift-full__progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress.percent}" aria-label="Прогресс учебной смены"><span style="width:${progress.percent}%"></span></div>
      ${phaseRailMarkup(step.phase, state)}
      <div class="first-shift-full__workspace">
        <article class="first-shift-full__lesson">
          <div class="first-shift-full__step-heading">
            <span>${String(state.stepIndex + 1).padStart(2, "0")}</span>
            <div><p>${escapeHtml(step.eyebrow)} · ${escapeHtml(phase?.label || "Шаг")}</p><h2 id="first-shift-step-title" tabindex="-1">${escapeHtml(step.title)}</h2></div>
          </div>
          <p class="first-shift-full__lead">${escapeHtml(step.lead)}</p>
          ${visualMarkup(step.visual)}
          <div class="first-shift-full__instruction-grid">
            <div><span>В портале</span><strong>${escapeHtml(step.portalPath)}</strong></div>
            <div><span>Что сохранить</span><strong>${escapeHtml(step.evidence)}</strong></div>
          </div>
          <div class="first-shift-full__stop"><span aria-hidden="true">!</span><div><strong>Стоп-правило</strong><p>${escapeHtml(step.stopRule)}</p></div></div>
        </article>
        <aside class="first-shift-full__decision" aria-labelledby="first-shift-question">
          <form data-first-shift-form data-step-id="${escapeHtml(step.id)}">
            <fieldset>
              <legend id="first-shift-question">${escapeHtml(step.question)}</legend>
              <p class="first-shift-full__choice-hint">${step.input === "multi" ? "Можно выбрать несколько вариантов" : "Выберите один вариант"}</p>
              <div class="first-shift-full__options">${optionsMarkup(step, selected)}</div>
            </fieldset>
            ${evaluation ? feedbackMarkup(evaluation) : ""}
            <button class="first-shift-full__button first-shift-full__button--check" type="button" data-action="${FIRST_SHIFT_FULL_ACTIONS.check}" data-step-id="${escapeHtml(step.id)}" ${selected.length ? "" : "disabled"}>Проверить решение</button>
          </form>
        </aside>
      </div>
      ${step.showPlatformGuides ? platformGuidesMarkup() : ""}
      <footer class="first-shift-full__footer">
        <button class="first-shift-full__button first-shift-full__button--secondary" type="button" data-action="${FIRST_SHIFT_FULL_ACTIONS.previous}" ${state.stepIndex === 0 ? "disabled" : ""}>← Назад</button>
        <span>Шаг ${state.stepIndex + 1} из ${FIRST_SHIFT_FULL_SCENARIO.steps.length}</span>
        <button class="first-shift-full__button" type="button" data-action="${FIRST_SHIFT_FULL_ACTIONS.next}" ${canContinue ? "" : "disabled"}>${state.stepIndex === FIRST_SHIFT_FULL_SCENARIO.steps.length - 1 ? "Завершить смену" : "Следующий шаг →"}</button>
      </footer>
    </section>
  `;
}

function phaseRailMarkup(currentPhase, state) {
  return `<ol class="first-shift-full__phases" aria-label="Этапы учебной смены">${FIRST_SHIFT_FULL_PHASES.map((phase) => {
    const complete = phase.stepIds.every((stepId) => state.checked.includes(stepId));
    const current = phase.id === currentPhase;
    return `<li class="${complete ? "is-complete" : ""} ${current ? "is-current" : ""}" ${current ? 'aria-current="step"' : ""}><span>${escapeHtml(phase.number)}</span><div><strong>${escapeHtml(phase.label)}</strong><small>${escapeHtml(phase.hint)}</small></div></li>`;
  }).join("")}</ol>`;
}

function optionsMarkup(step, selected) {
  const type = step.input === "multi" ? "checkbox" : "radio";
  return step.options.map((option, index) => {
    const checked = selected.includes(option.value);
    const inputId = `first-shift-${step.id}-${index}`;
    return `
      <label class="first-shift-full__option" for="${escapeHtml(inputId)}">
        <input id="${escapeHtml(inputId)}" type="${type}" name="first-shift-${escapeHtml(step.id)}" value="${escapeHtml(option.value)}" data-action="${FIRST_SHIFT_FULL_ACTIONS.select}" data-step-id="${escapeHtml(step.id)}" ${checked ? "checked" : ""} />
        <span class="first-shift-full__option-mark" aria-hidden="true"></span>
        <span>${escapeHtml(option.label)}</span>
      </label>
    `;
  }).join("");
}

function feedbackMarkup(evaluation) {
  const tone = evaluation.correct ? "success" : "error";
  const icon = evaluation.correct ? "✓" : "!";
  return `<div class="first-shift-full__feedback first-shift-full__feedback--${tone}" role="status" tabindex="-1"><span aria-hidden="true">${icon}</span><p>${escapeHtml(evaluation.feedback)}</p></div>`;
}

function visualMarkup(visual) {
  if (!visual) return "";
  const body = Array.isArray(visual.sequence)
    ? `<div class="first-shift-full__sequence">${visual.sequence.map((item) => `<div><span>${escapeHtml(item.time)}</span><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.text)}</small></div>`).join("")}</div>`
    : `<div class="first-shift-full__visual-items">${(visual.items || []).map((item) => `<div data-tone="${escapeHtml(item.tone || "neutral")}"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></div>`).join("")}</div>`;
  return `<section class="first-shift-full__visual" aria-label="${escapeHtml(visual.label)}"><p>${escapeHtml(visual.label)}</p><h4>${escapeHtml(visual.title)}</h4>${body}</section>`;
}

function platformGuidesMarkup() {
  return `
    <section class="first-shift-full__platforms" aria-labelledby="first-shift-platforms-title">
      <div class="first-shift-full__section-heading"><p>Три площадки</p><h3 id="first-shift-platforms-title">Кнопки различаются, контрольный принцип один</h3><span>${escapeHtml(FIRST_SHIFT_FULL_POLICY_REFERENCES.interfaceNote)}</span></div>
      <div class="first-shift-full__platform-grid">${Object.values(FIRST_SHIFT_PLATFORM_GUIDES).map((guide) => `
        <article>
          <div class="first-shift-full__platform-title"><span>${escapeHtml(guide.icon)}</span><h4>${escapeHtml(guide.label)}</h4></div>
          <ol>${guide.route.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>
          <p><strong>Раскрытие:</strong> ${escapeHtml(guide.disclosure)}</p>
          <p><strong>В портал:</strong> ${escapeHtml(guide.finalEvidence)}</p>
          ${guide.sourceUrl ? `<a href="${escapeHtml(guide.sourceUrl)}" target="_blank" rel="noopener noreferrer">Официальная справка ↗</a>` : `<small>Инструкция по раскрытию берётся из текущей задачи.</small>`}
        </article>
      `).join("")}</div>
    </section>
  `;
}

function completionMarkup(state, progress) {
  return `
    <section class="first-shift-full first-shift-full--complete" aria-labelledby="first-shift-full-title" data-first-shift-version="${STATE_VERSION}">
      <div class="first-shift-full__completion-mark" aria-hidden="true">✓</div>
      <p class="first-shift-full__eyebrow">Учебная смена завершена</p>
      <h1 id="first-shift-full-title" tabindex="-1">Вы прошли полный путь от задачи до выплаты</h1>
      <p>Принято ${progress.passed} из ${progress.total} безопасных решений. В реальной работе при любом расхождении действует стоп-правило и передача руководителю.</p>
      <div class="first-shift-full__completion-grid">${FIRST_SHIFT_FULL_PHASES.map((phase) => `<div><span>${escapeHtml(phase.number)}</span><strong>${escapeHtml(phase.label)}</strong><small>${escapeHtml(phase.hint)}</small></div>`).join("")}</div>
      <button class="first-shift-full__button first-shift-full__button--secondary" type="button" data-action="${FIRST_SHIFT_FULL_ACTIONS.restart}">Пройти смену ещё раз</button>
    </section>
  `;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
