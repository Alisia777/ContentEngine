const PLATFORM_ORDER = Object.freeze(["instagram", "youtube", "vk"]);
const STEP_ORDER = Object.freeze(["account", "warmup", "publication", "review", "link", "result"]);
const MAX_PLATFORMS = 3;
const MAX_OPTIONS = 4;
export const PLATFORM_SIMULATOR_PASS_PERCENT = 80;
export const PLATFORM_SIMULATOR_MIN_REASONING_LENGTH = 50;
export const PLATFORM_SIMULATOR_MIN_REASONING_WORDS = 8;
export const PLATFORM_SIMULATOR_MIN_DISTINCT_WORDS = 6;

const STEP_META = Object.freeze({
  account: Object.freeze({ number: "01", shortLabel: "Аккаунт" }),
  warmup: Object.freeze({ number: "02", shortLabel: "Прогрев" }),
  publication: Object.freeze({ number: "03", shortLabel: "Публикация" }),
  review: Object.freeze({ number: "04", shortLabel: "Контроль" }),
  link: Object.freeze({ number: "05", shortLabel: "Ссылка" }),
  result: Object.freeze({ number: "06", shortLabel: "Результат" }),
});

const RAW_PLATFORM_SIMULATORS = {
  instagram: {
    name: "Instagram",
    format: "Reels",
    accent: "coral",
    summary: "Репетиция безопасного пути: подготовить живой аккаунт, разместить только согласованный Reels и вернуть проверяемый результат.",
    steps: [
      {
        id: "account",
        title: "Подготовьте понятный живой аккаунт",
        instruction: "Профиль должен выглядеть как настоящий профиль автора, а не как одноразовая рекламная витрина.",
        mockTitle: "Карточка профиля перед первым рабочим днём",
        mockItems: ["аватар и понятное имя", "заполненное описание без громких обещаний", "двухфакторная защита и доступ только у владельца"],
        prompt: "Какой аккаунт безопаснее взять в работу?",
        options: [
          { id: "empty", label: "Только что созданный пустой профиль с названием товара" },
          { id: "complete", label: "Оформленный профиль автора с защищённым входом и обычными публикациями" },
          { id: "borrowed", label: "Взять давно созданный профиль партнёра через общий командный вход" },
        ],
        success: "Аккаунт подготовлен: он понятен человеку и защищён.",
        proof: "Чек-лист оформления аккаунта",
      },
      {
        id: "warmup",
        title: "Проведите спокойный прогрев",
        instruction: "Новый профиль нельзя сразу превращать в конвейер одинаковых действий. Сначала покажите нормальную человеческую активность.",
        mockTitle: "Первые дни аккаунта",
        mockItems: ["заходить с привычного устройства", "заполнять профиль постепенно", "смотреть и публиковать обычный контент без массовых действий"],
        prompt: "Что сделать в первые дни?",
        options: [
          { id: "burst", label: "За час подписаться на сотни людей и сразу выложить много Reels" },
          { id: "calm", label: "Несколько дней пользоваться профилем естественно и наращивать активность постепенно" },
          { id: "automation", label: "Подключить сервис ускоренного старта с гарантированными реакциями" },
        ],
        success: "Прогрев пройден без резких и массовых действий.",
        proof: "Учебный календарь прогрева",
      },
      {
        id: "publication",
        title: "Соберите согласованный Reels",
        instruction: "До размещения сверьте файл, товар, текст, права и указание рекламного характера по рабочему заданию.",
        mockTitle: "Экран проверки черновика",
        mockItems: ["одобренный вертикальный файл", "точный товар и проверенные формулировки", "маркировка и раскрытие по заданию — их нельзя скрывать"],
        prompt: "Как поступить перед размещением?",
        options: [
          { id: "hide_label", label: "Оформить ролик как личную рекомендацию и не заполнять рекламные поля" },
          { id: "approved", label: "Сверить одобренный файл и текст с заданием, затем подготовить черновик" },
          { id: "change", label: "Самостоятельно усилить обещания результата в подписи" },
        ],
        success: "Черновик Reels безопасно подготовлен. В симуляторе ничего не опубликовано.",
        proof: "Карточка проверки черновика",
      },
      {
        id: "review",
        title: "Проведите контроль допуска",
        instruction: "Перед размещением сопоставьте товар в кадре, исходники, согласованный текст и разрешение руководителя как один комплект.",
        mockTitle: "Стоп-лист перед Reels",
        mockItems: ["упаковка и артикул совпадают с задачей", "музыка и визуалы имеют подтверждённые права", "финальная версия получила явный допуск"],
        prompt: "В ролике верный сценарий, но этикетка похожа на другую версию товара. Что делать?",
        options: [
          { id: "visual_close", label: "Выпустить: зритель не заметит небольшое отличие упаковки" },
          { id: "crop", label: "Обрезать крупный план этикетки и оставить остальной ролик" },
          { id: "hold", label: "Остановить выпуск, сверить артикул и вернуть ролик на повторную проверку" },
        ],
        success: "Допуск подтверждён только после сверки товара, прав и финальной версии.",
        proof: "Протокол контроля допуска",
      },
      {
        id: "link",
        title: "Проверьте постоянную ссылку",
        instruction: "После реальной публикации сотрудник открывает материал как обычный зритель и копирует постоянную ссылку. Здесь вы только репетируете выбор.",
        mockTitle: "Проверка доступности результата",
        mockItems: ["ролик открывается не только автору", "ссылка ведёт на конкретный Reels", "видео, подпись и товар совпадают с заданием"],
        prompt: "Какую ссылку вернуть руководителю?",
        options: [
          { id: "profile", label: "Ссылку на профиль — руководитель сам найдёт ролик" },
          { id: "draft", label: "Адрес из экрана черновика, доступный только автору" },
          { id: "permalink", label: "Постоянную ссылку на конкретный Reels после проверки со стороны зрителя" },
        ],
        success: "Выбрана проверяемая постоянная ссылка на конкретный материал.",
        proof: "Учебная карточка ссылки",
      },
      {
        id: "result",
        title: "Зафиксируйте результат в портале",
        instruction: "Ссылка сама по себе не завершает задачу: приложите доказательство, укажите площадку и дождитесь статуса проверки.",
        mockTitle: "Карточка результата в рабочем портале",
        mockItems: ["Instagram · Reels", "постоянная ссылка и контрольный скриншот", "статус «Передано на проверку», а не «Выплачено»"],
        prompt: "Когда рабочий результат считается переданным?",
        options: [
          { id: "chat", label: "Когда ссылка отправлена сообщением в любой чат" },
          { id: "portal", label: "Когда ссылка и доказательство сохранены в нужной задаче, а портал подтвердил приём" },
          { id: "views", label: "Когда ролик набрал первые просмотры" },
        ],
        success: "Учебная смена Instagram завершена: результат оформлен для проверки.",
        proof: "Учебная квитанция передачи",
      },
    ],
  },
  youtube: {
    name: "YouTube",
    format: "Shorts",
    accent: "red",
    summary: "Репетиция пути Shorts: оформить канал, не спамить, проверить согласованную публикацию и сохранить точную ссылку.",
    steps: [
      {
        id: "account",
        title: "Настройте канал и защитите доступ",
        instruction: "До работы канал должен иметь владельца, понятное оформление, подтверждённый вход и резервный способ восстановления.",
        mockTitle: "Готовность канала",
        mockItems: ["название, аватар и описание", "подтверждённая учётная запись", "двухэтапная проверка и отсутствие общих паролей"],
        prompt: "Как подготовить новый канал?",
        options: [
          { id: "shared", label: "Оставить один командный вход, чтобы смены быстрее подменяли друг друга" },
          { id: "ready", label: "Оформить канал, подтвердить учётную запись и включить защиту входа" },
          { id: "anonymous", label: "Оставить канал пустым — оформление не влияет на доверие" },
        ],
        success: "Канал оформлен и защищён до начала публикаций.",
        proof: "Чек-лист готовности канала",
      },
      {
        id: "warmup",
        title: "Создайте естественную историю канала",
        instruction: "Прогрев не гарантирует отсутствие ограничений, но исключает очевидное спам-поведение нового канала.",
        mockTitle: "Безопасный старт",
        mockItems: ["обычные просмотры без накрутки", "постепенная настройка канала", "небольшой объём самостоятельного контента"],
        prompt: "Как начать работу нового канала?",
        options: [
          { id: "repeat", label: "Сразу загрузить десятки одинаковых Shorts" },
          { id: "organic", label: "Пользоваться каналом естественно и увеличивать частоту публикаций постепенно" },
          { id: "buy", label: "Запустить внешний пакет стартового продвижения с гарантированными просмотрами" },
        ],
        success: "Старт канала спланирован без спама и накруток.",
        proof: "Учебный план запуска канала",
      },
      {
        id: "publication",
        title: "Проверьте черновик Shorts",
        instruction: "Выберите вертикальный одобренный файл, точные сведения о товаре, подходящую видимость и обязательные раскрытия.",
        mockTitle: "Контроль перед выпуском",
        mockItems: ["вертикальный файл и корректный звук", "заголовок без ложных обещаний", "видимость и рекламные настройки по заданию"],
        prompt: "Какой маршрут правильный?",
        options: [
          { id: "publish_any", label: "Открыть общий доступ к первой версии и собрать замечания уже после выпуска" },
          { id: "check", label: "Сверить финальный файл, поля, права и раскрытия с заданием, затем подготовить выпуск" },
          { id: "promise", label: "Добавить в заголовок гарантированный результат для кликабельности" },
          { id: "rights", label: "Добавить трендовый фрагмент из подборки автора, указав его имя в описании" },
        ],
        success: "Черновик Shorts проверен. Симулятор не загружает и не публикует видео.",
        proof: "Карточка проверки Shorts",
      },
      {
        id: "review",
        title: "Проверьте права и режим доступа",
        instruction: "Финальный допуск объединяет проверку товара, лицензий, звука, видимости и версии файла.",
        mockTitle: "Контрольный просмотр Shorts",
        mockItems: ["точный товар виден в ключевых кадрах", "источник музыки и визуалов подтверждён", "общий доступ открывается только после допуска"],
        prompt: "Монтаж готов, но право на короткий музыкальный фрагмент не подтверждено. Как решить?",
        options: [
          { id: "short_use", label: "Оставить: несколько секунд обычно достаточно для свободного использования" },
          { id: "credit", label: "Указать исполнителя и оставить звук без повторного согласования" },
          { id: "replace", label: "Остановить выпуск и заменить звук на материал с подтверждёнными правами" },
        ],
        success: "Файл допущен только после подтверждения товара, прав и режима доступа.",
        proof: "Протокол прав и допуска",
      },
      {
        id: "link",
        title: "Скопируйте ссылку на конкретный Shorts",
        instruction: "В рабочем процессе ссылку проверяют в режиме зрителя: видео доступно, воспроизводится и соответствует заданию.",
        mockTitle: "Контроль ссылки",
        mockItems: ["ссылка на видео, не на Studio", "доступность с другой сессии", "финальный кадр и описание совпадают"],
        prompt: "Какой результат проверяемый?",
        options: [
          { id: "studio", label: "Внутренняя ссылка YouTube Studio" },
          { id: "channel", label: "Ссылка на главную страницу канала" },
          { id: "video", label: "Публично проверенная ссылка на конкретное видео" },
        ],
        success: "Выбрана ссылка на конкретный доступный Shorts.",
        proof: "Учебная карточка ссылки",
      },
      {
        id: "result",
        title: "Передайте доказательство, а не обещание",
        instruction: "В портале фиксируются площадка, ссылка, скриншот и время проверки. Статус выплаты не выставляется вручную.",
        mockTitle: "Результат задачи",
        mockItems: ["YouTube · Shorts", "ссылка и контрольный скриншот", "ожидание проверки руководителем"],
        prompt: "Что завершает передачу результата?",
        options: [
          { id: "verbal", label: "Сообщение «всё готово» без ссылки" },
          { id: "receipt", label: "Сохранённые в задаче ссылка и доказательство с подтверждением портала" },
          { id: "paid", label: "Самостоятельно выбранный статус «Выплачено»" },
        ],
        success: "Учебная смена YouTube завершена: доказательство готово к проверке.",
        proof: "Учебная квитанция передачи",
      },
    ],
  },
  vk: {
    name: "VK",
    format: "Клипы",
    accent: "blue",
    summary: "Репетиция VK Клипов: подготовить профиль или сообщество, пройти естественный старт и передать воспроизводимый результат.",
    steps: [
      {
        id: "account",
        title: "Выберите разрешённую точку публикации",
        instruction: "Заранее уточните в задаче, где размещать Клип: в личном профиле или в конкретном сообществе.",
        mockTitle: "Профиль или сообщество",
        mockItems: ["точно совпадает с назначением", "оформлено и доступно зрителю", "права администратора выданы адресно"],
        prompt: "Где готовить публикацию?",
        options: [
          { id: "any", label: "В любом сообществе, где уже есть права" },
          { id: "assigned", label: "В профиле или сообществе, прямо указанном в задаче, после проверки доступа" },
          { id: "password", label: "В давно ведущемся профиле партнёра через единый вход для команды" },
        ],
        success: "Назначенная точка публикации и права доступа проверены.",
        proof: "Чек-лист доступа VK",
      },
      {
        id: "warmup",
        title: "Запустите страницу без массовых действий",
        instruction: "Новый профиль или сообщество наполняют последовательно: оформление, обычная активность, несколько качественных материалов.",
        mockTitle: "Первые дни VK",
        mockItems: ["заполненная информация", "естественные просмотры и реакции", "постепенная частота без повторов и накрутки"],
        prompt: "Как выглядит безопасный старт?",
        options: [
          { id: "spam", label: "Одинаково разослать ссылку в десятки обсуждений" },
          { id: "natural", label: "Оформить страницу и постепенно добавлять нормальный разный контент без накрутки" },
          { id: "clone", label: "Загрузить серию одинаковых Клипов в первый день" },
          { id: "buy", label: "Подключить пакет гарантированного старта с первыми реакциями и просмотрами" },
        ],
        success: "Страница получает естественную историю без спама.",
        proof: "Учебный календарь запуска VK",
      },
      {
        id: "publication",
        title: "Подготовьте Клип по назначению",
        instruction: "Сверьте точное сообщество, финальный ролик, описание, права и рекламные требования до любого рабочего размещения.",
        mockTitle: "Проверка карточки Клипа",
        mockItems: ["назначенный профиль или сообщество", "одобренный вертикальный ролик", "корректные сведения и обязательные раскрытия"],
        prompt: "Что можно отправить на размещение?",
        options: [
          { id: "approved", label: "Только финальный ролик и текст после сверки с задачей и правилами" },
          { id: "raw", label: "Сначала открыть Клип зрителям, а финальную сверку провести по реакции аудитории" },
          { id: "mask", label: "Оформить как личный совет и не заполнять дополнительные рекламные поля" },
        ],
        success: "Карточка Клипа подготовлена безопасно. Реальной публикации не было.",
        proof: "Карточка проверки VK Клипа",
      },
      {
        id: "review",
        title: "Сверьте товар, права и сообщество",
        instruction: "Финальная проверка должна доказать не только качество ролика, но и точное назначение публикации.",
        mockTitle: "Контроль допуска VK Клипа",
        mockItems: ["артикул и упаковка совпадают", "сообщество совпадает с назначением", "все элементы ролика разрешены к использованию"],
        prompt: "Ролик одобрен, но в задаче указано другое сообщество той же команды. Ваше действие?",
        options: [
          { id: "same_owner", label: "Разместить здесь: владелец один, значит результат равноценен" },
          { id: "crosspost", label: "Разместить в обоих сообществах и вернуть более удачную ссылку" },
          { id: "clarify", label: "Остановиться и получить подтверждение точного сообщества до размещения" },
        ],
        success: "Точка публикации, товар и права подтверждены до выпуска.",
        proof: "Протокол назначения и допуска",
      },
      {
        id: "link",
        title: "Проверьте адрес конкретного Клипа",
        instruction: "В рабочей задаче результат должен открываться у проверяющего без административного доступа.",
        mockTitle: "Проверка со стороны зрителя",
        mockItems: ["конкретный Клип", "доступен обычному зрителю", "файл и описание совпадают с заданием"],
        prompt: "Какую ссылку сохранить?",
        options: [
          { id: "community", label: "Главную страницу сообщества" },
          { id: "admin", label: "Служебную ссылку из панели управления" },
          { id: "clip", label: "Проверенную зрительскую ссылку на конкретный Клип" },
        ],
        success: "Выбрана проверяемая ссылка на конкретный VK Клип.",
        proof: "Учебная карточка ссылки",
      },
      {
        id: "result",
        title: "Сохраните результат в назначенной задаче",
        instruction: "Зафиксируйте площадку, точную ссылку и контрольный скриншот. После этого ожидайте проверки, а не назначайте выплату сами.",
        mockTitle: "Передача результата",
        mockItems: ["VK · Клипы", "ссылка и доказательство доступности", "подтверждение приёма порталом"],
        prompt: "Какой финал смены правильный?",
        options: [
          { id: "portal", label: "Портал принял ссылку и доказательство в нужную задачу; статус — на проверке" },
          { id: "note", label: "Ссылка сохранена только в личных заметках" },
          { id: "delete", label: "После отправки ссылки можно сразу удалить Клип" },
        ],
        success: "Учебная смена VK завершена: результат передан на проверку.",
        proof: "Учебная квитанция передачи",
      },
    ],
  },
};

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.freeze(value);
  Object.values(value).forEach(deepFreeze);
  return value;
}

