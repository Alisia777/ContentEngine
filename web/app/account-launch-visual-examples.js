/**
 * Code-native visual walkthroughs for the account launch lessons.
 *
 * The screens are deliberately schematic. They teach the purpose of a control
 * without promising its exact label, position or availability in a platform's
 * current interface.
 */

export const ACCOUNT_VISUAL_STEP_ORDER = Object.freeze([
  "access",
  "profile",
  "upload",
  "disclosure",
  "link",
]);

const STEP_META = Object.freeze({
  access: Object.freeze({ number: "01", short: "Доступ", title: "Регистрация и защита" }),
  profile: Object.freeze({ number: "02", short: "Профиль", title: "Оформление профиля" }),
  upload: Object.freeze({ number: "03", short: "Загрузка", title: "Загрузка ролика" }),
  disclosure: Object.freeze({ number: "04", short: "Раскрытие", title: "Реклама и ИИ" }),
  link: Object.freeze({ number: "05", short: "Ссылка", title: "Копирование ссылки" }),
});

const PLATFORM_CONFIG = Object.freeze({
  instagram: Object.freeze({
    slug: "instagram",
    name: "Instagram",
    format: "Reels",
    accountSubject: "рабочий профиль",
    uploadArea: "зону создания Reels",
    draftLabel: "черновик Reels",
    commercialLabel: "Коммерческая связь / branded content",
    syntheticLabel: "Раскрытие реалистично изменённого или синтетического контента — если этого требуют текущие правила",
    linkLabel: "Ссылка на опубликованный Reel",
  }),
  youtube: Object.freeze({
    slug: "youtube",
    name: "YouTube",
    format: "Shorts",
    accountSubject: "рабочую учётную запись и канал",
    uploadArea: "зону создания Shorts или загрузки в Studio",
    draftLabel: "черновик Short",
    commercialLabel: "Paid promotion — когда есть оплата или иная выгода",
    syntheticLabel: "Использование ИИ / изменённый или синтетический контент (AI use / altered or synthetic content)",
    linkLabel: "Ссылка на опубликованный Short",
  }),
  vk: Object.freeze({
    slug: "vk",
    name: "VK",
    format: "VK Клипы",
    accountSubject: "рабочий профиль или сообщество",
    uploadArea: "зону создания VK Клипа",
    draftLabel: "черновик VK Клипа",
    commercialLabel: "Реклама / коммерческая публикация — по решению ответственного сотрудника",
    syntheticLabel: "Раскрытие изменённого или синтетического контента — если его требуют актуальные правила и интерфейс",
    linkLabel: "Ссылка на опубликованный VK Клип",
  }),
});

