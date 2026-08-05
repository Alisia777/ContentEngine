/*
 * ContentEngine Research · governed manual training-example intake.
 *
 * This module adds one compact user action to the existing Research workspace.
 * It records a public YouTube identity through a narrow authenticated RPC. It
 * never starts OpenAI/YouTube providers, never submits the paid research form,
 * and never treats one example as an active winner or generation rule.
 */

const ROUTE = "/workspace/research";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/u;
const ROLES = new Set(["reference", "competitor_mechanic", "anti_example"]);
const CATEGORIES = Object.freeze([
  ["electronics", "Электроника"],
  ["household", "Товары для дома"],
  ["cosmetics", "Косметика и уход"],
  ["baa", "БАДы"],
  ["sports_food", "Спортивное питание"],
  ["food", "Еда и напитки"],
  ["apparel", "Одежда и аксессуары"],
  ["other", "Другая категория"],
]);
const runtime = {
  queued: false,
  timers: new Set(),
  dialog: null,
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function create(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function routePath() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/g, "/")
    .replace(/\/$/, "") || "/";
}

function routeQuery() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  const query = raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "";
  return new URLSearchParams(query);
}

function projectId() {
  const value = String(routeQuery().get("project_id") || "").trim().toLowerCase();
  return UUID.test(value) ? value : "";
}

function runId() {
  const candidates = qa("[data-research-id]")
    .map((node) => String(node.dataset.researchId || "").trim().toLowerCase())
    .filter((value) => UUID.test(value));
  return candidates[0] || "";
}

function youtubeVideoId(value) {
  let url;
  try {
    url = new URL(String(value || "").trim());
  } catch {
    return "";
  }
  if (url.protocol !== "https:") return "";
  const host = url.hostname.toLowerCase();
  let candidate = "";
  if (host === "youtu.be" || host === "www.youtu.be") {
    candidate = url.pathname.split("/").filter(Boolean)[0] || "";
  } else if (["youtube.com", "www.youtube.com", "m.youtube.com"].includes(host)) {
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] === "watch") candidate = url.searchParams.get("v") || "";
    else if (["shorts", "embed", "live"].includes(parts[0])) candidate = parts[1] || "";
  }
  return VIDEO_ID.test(candidate) ? candidate : "";
}

function currentSessionToken() {
  const config = window.CONTENTENGINE_CONFIG || {};
  let projectRef = "";
  try {
    projectRef = new URL(String(config.SUPABASE_URL || "")).hostname.split(".")[0] || "";
  } catch {
    return "";
  }
  const expectedKey = `sb-${projectRef}-auth-token`;
  let raw = "";
  try {
    raw = window.localStorage.getItem(expectedKey) || "";
  } catch {
    return "";
  }
  if (!raw) return "";
  try {
    const value = JSON.parse(raw);
    return String(
      value?.access_token
        || value?.currentSession?.access_token
        || value?.session?.access_token
        || "",
    ).trim();
  } catch {
    return "";
  }
}

async function callRegistrationRpc(payload) {
  const config = window.CONTENTENGINE_CONFIG || {};
  const supabaseUrl = String(config.SUPABASE_URL || "").replace(/\/$/u, "");
  const publishableKey = String(config.SUPABASE_PUBLISHABLE_KEY || "").trim();
  const token = currentSessionToken();
  if (!supabaseUrl || !publishableKey || !token) {
    throw new Error("Сессия кабинета не найдена. Обновите страницу и войдите снова.");
  }
  const response = await fetch(
    `${supabaseUrl}/rest/v1/rpc/creator_register_research_training_example`,
    {
      method: "POST",
      cache: "no-store",
      credentials: "omit",
      referrerPolicy: "no-referrer",
      headers: {
        apikey: publishableKey,
        authorization: `Bearer ${token}`,
        "content-type": "application/json",
        accept: "application/json",
        "accept-profile": "public",
        "content-profile": "public",
      },
      body: JSON.stringify({ p_payload: payload }),
    },
  );
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok || body?.ok !== true) {
    const code = String(body?.code || body?.message || "").trim();
    const friendly = {
      research_training_example_run_not_found:
        "В этом проекте ещё нет исследования, к которому можно привязать пример.",
      research_training_example_category_mismatch:
        "Категория примера не совпадает с категорией текущего исследования.",
      research_training_example_youtube_url_invalid:
        "Нужна публичная ссылка YouTube: shorts, watch, youtu.be, embed или live.",
      research_training_example_ack_required:
        "Подтвердите публичность источника и запрет точного копирования.",
    }[code];
    throw new Error(friendly || code || `Сервер отклонил пример (${response.status}).`);
  }
  return body;
}