function cleanText(value, fallback = "", limit = 900) {
  const normalized = String(value ?? "").replace(/\s+/gu, " ").trim();
  return (normalized || fallback).slice(0, limit);
}

function cleanId(value, fallback) {
  const normalized = String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/gu, "_")
    .replace(/^_+|_+$/gu, "")
    .slice(0, 72);
  return normalized || fallback;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizeOption(raw, index, platformId, stepId) {
  if (!raw || typeof raw !== "object") return null;
  const label = cleanText(raw.label || raw.text, "", 360);
  if (!label) return null;
  return {
    id: cleanId(raw.id, `${platformId}_${stepId}_option_${index + 1}`),
    label,
  };
}

function normalizeStep(raw, index, platformId) {
  if (!raw || typeof raw !== "object") return null;
  const fallbackId = STEP_ORDER[index] || `step_${index + 1}`;
  const id = cleanId(raw.id, fallbackId);
  const options = (Array.isArray(raw.options) ? raw.options : [])
    .slice(0, MAX_OPTIONS)
    .map((option, optionIndex) => normalizeOption(option, optionIndex, platformId, id))
    .filter(Boolean);
  if (options.length < 2 || new Set(options.map((option) => option.id)).size !== options.length) return null;
  const mockItems = (Array.isArray(raw.mockItems) ? raw.mockItems : raw.mock_items || [])
    .slice(0, 5)
    .map((item) => cleanText(item, "", 220))
    .filter(Boolean);
  return {
    id,
    title: cleanText(raw.title, `Шаг ${index + 1}`, 180),
    instruction: cleanText(raw.instruction, "Выберите безопасное действие и прочитайте объяснение.", 700),
    mockTitle: cleanText(raw.mockTitle || raw.mock_title, "Учебный экран", 180),
    mockItems,
    prompt: cleanText(raw.prompt, "Какое действие выбрать?", 400),
    options,
    success: cleanText(raw.success, "Шаг выполнен верно.", 500),
    proof: cleanText(raw.proof, "Учебная отметка", 180),
  };
}

