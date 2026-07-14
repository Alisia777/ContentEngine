import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/+esm";
import { CreatorApi } from "./supabase-api.js";
import {
  FINAL_EXAM_CODE,
  REQUIRED_MODULE_CODES,
  WORKSPACE_TABS,
} from "./catalog.js";

const CONFIG = Object.freeze({ ...(window.CONTENTENGINE_CONFIG || {}) });
const app = document.querySelector("#app");
const toastRegion = document.querySelector("#toast-region");
const MAX_MOCK_BATCH_SIZE = Math.min(50, Math.max(1, Number(CONFIG.MAX_BATCH_SIZE) || 50));
const MOCK_GENERATION_ENABLED = CONFIG.MOCK_ENABLED === true;
const REAL_GENERATION_ENABLED = CONFIG.REAL_GENERATION_ENABLED === true;
const AUTH_REQUEST_TIMEOUT_MS = 15_000;
const REAL_GEN4_MODE = "real_gen4";
const REAL_SEEDANCE_MODE = "real_seedance";
const REAL_GENERATION_SKUS = Object.freeze({
  [REAL_GEN4_MODE]: Object.freeze({
    model: "gen4_turbo",
    durationSeconds: 5,
    audio: false,
    format: null,
    estimatedCredits: 25,
    estimatedUsd: "0.25",
    confirmation: "RUNWAY_GEN4_TURBO_5S_USD_0.25",
    label: "Runway gen4_turbo · 5 секунд · без голоса · ≈ 25 credits / $0.25",
  }),
  [REAL_SEEDANCE_MODE]: Object.freeze({
    model: "seedance2_fast",
    durationSeconds: 8,
    audio: true,
    format: "9:16",
    estimatedCredits: 232,
    estimatedUsd: "2.32",
    confirmation: "RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32",
    label: "Блогер + голос · 8 секунд · ≈ 232 credits / $2.32",
  }),
});
const MEMBERSHIP_LOCK_COPY = Object.freeze({
  membership_suspended: Object.freeze({
    title: "Доступ приостановлен",
    message: "Обратитесь к owner/admin вашей команды.",
  }),
  membership_revoked: Object.freeze({
    title: "Доступ отозван",
    message: "Обратитесь к owner/admin вашей команды.",
  }),
});

const state = {
  supabase: null,
  api: null,
  session: null,
  user: null,
  bootstrap: null,
  bootstrapStatus: "idle",
  bootstrapError: null,
  authPurpose: null,
  forcePassword: false,
  route: parseRoute(),
  mobileNavOpen: false,
  examResult: null,
  teamInviteResult: null,
  sections: Object.fromEntries(
    WORKSPACE_TABS.map(([key]) => [key, { status: "idle", data: null, error: null }]),
  ),
  sessionId: getSessionId(),
};

initialize().catch((error) => {
  console.error(error);
  renderFatal(error);
});

async function initialize() {
  bindGlobalEvents();

  const configProblems = validateConfig(CONFIG);
  if (configProblems.length) {
    renderSetup(configProblems);
    return;
  }

  state.supabase = createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_PUBLISHABLE_KEY, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
      flowType: "pkce",
      storage: window.sessionStorage,
      storageKey: `contentengine.creator-workspace.${new URL(CONFIG.SUPABASE_URL).hostname}.auth-session.v1`,
    },
  });
  state.api = new CreatorApi(state.supabase, CONFIG);

  const authLink = await consumeAuthLink();
  if (authLink?.purpose) {
    state.authPurpose = authLink.purpose;
    state.forcePassword = ["invite", "recovery"].includes(authLink.purpose);
  }

  const { data, error } = await state.supabase.auth.getSession();
  if (error) throw error;
  state.session = data.session;
  state.user = data.session?.user || null;

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
  window.addEventListener("hashchange", () => {
    state.route = parseRoute();
    state.mobileNavOpen = false;
    render();
    track("route_viewed", { route: state.route.path });
  });

  document.addEventListener("click", handleClick);
  document.addEventListener("submit", handleSubmit);
  document.addEventListener("change", handleChange);
  document.addEventListener("dragover", handleDragOver);
  document.addEventListener("dragleave", handleDragLeave);
  document.addEventListener("drop", handleDrop);
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

  if (event === "TOKEN_REFRESHED") {
    state.session = session;
    state.user = session?.user || null;
  }
}

async function consumeAuthLink() {
  const query = new URLSearchParams(window.location.search);
  const rawHash = window.location.hash && !window.location.hash.startsWith("#/")
    ? window.location.hash.slice(1)
    : "";
  const fragment = new URLSearchParams(rawHash);
  const errorDescription = query.get("error_description") || fragment.get("error_description");
  if (errorDescription) throw new Error(errorDescription);

  let purpose = query.get("type") || query.get("auth") || fragment.get("type");
  const tokenHash = query.get("token_hash") || fragment.get("token_hash");
  const code = query.get("code");
  const accessToken = fragment.get("access_token");
  const refreshToken = fragment.get("refresh_token");
  if (code && !purpose) purpose = "invite";
  let accepted = false;

  if (tokenHash && purpose) {
    const { error } = await state.supabase.auth.verifyOtp({
      token_hash: tokenHash,
      type: purpose,
    });
    if (error) throw error;
    accepted = true;
  } else if (code) {
    const { error } = await state.supabase.auth.exchangeCodeForSession(code);
    if (error) throw error;
    accepted = true;
  } else if (accessToken && refreshToken) {
    const { error } = await state.supabase.auth.setSession({
      access_token: accessToken,
      refresh_token: refreshToken,
    });
    if (error) throw error;
    accepted = true;
  }

  if (accepted) {
    const next = new URL(window.location.href);
    next.search = "";
    next.hash = ["invite", "recovery"].includes(purpose) ? "#/set-password" : "#/learn";
    window.history.replaceState({}, "", next);
    state.route = parseRoute();
  }

  return { accepted, purpose };
}

async function loadBootstrap() {
  state.bootstrapStatus = "loading";
  state.bootstrapError = null;
  render();

  try {
    const raw = await state.api.bootstrap({ session_id: state.sessionId });
    state.bootstrap = normalizeBootstrap(raw);
    if (membershipLockDetails(state.bootstrap)) {
      state.api.organizationId = null;
      state.examResult = null;
      state.teamInviteResult = null;
      for (const section of Object.values(state.sections)) {
        section.status = "idle";
        section.data = null;
        section.error = null;
      }
    }
    state.bootstrapStatus = "ready";
    state.bootstrapError = null;
  } catch (error) {
    state.bootstrap = null;
    state.bootstrapStatus = "error";
    state.bootstrapError = error;
  }
}

