import {
  ACCOUNT_LAUNCH_GUIDES,
  ADVERTISING_DECISION_STEPS,
  accountLaunchGuide,
} from "./account-launch-guides.js?v=20260716.1";

export const ACCOUNT_LAUNCH_PATH = "/learn/accounts";

export function accountLaunchSlugFromPath(path) {
  const normalized = String(path || "").replace(/\/+$/u, "");
  if (normalized === ACCOUNT_LAUNCH_PATH) return "";
  const match = normalized.match(/^\/learn\/accounts\/(instagram|youtube|vk)$/u);
  return match?.[1] || null;
}

export function accountLaunchCenterMarkup() {
  const guides = Object.values(ACCOUNT_LAUNCH_GUIDES);
  return `
    <section class="account-center-hero">
      <div>
        <p class="eyebrow">Для полного новичка</p>
        <h1>Запустите рабочий аккаунт без догадок</h1>
        <p>Выберите площадку и пройдите маршрут от регистрации и защиты входа до первой проверенной публикации. Здесь нет «секретных лимитов» и способов обходить маркировку.</p>
      </div>
      <aside class="account-center-promise" aria-label="Что даст центр запуска">
        <strong>После маршрута</strong>
        <span>аккаунт оформлен и защищён</span>
        <span>понятны рискованные действия</span>
        <span>есть чек-лист первой публикации</span>
      </aside>
    </section>
    <div class="account-platform-grid">
      ${guides.map((guide, index) => `
        <a class="account-platform-card account-platform-${escapeHtml(guide.slug)}" href="#${ACCOUNT_LAUNCH_PATH}/${escapeHtml(guide.slug)}">
          <span class="account-platform-number">0${index + 1}</span>
          <span class="account-platform-format">${escapeHtml(guide.format)}</span>
          <h2>${escapeHtml(guide.name)}</h2>
          <p>${escapeHtml(guide.summary)}</p>
          <strong>Открыть маршрут <span aria-hidden="true">→</span></strong>
        </a>
      `).join("")}
    </div>
    ${sharedSafetyNotice()}
  `;
}

export function accountLaunchGuideMarkup(slug, savedChecks = []) {
  const guide = accountLaunchGuide(slug);
  if (!guide) return "";
  const checked = new Set(Array.isArray(savedChecks) ? savedChecks.map(String) : []);
  return `
    <section class="account-guide" data-account-guide="${escapeHtml(guide.slug)}">
      <nav class="account-platform-tabs" aria-label="Площадки центра запуска">
        <a href="#${ACCOUNT_LAUNCH_PATH}">Все площадки</a>
        ${Object.values(ACCOUNT_LAUNCH_GUIDES).map((item) => `
          <a href="#${ACCOUNT_LAUNCH_PATH}/${escapeHtml(item.slug)}" ${item.slug === guide.slug ? 'aria-current="page" class="active"' : ""}>${escapeHtml(item.name)}</a>
        `).join("")}
      </nav>
      <header class="account-guide-hero account-platform-${escapeHtml(guide.slug)}">
        <div>
          <p class="eyebrow">${escapeHtml(guide.name)} · ${escapeHtml(guide.format)}</p>
          <h1>${escapeHtml(guide.title)}</h1>
          <p>${escapeHtml(guide.summary)}</p>
        </div>
        <div class="account-guide-score">
          <span>Маршрут</span><strong>5 шагов</strong><small>от регистрации до ссылки на пост</small>
        </div>
      </header>
      <div class="account-visual-root" data-account-visual-root data-account-platform="${escapeHtml(guide.slug)}"></div>
      ${guideSection(guide.slug, "01", "Регистрация и доступ", "Делайте по порядку — особенно если аккаунт новый.", guide.registration, "registration", checked)}
      ${guideSection(guide.slug, "02", "Профиль готов к работе", "Не публикуйте, пока каждый пункт не подтверждён.", guide.profile, "profile", checked)}
      ${rampMarkup(guide.ramp)}
      ${riskCompareMarkup(guide.allowed, guide.stop)}
      ${guideSection(guide.slug, "05", `Первая публикация в ${guide.format}`, "Ссылка в портал возвращается только после просмотра опубликованного файла.", guide.publish, "publish", checked)}
      ${advertisingCheckerMarkup(guide.slug)}
      ${officialSourcesMarkup(guide.sources)}
      <div class="account-guide-finish" aria-live="polite">
        <div><p class="eyebrow">Финишная проверка</p><h2>Все чек-листы сохранены в этой вкладке</h2><p>Это учебная готовность, а не разрешение публиковать любой материал. Конкретный ролик всё равно должен быть назначен и одобрен в задаче.</p></div>
        <a class="btn" href="#/learn/first-shift">Пройти «Первую смену» →</a>
      </div>
    </section>
  `;
}