function normalizePlatform(raw, index) {
  if (!raw || typeof raw !== "object") return null;
  const id = cleanId(raw.id, PLATFORM_ORDER[index] || `platform_${index + 1}`);
  const steps = (Array.isArray(raw.steps) ? raw.steps : [])
    .slice(0, STEP_ORDER.length)
    .map((step, stepIndex) => normalizeStep(step, stepIndex, id))
    .filter(Boolean);
  if (steps.length !== STEP_ORDER.length) return null;
  if (new Set(steps.map((step) => step.id)).size !== steps.length) return null;
  return {
    id,
    name: cleanText(raw.name, `Площадка ${index + 1}`, 80),
    format: cleanText(raw.format, "Вертикальное видео", 80),
    accent: cleanId(raw.accent, "forest"),
    summary: cleanText(raw.summary, "Пройдите учебную репетицию публикации по шагам.", 600),
    steps,
  };
}

export function normalizePlatformSimulatorCatalog(raw = RAW_PLATFORM_SIMULATORS) {
  const source = Array.isArray(raw)
    ? raw
    : Object.entries(raw && typeof raw === "object" ? raw : {}).map(([id, value]) => ({ ...value, id }));
  const seen = new Set();
  const platforms = [];
  for (const [index, item] of source.slice(0, MAX_PLATFORMS).entries()) {
    const platform = normalizePlatform(item, index);
    if (!platform || seen.has(platform.id)) continue;
    seen.add(platform.id);
    platforms.push(platform);
  }
  return deepFreeze(platforms);
}

export const PLATFORM_SIMULATOR_CATALOG = normalizePlatformSimulatorCatalog();

function platformById(catalog, platformId) {
  return catalog.find((platform) => platform.id === String(platformId || "")) || catalog[0] || null;
}

function stepById(platform, stepId) {
  return platform?.steps.find((step) => step.id === String(stepId || "")) || platform?.steps[0] || null;
}

function normalizeStringMap(raw, allowedKeys, valueAllowed = null) {
  const result = {};
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return result;
  allowedKeys.forEach((key) => {
    const value = String(raw[key] ?? "");
    if (value && (!valueAllowed || valueAllowed(key, value))) result[key] = value;
  });
  return result;
}

function reasoningWords(value) {
  return cleanText(value, "", 800)
    .toLocaleLowerCase("ru-RU")
    .match(/[\p{L}\p{N}]{2,}/gu) || [];
}

export function platformSimulatorReasoningIsSubstantive(value) {
  const normalized = cleanText(value, "", 800);
  const words = reasoningWords(normalized);
  const structured = /риск\s*:.+(проверка|доказательство)\s*:.+(действие|следующий шаг)\s*:/iu.test(normalized);
  return normalized.length >= PLATFORM_SIMULATOR_MIN_REASONING_LENGTH
    && words.length >= PLATFORM_SIMULATOR_MIN_REASONING_WORDS
    && new Set(words).size >= PLATFORM_SIMULATOR_MIN_DISTINCT_WORDS
    && structured;
}

function normalizeServerResult(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const passed = raw.passed === true;
  const pending = raw.pending === true || String(raw.status || "").toLowerCase() === "pending";
  const failed = !pending && (raw.passed === false || ["failed", "retry_required", "error"].includes(String(raw.status || "").toLowerCase()));
  if (!passed && !pending && !failed) return null;
  const status = passed ? "passed" : pending ? "pending" : "failed";
  const scoreRaw = raw.score_percent ?? raw.score;
  const criticalRaw = raw.critical_error_count ?? raw.criticalErrorCount;
  return {
    status,
    passed,
    scoreProvided: scoreRaw !== undefined && scoreRaw !== null,
    score: Math.max(0, Math.min(100, Number(scoreRaw) || 0)),
    criticalProvided: criticalRaw !== undefined && criticalRaw !== null,
    criticalErrorCount: Math.max(0, Number(criticalRaw) || 0),
    receiptId: cleanText(raw.receipt_id ?? raw.receiptId ?? raw.attempt_id ?? raw.attemptId, "", 160),
    feedback: cleanText(raw.feedback, "", 600),
  };
}