function visualStep(config, step) {
  if (step === "access") {
    return {
      ...STEP_META.access,
      purpose: `Создайте ${config.accountSubject}, заранее назначьте владельца и подготовьте восстановление доступа.`,
      screen: {
        eyebrow: `${config.name} · учебная схема`,
        title: "Доступ и защита",
        items: [
          { kind: "field", label: "Владелец", value: "рабочая команда" },
          { kind: "toggle", label: "Двухэтапная защита", value: "включить" },
          { kind: "note", label: "Резервный вход", value: "коды и контакт сохранены" },
        ],
      },
      hotspots: [
        { label: "Владелец", body: "До регистрации договоритесь, кто хранит основной доступ и кто подтверждает восстановление. Не используйте временный или чужой адрес." },
        { label: "Двухэтапная защита", body: "Включите доступный на площадке второй фактор. Сохраните способ входа, который не зависит от одного телефона исполнителя." },
        { label: "Восстановление", body: "Проверьте резервный контакт и сохраните коды у владельца команды. Пароли и коды в портал не загружаются." },
      ],
      completion: "Готово, когда понятны владелец, второй фактор и безопасный маршрут восстановления.",
    };
  }

  if (step === "profile") {
    return {
      ...STEP_META.profile,
      purpose: `Оформите ${config.accountSubject} так, чтобы человек сразу понимал, чей это аккаунт и о чём будут ${config.format}.`,
      screen: {
        eyebrow: `${config.name} · учебная схема`,
        title: "Карточка профиля",
        items: [
          { kind: "avatar", label: "Фото и имя", value: "один проект" },
          { kind: "field", label: "Описание", value: "кто вы и о чём контент" },
          { kind: "note", label: "Рабочий контакт", value: "если он нужен проекту" },
        ],
      },
      hotspots: [
        { label: "Имя и изображение", body: "Используйте согласованные имя, аватар и оформление одного проекта. Не копируйте чужой бренд и не изображайте официальный аккаунт без права." },
        { label: "Описание", body: "Коротко объясните тему аккаунта обычным языком. Не добавляйте обещаний результата, которых ролики и товар не подтверждают." },
        { label: "Проверка целиком", body: "Посмотрите профиль как новый зритель: имя, описание и контакт не должны противоречить друг другу." },
      ],
      completion: "Готово, когда профиль узнаваем, не имитирует чужой аккаунт и не содержит неподтверждённых обещаний.",
    };
  }

  if (step === "upload") {
    return {
      ...STEP_META.upload,
      purpose: `Найдите ${config.uploadArea}, выберите только назначенный вертикальный файл и сначала проверьте его как черновик.`,
      screen: {
        eyebrow: `${config.name} · ${config.format}`,
        title: "Подготовка публикации",
        items: [
          { kind: "media", label: "Вертикальный файл", value: "кадр 9:16" },
          { kind: "toggle", label: "Кадр и звук", value: "просмотрены целиком" },
          { kind: "action", label: "Безопасный следующий шаг", value: `сохранить ${config.draftLabel}` },
        ],
      },
      hotspots: [
        { label: "Назначенный файл", body: "Сверьте товар, упаковку и версию ролика с задачей. Похожий товар или случайный файл использовать нельзя." },
        { label: "Просмотр", body: "Проверьте первый и последний кадр, обрезку, читаемость, звук и отсутствие чужих личных данных." },
        { label: "Черновик", body: "Если хотя бы один пункт не подтверждён, сохраните черновик и остановитесь. Название кнопки и место могут меняться." },
      ],
      completion: "Готово, когда весь ролик просмотрен, товар совпадает с задачей, а спорная версия не опубликована.",
    };
  }

  if (step === "disclosure") {
    return {
      ...STEP_META.disclosure,
      purpose: "Перед публикацией проверьте коммерческую связь и реалистично изменённые сцены. Этот шаг не предназначен для обхода маркировки.",
      screen: {
        eyebrow: `${config.name} · проверка перед публикацией`,
        title: "Раскрытие контекста",
        items: [
          { kind: "warning", label: "Есть оплата, товар, скидка или задание бренда?", value: "остановиться и проверить" },
          { kind: "field", label: "Коммерческая связь", value: config.commercialLabel },
          { kind: "field", label: "ИИ / изменение", value: config.syntheticLabel },
        ],
      },
      hotspots: [
        { label: "Сначала факты", body: "Зафиксируйте оплату, подарок, промокод, партнёрскую ссылку, обязательные тезисы и контроль бренда. Не меняйте формулировки, чтобы скрыть эти признаки." },
        { label: "Коммерческое раскрытие", body: `Ищите настройку по смыслу: «${config.commercialLabel}». При сомнении не публикуйте и передайте задачу ответственному сотруднику.` },
        { label: "Изменённый или ИИ-контент", body: `Проверьте требование по смыслу: «${config.syntheticLabel}». Расположение и название настройки могут измениться.` },
      ],
      completion: "Готово только после внутреннего решения по рекламе и требуемым раскрытиям конкретного ролика.",
    };
  }

  return {
    ...STEP_META.link,
    purpose: "После публикации откройте сам ролик, проверьте его воспроизведение и скопируйте ссылку именно на эту публикацию.",
    screen: {
      eyebrow: `${config.name} · ${config.format}`,
      title: "Проверка результата",
      items: [
        { kind: "media", label: "Опубликованный ролик", value: "открывается и играет" },
        { kind: "action", label: "Действие по смыслу", value: "поделиться / скопировать ссылку" },
        { kind: "link", label: config.linkLabel, value: "вставить в назначенную задачу" },
      ],
    },
    hotspots: [
      { label: "Откройте публикацию", body: "Не копируйте адрес редактора, черновика, профиля или ленты. Сначала откройте страницу опубликованного ролика." },
      { label: "Скопируйте ссылку", body: "Найдите действие «поделиться» или «скопировать ссылку» по смыслу: точное название и расположение могут отличаться." },
      { label: "Проверьте и сохраните", body: "Откройте ссылку ещё раз, убедитесь, что это нужный ролик, затем вставьте её только в назначенную задачу портала." },
    ],
    completion: "Готово, когда ссылка повторно открывает нужный опубликованный ролик и сохранена в правильной задаче.",
  };
}