function closeDialog() {
  const dialog = runtime.dialog;
  if (!dialog) return;
  dialog.close?.();
  dialog.remove();
  runtime.dialog = null;
  document.body.classList.remove("ce-research-example-open");
}

function statusMessage(result) {
  if (result.learning_state === "linked_pending_human_review") {
    return "Пример добавлен в доказательную базу категории. Он ждёт человеческой проверки; один ролик не активирует winner или правило генерации.";
  }
  return "Пример сохранён в исследовании electronics. Чтобы он вошёл в категорийное обучение, подтвердите точную рыночную категорию «Аэрогрили».";
}

function openDialog() {
  if (runtime.dialog || !projectId()) return;
  const dialog = create("dialog", "ce-research-example-dialog");
  dialog.setAttribute("aria-labelledby", "ce-research-example-title");
  const header = create("header", "ce-research-example-dialog__header");
  const copy = create("div");
  copy.append(
    create("small", "", "ПРИМЕР → ДОКАЗАТЕЛЬСТВО"),
    create("h2", "", "Добавить видео без платного анализа"),
    create("p", "", "Система сохранит ссылку как кандидат для обучения. Она не будет утверждать, что просмотрела ролик, и не скопирует его покадрово."),
  );
  const close = create("button", "ce-research-example-dialog__close", "×");
  close.type = "button";
  close.setAttribute("aria-label", "Закрыть");
  header.append(copy, close);

  const form = create("form", "ce-research-example-form");
  form.id = "research-training-example-form";
  const urlLabel = create("label", "field");
  urlLabel.append(create("span", "", "Ссылка YouTube *"));
  const urlInput = create("input");
  urlInput.name = "source_url";
  urlInput.type = "url";
  urlInput.required = true;
  urlInput.maxLength = 2048;
  urlInput.placeholder = "https://www.youtube.com/shorts/…";
  urlLabel.append(urlInput);

  const pair = create("div", "ce-research-example-form__pair");
  const categoryLabel = create("label", "field");
  categoryLabel.append(create("span", "", "Категория ИИ *"));
  const category = create("select");
  category.name = "compliance_category";
  for (const [value, label] of CATEGORIES) {
    const option = create("option", "", label);
    option.value = value;
    option.selected = value === "electronics";
    category.append(option);
  }
  categoryLabel.append(category);
  const marketLabel = create("label", "field");
  marketLabel.append(create("span", "", "Точная категория *"));
  const market = create("input");
  market.name = "market_category_name";
  market.required = true;
  market.maxLength = 160;
  market.value = "Аэрогрили";
  marketLabel.append(market);
  pair.append(categoryLabel, marketLabel);

  const roleLabel = create("label", "field");
  roleLabel.append(create("span", "", "Роль примера *"));
  const role = create("select");
  role.name = "training_role";
  [["reference", "Референс"], ["competitor_mechanic", "Повторить только механику"], ["anti_example", "Антипример"]].forEach(([value, label]) => {
    const option = create("option", "", label);
    option.value = value;
    role.append(option);
  });
  roleLabel.append(role);

  const summaryLabel = create("label", "field");
  summaryLabel.append(create("span", "", "Что именно взять из примера *"));
  const summary = create("textarea");
  summary.name = "human_summary";
  summary.required = true;
  summary.minLength = 20;
  summary.maxLength = 1000;
  summary.rows = 4;
  summary.value = "Использовать ролик как пример короткого вертикального контента по аэрогрилю; брать только общую механику подачи и не копировать кадры, лицо, музыку, текст или чужой товар.";
  summaryLabel.append(summary);

  const acknowledgements = create("div", "ce-research-example-form__acks");
  const publicAck = create("label", "ce-research-example-check");
  const publicInput = create("input");
  publicInput.type = "checkbox";
  publicInput.name = "public_source_ack";
  publicInput.required = true;
  publicAck.append(publicInput, create("span", "", "Источник публичный; я добавляю только ссылку и своё пояснение."));
  const copyAck = create("label", "ce-research-example-check");
  const copyInput = create("input");
  copyInput.type = "checkbox";
  copyInput.name = "no_exact_copy_ack";
  copyInput.required = true;
  copyAck.append(copyInput, create("span", "", "Не копировать ролик покадрово, не переносить лицо, музыку, слоган, текст и товар конкурента."));
  acknowledgements.append(publicAck, copyAck);

  const feedback = create("p", "ce-research-example-form__feedback");
  feedback.setAttribute("role", "status");
  feedback.setAttribute("aria-live", "polite");
  const actions = create("div", "ce-research-example-form__actions");
  const cancel = create("button", "btn btn-secondary", "Отмена");
  cancel.type = "button";
  const submit = create("button", "btn btn-primary", "Добавить пример");
  submit.type = "submit";
  actions.append(cancel, submit);
  form.append(urlLabel, pair, roleLabel, summaryLabel, acknowledgements, feedback, actions);
  dialog.append(header, form);
  document.body.append(dialog);
  runtime.dialog = dialog;
  document.body.classList.add("ce-research-example-open");
  dialog.showModal?.();
  urlInput.focus({ preventScroll: true });

  close.addEventListener("click", closeDialog);
  cancel.addEventListener("click", closeDialog);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeDialog();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = new FormData(form);
    const sourceUrl = String(values.get("source_url") || "").trim();
    const videoId = youtubeVideoId(sourceUrl);
    const selectedRole = String(values.get("training_role") || "").trim();
    const selectedCategory = String(values.get("compliance_category") || "").trim();
    const selectedMarket = String(values.get("market_category_name") || "").trim();
    const humanSummary = String(values.get("human_summary") || "").replace(/\s+/gu, " ").trim();
    if (!videoId) {
      feedback.textContent = "Не удалось определить YouTube video ID. Проверьте ссылку Shorts/watch/youtu.be.";
      feedback.dataset.tone = "danger";
      urlInput.focus();
      return;
    }
    if (!ROLES.has(selectedRole) || humanSummary.length < 20) {
      feedback.textContent = "Укажите роль и понятное пояснение длиной не менее 20 символов.";
      feedback.dataset.tone = "danger";
      return;
    }
    submit.disabled = true;
    cancel.disabled = true;
    form.setAttribute("aria-busy", "true");
    feedback.textContent = "Сохраняем источник без provider call и без оплаты…";
    feedback.dataset.tone = "info";
    try {
      const payload = {
        project_id: projectId(),
        source_url: sourceUrl,
        compliance_category: selectedCategory,
        market_category_name: selectedMarket,
        training_role: selectedRole,
        human_summary: humanSummary,
        public_source_ack: values.has("public_source_ack"),
        no_exact_copy_ack: values.has("no_exact_copy_ack"),
        idempotency_key: `manual-youtube:${projectId()}:${videoId}:${selectedRole}:v1`,
      };
      const currentRunId = runId();
      if (currentRunId) payload.run_id = currentRunId;
      const result = await callRegistrationRpc(payload);
      feedback.textContent = statusMessage(result);
      feedback.dataset.tone = "success";
      const launch = q("[data-ce-research-example-launch]");
      if (launch) {
        launch.dataset.state = result.learning_state;
        q("strong", launch).textContent = "Пример добавлен";
        q("p", launch).textContent = statusMessage(result);
      }
      window.setTimeout(closeDialog, 2400);
    } catch (error) {
      feedback.textContent = String(error?.message || "Не удалось сохранить пример.");
      feedback.dataset.tone = "danger";
      submit.disabled = false;
      cancel.disabled = false;
      form.removeAttribute("aria-busy");
    }
  });
}