export function createPlatformSimulatorState(platformId, raw = {}, catalogInput = PLATFORM_SIMULATOR_CATALOG) {
  const catalog = normalizePlatformSimulatorCatalog(catalogInput);
  const platform = platformById(catalog, platformId);
  if (!platform) return deepFreeze({
    platformId: "", activeStepId: "", selectedByStep: {}, reasoningByStep: {}, decisionsByStep: {},
    completedStepIds: [], feedbackByStep: {}, feedbackKindByStep: {}, score: 0, criticalErrorCount: 0,
    serverStatus: "draft", serverResult: null, readyToFinish: false, finished: false, passed: false, complete: false,
  });
  const stepIds = platform.steps.map((step) => step.id);
  const selectedByStep = normalizeStringMap(raw.selectedByStep, stepIds, (stepId, optionId) => (
    Boolean(stepById(platform, stepId)?.options.some((option) => option.id === optionId))
  ));
  const reasoningByStep = Object.fromEntries(
    Object.entries(normalizeStringMap(raw.reasoningByStep, stepIds))
      .map(([stepId, value]) => [stepId, cleanText(value, "", 800)]),
  );
  const requestedDecisions = raw.decisionsByStep && typeof raw.decisionsByStep === "object"
    ? raw.decisionsByStep
    : {};
  const decisionsByStep = {};
  const completedStepIds = [];
  for (const stepId of stepIds) {
    const requestedOptionId = String(requestedDecisions[stepId]?.optionId || "");
    const selectedOptionId = requestedOptionId || (
      Array.isArray(raw.completedStepIds) && raw.completedStepIds.map(String).includes(stepId)
        ? selectedByStep[stepId]
        : ""
    );
    const step = stepById(platform, stepId);
    const option = step?.options.find((item) => item.id === selectedOptionId) || null;
    if (!option) break;
    decisionsByStep[stepId] = {
      optionId: option.id,
      reasoning: cleanText(requestedDecisions[stepId]?.reasoning || reasoningByStep[stepId], "", 800),
    };
    if (!platformSimulatorReasoningIsSubstantive(decisionsByStep[stepId].reasoning)) {
      delete decisionsByStep[stepId];
      break;
    }
    completedStepIds.push(stepId);
  }
  const requestedFinished = raw.finished === true;
  const finished = requestedFinished && completedStepIds.length === stepIds.length;
  const serverResult = finished ? normalizeServerResult(raw.serverResult) : null;
  const serverStatus = serverResult?.status || (finished ? "pending" : "draft");
  const passed = finished && serverResult?.passed === true;
  const score = serverResult?.score || 0;
  const criticalErrorCount = serverResult?.criticalErrorCount || 0;
  const firstIncompleteIndex = stepIds.findIndex((stepId) => !completedStepIds.includes(stepId));
  const maximumOpenIndex = firstIncompleteIndex < 0 ? stepIds.length - 1 : firstIncompleteIndex;
  const requestedIndex = stepIds.indexOf(String(raw.activeStepId || ""));
  const activeIndex = requestedIndex >= 0 && requestedIndex <= maximumOpenIndex ? requestedIndex : maximumOpenIndex;
  const feedbackByStep = normalizeStringMap(raw.feedbackByStep, stepIds);
  const feedbackKindByStep = normalizeStringMap(raw.feedbackKindByStep, stepIds, (_stepId, value) => ["error", "success", "info"].includes(value));
  return deepFreeze({
    platformId: platform.id,
    activeStepId: stepIds[Math.max(0, activeIndex)] || "",
    selectedByStep,
    reasoningByStep,
    decisionsByStep,
    completedStepIds,
    feedbackByStep,
    feedbackKindByStep,
    score,
    criticalErrorCount,
    criticalErrorStepIds: [],
    serverStatus,
    serverResult,
    readyToFinish: !finished && completedStepIds.length === stepIds.length,
    finished,
    passed,
    complete: passed,
  });
}

export function simulatorProgress(state, catalogInput = PLATFORM_SIMULATOR_CATALOG) {
  const catalog = normalizePlatformSimulatorCatalog(catalogInput);
  const platform = platformById(catalog, state?.platformId);
  const total = platform?.steps.length || 0;
  const completed = platform
    ? platform.steps.filter((step) => state?.completedStepIds?.includes(step.id)).length
    : 0;
  return {
    completed,
    total,
    percent: total ? Math.round((completed / total) * 100) : 0,
    score: Math.max(0, Math.min(100, Number(state?.score) || 0)),
  };
}

export function platformSimulatorAttemptPayload(rawState, catalogInput = PLATFORM_SIMULATOR_CATALOG) {
  const catalog = normalizePlatformSimulatorCatalog(catalogInput);
  const state = createPlatformSimulatorState(rawState?.platformId, rawState, catalog);
  const platform = platformById(catalog, state.platformId);
  if (!platform || !state.finished) return null;
  const decisions = {};
  const rationales = {};
  platform.steps.forEach((step) => {
    const decision = state.decisionsByStep[step.id] || null;
    decisions[step.id] = String(decision?.optionId || "");
    rationales[step.id] = cleanText(decision?.reasoning, "", 800);
  });
  return deepFreeze({
    moduleCode: "publishing_funnel",
    walkthroughId: `platform_publish_${platform.id}`,
    platformId: platform.id,
    assessmentVersion: 1,
    decisionCount: Object.values(decisions).filter(Boolean).length,
    decisions,
    rationales,
  });
}

export function platformSimulatorAttemptReceipt(rawState, catalogInput = PLATFORM_SIMULATOR_CATALOG) {
  const catalog = normalizePlatformSimulatorCatalog(catalogInput);
  const state = createPlatformSimulatorState(rawState?.platformId, rawState, catalog);
  const platform = platformById(catalog, state.platformId);
  if (!platform || !state.finished) return null;
  return deepFreeze({
    receiptId: state.serverResult?.receiptId || "",
    moduleCode: "publishing_funnel",
    walkthroughId: `platform_publish_${platform.id}`,
    platformId: platform.id,
    decisionCount: platform.steps.filter((step) => state.decisionsByStep[step.id]).length,
    score: state.score,
    passPercent: PLATFORM_SIMULATOR_PASS_PERCENT,
    criticalErrorCount: state.criticalErrorCount,
    scoreProvided: state.serverResult?.scoreProvided === true,
    criticalProvided: state.serverResult?.criticalProvided === true,
    status: state.serverStatus,
    feedback: state.serverResult?.feedback || "",
    passed: state.passed,
  });
}

export function reducePlatformSimulatorState(rawState, action, catalogInput = PLATFORM_SIMULATOR_CATALOG) {
  const catalog = normalizePlatformSimulatorCatalog(catalogInput);
  const state = createPlatformSimulatorState(rawState?.platformId, rawState, catalog);
  const platform = platformById(catalog, state.platformId);
  if (!platform) return state;
  const currentStep = stepById(platform, state.activeStepId);
  const type = String(action?.type || "");
  const selectedByStep = { ...state.selectedByStep };
  const reasoningByStep = { ...state.reasoningByStep };
  const decisionsByStep = { ...state.decisionsByStep };
  const feedbackByStep = { ...state.feedbackByStep };
  const feedbackKindByStep = { ...state.feedbackKindByStep };
  let activeStepId = state.activeStepId;
  let finished = state.finished;

  if (type === "reset") return createPlatformSimulatorState(platform.id, {}, catalog);
  if (type === "apply-server-result" && state.finished) {
    return createPlatformSimulatorState(platform.id, {
      ...state,
      serverResult: action.result,
      finished: true,
    }, catalog);
  }
  if (state.finished) return state;

  if (type === "select-answer") {
    const step = stepById(platform, action.stepId || activeStepId);
    const optionId = String(action.optionId || "");
    if (
      step
      && step.id === activeStepId
      && !decisionsByStep[step.id]
      && step.options.some((option) => option.id === optionId)
    ) {
      selectedByStep[step.id] = optionId;
      delete feedbackByStep[step.id];
      delete feedbackKindByStep[step.id];
    }
  }

  if (type === "set-reasoning") {
    const step = stepById(platform, action.stepId || activeStepId);
    if (step && step.id === activeStepId && !decisionsByStep[step.id]) {
      reasoningByStep[step.id] = cleanText(action.reasoning, "", 800);
      delete feedbackByStep[step.id];
      delete feedbackKindByStep[step.id];
    }
  }

  if (type === "edit-step") {
    const targetId = String(action.stepId || activeStepId);
    const targetIndex = platform.steps.findIndex((step) => step.id === targetId);
    if (targetIndex >= 0 && decisionsByStep[targetId]) {
      platform.steps.slice(targetIndex).forEach((step, offset) => {
        delete decisionsByStep[step.id];
        delete feedbackByStep[step.id];
        delete feedbackKindByStep[step.id];
        if (offset > 0) {
          delete selectedByStep[step.id];
          delete reasoningByStep[step.id];
        }
      });
      activeStepId = targetId;
      feedbackByStep[targetId] = "Решение открыто для изменения. После правки снова зафиксируйте его; более поздние этапы нужно будет пройти заново.";
      feedbackKindByStep[targetId] = "info";
    }
  }

  if (type === "check") {
    const step = currentStep;
    const selectedId = selectedByStep[step.id] || "";
    const option = step.options.find((item) => item.id === selectedId) || null;
    const reasoning = cleanText(reasoningByStep[step.id], "", 800);
    if (!option) {
      feedbackByStep[step.id] = "Сначала выберите один вариант — после проверки появится понятное объяснение.";
      feedbackKindByStep[step.id] = "error";
    } else if (!platformSimulatorReasoningIsSubstantive(reasoning)) {
      feedbackByStep[step.id] = `Заполните «Риск: … Проверка: … Действие: …»: минимум ${PLATFORM_SIMULATOR_MIN_REASONING_LENGTH} символов, ${PLATFORM_SIMULATOR_MIN_REASONING_WORDS} слов и ${PLATFORM_SIMULATOR_MIN_DISTINCT_WORDS} разных содержательных слов.`;
      feedbackKindByStep[step.id] = "error";
    } else if (!decisionsByStep[step.id]) {
      decisionsByStep[step.id] = {
        optionId: option.id,
        reasoning,
      };
      feedbackByStep[step.id] = "Решение и обоснование зафиксированы. Итоговую оценку сервер выдаст только после всех шести этапов.";
      feedbackKindByStep[step.id] = "info";
    }
  }

  if (type === "next") {
    const index = platform.steps.findIndex((step) => step.id === activeStepId);
    if (decisionsByStep[activeStepId] && index >= 0 && index < platform.steps.length - 1) {
      activeStepId = platform.steps[index + 1].id;
    }
  }

  if (type === "finish-attempt") {
    const answeredCount = platform.steps.filter((step) => decisionsByStep[step.id]).length;
    if (answeredCount === platform.steps.length) finished = true;
  }

  if (type === "go-to-step") {
    const targetId = String(action.stepId || "");
    const targetIndex = platform.steps.findIndex((step) => step.id === targetId);
    const firstIncompleteIndex = platform.steps.findIndex((step) => !decisionsByStep[step.id]);
    const maximumOpenIndex = firstIncompleteIndex < 0 ? platform.steps.length - 1 : firstIncompleteIndex;
    if (targetIndex >= 0 && targetIndex <= maximumOpenIndex) activeStepId = targetId;
    else {
      feedbackByStep[activeStepId] = "Этот этап пока закрыт. Завершите текущий шаг — следующий откроется автоматически.";
      feedbackKindByStep[activeStepId] = "info";
    }
  }

  return createPlatformSimulatorState(platform.id, {
    activeStepId,
    selectedByStep,
    reasoningByStep,
    decisionsByStep,
    feedbackByStep,
    feedbackKindByStep,
    finished,
    serverResult: state.serverResult,
  }, catalog);
}