function buildPlatformGuide(config) {
  return {
    slug: config.slug,
    name: config.name,
    format: config.format,
    interfaceNote: "Учебная схема, а не точная копия интерфейса. Названия и расположение элементов меняются: ищите действие по смыслу и сверяйтесь с актуальной официальной справкой площадки.",
    steps: Object.fromEntries(ACCOUNT_VISUAL_STEP_ORDER.map((step) => [step, visualStep(config, step)])),
  };
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.values(value).forEach(deepFreeze);
  return Object.freeze(value);
}

export const ACCOUNT_LAUNCH_VISUAL_EXAMPLES = deepFreeze(
  Object.fromEntries(Object.values(PLATFORM_CONFIG).map((config) => [config.slug, buildPlatformGuide(config)])),
);

let visualInstanceSequence = 0;

function normalizeInstanceId(value) {
  const normalized = String(value || "")
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/gu, "-")
    .replace(/^-+|-+$/gu, "")
    .slice(0, 64);
  if (normalized) return normalized;
  visualInstanceSequence += 1;
  return `account-visual-${visualInstanceSequence}`;
}

export function normalizeAccountVisualState(value = {}) {
  const platformIsValid = Object.hasOwn(ACCOUNT_LAUNCH_VISUAL_EXAMPLES, value.platform);
  const stepIsValid = ACCOUNT_VISUAL_STEP_ORDER.includes(value.step);
  const platform = platformIsValid
    ? String(value.platform)
    : "instagram";
  const step = stepIsValid ? String(value.step) : "access";
  const hotspotCount = ACCOUNT_LAUNCH_VISUAL_EXAMPLES[platform].steps[step].hotspots.length;
  const rawHotspot = Number(value.hotspot);
  const hotspot = platformIsValid && stepIsValid && Number.isInteger(rawHotspot)
    ? Math.min(Math.max(0, rawHotspot), Math.max(0, hotspotCount - 1))
    : 0;
  return Object.freeze({ platform, step, hotspot });
}

export function accountVisualStateAfter(current, action = {}) {
  const state = normalizeAccountVisualState(current);
  if (action.type === "select-platform" && Object.hasOwn(ACCOUNT_LAUNCH_VISUAL_EXAMPLES, action.platform)) {
    return normalizeAccountVisualState({ platform: action.platform, step: "access", hotspot: 0 });
  }
  if (action.type === "select-step" && ACCOUNT_VISUAL_STEP_ORDER.includes(action.step)) {
    return normalizeAccountVisualState({ ...state, step: action.step, hotspot: 0 });
  }
  if (action.type === "select-hotspot") {
    return normalizeAccountVisualState({ ...state, hotspot: Number(action.hotspot) });
  }
  if (action.type === "move-step") {
    const currentIndex = ACCOUNT_VISUAL_STEP_ORDER.indexOf(state.step);
    const delta = Number(action.delta) < 0 ? -1 : 1;
    const nextIndex = Math.min(ACCOUNT_VISUAL_STEP_ORDER.length - 1, Math.max(0, currentIndex + delta));
    return normalizeAccountVisualState({ ...state, step: ACCOUNT_VISUAL_STEP_ORDER[nextIndex], hotspot: 0 });
  }
  return state;
}

