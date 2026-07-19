import { CreatorApi, mediaKindRequiresProduct } from "./supabase-api.js?v=20260718.2";
import {
  FINAL_EXAM_CODE,
  NAVIGATION_MODES,
  NAVIGATION_MODE_STORAGE_KEY,
  REQUIRED_MODULE_CODES,
  SIMPLE_WORKSPACE_TAB_KEYS,
  WORKSPACE_TABS,
} from "./catalog.js?v=20260716.3";
import {
  ACCOUNT_LAUNCH_PATH,
  accountLaunchCenterMarkup,
  accountLaunchGuideMarkup,
  accountLaunchSlugFromPath,
  evaluateAdvertisingAnswers,
} from "./account-launch-view.js?v=20260716.2";
import {
  managerDashboardMarkup,
  managerOperationalHealthMarkup,
} from "./manager-dashboard-view.js?v=20260718.1";
import {
  generationSpendAllowsMinor,
  generationSpendSnapshotMarkup,
  managerGenerationSpendMarkup,
  normalizeGenerationSpendOverview,
} from "./generation-spend-view.js?v=20260717.2";
import {
  accessCenterMarkup,
  ensureAccessCenterStyles,
  normalizeAccessCenterEmail,
  normalizeAccessCenterResult,
} from "./access-center-view.js?v=20260717.1";
import {
  normalizeProductResearch,
  productResearchInputMarkup,
  productResearchProgressMarkup,
  productResearchResultMarkup,
  productResearchStatusKind,
  readProductResearchBrief,
} from "./product-research-view.js?v=20260716.2";
import {
  buildContentReviewFrameFiles,
  captureContentReviewEvidence,
  contentReviewHasBlockers,
  contentReviewRequiredRiskCodes,
  contentReviewStatusKind,
  contentReviewWorkspaceMarkup,
  normalizeContentReviewCatalog,
  normalizeContentReviewRun,
  readContentReviewDecision,
  readContentReviewForm,
  syncContentReviewFormVisibility,
} from "./content-review-view.js?v=20260717.1";
import {
  FIRST_SHIFT_FULL_ACTIONS,
  FIRST_SHIFT_FULL_SCENARIO,
  createFirstShiftFullState,
  firstShiftFullScenarioMarkup,
  reduceFirstShiftFullState,
} from "./first-shift-full-scenario.js?v=20260716.2";
import {
  GENERATION_ARCHIVE_PAGE_SIZE,
  GENERATION_VISIBLE_CAP,
  GENERATION_VISIBLE_STEP,
  PORTAL_THEME_STORAGE_KEY,
  PORTAL_THEMES,
  boundedRoundRobinWindow,
  filterGenerationBatches,
  generationArchiveCursor,
  generationWeekLabel,
  mergeGenerationPages,
  normalizeGenerationFilters,
  normalizePortalTheme,
  persistPortalThemePreference,
} from "./portal-experience.js?v=20260718.1";
import {
  normalizeWorkspaceBoard,
  workspaceBoardItemByKey,
  workspaceBoardItemKey,
  workspaceBoardMarkup,
} from "./workspace-board-view.js?v=20260716.2";
import {
  evaluateTrainingPractice,
  normalizeInteractiveWalkthroughs,
  setTrainingAudience,
  resetTrainingWalkthroughState,
  setTrainingWalkthroughMode,
  setTrainingWalkthroughStep,
  stopTrainingWalkthrough,
  syncTrainingWalkthroughStatus,
  trainingInteractiveMarkup,
  trainingWalkthroughStorageKey,
} from "./training-interactive.js?v=20260718.4";
import {
  LEARNING_TRACKS,
  achievementMarkup,
  achievementStorageKey,
  courseAchievement,
  courseMasterySnapshot,
  learningTrackStorageKey,
  lessonJourneyPercent,
  lessonJourneyStorageKey,
  normalizeCourseMastery,
  normalizeLearningTrack,
  normalizeLessonJourney,
  playTrainingFanfare,
  reduceLessonJourney,
  roleAwareLessonPath,
  shouldCelebrateCourse,
} from "./training-journey.js?v=20260718.3";
import {
  bindTrainingPlatformSimulators,
  syncPlatformSimulatorWalkthroughDOM,
  trainingPlatformSimulatorsMarkup,
} from "./training-platform-simulators.js?v=20260719.1";
import {
  bindTrainingMediaCards,
  trainingMediaCardsMarkup,
} from "./training-media-cards.js?v=20260719.1";
import {
  normalizeTrainingPracticalProject,
  normalizeTrainingPracticalReviews,
  readTrainingPracticalDecision,
  readTrainingPracticalSubmission,
  syncTrainingPracticalSource,
  trainingPracticalGateSnapshot,
  trainingPracticalProjectMarkup,
  trainingPracticalReviewQueueMarkup,
} from "./training-practical-review.js?v=20260719.1";

const DEDICATED_PLATFORM_WALKTHROUGH_IDS = new Set([
  "platform_publish_instagram",
  "platform_publish_youtube",
  "platform_publish_vk",
]);
let trainingMediaCatalogPromise = null;
import {
  myWorkRequestOptions,
  myWorkWorkspaceMarkup,
  normalizeMyWork,
  normalizeMyWorkFilters,
  normalizeNotifications,
  normalizeSavedWorkViews,
  notificationCenterMarkup,
  readMyWorkFilters,
} from "./my-work-view.js?v=20260716.4";

const CONFIG = Object.freeze({ ...(window.CONTENTENGINE_CONFIG || {}) });
const SUPABASE_SDK_URL = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/+esm";
const ACCOUNT_VISUAL_MODULE_URL = "./account-launch-visual-examples.js?v=20260716.2";
const app = document.querySelector("#app");
const toastRegion = document.querySelector("#toast-region");
const MAX_MOCK_BATCH_SIZE = Math.min(50, Math.max(1, Number(CONFIG.MAX_BATCH_SIZE) || 50));
const MOCK_GENERATION_ENABLED = CONFIG.MOCK_ENABLED === true;
const REAL_GENERATION_ENABLED = CONFIG.REAL_GENERATION_ENABLED === true;
const AUTH_REQUEST_TIMEOUT_MS = 15_000;
const AUTH_LINK_TIMEOUT_MESSAGE = "The auth service timed out. Retry this same link.";
const HOME_SECTION_TIMEOUT_MS = 8_000;
const WORKSPACE_REQUEST_TIMEOUT_MS = 12_000;
const WORKSPACE_BOARD_VISIBLE_STEP = 80;
const WORKSPACE_BOARD_MEMORY_CAP = 300;
const INVITE_REQUEST_TIMEOUT_MS = 25_000;
const PUBLIC_RECOVERY_RECEIPT_STORAGE_KEY = "contentengine.public-recovery-receipt.v1";
const PUBLIC_RECOVERY_PENDING_STATUSES = new Set(["requesting", "outcome_unknown", "provider_outcome_unknown"]);
const MANAGER_DASHBOARD_MAX_AGE_MS = 60_000;
const MANAGER_EMAIL_ACTION_COOLDOWN_MS = 60_000;
const PASSWORD_CHANGE_REQUIRED_MARKER = "contentengine_password_change_required";
const PASSWORD_CHANGE_COMPLETED_MARKER = "contentengine_password_change_completed";
const LEGACY_PASSWORD_CHANGE_MARKERS = Object.freeze([
  "contentengine_github_member_provisioned",
  "contentengine_owner_password_reset_once_20260714",
]);
const REAL_GENERATION_POLL_INTERVAL_MS = 7_000;
const REAL_GENERATION_SOFT_TIMEOUT_MS = 20_000;
const REAL_GENERATION_URL_MAX_AGE_MS = 4 * 60 * 1_000;
const REAL_GENERATION_ACTIVE_STATUSES = new Set(["queued", "starting", "submitted", "processing", "running"]);
const PRODUCT_RESEARCH_POLL_INTERVAL_MS = 5_000;
const CONTENT_REVIEW_POLL_INTERVAL_MS = 5_000;
const CONTENT_REVIEW_DRAFT_STORAGE_VERSION = 2;
const CONTENT_REVIEW_DRAFT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1_000;
const FINAL_EXAM_DRAFT_VERSION = 2;
const FINAL_EXAM_DRAFT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1_000;
const PRODUCT_RESEARCH_RUN_STORAGE_KEY = "contentengine.product-research-run.v1";
const OPERATIONAL_WORKSPACE_ROLES = new Set([
  "owner",
  "admin",
  "producer",
  "reviewer",
  "operator",
]);
const TRAINING_WALKTHROUGH_STEP_INTERVAL_MS = 4_500;
const COURSE_AUDIENCE_COPY = Object.freeze({
  factory_basics: "Всем ролям · общий старт",
  video_quality: "Съёмка и ИИ · проверка всем",
  publishing_funnel: "Публикаторам · остальным как рабочая база",
  security_wb: "Всем ролям · товар и деньги",
});
const COURSE_MASTERY_FALLBACKS = Object.freeze({
  factory_basics: Object.freeze({ required_walkthrough_ids: ["first_login_route"] }),
  security_wb: Object.freeze({ required_walkthrough_ids: ["substitute_article_match", "payout_status_route"] }),
  video_quality: Object.freeze({ required_walkthrough_ids: ["eight_second_quality"] }),
  publishing_funnel: Object.freeze({ required_walkthrough_ids: ["advertising_stop_decision"] }),
});
const COURSE_KNOWLEDGE_PRESENTATION = Object.freeze({
  factory_basics: Object.freeze({
    audienceLabel: "Всем участникам",
    roleHint: "Разберите кейс целиком: учтите роль, состояние задачи и следы в портале, затем выберите точный набор действий и объясните компромисс.",
  }),
  video_quality: Object.freeze({
    audienceLabel: "Тем, кто снимает сам или генерирует с ИИ",
    roleHint: "Сопоставьте технический результат, точность товара и достаточность доказательств; в multi-select отметьте весь необходимый набор, а не первый правдоподобный пункт.",
  }),
  publishing_funnel: Object.freeze({
    audienceLabel: "Тем, кто публикует в соцсетях",
    roleHint: "Оцените назначение, права, правила площадки и доказательство результата вместе; выберите точный набор с учётом конфликта дедлайна и прослеживаемости.",
  }),
  security_wb: Object.freeze({
    audienceLabel: "Всем участникам",
    roleHint: "Сверьте идентификаторы, статус, полномочия и источник данных; не угадывайте одно универсальное действие — восстановите проверяемую последовательность решения.",
  }),
});
const FINAL_EXAM_PRESENTATION = Object.freeze({
  exam_sku_mismatch: Object.freeze({
    prompt: "До дедлайна 25 минут. В задаче назначен SKU A, но на фото из рабочей папки виден SKU B; менеджер пока не отвечает. Какой маршрут оставляет проверяемое доказательство и не смешивает товары?",
    options: Object.freeze({
      "Использовать похожие фото и отметить это после публикации": "Собрать ролик из доступных фото, а конфликт SKU зафиксировать в отчёте уже после размещения",
      "Переименовать SKU B в отчёте": "Считать SKU B временным алиасом и переименовать его в итоговом отчёте без отдельного согласования",
      "Остановить задачу и запросить точные материалы SKU A": "Поставить задачу на паузу, приложить скрин конфликта и запросить точные материалы либо явное переназначение SKU",
      "Сделать один тестовый ролик без проверки": "Сделать закрытый тестовый ролик на SKU B, не отправляя его на проверку до ответа менеджера",
    }),
  }),
  exam_provider_wrong_pack: Object.freeze({
    prompt: "Провайдер вернул статус success и списал стоимость, но на 6-й секунде упаковка меняет цвет и логотип. Остальные варианты партии корректны, дедлайн близко. Как обработать именно этот результат?",
    options: Object.freeze({
      "Одобрить, потому что API завершился успешно": "Принять результат по техническому success, сохранив замечание о визуальном отклонении для следующей партии",
      "Опубликовать с предупреждением в описании": "Разместить текущий файл с уточнением в описании, что цвет упаковки может отличаться",
      "Отклонить конкретный файл и вернуть на пересоздание": "Отклонить только дефектный файл, приложить таймкод и вернуть его на пересоздание, не ломая корректную часть партии",
      "Скрыть неверные кадры обложкой": "Выбрать корректную обложку и сократить превью так, чтобы спорный кадр не был первым",
    }),
  }),
  exam_qa_requirements: Object.freeze({
    prompt: "Ролик технически готов, автопроверка не нашла ошибок, а публикационное окно через 40 минут. Какие проверки дают достаточное доказательство ручного QA до одобрения? Выберите все необходимые.",
    options: Object.freeze({
      "Посмотреть MP4 полностью": "Просмотреть финальный MP4 от первого до последнего кадра со звуком, а не только превью",
      "Сверить товар и упаковку с точными исходниками": "Сопоставить упаковку, вариант и артикул с утверждёнными исходниками именно этой задачи",
      "Проверить обещания, текст и CTA": "Проверить титры, фактические обещания и CTA против брифа и ограничений площадки",
      "Дождаться 1000 просмотров": "Считать QA завершённым только после пилотной публикации и первых 1000 просмотров",
    }),
  }),
  exam_missing_destination: Object.freeze({
    prompt: "Файл одобрен, но в задаче пусто поле площадки; в чате называют два разных аккаунта, и между ними возник конфликт назначения. До слота публикации 15 минут. Что фиксировать в портале?",
    options: Object.freeze({
      "Выбрать любой доступный аккаунт": "Взять свободный командный аккаунт той же площадки и после публикации сообщить, куда ушёл ролик",
      "Передать ролик коллеге без фиксации": "Передать файл публикатору из чата и оставить выбор аккаунта на его стороне без изменения задачи",
      "Остановиться и запросить назначение площадки": "Удержать публикацию, отметить блокер назначения и запросить одно подтверждённое направление в самой задаче",
      "Опубликовать в личном аккаунте": "Не терять слот: выпустить ролик в личном тестовом аккаунте и затем перенести ссылку",
    }),
  }),
  exam_publication_evidence: Object.freeze({
    prompt: "Публикатор сообщает «готово», но через неделю по ролику будут сверять площадку, задачу и выплату. Какие данные составляют минимальное проверяемое доказательство публикации? Выберите все нужные.",
    options: Object.freeze({
      "Публичный final URL поста": "Сохранить доступный final URL именно опубликованного поста и проверить, что он открывается",
      "Tracking link из назначенной задачи": "Связать публикацию с tracking link, выданной в назначенной задаче, не создавая новую вручную",
      "Пароль от социальной сети": "Добавить пароль аккаунта в закрытое поле доказательства, чтобы проверяющий мог войти при споре",
      "OAuth access token": "Приложить OAuth-токен к доказательству, чтобы коннектор позднее подтвердил принадлежность поста",
    }),
  }),
  exam_metrics_source: Object.freeze({
    prompt: "Коннектор метрик не отвечает два часа, а недельный отчёт нужно закрыть сегодня. Как сохранить ручной срез так, чтобы завтра его не приняли за данные API и можно было воспроизвести расчёт?",
    options: Object.freeze({
      "Ввести накопительный ручной или CSV-снимок с явной маркировкой источника и времени": "Загрузить ручной или CSV-снимок, указав кабинет-источник, время среза и накопительный характер показателей",
      "Назвать приблизительные цифры результатом API": "Внести оценочные цифры как предварительный результат API и исправить их после восстановления коннектора",
      "Передать пароль аналитику для скрейпинга кабинета": "Выдать аналитику временный пароль, чтобы он сам выгрузил показатели напрямую из кабинета",
      "Скопировать цифры конкурента": "Использовать медиану сопоставимых роликов как временный факт и пометить её отраслевым ориентиром",
    }),
  }),
  exam_secret_request: Object.freeze({
    prompt: "Коллега с ролью публикатора пишет, что интеграция остановилась, и просит OAuth-токен «на пять минут» прямо в комментарии к срочной задаче. Как снять блокер без передачи секрета?",
    options: Object.freeze({
      "Вставить токен и удалить комментарий позже": "Передать токен в комментарии, удалить сообщение после подключения и зафиксировать время доступа",
      "Отправить токен личным сообщением": "Передать токен в личном сообщении только этому сотруднику и попросить подтвердить удаление",
      "Не передавать секрет, остановить действие и сообщить владельцу безопасного контура": "Не раскрывать токен, отметить технический блокер и передать восстановление владельцу защищённой интеграции",
      "Сохранить токен в названии файла": "Поместить токен в имя закрытого служебного файла и дать коллеге ссылку на него",
    }),
  }),
  exam_real_spend_disabled: Object.freeze({
    prompt: "Платный провайдер доступен, но spend gate команды выключен. Клиент ждёт пример к созвону через час, прогноз одного запуска — $2.32. Как действовать без скрытого расхода?",
    options: Object.freeze({
      "Запустить один ролик — это не считается расходом": "Сделать один минимальный canary: сумма мала, а массовую генерацию оставить выключенной",
      "Остаться в mock/dry-run и запросить отдельное разрешение владельца на spend gate": "Подготовить dry-run и запросить у владельца явное разрешение на конкретный платный запуск со стоимостью",
      "Разделить запуск на несколько маленьких задач": "Разбить запрос на несколько коротких задач, каждая из которых останется ниже порога внимания",
      "Подставить личный API key": "Запустить через личный API-ключ и не учитывать сумму в бюджете команды",
    }),
  }),
  exam_wb_alias_history: Object.freeze({
    prompt: "Карточка товара переехала на новый артикул, но продажи и публикации продолжают приходить по старому. В отчёте уже есть два периода и конфликт названий. Как сохранить непрерывную историю без смешения товаров?",
    options: Object.freeze({
      "Переписать старые записи на новый артикул без истории": "Нормализовать прошлые записи на новый артикул, чтобы в отчёте осталась одна строка без периода перехода",
      "Создать датированную alias-связь обоих артикулов с каноническим товаром": "Привязать оба артикула к одному каноническому товару с датой действия связи и сохранить исходные события",
      "Создать случайный новый SKU": "Создать внутренний третий SKU для переходного периода и перенести в него обе серии метрик",
      "Сложить метрики с любым товаром того же бренда": "Объединить показатели в брендовый итог, если названия и категория карточек совпадают",
    }),
  }),
  exam_payout_separation: Object.freeze({
    prompt: "Креатор приложил рабочий URL и отметил публикацию выполненной, но метрики ещё не загрузились, а в реестре выплата остаётся pending. Какое событие является отдельным доказательством права на выплату?",
    options: Object.freeze({
      "Сразу после отметки самого креатора": "Самоотметка креатора и доступный URL автоматически переводят начисление в подтверждённое",
      "После проверки доказательства и решения уполномоченного owner/admin": "Уполномоченный руководитель сверяет доказательство с задачей и отдельно принимает решение по pending-начислению",
      "После любого комментария в чате": "Комментарий менеджера «принято» в рабочем чате достаточно считать решением по выплате",
      "До публикации, если ролик выглядит хорошо": "После QA можно предварительно подтвердить выплату, а URL добавить в реестр позднее",
    }),
  }),
  exam_platform_claims: Object.freeze({
    prompt: "Публикационный слот через 10 минут. Какие признаки являются блокерами, требующими остановить выпуск до устранения, даже если файл уже одобрен визуально? Выберите все подходящие.",
    options: Object.freeze({
      "Нет подтверждённых прав на исходник": "Для одного исходника нет подтверждения прав, хотя он уже использовался в прошлой кампании",
      "В ролике есть неподтверждённое медицинское обещание": "В голосе осталось медицинское обещание, которого нет в согласованных доказательствах продукта",
      "Фактический товар отличается от задания": "В кадре фактический вариант товара отличается от назначенного в задаче",
      "В календаре свободно другое время": "Назначенный слот неудобен, но в календаре позже есть свободное окно той же площадки",
    }),
  }),
  exam_idempotent_retry: Object.freeze({
    prompt: "После отправки партии интерфейс показал timeout. В списке пока пусто, но провайдер мог принять запрос и списать деньги. Как выполнить воспроизводимую проверку и повтор без дублей?",
    options: Object.freeze({
      "Создать новый idempotency key и повторить несколько раз": "Сформировать новый ключ и повторять до появления партии, затем удалить лишние результаты",
      "Повторить тот же запрос с тем же idempotency key и проверить сохранённый результат": "Повторить неизменённый запрос с прежним idempotency key и сверить возвращённый сохранённый результат",
      "Удалить все задачи команды": "Очистить незавершённые задачи текущей кампании и создать партию заново с нулевой истории",
      "Увеличить количество роликов": "Добавить к новой партии количество «пропавших» роликов, а совпадения убрать после ответа провайдера",
    }),
  }),
});
const FINAL_EXAM_RATIONALE_PROMPTS = Object.freeze({
  exam_sku_mismatch: "Обоснуйте остановку или продолжение: какой риск для товара, что именно вы проверите и какое действие зафиксируете в портале?",
  exam_qa_requirements: "Опишите контроль качества: какой риск нельзя пропустить, каким доказательством вы его проверите и что сделаете по результату?",
  exam_publication_evidence: "Опишите доказательство публикации: какой риск есть для учёта, что вы сверите и какое действие выполните в портале?",
  exam_payout_separation: "Разделите публикацию и выплату: какой риск возникает, что подтверждает начисление и кто должен выполнить следующее действие?",
});
const FINAL_EXAM_RATIONALE_CODES = Object.freeze(Object.keys(FINAL_EXAM_RATIONALE_PROMPTS));
const REAL_GEN4_MODE = "real_gen4";
const REAL_SEEDANCE_MODE = "real_seedance";
const REAL_GENERATION_SKUS = Object.freeze({
  [REAL_GEN4_MODE]: Object.freeze({
    model: "gen4_turbo",
    durationSeconds: 5,
    audio: false,
    format: null,
    estimatedCredits: 25,
    estimatedMinor: 25,
    estimatedUsd: "0.25",
    confirmation: "RUNWAY_GEN4_TURBO_5S_USD_0.25",
    label: "Анимация товара · 5 секунд · без голоса · ≈ $0.25",
  }),
  [REAL_SEEDANCE_MODE]: Object.freeze({
    model: "seedance2_fast",
    durationSeconds: 8,
    audio: true,
    format: "9:16",
    estimatedCredits: 232,
    estimatedMinor: 232,
    estimatedUsd: "2.32",
    confirmation: "RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32",
    label: "Блогер + голос · 8 секунд · ≈ $2.32",
  }),
});
const MEMBERSHIP_LOCK_COPY = Object.freeze({
  membership_suspended: Object.freeze({
    title: "Доступ приостановлен",
    message: "Обратитесь к руководителю вашей команды.",
  }),
  membership_revoked: Object.freeze({
    title: "Доступ отозван",
    message: "Обратитесь к руководителю вашей команды.",
  }),
});

const WORKSPACE_HOME_TAB = Object.freeze(["home", "Сегодня", "⌂"]);
const FACTORY_FLOW = Object.freeze([
  Object.freeze({
    key: "media",
    step: "01",
    label: "Материалы",
    hint: "точные фото и видео",
    learning: "Добавьте точное фото товара и проверьте артикул.",
  }),
  Object.freeze({
    key: "generation",
    step: "02",
    label: "Создание видео",
    hint: "сценарий и ролик",
    learning: "Выберите режим, задайте сценарий и подтвердите стоимость.",
  }),
  Object.freeze({
    key: "review",
    step: "03",
    label: "Проверка",
    hint: "качество и риски",
    learning: "Проверьте готовый ролик, рекламный контекст и все найденные блокеры.",
  }),
  Object.freeze({
    key: "tasks",
    step: "04",
    label: "Задачи",
    hint: "решение человека",
    learning: "Подтвердите качество или сохраните точную причину доработки.",
  }),
  Object.freeze({
    key: "placement",
    step: "05",
    label: "Публикации",
    hint: "пост и ссылка",
    learning: "Разместите одобренный ролик в назначенном аккаунте и сохраните ссылку.",
  }),
  Object.freeze({
    key: "stats",
    step: "06",
    label: "Результаты",
    hint: "метрики с датой",
    learning: "Запишите показатели вместе с источником и временем снимка.",
  }),
  Object.freeze({
    key: "payouts",
    step: "07",
    label: "Выплаты",
    hint: "начисление и расчёт",
    learning: "Проверьте сумму и отличайте начисление, одобрение и фактическую выплату.",
  }),
]);
const HOME_SECTION_KEYS = Object.freeze(FACTORY_FLOW.map((item) => item.key));
const WORKSPACE_SECTION_META = Object.freeze({
  home: Object.freeze({
    kicker: "Центр управления",
    note: "Одно главное действие и весь цикл без лишних переходов",
  }),
  media: Object.freeze({
    kicker: "Шаг 1 из 7",
    note: "После загрузки точный исходник станет доступен в генерации",
    now: "Загрузите фото именно того товара, который указан в задаче.",
    done: "Артикул, объём и упаковка совпадают, а этикетка читается.",
    guard: "Не используйте похожий товар, другой вкус, объём или чужой ролик.",
    nextLabel: "Создать ролик",
    nextHref: "#/workspace/generation",
    guideHref: "#/learn/factory_basics",
  }),
  research: Object.freeze({
    kicker: "Исследование продукта",
    note: "Публичные источники, вводные и гипотезы остаются раздельными до ручного утверждения",
    now: "Добавьте точный товар, фотографии, публичную ссылку, площадки и подтверждённые факты.",
    done: "Источники открываются, ТЗ отредактировано, а три сценария не содержат неподтверждённых обещаний.",
    guard: "Прогноз не гарантирует просмотры и продажи. Не утверждайте ТЗ, пока не проверены источники, свойства товара и рекламный режим.",
    nextLabel: "Утвердить ТЗ и создать задачи",
    nextHref: "#/workspace/tasks",
    guideHref: "#/learn/video_quality",
  }),
  generation: Object.freeze({
    kicker: "Шаг 2 из 7",
    note: "Сначала товар и сценарий, затем отдельное подтверждение стоимости",
    now: "Выберите один точный исходник и опишите один короткий ролик.",
    done: "Проверены формат, реплика и цена; создан ровно один запуск.",
    guard: "Не нажимайте запуск повторно, пока уже созданная работа обрабатывается.",
    nextLabel: "Проверить контент",
    nextHref: "#/workspace/review",
    guideHref: "#/learn/video_quality",
  }),
  review: Object.freeze({
    kicker: "Шаг 3 из 7",
    note: "Качество и правовые риски оцениваются отдельно до решения человека",
    now: "Выберите готовый файл, площадку и честно заполните рекламный контекст.",
    done: "Блокеры прочитаны, рекомендации понятны, а решение ответственного сохранено отдельной записью.",
    guard: "Высокий балл качества не отменяет рекламный, медицинский или правовой блокер.",
    nextLabel: "Открыть задачи",
    nextHref: "#/workspace/tasks",
    guideHref: "#/learn/video_quality",
  }),
  tasks: Object.freeze({
    kicker: "Шаг 4 из 7",
    note: "Начните назначенную работу или честно зафиксируйте блокер",
    now: "Откройте назначенную задачу и посмотрите результат целиком.",
    done: "Ролик одобрен или точная причина доработки сохранена в задаче.",
    guard: "Не принимайте ролик с искажённым товаром, обрывом речи или чужой упаковкой.",
    nextLabel: "Разместить одобренное",
    nextHref: "#/workspace/placement",
    guideHref: "#/learn/factory_basics",
  }),
  placement: Object.freeze({
    kicker: "Шаг 5 из 7",
    note: "Публикуйте только одобренный файл и верните ссылку на сам пост",
    now: "Сверьте площадку, аккаунт и готовое решение по маркировке.",
    done: "Пост опубликован, а в портал сохранён URL самого ролика.",
    guard: "Если рекламный статус неясен, остановитесь и запросите решение руководителя.",
    nextLabel: "Внести метрики",
    nextHref: "#/workspace/stats",
    guideHref: "#/learn/publishing_funnel",
  }),
  stats: Object.freeze({
    kicker: "Шаг 6 из 7",
    note: "Каждая цифра хранится вместе с источником и временем снимка",
    now: "Добавьте первый снимок показателей с датой и источником.",
    done: "Метрики привязаны к конкретному опубликованному ролику.",
    guard: "Не переносите цифры из другого поста и не оставляйте источник пустым.",
    nextLabel: "Проверить начисление",
    nextHref: "#/workspace/payouts",
    guideHref: "#/learn/publishing_funnel",
  }),
  payouts: Object.freeze({
    kicker: "Шаг 7 из 7",
    note: "Начисление, решение и внешний перевод — разные проверяемые этапы",
    now: "Сверьте сумму и текущий статус начисления по своей задаче.",
    done: "Только статус «Выплачено» подтверждает завершённый перевод.",
    guard: "Статус «Одобрено» ещё не означает, что деньги уже переведены.",
    nextLabel: "Вернуться к обзору",
    nextHref: "#/workspace/home",
    guideHref: "#/learn/security_wb",
  }),
  feedback: Object.freeze({
    kicker: "Помощь",
    note: "Опишите препятствие — запрос сохранится в рабочем контексте",
    now: "Опишите один вопрос: где остановились и что уже проверили.",
    done: "Запрос сохранён и содержит достаточно данных для ответа.",
    guard: "Не отправляйте пароли, коды входа, платёжные данные или секретные ключи.",
    nextLabel: "Вернуться к работе",
    nextHref: "#/workspace/home",
    guideHref: "#/learn/security_wb",
  }),
  team: Object.freeze({
    kicker: "Управление",
    note: "Доступ выдаётся персонально и открывается после обучения",
    now: "Проверьте участника, роль, обучение и последнее действие.",
    done: "У человека есть только нужный доступ и понятный следующий шаг.",
    guard: "Не создавайте общие учётки и не передавайте временный пароль в открытом чате.",
    nextLabel: "Вернуться к обзору",
    nextHref: "#/workspace/home",
    guideHref: "#/learn/security_wb",
  }),
});

const COURSE_VISUAL_EXAMPLES = Object.freeze({
  factory_basics: Object.freeze({
    theme: "portal",
    kicker: "Сначала посмотрите",
    title: "Первая задача — на трёх реальных экранах",
    summary: "Не запоминайте меню. Сверяйте свой экран с примером и двигайтесь слева направо: точный товар → создание ролика → проверка результата.",
    examples: Object.freeze([
      Object.freeze({
        step: "Экран 1",
        anchorLesson: "sku_and_sources",
        kind: "portal",
        eyebrow: "Портал · Материалы",
        title: "Добавьте именно тот товар, который стоит в задаче",
        caption: "Фотографии упаковки и артикул должны относиться к одной карточке. Похожий вкус или объём — уже другой товар.",
        result: "Материал готов к созданию видео",
        items: Object.freeze([
          Object.freeze({ label: "Артикул WB", value: "159068498" }),
          Object.freeze({ label: "Исходники", value: "6 точных фото" }),
          Object.freeze({ label: "Проверка", value: "Упаковка совпадает" }),
        ]),
      }),
      Object.freeze({
        step: "Экран 2",
        anchorLesson: "generation_modes",
        kind: "portal",
        eyebrow: "Портал · Создание видео",
        title: "Выберите формат и прочитайте стоимость до запуска",
        caption: "Для восьмисекундного UGC выберите режим с блогером и голосом. Указанная цена — только пример: перед запуском сверьте фактическую сумму в портале и подтвердите её отдельно.",
        result: "Один подтверждённый запуск",
        items: Object.freeze([
          Object.freeze({ label: "Режим", value: "Блогер + голос" }),
          Object.freeze({ label: "Формат", value: "9:16 · 8 секунд" }),
          Object.freeze({ label: "Стоимость", value: "Пример: ≈ $2.32" }),
        ]),
      }),
      Object.freeze({
        step: "Экран 3",
        anchorLesson: "traceable_cycle",
        kind: "portal",
        eyebrow: "Портал · Задачи",
        title: "Посмотрите ролик целиком и только потом подтвердите",
        caption: "Сначала проверьте товар, руки и лицо, голос, надписи и последние кадры. Если есть ошибка — отправьте на доработку, а не публикуйте.",
        result: "Одобренный файл можно размещать",
        items: Object.freeze([
          Object.freeze({ label: "Товар", value: "Совпадает" }),
          Object.freeze({ label: "Звук", value: "Речь слышно" }),
          Object.freeze({ label: "Статус", value: "Одобрено" }),
        ]),
      }),
    ]),
  }),
  video_quality: Object.freeze({
    theme: "shooting",
    kicker: "Покадровая шпаргалка",
    title: "Так выглядит хороший вертикальный исходник",
    summary: "Телефон уже настроен, товар остаётся в безопасной зоне, а восемь секунд разбиты на простые кадры. Эти примеры можно повторить буквально.",
    examples: Object.freeze([
      Object.freeze({
        step: "До записи",
        anchorLesson: "shoot_vertical_source",
        kind: "camera",
        eyebrow: "Камера телефона",
        title: "Вертикально 9:16, свет перед лицом",
        caption: "Протрите камеру, встаньте лицом к окну и оставьте свободное место сверху и снизу — интерфейс соцсети не перекроет товар.",
        result: "Лицо и упаковка читаются без увеличения",
        items: Object.freeze([
          Object.freeze({ label: "Формат", value: "9:16" }),
          Object.freeze({ label: "Свет", value: "Перед вами" }),
          Object.freeze({ label: "Фокус", value: "На товаре" }),
        ]),
      }),
      Object.freeze({
        step: "0–8 сек",
        anchorLesson: "eight_second_storyboard",
        kind: "storyboard",
        eyebrow: "Готовый план съёмки",
        title: "Одна мысль — три коротких кадра",
        caption: "Не пытайтесь рассказать всё. Покажите проблему, сам продукт и один понятный результат.",
        result: "Ролик понятен даже без звука",
        items: Object.freeze([
          Object.freeze({ label: "0–2 сек", value: "Проблема или вопрос" }),
          Object.freeze({ label: "2–5 сек", value: "Товар крупным планом" }),
          Object.freeze({ label: "5–8 сек", value: "Результат + действие" }),
        ]),
      }),
      Object.freeze({
        step: "Перед запуском",
        anchorLesson: "prompt_anatomy",
        kind: "portal",
        eyebrow: "Форма генерации",
        title: "Промпт говорит, кто, где и что делает",
        caption: "Укажите героя, продукт, действие, обстановку и короткую реплику. Не просите модель одновременно показать пять сцен.",
        result: "Сценарий помещается в восемь секунд",
        items: Object.freeze([
          Object.freeze({ label: "Герой", value: "Бьюти-блогер" }),
          Object.freeze({ label: "Действие", value: "Показывает флакон" }),
          Object.freeze({ label: "Реплика", value: "Одна короткая мысль" }),
        ]),
      }),
      Object.freeze({
        step: "Контроль",
        anchorLesson: "full_video_qa",
        kind: "compare",
        eyebrow: "Брак или готово",
        title: "Проверьте весь ролик, включая последний кадр",
        caption: "Искажённая этикетка, лишние пальцы, скачок лица, обрыв голоса или чужая упаковка — это доработка, даже если первые секунды хорошие.",
        result: "В публикацию идёт только чистый файл",
        items: Object.freeze([
          Object.freeze({ label: "Стоп", value: "Артефакты и обрыв" }),
          Object.freeze({ label: "Готово", value: "Товар и речь стабильны" }),
        ]),
      }),
    ]),
  }),
  publishing_funnel: Object.freeze({
    theme: "social",
    kicker: "Три площадки — три маршрута",
    title: "Куда нажать в Instagram, YouTube и VK",
    summary: "Выберите площадку из задачи, повторите путь по кнопкам и верните в портал ссылку именно на опубликованный ролик. Ниже — прогрев нового аккаунта и стоп-проверка рекламы.",
    examples: Object.freeze([
      Object.freeze({
        step: "Instagram",
        anchorLesson: "instagram_reels_step_by_step",
        kind: "social",
        platform: "Instagram Reels",
        eyebrow: "Новая публикация",
        title: "«+» → Reels → выбрать файл → Поделиться",
        caption: "Проверьте обложку, подпись и нужный аккаунт до нажатия «Поделиться». После публикации откройте ролик и скопируйте ссылку.",
        result: "Ссылка ведёт на сам Reels",
        items: Object.freeze([
          Object.freeze({ label: "1", value: "Нажмите «+»" }),
          Object.freeze({ label: "2", value: "Выберите Reels" }),
          Object.freeze({ label: "3", value: "Поделиться" }),
        ]),
      }),
      Object.freeze({
        step: "YouTube",
        anchorLesson: "youtube_shorts_step_by_step",
        kind: "social",
        platform: "YouTube Shorts",
        eyebrow: "Создать Shorts",
        title: "«+» → Создать Shorts → загрузить → Далее",
        caption: "Выберите правильный канал, задайте название и видимость из задачи. Не закрывайте приложение, пока загрузка не закончилась.",
        result: "Ссылка открывает опубликованный Shorts",
        items: Object.freeze([
          Object.freeze({ label: "1", value: "Нажмите «+»" }),
          Object.freeze({ label: "2", value: "Создать Shorts" }),
          Object.freeze({ label: "3", value: "Загрузить" }),
        ]),
      }),
      Object.freeze({
        step: "VK",
        anchorLesson: "vk_clips_step_by_step",
        kind: "social",
        platform: "VK Клипы",
        eyebrow: "Личный профиль или сообщество",
        title: "Клипы → «+» → выбрать файл → Опубликовать",
        caption: "Сначала сверьте, от чьего имени должна выйти публикация: личного профиля или бизнес-сообщества. Это разные места размещения.",
        result: "Ролик опубликован от нужного имени",
        items: Object.freeze([
          Object.freeze({ label: "1", value: "Откройте Клипы" }),
          Object.freeze({ label: "2", value: "Проверьте автора" }),
          Object.freeze({ label: "3", value: "Опубликовать" }),
        ]),
      }),
      Object.freeze({
        step: "До первой задачи",
        anchorLesson: "new_account_safe_start",
        kind: "calendar",
        eyebrow: "Новый аккаунт",
        title: "Прогрев — это нормальное поведение, а не спам",
        caption: "Здесь нет магического числа дней или действий и нет гарантии от блокировки. Честно заполните профиль, включите защиту, используйте оригинальные материалы и не имитируйте массовую активность.",
        result: "Аккаунт выглядит живым и управляемым",
        items: Object.freeze([
          Object.freeze({ label: "Шаг 1", value: "Профиль, контакты и 2FA" }),
          Object.freeze({ label: "Шаг 2", value: "Проверить роль и доступ" }),
          Object.freeze({ label: "Шаг 3", value: "Оригинальные материалы" }),
          Object.freeze({ label: "Шаг 4", value: "Реальные ответы без спама" }),
          Object.freeze({ label: "Шаг 5", value: "Статус аккаунта чистый" }),
          Object.freeze({ label: "Готово", value: "Публикация по задаче" }),
        ]),
      }),
      Object.freeze({
        step: "Стоп-проверка",
        anchorLesson: "advertising_classification_and_labeling",
        kind: "decision",
        eyebrow: "Рекламная маркировка",
        title: "Не пытайтесь «избежать бирки» — сначала определите режим публикации",
        caption: "Если есть оплата, бартер, обязательный бриф, промокод, ссылка или призыв к покупке — не публикуйте без решения руководителя и проверки маркировки. Сомнение тоже означает «стоп».",
        result: "Решение зафиксировано до размещения",
        items: Object.freeze([
          Object.freeze({ label: "Есть признаки рекламы", value: "Стоп → руководителю" }),
          Object.freeze({ label: "Есть сомнение", value: "Стоп → проверка" }),
          Object.freeze({ label: "Режим подтверждён", value: "Действуйте по задаче" }),
        ]),
      }),
      Object.freeze({
        step: "После публикации",
        anchorLesson: "three_urls",
        kind: "portal",
        eyebrow: "Ссылка и результат",
        title: "Верните ссылку на пост, а не на профиль или товар",
        caption: "Откройте опубликованный ролик, скопируйте его адрес, проверьте ссылку в новой вкладке и только затем сохраните её в портале вместе с первым снимком метрик.",
        result: "Пост открывается, дата и метрики зафиксированы",
        items: Object.freeze([
          Object.freeze({ label: "Ссылка", value: "На конкретный ролик" }),
          Object.freeze({ label: "Проверка", value: "Открывается без ошибки" }),
          Object.freeze({ label: "Метрики", value: "С датой и временем" }),
        ]),
      }),
    ]),
  }),
  security_wb: Object.freeze({
    theme: "payout",
    kicker: "Товар и деньги без догадок",
    title: "Подменный артикул и выплата — на одной схеме",
    summary: "Подменник связывает историю одного и того же товара, а выплата проходит отдельные проверяемые статусы. Исполнитель не придумывает ни артикул, ни сумму.",
    examples: Object.freeze([
      Object.freeze({
        step: "Артикул",
        anchorLesson: "wb_alias_history",
        kind: "alias",
        eyebrow: "Карточка Wildberries",
        title: "Подменный артикул — другой номер того же точного товара",
        caption: "Совпадают вкус, объём, состав и упаковка. Номер выдаёт руководитель в задаче; исполнитель сам не ищет и не подбирает замену.",
        result: "Старая история связана с текущей карточкой",
        items: Object.freeze([
          Object.freeze({ label: "Было", value: "Пример: 159068498" }),
          Object.freeze({ label: "Стало", value: "Номер из задачи" }),
          Object.freeze({ label: "Условие", value: "Тот же товар" }),
        ]),
      }),
      Object.freeze({
        step: "Расчёт",
        anchorLesson: "calculation_and_payout",
        kind: "portal",
        eyebrow: "Карточка задачи",
        title: "Сумма видна до начала работы",
        caption: "Если в задаче указано 0 ₽ или сумма непонятна, не начинайте работу и не соглашайтесь на устную формулу вне портала.",
        result: "Условия зафиксированы в задаче",
        items: Object.freeze([
          Object.freeze({ label: "Вознаграждение", value: "Сумма из задачи" }),
          Object.freeze({ label: "Подтверждение", value: "Ссылка на пост" }),
          Object.freeze({ label: "Просмотры", value: "Не меняют сумму сами" }),
        ]),
      }),
      Object.freeze({
        step: "Выплата",
        anchorLesson: "calculation_and_payout",
        kind: "payout",
        eyebrow: "Статусы начисления",
        title: "«Одобрено» ещё не означает «деньги переведены»",
        caption: "Портал показывает путь начисления. Факт внешнего перевода отмечается отдельно — поэтому всегда сверяйте последний статус.",
        result: "Выплата завершена только при статусе «Выплачено»",
        items: Object.freeze([
          Object.freeze({ label: "1", value: "Ожидает проверки" }),
          Object.freeze({ label: "2", value: "Одобрено" }),
          Object.freeze({ label: "3", value: "Выплачено" }),
        ]),
      }),
    ]),
  }),
});

const FIRST_SHIFT_STORAGE_PREFIX = "contentengine.first-shift.v2";
const FIRST_SHIFT_FULL_EVENT_TYPES = Object.freeze({
  [FIRST_SHIFT_FULL_ACTIONS.select]: "select",
  [FIRST_SHIFT_FULL_ACTIONS.check]: "check",
  [FIRST_SHIFT_FULL_ACTIONS.next]: "next",
  [FIRST_SHIFT_FULL_ACTIONS.previous]: "previous",
  [FIRST_SHIFT_FULL_ACTIONS.restart]: "restart",
});

ensureAccessCenterStyles();

const state = {
  supabase: null,
  api: null,
  authStorageKey: "",
  session: null,
  user: null,
  bootstrap: null,
  bootstrapStatus: "idle",
  bootstrapError: null,
  authPurpose: null,
  forcePassword: false,
  authLinkError: null,
  authLinkContinuationPending: false,
  resetReceipt: readStoredPublicRecoveryReceipt(),
  resetCountdownTimer: null,
  route: parseRoute(),
  routeTransition: true,
  workspaceDeepLinkFocusKey: "",
  portalTheme: normalizePortalTheme(document.documentElement.dataset.portalTheme),
  navigationMode: restoreNavigationModePreference(),
  dataEpoch: 0,
  bootstrapRequestId: 0,
  mobileNavOpen: false,
  realGenerationStartInFlight: false,
  realGenerationStartNotice: "",
  realGenerationPollTimer: null,
  realGenerationPollInFlight: false,
  realGenerationPollCursor: 0,
  realGenerationStatusRequests: new Map(),
  realGenerationResults: new Map(),
  realGenerationDrafts: new Map(),
  lastRealGenerationJobId: null,
  examResult: null,
  courseCheckResults: {},
  firstShift: null,
  accountVisualController: null,
  accountVisualMountRequest: 0,
  accountVisualStates: new Map(),
  teamInviteResult: null,
  managerDashboard: { status: "idle", data: null, error: null, requestId: 0, updatedAt: 0 },
  operationalHealth: { status: "idle", data: null, error: null, requestId: 0, updatedAt: 0 },
  generationSpend: {
    status: "idle",
    data: null,
    error: null,
    notice: "",
    requestId: 0,
    updatedAt: 0,
    saving: false,
  },
  accessCenter: {
    status: "idle",
    email: "",
    result: null,
    error: "",
    notice: "",
    requestId: 0,
  },
  managerRecoveryCooldowns: new Map(),
  managerInviteCooldowns: new Map(),
  productResearch: {
    phase: "idle",
    record: null,
    error: "",
    notice: "",
    pollTimer: null,
    requestId: 0,
    restoreAttempted: false,
  },
  contentReview: {
    phase: "idle",
    record: null,
    error: "",
    notice: "",
    pollTimer: null,
    requestId: 0,
    pendingMediaId: "",
    durableEvidence: null,
  },
  workspaceBoard: {
    selectedFolderId: "all",
    selectedItemKey: "",
    query: "",
    entityType: "all",
    busy: false,
    notice: "",
    error: "",
    dragging: null,
    loadingMore: false,
    hasMore: false,
    nextCursor: null,
    visibleItemLimit: WORKSPACE_BOARD_VISIBLE_STEP,
  },
  myWork: {
    filters: normalizeMyWorkFilters(),
    selectedViewId: "",
    savedViews: [],
    notifications: normalizeNotifications(),
    notificationsStatus: "idle",
    notificationsError: "",
    notificationsOpen: false,
    notificationsRequestId: 0,
    notificationsMutationEpoch: 0,
    notice: "",
    error: "",
    loadingMore: false,
    viewsLoaded: false,
  },
  trainingWalkthroughTimers: new Map(),
  trainingProgress: {
    items: new Map(),
    loadedModules: new Set(),
    loadRequests: new Map(),
    saveTimers: new Map(),
    saveQueues: new Map(),
    completionInFlight: new Set(),
  },
  generationArchive: {
    filters: normalizeGenerationFilters(),
    loading: false,
    loadingMore: false,
    exhausted: false,
    error: "",
    requestId: 0,
    nextCursor: null,
    serverLoaded: false,
  },
  home: { status: "idle", data: null, error: null, unavailable: [], requestId: 0 },
  sections: Object.fromEntries(
    WORKSPACE_TABS.map(([key]) => [key, { status: key === "research" ? "ready" : "idle", data: null, error: null, requestId: 0 }]),
  ),
  sessionId: getSessionId(),
};

applyPortalTheme(state.portalTheme, { persist: false });
applyNavigationMode(state.navigationMode, { persist: false, rerender: false });

let supabaseSdkPromise = null;

window.CONTENTENGINE_BOOT_WATCHDOG?.moduleLoaded();
initialize()
  .then(() => window.CONTENTENGINE_BOOT_WATCHDOG?.ready())
  .catch((error) => {
    console.error(error);
    renderFatal(error);
    window.CONTENTENGINE_BOOT_WATCHDOG?.failed("startup");
  });

async function loadSupabaseCreateClient() {
  if (!supabaseSdkPromise) {
    supabaseSdkPromise = withUiTimeout(
      import(SUPABASE_SDK_URL),
      AUTH_REQUEST_TIMEOUT_MS,
      "Не удалось загрузить защищённый клиент входа. Проверьте соединение и обновите страницу.",
    ).catch((error) => {
      supabaseSdkPromise = null;
      throw error;
    });
  }
  const sdk = await supabaseSdkPromise;
  if (typeof sdk?.createClient !== "function") {
    throw new Error("Supabase browser client is unavailable");
  }
  return sdk.createClient;
}

function createHybridAuthStorage() {
  const verifierStorage = window.localStorage;
  const sessionStorage = window.sessionStorage;
  return {
    getItem(key) {
      if (!isPkceVerifierStorageKey(key)) return safeStorageGet(sessionStorage, key);
      return safeStorageGet(sessionStorage, key) ?? safeStorageGet(verifierStorage, key);
    },
    setItem(key, value) {
      if (!isPkceVerifierStorageKey(key)) {
        safeStorageSet(sessionStorage, key, value);
        return;
      }
      if (safeStorageSet(verifierStorage, key, value)) {
        safeStorageRemove(sessionStorage, key);
      } else {
        safeStorageSet(sessionStorage, key, value);
      }
    },
    removeItem(key) {
      if (!isPkceVerifierStorageKey(key)) {
        safeStorageRemove(sessionStorage, key);
        return;
      }
      safeStorageRemove(verifierStorage, key);
      safeStorageRemove(sessionStorage, key);
    },
  };
}

function isPkceVerifierStorageKey(key) {
  return String(key || "").toLowerCase().includes("code-verifier");
}

function safeStorageGet(storage, key) {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function safeStorageSet(storage, key, value) {
  try {
    storage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

function safeStorageRemove(storage, key) {
  try {
    storage.removeItem(key);
  } catch {
    // Cleanup is best effort and never broadens session persistence.
  }
}

function navigationPreferenceStorage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function normalizeNavigationMode(value) {
  const requested = String(value || "").trim().toLowerCase();
  return NAVIGATION_MODES.some((mode) => mode.id === requested) ? requested : "simple";
}

function restoreNavigationModePreference() {
  return normalizeNavigationMode(
    safeStorageGet(navigationPreferenceStorage(), NAVIGATION_MODE_STORAGE_KEY),
  );
}

function clearStoredPkceVerifier() {
  const prefix = String(state.authStorageKey || "");
  for (const storage of [window.localStorage, window.sessionStorage]) {
    try {
      const keys = [];
      for (let index = 0; index < storage.length; index += 1) {
        const key = storage.key(index);
        if (key && key.startsWith(prefix) && isPkceVerifierStorageKey(key)) keys.push(key);
      }
      keys.forEach((key) => storage.removeItem(key));
    } catch {
      // A stale verifier expires harmlessly; the actual auth session remains tab-scoped.
    }
  }
}

function waitForAuthLinkResult(operation) {
  const trackedOperation = Promise.resolve(operation);
  let timerId;
  const timeout = new Promise((_, reject) => {
    timerId = window.setTimeout(() => {
      const failure = new Error(AUTH_LINK_TIMEOUT_MESSAGE);
      failure.code = "auth_link_timeout";
      failure.authLinkTransient = true;
      failure.authLinkContinuation = trackedOperation;
      reject(failure);
    }, AUTH_REQUEST_TIMEOUT_MS);
  });
  return Promise.race([trackedOperation, timeout])
    .then((result) => {
      if (state.authLinkError?.code === "auth_link_timeout") state.authLinkError = null;
      return result;
    })
    .finally(() => window.clearTimeout(timerId));
}

async function resumeAuthLinkAfterTimeout(failure, onSuccess, onFailure) {
  let authLink;
  try {
    authLink = await failure?.authLinkContinuation;
  } catch (lateError) {
    state.authLinkContinuationPending = false;
    await onFailure(lateError);
    return;
  }
  state.authLinkContinuationPending = false;
  if (state.authLinkError?.code === "auth_link_timeout") state.authLinkError = null;
  await onSuccess(authLink);
}

function retryAuthLinkIfIdle() {
  if (state.authLinkContinuationPending) {
    toast("Проверка ссылки ещё продолжается. Не обновляйте страницу — результат появится автоматически.", "info");
    return false;
  }
  window.location.reload();
  return true;
}

async function initialize() {
  bindGlobalEvents();

  const configProblems = validateConfig(CONFIG);
  if (configProblems.length) {
    renderSetup(configProblems);
    return;
  }

  const createClient = await loadSupabaseCreateClient();
  state.authStorageKey = `contentengine.creator-workspace.${new URL(CONFIG.SUPABASE_URL).hostname}.auth-session.v1`;
  state.supabase = createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_PUBLISHABLE_KEY, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
      flowType: "pkce",
      storage: createHybridAuthStorage(),
      storageKey: state.authStorageKey,
    },
  });
  state.api = new CreatorApi(state.supabase, CONFIG);
  void restorePublicRecoveryReceipt();

  let authLink = null;
  try {
    authLink = await waitForAuthLinkResult(consumeAuthLink());
  } catch (error) {
    state.authLinkContinuationPending = Boolean(
      error?.code === "auth_link_timeout" && error.authLinkContinuation,
    );
    handleAuthLinkFailure(error);
    render();
    if (error?.code === "auth_link_timeout" && error.authLinkContinuation) {
      void resumeAuthLinkAfterTimeout(
        error,
        completeInitialization,
        async (lateError) => {
          handleAuthLinkFailure(lateError);
          render();
        },
      ).catch((lateError) => {
        console.error(lateError);
        renderFatal(lateError);
        window.CONTENTENGINE_BOOT_WATCHDOG?.failed("auth-link-resume");
      });
    }
    return;
  }
  await completeInitialization(authLink);
}

async function completeInitialization(authLink) {
  if (authLink?.purpose) {
    state.authPurpose = authLink.purpose;
    state.forcePassword = ["invite", "recovery"].includes(authLink.purpose);
  }

  const sessionResult = authLink?.accepted
    ? { data: { session: authLink.session }, error: null }
    : await withUiTimeout(
      state.supabase.auth.getSession(),
      AUTH_REQUEST_TIMEOUT_MS,
      "Сервер входа не ответил за 15 секунд. Проверьте соединение и повторите.",
    );
  const { data, error } = sessionResult;
  if (error) throw error;
  state.session = data.session;
  state.user = data.session?.user || null;
  state.forcePassword = state.forcePassword || requiresPasswordChange(state.user);

  state.supabase.auth.onAuthStateChange((event, session) => {
    window.setTimeout(() => handleAuthStateChange(event, session), 0);
  });

  if (state.session && !state.forcePassword) {
    await loadBootstrap();
  }

  establishDefaultRoute();
  render();
}

function bindGlobalEvents() {
  window.addEventListener("storage", (event) => {
    if (event.key === PORTAL_THEME_STORAGE_KEY) {
      applyPortalTheme(event.newValue, { persist: false, announce: false });
    }
    if (event.key === NAVIGATION_MODE_STORAGE_KEY) {
      applyNavigationMode(event.newValue, {
        persist: false,
        announce: false,
        rerender: true,
      });
    }
    if (event.key === PUBLIC_RECOVERY_RECEIPT_STORAGE_KEY) {
      state.resetReceipt = readStoredPublicRecoveryReceipt();
      if (state.route.path === "/reset-password") {
        renderResetRequest();
        void restorePublicRecoveryReceipt();
      }
    }
  });
  window.setInterval(
    refreshManagerDashboardIfStale,
    MANAGER_DASHBOARD_MAX_AGE_MS,
  );
  window.setInterval(
    () => { void refreshTrainingPracticalReviews({ silent: true }); },
    MANAGER_DASHBOARD_MAX_AGE_MS,
  );
  window.addEventListener("hashchange", () => {
    state.route = parseRoute();
    state.workspaceDeepLinkFocusKey = "";
    if (state.route.path !== "/workspace/generation") stopRealGenerationPolling();
    if (state.route.path !== "/workspace/research") stopProductResearchPolling();
    if (state.route.path !== "/workspace/review") stopContentReviewPolling();
    if (
      state.route.path === "/workspace/team"
      && managerDashboardIsStale()
    ) {
      state.managerDashboard.status = "idle";
      state.operationalHealth.status = "idle";
      state.generationSpend.status = "idle";
    }
    state.routeTransition = true;
    if (
      state.route.path === "/workspace/home"
      && !["loading", "refreshing"].includes(state.home.status)
    ) state.home.status = "idle";
    setMobileNavOpen(false);
    state.myWork.notificationsOpen = false;
    document.body.classList.remove("notification-center-open");
    render();
    settleRouteView();
    track("route_viewed", { route: state.route.path });
  });
  window.addEventListener("resize", () => {
    if (window.innerWidth > 820 && state.mobileNavOpen) setMobileNavOpen(false);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      refreshManagerDashboardIfStale();
      void refreshTrainingPracticalReviews({ silent: true });
      scheduleRealGenerationPolling(250);
      scheduleContentReviewPolling(250);
    } else {
      stopRealGenerationPolling();
      stopContentReviewPolling();
    }
  });

  document.addEventListener("click", handleClick);
  document.addEventListener("submit", handleSubmit);
  document.addEventListener("input", handleFormActivity);
  document.addEventListener("change", handleChange);
  document.addEventListener("dragstart", handleDragStart);
  document.addEventListener("dragover", handleDragOver);
  document.addEventListener("dragleave", handleDragLeave);
  document.addEventListener("drop", handleDrop);
  document.addEventListener("dragend", handleDragEnd);
  document.addEventListener("keydown", handleKeyDown);
}

function managerDashboardIsStale() {
  const oldestConfirmedAt = Math.min(
    Number(state.managerDashboard.updatedAt) || 0,
    Number(state.operationalHealth.updatedAt) || 0,
    Number(state.generationSpend.updatedAt) || 0,
  );
  return oldestConfirmedAt === 0
    || Date.now() - oldestConfirmedAt > MANAGER_DASHBOARD_MAX_AGE_MS;
}

function refreshManagerDashboardIfStale() {
  if (
    document.visibilityState !== "visible"
    || state.route.path !== "/workspace/team"
    || !canManageTeam()
    || !managerDashboardIsStale()
    || ["loading", "refreshing"].includes(state.managerDashboard.status)
    || ["loading", "refreshing"].includes(state.operationalHealth.status)
    || ["loading", "refreshing"].includes(state.generationSpend.status)
  ) return;
  void loadManagerDashboard({ silent: true });
}

async function handleAuthStateChange(event, session) {
  if (event === "SIGNED_OUT") {
    clearAuthenticatedState();
    navigate("/login", true);
    return;
  }

  if (event === "PASSWORD_RECOVERY") {
    state.session = session;
    state.user = session?.user || null;
    state.authPurpose = "recovery";
    state.forcePassword = true;
    navigate("/set-password", true);
    return;
  }

  if (["TOKEN_REFRESHED", "USER_UPDATED", "SIGNED_IN"].includes(event)) {
    state.session = session;
    state.user = session?.user || null;
    state.forcePassword = state.forcePassword || requiresPasswordChange(state.user);
  }
}

async function requireAuthLinkSession(operation, purpose) {
  try {
    const result = await operation;
    if (result?.error) throw result.error;
    const session = result?.data?.session || null;
    if (!session) {
      const failure = new Error("Auth link response did not contain a session");
      failure.code = "auth_link_session_missing";
      failure.authLinkTransient = true;
      throw failure;
    }
    return session;
  } catch (error) {
    const failure = error instanceof Error ? error : new Error("Auth link request failed");
    failure.authPurpose = purpose;
    throw failure;
  }
}

async function consumeAuthLink() {
  const query = new URLSearchParams(window.location.search);
  const rawHash = window.location.hash && !window.location.hash.startsWith("#/")
    ? window.location.hash.slice(1)
    : "";
  const fragment = new URLSearchParams(rawHash);
  const errorDescription = query.get("error_description") || fragment.get("error_description");
  const errorCode = query.get("error_code") || query.get("error") || fragment.get("error_code") || fragment.get("error");
  if (errorDescription || errorCode) {
    const failure = new Error(errorDescription || "Auth link is invalid or has expired");
    failure.code = errorCode || "auth_link_invalid";
    failure.authPurpose = query.get("type") || query.get("auth") || fragment.get("type") || "unknown";
    throw failure;
  }

  let purpose = query.get("type") || query.get("auth") || fragment.get("type");
  const tokenHash = query.get("token_hash") || fragment.get("token_hash");
  const code = query.get("code");
  const accessToken = fragment.get("access_token");
  const refreshToken = fragment.get("refresh_token");
  if (code && !purpose) purpose = "invite";
  let session = null;

  if (tokenHash && purpose) {
    session = await requireAuthLinkSession(
      state.supabase.auth.verifyOtp({ token_hash: tokenHash, type: purpose }),
      purpose,
    );
  } else if (code) {
    session = await requireAuthLinkSession(
      state.supabase.auth.exchangeCodeForSession(code),
      purpose,
    );
  } else if (accessToken && refreshToken) {
    session = await requireAuthLinkSession(
      state.supabase.auth.setSession({
        access_token: accessToken,
        refresh_token: refreshToken,
      }),
      purpose,
    );
  }

  const accepted = Boolean(session);
  if (accepted) {
    clearStoredPkceVerifier();
    const next = new URL(window.location.href);
    next.search = "";
    next.hash = ["invite", "recovery"].includes(purpose) ? "#/set-password" : "#/learn";
    window.history.replaceState({}, "", next);
    state.route = parseRoute();
  }

  return { accepted, purpose, session };
}

function normalizeAuthLinkError(error) {
  const raw = String(error?.message || "").toLowerCase();
  const code = String(error?.code || "").toLowerCase();
  const status = Number(error?.status || error?.statusCode || error?.context?.status || 0);
  const purpose = ["invite", "recovery"].includes(error?.authPurpose)
    ? error.authPurpose
    : raw.includes("invite") ? "invite" : "recovery";
  const transient = error?.authLinkTransient === true
    || code === "auth_link_timeout"
    || code === "auth_link_session_missing"
    || [408, 429].includes(status)
    || status >= 500
    || error?.name === "TypeError"
    || /failed to fetch|network|timed? out|timeout|temporar(?:y|ily)|service unavailable|bad gateway|gateway timeout/u.test(raw);
  const definitiveCodes = new Set([
    "otp_expired",
    "token_expired",
    "invalid_token",
    "invalid_grant",
    "flow_state_expired",
    "flow_state_not_found",
    "bad_code_verifier",
  ]);
  const definitiveMessage = /(?:email\s+)?link.{0,40}(?:expired|invalid|already\s+(?:used|consumed))|token.{0,40}(?:expired|invalid|already\s+(?:used|consumed))/u.test(raw);
  const definitive = !transient && (definitiveCodes.has(code) || definitiveMessage);
  return {
    purpose,
    code: code || (definitive ? "auth_link_expired" : "auth_link_failed"),
    expired: definitive,
    definitive,
    transient: !definitive,
  };
}

function handleAuthLinkFailure(error) {
  const failure = normalizeAuthLinkError(error);
  state.authLinkError = failure;
  if (failure.definitive) clearAuthLinkUrl("/auth-link-error");
  return failure;
}

function clearAuthLinkUrl(route = "/auth-link-error") {
  const next = new URL(window.location.href);
  next.search = "";
  next.hash = `#${route}`;
  window.history.replaceState({}, "", next);
  state.route = parseRoute();
}

function requiresPasswordChange(user = state.user) {
  const metadata = user?.app_metadata && typeof user.app_metadata === "object"
    ? user.app_metadata
    : {};
  if (metadata[PASSWORD_CHANGE_REQUIRED_MARKER] === true) return true;
  if (metadata[PASSWORD_CHANGE_COMPLETED_MARKER] === true) return false;
  return LEGACY_PASSWORD_CHANGE_MARKERS.some((marker) => metadata[marker] === true);
}

async function loadBootstrap() {
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const requestApi = state.api;
  const requestId = state.bootstrapRequestId + 1;
  state.bootstrapRequestId = requestId;
  state.bootstrapStatus = "loading";
  state.bootstrapError = null;
  render();

  try {
    const raw = await requestApi.bootstrap({ session_id: state.sessionId });
    if (
      requestId !== state.bootstrapRequestId
      || requestEpoch !== state.dataEpoch
      || requestUserId !== state.user?.id
      || requestApi !== state.api
    ) return;
    const bootstrap = normalizeBootstrap(raw);
    requestApi.commitBootstrapContext(raw);
    state.bootstrap = bootstrap;
    state.courseCheckResults = Object.fromEntries(
      state.bootstrap.training.courseChecks.map((item) => [
        item.moduleCode,
        {
          passed: item.passed,
          score: item.correctCount,
          total: item.questionCount,
          status: item.status,
        },
      ]),
    );
    if (membershipLockDetails(state.bootstrap)) {
      state.api.organizationId = null;
      state.examResult = null;
      state.teamInviteResult = null;
      state.managerDashboard.requestId += 1;
      state.managerDashboard.status = "idle";
      state.managerDashboard.data = null;
      state.managerDashboard.error = null;
      state.managerDashboard.updatedAt = 0;
      state.operationalHealth.requestId += 1;
      state.operationalHealth.status = "idle";
      state.operationalHealth.data = null;
      state.operationalHealth.error = null;
      state.operationalHealth.updatedAt = 0;
      state.generationSpend.requestId += 1;
      state.generationSpend.status = "idle";
      state.generationSpend.data = null;
      state.generationSpend.error = null;
      state.generationSpend.notice = "";
      state.generationSpend.updatedAt = 0;
      state.generationSpend.saving = false;
      state.accessCenter.requestId += 1;
      state.accessCenter.status = "idle";
      state.accessCenter.email = "";
      state.accessCenter.result = null;
      state.accessCenter.error = "";
      state.accessCenter.notice = "";
      for (const section of Object.values(state.sections)) {
        section.status = "idle";
        section.data = null;
        section.error = null;
      }
    }
    state.bootstrapStatus = "ready";
    state.bootstrapError = null;
  } catch (error) {
    if (
      requestId !== state.bootstrapRequestId
      || requestEpoch !== state.dataEpoch
      || requestUserId !== state.user?.id
      || requestApi !== state.api
    ) return;
    state.bootstrap = null;
    state.bootstrapStatus = "error";
    state.bootstrapError = error;
  }
}

function normalizeBootstrap(raw) {
  const source = raw?.data && typeof raw.data === "object" ? raw.data : raw || {};
  const trainingSource = {
    ...(source.onboarding && typeof source.onboarding === "object" ? source.onboarding : {}),
    ...(source.learning && typeof source.learning === "object" ? source.learning : {}),
    ...(source.training && typeof source.training === "object" ? source.training : {}),
  };
  const serverModules = Array.isArray(trainingSource.modules) ? trainingSource.modules : [];
  const rawCertifications = trainingSource.certifications || source.certifications || [];
  const certifications = Array.isArray(rawCertifications) ? rawCertifications : [];
  const rawCompletedModules = trainingSource.completed_modules || trainingSource.completedModules || [];
  const completedModules = uniqueStrings([
    ...(Array.isArray(rawCompletedModules) ? rawCompletedModules : []),
    ...serverModules.filter((module) => module.type === "course" && module.completed).map((module) => module.code),
    ...certifications
      .filter((item) => !item.status || item.status === "passed")
      .map((item) => item.module_code || item.code),
  ]);
  const examSource = trainingSource.exam || source.exam || {};
  const rawCourseChecks = trainingSource.course_checks || trainingSource.courseChecks || [];
  const courseChecks = (Array.isArray(rawCourseChecks) ? rawCourseChecks : [])
    .map((item) => ({
      moduleCode: String(item?.module_code || item?.moduleCode || ""),
      status: String(item?.status || "not_started"),
      passed: normalizeBoolean(item?.passed ?? item?.status === "passed"),
      correctCount: Math.max(0, Number(item?.correct_count ?? item?.correctCount ?? 0)),
      questionCount: Math.max(0, Number(item?.question_count ?? item?.questionCount ?? 0)),
      completedAt: item?.completed_at ?? item?.completedAt ?? null,
    }))
    .filter((item) => item.moduleCode);
  const examPassed = normalizeBoolean(
    examSource.passed ??
      trainingSource.exam_passed ??
      source.exam_passed ??
      certifications.some(
        (item) => (item.module_code || item.code) === FINAL_EXAM_CODE && item.status === "passed",
      ),
  );
  const workspaceAccess = normalizeBoolean(
    source.workspace_access ??
      source.workspace_open ??
      source.access?.workspace_access ??
      source.gate?.workspace_access ??
      trainingSource.workspace_access ??
      false,
  );
  const practicalProject = normalizeTrainingPracticalProject(
    trainingSource.practical_project || trainingSource.practicalProject || null,
  );
  const practicalReviews = normalizeTrainingPracticalReviews(
    trainingSource.practical_reviews || trainingSource.practicalReviews || [],
  );
  const practicalUploadSource = trainingSource.practical_upload || trainingSource.practicalUpload || {};
  const practicalUpload = {
    bucketId: String(practicalUploadSource.bucket_id || practicalUploadSource.bucketId || ""),
    pathPrefix: String(practicalUploadSource.path_prefix || practicalUploadSource.pathPrefix || ""),
    maxUploadBytes: Math.max(1, Math.min(
      52_428_800,
      Number(practicalUploadSource.max_upload_bytes || practicalUploadSource.maxUploadBytes) || 52_428_800,
    )),
    acceptedMimeTypes: (Array.isArray(practicalUploadSource.accepted_mime_types)
      ? practicalUploadSource.accepted_mime_types
      : Array.isArray(practicalUploadSource.acceptedMimeTypes)
        ? practicalUploadSource.acceptedMimeTypes
        : ["video/mp4"]
    ).map(String).filter((item) => ["video/mp4", "video/webm", "video/quicktime"].includes(item)),
  };

  return {
    accessState: String(source.state || ""),
    profile: source.profile || source.user_profile || {},
    membership: source.membership || {},
    organization: source.organization || {},
    training: {
      completedModules,
      modules: serverModules,
      courseChecks,
      practicalProject,
      practicalReviews,
      practicalUpload,
      exam: {
        passed: examPassed,
        score: normalizePercent(examSource.score ?? trainingSource.exam_score ?? 0),
        attemptCount: Number(examSource.attempt_count ?? examSource.attemptCount ?? 0),
        attemptCount24h: Number(examSource.attempt_count_24h ?? 0),
        attemptLimit24h: Number(examSource.attempt_limit_24h ?? 5),
        available: normalizeBoolean(examSource.available ?? false),
        nextAttemptAt:
          examSource.next_attempt_at ??
          examSource.nextAttemptAt ??
          examSource.cooldown_until ??
          trainingSource.next_attempt_at ??
          null,
        passScore: Number(examSource.pass_score ?? 0),
        questionCount: Number(examSource.question_count ?? 0),
        questions: Array.isArray(examSource.questions) ? examSource.questions : [],
      },
    },
    workspaceAccess,
    storage: {
      bucket: source.storage?.bucket || CONFIG.STORAGE_BUCKET,
      pathPrefix: source.storage?.path_prefix || "",
    },
    capabilities: source.capabilities || {},
    summary: source.summary || {},
    raw: source,
  };
}

function membershipLockDetails(bootstrap = state.bootstrap) {
  return MEMBERSHIP_LOCK_COPY[bootstrap?.accessState] || null;
}

function hasOperationalWorkspaceRole() {
  const role = String(state.bootstrap?.membership?.role || "");
  return OPERATIONAL_WORKSPACE_ROLES.has(role);
}

function practicalProjectApproved() {
  return normalizeTrainingPracticalProject(
    state.bootstrap?.training?.practicalProject,
  ).approved;
}

function hasWorkspaceAccess() {
  if (
    !state.bootstrap
    || state.bootstrap.workspaceAccess !== true
    || !hasOperationalWorkspaceRole()
    || !trainingCatalogReady()
  ) return false;
  const completed = new Set(state.bootstrap.training.completedModules);
  return (
    REQUIRED_MODULE_CODES.every((code) => completed.has(code)) &&
    practicalProjectApproved() &&
    state.bootstrap.training.exam.passed === true
  );
}

function prerequisitesComplete() {
  const completed = new Set(state.bootstrap?.training?.completedModules || []);
  return REQUIRED_MODULE_CODES.every((code) => completed.has(code));
}

function learningPreferenceStorage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function restoreLearningTrack() {
  const key = learningTrackStorageKey(state.user?.id);
  const storage = learningPreferenceStorage();
  return normalizeLearningTrack(key && storage ? safeStorageGet(storage, key) : "all");
}

function persistLearningTrack(track) {
  const normalized = normalizeLearningTrack(track);
  const key = learningTrackStorageKey(state.user?.id);
  const storage = learningPreferenceStorage();
  if (key && storage) safeStorageSet(storage, key, normalized);
  return normalized;
}

function learningTrackPickerMarkup(selectedTrack = restoreLearningTrack()) {
  const normalized = normalizeLearningTrack(selectedTrack);
  const track = LEARNING_TRACKS[normalized];
  return `
    <section class="card learning-track-picker" data-learning-track-picker aria-labelledby="learning-track-title">
      <div class="learning-track-picker__head">
        <div>
          <p class="eyebrow">Сначала определите свою задачу</p>
          <h2 id="learning-track-title">Кем вы будете в этой смене?</h2>
        </div>
        <p>Выбор расставит акценты в примерах и тренажёрах. Четыре обязательных блока, тесты и итоговый экзамен остаются общими для всех.</p>
      </div>
      <div class="learning-track-picker__choices" role="group" aria-label="Моя учебная задача">
        ${Object.values(LEARNING_TRACKS).map((option) => `
          <button type="button" data-action="select-learning-track" data-learning-track="${escapeHtml(option.id)}" aria-pressed="${option.id === normalized ? "true" : "false"}">${escapeHtml(option.shortLabel)}</button>
        `).join("")}
      </div>
      <div class="learning-track-picker__result" data-learning-track-result role="status" aria-live="polite">
        <span class="learning-track-picker__number" aria-hidden="true">01</span>
        <div>
          <p class="eyebrow">Ваш учебный акцент</p>
          <h3 data-learning-track-title>${escapeHtml(track.title)}</h3>
          <p data-learning-track-description>${escapeHtml(track.description)}</p>
          <span class="learning-track-picker__focus" data-learning-track-focus>${escapeHtml(track.focus)}</span>
        </div>
        <a class="btn btn-secondary" data-learning-track-optional href="${escapeHtml(track.optionalHref)}">${escapeHtml(track.optionalTitle)} <span aria-hidden="true">→</span></a>
      </div>
    </section>
  `;
}

function learningSafetyGateMarkup() {
  const signals = [
    {
      title: "Товар или артикул не совпадает",
      body: "Не используйте похожий товар и не меняйте код самостоятельно. Остановите задачу и запросите точные материалы.",
    },
    {
      title: "Права, доступ или обещания о товаре неясны",
      body: "Не передавайте пароль, не берите материалы из поиска и не добавляйте обещания, которых нет в одобренном задании.",
    },
    {
      title: "Рекламный статус публикации не подтверждён",
      body: "Не пытайтесь убрать признаки рекламы словами «личное мнение». Получите датированное решение ответственного до размещения.",
    },
  ];
  return `
    <section class="card learning-safety-gate" aria-labelledby="learning-safety-gate-title">
      <div class="learning-safety-gate__intro">
        <span aria-hidden="true">!</span>
        <div><p class="eyebrow">Стоп-правило до любого действия</p><h2 id="learning-safety-gate-title">Не угадывайте — остановитесь и уточните</h2><p>Откройте сигнал, чтобы увидеть безопасный следующий шаг. Эти правила действуют до съёмки, генерации и публикации.</p></div>
      </div>
      <div class="learning-safety-gate__signals">
        ${signals.map((signal, index) => `<details><summary><span>${index + 1}</span>${escapeHtml(signal.title)}</summary><p>${escapeHtml(signal.body)}</p></details>`).join("")}
      </div>
    </section>
  `;
}

function restoreLessonJourney(course) {
  const lessons = Array.isArray(course?.lessons) ? course.lessons : [];
  const key = lessonJourneyStorageKey(state.user?.id, course?.code, course?.version);
  if (!key) return normalizeLessonJourney(null, lessons);
  const storage = learningPreferenceStorage();
  if (!storage) return normalizeLessonJourney(null, lessons);
  let raw = null;
  try {
    raw = JSON.parse(safeStorageGet(storage, key) || "null");
  } catch {
    safeStorageRemove(storage, key);
  }
  return normalizeLessonJourney(raw, lessons);
}

function persistLessonJourney(course, journey) {
  const lessons = Array.isArray(course?.lessons) ? course.lessons : [];
  const normalized = normalizeLessonJourney(journey, lessons);
  const key = lessonJourneyStorageKey(state.user?.id, course?.code, course?.version);
  const storage = learningPreferenceStorage();
  if (key && storage) safeStorageSet(storage, key, JSON.stringify({
    activeLessonId: normalized.activeLessonId,
    understoodLessonIds: normalized.understoodLessonIds,
  }));
  return normalized;
}

function courseLessonPlayerMarkup(course, journey) {
  const total = course.lessons.length;
  const normalized = normalizeLessonJourney(journey, course.lessons);
  const percent = lessonJourneyPercent(normalized, course.lessons);
  return `
    <section class="card course-lesson-player" data-course-lesson-player data-course-code="${escapeHtml(course.code)}" aria-labelledby="course-lesson-player-title">
      <div class="course-lesson-player__copy">
        <p class="eyebrow">Ваше место в блоке</p>
        <strong id="course-lesson-player-title" data-course-lesson-current>Урок ${normalized.activeIndex + 1} из ${total}</strong>
      </div>
      <span class="course-lesson-player__count" data-course-lesson-count>${normalized.understood.length} из ${total} отмечено понятным</span>
      <div class="course-lesson-player__bar" role="progressbar" aria-label="Личный прогресс по урокам блока" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}" data-course-lesson-progress>
        <span style="--lesson-progress:${percent}%" data-course-lesson-progress-fill></span>
      </div>
    </section>
  `;
}

function courseRequiredLessonIds(course) {
  const lessons = Array.isArray(course?.lessons) ? course.lessons : [];
  if (course?.mastery?.lessonRequirement === "all") return lessons.map((lesson) => lesson.id);
  return lessons.filter((lesson) => lesson.trackRecommended).map((lesson) => lesson.id);
}

function courseMasteryState(course) {
  const journey = restoreLessonJourney(course);
  const serverCompleted = state.bootstrap?.training?.completedModules?.includes(course.code) === true;
  const requiredLessonIds = courseRequiredLessonIds(course);
  const requiredWalkthroughIds = course.mastery?.requiredWalkthroughIds || [];
  const authoritativeWalkthroughIds = requiredWalkthroughIds.filter((walkthroughId) => (
    state.trainingProgress.items.get(trainingProgressKey(course.code, walkthroughId))?.completed === true
  ));
  const completedWalkthroughIds = serverCompleted
    ? requiredWalkthroughIds
    : [...new Set([
      ...authoritativeWalkthroughIds,
      ...Array.from(document.querySelectorAll(
        `[data-training-course="${CSS.escape(course.code)}"][data-training-complete="true"]`,
      )).map((root) => String(root.dataset.trainingWalkthrough || "")).filter(Boolean),
    ])];
  const confirmations = Array.from(document.querySelectorAll("[data-course-ack]"));
  return courseMasterySnapshot({
    requiredLessonIds,
    understoodLessonIds: serverCompleted ? requiredLessonIds : journey.understoodLessonIds,
    requiredWalkthroughIds,
    completedWalkthroughIds,
    testPassed: state.courseCheckResults[course.code]?.passed === true
      || serverCompleted,
    confirmationCount: confirmations.length,
    confirmedCount: confirmations.filter((input) => input.checked).length,
    weights: course.mastery?.weights,
  });
}

function masteryTaskCopy(key, task) {
  const labels = {
    lessons: ["Изучите основной маршрут", "уроков отмечено понятными"],
    practice: ["Завершите обязательную лабораторию", "практик подтверждено"],
    test: ["Пройдите рабочую аттестацию", "серверная проверка"],
    confirmation: ["Подтвердите готовность", "пунктов самопроверки"],
  };
  const [title, suffix] = labels[key];
  const status = task.total
    ? `${task.done} из ${task.total} ${suffix}`
    : "дополнительный шаг не требуется";
  return { title, status };
}

function courseMasteryCoachMarkup(course) {
  const tasks = ["lessons", "practice", "test", "confirmation"];
  return `
    <section class="card course-mastery-coach" data-course-mastery-coach data-course-code="${escapeHtml(course.code)}" aria-labelledby="course-mastery-title">
      <header class="course-mastery-coach__header">
        <div><p class="eyebrow">Тренер навыка · учебные XP</p><h2 id="course-mastery-title">Не просто прочитайте — подтвердите действие</h2><p>Блок считается освоенным после маршрута, лаборатории, рабочей аттестации и финальной самопроверки.</p></div>
        <div class="course-mastery-coach__score" aria-label="Текущий учебный опыт"><strong data-course-mastery-xp>0</strong><span>из 100 XP</span></div>
      </header>
      <div class="course-mastery-coach__bar" role="progressbar" aria-label="Освоение навыка" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-course-mastery-progress><span data-course-mastery-progress-fill style="--mastery-progress:0%"></span></div>
      <ol class="course-mastery-coach__tasks">
        ${tasks.map((key, index) => {
          const copy = masteryTaskCopy(key, { done: 0, total: key === "test" ? 1 : 0 });
          return `<li data-course-mastery-task="${key}"><span aria-hidden="true">${index + 1}</span><div><strong>${escapeHtml(copy.title)}</strong><small data-course-mastery-status>${escapeHtml(copy.status)}</small></div><button class="btn btn-secondary btn-small" type="button" data-action="training-mastery-next" data-mastery-step="${key}">Перейти <span aria-hidden="true">→</span></button></li>`;
        }).join("")}
      </ol>
      <p class="course-mastery-coach__note"><span aria-hidden="true">◎</span> XP показывают только учебный прогресс: они не являются деньгами, рейтингом сотрудника или допуском к работе.</p>
    </section>
  `;
}

function syncCourseMasteryPanel(course = null) {
  const courseCode = String(course?.code || document.querySelector("[data-course-lesson-player]")?.dataset.courseCode || "");
  const activeCourse = course || learningCourses().find((item) => item.code === courseCode);
  if (!activeCourse) return null;
  const snapshot = courseMasteryState(activeCourse);
  const root = document.querySelector("[data-course-mastery-coach]");
  if (root) {
    root.dataset.masteryReady = snapshot.ready ? "true" : "false";
    const score = root.querySelector("[data-course-mastery-xp]");
    const progress = root.querySelector("[data-course-mastery-progress]");
    const fill = root.querySelector("[data-course-mastery-progress-fill]");
    if (score) score.textContent = String(snapshot.xp);
    progress?.setAttribute("aria-valuenow", String(snapshot.xp));
    if (fill) fill.style.setProperty("--mastery-progress", `${snapshot.xp}%`);
    root.querySelectorAll("[data-course-mastery-task]").forEach((item) => {
      const key = item.dataset.courseMasteryTask;
      const task = snapshot.tasks[key];
      if (!task) return;
      const copy = masteryTaskCopy(key, task);
      item.classList.toggle("is-complete", task.complete);
      item.classList.toggle("is-next", snapshot.nextStep === key);
      const status = item.querySelector("[data-course-mastery-status]");
      if (status) status.textContent = task.complete ? `Готово · ${copy.status}` : copy.status;
      const button = item.querySelector('[data-action="training-mastery-next"]');
      if (button) {
        button.disabled = task.complete;
        button.innerHTML = task.complete
          ? '<span aria-hidden="true">✓</span> Готово'
          : 'Перейти <span aria-hidden="true">→</span>';
      }
    });
  }
  const button = document.querySelector('[data-action="complete-course"]');
  const completionInFlight = state.trainingProgress.completionInFlight.has(activeCourse.code);
  if (button) {
    button.disabled = !snapshot.ready || completionInFlight;
    button.setAttribute("aria-busy", completionInFlight ? "true" : "false");
  }
  const reason = document.querySelector("[data-course-completion-reason]");
  if (reason) {
    const copy = {
      lessons: "Сначала отметьте понятными все уроки вашего маршрута.",
      practice: "Сначала завершите обязательную лабораторию и дождитесь сохранения прогресса.",
      test: "Сначала пройдите рабочую аттестацию блока.",
      confirmation: "Подтвердите все пункты финальной самопроверки.",
      done: "Все четыре шага готовы — блок можно завершить.",
    };
    reason.textContent = copy[snapshot.nextStep];
    reason.dataset.status = snapshot.ready ? "ready" : "pending";
  }
  return snapshot;
}

function syncCourseLessonJourney(course, journey, { focus = false, scroll = false } = {}) {
  const lessons = Array.from(document.querySelectorAll("[data-course-lesson]"));
  if (!lessons.length) return normalizeLessonJourney(journey, []);
  const normalized = persistLessonJourney(course, journey);
  const understood = new Set(normalized.understood);
  lessons.forEach((lesson, index) => {
    const active = index === normalized.activeIndex;
    const complete = understood.has(index);
    lesson.classList.toggle("is-active", active);
    lesson.classList.toggle("is-understood", complete);
    lesson.dataset.lessonState = complete ? "understood" : active ? "current" : "not-started";
    const details = lesson.querySelector("[data-course-lesson-details]");
    const toggle = lesson.querySelector('[data-action="training-lesson-toggle"]');
    if (details) details.hidden = !active;
    if (toggle) {
      toggle.setAttribute("aria-expanded", active ? "true" : "false");
      toggle.setAttribute("aria-label", `${active ? "Свернуть" : "Открыть"} урок «${lesson.querySelector("h2")?.textContent || index + 1}»`);
    }
    const mark = lesson.querySelector('[data-action="training-lesson-understood"]');
    if (mark) {
      mark.setAttribute("aria-pressed", complete ? "true" : "false");
      mark.innerHTML = complete
        ? '<span aria-hidden="true">✓</span> Урок понятен'
        : index < lessons.length - 1
          ? 'Понятно — следующий урок <span aria-hidden="true">→</span>'
          : '<span aria-hidden="true">✓</span> Урок понятен';
    }
  });
  document.querySelectorAll("[data-course-roadmap-lesson]").forEach((item) => {
    const index = Number(item.dataset.courseRoadmapLesson);
    item.classList.toggle("is-understood", understood.has(index));
    const button = item.querySelector("button");
    if (button) {
      button.setAttribute("aria-current", index === normalized.activeIndex ? "step" : "false");
      const marker = button.querySelector("span");
      if (marker) marker.textContent = understood.has(index) ? "✓" : String(index + 1);
    }
  });
  const percent = lessonJourneyPercent(normalized, course.lessons);
  const current = document.querySelector("[data-course-lesson-current]");
  const count = document.querySelector("[data-course-lesson-count]");
  const progress = document.querySelector("[data-course-lesson-progress]");
  const fill = document.querySelector("[data-course-lesson-progress-fill]");
  if (current) current.textContent = `Урок ${normalized.activeIndex + 1} из ${lessons.length}`;
  if (count) count.textContent = `${understood.size} из ${lessons.length} отмечено понятным`;
  progress?.setAttribute("aria-valuenow", String(percent));
  if (fill) fill.style.setProperty("--lesson-progress", `${percent}%`);
  const activeLesson = lessons[normalized.activeIndex];
  if (scroll) scrollElementIntoView(activeLesson);
  if (focus) activeLesson?.querySelector('[data-action="training-lesson-toggle"]')?.focus({ preventScroll: true });
  track("training_lesson_viewed", {
    module_code: course.code,
    lesson_index: normalized.activeIndex + 1,
    lesson_state: understood.has(normalized.activeIndex) ? "understood" : "current",
    learning_track: restoreLearningTrack(),
  });
  syncCourseMasteryPanel(course);
  return normalized;
}

function closeTrainingAchievement({ restoreFocus = true } = {}) {
  const root = document.querySelector("[data-training-achievement]");
  if (!root) return;
  const returnFocus = root.__returnFocus;
  root.remove();
  document.body.classList.remove("training-achievement-open");
  if (restoreFocus && returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
}

function showTrainingAchievement(courseCode, returnFocus = document.activeElement) {
  closeTrainingAchievement({ restoreFocus: false });
  const achievement = learningCourses().find((course) => course.code === courseCode)?.achievement;
  document.body.insertAdjacentHTML("beforeend", achievementMarkup(courseCode, achievement));
  const root = document.querySelector("[data-training-achievement]");
  if (!root) return;
  root.__returnFocus = returnFocus;
  document.body.classList.add("training-achievement-open");
  root.querySelector('[data-action="close-training-achievement"]')?.focus({ preventScroll: true });
}

function learningCourses() {
  const modules = state.bootstrap?.training?.modules || [];
  const selectedTrack = restoreLearningTrack();
  const serverCourses = modules
    .filter((module) => module.type === "course")
    .sort((left, right) => Number(left.order || 0) - Number(right.order || 0))
    .map((module) => {
      const content = module.content && typeof module.content === "object" ? module.content : {};
      const meta = content.meta && typeof content.meta === "object" ? content.meta : content;
      const lessonPath = roleAwareLessonPath(
        module.code,
        content.lessons,
        meta.lesson_groups,
        selectedTrack,
      );
      const fullDurationMinutes = Math.max(
        1,
        Math.min(120, Number(meta.duration_minutes) || Math.max(5, lessonPath.allLessons.length * 3)),
      );
      const durationMinutes = fullDurationMinutes;
      const completionChecklist = Array.isArray(meta.completion_checklist)
        ? meta.completion_checklist.map((item) => String(item || "").trim()).filter(Boolean).slice(0, 5)
        : [];
      const glossary = (Array.isArray(meta.glossary) ? meta.glossary : [])
        .slice(0, 24)
        .map((item) => ({
          term: String(item?.term || "").trim().slice(0, 120),
          definition: String(item?.definition || "").trim().slice(0, 600),
        }))
        .filter((item) => item.term && item.definition);
      const rawKnowledgeCheck = meta.knowledge_check && typeof meta.knowledge_check === "object"
        ? meta.knowledge_check
        : {};
      const knowledgeQuestions = (Array.isArray(rawKnowledgeCheck.questions) ? rawKnowledgeCheck.questions : [])
        .slice(0, 8)
        .map((question, index) => ({
          id: String(question?.id || `question_${index + 1}`),
          type: ["single_choice", "multi_select"].includes(String(question?.question_type || question?.type || ""))
            ? String(question.question_type || question.type)
            : "single_choice",
          prompt: String(question?.prompt || ""),
          rationalePrompt: String(
            question?.rationale_prompt
            || question?.rationalePrompt
            || "Объясните, почему выбранный маршрут безопасен и что вы проверите перед следующим действием.",
          ).slice(0, 500),
          requiresRationale: question?.requires_rationale !== false,
          options: (Array.isArray(question?.options) ? question.options : [])
            .slice(0, 6)
            .map((option) => ({ value: String(option?.value || ""), label: String(option?.label || "") }))
            .filter((option) => option.value && option.label),
        }))
        .filter((question) => question.id && question.prompt && question.options.length >= 2);
      const knowledgeCheck = knowledgeQuestions.length
        ? {
            title: String(rawKnowledgeCheck.title || "Проверка блока"),
            audienceLabel: selectedTrack === "all"
              ? String(
                  rawKnowledgeCheck.audience_label
                  || rawKnowledgeCheck.audienceLabel
                  || COURSE_KNOWLEDGE_PRESENTATION[module.code]?.audienceLabel
                  || "Всем участникам",
                ).slice(0, 180)
              : `Ваш трек: ${LEARNING_TRACKS[selectedTrack].shortLabel}`,
            roleHint: String(
              rawKnowledgeCheck.role_hint
              || rawKnowledgeCheck.roleHint
              || COURSE_KNOWLEDGE_PRESENTATION[module.code]?.roleHint
              || "Выберите один безопасный следующий шаг в контексте рабочей задачи.",
            ).slice(0, 500),
            passScore: Math.max(
              1,
              Math.min(knowledgeQuestions.length, Number(rawKnowledgeCheck.pass_score) || knowledgeQuestions.length),
            ),
            questions: knowledgeQuestions,
          }
        : null;
      const mastery = normalizeCourseMastery(
        meta.mastery && typeof meta.mastery === "object"
          ? meta.mastery
          : COURSE_MASTERY_FALLBACKS[module.code],
      );
      const knownLessonIds = new Set(lessonPath.allLessons.map((lesson) => lesson.id));
      const knowledgeRemediation = Object.fromEntries(
        Object.entries(
          meta.knowledge_remediation && typeof meta.knowledge_remediation === "object"
            ? meta.knowledge_remediation
            : {},
        )
          .map(([questionCode, item]) => {
            const source = item && typeof item === "object" ? item : {};
            return [String(questionCode), {
              lessonId: String(source.lesson_id || source.lessonId || ""),
              tip: String(source.tip || "Повторите связанный урок и попробуйте снова.").slice(0, 500),
            }];
          })
          .filter(([questionCode, item]) => questionCode && knownLessonIds.has(item.lessonId)),
      );
      return {
        code: module.code,
        title: module.title,
        summary: module.description || "Обязательный модуль обучения.",
        duration: `${durationMinutes} мин`,
        durationMinutes,
        fullDurationMinutes,
        version: Math.max(1, Number(meta.version) || 1),
        blockLabel: String(meta.block_label || "Блок обучения"),
        outcome: String(meta.outcome || module.description || "Понимание рабочего процесса."),
        level: String(meta.level || "Практический курс"),
        audience: selectedTrack === "all"
          ? String(meta.audience_label || COURSE_AUDIENCE_COPY[module.code] || "Всем участникам")
          : `Ваш трек · ${LEARNING_TRACKS[selectedTrack].shortLabel}`,
        achievement: meta.achievement && typeof meta.achievement === "object"
          ? meta.achievement
          : courseAchievement(module.code),
        glossary,
        completionChecklist,
        knowledgeCheck,
        knowledgeRemediation,
        mastery,
        interactiveWalkthroughs: normalizeInteractiveWalkthroughs(content.interactive_walkthroughs)
          .filter((walkthrough) => !DEDICATED_PLATFORM_WALKTHROUGH_IDS.has(walkthrough.id)),
        lessonGroups: lessonPath.groups,
        allLessonCount: lessonPath.allLessons.length,
        recommendedLessonCount: lessonPath.recommendedLessonIds.length,
        lessons: lessonPath.lessons,
      };
    });
  return serverCourses;
}

function finalExamQuestions() {
  const questions = state.bootstrap?.training?.exam?.questions || [];
  const serverQuestions = questions
    .slice()
    .sort((left, right) => Number(left.order || 0) - Number(right.order || 0))
    .map((question) => {
      const code = String(question.code || "");
      const presentation = FINAL_EXAM_PRESENTATION[code];
      return {
        code,
        type: question.type || "single_choice",
        text: String(presentation?.prompt || question.prompt || ""),
        options: (Array.isArray(question.options) ? question.options : [])
          .map(normalizeExamOption)
          .filter((option) => option.value && option.label)
          .map((option) => ({
            value: option.value,
            label: String(presentation?.options?.[option.value] || option.label),
          })),
      };
    });
  return serverQuestions;
}

function finalExamRequiresRationale(questionCode) {
  return FINAL_EXAM_RATIONALE_CODES.includes(String(questionCode || ""));
}

function finalExamRationaleIsValid(value) {
  const rationale = String(value || "").replace(/\s+/gu, " ").trim();
  const words = rationale.toLocaleLowerCase("ru-RU").match(/[\p{L}\p{N}]+/gu) || [];
  const stopWords = new Set(["это", "как", "для", "что", "или", "при", "без", "под", "над", "его", "её", "она", "они", "там", "тут", "так", "вот", "the", "and", "for", "with", "this", "that"]);
  const meaningfulWords = new Set(words.filter((word) => (
    word.length >= 3
    && /\p{L}/u.test(word)
    && /[аеёиоуыэюяaeiouy]/u.test(word)
    && !stopWords.has(word)
  )));
  return rationale.length >= 40
    && rationale.length <= 900
    && words.length >= 7
    && meaningfulWords.size >= 5
    && /риск\s*:.+(проверка|доказательство)\s*:.+(действие|следующий шаг)\s*:/iu.test(rationale);
}

function finalExamDraftKey(userId = state.user?.id) {
  const safeUser = String(userId || "").replace(/[^a-zA-Z0-9_-]/g, "");
  return safeUser ? `contentengine.final-exam-draft.v${FINAL_EXAM_DRAFT_VERSION}:${safeUser}` : "";
}

function persistFinalExamDraft(form) {
  const key = finalExamDraftKey();
  if (!key || !form) return;
  const answers = {};
  finalExamQuestions().forEach((question) => {
    answers[question.code] = Array.from(form.querySelectorAll(
      `input[name="${CSS.escape(`answer_${question.code}`)}"]:checked`,
    )).map((input) => String(input.value || "")).filter(Boolean);
  });
  const rationales = {};
  FINAL_EXAM_RATIONALE_CODES.forEach((questionCode) => {
    const textarea = form.elements.namedItem(`rationale_${questionCode}`);
    rationales[questionCode] = String(textarea?.value || "").slice(0, 900);
  });
  try {
    window.localStorage.setItem(key, JSON.stringify({
      version: FINAL_EXAM_DRAFT_VERSION,
      updatedAt: Date.now(),
      answers,
      rationales,
    }));
  } catch {
    // Draft persistence is a convenience; the protected server remains authoritative.
  }
}

function restoreFinalExamDraft(form = document.querySelector("#exam-form")) {
  const key = finalExamDraftKey();
  if (!key || !form) return false;
  try {
    const draft = JSON.parse(window.localStorage.getItem(key) || "null");
    if (
      !draft
      || draft.version !== FINAL_EXAM_DRAFT_VERSION
      || Date.now() - Number(draft.updatedAt || 0) > FINAL_EXAM_DRAFT_MAX_AGE_MS
    ) {
      window.localStorage.removeItem(key);
      return false;
    }
    finalExamQuestions().forEach((question) => {
      const selected = new Set(Array.isArray(draft.answers?.[question.code])
        ? draft.answers[question.code].map(String)
        : []);
      form.querySelectorAll(`input[name="${CSS.escape(`answer_${question.code}`)}"]`).forEach((input) => {
        input.checked = selected.has(String(input.value || ""));
      });
    });
    FINAL_EXAM_RATIONALE_CODES.forEach((questionCode) => {
      const textarea = form.elements.namedItem(`rationale_${questionCode}`);
      if (!textarea || String(textarea.tagName || "").toUpperCase() !== "TEXTAREA") return;
      textarea.value = String(draft.rationales?.[questionCode] || "").slice(0, 900);
      const counter = textarea.closest(".knowledge-rationale")?.querySelector("[data-rationale-count]");
      if (counter) counter.textContent = String(textarea.value.length);
    });
    const answered = finalExamQuestions().filter((question) => (
      form.querySelector(`input[name="${CSS.escape(`answer_${question.code}`)}"]:checked`)
    )).length;
    const counter = form.querySelector("#exam-answer-count");
    if (counter) counter.textContent = `${answered} из ${finalExamQuestions().length} отвечено`;
    const status = form.querySelector("#exam-draft-status");
    if (status) status.textContent = "Черновик решений и обоснований восстановлен на этом устройстве.";
    return true;
  } catch {
    window.localStorage.removeItem(key);
    return false;
  }
}

function clearFinalExamDraft() {
  const key = finalExamDraftKey();
  if (!key) return;
  try { window.localStorage.removeItem(key); } catch { /* no-op */ }
}

function finalExamPassScore() {
  return Number(state.bootstrap?.training?.exam?.passScore || 0);
}

function trainingCatalogReady() {
  const courses = learningCourses();
  const courseCodes = new Set(courses.map((course) => course.code));
  return (
    courses.length === REQUIRED_MODULE_CODES.length &&
    REQUIRED_MODULE_CODES.every((code) => courseCodes.has(code)) &&
    courses.every((course) => course.title && course.lessons.length > 0 && course.knowledgeCheck?.questions.length === 6) &&
    state.bootstrap?.training?.exam?.questionCount === 12 &&
    finalExamPassScore() >= 1 &&
    finalExamPassScore() <= state.bootstrap.training.exam.questionCount
  );
}

function examQuestionsReady() {
  const questions = finalExamQuestions();
  const questionCodes = new Set(questions.map((question) => question.code));
  return (
    questions.length === state.bootstrap?.training?.exam?.questionCount &&
    questionCodes.size === questions.length &&
    questions.every(
      (question) =>
        question.code &&
        question.text &&
        ["single_choice", "multi_select"].includes(question.type) &&
        question.options.length >= 2,
    )
  );
}

function establishDefaultRoute() {
  const path = state.route.path;
  if (path !== "/") return;
  if (!state.session) navigate("/login", true);
  else if (state.forcePassword) navigate("/set-password", true);
  else if (membershipLockDetails()) navigate("/access-locked", true);
  else if (hasWorkspaceAccess()) navigate("/workspace/home", true);
  else navigate("/learn", true);
}

function destroyAccountVisualController() {
  state.accountVisualMountRequest += 1;
  const current = state.accountVisualController;
  if (current?.slug && current.instance?.getState) {
    state.accountVisualStates.set(current.slug, current.instance.getState());
  }
  current?.instance?.destroy?.();
  current?.destroy?.();
  state.accountVisualController = null;
}

async function mountAccountVisualLesson(visualRoot, slug) {
  const requestId = state.accountVisualMountRequest;
  try {
    const visualModule = await import(ACCOUNT_VISUAL_MODULE_URL);
    if (
      requestId !== state.accountVisualMountRequest
      || !visualRoot.isConnected
      || accountLaunchSlugFromPath(state.route.path) !== slug
    ) return;
    const savedState = state.accountVisualStates.get(slug) || {};
    const instance = visualModule.mountAccountLaunchVisualExamples(visualRoot, {
      ...savedState,
      platform: slug,
      lockPlatform: true,
      instanceId: `account-visual-${slug}`,
    });
    state.accountVisualController = { slug, instance };
  } catch (error) {
    if (requestId !== state.accountVisualMountRequest || !visualRoot.isConnected) return;
    console.error("Account launch visual examples failed", error);
    visualRoot.innerHTML = alertMarkup(
      "Наглядный пример временно не загрузился. Пошаговый чек-лист ниже остаётся доступен.",
      "warning",
    );
  }
}

function render() {
  closeTrainingAchievement({ restoreFocus: false });
  stopAllTrainingWalkthroughs();
  destroyAccountVisualController();
  const path = state.route.path;
  const accountLaunchSlug = accountLaunchSlugFromPath(path);

  if (state.authLinkError) {
    renderAuthLinkError();
    return;
  }

  if (!state.session) {
    if (path === "/reset-password") renderResetRequest();
    else renderLogin();
    return;
  }

  if (state.forcePassword || path === "/set-password") {
    renderSetPassword();
    return;
  }

  if (state.bootstrapStatus === "loading" || state.bootstrapStatus === "idle") {
    renderBootstrapLoading();
    return;
  }

  if (state.bootstrapStatus === "error") {
    renderBootstrapError();
    return;
  }

  if (membershipLockDetails()) {
    renderMembershipLocked();
    return;
  }

  if (!hasWorkspaceAccess()) {
    if (path.startsWith("/workspace/")) {
      navigate("/learn", true);
      return;
    }
    if (path === "/learn/first-shift") {
      renderFirstShift();
      return;
    }
    if (accountLaunchSlug !== null) {
      renderAccountLaunch(accountLaunchSlug);
      return;
    }
    if (path === "/learn/practical") {
      renderTrainingPracticalProject();
      return;
    }
    if (path.startsWith("/learn/") && path !== "/learn/exam") {
      renderCourse(path.replace("/learn/", ""));
      return;
    }
    if (path === "/learn/exam") {
      renderExam();
      return;
    }
    renderLearningHome();
    return;
  }

  if (path === "/learn") {
    renderLearningHome();
    return;
  }
  if (path === "/learn/first-shift") {
    renderFirstShift();
    return;
  }
  if (accountLaunchSlug !== null) {
    renderAccountLaunch(accountLaunchSlug);
    return;
  }
  if (path === "/learn/practical") {
    renderTrainingPracticalProject();
    return;
  }
  if (path.startsWith("/learn/") && path !== "/learn/exam") {
    renderCourse(path.replace("/learn/", ""));
    return;
  }
  if (path === "/learn/exam") {
    renderExam();
    return;
  }

  const requestedSection = path.startsWith("/workspace/")
    ? path.replace("/workspace/", "")
    : "home";
  const section = visibleWorkspaceTabs().some(([key]) => key === requestedSection)
    ? requestedSection
    : "home";
  if (path !== `/workspace/${section}`) {
    navigate(`/workspace/${section}`, true);
    return;
  }
  renderWorkspace(section);
}

function renderLogin(message = "", rememberedEmail = "") {
  app.innerHTML = authLayout(`
    <section class="auth-card" aria-labelledby="login-title">
      <p class="eyebrow">Вход для команды</p>
      <h2 id="login-title">Добро пожаловать</h2>
      <p class="lead">Используйте рабочую почту и ваш персональный пароль.</p>
      ${message ? alertMarkup(message, "danger") : ""}
      <form id="login-form" class="form-stack" novalidate>
        <label class="field">
          <span>Рабочая почта</span>
          <input name="email" type="email" autocomplete="username" inputmode="email" required placeholder="name@company.ru" value="${escapeHtml(rememberedEmail)}" />
        </label>
        <label class="field">
          <span>Пароль</span>
          <input name="password" type="password" autocomplete="current-password" required minlength="8" placeholder="Введите пароль" />
        </label>
        <button class="btn btn-block" type="submit">Войти в завод <span aria-hidden="true">→</span></button>
      </form>
      <div class="auth-actions">
        <a class="text-link" href="#/reset-password">Не помню пароль</a>
      </div>
      <details class="auth-access-guide">
        <summary>Как получить доступ впервые</summary>
        <ol class="auth-start-route" aria-label="Как получить доступ">
          <li><span>1</span><p><strong>Руководитель добавляет вашу рабочую почту</strong><small>Открытой регистрации нет — так чужой человек не попадёт в команду.</small></p></li>
          <li><span>2</span><p><strong>Вы получаете приглашение или временный пароль</strong><small>Задайте пароль по ссылке или войдите с временным паролем и сразу смените его.</small></p></li>
          <li><span>3</span><p><strong>После входа проходите 4 блока и экзамен</strong><small>Затем откроются рабочие разделы, задачи и ваши выплаты.</small></p></li>
        </ol>
      </details>
      <p class="auth-footer"><strong>Нет приглашения?</strong> Попросите руководителя добавить вас в команду. Самостоятельная регистрация закрыта.<br /><span>Сессия действует только в этой вкладке и завершится после её закрытия.</span></p>
    </section>
  `);
  focusFirst(message ? '#login-form input[name="password"]' : "#login-form input");
}

function renderResetRequest(message = "") {
  const receipt = state.resetReceipt;
  const resendAt = Number(receipt?.cooldownUntil || 0);
  const coolingDown = resendAt > Date.now();
  const outcomeUnknown = PUBLIC_RECOVERY_PENDING_STATUSES.has(String(receipt?.status || ""));
  const retrySameRequest = shouldRetrySamePublicRecoveryRequest(receipt);
  const requestedTime = receipt?.requestedAt ? ` ${formatTime(receipt.requestedAt)}` : "";
  const addressHint = receipt?.maskedEmail ? ` для ${receipt.maskedEmail}` : "";
  const receiptMarkup = receipt
    ? alertMarkup(
      outcomeUnknown
        ? retrySameRequest
          ? "Связь прервалась до подтверждения результата. Номер запроса сохранён. Повторите с тем же адресом: сервер проверит тот же запрос и не создаст дубликат."
          : "Сервер сохранил квитанцию, но почтовый сервис не подтвердил итог. Дождитесь окончания защитного интервала; затем можно создать новый запрос."
        : `Запрос принят сервером${requestedTime}${addressHint}. Это квитанция запроса, а не подтверждение доставки письма. Проверьте «Входящие» и «Спам».`,
      outcomeUnknown ? "warning" : "success",
    )
    : "";
  app.innerHTML = authLayout(`
    <section class="auth-card" aria-labelledby="reset-title">
      <p class="eyebrow">Восстановление доступа</p>
      <h2 id="reset-title">Получите ссылку для нового пароля</h2>
      <p class="lead">Укажите рабочую почту. Новый пароль вы зададите после перехода по безопасной ссылке из письма.</p>
      ${message ? alertMarkup(message, "success") : ""}
      ${receiptMarkup}
      <form id="reset-form" class="form-stack" novalidate>
        <label class="field">
          <span>Рабочая почта</span>
          <input name="email" type="email" autocomplete="email" inputmode="email" required placeholder="name@company.ru" />
        </label>
        <button id="reset-submit" class="btn btn-block" type="submit" data-resend-at="${resendAt}" ${coolingDown ? "disabled" : ""}>${coolingDown ? "Повторная отправка временно закрыта" : retrySameRequest ? "Проверить тот же запрос" : receipt ? "Отправить ещё раз" : "Получить ссылку"}</button>
      </form>
      <div class="auth-actions"><a class="text-link" href="#/login">Вернуться ко входу</a></div>
      <p class="auth-footer">Ответ одинаков для любого адреса и не раскрывает наличие аккаунта. Сотрудник поддержки никогда не попросит прислать пароль или содержимое ссылки.</p>
    </section>
  `);
  focusFirst("#reset-form input");
  startResetResendCountdown();
}

function renderAuthLinkError() {
  const failure = state.authLinkError || { purpose: "recovery", definitive: true };
  const recovery = failure.purpose !== "invite";
  if (!failure.definitive && state.authLinkContinuationPending) {
    app.innerHTML = authLayout(`
      <section class="auth-card" aria-labelledby="auth-link-error-title" aria-live="polite">
        <p class="eyebrow">Проверка ссылки</p>
        <h2 id="auth-link-error-title">Проверка продолжается</h2>
        <p class="lead">Сервис входа отвечает дольше обычного. Одноразовая ссылка уже обрабатывается в фоне, результат появится здесь автоматически.</p>
        ${alertMarkup("Не обновляйте страницу и не открывайте ссылку повторно: это может прервать вход или потратить одноразовый токен.", "warning")}
        <p class="auth-footer">Можно оставить вкладку открытой. Кнопка повтора появится только после окончательной временной ошибки.</p>
      </section>
    `);
    return;
  }
  if (!failure.definitive) {
    app.innerHTML = authLayout(`
      <section class="auth-card" aria-labelledby="auth-link-error-title">
        <p class="eyebrow">Временная ошибка связи</p>
        <h2 id="auth-link-error-title">Ссылка сохранена — повторите её</h2>
        <p class="lead">Сервис входа временно не ответил. Мы не удаляли одноразовый токен из адресной строки и не считаем ссылку испорченной.</p>
        ${alertMarkup("Нажмите кнопку один раз и дождитесь ответа. Не запрашивайте новое письмо, пока эта ссылка не получила окончательный результат.", "warning")}
        <div class="form-stack">
          <button class="btn btn-block" type="button" data-action="retry-auth-link">Повторить эту же ссылку</button>
        </div>
        <p class="auth-footer">Адрес ссылки останется без изменений; секретное содержимое на экран не выводится.</p>
      </section>
    `);
    focusFirst("[data-action='retry-auth-link']");
    return;
  }
  app.innerHTML = authLayout(`
    <section class="auth-card" aria-labelledby="auth-link-error-title">
      <p class="eyebrow">Ссылка больше не действует</p>
      <h2 id="auth-link-error-title">${recovery ? "Запросите новую ссылку" : "Нужно новое приглашение"}</h2>
      <p class="lead">${recovery
        ? "Ссылка восстановления устарела, уже использована или открыта не полностью. Токен удалён из адресной строки."
        : "Ссылка приглашения устарела, уже использована или открыта не полностью. Токен удалён из адресной строки."}</p>
      ${alertMarkup(recovery
        ? "Нажмите кнопку ниже и снова укажите ту же рабочую почту. Используйте только самое свежее письмо."
        : "Попросите руководителя повторно отправить приглашение на ваш точный рабочий адрес.", "warning")}
      <div class="form-stack">
        <button class="btn btn-block" type="button" data-action="request-new-auth-link" data-purpose="${recovery ? "recovery" : "invite"}">${recovery ? "Запросить новую ссылку" : "Запросить новое приглашение у руководителя"}</button>
      </div>
      <p class="auth-footer">Обновлять эту страницу не нужно: недействительный токен уже очищен.</p>
    </section>
  `);
  focusFirst("[data-action='request-new-auth-link']");
}

function renderSetPassword(message = "", type = "") {
  app.innerHTML = authLayout(`
    <section class="auth-card" aria-labelledby="password-title">
      <p class="eyebrow">${state.authPurpose === "invite" ? "Активация приглашения" : "Защита аккаунта"}</p>
      <h2 id="password-title">Придумайте пароль</h2>
      <p class="lead">10–128 символов: строчная и заглавная латинские буквы и цифра. Не используйте пароль от почты или соцсетей.</p>
      ${message ? alertMarkup(message, type || "danger") : ""}
      <form id="password-form" class="form-stack" novalidate>
        <label class="field">
          <span>Новый пароль</span>
          <input name="password" type="password" autocomplete="new-password" required minlength="10" maxlength="128" placeholder="Например: NewFactory2026" />
        </label>
        <label class="field">
          <span>Повторите пароль</span>
          <input name="password_confirmation" type="password" autocomplete="new-password" required minlength="10" maxlength="128" placeholder="Ещё раз" />
        </label>
        <button class="btn btn-block" type="submit">Сохранить и продолжить</button>
      </form>
      <p class="auth-footer">До успешного сохранения нового пароля рабочие разделы останутся закрыты. Ссылка активации одноразовая.</p>
    </section>
  `);
  focusFirst("#password-form input");
}

function authLayout(panel) {
  return `
    <div class="auth-layout">
      ${brandAtmosphereMarkup()}
      <div class="auth-theme-control">${themePickerMarkup("auth", true)}</div>
      <section class="auth-story" aria-label="О продукте">
        <div class="auth-brand">
          <div class="brand-mark" aria-hidden="true"><img src="./assets/brand/logo_mark.svg" alt="" /></div>
          <div><strong>ALTEA</strong><span>Контент ИИ Завод</span></div>
        </div>
        <div class="auth-message">
          <p class="eyebrow">От товара до результата</p>
          <h1>Понятная работа.<br /><em>Измеримый результат.</em></h1>
          <p>Обучение, подготовка видео, проверка, размещение и метрики — один безопасный цикл для всей команды.</p>
        </div>
        <div class="auth-steps" aria-label="Этапы работы">
          <div class="auth-step"><b>01 · ОБУЧЕНИЕ</b><span>4 коротких курса и экзамен</span></div>
          <div class="auth-step"><b>02 · ПРОИЗВОДСТВО</b><span>Только назначенные артикулы и материалы</span></div>
          <div class="auth-step"><b>03 · РЕЗУЛЬТАТ</b><span>Ссылка на пост, показатели и выплата</span></div>
        </div>
      </section>
      <main id="main-content" class="auth-panel" tabindex="-1">${panel}</main>
    </div>
  `;
}

function renderBootstrapLoading() {
  app.innerHTML = `
    <main id="main-content" class="boot-screen" tabindex="-1" aria-live="polite">
      <div class="boot-mark" aria-hidden="true">A</div>
      <p class="eyebrow">Безопасный вход выполнен</p>
      <h1>Готовим ваше рабочее место…</h1>
      <p class="muted">Проверяем команду, обучение и доступные задачи.</p>
      <div class="loading-line" aria-hidden="true"><span></span></div>
    </main>
  `;
}

function renderBootstrapError() {
  console.error("Workspace bootstrap failed", state.bootstrapError);
  app.innerHTML = `
    <main id="main-content" class="error-page" tabindex="-1">
      <div class="boot-mark" aria-hidden="true">!</div>
      <p class="eyebrow">Вход выполнен, кабинет недоступен</p>
      <h1>Не удалось загрузить рабочее место</h1>
      <p class="muted">Проверьте соединение и попробуйте ещё раз. Если ошибка повторится, сообщите руководителю команды.</p>
      <div class="inline-actions" style="justify-content:center; margin-top:20px">
        <button class="btn" type="button" data-action="retry-bootstrap">Проверить снова</button>
        <button class="btn btn-secondary" type="button" data-action="logout">Выйти</button>
      </div>
    </main>
  `;
}

function renderMembershipLocked() {
  const details = membershipLockDetails();
  if (!details) return;
  app.innerHTML = `
    <main id="main-content" class="error-page" tabindex="-1" aria-labelledby="membership-lock-title">
      <div class="boot-mark" aria-hidden="true">!</div>
      <p class="eyebrow">Доступ к Контент ИИ Заводу закрыт</p>
      <h1 id="membership-lock-title">${escapeHtml(details.title)}</h1>
      <p class="muted">${escapeHtml(details.message)}</p>
      <p class="tiny muted">Самостоятельно восстановить доступ нельзя. Статус участника меняет только руководитель команды.</p>
      <div class="inline-actions" style="justify-content:center; margin-top:20px">
        <button class="btn btn-secondary" type="button" data-action="logout">Выйти</button>
      </div>
    </main>
  `;
}

function trainingAchievementShelfMarkup(courses, completedModules) {
  const completed = completedModules instanceof Set ? completedModules : new Set(completedModules || []);
  const unlocked = courses.filter((course) => completed.has(course.code)).length;
  return `
    <section class="card training-achievement-shelf" aria-labelledby="training-achievement-shelf-title">
      <header class="training-achievement-shelf__header">
        <div><p class="eyebrow">Коллекция навыков</p><h2 id="training-achievement-shelf-title">Ваши подтверждённые ачивки</h2><p>Значок открывается только после серверного подтверждения курса. Локальные отметки и XP сами по себе его не выдают.</p></div>
        <span class="training-achievement-shelf__count">${unlocked} из ${courses.length}</span>
      </header>
      <ol class="training-achievement-shelf__grid">
        ${courses.map((course) => {
          const achievement = course.achievement?.name || course.achievement?.title
            ? course.achievement
            : courseAchievement(course.code);
          const isUnlocked = completed.has(course.code);
          return `
            <li class="${isUnlocked ? "is-unlocked" : "is-locked"}">
              <span class="training-achievement-shelf__badge" aria-hidden="true">${isUnlocked ? escapeHtml(achievement.icon || "✦") : "◇"}</span>
              <div><strong>${escapeHtml(achievement.name || achievement.title || courseAchievement(course.code).name)}</strong><small>${isUnlocked ? "Подтверждено сервером" : "Откроется после курса"}</small></div>
              <a href="#/learn/${encodeURIComponent(course.code)}" aria-label="${isUnlocked ? "Повторить" : "Открыть"} курс «${escapeHtml(course.title)}»">${isUnlocked ? "Повторить" : "Открыть"} <span aria-hidden="true">→</span></a>
            </li>
          `;
        }).join("")}
      </ol>
    </section>
  `;
}

function renderLearningHome() {
  const completed = new Set(state.bootstrap.training.completedModules);
  const firstShift = ensureFirstShiftState();
  const courses = learningCourses();
  const completeCount = REQUIRED_MODULE_CODES.filter((code) => completed.has(code)).length;
  const examPassed = state.bootstrap.training.exam.passed;
  const practicalProject = normalizeTrainingPracticalProject(state.bootstrap.training.practicalProject);
  const practicalApproved = practicalProject.approved;
  const practicalGate = trainingPracticalGateSnapshot(practicalProject, {
    coursesComplete: completeCount === REQUIRED_MODULE_CODES.length,
    examPassed,
  });
  const coursesComplete = completeCount === REQUIRED_MODULE_CODES.length;
  const practicalStatusLabel = practicalProject.approved
    ? "Принята"
    : practicalProject.status === "submitted"
      ? "На проверке"
      : practicalProject.status === "changes_requested"
        ? "Нужна доработка"
        : coursesComplete ? "Доступна" : "После 4 курсов";
  const practicalStatusTone = practicalProject.approved
    ? "badge-success"
    : practicalProject.status === "submitted"
      ? "badge-warning"
      : coursesComplete ? "badge-info" : "";
  const practicalActionLabel = practicalProject.approved
    ? "Посмотреть решение"
    : practicalProject.status === "submitted"
      ? "Проверить статус"
      : practicalProject.status === "changes_requested"
        ? "Исправить и отправить"
        : "Отправить пробный ролик";
  const progress = Math.round(((completeCount + (practicalApproved ? 1 : 0) + (examPassed ? 1 : 0)) / 6) * 100);
  const catalogReady = trainingCatalogReady();
  const workspaceReady = hasWorkspaceAccess();
  const rolePending = examPassed && practicalApproved && !hasOperationalWorkspaceRole();
  const nextCourse = courses.find((course) => !completed.has(course.code));
  const nextHref = rolePending
    ? "#/learn"
    : workspaceReady
    ? "#/workspace/home"
    : nextCourse
      ? `#/learn/${encodeURIComponent(nextCourse.code)}`
      : !practicalApproved
        ? "#/learn/practical"
        : "#/learn/exam";
  const nextLabel = rolePending
    ? "Проверить назначение роли"
    : workspaceReady
    ? "Перейти к работе"
    : nextCourse
      ? completeCount === 0 ? "Начать с блока 1" : "Продолжить обучение"
      : !practicalApproved
        ? practicalProject.status === "submitted" ? "Проверить решение руководителя" : "Отправить пробный ролик"
        : examPassed ? "Проверить допуск" : "Начать экзамен";
  const nextCourseIndex = nextCourse ? courses.findIndex((course) => course.code === nextCourse.code) : -1;
  const afterNextCourse = nextCourseIndex >= 0 ? courses[nextCourseIndex + 1] : null;
  const nowTitle = rolePending
    ? "Экзамен сдан — рабочую роль назначает руководитель"
    : workspaceReady
    ? "Допуск готов — откройте рабочий кабинет"
    : nextCourse
      ? `Сейчас: ${nextCourse.title}`
      : !practicalApproved
        ? practicalProject.status === "submitted" ? "Сейчас: дождитесь проверки пробного ролика" : "Сейчас: покажите навык на пробном ролике"
        : "Сейчас: итоговый экзамен";
  const nowDescription = rolePending
    ? "Руководитель команды должен назначить вам рабочую роль. Только после этого откроется кабинет; учебная смена ниже остаётся необязательной тренировкой."
    : workspaceReady
    ? `Обучение завершено. Портал покажет одно главное действие на сегодня и проведёт по ${FACTORY_FLOW.length} рабочим этапам.`
    : nextCourse
      ? `Завершите только этот блок. ${afterNextCourse ? `После него откроется «${afterNextCourse.title}».` : "После него откроется итоговый экзамен."}`
      : !practicalApproved
        ? practicalProject.status === "submitted"
          ? "Руководитель должен полностью посмотреть материал и принять его либо вернуть с конкретным замечанием. Повторной кнопкой этот этап не закрывается."
          : "Загрузите один вертикальный ролик, пройдите самопроверку и передайте его руководителю. Только человеческое решение откроет экзамен."
        : "Ответьте на 12 рабочих ситуаций. После успешной попытки автоматически откроется кабинет.";
  const nowStep = workspaceReady || rolePending
    ? "✓"
    : String(nextCourseIndex >= 0 ? nextCourseIndex + 1 : practicalApproved ? 6 : 5).padStart(2, "0");
  const heroTitle = workspaceReady
    ? "Вы готовы к производству"
    : rolePending
      ? "Обучение завершено — роль назначает руководитель"
      : "Освойте цикл и докажите навык на реальной работе";
  const heroDescription = workspaceReady
    ? "Допуск получен. Возвращайтесь к схемам и инструкциям в любой момент — они остаются вашей рабочей шпаргалкой."
    : rolePending
      ? "Экзамен уже сдан. Руководитель команды должен назначить рабочую роль; учебная смена остаётся дополнительной практикой и не открывает кабинет."
      : "От точного товара до опубликованного ролика и метрик: уроки объясняют маршрут, сложные кейсы проверяют решение, а пробный ролик подтверждает практический навык.";
  const primaryActionMarkup = rolePending
    ? `<button class="btn" type="button" data-action="retry-bootstrap">Проверить назначение роли <span aria-hidden="true">↻</span></button>`
    : `<a class="btn" href="${nextHref}">${nextLabel} <span aria-hidden="true">→</span></a>`;
  const heroPrimaryActionMarkup = rolePending
    ? `<button class="btn btn-light" type="button" data-action="retry-bootstrap">Проверить назначение роли <span aria-hidden="true">↻</span></button>`
    : `<a class="btn btn-light" href="${nextHref}">${nextLabel} <span aria-hidden="true">→</span></a>`;

  const content = `
    <div class="page-wrap learning-page">
      <section class="card learning-hero">
        <div class="learning-hero-copy">
          <p class="eyebrow learning-eyebrow">Практическая академия ALTEA</p>
          <h1>${heroTitle}</h1>
          <p>${heroDescription}</p>
          <div class="learning-hero-actions">
            ${heroPrimaryActionMarkup}
            <button class="btn btn-ghost-light" type="button" data-action="scroll-to" data-target="work-map">Посмотреть карту работы</button>
          </div>
        </div>
        <div class="learning-passport" aria-label="Паспорт допуска к работе">
          <div class="learning-passport-head">
            <div>
              <span>Ваш прогресс</span>
              <strong>${progress}%</strong>
            </div>
            <span class="learning-passport-mark" aria-hidden="true">A</span>
          </div>
          <div class="progress-bar progress-bar-gold" role="progressbar" aria-label="Прогресс обучения" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}"><span style="width:${progress}%"></span></div>
          <ol class="passport-steps">
            ${courses.map((course, index) => `
              <li class="${completed.has(course.code) ? "complete" : nextCourse?.code === course.code && !workspaceReady ? "current" : ""}">
                <span>${completed.has(course.code) ? "✓" : index + 1}</span>
                <div><strong>${escapeHtml(course.title)}</strong><small>${completed.has(course.code) ? "готово" : course.duration}</small></div>
              </li>
            `).join("")}
            <li class="${practicalApproved ? "complete" : practicalGate.nextStep === "practical" || practicalGate.nextStep === "manager_review" ? "current" : ""}">
              <span>${practicalApproved ? "✓" : 5}</span>
              <div><strong>Пробная работа</strong><small>${practicalStatusLabel.toLocaleLowerCase("ru-RU")}</small></div>
            </li>
            <li class="${examPassed ? "complete" : practicalGate.nextStep === "exam" ? "current" : ""}">
              <span>${examPassed ? "✓" : 6}</span>
              <div><strong>Итоговый экзамен</strong><small>${examPassed ? "экзамен сдан" : "12 сценариев"}</small></div>
            </li>
          </ol>
        </div>
      </section>

      ${catalogReady ? "" : alertMarkup("Каталог обучения загрузился не полностью. Обновите страницу или обратитесь к администратору — допуск останется закрыт до восстановления данных.", "danger")}

      <section class="card learning-now" aria-labelledby="learning-now-title">
        <div class="learning-now-step" aria-hidden="true"><small>Сейчас</small><strong>${nowStep}</strong></div>
        <div class="learning-now-copy">
          <p class="eyebrow">Один обязательный шаг</p>
          <h2 id="learning-now-title">${escapeHtml(nowTitle)}</h2>
          <p>${escapeHtml(nowDescription)}</p>
        </div>
        ${primaryActionMarkup}
      </section>

      ${learningTrackPickerMarkup()}

      ${trainingAchievementShelfMarkup(courses, completed)}

      ${learningSafetyGateMarkup()}

      <section id="work-map" class="card work-map-section" aria-labelledby="work-map-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Как устроена работа</p>
            <h2 id="work-map-title">Один товар проходит ${FACTORY_FLOW.length} понятных этапов</h2>
          </div>
          <p>Не нужно держать весь процесс в голове: каждый следующий шаг живёт в своём разделе портала.</p>
        </div>
        ${portalWorkflowMarkup()}
        <div class="work-map-rule"><span aria-hidden="true">◎</span><p><strong>Главное правило:</strong> точный артикул товара, исходный файл и итоговая ссылка должны оставаться связаны от загрузки до результата.</p></div>
      </section>

      <div class="learning-section-heading">
        <div>
          <p class="eyebrow">Маршрут обучения</p>
          <h2>Четыре понятных блока: от первой съёмки до результата</h2>
        </div>
        <span>${completeCount} из 4 завершено</span>
      </div>

      <div class="course-grid">
        ${courses.map((course, index) => courseCardMarkup(course, index, completed.has(course.code), nextCourse?.code === course.code && !workspaceReady)).join("")}
      </div>

      <section class="card exam-card premium-exam-card training-practical-card">
        <div class="exam-card-visual" aria-hidden="true">
          <span>${practicalProject.approved ? "✓" : "05"}</span><small>пробная<br />работа</small>
        </div>
        <div class="exam-card-copy">
          <span class="badge ${practicalStatusTone}">${practicalStatusLabel}</span>
          <h2>Докажите навык на одном реальном ролике</h2>
          <p class="muted">Загрузите вертикальный MP4 или безопасную HTTPS-ссылку. Руководитель полностью посмотрит материал и сохранит решение с комментарием.</p>
        </div>
        ${coursesComplete
          ? `<a class="btn" href="#/learn/practical">${practicalActionLabel} <span aria-hidden="true">→</span></a>`
          : `<span class="btn btn-secondary" aria-disabled="true">Сначала завершите курсы</span>`}
      </section>

      <section class="card exam-card premium-exam-card">
        <div class="exam-card-visual" aria-hidden="true">
          <span>12</span><small>рабочих<br />сценариев</small>
        </div>
        <div class="exam-card-copy">
          <span class="badge ${examPassed ? "badge-success" : coursesComplete && practicalApproved ? "badge-info" : ""}">${examPassed ? "Сдан" : !coursesComplete ? "После 4 курсов" : catalogReady && practicalApproved ? "Доступен" : practicalProject.status === "submitted" ? "После проверки ролика" : "После пробной работы"}</span>
          <h2>Финальная проверка перед работой</h2>
          <p class="muted">Нужно решить не меньше ${finalExamPassScore()} из 12 реальных ситуаций: товар, качество, публикация, деньги и безопасность.</p>
        </div>
        ${catalogReady && prerequisitesComplete() && practicalApproved
          ? `<a class="btn" href="#/learn/exam">${examPassed ? "Посмотреть результат" : "Начать экзамен"} <span aria-hidden="true">→</span></a>`
          : `<span class="btn btn-secondary" aria-disabled="true">${coursesComplete ? "Сначала сдайте пробную работу" : "Сначала завершите курсы"}</span>`}
      </section>

      <div class="learning-section-heading learning-section-heading--optional">
        <div>
          <p class="eyebrow">Дополнительная практика · необязательно для допуска</p>
          <h2>Закрепите весь маршрут без рабочих действий</h2>
        </div>
        <span>Можно пройти в любое время</span>
      </div>

      <section class="card first-shift-invite" aria-labelledby="first-shift-invite-title">
        <div class="first-shift-invite-mark" aria-hidden="true"><span>${FIRST_SHIFT_FULL_SCENARIO.steps.length}</span><small>решений</small></div>
        <div>
          <p class="eyebrow">Необязательно · безопасная репетиция · ${FIRST_SHIFT_FULL_SCENARIO.durationMinutes} минут</p>
          <h2 id="first-shift-invite-title">Пройдите полный путь от задачи до выплаты</h2>
          <p>Проверьте основной и подменный артикулы, сумму, исходники, съёмку или генерацию, качество, публикацию, метрики и фактическую выплату.</p>
          <p class="first-shift-invite-note"><span aria-hidden="true">◎</span> Тренажёр не создаёт задач, не списывает деньги и не влияет на допуск.</p>
        </div>
        <a class="btn" href="#/learn/first-shift">${firstShift.completed ? "Посмотреть результат" : firstShift.checked.length || firstShift.stepIndex > 0 ? "Продолжить смену" : "Начать тренировку"} <span aria-hidden="true">→</span></a>
      </section>

      <section class="card first-shift-invite account-launch-invite" aria-labelledby="account-launch-invite-title">
        <div class="first-shift-invite-mark" aria-hidden="true"><span>3</span><small>сети</small></div>
        <div>
          <p class="eyebrow">Необязательно · Instagram · YouTube · VK</p>
          <h2 id="account-launch-invite-title">Запустите новый аккаунт с нуля</h2>
          <p>Регистрация, защита входа, оформление, безопасный прогрев и чек-лист первой публикации — отдельно для каждой площадки.</p>
          <p class="first-shift-invite-note"><span aria-hidden="true">!</span> Без выдуманных лимитов и советов по обходу рекламной маркировки.</p>
        </div>
        <a class="btn" href="#${ACCOUNT_LAUNCH_PATH}">Открыть центр запуска <span aria-hidden="true">→</span></a>
      </section>
    </div>
  `;
  app.innerHTML = learningScaffold(content, "/learn");
}

function renderAccountLaunch(slug = "") {
  const savedChecks = slug ? restoreAccountLaunchChecks(slug) : [];
  const body = slug
    ? accountLaunchGuideMarkup(slug, savedChecks)
    : accountLaunchCenterMarkup();
  const content = `
    <div class="page-wrap account-launch-page">
      ${body || alertMarkup("Маршрут площадки не найден. Вернитесь в центр запуска и выберите Instagram, YouTube или VK.", "danger")}
    </div>
  `;
  app.innerHTML = learningScaffold(content, ACCOUNT_LAUNCH_PATH);
  if (!slug) return;
  const visualRoot = app.querySelector("[data-account-visual-root]");
  if (!visualRoot) return;
  void mountAccountVisualLesson(visualRoot, slug);
}

function portalWorkflowMarkup() {
  return `
    <ol class="portal-workflow" style="--workflow-step-count:${FACTORY_FLOW.length}">
      ${FACTORY_FLOW.map((item, index) => `
        <li>
          <div class="workflow-node"><span>${item.step}</span><i aria-hidden="true">${index === FACTORY_FLOW.length - 1 ? "✓" : "→"}</i></div>
          <strong>${escapeHtml(item.label)}</strong>
          <p>${escapeHtml(item.learning)}</p>
        </li>
      `).join("")}
    </ol>
  `;
}

function courseCardMarkup(course, index, complete, current = false) {
  return `
    <article class="card course-card course-tone-${index + 1} ${complete ? "complete" : ""} ${current ? "current" : ""}">
      <div class="course-card-top">
        <div class="course-number" aria-hidden="true">${String(index + 1).padStart(2, "0")}</div>
        <span class="badge ${complete ? "badge-success" : current ? "badge-info" : ""}">${complete ? "Пройден" : current ? "Начните здесь" : escapeHtml(course.level)}</span>
      </div>
      <div class="course-card-meta"><span>${course.duration}</span><span>${course.recommendedLessonCount < course.allLessonCount ? `${course.recommendedLessonCount} в вашем маршруте · ${course.allLessonCount} всего` : `${course.allLessonCount} уроков`}</span><span>${escapeHtml(course.audience)}</span></div>
      <p class="course-block-label">${escapeHtml(course.blockLabel)}</p>
      <h2>${escapeHtml(course.title)}</h2>
      <p>${escapeHtml(course.summary)}</p>
      ${course.code === "publishing_funnel" ? `<div class="platform-pills" aria-label="Площадки курса"><span>Instagram Reels</span><span>YouTube Shorts</span><span>VK Клипы</span></div>` : ""}
      <div class="course-outcome">
        <span>После курса</span>
        <strong>${escapeHtml(course.outcome)}</strong>
      </div>
      <div class="course-footer">
        <span class="course-status-dot"><i aria-hidden="true"></i>${complete ? "Материал доступен для повторения" : current ? "Ваш следующий шаг" : "Можно посмотреть заранее"}</span>
        <a class="btn btn-small ${complete ? "btn-secondary" : ""}" href="#/learn/${encodeURIComponent(course.code)}">
          ${complete ? "Повторить" : current ? "Начать блок" : "Посмотреть"} <span aria-hidden="true">→</span>
        </a>
      </div>
    </article>
  `;
}

function renderCourse(code) {
  const courses = learningCourses();
  const course = courses.find((item) => item.code === code);
  if (!course) {
    navigate("/learn", true);
    return;
  }
  const courseIndex = Math.max(0, courses.findIndex((item) => item.code === course.code));
  const complete = state.bootstrap.training.completedModules.includes(course.code);
  const checkPassed = complete || state.courseCheckResults[course.code]?.passed === true;
  const lessonJourney = restoreLessonJourney(course);
  const selectedTrack = LEARNING_TRACKS[restoreLearningTrack()];
  const completionChecklist = course.completionChecklist.length
    ? course.completionChecklist
    : [
        "Я понимаю порядок действий в этом разделе.",
        "Я знаю, какие ошибки останавливают задачу.",
        "Я смогу повторить процесс в рабочем кабинете.",
      ];
  const content = `
    <div class="page-wrap learning-page course-page">
      <header class="card course-hero course-tone-${courseIndex + 1}">
        <div class="course-hero-copy">
          <p class="eyebrow"><a href="#/learn">Академия</a> · ${escapeHtml(course.blockLabel)}</p>
          <h1>${escapeHtml(course.title)}</h1>
          <p>${escapeHtml(course.summary)}</p>
          <div class="course-hero-meta">
            <span>${escapeHtml(course.duration)}</span>
            <span>${course.recommendedLessonCount < course.allLessonCount ? `${course.recommendedLessonCount} основных · ${course.allLessonCount} всего` : `${course.allLessonCount} практических уроков`}</span>
            <span>${escapeHtml(course.audience)}</span>
          </div>
          <p class="course-track-note"><strong>Ваш акцент:</strong> ${escapeHtml(selectedTrack.shortLabel)} · ${escapeHtml(selectedTrack.focus)} <a href="#/learn">Изменить задачу</a></p>
        </div>
        <div class="course-hero-outcome">
          <span class="course-hero-icon" aria-hidden="true">${String(courseIndex + 1).padStart(2, "0")}</span>
          <p>Результат курса</p>
          <h2>${escapeHtml(course.outcome)}</h2>
          <span class="badge ${complete ? "badge-success" : ""}">${complete ? "Курс пройден" : "Обязательный курс"}</span>
        </div>
      </header>
      <section class="course-learning-flow" aria-labelledby="course-learning-flow-title">
        <div><p class="eyebrow">Как пройти блок</p><h2 id="course-learning-flow-title">Четыре проверяемых шага</h2></div>
        <ol>
          <li><span>1</span><div><strong>Изучите уроки</strong><small>Пройдите материал сверху вниз и сверьтесь с примерами.</small></div></li>
          <li><span>2</span><div><strong>Закрепите на практике</strong><small>Разберите кадры, решите короткую ситуацию и отметьте самопроверку.</small></div></li>
          <li><span>3</span><div><strong>Пройдите рабочую аттестацию</strong><small>Решения и допуск проверяет защищённый сервер.</small></div></li>
          <li><span>4</span><div><strong>Подтвердите готовность</strong><small>Сверьте финальный чек-лист — портал сохранит результат и выдаст ачивку.</small></div></li>
        </ol>
      </section>
      ${courseMasteryCoachMarkup(course)}
      <div class="course-layout">
        <div>
          ${courseLessonPlayerMarkup(course, lessonJourney)}
          <nav class="card course-roadmap" aria-label="Содержание курса">
            <div><p class="eyebrow">Содержание</p><strong>Открывайте по одному уроку</strong></div>
            <ol>
              ${course.lessons.map((lesson, index) => `${lesson.groupStart ? `<li class="course-roadmap-group"><span>${escapeHtml(lesson.groupTitle)}</span></li>` : ""}<li data-course-roadmap-lesson="${index}" class="${lessonJourney.understood.includes(index) ? "is-understood" : ""} ${lesson.trackRecommended ? "is-track-recommended" : "is-track-reference"}"><button type="button" data-action="training-lesson-open" data-lesson-index="${index}" aria-current="${lessonJourney.activeIndex === index ? "step" : "false"}"><span>${lessonJourney.understood.includes(index) ? "✓" : index + 1}</span>${escapeHtml(lesson.title)}</button></li>`).join("")}
              <li><button type="button" data-action="scroll-to" data-target="course-check"><span>✓</span>Рабочая аттестация</button></li>
            </ol>
          </nav>
          <div class="lesson-stack">
            ${course.lessons.map((lesson, index) => `${lesson.groupStart ? `<header class="lesson-group-heading"><span>${String(course.lessonGroups.findIndex((group) => group.id === lesson.groupId) + 1).padStart(2, "0")}</span><div><p class="eyebrow">Этап маршрута</p><h2>${escapeHtml(lesson.groupTitle)}</h2></div></header>` : ""}${lessonMarkup(lesson, index, course.lessons, lessonJourney)}`).join("")}
          </div>
          ${courseVisualExamplesMarkup(course.code)}
          <div data-training-media-cards-host data-module-code="${escapeHtml(course.code)}" aria-live="polite"></div>
          ${trainingInteractiveMarkup(course.code, course.interactiveWalkthroughs)}
          ${course.code === "publishing_funnel" ? trainingPlatformSimulatorsMarkup() : ""}
          ${courseGlossaryMarkup(course.glossary)}
          ${courseKnowledgeCheckMarkup(course, checkPassed)}
        </div>
        <aside class="card sticky-card course-completion-card">
          <div class="completion-ring" style="--completion:${complete ? 100 : 0}" aria-hidden="true"><span>${complete ? "✓" : course.lessons.length}</span></div>
          <p class="eyebrow">Завершение курса</p>
          <h2>Проверьте себя</h2>
          <div class="course-achievement-preview"><span aria-hidden="true">${escapeHtml(course.achievement.icon || courseAchievement(course.code).icon)}</span><div><small>Ачивка после подтверждения</small><strong>${escapeHtml(course.achievement.name || course.achievement.title || courseAchievement(course.code).name)}</strong></div></div>
          <p class="muted tiny">Сначала пройдите рабочую аттестацию блока, затем подтвердите чек-лист. Завершение сохранится в рабочем профиле.</p>
          ${complete ? alertMarkup("Курс уже пройден. Материал можно повторять без ограничений.", "success") : `
            <div class="course-check-gate ${checkPassed ? "passed" : ""}" data-course-check-gate>
              <span aria-hidden="true">${checkPassed ? "✓" : "?"}</span>
              <strong>${checkPassed ? "Аттестация пройдена" : "Сначала пройдите аттестацию ниже"}</strong>
            </div>
            <div class="completion-checklist">
              ${completionChecklist.map((item, index) => `
                <label class="acknowledgement">
                  <input id="course-ack-${index + 1}" type="checkbox" data-course-ack />
                  <span>${escapeHtml(item)}</span>
                </label>
              `).join("")}
            </div>
            <button class="btn btn-block" type="button" data-action="complete-course" data-module-code="${escapeHtml(course.code)}" disabled>Завершить блок</button>
            <p class="course-completion-reason" data-course-completion-reason role="status">Сначала завершите маршрут, лабораторию и рабочую аттестацию.</p>
          `}
          <a class="btn btn-secondary btn-block course-back-link" href="#/learn">К списку курсов</a>
        </aside>
      </div>
    </div>
  `;
  app.innerHTML = learningScaffold(content, `/learn/${course.code}`);
  if (checkPassed) clearCourseAssessmentDraft(course.code);
  else restoreCourseAssessmentDraft(course.code);
  syncCourseLessonJourney(course, lessonJourney);
  restoreTrainingWalkthroughState(course.code);
  restoreTrainingAudience(course.code);
  bindCoursePlatformSimulators(course);
  void hydrateTrainingMediaCards(course.code);
  syncCourseMasteryPanel(course);
  void restoreServerTrainingWalkthroughState(course.code);
  track("course_opened", { module_code: course.code });
}

function courseAssessmentDraftKey(courseCode, userId = state.user?.id) {
  const safeUser = String(userId || "").replace(/[^a-zA-Z0-9_-]/g, "");
  const safeCourse = String(courseCode || "").replace(/[^a-z0-9_-]/g, "");
  return safeUser && safeCourse
    ? `contentengine.course-assessment-draft.v1:${safeUser}:${safeCourse}`
    : "";
}

function persistCourseAssessmentDraft(form) {
  const courseCode = String(form?.dataset?.courseCode || "");
  const key = courseAssessmentDraftKey(courseCode);
  if (!key || !form) return;
  const answers = {};
  form.querySelectorAll("[data-check-question]").forEach((question) => {
    const questionId = String(question.dataset.checkQuestion || "");
    if (!questionId) return;
    answers[questionId] = Array.from(question.querySelectorAll("input:checked"))
      .map((input) => String(input.value || ""))
      .filter(Boolean)
      .slice(0, 8);
  });
  const rationales = {};
  form.querySelectorAll(".knowledge-rationale textarea").forEach((textarea) => {
    const name = String(textarea.name || "");
    if (name) rationales[name] = String(textarea.value || "").slice(0, 900);
  });
  try {
    window.localStorage.setItem(key, JSON.stringify({
      version: 1,
      courseCode,
      updatedAt: Date.now(),
      answers,
      rationales,
    }));
  } catch {
    // Draft persistence is a convenience; assessment submission stays usable.
  }
}

function restoreCourseAssessmentDraft(courseCode) {
  const key = courseAssessmentDraftKey(courseCode);
  const form = document.querySelector(`#course-check-form[data-course-code="${CSS.escape(courseCode)}"]`);
  if (!key || !form) return false;
  try {
    const draft = JSON.parse(window.localStorage.getItem(key) || "null");
    if (
      !draft
      || draft.version !== 1
      || draft.courseCode !== courseCode
      || Date.now() - Number(draft.updatedAt || 0) > 7 * 24 * 60 * 60 * 1000
    ) {
      window.localStorage.removeItem(key);
      return false;
    }
    Object.entries(draft.answers || {}).forEach(([questionId, values]) => {
      const selected = new Set(Array.isArray(values) ? values.map(String) : []);
      form.querySelectorAll(
        `[data-check-question="${CSS.escape(questionId)}"] input`,
      ).forEach((input) => { input.checked = selected.has(String(input.value || "")); });
    });
    Object.entries(draft.rationales || {}).forEach(([name, value]) => {
      const textarea = form.elements.namedItem(name);
      if (!textarea || String(textarea.tagName || "").toUpperCase() !== "TEXTAREA") return;
      textarea.value = String(value || "").slice(0, 900);
      const counter = textarea.closest(".knowledge-rationale")?.querySelector("[data-rationale-count]");
      if (counter) counter.textContent = String(textarea.value.length);
    });
    const result = form.querySelector("#course-check-result");
    if (result && Object.keys(draft.rationales || {}).length) {
      result.textContent = "Черновик ответов восстановлен на этом устройстве.";
    }
    return true;
  } catch {
    window.localStorage.removeItem(key);
    return false;
  }
}

function clearCourseAssessmentDraft(courseCode) {
  const key = courseAssessmentDraftKey(courseCode);
  if (!key) return;
  try { window.localStorage.removeItem(key); } catch { /* no-op */ }
}

function trainingWalkthroughRoot(control) {
  return control?.closest?.("[data-training-walkthrough]") || null;
}

function trainingWalkthroughStateKey(root) {
  return trainingWalkthroughStorageKey(
    state.user?.id,
    root?.dataset?.trainingCourse,
    root?.dataset?.trainingWalkthrough,
  );
}

function persistTrainingWalkthroughState(root, { syncServer = true } = {}) {
  const key = trainingWalkthroughStateKey(root);
  if (!key || !root) return;
  const payload = {
    step: Math.max(0, Number(root.dataset.trainingStep) || 0),
    checks: Array.from(root.querySelectorAll("[data-training-check]")).map((input) => input.checked === true),
    checkIds: Array.from(root.querySelectorAll("[data-training-check]:checked"))
      .map((input) => String(input.dataset.trainingCheck || ""))
      .filter(Boolean),
    mode: String(root.dataset.trainingMode || "watch"),
    practiceOption: String(root.querySelector("[data-training-practice-option]:checked")?.value || ""),
  };
  try {
    window.localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // Session storage and server synchronization remain available.
  }
  try {
    window.sessionStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // Server synchronization below remains the durable path.
  }
  if (syncServer) scheduleServerTrainingWalkthroughProgress(root);
  syncCourseMasteryPanel();
}

function renderTrainingPracticalProject() {
  const project = state.bootstrap.training.practicalProject;
  const upload = state.bootstrap.training.practicalUpload || {};
  const coursesComplete = prerequisitesComplete();
  const managerReviewQueue = canManageTeam()
    ? trainingPracticalReviewQueueMarkup(state.bootstrap?.training?.practicalReviews || [])
    : "";
  const content = `
    <div class="page-wrap learning-page training-practical-page">
      <header class="card course-hero course-tone-4">
        <div class="course-hero-copy">
          <p class="eyebrow"><a href="#/learn">Академия</a> · Практический допуск</p>
          <h1>Один ролик, который нельзя зачесть кликами</h1>
          <p>Для финального допуска загрузите пробную вертикальную работу MP4. Безопасную HTTPS-ссылку можно отправить только для предварительного разбора и возврата замечаний.</p>
        </div>
        <div class="course-hero-outcome"><span class="course-hero-icon" aria-hidden="true">05</span><p>Критерий</p><h2>Точный товар, чистый кадр, безопасный текст и воспроизводимый результат</h2></div>
      </header>
      ${managerReviewQueue}
      ${coursesComplete
        ? trainingPracticalProjectMarkup(project, { maxUploadBytes: upload.maxUploadBytes })
        : `<section class="card result-banner"><div class="result-score">4/4</div><h2>Сначала завершите четыре курса</h2><p class="muted">Пробная работа откроется после серверного зачёта всех блоков.</p><a class="btn" href="#/learn">Вернуться к курсам</a></section>`}
      ${coursesComplete && practicalProjectApproved()
        ? `<section class="card training-practical-next"><div><p class="eyebrow">Следующий этап</p><h2>Практика принята — переходите к итоговым ситуациям</h2></div><a class="btn" href="#/learn/exam">Открыть экзамен <span aria-hidden="true">→</span></a></section>`
        : ""}
    </div>
  `;
  app.innerHTML = learningScaffold(content, "/learn/practical");
  const form = document.querySelector("#training-practical-submit-form");
  if (form) syncTrainingPracticalSource(form);
}

function trainingPracticalUploadSettings() {
  const source = state.bootstrap?.training?.practicalUpload || {};
  return {
    bucketId: String(source.bucketId || "").trim(),
    pathPrefix: String(source.pathPrefix || "").trim(),
    maxUploadBytes: Math.max(1, Number(source.maxUploadBytes) || 52_428_800),
    acceptedMimeTypes: new Set(
      (Array.isArray(source.acceptedMimeTypes) ? source.acceptedMimeTypes : ["video/mp4"])
        .map((value) => String(value || "").trim().toLowerCase())
        .filter(Boolean),
    ),
  };
}

async function submitTrainingPracticalProject(form) {
  const submission = readTrainingPracticalSubmission(form);
  if (!submission.valid) {
    toast(submission.errors[0] || "Проверьте пробную работу перед отправкой.", "error");
    return;
  }

  const settings = trainingPracticalUploadSettings();
  const file = submission.file;
  let uploadedObjectKey = "";
  let projectCommitted = false;
  if (file) {
    if (!settings.bucketId || !settings.pathPrefix) {
      toast("Защищённая папка для пробной работы ещё не подготовлена. Обновите страницу или обратитесь к руководителю.", "error");
      return;
    }
    if (file.size > settings.maxUploadBytes) {
      toast(`Файл превышает лимит ${Math.max(1, Math.round(settings.maxUploadBytes / 1_048_576))} МБ.`, "error");
      return;
    }
    if (!settings.acceptedMimeTypes.has(String(file.type || "").toLowerCase())) {
      toast("Для пробной работы нужен MP4-файл.", "error");
      return;
    }
  }

  setFormBusy(form, true, file ? "Загружаем и отправляем…" : "Отправляем…");
  try {
    const payload = {
      ...submission.payload,
      action: "submit",
      evidence_kind: file ? "private_file" : "https_url",
    };
    if (file) {
      uploadedObjectKey = `${settings.pathPrefix}${crypto.randomUUID()}.mp4`;
      await state.api.uploadTrainingPracticalObject(
        settings.bucketId,
        settings.pathPrefix,
        uploadedObjectKey,
        file,
      );
      payload.object_key = uploadedObjectKey;
      payload.file_metadata = { file_name: file.name };
      delete payload.evidence_url;
    }

    await state.api.savePracticalProject(payload);
    projectCommitted = true;
    await track("training_practical_project_submitted", {
      platform: payload.platform,
      evidence_kind: payload.evidence_kind,
    });
    await loadBootstrap();
    render();
    toast("Пробная работа передана руководителю. Решение появится в этом разделе.", "success");
  } catch (error) {
    if (uploadedObjectKey && !projectCommitted && error?.name === "CreatorApiError") {
      await state.api.removeTrainingPracticalObject(
        settings.bucketId,
        settings.pathPrefix,
        uploadedObjectKey,
      ).catch(() => {});
    }
    toast(actionErrorMessage(error), "error");
  } finally {
    if (form.isConnected) setFormBusy(form, false);
  }
}

async function submitTrainingPracticalDecision(form, submitter) {
  const decision = readTrainingPracticalDecision(form, submitter);
  if (!decision.valid) {
    toast(decision.errors[0] || "Проверьте решение по пробной работе.", "error");
    return;
  }
  setFormBusy(form, true, "Сохраняем решение…");
  try {
    await state.api.decidePracticalProject(decision.payload);
    await track("training_practical_project_decided", {
      project_id: decision.payload.project_id,
      decision: decision.payload.decision,
    });
    await loadBootstrap();
    render();
    toast(
      decision.payload.decision === "approve"
        ? "Пробная работа принята. Участнику открыт итоговый экзамен."
        : "Работа возвращена с комментарием. Участник увидит, что исправить.",
      "success",
    );
  } catch (error) {
    toast(actionErrorMessage(error), "error");
  } finally {
    if (form.isConnected) setFormBusy(form, false);
  }
}

let trainingPracticalReviewRefreshPromise = null;

async function refreshTrainingPracticalReviews({ silent = false, control = null } = {}) {
  if (
    !canManageTeam()
    || !["/learn/practical", "/workspace/team"].includes(state.route.path)
  ) return;
  if (trainingPracticalReviewRefreshPromise) {
    await trainingPracticalReviewRefreshPromise;
    return;
  }
  if (control) {
    control.disabled = true;
    control.setAttribute("aria-busy", "true");
  }
  trainingPracticalReviewRefreshPromise = state.api.bootstrap({
    session_id: state.sessionId,
    refresh_scope: "training_practical_reviews",
  });
  try {
    const raw = await trainingPracticalReviewRefreshPromise;
    const fresh = normalizeBootstrap(raw);
    if (
      fresh.profile?.id !== state.bootstrap?.profile?.id
      || fresh.organization?.id !== state.bootstrap?.organization?.id
    ) throw new Error("training_practical_refresh_context_changed");
    state.api.commitBootstrapContext(raw);
    state.bootstrap = {
      ...state.bootstrap,
      training: {
        ...state.bootstrap.training,
        practicalReviews: fresh.training.practicalReviews,
      },
    };
    const queue = document.querySelector(".training-practical-queue");
    const hasUnsentReviewNote = Array.from(
      queue?.querySelectorAll(".training-practical-review__form textarea") || [],
    ).some((textarea) => String(textarea.value || "").trim());
    if (queue && !hasUnsentReviewNote) {
      const replacement = document.createElement("div");
      replacement.innerHTML = trainingPracticalReviewQueueMarkup(
        state.bootstrap.training.practicalReviews,
      ).trim();
      if (replacement.firstElementChild) queue.replaceWith(replacement.firstElementChild);
    } else if (queue && hasUnsentReviewNote) {
      queue.dataset.refreshPending = "true";
      if (!silent) toast("Очередь получена, но не перерисована: сначала сохраните набранный комментарий.", "info");
      return;
    }
    if (!silent) toast("Очередь пробных работ обновлена.", "success");
  } catch (error) {
    if (!silent) toast(actionErrorMessage(error), "error");
  } finally {
    trainingPracticalReviewRefreshPromise = null;
    if (control?.isConnected) {
      control.disabled = false;
      control.removeAttribute("aria-busy");
    }
  }
}

async function openTrainingPracticalMedia(control) {
  const objectKey = String(control.dataset.objectKey || "").trim();
  const bucketId = String(state.bootstrap?.training?.practicalUpload?.bucketId || "").trim();
  const pendingWindow = openGenerationWaitingWindow();
  const originalLabel = control.textContent;
  control.disabled = true;
  control.textContent = "Готовим защищённую ссылку…";
  try {
    if (!objectKey || !bucketId) throw new Error("Защищённый файл пробной работы не найден.");
    const urls = await state.api.signedTrainingPracticalObjectUrls(bucketId, [objectKey], 600);
    const signedUrl = String(urls.get(objectKey) || "");
    if (!signedUrl) throw new Error("Сервис не выдал ссылку на пробную работу.");
    openGenerationOutput(signedUrl, pendingWindow);
    toast("Пробная работа открыта по временной защищённой ссылке.", "success");
  } catch (error) {
    pendingWindow?.close();
    toast(actionErrorMessage(error), "error");
  } finally {
    if (control.isConnected) {
      control.disabled = false;
      control.textContent = originalLabel;
    }
  }
}

function platformSimulatorSessionStorageKey() {
  const userId = String(state.user?.id || "anonymous");
  return `contentengine.training-platform-simulators.v1:${userId}`;
}

function restorePlatformSimulatorSession() {
  try {
    const raw = window.localStorage.getItem(platformSimulatorSessionStorageKey());
    const parsed = raw ? JSON.parse(raw) : {};
    const states = parsed?.states && typeof parsed.states === "object"
      ? Object.fromEntries(Object.entries(parsed.states).map(([platformId, platformState]) => [
        platformId,
        {
          ...(platformState && typeof platformState === "object" ? platformState : {}),
          finished: false,
          passed: false,
          complete: false,
          serverResult: null,
        },
      ]))
      : {};
    return { activePlatformId: String(parsed?.activePlatformId || ""), states };
  } catch {
    return {};
  }
}

function bindCoursePlatformSimulators(course) {
  if (course?.code !== "publishing_funnel") return;
  const section = document.querySelector("[data-training-platform-simulators]");
  if (!section) return;
  bindTrainingPlatformSimulators(section, {
    initialState: restorePlatformSimulatorSession(),
    onChange(session, action) {
      try {
        const gradedState = session.states?.[String(action?.platformId || "")];
        if (action?.type === "apply-server-result" && gradedState?.passed) {
          window.localStorage.removeItem(platformSimulatorSessionStorageKey());
        } else {
          window.localStorage.setItem(platformSimulatorSessionStorageKey(), JSON.stringify(session));
        }
      } catch {
        // Server progress remains authoritative for completed simulator routes.
      }
      syncCourseMasteryPanel(course);
    },
    async onSubmitAttempt(payload) {
      const raw = await state.api.submitPlatformSimulator({
        platformId: payload.platformId,
        assessmentVersion: payload.assessmentVersion,
        decisions: payload.decisions,
        rationales: payload.rationales,
      });
      const attempt = raw?.attempt || raw?.result?.attempt || raw?.data?.attempt || {};
      const passed = attempt.passed === true;
      const rawProgress = raw?.progress || raw?.result?.progress || raw?.data?.progress || null;
      if (passed && rawProgress) {
        const [progress] = normalizeServerTrainingProgress({ items: [rawProgress] });
        if (progress) {
          const key = trainingProgressKey(progress.moduleCode, progress.walkthroughId);
          const current = state.trainingProgress.items.get(key);
          if (!current || progress.version >= current.version) {
            state.trainingProgress.items.set(key, progress);
            state.trainingProgress.loadedModules.add(progress.moduleCode);
            applyServerTrainingProgress(progress);
          }
        }
      }
      track("training_platform_simulator_graded", {
        platform: payload.platformId,
        passed,
        server_graded: true,
      });
      toast(
        passed
          ? `Маршрут ${payload.platformId} подтверждён сервером.`
          : "Попытка не зачтена. Повторите материал и через минуту пройдите все шесть решений заново.",
        passed ? "success" : "error",
      );
      return raw;
    },
  });
}

async function trainingMediaCatalog() {
  if (!trainingMediaCatalogPromise) {
    trainingMediaCatalogPromise = fetch("./assets/training/training-media-catalog.v1.json", {
      credentials: "same-origin",
      cache: "no-cache",
    }).then((response) => {
      if (!response.ok) throw new Error(`training_media_catalog_${response.status}`);
      return response.json();
    }).catch((error) => {
      trainingMediaCatalogPromise = null;
      throw error;
    });
  }
  return trainingMediaCatalogPromise;
}

async function hydrateTrainingMediaCards(courseCode) {
  const host = document.querySelector(
    `[data-training-media-cards-host][data-module-code="${CSS.escape(String(courseCode || ""))}"]`,
  );
  if (!host) return;
  try {
    const catalog = await trainingMediaCatalog();
    if (!host.isConnected || state.route.path !== `/learn/${courseCode}`) return;
    host.innerHTML = trainingMediaCardsMarkup(catalog, { moduleCode: courseCode });
    bindTrainingMediaCards(host);
  } catch (error) {
    console.warn("Training media catalog unavailable", error);
    if (host.isConnected) {
      host.innerHTML = alertMarkup(
        "Примеры «правильно / ошибка» временно не загрузились. Обновите страницу; текст курса и обязательная проверка остаются доступны.",
        "warning",
      );
    }
  }
}

function restoreTrainingWalkthroughState(courseCode) {
  document.querySelectorAll(`[data-training-course="${CSS.escape(courseCode)}"]`).forEach((root) => {
    const key = trainingWalkthroughStateKey(root);
    if (!key) return;
    let saved = null;
    try {
      saved = JSON.parse(window.localStorage.getItem(key) || "null");
    } catch {
      saved = null;
    }
    if (!saved || typeof saved !== "object") {
      try {
        saved = JSON.parse(window.sessionStorage.getItem(key) || "null");
      } catch {
        saved = null;
      }
    }
    try {
      saved = saved && typeof saved === "object" ? saved : {};
      setTrainingWalkthroughStep(root, Math.max(0, Number(saved.step) || 0));
      const checkIds = new Set(Array.isArray(saved.checkIds) ? saved.checkIds.map(String) : []);
      const checks = Array.isArray(saved.checks) ? saved.checks : [];
      root.querySelectorAll("[data-training-check]").forEach((input, index) => {
        input.checked = checkIds.size
          ? checkIds.has(String(input.dataset.trainingCheck || ""))
          : checks[index] === true;
      });
      if (saved.practiceOption) evaluateTrainingPractice(root, String(saved.practiceOption));
      setTrainingWalkthroughMode(root, saved.mode);
      syncTrainingWalkthroughStatus(root);
    } catch {
      setTrainingWalkthroughStep(root, 0);
      setTrainingWalkthroughMode(root, "watch");
      syncTrainingWalkthroughStatus(root);
    }
  });
}

function restoreTrainingAudience(courseCode) {
  const courseRoot = document.querySelector(`[data-training-interactive-course="${CSS.escape(courseCode)}"]`);
  if (!courseRoot) return;
  const course = learningCourses().find((item) => item.code === courseCode);
  const required = new Set(course?.mastery?.requiredWalkthroughIds || []);
  courseRoot.querySelectorAll("[data-training-walkthrough]").forEach((walkthrough) => {
    walkthrough.dataset.trainingMasteryRequired = required.has(
      String(walkthrough.dataset.trainingWalkthrough || ""),
    ) ? "true" : "false";
  });
  setTrainingAudience(courseRoot, restoreLearningTrack());
}

function trainingProgressKey(moduleCode, walkthroughId) {
  return `${String(moduleCode || "").trim()}:${String(walkthroughId || "").trim()}`;
}

function normalizeServerTrainingProgress(raw) {
  const root = raw?.data && typeof raw.data === "object" ? raw.data : raw || {};
  return (Array.isArray(root.items) ? root.items : [])
    .map((item) => ({
      moduleCode: String(item?.module_code || ""),
      walkthroughId: String(item?.walkthrough_id || ""),
      currentFrameId: String(item?.current_frame_id || ""),
      positionSeconds: Math.max(0, Number(item?.position_seconds) || 0),
      completedFrameIds: Array.isArray(item?.completed_frame_ids)
        ? [...new Set(item.completed_frame_ids.map(String).filter(Boolean))]
        : [],
      completed: item?.completed === true,
      updatedAt: String(item?.updated_at || ""),
      version: Math.max(1, Number(item?.version) || 1),
    }))
    .filter((item) => item.moduleCode && item.walkthroughId);
}

async function restoreServerTrainingWalkthroughState(courseCode) {
  const moduleCode = String(courseCode || "").trim();
  if (
    !moduleCode
    || !state.api
    || state.trainingProgress.loadedModules.has(moduleCode)
    || state.trainingProgress.loadRequests.has(moduleCode)
  ) return;
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const request = state.api.trainingProgress(moduleCode);
  state.trainingProgress.loadRequests.set(moduleCode, request);
  try {
    const raw = await request;
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id) return;
    for (const progress of normalizeServerTrainingProgress(raw)) {
      const key = trainingProgressKey(progress.moduleCode, progress.walkthroughId);
      const current = state.trainingProgress.items.get(key);
      let effectiveProgress = current;
      if (!current || progress.version >= current.version) {
        state.trainingProgress.items.set(key, progress);
        effectiveProgress = progress;
      }
      const queue = state.trainingProgress.saveQueues.get(key);
      if (effectiveProgress && !queue?.inFlight && !queue?.latestPayload) {
        applyServerTrainingProgress(effectiveProgress);
      }
    }
    state.trainingProgress.loadedModules.add(moduleCode);
  } catch (error) {
    console.warn("Training walkthrough progress unavailable", error);
  } finally {
    if (state.trainingProgress.loadRequests.get(moduleCode) === request) {
      state.trainingProgress.loadRequests.delete(moduleCode);
    }
  }
}

function applyServerTrainingProgress(progress) {
  if (state.route.path !== `/learn/${progress.moduleCode}`) return;
  const root = document.querySelector(
    `[data-training-course="${CSS.escape(progress.moduleCode)}"]`
    + `[data-training-walkthrough="${CSS.escape(progress.walkthroughId)}"]`,
  );
  if (!root) return;
  const frames = Array.from(root.querySelectorAll("[data-training-frame]"));
  const currentIndex = frames.findIndex(
    (frame) => frame.dataset.trainingFrameId === progress.currentFrameId,
  );
  const completedIndex = frames.reduce(
    (latest, frame, index) => (
      progress.completedFrameIds.includes(frame.dataset.trainingFrameId)
        ? Math.max(latest, index)
        : latest
    ),
    -1,
  );
  const localIndex = Math.max(0, Number(root.dataset.trainingStep) || 0);
  const serverIndex = currentIndex >= 0 ? currentIndex : Math.max(0, completedIndex);
  setTrainingWalkthroughStep(
    root,
    progress.completed === true
      ? Math.max(0, frames.length - 1)
      : Math.max(localIndex, serverIndex),
  );
  root.dataset.trainingProgressVersion = String(progress.version);
  if (progress.completed === true) {
    root.dataset.trainingServerComplete = "true";
    root.querySelectorAll("[data-training-check]").forEach((input) => {
      input.checked = true;
    });
    root.dataset.trainingPracticeComplete = "true";
    const practice = root.querySelector("[data-training-practice]");
    if (practice) {
      practice.dataset.trainingPracticeComplete = "true";
      practice.setAttribute("aria-invalid", "false");
      const feedback = practice.querySelector("[data-training-practice-feedback]");
      if (feedback) {
        feedback.textContent = "Эта практика уже была завершена и восстановлена из рабочего профиля.";
        feedback.dataset.trainingFeedbackStatus = "success";
      }
    }
    syncTrainingWalkthroughStatus(root);
    if (DEDICATED_PLATFORM_WALKTHROUGH_IDS.has(progress.walkthroughId)) {
      syncPlatformSimulatorWalkthroughDOM(root, {
        platformId: progress.walkthroughId.replace("platform_publish_", ""),
      });
    }
  }
  const video = root.querySelector("[data-training-video]");
  if (video && progress.positionSeconds > 0) {
    const restorePosition = () => {
      const duration = Number(video.duration);
      const serverPosition = Number.isFinite(duration)
        ? Math.min(duration, progress.positionSeconds)
        : progress.positionSeconds;
      video.currentTime = Math.max(Number(video.currentTime) || 0, serverPosition);
    };
    if (video.readyState >= 1) restorePosition();
    else video.addEventListener("loadedmetadata", restorePosition, { once: true });
  }
  syncCourseMasteryPanel();
}

function serverTrainingProgressPayload(root) {
  if (!root) return null;
  const moduleCode = String(root.dataset.trainingCourse || "");
  const walkthroughId = String(root.dataset.trainingWalkthrough || "");
  if (DEDICATED_PLATFORM_WALKTHROUGH_IDS.has(walkthroughId)) return null;
  const frames = Array.from(root.querySelectorAll("[data-training-frame]"));
  const currentIndex = Math.max(
    0,
    Math.min(frames.length - 1, Number(root.dataset.trainingStep) || 0),
  );
  const currentFrameId = String(frames[currentIndex]?.dataset.trainingFrameId || "");
  if (!moduleCode || !walkthroughId || !currentFrameId || !frames.length) return null;
  const completedFrameIds = frames
    .slice(0, currentIndex + 1)
    .map((frame) => String(frame.dataset.trainingFrameId || ""))
    .filter(Boolean);
  const completed = syncTrainingWalkthroughStatus(root).complete;
  const video = root.querySelector("[data-training-video]");
  const durationSeconds = Math.max(1, Number(root.dataset.trainingDurationSeconds) || 1);
  const positionSeconds = Number.isFinite(Number(video?.currentTime)) && Number(video?.currentTime) > 0
    ? Number(video.currentTime.toFixed(3))
    : Number(Math.min(
      durationSeconds,
      durationSeconds * ((currentIndex + 1) / frames.length),
    ).toFixed(3));
  return {
    module_code: moduleCode,
    walkthrough_id: walkthroughId,
    current_frame_id: currentFrameId,
    position_seconds: positionSeconds,
    completed_frame_ids: completedFrameIds,
    completed,
  };
}

function mergeTrainingProgressPayload(previous, next) {
  if (!previous) return {
    ...next,
    completed_frame_ids: [...new Set(next.completed_frame_ids || [])],
  };
  if (!next) return previous;
  return {
    ...previous,
    ...next,
    current_frame_id: next.current_frame_id || previous.current_frame_id,
    position_seconds: Math.max(
      Number(previous.position_seconds) || 0,
      Number(next.position_seconds) || 0,
    ),
    completed_frame_ids: [...new Set([
      ...(previous.completed_frame_ids || []),
      ...(next.completed_frame_ids || []),
    ])],
    completed: previous.completed === true || next.completed === true,
  };
}

function trainingProgressQueueIsCurrent(queue) {
  return Boolean(
    queue
    && state.api
    && state.session
    && state.trainingProgress.saveQueues.get(queue.key) === queue
    && queue.requestEpoch === state.dataEpoch
    && queue.requestUserId === state.user?.id
  );
}

function scheduleTrainingProgressQueueDrain(key, delayMs = 0) {
  const previousTimer = state.trainingProgress.saveTimers.get(key);
  if (previousTimer) window.clearTimeout(previousTimer);
  const timer = window.setTimeout(() => {
    state.trainingProgress.saveTimers.delete(key);
    void drainTrainingProgressSaveQueue(key);
  }, Math.max(0, Number(delayMs) || 0));
  state.trainingProgress.saveTimers.set(key, timer);
}

async function refreshTrainingProgressVersion(queue) {
  const raw = await state.api.trainingProgress(queue.moduleCode);
  if (!trainingProgressQueueIsCurrent(queue)) return false;
  let targetFound = false;
  for (const progress of normalizeServerTrainingProgress(raw)) {
    const key = trainingProgressKey(progress.moduleCode, progress.walkthroughId);
    const current = state.trainingProgress.items.get(key);
    if (!current || progress.version >= current.version) {
      state.trainingProgress.items.set(key, progress);
    }
    if (key === queue.key) targetFound = true;
  }
  if (!targetFound) state.trainingProgress.items.delete(queue.key);
  state.trainingProgress.loadedModules.add(queue.moduleCode);
  return true;
}

async function drainTrainingProgressSaveQueue(key) {
  const queue = state.trainingProgress.saveQueues.get(key);
  if (!trainingProgressQueueIsCurrent(queue) || queue.inFlight || !queue.latestPayload) return;
  queue.inFlight = true;
  let payload = queue.latestPayload;
  queue.latestPayload = null;
  let retryDelay = null;
  let conflictRetries = 0;
  try {
    while (trainingProgressQueueIsCurrent(queue)) {
      if (queue.latestPayload) {
        payload = mergeTrainingProgressPayload(payload, queue.latestPayload);
        queue.latestPayload = null;
      }
      const current = state.trainingProgress.items.get(key);
      const requestPayload = { ...payload };
      if (current?.version) requestPayload.expected_version = current.version;
      else delete requestPayload.expected_version;
      try {
        const raw = await state.api.saveTrainingProgress(requestPayload);
        if (!trainingProgressQueueIsCurrent(queue)) return;
        const source = raw?.data && typeof raw.data === "object" ? raw.data : raw || {};
        const savedItems = normalizeServerTrainingProgress({
          items: source.progress ? [source.progress] : [],
        });
        const saved = savedItems[0];
        if (!saved) {
          throw new Error("training_progress_response_invalid");
        }
        const previous = state.trainingProgress.items.get(key);
        if (!previous || saved.version >= previous.version) {
          state.trainingProgress.items.set(key, saved);
          if (queue.root?.isConnected) {
            queue.root.dataset.trainingProgressVersion = String(saved.version);
          }
        }
        queue.failureCount = 0;
        break;
      } catch (error) {
        if (
          String(error?.serverCode || error?.code || "") !==
            "training_progress_version_conflict"
        ) {
          queue.latestPayload = mergeTrainingProgressPayload(payload, queue.latestPayload);
          queue.failureCount = Math.min(5, (queue.failureCount || 0) + 1);
          retryDelay = Math.min(30_000, 1_500 * (2 ** (queue.failureCount - 1)));
          console.warn("Training walkthrough progress was not synchronized", error);
          break;
        }
        conflictRetries += 1;
        let refreshed = false;
        try {
          refreshed = await refreshTrainingProgressVersion(queue);
        } catch (refreshError) {
          queue.latestPayload = mergeTrainingProgressPayload(payload, queue.latestPayload);
          queue.failureCount = Math.min(5, (queue.failureCount || 0) + 1);
          retryDelay = Math.min(30_000, 1_500 * (2 ** (queue.failureCount - 1)));
          console.warn("Training walkthrough progress version refresh failed", refreshError);
          break;
        }
        if (!refreshed || !trainingProgressQueueIsCurrent(queue)) return;
        payload = mergeTrainingProgressPayload(payload, queue.latestPayload);
        queue.latestPayload = null;
        if (conflictRetries >= 2) {
          queue.latestPayload = mergeTrainingProgressPayload(payload, queue.latestPayload);
          retryDelay = 1_500;
          break;
        }
      }
    }
  } finally {
    queue.inFlight = false;
    if (!trainingProgressQueueIsCurrent(queue)) return;
    if (queue.latestPayload) {
      if (retryDelay !== null) scheduleTrainingProgressQueueDrain(key, retryDelay);
      else window.queueMicrotask(() => void drainTrainingProgressSaveQueue(key));
    } else {
      queue.failureCount = 0;
      state.trainingProgress.saveQueues.delete(key);
    }
  }
}

function scheduleServerTrainingWalkthroughProgress(root, delayMs = 650) {
  const payload = serverTrainingProgressPayload(root);
  if (!payload || !state.api || !state.session) return;
  const key = trainingProgressKey(payload.module_code, payload.walkthrough_id);
  let queue = state.trainingProgress.saveQueues.get(key);
  if (!trainingProgressQueueIsCurrent(queue)) {
    queue = {
      key,
      moduleCode: payload.module_code,
      walkthroughId: payload.walkthrough_id,
      requestEpoch: state.dataEpoch,
      requestUserId: state.user?.id,
      latestPayload: null,
      inFlight: false,
      failureCount: 0,
      root,
    };
    state.trainingProgress.saveQueues.set(key, queue);
  }
  queue.root = root;
  queue.latestPayload = mergeTrainingProgressPayload(queue.latestPayload, payload);
  if (!queue.inFlight) scheduleTrainingProgressQueueDrain(key, delayMs);
}

function waitForCompletedTrainingProgress(key, timeoutMs = 12_000) {
  const deadline = Date.now() + Math.max(1_000, Number(timeoutMs) || 12_000);
  return new Promise((resolve, reject) => {
    const inspect = () => {
      if (state.trainingProgress.items.get(key)?.completed === true) {
        resolve(true);
        return;
      }
      const queue = state.trainingProgress.saveQueues.get(key);
      if (!queue || !trainingProgressQueueIsCurrent(queue) || Date.now() >= deadline) {
        const error = new Error("training_progress_sync_required");
        error.code = "training_progress_sync_required";
        reject(error);
        return;
      }
      window.setTimeout(inspect, 80);
    };
    inspect();
  });
}

async function flushRequiredTrainingProgress(course) {
  const required = new Set(course?.mastery?.requiredWalkthroughIds || []);
  const roots = Array.from(document.querySelectorAll(
    `[data-training-course="${CSS.escape(String(course?.code || ""))}"]`,
  )).filter((root) => required.has(String(root.dataset.trainingWalkthrough || "")));
  const missingDedicatedProgress = roots.some((root) => {
    const walkthroughId = String(root.dataset.trainingWalkthrough || "");
    const key = trainingProgressKey(root.dataset.trainingCourse, walkthroughId);
    return DEDICATED_PLATFORM_WALKTHROUGH_IDS.has(walkthroughId)
      && state.trainingProgress.items.get(key)?.completed !== true;
  });
  if (missingDedicatedProgress) {
    const raw = await state.api.trainingProgress(String(course?.code || ""));
    for (const progress of normalizeServerTrainingProgress(raw)) {
      const key = trainingProgressKey(progress.moduleCode, progress.walkthroughId);
      const current = state.trainingProgress.items.get(key);
      if (!current || progress.version >= current.version) {
        state.trainingProgress.items.set(key, progress);
        applyServerTrainingProgress(progress);
      }
    }
    state.trainingProgress.loadedModules.add(String(course?.code || ""));
  }
  for (const root of roots) {
    const key = trainingProgressKey(root.dataset.trainingCourse, root.dataset.trainingWalkthrough);
    if (DEDICATED_PLATFORM_WALKTHROUGH_IDS.has(String(root.dataset.trainingWalkthrough || ""))) {
      if (state.trainingProgress.items.get(key)?.completed !== true) {
        const error = new Error("platform_simulator_server_grading_required");
        error.code = "platform_simulator_server_grading_required";
        throw error;
      }
      continue;
    }
    persistTrainingWalkthroughState(root);
    await drainTrainingProgressSaveQueue(key);
    await waitForCompletedTrainingProgress(key);
  }
}

function stopTrainingWalkthroughSession(root) {
  const timer = state.trainingWalkthroughTimers.get(root);
  if (timer) window.clearInterval(timer);
  state.trainingWalkthroughTimers.delete(root);
  stopTrainingWalkthrough(root);
  persistTrainingWalkthroughState(root);
}

function stopAllTrainingWalkthroughs() {
  for (const [root, timer] of state.trainingWalkthroughTimers.entries()) {
    window.clearInterval(timer);
    stopTrainingWalkthrough(root);
    persistTrainingWalkthroughState(root);
  }
  state.trainingWalkthroughTimers.clear();
  document.querySelectorAll("[data-training-walkthrough]").forEach((root) => {
    stopTrainingWalkthrough(root);
    persistTrainingWalkthroughState(root);
  });
}

function setTrainingWalkthroughStepAndPersist(root, index) {
  stopTrainingWalkthroughSession(root);
  const next = setTrainingWalkthroughStep(root, index);
  persistTrainingWalkthroughState(root);
  return next;
}

async function toggleTrainingWalkthrough(root) {
  if (!root) return;
  if (root.dataset.trainingPlaying === "true") {
    stopTrainingWalkthroughSession(root);
    return;
  }

  const video = root.querySelector("[data-training-video]");
  if (video) {
    try {
      await video.play();
      root.dataset.trainingPlaying = "true";
      root.querySelector('[data-action="training-walkthrough-play"]')?.setAttribute("aria-pressed", "true");
      video.onpause = () => persistTrainingWalkthroughState(root);
      video.onended = () => stopTrainingWalkthroughSession(root);
    } catch {
      toast("Видео не запустилось. Используйте покадровый разбор и текстовую расшифровку.", "info");
    }
    return;
  }

  root.dataset.trainingPlaying = "true";
  root.querySelector('[data-action="training-walkthrough-play"]')?.setAttribute("aria-pressed", "true");
  const timer = window.setInterval(() => {
    if (!root.isConnected) {
      stopTrainingWalkthroughSession(root);
      return;
    }
    const current = Math.max(0, Number(root.dataset.trainingStep) || 0);
    const total = Math.max(1, Number(root.dataset.trainingStepCount) || 1);
    if (current >= total - 1) {
      stopTrainingWalkthroughSession(root);
      return;
    }
    setTrainingWalkthroughStep(root, current + 1);
    root.dataset.trainingPlaying = "true";
    root.querySelector('[data-action="training-walkthrough-play"]')?.setAttribute("aria-pressed", "true");
    persistTrainingWalkthroughState(root);
  }, TRAINING_WALKTHROUGH_STEP_INTERVAL_MS);
  state.trainingWalkthroughTimers.set(root, timer);
}

function firstShiftStorageKey(userId = state.user?.id) {
  const safeUserId = encodeURIComponent(String(userId || "anonymous"));
  return `${FIRST_SHIFT_STORAGE_PREFIX}:${safeUserId}`;
}

function normalizeFirstShiftState(value, userId) {
  return {
    userId: String(userId || ""),
    ...createFirstShiftFullState(value && typeof value === "object" ? value : {}),
  };
}

function ensureFirstShiftState() {
  const userId = String(state.user?.id || "");
  if (state.firstShift?.userId === userId) return state.firstShift;
  let stored = null;
  try {
    stored = JSON.parse(window.sessionStorage.getItem(firstShiftStorageKey(userId)) || "null");
  } catch {
    stored = null;
  }
  state.firstShift = normalizeFirstShiftState(stored, userId);
  return state.firstShift;
}

function persistFirstShiftState() {
  const practice = ensureFirstShiftState();
  try {
    window.sessionStorage.setItem(firstShiftStorageKey(practice.userId), JSON.stringify(practice));
  } catch {
    // The simulator still works in-memory when browser storage is unavailable.
  }
}

function accountLaunchStorageKey(slug, userId = state.user?.id) {
  const platform = String(slug || "").toLowerCase();
  return userId && ["instagram", "youtube", "vk"].includes(platform)
    ? `contentengine.account-launch.v1.${userId}.${platform}`
    : null;
}

function restoreAccountLaunchChecks(slug) {
  const key = accountLaunchStorageKey(slug);
  if (!key) return [];
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(key) || "[]");
    return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
  } catch {
    window.sessionStorage.removeItem(key);
    return [];
  }
}

function persistAccountLaunchChecks(slug, checks) {
  const key = accountLaunchStorageKey(slug);
  if (!key) return;
  try {
    window.sessionStorage.setItem(key, JSON.stringify([...new Set(checks.map(String).filter(Boolean))]));
  } catch {
    // The checklist is a convenience only and must never block the lesson.
  }
}

function clearAccountLaunchChecks(userId = state.user?.id) {
  if (!userId) return;
  try {
    for (const slug of ["instagram", "youtube", "vk"]) {
      window.sessionStorage.removeItem(accountLaunchStorageKey(slug, userId));
    }
  } catch {
    // Logout must finish even when browser storage is unavailable.
  }
}

function renderFirstShift() {
  const practice = ensureFirstShiftState();
  const content = `
    <div class="page-wrap learning-page first-shift-page first-shift-full-page">
      ${firstShiftSafetyBanner()}
      ${firstShiftFullScenarioMarkup(practice)}
      <div class="first-shift-footer-actions">
        <a class="btn btn-secondary" href="#/learn">Вернуться к курсам</a>
        <p class="muted">Результат хранится только в этой вкладке и не заменяет курсы или итоговый экзамен.</p>
      </div>
    </div>
  `;
  app.innerHTML = learningScaffold(content, "/learn/first-shift");
}

function firstShiftSafetyBanner() {
  return `
    <div class="first-shift-safety" role="status">
      <span aria-hidden="true">◎</span>
      <div><strong>Учебный режим · списаний нет</strong><small>Нет API-вызовов, реальной генерации, публикаций, начислений или влияния на допуск.</small></div>
    </div>
  `;
}


function courseVisualExamplesMarkup(courseCode) {
  const safeCode = String(courseCode || "").replace(/[^a-z0-9_-]/g, "");
  const guide = COURSE_VISUAL_EXAMPLES[safeCode];
  if (!guide || !Array.isArray(guide.examples) || !guide.examples.length) return "";
  const safeThemes = new Set(["portal", "shooting", "social", "payout"]);
  const theme = safeThemes.has(guide.theme) ? guide.theme : "portal";
  const headingId = `course-examples-${safeCode}`;
  return `
    <section class="card course-example-gallery course-example-theme-${theme}" aria-labelledby="${escapeHtml(headingId)}">
      <header class="course-example-gallery-head">
        <div>
          <p class="eyebrow">${escapeHtml(guide.kicker || "Визуальные примеры")}</p>
          <h2 id="${escapeHtml(headingId)}">${escapeHtml(guide.title || "Посмотрите, как выглядит готовый шаг")}</h2>
        </div>
        <p>${escapeHtml(guide.summary || "Сверьте свой экран с примером и повторите действие.")}</p>
      </header>
      <div class="course-example-grid">
        ${guide.examples.map((example, index) => courseExampleCardMarkup(example, index)).join("")}
      </div>
      <footer class="course-example-gallery-note">
        <span aria-hidden="true">↗</span>
        <p><strong>Как пользоваться:</strong> откройте нужный экран в телефоне или портале, положите эту схему рядом и повторяйте шаги по порядку.</p>
      </footer>
    </section>
  `;
}

function courseExampleCardMarkup(example, index) {
  const step = example?.step || `Пример ${index + 1}`;
  const eyebrow = example?.eyebrow || "Пошаговый пример";
  const title = example?.title || "Повторите действие";
  const caption = example?.caption || "Сверьте значения перед продолжением.";
  const result = example?.result || "Шаг завершён";
  const kind = courseExampleKind(example?.kind);
  const anchorLesson = String(example?.anchorLesson || "").replace(/[^a-z0-9_-]/g, "");
  const targetId = anchorLesson ? `lesson-${anchorLesson}` : "";
  return `
    <article class="course-example-card course-example-${kind}">
      <div class="course-example-card-top">
        <span>${escapeHtml(step)}</span>
        <small>${String(index + 1).padStart(2, "0")}</small>
      </div>
      ${courseExampleVisualMarkup(example, kind)}
      <div class="course-example-copy">
        <p class="eyebrow">${escapeHtml(eyebrow)}</p>
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(caption)}</p>
      </div>
      ${targetId ? `<button class="course-example-lesson-link" type="button" data-action="scroll-to" data-target="${escapeHtml(targetId)}">Разобрать подробно в уроке <span aria-hidden="true">↓</span></button>` : ""}
      <div class="course-example-result"><span aria-hidden="true">✓</span><div><small>Должно получиться</small><strong>${escapeHtml(result)}</strong></div></div>
    </article>
  `;
}

function courseExampleKind(value) {
  const kind = String(value || "portal");
  return new Set(["portal", "camera", "storyboard", "compare", "social", "calendar", "decision", "alias", "payout"]).has(kind)
    ? kind
    : "portal";
}

function courseExampleItems(example, limit = 8) {
  return Array.isArray(example?.items) ? example.items.slice(0, limit) : [];
}

function courseExampleVisualMarkup(example, kind = courseExampleKind(example?.kind)) {
  const items = courseExampleItems(example);
  const platform = example?.platform || "Публикация";
  const visualLabel = example?.title || "Визуальный пример";

  if (kind === "camera") {
    return `
      <div class="course-example-visual example-camera" role="img" aria-label="${escapeHtml(visualLabel)}">
        <div class="example-phone-shell">
          <div class="example-phone-notch"></div>
          <div class="example-camera-grid" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
          <div class="example-camera-subject" aria-hidden="true"><span></span><i></i></div>
          <span class="example-camera-format">9:16</span>
          <span class="example-camera-rec">● REC</span>
        </div>
        <div class="example-visual-facts">${items.map((item) => `<span><small>${escapeHtml(item?.label || "Проверка")}</small><strong>${escapeHtml(item?.value || "—")}</strong></span>`).join("")}</div>
      </div>
    `;
  }

  if (kind === "storyboard") {
    return `
      <div class="course-example-visual example-storyboard" aria-label="${escapeHtml(visualLabel)}">
        ${items.map((item, index) => `
          <section>
            <div class="example-story-frame example-story-frame-${index + 1}" aria-hidden="true"><i></i><span>${index + 1}</span></div>
            <small>${escapeHtml(item?.label || `Кадр ${index + 1}`)}</small>
            <strong>${escapeHtml(item?.value || "—")}</strong>
          </section>
        `).join("")}
      </div>
    `;
  }

  if (kind === "compare") {
    return `
      <div class="course-example-visual example-compare" aria-label="${escapeHtml(visualLabel)}">
        ${items.map((item, index) => `
          <section class="${index === 0 ? "example-compare-stop" : "example-compare-go"}">
            <span>${index === 0 ? "!" : "✓"}</span>
            <small>${escapeHtml(item?.label || (index === 0 ? "Стоп" : "Готово"))}</small>
            <strong>${escapeHtml(item?.value || "—")}</strong>
            <div class="example-quality-frame" aria-hidden="true"><i></i><i></i><i></i></div>
          </section>
        `).join("")}
      </div>
    `;
  }

  if (kind === "social") {
    return `
      <div class="course-example-visual example-social" aria-label="${escapeHtml(visualLabel)}">
        <div class="example-phone-shell example-social-phone">
          <div class="example-phone-notch"></div>
          <header><span class="example-social-avatar">A</span><strong>${escapeHtml(platform)}</strong><i aria-hidden="true">•••</i></header>
          <div class="example-social-video" aria-hidden="true"><span></span><i>▶</i></div>
          <div class="example-social-actions" aria-hidden="true"><span>♡</span><span>○</span><span>↗</span></div>
          <ol>${items.map((item) => `<li><span>${escapeHtml(item?.label || "•")}</span><strong>${escapeHtml(item?.value || "—")}</strong></li>`).join("")}</ol>
        </div>
      </div>
    `;
  }

  if (kind === "calendar") {
    return `
      <div class="course-example-visual example-calendar" aria-label="${escapeHtml(visualLabel)}">
        <div class="example-calendar-week">${items.map((item, index) => `<section class="${index === items.length - 1 ? "current" : ""}"><span>${escapeHtml(item?.label || `День ${index + 1}`)}</span><strong>${escapeHtml(item?.value || "—")}</strong><i aria-hidden="true">${index === items.length - 1 ? "→" : "✓"}</i></section>`).join("")}</div>
      </div>
    `;
  }

  if (kind === "decision") {
    const tones = ["stop", "review", "go"];
    return `
      <div class="course-example-visual example-decision" aria-label="${escapeHtml(visualLabel)}">
        ${items.map((item, index) => `<section class="example-decision-${tones[index] || "review"}"><span aria-hidden="true">${index === 0 ? "!" : index === 1 ? "?" : "✓"}</span><div><small>${escapeHtml(item?.label || "Проверка")}</small><strong>${escapeHtml(item?.value || "—")}</strong></div></section>`).join("")}
      </div>
    `;
  }

  if (kind === "alias") {
    const previous = items[0];
    const current = items[1];
    const condition = items[2];
    return `
      <div class="course-example-visual example-alias" aria-label="${escapeHtml(visualLabel)}">
        <div class="example-alias-flow">
          <section><small>${escapeHtml(previous?.label || "Было")}</small><strong>${escapeHtml(previous?.value || "—")}</strong></section>
          <span aria-hidden="true">→</span>
          <section><small>${escapeHtml(current?.label || "Стало")}</small><strong>${escapeHtml(current?.value || "—")}</strong></section>
        </div>
        <div class="example-alias-condition"><span aria-hidden="true">=</span><strong>${escapeHtml(condition?.value || "Тот же товар")}</strong></div>
      </div>
    `;
  }

  if (kind === "payout") {
    return `
      <div class="course-example-visual example-payout" aria-label="${escapeHtml(visualLabel)}">
        <ol>${items.map((item, index) => `<li class="${index === items.length - 1 ? "complete" : ""}"><span>${escapeHtml(item?.label || String(index + 1))}</span><div><strong>${escapeHtml(item?.value || "—")}</strong><small>${index === items.length - 1 ? "Факт перевода" : "Статус в портале"}</small></div></li>`).join("")}</ol>
      </div>
    `;
  }

  return `
    <div class="course-example-visual example-portal" aria-label="${escapeHtml(visualLabel)}">
      <div class="example-portal-window">
        <div class="example-portal-bar"><i></i><i></i><i></i><span>Контент ИИ Завод</span></div>
        <div class="example-portal-body">
          <aside aria-hidden="true"><span></span><span></span><span></span><span></span></aside>
          <div class="example-portal-panel">
            <div class="example-portal-heading" aria-hidden="true"><span></span><i></i></div>
            ${items.map((item) => `<div class="example-portal-row"><small>${escapeHtml(item?.label || "Поле")}</small><strong>${escapeHtml(item?.value || "—")}</strong><span aria-hidden="true">✓</span></div>`).join("")}
            <button type="button" tabindex="-1" aria-hidden="true">Продолжить →</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function lessonAnchorId(lesson, index = 0) {
  const lessonCode = String(lesson?.id || "").replace(/[^a-z0-9_-]/g, "");
  return `lesson-${lessonCode || index + 1}`;
}

function lessonAudienceLabel(lesson) {
  const audiences = Array.isArray(lesson?.audiences) ? lesson.audiences.map(String) : [];
  if (!audiences.length || audiences.includes("all")) return "Всем ролям";
  const labels = { self: "Снимаю сам", ai: "Создаю с ИИ", publish: "Публикую" };
  return audiences.map((audience) => labels[audience]).filter(Boolean).join(" · ") || "Справочный урок";
}

function lessonRouteLabel(lesson) {
  if (restoreLearningTrack() === "all") return "Общий маршрут";
  return lesson?.trackRecommended ? "Ваш маршрут" : "К общей аттестации";
}

function lessonMarkup(lesson, index, lessons, journey = {}) {
  const total = lessons.length;
  const normalized = normalizeLessonJourney(journey, lessons);
  const active = normalized.activeIndex === index;
  const understood = normalized.understood.includes(index);
  const anchorId = lessonAnchorId(lesson, index);
  const titleId = `${anchorId}-title`;
  const detailsId = `${anchorId}-details`;
  return `
    <article id="${escapeHtml(anchorId)}" class="card lesson-card ${active ? "is-active" : ""} ${understood ? "is-understood" : ""} ${lesson.trackRecommended ? "is-track-recommended" : "is-track-reference"}" data-course-lesson data-lesson-id="${escapeHtml(lesson.id)}" data-lesson-index="${index}" data-lesson-state="${understood ? "understood" : active ? "current" : "not-started"}" aria-labelledby="${escapeHtml(titleId)}">
      <div class="lesson-step-rail" aria-hidden="true"><span>${String(index + 1).padStart(2, "0")}</span><i></i>${understood ? "<em>✓</em>" : `<small>${String(total).padStart(2, "0")}</small>`}</div>
      <div class="lesson-content">
        <header class="lesson-heading">
          <div class="lesson-heading__top">
            <div>
              <div class="lesson-kicker"><p class="eyebrow">Практический шаг ${index + 1}</p><span class="lesson-route-badge">${escapeHtml(lessonRouteLabel(lesson))}</span><span>Кому: ${escapeHtml(lessonAudienceLabel(lesson))}</span>${lesson.reviewed_at ? `<span>Проверено ${escapeHtml(formatDate(lesson.reviewed_at))}</span>` : ""}</div>
              <h2 id="${escapeHtml(titleId)}">${escapeHtml(lesson.title)}</h2>
            </div>
            <button class="lesson-toggle" type="button" data-action="training-lesson-toggle" data-lesson-index="${index}" aria-expanded="${active ? "true" : "false"}" aria-controls="${escapeHtml(detailsId)}" aria-label="${active ? "Свернуть" : "Открыть"} урок «${escapeHtml(lesson.title)}»"><span aria-hidden="true">⌄</span></button>
          </div>
          <p class="lesson-heading__summary">${escapeHtml(lesson.body)}</p>
        </header>
        <div id="${escapeHtml(detailsId)}" class="lesson-details" data-course-lesson-details ${active ? "" : "hidden"}>
          ${lesson.takeaway ? `<div class="lesson-takeaway"><span>Главное</span><strong>${escapeHtml(lesson.takeaway)}</strong></div>` : ""}
          ${lessonVisualMarkup(lesson.visual)}
          ${Array.isArray(lesson.bullets) && lesson.bullets.length ? `<ul class="lesson-bullets">${lesson.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
          ${lessonChecklistMarkup(lesson.checklist)}
          ${lessonPracticeMarkup(lesson.practice)}
          ${lesson.callout ? alertMarkup(lesson.callout, "warning") : ""}
          <footer class="lesson-actions">
            <div class="lesson-actions__nav">
              ${index > 0 ? `<button class="btn btn-secondary btn-small" type="button" data-action="training-lesson-open" data-lesson-index="${index - 1}"><span aria-hidden="true">←</span> Предыдущий</button>` : ""}
              ${index < total - 1 ? `<button class="btn btn-secondary btn-small" type="button" data-action="training-lesson-open" data-lesson-index="${index + 1}">Следующий <span aria-hidden="true">→</span></button>` : `<button class="btn btn-secondary btn-small" type="button" data-action="scroll-to" data-target="course-check">К аттестации <span aria-hidden="true">↓</span></button>`}
            </div>
            <button class="btn btn-small lesson-understood" type="button" data-action="training-lesson-understood" data-lesson-index="${index}" aria-pressed="${understood ? "true" : "false"}">${understood ? '<span aria-hidden="true">✓</span> Урок понятен' : index < total - 1 ? 'Понятно — следующий урок <span aria-hidden="true">→</span>' : '<span aria-hidden="true">✓</span> Урок понятен'}</button>
          </footer>
        </div>
      </div>
    </article>
  `;
}

function courseGlossaryMarkup(glossary) {
  if (!Array.isArray(glossary) || !glossary.length) return "";
  return `
    <details class="card course-glossary">
      <summary><span aria-hidden="true">Aa</span><div><p class="eyebrow">Словарь новичка</p><strong>Открыть ${glossary.length} ${glossary.length === 1 ? "термин" : glossary.length < 5 ? "термина" : "терминов"} простыми словами</strong></div></summary>
      <dl>
        ${glossary.map((item) => `<div><dt>${escapeHtml(item.term)}</dt><dd>${escapeHtml(item.definition)}</dd></div>`).join("")}
      </dl>
    </details>
  `;
}

function courseKnowledgeCheckMarkup(course, passed) {
  const check = course.knowledgeCheck;
  if (!check?.questions?.length) return "";
  const questionCount = check.questions.length;
  const questionLabel = questionCount % 10 === 1 && questionCount % 100 !== 11
    ? "вопрос"
    : [2, 3, 4].includes(questionCount % 10) && ![12, 13, 14].includes(questionCount % 100)
      ? "вопроса"
      : "вопросов";
  return `
    <section id="course-check" class="card course-knowledge-check" aria-labelledby="course-check-title" tabindex="-1">
      <div class="knowledge-check-head">
        <div><p class="eyebrow">Рабочая аттестация блока</p><h2 id="course-check-title">${escapeHtml(check.title)}</h2></div>
        <span>${questionCount} ${questionLabel} · нужно ${check.passScore}</span>
      </div>
      <div class="knowledge-check-audience">
        <span>Кому: ${escapeHtml(check.audienceLabel)}</span>
        <p>${escapeHtml(check.roleHint)}</p>
      </div>
      <p class="muted">Это рабочая аттестация, а не опрос на внимательность. Ответ фиксируется вместе с вашим обоснованием; в вопросах «выберите все» засчитывается только точный набор действий. Критически опасное решение проваливает попытку целиком.</p>
      <form id="course-check-form" data-course-code="${escapeHtml(course.code)}" novalidate>
        ${check.questions.map((question, questionIndex) => {
          const inputName = `check_${course.code}_${question.id}`;
          const isMulti = question.type === "multi_select";
          return `
            <fieldset class="knowledge-question" data-check-question="${escapeHtml(question.id)}">
              <legend><span class="knowledge-question-number">${questionIndex + 1}</span><span class="knowledge-question-copy">${escapeHtml(question.prompt)}<small>${isMulti ? "Выберите все необходимые действия — лишний вариант делает ответ неверным." : "Выберите одно лучшее рабочее решение."}</small></span></legend>
              <div class="knowledge-options">
                ${question.options.map((option) => `
                  <label>
                    <input type="${isMulti ? "checkbox" : "radio"}" name="${escapeHtml(inputName)}" value="${escapeHtml(option.value)}" />
                    <span>${escapeHtml(option.label)}</span>
                  </label>
                `).join("")}
              </div>
              ${question.requiresRationale ? `<label class="knowledge-rationale"><span>${escapeHtml(question.rationalePrompt)}</span><textarea name="reason_${escapeHtml(course.code)}_${escapeHtml(question.id)}" minlength="40" maxlength="900" rows="3" required placeholder="Риск: … Проверка: … Действие: …"></textarea><small><span data-rationale-count>0</span>/900 · три части «Риск / Проверка / Действие», минимум 40 знаков, 7 слов и 5 разных содержательных слов</small></label>` : ""}
            </fieldset>
          `;
        }).join("")}
        <div class="knowledge-check-actions">
          <button class="btn" type="submit">Проверить ответы</button>
          <div id="course-check-result" class="knowledge-check-result ${passed ? "passed" : ""}" aria-live="polite">${passed ? "Рабочая аттестация уже пройдена. Можно завершать блок." : ""}</div>
        </div>
      </form>
    </section>
  `;
}

function lessonVisualMarkup(visual) {
  if (!visual || typeof visual !== "object") return "";
  const type = String(visual.type || "");
  const title = visual.title ? `<p class="visual-title">${escapeHtml(visual.title)}</p>` : "";
  const itemsByType = {
    workflow: visual.steps,
    annotated_ui: visual.panels,
    timeline: visual.segments,
    decision: visual.branches,
    metrics: visual.cards,
  };
  const rawItems = Array.isArray(visual.items) ? visual.items : itemsByType[type];
  const items = Array.isArray(rawItems) ? rawItems.slice(0, 8) : [];

  if (type === "workflow" && items.length) {
    return `<figure class="lesson-visual visual-workflow">${title}<ol>${items.map((item, index) => {
      const label = typeof item === "string" ? item : item?.label || item?.title || "";
      const detail = typeof item === "object" ? item?.detail || item?.description || "" : "";
      return `<li><span>${index + 1}</span><div><strong>${escapeHtml(label)}</strong>${detail ? `<small>${escapeHtml(detail)}</small>` : ""}</div></li>`;
    }).join("")}</ol></figure>`;
  }

  if (type === "annotated_ui" && items.length) {
    const windowTitle = visual.window_title || "Контент ИИ Завод";
    return `<figure class="lesson-visual visual-interface">${title}<div class="interface-window"><div class="interface-toolbar"><i></i><i></i><i></i><span>${escapeHtml(windowTitle)}</span></div><div class="interface-body">${items.map((item, index) => {
      const label = item?.area || item?.title || item?.label || item;
      const detail = [item?.label && item?.area ? item.label : "", item?.detail || ""].filter(Boolean).join(" · ");
      return `<div class="interface-field"><span>${index + 1}</span><div><strong>${escapeHtml(label)}</strong>${detail ? `<small>${escapeHtml(detail)}</small>` : ""}</div></div>`;
    }).join("")}</div></div></figure>`;
  }

  if (type === "timeline" && items.length) {
    return `<figure class="lesson-visual visual-timeline">${title}<ol>${items.map((item) => `<li><span>${escapeHtml(item?.time || item?.label || "")}</span><div><strong>${escapeHtml(item?.title || item?.label || item)}</strong>${item?.detail ? `<small>${escapeHtml(item.detail)}</small>` : ""}</div></li>`).join("")}</ol></figure>`;
  }

  if (type === "comparison") {
    const columns = Array.isArray(visual.columns) ? visual.columns.slice(0, 4) : [];
    const stopColumn = columns.find((column) => ["danger", "stop"].includes(column?.tone));
    const goColumn = columns.find((column) => ["success", "go"].includes(column?.tone));
    const left = Array.isArray(visual.left)
      ? visual.left.slice(0, 6)
      : Array.isArray(stopColumn?.items)
        ? stopColumn.items.slice(0, 6)
        : [];
    const right = Array.isArray(visual.right)
      ? visual.right.slice(0, 6)
      : Array.isArray(goColumn?.items)
        ? goColumn.items.slice(0, 6)
        : [];
    if (!left.length && !right.length) return "";
    return `<figure class="lesson-visual visual-comparison">${title}<div class="comparison-grid"><section class="comparison-stop"><span>Стоп</span><h3>${escapeHtml(visual.left_title || stopColumn?.label || "Так нельзя")}</h3><ul>${left.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section><section class="comparison-go"><span>Верно</span><h3>${escapeHtml(visual.right_title || goColumn?.label || "Так правильно")}</h3><ul>${right.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section></div></figure>`;
  }

  if (type === "decision" && items.length) {
    const question = visual.question ? `<p class="decision-question">${escapeHtml(visual.question)}</p>` : "";
    return `<figure class="lesson-visual visual-decision">${title}${question}<div>${items.map((item) => {
      const toneMap = { danger: "stop", warning: "review", success: "go", stop: "stop", review: "review", go: "go" };
      const tone = toneMap[item?.tone] || "review";
      return `<section class="decision-${tone}"><span>${tone === "stop" ? "Стоп" : tone === "go" ? "Можно" : "Проверить"}</span><strong>${escapeHtml(item?.condition || item?.label || "")}</strong><p>${escapeHtml(item?.action || item?.detail || "")}</p></section>`;
    }).join("")}</div></figure>`;
  }

  if (type === "metrics" && items.length) {
    return `<figure class="lesson-visual visual-metrics">${title}<div>${items.map((item) => {
      const value = item?.value || item?.formula || "—";
      const note = item?.note || item?.why || "";
      return `<section><span>${escapeHtml(item?.label || "Метрика")}</span><strong>${escapeHtml(value)}</strong>${note ? `<small>${escapeHtml(note)}</small>` : ""}</section>`;
    }).join("")}</div></figure>`;
  }

  return "";
}

function lessonChecklistMarkup(checklist) {
  if (!checklist || typeof checklist !== "object") return "";
  const doItems = Array.isArray(checklist.do) ? checklist.do.slice(0, 6) : [];
  const dontItems = Array.isArray(checklist.dont) ? checklist.dont.slice(0, 6) : [];
  if (!doItems.length && !dontItems.length) return "";
  return `
    <div class="lesson-checklist">
      ${doItems.length ? `<section><span class="checklist-icon checklist-do">✓</span><div><h3>Сделайте</h3><ul>${doItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div></section>` : ""}
      ${dontItems.length ? `<section><span class="checklist-icon checklist-dont">!</span><div><h3>Остановитесь, если</h3><ul>${dontItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div></section>` : ""}
    </div>
  `;
}

function lessonPracticeMarkup(practice) {
  if (!practice || typeof practice !== "object") return "";
  const steps = Array.isArray(practice.steps) ? practice.steps.slice(0, 6) : [];
  if (!practice.title && !steps.length) return "";
  return `
    <section class="lesson-practice">
      <span class="practice-mark" aria-hidden="true">↗</span>
      <div><p class="eyebrow">${escapeHtml(practice.eyebrow || "Попробуйте в кабинете")}</p><h3>${escapeHtml(practice.title || "Закрепите шаг")}</h3>${steps.length ? `<ol>${steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>` : ""}</div>
    </section>
  `;
}

function renderExam() {
  if (!trainingCatalogReady()) {
    const content = `
      <div class="page-wrap">
        <section class="card result-banner">
          <div class="result-score" aria-hidden="true">!</div>
          <h2>Экзамен временно недоступен</h2>
          <p class="muted">Система не получила полный каталог из четырёх курсов и двенадцати вопросов. Рабочий кабинет остаётся закрыт.</p>
          <button class="btn" type="button" data-action="retry-bootstrap">Проверить ещё раз</button>
        </section>
      </div>
    `;
    app.innerHTML = learningScaffold(content, "/learn/exam");
    return;
  }

  if (!prerequisitesComplete()) {
    const content = `
      <div class="page-wrap">
        <section class="card result-banner">
          <div class="result-score">4/4</div>
          <h2>Сначала завершите четыре курса</h2>
          <p class="muted">Экзамен откроется, когда система подтвердит каждый обязательный модуль.</p>
          <a class="btn" href="#/learn">Вернуться к курсам</a>
        </section>
      </div>
    `;
    app.innerHTML = learningScaffold(content, "/learn/exam");
    return;
  }

  if (!practicalProjectApproved()) {
    const project = normalizeTrainingPracticalProject(state.bootstrap.training.practicalProject);
    const waiting = project.status === "submitted";
    const content = `
      <div class="page-wrap">
        <section class="card result-banner">
          <div class="result-score" aria-hidden="true">05</div>
          <p class="eyebrow">Практический допуск</p>
          <h2>${waiting ? "Пробная работа проверяется руководителем" : "Сначала покажите навык на пробном ролике"}</h2>
          <p class="muted">${waiting
            ? "Экзамен откроется только после человеческого решения. Обновите статус позже — повторная отправка не ускорит проверку."
            : "Одних кликов и правильных ответов недостаточно. Загрузите вертикальный MP4 или HTTPS-ссылку, пройдите самопроверку и получите решение руководителя."}</p>
          <a class="btn" href="#/learn/practical">${waiting ? "Открыть статус проверки" : "Перейти к пробной работе"} <span aria-hidden="true">→</span></a>
        </section>
      </div>
    `;
    app.innerHTML = learningScaffold(content, "/learn/exam");
    return;
  }

  if (state.bootstrap.training.exam.passed) {
    clearFinalExamDraft();
    const score = state.bootstrap.training.exam.score;
    const workspaceReady = hasWorkspaceAccess();
    const content = `
      <div class="page-wrap">
        <section class="card result-banner">
          <div class="result-score">${score ? `${score}%` : "✓"}</div>
          <p class="eyebrow">Итоговый экзамен</p>
          <h2>${workspaceReady ? "Допуск к кабинету получен" : "Экзамен сдан — роль назначает руководитель"}</h2>
          <p class="muted">${workspaceReady
            ? "Все рабочие разделы открыты. Правила качества и прослеживаемости продолжают действовать в каждой задаче."
            : "Руководитель команды должен назначить вам рабочую роль. До назначения кабинет закрыт; учебная смена остаётся дополнительной тренировкой и не заменяет назначение роли."}</p>
          ${workspaceReady
            ? `<a class="btn" href="#/workspace/home">Перейти к работе <span aria-hidden="true">→</span></a>`
            : `<div class="inline-actions" style="justify-content:center">
                <button class="btn" type="button" data-action="retry-bootstrap">Проверить назначение роли <span aria-hidden="true">↻</span></button>
                <a class="btn btn-secondary" href="#/learn/first-shift">Пройти учебную смену</a>
              </div>`}
        </section>
      </div>
    `;
    app.innerHTML = learningScaffold(content, "/learn/exam");
    return;
  }

  const retry = examRetryState();
  if (retry.blocked) {
    const content = `
      <div class="page-wrap">
        <section class="card result-banner">
          <div class="result-score" aria-hidden="true">⏱</div>
          <p class="eyebrow">Итоговый экзамен · за 24 часа: ${state.bootstrap.training.exam.attemptCount24h}/${state.bootstrap.training.exam.attemptLimit24h} · всего: ${state.bootstrap.training.exam.attemptCount}</p>
          <h2>Новая попытка откроется ${escapeHtml(formatDate(retry.nextAttemptAt, true))}</h2>
          <p class="muted">Осталось ${escapeHtml(retry.waitLabel)}. Повторите четыре курса и вернитесь после паузы — рабочий кабинет пока остаётся закрыт.</p>
          ${alertMarkup("Ответы и ключ проверки хранятся на защищённом сервере. Здесь показаны только темы для повторения.", "info")}
          <a class="btn" href="#/learn">Повторить материалы</a>
        </section>
      </div>
    `;
    app.innerHTML = learningScaffold(content, "/learn/exam");
    return;
  }

  if (!examQuestionsReady()) {
    const content = `
      <div class="page-wrap">
        <section class="card result-banner">
          <div class="result-score" aria-hidden="true">!</div>
          <h2>Вопросы экзамена не загрузились</h2>
          <p class="muted">Обновите данные. До получения всех двенадцати сценариев отправка экзамена закрыта.</p>
          <button class="btn" type="button" data-action="retry-bootstrap">Загрузить снова</button>
        </section>
      </div>
    `;
    app.innerHTML = learningScaffold(content, "/learn/exam");
    return;
  }

  const result = state.examResult;
  const questions = finalExamQuestions();
  const content = `
    <div class="page-wrap">
      <header class="page-header">
        <div>
          <p class="eyebrow">Итоговый допуск · ${questions.length} сценариев</p>
          <h1>Как вы поступите в реальной работе?</h1>
          <p>Ответьте на все вопросы и письменно разберите четыре ключевых решения по схеме «Риск / Проверка / Действие». Для прохождения нужно ${finalExamPassScore()} правильных ответов из 12. Проверка выполняется на защищённом сервере.</p>
        </div>
        <span class="badge badge-warning">Попытка за 24 часа ${Math.min(state.bootstrap.training.exam.attemptCount24h + 1, state.bootstrap.training.exam.attemptLimit24h)}/${state.bootstrap.training.exam.attemptLimit24h}</span>
      </header>
      ${result && !result.passed ? examResultMarkup(result) : ""}
      <form id="exam-form" class="exam-form" novalidate>
        ${questions.map((question, index) => questionMarkup(question, index)).join("")}
        <div class="exam-submit">
          <div><strong id="exam-answer-count" aria-live="polite">0 из ${questions.length} отвечено</strong><br /><small id="exam-draft-status" class="muted" aria-live="polite">Незаполненный экзамен не отправится · черновик хранится 7 дней на этом устройстве</small></div>
          <button class="btn" type="submit">Проверить ответы</button>
        </div>
      </form>
    </div>
  `;
  app.innerHTML = learningScaffold(content, "/learn/exam");
  restoreFinalExamDraft();
  track("exam_opened", { question_count: questions.length });
}

function questionMarkup(question, index) {
  const inputType = question.type === "multi_select" ? "checkbox" : "radio";
  return `
    <fieldset class="card question-card" data-exam-question="${escapeHtml(question.code)}">
      <legend><span class="question-number">${index + 1}</span>${escapeHtml(question.text)}</legend>
      <div class="option-list">
        ${question.options.map((option) => `
          <label class="option">
            <input type="${inputType}" name="answer_${escapeHtml(question.code)}" value="${escapeHtml(option.value)}" />
            <span>${escapeHtml(option.label)}</span>
          </label>
        `).join("")}
      </div>
      ${finalExamRequiresRationale(question.code) ? `
        <label class="knowledge-rationale exam-rationale">
          <span>${escapeHtml(FINAL_EXAM_RATIONALE_PROMPTS[question.code])}</span>
          <textarea name="rationale_${escapeHtml(question.code)}" data-exam-rationale="${escapeHtml(question.code)}" minlength="40" maxlength="900" rows="4" required placeholder="Риск: … Проверка: … Действие: …"></textarea>
          <small><span data-rationale-count>0</span>/900 · три разные по смыслу части, минимум 40 знаков, 7 слов и 5 содержательных слов</small>
        </label>
      ` : ""}
    </fieldset>
  `;
}

function examResultMarkup(result) {
  return `
    <section class="card result-banner" style="margin-bottom:18px">
      <div class="result-score" aria-hidden="true">?</div>
      <h2>Пока не хватило одного или нескольких решений</h2>
      <p class="muted">Точный балл и правильные ответы не раскрываются. Повторите рабочий маршрут целиком и попробуйте ещё раз — кабинет пока закрыт.</p>
    </section>
  `;
}

function examRetryState() {
  const raw = state.bootstrap?.training?.exam?.nextAttemptAt;
  if (!raw) return { blocked: false, nextAttemptAt: null, waitLabel: "" };
  const nextAttemptAt = new Date(raw);
  const remainingMs = nextAttemptAt.getTime() - Date.now();
  if (!Number.isFinite(remainingMs) || remainingMs <= 0) {
    return { blocked: false, nextAttemptAt: raw, waitLabel: "" };
  }
  const totalMinutes = Math.max(1, Math.ceil(remainingMs / 60_000));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  const waitLabel = hours
    ? `${hours} ч ${minutes ? `${minutes} мин` : ""}`.trim()
    : `${minutes} мин`;
  return { blocked: true, nextAttemptAt: raw, waitLabel };
}

function learningScaffold(content, activePath) {
  const profile = displayProfile();
  const transitionClass = consumeRouteTransitionClass();
  const rolePending = state.bootstrap?.training?.exam?.passed === true
    && practicalProjectApproved()
    && !hasOperationalWorkspaceRole();
  return `
    <div class="workspace-shell">
      <aside class="sidebar" aria-label="Навигация обучения">
        ${brandMarkup()}
        <nav class="workspace-nav">
          <span class="nav-caption">Допуск к работе</span>
          <a class="nav-link ${activePath === "/learn" ? "active" : ""}" href="#/learn" ${activePath === "/learn" ? 'aria-current="page"' : ""}>
            <span class="nav-icon" aria-hidden="true">◎</span><span>Курсы</span>
          </a>
          <a class="nav-link ${activePath === "/learn/first-shift" ? "active" : ""}" href="#/learn/first-shift" ${activePath === "/learn/first-shift" ? 'aria-current="page"' : ""}>
            <span class="nav-icon" aria-hidden="true">↗</span><span>Первая смена</span>
          </a>
          <a class="nav-link ${activePath.startsWith(ACCOUNT_LAUNCH_PATH) ? "active" : ""}" href="#${ACCOUNT_LAUNCH_PATH}" ${activePath.startsWith(ACCOUNT_LAUNCH_PATH) ? 'aria-current="page"' : ""}>
            <span class="nav-icon" aria-hidden="true">#</span><span>Запуск аккаунтов</span>
          </a>
          <a class="nav-link ${activePath === "/learn/practical" ? "active" : ""}" href="#/learn/practical" ${activePath === "/learn/practical" ? 'aria-current="page"' : ""}>
            <span class="nav-icon" aria-hidden="true">▣</span><span>Пробная работа</span>
          </a>
          <a class="nav-link ${activePath === "/learn/exam" ? "active" : ""}" href="#/learn/exam" ${activePath === "/learn/exam" ? 'aria-current="page"' : ""}>
            <span class="nav-icon" aria-hidden="true">◇</span><span>Итоговый экзамен</span>
          </a>
          ${hasWorkspaceAccess() ? `
            <span class="nav-caption" style="margin-top:15px">Работа</span>
            <a class="nav-link" href="#/workspace/home"><span class="nav-icon" aria-hidden="true">→</span><span>Открыть кабинет</span></a>
          ` : `
            <span class="nav-caption" style="margin-top:15px">Работа</span>
            <span class="nav-link" aria-disabled="true" style="opacity:.58"><span class="nav-icon" aria-hidden="true">⌑</span><span>${rolePending ? "Роль назначает руководитель" : "Закрыто до полного допуска"}</span></span>
          `}
        </nav>
        ${sidebarFooterMarkup(profile)}
      </aside>
      <section class="workspace-main">
        ${brandAtmosphereMarkup()}
        ${mobileTopbarMarkup("Обучение")}
        ${state.mobileNavOpen ? mobileNavMarkup(true, "", activePath) : ""}
        <main id="main-content" class="${transitionClass}" tabindex="-1">${content}</main>
      </section>
    </div>
  `;
}

function renderWorkspaceBoardSection(sectionState) {
  const board = normalizeWorkspaceBoard(sectionState.data || {});
  const markup = workspaceBoardMarkup(board, {
    selectedFolderId: state.workspaceBoard.selectedFolderId,
    selectedItemKey: state.workspaceBoard.selectedItemKey,
    query: state.workspaceBoard.query,
    entityType: state.workspaceBoard.entityType,
    busy: state.workspaceBoard.busy || sectionState.status === "refreshing",
    notice: state.workspaceBoard.notice,
    error: state.workspaceBoard.error,
    visibleItemLimit: state.workspaceBoard.visibleItemLimit,
  });
  const pagination = state.workspaceBoard.hasMore
    ? `
      <div class="workspace-board-pagination">
        <button class="btn btn-secondary" type="button" data-action="load-more-workspace-items" ${state.workspaceBoard.loadingMore ? "disabled" : ""}>
          ${state.workspaceBoard.loadingMore ? "Загружаем…" : "Показать ещё объекты"}
        </button>
        <span class="muted tiny">Объекты загружаются частями по 100 — рабочий стол не зависает при большой медиатеке.</span>
      </div>`
    : "";
  return `<div class="page-wrap page-wrap-workspace-board">${sectionBody(sectionState, `${markup}${pagination}`)}</div>`;
}

function currentWorkspaceBoard() {
  return normalizeWorkspaceBoard(state.sections.board?.data || {});
}

function workspaceBoardBrowserOptions(cursor = null) {
  const options = { page_size: 100 };
  const folderId = String(state.workspaceBoard.selectedFolderId || "all");
  if (folderId === "root") options.folder_id = null;
  else if (folderId !== "all") options.folder_id = folderId;
  if (state.workspaceBoard.query) options.search = state.workspaceBoard.query;
  if (state.workspaceBoard.entityType !== "all") {
    options.entity_types = [state.workspaceBoard.entityType];
  }
  if (cursor) options.cursor = cursor;
  return options;
}

function workspaceBoardQuerySignature() {
  return JSON.stringify(workspaceBoardBrowserOptions());
}

async function refreshWorkspaceBoardAfterMutation() {
  const target = state.sections.board;
  if (!target) return;
  if (["loading", "refreshing"].includes(target.status)) target.status = "ready";
  await loadSection("board", { silent: true });
}

async function submitWorkspaceFolderCreate(form) {
  const values = new FormData(form);
  const name = String(values.get("folder_name") || "").trim();
  const rawParentId = String(values.get("parent_folder_id") || "root");
  state.workspaceBoard.busy = true;
  state.workspaceBoard.error = "";
  state.workspaceBoard.notice = "";
  renderWorkspace("board");
  try {
    const response = await state.api.createWorkspaceFolder({
      name,
      parentId: rawParentId === "root" ? null : rawParentId,
    });
    const source = response?.data ?? response ?? {};
    const folderId = String(source.folder?.id || source.folder_id || "");
    if (folderId) state.workspaceBoard.selectedFolderId = folderId;
    state.workspaceBoard.notice = `Папка «${name}» создана.`;
    await refreshWorkspaceBoardAfterMutation();
  } catch (error) {
    state.workspaceBoard.error = actionErrorMessage(error);
  } finally {
    state.workspaceBoard.busy = false;
    if (state.route.path === "/workspace/board") renderWorkspace("board");
  }
}

async function submitWorkspaceFolderEdit(form) {
  const values = new FormData(form);
  const folderId = String(values.get("folder_id") || "");
  const name = String(values.get("folder_name") || "").trim();
  const expectedVersion = Math.max(1, Number(values.get("folder_version")) || 1);
  state.workspaceBoard.busy = true;
  state.workspaceBoard.error = "";
  state.workspaceBoard.notice = "";
  renderWorkspace("board");
  try {
    await state.api.updateWorkspaceFolder(folderId, {
      expectedVersion,
      name,
    });
    state.workspaceBoard.notice = `Название папки сохранено: «${name}».`;
    await refreshWorkspaceBoardAfterMutation();
  } catch (error) {
    state.workspaceBoard.error = actionErrorMessage(error);
  } finally {
    state.workspaceBoard.busy = false;
    if (state.route.path === "/workspace/board") renderWorkspace("board");
  }
}

async function submitWorkspaceBoardFilters(form) {
  const values = new FormData(form);
  state.workspaceBoard.query = String(values.get("query") || "").trim().slice(0, 120);
  state.workspaceBoard.entityType = String(values.get("entity_type") || "all");
  state.workspaceBoard.notice = "";
  state.workspaceBoard.error = "";
  state.workspaceBoard.hasMore = false;
  state.workspaceBoard.nextCursor = null;
  state.workspaceBoard.visibleItemLimit = WORKSPACE_BOARD_VISIBLE_STEP;
  await loadSection("board");
}

async function archiveWorkspaceBoardFolder(folderId, expectedVersion) {
  const board = currentWorkspaceBoard();
  const folder = board.folders.find((item) => item.id === String(folderId || ""));
  if (!folder) {
    state.workspaceBoard.error = "Папка больше не найдена. Обновите рабочий стол.";
    renderWorkspace("board");
    return;
  }
  if (!window.confirm(`Архивировать пустую папку «${folder.name}»?`)) return;
  state.workspaceBoard.busy = true;
  state.workspaceBoard.error = "";
  state.workspaceBoard.notice = "";
  renderWorkspace("board");
  try {
    await state.api.updateWorkspaceFolder(folder.id, {
      expectedVersion: Math.max(1, Number(expectedVersion) || folder.version || 1),
      archive: true,
    });
    state.workspaceBoard.selectedFolderId = "all";
    state.workspaceBoard.selectedItemKey = "";
    state.workspaceBoard.notice = `Папка «${folder.name}» отправлена в архив.`;
    await refreshWorkspaceBoardAfterMutation();
  } catch (error) {
    state.workspaceBoard.error = actionErrorMessage(error);
  } finally {
    state.workspaceBoard.busy = false;
    if (state.route.path === "/workspace/board") renderWorkspace("board");
  }
}

async function moveWorkspaceBoardItem({
  entityType,
  entityId,
  itemKey,
  destinationFolderId,
}) {
  const board = currentWorkspaceBoard();
  const normalizedKey = String(itemKey || workspaceBoardItemKey(entityType, entityId));
  const item = workspaceBoardItemByKey(board, normalizedKey);
  if (!item) {
    state.workspaceBoard.error = "Объект больше не найден. Обновите рабочий стол.";
    state.workspaceBoard.notice = "";
    renderWorkspace("board");
    return;
  }
  const destination = String(destinationFolderId || "root");
  const destinationId = destination === "root" ? null : destination;
  if ((item.folderId || null) === destinationId) {
    state.workspaceBoard.notice = "Объект уже находится в этой папке.";
    state.workspaceBoard.error = "";
    renderWorkspace("board");
    return;
  }
  state.workspaceBoard.busy = true;
  state.workspaceBoard.error = "";
  state.workspaceBoard.notice = "";
  renderWorkspace("board");
  try {
    await state.api.moveWorkspaceItems(
      [{ type: item.entityType, id: item.id }],
      destinationId,
    );
    const destinationName = destinationId
      ? board.folders.find((folder) => folder.id === destinationId)?.name || "выбранную папку"
      : "Без папки";
    state.workspaceBoard.selectedFolderId = destinationId || "root";
    state.workspaceBoard.selectedItemKey = item.key;
    state.workspaceBoard.notice = `«${item.title}» перемещён в «${destinationName}».`;
    await refreshWorkspaceBoardAfterMutation();
  } catch (error) {
    state.workspaceBoard.error = actionErrorMessage(error);
  } finally {
    state.workspaceBoard.busy = false;
    if (state.route.path === "/workspace/board") renderWorkspace("board");
  }
}

async function loadMoreWorkspaceBoard() {
  const cursor = state.workspaceBoard.nextCursor;
  if (!cursor || state.workspaceBoard.loadingMore || !state.workspaceBoard.hasMore) return;
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const sectionRequestId = state.sections.board.requestId;
  const querySignature = workspaceBoardQuerySignature();
  const requestIsCurrent = () => (
    requestEpoch === state.dataEpoch
    && requestUserId === state.user?.id
    && sectionRequestId === state.sections.board.requestId
    && querySignature === workspaceBoardQuerySignature()
  );
  state.workspaceBoard.loadingMore = true;
  state.workspaceBoard.error = "";
  renderWorkspace("board");
  try {
    const raw = await withUiTimeout(
      state.api.workspaceBrowser(workspaceBoardBrowserOptions(cursor)),
      WORKSPACE_REQUEST_TIMEOUT_MS,
      "workspace_section_timeout",
    );
    if (!requestIsCurrent()) return;
    const next = await hydratePrivateMedia(raw?.data ?? raw ?? {});
    if (!requestIsCurrent()) return;
    const previous = state.sections.board.data || {};
    const itemMap = new Map();
    [...listFrom(previous, "items"), ...listFrom(next, "items")].forEach((item) => {
      const key = workspaceBoardItemKey(
        item?.entity_type || item?.type,
        item?.id || item?.item_id,
      );
      if (key) itemMap.set(key, item);
    });
    const mergedItems = [...itemMap.values()];
    const cappedItems = mergedItems.slice(0, WORKSPACE_BOARD_MEMORY_CAP);
    state.sections.board.data = {
      ...previous,
      ...next,
      folders: Array.isArray(next.folders) ? next.folders : previous.folders,
      items: cappedItems,
    };
    const meta = next?._meta && typeof next._meta === "object" ? next._meta : {};
    const memoryCapReached = mergedItems.length >= WORKSPACE_BOARD_MEMORY_CAP;
    state.workspaceBoard.hasMore = !memoryCapReached && meta.has_more === true;
    state.workspaceBoard.nextCursor = state.workspaceBoard.hasMore ? meta.next_cursor || null : null;
    state.workspaceBoard.visibleItemLimit = Math.min(
      WORKSPACE_BOARD_MEMORY_CAP,
      state.workspaceBoard.visibleItemLimit + WORKSPACE_BOARD_VISIBLE_STEP,
    );
    state.workspaceBoard.notice = memoryCapReached
      ? `Загружены ${WORKSPACE_BOARD_MEMORY_CAP} самых новых объектов. Для более старых используйте папку, тип или поиск.`
      : `Загружено объектов: ${cappedItems.length}.`;
  } catch (error) {
    if (requestIsCurrent()) state.workspaceBoard.error = actionErrorMessage(error);
  } finally {
    state.workspaceBoard.loadingMore = false;
    if (requestIsCurrent() && state.route.path === "/workspace/board") renderWorkspace("board");
  }
}

function renderWorkspace(section) {
  if (state.myWork.notificationsStatus === "idle") {
    window.queueMicrotask(() => loadMyWorkNotifications({ silent: true }));
  }
  const sectionState = section === "home" ? state.home : state.sections[section];
  if (section === "research" && sectionState.status === "idle") {
    sectionState.status = "ready";
  } else if (sectionState.status === "idle") {
    window.queueMicrotask(() => section === "home" ? loadHome() : loadSection(section));
  }

  const renderer = {
    home: renderHomeSection,
    work: renderMyWorkSection,
    board: renderWorkspaceBoardSection,
    generation: renderGenerationSection,
    review: renderContentReviewSection,
    placement: renderPlacementSection,
    stats: renderStatsSection,
    payouts: renderPayoutsSection,
    tasks: renderTasksSection,
    media: renderMediaSection,
    research: renderProductResearchSection,
    feedback: renderFeedbackSection,
    team: renderTeamSection,
  }[section];

  const initialSectionLoad = section !== "home"
    && ["idle", "loading"].includes(sectionState.status)
    && !sectionState.data;
  const content = initialSectionLoad ? workspaceInitialLoadingMarkup(section) : renderer(sectionState);
  const existingShell = app.querySelector(".workspace-shell[data-workspace-section]");
  const existingContent = app.querySelector("#workspace-content");
  if (existingShell?.dataset.workspaceSection === section && existingContent) {
    const focusedControl = captureWorkspaceFocus(existingContent);
    const dirtyForms = captureDirtyWorkspaceForms(existingContent);
    existingContent.innerHTML = content;
    restoreDirtyWorkspaceForms(existingContent, dirtyForms);
    restoreWorkspaceFocus(existingContent, focusedControl, section);
    refreshNotificationLayer();
    scheduleWorkspaceDeepLinkFocus(section);
    return;
  }
  app.innerHTML = workspaceScaffold(content, section);
  refreshNotificationLayer();
  scheduleWorkspaceDeepLinkFocus(section);
}

function captureWorkspaceFocus(container) {
  const active = document.activeElement;
  if (!active || active === document.body || !container?.contains(active)) return null;
  const forms = Array.from(container.querySelectorAll("form"));
  return {
    id: String(active.id || ""),
    action: String(active.dataset?.action || ""),
    name: String(active.getAttribute?.("name") || ""),
    value: String(active.value || ""),
    jobId: String(active.dataset?.jobId || ""),
    outputAction: String(active.dataset?.outputAction || ""),
    generationJobId: String(active.closest?.("[data-generation-job-id]")?.dataset?.generationJobId || ""),
    formKey: active.form ? workspaceFormKey(active.form, forms.indexOf(active.form)) : "",
    selectionStart: Number.isInteger(active.selectionStart) ? active.selectionStart : null,
    selectionEnd: Number.isInteger(active.selectionEnd) ? active.selectionEnd : null,
  };
}

function restoreWorkspaceFocus(container, identity, section) {
  if (!identity) return;
  window.queueMicrotask(() => {
    const candidates = Array.from(container.querySelectorAll("button, a, input, select, textarea, [tabindex]"));
    let target = identity.id ? candidates.find((item) => item.id === identity.id) : null;
    if (!target && identity.action) {
      target = candidates.find((item) => (
        item.dataset?.action === identity.action
        && (!identity.jobId || item.dataset?.jobId === identity.jobId)
        && (!identity.outputAction || item.dataset?.outputAction === identity.outputAction)
        && (!identity.generationJobId || item.closest?.("[data-generation-job-id]")?.dataset?.generationJobId === identity.generationJobId)
      ));
    }
    if (!target && identity.name) {
      const forms = Array.from(container.querySelectorAll("form"));
      target = candidates.find((item) => {
        const formKey = item.form ? workspaceFormKey(item.form, forms.indexOf(item.form)) : "";
        return item.getAttribute?.("name") === identity.name
          && (!identity.formKey || formKey === identity.formKey)
          && (!identity.value || String(item.value || "") === identity.value);
      });
    }
    if (!target || target.disabled || target.getAttribute?.("aria-hidden") === "true") {
      target = section === "generation" ? container.querySelector("#generation-archive-summary") : null;
    }
    if (!target) return;
    target.focus({ preventScroll: true });
    if (
      identity.selectionStart !== null
      && typeof target.setSelectionRange === "function"
      && !target.disabled
    ) {
      target.setSelectionRange(identity.selectionStart, identity.selectionEnd ?? identity.selectionStart);
    }
  });
}

function workspaceInitialLoadingMarkup(section) {
  const label = visibleWorkspaceTabs().find(([key]) => key === section)?.[1] || "Рабочий раздел";
  return `
    <div class="page-wrap">
      <section class="workspace-initial-loading card" role="status" aria-label="Загружаем раздел ${escapeHtml(label)}">
        <span class="sr-only">Загружаем раздел ${escapeHtml(label)}…</span>
        <div aria-hidden="true" class="skeleton skeleton-kicker"></div>
        <div aria-hidden="true" class="skeleton skeleton-title"></div>
        <div aria-hidden="true" class="skeleton skeleton-copy"></div>
        <div aria-hidden="true" class="skeleton skeleton-panel"></div>
      </section>
    </div>
  `;
}

function workspaceFormKey(form, index) {
  if (form.id) return `id:${form.id}`;
  if (form.dataset.placementId) return `placement:${form.dataset.placementId}`;
  if (form.dataset.payoutId) return `payout:${form.dataset.payoutId}:${form.className}`;
  return `index:${index}:${form.className}`;
}

function captureDirtyWorkspaceForms(container) {
  return Array.from(container.querySelectorAll('form[data-dirty="true"], form[data-busy="true"]')).map((form, index) => ({
    key: workspaceFormKey(form, index),
    dirty: form.dataset.dirty === "true",
    busy: form.dataset.busy === "true",
    busyLabel: form.querySelector('button[type="submit"]')?.textContent || "",
    fields: Array.from(form.elements).map((field) => {
      const checkable = field instanceof HTMLInputElement && ["checkbox", "radio"].includes(field.type);
      return {
        value: field.value,
        checked: checkable ? field.checked : null,
        selectedValues: field instanceof HTMLSelectElement && field.multiple
          ? Array.from(field.selectedOptions).map((option) => option.value)
          : null,
        files: field instanceof HTMLInputElement && field.type === "file"
          ? Array.from(field.files || [])
          : null,
      };
    }),
  }));
}

function restoreDirtyWorkspaceForms(container, snapshots) {
  if (!snapshots.length) return;
  const forms = Array.from(container.querySelectorAll("form"));
  snapshots.forEach((snapshot) => {
    const form = forms.find((candidate, index) => workspaceFormKey(candidate, index) === snapshot.key);
    if (!form) return;
    Array.from(form.elements).forEach((field, fieldIndex) => {
      const saved = snapshot.fields[fieldIndex];
      if (!saved) return;
      if (field instanceof HTMLInputElement && field.type === "file" && saved.files?.length) {
        try {
          const transfer = new DataTransfer();
          saved.files.forEach((file) => transfer.items.add(file));
          field.files = transfer.files;
        } catch {
          // Browsers that prohibit restoring a FileList keep the safe empty input.
        }
      } else if (field instanceof HTMLSelectElement && field.multiple && saved.selectedValues) {
        Array.from(field.options).forEach((option) => {
          option.selected = saved.selectedValues.includes(option.value);
        });
      } else if (saved.checked !== null && "checked" in field) {
        field.checked = saved.checked;
      } else if (!(field instanceof HTMLButtonElement)) {
        field.value = saved.value;
      }
    });
    if (snapshot.dirty) form.dataset.dirty = "true";
    if (form.id === "mock-batch-form") syncGenerationModeForm(form);
    if (form.id === "media-upload-form") {
      showSelectedFile(form.elements.file?.files?.[0]);
      syncMediaProductFields(form);
    }
    if (snapshot.busy) setFormBusy(form, true, snapshot.busyLabel || "Подождите…");
  });
}

function workspaceNavLinkMarkup(key, label, icon, activeSection) {
  const stage = FACTORY_FLOW.find((item) => item.key === key);
  const active = key === activeSection;
  return `
    <a class="nav-link ${stage ? "nav-link-stage" : ""} ${active ? "active" : ""}" href="#/workspace/${key}" ${active ? 'aria-current="page"' : ""}>
      <span class="${stage ? "nav-stage-number" : "nav-icon"}" aria-hidden="true">${stage?.step || icon}</span>
      <span class="nav-link-copy"><strong>${escapeHtml(label)}</strong>${stage ? `<small>${escapeHtml(stage.hint)}</small>` : ""}</span>
    </a>
  `;
}

function workspaceNotificationButtonMarkup() {
  const unread = Math.max(0, Number(state.myWork.notifications?.counts?.unread) || 0);
  return `
    <button class="nav-link workspace-notification-nav" type="button" data-action="toggle-work-notifications" aria-haspopup="dialog">
      <span class="nav-icon" aria-hidden="true">!</span>
      <span class="nav-link-copy"><strong>Уведомления</strong><small>${unread ? `${formatNumber(unread)} новых` : "Новых событий нет"}</small></span>
      ${unread ? `<span class="workspace-notification-count" data-notification-count>${formatNumber(unread)}</span>` : ""}
    </button>
  `;
}

function workspaceScaffold(content, activeSection) {
  const profile = displayProfile();
  const tabs = workspaceNavigationTabs(activeSection);
  const tabLabel = tabs.find(([key]) => key === activeSection)?.[1] || "Кабинет";
  const transitionClass = consumeRouteTransitionClass();
  return `
    <div class="workspace-shell" data-workspace-section="${escapeHtml(activeSection)}">
      <aside class="sidebar" aria-label="Основная навигация">
        ${brandMarkup()}
        <nav class="workspace-nav">
          <span class="nav-caption">Рабочий день</span>
          ${workspaceNotificationButtonMarkup()}
          ${tabs.map(([key, label, icon]) => `
            ${key === "media" ? `<span class="nav-caption nav-caption-spaced">Производственный цикл</span>` : ""}
            ${key === "feedback" ? `<span class="nav-caption nav-caption-spaced">Поддержка</span>` : ""}
            ${key === "team" ? `<span class="nav-caption nav-caption-spaced">Управление</span>` : ""}
            ${workspaceNavLinkMarkup(key, label, icon, activeSection)}
          `).join("")}
          <span class="nav-caption nav-caption-spaced">Знания</span>
          <a class="nav-link" href="#/learn"><span class="nav-icon" aria-hidden="true">◎</span><span>Обучение</span></a>
          <a class="nav-link" href="#${ACCOUNT_LAUNCH_PATH}"><span class="nav-icon" aria-hidden="true">#</span><span>Запуск аккаунтов</span></a>
        </nav>
        ${sidebarFooterMarkup(profile)}
      </aside>
      <section class="workspace-main">
        ${brandAtmosphereMarkup()}
        ${mobileTopbarMarkup(tabLabel)}
        ${state.mobileNavOpen ? mobileNavMarkup(false, activeSection) : ""}
        <main id="main-content" class="${transitionClass}" tabindex="-1"><div id="workspace-content">${content}</div></main>
      </section>
      <div id="workspace-notification-layer">${notificationCenterMarkup(state.myWork.notifications, {
        open: state.myWork.notificationsOpen,
        loading: state.myWork.notificationsStatus === "loading",
        error: state.myWork.notificationsError,
      })}</div>
    </div>
  `;
}

function refreshNotificationLayer({ focus = false } = {}) {
  const host = document.querySelector("#workspace-notification-layer");
  if (host) {
    host.innerHTML = notificationCenterMarkup(state.myWork.notifications, {
      open: state.myWork.notificationsOpen,
      loading: state.myWork.notificationsStatus === "loading",
      error: state.myWork.notificationsError,
    });
  }
  document.body.classList.toggle("notification-center-open", state.myWork.notificationsOpen);
  document.querySelectorAll(".workspace-shell > .sidebar, .workspace-shell > .workspace-main").forEach((region) => {
    region.toggleAttribute("inert", state.myWork.notificationsOpen);
  });
  document.querySelectorAll(".workspace-notification-nav").forEach((control) => {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = workspaceNotificationButtonMarkup().trim();
    const replacement = wrapper.firstElementChild;
    if (replacement) control.replaceWith(replacement);
  });
  if (focus && state.myWork.notificationsOpen) {
    window.queueMicrotask(() => document.querySelector(".notification-close")?.focus());
  }
}

function canManageTeam() {
  return ["owner", "admin"].includes(state.bootstrap?.membership?.role);
}

function canManageGenerationSpendPolicy() {
  return ["owner", "admin"].includes(state.bootstrap?.membership?.role);
}

function canManageProductResearch() {
  return ["owner", "admin", "producer"].includes(state.bootstrap?.membership?.role);
}

function visibleWorkspaceTabs() {
  const accessible = WORKSPACE_TABS.filter(([key]) => (
    (key !== "team" || canManageTeam())
    && (key !== "research" || canManageProductResearch())
  ));
  const workTab = accessible.find(([key]) => key === "work");
  return [
    WORKSPACE_HOME_TAB,
    ...(workTab ? [workTab] : []),
    ...accessible.filter(([key]) => key !== "work"),
  ];
}

function workspaceNavigationTabs(activeSection = "") {
  const accessibleTabs = visibleWorkspaceTabs();
  if (state.navigationMode === "all") return accessibleTabs;
  const simpleKeys = new Set(SIMPLE_WORKSPACE_TAB_KEYS);
  return accessibleTabs.filter(([key]) => simpleKeys.has(key) || key === activeSection);
}

function brandMarkup() {
  return `
    <div class="workspace-brand">
      <div class="brand-mark" aria-hidden="true"><img src="./assets/brand/logo_mark.svg" alt="" /></div>
      <div><strong>ALTEA</strong><span>Контент ИИ Завод</span></div>
    </div>
  `;
}

function brandAtmosphereMarkup() {
  return `
    <div class="brand-atmosphere" aria-hidden="true">
      <span class="brand-flower"></span>
      <span class="brand-petal brand-petal-one"></span>
      <span class="brand-petal brand-petal-two"></span>
      <span class="brand-petal brand-petal-three"></span>
    </div>
  `;
}

function themePickerMarkup(scope, compact = false) {
  return `
    <div class="portal-theme-picker ${compact ? "is-compact" : ""}" role="group" aria-label="Оформление портала">
      <span class="portal-theme-label">${compact ? "Тема" : "Оформление"}</span>
      <div class="portal-theme-options">
        ${PORTAL_THEMES.map((theme) => `
          <button
            id="portal-theme-${escapeHtml(scope)}-${escapeHtml(theme.id)}"
            class="portal-theme-option ${state.portalTheme === theme.id ? "is-active" : ""}"
            type="button"
            data-action="set-portal-theme"
            data-theme-value="${escapeHtml(theme.id)}"
            aria-pressed="${state.portalTheme === theme.id ? "true" : "false"}"
            title="${escapeHtml(`${theme.label}: ${theme.description}`)}"
          ><span class="portal-theme-swatch" data-swatch="${escapeHtml(theme.id)}" aria-hidden="true"></span><span>${escapeHtml(theme.label)}</span></button>
        `).join("")}
      </div>
    </div>
  `;
}

function navigationModePickerMarkup(scope, compact = false) {
  return `
    <div class="navigation-mode-picker ${compact ? "is-compact" : ""}" role="group" aria-label="Режим рабочего меню">
      <span class="navigation-mode-label">Меню</span>
      <div class="navigation-mode-options">
        ${NAVIGATION_MODES.map((mode) => `
          <button
            id="navigation-mode-${escapeHtml(scope)}-${escapeHtml(mode.id)}"
            class="navigation-mode-option ${state.navigationMode === mode.id ? "is-active" : ""}"
            type="button"
            data-action="set-navigation-mode"
            data-navigation-mode="${escapeHtml(mode.id)}"
            aria-pressed="${state.navigationMode === mode.id ? "true" : "false"}"
            title="${escapeHtml(mode.description)}"
          >${escapeHtml(mode.label)}</button>
        `).join("")}
      </div>
      <small>${state.navigationMode === "simple"
        ? "Показан основной путь. Служебные разделы доступны в режиме «Все инструменты»."
        : "Показаны все доступные рабочие и управленческие разделы."}</small>
    </div>
  `;
}

function applyPortalTheme(value, { persist = true, announce = false } = {}) {
  const theme = normalizePortalTheme(value);
  state.portalTheme = theme;
  document.documentElement.dataset.portalTheme = theme;
  const browserColors = {
    emerald: "#183a35",
    bordeaux: "#5a2538",
    sapphire: "#183b63",
    "altea-dark": "#0b1513",
  };
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", browserColors[theme]);
  if (persist) persistPortalThemePreference(theme);
  document.querySelectorAll("[data-theme-value]").forEach((control) => {
    const active = control.dataset.themeValue === theme;
    control.classList.toggle("is-active", active);
    control.setAttribute("aria-pressed", String(active));
  });
  if (announce) {
    const selected = PORTAL_THEMES.find((item) => item.id === theme);
    toast(`Тема «${selected?.label || "Изумруд"}» включена.`, "success");
  }
}

function applyNavigationMode(value, {
  persist = true,
  announce = false,
  rerender = false,
} = {}) {
  const navigationMode = normalizeNavigationMode(value);
  const changed = state.navigationMode !== navigationMode;
  state.navigationMode = navigationMode;
  document.documentElement.dataset.navigationMode = navigationMode;
  if (persist) {
    safeStorageSet(
      navigationPreferenceStorage(),
      NAVIGATION_MODE_STORAGE_KEY,
      navigationMode,
    );
  }
  document.querySelectorAll("[data-navigation-mode]").forEach((control) => {
    const active = control.dataset.navigationMode === navigationMode;
    control.classList.toggle("is-active", active);
    control.setAttribute("aria-pressed", String(active));
  });
  if (rerender && changed) render();
  if (announce && changed) {
    const selected = NAVIGATION_MODES.find((mode) => mode.id === navigationMode);
    toast(`Меню «${selected?.label || "Простой"}» включено.`, "success");
  }
}

function sidebarFooterMarkup(profile) {
  return `
    <div class="sidebar-footer">
      ${navigationModePickerMarkup("sidebar")}
      ${themePickerMarkup("sidebar")}
      <div class="sidebar-status"><span class="status-dot"></span><span>Защищённое соединение</span></div>
      <div class="sidebar-user">
        <span class="avatar" aria-hidden="true">${escapeHtml(profile.initials)}</span>
        <div class="user-meta"><strong>${escapeHtml(profile.name)}</strong><span>${escapeHtml(profile.role)}</span></div>
        <button class="logout-button" type="button" data-action="logout" title="Выйти" aria-label="Выйти">↪</button>
      </div>
    </div>
  `;
}

function mobileTopbarMarkup(label) {
  const menuLabel = state.mobileNavOpen ? "Закрыть меню" : "Открыть меню";
  return `
    <header class="mobile-topbar">
      <span class="mobile-brand">ALTEA · ${escapeHtml(label)}</span>
      <button class="mobile-nav-trigger" type="button" data-action="toggle-mobile-nav" aria-label="${menuLabel}" aria-controls="mobile-navigation" aria-expanded="${state.mobileNavOpen}">${state.mobileNavOpen ? "×" : "☰"}</button>
    </header>
  `;
}

function setMobileNavOpen(open, restoreFocus = false) {
  const nextOpen = Boolean(open);
  const trigger = document.querySelector(".mobile-nav-trigger");
  const existingNav = document.querySelector("#mobile-navigation");
  state.mobileNavOpen = nextOpen;
  document.body.classList.toggle("mobile-nav-open", nextOpen);

  if (trigger) {
    trigger.setAttribute("aria-expanded", String(nextOpen));
    trigger.setAttribute("aria-label", nextOpen ? "Закрыть меню" : "Открыть меню");
    trigger.textContent = nextOpen ? "×" : "☰";
  }

  if (nextOpen && !existingNav) {
    const learningOnly = state.route.path.startsWith("/learn");
    const activeSection = state.route.path.startsWith("/workspace/")
      ? state.route.path.replace("/workspace/", "")
      : "";
    document.querySelector(".mobile-topbar")?.insertAdjacentHTML(
      "afterend",
      mobileNavMarkup(learningOnly, activeSection, state.route.path),
    );
    window.queueMicrotask(() => document.querySelector("#mobile-navigation a, #mobile-navigation button")?.focus());
  } else if (!nextOpen) {
    existingNav?.remove();
    if (restoreFocus) trigger?.focus();
  }
}

function handleKeyDown(event) {
  const achievement = document.querySelector("[data-training-achievement]");
  if (achievement && event.key === "Escape") {
    event.preventDefault();
    closeTrainingAchievement();
    return;
  }
  if (achievement && event.key === "Tab") {
    const focusable = Array.from(achievement.querySelectorAll('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
    return;
  }
  const trainingTimelineControl = event.target.closest?.('[data-training-timeline] [data-action="training-walkthrough-jump"]');
  if (trainingTimelineControl && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
    const root = trainingWalkthroughRoot(trainingTimelineControl);
    const total = Math.max(1, Number(root?.dataset.trainingStepCount) || 1);
    const current = Math.max(0, Number(root?.dataset.trainingStep) || 0);
    const next = event.key === "Home"
      ? 0
      : event.key === "End"
        ? total - 1
        : event.key === "ArrowLeft"
          ? current - 1
          : current + 1;
    event.preventDefault();
    const selected = setTrainingWalkthroughStepAndPersist(root, next);
    root?.querySelector(`[data-training-step-target="${selected}"]`)?.focus({ preventScroll: true });
    return;
  }
  if (event.key === "Escape" && state.mobileNavOpen) {
    event.preventDefault();
    setMobileNavOpen(false, true);
    return;
  }
  if (event.key === "Escape" && state.myWork.notificationsOpen) {
    event.preventDefault();
    state.myWork.notificationsOpen = false;
    refreshNotificationLayer();
    document.querySelector(".workspace-notification-nav")?.focus();
    return;
  }
  if (
    event.key === "Escape"
    && state.route.path === "/workspace/board"
    && (state.workspaceBoard.dragging || state.workspaceBoard.selectedItemKey)
  ) {
    event.preventDefault();
    state.workspaceBoard.dragging = null;
    state.workspaceBoard.selectedItemKey = "";
    state.workspaceBoard.notice = "";
    clearWorkspaceDropTargets();
    renderWorkspace("board");
    return;
  }
  if (event.key === "Tab" && state.mobileNavOpen) {
    const nav = document.querySelector("#mobile-navigation");
    const focusable = Array.from(nav?.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') || [])
      .filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true");
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
    return;
  }
  if (event.key === "Tab" && state.myWork.notificationsOpen) {
    const drawer = document.querySelector(".notification-drawer");
    const focusable = Array.from(drawer?.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') || [])
      .filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true");
    if (!focusable.length) {
      event.preventDefault();
      drawer?.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!drawer?.contains(document.activeElement)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}

function mobileNavMarkup(learningOnly, activeSection = "", activeLearningPath = "") {
  return `
    <nav id="mobile-navigation" class="mobile-nav" aria-label="Мобильная навигация">
      ${learningOnly ? `
        <a class="nav-link ${activeLearningPath === "/learn" ? "active" : ""}" href="#/learn" ${activeLearningPath === "/learn" ? 'aria-current="page"' : ""}><span class="nav-icon" aria-hidden="true">◎</span>Курсы</a>
        <a class="nav-link ${activeLearningPath === "/learn/first-shift" ? "active" : ""}" href="#/learn/first-shift" ${activeLearningPath === "/learn/first-shift" ? 'aria-current="page"' : ""}><span class="nav-icon" aria-hidden="true">↗</span>Первая смена</a>
        <a class="nav-link ${activeLearningPath.startsWith(ACCOUNT_LAUNCH_PATH) ? "active" : ""}" href="#${ACCOUNT_LAUNCH_PATH}" ${activeLearningPath.startsWith(ACCOUNT_LAUNCH_PATH) ? 'aria-current="page"' : ""}><span class="nav-icon" aria-hidden="true">#</span>Запуск аккаунтов</a>
        <a class="nav-link ${activeLearningPath === "/learn/practical" ? "active" : ""}" href="#/learn/practical" ${activeLearningPath === "/learn/practical" ? 'aria-current="page"' : ""}><span class="nav-icon" aria-hidden="true">▣</span>Пробная работа</a>
        <a class="nav-link ${activeLearningPath === "/learn/exam" ? "active" : ""}" href="#/learn/exam" ${activeLearningPath === "/learn/exam" ? 'aria-current="page"' : ""}><span class="nav-icon" aria-hidden="true">◇</span>Экзамен</a>
        ${hasWorkspaceAccess() ? `<a class="nav-link" href="#/workspace/home"><span class="nav-icon" aria-hidden="true">→</span>Кабинет</a>` : ""}
      ` : `
        <span class="nav-caption">Сегодня</span>
        ${workspaceNotificationButtonMarkup()}
        ${workspaceNavigationTabs(activeSection).map(([key, label, icon]) => `
          ${key === "media" ? `<span class="nav-caption nav-caption-spaced">Производство · 01–07</span>` : ""}
          ${key === "feedback" ? `<span class="nav-caption nav-caption-spaced">Поддержка</span>` : ""}
          ${key === "team" ? `<span class="nav-caption nav-caption-spaced">Управление</span>` : ""}
          ${workspaceNavLinkMarkup(key, label, icon, activeSection)}
        `).join("")}
        <span class="nav-caption nav-caption-spaced">Знания</span>
        <a class="nav-link" href="#/learn"><span class="nav-icon" aria-hidden="true">◎</span>Обучение</a>
        <a class="nav-link" href="#${ACCOUNT_LAUNCH_PATH}"><span class="nav-icon" aria-hidden="true">#</span>Запуск аккаунтов</a>
      `}
      ${navigationModePickerMarkup("mobile", true)}
      ${themePickerMarkup("mobile", true)}
      <button class="btn btn-secondary btn-block" type="button" data-action="logout">Выйти</button>
    </nav>
  `;
}

async function loadSection(section, options = {}) {
  const target = state.sections[section];
  if (!target || ["loading", "refreshing"].includes(target.status)) return;
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const requestId = target.requestId + 1;
  target.requestId = requestId;
  target.status = target.data ? "refreshing" : "loading";
  target.error = null;
  if (section === "work") state.myWork.error = "";
  if (!options.silent) render();

  try {
    const sectionRequest = section === "work"
      ? state.api.myWork(myWorkRequestOptions(state.myWork.filters))
      : section === "board"
      ? state.api.workspaceBrowser(workspaceBoardBrowserOptions())
      : section === "review"
        ? state.api.contentReviewCatalog({ limit: 50 })
        : state.api.workspaceSection(
          section,
          section === "generation" ? { page_size: GENERATION_ARCHIVE_PAGE_SIZE } : {},
        );
    const initialGenerationFilters = section === "generation"
      ? normalizeGenerationFilters(state.generationArchive.filters)
      : null;
    const generationArchiveRequest = initialGenerationFilters
      ? withUiTimeout(
        state.api.generationArchive({
          period: initialGenerationFilters.period,
          status: initialGenerationFilters.status,
          query: initialGenerationFilters.query,
          page_size: GENERATION_ARCHIVE_PAGE_SIZE,
        }),
        WORKSPACE_REQUEST_TIMEOUT_MS,
        "generation_archive_timeout",
      ).then(
        (value) => ({ status: "fulfilled", value }),
        (reason) => ({ status: "rejected", reason }),
      )
      : null;
    let raw = await withUiTimeout(
      sectionRequest,
      WORKSPACE_REQUEST_TIMEOUT_MS,
      "workspace_section_timeout",
    );
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id || requestId !== target.requestId) return;
    if (section === "work") {
      const firstViewLoad = !state.myWork.viewsLoaded;
      const notificationFetch = beginMyWorkNotificationFetch();
      const [viewsResult, notificationsResult] = await Promise.allSettled([
        withUiTimeout(
          state.api.savedWorkViews({ action: "list" }),
          WORKSPACE_REQUEST_TIMEOUT_MS,
          "saved_work_views_timeout",
        ),
        withUiTimeout(
          state.api.notifications({ page_size: 50 }),
          WORKSPACE_REQUEST_TIMEOUT_MS,
          "notifications_timeout",
        ),
      ]);
      if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id || requestId !== target.requestId) return;
      if (viewsResult.status === "fulfilled") {
        state.myWork.savedViews = normalizeSavedWorkViews(viewsResult.value);
        state.myWork.viewsLoaded = true;
      }
      if (myWorkNotificationFetchIsCurrent(notificationFetch)) {
        if (notificationsResult.status === "fulfilled") {
          state.myWork.notifications = normalizeNotifications(notificationsResult.value);
          state.myWork.notificationsStatus = "ready";
          state.myWork.notificationsError = "";
        } else {
          state.myWork.notificationsStatus = "error";
          state.myWork.notificationsError = "Уведомления временно не загрузились. Рабочая очередь доступна.";
        }
      }

      const noLocalFilters = !state.myWork.filters.query
        && !state.myWork.filters.itemTypes.length
        && !state.myWork.filters.statuses.length;
      const defaultView = firstViewLoad && noLocalFilters
        ? state.myWork.savedViews.find((view) => view.isDefault)
        : null;
      if (defaultView) {
        state.myWork.selectedViewId = defaultView.id;
        state.myWork.filters = normalizeMyWorkFilters(defaultView.filters);
        raw = await withUiTimeout(
          state.api.myWork(myWorkRequestOptions(state.myWork.filters)),
          WORKSPACE_REQUEST_TIMEOUT_MS,
          "workspace_section_timeout",
        );
      }
    }
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id || requestId !== target.requestId) return;
    let data = raw?.data ?? raw ?? {};
    let generationArchiveResult = null;
    if (section === "generation") {
      const archiveOutcome = await generationArchiveRequest;
      if (archiveOutcome?.status === "fulfilled") {
        const archiveRaw = archiveOutcome.value;
        if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id || requestId !== target.requestId) return;
        generationArchiveResult = archiveRaw?.data ?? archiveRaw ?? {};
        data = {
          ...data,
          batches: listFrom(generationArchiveResult, "batches"),
          generation_archive_meta: generationArchiveResult?._meta || {},
        };
        state.generationArchive.error = "";
      } else {
        console.warn("Server generation archive unavailable", archiveOutcome?.reason);
        state.generationArchive.error = "Серверный архив временно недоступен. Показана первая локальная страница.";
      }
    }
    if (section === "team") {
      try {
        const persisted = await withUiTimeout(
          state.api.inviteAttempts(),
          AUTH_REQUEST_TIMEOUT_MS,
          "История приглашений временно недоступна.",
        );
        if (Array.isArray(persisted?.results) && persisted.results.length) {
          state.teamInviteResult = persisted;
          persistTeamInviteResult(persisted);
        } else if (!state.teamInviteResult) {
          state.teamInviteResult = restoreTeamInviteResult();
        }
      } catch (error) {
        console.warn("Invite delivery history unavailable", error);
        if (!state.teamInviteResult) state.teamInviteResult = restoreTeamInviteResult();
      }
    }
    if (section === "media" || section === "board" || section === "review") {
      data = await hydratePrivateMedia(data);
    }
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id || requestId !== target.requestId) return;
    target.data = data;
    target.status = "ready";
    if (section === "board") {
      const meta = data?._meta && typeof data._meta === "object" ? data._meta : {};
      state.workspaceBoard.loadingMore = false;
      state.workspaceBoard.hasMore = meta.has_more === true;
      state.workspaceBoard.nextCursor = meta.next_cursor || null;
    }
    if (section === "generation") {
      const loadedBatches = listFrom(data, "batches");
      const archiveMeta = data?.generation_archive_meta && typeof data.generation_archive_meta === "object"
        ? data.generation_archive_meta
        : {};
      state.generationArchive.requestId += 1;
      state.generationArchive.loading = false;
      state.generationArchive.loadingMore = false;
      state.generationArchive.serverLoaded = Boolean(generationArchiveResult);
      state.generationArchive.nextCursor = generationArchiveResult ? archiveMeta.next_cursor || null : null;
      state.generationArchive.exhausted = generationArchiveResult
        ? archiveMeta.has_more !== true
        : loadedBatches.length < GENERATION_ARCHIVE_PAGE_SIZE;
    }
    if (section === "review") {
      const catalog = normalizeContentReviewCatalog(data);
      const routeReviewId = safeWorkspaceRouteEntityId("review");
      let routeRecord = routeReviewId
        ? catalog.runs.find((item) => item.id === routeReviewId)
          || (String(state.contentReview.record?.id || "") === routeReviewId
            ? state.contentReview.record
            : null)
        : null;
      if (routeReviewId && !routeRecord) {
        try {
          const routeStatus = await withUiTimeout(
            state.api.contentReviewStatus(routeReviewId),
            WORKSPACE_REQUEST_TIMEOUT_MS,
            "content_review_status_timeout",
          );
          const hydratedRouteStatus = await hydratePrivateMedia(
            routeStatus,
            { refreshSignedUrls: true },
          );
          const normalizedRouteRecord = normalizeContentReviewRun(hydratedRouteStatus);
          if (normalizedRouteRecord.id === routeReviewId) {
            routeRecord = normalizedRouteRecord;
          }
        } catch (error) {
          console.warn("Deep-linked content review is unavailable", error);
        }
      }
      if (
        requestEpoch !== state.dataEpoch
        || requestUserId !== state.user?.id
        || requestId !== target.requestId
      ) return;
      const selectedId = routeReviewId || String(state.contentReview.record?.id || "");
      state.contentReview.record = routeRecord
        || catalog.runs.find((item) => item.id === selectedId)
        || catalog.runs.find((item) => contentReviewStatusKind(item.status) === "active")
        || catalog.runs[0]
        || null;
      state.contentReview.phase = state.contentReview.record?.summaryOnly
        ? "refreshing"
        : state.contentReview.record && contentReviewStatusKind(state.contentReview.record.status) === "active"
          ? "processing"
          : "idle";
      scheduleContentReviewPolling();
      if (state.contentReview.record?.summaryOnly) {
        window.queueMicrotask(() => pollContentReviewStatus({ silent: true, refreshMedia: true }));
      }
    }
  } catch (error) {
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id || requestId !== target.requestId) return;
    target.error = error;
    target.status = "error";
  }
  if (state.route.path === `/workspace/${section}`) render();
  else if (options.rerenderSection && state.route.path === `/workspace/${options.rerenderSection}`) render();
  else if (options.silent && section === "team") syncGenerationAssigneeOptions();
}

function beginMyWorkNotificationFetch() {
  state.myWork.notificationsRequestId += 1;
  return {
    requestId: state.myWork.notificationsRequestId,
    mutationEpoch: state.myWork.notificationsMutationEpoch,
    dataEpoch: state.dataEpoch,
    userId: state.user?.id,
  };
}

function myWorkNotificationFetchIsCurrent(request) {
  return Boolean(
    request
    && request.requestId === state.myWork.notificationsRequestId
    && request.mutationEpoch === state.myWork.notificationsMutationEpoch
    && request.dataEpoch === state.dataEpoch
    && request.userId === state.user?.id
  );
}

async function loadMyWorkNotifications({ silent = false } = {}) {
  if (state.myWork.notificationsStatus === "loading") return;
  const request = beginMyWorkNotificationFetch();
  state.myWork.notificationsStatus = "loading";
  state.myWork.notificationsError = "";
  if (!silent) refreshNotificationLayer();
  try {
    const raw = await withUiTimeout(
      state.api.notifications({ page_size: 50 }),
      WORKSPACE_REQUEST_TIMEOUT_MS,
      "notifications_timeout",
    );
    if (!myWorkNotificationFetchIsCurrent(request)) return;
    state.myWork.notifications = normalizeNotifications(raw);
    state.myWork.notificationsStatus = "ready";
  } catch (error) {
    if (!myWorkNotificationFetchIsCurrent(request)) return;
    state.myWork.notificationsStatus = "error";
    state.myWork.notificationsError = "Не удалось обновить уведомления. Рабочие разделы продолжают работать.";
    console.warn("Notifications unavailable", error);
  }
  if (!myWorkNotificationFetchIsCurrent(request)) return;
  refreshNotificationLayer();
  if (state.route.path === "/workspace/work") renderWorkspace("work");
}

async function markMyWorkNotificationsRead(notificationIds) {
  const ids = [...new Set((notificationIds || []).map(String).filter(Boolean))].slice(0, 100);
  if (!ids.length) return;
  state.myWork.notificationsMutationEpoch += 1;
  state.myWork.notificationsRequestId += 1;
  try {
    await state.api.markNotificationsRead(ids, true);
    state.myWork.notificationsMutationEpoch += 1;
    const now = new Date().toISOString();
    const marked = new Set(ids);
    state.myWork.notifications = {
      ...state.myWork.notifications,
      counts: {
        ...state.myWork.notifications.counts,
        unread: Math.max(
          0,
          Number(state.myWork.notifications.counts?.unread || 0)
          - state.myWork.notifications.items.filter((item) => marked.has(item.id) && !item.readAt).length,
        ),
      },
      items: state.myWork.notifications.items.map((item) => (
        marked.has(item.id) ? { ...item, readAt: item.readAt || now } : item
      )),
    };
    state.myWork.notificationsStatus = "ready";
    state.myWork.notificationsError = "";
    refreshNotificationLayer();
    if (state.route.path === "/workspace/work") renderWorkspace("work");
  } catch (error) {
    state.myWork.notificationsMutationEpoch += 1;
    if (state.myWork.notificationsStatus === "loading") {
      state.myWork.notificationsStatus = "ready";
    }
    state.myWork.notificationsError = actionErrorMessage(error);
    refreshNotificationLayer();
  }
}

async function markAllMyWorkNotificationsRead() {
  if (!Number(state.myWork.notifications.counts?.unread || 0)) return;
  state.myWork.notificationsMutationEpoch += 1;
  state.myWork.notificationsRequestId += 1;
  try {
    await state.api.markAllNotificationsRead();
    state.myWork.notificationsMutationEpoch += 1;
    const now = new Date().toISOString();
    state.myWork.notifications = {
      ...state.myWork.notifications,
      counts: {
        ...state.myWork.notifications.counts,
        unread: 0,
      },
      items: state.myWork.notifications.items.map((item) => ({
        ...item,
        readAt: item.readAt || now,
      })),
    };
    state.myWork.notificationsStatus = "ready";
    state.myWork.notificationsError = "";
    refreshNotificationLayer();
    if (state.route.path === "/workspace/work") renderWorkspace("work");
  } catch (error) {
    state.myWork.notificationsMutationEpoch += 1;
    if (state.myWork.notificationsStatus === "loading") {
      state.myWork.notificationsStatus = "ready";
    }
    state.myWork.notificationsError = actionErrorMessage(error);
    refreshNotificationLayer();
  }
}

async function loadMoreMyWork() {
  const target = state.sections.work;
  const current = normalizeMyWork(target.data);
  if (!current.nextCursor || state.myWork.loadingMore) return;
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const sectionRequestId = target.requestId;
  state.myWork.loadingMore = true;
  state.myWork.error = "";
  renderWorkspace("work");
  try {
    const raw = await withUiTimeout(
      state.api.myWork(myWorkRequestOptions(state.myWork.filters, current.nextCursor)),
      WORKSPACE_REQUEST_TIMEOUT_MS,
      "workspace_section_timeout",
    );
    if (
      requestEpoch !== state.dataEpoch
      || requestUserId !== state.user?.id
      || sectionRequestId !== target.requestId
    ) return;
    const next = normalizeMyWork(raw);
    const itemMap = new Map();
    [...current.items, ...next.items].forEach((item) => {
      itemMap.set(`${item.itemType}:${item.id}`, item);
    });
    target.data = {
      ...next,
      items: [...itemMap.values()],
    };
  } catch (error) {
    if (requestEpoch === state.dataEpoch && requestUserId === state.user?.id) {
      state.myWork.error = actionErrorMessage(error);
    }
  } finally {
    state.myWork.loadingMore = false;
    if (state.route.path === "/workspace/work") renderWorkspace("work");
  }
}

async function reloadSavedWorkViews() {
  const raw = await withUiTimeout(
    state.api.savedWorkViews({ action: "list" }),
    WORKSPACE_REQUEST_TIMEOUT_MS,
    "saved_work_views_timeout",
  );
  state.myWork.savedViews = normalizeSavedWorkViews(raw);
  state.myWork.viewsLoaded = true;
}

async function loadManagerDashboard({ silent = false } = {}) {
  const target = state.managerDashboard;
  const health = state.operationalHealth;
  const spend = state.generationSpend;
  if (
    !canManageTeam()
    || ["loading", "refreshing"].includes(target.status)
    || ["loading", "refreshing"].includes(health.status)
    || ["loading", "refreshing"].includes(spend.status)
  ) return;
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const requestId = target.requestId + 1;
  const healthRequestId = health.requestId + 1;
  target.requestId = requestId;
  target.status = target.data ? "refreshing" : "loading";
  target.error = null;
  health.requestId = healthRequestId;
  health.status = health.data ? "refreshing" : "loading";
  health.error = null;
  if (!silent && state.route.path === "/workspace/team") render();
  const renderCurrentTeam = () => {
    if (state.route.path === "/workspace/team") render();
  };
  const dashboardRequest = withUiTimeout(
    state.api.managerDashboard(),
    WORKSPACE_REQUEST_TIMEOUT_MS,
    "manager_dashboard_timeout",
  ).then((raw) => {
      if (
        requestEpoch !== state.dataEpoch
        || requestUserId !== state.user?.id
        || requestId !== target.requestId
      ) return;
      target.data = raw?.data ?? raw ?? {};
      target.status = "ready";
      target.updatedAt = Date.now();
      renderCurrentTeam();
    }).catch((error) => {
      if (
        requestEpoch !== state.dataEpoch
        || requestUserId !== state.user?.id
        || requestId !== target.requestId
      ) return;
      target.error = error;
      target.status = "error";
      renderCurrentTeam();
    });
  const healthRequest = withUiTimeout(
    state.api.operationalHealth(),
    WORKSPACE_REQUEST_TIMEOUT_MS,
    "operational_health_timeout",
  ).then((raw) => {
      if (
        requestEpoch !== state.dataEpoch
        || requestUserId !== state.user?.id
        || healthRequestId !== health.requestId
      ) return;
      health.data = raw?.data ?? raw ?? {};
      health.status = "ready";
      health.updatedAt = Date.now();
      renderCurrentTeam();
    }).catch((error) => {
      if (
        requestEpoch !== state.dataEpoch
        || requestUserId !== state.user?.id
        || healthRequestId !== health.requestId
      ) return;
      health.error = error;
      health.status = "error";
      renderCurrentTeam();
    });
  const spendRequest = loadGenerationSpendOverview({ silent: true, force: true });
  await Promise.allSettled([dashboardRequest, healthRequest, spendRequest]);
}

async function loadGenerationSpendOverview({ silent = false, force = false } = {}) {
  const target = state.generationSpend;
  if (
    !hasWorkspaceAccess()
    || (!force && ["loading", "refreshing"].includes(target.status))
  ) return target.data;
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const requestId = target.requestId + 1;
  target.requestId = requestId;
  target.status = target.data ? "refreshing" : "loading";
  target.error = null;
  if (!silent && ["/workspace/team", "/workspace/generation"].includes(state.route.path)) render();
  try {
    const raw = await withUiTimeout(
      state.api.generationSpendOverview(),
      WORKSPACE_REQUEST_TIMEOUT_MS,
      "generation_spend_overview_timeout",
    );
    if (
      requestEpoch !== state.dataEpoch
      || requestUserId !== state.user?.id
      || requestId !== target.requestId
    ) return target.data;
    target.data = raw?.data ?? raw ?? {};
    target.status = "ready";
    target.error = null;
    target.updatedAt = Date.now();
    return target.data;
  } catch (error) {
    if (
      requestEpoch !== state.dataEpoch
      || requestUserId !== state.user?.id
      || requestId !== target.requestId
    ) return target.data;
    target.error = error;
    target.status = "error";
    return target.data;
  } finally {
    if (
      requestEpoch === state.dataEpoch
      && requestUserId === state.user?.id
      && requestId === target.requestId
      && ["/workspace/team", "/workspace/generation"].includes(state.route.path)
    ) render();
  }
}

async function hydratePrivateMedia(data, { refreshSignedUrls = false } = {}) {
  if (!data || typeof data !== "object") return data;
  const listKeys = ["media", "media_items", "items", "artifacts"];
  const roots = [data];
  if (data.data && typeof data.data === "object" && !Array.isArray(data.data)) roots.push(data.data);
  const singularHolders = [];
  const objectKeys = [];
  for (const root of roots) {
    for (const key of listKeys) {
      if (!Array.isArray(root[key])) continue;
      for (const item of root[key]) {
        const objectKey = item?.object_name || item?.object_key;
        if (objectKey && (refreshSignedUrls || !item.signed_url)) objectKeys.push(String(objectKey));
      }
    }
    for (const holder of [root, root.run, root.review]) {
      if (!holder || typeof holder !== "object" || Array.isArray(holder)) continue;
      const item = holder.media;
      if (!item || typeof item !== "object" || Array.isArray(item)) continue;
      singularHolders.push({ holder, item });
      const objectKey = item.object_name || item.object_key;
      if (objectKey && (refreshSignedUrls || !item.signed_url)) objectKeys.push(String(objectKey));
    }
  }
  if (!objectKeys.length) return data;
  try {
    const signedUrls = await state.api.signedPrivateObjectUrls([...new Set(objectKeys)]);
    for (const root of roots) {
      for (const key of listKeys) {
        if (!Array.isArray(root[key])) continue;
        root[key] = root[key].map((item) => {
          const objectKey = item?.object_name || item?.object_key;
          return objectKey && signedUrls.has(String(objectKey))
            ? { ...item, signed_url: signedUrls.get(String(objectKey)) }
            : item;
        });
      }
    }
    for (const { holder, item } of singularHolders) {
      const objectKey = item.object_name || item.object_key;
      if (objectKey && signedUrls.has(String(objectKey))) {
        holder.media = { ...item, signed_url: signedUrls.get(String(objectKey)) };
      }
    }
  } catch {
    // Metadata remains usable when a short-lived preview URL cannot be issued.
  }
  return data;
}

async function loadHome() {
  if (["loading", "refreshing"].includes(state.home.status)) return;
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const requestId = state.home.requestId + 1;
  state.home.requestId = requestId;
  state.home.status = state.home.data ? "refreshing" : "loading";
  state.home.error = null;
  render();

  const previousData = state.home.data || {};
  const results = await Promise.all(HOME_SECTION_KEYS.map(async (section) => {
    try {
      const raw = await withUiTimeout(
        section === "review"
          ? state.api.contentReviewCatalog({ limit: 50 })
          : state.api.workspaceSection(section),
        HOME_SECTION_TIMEOUT_MS,
        "home_section_timeout",
      );
      let data = raw?.data ?? raw ?? {};
      return { section, data, error: null };
    } catch (error) {
      console.error(`Home section failed: ${section}`, error);
      return { section, data: previousData[section] || {}, error };
    }
  }));
  if (
    requestEpoch !== state.dataEpoch
    || requestUserId !== state.user?.id
    || requestId !== state.home.requestId
  ) return;

  const failed = results.filter((result) => result.error);
  const hasPreviousData = Object.keys(previousData).length > 0;
  state.home.data = Object.fromEntries(results.map((result) => [result.section, result.data]));
  state.home.unavailable = failed.map((result) => result.section);
  state.home.error = failed.length === results.length ? failed[0]?.error : null;
  state.home.status = failed.length === results.length && !hasPreviousData ? "error" : "ready";
  if (state.route.path === "/workspace/home") render();
}

function isActionablePlacement(item) {
  return ["scheduled", "ready"].includes(String(item?.status || "").toLowerCase());
}

function isCompletedPlacement(item) {
  return ["done", "completed", "published"].includes(String(item?.status || "").toLowerCase());
}

function isAutomaticGenerationWait(task) {
  if (String(task?.task_type || "") !== "video_review") return false;
  const result = task?.result && typeof task.result === "object"
    ? task.result
    : task?.result_json && typeof task.result_json === "object"
      ? task.result_json
      : {};
  return ["queued", "starting", "submitted", "processing", "running"].includes(
    String(result.generation_status || "").toLowerCase(),
  );
}

function homeNextAction({ media, batches, tasks, placements, publications, payouts }) {
  const blockedTask = tasks.find(
    (item) => String(item.status || "") === "blocked" && !isAutomaticGenerationWait(item),
  );
  if (blockedTask) {
    return {
      step: "Нужна помощь",
      title: blockedTask.title || "Разберите препятствие в задаче",
      description: "В задаче зафиксирован блокер. Уточните причину и продолжите только после решения.",
      href: "#/workspace/tasks",
      cta: "Открыть задачи",
      doneWhen: "Причина понятна и решение руководителя сохранено в задаче.",
      nextHint: "Вернитесь к тому же шагу, не начинайте новую работу.",
    };
  }
  const activeTask = tasks.find(
    (item) => !["done", "cancelled", "blocked"].includes(String(item.status || "")) && !isAutomaticGenerationWait(item),
  );
  if (activeTask) {
    return {
      step: "Следующее действие",
      title: activeTask.title || "Продолжите назначенную задачу",
      description: activeTask.instructions || "Откройте задачу, выполните один следующий шаг и сохраните результат.",
      href: "#/workspace/tasks",
      cta: "Перейти к задаче",
      doneWhen: "Статус задачи изменён, а результат или блокер сохранён.",
      nextHint: "Портал сам покажет следующий этап после сохранения.",
    };
  }
  const activeGeneration = batches.find((item) => ["queued", "starting", "submitted", "processing", "running"].includes(String(item.status || "").toLowerCase()));
  if (activeGeneration) {
    return {
      step: "Видео создаётся",
      title: activeGeneration.name || activeGeneration.sku || "Проверьте готовность ролика",
      description: "Запуск уже принят. Не запускайте его повторно — статус и готовый файл появятся в списке.",
      href: "#/workspace/generation",
      cta: "Проверить запуск",
      doneWhen: "Появился готовый файл или понятная причина ошибки.",
      nextHint: "Готовый ролик перейдёт в проверку задачи.",
    };
  }
  const openPlacement = placements.find(isActionablePlacement);
  if (openPlacement) {
    return {
      step: "Готово к публикации",
      title: openPlacement.title || openPlacement.product_name || "Опубликуйте одобренный ролик",
      description: "Сверьте назначенный аккаунт и рекламный статус, затем сохраните ссылку на опубликованный пост.",
      href: "#/workspace/placement",
      cta: "Открыть публикацию",
      doneWhen: "В портал сохранена рабочая ссылка на конкретный ролик.",
      nextHint: "После публикации внесите первый снимок метрик.",
    };
  }
  const completedPlacementWithoutMetrics = placements.find((placement) => {
    if (!isCompletedPlacement(placement)) return false;
    const placementId = String(placement.id || placement.placement_id || "");
    const publication = placementId
      ? publications.find((item) => String(item.placement_id || item.id || "") === placementId)
      : null;
    return !publication?.observed_at;
  });
  if (completedPlacementWithoutMetrics) {
    return {
      step: "Зафиксируйте результат",
      title: "Добавьте первый снимок метрик",
      description: "Ролик уже опубликован. Сохраните показатели вместе с датой и ссылкой на конкретный пост.",
      href: "#/workspace/stats",
      cta: "Внести показатели",
      doneWhen: "В разделе есть дата, источник и первый набор показателей.",
      nextHint: "После проверки результата следите за начислением.",
    };
  }
  const waitingPayout = payouts.find((item) => ["pending", "approved"].includes(String(item.status || "").toLowerCase()));
  if (waitingPayout) {
    return {
      step: "Проверьте расчёт",
      title: "Начисление ещё не завершено",
      description: "Сверьте сумму и статус. «Одобрено» означает подтверждение, но не завершённый внешний перевод.",
      href: "#/workspace/payouts",
      cta: "Открыть выплаты",
      doneWhen: "Статус изменился на «Выплачено» или сохранена понятная причина ожидания.",
      nextHint: "После выплаты цикл этой задачи завершён.",
    };
  }
  if (!media.length) {
    return {
      step: "Начните здесь",
      title: "Добавьте точное фото товара",
      description: "Загрузите фронтальный кадр с читаемой этикеткой — после этого он появится в форме создания видео.",
      href: "#/workspace/media",
      cta: "Добавить материал",
      doneWhen: "Фото загрузилось, а товар, объём и этикетка совпадают.",
      nextHint: "Перейдите в «Создание видео» и выберите этот исходник.",
    };
  }
  return {
    step: "Всё готово",
    title: "Создайте следующий ролик",
    description: "Исходники уже в защищённом хранилище. Выберите товар, сценарий и подходящий режим запуска.",
    href: "#/workspace/generation",
    cta: "Создать видео",
    doneWhen: "Один запуск создан после отдельной проверки стоимости.",
    nextHint: "Дождитесь статуса, не оплачивайте повторный запуск.",
  };
}

function renderHomeSection(homeState) {
  if ((homeState.status === "loading" || homeState.status === "idle") && !homeState.data) {
    return `
      <div class="page-wrap workspace-home">
        <section class="home-hero home-hero-loading" role="status" aria-label="Собираем рабочий день">
          <span class="sr-only">Собираем рабочий день…</span>
          <div aria-hidden="true" class="skeleton skeleton-title"></div>
          <div aria-hidden="true" class="skeleton skeleton-copy"></div>
          <div aria-hidden="true" class="skeleton skeleton-action"></div>
        </section>
        <div aria-hidden="true" class="metrics-grid home-metrics">${Array.from({ length: 4 }, () => '<div class="card metric-card"><div class="skeleton"></div></div>').join("")}</div>
      </div>
    `;
  }
  if (homeState.status === "error") {
    return `
      <div class="page-wrap workspace-home">
        <section class="card home-error-state" role="alert">
          <span class="home-error-mark" aria-hidden="true">!</span>
          <p class="eyebrow">Рабочий день</p>
          <h1>Не удалось собрать сводку</h1>
          <p>Проверьте соединение и попробуйте ещё раз. Остальные разделы доступны в меню.</p>
          <button class="btn" type="button" data-action="refresh-home">Попробовать снова</button>
        </section>
      </div>
    `;
  }

  const data = homeState.data || {};
  const media = listFrom(data.media || {}, "media", "items", "artifacts");
  const batches = listFrom(data.generation || {}, "batches");
  const reviewRuns = normalizeContentReviewCatalog(data.review || {}).runs;
  const tasks = listFrom(data.tasks || {}, "tasks", "items", "rows");
  const placements = listFrom(data.placement || {}, "placements", "items", "tasks");
  const stats = data.stats || {};
  const publications = listFrom(stats, "publications", "items", "rows");
  const payouts = listFrom(data.payouts || {}, "payouts", "items", "rows");
  const activeTasks = tasks.filter(
    (item) => !["done", "cancelled"].includes(String(item.status || "")) && !isAutomaticGenerationWait(item),
  ).length;
  const activeGenerations = batches.filter((item) => ["queued", "starting", "submitted", "processing", "running"].includes(String(item.status || "").toLowerCase())).length;
  const reviewBlockers = reviewRuns.filter((item) => (
    contentReviewStatusKind(item.status) === "ready" && contentReviewHasBlockers(item) && !item.decision
  )).length;
  const activeReviews = reviewRuns.filter((item) => contentReviewStatusKind(item.status) === "active").length;
  const openPlacements = placements.filter(isActionablePlacement).length;
  const waitingPayoutMinor = sumMinor(payouts.filter((item) => ["pending", "approved"].includes(String(item.status || ""))));
  const action = homeNextAction({ media, batches, tasks, placements, publications, payouts });
  const firstName = displayProfile().name.split(/\s+/).filter(Boolean)[0] || "Сергей";
  const flowValues = {
    media: `${media.length}`,
    generation: activeGenerations ? `${activeGenerations} в работе` : `${batches.length}`,
    review: activeReviews ? `${activeReviews} в работе` : reviewBlockers ? `${reviewBlockers} блокеров` : `${reviewRuns.length}`,
    tasks: activeTasks ? `${activeTasks} активных` : "0",
    placement: openPlacements ? `${openPlacements} к выходу` : "0",
    stats: `${publications.length}`,
    payouts: formatMoney(waitingPayoutMinor),
  };

  return `
    <div class="page-wrap workspace-home">
      ${homeState.status === "refreshing" ? '<div class="refresh-indicator" role="status"><span aria-hidden="true"></span>Обновляем сводку…</div>' : ""}
      ${homeState.unavailable?.length ? alertMarkup("Часть свежих данных пока недоступна. Показаны последние сохранённые значения; повторите обновление позже.", "warning") : ""}
      <section class="home-hero">
        <div class="home-hero-copy">
          <p class="eyebrow">Сегодня в ALTEA</p>
          <h1>${escapeHtml(firstName)}, всё важное — перед вами</h1>
          <p>Портал сам собирает следующий шаг: от точного исходника до публикации, результата и выплаты.</p>
          <article class="home-next-action">
            <div class="home-next-action-main">
              <div>
                <span>${escapeHtml(action.step)}</span>
                <h2>${escapeHtml(action.title)}</h2>
                <p>${escapeHtml(action.description)}</p>
              </div>
              <a class="btn btn-light" href="${action.href}">${escapeHtml(action.cta)} <span aria-hidden="true">→</span></a>
            </div>
            <div class="home-next-action-proof">
              <span><small>Готово, когда</small><strong>${escapeHtml(action.doneWhen)}</strong></span>
              <span><small>Потом</small><strong>${escapeHtml(action.nextHint)}</strong></span>
            </div>
          </article>
        </div>
        <div class="home-hero-visual" role="img" aria-label="${FACTORY_FLOW.length} этапов производственного цикла">
          <span class="home-orbit home-orbit-one"></span>
          <span class="home-orbit home-orbit-two"></span>
          <div class="home-seal"><strong>A</strong><span>${FACTORY_FLOW.length} этапов</span></div>
        </div>
      </section>

      <div class="metrics-grid home-metrics">
        ${[
          ["Активные задачи", activeTasks, "что требует действия сейчас", "tasks"],
          ["Видео создаётся", activeGenerations, "запуски без повторной оплаты", "generation"],
          ["К публикации", openPlacements, "одобренные ролики без ссылки", "placement"],
          ["Ждёт выплаты", formatMoney(waitingPayoutMinor), "одобрено или на проверке", "payouts"],
        ].map(([label, value, hint, key]) => `<a class="card metric-card home-metric-card" href="#/workspace/${key}"><span class="metric-label">${label}</span><strong>${typeof value === "number" ? formatNumber(value) : value}</strong><small>${hint}</small><span class="metric-arrow" aria-hidden="true">↗</span></a>`).join("")}
      </div>
      <p class="home-data-scope">Оперативная сводка показывает последние 50 записей каждого раздела. Старые видео подгружаются в архиве порциями, не замедляя рабочий день.</p>
      <a class="card home-board-shortcut" href="#/workspace/board">
        <span class="home-board-shortcut__mark" aria-hidden="true">▦</span>
        <span class="home-board-shortcut__copy">
          <small>Рабочее пространство</small>
          <strong>Разложить материалы и задачи по папкам</strong>
          <span>Карточки открываются нажатием, перемещаются мышью или через доступное меню на телефоне.</span>
        </span>
        <span class="home-board-shortcut__action">Открыть <i aria-hidden="true">→</i></span>
      </a>

      <section class="card home-flow-card">
        <div class="section-heading home-section-heading">
          <div><p class="eyebrow">Карта производства</p><h2>${FACTORY_FLOW.length} этапов одного результата</h2></div>
          <p>Каждый этап хранит свою часть истории товара. Нажмите на этап, чтобы продолжить работу.</p>
        </div>
        <ol class="home-flow-list" style="--workflow-step-count:${FACTORY_FLOW.length}">
          ${FACTORY_FLOW.map((item) => `<li><a href="#/workspace/${item.key}"><span>${item.step}</span><div><strong>${item.label}</strong><small>${item.hint}</small></div><em>${escapeHtml(flowValues[item.key])}</em></a></li>`).join("")}
        </ol>
      </section>

      <div class="home-guidance-grid">
        <section class="card home-guidance-card">
          <span class="guidance-mark" aria-hidden="true">✓</span>
          <div><p class="eyebrow">Перед любым запуском</p><h2>Товар, файл и задача совпадают</h2><p>Не используйте похожий артикул, случайный референс или другой аккаунт публикации.</p></div>
        </section>
        <section class="card home-guidance-card home-guidance-card-accent">
          <span class="guidance-mark" aria-hidden="true">!</span>
          <div><p class="eyebrow">Если чего-то не хватает</p><h2>Остановитесь и зафиксируйте блокер</h2><p>Так руководитель увидит проблему, а результат не потеряет связь с исходной задачей.</p></div>
        </section>
      </div>
    </div>
  `;
}

function realGenerationSku(mode) {
  return REAL_GENERATION_SKUS[String(mode || "")] || null;
}

function generationAssignableMembers() {
  const members = listFrom(state.sections.team.data || {}, "members").filter(
    (member) => member.status === "active" && normalizeBoolean(member.exam_passed),
  );
  if (state.user?.id && !members.some((member) => String(member.profile_id) === String(state.user.id))) {
    members.unshift({
      profile_id: state.user.id,
      display_name: state.bootstrap?.profile?.display_name || state.user.email || "Вы",
      role: state.bootstrap?.membership?.role,
      status: "active",
      exam_passed: true,
    });
  }
  return members;
}

function productResearchAssignableMembers() {
  const members = listFrom(state.sections.team.data || {}, "members")
    .filter((member) => member.status === "active" && member.profile_id);
  if (state.user?.id && !members.some((member) => String(member.profile_id) === String(state.user.id))) {
    members.unshift({
      profile_id: state.user.id,
      display_name: state.bootstrap?.profile?.display_name || state.user.email || "Вы",
      email: state.user.email || "",
      role: state.bootstrap?.membership?.role,
      status: "active",
    });
  }
  return members;
}

function syncGenerationAssigneeOptions() {
  const select = document.querySelector('#mock-batch-form select[name="assignee_id"]');
  if (!select) return;
  const selected = select.value;
  select.innerHTML = generationAssignableMembers().map((member) => `
    <option value="${escapeHtml(member.profile_id)}" ${String(member.profile_id) === String(selected || state.user?.id) ? "selected" : ""}>${escapeHtml(member.display_name || member.email || humanRole(member.role))}</option>
  `).join("");
}

function isRealGenerationMode(mode) {
  return realGenerationSku(mode) !== null;
}

function activeGenerationCampaigns() {
  if (!state.generationSpend.data || state.generationSpend.status !== "ready") return [];
  return normalizeGenerationSpendOverview(state.generationSpend.data).campaigns
    .filter((campaign) => campaign.id && campaign.enabled && !campaign.blockerCode);
}

function realGenerationSpendAllowed(mode, campaignId = "") {
  const sku = realGenerationSku(mode);
  if (!sku) return true;
  if (!state.generationSpend.data || state.generationSpend.status !== "ready") return false;
  return generationSpendAllowsMinor(
    normalizeGenerationSpendOverview(state.generationSpend.data),
    sku.estimatedMinor,
    campaignId,
  );
}

function renderGenerationSection(sectionState) {
  const data = sectionState.data || {};
  const batches = listFrom(data, "batches");
  const archiveFilters = normalizeGenerationFilters(state.generationArchive.filters);
  const filteredBatches = filterGenerationBatches(batches, archiveFilters);
  const visibleBatches = filteredBatches.slice(0, archiveFilters.visible);
  const media = listFrom(data, "media", "media_items");
  const exactMedia = media.filter((item) => ["product_photo", "packshot"].includes(item.kind));
  const aliases = listFrom(data, "wb_aliases", "aliases");
  const generationCampaigns = activeGenerationCampaigns();
  const seedanceCampaign = generationCampaigns.find((campaign) =>
    realGenerationSpendAllowed(REAL_SEEDANCE_MODE, campaign.id)
  );
  const gen4Campaign = generationCampaigns.find((campaign) =>
    realGenerationSpendAllowed(REAL_GEN4_MODE, campaign.id)
  );
  const seedanceSpendAllowed = Boolean(seedanceCampaign);
  const gen4SpendAllowed = Boolean(gen4Campaign);
  const defaultMode = MOCK_GENERATION_ENABLED
    ? "mock"
    : seedanceSpendAllowed
      ? REAL_SEEDANCE_MODE
      : gen4SpendAllowed
        ? REAL_GEN4_MODE
        : REAL_SEEDANCE_MODE;
  const defaultCampaignId = defaultMode === REAL_SEEDANCE_MODE
    ? seedanceCampaign?.id || ""
    : defaultMode === REAL_GEN4_MODE
      ? gen4Campaign?.id || ""
      : seedanceCampaign?.id || gen4Campaign?.id || generationCampaigns[0]?.id || "";
  const defaultRealSku = realGenerationSku(defaultMode) || REAL_GENERATION_SKUS[REAL_SEEDANCE_MODE];
  const defaultIsReal = isRealGenerationMode(defaultMode);
  if (state.generationSpend.status === "idle") {
    window.queueMicrotask(() => loadGenerationSpendOverview({ silent: true }));
  }
  const canManageAliases = ["owner", "admin", "producer"].includes(state.bootstrap?.membership?.role);
  const canAssignTeam = canManageTeam();
  if (canAssignTeam && state.sections.team.status === "idle") {
    window.queueMicrotask(() => loadSection("team", { silent: true }));
  }
  const assignableMembers = generationAssignableMembers();
  const activeRealJobs = realGenerationJobsFromBatches(batches);
  const reconciliationRealJobs = realGenerationReconciliationJobsFromBatches(batches);
  const startingRealJobs = activeRealJobs.filter((item) => item.status === "starting");
  window.queueMicrotask(() => {
    scheduleRealGenerationPolling();
  });
  return `
    <div class="page-wrap">
      ${pageHeader(
        "Создание видео",
        "Создайте тестовые варианты без списаний или один готовый ролик по фотографии выбранного товара.",
        REAL_GENERATION_ENABLED && (seedanceSpendAllowed || gen4SpendAllowed)
          ? `<span class="badge badge-info">ТЕСТОВЫЙ + ПЛАТНЫЙ</span>`
          : `<span class="badge badge-mock">ТЕСТОВЫЙ · БЕЗ СПИСАНИЙ</span>`,
      )}
      <div class="split-grid">
        <section class="card card-pad">
          <p class="eyebrow">Новый запуск</p>
          <h2 style="font:600 1.55rem/1.15 Georgia,serif; margin:0 0 8px">Выберите режим запуска</h2>
          <p class="muted tiny">Тестовый режим создаёт до ${MAX_MOCK_BATCH_SIZE} вариантов без списаний. Платный режим создаёт ровно один ролик: 5-секундную анимацию товара без голоса или 8-секундного блогера с озвучкой.</p>
          ${generationSpendSnapshotMarkup(state.generationSpend, {
            requestMinor: Math.min(REAL_GENERATION_SKUS[REAL_GEN4_MODE].estimatedMinor, REAL_GENERATION_SKUS[REAL_SEEDANCE_MODE].estimatedMinor),
            campaignId: defaultCampaignId,
          })}
          ${state.realGenerationStartNotice ? alertMarkup(state.realGenerationStartNotice, "warning") : ""}
          ${startingRealJobs.length ? alertMarkup("Платный запуск сейчас сверяется с видеосервисом. Не запускайте его повторно: сначала дождитесь проверки статуса — так мы исключаем двойное списание.", "warning") : ""}
          ${reconciliationRealJobs.length ? alertMarkup("Автопроверка одного или нескольких запусков остановлена безопасно: исход запроса к Runway неизвестен. Не создавайте новый платный запуск, пока владелец или администратор не выполнит ручную сверку в очереди.", "warning") : ""}
          <form id="mock-batch-form" class="form-stack" style="margin-top:18px" novalidate>
            <label class="field">
              <span>Режим генерации *</span>
              <select id="generation-mode" name="generation_mode" required>
                ${MOCK_GENERATION_ENABLED ? `<option value="mock" ${defaultMode === "mock" ? "selected" : ""}>Тестовые варианты · без списаний</option>` : ""}
                ${REAL_GENERATION_ENABLED ? `
                  <option value="${REAL_SEEDANCE_MODE}" ${defaultMode === REAL_SEEDANCE_MODE ? "selected" : ""} ${seedanceSpendAllowed ? "" : "disabled"}>${REAL_GENERATION_SKUS[REAL_SEEDANCE_MODE].label}${seedanceSpendAllowed ? "" : " · лимит"}</option>
                  <option value="${REAL_GEN4_MODE}" ${defaultMode === REAL_GEN4_MODE ? "selected" : ""} ${gen4SpendAllowed ? "" : "disabled"}>${REAL_GENERATION_SKUS[REAL_GEN4_MODE].label}${gen4SpendAllowed ? "" : " · лимит"}</option>
                ` : ""}
              </select>
            </label>
            <label class="field" id="generation-campaign-field" ${defaultIsReal ? "" : "hidden"}>
              <span>Кампания и её бюджет *</span>
              <select name="campaign_id" ${defaultIsReal ? "required" : "disabled"}>
                ${generationCampaigns.length
                  ? generationCampaigns.map((campaign) => `<option value="${escapeHtml(campaign.id)}" ${campaign.id === defaultCampaignId ? "selected" : ""}>${escapeHtml(campaign.name || "Кампания")} · доступно $${((campaign.remainingMinor || 0) / 100).toFixed(2)}</option>`).join("")
                  : `<option value="">Нет активной кампании</option>`}
              </select>
              <small class="field-hint">Сумма будет атомарно зарезервирована и в лимите команды, и в лимите этой кампании.</small>
            </label>
            <div id="real-generation-confirmation" ${defaultIsReal ? "" : "hidden"}>
              <div class="alert alert-warning" role="status"><strong aria-hidden="true">!</strong><span id="real-generation-price">Один ролик — около $${defaultRealSku.estimatedUsd} (${defaultRealSku.estimatedCredits} кредитов). Окончательная стоимость зависит от тарифа сервиса.</span></div>
              <p id="real-generation-note" class="muted tiny" style="margin:8px 0 0">${defaultMode === REAL_SEEDANCE_MODE ? "Голос создаётся по сценарию, но реплика может отличаться. Обязательно прослушайте ролик перед публикацией." : "Этот режим создаёт видео без сгенерированной речи."}</p>
              <label class="option" style="margin-top:10px">
                <input type="checkbox" name="real_spend_confirmation" value="${defaultRealSku.confirmation}" ${defaultIsReal ? "required" : ""} />
                <span><strong>Подтверждаю создание одного платного видео</strong><br /><small id="real-generation-confirmation-copy" class="muted">${defaultRealSku.durationSeconds} секунд · одно видео · около $${defaultRealSku.estimatedUsd}</small></span>
              </label>
            </div>
            <label class="field">
              <span>Код товара / артикул *</span>
              <input name="sku" required maxlength="120" placeholder="Например: WB-12345678" autocomplete="off" />
              <small class="field-hint">Скопируйте из назначенной карточки, не вводите похожий товар.</small>
            </label>
            <label class="field">
              <span>Название товара *</span>
              <input name="product_name" required maxlength="180" placeholder="Точное название и вариант" autocomplete="off" />
            </label>
            <div class="form-grid-2">
              <label class="field">
                <span>Площадка *</span>
                <select name="platform" required><option value="instagram">Instagram</option><option value="tiktok">TikTok</option><option value="youtube">YouTube</option><option value="vk">VK</option><option value="telegram">Telegram</option><option value="wildberries">Wildberries</option></select>
              </label>
              <label class="field">
                <span>Аккаунт или карточка для публикации *</span>
                <input name="destination_ref" required minlength="2" maxlength="240" placeholder="Точный @аккаунт, канал или карточка" autocomplete="off" />
              </label>
            </div>
            ${canAssignTeam ? `
              <div class="form-grid-2">
                <label class="field">
                  <span>Исполнитель *</span>
                  <select name="assignee_id" required>
                    ${assignableMembers.map((member) => `<option value="${escapeHtml(member.profile_id)}" ${String(member.profile_id) === String(state.user?.id) ? "selected" : ""}>${escapeHtml(member.display_name || member.email || humanRole(member.role))}</option>`).join("")}
                  </select>
                  <small class="field-hint">Доступны только участники, уже сдавшие экзамен.</small>
                </label>
                <label class="field">
                  <span>Начисление исполнителю, ₽</span>
                  <input name="payout_rub" type="number" min="0" max="10000" step="0.01" value="0" required />
                  <small class="field-hint">Сумма появится в разделе «Выплаты» после принятия задачи. Перевод выполняется отдельно.</small>
                </label>
              </div>
            ` : ""}
            <div class="form-grid-2">
              <label class="field">
                <span>Количество вариантов</span>
                <input name="count" type="number" min="1" max="${defaultIsReal ? 1 : MAX_MOCK_BATCH_SIZE}" value="${defaultIsReal ? 1 : 5}" ${defaultIsReal ? "readonly" : ""} required />
                <small id="generation-count-hint" class="field-hint">${defaultIsReal ? "Платный режим всегда создаёт ровно одно видео." : `Тестовый режим: от 1 до ${MAX_MOCK_BATCH_SIZE} вариантов.`}</small>
              </label>
              <label class="field">
                <span>Формат</span>
                <select name="format"><option value="9:16">9:16 · вертикальный</option><option value="1:1">1:1 · квадрат</option><option value="16:9">16:9 · горизонтальный</option></select>
              </label>
            </div>
            <label class="field">
              <span>Сценарий и главная мысль</span>
              <textarea name="brief" maxlength="1200" ${defaultIsReal ? "required" : ""} placeholder="Кто в кадре, где происходит действие, как показан товар и какую фразу произносит герой"></textarea>
              <small id="generation-brief-hint" class="field-hint">${defaultMode === REAL_SEEDANCE_MODE ? "Перед оплатой вставьте сценарий именно выбранного товара и проверьте дословную реплику." : "Для платного режима опишите один ролик без неподтверждённых обещаний."}</small>
            </label>
            ${exactMedia.length ? `
              <fieldset style="border:0; padding:0; margin:0">
                <legend class="field-label">Фото выбранного товара *</legend>
                <p id="generation-media-hint" class="muted tiny">${defaultIsReal ? "Для платного запуска выберите ровно один исходник." : "Для тестового режима можно выбрать один или несколько исходников."}</p>
                <div class="option-list" style="margin-top:8px">
                  ${exactMedia.slice(0, 8).map((item) => `
                    <label class="option">
                      <input type="${defaultIsReal ? "radio" : "checkbox"}" name="media_id" value="${escapeHtml(item.public_id || item.id)}" />
                      <span><strong>${escapeHtml(item.original_filename || item.name || "Файл")}</strong><br /><small class="muted">${escapeHtml(humanMediaKind(item.kind))}</small></span>
                    </label>
                  `).join("")}
                </div>
              </fieldset>
            ` : `<div class="alert alert-warning" role="status"><strong aria-hidden="true">!</strong><span>Сначала добавьте точное фото товара или упаковки в разделе <a href="#/workspace/media">«Материалы»</a>. Без исходника запуск недоступен.</span></div>`}
            <button id="generation-submit" class="btn btn-block" type="submit" ${(exactMedia.length && !state.realGenerationStartInFlight && (!defaultIsReal || realGenerationSpendAllowed(defaultMode, defaultCampaignId))) ? "" : "disabled"}>${state.realGenerationStartInFlight ? "Проверяем платный запуск — не повторяйте" : (defaultIsReal ? `Создать один ролик · около $${defaultRealSku.estimatedUsd}` : "Создать тестовые варианты")}</button>
          </form>
          ${canRepeatRealGeneration(state.lastRealGenerationJobId) ? `
            <div class="generation-repeat-panel" role="status">
              <div><strong>Нужен ещё один вариант?</strong><span>Поля сохранены. Перед новым платным запуском ещё раз проверьте сценарий и подтвердите стоимость.</span></div>
              <button class="btn btn-secondary btn-small" type="button" data-action="repeat-real-generation" data-job-id="${escapeHtml(state.lastRealGenerationJobId)}">Создать ещё вариант</button>
            </div>
          ` : ""}
        </section>

        <section class="card">
          <div class="card-header"><div><p class="eyebrow">Архив и очередь</p><h2>Видео по неделям</h2><small class="muted">${activeRealJobs.length ? `Автопроверка активных роликов каждые ${REAL_GENERATION_POLL_INTERVAL_MS / 1_000} секунд` : (reconciliationRealJobs.length ? `${reconciliationRealJobs.length} запуск(а) ждут ручной сверки без повторной оплаты` : "Активных платных запусков нет")}</small></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="generation">Обновить</button></div>
          ${sectionBody(sectionState, generationArchiveMarkup(
            batches,
            filteredBatches,
            visibleBatches,
            archiveFilters,
          ))}
        </section>
      </div>
      ${(canManageAliases || aliases.length) ? `
        <section class="card card-pad" style="margin-top:22px">
          <div class="split-grid">
            <div>
              <p class="eyebrow">Идентичность товара</p>
              <h2 style="font:600 1.5rem/1.2 Georgia,serif; margin:0 0 8px">Артикулы Wildberries</h2>
              <p class="muted tiny"><strong>Подменный артикул</strong> — другой номер карточки WB, который руководитель подтвердил для того же точного товара. Это не похожий вкус, объём или упаковка. Исполнитель сам подменник не выбирает: он использует номер из задачи, а портал сохраняет старую и новую карточки с датой, не переписывая прошлые метрики.</p>
              ${aliases.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>Код товара</th><th>Текущий</th><th>Старый / подменный</th></tr></thead><tbody>${aliases.slice(0, 20).map((item) => `<tr><td>${escapeHtml(item.sku)}</td><td>${escapeHtml(item.current_article || item.canonical_article || "—")}</td><td>${escapeHtml(item.alias_article || item.wb_alias || "—")}</td></tr>`).join("")}</tbody></table></div>` : emptyState("WB", "Связей пока нет", "Подменник добавляет только руководитель после подтверждения, что товар действительно тот же.")}
            </div>
            ${canManageAliases ? `
              <form id="wb-alias-form" class="form-stack" novalidate>
                <label class="field"><span>Внутренний код товара *</span><input name="sku" required maxlength="120" placeholder="Точный код товара из задачи" /></label>
                <label class="field"><span>Текущий артикул WB *</span><input name="current_article" required maxlength="120" inputmode="numeric" placeholder="Например: 123456789" /></label>
                <label class="field"><span>Старый / подменный артикул того же товара *</span><input name="alias_article" required maxlength="120" inputmode="numeric" placeholder="Артикул из исторических данных" /></label>
                <label class="field"><span>Почему появилась связь *</span><textarea name="reason" required minlength="5" maxlength="600" placeholder="Например: WB заменил карточку 13.07.2026; подтверждено владельцем"></textarea></label>
                <button class="btn" type="submit">Сохранить связь без перезаписи истории</button>
              </form>
            ` : alertMarkup("Изменять связи может только руководитель или продюсер. Вам доступен просмотр.", "info")}
          </div>
        </section>
      ` : ""}
    </div>
  `;
}

function generationArchiveMarkup(batches, filteredBatches, visibleBatches, filters) {
  const hasMoreVisible = visibleBatches.length < filteredBatches.length && filters.visible < GENERATION_VISIBLE_CAP;
  const archive = state.generationArchive;
  return `
    <div class="generation-archive" aria-busy="${archive.loading || archive.loadingMore ? "true" : "false"}">
      <form id="generation-archive-filter-form" class="generation-archive-toolbar" novalidate>
        <label class="field">
          <span>Период</span>
          <select name="period">
            <option value="week" ${filters.period === "week" ? "selected" : ""}>Эта неделя</option>
            <option value="4w" ${filters.period === "4w" ? "selected" : ""}>Последние 4 недели</option>
            <option value="12w" ${filters.period === "12w" ? "selected" : ""}>Последние 12 недель</option>
            <option value="all" ${filters.period === "all" ? "selected" : ""}>Вся история</option>
          </select>
        </label>
        <label class="field">
          <span>Статус</span>
          <select name="status">
            <option value="all" ${filters.status === "all" ? "selected" : ""}>Все статусы</option>
            <option value="active" ${filters.status === "active" ? "selected" : ""}>Сейчас создаются</option>
            <option value="ready" ${filters.status === "ready" ? "selected" : ""}>Готовые</option>
            <option value="issue" ${filters.status === "issue" ? "selected" : ""}>Ошибки и отменённые</option>
          </select>
        </label>
        <label class="field generation-archive-search">
          <span>Товар или запуск</span>
          <input name="query" maxlength="120" value="${escapeHtml(filters.query)}" placeholder="Артикул, название или ID" autocomplete="off" />
        </label>
        <button id="generation-archive-submit" class="btn btn-small" type="submit" ${archive.loading ? "disabled" : ""}>${archive.loading ? "Ищем…" : "Показать"}</button>
      </form>
      <div id="generation-archive-summary" class="generation-archive-summary" tabindex="-1" aria-live="polite" aria-atomic="true">
        <span>${archive.serverLoaded ? "Сервер нашёл" : "Найдено локально"} <strong>${formatNumber(filteredBatches.length)}</strong> на загруженных страницах</span>
        <span>На экране: ${formatNumber(visibleBatches.length)}</span>
      </div>
      ${archive.error ? `<div class="alert alert-danger" role="alert"><strong aria-hidden="true">!</strong><span>${escapeHtml(archive.error)}</span></div>` : ""}
      ${visibleBatches.length
        ? generationTable(visibleBatches)
        : `<div class="empty-state"><div class="empty-icon" aria-hidden="true">⌕</div><h3>${archive.serverLoaded ? "Во всём архиве ничего не найдено" : `Среди ${formatNumber(batches.length)} загруженных запусков ничего нет`}</h3><p>Измените период, статус или поисковый запрос.</p><button class="btn btn-secondary btn-small" type="button" data-action="reset-generation-filters">Сбросить фильтры</button></div>`}
      <div class="generation-archive-actions">
        ${hasMoreVisible ? `<button class="btn btn-secondary btn-small" type="button" data-action="show-more-generation">Показать ещё ${GENERATION_VISIBLE_STEP}</button>` : ""}
        ${filteredBatches.length > visibleBatches.length && filters.visible >= GENERATION_VISIBLE_CAP ? `<span class="muted tiny">Уточните период или поиск, чтобы не выводить больше ${GENERATION_VISIBLE_CAP} строк сразу</span>` : ""}
        ${!archive.exhausted ? `<button class="btn btn-secondary btn-small" type="button" data-action="load-more-generation" ${archive.loading || archive.loadingMore ? "disabled" : ""}>${archive.loadingMore ? "Загружаем…" : archive.error ? "Повторить загрузку истории" : `Загрузить ещё ${GENERATION_ARCHIVE_PAGE_SIZE} старых`}</button>` : `<span class="muted tiny">Загружена вся доступная история по выбранным фильтрам</span>`}
      </div>
      <p class="generation-archive-note">Период, статус и поиск применяются на сервере ко всему архиву. Кнопка «Загрузить ещё» добавляет следующую страницу без повторов. <span class="generation-mobile-hint">На телефоне таблицу можно листать по горизонтали.</span></p>
    </div>
  `;
}

async function submitGenerationArchiveFilters(form) {
  form.removeAttribute("data-dirty");
  const values = new FormData(form);
  state.generationArchive.filters = normalizeGenerationFilters({
    period: values.get("period"),
    status: values.get("status"),
    query: values.get("query"),
    visible: GENERATION_VISIBLE_STEP,
  });
  state.generationArchive.error = "";
  await reloadGenerationArchive();
}

function focusGenerationArchiveSummary() {
  window.queueMicrotask(() => {
    document.querySelector("#generation-archive-summary")?.focus({ preventScroll: true });
  });
}

async function reloadGenerationArchive() {
  const archive = state.generationArchive;
  const target = state.sections.generation;
  if (archive.loading || archive.loadingMore || !target?.data) return;
  const filters = normalizeGenerationFilters(archive.filters);
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const requestId = archive.requestId + 1;
  archive.requestId = requestId;
  archive.loading = true;
  archive.error = "";
  archive.nextCursor = null;
  archive.exhausted = false;
  renderWorkspace("generation");
  try {
    const raw = await withUiTimeout(
      state.api.generationArchive({
        period: filters.period,
        status: filters.status,
        query: filters.query,
        page_size: GENERATION_ARCHIVE_PAGE_SIZE,
      }),
      WORKSPACE_REQUEST_TIMEOUT_MS,
      "generation_archive_timeout",
    );
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id || requestId !== archive.requestId) return;
    const data = raw?.data ?? raw ?? {};
    const batches = listFrom(data, "batches");
    const meta = data?._meta && typeof data._meta === "object" ? data._meta : {};
    target.data = {
      ...target.data,
      batches,
      generation_archive_meta: meta,
    };
    target.status = "ready";
    archive.serverLoaded = true;
    archive.nextCursor = meta.next_cursor || null;
    archive.exhausted = meta.has_more !== true;
  } catch (error) {
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id || requestId !== archive.requestId) return;
    archive.serverLoaded = false;
    archive.nextCursor = null;
    archive.exhausted = true;
    archive.error = `${actionErrorMessage(error)} Показана только ранее загруженная страница; повторите поиск после восстановления связи.`;
  } finally {
    if (requestEpoch === state.dataEpoch && requestUserId === state.user?.id && requestId === archive.requestId) {
      archive.loading = false;
      if (state.route.path === "/workspace/generation") renderWorkspace("generation");
      focusGenerationArchiveSummary();
    }
  }
}

async function loadMoreGenerationArchive() {
  const archive = state.generationArchive;
  const target = state.sections.generation;
  if (archive.loading || archive.loadingMore || archive.exhausted || !target?.data) return;
  const currentBatches = listFrom(target.data, "batches");
  const cursor = archive.serverLoaded
    ? archive.nextCursor
    : generationArchiveCursor(currentBatches)?.generation_batches || null;
  if (!cursor) {
    archive.exhausted = true;
    renderWorkspace("generation");
    return;
  }
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const requestId = archive.requestId + 1;
  archive.requestId = requestId;
  archive.loadingMore = true;
  archive.error = "";
  renderWorkspace("generation");
  try {
    const filters = normalizeGenerationFilters(archive.filters);
    const raw = await withUiTimeout(
      archive.serverLoaded
        ? state.api.generationArchive({
          period: filters.period,
          status: filters.status,
          query: filters.query,
          page_size: GENERATION_ARCHIVE_PAGE_SIZE,
          cursor,
        })
        : state.api.workspaceSection("generation", {
          page_size: GENERATION_ARCHIVE_PAGE_SIZE,
          cursor: { generation_batches: cursor },
        }),
      WORKSPACE_REQUEST_TIMEOUT_MS,
      "generation_archive_timeout",
    );
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id || requestId !== archive.requestId) return;
    const incomingData = raw?.data ?? raw ?? {};
    const incomingBatches = listFrom(incomingData, "batches");
    const mergedBatches = mergeGenerationPages(currentBatches, incomingBatches);
    const meta = incomingData?._meta && typeof incomingData._meta === "object"
      ? incomingData._meta
      : {};
    target.data = {
      ...target.data,
      batches: mergedBatches,
      generation_archive_meta: archive.serverLoaded
        ? meta
        : target.data?.generation_archive_meta,
    };
    target.status = "ready";
    if (archive.serverLoaded) {
      archive.nextCursor = meta.next_cursor || null;
      archive.exhausted = meta.has_more !== true;
    } else {
      archive.exhausted = incomingBatches.length < GENERATION_ARCHIVE_PAGE_SIZE
        || mergedBatches.length === currentBatches.length;
    }
  } catch (error) {
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id || requestId !== archive.requestId) return;
    archive.error = actionErrorMessage(error);
  } finally {
    if (requestEpoch === state.dataEpoch && requestUserId === state.user?.id && requestId === archive.requestId) {
      archive.loadingMore = false;
      if (state.route.path === "/workspace/generation") renderWorkspace("generation");
    }
  }
}

function generationTable(items) {
  return `
    <div class="table-wrap"><table class="data-table generation-table">
      <caption class="sr-only">Архив запусков генерации видео</caption>
      <thead><tr><th scope="col">Запуск</th><th scope="col">Код товара</th><th scope="col">Этап</th><th scope="col">Стоимость</th><th scope="col">Создан</th></tr></thead>
      <tbody>${items.map((item, index) => {
        const weekLabel = generationWeekLabel(item.created_at);
        const previousWeekLabel = index > 0
          ? generationWeekLabel(items[index - 1]?.created_at)
          : "";
        const weekHeading = index === 0 || weekLabel !== previousWeekLabel
          ? `<tr class="generation-week-heading"><th colspan="5" scope="rowgroup">Неделя ${escapeHtml(weekLabel)}</th></tr>`
          : "";
        const details = generationBatchDetails(item);
        if (!details.real) {
          return `${weekHeading}
            <tr>
              <td><strong>${escapeHtml(item.name || item.public_id || `#${item.id}`)}</strong><br /><small class="muted">Тестовые варианты · без списаний</small></td>
              <td>${escapeHtml(item.sku || details.parameters.sku || "—")}</td>
              <td>${statusBadge(details.status)}<br /><small class="muted">Готово ${formatNumber(item.total_accepted ?? item.completed ?? 0)} из ${formatNumber(item.total_requested ?? item.count ?? 0)}</small></td>
              <td>0 ₽</td>
              <td>${formatDate(item.created_at)}<br /><small class="muted">${escapeHtml(generationWeekLabel(item.created_at))}</small></td>
            </tr>
          `;
        }

        const failure = details.failureCode ? generationFailureMessage(details.failureCode) : "";
        const previewUrl = trustedCachedGenerationUrl(details.jobId);
        const startingWarning = details.reconciliationRequired
          ? `<div class="generation-reconcile-warning generation-reconcile-warning-critical" role="alert"><strong>Нужна ручная сверка Runway.</strong><span>Автоопрос остановлен, потому что исход платного POST неизвестен. Новый запуск запрещён до фиксации существующего task ID или подтверждения его отсутствия.</span></div>`
          : details.status === "starting"
            ? `<div class="generation-reconcile-warning"><strong>Идёт сверка запуска.</strong><span>Не запускайте видео повторно — сначала система проверит, был ли запрос принят сервисом.</span></div>`
          : "";
        const failureMarkup = details.status === "failed"
          ? `<div class="generation-failure" role="alert"><strong>Ролик не создан</strong><span>${escapeHtml(failure || "Видеосервис завершил задачу с ошибкой.")}</span></div>`
          : "";
        const actions = generationActionsMarkup(details);
        const preview = previewUrl
          ? `<div class="generation-result-preview"><video src="${escapeHtml(previewUrl)}" controls preload="none" playsinline aria-label="Готовый ролик ${escapeHtml(item.sku || "")}"></video><small>Защищённая ссылка обновляется при каждом открытии или скачивании.</small></div>`
          : "";
        return `${weekHeading}
          <tr data-generation-job-id="${escapeHtml(details.jobId)}" tabindex="-1">
            <td><strong>${escapeHtml(item.name || item.public_id || `#${item.id}`)}</strong><br /><small class="muted">Платный ролик · ${details.duration} секунд${details.audio ? " · с озвучкой" : " · без голоса"}</small></td>
            <td>${escapeHtml(item.sku || details.parameters.sku || "—")}</td>
            <td>
              ${generationStageMarkup(details.status)}
              ${startingWarning}
              ${failureMarkup}
              ${details.transientError ? `<small class="generation-transient-error">${escapeHtml(details.transientError)}</small>` : ""}
              ${actions}
              ${preview}
            </td>
            <td>${generationCostMarkup(details)}</td>
            <td>${formatDate(item.created_at)}<br /><small class="muted">${escapeHtml(generationWeekLabel(item.created_at))}</small>${details.checkedAt ? `<br /><small class="muted">Проверено ${formatDate(details.checkedAt, true)}</small>` : ""}</td>
          </tr>
        `;
      }).join("")}</tbody>
    </table></div>
  `;
}

function generationBatchDetails(item) {
  const parameters = item?.parameters && typeof item.parameters === "object" ? item.parameters : {};
  const real = String(item?.mode || parameters.mode || "mock").toLowerCase() === "real";
  const jobId = real ? String(parameters.job_id || "") : "";
  const cached = jobId ? state.realGenerationResults.get(jobId) : null;
  const job = cached?.job && typeof cached.job === "object" ? cached.job : {};
  const billing = parameters.billing && typeof parameters.billing === "object" ? parameters.billing : {};
  const status = String(job.status || item?.status || parameters.job_status || "queued").toLowerCase();
  const estimatedMinor = firstFiniteNumber(job.estimated_cost_minor, item?.estimated_cost_minor, billing.estimated_cost_minor);
  const actualMinor = firstFiniteNumber(job.actual_cost_minor, item?.actual_cost_minor, parameters.actual_cost_minor);
  return {
    item,
    parameters,
    real,
    jobId,
    status,
    duration: Number(job.duration_seconds || item?.duration_seconds || parameters.duration_seconds || 5),
    audio: normalizeBoolean(job.audio ?? item?.audio ?? parameters.audio),
    estimatedMinor,
    actualMinor,
    failureCode: String(job.failure_code || parameters.failure_code || ""),
    submissionState: String(job.submission_state || parameters.submission_state || ""),
    reconciliationRequired: normalizeBoolean(
      job.reconciliation_required ?? parameters.reconciliation_required,
    ),
    reconciliationIncidentId: String(
      job.reconciliation_incident_id || parameters.reconciliation_incident_id || "",
    ),
    reconciliationRequiredAt: String(
      job.reconciliation_required_at || parameters.reconciliation_required_at || "",
    ),
    reconciliationReasonCode: String(
      job.reconciliation_reason_code || parameters.reconciliation_reason_code || "",
    ),
    reconciliationResolution: String(
      job.reconciliation_resolution || parameters.reconciliation_resolution || "",
    ),
    canReconcile: normalizeBoolean(job.can_reconcile ?? parameters.can_reconcile),
    checkedAt: cached?.checkedAt || "",
    transientError: cached?.transientError || "",
  };
}

function generationStageMarkup(status) {
  const normalized = String(status || "queued").toLowerCase();
  const failed = normalized === "failed" || normalized === "cancelled";
  const order = { queued: 0, starting: 0, submitted: 1, processing: 2, running: 2, saving: 3, uploading: 3, succeeded: 4, completed: 4 };
  const current = order[normalized] ?? (failed ? 2 : 0);
  const labels = ["Принято", "В очереди", "Создаётся", "Сохраняется", "Готово"];
  return `
    <div class="generation-stage" role="group" aria-label="Этап платной генерации: ${escapeHtml(humanGenerationStatus(normalized))}">
      ${labels.map((label, index) => `<span class="${failed ? (index === current ? "is-error" : index < current ? "is-done" : "") : (index < current ? "is-done" : index === current ? "is-current" : "")}"><i aria-hidden="true">${failed && index === current ? "!" : (index < current ? "✓" : index + 1)}</i>${label}</span>`).join("")}
    </div>
  `;
}

function generationActionsMarkup(details) {
  if (!details.jobId) return "";
  if (details.reconciliationRequired) {
    if (!details.canReconcile || !details.reconciliationIncidentId) {
      return `
        <div class="generation-reconciliation-readonly" role="status">
          <strong>Действие руководителя</strong>
          <span>Ручную сверку выполняет владелец или администратор команды в этой карточке. До решения новый платный запуск не создавайте.</span>
        </div>
      `;
    }
    return `
      <form class="generation-reconciliation-form" data-job-id="${escapeHtml(details.jobId)}" data-incident-id="${escapeHtml(details.reconciliationIncidentId)}" novalidate>
        <div class="generation-reconciliation-heading">
          <strong>Сверить с панелью Runway</strong>
          <span>Проверяйте только task, созданный рядом со временем этого запуска. Портал дополнительно сверит ID, статус и createdAt через API.</span>
        </div>
        <label class="field">
          <span>Runway task ID</span>
          <input name="provider_task_id" maxlength="128" placeholder="Нужен для кнопки «Прикрепить task»" autocomplete="off" />
        </label>
        <label class="field">
          <span>Основание проверки *</span>
          <input name="evidence_reference" required minlength="8" maxlength="500" placeholder="Например: Runway dashboard, 16.07 14:35" autocomplete="off" />
        </label>
        <label class="field">
          <span>Что именно проверено *</span>
          <textarea name="reason" required minlength="20" maxlength="1000" placeholder="Укажите время, модель, товар и почему task относится к этому запуску или отсутствует"></textarea>
        </label>
        <label class="option generation-reconciliation-confirmation">
          <input type="checkbox" name="manual_confirmation" value="confirmed" required />
          <span>Подтверждаю ручную проверку в Runway и понимаю, что портал не повторяет платный POST автоматически.</span>
        </label>
        <div class="generation-result-actions">
          <button class="btn btn-small" type="submit" name="resolution" value="attach_existing_task">Прикрепить найденный task</button>
          <button class="btn btn-secondary btn-small" type="submit" name="resolution" value="confirm_no_submission">Подтвердить: task отсутствует</button>
        </div>
        <small class="generation-reconciliation-note">Подтверждение отсутствия станет доступно не раньше чем через две минуты после фиксации инцидента.</small>
      </form>
    `;
  }
  if (["succeeded", "completed"].includes(details.status)) {
    return `
      <div class="generation-result-actions">
        <button class="btn btn-secondary btn-small" type="button" data-action="check-real-generation" data-output-action="preview" data-job-id="${escapeHtml(details.jobId)}">Показать видео</button>
        <button class="btn btn-small" type="button" data-action="check-real-generation" data-output-action="download" data-job-id="${escapeHtml(details.jobId)}">Скачать MP4</button>
        <button class="btn btn-secondary btn-small" type="button" data-action="check-real-generation" data-output-action="open" data-job-id="${escapeHtml(details.jobId)}">Открыть отдельно</button>
        <a class="btn btn-secondary btn-small" href="#/workspace/review">Проверить контент</a>
      </div>
    `;
  }
  if (details.status === "failed" || details.status === "cancelled") {
    const canRepeat = canRepeatRealGeneration(details.jobId);
    return canRepeat
      ? `<div class="generation-result-actions"><button class="btn btn-secondary btn-small" type="button" data-action="repeat-real-generation" data-job-id="${escapeHtml(details.jobId)}">Создать новый вариант</button></div>`
      : "";
  }
  return `<div class="generation-result-actions"><button class="btn btn-secondary btn-small" type="button" data-action="check-real-generation" data-output-action="status" data-job-id="${escapeHtml(details.jobId)}">Проверить сейчас</button></div>`;
}

function generationCostMarkup(details) {
  const estimated = details.estimatedMinor === null ? "—" : formatGenerationUsd(details.estimatedMinor);
  const terminalWithoutCharge = ["failed", "cancelled"].includes(details.status) && details.actualMinor === 0;
  const providerAccepted = ["submitted", "processing", "running", "saving", "uploading", "succeeded", "completed"].includes(details.status);
  const provisional = terminalWithoutCharge
    ? formatGenerationUsd(0)
    : providerAccepted && details.actualMinor !== null
      ? formatGenerationUsd(details.actualMinor)
      : estimated;
  const provisionalLabel = terminalWithoutCharge
    ? "Резерв освобождён"
    : providerAccepted
      ? "Учтено предварительно"
      : "Зарезервировано";
  return `<div class="generation-cost"><span><small>Оценка запуска</small><strong>${estimated}</strong></span><span><small>${provisionalLabel}</small><strong>${provisional}</strong></span><em>Не является итоговым счётом провайдера</em></div>`;
}

function realGenerationJobsFromBatches(batches = listFrom(state.sections.generation.data || {}, "batches")) {
  return batches
    .map(generationBatchDetails)
    .filter((details) =>
      details.real
      && details.jobId
      && !details.reconciliationRequired
      && REAL_GENERATION_ACTIVE_STATUSES.has(details.status)
    );
}

function realGenerationReconciliationJobsFromBatches(
  batches = listFrom(state.sections.generation.data || {}, "batches"),
) {
  return batches
    .map(generationBatchDetails)
    .filter((details) => details.real && details.jobId && details.reconciliationRequired);
}

function canRepeatRealGeneration(jobId) {
  const normalizedJobId = String(jobId || "");
  if (!normalizedJobId || !state.realGenerationDrafts.has(normalizedJobId)) return false;
  const batch = listFrom(state.sections.generation.data || {}, "batches")
    .find((item) => String(item?.parameters?.job_id || "") === normalizedJobId);
  if (!batch) return false;
  const details = generationBatchDetails(batch);
  return !details.reconciliationRequired
    && ["succeeded", "completed", "failed", "cancelled"].includes(details.status);
}

function stopRealGenerationPolling() {
  if (state.realGenerationPollTimer !== null) {
    window.clearTimeout(state.realGenerationPollTimer);
    state.realGenerationPollTimer = null;
  }
}

function scheduleRealGenerationPolling(delayMs = REAL_GENERATION_POLL_INTERVAL_MS) {
  stopRealGenerationPolling();
  if (
    state.route.path !== "/workspace/generation"
    || document.visibilityState !== "visible"
    || !state.session
    || state.realGenerationPollInFlight
    || !realGenerationJobsFromBatches().length
  ) return;
  const delay = Math.max(250, Number(delayMs) || REAL_GENERATION_POLL_INTERVAL_MS);
  state.realGenerationPollTimer = window.setTimeout(runRealGenerationPolling, delay);
}

async function runRealGenerationPolling() {
  state.realGenerationPollTimer = null;
  if (state.route.path !== "/workspace/generation" || document.visibilityState !== "visible") return;
  const pollingWindow = boundedRoundRobinWindow(
    realGenerationJobsFromBatches(),
    state.realGenerationPollCursor,
    4,
  );
  const activeJobs = pollingWindow.items;
  state.realGenerationPollCursor = pollingWindow.nextCursor;
  if (!activeJobs.length || state.realGenerationPollInFlight) return;
  state.realGenerationPollInFlight = true;
  try {
    await Promise.allSettled(activeJobs.map(async ({ jobId }) => {
      const outcome = await waitForRealGenerationStatus(jobId, REAL_GENERATION_SOFT_TIMEOUT_MS, "auto");
      if (outcome.timedOut) markGenerationStatusStillRunning(jobId);
    }));
  } finally {
    state.realGenerationPollInFlight = false;
    scheduleRealGenerationPolling();
  }
}

function requestRealGenerationStatus(jobId, source = "manual") {
  const normalizedJobId = String(jobId || "");
  const existing = state.realGenerationStatusRequests.get(normalizedJobId);
  if (existing?.promise) return existing.promise;
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const promise = state.api.realGenerationStatus(normalizedJobId);
  state.realGenerationStatusRequests.set(normalizedJobId, { promise, source });
  promise.then(
    (result) => {
      if (requestEpoch === state.dataEpoch && requestUserId === state.user?.id) {
        applyRealGenerationResult(normalizedJobId, result, { source });
      }
    },
    (error) => {
      if (requestEpoch === state.dataEpoch && requestUserId === state.user?.id) {
        applyRealGenerationStatusError(normalizedJobId, error);
      }
    },
  ).finally(() => {
    const current = state.realGenerationStatusRequests.get(normalizedJobId);
    if (current?.promise === promise) state.realGenerationStatusRequests.delete(normalizedJobId);
    scheduleRealGenerationPolling();
  });
  return promise;
}

function waitForRealGenerationStatus(jobId, timeoutMs, source = "manual") {
  return withSoftTimeoutResult(requestRealGenerationStatus(jobId, source), timeoutMs);
}

function withSoftTimeoutResult(operation, timeoutMs) {
  let timerId;
  const timeout = new Promise((resolve) => {
    timerId = window.setTimeout(() => resolve({ timedOut: true, result: null }), timeoutMs);
  });
  return Promise.race([
    Promise.resolve(operation).then((result) => ({ timedOut: false, result })),
    timeout,
  ]).finally(() => window.clearTimeout(timerId));
}

function applyRealGenerationResult(jobId, result, options = {}) {
  const job = result?.job && typeof result.job === "object" ? result.job : null;
  if (!job || String(job.id || "") !== String(jobId || "")) return;
  const previous = state.realGenerationResults.get(jobId);
  const signedUrl = String(result?.signed_url || "");
  const safeSignedUrl = signedUrl && isTrustedGenerationDownload(signedUrl) ? signedUrl : "";
  const checkedAt = new Date().toISOString();
  state.realGenerationResults.set(jobId, {
    job: { ...job },
    signedUrl: safeSignedUrl || previous?.signedUrl || "",
    signedUrlIssuedAt: safeSignedUrl ? Date.now() : (previous?.signedUrlIssuedAt || 0),
    checkedAt,
    transientError: "",
  });
  patchGenerationBatch(jobId, job);

  const previousStatus = String(previous?.job?.status || "").toLowerCase();
  const nextStatus = String(job.status || "").toLowerCase();
  const previousReconciliationRequired = normalizeBoolean(
    previous?.job?.reconciliation_required,
  );
  const nextReconciliationRequired = normalizeBoolean(job.reconciliation_required);
  if (
    previousStatus !== nextStatus
    && ["queued", "submitted", "failed", "cancelled", "succeeded", "completed"].includes(nextStatus)
  ) {
    void loadGenerationSpendOverview({ silent: true, force: true });
  }
  if (options.source === "auto" && previousStatus && previousStatus !== nextStatus) {
    if (["succeeded", "completed"].includes(nextStatus)) {
      toast("Платный ролик готов. Он доступен в очереди для просмотра и скачивания.", "success");
    } else if (nextStatus === "failed") {
      toast(generationFailureMessage(job.failure_code), "error");
    }
  }
  if (
    options.source === "auto"
    && !previousReconciliationRequired
    && nextReconciliationRequired
  ) {
    toast("Автопроверка платного запуска остановлена безопасно. Нужна ручная сверка владельцем или администратором; новый запуск не создавайте.", "info");
  }
  if (options.renderNow !== false && state.route.path === "/workspace/generation") render();
}

function applyRealGenerationStatusError(jobId, error) {
  const previous = state.realGenerationResults.get(jobId) || {};
  const safeMessage = error?.isUserSafe === true || error?.name === "CreatorApiError"
    ? String(error.message || "Сервис временно недоступен.")
    : "Связь с видеосервисом временно прервалась. Проверка повторится автоматически.";
  state.realGenerationResults.set(jobId, {
    ...previous,
    checkedAt: new Date().toISOString(),
    transientError: safeMessage,
  });
  if (state.route.path === "/workspace/generation") render();
}

function markGenerationStatusStillRunning(jobId) {
  const previous = state.realGenerationResults.get(jobId) || {};
  state.realGenerationResults.set(jobId, {
    ...previous,
    transientError: "Проверка продолжается в фоне. Новый платный запуск не требуется.",
  });
  if (state.route.path === "/workspace/generation") render();
}

function patchGenerationBatch(jobId, job) {
  const batches = listFrom(state.sections.generation.data || {}, "batches");
  const batch = batches.find((item) => String(item?.parameters?.job_id || "") === String(jobId));
  if (!batch) return;
  batch.status = String(job.status || batch.status || "queued");
  if (["succeeded", "completed"].includes(String(job.status || "").toLowerCase())) {
    batch.total_created = 1;
    batch.total_accepted = 1;
  }
  batch.parameters = {
    ...(batch.parameters || {}),
    job_status: job.status,
    actual_cost_minor: job.actual_cost_minor,
    failure_code: job.failure_code,
    submission_state: job.submission_state,
    reconciliation_required: job.reconciliation_required,
    reconciliation_incident_id: job.reconciliation_incident_id,
    reconciliation_required_at: job.reconciliation_required_at,
    reconciliation_reason_code: job.reconciliation_reason_code,
    reconciliation_resolution: job.reconciliation_resolution,
    can_reconcile: job.can_reconcile,
  };
}

function trustedCachedGenerationUrl(jobId) {
  const cached = state.realGenerationResults.get(String(jobId || ""));
  if (!cached?.signedUrl || !cached.signedUrlIssuedAt) return "";
  if (Date.now() - cached.signedUrlIssuedAt > REAL_GENERATION_URL_MAX_AGE_MS) return "";
  return isTrustedGenerationDownload(cached.signedUrl) ? cached.signedUrl : "";
}

function generationFailureMessage(code) {
  const messages = {
    provider_configuration_error: "Видеосервис временно не настроен. Списание не подтверждено; перед новым запуском обратитесь к руководителю.",
    provider_authentication_failed: "Видеосервис отклонил служебный доступ. Перед новым запуском обратитесь к руководителю.",
    provider_credits_unavailable: "На балансе видеосервиса недостаточно кредитов. Пополните баланс и создайте новый запуск позже.",
    provider_rate_limited: "Видеосервис временно ограничил частоту запросов. Подождите и повторите новым запуском позже.",
    provider_request_rejected: "Видеосервис отклонил исходник или сценарий. Проверьте фото и текст перед новым запуском.",
    provider_request_failed: "Видеосервис не смог принять запрос. Сначала проверьте фактическую стоимость, затем решите, нужен ли новый запуск.",
    provider_task_failed: "Видеосервис начал работу, но не смог создать ролик. Стоимость показана рядом с задачей.",
    provider_timeout: "Видеосервис не завершил ролик вовремя. Новый запуск делайте только после проверки стоимости.",
    provider_response_invalid: "Видеосервис вернул неполный ответ. Обратитесь к руководителю до нового платного запуска.",
    provider_submission_not_found: "Руководитель подтвердил, что Runway task для этого запуска отсутствует. Списание не зафиксировано; новый запуск создаётся отдельно с новым подтверждением цены.",
    output_download_failed: "Ролик создан у видеосервиса, но портал пока не смог забрать файл. Повторите проверку статуса без нового запуска.",
    output_validation_failed: "Полученный файл не прошёл безопасную проверку. Обратитесь к руководителю до нового запуска.",
    output_upload_failed: "Ролик создан, но пока не сохранён в защищённой папке. Повторите проверку без нового запуска.",
    internal_error: "Портал не завершил обработку ролика. Обратитесь к руководителю и не запускайте оплату повторно.",
  };
  return messages[String(code || "")] || "Видеосервис не смог создать ролик. Проверьте фактическую стоимость перед новым платным запуском.";
}

function firstFiniteNumber(...values) {
  for (const value of values) {
    if (value === null || value === undefined || value === "") continue;
    const numeric = Number(value);
    if (Number.isFinite(numeric) && numeric >= 0) return numeric;
  }
  return null;
}

function formatGenerationUsd(minor) {
  const numeric = Number(minor);
  return Number.isFinite(numeric) ? `$${(numeric / 100).toFixed(2)}` : "—";
}

function realGenerationDraftFromPayload(payload, mode) {
  return {
    generation_mode: mode,
    campaign_id: payload.campaign_id,
    sku: payload.sku,
    product_name: payload.product_name,
    count: "1",
    format: payload.format,
    brief: payload.brief,
    media_ids: [...payload.media_ids],
    platform: payload.platform,
    destination_ref: payload.destination_ref,
    assignee_id: payload.assignee_id || "",
    payout_rub: Number(payload.payout_minor || 0) / 100,
  };
}

function restoreRealGenerationDraft(jobId) {
  const draft = state.realGenerationDrafts.get(String(jobId || ""));
  const form = document.querySelector("#mock-batch-form");
  if (!draft || !form) {
    toast("Сохранённые поля этого запуска недоступны. Заполните новый запуск вручную.", "info");
    return;
  }
  const setValue = (name, value) => {
    const field = form.elements[name];
    if (field) field.value = String(value ?? "");
  };
  setValue("generation_mode", draft.generation_mode);
  setValue("campaign_id", draft.campaign_id);
  for (const name of ["sku", "product_name", "count", "format", "brief", "platform", "destination_ref", "assignee_id", "payout_rub"]) {
    setValue(name, draft[name]);
  }
  form.querySelectorAll('input[name="media_id"]').forEach((input) => {
    input.checked = draft.media_ids.includes(input.value);
  });
  if (form.elements.real_spend_confirmation) form.elements.real_spend_confirmation.checked = false;
  form.dataset.dirty = "true";
  syncGenerationModeForm(form);
  form.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
  window.setTimeout(() => form.elements.brief?.focus({ preventScroll: true }), prefersReducedMotion() ? 0 : 350);
  toast("Поля восстановлены. Измените сценарий и заново подтвердите стоимость перед новым запуском.", "success");
}

function openGenerationWaitingWindow() {
  try {
    const opened = window.open("about:blank", "_blank");
    if (!opened) return null;
    opened.opener = null;
    opened.document.title = "Готовим ролик";
    opened.document.body.textContent = "Проверяем защищённую ссылку на ролик…";
    return opened;
  } catch {
    return null;
  }
}

function openGenerationOutput(url, pendingWindow = null) {
  if (pendingWindow && !pendingWindow.closed) {
    pendingWindow.location.replace(url);
    return;
  }
  openExternalDownload(url);
}

function downloadGenerationOutput(url, jobId) {
  const link = document.createElement("a");
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.referrerPolicy = "no-referrer";
  link.download = `contentengine-${String(jobId || "video")}.mp4`;
  document.body.append(link);
  link.click();
  link.remove();
}

function canDecideContentReview() {
  return ["owner", "admin", "producer", "reviewer"].includes(state.bootstrap?.membership?.role);
}

function contentReviewDraftStorageKey() {
  const organizationId = String(state.bootstrap?.organization?.id || "").trim().toLowerCase();
  const userId = String(state.user?.id || "").trim().toLowerCase();
  if (!contentReviewUuid(organizationId) || !contentReviewUuid(userId)) return "";
  return `contentengine.content-review-draft.v${CONTENT_REVIEW_DRAFT_STORAGE_VERSION}:${organizationId}:${userId}`;
}

function persistContentReviewDraft(form, { durableEvidence = state.contentReview.durableEvidence } = {}) {
  const key = contentReviewDraftStorageKey();
  if (!key || !(form instanceof HTMLFormElement)) return false;
  const input = readContentReviewForm(form);
  const evidence = usableContentReviewEvidence(durableEvidence, {
    mediaId: input.media_id,
  });
  state.contentReview.durableEvidence = evidence;
  try {
    window.localStorage.setItem(key, JSON.stringify({
      version: CONTENT_REVIEW_DRAFT_STORAGE_VERSION,
      updatedAt: new Date().toISOString(),
      input,
      evidence,
    }));
    const status = form.querySelector("[data-content-review-draft-status]");
    if (status) status.textContent = evidence?.status === "commit_pending"
      ? "Кадры уже загружены; подтверждение evidence безопасно повторится без новой загрузки."
      : evidence
        ? "Черновик и сохранённый evidence готовы к фоновому запуску."
        : "Черновик сохранён в этом браузере.";
    return true;
  } catch {
    const status = form.querySelector("[data-content-review-draft-status]");
    if (status) status.textContent = "Браузер запретил локальное сохранение. Не закрывайте форму до запуска.";
    return false;
  }
}

function restoreContentReviewDraft() {
  const form = document.querySelector("#content-review-form");
  const key = contentReviewDraftStorageKey();
  if (!(form instanceof HTMLFormElement) || !key) return;
  let draft;
  try {
    draft = JSON.parse(window.localStorage.getItem(key) || "null");
  } catch {
    draft = null;
  }
  const updatedAt = Date.parse(String(draft?.updatedAt || ""));
  if (
    !draft
    || draft.version !== CONTENT_REVIEW_DRAFT_STORAGE_VERSION
    || !draft.input
    || typeof draft.input !== "object"
    || Array.isArray(draft.input)
    || !Number.isFinite(updatedAt)
    || Date.now() - updatedAt > CONTENT_REVIEW_DRAFT_MAX_AGE_MS
  ) {
    if (draft) clearContentReviewDraft();
    return;
  }
  const textFields = [
    "platform", "content_kind", "product_category", "caption_text",
    "script_text", "advertiser_name", "erid", "people_present",
  ];
  for (const name of textFields) {
    const control = form.elements.namedItem(name);
    if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement || control instanceof HTMLTextAreaElement) {
      control.value = String(draft.input[name] ?? "");
    }
  }
  const mediaControl = Array.from(form.querySelectorAll('input[name="media_id"]'))
    .find((control) => String(control.value || "") === String(draft.input.media_id || ""));
  if (mediaControl instanceof HTMLInputElement) mediaControl.checked = true;
  const booleanFields = [
    "rights_confirmed", "claims_verified", "ad_label_confirmed", "ord_confirmed",
    "audience_over_10000", "rkn_registered", "person_consent_confirmed",
    "external_ai_processing_confirmed", "ai_generated", "ai_disclosure_confirmed",
    "captions_confirmed", "mandatory_warning_confirmed",
  ];
  for (const name of booleanFields) {
    const control = form.elements.namedItem(name);
    if (control instanceof HTMLInputElement) control.checked = draft.input[name] === true;
  }
  state.contentReview.durableEvidence = usableContentReviewEvidence(draft.evidence, {
    mediaId: String(draft.input.media_id || ""),
  });
  syncContentReviewFormVisibility(form);
  form.dataset.dirty = "true";
  const status = form.querySelector("[data-content-review-draft-status]");
  if (status) status.textContent = state.contentReview.durableEvidence?.status === "commit_pending"
    ? "Черновик восстановлен; подтвердим уже загруженные кадры без повторной загрузки."
    : state.contentReview.durableEvidence
      ? "Черновик восстановлен; сохранённый evidence будет использован повторно."
      : "Черновик восстановлен из этого браузера.";
}

function clearContentReviewDraft() {
  const key = contentReviewDraftStorageKey();
  if (key) {
    try {
      window.localStorage.removeItem(key);
    } catch {
      // A completed server-side start must not fail because local storage is unavailable.
    }
  }
  state.contentReview.durableEvidence = null;
}

function usableContentReviewEvidence(value, { mediaId = "", mediaSha256 = "" } = {}) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const evidenceId = String(value.evidenceId || value.evidence_id || "").trim().toLowerCase();
  const storedMediaId = String(value.mediaId || value.media_id || "").trim().toLowerCase();
  const storedSha256 = String(value.mediaSha256 || value.media_sha256 || "").trim().toLowerCase();
  const expiresAt = String(value.expiresAt || value.expires_at || "").trim();
  const technicalMetrics = value.technicalMetrics || value.technical_metrics;
  const status = String(value.status || "ready").trim().toLowerCase();
  if (
    !contentReviewUuid(evidenceId)
    || !contentReviewUuid(storedMediaId)
    || storedMediaId !== String(mediaId || storedMediaId).trim().toLowerCase()
    || (mediaSha256 && storedSha256 !== String(mediaSha256).trim().toLowerCase())
    || !/^[0-9a-f]{64}$/u.test(storedSha256)
    || !Number.isFinite(Date.parse(expiresAt))
    || Date.parse(expiresAt) <= Date.now() + 30_000
    || !technicalMetrics
    || typeof technicalMetrics !== "object"
    || Array.isArray(technicalMetrics)
    || String(technicalMetrics.source_type || "").toLowerCase() !== "video"
    || !["ready", "commit_pending"].includes(status)
  ) return null;
  const normalized = {
    status,
    evidenceId,
    mediaId: storedMediaId,
    mediaSha256: storedSha256,
    expiresAt,
    technicalMetrics,
  };
  if (status === "ready") return normalized;

  const commitIdempotencyKey = String(
    value.commitIdempotencyKey || value.commit_idempotency_key || "",
  ).trim().toLowerCase();
  const frames = Array.isArray(value.frames) ? value.frames : [];
  const normalizedFrames = frames.map((frame) => ({
    object_name: String(frame?.object_name || "").trim(),
    sha256: String(frame?.sha256 || "").trim().toLowerCase(),
    size_bytes: Number(frame?.size_bytes),
    timecode_seconds: Math.round(Number(frame?.timecode_seconds) * 1_000) / 1_000,
  }));
  const storagePrefix = `${String(state.bootstrap?.organization?.id || "").trim().toLowerCase()}/${String(state.user?.id || "").trim().toLowerCase()}/review-evidence/${evidenceId}/`;
  if (
    !contentReviewUuid(commitIdempotencyKey)
    || normalizedFrames.length < 4
    || normalizedFrames.length > 5
    || Number(technicalMetrics.frame_count) !== normalizedFrames.length
    || new Set(normalizedFrames.map((frame) => frame.object_name)).size !== normalizedFrames.length
    || normalizedFrames.some((frame, index) => (
      frame.object_name !== `${storagePrefix}frame-${String(index + 1).padStart(2, "0")}.jpg`
      || !/^[0-9a-f]{64}$/u.test(frame.sha256)
      || !Number.isInteger(frame.size_bytes)
      || frame.size_bytes < 128
      || frame.size_bytes > 250_000
      || !Number.isFinite(frame.timecode_seconds)
      || frame.timecode_seconds < 0
      || frame.timecode_seconds > 3_600
      || (index > 0 && frame.timecode_seconds <= normalizedFrames[index - 1].timecode_seconds)
    ))
  ) return null;
  return {
    ...normalized,
    commitIdempotencyKey,
    frames: normalizedFrames,
  };
}

function contentReviewUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(
    String(value || ""),
  );
}

function renderContentReviewSection(sectionState) {
  const catalog = normalizeContentReviewCatalog(sectionState.data || {});
  const routeReviewId = safeWorkspaceRouteEntityId("review");
  const currentId = routeReviewId || String(state.contentReview.record?.id || "");
  const catalogRecord = catalog.runs.find((item) => item.id === currentId);
  if (
    catalogRecord
    && (
      routeReviewId
      || !state.contentReview.record
      || state.contentReview.record.summaryOnly
    )
  ) {
    state.contentReview.record = catalogRecord;
  }
  else if (!state.contentReview.record) {
    state.contentReview.record = catalog.runs.find((item) => contentReviewStatusKind(item.status) === "active")
      || catalog.runs[0]
      || null;
  }
  if (state.contentReview.record && contentReviewStatusKind(state.contentReview.record.status) === "active") {
    window.queueMicrotask(() => scheduleContentReviewPolling());
  }
  window.queueMicrotask(() => {
    bindContentReviewDecisionMedia();
    restoreContentReviewDraft();
    selectPendingContentReviewMedia();
  });
  return `
    <div class="page-wrap content-review-page">
      ${pageHeader(
        "Проверка контента",
        "Проверьте готовый файл до публикации: отдельно качество ролика, отдельно риски и обязательные реквизиты.",
        `<span class="badge badge-info">Решение принимает человек</span>`,
      )}
      ${contentReviewWorkspaceMarkup({
        catalog,
        currentRun: state.contentReview.record,
        phase: state.contentReview.phase,
        error: state.contentReview.error,
        notice: state.contentReview.notice,
        canDecide: canDecideContentReview(),
      })}
    </div>`;
}

function selectPendingContentReviewMedia() {
  const mediaId = String(state.contentReview.pendingMediaId || "");
  if (!mediaId || state.route.path !== "/workspace/review") return;
  const controls = Array.from(document.querySelectorAll('#content-review-form input[name="media_id"]'));
  const target = controls.find((control) => String(control.value || "") === mediaId);
  if (!target) return;
  target.checked = true;
  if (String(state.contentReview.durableEvidence?.mediaId || "") !== mediaId) {
    state.contentReview.durableEvidence = null;
  }
  target.form?.setAttribute("data-dirty", "true");
  persistContentReviewDraft(target.form);
  state.contentReview.pendingMediaId = "";
  target.closest(".content-review-media-option")?.scrollIntoView({ block: "center", behavior: "smooth" });
  target.focus({ preventScroll: true });
}

function bindContentReviewDecisionMedia() {
  const form = document.querySelector(".content-review-decision-form");
  if (!form || form.dataset.mediaBinding === "true") return;
  form.dataset.mediaBinding = "true";
  const media = form.querySelector("[data-content-review-exact-media]");
  const stateNode = form.querySelector("[data-content-review-media-state]");
  const watchControl = form.elements.media_watched_confirmed;
  const submitControls = Array.from(form.querySelectorAll("[data-review-decision-submit]"));
  const setLocked = (status, message) => {
    form.dataset.exactMediaState = status;
    if (watchControl) {
      watchControl.checked = false;
      watchControl.disabled = true;
    }
    submitControls.forEach((control) => {
      control.disabled = true;
    });
    if (stateNode) {
      stateNode.textContent = message;
      stateNode.classList.toggle("is-error", status === "error" || status === "unavailable");
      stateNode.classList.toggle("is-ready", false);
    }
  };
  const setReady = (message) => {
    form.dataset.exactMediaState = "ready";
    if (watchControl) watchControl.disabled = false;
    submitControls.forEach((control) => {
      control.disabled = false;
    });
    if (stateNode) {
      stateNode.textContent = message;
      stateNode.classList.remove("is-error");
      stateNode.classList.add("is-ready");
    }
  };
  if (!media) {
    setLocked("unavailable", stateNode?.textContent || "Точный файл недоступен. Обновите статус проверки.");
    return;
  }
  const mediaSource = () => String(media.currentSrc || media.getAttribute("src") || "");
  const onError = () => setLocked(
    "error",
    "Не удалось открыть точный защищённый файл. Решение заблокировано: обновите статус и попробуйте снова.",
  );
  media.addEventListener("error", onError);
  if (media instanceof HTMLVideoElement) {
    let loadedSource = "";
    const onLoadStart = () => {
      loadedSource = "";
      delete media.dataset.contentReviewEndedSrc;
      setLocked("loading", "Загружаем метаданные MP4. После загрузки воспроизведите этот же файл до конца.");
    };
    const onLoadedMetadata = () => {
      loadedSource = mediaSource();
      if (!loadedSource || !Number.isFinite(media.duration) || media.duration <= 0) {
        onError();
        return;
      }
      media.dataset.contentReviewLoadedSrc = loadedSource;
      setLocked("metadata", "MP4 доступен. Воспроизведите этот же файл до события окончания; затем подтвердите личный просмотр.");
    };
    const onEnded = () => {
      const endedSource = mediaSource();
      if (!loadedSource || endedSource !== loadedSource || media.dataset.contentReviewLoadedSrc !== endedSource) {
        setLocked("error", "Источник MP4 изменился во время просмотра. Обновите статус и просмотрите точный файл заново.");
        return;
      }
      media.dataset.contentReviewEndedSrc = endedSource;
      setReady("Браузер получил событие окончания для этого MP4. Теперь подтвердите личную проверку звука и субтитров.");
    };
    media.addEventListener("loadstart", onLoadStart);
    media.addEventListener("loadedmetadata", onLoadedMetadata);
    media.addEventListener("ended", onEnded);
    media.addEventListener("emptied", onLoadStart);
    if (media.readyState >= HTMLMediaElement.HAVE_METADATA) onLoadedMetadata();
    else setLocked("loading", "Загружаем метаданные MP4. После загрузки воспроизведите этот же файл до конца.");
    return;
  }
  if (media instanceof HTMLImageElement) {
    const onLoad = () => {
      if (!media.naturalWidth || !media.naturalHeight) {
        onError();
        return;
      }
      setReady("Изображение загружено. Осмотрите точный файл и подтвердите личную проверку.");
    };
    media.addEventListener("load", onLoad);
    if (media.complete) {
      if (media.naturalWidth > 0) onLoad();
      else onError();
    } else {
      setLocked("loading", "Проверяем доступность точного изображения.");
    }
  }
}

function contentReviewExactMediaReady(form) {
  if (form?.dataset.exactMediaState !== "ready") return false;
  const media = form.querySelector("[data-content-review-exact-media]");
  if (media instanceof HTMLVideoElement) {
    const currentSource = String(media.currentSrc || media.getAttribute("src") || "");
    return Boolean(
      currentSource
      && media.dataset.contentReviewLoadedSrc === currentSource
      && media.dataset.contentReviewEndedSrc === currentSource
      && media.ended,
    );
  }
  return media instanceof HTMLImageElement && media.complete && media.naturalWidth > 0;
}

function stopContentReviewPolling() {
  if (state.contentReview.pollTimer !== null) {
    window.clearTimeout(state.contentReview.pollTimer);
    state.contentReview.pollTimer = null;
  }
}

function scheduleContentReviewPolling(delay = CONTENT_REVIEW_POLL_INTERVAL_MS) {
  stopContentReviewPolling();
  const record = state.contentReview.record;
  if (
    state.route.path !== "/workspace/review"
    || document.visibilityState !== "visible"
    || !record?.id
    || contentReviewStatusKind(record.status) !== "active"
    || ["preparing", "saving_evidence", "queueing", "starting", "refreshing", "deciding"].includes(state.contentReview.phase)
  ) return;
  state.contentReview.pollTimer = window.setTimeout(() => {
    state.contentReview.pollTimer = null;
    pollContentReviewStatus({ silent: true });
  }, Math.max(250, Number(delay) || CONTENT_REVIEW_POLL_INTERVAL_MS));
}

async function pollContentReviewStatus({ silent = false, refreshMedia = false } = {}) {
  const review = state.contentReview;
  const reviewId = String(review.record?.id || "");
  if (!reviewId || ["preparing", "saving_evidence", "queueing", "starting", "deciding"].includes(review.phase)) return;
  const requestId = review.requestId + 1;
  review.requestId = requestId;
  if (!silent) {
    review.phase = "refreshing";
    review.error = "";
    renderWorkspace("review");
  }
  try {
    let raw = await withUiTimeout(
      state.api.contentReviewStatus(reviewId),
      WORKSPACE_REQUEST_TIMEOUT_MS,
      "content_review_status_timeout",
    );
    const returnedStatus = String(
      raw?.run?.status
      || raw?.review?.status
      || raw?.data?.run?.status
      || raw?.data?.review?.status
      || "",
    );
    if (refreshMedia || contentReviewStatusKind(returnedStatus) === "ready") {
      raw = await hydratePrivateMedia(raw, { refreshSignedUrls: true });
    }
    if (requestId !== review.requestId || reviewId !== String(review.record?.id || "")) return;
    const previousKind = contentReviewStatusKind(review.record?.status);
    review.record = normalizeContentReviewRun(raw, review.record);
    const kind = contentReviewStatusKind(review.record.status);
    review.phase = kind === "active" ? "processing" : kind === "failed" ? "error" : "idle";
    review.error = kind === "failed"
      ? (review.record.failureMessage || "Проверка завершилась с ошибкой. Исходный материал не потерян.")
      : "";
    upsertContentReviewRun(review.record);
    if (previousKind === "active" && kind === "ready") {
      review.notice = "Проверка завершена. Прочитайте блокеры и рекомендации, затем зафиксируйте решение человека.";
      await track("content_review_completed", {
        review_id: review.record.id,
        overall_score: review.record.result.overallScore,
        compliance_status: review.record.result.complianceStatus,
        blockers_count: review.record.result.blockersCount,
      });
    }
  } catch (error) {
    if (requestId !== review.requestId) return;
    review.phase = contentReviewStatusKind(review.record?.status) === "active" ? "processing" : "error";
    review.error = String(error?.message || "") === "content_review_status_timeout"
      ? "Сервер не ответил вовремя. Проверка не потеряна — статус обновится автоматически."
      : actionErrorMessage(error);
  }
  if (state.route.path === "/workspace/review") renderWorkspace("review");
  scheduleContentReviewPolling();
}

function upsertContentReviewRun(run) {
  const target = state.sections.review;
  if (!target?.data || !run?.id) return;
  const current = listFrom(target.data, "runs", "recent_reviews", "reviews", "history", "items");
  const next = [run, ...current.filter((item) => String(item?.id || item?.review_id || "") !== String(run.id))];
  if (Array.isArray(target.data.runs) || !["recent_reviews", "reviews", "history", "items"].some((key) => Array.isArray(target.data[key]))) {
    target.data = { ...target.data, runs: next };
  } else {
    const key = ["recent_reviews", "reviews", "history", "items"].find((candidate) => Array.isArray(target.data[candidate]));
    target.data = { ...target.data, [key]: next };
  }
}

function renderMyWorkSection(sectionState) {
  return myWorkWorkspaceMarkup({
    work: sectionState.data || {},
    notifications: state.myWork.notifications,
    savedViews: state.myWork.savedViews,
    filters: state.myWork.filters,
    selectedViewId: state.myWork.selectedViewId,
    notice: state.myWork.notice,
    error: state.myWork.error || (sectionState.status === "error"
      ? "Единая очередь временно не загрузилась. Обновите раздел."
      : ""),
    loadingMore: state.myWork.loadingMore,
  });
}

function renderPlacementSection(sectionState) {
  const data = sectionState.data || {};
  const items = listFrom(data, "placements", "items", "tasks");
  const openCount = items.filter(isActionablePlacement).length;
  return `
    <div class="page-wrap">
      ${pageHeader("Публикации", "Скачайте одобренный ролик, разместите его на указанной площадке и сохраните ссылку на сам пост.", `<span class="badge badge-info">${openCount} ждут действия</span>`)}
      ${alertMarkup("Нужна публичная ссылка именно на опубликованный пост. Ссылка на карточку товара не завершает задачу.", "info")}
      <div class="placement-list" style="margin-top:18px">
        ${sectionBody(sectionState, items.length ? items.map(placementCard).join("") : emptyState("↗", "Публиковать пока нечего", "Ничего делать не нужно: здесь появится только одобренный ролик с назначенной площадкой.", { href: "#/workspace/tasks", label: "Проверить задачи" }))}
      </div>
    </div>
  `;
}

function placementCard(item) {
  const complete = isCompletedPlacement(item);
  const actionable = isActionablePlacement(item);
  return `
    <article class="card placement-card" data-placement-id="${escapeHtml(item.id || item.placement_id || "")}" tabindex="-1">
      <div class="placement-top">
        <div>
          <p class="eyebrow">${escapeHtml(item.platform || item.destination || "Площадка")}</p>
          <h3>${escapeHtml(item.title || item.product_name || `Задача #${item.id}`)}</h3>
          <p>${escapeHtml(item.instructions || "Используйте одобренный файл и описание из задачи.")}</p>
        </div>
        ${statusBadge(item.status || "todo")}
      </div>
      <ul class="checklist">
        <li>Сверить назначенный аккаунт и площадку</li>
        <li>Открыть «Проверку контента» и убедиться, что по этой версии нет нерешённых блокеров</li>
        <li>Проверить в инструкции решение: информационный материал или реклама</li>
        <li>Если это реклама — сверить пометку «Реклама», рекламодателя, идентификатор рекламы (ERID) и разрешение площадки</li>
        <li>Использовать ссылку для перехода, указанную в задаче</li>
        <li>После публикации сохранить ссылку на сам пост</li>
      </ul>
      ${alertMarkup("Если в задаче нет решения по рекламе или обязательных реквизитов, не публикуйте и верните её руководителю. Бирка соцсети не заменяет правовую проверку.", "warning")}
      <p class="tiny"><a href="#/workspace/review">Открыть историю проверки контента →</a></p>
      ${item.tracking_url ? `<p class="tiny"><strong>Ссылка из задачи:</strong> <a href="${safeExternalUrl(item.tracking_url)}" target="_blank" rel="noopener noreferrer">открыть</a></p>` : ""}
      ${complete ? alertMarkup(`Публикация подтверждена: ${item.final_url || "ссылка сохранена"}`, "success") : actionable ? `
        <form class="inline-actions placement-form" data-placement-id="${escapeHtml(item.id)}" novalidate>
          <label class="field" style="flex:1; min-width:250px"><span>Ссылка на опубликованный пост</span><input name="final_url" type="url" required inputmode="url" placeholder="https://…/ваш-пост" /></label>
          <label class="option" style="flex-basis:100%">
            <input type="checkbox" name="compliance_ack" value="confirmed" required />
            <span><strong>Рекламный статус проверен по инструкции задачи</strong><br /><small class="muted">Если это реклама, обязательные реквизиты и площадка подтверждены руководителем; если решения нет — я не публикую.</small></span>
          </label>
          <button class="btn" type="submit" style="align-self:end">Подтвердить публикацию</button>
        </form>
      ` : alertMarkup("Эта публикация закрыта и не требует действий. Если это ошибка, сообщите руководителю.", "info")}
    </article>
  `;
}

function renderStatsSection(sectionState) {
  const data = sectionState.data || {};
  const summary = data.summary || data.metrics || {};
  const summaryScope = data.summary_scope === "page" ? " · по последним загруженным записям" : "";
  const rows = listFrom(data, "publications", "items", "rows");
  const publicationOptions = listFrom(data, "publication_options", "placements", "published_placements");
  const cards = [
    ["Опубликовано", summary.published ?? summary.publications ?? 0, `роликов со ссылкой на пост${summaryScope}`],
    ["Просмотры", summary.views ?? 0, `последний подтверждённый снимок${summaryScope}`],
    ["Переходы", summary.clicks ?? 0, `по ссылкам из задач${summaryScope}`],
    ["CTR", formatPercent(summary.ctr ?? 0), `переходы / просмотры${summaryScope}`],
  ];
  return `
    <div class="page-wrap">
      ${pageHeader("Результаты", "Здесь собраны публикации, просмотры, переходы и заказы с датой последнего обновления.", `<button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="stats">Обновить</button>`)}
      <div class="metrics-grid">${cards.map(([label, value, hint]) => `
        <article class="card metric-card"><span class="metric-label">${label}</span><strong>${typeof value === "number" ? formatNumber(value) : value}</strong><small>${hint}</small></article>
      `).join("")}</div>
      <section class="card card-pad" style="margin-bottom:22px">
        <div class="split-grid split-grid-results">
          <div>
            <p class="eyebrow">Ручной снимок</p>
            <h2 style="font:600 1.5rem/1.2 Georgia,serif; margin:0 0 8px">Зафиксировать цифры на сейчас</h2>
            <p class="muted tiny">Введите <strong>накопительные итоги</strong> публикации, а не прирост за день. Например, если вчера было 900 просмотров, а сегодня 1200 — укажите 1200.</p>
            ${alertMarkup("Результат будет помечен как введённый вручную. Будущие автоматические подключения не сотрут историю.", "info")}
          </div>
          ${publicationOptions.length ? `
            <form id="manual-metric-form" class="form-stack" novalidate>
              <label class="field"><span>Опубликованный ролик *</span><select name="placement_id" required><option value="">Выберите публикацию</option>${publicationOptions.map((item) => `<option value="${escapeHtml(item.id || item.placement_id)}">${escapeHtml(item.title || item.sku || item.final_url || `Публикация #${item.id}`)}</option>`).join("")}</select></label>
              <div class="form-grid-2">
                <label class="field"><span>Просмотры *</span><input name="views" type="number" min="0" step="1" value="0" required /></label>
                <label class="field"><span>Переходы *</span><input name="clicks" type="number" min="0" step="1" value="0" required /></label>
                <label class="field"><span>Заказы *</span><input name="orders" type="number" min="0" step="1" value="0" required /></label>
                <label class="field"><span>Выручка, ₽ *</span><input name="revenue_rub" type="number" min="0" step="0.01" value="0" required /></label>
              </div>
              <label class="field"><span>Когда сняты цифры *</span><input name="observed_at" type="datetime-local" value="${datetimeLocalNow()}" required /></label>
              <button class="btn" type="submit">Сохранить накопительный снимок</button>
            </form>
          ` : alertMarkup("Сначала сохраните ссылку хотя бы на один пост в разделе «Публикации».", "warning")}
        </div>
      </section>
      <section class="card">
        <div class="card-header"><div><p class="eyebrow">По публикациям</p><h2>Измеримые результаты</h2></div><span class="badge">Автоматически · из файла · вручную</span></div>
        ${sectionBody(sectionState, rows.length ? statsTable(rows) : emptyState("◫", "Результатов пока нет", "Сначала опубликуйте одобренный ролик и сохраните ссылку на конкретный пост.", { href: "#/workspace/placement", label: "Проверить публикации" }))}
      </section>
    </div>
  `;
}

function statsTable(items) {
  return `<div class="table-wrap"><table class="data-table">
    <thead><tr><th>Публикация</th><th>Площадка</th><th>Просмотры</th><th>Переходы</th><th>Заказы</th><th>Выручка</th><th>Источник</th><th>Снимок</th></tr></thead>
    <tbody>${items.map((item) => `<tr data-payout-id="${escapeHtml(item.id || item.payout_id || "")}" tabindex="-1">
      <td><strong>${escapeHtml(item.title || item.sku || `#${item.id}`)}</strong>${item.final_url ? `<br /><a class="tiny" href="${safeExternalUrl(item.final_url)}" target="_blank" rel="noopener noreferrer">Открыть пост</a>` : ""}</td>
      <td>${escapeHtml(item.platform || "—")}</td>
      <td>${formatNumber(item.views || 0)}</td>
      <td>${formatNumber(item.clicks || 0)}</td>
      <td>${formatNumber(item.orders || 0)}</td>
      <td>${formatMoney(item.revenue_minor || 0)}</td>
      <td><span class="badge">${escapeHtml(humanMetricSource(item.source))}</span></td>
      <td>${formatDate(item.observed_at || item.captured_at || item.updated_at, true)}</td>
    </tr>`).join("")}</tbody>
  </table></div>`;
}

function renderPayoutsSection(sectionState) {
  const data = sectionState.data || {};
  const items = listFrom(data, "payouts", "items", "rows");
  const canManagePayouts = ["owner", "admin"].includes(state.bootstrap?.membership?.role);
  const totals = data.summary || {};
  const totalsHint = data.summary ? "по серверной сводке" : "в последних 50 начислениях";
  const pendingMinor = totals.pending_minor ?? sumMinor(items.filter((i) => i.status === "pending"));
  const approvedMinor = totals.approved_minor ?? sumMinor(items.filter((i) => i.status === "approved"));
  const paidMinor = totals.paid_minor ?? sumMinor(items.filter((i) => i.status === "paid"));
  return `
    <div class="page-wrap">
      ${pageHeader(
        "Выплаты",
        canManagePayouts
          ? "Проверьте начисление команды, затем отдельно зафиксируйте решение и факт перевода."
          : "Здесь видны только ваши начисления. Решение принимает руководитель; банковские реквизиты в кабинете не хранятся.",
        `<span class="badge">${canManagePayouts ? "Реестр команды" : "Личный реестр"}</span>`,
      )}
      <div class="metrics-grid metrics-grid-three">
        ${[["Ожидает проверки", pendingMinor], ["Одобрено", approvedMinor], ["Выплачено", paidMinor]].map(([label, value]) => `<article class="card metric-card"><span class="metric-label">${label}</span><strong>${formatMoney(value)}</strong><small>${totalsHint}</small></article>`).join("")}
      </div>
      <section class="card">
        <div class="card-header"><div><p class="eyebrow">История</p><h2>Начисления и статусы</h2></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="payouts">Обновить</button></div>
        ${sectionBody(sectionState, items.length ? payoutsTable(items, canManagePayouts) : emptyState("₽", "Начислений пока нет", "Ничего не потеряно: начисление появится после подтверждённой задачи и проверки результата.", { href: "#/workspace/tasks", label: "Проверить задачи" }))}
      </section>
    </div>
  `;
}

function payoutsTable(items, canManagePayouts) {
  return `<div class="table-wrap"><table class="data-table">
    <thead><tr><th>Получатель / основание</th><th>Сумма</th><th>Статус</th><th>Создано</th><th>Оплачено</th>${canManagePayouts ? "<th>Решение</th>" : ""}</tr></thead>
    <tbody>${items.map((item) => `<tr>
      <td>${item.profile_name || item.creator_name ? `<strong>${escapeHtml(item.profile_name || item.creator_name)}</strong><br />` : ""}<span>${escapeHtml(item.reason || item.task_title || `Задача #${item.task_id || item.creator_task_id || "—"}`)}</span></td>
      <td>${formatMoney(item.amount_minor || 0, item.currency || "RUB")}</td>
      <td>${statusBadge(item.status || "pending")}</td>
      <td>${formatDate(item.created_at)}</td><td>${formatDate(item.paid_at)}${item.external_payment_reference ? `<br /><small class="muted">${escapeHtml(item.external_payment_reference)}</small>` : ""}</td>
      ${canManagePayouts ? `<td>${payoutDecisionMarkup(item)}</td>` : ""}
    </tr>`).join("")}</tbody>
  </table></div>`;
}

function payoutDecisionMarkup(item) {
  const payoutId = escapeHtml(item.id || item.payout_id || "");
  const status = String(item.status || "pending").toLowerCase();
  if (String(item.profile_id || "") === String(state.user?.id || "")) {
    return `<span class="muted tiny">Ваше начисление должен проверить другой руководитель</span>`;
  }
  if (status === "pending") {
    return `
      <div class="payout-actions">
        <button class="btn btn-small" type="button" data-action="decide-payout" data-payout-id="${payoutId}" data-decision="approve">Одобрить</button>
        <form class="payout-reject-form" data-payout-id="${payoutId}" novalidate>
          <label class="field"><span>Причина отказа *</span><input name="notes" required minlength="10" maxlength="1000" placeholder="Не меньше 10 символов" /></label>
          <button class="btn btn-secondary btn-small" type="submit">Отклонить</button>
        </form>
      </div>
    `;
  }
  if (status === "approved") {
    return `
      <form class="payout-paid-form form-stack" data-payout-id="${payoutId}" novalidate>
        <label class="field"><span>Номер внешней оплаты *</span><input name="external_payment_reference" required minlength="3" maxlength="180" placeholder="PAY-2026-000123" /></label>
        <button class="btn btn-small" type="submit">Отметить выплаченной</button>
      </form>
    `;
  }
  if (status === "rejected" && item.reason) {
    return `<small class="muted">Причина: ${escapeHtml(item.reason)}</small>`;
  }
  return `<span class="muted tiny">Действий нет</span>`;
}

function renderTasksSection(sectionState) {
  const data = sectionState.data || {};
  const items = listFrom(data, "tasks", "items", "rows");
  return `
    <div class="page-wrap">
      ${pageHeader("Задачи", "Выполняйте только назначенные вам действия. Блокер лучше скрытой ошибки.", `<span class="badge badge-info">${items.filter((i) => !["done", "cancelled"].includes(i.status)).length} активных</span>`)}
      <div class="task-list">
        ${sectionBody(sectionState, items.length ? items.map(taskCard).join("") : emptyState("✓", "Задач пока нет", "Ничего делать не нужно: новая работа появится здесь после назначения руководителем.", { href: "#/workspace/home", label: "Вернуться к обзору" }))}
      </div>
    </div>
  `;
}

function taskCard(item) {
  const checklist = Array.isArray(item.checklist) ? item.checklist : item.checklist_json || [];
  const payoutMinor = Math.max(0, Number(item.payout_minor || 0));
  return `
    <article class="card task-card" data-task-id="${escapeHtml(item.id || item.task_id || "")}" tabindex="-1">
      <div class="task-top">
        <div>
          <p class="eyebrow">${escapeHtml(humanTaskType(item.task_type))} · приоритет ${Number(item.priority || 3)}</p>
          <h3>${escapeHtml(item.title || `Задача #${item.id}`)}</h3>
          <p>${escapeHtml(item.instructions || "Следуйте чек-листу и сохраните результат в этой задаче.")}</p>
        </div>
        ${statusBadge(item.status || "todo")}
      </div>
      <div class="task-facts" aria-label="Условия задачи">
        <span><small>Вознаграждение</small><strong>${formatMoney(payoutMinor, item.currency || "RUB")}</strong></span>
        <span><small>Срок</small><strong>${item.due_at ? formatDate(item.due_at, true) : "Не указан"}</strong></span>
      </div>
      ${checklist.length ? `<ul class="checklist">${checklist.map((point) => `<li>${escapeHtml(typeof point === "string" ? point : point.label || point.title || "Шаг")}</li>`).join("")}</ul>` : ""}
      <div class="inline-actions">
        ${taskActionsMarkup(item)}
      </div>
    </article>
  `;
}

function taskActionsMarkup(item) {
  const taskId = escapeHtml(item.id || "");
  const status = String(item.status || "todo");
  const result = item.result && typeof item.result === "object"
    ? item.result
    : item.result_json && typeof item.result_json === "object"
      ? item.result_json
      : {};
  const manager = ["owner", "admin", "producer", "reviewer"].includes(
    state.bootstrap?.membership?.role,
  );
  const activeRunwayReview = item.task_type === "video_review" &&
    result.provider === "runway" &&
    ["queued", "starting", "submitted", "processing"].includes(
      String(result.generation_status || ""),
    );
  if (activeRunwayReview) {
    return '<span class="muted tiny">Видео создаётся. Статус задачи изменится автоматически.</span>';
  }
  const action = (nextStatus, label, secondary = false) =>
    `<button class="btn ${secondary ? "btn-secondary " : ""}btn-small" type="button" data-action="transition-task" data-task-id="${taskId}" data-status="${nextStatus}">${label}</button>`;
  const generatedVideoReady = item.task_type === "video_review"
    && String(result.generation_status || "").toLowerCase() === "succeeded"
    && String(result.output_media_id || "").trim();
  if (generatedVideoReady && ["submitted", "review"].includes(status)) {
    return `
      <button class="btn btn-small" type="button" data-action="open-generated-content-review" data-media-id="${escapeHtml(result.output_media_id)}">Открыть проверку контента</button>
      ${manager ? action("blocked", "Вернуть с блокером", true) : ""}
    `;
  }

  if (status === "todo") {
    return action("in_progress", "Начать") + action("blocked", "Есть блокер", true);
  }
  if (status === "in_progress") {
    return action("submitted", "Отправить на проверку") + action("blocked", "Есть блокер", true);
  }
  if (status === "blocked") {
    return action("in_progress", "Продолжить после решения блокера");
  }
  if (manager && status === "submitted") {
    return (
      action("review", "Взять на проверку") +
      action("done", "Принять") +
      action("blocked", "Вернуть с блокером", true)
    );
  }
  if (manager && status === "review") {
    return action("done", "Принять") + action("blocked", "Вернуть с блокером", true);
  }
  return "";
}

function renderProductResearchSection() {
  if (!canManageProductResearch()) {
    return `<div class="page-wrap">${alertMarkup("Разбор товара доступен руководителю и продюсеру.", "danger")}</div>`;
  }
  const research = state.productResearch;
  restoreProductResearchSession();
  const mediaState = state.sections.media;
  if (mediaState.status === "idle") {
    window.queueMicrotask(() => loadSection("media", { silent: true, rerenderSection: "research" }));
  }
  const teamState = state.sections.team;
  if (teamState.status === "idle") {
    window.queueMicrotask(() => loadSection("team", { silent: true, rerenderSection: "research" }));
  }
  const media = listFrom(mediaState.data || {}, "media", "items", "artifacts")
    .filter((item) => String(item.mime_type || "").startsWith("image/") || ["product_photo", "packshot"].includes(String(item.kind || "")));
  const statusKind = research.record ? productResearchStatusKind(research.record.status) : "";
  let content;
  if (["starting", "processing"].includes(research.phase) || statusKind === "active") {
    content = productResearchProgressMarkup(research.record, research.error);
  } else if (research.record && ["ready", "approved"].includes(statusKind)) {
    content = productResearchResultMarkup(research.record, {
      saving: research.phase === "saving",
      approving: research.phase === "approving",
      notice: research.notice,
      error: research.error,
      members: productResearchAssignableMembers(),
      defaultAssigneeId: state.user?.id || "",
    });
  } else if (research.phase === "error" && research.record) {
    content = productResearchProgressMarkup(research.record, research.error);
  } else {
    content = productResearchInputMarkup({
      media,
      mediaLoading: ["idle", "loading"].includes(mediaState.status),
      error: research.error,
    });
  }
  return `
    <div class="page-wrap product-research-page">
      ${pageHeader(
        "Разбор товара",
        "Фото, карточка и подтверждённые вводные превращаются в редактируемое ТЗ, три сценария и честную оценку потенциала.",
        `<span class="badge badge-info">Человек утверждает итог</span>`,
      )}
      ${content}
    </div>`;
}

function stopProductResearchPolling() {
  if (state.productResearch.pollTimer) window.clearTimeout(state.productResearch.pollTimer);
  state.productResearch.pollTimer = null;
}

function productResearchRunStorageKey() {
  const userId = String(state.user?.id || "").trim();
  const organizationId = String(state.bootstrap?.organization?.id || state.api?.organizationId || "").trim();
  return userId && organizationId
    ? `${PRODUCT_RESEARCH_RUN_STORAGE_KEY}:${organizationId}:${userId}`
    : "";
}

function persistProductResearchRunId(runId) {
  const key = productResearchRunStorageKey();
  const normalizedRunId = String(runId || "").trim();
  if (!key || !normalizedRunId) return;
  try {
    window.sessionStorage.setItem(key, normalizedRunId);
  } catch {
    // Status recovery remains available inside the current SPA session.
  }
}

function clearProductResearchRunId() {
  const key = productResearchRunStorageKey();
  if (!key) return;
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // A blocked storage API must not prevent starting a fresh research run.
  }
}

function restoreProductResearchSession() {
  const research = state.productResearch;
  if (research.restoreAttempted || research.record) return;
  research.restoreAttempted = true;
  const key = productResearchRunStorageKey();
  if (!key) return;
  let runId = "";
  try {
    runId = String(window.sessionStorage.getItem(key) || "").trim();
  } catch {
    return;
  }
  if (!runId) return;
  research.record = normalizeProductResearch({ run: { id: runId, status: "queued" } });
  research.phase = "processing";
  window.queueMicrotask(() => pollProductResearchStatus({ silent: true }));
}

function scheduleProductResearchPolling(delay = PRODUCT_RESEARCH_POLL_INTERVAL_MS) {
  stopProductResearchPolling();
  if (
    state.route.path !== "/workspace/research"
    || !state.productResearch.record?.id
    || productResearchStatusKind(state.productResearch.record.status) !== "active"
  ) return;
  state.productResearch.pollTimer = window.setTimeout(() => {
    state.productResearch.pollTimer = null;
    pollProductResearchStatus({ silent: true });
  }, Math.max(250, Number(delay) || PRODUCT_RESEARCH_POLL_INTERVAL_MS));
}

async function pollProductResearchStatus({ silent = false } = {}) {
  const research = state.productResearch;
  const runId = String(research.record?.id || "");
  if (!runId || ["starting", "saving", "approving"].includes(research.phase)) return;
  const requestId = research.requestId + 1;
  research.requestId = requestId;
  if (!silent) {
    research.phase = "processing";
    research.error = "";
    renderWorkspace("research");
  }
  try {
    const raw = await withUiTimeout(
      state.api.productResearchStatus(runId),
      WORKSPACE_REQUEST_TIMEOUT_MS,
      "product_research_status_timeout",
    );
    if (requestId !== research.requestId || runId !== String(research.record?.id || "")) return;
    research.record = normalizeProductResearch(raw, research.record);
    const kind = productResearchStatusKind(research.record.status);
    research.phase = kind === "failed" ? "error" : kind === "active" ? "processing" : kind;
    research.error = kind === "failed"
      ? (research.record.failureMessage || "Исследование завершилось с ошибкой. Проверьте вводные или начните новый разбор.")
      : "";
  } catch (error) {
    if (requestId !== research.requestId) return;
    research.phase = "error";
    research.error = String(error?.message || "") === "product_research_status_timeout"
      ? "Сервер не ответил вовремя. Запуск не потерян — проверьте статус ещё раз."
      : actionErrorMessage(error);
  }
  if (state.route.path === "/workspace/research") renderWorkspace("research");
  scheduleProductResearchPolling();
}

function renderMediaSection(sectionState) {
  const data = sectionState.data || {};
  const items = listFrom(data, "media", "items", "artifacts");
  return `
    <div class="page-wrap">
      ${pageHeader("Материалы", "Загрузите точные фото и видео товара. Они появятся при создании ролика и останутся доступны только вашей команде.", `<span class="badge badge-success">Файлы защищены</span>`)}
      <div class="split-grid split-grid-media">
        <section class="card card-pad">
          <p class="eyebrow">Добавить исходник</p>
          <h2 style="font:600 1.45rem/1.2 Georgia,serif; margin:0 0 8px">Точные фото или видео</h2>
          <p class="muted tiny">Файл попадёт в вашу закрытую папку. Максимум ${formatBytes(CONFIG.MAX_UPLOAD_BYTES)}.</p>
          <form id="media-upload-form" class="form-stack" novalidate>
            <div class="upload-zone" data-upload-zone>
              <span class="empty-icon" aria-hidden="true">⇧</span>
              <label for="media-file">Выбрать файл</label>
              <input id="media-file" name="file" type="file" accept="image/jpeg,image/png,image/webp,video/mp4" required />
              <small class="muted">Фото JPG, PNG, WEBP или видео MP4</small>
              <strong id="selected-file-name" style="margin-top:8px"></strong>
            </div>
            <label class="field"><span>Тип материала</span><select name="kind" required><option value="product_photo">Фото товара</option><option value="packshot">Фото упаковки без фона</option><option value="creator_reference">Пример желаемого кадра</option><option value="source_video">Исходное видео</option></select></label>
            <div class="form-stack" data-media-product-fields>
              <div>
                <p class="eyebrow">Привязка к товару</p>
                <p class="muted tiny" id="media-product-fields-hint">Для фото товара и упаковки укажите точный артикул и название. Они создадут или обновят карточку товара команды.</p>
              </div>
              <div class="form-grid-2" aria-describedby="media-product-fields-hint">
                <label class="field">
                  <span>Артикул товара *</span>
                  <input name="sku" required maxlength="120" autocomplete="off" placeholder="Например: WB-12345678" />
                  <small class="field-hint">Скопируйте артикул из карточки товара.</small>
                </label>
                <label class="field">
                  <span>Название товара *</span>
                  <input name="product_name" required minlength="2" maxlength="180" autocomplete="off" placeholder="Точное название и вариант" />
                  <small class="field-hint">Укажите название длиной от 2 до 180 символов.</small>
                </label>
              </div>
            </div>
            <label class="acknowledgement"><input name="rights_confirmed" type="checkbox" required /><span>У команды есть право использовать этот материал.</span></label>
            <button class="btn btn-block" type="submit">Загрузить в защищённую папку</button>
          </form>
        </section>
        <section>
          <div class="inline-actions" style="justify-content:space-between; margin-bottom:14px"><div><p class="eyebrow">Ваши файлы</p><h2 style="font:600 1.55rem/1.2 Georgia,serif; margin:0">${items.length} материалов</h2></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="media">Обновить</button></div>
          ${sectionBody(sectionState, items.length ? `<div class="media-grid">${items.map(mediaCard).join("")}</div>` : emptyState("▧", "Материалов пока нет", "Добавьте точное фото товара — после загрузки оно станет доступно при создании видео.", { target: "media-upload-form", label: "Выбрать точное фото" }))}
        </section>
      </div>
    </div>
  `;
}

function mediaCard(item) {
  const url = safeExternalUrl(item.signed_url || item.access_url || item.preview_url || "");
  const mime = String(item.mime_type || "");
  let preview = `<span aria-hidden="true">${mime.startsWith("video/") ? "▶" : "▧"}</span>`;
  if (url !== "#") {
    if (mime.startsWith("image/")) preview = `<img src="${url}" alt="${escapeHtml(item.original_filename || "Исходник")}" loading="lazy" />`;
    else if (mime === "video/mp4") preview = `<video src="${url}" preload="none" controls></video>`;
  }
  return `
    <article class="card media-card">
      <div class="media-preview">${preview}</div>
      <div class="media-info">
        <strong title="${escapeHtml(item.original_filename || "Файл")}">${escapeHtml(item.original_filename || item.name || "Файл")}</strong>
        <small>${escapeHtml(humanMediaKind(item.kind))} · ${formatBytes(item.size_bytes || 0)}</small>
        <div class="inline-actions" style="margin-top:10px">${url !== "#" ? `<a class="btn btn-secondary btn-small" href="${url}" target="_blank" rel="noopener noreferrer">Открыть</a>` : ""}<a class="btn btn-secondary btn-small" href="#/workspace/review">Проверить</a>${statusBadge(item.status || "ready")}</div>
      </div>
    </article>
  `;
}

function renderFeedbackSection(sectionState) {
  const data = sectionState.data || {};
  const items = listFrom(data, "feedback", "items", "requests");
  return `
    <div class="page-wrap">
      ${pageHeader("Помощь и идеи", "Опишите, что мешает работе или что стоит улучшить. Не добавляйте пароли, коды и платёжные данные.", `<span class="badge">Связь с командой</span>`)}
      <div class="split-grid">
        <section class="card card-pad">
          <p class="eyebrow">Новый запрос</p>
          <h2 style="font:600 1.5rem/1.2 Georgia,serif; margin:0 0 8px">Что мешает выполнить работу?</h2>
          <form id="feedback-form" class="form-stack" style="margin-top:18px" novalidate>
            <div class="feedback-form-grid">
              <label class="field"><span>Тип</span><select name="category"><option value="interface">Интерфейс</option><option value="generation">Создание видео</option><option value="quality">Качество</option><option value="funnel">Публикации</option><option value="social_data">Данные соцсетей</option><option value="payouts">Выплаты</option><option value="wb_aliases">Артикулы WB</option><option value="analytics">Результаты</option><option value="training">Обучение</option><option value="other">Другое</option></select></label>
              <label class="field"><span>Раздел</span><select name="section">${visibleWorkspaceTabs().filter(([key]) => !["home", "team"].includes(key)).map(([key, label]) => `<option value="${key}">${label}</option>`).join("")}</select></label>
              <label class="field field-wide"><span>Короткий заголовок *</span><input name="title" required maxlength="180" placeholder="Например: не вижу точное фото упаковки" /></label>
              <label class="field field-wide"><span>Что произошло и какой результат нужен *</span><textarea name="description" required minlength="5" maxlength="2000" placeholder="Опишите шаги без паролей, токенов и платёжных реквизитов"></textarea></label>
            </div>
            <button class="btn" type="submit">Отправить запрос</button>
          </form>
        </section>
        <section>
          <div class="inline-actions" style="justify-content:space-between; margin-bottom:14px"><div><p class="eyebrow">Ваши запросы</p><h2 style="font:600 1.5rem/1.2 Georgia,serif; margin:0">История</h2></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="feedback">Обновить</button></div>
          <div class="feedback-list">${sectionBody(sectionState, items.length ? items.map(feedbackCard).join("") : emptyState("+", "Запросов пока нет", "Если всё понятно — отлично. Если нет, расскажите прямо здесь."))}</div>
        </section>
      </div>
    </div>
  `;
}

function renderTeamSection(sectionState) {
  if (!canManageTeam()) {
    return `<div class="page-wrap">${alertMarkup("Управление командой доступно только руководителю.", "danger")}</div>`;
  }
  if (state.managerDashboard.status === "idle") {
    window.queueMicrotask(() => loadManagerDashboard({ silent: true }));
  }
  const members = listFrom(sectionState.data || {}, "members");
  return `
    <div class="page-wrap">
      ${pageHeader("Команда", "Пригласите креаторов по рабочей почте. Пароли и секреты в эту форму не вводятся.", `<span class="badge badge-info">До 50 человек</span>`)}
      ${alertMarkup("Каждый новый участник входит как trainee. Рабочие разделы откроются только после четырёх курсов, принятой руководителем пробной работы и успешного экзамена из 12 сценариев.", "info")}
      <div class="split-grid" style="margin-top:18px">
        <section class="card card-pad">
          <p class="eyebrow">Массовое приглашение</p>
          <h2 style="font:600 1.55rem/1.15 Georgia,serif; margin:0 0 8px">Один email на строку</h2>
          <p class="muted tiny">Повторы будут удалены до отправки. Максимум 50 уникальных адресов за один запуск.</p>
          <form id="team-invite-form" class="form-stack" novalidate>
            <label class="field">
              <span>Рабочие адреса *</span>
              <textarea name="emails" required rows="12" maxlength="16000" spellcheck="false" autocomplete="off" placeholder="creator-01@company.ru&#10;creator-02@company.ru"></textarea>
            </label>
            <button class="btn btn-block" type="submit">Отправить приглашения</button>
          </form>
        </section>
        <section class="card">
          <div class="card-header"><div><p class="eyebrow">Последний запуск</p><h2>Результаты почтовых запросов</h2></div></div>
          ${state.teamInviteResult ? teamInviteResultMarkup(state.teamInviteResult) : emptyState("◎", "Приглашений ещё не было", "После запуска здесь появится принятый сервисом статус по каждому адресу.")}
        </section>
      </div>
      ${accessCenterMarkup(state.accessCenter)}
      <section class="card" style="margin-top:22px">
        <div class="card-header"><div><p class="eyebrow">Доступ и результат</p><h2>Участники команды</h2></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="team">Обновить</button></div>
        ${sectionBody(sectionState, members.length ? teamMembersTable(members) : emptyState("◎", "В команде пока никого нет", "Отправьте приглашения выше — новые участники появятся после первого входа."))}
      </section>
      ${trainingPracticalReviewQueueMarkup(state.bootstrap?.training?.practicalReviews || [])}
      ${managerDashboardSectionMarkup()}
    </div>
  `;
}

function managerDashboardSectionMarkup() {
  const dashboard = state.managerDashboard;
  const spendMarkup = managerGenerationSpendMarkup(state.generationSpend, { canEdit: canManageGenerationSpendPolicy() });
  if (["idle", "loading"].includes(dashboard.status) && !dashboard.data) {
    return `${spendMarkup}<section class="manager-funnel manager-dashboard-loading" role="status"><div class="loading-line" aria-hidden="true"><span></span></div><strong>Собираем, где команда остановилась…</strong><p class="muted">Письмо, вход, обучение, генерация, публикация и выплата проверяются одним отчётом.</p></section>`;
  }
  if (dashboard.status === "error" && !dashboard.data) {
    return `${spendMarkup}<section class="manager-funnel">${alertMarkup("Не удалось загрузить очередь внимания. Список участников выше продолжает работать.", "warning")}<button class="btn btn-secondary btn-small" type="button" data-action="refresh-manager-dashboard">Повторить загрузку</button>${managerOperationalHealthMarkup(state.operationalHealth)}</section>`;
  }
  return `${spendMarkup}${dashboard.status === "refreshing" ? `<p class="tiny muted manager-refresh-note" role="status">Обновляем сводку без остановки страницы…</p>` : ""}${dashboard.status === "error" ? alertMarkup("Не удалось обновить сводку. Ниже показаны последние сохранённые данные — нажмите «Обновить» ещё раз позже.", "warning") : ""}${managerDashboardMarkup(dashboard.data || {}, state.operationalHealth)}`;
}

function teamMembersTable(members) {
  return `<div class="table-wrap"><table class="data-table">
    <thead><tr><th>Участник</th><th>Роль</th><th>Курсы</th><th>Экзамен</th><th>Задачи</th><th>Публикации</th></tr></thead>
    <tbody>${members.map((member) => `<tr>
      <td><strong>${escapeHtml(member.display_name || member.email || "Участник")}</strong>${member.display_name && member.email ? `<br /><small class="muted">${escapeHtml(member.email)}</small>` : ""}${member.status && member.status !== "active" ? `<br />${statusBadge(member.status)}` : ""}</td>
      <td>${escapeHtml(humanRole(member.role || "trainee"))}</td>
      <td><strong>${formatNumber(member.courses_completed ?? 0)}/${formatNumber(member.courses_required ?? 4)}</strong></td>
      <td>${normalizeBoolean(member.exam_passed) ? statusBadge("passed") : statusBadge("pending")}</td>
      <td>${formatNumber(member.tasks_done ?? 0)}/${formatNumber(member.tasks_total ?? 0)}</td>
      <td>${formatNumber(member.published_count ?? 0)}</td>
    </tr>`).join("")}</tbody>
  </table></div>`;
}

function teamInviteResultMarkup(result) {
  const rows = Array.isArray(result?.results) ? result.results : [];
  const smtpRequired = result?.smtp_required === true || rows.some((item) => item.status === "smtp_required");
  const statusLabels = {
    invited: "Запрос принят сервисом; доставка письма не подтверждена",
    already_exists: "Существующий аккаунт подключён; новое письмо не отправлялось",
    rate_limited: "Лимит отправки",
    smtp_required: "Почта не настроена",
    failed: "Не отправлено",
    pending_verification: "Ответ не получен вовремя — проверьте историю перед повтором",
  };
  const reasonLabels = {
    invite_request_accepted: "Приглашение принято почтовым сервисом",
    existing_account_connected: "Доступ существующего аккаунта активирован",
    auth_user_already_exists: "Аккаунт уже существует",
    email_rate_limited: "Сработал лимит почтовых запросов",
    smtp_not_configured: "SMTP-провайдер не разрешил отправку",
    auth_invite_failed: "Auth не принял запрос приглашения",
    password_marker_failed: "Не удалось включить обязательную смену пароля",
    membership_provision_failed: "Не удалось подготовить членство в команде",
    membership_reconcile_failed: "Не удалось подключить существующий аккаунт",
    auth_user_missing: "Auth не вернул созданный аккаунт",
    client_timeout: "Портал перестал ждать ответ, операция могла завершиться позже",
  };
  const retryable = rows.filter((item) => !["invited", "already_exists"].includes(item.status));
  return `
    <div class="card-pad" style="padding-top:0">
      ${result.requested_at ? `<p class="tiny muted">Последний запрос: ${escapeHtml(formatDate(result.requested_at, true))}${result.request_id ? ` · № ${escapeHtml(String(result.request_id).slice(0, 8))}` : ""}</p>` : ""}
      <div class="metrics-grid metrics-grid-three" style="margin-bottom:16px">
        <article class="metric-card"><span class="metric-label">Запрошено</span><strong>${formatNumber(result.requested ?? rows.length)}</strong></article>
        <article class="metric-card"><span class="metric-label">Принято сервисом</span><strong>${formatNumber(result.invited ?? 0)}</strong></article>
        <article class="metric-card"><span class="metric-label">Уже существуют</span><strong>${formatNumber(result.already_exists ?? 0)}</strong></article>
      </div>
      ${Number(result.invited || 0) > 0 ? alertMarkup("Статус «Принято сервисом» подтверждает запрос, но не попадание письма во «Входящие». Участнику нужно проверить также «Спам» и использовать только самое свежее письмо.", "info") : ""}
      ${smtpRequired ? alertMarkup("Почтовая отправка портала ещё не настроена. Адреса со статусом «Почта не настроена» не получили приглашение.", "warning") : ""}
      ${rows.some((item) => item.status === "rate_limited") ? alertMarkup("Достигнут лимит отправки писем. Не повторяйте весь список: позже отправьте только адреса со статусом «Лимит отправки».", "warning") : ""}
      ${result.persistence === "unavailable" ? alertMarkup("Сервер не подтвердил сохранение истории этого запуска. Не повторяйте список вслепую: сначала нажмите «Обновить».", "warning") : ""}
      <div class="table-wrap"><table class="data-table">
        <thead><tr><th>Email</th><th>Результат</th></tr></thead>
        <tbody>${rows.map((item) => `<tr><td>${escapeHtml(item.email || "—")}</td><td>${statusBadge(item.status || "failed")}<br /><small class="muted">${escapeHtml(statusLabels[item.status] || "Неизвестный результат")}</small>${item.reason_code ? `<br /><small class="muted">${escapeHtml(reasonLabels[item.reason_code] || item.reason_code)}</small>` : ""}</td></tr>`).join("")}</tbody>
      </table></div>
      ${retryable.length ? `<button class="btn btn-secondary btn-small" type="button" data-action="prepare-failed-invites" style="margin-top:14px">Заполнить только неудачные (${retryable.length})</button>` : ""}
    </div>
  `;
}

function teamInviteStorageKey() {
  const userId = state.user?.id;
  const organizationId = state.bootstrap?.organization?.id;
  return userId && organizationId
    ? `contentengine.invite-result.v1.${organizationId}.${userId}`
    : null;
}

function persistTeamInviteResult(result) {
  const key = teamInviteStorageKey();
  if (!key || !result) return;
  try {
    window.sessionStorage.setItem(key, JSON.stringify({
      expiresAt: Date.now() + 24 * 60 * 60 * 1000,
      result,
    }));
  } catch {
    // The server-side invite ledger remains the source of truth.
  }
}

function restoreTeamInviteResult() {
  const key = teamInviteStorageKey();
  if (!key) return null;
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(key) || "null");
    if (!saved?.result || Number(saved.expiresAt || 0) < Date.now()) {
      window.sessionStorage.removeItem(key);
      return null;
    }
    return saved.result;
  } catch {
    window.sessionStorage.removeItem(key);
    return null;
  }
}

function feedbackCard(item) {
  return `<article class="card feedback-card"><div class="feedback-top"><div><p class="eyebrow">${escapeHtml(item.category || "запрос")} · ${formatDate(item.created_at)}</p><h3>${escapeHtml(item.title || "Без заголовка")}</h3><p>${escapeHtml(item.details || item.description || "")}</p></div>${statusBadge(item.status || "new")}</div>${item.response ? alertMarkup(item.response, "success") : ""}</article>`;
}

function workspaceDirectionMarkup(meta) {
  if (!meta?.now || !meta?.done || !meta?.nextHref) return "";
  return `
    <section class="workspace-direction card" aria-label="Что делать в этом разделе">
      <div class="workspace-direction-heading">
        <span class="direction-seal" aria-hidden="true">A</span>
        <div><p class="eyebrow">Маршрут без догадок</p><h2>Сделайте один шаг и проверьте результат</h2></div>
      </div>
      <ol class="workspace-direction-steps">
        <li><span>01</span><div><small>Сделайте сейчас</small><strong>${escapeHtml(meta.now)}</strong></div></li>
        <li><span>02</span><div><small>Готово, когда</small><strong>${escapeHtml(meta.done)}</strong></div></li>
        <li><span>03</span><div><small>После этого</small><strong>${escapeHtml(meta.nextLabel)}</strong></div></li>
      </ol>
      <div class="workspace-direction-footer">
        <p><span aria-hidden="true">!</span><strong>Стоп-правило:</strong> ${escapeHtml(meta.guard)}</p>
        <a class="direction-next-link" href="${escapeHtml(meta.nextHref)}">Когда закончите: ${escapeHtml(meta.nextLabel)} <span aria-hidden="true">→</span></a>
      </div>
    </section>
  `;
}

function pageHeader(title, description, actions = "") {
  const activeSection = state.route.path.startsWith("/workspace/")
    ? state.route.path.replace("/workspace/", "")
    : "home";
  const meta = WORKSPACE_SECTION_META[activeSection] || WORKSPACE_SECTION_META.home;
  const inFactoryFlow = FACTORY_FLOW.some((item) => item.key === activeSection);
  return `
    <section class="workspace-page-intro">
      <header class="page-header">
        <div class="page-header-copy">
          <p class="eyebrow">${escapeHtml(meta.kicker)}</p>
          <h1>${escapeHtml(title)}</h1>
          <p>${escapeHtml(description)}</p>
          <span class="page-context-note"><i aria-hidden="true"></i>${escapeHtml(meta.note)}</span>
        </div>
        <div class="page-actions">
          ${actions}
          <a class="workspace-guide-link" href="${escapeHtml(meta.guideHref || "#/learn")}"><span aria-hidden="true">?</span> Инструкция для этого шага</a>
        </div>
      </header>
      ${inFactoryFlow ? factoryFlowMarkup(activeSection) : ""}
    </section>
    ${workspaceDirectionMarkup(meta)}
  `;
}

function factoryFlowMarkup(activeSection) {
  return `
    <nav class="factory-flow" aria-label="Этапы производственного цикла">
      <ol style="--workflow-step-count:${FACTORY_FLOW.length}">
        ${FACTORY_FLOW.map((item) => `
          <li class="${item.key === activeSection ? "active" : ""}">
            <a href="#/workspace/${item.key}" ${item.key === activeSection ? 'aria-current="step"' : ""}>
              <span>${item.step}</span>
              <div><strong>${item.label}</strong><small>${item.hint}</small></div>
            </a>
          </li>
        `).join("")}
      </ol>
    </nav>
  `;
}

function sectionBody(sectionState, readyMarkup) {
  if ((sectionState.status === "loading" || sectionState.status === "idle") && !sectionState.data) {
    return `<div class="skeleton-stack" role="status"><span class="sr-only">Загружаем данные…</span><div aria-hidden="true" class="skeleton"></div><div aria-hidden="true" class="skeleton"></div><div aria-hidden="true" class="skeleton"></div></div>`;
  }
  if (sectionState.status === "error") {
    console.error(sectionState.error);
    const section = state.route.path.startsWith("/workspace/")
      ? state.route.path.replace("/workspace/", "")
      : "";
    const retry = state.sections[section]
      ? `<button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="${escapeHtml(section)}">Повторить</button>`
      : "";
    return `<div class="empty-state" role="alert"><div class="empty-icon" aria-hidden="true">!</div><h3>Не удалось загрузить раздел</h3><p>Проверьте соединение и попробуйте ещё раз. Если ошибка повторится, сообщите руководителю команды.</p>${retry}</div>`;
  }
  if (sectionState.status === "refreshing") {
    return `<div class="refresh-indicator" role="status"><span aria-hidden="true"></span>Обновляем данные…</div>${readyMarkup}`;
  }
  return readyMarkup;
}

function emptyState(icon, title, message, action = null) {
  const actionMarkup = action?.href
    ? `<a class="btn btn-secondary btn-small empty-state-action" href="${escapeHtml(action.href)}">${escapeHtml(action.label)} <span aria-hidden="true">→</span></a>`
    : action?.target
      ? `<button class="btn btn-secondary btn-small empty-state-action" type="button" data-action="scroll-to" data-target="${escapeHtml(action.target)}">${escapeHtml(action.label)} <span aria-hidden="true">↑</span></button>`
      : "";
  return `<div class="empty-state"><div class="empty-icon" aria-hidden="true">${icon}</div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p>${actionMarkup}</div>`;
}

function reserveManagerEmailAction(cooldowns, email) {
  const key = String(email || "").trim().toLowerCase();
  const now = Date.now();
  const blockedUntil = Number(cooldowns.get(key) || 0);
  if (blockedUntil > now) return Math.max(1, Math.ceil((blockedUntil - now) / 1_000));
  cooldowns.set(key, now + MANAGER_EMAIL_ACTION_COOLDOWN_MS);
  return 0;
}

async function handleClick(event) {
  if (state.mobileNavOpen && !event.target.closest(".mobile-nav, .mobile-nav-trigger")) {
    setMobileNavOpen(false);
  }
  const workspaceDragHandle = event.target.closest("[data-workspace-drag-item]");
  if (workspaceDragHandle) {
    state.workspaceBoard.selectedItemKey = workspaceDragHandle.dataset.itemKey
      || workspaceBoardItemKey(
        workspaceDragHandle.dataset.entityType,
        workspaceDragHandle.dataset.entityId,
      );
    state.workspaceBoard.notice = "Объект выбран. Укажите папку в панели справа или перетащите ручку на папку.";
    state.workspaceBoard.error = "";
    renderWorkspace("board");
    window.queueMicrotask(() => document.querySelector("[data-workspace-item-drawer] button[data-action='move-workspace-item']")?.focus());
    return;
  }
  const control = event.target.closest("[data-action]");
  if (!control) return;
  const action = control.dataset.action;

  if (action === "open-training-practical-media") {
    await openTrainingPracticalMedia(control);
    return;
  }

  if (action === "refresh-training-practical-reviews") {
    await refreshTrainingPracticalReviews({ control });
    return;
  }

  if (action === "select-learning-track") {
    const selected = persistLearningTrack(control.dataset.learningTrack);
    renderLearningHome();
    window.queueMicrotask(() => document.querySelector(`[data-learning-track="${CSS.escape(selected)}"]`)?.focus({ preventScroll: true }));
    track("training_track_selected", { learning_track: selected });
    toast(`Учебный акцент: ${LEARNING_TRACKS[selected].shortLabel}.`, "success");
    return;
  }

  if (action === "training-mastery-next") {
    const courseCode = String(document.querySelector("[data-course-lesson-player]")?.dataset.courseCode || "");
    const course = learningCourses().find((item) => item.code === courseCode);
    if (!course) return;
    const snapshot = syncCourseMasteryPanel(course);
    const step = String(control.dataset.masteryStep || snapshot?.nextStep || "lessons");
    if (step === "lessons") {
      const journey = restoreLessonJourney(course);
      const understood = new Set(journey.understoodLessonIds);
      const required = new Set(courseRequiredLessonIds(course));
      const index = course.lessons.findIndex((lesson) => required.has(lesson.id) && !understood.has(lesson.id));
      if (index >= 0) syncCourseLessonJourney(course, reduceLessonJourney(journey, { type: "open", index }, course.lessons), { focus: true, scroll: true });
    } else if (step === "practice") {
      const required = new Set(course.mastery.requiredWalkthroughIds);
      const root = Array.from(document.querySelectorAll(`[data-training-course="${CSS.escape(course.code)}"]`))
        .find((item) => required.has(String(item.dataset.trainingWalkthrough || "")) && item.dataset.trainingComplete !== "true");
      scrollElementIntoView(root, "center");
      root?.querySelector('[data-action="training-walkthrough-play"]')?.focus({ preventScroll: true });
    } else if (step === "test") {
      const target = document.querySelector("#course-check");
      scrollElementIntoView(target, "start");
      target?.focus({ preventScroll: true });
    } else if (step === "confirmation") {
      const target = document.querySelector(".course-completion-card");
      scrollElementIntoView(target, "center");
      target?.querySelector("[data-course-ack]:not(:checked)")?.focus({ preventScroll: true });
    }
    track("training_mastery_step_opened", { module_code: course.code, mastery_step: step });
    return;
  }

  if (["training-lesson-open", "training-lesson-toggle", "training-lesson-understood"].includes(action)) {
    const courseCode = String(document.querySelector("[data-course-lesson-player]")?.dataset.courseCode || "");
    const lessons = Array.from(document.querySelectorAll("[data-course-lesson]"));
    const course = learningCourses().find((item) => item.code === courseCode);
    if (!course || !lessons.length) return;
    const index = Math.max(0, Math.min(lessons.length - 1, Number(control.dataset.lessonIndex) || 0));
    const current = restoreLessonJourney(course);
    if (action === "training-lesson-toggle" && current.activeIndex === index && control.getAttribute("aria-expanded") === "true") {
      const lesson = lessons[index];
      lesson.querySelector("[data-course-lesson-details]")?.setAttribute("hidden", "");
      control.setAttribute("aria-expanded", "false");
      control.setAttribute("aria-label", `Открыть урок «${lesson.querySelector("h2")?.textContent || index + 1}»`);
      return;
    }
    const wasUnderstood = current.understood.includes(index);
    const next = action === "training-lesson-understood"
        ? reduceLessonJourney(current, {
          type: wasUnderstood ? "reopen" : "understand",
          index,
          moveNext: !wasUnderstood,
        }, course.lessons)
      : reduceLessonJourney(current, { type: "open", index }, course.lessons);
    syncCourseLessonJourney(course, next, {
      focus: true,
      scroll: action !== "training-lesson-toggle",
    });
    if (action === "training-lesson-understood") {
      track(wasUnderstood ? "training_lesson_reopened" : "training_lesson_completed", {
        module_code: courseCode,
        lesson_index: index + 1,
        learning_track: restoreLearningTrack(),
      });
      if (!wasUnderstood) toast("Урок отмечен понятным. Прогресс сохранён на этом устройстве.", "success");
    }
    return;
  }

  if (action === "close-training-achievement") {
    closeTrainingAchievement();
    return;
  }

  if (action === "play-training-fanfare") {
    const played = playTrainingFanfare();
    if (played) {
      control.disabled = true;
      control.innerHTML = '<span aria-hidden="true">✓</span> Фанфары сыграли';
    } else {
      toast("В этом браузере звук недоступен, но ачивка уже сохранена.", "info");
    }
    return;
  }

  if (action === "toggle-work-notifications") {
    event.preventDefault();
    if (!state.myWork.notificationsOpen && state.mobileNavOpen) setMobileNavOpen(false);
    state.myWork.notificationsOpen = !state.myWork.notificationsOpen;
    refreshNotificationLayer({ focus: state.myWork.notificationsOpen });
    if (
      state.myWork.notificationsOpen
      && ["idle", "error"].includes(state.myWork.notificationsStatus)
    ) {
      void loadMyWorkNotifications();
    }
    return;
  }

  if (action === "open-work-notification") {
    const notificationId = String(control.dataset.notificationId || "");
    if (notificationId) void markMyWorkNotificationsRead([notificationId]);
    return;
  }

  if (action === "mark-all-notifications-read") {
    await markAllMyWorkNotificationsRead();
    return;
  }

  if (action === "refresh-my-work") {
    state.myWork.notice = "";
    state.myWork.error = "";
    await loadSection("work");
    return;
  }

  if (action === "reset-my-work-filters") {
    state.myWork.filters = normalizeMyWorkFilters();
    state.myWork.selectedViewId = "";
    state.myWork.notice = "";
    state.myWork.error = "";
    await loadSection("work");
    return;
  }

  if (action === "load-more-my-work") {
    await loadMoreMyWork();
    return;
  }

  if (action === "apply-my-work-view") {
    const viewId = String(control.dataset.viewId || "");
    const view = state.myWork.savedViews.find((item) => item.id === viewId);
    state.myWork.selectedViewId = view?.id || "";
    state.myWork.filters = normalizeMyWorkFilters(view?.filters);
    state.myWork.notice = view
      ? `Фильтр «${view.name}» применён.`
      : "";
    state.myWork.error = "";
    await loadSection("work");
    return;
  }

  if (action === "delete-my-work-view") {
    const viewId = String(control.dataset.viewId || "");
    const version = Number(control.dataset.viewVersion || 0);
    if (!viewId || !window.confirm("Удалить сохранённый фильтр?")) return;
    try {
      await state.api.savedWorkViews({
        action: "delete",
        view_id: viewId,
        expected_version: version,
      });
      if (state.myWork.selectedViewId === viewId) {
        state.myWork.selectedViewId = "";
        state.myWork.filters = normalizeMyWorkFilters();
      }
      await reloadSavedWorkViews();
      state.myWork.notice = "Сохранённый фильтр удалён.";
      state.myWork.error = "";
    } catch (error) {
      state.myWork.error = actionErrorMessage(error);
    }
    renderWorkspace("work");
    return;
  }

  if (action === "training-walkthrough-play") {
    await toggleTrainingWalkthrough(trainingWalkthroughRoot(control));
    return;
  }

  if (action === "training-mode-select") {
    const root = trainingWalkthroughRoot(control);
    stopTrainingWalkthroughSession(root);
    const mode = setTrainingWalkthroughMode(root, control.dataset.trainingModeValue);
    persistTrainingWalkthroughState(root);
    if (mode === "practice") {
      root?.querySelector("[data-training-practice-option]")?.focus?.({ preventScroll: true });
    }
    return;
  }

  if (action === "training-walkthrough-jump") {
    setTrainingWalkthroughStepAndPersist(
      trainingWalkthroughRoot(control),
      Number(control.dataset.trainingStepTarget) || 0,
    );
    return;
  }

  if (action === "training-walkthrough-reset") {
    const root = trainingWalkthroughRoot(control);
    resetTrainingWalkthroughState(root);
    persistTrainingWalkthroughState(root, { syncServer: false });
    root?.querySelector('[data-action="training-walkthrough-play"]')?.focus({ preventScroll: true });
    toast("Повтор начат локально. Уже полученный зачёт сохраняется в рабочем профиле.", "info");
    return;
  }

  if (["training-walkthrough-previous", "training-walkthrough-next"].includes(action)) {
    const root = trainingWalkthroughRoot(control);
    const current = Math.max(0, Number(root?.dataset?.trainingStep) || 0);
    const next = action === "training-walkthrough-previous"
      ? current - 1
      : current + 1;
    setTrainingWalkthroughStepAndPersist(root, next);
    return;
  }

  if (action === "set-portal-theme") {
    applyPortalTheme(control.dataset.themeValue, { persist: true, announce: true });
    return;
  }

  if (action === "set-navigation-mode") {
    applyNavigationMode(control.dataset.navigationMode, {
      persist: true,
      announce: true,
      rerender: true,
    });
    return;
  }

  if (action === "select-workspace-folder") {
    state.workspaceBoard.selectedFolderId = String(control.dataset.folderId || "all");
    state.workspaceBoard.selectedItemKey = "";
    state.workspaceBoard.notice = "";
    state.workspaceBoard.error = "";
    state.workspaceBoard.hasMore = false;
    state.workspaceBoard.nextCursor = null;
    state.workspaceBoard.visibleItemLimit = WORKSPACE_BOARD_VISIBLE_STEP;
    await loadSection("board");
    return;
  }

  if (action === "open-workspace-item") {
    state.workspaceBoard.selectedItemKey = String(
      control.dataset.itemKey
      || workspaceBoardItemKey(control.dataset.entityType, control.dataset.entityId),
    );
    state.workspaceBoard.notice = "";
    state.workspaceBoard.error = "";
    renderWorkspace("board");
    window.queueMicrotask(() => document.querySelector("[data-workspace-item-drawer] [data-action='close-workspace-item']")?.focus());
    return;
  }

  if (action === "close-workspace-item") {
    state.workspaceBoard.selectedItemKey = "";
    renderWorkspace("board");
    window.queueMicrotask(() => document.querySelector(".workspace-board__item-open")?.focus());
    return;
  }

  if (action === "move-workspace-item") {
    await moveWorkspaceBoardItem({
      entityType: control.dataset.entityType,
      entityId: control.dataset.entityId,
      itemKey: control.dataset.itemKey,
      destinationFolderId: control.dataset.targetFolderId || control.dataset.folderId,
    });
    return;
  }

  if (action === "archive-workspace-folder") {
    await archiveWorkspaceBoardFolder(
      control.dataset.folderId,
      Number(control.dataset.folderVersion) || 1,
    );
    return;
  }

  if (action === "reset-workspace-filters") {
    state.workspaceBoard.query = "";
    state.workspaceBoard.entityType = "all";
    state.workspaceBoard.notice = "";
    state.workspaceBoard.error = "";
    state.workspaceBoard.hasMore = false;
    state.workspaceBoard.nextCursor = null;
    state.workspaceBoard.visibleItemLimit = WORKSPACE_BOARD_VISIBLE_STEP;
    await loadSection("board");
    return;
  }

  if (action === "show-more-workspace-items") {
    state.workspaceBoard.visibleItemLimit = Math.min(
      WORKSPACE_BOARD_MEMORY_CAP,
      state.workspaceBoard.visibleItemLimit + WORKSPACE_BOARD_VISIBLE_STEP,
    );
    renderWorkspace("board");
    return;
  }

  if (action === "load-more-workspace-items") {
    await loadMoreWorkspaceBoard();
    return;
  }

  if (action === "refresh-product-research") {
    await pollProductResearchStatus();
    return;
  }

  if (action === "open-generated-content-review") {
    const mediaId = String(control.dataset.mediaId || "").trim();
    if (!mediaId) {
      toast("У готового ролика не найден точный файл. Обновите задачи и генерацию.", "error");
      return;
    }
    state.contentReview.pendingMediaId = mediaId;
    state.contentReview.record = null;
    state.contentReview.phase = "idle";
    state.contentReview.error = "";
    state.contentReview.notice = "Выберите контекст публикации и запустите обязательную проверку готового ролика.";
    navigate("/workspace/review");
    return;
  }

  if (action === "open-content-review") {
    const reviewId = String(control.dataset.reviewId || "");
    const catalog = normalizeContentReviewCatalog(state.sections.review.data || {});
    const selected = catalog.runs.find((item) => item.id === reviewId);
    if (!selected) {
      toast("Эта проверка не найдена в загруженной истории. Обновите раздел.", "error");
      return;
    }
    state.contentReview.record = selected;
    state.contentReview.phase = "refreshing";
    state.contentReview.error = "";
    state.contentReview.notice = "";
    renderWorkspace("review");
    await pollContentReviewStatus({ silent: true, refreshMedia: true });
    scheduleContentReviewPolling(250);
    window.queueMicrotask(() => document.querySelector("[data-review-result-id], .content-review-progress, .content-review-failed")?.scrollIntoView({ block: "start", behavior: "smooth" }));
    return;
  }

  if (action === "refresh-content-review") {
    const reviewId = String(control.dataset.reviewId || state.contentReview.record?.id || "");
    if (reviewId && reviewId !== String(state.contentReview.record?.id || "")) {
      const catalog = normalizeContentReviewCatalog(state.sections.review.data || {});
      state.contentReview.record = catalog.runs.find((item) => item.id === reviewId) || state.contentReview.record;
    }
    await pollContentReviewStatus({ refreshMedia: true });
    return;
  }

  if (action === "new-product-research") {
    stopProductResearchPolling();
    clearProductResearchRunId();
    state.productResearch.requestId += 1;
    state.productResearch.phase = "idle";
    state.productResearch.record = null;
    state.productResearch.error = "";
    state.productResearch.notice = "";
    state.productResearch.restoreAttempted = true;
    renderWorkspace("research");
    window.queueMicrotask(() => document.querySelector('#product-research-start-form input[name="product_name"]')?.focus());
    return;
  }

  if (action === "reset-generation-filters") {
    document.querySelector("#generation-archive-filter-form")?.removeAttribute("data-dirty");
    state.generationArchive.filters = normalizeGenerationFilters({
      period: "4w",
      status: "all",
      query: "",
      visible: GENERATION_VISIBLE_STEP,
    });
    state.generationArchive.error = "";
    await reloadGenerationArchive();
    return;
  }

  if (action === "show-more-generation") {
    state.generationArchive.filters = normalizeGenerationFilters({
      ...state.generationArchive.filters,
      visible: Number(state.generationArchive.filters?.visible || GENERATION_VISIBLE_STEP) + GENERATION_VISIBLE_STEP,
    });
    renderWorkspace("generation");
    return;
  }

  if (action === "load-more-generation") {
    await loadMoreGenerationArchive();
    return;
  }

  if (action === "reload-page") {
    window.location.reload();
    return;
  }

  if (action === "toggle-mobile-nav") {
    setMobileNavOpen(!state.mobileNavOpen, state.mobileNavOpen);
    return;
  }

  if (action === "retry-auth-link") {
    retryAuthLinkIfIdle();
    return;
  }

  if (action === "request-new-auth-link") {
    const purpose = String(control.dataset.purpose || "recovery");
    state.authLinkError = null;
    navigate(purpose === "invite" ? "/login" : "/reset-password", true);
    return;
  }

  if (action === "prepare-failed-invites") {
    const rows = Array.isArray(state.teamInviteResult?.results) ? state.teamInviteResult.results : [];
    const emails = rows
      .filter((item) => !["invited", "already_exists"].includes(item.status))
      .map((item) => String(item.email || "").trim())
      .filter(Boolean);
    const field = document.querySelector("#team-invite-form textarea[name='emails']");
    if (field && emails.length) {
      field.value = [...new Set(emails)].join("\n");
      field.closest("form").dataset.dirty = "true";
      scrollElementIntoView(field.closest(".card"));
      field.focus({ preventScroll: true });
      toast("В форму перенесены только адреса без подтверждённого результата. Проверьте список перед повтором.", "info");
    }
    return;
  }

  if (action === "refresh-manager-dashboard") {
    if (
      ["loading", "refreshing"].includes(state.managerDashboard.status)
      || ["loading", "refreshing"].includes(state.operationalHealth.status)
      || ["loading", "refreshing"].includes(state.generationSpend.status)
    ) {
      toast("Сводка уже обновляется.", "info");
      return;
    }
    await loadManagerDashboard();
    return;
  }

  if (action === "refresh-generation-spend") {
    if (["loading", "refreshing"].includes(state.generationSpend.status)) {
      toast("Денежный остаток уже проверяется.", "info");
      return;
    }
    state.generationSpend.notice = "";
    state.generationSpend.error = null;
    await loadGenerationSpendOverview();
    return;
  }

  if (action === "open-manager-access") {
    await openManagerAccessCenter(String(control.dataset.email || ""));
    return;
  }

  if (action === "reset-manager-access") {
    resetManagerAccessCenter();
    return;
  }

  if (action === "retry-manager-invite") {
    await retryManagerInvite(String(control.dataset.email || ""), control);
    return;
  }

  if (action === "send-manager-recovery") {
    const email = String(control.dataset.email || "").trim();
    if (!canManageTeam() || !hasWorkspaceAccess()) {
      toast("Отправить восстановление может только сертифицированный руководитель.", "error");
      return;
    }
    if (!email) {
      toast("У участника не указан рабочий email.", "error");
      return;
    }
    const cooldownSeconds = reserveManagerEmailAction(state.managerRecoveryCooldowns, email);
    if (cooldownSeconds > 0) {
      toast(`Повтор для этого адреса временно закрыт. Подождите ${cooldownSeconds} сек. и сначала проверьте самое свежее письмо.`, "info");
      return;
    }
    await openManagerAccessCenter(email);
    return;
  }

  if (action === "copy-manager-reminder") {
    const email = String(control.dataset.email || "участник");
    const stage = String(control.dataset.stage || "обучение");
    const message = `${email}, откройте портал Контент ИИ Завода и завершите ${stage}. Если вход не открывается или страница зависла, пришлите руководителю точный текст ошибки и снимок экрана — новый аккаунт создавать не нужно.`;
    try {
      await navigator.clipboard.writeText(message);
      toast("Напоминание скопировано.", "success");
    } catch {
      toast(message, "info");
    }
    return;
  }

  if (action === "skip-to-content") {
    const main = document.querySelector("#main-content");
    main?.focus({ preventScroll: true });
    scrollElementIntoView(main);
    return;
  }

  if (action === "logout") {
    control.disabled = true;
    await state.supabase?.auth.signOut({ scope: "local" });
    clearAuthenticatedState();
    navigate("/login", true);
    return;
  }

  if (action === "retry-bootstrap") {
    control.disabled = true;
    await loadBootstrap();
    establishDefaultRoute();
    render();
    return;
  }

  if (action === "scroll-to") {
    const targetId = String(control.dataset.target || "");
    let target = targetId ? document.getElementById(targetId) : null;
    if (target?.matches?.("[data-course-lesson]")) {
      const courseCode = String(document.querySelector("[data-course-lesson-player]")?.dataset.courseCode || "");
      const lessons = Array.from(document.querySelectorAll("[data-course-lesson]"));
      const course = learningCourses().find((item) => item.code === courseCode);
      const lessonIndex = lessons.indexOf(target);
      if (course && lessonIndex >= 0) {
        syncCourseLessonJourney(
          course,
          reduceLessonJourney(restoreLessonJourney(course), { type: "open", index: lessonIndex }, course.lessons),
          { focus: false, scroll: false },
        );
        target = lessons[lessonIndex];
      }
    }
    if (target) {
      scrollElementIntoView(target);
      if (target.matches?.("[data-course-lesson]")) {
        target.querySelector('[data-action="training-lesson-toggle"]')?.focus({ preventScroll: true });
      } else if (target.hasAttribute("tabindex")) target.focus({ preventScroll: true });
    }
    return;
  }

  const firstShiftEventType = FIRST_SHIFT_FULL_EVENT_TYPES[action];
  if (firstShiftEventType) {
    const practice = ensureFirstShiftState();
    const eventPayload = {
      type: firstShiftEventType,
      stepId: String(control.dataset.stepId || ""),
    };
    if (firstShiftEventType === "select") {
      eventPayload.value = String(control.value || "");
      eventPayload.selected = control.checked === true;
    }
    state.firstShift = {
      userId: practice.userId,
      ...reduceFirstShiftFullState(practice, eventPayload),
    };
    persistFirstShiftState();

    if (firstShiftEventType === "select") {
      renderFirstShift();
      window.queueMicrotask(() => {
        const selectedControl = [...app.querySelectorAll(`[data-action="${FIRST_SHIFT_FULL_ACTIONS.select}"]`)]
          .find((input) => input.dataset.stepId === eventPayload.stepId && input.value === eventPayload.value);
        selectedControl?.focus?.({ preventScroll: true });
      });
      return;
    }

    renderFirstShift();
    window.queueMicrotask(() => {
      const target = firstShiftEventType === "check"
        ? app.querySelector(".first-shift-full__feedback")
        : (["next", "previous"].includes(firstShiftEventType) && !state.firstShift.completed
            ? app.querySelector("#first-shift-step-title")
            : app.querySelector("#first-shift-full-title"));
      target?.focus?.({ preventScroll: true });
      if (["check", "next", "previous"].includes(firstShiftEventType)) scrollElementIntoView(target, "center");
    });
    if (firstShiftEventType === "restart") toast("Полная учебная смена начата заново.", "info");
    return;
  }


  if (action === "complete-course") {
    const moduleCode = control.dataset.moduleCode;
    if (state.trainingProgress.completionInFlight.has(moduleCode)) return;
    const wasCompleted = state.bootstrap.training.completedModules.includes(moduleCode);
    const course = learningCourses().find((item) => item.code === moduleCode);
    const mastery = course ? syncCourseMasteryPanel(course) : null;
    if (!mastery?.ready) {
      const messages = {
        lessons: "Сначала отметьте понятными уроки вашего маршрута.",
        practice: "Сначала завершите обязательную учебную лабораторию.",
        test: "Сначала пройдите рабочую аттестацию этого блока.",
        confirmation: "Подтвердите все пункты финальной самопроверки.",
      };
      toast(messages[mastery?.nextStep] || "Завершите все четыре шага освоения навыка.", "error");
      document.querySelector(`[data-course-mastery-task="${CSS.escape(mastery?.nextStep || "lessons")}"] [data-action="training-mastery-next"]`)?.click();
      return;
    }
    if (state.courseCheckResults[moduleCode]?.passed !== true) {
      toast("Сначала пройдите рабочую аттестацию этого блока.", "error");
      scrollElementIntoView(document.querySelector("#course-check-form"));
      return;
    }
    const confirmations = Array.from(document.querySelectorAll("[data-course-ack]"));
    if (!confirmations.length || confirmations.some((checkbox) => !checkbox.checked)) {
      toast("Подтвердите все пункты самопроверки.", "error");
      return;
    }
    state.trainingProgress.completionInFlight.add(moduleCode);
    syncCourseMasteryPanel(course);
    try {
      await flushRequiredTrainingProgress(course);
      await state.api.completeModule(moduleCode);
      await track("course_completed", { module_code: moduleCode });
      await loadBootstrap();
      const serverCompleted = state.bootstrap.training.completedModules.includes(moduleCode);
      const celebrationKey = achievementStorageKey(state.user?.id, moduleCode);
      const celebrationStorage = learningPreferenceStorage();
      const alreadyCelebrated = celebrationKey && celebrationStorage
        ? safeStorageGet(celebrationStorage, celebrationKey) === "shown"
        : false;
      const celebrate = shouldCelebrateCourse({ wasCompleted, serverCompleted, alreadyCelebrated });
      if (!serverCompleted) throw new Error("Сервер не подтвердил завершение блока. Обновите страницу и проверьте результат.");
      if (celebrate && celebrationKey && celebrationStorage) safeStorageSet(celebrationStorage, celebrationKey, "shown");
      toast("Курс завершён и сохранён.", "success");
      navigate("/learn", true);
      if (celebrate) {
        window.queueMicrotask(() => {
          const returnFocus = document.querySelector(`a[href="#/learn/${CSS.escape(moduleCode)}"]`)
            || document.querySelector("#main-content");
          showTrainingAchievement(moduleCode, returnFocus);
          track("training_achievement_unlocked", { module_code: moduleCode });
        });
      }
    } catch (error) {
      toast(actionErrorMessage(error), "error");
    } finally {
      state.trainingProgress.completionInFlight.delete(moduleCode);
      if (control.isConnected) syncCourseMasteryPanel(course);
    }
    return;
  }

  if (action === "refresh-section") {
    const section = control.dataset.section;
    if (state.sections[section]) {
      if (section === "generation") {
        state.generationArchive.requestId += 1;
        state.generationArchive.loading = false;
        state.generationArchive.loadingMore = false;
        state.generationArchive.exhausted = false;
        state.generationArchive.error = "";
        state.generationArchive.nextCursor = null;
        state.generationArchive.serverLoaded = false;
      }
      state.sections[section].requestId += 1;
      state.sections[section].status = "idle";
      render();
    }
    return;
  }

  if (action === "refresh-home") {
    state.home.requestId += 1;
    state.home.status = "idle";
    render();
    return;
  }

  if (action === "repeat-real-generation") {
    restoreRealGenerationDraft(control.dataset.jobId);
    return;
  }

  if (action === "check-real-generation") {
    const jobId = String(control.dataset.jobId || "");
    const outputAction = String(control.dataset.outputAction || "status");
    const pendingWindow = outputAction === "open" ? openGenerationWaitingWindow() : null;
    control.disabled = true;
    const originalLabel = control.textContent;
    control.textContent = outputAction === "download" ? "Готовим файл…" : "Проверяем…";
    try {
      const outcome = await waitForRealGenerationStatus(jobId, REAL_GENERATION_SOFT_TIMEOUT_MS, "manual");
      if (outcome.timedOut) {
        pendingWindow?.close();
        toast("Проверка занимает больше обычного. Она продолжается без нового платного запуска — нажмите «Проверить сейчас» немного позже.", "info");
        return;
      }
      const result = outcome.result;
      const status = String(result?.job?.status || "processing").toLowerCase();
      const signedUrl = String(result?.signed_url || "");
      if (["succeeded", "completed"].includes(status) && signedUrl) {
        if (!isTrustedGenerationDownload(signedUrl)) throw new Error("Сервис вернул небезопасную ссылку на результат.");
        if (outputAction === "download") {
          downloadGenerationOutput(signedUrl, jobId);
          toast("Ролик готов. Браузеру передан свежий MP4-файл.", "success");
        } else if (outputAction === "open") {
          openGenerationOutput(signedUrl, pendingWindow);
          toast("Ролик открыт по свежей защищённой ссылке.", "success");
        } else {
          pendingWindow?.close();
          toast("Ролик готов — его можно посмотреть и скачать в карточке запуска.", "success");
        }
      } else if (status === "failed") {
        pendingWindow?.close();
        toast(generationFailureMessage(result?.job?.failure_code), "error");
      } else {
        pendingWindow?.close();
        toast(`Текущий статус видео: ${humanGenerationStatus(status)}.`, "info");
      }
    } catch (error) {
      pendingWindow?.close();
      toast(actionErrorMessage(error), "error");
    } finally {
      if (control.isConnected) {
        control.disabled = false;
        control.textContent = originalLabel;
      }
      scheduleRealGenerationPolling();
    }
    return;
  }

  if (action === "transition-task") {
    control.disabled = true;
    try {
      const taskId = control.dataset.taskId;
      const status = control.dataset.status;
      await state.api.transitionTask(taskId, status);
      await track("task_status_changed", { task_id: String(taskId), status });
      state.sections.tasks.status = "idle";
      toast(status === "blocked" ? "Блокер зафиксирован." : "Статус задачи обновлён.", "success");
      render();
    } catch (error) {
      control.disabled = false;
      toast(actionErrorMessage(error), "error");
    }
    return;
  }

  if (action === "decide-payout") {
    if (!["owner", "admin"].includes(state.bootstrap?.membership?.role)) {
      toast("Решение по выплате доступно только руководителю.", "error");
      return;
    }
    control.disabled = true;
    try {
      const payoutId = control.dataset.payoutId;
      await state.api.decidePayout(payoutId, "approve");
      await track("payout_decided", { payout_id: String(payoutId), decision: "approve" });
      state.sections.payouts.status = "idle";
      toast("Начисление одобрено. Теперь можно отдельно зафиксировать внешнюю оплату.", "success");
      render();
    } catch (error) {
      control.disabled = false;
      toast(actionErrorMessage(error), "error");
    }
  }
}

async function handleSubmit(event) {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  event.preventDefault();

  if (!form.reportValidity()) return;

  if (form.id === "login-form") await submitLogin(form);
  else if (form.id === "reset-form") await submitReset(form);
  else if (form.id === "password-form") await submitPassword(form);
  else if (form.id === "account-ad-form") submitAccountAdvertisingCheck(form);
  else if (form.id === "course-check-form") await submitCourseKnowledgeCheck(form);
  else if (form.id === "training-practical-submit-form") await submitTrainingPracticalProject(form);
  else if (form.classList.contains("training-practical-review__form")) await submitTrainingPracticalDecision(form, event.submitter);
  else if (form.id === "exam-form") await submitExam(form);
  else if (form.id === "workspace-folder-create-form") await submitWorkspaceFolderCreate(form);
  else if (form.id === "workspace-folder-edit-form") await submitWorkspaceFolderEdit(form);
  else if (form.id === "workspace-board-filter-form") await submitWorkspaceBoardFilters(form);
  else if (form.id === "my-work-filter-form") await submitMyWorkFilters(form);
  else if (form.id === "save-my-work-view-form") await submitSavedMyWorkView(form);
  else if (form.id === "generation-archive-filter-form") await submitGenerationArchiveFilters(form);
  else if (form.id === "product-research-start-form") await submitProductResearchStart(form);
  else if (form.id === "product-research-brief-form") await submitProductResearchBrief(form, event.submitter);
  else if (form.id === "content-review-form") await submitContentReview(form);
  else if (form.classList.contains("content-review-decision-form")) await submitContentReviewDecision(form, event.submitter);
  else if (form.classList.contains("generation-reconciliation-form")) await submitRealGenerationReconciliation(form, event.submitter);
  else if (form.id === "mock-batch-form") await submitGenerationBatch(form);
  else if (form.id === "manual-metric-form") await submitManualMetric(form);
  else if (form.id === "wb-alias-form") await submitWbAlias(form);
  else if (form.id === "media-upload-form") await submitMedia(form);
  else if (form.id === "feedback-form") await submitFeedback(form);
  else if (form.id === "team-invite-form") await submitTeamInvites(form);
  else if (form.id === "manager-access-form") await submitManagerAccess(form);
  else if (form.id === "generation-spend-policy-form") await submitGenerationSpendPolicy(form, event.submitter);
  else if (form.id === "generation-campaign-create-form") await submitGenerationCampaignCreate(form);
  else if (form.classList.contains("generation-campaign-policy-form")) await submitGenerationCampaignPolicy(form, event.submitter);
  else if (form.classList.contains("placement-form")) await submitPlacement(form);
  else if (form.classList.contains("payout-reject-form")) await submitPayoutReject(form);
  else if (form.classList.contains("payout-paid-form")) await submitPayoutPaid(form);
}

function campaignPolicyPayload(values, enabled) {
  return {
    paid_generation_enabled: enabled,
    daily_limit_minor: usdInputToMinor(values.get("daily_limit_usd")),
    monthly_limit_minor: usdInputToMinor(values.get("monthly_limit_usd")),
    per_request_limit_minor: usdInputToMinor(values.get("per_request_limit_usd")),
    reason: String(values.get("reason") || "").trim(),
  };
}

function validateCampaignPolicyPayload(payload) {
  if ([payload.daily_limit_minor, payload.monthly_limit_minor, payload.per_request_limit_minor].some((value) => value === null)) {
    toast("Укажите каждый лимит кампании в долларах и центах, минимум $0.01.", "error");
    return false;
  }
  if (payload.per_request_limit_minor > payload.daily_limit_minor || payload.daily_limit_minor > payload.monthly_limit_minor) {
    toast("Лимит одного запуска должен быть не больше дневного, а дневной — не больше месячного.", "error");
    return false;
  }
  return true;
}

function acceptGenerationSpendMutation(raw) {
  const source = raw?.data ?? raw ?? {};
  state.generationSpend.data = source?.overview ?? source;
  state.generationSpend.status = "ready";
  state.generationSpend.updatedAt = Date.now();
}

async function submitGenerationCampaignCreate(form) {
  if (!canManageGenerationSpendPolicy()) {
    toast("Создавать кампании может только владелец или администратор команды.", "error");
    return;
  }
  const values = new FormData(form);
  const payload = {
    name: String(values.get("name") || "").trim(),
    ...campaignPolicyPayload(values, values.get("paid_generation_enabled") === "true"),
  };
  if (!validateCampaignPolicyPayload(payload)) return;
  state.generationSpend.requestId += 1;
  state.generationSpend.saving = true;
  state.generationSpend.notice = "";
  state.generationSpend.error = null;
  setFormBusy(form, true, "Создаём…");
  try {
    const raw = await state.api.createGenerationCampaign(payload);
    acceptGenerationSpendMutation(raw);
    state.generationSpend.notice = `Кампания «${payload.name}» создана и готова к выбору в платном запуске.`;
    toast(state.generationSpend.notice, "success");
  } catch (error) {
    state.generationSpend.error = actionErrorMessage(error);
    toast(state.generationSpend.error, "error");
  } finally {
    state.generationSpend.saving = false;
    if (form.isConnected) setFormBusy(form, false);
    if (state.route.path === "/workspace/team") renderWorkspace("team");
  }
}

async function submitGenerationCampaignPolicy(form, submitter) {
  if (!canManageGenerationSpendPolicy()) {
    toast("Изменять бюджет кампании может только владелец или администратор команды.", "error");
    return;
  }
  const action = String(submitter?.value || "save");
  if (!["save", "pause", "resume"].includes(action)) {
    toast("Не удалось определить действие с бюджетом кампании.", "error");
    return;
  }
  const values = new FormData(form);
  const campaign = normalizeGenerationSpendOverview(state.generationSpend.data || {}).campaigns
    .find((item) => item.id === String(form.dataset.campaignId || ""));
  const enabled = action === "pause"
    ? false
    : action === "resume"
      ? true
      : campaign?.policy?.paidGenerationEnabled === true;
  const payload = {
    ...campaignPolicyPayload(values, enabled),
    expected_version: Number(values.get("expected_version")),
  };
  if (!validateCampaignPolicyPayload(payload)) return;
  state.generationSpend.requestId += 1;
  state.generationSpend.saving = true;
  state.generationSpend.notice = "";
  state.generationSpend.error = null;
  setFormBusy(form, true, action === "pause" ? "Ставим на паузу…" : "Сохраняем…");
  try {
    const raw = await state.api.updateGenerationCampaignSpendPolicy(form.dataset.campaignId, payload);
    acceptGenerationSpendMutation(raw);
    state.generationSpend.notice = action === "pause"
      ? "Кампания поставлена на паузу. Новые платные ролики из её бюджета не запустятся."
      : action === "resume"
        ? "Кампания включена и снова доступна для платных запусков."
        : "Бюджет кампании сохранён.";
    toast(state.generationSpend.notice, "success");
  } catch (error) {
    state.generationSpend.error = actionErrorMessage(error);
    if ([error?.code, error?.serverCode].some((code) => String(code || "") === "generation_campaign_budget_policy_changed")) {
      await loadGenerationSpendOverview({ silent: true, force: true });
      state.generationSpend.error = "Бюджет кампании уже изменился в другой вкладке. Показана свежая версия — проверьте её и повторите действие.";
    }
    toast(state.generationSpend.error, "error");
  } finally {
    state.generationSpend.saving = false;
    if (form.isConnected) setFormBusy(form, false);
    if (state.route.path === "/workspace/team") renderWorkspace("team");
  }
}

async function submitGenerationSpendPolicy(form, submitter) {
  if (!canManageGenerationSpendPolicy()) {
    toast("Изменить денежные лимиты может только владелец или администратор команды.", "error");
    return;
  }
  const action = String(submitter?.value || "save");
  if (!["save", "pause", "resume"].includes(action)) {
    toast("Не удалось определить действие с денежным лимитом.", "error");
    return;
  }
  const values = new FormData(form);
  const current = normalizeGenerationSpendOverview(state.generationSpend.data || {});
  const enabled = action === "pause"
    ? false
    : action === "resume"
      ? true
      : current.policy.paidGenerationEnabled;
  const payload = {
    paid_generation_enabled: enabled,
    daily_limit_minor: usdInputToMinor(values.get("daily_limit_usd")),
    monthly_limit_minor: usdInputToMinor(values.get("monthly_limit_usd")),
    per_request_limit_minor: usdInputToMinor(values.get("per_request_limit_usd")),
    timezone: String(values.get("timezone") || current.policy.timezone || "Europe/Moscow"),
    reason: String(values.get("reason") || "").trim(),
    expected_version: Number(values.get("expected_version")),
  };
  if ([payload.daily_limit_minor, payload.monthly_limit_minor, payload.per_request_limit_minor].some((value) => value === null)) {
    toast("Укажите каждый лимит в долларах и центах, минимум $0.01.", "error");
    return;
  }
  if (
    payload.per_request_limit_minor > payload.daily_limit_minor
    || payload.daily_limit_minor > payload.monthly_limit_minor
  ) {
    toast("Лимит одного запуска должен быть не больше дневного, а дневной — не больше месячного.", "error");
    return;
  }

  // Invalidate any overview request that started before this mutation. Its
  // stale response must never overwrite the newly saved policy or pause.
  state.generationSpend.requestId += 1;
  state.generationSpend.saving = true;
  state.generationSpend.notice = "";
  state.generationSpend.error = null;
  setFormBusy(form, true, action === "pause" ? "Останавливаем…" : "Сохраняем…");
  try {
    const raw = await state.api.updateGenerationSpendPolicy(payload);
    state.generationSpend.data = raw?.data ?? raw ?? state.generationSpend.data;
    state.generationSpend.status = "ready";
    state.generationSpend.updatedAt = Date.now();
    state.generationSpend.notice = action === "pause"
      ? "Платные запуски остановлены. Уже отправленные задачи продолжат безопасную обработку."
      : action === "resume"
        ? "Платные запуски включены с новыми лимитами."
        : "Денежные лимиты сохранены.";
    toast(state.generationSpend.notice, "success");
  } catch (error) {
    state.generationSpend.error = actionErrorMessage(error);
    if (
      [error?.code, error?.serverCode].some((code) =>
        ["generation_budget_policy_changed", "generation_spend_policy_version_conflict"].includes(
          String(code || ""),
        )
      )
    ) {
      await loadGenerationSpendOverview({ silent: true, force: true });
      state.generationSpend.error = "Лимиты уже изменились в другой вкладке. Показана свежая версия — проверьте её и повторите действие.";
    }
    toast(state.generationSpend.error, "error");
  } finally {
    state.generationSpend.saving = false;
    if (form.isConnected) setFormBusy(form, false);
    if (state.route.path === "/workspace/team") renderWorkspace("team");
  }
}

function usdInputToMinor(value) {
  const normalized = String(value ?? "").trim();
  if (!/^\d{1,7}(?:\.\d{1,2})?$/u.test(normalized)) return null;
  const number = Number(normalized);
  const minor = Math.round(number * 100);
  return Number.isSafeInteger(minor) && minor >= 1 && minor <= 100_000_000 ? minor : null;
}

async function submitMyWorkFilters(form) {
  state.myWork.filters = readMyWorkFilters(form);
  state.myWork.selectedViewId = "";
  state.myWork.notice = "";
  state.myWork.error = "";
  await loadSection("work");
}

async function submitSavedMyWorkView(form) {
  const values = new FormData(form);
  const name = String(values.get("name") || "").trim();
  const makeDefault = values.get("is_default") === "true";
  setFormBusy(form, true, "Сохраняем…");
  try {
    const raw = await state.api.savedWorkViews({
      action: "upsert",
      name,
      filters: state.myWork.filters,
      is_default: makeDefault,
    });
    let views = normalizeSavedWorkViews(raw);
    if (!views.length) {
      await reloadSavedWorkViews();
      views = state.myWork.savedViews;
    } else {
      state.myWork.savedViews = views;
      state.myWork.viewsLoaded = true;
    }
    const saved = views
      .filter((view) => view.name.toLocaleLowerCase("ru-RU") === name.toLocaleLowerCase("ru-RU"))
      .sort((left, right) => String(right.updatedAt).localeCompare(String(left.updatedAt)))[0]
      || views[0];
    state.myWork.selectedViewId = saved?.id || "";
    state.myWork.notice = `Фильтр «${name}» сохранён${makeDefault ? " и назначен основным" : ""}.`;
    state.myWork.error = "";
    form.reset();
  } catch (error) {
    state.myWork.error = actionErrorMessage(error);
  } finally {
    if (form.isConnected) setFormBusy(form, false);
    if (state.route.path === "/workspace/work") renderWorkspace("work");
  }
}

function handleChange(event) {
  handleFormActivity(event);

  if (event.target.matches("[data-training-practical-source]")) {
    const form = event.target.closest("[data-training-practical-form]");
    if (form) syncTrainingPracticalSource(form, event.target.value);
  }

  if (event.target.matches("[data-account-check]")) {
    const guide = event.target.closest("[data-account-guide]");
    const slug = String(guide?.dataset.accountGuide || "");
    const checks = Array.from(guide?.querySelectorAll("[data-account-check]:checked") || [])
      .map((input) => String(input.dataset.accountCheck || ""))
      .filter(Boolean);
    persistAccountLaunchChecks(slug, checks);
  }

  if (event.target.matches("[data-course-ack]")) {
    syncCourseCompletionButton();
  }

  const knowledgeQuestion = event.target.closest?.("[data-check-question]");
  if (knowledgeQuestion) {
    knowledgeQuestion.setAttribute("aria-invalid", "false");
    knowledgeQuestion.classList.remove("incorrect");
  }

  if (event.target.matches("[data-training-check]")) {
    const root = trainingWalkthroughRoot(event.target);
    syncTrainingWalkthroughStatus(root);
    persistTrainingWalkthroughState(root);
    syncCourseCompletionButton();
  }

  if (event.target.matches("[data-training-practice-option]")) {
    const root = trainingWalkthroughRoot(event.target);
    evaluateTrainingPractice(root, event.target.value);
    persistTrainingWalkthroughState(root);
    syncCourseCompletionButton();
  }

  if (event.target.closest("#exam-form")) {
    const examCard = event.target.closest("[data-exam-question]");
    examCard?.setAttribute("aria-invalid", "false");
    const questions = finalExamQuestions();
    const answered = questions.filter((question) =>
      document.querySelector(`input[name="${CSS.escape(`answer_${question.code}`)}"]:checked`),
    ).length;
    const counter = document.querySelector("#exam-answer-count");
    if (counter) counter.textContent = `${answered} из ${questions.length} отвечено`;
  }

  if (event.target.id === "media-file") {
    showSelectedFile(event.target.files?.[0]);
  }

  const mediaForm = event.target.closest("#media-upload-form");
  if (mediaForm && event.target.name === "kind") {
    syncMediaProductFields(mediaForm);
  }

  const generationForm = event.target.closest("#mock-batch-form");
  if (generationForm && ["generation_mode", "campaign_id"].includes(event.target.name)) {
    syncGenerationModeForm(generationForm);
  }

  const contentReviewForm = event.target.closest("#content-review-form");
  if (contentReviewForm) {
    if (
      event.target.name === "media_id"
      && String(state.contentReview.durableEvidence?.mediaId || "") !== String(event.target.value || "")
    ) {
      state.contentReview.durableEvidence = null;
    }
    syncContentReviewFormVisibility(contentReviewForm);
    persistContentReviewDraft(contentReviewForm);
  }
}

function submitAccountAdvertisingCheck(form) {
  const values = new FormData(form);
  const result = evaluateAdvertisingAnswers({
    value_exchange: values.get("value_exchange"),
    brand_control: values.get("brand_control"),
    product_focus: values.get("product_focus"),
  });
  const target = form.querySelector("#account-ad-result");
  if (!target) return;
  target.dataset.status = result.status;
  target.innerHTML = `<strong>${escapeHtml(result.title)}</strong><p>${escapeHtml(result.message)}</p>`;
  target.focus?.({ preventScroll: true });
  if (result.status === "review") toast("Публикация остановлена до проверки руководителем.", "info");
}

function handleFormActivity(event) {
  const rationale = event.target.closest?.(".knowledge-rationale textarea");
  if (rationale) {
    const counter = rationale.closest(".knowledge-rationale")?.querySelector("[data-rationale-count]");
    if (counter) counter.textContent = String(rationale.value.length);
  }
  const courseAssessmentForm = event.target.closest?.("#course-check-form");
  if (courseAssessmentForm) persistCourseAssessmentDraft(courseAssessmentForm);
  const finalExamForm = event.target.closest?.("#exam-form");
  if (finalExamForm) persistFinalExamDraft(finalExamForm);
  const practicalReviewForm = event.target.closest?.(".training-practical-review__form");
  if (practicalReviewForm) practicalReviewForm.dataset.dirty = "true";
  const form = event.target.closest?.("#workspace-content form");
  if (form) {
    form.dataset.dirty = "true";
    if (form.id === "content-review-form") persistContentReviewDraft(form);
  }
}

function clearWorkspaceDropTargets() {
  document.querySelectorAll("[data-workspace-drop-folder].is-drop-target").forEach((target) => {
    target.classList.remove("is-drop-target");
    target.removeAttribute("data-drop-active");
  });
  document.querySelectorAll(".workspace-board__item.is-dragging").forEach((item) => {
    item.classList.remove("is-dragging");
  });
}

function handleDragStart(event) {
  const handle = event.target.closest?.("[data-workspace-drag-item]");
  if (!handle || state.workspaceBoard.busy) return;
  const entityType = String(handle.dataset.entityType || "");
  const entityId = String(handle.dataset.entityId || "");
  const itemKey = String(handle.dataset.itemKey || workspaceBoardItemKey(entityType, entityId));
  if (!entityType || !entityId || !itemKey) {
    event.preventDefault();
    return;
  }
  state.workspaceBoard.dragging = { entityType, entityId, itemKey };
  handle.closest(".workspace-board__item")?.classList.add("is-dragging");
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", itemKey);
  }
}

function handleDragOver(event) {
  const folder = event.target.closest?.("[data-workspace-drop-folder]");
  if (folder && state.workspaceBoard.dragging && !state.workspaceBoard.busy) {
    event.preventDefault();
    clearWorkspaceDropTargets();
    folder.classList.add("is-drop-target");
    folder.setAttribute("data-drop-active", "true");
    if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
    return;
  }
  const zone = event.target.closest("[data-upload-zone]");
  if (!zone) return;
  event.preventDefault();
  zone.classList.add("dragover");
}

function handleDragLeave(event) {
  const folder = event.target.closest?.("[data-workspace-drop-folder]");
  if (folder && !folder.contains(event.relatedTarget)) {
    folder.classList.remove("is-drop-target");
    folder.removeAttribute("data-drop-active");
  }
  const zone = event.target.closest("[data-upload-zone]");
  if (zone && !zone.contains(event.relatedTarget)) zone.classList.remove("dragover");
}

async function handleDrop(event) {
  const folder = event.target.closest?.("[data-workspace-drop-folder]");
  if (folder && state.workspaceBoard.dragging) {
    event.preventDefault();
    const dragging = { ...state.workspaceBoard.dragging };
    const destinationFolderId = String(folder.dataset.folderId || "root");
    state.workspaceBoard.dragging = null;
    clearWorkspaceDropTargets();
    await moveWorkspaceBoardItem({ ...dragging, destinationFolderId });
    return;
  }
  const zone = event.target.closest("[data-upload-zone]");
  if (!zone) return;
  event.preventDefault();
  zone.classList.remove("dragover");
  const file = event.dataTransfer?.files?.[0];
  const input = zone.querySelector('input[type="file"]');
  if (!file || !input) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  input.files = transfer.files;
  zone.closest("form")?.setAttribute("data-dirty", "true");
  showSelectedFile(file);
}

function handleDragEnd() {
  state.workspaceBoard.dragging = null;
  clearWorkspaceDropTargets();
}

function showSelectedFile(file) {
  const target = document.querySelector("#selected-file-name");
  if (target) target.textContent = file ? `${file.name} · ${formatBytes(file.size)}` : "";
}

function syncMediaProductFields(form) {
  const required = mediaKindRequiresProduct(form.elements.kind?.value);
  const fields = form.querySelector("[data-media-product-fields]");
  if (fields) fields.hidden = !required;
  for (const name of ["sku", "product_name"]) {
    const input = form.elements[name];
    if (!input) continue;
    input.disabled = !required;
    input.required = required;
    if (!required) input.setCustomValidity("");
  }
}

function syncGenerationModeForm(form) {
  const mode = String(form.elements.generation_mode?.value || "mock");
  const sku = realGenerationSku(mode);
  const real = sku !== null;
  const seedance = mode === REAL_SEEDANCE_MODE;
  const count = form.elements.count;
  const brief = form.elements.brief;
  const format = form.elements.format;
  const confirmation = form.querySelector("#real-generation-confirmation");
  const campaignField = form.querySelector("#generation-campaign-field");
  const campaignSelect = form.elements.campaign_id;
  const confirmationInput = form.elements.real_spend_confirmation;
  const submit = form.querySelector("#generation-submit");
  const countHint = form.querySelector("#generation-count-hint");
  const mediaHint = form.querySelector("#generation-media-hint");
  const price = form.querySelector("#real-generation-price");
  const note = form.querySelector("#real-generation-note");
  const confirmationCopy = form.querySelector("#real-generation-confirmation-copy");
  const briefHint = form.querySelector("#generation-brief-hint");
  const spendAllowed = !real || realGenerationSpendAllowed(mode, campaignSelect?.value || "");

  if (count) {
    if (real) {
      if (!count.readOnly) count.dataset.mockCount = count.value;
      count.value = "1";
      count.max = "1";
      count.readOnly = true;
    } else {
      count.max = String(MAX_MOCK_BATCH_SIZE);
      count.readOnly = false;
      count.value = count.dataset.mockCount || count.value || "5";
    }
  }
  if (brief) {
    brief.required = real;
  }
  if (format) {
    format.disabled = Boolean(sku?.format);
    if (sku?.format) format.value = sku.format;
  }
  if (confirmation) confirmation.hidden = !real;
  if (campaignField) campaignField.hidden = !real;
  if (campaignSelect) {
    campaignSelect.disabled = !real;
    campaignSelect.required = real;
  }
  if (confirmationInput) {
    confirmationInput.required = real;
    if (!real) {
      confirmationInput.checked = false;
    } else if (confirmationInput.value !== sku.confirmation) {
      confirmationInput.value = sku.confirmation;
      confirmationInput.checked = false;
    }
  }
  form.querySelectorAll('input[name="media_id"]').forEach((input) => {
    input.type = real ? "radio" : "checkbox";
  });
  if (countHint) {
    countHint.textContent = real
      ? "Платный режим всегда создаёт ровно одно видео."
      : `Можно подготовить от 1 до ${MAX_MOCK_BATCH_SIZE} тестовых вариантов.`;
  }
  if (mediaHint) {
    mediaHint.textContent = real
      ? "Для платного запуска выберите ровно один исходник."
      : "Для тестовых вариантов можно выбрать один или несколько исходников.";
  }
  if (price && sku) {
    price.textContent = `Ориентировочная стоимость: $${sku.estimatedUsd} (${sku.estimatedCredits} кредитов). Итоговая сумма зависит от тарифа сервиса.`;
  }
  if (note && sku) {
    note.textContent = seedance
      ? "Голос создаётся по сценарию, но реплика может отличаться. Обязательно прослушайте ролик перед публикацией."
      : "Этот режим создаёт видео без сгенерированной речи.";
  }
  if (confirmationCopy && sku) {
    confirmationCopy.textContent = `${sku.durationSeconds} секунд · одно видео · около $${sku.estimatedUsd}`;
  }
  if (briefHint) {
    briefHint.textContent = seedance
      ? "Перед оплатой вставьте сценарий именно выбранного товара и проверьте дословную реплику."
      : "Для платного режима опишите один ролик без неподтверждённых обещаний.";
  }
  const spendSnapshot = form.closest(".card")?.querySelector(".generation-spend-snapshot");
  if (spendSnapshot) {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = generationSpendSnapshotMarkup(state.generationSpend, {
      requestMinor: sku?.estimatedMinor ?? REAL_GENERATION_SKUS[REAL_GEN4_MODE].estimatedMinor,
      campaignId: campaignSelect?.value || "",
    }).trim();
    if (wrapper.firstElementChild) spendSnapshot.replaceWith(wrapper.firstElementChild);
  }
  if (submit) {
    submit.disabled = state.realGenerationStartInFlight
      || !form.querySelector('input[name="media_id"]')
      || !spendAllowed;
    submit.textContent = state.realGenerationStartInFlight
      ? "Проверяем платный запуск — не повторяйте"
      : real && !spendAllowed
        ? "Платный запуск остановлен лимитом"
        : (real ? `Создать одно платное видео · около $${sku.estimatedUsd}` : "Создать тестовые варианты");
  }
}


async function submitLogin(form) {
  const values = new FormData(form);
  const email = String(values.get("email") || "").trim();
  const password = String(values.get("password") || "");
  setFormBusy(form, true, "Проверяем…");
  try {
    const { data, error } = await withUiTimeout(
      state.supabase.auth.signInWithPassword({ email, password }),
      AUTH_REQUEST_TIMEOUT_MS,
      "Сервер входа не ответил за 15 секунд. Проверьте соединение и повторите.",
    );
    if (error) throw error;
    state.session = data.session;
    state.user = data.user;
    state.forcePassword = requiresPasswordChange(data.user);
    state.authPurpose = state.forcePassword ? "temporary" : null;
    await track("login_succeeded", { method: "password" });
    if (state.forcePassword) navigate("/set-password", true);
    else {
      await loadBootstrap();
      if (membershipLockDetails()) navigate("/access-locked", true);
      else if (hasWorkspaceAccess()) navigate("/workspace/home", true);
      else navigate("/learn", true);
    }
  } catch (error) {
    renderLogin(authErrorMessage(error), email);
  }
}

async function submitReset(form) {
  const email = normalizeAccessCenterEmail(new FormData(form).get("email"));
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/u.test(email) || email.length > 254) {
    toast("Укажите рабочую почту в формате name@company.ru.", "error");
    return;
  }

  const previousReceipt = state.resetReceipt;
  const retrySameRequest = shouldRetrySamePublicRecoveryRequest(previousReceipt);
  const requestId = retrySameRequest && previousReceipt?.requestId
    ? previousReceipt.requestId
    : crypto.randomUUID();
  state.resetReceipt = retrySameRequest
    ? {
      ...previousReceipt,
      requestId,
      status: "requesting",
    }
    : {
      receiptToken: "",
      requestId,
      status: "requesting",
      cooldownUntil: 0,
      maskedEmail: "",
    };
  persistPublicRecoveryReceipt(state.resetReceipt);
  setFormBusy(form, true, retrySameRequest ? "Проверяем тот же запрос…" : "Отправляем…");

  try {
    const receipt = await withUiTimeout(
      state.api.requestPublicPasswordRecovery({ email, requestId }),
      AUTH_REQUEST_TIMEOUT_MS,
      "Сервер восстановления пока не подтвердил результат.",
    );
    state.resetReceipt = publicRecoveryReceiptState(receipt, {
      maskedEmail: maskEmail(email),
    });
    persistPublicRecoveryReceipt(state.resetReceipt);
    renderResetRequest();
  } catch (error) {
    const retryAfterSeconds = Number(error?.details?.retry_after_seconds || 0);
    const serverCooldownUntil = Number.isInteger(retryAfterSeconds) && retryAfterSeconds > 0
      ? Date.now() + retryAfterSeconds * 1000
      : 0;
    state.resetReceipt = {
      ...state.resetReceipt,
      status: "outcome_unknown",
      cooldownUntil: Math.max(
        Number(state.resetReceipt?.cooldownUntil || 0),
        serverCooldownUntil,
      ),
    };
    persistPublicRecoveryReceipt(state.resetReceipt);
    renderResetRequest();
    toast(
      "Ответ сервера не подтверждён. Квитанция и номер запроса сохранены — введите тот же адрес и повторите проверку.",
      "error",
    );
  } finally {
    if (form.isConnected) setFormBusy(form, false);
  }
}

async function submitPassword(form) {
  const values = new FormData(form);
  const password = String(values.get("password") || "");
  const confirmation = String(values.get("password_confirmation") || "");
  if (password !== confirmation) {
    renderSetPassword("Пароли не совпадают. Введите их ещё раз.");
    return;
  }
  if (
    password.length < 10 || password.length > 128 ||
    !/[a-z]/u.test(password) || !/[A-Z]/u.test(password) || !/[0-9]/u.test(password) ||
    Array.from(password).some((character) => /\p{Cc}/u.test(character))
  ) {
    renderSetPassword("Используйте 10–128 символов, строчную и заглавную латинские буквы и цифру.");
    return;
  }
  setFormBusy(form, true, "Сохраняем…");
  try {
    if (requiresPasswordChange(state.user)) {
      const { data, error } = await withUiTimeout(
        state.supabase.functions.invoke("creator-set-password", { body: { password } }),
        AUTH_REQUEST_TIMEOUT_MS,
        "Сервер смены пароля не ответил за 15 секунд. Повторите — рабочие разделы остаются закрыты.",
      );
      if (error) throw await normalizePasswordFunctionError(error);
      if (!data?.ok || data.password_change_required !== false) {
        throw new Error("required_password_change_incomplete");
      }
      state.user = {
        ...state.user,
        app_metadata: data.app_metadata || {
          ...(state.user?.app_metadata || {}),
          [PASSWORD_CHANGE_REQUIRED_MARKER]: false,
          [PASSWORD_CHANGE_COMPLETED_MARKER]: true,
        },
      };
      try {
        const { data: refreshed, error: refreshError } = await withUiTimeout(
          state.supabase.auth.refreshSession(),
          AUTH_REQUEST_TIMEOUT_MS,
          "refresh_after_password_change_timeout",
        );
        if (!refreshError && refreshed?.session) {
          state.session = refreshed.session;
          state.user = refreshed.user || refreshed.session.user || state.user;
        }
      } catch (refreshError) {
        console.warn("Session refresh after required password change failed", refreshError);
      }
    } else {
      const { data, error } = await withUiTimeout(
        state.supabase.auth.updateUser({ password }),
        AUTH_REQUEST_TIMEOUT_MS,
        "Сервер смены пароля не ответил за 15 секунд. Повторите попытку.",
      );
      if (error) throw error;
      state.user = data.user || state.user;
    }
    state.forcePassword = false;
    state.authPurpose = null;
    await loadBootstrap();
    toast("Пароль сохранён.", "success");
    if (membershipLockDetails()) navigate("/access-locked", true);
    else navigate("/learn", true);
  } catch (error) {
    renderSetPassword(authErrorMessage(error));
  }
}

async function submitCourseKnowledgeCheck(form) {
  const courseCode = String(form.dataset.courseCode || "");
  const course = learningCourses().find((item) => item.code === courseCode);
  const check = course?.knowledgeCheck;
  if (!check?.questions?.length) {
    toast("Рабочая аттестация блока не загрузилась. Обновите страницу.", "error");
    return;
  }

  const answers = {};
  const rationales = {};
  for (const question of check.questions) {
    const inputName = `check_${courseCode}_${question.id}`;
    const selected = Array.from(form.querySelectorAll(`input[name="${CSS.escape(inputName)}"]:checked`));
    if (!selected.length) {
      const fieldset = form.querySelector(`[data-check-question="${CSS.escape(question.id)}"]`);
      fieldset?.classList.add("incorrect");
      fieldset?.setAttribute("aria-invalid", "true");
      fieldset?.setAttribute("tabindex", "-1");
      scrollElementIntoView(fieldset, "center");
      fieldset?.focus({ preventScroll: true });
      toast("Ответьте на все вопросы рабочей аттестации.", "error");
      return;
    }
    answers[question.id] = question.type === "multi_select"
      ? selected.map((input) => input.value)
      : selected[0].value;
    if (question.requiresRationale) {
      const rationaleName = `reason_${courseCode}_${question.id}`;
      const rationale = String(form.elements.namedItem(rationaleName)?.value || "").replace(/\s+/gu, " ").trim();
      const rationaleWords = rationale.toLocaleLowerCase("ru-RU").match(/[\p{L}\p{N}]+/gu) || [];
      const rationaleStopWords = new Set(["это", "как", "для", "что", "или", "при", "без", "под", "над", "его", "её", "она", "они", "там", "тут", "так", "вот", "the", "and", "for", "with", "this", "that"]);
      const meaningfulWords = new Set(rationaleWords.filter((word) => (
        word.length >= 3
        && /\p{L}/u.test(word)
        && /[аеёиоуыэюяaeiouy]/u.test(word)
        && !rationaleStopWords.has(word)
      )));
      const structuredRationale = /риск\s*:.+(проверка|доказательство)\s*:.+(действие|следующий шаг)\s*:/iu.test(rationale);
      if (rationale.length < 40 || rationaleWords.length < 7 || meaningfulWords.size < 5 || !structuredRationale) {
        const fieldset = form.querySelector(`[data-check-question="${CSS.escape(question.id)}"]`);
        fieldset?.classList.add("incorrect");
        fieldset?.setAttribute("aria-invalid", "true");
        scrollElementIntoView(fieldset, "center");
        form.elements.namedItem(rationaleName)?.focus({ preventScroll: true });
        toast("Заполните три части своими словами: «Риск: … Проверка: … Действие: …». Нужно минимум 40 знаков, 7 слов и 5 разных содержательных слов.", "error");
        return;
      }
      rationales[question.id] = rationale;
    }
  }

  setFormBusy(form, true, "Проверяем на сервере…");
  try {
    const raw = await state.api.submitCourseCheck(courseCode, answers, rationales);
    const source = raw?.result || raw?.data || raw || {};
    const passed = normalizeBoolean(source.passed);
    const questionCount = Math.max(1, Number(source.question_count ?? source.questionCount ?? check.questions.length));
    const requiredCorrect = Math.max(1, Number(source.required_correct ?? source.requiredCorrect ?? check.passScore));
    const reasoningCount = passed ? questionCount : 0;

    for (const question of check.questions) {
      const fieldset = form.querySelector(`[data-check-question="${CSS.escape(question.id)}"]`);
      fieldset?.classList.remove("correct", "incorrect");
      fieldset?.setAttribute("aria-invalid", "false");
      if (passed) fieldset?.classList.add("correct");
    }

    state.courseCheckResults[courseCode] = {
      passed,
      score: passed ? requiredCorrect : 0,
      total: questionCount,
      status: passed ? "passed" : "retry_required",
    };
    if (passed) clearCourseAssessmentDraft(courseCode);
    else persistCourseAssessmentDraft(form);
    const nextMasteryStep = passed ? courseMasteryState(course).nextStep : "test";
    const nextInstruction = {
      lessons: "Теперь вернитесь к незавершённым урокам — тренер навыка покажет первый из них.",
      practice: "Теперь завершите обязательную лабораторию и дождитесь серверного подтверждения.",
      confirmation: "Теперь подтвердите финальный чек-лист готовности.",
      done: "Все четыре шага готовы — блок можно завершить.",
    }[nextMasteryStep] || "Тренер навыка покажет следующий обязательный шаг.";
    const result = form.querySelector("#course-check-result");
    if (result) {
      const feedback = String(source.feedback || (passed
        ? "Проверка пройдена."
        : "Повторите отмеченные темы и попробуйте ещё раз."));
      result.className = `knowledge-check-result ${passed ? "passed" : "failed"}`;
      result.innerHTML = passed
        ? `<strong>Серверная проверка пройдена: приняты все ${reasoningCount} обоснований.</strong><span>${escapeHtml(feedback)} ${escapeHtml(nextInstruction)}</span>`
        : `<strong>Попытка не зачтена — правильные ответы и точный балл не раскрываются.</strong><span>${escapeHtml(feedback)}</span>`;
    }
    const gate = document.querySelector("[data-course-check-gate]");
    if (gate) {
      gate.classList.toggle("passed", passed);
      gate.innerHTML = `<span aria-hidden="true">${passed ? "✓" : "?"}</span><strong>${passed ? "Аттестация пройдена" : "Аттестация пока не пройдена"}</strong>`;
    }
    syncCourseCompletionButton();
    await track("course_check_submitted", {
      module_code: courseCode,
      passed,
      question_count: questionCount,
    });
    toast(passed ? "Рабочая аттестация пройдена." : "Попытка не зачтена — повторите рабочий маршрут целиком.", passed ? "success" : "info");
  } catch (error) {
      toast(actionErrorMessage(error), "error");
  } finally {
    if (form.isConnected) setFormBusy(form, false);
  }
}

function syncCourseCompletionButton() {
  syncCourseMasteryPanel();
}

async function submitExam(form) {
  const questions = finalExamQuestions();
  const answers = {};
  const rationales = {};
  for (const question of questions) {
    const selected = [
      ...form.querySelectorAll(`input[name="${CSS.escape(`answer_${question.code}`)}"]:checked`),
    ];
    if (!selected.length) {
      const card = selectedQuestionCard(question.code);
      card?.setAttribute("aria-invalid", "true");
      card?.setAttribute("tabindex", "-1");
      scrollElementIntoView(card, "center");
      card?.focus({ preventScroll: true });
      toast("Ответьте на все 12 вопросов.", "error");
      return;
    }
    answers[question.code] = selected.map((input) => input.value);
  }

  const normalizedRationales = new Set();
  for (const questionCode of FINAL_EXAM_RATIONALE_CODES) {
    const rationaleName = `rationale_${questionCode}`;
    const textarea = form.elements.namedItem(rationaleName);
    const rationale = String(textarea?.value || "").replace(/\s+/gu, " ").trim();
    const card = form.querySelector(`[data-exam-question="${CSS.escape(questionCode)}"]`);
    if (!finalExamRationaleIsValid(rationale)) {
      card?.setAttribute("aria-invalid", "true");
      scrollElementIntoView(card, "center");
      textarea?.focus({ preventScroll: true });
      persistFinalExamDraft(form);
      toast("Для четырёх ключевых кейсов нужен собственный разбор: «Риск: … Проверка: … Действие: …». Минимум 40 знаков, 7 слов и 5 содержательных слов.", "error");
      return;
    }
    const normalizedRationale = rationale.toLocaleLowerCase("ru-RU");
    if (normalizedRationales.has(normalizedRationale)) {
      card?.setAttribute("aria-invalid", "true");
      scrollElementIntoView(card, "center");
      textarea?.focus({ preventScroll: true });
      persistFinalExamDraft(form);
      toast("Нельзя копировать одно обоснование в разные кейсы. Разберите риск, проверку и действие отдельно для каждой ситуации.", "error");
      return;
    }
    normalizedRationales.add(normalizedRationale);
    rationales[questionCode] = rationale;
  }

  persistFinalExamDraft(form);
  setFormBusy(form, true, "Проверяем на сервере…");
  try {
    const raw = await state.api.submitExam(answers, rationales);
    const source = raw?.result || raw?.data || raw || {};
    state.examResult = {
      passed: normalizeBoolean(source.passed),
      total: Number(source.question_count ?? source.total ?? questions.length),
    };
    if (state.examResult.passed) clearFinalExamDraft();
    await track("exam_submitted", {
      passed: state.examResult.passed,
      attempt_number: state.bootstrap.training.exam.attemptCount + 1,
    });
    await loadBootstrap();
    if (!state.examResult.passed) {
      state.route = { path: "/learn/exam", query: new URLSearchParams() };
      render();
      window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
      toast("Экзамен не зачтён. Точный балл скрыт — повторите весь рабочий маршрут.", "info");
    } else if (hasWorkspaceAccess()) {
      toast("Экзамен сдан. Рабочий кабинет открыт.", "success");
      navigate("/workspace/home", true);
    } else {
      toast("Экзамен сдан. Теперь руководитель должен назначить вам рабочую роль.", "success");
      state.route = { path: "/learn/exam", query: new URLSearchParams() };
      render();
      window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
    }
  } catch (error) {
    await loadBootstrap();
    state.route = { path: "/learn/exam", query: new URLSearchParams() };
    render();
      toast(actionErrorMessage(error), "error");
  }
}

async function submitGenerationBatch(form) {
  const values = new FormData(form);
  const mode = String(values.get("generation_mode") || "mock");
  if (isRealGenerationMode(mode)) {
    await submitRealGeneration(form, values, mode);
    return;
  }
  await submitMockBatch(form, values);
}

async function submitRealGenerationReconciliation(form, submitter) {
  const resolution = String(submitter?.value || "");
  const values = new FormData(form);
  const jobId = String(form.dataset.jobId || "");
  const incidentId = String(form.dataset.incidentId || "");
  const providerTaskId = String(values.get("provider_task_id") || "").trim();
  const evidenceReference = String(values.get("evidence_reference") || "").trim();
  const reason = String(values.get("reason") || "").trim();

  if (!["owner", "admin"].includes(state.bootstrap?.membership?.role)) {
    toast("Ручную сверку платного запуска может выполнить только владелец или администратор.", "error");
    return;
  }
  if (!["attach_existing_task", "confirm_no_submission"].includes(resolution)) {
    toast("Выберите результат ручной сверки.", "error");
    return;
  }
  if (values.get("manual_confirmation") !== "confirmed") {
    toast("Подтвердите, что вручную проверили запуск в панели Runway.", "error");
    return;
  }
  if (resolution === "attach_existing_task" && !providerTaskId) {
    toast("Для прикрепления укажите точный Runway task ID.", "error");
    form.elements.provider_task_id?.focus();
    return;
  }

  setFormBusy(form, true, resolution === "attach_existing_task"
    ? "Проверяем Runway task…"
    : "Фиксируем отсутствие task…");
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  try {
    const result = await state.api.reconcileRealGeneration(jobId, {
      incident_id: incidentId,
      resolution,
      provider_task_id: providerTaskId,
      evidence_reference: evidenceReference,
      reason,
    });
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id) return;
    applyRealGenerationResult(jobId, result, { renderNow: false, source: "manual" });
    state.sections.generation.status = "idle";
    state.sections.tasks.status = "idle";
    if (resolution === "attach_existing_task") {
      toast("Runway task подтверждён и прикреплён. Портал продолжит обработку без повторного платного запуска.", "success");
    } else {
      toast("Отсутствие Runway task зафиксировано. Этот запуск закрыт без списания; новый создаётся отдельно.", "success");
    }
  } catch (error) {
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id) return;
    toast(actionErrorMessage(error), "error");
  } finally {
    if (
      requestEpoch === state.dataEpoch
      && requestUserId === state.user?.id
      && form.isConnected
    ) {
      setFormBusy(form, false);
    }
    if (state.route.path === "/workspace/generation") render();
    scheduleRealGenerationPolling(500);
  }
}

async function submitRealGeneration(form, values, mode) {
  if (state.realGenerationStartInFlight) {
    toast("Платный запуск уже отправляется. Дождитесь результата текущего запроса.", "info");
    return;
  }
  if (!REAL_GENERATION_ENABLED) {
    toast("Платная генерация выключена в конфигурации портала.", "error");
    return;
  }
  const generationSku = realGenerationSku(mode);
  if (!generationSku) {
    toast("Выберите точный платный режим генерации.", "error");
    return;
  }
  const campaignId = String(values.get("campaign_id") || "").trim();
  if (!campaignId) {
    toast("Выберите активную кампанию из свежей денежной сводки.", "error");
    return;
  }
  if (!realGenerationSpendAllowed(mode, campaignId)) {
    const overview = normalizeGenerationSpendOverview(state.generationSpend.data || {});
    toast(overview.blockerMessage || "Для выбранной цены не хватает утверждённого денежного остатка. Тестовый режим остаётся доступен.", "error");
    await loadGenerationSpendOverview({ silent: true, force: true });
    if (state.route.path === "/workspace/generation") renderWorkspace("generation");
    return;
  }
  const mediaIds = values.getAll("media_id").map(String);
  const brief = String(values.get("brief") || "").trim();
  if (Number(values.get("count")) !== 1) {
    toast("Платный режим создаёт ровно одно видео за запуск.", "error");
    return;
  }
  if (mediaIds.length !== 1) {
    toast("Для платного запуска выберите ровно одно точное фото товара.", "error");
    return;
  }
  if (!brief) {
    toast("Укажите одну главную мысль ролика.", "error");
    return;
  }
  if (values.get("real_spend_confirmation") !== generationSku.confirmation) {
    toast(`Подтвердите создание одного платного видео примерно за $${generationSku.estimatedUsd}.`, "error");
    return;
  }
  const payoutRub = canManageTeam() ? Number(values.get("payout_rub") || 0) : 0;
  if (!Number.isFinite(payoutRub) || payoutRub < 0 || payoutRub > 10_000 || !Number.isSafeInteger(Math.round(payoutRub * 100))) {
    toast("Вознаграждение должно быть от 0 до 10 000 ₽ за задачу.", "error");
    return;
  }

  const payload = {
    campaign_id: campaignId,
    sku: String(values.get("sku") || "").trim(),
    product_name: String(values.get("product_name") || "").trim(),
    count: 1,
    format: generationSku.format || String(values.get("format") || "9:16"),
    brief,
    media_ids: mediaIds,
    platform: String(values.get("platform") || "").trim(),
    destination_ref: String(values.get("destination_ref") || "").trim(),
    model: generationSku.model,
    duration_seconds: generationSku.durationSeconds,
    audio: generationSku.audio,
    spend_confirmation: String(values.get("real_spend_confirmation") || ""),
    ...(canManageTeam()
      ? {
          assignee_id: String(values.get("assignee_id") || state.user?.id || ""),
          payout_minor: Math.round(payoutRub * 100),
        }
      : {}),
  };

  state.realGenerationStartInFlight = true;
  state.realGenerationStartNotice = "";
  setFormBusy(form, true, "Отправляем платный запуск…");
  const draft = realGenerationDraftFromPayload(payload, mode);
  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const startRequest = state.api.startRealGeneration(payload);
  try {
    const firstWait = await withSoftTimeoutResult(startRequest, REAL_GENERATION_SOFT_TIMEOUT_MS);
    let result;
    if (firstWait.timedOut) {
      state.realGenerationStartNotice = "Подтверждение запуска занимает больше обычного. Запрос продолжает проверяться; не нажимайте запуск повторно и не подтверждайте новую оплату.";
      setFormBusy(form, false);
      if (form.elements.real_spend_confirmation) form.elements.real_spend_confirmation.checked = false;
      form.dataset.dirty = "true";
      render();
      result = await startRequest;
    } else {
      result = firstWait.result;
    }
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id) return;
    if (!result?.job?.id) throw new Error("Runway принял запрос без номера задачи. Обновите очередь.");
    const jobId = String(result.job.id);
    state.realGenerationDrafts.set(jobId, draft);
    state.lastRealGenerationJobId = jobId;
    applyRealGenerationResult(jobId, result, { renderNow: false });
    track("real_generation_started", {
      provider: "runway",
      model: generationSku.model,
      duration_seconds: generationSku.durationSeconds,
      audio: generationSku.audio,
      estimated_credits: generationSku.estimatedCredits,
      format: payload.format,
      platform: payload.platform,
      has_media: true,
    });
    state.realGenerationStartNotice = "";
    setFormBusy(form, false);
    form.dataset.dirty = "true";
    if (form.elements.real_spend_confirmation) form.elements.real_spend_confirmation.checked = false;
    syncGenerationModeForm(form);
    state.sections.generation.status = "idle";
    state.sections.placement.status = "idle";
    state.sections.tasks.status = "idle";
    const resultStatus = String(result.job.status || "queued").toLowerCase();
    if (resultStatus === "failed") {
      toast(generationFailureMessage(result.job.failure_code), "error");
    } else {
      toast(`Платный запуск принят: одно видео, ${generationSku.durationSeconds} секунд, ориентировочно $${generationSku.estimatedUsd}. Статус обновится автоматически.`, "success");
    }
    render();
  } catch (error) {
    if (requestEpoch !== state.dataEpoch || requestUserId !== state.user?.id) return;
    setFormBusy(form, false);
    if (form.elements.real_spend_confirmation) form.elements.real_spend_confirmation.checked = false;
    form.dataset.dirty = "true";
    if (error?.job?.id) {
      const jobId = String(error.job.id);
      state.realGenerationDrafts.set(jobId, draft);
      state.lastRealGenerationJobId = jobId;
      applyRealGenerationResult(jobId, { job: error.job }, { renderNow: false });
    }
    state.realGenerationStartNotice = "Запуск не подтверждён окончательно. Сначала обновите очередь и проверьте существующую задачу; не создавайте дубликат с новой оплатой.";
    state.sections.generation.status = "idle";
    toast(actionErrorMessage(error), "error");
  } finally {
    state.realGenerationStartInFlight = false;
    const renderedForm = document.querySelector("#mock-batch-form");
    if (renderedForm) {
      if (renderedForm.dataset.busy === "true") setFormBusy(renderedForm, false);
      if (renderedForm.elements.real_spend_confirmation) renderedForm.elements.real_spend_confirmation.checked = false;
      syncGenerationModeForm(renderedForm);
    }
    if (state.route.path === "/workspace/generation") render();
    scheduleRealGenerationPolling(500);
  }
}

async function submitMockBatch(form, values = new FormData(form)) {
  if (!MOCK_GENERATION_ENABLED) {
    toast("Тестовый режим сейчас недоступен.", "error");
    return;
  }
  const count = Number(values.get("count"));
  const mediaIds = values.getAll("media_id").map(String);
  if (!Number.isInteger(count) || count < 1 || count > MAX_MOCK_BATCH_SIZE) {
    toast(`Укажите от 1 до ${MAX_MOCK_BATCH_SIZE} вариантов.`, "error");
    return;
  }
  if (!mediaIds.length) {
    toast("Выберите хотя бы одно точное фото товара или упаковки из раздела «Материалы».", "error");
    return;
  }
  const payoutRub = canManageTeam() ? Number(values.get("payout_rub") || 0) : 0;
  if (!Number.isFinite(payoutRub) || payoutRub < 0 || payoutRub > 10_000 || !Number.isSafeInteger(Math.round(payoutRub * 100))) {
    toast("Вознаграждение должно быть от 0 до 10 000 ₽ за задачу.", "error");
    return;
  }
  setFormBusy(form, true, "Создаём тестовые варианты…");
  try {
    const payload = {
      sku: String(values.get("sku") || "").trim(),
      product_name: String(values.get("product_name") || "").trim(),
      count,
      format: String(values.get("format") || "9:16"),
      brief: String(values.get("brief") || "").trim(),
      media_ids: mediaIds,
      platform: String(values.get("platform") || "").trim(),
      destination_ref: String(values.get("destination_ref") || "").trim(),
      ...(canManageTeam()
        ? {
            assignee_id: String(values.get("assignee_id") || state.user?.id || ""),
            payout_minor: Math.round(payoutRub * 100),
          }
        : {}),
    };
    await state.api.createMockBatch(payload);
    await track("mock_batch_created", {
      count,
      format: payload.format,
      platform: payload.platform,
      has_media: true,
      delegated: Boolean(payload.assignee_id && payload.assignee_id !== state.user?.id),
      payout_minor: payload.payout_minor || 0,
    });
    delete form.dataset.dirty;
    form.reset();
    syncGenerationModeForm(form);
    state.sections.generation.status = "idle";
    state.sections.placement.status = "idle";
    state.sections.tasks.status = "idle";
    toast(`Создано ${count} тестовых вариантов без списаний. Задачи и публикации готовы.`, "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
      toast(actionErrorMessage(error), "error");
  }
}

async function submitManualMetric(form) {
  const values = new FormData(form);
  const views = nonnegativeInteger(values.get("views"));
  const clicks = nonnegativeInteger(values.get("clicks"));
  const orders = nonnegativeInteger(values.get("orders"));
  const revenueRub = Number(values.get("revenue_rub"));
  const observedAt = new Date(String(values.get("observed_at") || ""));
  if ([views, clicks, orders].some((value) => value === null)) {
    toast("Просмотры, переходы и заказы должны быть целыми неотрицательными числами.", "error");
    return;
  }
  if (!Number.isFinite(revenueRub) || revenueRub < 0 || !Number.isSafeInteger(Math.round(revenueRub * 100))) {
    toast("Укажите неотрицательную выручку в рублях.", "error");
    return;
  }
  if (Number.isNaN(observedAt.getTime()) || observedAt.getTime() > Date.now() + 5 * 60_000) {
    toast("Укажите фактическое время снятия метрик, не время в будущем.", "error");
    return;
  }

  setFormBusy(form, true, "Сохраняем снимок…");
  try {
    const placementId = String(values.get("placement_id") || "");
    await state.api.recordMetric({
      placement_id: placementId,
      views,
      clicks,
      orders,
      revenue_minor: Math.round(revenueRub * 100),
      observed_at: observedAt.toISOString(),
    });
    await track("metric_snapshot_recorded", {
      placement_id: placementId,
      source: "manual",
      views,
      clicks,
      orders,
    });
    delete form.dataset.dirty;
    state.sections.stats.status = "idle";
    toast("Текущие показатели сохранены как введённые вручную.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
      toast(actionErrorMessage(error), "error");
  }
}

async function submitWbAlias(form) {
  if (!["owner", "admin", "producer"].includes(state.bootstrap?.membership?.role)) {
    toast("Изменять связи артикулов может только руководитель или продюсер.", "error");
    return;
  }
  const values = new FormData(form);
  const payload = {
    sku: String(values.get("sku") || "").trim(),
    current_article: String(values.get("current_article") || "").trim(),
    alias_article: String(values.get("alias_article") || "").trim(),
    reason: String(values.get("reason") || "").trim(),
  };
  if (!/^\d{4,20}$/.test(payload.current_article) || !/^\d{4,20}$/.test(payload.alias_article)) {
    toast("Артикул WB должен содержать от 4 до 20 цифр.", "error");
    return;
  }
  if (payload.current_article === payload.alias_article) {
    toast("Текущий и старый артикулы должны отличаться.", "error");
    return;
  }

  setFormBusy(form, true, "Сохраняем историю…");
  try {
    await state.api.setWbAlias(payload);
    await track("wb_alias_recorded", {
      sku: payload.sku,
      current_article: payload.current_article,
      alias_article: payload.alias_article,
    });
    delete form.dataset.dirty;
    form.reset();
    state.sections.generation.status = "idle";
    state.sections.stats.status = "idle";
    toast("Связь артикулов добавлена. Исторические записи не перезаписаны.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
      toast(actionErrorMessage(error), "error");
  }
}

async function submitPayoutReject(form) {
  if (!["owner", "admin"].includes(state.bootstrap?.membership?.role)) {
    toast("Решение по выплате доступно только руководителю.", "error");
    return;
  }
  const notes = String(new FormData(form).get("notes") || "").trim();
  if (notes.length < 10) {
    toast("Укажите понятную причину отказа — не меньше 10 символов.", "error");
    return;
  }
  setFormBusy(form, true, "Отклоняем…");
  try {
    const payoutId = form.dataset.payoutId;
    await state.api.decidePayout(payoutId, "reject", { notes });
    await track("payout_decided", { payout_id: String(payoutId), decision: "reject" });
    delete form.dataset.dirty;
    state.sections.payouts.status = "idle";
    toast("Начисление отклонено, причина сохранена.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
      toast(actionErrorMessage(error), "error");
  }
}

async function submitPayoutPaid(form) {
  if (!["owner", "admin"].includes(state.bootstrap?.membership?.role)) {
    toast("Факт выплаты может подтвердить только руководитель.", "error");
    return;
  }
  const reference = String(new FormData(form).get("external_payment_reference") || "").trim();
  if (reference.length < 3) {
    toast("Укажите номер или ссылку внешней оплаты.", "error");
    return;
  }
  setFormBusy(form, true, "Фиксируем оплату…");
  try {
    const payoutId = form.dataset.payoutId;
    await state.api.decidePayout(payoutId, "paid", {
      external_payment_reference: reference,
    });
    await track("payout_decided", { payout_id: String(payoutId), decision: "paid" });
    delete form.dataset.dirty;
    state.sections.payouts.status = "idle";
    toast("Внешняя оплата подтверждена и добавлена в реестр.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
      toast(actionErrorMessage(error), "error");
  }
}

async function submitPlacement(form) {
  const values = new FormData(form);
  const finalUrl = String(values.get("final_url") || "").trim();
  const complianceAck = values.get("compliance_ack") === "confirmed";
  if (!isHttpsUrl(finalUrl)) {
    toast("Введите полный публичный HTTPS URL поста.", "error");
    return;
  }
  setFormBusy(form, true, "Проверяем ссылку…");
  try {
    const taskId = form.dataset.placementId;
    await state.api.confirmPlacement(taskId, finalUrl, complianceAck);
    await track("placement_confirmed", { task_id: String(taskId), hostname: new URL(finalUrl).hostname });
    delete form.dataset.dirty;
    state.sections.placement.status = "idle";
    state.sections.stats.status = "idle";
    state.sections.payouts.status = "idle";
    toast("Ссылка на пост сохранена. Публикация подтверждена.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
      toast(actionErrorMessage(error), "error");
  }
}

async function submitFeedback(form) {
  const values = new FormData(form);
  setFormBusy(form, true, "Отправляем…");
  try {
    await state.api.createFeedback({
      category: String(values.get("category") || "other"),
      section: String(values.get("section") || "feedback"),
      title: String(values.get("title") || "").trim(),
      description: String(values.get("description") || "").trim(),
    });
    await track("feedback_created", {
        category: String(values.get("category") || "other"),
      section: String(values.get("section") || "feedback"),
    });
    delete form.dataset.dirty;
    form.reset();
    state.sections.feedback.status = "idle";
    toast("Запрос отправлен. Спасибо — он уже в общей очереди.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
      toast(actionErrorMessage(error), "error");
  }
}

async function submitTeamInvites(form) {
  if (!canManageTeam() || !hasWorkspaceAccess()) {
    toast("Приглашать участников может только сертифицированный руководитель.", "error");
    return;
  }
  const raw = String(new FormData(form).get("emails") || "");
  const submitted = raw.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
  const emails = [...new Set(submitted.map((value) => value.toLowerCase()))];
  const emailPattern = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$/u;
  if (emails.length < 1 || emails.length > 50) {
    toast("Укажите от 1 до 50 уникальных email — по одному на строку.", "error");
    return;
  }
  const invalid = emails.find((email) => email.length > 320 || !emailPattern.test(email));
  if (invalid) {
    toast(`Проверьте адрес: ${invalid}`, "error");
    return;
  }

  setFormBusy(form, true, "Отправляем приглашения…");
  try {
    const { data, error } = await withUiTimeout(
      state.supabase.functions.invoke("creator-invite", { body: { emails } }),
      INVITE_REQUEST_TIMEOUT_MS,
      "invite_request_timeout",
    );
    if (error) throw await normalizeInviteFunctionError(error);
    if (!data || !Array.isArray(data.results)) {
      throw new Error("Supabase не вернул результаты приглашений.");
    }
    state.teamInviteResult = data;
    persistTeamInviteResult(data);
    delete form.dataset.dirty;
    state.sections.team.status = "idle";
    await track("team_invites_completed", {
      requested: Number(data.requested ?? emails.length),
      invited: Number(data.invited ?? 0),
      already_exists: Number(data.already_exists ?? 0),
      failed: Number(data.failed ?? 0),
    });
    toast(
      Number(data.invited || 0) > 0
        ? `Сервис принял запросов: ${Number(data.invited)}. Доставка писем ещё не подтверждена.`
        : "Запуск завершён. Проверьте статусы справа.",
      Number(data.failed || 0) > 0 ? "info" : "success",
    );
    render();
  } catch (error) {
    setFormBusy(form, false);
    if (String(error?.message || "") === "invite_request_timeout") {
      const uncertain = {
        ok: false,
        requested: emails.length,
        invited: 0,
        already_exists: 0,
        failed: emails.length,
        requested_at: new Date().toISOString(),
        delivery_confirmed: false,
        persistence: "unavailable",
        results: emails.map((email) => ({
          email,
          status: "pending_verification",
          reason_code: "client_timeout",
          delivery_status: "not_requested",
          membership_provisioned: false,
        })),
      };
      state.teamInviteResult = uncertain;
      persistTeamInviteResult(uncertain);
      toast("Портал перестал ждать через 25 секунд. Не запускайте весь список повторно: нажмите «Обновить» и проверьте сохранённую историю.", "info");
      render();
    } else {
      toast(actionErrorMessage(error), "error");
    }
  }
}

async function submitManagerAccess(form) {
  const email = normalizeAccessCenterEmail(new FormData(form).get("email"));
  if (!isManagerAccessEmail(email)) {
    toast("Укажите точный рабочий email участника.", "error");
    form.elements.email?.focus();
    return;
  }
  await runManagerAccessFlow(email);
}

async function openManagerAccessCenter(email) {
  const normalizedEmail = normalizeAccessCenterEmail(email);
  if (!isManagerAccessEmail(normalizedEmail)) {
    toast("Не удалось определить точный рабочий email участника.", "error");
    return;
  }
  if (["checking", "repairing"].includes(state.accessCenter.status)) {
    toast("Проверка другого адреса будет доступна после завершения текущей.", "info");
    return;
  }
  state.accessCenter.email = normalizedEmail;
  state.accessCenter.result = null;
  state.accessCenter.error = "";
  state.accessCenter.notice = "";
  if (state.route.path === "/workspace/team") {
    renderWorkspace("team");
    window.queueMicrotask(() => {
      const center = document.querySelector("[data-access-center]");
      if (center) scrollElementIntoView(center);
    });
  }
  await runManagerAccessFlow(normalizedEmail);
}

function resetManagerAccessCenter() {
  state.accessCenter.requestId += 1;
  state.accessCenter.status = "idle";
  state.accessCenter.email = "";
  state.accessCenter.result = null;
  state.accessCenter.error = "";
  state.accessCenter.notice = "";
  if (state.route.path === "/workspace/team") {
    renderWorkspace("team");
    window.queueMicrotask(() => document.querySelector("#manager-access-email")?.focus());
  }
}

async function runManagerAccessFlow(email) {
  const normalizedEmail = normalizeAccessCenterEmail(email);
  if (!canManageTeam() || !hasWorkspaceAccess()) {
    toast("Проверять и восстанавливать доступ может только сертифицированный руководитель.", "error");
    return;
  }
  if (!isManagerAccessEmail(normalizedEmail)) {
    toast("Укажите точный рабочий email участника.", "error");
    return;
  }
  if (["checking", "repairing"].includes(state.accessCenter.status)) {
    toast("Проверка доступа уже выполняется.", "info");
    return;
  }

  const requestEpoch = state.dataEpoch;
  const requestUserId = state.user?.id;
  const requestId = state.accessCenter.requestId + 1;
  state.accessCenter.requestId = requestId;
  state.accessCenter.status = "checking";
  state.accessCenter.email = normalizedEmail;
  state.accessCenter.result = null;
  state.accessCenter.error = "";
  state.accessCenter.notice = "";
  if (state.route.path === "/workspace/team") renderWorkspace("team");

  const requestIsCurrent = () => (
    requestEpoch === state.dataEpoch
    && requestUserId === state.user?.id
    && requestId === state.accessCenter.requestId
  );

  try {
    const inspected = await withUiTimeout(
      state.api.inspectAccess(normalizedEmail),
      INVITE_REQUEST_TIMEOUT_MS,
      "access_center_timeout",
    );
    if (!requestIsCurrent()) return;
    const inspectedRecord = normalizeAccessCenterResult(inspected, normalizedEmail);
    state.accessCenter.result = inspected;
    if (inspectedRecord.repairBlocked) {
      state.accessCenter.status = "ready";
      state.accessCenter.notice = "Автоматическая отправка остановлена: почтовый статус требует ручной проверки.";
      if (state.route.path === "/workspace/team") renderWorkspace("team");
      toast(managerAccessBlockedMessage(inspectedRecord.delivery.status), "error");
      return;
    }

    state.accessCenter.status = "repairing";
    state.accessCenter.notice = "Состояние проверено. Сервер выбирает допустимый способ восстановления.";
    if (state.route.path === "/workspace/team") renderWorkspace("team");

    const repaired = await withUiTimeout(
      state.api.repairAccess(normalizedEmail),
      INVITE_REQUEST_TIMEOUT_MS,
      "access_center_timeout",
    );
    if (!requestIsCurrent()) return;
    const repairedRecord = normalizeAccessCenterResult(repaired, normalizedEmail);
    state.accessCenter.result = repaired;
    state.accessCenter.status = "ready";
    state.accessCenter.notice = managerAccessOutcomeMessage(repairedRecord);

    await refreshManagerDataAfterAccessRepair();
    if (!requestIsCurrent()) return;
    toast(
      managerAccessOutcomeMessage(repairedRecord),
      ["already_ready", "recovery_requested", "invite_requested", "membership_connected_recovery_requested"].includes(repairedRecord.outcome)
        ? "success"
        : "info",
    );
  } catch (error) {
    if (!requestIsCurrent()) return;
    state.accessCenter.status = "error";
    state.accessCenter.error = String(error?.message || "") === "access_center_timeout"
      ? "Сервис доступа не ответил за 25 секунд. Не отправляйте повтор: сначала обновите сводку."
      : actionErrorMessage(error);
    state.accessCenter.notice = "";
  } finally {
    if (requestIsCurrent() && state.route.path === "/workspace/team") renderWorkspace("team");
  }
}

async function refreshManagerDataAfterAccessRepair() {
  state.sections.team.status = "idle";
  state.managerDashboard.status = "idle";
  await Promise.allSettled([
    loadSection("team", { silent: true }),
    loadManagerDashboard({ silent: true }),
  ]);
}

function managerAccessOutcomeMessage(record) {
  return {
    already_ready: "Доступ уже готов. Новое письмо не отправлялось.",
    pending_delivery: "Предыдущее письмо ещё обрабатывается. Повтор не запущен.",
    recovery_requested: "Запрос восстановления принят. Доставка письма пока не подтверждена.",
    invite_requested: "Новое приглашение принято. Доставка письма пока не подтверждена.",
    membership_connected_recovery_requested: "Аккаунт подключён к команде, запрос восстановления принят.",
    invite_pending_verification: "Приглашение принято, итог доставки ещё проверяется.",
    cooldown: "Защитный интервал ещё действует. Проверьте самое свежее письмо.",
    provider_outcome_pending: "Почтовый сервис мог принять письмо, но ответ не успел вернуться. Повтор временно закрыт, пока сервер проверяет результат.",
    manual_review: "Автоматическое восстановление остановлено для ручной проверки.",
    invite_failed: "Приглашение не подтверждено. Проверьте новый статус перед повтором.",
  }[record?.outcome] || "Состояние доступа обновлено. Проверьте данные карточки.";
}

function managerAccessBlockedMessage(deliveryStatus) {
  return {
    bounced: "Письмо возвращено почтовым сервером. Автоматический повтор отключён.",
    complained: "Получатель пожаловался на письмо. Автоматический повтор отключён.",
    failed: "Почтовый провайдер завершил попытку ошибкой. Нужна ручная проверка причины.",
    suppressed: "Новое письмо не отправлялось: сервер подавил дубль или частый повтор.",
  }[deliveryStatus] || "Почтовый статус требует ручной проверки. Автоматический повтор отключён.";
}

function isManagerAccessEmail(email) {
  return Boolean(
    email
    && email.length <= 320
    && /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$/u.test(email),
  );
}

async function retryManagerInvite(email, control) {
  const normalizedEmail = normalizeAccessCenterEmail(email);
  if (!canManageTeam() || !hasWorkspaceAccess() || !isManagerAccessEmail(normalizedEmail)) {
    toast("Не удалось подготовить безопасный повтор для этого адреса.", "error");
    return;
  }
  const cooldownSeconds = reserveManagerEmailAction(state.managerInviteCooldowns, normalizedEmail);
  if (cooldownSeconds > 0) {
    toast(`Повтор для этого адреса временно закрыт ещё на ${cooldownSeconds} сек. Сначала обновите журнал приглашений.`, "info");
    return;
  }
  if (control?.isConnected) control.disabled = true;
  await openManagerAccessCenter(normalizedEmail);
}

async function normalizeInviteFunctionError(error) {
  let code = "";
  try {
    const response = error?.context;
    if (response && typeof response.clone === "function") {
      const payload = await response.clone().json();
      code = String(payload?.code || "");
    }
  } catch {
    // Fall back to the SDK error message below.
  }
  const messages = {
    invite_count_invalid: "За один запуск можно пригласить от 1 до 50 человек.",
    email_invalid: "Один или несколько email заполнены неверно.",
    workspace_unavailable: "Рабочая команда временно недоступна. Повторите попытку позже.",
    final_exam_required: "Сначала завершите обучение и сдайте итоговый экзамен.",
    team_management_forbidden: "Приглашать участников может только руководитель.",
    origin_not_allowed: "Этот адрес приложения не разрешён для приглашений.",
    request_too_large: "Список приглашений слишком большой.",
  };
  const normalized = new Error(messages[code] || authErrorMessage(error));
  normalized.isUserSafe = true;
  return normalized;
}

async function normalizePasswordFunctionError(error) {
  let code = "";
  try {
    const response = error?.context;
    if (response && typeof response.clone === "function") {
      const payload = await response.clone().json();
      code = String(payload?.code || "");
    }
  } catch {
    // Fall back to a safe generic message.
  }
  const messages = {
    password_policy_invalid: "Пароль не соответствует требованиям. Используйте 10–128 символов, буквы разного регистра и цифру.",
    password_change_not_required: "Обязательная смена пароля уже завершена. Обновите страницу и войдите снова.",
    session_required: "Сессия завершилась. Откройте свежую ссылку или войдите снова.",
    account_unavailable: "Не удалось проверить аккаунт. Обратитесь к руководителю команды.",
    password_update_failed: "Сервер не сохранил новый пароль. Рабочие разделы остаются закрыты; повторите попытку.",
    origin_not_allowed: "Этот адрес портала не разрешён для смены пароля.",
  };
  const normalized = new Error(messages[code] || "Не удалось безопасно сохранить новый пароль. Повторите попытку.");
  normalized.isUserSafe = true;
  return normalized;
}

async function submitProductResearchStart(form) {
  const values = new FormData(form);
  const productName = String(values.get("product_name") || "").trim();
  const sku = String(values.get("sku") || "").trim();
  const marketplaceUrl = String(values.get("marketplace_url") || "").trim();
  const sourceMediaIds = values.getAll("source_media_ids").map(String).filter(Boolean);
  const platforms = values.getAll("platforms").map(String).filter((item) => ["instagram", "youtube", "vk"].includes(item));
  if (!platforms.length) {
    toast("Выберите хотя бы одну площадку: Instagram, YouTube или VK.", "error");
    form.querySelector(".product-research-platforms")?.scrollIntoView({ block: "center" });
    return;
  }
  if (!marketplaceUrl && !sourceMediaIds.length) {
    toast("Добавьте публичную ссылку на товар или выберите хотя бы одно точное фото.", "error");
    return;
  }
  if (sourceMediaIds.length > 5) {
    toast("Для одного анализа выберите не больше пяти самых точных фотографий.", "error");
    return;
  }
  if (marketplaceUrl && !isHttpsUrl(marketplaceUrl)) {
    toast("Ссылка на товар должна начинаться с https://", "error");
    form.elements.marketplace_url?.focus();
    return;
  }
  const objectiveLabels = {
    conversion: "Подготовить нативные товарные ролики для переходов и заказов",
    awareness: "Подготовить ролики для узнаваемости товара и бренда",
    ugc: "Подготовить естественный UGC-обзор от лица блогера",
    education: "Понятно показать применение товара и снять основные вопросы",
  };
  const objectiveKey = String(values.get("objective") || "conversion");
  const knownFacts = String(values.get("known_facts") || "").trim();
  const objective = [objectiveLabels[objectiveKey] || objectiveLabels.conversion, knownFacts ? `Подтверждённые вводные пользователя: ${knownFacts}` : ""]
    .filter(Boolean)
    .join("\n");
  const previous = normalizeProductResearch({ run: { status: "queued" } }, {
    productName,
    sku,
    status: "queued",
  });
  stopProductResearchPolling();
  state.productResearch.requestId += 1;
  state.productResearch.phase = "starting";
  state.productResearch.record = previous;
  state.productResearch.error = "";
  state.productResearch.notice = "";
  renderWorkspace("research");
  try {
    const raw = await state.api.startProductResearch(
      {
        sku,
        product_name: productName,
        objective,
        marketplace_url: marketplaceUrl || null,
        source_media_ids: sourceMediaIds,
        platforms,
      },
      {
        onRunCreated: (run) => {
          persistProductResearchRunId(run?.id);
          state.productResearch.record = normalizeProductResearch({ run }, previous);
        },
      },
    );
    state.productResearch.record = normalizeProductResearch(raw, previous);
    persistProductResearchRunId(state.productResearch.record.id);
    const kind = productResearchStatusKind(state.productResearch.record.status);
    state.productResearch.phase = kind === "ready" ? "ready" : "processing";
    await track("product_research_started", {
      run_id: state.productResearch.record.id,
      source_media_count: sourceMediaIds.length,
      platform_count: platforms.length,
    });
  } catch (error) {
    const recoverableRun = error?.job?.id
      ? normalizeProductResearch({ run: error.job }, previous)
      : null;
    state.productResearch.record = recoverableRun;
    state.productResearch.phase = "error";
    state.productResearch.error = actionErrorMessage(error);
  }
  if (state.route.path === "/workspace/research") renderWorkspace("research");
  scheduleProductResearchPolling(800);
}

async function submitProductResearchBrief(form, submitter) {
  const research = state.productResearch;
  const mode = String(submitter?.dataset?.researchSubmit || "save");
  if (!research.record?.id || !["save", "approve"].includes(mode)) {
    toast("Не удалось определить действие с ТЗ. Обновите раздел.", "error");
    return;
  }
  if (mode === "approve" && form.elements.approve_ack?.checked !== true) {
    toast("Перед созданием задач подтвердите ручную проверку фактов и сценариев.", "error");
    form.elements.approve_ack?.focus();
    return;
  }
  const draft = readProductResearchBrief(form);
  if (draft.scenarios.some((scenario) => !scenario.hook || !scenario.script || !scenario.task_title)) {
    toast("В каждом из трёх сценариев заполните хук, реплику и название задачи.", "error");
    return;
  }
  const sourceIds = Array.from(new Set(research.record.sourceIds || [])).filter(Boolean);
  if (!sourceIds.length) {
    toast("У ТЗ нет подтверждённых источников. Обновите статус исследования.", "error");
    return;
  }
  const editableBrief = mergeProductResearchBrief(research.record.rawBrief, draft);
  const taskBlueprint = productResearchTaskBlueprint(draft);
  research.phase = mode === "approve" ? "approving" : "saving";
  research.error = "";
  research.notice = "";
  renderWorkspace("research");
  try {
    const saved = await state.api.saveCreativeBriefDraft(research.record.id, {
      title: draft.title,
      brief: editableBrief,
      source_ids: sourceIds,
      task_blueprint: taskBlueprint,
    });
    const savedDraftId = String(saved?.draft?.id || saved?.data?.draft?.id || "");
    const localRecord = normalizeProductResearch({
      run: { id: research.record.id, status: "completed" },
      latest_draft: {
        id: savedDraftId || research.record.draftId,
        title: draft.title,
        brief: editableBrief,
        source_ids: sourceIds,
        task_blueprint: taskBlueprint,
      },
      sources: research.record.sources,
      forecasts: [{
        score: research.record.score,
        confidence: research.record.confidence,
        factors: {
          strengths: research.record.factors.filter((factor) => factor.impact >= 0).map((factor) => factor.label),
          risks: research.record.factors.filter((factor) => factor.impact < 0).map((factor) => factor.label),
        },
      }],
    }, research.record);
    research.record = localRecord;
    form.removeAttribute("data-dirty");
    if (mode === "approve") {
      const draftId = savedDraftId || localRecord.draftId;
      const approved = await state.api.approveCreativeBrief(draftId);
      research.record = normalizeProductResearch(approved, {
        ...localRecord,
        status: "approved",
      });
      research.phase = "approved";
      research.notice = "ТЗ утверждено. Портал создал три связанные задачи без повторного копирования текста.";
      state.sections.tasks.status = "idle";
      await track("product_research_approved", {
        run_id: research.record.id,
        task_count: research.record.taskIds.length,
      });
    } else {
      research.phase = "ready";
      research.notice = "Черновик сохранён новой версией. Задачи ещё не создавались.";
      await track("product_research_draft_saved", { run_id: research.record.id });
    }
  } catch (error) {
    research.phase = "ready";
    research.error = actionErrorMessage(error);
  }
  if (state.route.path === "/workspace/research") renderWorkspace("research");
}

function mergeProductResearchBrief(base, draft) {
  const original = base && typeof base === "object" && !Array.isArray(base) ? base : {};
  const originalScenarios = Array.isArray(original.scenarios) ? original.scenarios : [];
  return {
    ...original,
    target_audience: draft.target_audience,
    key_message: draft.key_message,
    proof_points: splitResearchLines(draft.proof_points),
    avoid_claims: splitResearchLines(draft.avoid_claims),
    visual_direction: draft.visual_direction,
    cta: draft.cta,
    scenarios: draft.scenarios.map((scenario, index) => ({
      ...(originalScenarios[index] || {}),
      title: scenario.title,
      platform: scenario.platform,
      hook: scenario.hook,
      spoken_script: scenario.script,
      shot_list: splitResearchLines(scenario.shot_list),
      task_title: scenario.task_title,
    })),
  };
}

function productResearchTaskBlueprint(draft) {
  const proofPoints = splitResearchLines(draft.proof_points);
  const avoidClaims = splitResearchLines(draft.avoid_claims);
  const sharedInstructions = [
    draft.target_audience ? `Целевая аудитория: ${draft.target_audience}` : "",
    draft.key_message ? `Главная мысль: ${draft.key_message}` : "",
    proofPoints.length
      ? `Подтверждённые доказательства — использовать только в этой формулировке:\n${proofPoints.map((item) => `• ${item}`).join("\n")}`
      : "Подтверждённые доказательства: не указаны — не добавлять свойства от себя.",
    avoidClaims.length
      ? `Запрещённые и неподтверждённые обещания — не использовать:\n${avoidClaims.map((item) => `• ${item}`).join("\n")}`
      : "Запрещённые обещания: отдельно не перечислены — любые новые факты сначала вернуть на проверку.",
    draft.visual_direction ? `Визуальное направление: ${draft.visual_direction}` : "",
    draft.cta ? `Разрешённый призыв к действию: ${draft.cta}` : "",
    "Ручная проверка перед сдачей: сверить товар и упаковку, дословную реплику, доказательства, рекламный статус и запрещённые обещания.",
  ].filter(Boolean);
  return draft.scenarios.map((scenario) => ({
    task_type: "general",
    assignee_id: scenario.assignee_id,
    title: scenario.task_title,
    instructions: [
      `Угол подачи: ${scenario.title}`,
      `Площадка: ${scenario.platform}`,
      `Хук: ${scenario.hook}`,
      `Реплика блогера: ${scenario.script}`,
      `Кадры:\n${scenario.shot_list}`,
      ...sharedInstructions,
    ].join("\n"),
    priority: 3,
    payout_minor: 0,
  }));
}

function splitResearchLines(value) {
  return String(value || "").split(/\r?\n/u).map((item) => item.trim()).filter(Boolean);
}

async function persistContentReviewVideoEvidence(media, capturedEvidence, form) {
  const existing = usableContentReviewEvidence(state.contentReview.durableEvidence, {
    mediaId: media.id,
    mediaSha256: media.sha256,
  });
  if (existing?.status === "ready") return existing;
  const promoteReady = (pending) => {
    const ready = {
      status: "ready",
      evidenceId: pending.evidenceId,
      mediaId: pending.mediaId,
      mediaSha256: pending.mediaSha256,
      expiresAt: pending.expiresAt,
      technicalMetrics: pending.technicalMetrics,
    };
    state.contentReview.durableEvidence = ready;
    persistContentReviewDraft(form, { durableEvidence: ready });
    return ready;
  };
  if (existing?.status === "commit_pending") {
    await state.api.commitContentReviewEvidence({
      evidenceId: existing.evidenceId,
      technicalMetrics: existing.technicalMetrics,
      frames: existing.frames,
      idempotencyKey: existing.commitIdempotencyKey,
    });
    return promoteReady(existing);
  }

  const frameFiles = await buildContentReviewFrameFiles(capturedEvidence);
  const prepared = await state.api.prepareContentReviewEvidence({
    mediaId: media.id,
    frameCount: frameFiles.length,
  });
  const pendingDraft = {
    status: "commit_pending",
    evidenceId: prepared.evidenceId,
    mediaId: media.id,
    mediaSha256: media.sha256,
    expiresAt: prepared.expiresAt,
    technicalMetrics: capturedEvidence.technical_metrics,
    commitIdempotencyKey: crypto.randomUUID(),
    frames: frameFiles.map((frame, index) => ({
      object_name: prepared.frameObjectNames[index],
      sha256: frame.sha256,
      size_bytes: frame.sizeBytes,
      timecode_seconds: Math.round(frame.timecodeSeconds * 1_000) / 1_000,
    })),
  };
  const pending = usableContentReviewEvidence(pendingDraft, {
    mediaId: media.id,
    mediaSha256: media.sha256,
  });
  if (!pending) {
    throw new Error("Не удалось создать безопасный recovery-черновик для подтверждения кадров.");
  }
  const uploadedObjectNames = [];
  let commitStarted = false;
  try {
    for (let index = 0; index < frameFiles.length; index += 1) {
      const objectName = prepared.frameObjectNames[index];
      await state.api.uploadPrivateObject(objectName, frameFiles[index].blob);
      uploadedObjectNames.push(objectName);
    }
    state.contentReview.durableEvidence = pending;
    if (!persistContentReviewDraft(form, { durableEvidence: pending })) {
      throw new Error("Браузер не сохранил recovery-черновик. Кадры не будут подтверждены до безопасного локального сохранения.");
    }
    commitStarted = true;
    await state.api.commitContentReviewEvidence({
      evidenceId: pending.evidenceId,
      technicalMetrics: pending.technicalMetrics,
      frames: pending.frames,
      idempotencyKey: pending.commitIdempotencyKey,
    });
  } catch (error) {
    // Once commit has started its response may be lost after a successful
    // transaction. Only definitely-uncommitted partial uploads are removed;
    // committed/ambiguous evidence is left for server reconciliation/sweeping.
    if (!commitStarted && uploadedObjectNames.length) {
      await state.api.removePrivateObjects(uploadedObjectNames).catch(() => {});
      state.contentReview.durableEvidence = null;
      persistContentReviewDraft(form, { durableEvidence: null });
    }
    throw error;
  }
  return promoteReady(pending);
}

async function submitContentReview(form) {
  const review = state.contentReview;
  if (["preparing", "saving_evidence", "queueing", "starting", "processing", "deciding"].includes(review.phase)) {
    toast("Текущая проверка ещё не завершена. Дождитесь результата или откройте её статус.", "info");
    return;
  }
  const input = readContentReviewForm(form);
  const catalog = normalizeContentReviewCatalog(state.sections.review.data || {});
  const media = catalog.media.find((item) => item.id === input.media_id);
  if (!media) {
    toast("Выбранный материал не найден. Обновите раздел и выберите файл снова.", "error");
    return;
  }
  if (String(media.metadata?.kind || "") === "generated_video") {
    input.content_kind = "advertising";
    input.ai_generated = true;
    if (form.elements.content_kind) form.elements.content_kind.value = "advertising";
    if (form.elements.ai_generated) form.elements.ai_generated.checked = true;
    syncContentReviewFormVisibility(form);
    if (
      !input.advertiser_name ||
      !input.erid ||
      !input.ad_label_confirmed ||
      !input.ord_confirmed ||
      !input.rights_confirmed ||
      !input.claims_verified
    ) {
      toast("Готовый платный AI-ролик проверяется только как реклама. Заполните рекламодателя и ERID, подтвердите маркировку, ОРД, права и факты о товаре.", "error");
      form.elements.advertiser_name?.focus();
      return;
    }
  }
  if (input.people_present === "yes" && !input.person_consent_confirmed) {
    toast("В кадре есть узнаваемые люди, но согласие не подтверждено. Проверка продолжится и зафиксирует это как риск.", "info");
  }
  if (input.people_present !== "no" && !input.external_ai_processing_confirmed) {
    toast("Контрольные кадры с узнаваемыми людьми нельзя отправлять внешнему AI-провайдеру без подтверждённого законного основания и информирования.", "error");
    form.elements.external_ai_processing_confirmed?.focus();
    return;
  }
  if (input.content_kind === "advertising" && (!input.advertiser_name || !input.erid)) {
    toast("У рекламы не заполнены рекламодатель или ERID. Проверка продолжится, но публикация, скорее всего, будет заблокирована.", "info");
  }
  persistContentReviewDraft(form);
  const completedRuns = catalog.runs.filter((item) => contentReviewStatusKind(item.status) === "ready");
  const previousSameMedia = completedRuns.find((item) => item.mediaId === media.id);
  const previousSameProduct = media.productId
    ? completedRuns.find((item) => item.media?.productId === media.productId)
    : null;
  const previous = previousSameMedia || previousSameProduct || null;
  const comparisonScope = previousSameMedia ? "этого же файла" : previousSameProduct ? "предыдущего файла того же товара" : "";
  stopContentReviewPolling();
  review.requestId += 1;
  review.phase = "preparing";
  review.error = "";
  review.notice = comparisonScope
    ? `Новый результат будет сравниваться с проверкой ${comparisonScope}.`
    : "Это первая сопоставимая проверка: история изменений начнёт собираться с этой версии.";
  renderWorkspace("review");
  let evidence;
  let durableEvidence = usableContentReviewEvidence(review.durableEvidence, {
    mediaId: media.id,
    mediaSha256: media.sha256,
  });
  try {
    evidence = durableEvidence
      ? { frames: [], technical_metrics: durableEvidence.technicalMetrics }
      : await captureContentReviewEvidence(media);
  } catch (error) {
    review.phase = "idle";
    review.error = actionErrorMessage(error);
    renderWorkspace("review");
    return;
  }
  if (media.isVideo && durableEvidence?.status !== "ready") {
    review.phase = "saving_evidence";
    renderWorkspace("review");
    try {
      durableEvidence = await persistContentReviewVideoEvidence(media, evidence, form);
      review.durableEvidence = durableEvidence;
      persistContentReviewDraft(form, { durableEvidence });
    } catch (error) {
      review.phase = "idle";
      review.error = actionErrorMessage(error);
      const pendingEvidence = usableContentReviewEvidence(review.durableEvidence, {
        mediaId: media.id,
        mediaSha256: media.sha256,
      });
      if (pendingEvidence?.status === "commit_pending") {
        review.notice = "Кадры уже загружены. Следующая попытка повторит только подтверждение тем же ключом — повторной загрузки не будет.";
      }
      renderWorkspace("review");
      return;
    }
  }
  review.phase = "queueing";
  review.error = "";
  review.notice = media.isVideo
    ? "Контрольные кадры сохранены. Теперь сервер ставит проверку в фоновую очередь."
    : review.notice;
  renderWorkspace("review");
  try {
    const raw = await state.api.startContentReview(
      {
        ...input,
        parent_review_id: previous?.id || null,
        technical_metrics: evidence.technical_metrics,
        ...(durableEvidence ? { evidence_id: durableEvidence.evidenceId } : {}),
      },
      {
        onRunCreated: (run) => {
          review.record = normalizeContentReviewRun({ run }, {
            id: run?.id,
            status: run?.status || "queued",
            mediaId: media.id,
            media,
            input: {
              mediaId: media.id,
              platform: input.platform,
              contentKind: input.content_kind,
              productCategory: input.product_category,
            },
          });
          upsertContentReviewRun(review.record);
        },
      },
    );
    review.record = normalizeContentReviewRun(raw, review.record || {
      mediaId: media.id,
      media,
    });
    upsertContentReviewRun(review.record);
    review.phase = contentReviewStatusKind(review.record.status) === "ready" ? "idle" : "processing";
    const durableSourceLabel = media.isVideo ? "Evidence сохранён" : "Исходник сохранён";
    review.notice = previous
      ? `Проверка создана и связана с ${comparisonScope}. ${durableSourceLabel}: вкладку можно закрыть, сервер продолжит работу.`
      : `Проверка поставлена в фоновую очередь. ${durableSourceLabel}: вкладку можно закрыть, сервер продолжит работу.`;
    form.removeAttribute("data-dirty");
    clearContentReviewDraft();
    await track("content_review_started", {
      review_id: review.record.id,
      media_id: media.id,
      platform: input.platform,
      content_kind: input.content_kind,
      frame_count: Number(evidence.technical_metrics?.frame_count || evidence.frames?.length || 0),
      evidence_id: durableEvidence?.evidenceId || null,
      evidence_persisted: Boolean(durableEvidence),
      raw_video_sent: false,
      comparison_scope: previousSameMedia ? "same_media" : previousSameProduct ? "same_product" : "none",
    });
  } catch (error) {
    review.record = null;
    review.phase = "idle";
    review.error = actionErrorMessage(error);
    if (durableEvidence) {
      review.notice = "Evidence уже сохранён и не удалён. Повторите запуск: кадры загружать заново не потребуется.";
      review.durableEvidence = durableEvidence;
      persistContentReviewDraft(form, { durableEvidence });
    }
  }
  if (state.route.path === "/workspace/review") renderWorkspace("review");
  scheduleContentReviewPolling(800);
}

async function submitContentReviewDecision(form, submitter) {
  if (!canDecideContentReview()) {
    toast("Финальное решение доступно только руководителю, продюсеру или проверяющему.", "error");
    return;
  }
  const review = state.contentReview;
  const reviewId = String(form.dataset.reviewId || "");
  if (!reviewId || reviewId !== String(review.record?.id || "")) {
    toast("Откройте актуальную проверку и повторите решение.", "error");
    return;
  }
  if (!contentReviewExactMediaReady(form)) {
    toast("Решение заблокировано: точный файл не загрузился или MP4 не был воспроизведён до конца без смены источника.", "error");
    form.querySelector("[data-content-review-exact-media]")?.focus();
    return;
  }
  const decision = readContentReviewDecision(form, submitter);
  if (decision.decision === "approved" && contentReviewHasBlockers(review.record)) {
    toast("Одобрение недоступно: в этой версии остаются критические блокеры.", "error");
    return;
  }
  if (!decision.mediaWatchedConfirmed) {
    toast("Сначала полностью просмотрите именно этот защищённый файл, включая звук и субтитры.", "error");
    form.elements.media_watched_confirmed?.focus();
    return;
  }
  const requiredRiskCodes = contentReviewRequiredRiskCodes(review.record);
  const acknowledgedRiskCodes = new Set(decision.riskAcknowledgements);
  const missingRiskCodes = requiredRiskCodes.filter((code) => !acknowledgedRiskCodes.has(code));
  if (decision.decision === "approved" && missingRiskCodes.length) {
    toast(`Для одобрения подтвердите каждый высокий или обязательный риск: осталось ${missingRiskCodes.length}.`, "error");
    Array.from(form.querySelectorAll('input[name="risk_acknowledgements"]'))
      .find((control) => control.value === missingRiskCodes[0])
      ?.focus();
    return;
  }
  review.phase = "deciding";
  review.error = "";
  review.notice = "";
  renderWorkspace("review");
  try {
    const raw = await state.api.decideContentReview(
      reviewId,
      decision.decision,
      decision.reason,
      {
        resolvedRecommendationCodes: decision.resolvedRecommendationCodes,
        riskAcknowledgements: decision.riskAcknowledgements,
        mediaWatchedConfirmed: decision.mediaWatchedConfirmed,
      },
    );
    review.record = normalizeContentReviewRun(raw, review.record);
    upsertContentReviewRun(review.record);
    review.phase = "idle";
    review.notice = "Неизменяемое решение сохранено. Для исправленного файла создайте новую проверку.";
    try {
      const [freshStatus, freshCatalog] = await Promise.all([
        state.api.contentReviewStatus(reviewId),
        state.api.contentReviewCatalog({ limit: 50 }),
      ]);
      const [hydratedStatus, hydratedCatalog] = await Promise.all([
        hydratePrivateMedia(freshStatus, { refreshSignedUrls: true }),
        hydratePrivateMedia(freshCatalog, { refreshSignedUrls: true }),
      ]);
      review.record = normalizeContentReviewRun(hydratedStatus, review.record);
      state.sections.review.data = hydratedCatalog;
      state.sections.review.status = "ready";
      state.sections.review.error = null;
      upsertContentReviewRun(review.record);
    } catch (refreshError) {
      console.warn("Content review post-decision refresh failed", refreshError);
      review.error = "Решение сохранено, но свежий статус не загрузился. Нажмите «Обновить» — повторно решение не отправляйте.";
    }
    await track("content_review_decided", {
      review_id: reviewId,
      decision: decision.decision,
      resolved_recommendation_count: decision.resolvedRecommendationCodes.length,
      risk_acknowledgement_count: decision.riskAcknowledgements.length,
      media_watched_confirmed: true,
    });
  } catch (error) {
    review.phase = "idle";
    review.error = actionErrorMessage(error);
  }
  if (state.route.path === "/workspace/review") renderWorkspace("review");
}

async function submitMedia(form) {
  const values = new FormData(form);
  const file = values.get("file");
  if (!(file instanceof File) || file.size === 0) {
    toast("Выберите непустой файл.", "error");
    return;
  }
  if (file.size > Number(CONFIG.MAX_UPLOAD_BYTES)) {
    toast(`Файл больше лимита ${formatBytes(CONFIG.MAX_UPLOAD_BYTES)}.`, "error");
    return;
  }
  const allowedTypes = new Set(["image/jpeg", "image/png", "image/webp", "video/mp4"]);
  if (!allowedTypes.has(file.type)) {
    toast("Разрешены JPG, PNG, WEBP и MP4.", "error");
    return;
  }

  const kind = String(values.get("kind") || "product_photo").trim();
  const productIdentity = {};
  if (mediaKindRequiresProduct(kind)) {
    const sku = String(values.get("sku") || "").trim();
    const productName = String(values.get("product_name") || "").trim();
    if (!sku || sku.length > 120) {
      toast("Укажите точный артикул товара длиной до 120 символов.", "error");
      form.elements.sku?.focus();
      return;
    }
    if (productName.length < 2 || productName.length > 180) {
      toast("Укажите точное название товара длиной от 2 до 180 символов.", "error");
      form.elements.product_name?.focus();
      return;
    }
    productIdentity.sku = sku;
    productIdentity.product_name = productName;
  }

  setFormBusy(form, true, "Проверяем файл и загружаем…");
  let objectKey = "";
  try {
    objectKey = privateObjectKey(file.name);
    const sha256 = await fileSha256(file);
    await state.api.uploadPrivateObject(objectKey, file);
    try {
      await state.api.registerMedia({
        bucket: state.bootstrap.storage.bucket,
        object_key: objectKey,
        original_filename: file.name,
        mime_type: file.type,
        size_bytes: file.size,
        sha256,
        kind,
        ...productIdentity,
        rights_confirmed: values.get("rights_confirmed") === "on",
      });
    } catch (registrationError) {
      await state.api.removePrivateObject(objectKey).catch(() => {});
      throw registrationError;
    }
    await track("media_uploaded", { kind, mime_type: file.type, size_bytes: file.size });
    delete form.dataset.dirty;
    form.reset();
    showSelectedFile(null);
    syncMediaProductFields(form);
    state.sections.media.status = "idle";
    state.sections.generation.status = "idle";
    toast("Файл сохранён в защищённой папке.", "success");
    render();
  } catch (error) {
    toast(actionErrorMessage(error), "error");
  } finally {
    if (form.isConnected) setFormBusy(form, false);
  }
}

async function track(eventName, properties = {}) {
  if (!state.api || !state.session || !state.bootstrap || membershipLockDetails()) return;
  try {
    await state.api.captureEvent({
      event_name: eventName,
      event_version: 1,
      session_id: state.sessionId,
      route: state.route.path,
      occurred_at: new Date().toISOString(),
      properties,
    });
  } catch {
    // Product telemetry must never block a person's task.
  }
}

function validateConfig(config) {
  const problems = [];
  if (!/^https:\/\/[a-z0-9-]+\.supabase\.co$/i.test(String(config.SUPABASE_URL || ""))) {
    problems.push("Укажите HTTPS URL проекта Supabase.");
  }
  const key = String(config.SUPABASE_PUBLISHABLE_KEY || "");
  if (!key || key.includes("__SET_") || key.includes("REPLACE_ME")) {
    problems.push("Добавьте browser-safe Supabase Publishable key в config.js.");
  }
  if (/sb_secret_|service[_-]?role|postgres(?:ql)?:\/\//i.test(key)) {
    problems.push("В config.js обнаружен запрещённый секрет. Немедленно удалите и перевыпустите его.");
  }
  if (typeof config.MOCK_ENABLED !== "boolean" || typeof config.REAL_GENERATION_ENABLED !== "boolean") {
    problems.push("Укажите явные флаги MOCK_ENABLED и REAL_GENERATION_ENABLED.");
  } else if (!config.MOCK_ENABLED && !config.REAL_GENERATION_ENABLED) {
    problems.push("Включите хотя бы один режим генерации.");
  }
  if (!config.STORAGE_BUCKET || String(config.STORAGE_BUCKET).toLowerCase().includes("public")) {
    problems.push("Укажите имя приватного Storage bucket.");
  }
  return problems;
}

function renderSetup(problems) {
  console.error("Portal configuration is incomplete", problems);
  app.innerHTML = `
    <main id="main-content" class="setup-screen" tabindex="-1">
      <section class="card setup-card">
        <div class="boot-mark" aria-hidden="true">A</div>
        <p class="eyebrow">Портал временно недоступен</p>
        <h1 style="font:600 2.4rem/1.1 Georgia,serif; margin:8px 0">Не удалось запустить рабочее пространство</h1>
        <p class="muted">Обновите страницу через несколько минут. Если экран появится снова, отправьте его руководителю команды — технические детали уже сохранены в журнале браузера.</p>
        <button class="btn" type="button" data-action="reload-page">Обновить страницу</button>
      </section>
    </main>
  `;
}

function startupDiagnosticCode(error) {
  const code = String(error?.code || "").trim().toLowerCase();
  const name = String(error?.name || "").trim().toLowerCase();
  if (["ui_timeout", "auth_link_timeout"].includes(code) || name === "aborterror") {
    return "startup_timeout";
  }
  if (
    ["typeerror", "networkerror"].includes(name)
    || ["err_module_not_found", "module_not_found", "import_failed"].includes(code)
  ) {
    return "auth_client_load_failed";
  }
  if (code.startsWith("auth_link_")) return "auth_link_failed";
  return "startup_error";
}

function renderFatal(error) {
  console.error("Portal startup failed", error);
  const diagnosticCode = startupDiagnosticCode(error);
  app.innerHTML = `
    <main id="main-content" class="error-page" tabindex="-1">
      <div class="boot-mark" aria-hidden="true">!</div>
      <p class="eyebrow">Ошибка запуска</p>
      <h1>Интерфейс не загрузился</h1>
      <p class="muted">Обновите страницу. Если ошибка повторится, сообщите руководителю команды.</p>
      <p class="tiny muted">Код диагностики: <code>${escapeHtml(diagnosticCode)}</code></p>
      <button class="btn" type="button" data-action="reload-page">Обновить страницу</button>
    </main>
  `;
}

function parseRoute() {
  const raw = window.location.hash.startsWith("#/") ? window.location.hash.slice(1) : "/";
  const [pathPart, queryPart = ""] = raw.split("?");
  let path = pathPart || "/";
  if (!path.startsWith("/")) path = `/${path}`;
  path = path.replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
  return { path, query: new URLSearchParams(queryPart) };
}

function navigate(path, replace = false) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const hash = `#${normalized}`;
  if (replace) {
    const next = new URL(window.location.href);
    next.hash = hash;
    window.history.replaceState({}, "", next);
    state.route = parseRoute();
    state.workspaceDeepLinkFocusKey = "";
    state.routeTransition = true;
    if (
      state.route.path === "/workspace/home"
      && !["loading", "refreshing"].includes(state.home.status)
    ) state.home.status = "idle";
    render();
    settleRouteView();
  } else if (window.location.hash === hash) {
    state.route = parseRoute();
    state.workspaceDeepLinkFocusKey = "";
    state.routeTransition = true;
    if (
      state.route.path === "/workspace/home"
      && !["loading", "refreshing"].includes(state.home.status)
    ) state.home.status = "idle";
    render();
    settleRouteView();
  } else {
    window.location.hash = normalized;
  }
}

function clearAuthenticatedState() {
  stopAllTrainingWalkthroughs();
  clearWorkspaceDropTargets();
  destroyAccountVisualController();
  state.accountVisualStates.clear();
  clearAccountLaunchChecks(state.user?.id);
  stopRealGenerationPolling();
  stopProductResearchPolling();
  stopContentReviewPolling();
  clearStoredPkceVerifier();
  if (state.resetCountdownTimer) window.clearInterval(state.resetCountdownTimer);
  setMobileNavOpen(false);
  state.dataEpoch += 1;
  state.bootstrapRequestId += 1;
  state.session = null;
  state.user = null;
  state.api?.clearBootstrapContext();
  state.realGenerationStartInFlight = false;
  state.realGenerationStartNotice = "";
  state.realGenerationPollInFlight = false;
  state.realGenerationPollCursor = 0;
  state.realGenerationStatusRequests.clear();
  state.realGenerationResults.clear();
  state.realGenerationDrafts.clear();
  state.lastRealGenerationJobId = null;
  state.bootstrap = null;
  state.bootstrapStatus = "idle";
  state.bootstrapError = null;
  state.forcePassword = false;
  state.authPurpose = null;
  state.authLinkError = null;
  state.authLinkContinuationPending = false;
  state.resetReceipt = readStoredPublicRecoveryReceipt();
  state.resetCountdownTimer = null;
  state.examResult = null;
  state.courseCheckResults = {};
  state.firstShift = null;
  for (const timer of state.trainingProgress.saveTimers.values()) {
    window.clearTimeout(timer);
  }
  state.trainingProgress.items.clear();
  state.trainingProgress.loadedModules.clear();
  state.trainingProgress.loadRequests.clear();
  state.trainingProgress.saveTimers.clear();
  state.trainingProgress.saveQueues.clear();
  state.trainingProgress.completionInFlight.clear();
  state.teamInviteResult = null;
  state.managerDashboard.requestId += 1;
  state.managerDashboard.status = "idle";
  state.managerDashboard.data = null;
  state.managerDashboard.error = null;
  state.managerDashboard.updatedAt = 0;
  state.operationalHealth.requestId += 1;
  state.operationalHealth.status = "idle";
  state.operationalHealth.data = null;
  state.operationalHealth.error = null;
  state.operationalHealth.updatedAt = 0;
  state.generationSpend.requestId += 1;
  state.generationSpend.status = "idle";
  state.generationSpend.data = null;
  state.generationSpend.error = null;
  state.generationSpend.notice = "";
  state.generationSpend.updatedAt = 0;
  state.generationSpend.saving = false;
  state.accessCenter.requestId += 1;
  state.accessCenter.status = "idle";
  state.accessCenter.email = "";
  state.accessCenter.result = null;
  state.accessCenter.error = "";
  state.accessCenter.notice = "";
  state.managerRecoveryCooldowns.clear();
  state.managerInviteCooldowns.clear();
  state.productResearch.requestId += 1;
  state.productResearch.phase = "idle";
  state.productResearch.record = null;
  state.productResearch.error = "";
  state.productResearch.notice = "";
  state.productResearch.restoreAttempted = false;
  state.contentReview.requestId += 1;
  state.contentReview.phase = "idle";
  state.contentReview.record = null;
  state.contentReview.error = "";
  state.contentReview.notice = "";
  state.contentReview.pendingMediaId = "";
  state.contentReview.durableEvidence = null;
  state.workspaceBoard.selectedFolderId = "all";
  state.workspaceBoard.selectedItemKey = "";
  state.workspaceBoard.query = "";
  state.workspaceBoard.entityType = "all";
  state.workspaceBoard.busy = false;
  state.workspaceBoard.notice = "";
  state.workspaceBoard.error = "";
  state.workspaceBoard.dragging = null;
  state.workspaceBoard.loadingMore = false;
  state.workspaceBoard.hasMore = false;
  state.workspaceBoard.nextCursor = null;
  state.workspaceBoard.visibleItemLimit = WORKSPACE_BOARD_VISIBLE_STEP;
  state.myWork.filters = normalizeMyWorkFilters();
  state.myWork.selectedViewId = "";
  state.myWork.savedViews = [];
  state.myWork.notifications = normalizeNotifications();
  state.myWork.notificationsStatus = "idle";
  state.myWork.notificationsError = "";
  state.myWork.notificationsOpen = false;
  state.myWork.notificationsRequestId += 1;
  state.myWork.notificationsMutationEpoch += 1;
  state.myWork.notice = "";
  state.myWork.error = "";
  state.myWork.loadingMore = false;
  state.myWork.viewsLoaded = false;
  state.workspaceDeepLinkFocusKey = "";
  document.body.classList.remove("notification-center-open");
  state.generationArchive.requestId += 1;
  state.generationArchive.filters = normalizeGenerationFilters();
  state.generationArchive.loading = false;
  state.generationArchive.loadingMore = false;
  state.generationArchive.exhausted = false;
  state.generationArchive.error = "";
  state.generationArchive.nextCursor = null;
  state.generationArchive.serverLoaded = false;
  state.home.status = "idle";
  state.home.data = null;
  state.home.error = null;
  state.home.unavailable = [];
  state.home.requestId += 1;
  for (const section of Object.values(state.sections)) {
    section.requestId += 1;
    section.status = "idle";
    section.data = null;
    section.error = null;
  }
}

function consumeRouteTransitionClass() {
  if (!state.routeTransition) return "";
  state.routeTransition = false;
  return "route-enter";
}

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
}

function scrollElementIntoView(element, block = "start") {
  element?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block });
}

function safeWorkspaceRouteEntityId(parameterName) {
  if (!state.route.path.startsWith("/workspace/")) return "";
  const values = state.route.query.getAll(parameterName);
  if (values.length !== 1) return "";
  const value = String(values[0] || "").trim().toLowerCase();
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u.test(value)
    ? value
    : "";
}

function workspaceDeepLinkTarget(section) {
  const definitions = {
    work: ["item", (id) => [`[data-work-item-id="${id}"]`]],
    tasks: ["item", (id) => [`[data-task-id="${id}"]`]],
    generation: ["job", (id) => [`[data-generation-job-id="${id}"]`]],
    review: ["review", (id) => [
      `[data-review-result-id="${id}"]`,
      `.content-review-decision-form[data-review-id="${id}"]`,
      `[data-action="open-content-review"][data-review-id="${id}"]`,
    ]],
    placement: ["placement", (id) => [`[data-placement-id="${id}"]`]],
    payouts: ["payout", (id) => [`[data-payout-id="${id}"]`]],
  };
  const definition = definitions[section];
  if (!definition || state.route.path !== `/workspace/${section}`) return null;
  const [parameterName, selectorsFor] = definition;
  const entityId = safeWorkspaceRouteEntityId(parameterName);
  if (!entityId) return null;
  return {
    key: `${state.route.path}?${parameterName}=${entityId}`,
    selectors: selectorsFor(entityId),
  };
}

function scheduleWorkspaceDeepLinkFocus(section) {
  const targetDefinition = workspaceDeepLinkTarget(section);
  if (
    !targetDefinition
    || state.workspaceDeepLinkFocusKey === targetDefinition.key
  ) return;
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
    if (state.route.path !== `/workspace/${section}`) return;
    const currentDefinition = workspaceDeepLinkTarget(section);
    if (!currentDefinition || currentDefinition.key !== targetDefinition.key) return;
    const target = currentDefinition.selectors
      .map((selector) => document.querySelector(selector))
      .find(Boolean);
    if (!target) return;
    state.workspaceDeepLinkFocusKey = currentDefinition.key;
    target.dataset.deepLinkFocused = "true";
    const focusTarget = target.matches(
      "a[href], button, input, select, textarea, [tabindex]",
    )
      ? target
      : target.querySelector(
        "a[href], button:not([disabled]), input:not([disabled]), "
        + "select:not([disabled]), textarea:not([disabled]), [tabindex]",
      );
    focusTarget?.focus?.({ preventScroll: true });
    scrollElementIntoView(target, "center");
    window.setTimeout(() => {
      if (target.isConnected) delete target.dataset.deepLinkFocused;
    }, 2400);
  }));
}

function settleRouteView() {
  window.requestAnimationFrame(() => {
    const path = state.route.path;
    let label = {
      "/login": "Вход",
      "/reset-password": "Восстановление доступа",
      "/set-password": "Новый пароль",
      "/access-locked": "Доступ приостановлен",
      "/learn": "Обучение",
      "/learn/first-shift": "Первая смена",
      "/learn/accounts": "Запуск аккаунтов",
      "/learn/practical": "Пробная работа",
      "/learn/exam": "Итоговый экзамен",
    }[path];
    if (!label && path.startsWith("/learn/accounts/")) {
      const platform = path.replace("/learn/accounts/", "");
      label = `Запуск ${platform === "vk" ? "VK" : platform === "youtube" ? "YouTube" : "Instagram"}`;
    }
    if (!label && path.startsWith("/workspace/")) {
      const section = path.replace("/workspace/", "");
      label = visibleWorkspaceTabs().find(([key]) => key === section)?.[1] || "Рабочий кабинет";
    }
    if (!label && path.startsWith("/learn/")) {
      const courseCode = path.replace("/learn/", "");
      label = learningCourses().find((course) => course.code === courseCode)?.title || "Курс";
    }
    document.title = `${label || "Контент ИИ Завод"} · Контент ИИ Завод`;
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    document.querySelector("#main-content")?.focus({ preventScroll: true });
  });
}

function authRedirectUrl(purpose) {
  const url = new URL("./", window.location.href);
  url.search = `?auth=${encodeURIComponent(purpose)}`;
  url.hash = "";
  return url.href;
}

function authErrorMessage(error) {
  const raw = String(error?.message || "Не удалось выполнить вход.");
  const normalized = raw.toLowerCase();
  if (error?.isUserSafe === true) return raw;
  if (normalized.includes("invalid login credentials")) return "Почта или пароль не совпали. Проверьте раскладку и попробуйте ещё раз.";
  if (normalized.includes("email not confirmed")) return "Сначала подтвердите почту по ссылке из приглашения.";
  if (normalized.includes("expired") || normalized.includes("otp")) return "Ссылка устарела или уже использована. Запросите новую.";
  if (normalized.includes("rate limit")) return "Слишком много попыток. Подождите несколько минут.";
  if (normalized.includes("не ответил за 15 секунд")) return raw;
  if (normalized.includes("required_password_change_incomplete")) return "Сервер не подтвердил смену временного пароля. Рабочие разделы остаются закрыты; повторите попытку.";
  console.error("Authentication request failed", error);
  return "Не удалось выполнить запрос. Проверьте соединение и попробуйте ещё раз.";
}

function actionErrorMessage(error) {
  console.error("Workspace action failed", error);
  if (error?.isUserSafe === true || error?.name === "CreatorApiError") {
    return String(error.message || "Не удалось выполнить действие.");
  }
  const normalized = String(error?.message || "").toLowerCase();
  if (normalized.includes("rate limit") || normalized.includes("too many")) {
    return "Слишком много запросов. Подождите несколько минут и повторите действие.";
  }
  if (normalized.includes("timeout") || normalized.includes("network") || normalized.includes("fetch")) {
    return "Связь прервалась. Проверьте интернет и повторите действие.";
  }
  if (normalized.includes("permission") || normalized.includes("forbidden") || normalized.includes("row-level")) {
    return "Для этого действия не хватает доступа. Обратитесь к руководителю команды.";
  }
  if (normalized.includes("duplicate") || normalized.includes("already exists")) {
    return "Такая запись уже существует. Обновите раздел и проверьте результат.";
  }
  if (normalized.includes("insufficient") || normalized.includes("balance") || normalized.includes("credit")) {
    return "Недостаточно средств для платного запуска. Проверьте баланс и повторите действие.";
  }
  if (normalized.includes("file") && (normalized.includes("size") || normalized.includes("type"))) {
    return "Файл не подходит по формату или размеру. Выберите другой исходник.";
  }
  if (normalized.includes("session") || normalized.includes("jwt")) {
    return "Сессия завершилась. Войдите в портал снова.";
  }
  return "Не удалось выполнить действие. Обновите раздел и попробуйте ещё раз.";
}

function displayProfile() {
  const profile = state.bootstrap?.profile || {};
  const membership = state.bootstrap?.membership || {};
  const email = state.user?.email || "";
  const name = profile.display_name || profile.name || email.split("@")[0] || "Участник";
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
  return { name, initials: initials || "AI", role: humanRole(membership.role || "creator") };
}

function humanRole(role) {
  return {
    owner: "Руководитель",
    admin: "Администратор команды",
    producer: "Продюсер",
    reviewer: "Проверяющий",
    operator: "Оператор",
    trainee: "Стажёр",
    viewer: "Наблюдатель",
    creator: "Креатор",
  }[role] || role;
}

function humanTaskType(type) {
  return {
    mock_generation: "Подготовка тестовых вариантов",
    video_review: "Проверка качества",
    general: "Общая задача",
    create_video: "Создание ролика",
    review_video: "Проверка качества",
    placement: "Публикация",
    metrics: "Сбор результатов",
    fix: "Исправление",
  }[type] || type || "Задача";
}

function humanMediaKind(kind) {
  return {
    product_photo: "Фото товара",
    packshot: "Фото упаковки",
    reference: "Референс",
    creator_reference: "Референс креатора",
    raw_video: "Исходное видео",
    source_video: "Исходное видео",
    generated_video: "Готовый ролик",
    voiceover: "Озвучка",
    subtitle: "Субтитры",
  }[String(kind || "")] || "Материал";
}

function humanMetricSource(source) {
  return {
    manual: "Вручную",
    csv: "Из файла",
    import: "Из файла",
    api: "Автоматически",
    official_api: "Автоматически",
    instagram: "Instagram",
    youtube: "YouTube",
    vk: "VK",
  }[String(source || "").toLowerCase()] || "Подтверждённый источник";
}

function listFrom(data, ...keys) {
  if (Array.isArray(data)) return data;
  for (const key of keys) {
    if (Array.isArray(data?.[key])) return data[key];
  }
  return [];
}

function statusBadge(status) {
  const normalized = String(status || "unknown").toLowerCase().replace(/[^a-z0-9_]/g, "");
  const labels = {
    todo: "К выполнению",
    in_progress: "В работе",
    submitted: "Отправлено",
    review: "На проверке",
    done: "Готово",
    completed: "Готово",
    approved: "Одобрено",
    paid: "Выплачено",
    ready: "Готово",
    pending: "Ожидает",
    queued: "В очереди",
    starting: "Запуск подтверждается",
    processing: "Генерируется",
    succeeded: "Готово",
    validated: "Проверено",
    running: "Выполняется",
    blocked: "Заблокировано",
    rejected: "Отклонено",
    failed: "Ошибка",
    cancelled: "Отменено",
    published: "Опубликовано",
    passed: "Сдан",
    active: "Активен",
    inactive: "Отключён",
    invited: "Принято сервисом",
    already_exists: "Аккаунт подключён",
    rate_limited: "Лимит",
    smtp_required: "Письмо не отправлено",
    pending_verification: "Нужно проверить",
    new: "Новый",
    reviewing: "На рассмотрении",
    planned: "Запланировано",
  };
  return `<span class="status-badge status-${normalized}">${escapeHtml(labels[normalized] || status || "—")}</span>`;
}

function humanGenerationStatus(status) {
  return {
    starting: "запуск подтверждается; повторный запуск заблокирован",
    submitted: "отправлено провайдеру",
    queued: "в очереди",
    processing: "генерируется",
    running: "генерируется",
    succeeded: "готово",
    completed: "готово",
    failed: "ошибка",
    cancelled: "отменено",
  }[status] || status || "неизвестно";
}

function alertMarkup(message, type = "info") {
  const icon = { danger: "!", warning: "!", success: "✓", info: "i" }[type] || "i";
  return `<div class="alert alert-${type}" role="${type === "danger" ? "alert" : "status"}"><strong aria-hidden="true">${icon}</strong><span>${escapeHtml(message)}</span></div>`;
}

function setFormBusy(form, busy, label = "Подождите…") {
  if (busy) form.dataset.busy = "true";
  else delete form.dataset.busy;
  const controls = form.querySelectorAll("button, input, select, textarea");
  controls.forEach((control) => {
    if (busy) {
      control.dataset.wasDisabled = String(control.disabled);
      control.disabled = true;
    } else {
      control.disabled = control.dataset.wasDisabled === "true";
      delete control.dataset.wasDisabled;
    }
  });
  const submit = form.querySelector('button[type="submit"]');
  if (submit) {
    if (busy) {
      submit.dataset.originalLabel = submit.innerHTML;
      submit.textContent = label;
    } else if (submit.dataset.originalLabel) {
      submit.innerHTML = submit.dataset.originalLabel;
      delete submit.dataset.originalLabel;
    }
  }
}

function withUiTimeout(operation, timeoutMs, message) {
  let timerId;
  const timeout = new Promise((_, reject) => {
    timerId = window.setTimeout(() => {
      const failure = new Error(message);
      failure.code = "ui_timeout";
      reject(failure);
    }, timeoutMs);
  });
  return Promise.race([operation, timeout]).finally(() => window.clearTimeout(timerId));
}

function toast(message, type = "info") {
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.setAttribute("role", type === "error" ? "alert" : "status");
  const icon = document.createElement("strong");
  icon.textContent = type === "success" ? "✓" : type === "error" ? "!" : "i";
  const text = document.createElement("span");
  text.textContent = String(message || "Готово");
  node.append(icon, text);
  toastRegion.append(node);
  window.setTimeout(() => node.remove(), 5200);
}

function focusFirst(selector) {
  window.requestAnimationFrame(() => document.querySelector(selector)?.focus());
}

function selectedQuestionCard(code) {
  return document.querySelector(`[data-exam-question="${CSS.escape(code)}"]`);
}

function normalizePercent(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return 0;
  return Math.round(numeric <= 1 ? numeric * 100 : numeric);
}

function normalizeBoolean(value) {
  return value === true || value === 1 || String(value).toLowerCase() === "true";
}

function normalizeExamOption(option) {
  if (typeof option === "string" || typeof option === "number") {
    const value = String(option).trim();
    return { value, label: value };
  }
  if (!option || typeof option !== "object" || Array.isArray(option)) {
    return { value: "", label: "" };
  }
  const value = String(option.value ?? option.code ?? option.id ?? option.label ?? option.text ?? "").trim();
  const label = String(option.label ?? option.text ?? option.title ?? value).trim();
  return { value, label };
}

function formatPercent(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return "0%";
  return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(numeric)}%`;
}

function formatNumber(value) {
  const numeric = Number(value || 0);
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(Number.isFinite(numeric) ? numeric : 0);
}

function nonnegativeInteger(value) {
  const numeric = Number(value);
  return Number.isSafeInteger(numeric) && numeric >= 0 ? numeric : null;
}

function datetimeLocalNow() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function formatMoney(minor, currency = "RUB") {
  const numeric = Number(minor || 0) / 100;
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency, maximumFractionDigits: 2 }).format(numeric);
}

function sumMinor(items) {
  return items.reduce((sum, item) => sum + Number(item.amount_minor || 0), 0);
}

function formatDate(value, withTime = false) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

function shouldRetrySamePublicRecoveryRequest(receipt) {
  return Boolean(
    receipt?.requestId
    && !receipt?.receiptToken
    && PUBLIC_RECOVERY_PENDING_STATUSES.has(String(receipt?.status || "")),
  );
}
function publicRecoveryReceiptState(receipt, { maskedEmail = "" } = {}) {
  const cooldownDate = new Date(receipt?.cooldownUntil || "");
  return {
    receiptToken: String(receipt?.receiptToken || ""),
    requestId: String(receipt?.requestId || ""),
    status: String(receipt?.status || "accepted"),
    requestedAt: String(receipt?.requestedAt || ""),
    cooldownUntil: Number.isNaN(cooldownDate.getTime()) ? 0 : cooldownDate.getTime(),
    maskedEmail: String(maskedEmail || ""),
  };
}

function readStoredPublicRecoveryReceipt() {
  let parsed;
  try {
    parsed = JSON.parse(
      safeStorageGet(window.localStorage, PUBLIC_RECOVERY_RECEIPT_STORAGE_KEY) || "null",
    );
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
  const receiptToken = String(parsed.receipt_token || "").trim();
  const requestId = String(parsed.request_id || "").trim();
  const status = String(parsed.status || "").trim().toLowerCase();
  const cooldownUntil = Number(parsed.cooldown_until || 0);
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(requestId)
    || (receiptToken && (
      receiptToken.length < 16
      || receiptToken.length > 512
      || !/^[a-z0-9._~-]+$/iu.test(receiptToken)
    ))
    || !/^[a-z0-9_]{2,64}$/u.test(status)
    || !Number.isFinite(cooldownUntil)
    || cooldownUntil < 0
  ) return null;
  return { receiptToken, requestId, status, cooldownUntil };
}

function persistPublicRecoveryReceipt(receipt) {
  const requestId = String(receipt?.requestId || "").trim();
  if (!requestId) return;
  safeStorageSet(
    window.localStorage,
    PUBLIC_RECOVERY_RECEIPT_STORAGE_KEY,
    JSON.stringify({
      receipt_token: String(receipt?.receiptToken || ""),
      request_id: requestId,
      status: String(receipt?.status || "outcome_unknown"),
      cooldown_until: Math.max(0, Number(receipt?.cooldownUntil || 0)),
    }),
  );
}

async function restorePublicRecoveryReceipt() {
  const current = state.resetReceipt;
  if (!state.api || !current?.receiptToken) return;
  try {
    const receipt = await withUiTimeout(
      state.api.getPublicRecoveryReceipt({ receiptToken: current.receiptToken }),
      AUTH_REQUEST_TIMEOUT_MS,
      "Сервер квитанций временно не ответил.",
    );
    state.resetReceipt = publicRecoveryReceiptState(
      {
        ...receipt,
        requestId: receipt.requestId || current.requestId,
      },
      { maskedEmail: current.maskedEmail || "" },
    );
    persistPublicRecoveryReceipt(state.resetReceipt);
    if (state.route.path === "/reset-password") renderResetRequest();
  } catch (error) {
    console.warn("Public recovery receipt refresh failed; preserved local receipt", error);
  }
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "только что";
  return new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function maskEmail(value) {
  const email = String(value || "").trim();
  const separator = email.lastIndexOf("@");
  if (separator <= 0) return "указанного адреса";
  const local = email.slice(0, separator);
  const domain = email.slice(separator + 1);
  const visible = local.slice(0, Math.min(2, local.length));
  return `${visible}${"•".repeat(Math.max(3, Math.min(8, local.length - visible.length)))}@${domain}`;
}

function startResetResendCountdown() {
  if (state.resetCountdownTimer) window.clearInterval(state.resetCountdownTimer);
  const button = document.querySelector("#reset-submit[data-resend-at]");
  if (!button) return;
  const update = () => {
    if (!button.isConnected) {
      window.clearInterval(state.resetCountdownTimer);
      state.resetCountdownTimer = null;
      return;
    }
    const remaining = Math.max(0, Number(button.dataset.resendAt || 0) - Date.now());
    if (remaining <= 0) {
      button.disabled = false;
      button.textContent = shouldRetrySamePublicRecoveryRequest(state.resetReceipt)
        ? "Проверить тот же запрос"
        : state.resetReceipt ? "Отправить ещё раз" : "Получить ссылку";
      window.clearInterval(state.resetCountdownTimer);
      state.resetCountdownTimer = null;
      return;
    }
    button.disabled = true;
    button.textContent = `Повторить через ${Math.ceil(remaining / 1000)} с`;
  };
  update();
  if (button.disabled) state.resetCountdownTimer = window.setInterval(update, 1000);
}

function formatBytes(bytes) {
  const numeric = Number(bytes || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return "0 Б";
  const units = ["Б", "КБ", "МБ", "ГБ"];
  const index = Math.min(Math.floor(Math.log(numeric) / Math.log(1024)), units.length - 1);
  return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(numeric / 1024 ** index)} ${units[index]}`;
}

function safeExternalUrl(value) {
  if (!value) return "#";
  try {
    const url = String(value).startsWith("/")
      ? new URL(value, CONFIG.SUPABASE_URL)
      : new URL(String(value));
    return url.protocol === "https:" || url.protocol === "blob:" ? escapeHtml(url.href) : "#";
  } catch {
    return "#";
  }
}

function isHttpsUrl(value) {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

function isTrustedGenerationDownload(value) {
  try {
    const url = new URL(value);
    const supabase = new URL(CONFIG.SUPABASE_URL);
    return url.protocol === "https:" && url.hostname === supabase.hostname;
  } catch {
    return false;
  }
}

function openExternalDownload(value) {
  const link = document.createElement("a");
  link.href = value;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.referrerPolicy = "no-referrer";
  document.body.append(link);
  link.click();
  link.remove();
}

function privateObjectKey(filename) {
  const org = String(state.bootstrap?.organization?.id || "");
  const user = String(state.user?.id || "");
  const prefix = String(state.bootstrap?.storage?.pathPrefix || "");
  const bucket = String(state.bootstrap?.storage?.bucket || "");
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  if (
    !uuid.test(org) ||
    !uuid.test(user) ||
    bucket !== CONFIG.STORAGE_BUCKET ||
    bucket !== "contentengine-private" ||
    prefix !== `${org}/${user}/`
  ) {
    throw new Error("Supabase не подтвердил безопасный путь приватной папки.");
  }
  const month = new Date().toISOString().slice(0, 7);
  const safeName = String(filename || "file")
    .normalize("NFKD")
    .replace(/[^a-zA-Z0-9._-]/g, "-")
    .replace(/-+/g, "-")
    .slice(-120);
  return `${prefix}uploads/${month}/${crypto.randomUUID()}-${safeName}`;
}

async function fileSha256(file) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function uniqueStrings(items) {
  return [...new Set((Array.isArray(items) ? items : []).filter(Boolean).map(String))];
}

function getSessionId() {
  const key = "contentengine.session-id.v1";
  try {
    let value = window.sessionStorage.getItem(key);
    if (!value) {
      value = crypto.randomUUID();
      window.sessionStorage.setItem(key, value);
    }
    return value;
  } catch {
    return crypto.randomUUID();
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