export function createPlatformSimulatorSession(raw = {}, catalogInput = PLATFORM_SIMULATOR_CATALOG) {
  const catalog = normalizePlatformSimulatorCatalog(catalogInput);
  const requestedPlatformId = String(raw.activePlatformId || "");
  const activePlatform = platformById(catalog, requestedPlatformId);
  const states = {};
  catalog.forEach((platform) => {
    states[platform.id] = createPlatformSimulatorState(platform.id, raw.states?.[platform.id] || {}, catalog);
  });
  return deepFreeze({ activePlatformId: activePlatform?.id || catalog[0]?.id || "", states });
}

export function reducePlatformSimulatorSession(rawSession, action, catalogInput = PLATFORM_SIMULATOR_CATALOG) {
  const catalog = normalizePlatformSimulatorCatalog(catalogInput);
  const session = createPlatformSimulatorSession(rawSession, catalog);
  const requestedPlatform = platformById(catalog, action?.platformId || session.activePlatformId);
  if (!requestedPlatform) return session;
  if (action?.type === "select-platform") {
    return createPlatformSimulatorSession({ ...session, activePlatformId: requestedPlatform.id }, catalog);
  }
  const states = { ...session.states };
  states[requestedPlatform.id] = reducePlatformSimulatorState(states[requestedPlatform.id], action, catalog);
  return createPlatformSimulatorSession({ activePlatformId: session.activePlatformId, states }, catalog);
}

function optionMarkup(platform, step, option) {
  const inputId = `platform-simulator-${platform.id}-${step.id}-${option.id}`;
  return `
    <label class="training-platform-simulator__option" for="${escapeHtml(inputId)}">
      <input id="${escapeHtml(inputId)}" type="radio" name="platform-simulator-${escapeHtml(platform.id)}-${escapeHtml(step.id)}" value="${escapeHtml(option.id)}" data-simulator-option data-platform-id="${escapeHtml(platform.id)}" data-step-id="${escapeHtml(step.id)}" />
      <span><i aria-hidden="true"></i>${escapeHtml(option.label)}</span>
    </label>
  `;
}

function stepMarkup(platform, step, index) {
  const titleId = `platform-simulator-${platform.id}-${step.id}-title`;
  const feedbackId = `platform-simulator-${platform.id}-${step.id}-feedback`;
  const reasoningId = `platform-simulator-${platform.id}-${step.id}-reasoning`;
  const reasoningHelpId = `${reasoningId}-help`;
  return `
    <section class="training-platform-simulator__step" data-simulator-step="${escapeHtml(step.id)}" data-training-frame data-training-frame-id="platform_${escapeHtml(platform.id)}_${escapeHtml(step.id)}" data-training-frame-index="${index}" aria-labelledby="${escapeHtml(titleId)}" aria-hidden="${index ? "true" : "false"}"${index ? " hidden" : ""}>
      <div class="training-platform-simulator__lesson">
        <p class="training-platform-simulator__kicker">${escapeHtml(STEP_META[step.id]?.number || String(index + 1).padStart(2, "0"))} · ${escapeHtml(STEP_META[step.id]?.shortLabel || "Практика")}</p>
        <h3 id="${escapeHtml(titleId)}" tabindex="-1">${escapeHtml(step.title)}</h3>
        <p>${escapeHtml(step.instruction)}</p>
        <div class="training-platform-simulator__mock" aria-label="${escapeHtml(step.mockTitle)}">
          <div class="training-platform-simulator__mock-top"><span aria-hidden="true"></span><strong>${escapeHtml(step.mockTitle)}</strong><em>учебный экран</em></div>
          <ul>${step.mockItems.map((item) => `<li><span aria-hidden="true">✓</span>${escapeHtml(item)}</li>`).join("")}</ul>
        </div>
      </div>
      <fieldset class="training-platform-simulator__decision" aria-describedby="${escapeHtml(feedbackId)}">
        <legend>${escapeHtml(step.prompt)}</legend>
        <div class="training-platform-simulator__options">
          ${step.options.map((option) => optionMarkup(platform, step, option)).join("")}
        </div>
        <label class="training-platform-simulator__reasoning" for="${escapeHtml(reasoningId)}">
          <span>Почему вы выбрали это действие?</span>
          <textarea id="${escapeHtml(reasoningId)}" rows="3" minlength="${PLATFORM_SIMULATOR_MIN_REASONING_LENGTH}" maxlength="800" required data-simulator-reasoning data-platform-id="${escapeHtml(platform.id)}" data-step-id="${escapeHtml(step.id)}" aria-describedby="${escapeHtml(reasoningHelpId)} ${escapeHtml(feedbackId)}" placeholder="Риск: … Проверка: … Действие: …"></textarea>
          <small id="${escapeHtml(reasoningHelpId)}">Три части «Риск / Проверка / Действие», минимум ${PLATFORM_SIMULATOR_MIN_REASONING_LENGTH} символов и ${PLATFORM_SIMULATOR_MIN_REASONING_WORDS} осмысленных слов. <b data-simulator-reasoning-count>0</b>/800</small>
        </label>
        <p class="training-platform-simulator__answer-policy">До финальной отправки решение можно изменить; более поздние этапы тогда откроются заново. Правильный вариант не показывается: все шесть решений оценивает сервер одновременно.</p>
        <div id="${escapeHtml(feedbackId)}" class="training-platform-simulator__feedback" data-simulator-feedback data-feedback-kind="idle" role="status" aria-live="polite" aria-atomic="true" tabindex="-1">Выберите действие и нажмите «Проверить решение».</div>
        <div class="training-platform-simulator__actions">
          <button type="button" class="training-platform-simulator__primary" data-simulator-action="check" data-platform-id="${escapeHtml(platform.id)}">Зафиксировать решение</button>
          <button type="button" data-simulator-action="edit-step" data-platform-id="${escapeHtml(platform.id)}" data-step-id="${escapeHtml(step.id)}" hidden>Изменить решение</button>
          <button type="button" data-simulator-action="${index === platform.steps.length - 1 ? "finish-attempt" : "next"}" data-platform-id="${escapeHtml(platform.id)}" disabled>${index === platform.steps.length - 1 ? "Подвести итог попытки" : "Следующий этап"}<span aria-hidden="true"> →</span></button>
        </div>
      </fieldset>
    </section>
  `;
}