export function accountLaunchVisualExamplesMarkup(options = {}) {
  const state = normalizeAccountVisualState({
    platform: options.platform,
    step: options.step,
    hotspot: options.hotspot,
  });
  const instanceId = normalizeInstanceId(options.instanceId);
  const lockPlatform = options.lockPlatform === true;
  const guide = ACCOUNT_LAUNCH_VISUAL_EXAMPLES[state.platform];
  const step = guide.steps[state.step];
  const stepIndex = ACCOUNT_VISUAL_STEP_ORDER.indexOf(state.step);
  const selectedHotspot = step.hotspots[state.hotspot];

  return `
    <section class="account-visual-examples" data-account-visual-examples data-av-instance="${escapeHtml(instanceId)}" data-av-platform-current="${escapeHtml(state.platform)}" data-av-platform-locked="${lockPlatform}" data-av-step-current="${escapeHtml(state.step)}" data-av-hotspot-current="${state.hotspot}" aria-labelledby="${escapeHtml(instanceId)}-title">
      <header class="account-visual-header">
        <p class="account-visual-eyebrow">Наглядная репетиция · без чужих скриншотов</p>
        <h2 id="${escapeHtml(instanceId)}-title">Пять действий до проверенной ссылки</h2>
        <p>${escapeHtml(guide.interfaceNote)}</p>
      </header>

      ${lockPlatform
        ? `<p class="account-visual-platform-lock"><span>Площадка урока</span><strong>${escapeHtml(guide.name)} · ${escapeHtml(guide.format)}</strong></p>`
        : `<div class="account-visual-platforms" role="group" aria-label="Выберите площадку">
            ${Object.values(ACCOUNT_LAUNCH_VISUAL_EXAMPLES).map((platform) => `
              <button class="account-visual-platform" type="button" data-av-platform="${escapeHtml(platform.slug)}" aria-pressed="${platform.slug === state.platform}">
                <span>${escapeHtml(platform.name)}</span><small>${escapeHtml(platform.format)}</small>
              </button>
            `).join("")}
          </div>`}

      <ol class="account-visual-steps" aria-label="Шаги публикации">
        ${ACCOUNT_VISUAL_STEP_ORDER.map((stepCode) => {
          const meta = STEP_META[stepCode];
          const current = stepCode === state.step;
          return `<li><button type="button" data-av-step="${escapeHtml(stepCode)}" ${current ? 'aria-current="step"' : ""}><span>${escapeHtml(meta.number)}</span><strong>${escapeHtml(meta.short)}</strong></button></li>`;
        }).join("")}
      </ol>

      <article class="account-visual-stage" aria-labelledby="${escapeHtml(instanceId)}-step-title">
        <div class="account-visual-stage-head">
          <div><p class="account-visual-eyebrow">Шаг ${stepIndex + 1} из ${ACCOUNT_VISUAL_STEP_ORDER.length} · ${escapeHtml(guide.name)}</p><h3 id="${escapeHtml(instanceId)}-step-title">${escapeHtml(step.title)}</h3></div>
          <p>${escapeHtml(step.purpose)}</p>
        </div>

        <div class="account-visual-layout">
          <div class="account-visual-pseudo-wrap">
            <div class="account-visual-pseudo-screen" role="group" aria-label="Учебный псевдоэкран: ${escapeHtml(step.title)} для ${escapeHtml(guide.name)}">
              <div class="account-visual-screen-top" aria-hidden="true"><span></span><span></span><span></span></div>
              <div class="account-visual-screen-heading"><small>${escapeHtml(step.screen.eyebrow)}</small><strong>${escapeHtml(step.screen.title)}</strong></div>
              <div class="account-visual-screen-items">
                ${step.screen.items.map(screenItemMarkup).join("")}
              </div>
              <p class="account-visual-screen-note">Схема показывает смысл действия, а не точное расположение кнопки.</p>
              ${step.hotspots.map((hotspot, index) => hotspotMarkup(instanceId, hotspot, index, state.hotspot)).join("")}
            </div>
          </div>

          <aside class="account-visual-captions" aria-labelledby="${escapeHtml(instanceId)}-captions-title">
            <h4 id="${escapeHtml(instanceId)}-captions-title">Что означает каждая метка</h4>
            <ol>
              ${step.hotspots.map((hotspot, index) => `
                <li id="${escapeHtml(instanceId)}-caption-${index}" class="${index === state.hotspot ? "is-selected" : ""}">
                  <span aria-hidden="true">${index + 1}</span><div><strong>${escapeHtml(hotspot.label)}</strong><p>${escapeHtml(hotspot.body)}</p></div>
                </li>
              `).join("")}
            </ol>
            <div id="${escapeHtml(instanceId)}-detail" class="account-visual-selected-detail" role="status" aria-live="polite" aria-atomic="true">
              <small>Выбрана метка ${state.hotspot + 1}</small><strong>${escapeHtml(selectedHotspot.label)}</strong><span>${escapeHtml(selectedHotspot.body)}</span>
            </div>
            <p class="account-visual-completion"><strong>Проверка шага:</strong> ${escapeHtml(step.completion)}</p>
            <div class="account-visual-actions">
              <button type="button" data-av-move="previous" ${stepIndex === 0 ? "disabled" : ""}>← Назад</button>
              <button type="button" data-av-move="next" ${stepIndex === ACCOUNT_VISUAL_STEP_ORDER.length - 1 ? "disabled" : ""}>Дальше →</button>
            </div>
          </aside>
        </div>
      </article>
    </section>
  `;
}