function normalizeBootstrap(raw) {
  const source = raw?.data && typeof raw.data === "object" ? raw.data : raw || {};
  const trainingSource = source.learning || source.training || source.onboarding || {};
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

  return {
    accessState: String(source.state || ""),
    profile: source.profile || source.user_profile || {},
    membership: source.membership || {},
    organization: source.organization || {},
    training: {
      completedModules,
      modules: serverModules,
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

function hasWorkspaceAccess() {
  if (!state.bootstrap || state.bootstrap.workspaceAccess !== true || !trainingCatalogReady()) return false;
  const completed = new Set(state.bootstrap.training.completedModules);
  return (
    REQUIRED_MODULE_CODES.every((code) => completed.has(code)) &&
    state.bootstrap.training.exam.passed === true
  );
}

function prerequisitesComplete() {
  const completed = new Set(state.bootstrap?.training?.completedModules || []);
  return REQUIRED_MODULE_CODES.every((code) => completed.has(code));
}

function learningCourses() {
  const modules = state.bootstrap?.training?.modules || [];
  const serverCourses = modules
    .filter((module) => module.type === "course")
    .sort((left, right) => Number(left.order || 0) - Number(right.order || 0))
    .map((module) => ({
      code: module.code,
      title: module.title,
      summary: module.description || "Обязательный модуль обучения.",
      duration: `${module.content?.lessons?.length || 0} шага`,
      lessons: Array.isArray(module.content?.lessons) ? module.content.lessons : [],
    }));
  return serverCourses;
}

function finalExamQuestions() {
  const questions = state.bootstrap?.training?.exam?.questions || [];
  const serverQuestions = questions
    .slice()
    .sort((left, right) => Number(left.order || 0) - Number(right.order || 0))
    .map((question) => ({
      code: question.code,
      type: question.type || "single_choice",
      text: question.prompt,
      options: (Array.isArray(question.options) ? question.options : [])
        .map(normalizeExamOption)
        .filter((option) => option.value && option.label),
    }));
  return serverQuestions;
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
    courses.every((course) => course.title && course.lessons.length > 0) &&
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
  else if (hasWorkspaceAccess()) navigate("/workspace/generation", true);
  else navigate("/learn", true);
}

function render() {
  const path = state.route.path;

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
    : "generation";
  const section = visibleWorkspaceTabs().some(([key]) => key === requestedSection)
    ? requestedSection
    : "generation";
  if (path !== `/workspace/${section}`) {
    navigate(`/workspace/${section}`, true);
    return;
  }
  renderWorkspace(section);
}

function renderLogin(message = "") {
  app.innerHTML = authLayout(`
    <section class="auth-card" aria-labelledby="login-title">
      <p class="eyebrow">Вход для команды</p>
      <h2 id="login-title">Добро пожаловать</h2>
      <p class="lead">Используйте адрес, на который пришло приглашение.</p>
      ${message ? alertMarkup(message, "danger") : ""}
      <form id="login-form" class="form-stack" novalidate>
        <label class="field">
          <span>Рабочая почта</span>
          <input name="email" type="email" autocomplete="username" inputmode="email" required placeholder="name@company.ru" />
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
      <p class="auth-footer">Нет приглашения? Попросите руководителя добавить вас в команду. Самостоятельная регистрация закрыта.</p>
      <p class="auth-footer">Сессия действует только в этой вкладке и завершится после её закрытия. Для массового запуска 50+ рекомендуется отдельный домен.</p>
    </section>
  `);
  focusFirst("#login-form input");
}

function renderResetRequest(message = "") {
  app.innerHTML = authLayout(`
    <section class="auth-card" aria-labelledby="reset-title">
      <p class="eyebrow">Восстановление доступа</p>
      <h2 id="reset-title">Задайте новый пароль</h2>
      <p class="lead">Мы отправим безопасную ссылку на рабочую почту.</p>
      ${message ? alertMarkup(message, "success") : ""}
      <form id="reset-form" class="form-stack" novalidate>
        <label class="field">
          <span>Рабочая почта</span>
          <input name="email" type="email" autocomplete="email" inputmode="email" required placeholder="name@company.ru" />
        </label>
        <button class="btn btn-block" type="submit">Отправить ссылку</button>
      </form>
      <div class="auth-actions"><a class="text-link" href="#/login">Вернуться ко входу</a></div>
      <p class="auth-footer">Сотрудник поддержки никогда не попросит прислать пароль или содержимое ссылки.</p>
    </section>
  `);
  focusFirst("#reset-form input");
}

function renderSetPassword(message = "", type = "") {
  app.innerHTML = authLayout(`
    <section class="auth-card" aria-labelledby="password-title">
      <p class="eyebrow">${state.authPurpose === "invite" ? "Активация приглашения" : "Защита аккаунта"}</p>
      <h2 id="password-title">Придумайте пароль</h2>
      <p class="lead">Не меньше 10 символов. Не используйте пароль от почты или соцсетей.</p>
      ${message ? alertMarkup(message, type || "danger") : ""}
      <form id="password-form" class="form-stack" novalidate>
        <label class="field">
          <span>Новый пароль</span>
          <input name="password" type="password" autocomplete="new-password" required minlength="10" placeholder="Минимум 10 символов" />
        </label>
        <label class="field">
          <span>Повторите пароль</span>
          <input name="password_confirmation" type="password" autocomplete="new-password" required minlength="10" placeholder="Ещё раз" />
        </label>
        <button class="btn btn-block" type="submit">Сохранить и продолжить</button>
      </form>
      <p class="auth-footer">Ссылка активации одноразовая. После сохранения начнётся обязательное обучение.</p>
    </section>
  `);
  focusFirst("#password-form input");
}

function authLayout(panel) {
  return `
    <div class="auth-layout">
      <section class="auth-story" aria-label="О продукте">
        <div class="auth-brand">
          <div class="brand-mark" aria-hidden="true">A</div>
          <div><strong>ALTEA</strong><span>Контент ИИ Завод</span></div>
        </div>
        <div class="auth-message">
          <p class="eyebrow">От товара до результата</p>
          <h1>Понятная работа.<br /><em>Измеримый результат.</em></h1>
          <p>Обучение, подготовка видео, проверка, размещение и метрики — один безопасный цикл для всей команды.</p>
        </div>
        <div class="auth-steps" aria-label="Этапы работы">
          <div class="auth-step"><b>01 · ОБУЧЕНИЕ</b><span>4 коротких курса и экзамен</span></div>
          <div class="auth-step"><b>02 · ПРОИЗВОДСТВО</b><span>Только назначенные SKU и материалы</span></div>
          <div class="auth-step"><b>03 · РЕЗУЛЬТАТ</b><span>Final URL, метрики и выплата</span></div>
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
  const message = state.bootstrapError?.message || "Не удалось получить рабочие данные.";
  app.innerHTML = `
    <main id="main-content" class="error-page" tabindex="-1">
      <div class="boot-mark" aria-hidden="true">!</div>
      <p class="eyebrow">Вход выполнен, кабинет недоступен</p>
      <h1>Облачная настройка не завершена</h1>
      <p class="muted">${escapeHtml(message)}</p>
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

function renderLearningHome() {
  const completed = new Set(state.bootstrap.training.completedModules);
  const completeCount = REQUIRED_MODULE_CODES.filter((code) => completed.has(code)).length;
  const examPassed = state.bootstrap.training.exam.passed;
  const progress = Math.round(((completeCount + (examPassed ? 1 : 0)) / 5) * 100);
  const catalogReady = trainingCatalogReady();

  const content = `
    <div class="page-wrap">
      <section class="card onboarding-hero">
        <p class="eyebrow" style="color:#e4c98f">Обязательный допуск к работе</p>
        <h1>${examPassed ? "Допуск получен" : "Сначала научимся работать безопасно"}</h1>
        <p>${examPassed ? "Вы можете вернуться к материалам в любой момент." : "Четыре коротких курса объяснят весь цикл. После них — 12 рабочих сценариев. Кабинет откроется только после успешного экзамена."}</p>
        <div class="onboarding-progress">
          <div class="progress-bar" aria-label="Прогресс обучения: ${progress}%"><span style="width:${progress}%"></span></div>
          <strong>${completeCount}/4 курса${examPassed ? " · экзамен сдан" : ""}</strong>
        </div>
      </section>

      ${catalogReady ? "" : alertMarkup("Supabase вернул неполный каталог обучения. Допуск закрыт: обновите страницу или обратитесь к администратору.", "danger")}

      <div class="course-grid">
        ${learningCourses().map((course, index) => courseCardMarkup(course, index, completed.has(course.code))).join("")}
      </div>

      <section class="card exam-card">
        <div>
          <span class="badge ${examPassed ? "badge-success" : prerequisitesComplete() ? "badge-info" : ""}">
            ${examPassed ? "Сдан" : catalogReady && prerequisitesComplete() ? "Доступен" : "После 4 курсов"}
          </span>
          <h2>Итоговый экзамен: 12 ситуаций</h2>
          <p class="muted">Для допуска нужно правильно решить не меньше ${finalExamPassScore()} из 12 сценариев. Ответы проверяет Supabase, ключа ответов в браузере нет.</p>
        </div>
        <a class="btn ${catalogReady && prerequisitesComplete() ? "" : "btn-secondary"}" href="${catalogReady && prerequisitesComplete() ? "#/learn/exam" : "#/learn"}" ${catalogReady && prerequisitesComplete() ? "" : "aria-disabled=\"true\""}>
          ${examPassed ? "Посмотреть результат" : catalogReady && prerequisitesComplete() ? "Начать экзамен" : "Сначала курсы"}
        </a>
      </section>
    </div>
  `;
  app.innerHTML = learningScaffold(content, "/learn");
}

function courseCardMarkup(course, index, complete) {
  return `
    <article class="card course-card ${complete ? "complete" : ""}">
      <div class="course-number" aria-hidden="true">0${index + 1}</div>
      <span class="badge ${complete ? "badge-success" : ""}">${complete ? "Пройден" : course.duration}</span>
      <h2>${escapeHtml(course.title)}</h2>
      <p>${escapeHtml(course.summary)}</p>
      <div class="course-footer">
        <small class="muted">${course.lessons.length} шага</small>
        <a class="btn btn-small ${complete ? "btn-secondary" : ""}" href="#/learn/${encodeURIComponent(course.code)}">
          ${complete ? "Повторить" : "Открыть"} <span aria-hidden="true">→</span>
        </a>
      </div>
    </article>
  `;
}

function renderCourse(code) {
  const course = learningCourses().find((item) => item.code === code);
  if (!course) {
    navigate("/learn", true);
    return;
  }
  const complete = state.bootstrap.training.completedModules.includes(course.code);
  const content = `
    <div class="page-wrap">
      <header class="page-header">
        <div>
          <p class="eyebrow"><a href="#/learn" style="text-decoration:none">Обучение</a> · ${escapeHtml(course.duration)}</p>
          <h1>${escapeHtml(course.title)}</h1>
          <p>${escapeHtml(course.summary)}</p>
        </div>
        <span class="badge ${complete ? "badge-success" : ""}">${complete ? "Курс пройден" : "Обязательный курс"}</span>
      </header>
      <div class="course-layout">
        <div class="lesson-stack">
          ${course.lessons.map((lesson, index) => lessonMarkup(lesson, index)).join("")}
        </div>
        <aside class="card sticky-card">
          <p class="eyebrow">Завершение курса</p>
          <h2 style="font:600 1.35rem/1.2 Georgia,serif">Проверьте понимание</h2>
          <p class="muted tiny">Отметка сохраняется в Supabase и относится только к вашему аккаунту.</p>
          ${complete ? alertMarkup("Курс уже пройден. Материал можно повторять без ограничений.", "success") : `
            <label class="acknowledgement">
              <input id="course-ack" type="checkbox" />
              <span>Я прочитал(а) все шаги и понимаю, когда нужно остановить задачу и обратиться к руководителю.</span>
            </label>
            <button class="btn btn-block" type="button" data-action="complete-course" data-module-code="${escapeHtml(course.code)}" disabled>Завершить курс</button>
          `}
          <a class="btn btn-secondary btn-block" style="margin-top:10px" href="#/learn">К списку курсов</a>
        </aside>
      </div>
    </div>
  `;
  app.innerHTML = learningScaffold(content, `/learn/${course.code}`);
  track("course_opened", { module_code: course.code });
}

function lessonMarkup(lesson, index) {
  return `
    <article class="card lesson-card">
      <p class="eyebrow">Шаг ${index + 1}</p>
      <h2>${escapeHtml(lesson.title)}</h2>
      <p>${escapeHtml(lesson.body)}</p>
      ${lesson.bullets ? `<ul>${lesson.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
      ${lesson.callout ? alertMarkup(lesson.callout, "warning") : ""}
    </article>
  `;
}

function renderExam() {
  if (!trainingCatalogReady()) {
    const content = `
      <div class="page-wrap">
        <section class="card result-banner">
          <div class="result-score" aria-hidden="true">!</div>
          <h2>Экзамен временно недоступен</h2>
          <p class="muted">Supabase не вернул полный каталог из четырёх курсов и двенадцати вопросов. Рабочий кабинет остаётся закрыт.</p>
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
          <p class="muted">Экзамен откроется, когда Supabase подтвердит каждый обязательный модуль.</p>
          <a class="btn" href="#/learn">Вернуться к курсам</a>
        </section>
      </div>
    `;
    app.innerHTML = learningScaffold(content, "/learn/exam");
    return;
  }

  if (state.bootstrap.training.exam.passed) {
    const score = state.bootstrap.training.exam.score;
    const content = `
      <div class="page-wrap">
        <section class="card result-banner">
          <div class="result-score">${score ? `${score}%` : "✓"}</div>
          <p class="eyebrow">Итоговый экзамен</p>
          <h2>Допуск к кабинету получен</h2>
          <p class="muted">Все рабочие разделы открыты. Правила качества и прослеживаемости продолжают действовать в каждой задаче.</p>
          <a class="btn" href="#/workspace/generation">Перейти к работе <span aria-hidden="true">→</span></a>
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
          ${alertMarkup("Ответы и ключ проверки остаются на стороне Supabase. Система показывает только темы для повторения.", "info")}
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
          <p class="muted">Обновите данные из Supabase. До получения всех двенадцати сценариев отправка экзамена закрыта.</p>
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
          <p>Ответьте на все вопросы. Для прохождения нужно ${finalExamPassScore()} правильных ответов из 12. Проверка выполняется на стороне Supabase.</p>
        </div>
        <span class="badge badge-warning">Попытка за 24 часа ${Math.min(state.bootstrap.training.exam.attemptCount24h + 1, state.bootstrap.training.exam.attemptLimit24h)}/${state.bootstrap.training.exam.attemptLimit24h}</span>
      </header>
      ${result && !result.passed ? examResultMarkup(result) : ""}
      <form id="exam-form" class="exam-form" novalidate>
        ${questions.map((question, index) => questionMarkup(question, index)).join("")}
        <div class="exam-submit">
          <div><strong id="exam-answer-count">0 из 12 отвечено</strong><br /><small class="muted">Незаполненный экзамен не отправится</small></div>
          <button class="btn" type="submit">Проверить ответы</button>
        </div>
      </form>
    </div>
  `;
  app.innerHTML = learningScaffold(content, "/learn/exam");
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
    </fieldset>
  `;
}

function examResultMarkup(result) {
  const correct = Number(result.correctCount || 0);
  const total = Number(result.total || finalExamQuestions().length);
  return `
    <section class="card result-banner" style="margin-bottom:18px">
      <div class="result-score">${correct}/${total}</div>
      <h2>Пока не хватило одного или нескольких решений</h2>
      <p class="muted">Повторите темы, отмеченные проверкой, и попробуйте ещё раз. Рабочий кабинет остаётся закрыт.</p>
      ${result.topics?.length ? `<p><strong>Повторить:</strong> ${result.topics.map(escapeHtml).join(", ")}</p>` : ""}
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
  return `
    <div class="workspace-shell">
      <aside class="sidebar" aria-label="Навигация обучения">
        ${brandMarkup()}
        <nav class="workspace-nav">
          <span class="nav-caption">Допуск к работе</span>
          <a class="nav-link ${activePath === "/learn" ? "active" : ""}" href="#/learn">
            <span class="nav-icon" aria-hidden="true">◎</span><span>Курсы</span>
          </a>
          <a class="nav-link ${activePath === "/learn/exam" ? "active" : ""}" href="#/learn/exam">
            <span class="nav-icon" aria-hidden="true">◇</span><span>Итоговый экзамен</span>
          </a>
          ${hasWorkspaceAccess() ? `
            <span class="nav-caption" style="margin-top:15px">Работа</span>
            <a class="nav-link" href="#/workspace/generation"><span class="nav-icon" aria-hidden="true">→</span><span>Открыть кабинет</span></a>
          ` : `
            <span class="nav-caption" style="margin-top:15px">Работа</span>
            <span class="nav-link" aria-disabled="true" style="opacity:.42"><span class="nav-icon" aria-hidden="true">⌑</span><span>Закрыто до экзамена</span></span>
          `}
        </nav>
        ${sidebarFooterMarkup(profile)}
      </aside>
      <section class="workspace-main">
        ${mobileTopbarMarkup("Обучение")}
        ${state.mobileNavOpen ? mobileNavMarkup(true) : ""}
        <main id="main-content" tabindex="-1">${content}</main>
      </section>
    </div>
  `;
}

function renderWorkspace(section) {
  const sectionState = state.sections[section];
  if (sectionState.status === "idle") {
    window.queueMicrotask(() => loadSection(section));
  }

  const renderer = {
    generation: renderGenerationSection,
    placement: renderPlacementSection,
    stats: renderStatsSection,
    payouts: renderPayoutsSection,
    tasks: renderTasksSection,
    media: renderMediaSection,
    feedback: renderFeedbackSection,
    team: renderTeamSection,
  }[section];

  const content = renderer(sectionState);
  app.innerHTML = workspaceScaffold(content, section);
}

function workspaceScaffold(content, activeSection) {
  const profile = displayProfile();
  const tabs = visibleWorkspaceTabs();
  const tabLabel = tabs.find(([key]) => key === activeSection)?.[1] || "Кабинет";
  return `
    <div class="workspace-shell">
      <aside class="sidebar" aria-label="Основная навигация">
        ${brandMarkup()}
        <nav class="workspace-nav">
          <span class="nav-caption">Производство</span>
          ${tabs.map(([key, label, icon]) => `
            ${key === "stats" ? `<span class="nav-caption" style="margin-top:15px">Результат</span>` : ""}
            ${key === "media" ? `<span class="nav-caption" style="margin-top:15px">Материалы и помощь</span>` : ""}
            ${key === "team" ? `<span class="nav-caption" style="margin-top:15px">Администрирование</span>` : ""}
            <a class="nav-link ${key === activeSection ? "active" : ""}" href="#/workspace/${key}">
              <span class="nav-icon" aria-hidden="true">${icon}</span><span>${label}</span>
            </a>
          `).join("")}
          <a class="nav-link" href="#/learn"><span class="nav-icon" aria-hidden="true">◎</span><span>Обучение</span></a>
        </nav>
        ${sidebarFooterMarkup(profile)}
      </aside>
      <section class="workspace-main">
        ${mobileTopbarMarkup(tabLabel)}
        ${state.mobileNavOpen ? mobileNavMarkup(false, activeSection) : ""}
        <main id="main-content" tabindex="-1">${content}</main>
      </section>
    </div>
  `;
}

function canManageTeam() {
  return ["owner", "admin"].includes(state.bootstrap?.membership?.role);
}

function visibleWorkspaceTabs() {
  return WORKSPACE_TABS.filter(([key]) => key !== "team" || canManageTeam());
}

function brandMarkup() {
  return `
    <div class="workspace-brand">
      <div class="brand-mark" aria-hidden="true">A</div>
      <div><strong>ALTEA</strong><span>Контент ИИ Завод</span></div>
    </div>
  `;
}

function sidebarFooterMarkup(profile) {
  return `
    <div class="sidebar-footer">
      <div class="sidebar-status"><span class="status-dot"></span><span>Supabase · защищено</span></div>
      <div class="sidebar-user">
        <span class="avatar" aria-hidden="true">${escapeHtml(profile.initials)}</span>
        <div class="user-meta"><strong>${escapeHtml(profile.name)}</strong><span>${escapeHtml(profile.role)}</span></div>
        <button class="logout-button" type="button" data-action="logout" title="Выйти" aria-label="Выйти">↪</button>
      </div>
    </div>
  `;
}

function mobileTopbarMarkup(label) {
  return `
    <header class="mobile-topbar">
      <span class="mobile-brand">ALTEA · ${escapeHtml(label)}</span>
      <button class="mobile-nav-trigger" type="button" data-action="toggle-mobile-nav" aria-label="Открыть меню" aria-expanded="${state.mobileNavOpen}">☰</button>
    </header>
  `;
}

function mobileNavMarkup(learningOnly, activeSection = "") {
  return `
    <nav class="mobile-nav" aria-label="Мобильная навигация">
      ${learningOnly ? `
        <a class="nav-link" href="#/learn"><span class="nav-icon">◎</span>Курсы</a>
        <a class="nav-link" href="#/learn/exam"><span class="nav-icon">◇</span>Экзамен</a>
        ${hasWorkspaceAccess() ? `<a class="nav-link" href="#/workspace/generation"><span class="nav-icon">→</span>Кабинет</a>` : ""}
      ` : visibleWorkspaceTabs().map(([key, label, icon]) => `
        <a class="nav-link ${key === activeSection ? "active" : ""}" href="#/workspace/${key}"><span class="nav-icon">${icon}</span>${label}</a>
      `).join("")}
      <button class="btn btn-secondary btn-block" type="button" data-action="logout">Выйти</button>
    </nav>
  `;
}

async function loadSection(section, options = {}) {
  const target = state.sections[section];
  if (!target || target.status === "loading") return;
  target.status = "loading";
  target.error = null;
  if (!options.silent) render();

  try {
    const raw = await state.api.workspaceSection(section);
    target.data = raw?.data ?? raw ?? {};
    if (["generation", "media"].includes(section)) {
      target.data = await hydratePrivateMedia(target.data);
    }
    target.status = "ready";
  } catch (error) {
    target.error = error;
    target.status = "error";
  }
  render();
}

async function hydratePrivateMedia(data) {
  if (!data || typeof data !== "object") return data;
  const listKeys = ["media", "media_items", "items", "artifacts"];
  const objectKeys = [];
  for (const key of listKeys) {
    if (!Array.isArray(data[key])) continue;
    for (const item of data[key]) {
      const objectKey = item?.object_name || item?.object_key;
      if (objectKey && !item.signed_url) objectKeys.push(String(objectKey));
    }
  }
  if (!objectKeys.length) return data;
  try {
    const signedUrls = await state.api.signedPrivateObjectUrls(objectKeys);
    for (const key of listKeys) {
      if (!Array.isArray(data[key])) continue;
      data[key] = data[key].map((item) => {
        const objectKey = item?.object_name || item?.object_key;
        return objectKey && signedUrls.has(String(objectKey))
          ? { ...item, signed_url: signedUrls.get(String(objectKey)) }
          : item;
      });
    }
  } catch {
    // Metadata remains usable when a short-lived preview URL cannot be issued.
  }
  return data;
}

function realGenerationSku(mode) {
  return REAL_GENERATION_SKUS[String(mode || "")] || null;
}

function isRealGenerationMode(mode) {
  return realGenerationSku(mode) !== null;
}

function renderGenerationSection(sectionState) {
  const data = sectionState.data || {};
  const batches = listFrom(data, "batches");
  const media = listFrom(data, "media", "media_items");
  const exactMedia = media.filter((item) => ["product_photo", "packshot"].includes(item.kind));
  const aliases = listFrom(data, "wb_aliases", "aliases");
  const defaultMode = MOCK_GENERATION_ENABLED ? "mock" : REAL_SEEDANCE_MODE;
  const defaultRealSku = realGenerationSku(defaultMode) || REAL_GENERATION_SKUS[REAL_SEEDANCE_MODE];
  const defaultIsReal = isRealGenerationMode(defaultMode);
  const canManageAliases = ["owner", "admin", "producer"].includes(state.bootstrap?.membership?.role);
  const canAssignTeam = canManageTeam();
  if (canAssignTeam && state.sections.team.status === "idle") {
    window.queueMicrotask(() => loadSection("team", { silent: true }));
  }
  const assignableMembers = listFrom(state.sections.team.data || {}, "members").filter(
    (member) => member.status === "active" && normalizeBoolean(member.exam_passed),
  );
  if (
    state.user?.id &&
    !assignableMembers.some((member) => String(member.profile_id) === String(state.user.id))
  ) {
    assignableMembers.unshift({
      profile_id: state.user.id,
      display_name: state.bootstrap?.profile?.display_name || state.user.email || "Вы",
      role: state.bootstrap?.membership?.role,
      status: "active",
      exam_passed: true,
    });
  }
  return `
    <div class="page-wrap">
      ${pageHeader(
        "Генерация",
        "Подготовьте бесплатный dry-run или один реальный ролик Runway по точному SKU и исходнику.",
        REAL_GENERATION_ENABLED
          ? `<span class="badge badge-info">RUNWAY + MOCK</span>`
          : `<span class="badge badge-mock">MOCK · 0 ₽</span>`,
      )}
      <div class="split-grid">
        <section class="card card-pad">
          <p class="eyebrow">Одно следующее действие</p>
          <h2 style="font:600 1.55rem/1.15 Georgia,serif; margin:0 0 8px">Выберите режим запуска</h2>
          <p class="muted tiny">Mock создаёт до ${MAX_MOCK_BATCH_SIZE} dry-run вариантов без списаний. Платный режим создаёт ровно один ролик: 5-секундную анимацию товара без голоса или 8-секундного блогера с аудио.</p>
          <form id="mock-batch-form" class="form-stack" style="margin-top:18px" novalidate>
            <label class="field">
              <span>Режим генерации *</span>
              <select id="generation-mode" name="generation_mode" required>
                ${MOCK_GENERATION_ENABLED ? `<option value="mock" ${defaultMode === "mock" ? "selected" : ""}>Mock · dry-run · 0 ₽</option>` : ""}
                ${REAL_GENERATION_ENABLED ? `
                  <option value="${REAL_SEEDANCE_MODE}" ${defaultMode === REAL_SEEDANCE_MODE ? "selected" : ""}>${REAL_GENERATION_SKUS[REAL_SEEDANCE_MODE].label}</option>
                  <option value="${REAL_GEN4_MODE}" ${defaultMode === REAL_GEN4_MODE ? "selected" : ""}>${REAL_GENERATION_SKUS[REAL_GEN4_MODE].label}</option>
                ` : ""}
              </select>
            </label>
            <div id="real-generation-confirmation" ${defaultIsReal ? "" : "hidden"}>
              <div class="alert alert-warning" role="status"><strong aria-hidden="true">!</strong><span id="real-generation-price">Платный запуск: ориентировочно ${defaultRealSku.estimatedCredits} credits / $${defaultRealSku.estimatedUsd}. Итог зависит от тарифа провайдера.</span></div>
              <p id="real-generation-note" class="muted tiny" style="margin:8px 0 0">${defaultMode === REAL_SEEDANCE_MODE ? "Runway создаёт аудио по текстовому запросу, но не гарантирует дословную русскую реплику. Проверьте результат перед публикацией." : "Этот режим создаёт видео без сгенерированной речи."}</p>
              <label class="option" style="margin-top:10px">
                <input type="checkbox" name="real_spend_confirmation" value="${defaultRealSku.confirmation}" ${defaultIsReal ? "required" : ""} />
                <span><strong>Подтверждаю один платный запуск Runway</strong><br /><small id="real-generation-confirmation-copy" class="muted">${defaultRealSku.model} · ${defaultRealSku.durationSeconds} секунд · ровно одно видео · около $${defaultRealSku.estimatedUsd}</small></span>
              </label>
            </div>
            <label class="field">
              <span>Артикул / SKU *</span>
              <input name="sku" required maxlength="120" placeholder="Например: WB-12345678" autocomplete="off" />
              <small class="field-hint">Скопируйте из назначенной карточки, не вводите похожий товар.</small>
            </label>
            <label class="field">
              <span>Название товара *</span>
              <input name="product_name" required maxlength="180" placeholder="Точное название и вариант" autocomplete="off" />
            </label>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px">
              <label class="field">
                <span>Площадка *</span>
                <select name="platform" required><option value="instagram">Instagram</option><option value="tiktok">TikTok</option><option value="youtube">YouTube</option><option value="vk">VK</option><option value="telegram">Telegram</option><option value="wildberries">Wildberries</option></select>
              </label>
              <label class="field">
                <span>Аккаунт / карточка *</span>
                <input name="destination_ref" required minlength="2" maxlength="240" placeholder="Точный @аккаунт, канал или карточка" autocomplete="off" />
              </label>
            </div>
            ${canAssignTeam ? `
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px">
                <label class="field">
                  <span>Исполнитель *</span>
                  <select name="assignee_id" required>
                    ${assignableMembers.map((member) => `<option value="${escapeHtml(member.profile_id)}" ${String(member.profile_id) === String(state.user?.id) ? "selected" : ""}>${escapeHtml(member.display_name || member.email || humanRole(member.role))}</option>`).join("")}
                  </select>
                  <small class="field-hint">Доступны только участники, уже сдавшие экзамен.</small>
                </label>
                <label class="field">
                  <span>Вознаграждение за задачу, ₽</span>
                  <input name="payout_rub" type="number" min="0" max="10000" step="0.01" value="0" required />
                  <small class="field-hint">Это начисление в реестре, не автоматический платёж.</small>
                </label>
              </div>
            ` : ""}
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px">
              <label class="field">
                <span>Количество</span>
                <input name="count" type="number" min="1" max="${defaultIsReal ? 1 : MAX_MOCK_BATCH_SIZE}" value="${defaultIsReal ? 1 : 5}" ${defaultIsReal ? "readonly" : ""} required />
                <small id="generation-count-hint" class="field-hint">${defaultIsReal ? "Платный режим всегда создаёт ровно одно видео." : `Mock: от 1 до ${MAX_MOCK_BATCH_SIZE} вариантов.`}</small>
              </label>
              <label class="field">
                <span>Формат</span>
                <select name="format"><option value="9:16">9:16 · вертикальный</option><option value="1:1">1:1 · квадрат</option><option value="16:9">16:9 · горизонтальный</option></select>
              </label>
            </div>
            <label class="field">
              <span>Что должен понять зритель</span>
              <textarea name="brief" maxlength="1200" ${defaultIsReal ? "required" : ""} placeholder="Опишите блогера, точный товар, сцену и дословную реплику"></textarea>
              <small id="generation-brief-hint" class="field-hint">${defaultMode === REAL_SEEDANCE_MODE ? "Перед оплатой вставьте сценарий именно выбранного товара и проверьте дословную реплику." : "Для платного режима опишите один ролик без неподтверждённых обещаний."}</small>
            </label>
            ${exactMedia.length ? `
              <fieldset style="border:0; padding:0; margin:0">
                <legend class="field-label">Точное фото товара *</legend>
                <p id="generation-media-hint" class="muted tiny">${defaultIsReal ? "Для платного запуска выберите ровно один исходник." : "Для mock можно выбрать один или несколько исходников."}</p>
                <div class="option-list" style="margin-top:8px">
                  ${exactMedia.slice(0, 8).map((item) => `
                    <label class="option">
                      <input type="${defaultIsReal ? "radio" : "checkbox"}" name="media_id" value="${escapeHtml(item.public_id || item.id)}" />
                      <span><strong>${escapeHtml(item.original_filename || item.name || "Файл")}</strong><br /><small class="muted">${escapeHtml(item.kind || item.mime_type || "исходник")}</small></span>
                    </label>
                  `).join("")}
                </div>
              </fieldset>
            ` : `<div class="alert alert-warning" role="status"><strong aria-hidden="true">!</strong><span>Сначала добавьте точное фото товара или packshot в <a href="#/workspace/media">Медиатеку</a>. Без исходника запуск недоступен.</span></div>`}
            <button id="generation-submit" class="btn btn-block" type="submit" ${exactMedia.length ? "" : "disabled"}>${defaultIsReal ? `Запустить 1 платное видео · около $${defaultRealSku.estimatedUsd}` : "Подготовить dry-run batch"}</button>
          </form>
        </section>

        <section class="card">
          <div class="card-header"><div><p class="eyebrow">Очередь</p><h2>Последние batch</h2></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="generation">Обновить</button></div>
          ${sectionBody(sectionState, batches.length ? generationTable(batches) : emptyState("✦", "Пока нет запусков", "Заполните форму слева — первый batch появится здесь."))}
        </section>
      </div>
      ${(canManageAliases || aliases.length) ? `
        <section class="card card-pad" style="margin-top:22px">
          <div class="split-grid">
            <div>
              <p class="eyebrow">Идентичность товара</p>
              <h2 style="font:600 1.5rem/1.2 Georgia,serif; margin:0 0 8px">Артикулы Wildberries</h2>
              <p class="muted tiny">Если WB заменил артикул, мы не переписываем прошлое. Старая и подменная карточки сохраняются как датированная связь с одним точным SKU — так метрики остаются сопоставимыми.</p>
              ${aliases.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>SKU</th><th>Текущий</th><th>Старый / подменный</th></tr></thead><tbody>${aliases.slice(0, 20).map((item) => `<tr><td>${escapeHtml(item.sku)}</td><td>${escapeHtml(item.current_article || item.canonical_article || "—")}</td><td>${escapeHtml(item.alias_article || item.wb_alias || "—")}</td></tr>`).join("")}</tbody></table></div>` : emptyState("WB", "Связей пока нет", "Добавляйте alias только после подтверждённой замены артикула.")}
            </div>
            ${canManageAliases ? `
              <form id="wb-alias-form" class="form-stack" novalidate>
                <label class="field"><span>Внутренний SKU *</span><input name="sku" required maxlength="120" placeholder="Точный SKU товара" /></label>
                <label class="field"><span>Текущий артикул WB *</span><input name="current_article" required maxlength="120" inputmode="numeric" placeholder="Например: 123456789" /></label>
                <label class="field"><span>Старый / подменный артикул *</span><input name="alias_article" required maxlength="120" inputmode="numeric" placeholder="Артикул из исторических данных" /></label>
                <label class="field"><span>Почему появилась связь *</span><textarea name="reason" required minlength="5" maxlength="600" placeholder="Например: WB заменил карточку 13.07.2026; подтверждено владельцем"></textarea></label>
                <button class="btn" type="submit">Сохранить связь без перезаписи истории</button>
              </form>
            ` : alertMarkup("Изменять связи могут owner, admin или producer. Вам доступен только просмотр.", "info")}
          </div>
        </section>
      ` : ""}
    </div>
  `;
}

function generationTable(items) {
  return `
    <div class="table-wrap"><table class="data-table">
      <thead><tr><th>Batch</th><th>SKU</th><th>Запрошено</th><th>Готово</th><th>Статус</th><th>Создан</th></tr></thead>
      <tbody>${items.map((item) => {
        const parameters = item.parameters && typeof item.parameters === "object" ? item.parameters : {};
        const real = String(item.mode || parameters.mode || "mock").toLowerCase() === "real";
        const model = String(item.model || parameters.model || "gen4_turbo");
        const duration = Number(item.duration_seconds || parameters.duration_seconds || 5);
        const audio = normalizeBoolean(item.audio ?? parameters.audio);
        const realLabel = `Runway · ${model} · ${duration}s${audio ? " · audio" : ""} · paid`;
        const jobId = real ? String(parameters.job_id || "") : "";
        const status = String(item.status || parameters.job_status || "queued");
        const realAction = jobId
          ? `<div style="margin-top:8px"><button class="btn btn-secondary btn-small" type="button" data-action="check-real-generation" data-job-id="${escapeHtml(jobId)}">${["succeeded", "completed"].includes(status.toLowerCase()) ? "Скачать MP4" : "Проверить статус"}</button></div>`
          : "";
        return `
          <tr>
            <td><strong>${escapeHtml(item.name || item.public_id || `#${item.id}`)}</strong><br /><small class="muted">${real ? escapeHtml(realLabel) : "mock · dry-run"}</small></td>
            <td>${escapeHtml(item.sku || parameters.sku || "—")}</td>
            <td>${formatNumber(item.total_requested ?? item.count ?? (real ? 1 : 0))}</td>
            <td>${formatNumber(item.total_accepted ?? item.completed ?? 0)}</td>
            <td>${statusBadge(status)}${realAction}</td>
            <td>${formatDate(item.created_at)}</td>
          </tr>
        `;
      }).join("")}</tbody>
    </table></div>
  `;
}

function renderPlacementSection(sectionState) {
  const data = sectionState.data || {};
  const items = listFrom(data, "placements", "items", "tasks");
  const openCount = items.filter((item) => !["done", "completed", "published"].includes(item.status)).length;
  return `
    <div class="page-wrap">
      ${pageHeader("Размещение", "Скачайте одобренный ролик, опубликуйте на назначенной площадке и верните final URL.", `<span class="badge badge-info">${openCount} ждут действия</span>`)}
      ${alertMarkup("Final URL — это публичная ссылка на сам пост. Ссылка на карточку товара не завершает задачу.", "info")}
      <div class="placement-list" style="margin-top:18px">
        ${sectionBody(sectionState, items.length ? items.map(placementCard).join("") : emptyState("↗", "Нет задач на размещение", "Здесь появятся только одобренные ролики с назначенной площадкой."))}
      </div>
    </div>
  `;
}

function placementCard(item) {
  const complete = ["done", "completed", "published"].includes(item.status);
  return `
    <article class="card placement-card">
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
        <li>Использовать tracking link из задачи</li>
        <li>После публикации вернуть final URL</li>
      </ul>
      ${item.tracking_url ? `<p class="tiny"><strong>Tracking link:</strong> <a href="${safeExternalUrl(item.tracking_url)}" target="_blank" rel="noopener noreferrer">открыть безопасно</a></p>` : ""}
      ${complete ? alertMarkup(`Публикация подтверждена: ${item.final_url || "ссылка сохранена"}`, "success") : `
        <form class="inline-actions placement-form" data-placement-id="${escapeHtml(item.id)}" novalidate>
          <label class="field" style="flex:1; min-width:250px"><span>Final URL поста</span><input name="final_url" type="url" required inputmode="url" placeholder="https://…/ваш-пост" /></label>
          <button class="btn" type="submit" style="align-self:end">Подтвердить размещение</button>
        </form>
      `}
    </article>
  `;
}

function renderStatsSection(sectionState) {
  const data = sectionState.data || {};
  const summary = data.summary || data.metrics || {};
  const rows = listFrom(data, "publications", "items", "rows");
  const publicationOptions = listFrom(data, "publication_options", "placements", "published_placements");
  const cards = [
    ["Опубликовано", summary.published ?? summary.publications ?? 0, "роликов с final URL"],
    ["Просмотры", summary.views ?? 0, "последний подтверждённый снимок"],
    ["Переходы", summary.clicks ?? 0, "по tracking links"],
    ["CTR", formatPercent(summary.ctr ?? 0), "переходы / просмотры"],
  ];
  return `
    <div class="page-wrap">
      ${pageHeader("Статистика", "Только прослеживаемые публикации: задача → final URL → источник метрик → снимок.", `<button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="stats">Обновить</button>`)}
      <div class="metrics-grid">${cards.map(([label, value, hint]) => `
        <article class="card metric-card"><span class="metric-label">${label}</span><strong>${typeof value === "number" ? formatNumber(value) : value}</strong><small>${hint}</small></article>
      `).join("")}</div>
      <section class="card card-pad" style="margin-bottom:22px">
        <div class="split-grid" style="grid-template-columns:minmax(240px,.7fr) minmax(480px,1.3fr)">
          <div>
            <p class="eyebrow">Ручной снимок</p>
            <h2 style="font:600 1.5rem/1.2 Georgia,serif; margin:0 0 8px">Зафиксировать цифры на сейчас</h2>
            <p class="muted tiny">Введите <strong>накопительные итоги</strong> публикации, а не прирост за день. Например, если вчера было 900 просмотров, а сегодня 1200 — укажите 1200.</p>
            ${alertMarkup("Источник будет честно помечен как manual. Официальные API-подключения появятся позже и не перезапишут историю снимков.", "info")}
          </div>
          ${publicationOptions.length ? `
            <form id="manual-metric-form" class="form-stack" novalidate>
              <label class="field"><span>Опубликованный ролик *</span><select name="placement_id" required><option value="">Выберите публикацию</option>${publicationOptions.map((item) => `<option value="${escapeHtml(item.id || item.placement_id)}">${escapeHtml(item.title || item.sku || item.final_url || `Публикация #${item.id}`)}</option>`).join("")}</select></label>
              <div style="display:grid; grid-template-columns:repeat(2,1fr); gap:12px">
                <label class="field"><span>Просмотры *</span><input name="views" type="number" min="0" step="1" value="0" required /></label>
                <label class="field"><span>Переходы *</span><input name="clicks" type="number" min="0" step="1" value="0" required /></label>
                <label class="field"><span>Заказы *</span><input name="orders" type="number" min="0" step="1" value="0" required /></label>
                <label class="field"><span>Выручка, ₽ *</span><input name="revenue_rub" type="number" min="0" step="0.01" value="0" required /></label>
              </div>
              <label class="field"><span>Когда сняты цифры *</span><input name="observed_at" type="datetime-local" value="${datetimeLocalNow()}" required /></label>
              <button class="btn" type="submit">Сохранить накопительный снимок</button>
            </form>
          ` : alertMarkup("Сначала подтвердите хотя бы одну публикацию через final URL в разделе «Размещение».", "warning")}
        </div>
      </section>
      <section class="card">
        <div class="card-header"><div><p class="eyebrow">По публикациям</p><h2>Измеримые результаты</h2></div><span class="badge">API / CSV / ручной снимок</span></div>
        ${sectionBody(sectionState, rows.length ? statsTable(rows) : emptyState("◫", "Метрик пока нет", "После размещения сохраните final URL и добавьте первый подтверждённый снимок."))}
      </section>
    </div>
  `;
}

function statsTable(items) {
  return `<div class="table-wrap"><table class="data-table">
    <thead><tr><th>Публикация</th><th>Площадка</th><th>Просмотры</th><th>Переходы</th><th>Заказы</th><th>Выручка</th><th>Источник</th><th>Снимок</th></tr></thead>
    <tbody>${items.map((item) => `<tr>
      <td><strong>${escapeHtml(item.title || item.sku || `#${item.id}`)}</strong>${item.final_url ? `<br /><a class="tiny" href="${safeExternalUrl(item.final_url)}" target="_blank" rel="noopener noreferrer">Открыть пост</a>` : ""}</td>
      <td>${escapeHtml(item.platform || "—")}</td>
      <td>${formatNumber(item.views || 0)}</td>
      <td>${formatNumber(item.clicks || 0)}</td>
      <td>${formatNumber(item.orders || 0)}</td>
      <td>${formatMoney(item.revenue_minor || 0)}</td>
      <td><span class="badge">${escapeHtml(item.source || "не указан")}</span></td>
      <td>${formatDate(item.observed_at || item.captured_at || item.updated_at, true)}</td>
    </tr>`).join("")}</tbody>
  </table></div>`;
}

function renderPayoutsSection(sectionState) {
  const data = sectionState.data || {};
  const items = listFrom(data, "payouts", "items", "rows");
  const canManagePayouts = ["owner", "admin"].includes(state.bootstrap?.membership?.role);
  const totals = data.summary || {};
  const pendingMinor = totals.pending_minor ?? sumMinor(items.filter((i) => i.status === "pending"));
  const approvedMinor = totals.approved_minor ?? sumMinor(items.filter((i) => i.status === "approved"));
  const paidMinor = totals.paid_minor ?? sumMinor(items.filter((i) => i.status === "paid"));
  return `
    <div class="page-wrap">
      ${pageHeader(
        "Выплаты",
        canManagePayouts
          ? "Проверьте начисление команды, затем отдельно зафиксируйте решение и факт внешней оплаты."
          : "Здесь видны только ваши начисления. Решения принимает owner или admin; банковские реквизиты в кабинете не хранятся.",
        `<span class="badge">${canManagePayouts ? "Реестр команды" : "Личный реестр"}</span>`,
      )}
      <div class="metrics-grid" style="grid-template-columns:repeat(3,1fr)">
        ${[["Ожидает проверки", pendingMinor], ["Одобрено", approvedMinor], ["Выплачено", paidMinor]].map(([label, value]) => `<article class="card metric-card"><span class="metric-label">${label}</span><strong>${formatMoney(value)}</strong><small>по прослеживаемым задачам</small></article>`).join("")}
      </div>
      <section class="card">
        <div class="card-header"><div><p class="eyebrow">История</p><h2>Начисления и статусы</h2></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="payouts">Обновить</button></div>
        ${sectionBody(sectionState, items.length ? payoutsTable(items, canManagePayouts) : emptyState("₽", "Начислений пока нет", "Первое начисление появится после подтверждённой задачи и проверки результата."))}
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
    return `<span class="muted tiny">Ваше начисление должен проверить другой owner/admin</span>`;
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
        ${sectionBody(sectionState, items.length ? items.map(taskCard).join("") : emptyState("✓", "Нет назначенных задач", "Когда руководитель назначит работу, она появится здесь."))}
      </div>
    </div>
  `;
}

function taskCard(item) {
  const checklist = Array.isArray(item.checklist) ? item.checklist : item.checklist_json || [];
  return `
    <article class="card task-card">
      <div class="task-top">
        <div>
          <p class="eyebrow">${escapeHtml(humanTaskType(item.task_type))} · приоритет ${Number(item.priority || 3)}</p>
          <h3>${escapeHtml(item.title || `Задача #${item.id}`)}</h3>
          <p>${escapeHtml(item.instructions || "Следуйте чек-листу и сохраните результат в этой задаче.")}</p>
        </div>
        ${statusBadge(item.status || "todo")}
      </div>
      ${checklist.length ? `<ul class="checklist">${checklist.map((point) => `<li>${escapeHtml(typeof point === "string" ? point : point.label || point.title || "Шаг")}</li>`).join("")}</ul>` : ""}
      <div class="inline-actions">
        ${taskActionsMarkup(item)}
        ${item.due_at ? `<span class="tiny muted">Срок: ${formatDate(item.due_at, true)}</span>` : ""}
      </div>
    </article>
  `;
}

function taskActionsMarkup(item) {
  const taskId = escapeHtml(item.id || "");
  const status = String(item.status || "todo");
  const result = item.result && typeof item.result === "object" ? item.result : {};
  const activeRunwayReview = item.task_type === "video_review" &&
    result.provider === "runway" &&
    ["queued", "starting", "submitted", "processing"].includes(
      String(result.generation_status || ""),
    );
  if (activeRunwayReview) {
    return '<span class="muted tiny">Видео создаётся в Runway. Статус задачи изменится автоматически.</span>';
  }
  const manager = ["owner", "admin", "producer", "reviewer"].includes(
    state.bootstrap?.membership?.role,
  );
  const action = (nextStatus, label, secondary = false) =>
    `<button class="btn ${secondary ? "btn-secondary " : ""}btn-small" type="button" data-action="transition-task" data-task-id="${taskId}" data-status="${nextStatus}">${label}</button>`;

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

function renderMediaSection(sectionState) {
  const data = sectionState.data || {};
  const items = listFrom(data, "media", "items", "artifacts");
  return `
    <div class="page-wrap">
      ${pageHeader("Медиатека", "Приватные исходники и результаты разложены по папкам команды, пользователя и товара.", `<span class="badge badge-success">Приватный bucket</span>`)}
      <div class="split-grid" style="grid-template-columns:minmax(280px,.65fr) minmax(480px,1.35fr)">
        <section class="card card-pad">
          <p class="eyebrow">Добавить исходник</p>
          <h2 style="font:600 1.45rem/1.2 Georgia,serif; margin:0 0 8px">Точные фото или видео</h2>
          <p class="muted tiny">Файл попадёт в вашу закрытую папку. Максимум ${formatBytes(CONFIG.MAX_UPLOAD_BYTES)}.</p>
          <form id="media-upload-form" class="form-stack" novalidate>
            <div class="upload-zone" data-upload-zone>
              <span class="empty-icon" aria-hidden="true">⇧</span>
              <label for="media-file">Выбрать файл</label>
              <input id="media-file" name="file" type="file" accept="image/jpeg,image/png,image/webp,video/mp4" required />
              <small class="muted">JPG, PNG, WEBP или MP4</small>
              <strong id="selected-file-name" style="margin-top:8px"></strong>
            </div>
            <label class="field"><span>Тип материала</span><select name="kind"><option value="product_photo">Фото товара</option><option value="packshot">Packshot</option><option value="creator_reference">Референс креатора</option><option value="source_video">Исходное видео</option></select></label>
            <label class="acknowledgement"><input name="rights_confirmed" type="checkbox" required /><span>У команды есть право использовать этот материал.</span></label>
            <button class="btn btn-block" type="submit">Загрузить в приватную папку</button>
          </form>
        </section>
        <section>
          <div class="inline-actions" style="justify-content:space-between; margin-bottom:14px"><div><p class="eyebrow">Ваши файлы</p><h2 style="font:600 1.55rem/1.2 Georgia,serif; margin:0">${items.length} материалов</h2></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="media">Обновить</button></div>
          ${sectionBody(sectionState, items.length ? `<div class="media-grid">${items.map(mediaCard).join("")}</div>` : emptyState("▧", "Медиатека пуста", "Добавьте точные фото товара — после этого их можно выбрать в mock batch."))}
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
    else if (mime === "video/mp4") preview = `<video src="${url}" preload="metadata" controls></video>`;
  }
  return `
    <article class="card media-card">
      <div class="media-preview">${preview}</div>
      <div class="media-info">
        <strong title="${escapeHtml(item.original_filename || "Файл")}">${escapeHtml(item.original_filename || item.name || "Файл")}</strong>
        <small>${escapeHtml(item.kind || "материал")} · ${formatBytes(item.size_bytes || 0)}</small>
        <div class="inline-actions" style="margin-top:10px">${url !== "#" ? `<a class="btn btn-secondary btn-small" href="${url}" target="_blank" rel="noopener noreferrer">Открыть</a>` : ""}${statusBadge(item.status || "ready")}</div>
      </div>
    </article>
  `;
}

function renderFeedbackSection(sectionState) {
  const data = sectionState.data || {};
  const items = listFrom(data, "feedback", "items", "requests");
  return `
    <div class="page-wrap">
      ${pageHeader("Что добавить", "Опишите препятствие или идею. Запрос автоматически связан с вашим рабочим контекстом, но не включает секреты.", `<span class="badge">Обратная связь</span>`)}
      <div class="split-grid">
        <section class="card card-pad">
          <p class="eyebrow">Новый запрос</p>
          <h2 style="font:600 1.5rem/1.2 Georgia,serif; margin:0 0 8px">Что мешает выполнить работу?</h2>
          <form id="feedback-form" class="form-stack" style="margin-top:18px" novalidate>
            <div class="feedback-form-grid">
              <label class="field"><span>Тип</span><select name="category"><option value="interface">Интерфейс</option><option value="generation">Генерация</option><option value="quality">Качество</option><option value="funnel">Воронка / размещение</option><option value="social_data">Данные соцсетей</option><option value="payouts">Выплаты</option><option value="wb_aliases">Артикулы WB</option><option value="analytics">Аналитика</option><option value="training">Обучение</option><option value="other">Другое</option></select></label>
              <label class="field"><span>Раздел</span><select name="section">${visibleWorkspaceTabs().filter(([key]) => key !== "team").map(([key, label]) => `<option value="${key}">${label}</option>`).join("")}</select></label>
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
    return `<div class="page-wrap">${alertMarkup("Управление командой доступно только owner или admin.", "danger")}</div>`;
  }
  const members = listFrom(sectionState.data || {}, "members");
  return `
    <div class="page-wrap">
      ${pageHeader("Команда", "Пригласите креаторов по рабочей почте. Пароли и секреты в эту форму не вводятся.", `<span class="badge badge-info">До 50 человек</span>`)}
      ${alertMarkup("Каждый новый участник входит как trainee. Рабочие разделы откроются только после четырёх курсов и успешного экзамена из 12 сценариев.", "info")}
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
          <div class="card-header"><div><p class="eyebrow">Последний запуск</p><h2>Результаты доставки</h2></div></div>
          ${state.teamInviteResult ? teamInviteResultMarkup(state.teamInviteResult) : emptyState("◎", "Приглашений ещё не было", "После отправки здесь появится результат по каждому адресу.")}
        </section>
      </div>
      <section class="card" style="margin-top:22px">
        <div class="card-header"><div><p class="eyebrow">Доступ и результат</p><h2>Участники команды</h2></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="team">Обновить</button></div>
        ${sectionBody(sectionState, members.length ? teamMembersTable(members) : emptyState("◎", "В команде пока никого нет", "Отправьте приглашения выше — новые участники появятся после первого входа."))}
      </section>
    </div>
  `;
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
    invited: "Приглашение отправлено",
    already_exists: "Уже есть в Auth",
    rate_limited: "Лимит отправки",
    smtp_required: "Нужен SMTP",
    failed: "Не отправлено",
  };
  return `
    <div class="card-pad" style="padding-top:0">
      <div class="metrics-grid" style="grid-template-columns:repeat(3,1fr); margin-bottom:16px">
        <article class="metric-card"><span class="metric-label">Запрошено</span><strong>${formatNumber(result.requested ?? rows.length)}</strong></article>
        <article class="metric-card"><span class="metric-label">Отправлено</span><strong>${formatNumber(result.invited ?? 0)}</strong></article>
        <article class="metric-card"><span class="metric-label">Уже существуют</span><strong>${formatNumber(result.already_exists ?? 0)}</strong></article>
      </div>
      ${smtpRequired ? alertMarkup("Supabase просит настроить собственный SMTP. Приглашения со статусом «Нужен SMTP» не были доставлены.", "warning") : ""}
      ${rows.some((item) => item.status === "rate_limited") ? alertMarkup("Достигнут почтовый лимит Supabase. Не повторяйте весь список: позже отправьте только адреса со статусом «Лимит отправки».", "warning") : ""}
      <div class="table-wrap"><table class="data-table">
        <thead><tr><th>Email</th><th>Результат</th></tr></thead>
        <tbody>${rows.map((item) => `<tr><td>${escapeHtml(item.email || "—")}</td><td>${statusBadge(item.status || "failed")}<br /><small class="muted">${escapeHtml(statusLabels[item.status] || "Неизвестный результат")}</small></td></tr>`).join("")}</tbody>
      </table></div>
    </div>
  `;
}

function feedbackCard(item) {
  return `<article class="card feedback-card"><div class="feedback-top"><div><p class="eyebrow">${escapeHtml(item.category || "запрос")} · ${formatDate(item.created_at)}</p><h3>${escapeHtml(item.title || "Без заголовка")}</h3><p>${escapeHtml(item.details || item.description || "")}</p></div>${statusBadge(item.status || "new")}</div>${item.response ? alertMarkup(item.response, "success") : ""}</article>`;
}

function pageHeader(title, description, actions = "") {
  return `<header class="page-header"><div><p class="eyebrow">Рабочий кабинет</p><h1>${escapeHtml(title)}</h1><p>${escapeHtml(description)}</p></div>${actions ? `<div class="page-actions">${actions}</div>` : ""}</header>`;
}

function sectionBody(sectionState, readyMarkup) {
  if (sectionState.status === "loading" || sectionState.status === "idle") {
    return `<div class="skeleton-stack" aria-label="Загрузка"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>`;
  }
  if (sectionState.status === "error") {
    return `<div class="empty-state"><div class="empty-icon">!</div><h3>Не удалось загрузить раздел</h3><p>${escapeHtml(sectionState.error?.message || "Повторите попытку.")}</p></div>`;
  }
  return readyMarkup;
}

function emptyState(icon, title, message) {
  return `<div class="empty-state"><div class="empty-icon" aria-hidden="true">${icon}</div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p></div>`;
}

async function handleClick(event) {
  const control = event.target.closest("[data-action]");
  if (!control) return;
  const action = control.dataset.action;

  if (action === "reload-page") {
    window.location.reload();
    return;
  }

  if (action === "toggle-mobile-nav") {
    state.mobileNavOpen = !state.mobileNavOpen;
    render();
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

  if (action === "complete-course") {
    const checkbox = document.querySelector("#course-ack");
    if (!checkbox?.checked) {
      toast("Подтвердите, что прочитали все шаги.", "error");
      return;
    }
    control.disabled = true;
    try {
      const moduleCode = control.dataset.moduleCode;
      await state.api.completeModule(moduleCode);
      await track("course_completed", { module_code: moduleCode });
      await loadBootstrap();
      toast("Курс завершён и сохранён.", "success");
      navigate("/learn", true);
    } catch (error) {
      control.disabled = false;
      toast(error.message, "error");
    }
    return;
  }

  if (action === "refresh-section") {
    const section = control.dataset.section;
    if (state.sections[section]) {
      state.sections[section].status = "idle";
      render();
    }
    return;
  }

  if (action === "check-real-generation") {
    control.disabled = true;
    try {
      const result = await state.api.realGenerationStatus(control.dataset.jobId);
      const status = String(result?.job?.status || "processing").toLowerCase();
      const signedUrl = String(result?.signed_url || "");
      state.sections.generation.status = "idle";
      if (["succeeded", "completed"].includes(status) && signedUrl) {
        if (!isTrustedGenerationDownload(signedUrl)) throw new Error("Сервис вернул небезопасную ссылку на результат.");
        openExternalDownload(signedUrl);
        toast("Ролик готов. Открыта свежая защищённая ссылка.", "success");
      } else if (status === "failed") {
        toast("Runway сообщил об ошибке генерации. Обновите очередь для подробностей.", "error");
      } else {
        toast(`Текущий статус Runway: ${humanGenerationStatus(status)}.`, "info");
      }
      render();
    } catch (error) {
      control.disabled = false;
      toast(error.message, "error");
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
      toast(error.message, "error");
    }
    return;
  }

  if (action === "decide-payout") {
    if (!["owner", "admin"].includes(state.bootstrap?.membership?.role)) {
      toast("Решение по выплате доступно только owner или admin.", "error");
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
      toast(error.message, "error");
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
  else if (form.id === "exam-form") await submitExam(form);
  else if (form.id === "mock-batch-form") await submitGenerationBatch(form);
  else if (form.id === "manual-metric-form") await submitManualMetric(form);
  else if (form.id === "wb-alias-form") await submitWbAlias(form);
  else if (form.id === "media-upload-form") await submitMedia(form);
  else if (form.id === "feedback-form") await submitFeedback(form);
  else if (form.id === "team-invite-form") await submitTeamInvites(form);
  else if (form.classList.contains("placement-form")) await submitPlacement(form);
  else if (form.classList.contains("payout-reject-form")) await submitPayoutReject(form);
  else if (form.classList.contains("payout-paid-form")) await submitPayoutPaid(form);
}

function handleChange(event) {
  if (event.target.id === "course-ack") {
    const button = document.querySelector('[data-action="complete-course"]');
    if (button) button.disabled = !event.target.checked;
  }

  if (event.target.closest("#exam-form")) {
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

  const generationForm = event.target.closest("#mock-batch-form");
  if (generationForm && event.target.name === "generation_mode") {
    syncGenerationModeForm(generationForm);
  }
}

function handleDragOver(event) {
  const zone = event.target.closest("[data-upload-zone]");
  if (!zone) return;
  event.preventDefault();
  zone.classList.add("dragover");
}

function handleDragLeave(event) {
  const zone = event.target.closest("[data-upload-zone]");
  if (zone) zone.classList.remove("dragover");
}

function handleDrop(event) {
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
  showSelectedFile(file);
}

function showSelectedFile(file) {
  const target = document.querySelector("#selected-file-name");
  if (target) target.textContent = file ? `${file.name} · ${formatBytes(file.size)}` : "";
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
  const confirmationInput = form.elements.real_spend_confirmation;
  const submit = form.querySelector("#generation-submit");
  const countHint = form.querySelector("#generation-count-hint");
  const mediaHint = form.querySelector("#generation-media-hint");
  const price = form.querySelector("#real-generation-price");
  const note = form.querySelector("#real-generation-note");
  const confirmationCopy = form.querySelector("#real-generation-confirmation-copy");
  const briefHint = form.querySelector("#generation-brief-hint");

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
      : `Mock: от 1 до ${MAX_MOCK_BATCH_SIZE} вариантов.`;
  }
  if (mediaHint) {
    mediaHint.textContent = real
      ? "Для платного запуска выберите ровно один исходник."
      : "Для mock можно выбрать один или несколько исходников.";
  }
  if (price && sku) {
    price.textContent = `Платный запуск: ориентировочно ${sku.estimatedCredits} credits / $${sku.estimatedUsd}. Итог зависит от тарифа провайдера.`;
  }
  if (note && sku) {
    note.textContent = seedance
      ? "Runway создаёт аудио по текстовому запросу, но не гарантирует дословную русскую реплику. Проверьте результат перед публикацией."
      : "Этот режим создаёт видео без сгенерированной речи.";
  }
  if (confirmationCopy && sku) {
    confirmationCopy.textContent = `${sku.model} · ${sku.durationSeconds} секунд · ровно одно видео · около $${sku.estimatedUsd}`;
  }
  if (briefHint) {
    briefHint.textContent = seedance
      ? "Перед оплатой вставьте сценарий именно выбранного товара и проверьте дословную реплику."
      : "Для платного режима опишите один ролик без неподтверждённых обещаний.";
  }
  if (submit) {
    submit.textContent = real
      ? `Запустить 1 платное видео · около $${sku.estimatedUsd}`
      : "Подготовить dry-run batch";
  }
}

async function submitLogin(form) {
  const values = new FormData(form);
  const email = String(values.get("email") || "").trim();
  const password = String(values.get("password") || "");
  setFormBusy(form, true, "Проверяем…");
  try {
    const { data, error } = await state.supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    state.session = data.session;
    state.user = data.user;
    state.forcePassword = false;
    state.authPurpose = null;
    await loadBootstrap();
    await track("login_succeeded", { method: "password" });
    if (membershipLockDetails()) navigate("/access-locked", true);
    else if (hasWorkspaceAccess()) navigate("/workspace/generation", true);
    else navigate("/learn", true);
  } catch (error) {
    renderLogin(authErrorMessage(error));
  }
}

async function submitReset(form) {
  const email = String(new FormData(form).get("email") || "").trim();
  setFormBusy(form, true, "Отправляем…");
  try {
    const { error } = await withUiTimeout(
      state.supabase.auth.resetPasswordForEmail(email, {
        redirectTo: authRedirectUrl("recovery"),
      }),
      AUTH_REQUEST_TIMEOUT_MS,
      "Сервер восстановления не ответил за 15 секунд. Обновите страницу и повторите.",
    );
    if (error) throw error;
    renderResetRequest("Если адрес зарегистрирован, письмо уже отправлено. Проверьте также папку «Спам».");
  } catch (error) {
    toast(authErrorMessage(error), "error");
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
  if (password.length < 10) {
    renderSetPassword("Пароль должен содержать не меньше 10 символов.");
    return;
  }
  setFormBusy(form, true, "Сохраняем…");
  try {
    const { data, error } = await state.supabase.auth.updateUser({ password });
    if (error) throw error;
    state.user = data.user || state.user;
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

async function submitExam(form) {
  const questions = finalExamQuestions();
  const answers = {};
  for (const question of questions) {
    const selected = [
      ...form.querySelectorAll(`input[name="${CSS.escape(`answer_${question.code}`)}"]:checked`),
    ];
    if (!selected.length) {
      selectedQuestionCard(question.code)?.scrollIntoView({ behavior: "smooth", block: "center" });
      toast("Ответьте на все 12 вопросов.", "error");
      return;
    }
    answers[question.code] = selected.map((input) => input.value);
  }

  setFormBusy(form, true, "Проверяем на сервере…");
  try {
    const raw = await state.api.submitExam(answers);
    const source = raw?.result || raw?.data || raw || {};
    state.examResult = {
      passed: normalizeBoolean(source.passed),
      correctCount: Number(source.correct_count ?? source.correctCount ?? 0),
      total: Number(source.question_count ?? source.total ?? questions.length),
      score: normalizePercent(source.score_percent ?? source.score ?? 0),
      topics: Array.isArray(source.topics) ? source.topics : source.review_topics || [],
    };
    await track("exam_submitted", {
      passed: state.examResult.passed,
      score: state.examResult.score,
      attempt_number: state.bootstrap.training.exam.attemptCount + 1,
    });
    await loadBootstrap();
    if (hasWorkspaceAccess()) {
      toast("Экзамен сдан. Рабочий кабинет открыт.", "success");
      navigate("/workspace/generation", true);
    } else {
      state.route = { path: "/learn/exam", query: new URLSearchParams() };
      render();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  } catch (error) {
    await loadBootstrap();
    state.route = { path: "/learn/exam", query: new URLSearchParams() };
    render();
    toast(error.message, "error");
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

async function submitRealGeneration(form, values, mode) {
  if (!REAL_GENERATION_ENABLED) {
    toast("Платная генерация выключена в конфигурации портала.", "error");
    return;
  }
  const generationSku = realGenerationSku(mode);
  if (!generationSku) {
    toast("Выберите точный платный режим генерации.", "error");
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
    toast("Для Runway укажите одну главную мысль ролика.", "error");
    return;
  }
  if (values.get("real_spend_confirmation") !== generationSku.confirmation) {
    toast(`Подтвердите один платный запуск Runway около $${generationSku.estimatedUsd}.`, "error");
    return;
  }
  const payoutRub = canManageTeam() ? Number(values.get("payout_rub") || 0) : 0;
  if (!Number.isFinite(payoutRub) || payoutRub < 0 || payoutRub > 10_000 || !Number.isSafeInteger(Math.round(payoutRub * 100))) {
    toast("Вознаграждение должно быть от 0 до 10 000 ₽ за задачу.", "error");
    return;
  }

  const payload = {
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

  setFormBusy(form, true, `Запускаем 1 видео Runway · ${generationSku.durationSeconds} секунд…`);
  try {
    const result = await state.api.startRealGeneration(payload);
    if (!result?.job?.id) throw new Error("Runway принял запрос без номера задачи. Обновите очередь.");
    await track("real_generation_started", {
      provider: "runway",
      model: generationSku.model,
      duration_seconds: generationSku.durationSeconds,
      audio: generationSku.audio,
      estimated_credits: generationSku.estimatedCredits,
      format: payload.format,
      platform: payload.platform,
      has_media: true,
    });
    form.reset();
    syncGenerationModeForm(form);
    state.sections.generation.status = "idle";
    state.sections.placement.status = "idle";
    state.sections.tasks.status = "idle";
    toast(`Платный запуск принят: 1 видео Runway ${generationSku.model}, ${generationSku.durationSeconds} секунд, ориентировочно $${generationSku.estimatedUsd}.`, "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
    toast(error.message, "error");
  }
}

async function submitMockBatch(form, values = new FormData(form)) {
  if (!MOCK_GENERATION_ENABLED) {
    toast("Mock-режим выключен в конфигурации портала.", "error");
    return;
  }
  const count = Number(values.get("count"));
  const mediaIds = values.getAll("media_id").map(String);
  if (!Number.isInteger(count) || count < 1 || count > MAX_MOCK_BATCH_SIZE) {
    toast(`Укажите от 1 до ${MAX_MOCK_BATCH_SIZE} вариантов.`, "error");
    return;
  }
  if (!mediaIds.length) {
    toast("Выберите хотя бы одно точное фото товара или packshot из Медиатеки.", "error");
    return;
  }
  const payoutRub = canManageTeam() ? Number(values.get("payout_rub") || 0) : 0;
  if (!Number.isFinite(payoutRub) || payoutRub < 0 || payoutRub > 10_000 || !Number.isSafeInteger(Math.round(payoutRub * 100))) {
    toast("Вознаграждение должно быть от 0 до 10 000 ₽ за задачу.", "error");
    return;
  }
  setFormBusy(form, true, "Создаём mock batch…");
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
    form.reset();
    syncGenerationModeForm(form);
    state.sections.generation.status = "idle";
    state.sections.placement.status = "idle";
    state.sections.tasks.status = "idle";
    toast(`Dry-run batch на ${count} вариантов создан. Задачи и размещение готовы; платный ИИ не вызывался.`, "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
    toast(error.message, "error");
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
    state.sections.stats.status = "idle";
    toast("Накопительный снимок метрик сохранён с источником manual.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
    toast(error.message, "error");
  }
}

async function submitWbAlias(form) {
  if (!["owner", "admin", "producer"].includes(state.bootstrap?.membership?.role)) {
    toast("Изменять связи артикулов может owner, admin или producer.", "error");
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
    form.reset();
    state.sections.generation.status = "idle";
    state.sections.stats.status = "idle";
    toast("Связь артикулов добавлена. Исторические записи не перезаписаны.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
    toast(error.message, "error");
  }
}

async function submitPayoutReject(form) {
  if (!["owner", "admin"].includes(state.bootstrap?.membership?.role)) {
    toast("Решение по выплате доступно только owner или admin.", "error");
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
    state.sections.payouts.status = "idle";
    toast("Начисление отклонено, причина сохранена.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
    toast(error.message, "error");
  }
}

async function submitPayoutPaid(form) {
  if (!["owner", "admin"].includes(state.bootstrap?.membership?.role)) {
    toast("Факт выплаты может подтвердить только owner или admin.", "error");
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
    state.sections.payouts.status = "idle";
    toast("Внешняя оплата подтверждена и добавлена в реестр.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
    toast(error.message, "error");
  }
}

async function submitPlacement(form) {
  const finalUrl = String(new FormData(form).get("final_url") || "").trim();
  if (!isHttpsUrl(finalUrl)) {
    toast("Введите полный публичный HTTPS URL поста.", "error");
    return;
  }
  setFormBusy(form, true, "Проверяем ссылку…");
  try {
    const taskId = form.dataset.placementId;
    await state.api.confirmPlacement(taskId, finalUrl);
    await track("placement_confirmed", { task_id: String(taskId), hostname: new URL(finalUrl).hostname });
    state.sections.placement.status = "idle";
    state.sections.stats.status = "idle";
    state.sections.payouts.status = "idle";
    toast("Final URL сохранён. Цикл публикации подтверждён.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
    toast(error.message, "error");
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
    form.reset();
    state.sections.feedback.status = "idle";
    toast("Запрос отправлен. Спасибо — он уже в общей очереди.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
    toast(error.message, "error");
  }
}

async function submitTeamInvites(form) {
  if (!canManageTeam() || !hasWorkspaceAccess()) {
    toast("Приглашать команду может только сертифицированный owner или admin.", "error");
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
    const { data, error } = await state.supabase.functions.invoke("creator-invite", {
      body: { emails },
    });
    if (error) throw await normalizeInviteFunctionError(error);
    if (!data || !Array.isArray(data.results)) {
      throw new Error("Supabase не вернул результаты приглашений.");
    }
    state.teamInviteResult = data;
    state.sections.team.status = "idle";
    await track("team_invites_completed", {
      requested: Number(data.requested ?? emails.length),
      invited: Number(data.invited ?? 0),
      already_exists: Number(data.already_exists ?? 0),
      failed: Number(data.failed ?? 0),
    });
    toast(
      Number(data.invited || 0) > 0
        ? `Отправлено приглашений: ${Number(data.invited)}.`
        : "Запуск завершён. Проверьте статусы справа.",
      Number(data.failed || 0) > 0 ? "info" : "success",
    );
    render();
  } catch (error) {
    setFormBusy(form, false);
    toast(error.message, "error");
  }
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
    workspace_unavailable: "Рабочая команда Supabase пока недоступна.",
    final_exam_required: "Сначала завершите обучение и сдайте итоговый экзамен.",
    team_management_forbidden: "Приглашать участников может только owner или admin.",
    origin_not_allowed: "Этот адрес приложения не разрешён для приглашений.",
    request_too_large: "Список приглашений слишком большой.",
  };
  return new Error(messages[code] || authErrorMessage(error));
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

  setFormBusy(form, true, "Шифруем маршрут и загружаем…");
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
        kind: String(values.get("kind") || "product_photo"),
        rights_confirmed: values.get("rights_confirmed") === "on",
      });
    } catch (registrationError) {
      await state.api.removePrivateObject(objectKey).catch(() => {});
      throw registrationError;
    }
    await track("media_uploaded", { kind: String(values.get("kind")), mime_type: file.type, size_bytes: file.size });
    form.reset();
    showSelectedFile(null);
    state.sections.media.status = "idle";
    state.sections.generation.status = "idle";
    toast("Файл сохранён в приватной папке.", "success");
    render();
  } catch (error) {
    setFormBusy(form, false);
    toast(error.message, "error");
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
  app.innerHTML = `
    <main id="main-content" class="setup-screen" tabindex="-1">
      <section class="card setup-card">
        <div class="boot-mark" aria-hidden="true">A</div>
        <p class="eyebrow">Одноразовая облачная настройка</p>
        <h1 style="font:600 2.4rem/1.1 Georgia,serif; margin:8px 0">Подключите публичный ключ Supabase</h1>
        <p class="muted">Интерфейс уже готов, но безопасно не запускается с пустой конфигурацией.</p>
        ${problems.map((problem) => alertMarkup(problem, "warning")).join("")}
        <ol>
          <li>Откройте Supabase → Settings → API Keys.</li>
          <li>Скопируйте только <strong>Publishable key</strong>, начинающийся с <code>sb_publishable_</code>.</li>
          <li>Вставьте его в <code>web/app/config.js</code> вместо placeholder.</li>
          <li>Никогда не используйте здесь Secret key или пароль базы.</li>
        </ol>
        <p class="tiny muted">Publishable key виден браузеру по замыслу Supabase. Доступ к данным ограничивают Auth, RLS и узкие RPC.</p>
      </section>
    </main>
  `;
}

function renderFatal(error) {
  app.innerHTML = `
    <main id="main-content" class="error-page" tabindex="-1">
      <div class="boot-mark" aria-hidden="true">!</div>
      <p class="eyebrow">Ошибка запуска</p>
      <h1>Интерфейс не загрузился</h1>
      <p class="muted">${escapeHtml(error?.message || "Обновите страницу или обратитесь к администратору.")}</p>
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
    render();
  } else if (window.location.hash === hash) {
    state.route = parseRoute();
    render();
  } else {
    window.location.hash = normalized;
  }
}

function clearAuthenticatedState() {
  state.session = null;
  state.user = null;
  state.bootstrap = null;
  state.bootstrapStatus = "idle";
  state.bootstrapError = null;
  state.forcePassword = false;
  state.authPurpose = null;
  state.examResult = null;
  state.teamInviteResult = null;
  for (const section of Object.values(state.sections)) {
    section.status = "idle";
    section.data = null;
    section.error = null;
  }
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
  if (normalized.includes("invalid login credentials")) return "Почта или пароль не совпали. Проверьте раскладку и попробуйте ещё раз.";
  if (normalized.includes("email not confirmed")) return "Сначала подтвердите почту по ссылке из приглашения.";
  if (normalized.includes("expired") || normalized.includes("otp")) return "Ссылка устарела или уже использована. Запросите новую.";
  if (normalized.includes("rate limit")) return "Слишком много попыток. Подождите несколько минут.";
  return raw;
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
    owner: "Владелец",
    admin: "Администратор",
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
    mock_generation: "Подготовка mock-пакета",
    video_review: "Проверка качества",
    general: "Общая задача",
    create_video: "Создание ролика",
    review_video: "Проверка качества",
    placement: "Размещение",
    metrics: "Метрики",
    fix: "Исправление",
  }[type] || type || "Задача";
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
    invited: "Отправлено",
    already_exists: "Уже существует",
    rate_limited: "Лимит",
    smtp_required: "Нужен SMTP",
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
    succeeded: "готово",
    completed: "готово",
    failed: "ошибка",
  }[status] || status || "неизвестно";
}

function alertMarkup(message, type = "info") {
  const icon = { danger: "!", warning: "!", success: "✓", info: "i" }[type] || "i";
  return `<div class="alert alert-${type}" role="${type === "danger" ? "alert" : "status"}"><strong aria-hidden="true">${icon}</strong><span>${escapeHtml(message)}</span></div>`;
}

function setFormBusy(form, busy, label = "Подождите…") {
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
    timerId = window.setTimeout(() => reject(new Error(message)), timeoutMs);
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