function panelMarkup(platform, index) {
  const headingId = `platform-simulator-${platform.id}-title`;
  return `
    <article id="platform-simulator-panel-${escapeHtml(platform.id)}" class="training-platform-simulator training-platform-simulator--${escapeHtml(platform.accent)}" data-simulator-panel data-platform-id="${escapeHtml(platform.id)}" data-training-walkthrough="platform_publish_${escapeHtml(platform.id)}" data-training-course="publishing_funnel" data-training-step="0" data-training-step-count="${platform.steps.length}" data-training-duration-seconds="300" data-training-mode="practice" data-training-playing="false" data-training-practice-required="true" data-training-practice-complete="false" data-training-complete="false" role="tabpanel" aria-labelledby="platform-simulator-tab-${escapeHtml(platform.id)}"${index ? " hidden" : ""}>
      <header class="training-platform-simulator__header">
        <div>
          <p>${escapeHtml(platform.name)} · ${escapeHtml(platform.format)}</p>
          <h2 id="${escapeHtml(headingId)}">Учебная смена без риска</h2>
          <span>${escapeHtml(platform.summary)}</span>
        </div>
        <div class="training-platform-simulator__header-status">
          <div class="training-platform-simulator__progress-copy"><strong data-simulator-progress-label>0 из ${platform.steps.length}</strong><span>этапов освоено</span></div>
          <button type="button" class="training-platform-simulator__restart" data-simulator-action="reset" data-simulator-reset-global data-platform-id="${escapeHtml(platform.id)}">Начать попытку заново</button>
        </div>
      </header>
      <div class="training-platform-simulator__progress" role="progressbar" aria-label="Прогресс симулятора ${escapeHtml(platform.name)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-simulator-progress><span data-simulator-progress-fill style="width:0%"></span></div>
      <nav class="training-platform-simulator__steps" aria-label="Этапы учебной смены ${escapeHtml(platform.name)}">
        ${platform.steps.map((step, stepIndex) => `<button type="button" data-simulator-action="go-to-step" data-platform-id="${escapeHtml(platform.id)}" data-step-id="${escapeHtml(step.id)}" aria-current="${stepIndex ? "false" : "step"}"${stepIndex ? " disabled" : ""}><span>${escapeHtml(STEP_META[step.id]?.number || String(stepIndex + 1))}</span><strong>${escapeHtml(STEP_META[step.id]?.shortLabel || step.title)}</strong><i aria-hidden="true">✓</i></button>`).join("")}
      </nav>
      <div data-simulator-stage-host>
        ${platform.steps.map((step, stepIndex) => stepMarkup(platform, step, stepIndex)).join("")}
      </div>
      <section class="training-platform-simulator__receipt" data-simulator-receipt role="status" aria-live="polite" hidden>
        <span class="training-platform-simulator__receipt-icon" data-simulator-receipt-icon aria-hidden="true">✓</span>
        <div><p data-simulator-receipt-kicker>Серверная проверка</p><h3 data-simulator-receipt-title>Проверяем шесть решений: ${escapeHtml(platform.name)} · ${escapeHtml(platform.format)}</h3><span data-simulator-receipt-body>Ответы отправлены без подсказки ключа. Дождитесь серверной квитанции.</span><code data-simulator-receipt-id></code></div>
        <dl><div><dt>Баллы</dt><dd data-simulator-receipt-score>0%</dd></div><div><dt>Критические ошибки</dt><dd data-simulator-receipt-critical>0</dd></div></dl>
        <button type="button" data-simulator-action="reset" data-platform-id="${escapeHtml(platform.id)}">Пройти ещё раз</button>
      </section>
    </article>
  `;
}

export function trainingPlatformSimulatorsMarkup(rawCatalog = PLATFORM_SIMULATOR_CATALOG) {
  const catalog = normalizePlatformSimulatorCatalog(rawCatalog);
  if (!catalog.length) return "";
  return `
    <section class="training-platform-simulators" data-training-platform-simulators data-simulator-version="1" aria-labelledby="training-platform-simulators-title">
      <header class="training-platform-simulators__intro">
        <div><p>Практическая лаборатория</p><h2 id="training-platform-simulators-title">Потренируйтесь до реальной публикации</h2></div>
        <p>Выберите площадку и пройдите шесть связанных решений по порядку. Ответов в браузере нет: сервер оценивает весь маршрут после отправки.</p>
      </header>
      <div class="training-platform-simulators__notice" role="note"><span aria-hidden="true">◎</span><p><strong>Учебная симуляция — ничего не публикуется.</strong> Модуль не входит в соцсети, не загружает файлы, не создаёт ссылки и не меняет рабочие задачи.</p></div>
      <div class="training-platform-simulators__route" aria-label="Маршрут учебной смены">${STEP_ORDER.map((stepId) => `<span><i>${escapeHtml(STEP_META[stepId].number)}</i>${escapeHtml(STEP_META[stepId].shortLabel)}</span>`).join("<b aria-hidden=\"true\">→</b>")}</div>
      <div class="training-platform-simulators__tabs" role="tablist" aria-label="Выберите площадку. Стрелки влево и вправо переключают вкладки.">
        ${catalog.map((platform, index) => `<button id="platform-simulator-tab-${escapeHtml(platform.id)}" type="button" role="tab" aria-selected="${index ? "false" : "true"}" aria-controls="platform-simulator-panel-${escapeHtml(platform.id)}" tabindex="${index ? "-1" : "0"}" data-simulator-action="select-platform" data-platform-id="${escapeHtml(platform.id)}"><span>${escapeHtml(platform.name)}</span><small>${escapeHtml(platform.format)}</small></button>`).join("")}
      </div>
      <div class="training-platform-simulators__panels">
        ${catalog.map(panelMarkup).join("")}
      </div>
      <p class="training-platform-simulators__legal">Симулятор обучает рабочему маршруту, но не заменяет актуальные правила площадки, требования закона и указания конкретной задачи. Не пытайтесь скрывать рекламный характер материала или обходить маркировку.</p>
    </section>
  `;
}

function simulatorRoot(root) {
  if (!root || typeof root.querySelector !== "function") return null;
  if (typeof root.matches === "function" && root.matches("[data-training-platform-simulators]")) return root;
  return root.querySelector("[data-training-platform-simulators]");
}

function simulatorPanel(root, platformId = "") {
  if (!root || typeof root.querySelector !== "function") return null;
  if (typeof root.matches === "function" && root.matches("[data-simulator-panel]")) return root;
  const normalizedId = cleanId(platformId, "");
  return normalizedId
    ? root.querySelector(`[data-simulator-panel][data-platform-id="${normalizedId}"]`)
    : root.querySelector("[data-simulator-panel]:not([hidden])") || root.querySelector("[data-simulator-panel]");
}