export function evaluateAdvertisingAnswers(answers) {
  const normalized = ADVERTISING_DECISION_STEPS.map((step) => String(answers?.[step.id] || ""));
  if (normalized.some((answer) => !["yes", "no"].includes(answer))) {
    return Object.freeze({
      status: "incomplete",
      title: "Ответьте на все три вопроса",
      message: "До этого публикацию нельзя считать проверенной.",
    });
  }
  if (normalized.includes("yes")) {
    return Object.freeze({
      status: "review",
      title: "Стоп: возможна реклама или branded content",
      message: "Не публикуйте и не пытайтесь скрыть рекламные признаки. Передайте задачу руководителю для проверки маркировки и настроек площадки.",
    });
  }
  return Object.freeze({
    status: "document",
    title: "Явный обмен ценностью не найден",
    message: "Сохраните ответы в задаче. Это не автоматическое освобождение от маркировки: финальное решение остаётся за ответственным сотрудником до публикации.",
  });
}

function guideSection(slug, number, title, summary, items, section, checked) {
  return `
    <section class="account-guide-section" aria-labelledby="account-${escapeHtml(section)}-title">
      <header><span>${escapeHtml(number)}</span><div><h2 id="account-${escapeHtml(section)}-title">${escapeHtml(title)}</h2><p>${escapeHtml(summary)}</p></div></header>
      <div class="account-checklist">
        ${items.map((item, index) => {
          const id = `${slug}-${section}-${index + 1}`;
          return `
            <label class="account-check-row">
              <input id="account-check-${escapeHtml(id)}" type="checkbox" data-account-check="${escapeHtml(id)}" data-account-platform="${escapeHtml(slug)}" data-account-section="${escapeHtml(section)}" ${checked.has(id) ? "checked" : ""} />
              <span><b aria-hidden="true">${String(index + 1).padStart(2, "0")}</b>${escapeHtml(item)}</span>
            </label>
          `;
        }).join("")}
      </div>
    </section>
  `;
}

function rampMarkup(phases) {
  return `
    <section class="account-guide-section account-ramp" aria-labelledby="account-ramp-title">
      <header><span>03</span><div><h2 id="account-ramp-title">Безопасный прогрев — это не накрутка</h2><p>Площадки не публикуют гарантированных «безопасных чисел». Поэтому маршрут строится по качеству и естественности действий, а не по выдуманной норме лайков в день.</p></div></header>
      <div class="account-ramp-track">
        ${phases.map((phase, index) => `
          <article><span>${index + 1}</span><p class="eyebrow">${escapeHtml(phase.label)}</p><h3>${escapeHtml(phase.title)}</h3><p>${escapeHtml(phase.body)}</p></article>
        `).join("")}
      </div>
    </section>
  `;
}

function riskCompareMarkup(allowed, stop) {
  return `
    <section class="account-guide-section" aria-labelledby="account-rules-title">
      <header><span>04</span><div><h2 id="account-rules-title">Что можно и где остановиться</h2><p>Красная колонка — не «нежелательно», а повод прекратить действие и уточнить его у руководителя.</p></div></header>
      <div class="account-risk-grid">
        <article class="account-risk-good"><p class="eyebrow">Можно</p><h3>Нормальная рабочая активность</h3><ul>${allowed.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></article>
        <article class="account-risk-stop"><p class="eyebrow">Стоп</p><h3>Риск ограничения или ошибки</h3><ul>${stop.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></article>
      </div>
    </section>
  `;
}

function advertisingCheckerMarkup(slug) {
  return `
    <section class="account-ad-checker" aria-labelledby="account-ad-title">
      <div class="account-ad-head"><span aria-hidden="true">!</span><div><p class="eyebrow">Перед кнопкой «Опубликовать»</p><h2 id="account-ad-title">Проверка рекламного характера</h2><p>Этот тест останавливает сомнительную публикацию. Он не учит обходить маркировку и не заменяет решение ответственного сотрудника.</p></div></div>
      <form id="account-ad-form" data-platform="${escapeHtml(slug)}" novalidate>
        ${ADVERTISING_DECISION_STEPS.map((step, index) => `
          <fieldset>
            <legend><span class="account-ad-question"><b aria-hidden="true">${index + 1}</b><span>${escapeHtml(step.question)}</span></span></legend>
            <div class="account-ad-options">
              <label><input type="radio" name="${escapeHtml(step.id)}" value="yes" /> Да</label>
              <label><input type="radio" name="${escapeHtml(step.id)}" value="no" /> Нет</label>
            </div>
          </fieldset>
        `).join("")}
        <button class="btn" type="submit">Проверить перед публикацией</button>
        <div id="account-ad-result" class="account-ad-result" role="status" aria-live="polite"></div>
      </form>
    </section>
  `;
}

function officialSourcesMarkup(sources) {
  return `
    <aside class="account-sources" aria-labelledby="account-sources-title">
      <div><p class="eyebrow">Проверено по первоисточникам</p><h2 id="account-sources-title">Официальная справка площадки</h2><p>Интерфейс и правила меняются. Если кнопка называется иначе, сверяйтесь с этими страницами, а не с устаревшим роликом из поиска.</p></div>
      <ul>${sources.map((source) => `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label)} <span aria-hidden="true">↗</span></a></li>`).join("")}</ul>
    </aside>
  `;
}

function sharedSafetyNotice() {
  return `
    <section class="account-safety-notice">
      <span aria-hidden="true">!</span><div><strong>Нет способа гарантировать отсутствие блокировки.</strong><p>Решение всегда принимает площадка. Центр уменьшает типичные риски: слабая защита входа, массовые автоматические действия, дубли, чужой контент и нераскрытая коммерческая связь.</p></div>
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