function mount() {
  if (routePath() !== ROUTE) {
    closeDialog();
    return;
  }
  const project = projectId();
  if (!project) return;
  const page = q(".product-research-page, .page-wrap");
  if (!page || q("[data-ce-research-example-launch]", page)) return;
  const anchor = q(
    ".product-research-progress, .product-research-result, .product-research-start-grid",
    page,
  ) || page.firstElementChild;
  const launch = create("section", "ce-research-example-launch");
  launch.dataset.ceResearchExampleLaunch = "true";
  const copy = create("div");
  copy.append(
    create("small", "", "БЕЗ ПОВТОРНОГО ПЛАТНОГО АНАЛИЗА"),
    create("strong", "", "Добавить YouTube-пример в обучение"),
    create("p", "", "Shorts/watch/youtu.be сохраняются как один источник. Один пример остаётся кандидатом и не становится winner автоматически."),
  );
  const button = create("button", "btn btn-secondary", "Добавить пример");
  button.type = "button";
  button.addEventListener("click", openDialog);
  launch.append(copy, button);
  if (anchor?.parentNode) anchor.before(launch);
  else page.prepend(launch);
}

function clearTimers() {
  runtime.timers.forEach((timer) => window.clearTimeout(timer));
  runtime.timers.clear();
}

function schedule() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
  clearTimers();
  [120, 420, 900].forEach((delay) => {
    const timer = window.setTimeout(() => {
      runtime.timers.delete(timer);
      mount();
    }, delay);
    runtime.timers.add(timer);
  });
}

window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
window.addEventListener("pageshow", schedule, { passive: true });
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", schedule, { once: true });
} else {
  schedule();
}

window.ContentEngineResearchTrainingExample = Object.freeze({
  schedule,
  youtubeVideoId,
});