export function syncPlatformSimulatorWalkthroughDOM(root, rawState, catalogInput = PLATFORM_SIMULATOR_CATALOG) {
  const catalog = normalizePlatformSimulatorCatalog(catalogInput);
  const state = createPlatformSimulatorState(rawState?.platformId, rawState, catalog);
  const platform = platformById(catalog, state.platformId);
  const panel = simulatorPanel(root, state.platformId);
  if (!platform || !panel) return state;
  const authoritativeComplete = panel.dataset?.trainingServerComplete === "true";
  const effectivePassed = authoritativeComplete || state.passed;
  const progress = simulatorProgress(state, catalog);
  const activeIndex = Math.max(0, platform.steps.findIndex((step) => step.id === state.activeStepId));
  panel.dataset.trainingStep = String(effectivePassed ? platform.steps.length - 1 : activeIndex);
  panel.dataset.trainingPracticeComplete = effectivePassed ? "true" : "false";
  panel.dataset.trainingComplete = effectivePassed ? "true" : "false";
  panel.dataset.simulatorScore = String(state.score);
  panel.dataset.simulatorCriticalErrors = String(state.criticalErrorCount);
  panel.dataset.simulatorServerStatus = state.serverStatus;
  panel.classList?.toggle?.("is-simulator-complete", effectivePassed);
  panel.classList?.toggle?.("is-simulator-failed", state.serverStatus === "failed");
  const globalReset = panel.querySelector?.("[data-simulator-reset-global]");
  if (globalReset) {
    globalReset.disabled = authoritativeComplete || state.serverStatus === "pending";
    globalReset.textContent = state.serverStatus === "pending"
      ? "Дождитесь проверки…"
      : "Начать попытку заново";
  }
  const label = panel.querySelector?.("[data-simulator-progress-label]");
  if (label) label.textContent = `${effectivePassed ? progress.total : progress.completed} из ${progress.total}`;
  const progressbar = panel.querySelector?.("[data-simulator-progress]");
  progressbar?.setAttribute?.("aria-valuenow", String(effectivePassed ? 100 : progress.percent));
  const fill = panel.querySelector?.("[data-simulator-progress-fill]");
  if (fill?.style) fill.style.width = `${effectivePassed ? 100 : progress.percent}%`;
  const firstIncompleteIndex = platform.steps.findIndex((step) => !state.completedStepIds.includes(step.id));
  const maximumOpenIndex = firstIncompleteIndex < 0 ? platform.steps.length - 1 : firstIncompleteIndex;
  panel.querySelectorAll?.('[data-simulator-action="go-to-step"]').forEach((button, index) => {
    const complete = state.completedStepIds.includes(String(button.dataset?.stepId || ""));
    button.disabled = effectivePassed || state.finished || index > maximumOpenIndex;
    button.setAttribute?.("aria-current", button.dataset?.stepId === state.activeStepId ? "step" : "false");
    button.dataset.simulatorStepComplete = complete ? "true" : "false";
  });
  panel.querySelectorAll?.("[data-simulator-step]").forEach((stepElement) => {
    const stepId = String(stepElement.dataset?.simulatorStep || "");
    const stepActive = stepId === state.activeStepId;
    stepElement.hidden = effectivePassed || !stepActive || state.finished;
    stepElement.setAttribute?.("aria-hidden", effectivePassed || !stepActive || state.finished ? "true" : "false");
    stepElement.querySelectorAll?.("[data-simulator-option]").forEach((input) => {
      input.checked = state.selectedByStep[stepId] === String(input.value || "");
      input.disabled = Boolean(state.decisionsByStep[stepId]);
    });
    const reasoning = stepElement.querySelector?.("[data-simulator-reasoning]");
    if (reasoning) {
      const value = state.reasoningByStep[stepId] || "";
      if (reasoning.value !== value) reasoning.value = value;
      reasoning.disabled = Boolean(state.decisionsByStep[stepId]);
      const count = stepElement.querySelector?.("[data-simulator-reasoning-count]");
      if (count) count.textContent = String(value.length);
    }
    const feedback = stepElement.querySelector?.("[data-simulator-feedback]");
    if (feedback) {
      feedback.textContent = state.feedbackByStep[stepId] || "Выберите действие и нажмите «Зафиксировать решение».";
      feedback.dataset.feedbackKind = state.feedbackKindByStep[stepId] || "idle";
    }
    const check = stepElement.querySelector?.('[data-simulator-action="check"]');
    if (check) check.disabled = state.completedStepIds.includes(stepId);
    const edit = stepElement.querySelector?.('[data-simulator-action="edit-step"]');
    if (edit) {
      const editable = !effectivePassed && !state.finished && state.completedStepIds.includes(stepId);
      edit.hidden = !editable;
      edit.disabled = !editable;
    }
    const next = stepElement.querySelector?.('[data-simulator-action="next"], [data-simulator-action="finish-attempt"]');
    if (next) next.disabled = !state.completedStepIds.includes(stepId);
  });
  const receipt = panel.querySelector?.("[data-simulator-receipt]");
  if (receipt) {
    receipt.hidden = !state.finished && !authoritativeComplete;
    if (authoritativeComplete && !state.finished) {
      receipt.dataset.simulatorPassed = "true";
      receipt.dataset.simulatorStatus = "passed";
      receipt.querySelector?.("[data-simulator-receipt-icon]")?.replaceChildren?.("✓");
      const kicker = receipt.querySelector?.("[data-simulator-receipt-kicker]");
      if (kicker) kicker.textContent = "Подтверждено сервером";
      const title = receipt.querySelector?.("[data-simulator-receipt-title]");
      if (title) title.textContent = `Маршрут зачтён: ${platform.name} · ${platform.format}`;
      const body = receipt.querySelector?.("[data-simulator-receipt-body]");
      if (body) body.textContent = "Серверная квитанция уже сохранена в рабочем профиле. Повторно проходить лабораторию не нужно.";
      const receiptId = receipt.querySelector?.("[data-simulator-receipt-id]");
      if (receiptId) receiptId.textContent = "SERVER VERIFIED";
      const score = receipt.querySelector?.("[data-simulator-receipt-score]");
      if (score) score.textContent = "зачтено";
      const critical = receipt.querySelector?.("[data-simulator-receipt-critical]");
      if (critical) critical.textContent = "0";
      const reset = receipt.querySelector?.('[data-simulator-action="reset"]');
      if (reset) reset.disabled = true;
    }
    const attemptReceipt = platformSimulatorAttemptReceipt(state, catalog);
    if (attemptReceipt) {
      const pending = attemptReceipt.status === "pending";
      receipt.dataset.simulatorPassed = attemptReceipt.passed ? "true" : "false";
      receipt.dataset.simulatorStatus = attemptReceipt.status;
      receipt.dataset.simulatorScore = String(attemptReceipt.score);
      receipt.dataset.simulatorCriticalErrors = String(attemptReceipt.criticalErrorCount);
      const icon = receipt.querySelector?.("[data-simulator-receipt-icon]");
      if (icon) icon.textContent = pending ? "…" : attemptReceipt.passed ? "✓" : "!";
      const kicker = receipt.querySelector?.("[data-simulator-receipt-kicker]");
      if (kicker) kicker.textContent = pending ? "Серверная проверка" : attemptReceipt.passed ? "Практический маршрут пройден" : "Попытка не зачтена";
      const title = receipt.querySelector?.("[data-simulator-receipt-title]");
      if (title) title.textContent = pending
        ? `Проверяем шесть решений: ${platform.name} · ${platform.format}`
        : attemptReceipt.passed
          ? `Учебная квитанция: ${platform.name} · ${platform.format}`
          : `Нужна новая попытка: ${platform.name} · ${platform.format}`;
      const body = receipt.querySelector?.("[data-simulator-receipt-body]");
      if (body) body.textContent = pending
        ? "Ответы приняты к серверной оценке. Не закрывайте страницу до появления квитанции."
        : attemptReceipt.passed
          ? "Порог освоения достигнут без критических ошибок. Это не подтверждение реальной публикации."
          : attemptReceipt.feedback
            ? attemptReceipt.feedback
            : attemptReceipt.criticalErrorCount
            ? "Обнаружено критически опасное решение. Повторите материал и пройдите сценарий заново."
            : `Результат ниже ${PLATFORM_SIMULATOR_PASS_PERCENT}%. Разберите маршрут и повторите попытку.`;
      const receiptId = receipt.querySelector?.("[data-simulator-receipt-id]");
      if (receiptId) receiptId.textContent = attemptReceipt.receiptId;
      const score = receipt.querySelector?.("[data-simulator-receipt-score]");
      if (score) score.textContent = pending
        ? "—"
        : attemptReceipt.scoreProvided ? `${attemptReceipt.score}%` : attemptReceipt.passed ? "зачтено" : "скрыто";
      const critical = receipt.querySelector?.("[data-simulator-receipt-critical]");
      if (critical) critical.textContent = pending
        ? "—"
        : attemptReceipt.criticalProvided ? String(attemptReceipt.criticalErrorCount) : "скрыто";
      const reset = receipt.querySelector?.('[data-simulator-action="reset"]');
      if (reset) reset.disabled = pending;
    }
  }
  return state;
}

export function platformSimulatorWalkthroughSnapshot(root, platformId = "") {
  const panel = simulatorPanel(root, platformId);
  if (!panel) return null;
  const frames = Array.from(panel.querySelectorAll?.("[data-training-frame]") || []);
  const currentIndex = Math.max(
    0,
    Math.min(frames.length - 1, Number(panel.dataset?.trainingStep) || 0),
  );
  const complete = panel.dataset?.trainingComplete === "true";
  const receipt = panel.querySelector?.("[data-simulator-receipt]");
  return deepFreeze({
    moduleCode: String(panel.dataset?.trainingCourse || ""),
    walkthroughId: String(panel.dataset?.trainingWalkthrough || ""),
    currentStep: currentIndex,
    currentFrameId: String(frames[currentIndex]?.dataset?.trainingFrameId || ""),
    completedFrameIds: frames
      .slice(0, complete ? frames.length : currentIndex + 1)
      .map((frame) => String(frame.dataset?.trainingFrameId || ""))
      .filter(Boolean),
    durationSeconds: Math.max(1, Number(panel.dataset?.trainingDurationSeconds) || 1),
    score: Math.max(0, Math.min(100, Number(panel.dataset?.simulatorScore) || 0)),
    criticalErrors: Math.max(0, Number(panel.dataset?.simulatorCriticalErrors) || 0),
    receiptId: String(receipt?.querySelector?.("[data-simulator-receipt-id]")?.textContent || ""),
    complete,
  });
}