export function mountAccountLaunchVisualExamples(container, options = {}) {
  if (!container || typeof container.addEventListener !== "function" || typeof container.querySelector !== "function") {
    throw new TypeError("A DOM container is required to mount account launch visual examples.");
  }

  const instanceId = normalizeInstanceId(options.instanceId);
  const lockPlatform = options.lockPlatform === true;
  let state = normalizeAccountVisualState(options);
  let destroyed = false;

  const render = (focusSelector = "") => {
    if (destroyed) return;
    container.innerHTML = accountLaunchVisualExamplesMarkup({ ...state, instanceId, lockPlatform });
    if (!focusSelector) return;
    queueMicrotask(() => container.querySelector(focusSelector)?.focus());
  };

  const handleClick = (event) => {
    const control = event.target?.closest?.("[data-av-platform], [data-av-step], [data-av-hotspot], [data-av-move]");
    if (!control || !container.contains(control)) return;

    let action = null;
    let focusSelector = "";
    if (control.dataset.avPlatform) {
      if (lockPlatform) return;
      action = { type: "select-platform", platform: control.dataset.avPlatform };
      focusSelector = `[data-av-platform="${cssAttributeValue(control.dataset.avPlatform)}"]`;
    } else if (control.dataset.avStep) {
      action = { type: "select-step", step: control.dataset.avStep };
      focusSelector = `[data-av-step="${cssAttributeValue(control.dataset.avStep)}"]`;
    } else if (control.dataset.avHotspot !== undefined) {
      action = { type: "select-hotspot", hotspot: Number(control.dataset.avHotspot) };
      focusSelector = `[data-av-hotspot="${cssAttributeValue(control.dataset.avHotspot)}"]`;
    } else if (control.dataset.avMove) {
      action = { type: "move-step", delta: control.dataset.avMove === "previous" ? -1 : 1 };
    }
    if (!action) return;

    state = accountVisualStateAfter(state, action);
    if (action.type === "move-step") focusSelector = `[data-av-step="${cssAttributeValue(state.step)}"]`;
    render(focusSelector);
  };

  container.addEventListener("click", handleClick);
  render();

  return Object.freeze({
    getState: () => state,
    setState: (nextState) => {
      state = normalizeAccountVisualState(nextState);
      render();
      return state;
    },
    destroy: () => {
      if (destroyed) return;
      destroyed = true;
      container.removeEventListener("click", handleClick);
    },
  });
}

function screenItemMarkup(item) {
  return `
    <div class="account-visual-screen-item account-visual-screen-${escapeHtml(item.kind)}">
      ${item.kind === "media" ? '<span class="account-visual-media-frame" aria-hidden="true">9:16</span>' : ""}
      ${item.kind === "avatar" ? '<span class="account-visual-avatar" aria-hidden="true">A</span>' : ""}
      <div><small>${escapeHtml(item.label)}</small><strong>${escapeHtml(item.value)}</strong></div>
      ${item.kind === "toggle" ? '<span class="account-visual-toggle" aria-hidden="true">✓</span>' : ""}
    </div>
  `;
}

function hotspotMarkup(instanceId, hotspot, index, selectedIndex) {
  return `
    <button class="account-visual-hotspot account-visual-hotspot-${index + 1}" type="button" data-av-hotspot="${index}" aria-label="Метка ${index + 1}: ${escapeHtml(hotspot.label)}" aria-describedby="${escapeHtml(instanceId)}-caption-${index}" aria-controls="${escapeHtml(instanceId)}-detail" aria-pressed="${index === selectedIndex}">${index + 1}</button>
  `;
}

function cssAttributeValue(value) {
  return String(value ?? "").replace(/["\\]/gu, "\\$&");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