export function renderPlatformSimulatorSession(root, rawSession, catalogInput = PLATFORM_SIMULATOR_CATALOG) {
  const section = simulatorRoot(root);
  const catalog = normalizePlatformSimulatorCatalog(catalogInput);
  const session = createPlatformSimulatorSession(rawSession, catalog);
  if (!section) return session;
  section.querySelectorAll?.('[role="tab"][data-platform-id]').forEach((tab) => {
    const active = tab.dataset?.platformId === session.activePlatformId;
    tab.setAttribute?.("aria-selected", active ? "true" : "false");
    tab.setAttribute?.("tabindex", active ? "0" : "-1");
  });
  section.querySelectorAll?.("[data-simulator-panel]").forEach((panel) => {
    const platformId = String(panel.dataset?.platformId || "");
    const active = platformId === session.activePlatformId;
    panel.hidden = !active;
    const platform = platformById(catalog, platformId);
    const state = session.states[platformId];
    if (!platform || !state) return;
    syncPlatformSimulatorWalkthroughDOM(panel, state, catalog);
  });
  return session;
}

const BOUND_SIMULATORS = new WeakMap();

export function bindTrainingPlatformSimulators(root, options = {}) {
  const section = simulatorRoot(root);
  if (!section || typeof section.addEventListener !== "function") return () => {};
  BOUND_SIMULATORS.get(section)?.();
  const catalog = normalizePlatformSimulatorCatalog(options.catalog || PLATFORM_SIMULATOR_CATALOG);
  let session = createPlatformSimulatorSession(options.initialState || {}, catalog);
  const notify = (action) => {
    renderPlatformSimulatorSession(section, session, catalog);
    if (typeof options.onChange === "function") {
      options.onChange(
        session,
        action,
        platformSimulatorWalkthroughSnapshot(section, action?.platformId || session.activePlatformId),
      );
    }
  };
  const focusActiveStep = (platformId) => {
    const panel = section.querySelector?.(`[data-simulator-panel][data-platform-id="${platformId}"]`);
    const activeStep = panel?.querySelector?.('[data-simulator-step]:not([hidden])');
    const heading = activeStep?.querySelector?.("h3[tabindex='-1']");
    heading?.focus?.({ preventScroll: true });
    heading?.scrollIntoView?.({ behavior: "auto", block: "center" });
  };
  const focusReceipt = (platformId) => {
    const receipt = section.querySelector?.(
      `[data-simulator-panel][data-platform-id="${platformId}"] [data-simulator-receipt]:not([hidden])`,
    );
    receipt?.setAttribute?.("tabindex", "-1");
    receipt?.focus?.({ preventScroll: true });
  };
  const apply = (action, focusTarget = "") => {
    session = reducePlatformSimulatorSession(session, action, catalog);
    notify(action);
    if (focusTarget === "feedback") {
      const panel = section.querySelector?.(`[data-simulator-panel][data-platform-id="${session.activePlatformId}"]`);
      panel?.querySelector?.(`[data-simulator-step="${session.states[session.activePlatformId]?.activeStepId}"] [data-simulator-feedback]`)?.focus?.();
    }
    if (focusTarget === "step") focusActiveStep(session.activePlatformId);
    if (focusTarget === "receipt") focusReceipt(session.activePlatformId);
  };
  const submitFinishedAttempt = async (platformId) => {
    const payload = platformSimulatorAttemptPayload(session.states[platformId], catalog);
    if (!payload || typeof options.onSubmitAttempt !== "function") return;
    try {
      const raw = await options.onSubmitAttempt(payload, session);
      const result = raw?.attempt || raw?.result?.attempt || raw?.data?.attempt || raw?.result || raw?.data || raw || {};
      apply({ type: "apply-server-result", platformId, result });
    } catch (error) {
      apply({
        type: "apply-server-result",
        platformId,
        result: {
          passed: false,
          status: "error",
          feedback: String(error?.message || "Сервер не подтвердил попытку."),
        },
      });
    }
  };
  const handleClick = (event) => {
    const button = event.target?.closest?.("[data-simulator-action]");
    if (!button || !section.contains?.(button)) return;
    const actionName = String(button.dataset?.simulatorAction || "");
    const platformId = String(button.dataset?.platformId || session.activePlatformId);
    if (actionName === "select-platform") apply({ type: "select-platform", platformId });
    if (actionName === "go-to-step") apply({ type: "go-to-step", platformId, stepId: button.dataset?.stepId }, "step");
    if (actionName === "check") {
      const platformState = session.states[platformId];
      const panel = simulatorPanel(section, platformId);
      const reasoning = panel?.querySelector?.(
        `[data-simulator-step="${platformState?.activeStepId}"] [data-simulator-reasoning]`,
      );
      session = reducePlatformSimulatorSession(session, {
        type: "set-reasoning",
        platformId,
        stepId: platformState?.activeStepId,
        reasoning: reasoning?.value || "",
      }, catalog);
      apply({ type: "check", platformId }, "feedback");
    }
    if (actionName === "edit-step") apply({ type: "edit-step", platformId, stepId: button.dataset?.stepId }, "step");
    if (actionName === "next") apply({ type: "next", platformId }, "step");
    if (actionName === "finish-attempt") {
      apply({ type: "finish-attempt", platformId }, "receipt");
      void submitFinishedAttempt(platformId);
    }
    if (actionName === "reset") apply({ type: "reset", platformId }, "step");
  };
  const handleChange = (event) => {
    const input = event.target?.closest?.("[data-simulator-option]");
    if (!input || !section.contains?.(input)) return;
    apply({
      type: "select-answer",
      platformId: input.dataset?.platformId,
      stepId: input.dataset?.stepId,
      optionId: input.value,
    });
  };
  const handleInput = (event) => {
    const textarea = event.target?.closest?.("[data-simulator-reasoning]");
    if (!textarea || !section.contains?.(textarea)) return;
    session = reducePlatformSimulatorSession(session, {
      type: "set-reasoning",
      platformId: textarea.dataset?.platformId,
      stepId: textarea.dataset?.stepId,
      reasoning: textarea.value,
    }, catalog);
    const count = textarea.closest?.("[data-simulator-step]")?.querySelector?.("[data-simulator-reasoning-count]");
    if (count) count.textContent = String(String(textarea.value || "").trim().replace(/\s+/gu, " ").length);
  };
  const handleKeydown = (event) => {
    const tab = event.target?.closest?.('[role="tab"][data-platform-id]');
    if (!tab || !section.contains?.(tab) || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const tabs = Array.from(section.querySelectorAll?.('[role="tab"][data-platform-id]') || []);
    const currentIndex = Math.max(0, tabs.indexOf(tab));
    const nextIndex = event.key === "Home" ? 0
      : event.key === "End" ? tabs.length - 1
        : event.key === "ArrowLeft" ? (currentIndex - 1 + tabs.length) % tabs.length
          : (currentIndex + 1) % tabs.length;
    event.preventDefault?.();
    const nextTab = tabs[nextIndex];
    apply({ type: "select-platform", platformId: nextTab?.dataset?.platformId });
    nextTab?.focus?.();
  };
  section.addEventListener("click", handleClick);
  section.addEventListener("change", handleChange);
  section.addEventListener("input", handleInput);
  section.addEventListener("keydown", handleKeydown);
  const cleanup = () => {
    section.removeEventListener?.("click", handleClick);
    section.removeEventListener?.("change", handleChange);
    section.removeEventListener?.("input", handleInput);
    section.removeEventListener?.("keydown", handleKeydown);
    if (BOUND_SIMULATORS.get(section) === cleanup) BOUND_SIMULATORS.delete(section);
  };
  BOUND_SIMULATORS.set(section, cleanup);
  notify({ type: "init" });
  return cleanup;
}
