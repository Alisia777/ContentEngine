/*
 * Workspace desk drafts
 * Keeps unfinished form values in memory while the tab is open. File objects are
 * never serialized or persisted. Password, hidden and secret-like fields are never captured.
 */

const DRAFT_ROUTE_PREFIXES = ["/workspace/", "/learn"];
const DRAFT_FIELD_EXCLUSIONS = new Set(["password", "hidden", "submit", "button", "reset", "image"]);
const DRAFT_SECRET_PATTERN = /(password|secret|api[_-]?key|authorization|access[_-]?token|refresh[_-]?token)/i;
const MAX_DRAFT_AGE_MS = 4 * 60 * 60 * 1000;
const draftRoutes = new Map();
let restoreQueued = false;
let restoring = false;

function draftRoute() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  const path = raw.split("?")[0] || "/";
  return (`/${path}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function isDraftRoute(route) {
  return DRAFT_ROUTE_PREFIXES.some((prefix) => String(route || "").startsWith(prefix));
}

function formRoot() {
  return document.querySelector("#workspace-content")
    || document.querySelector(".learning-page")
    || document.querySelector("#main-content");
}

function formKey(form, index = 0) {
  if (form.id) return `id:${form.id}`;
  for (const key of ["placementId", "payoutId", "taskId", "mediaId", "reviewId", "generationJobId"]) {
    if (form.dataset?.[key]) return `${key}:${form.dataset[key]}`;
  }
  return `index:${index}:${String(form.className || "form").replace(/\s+/g, ".")}`;
}

function eligibleField(field) {
  if (!(field instanceof HTMLElement) || !field.matches("input, select, textarea")) return false;
  const type = String(field.type || "").toLowerCase();
  if (DRAFT_FIELD_EXCLUSIONS.has(type)) return false;
  const identity = [
    field.id,
    field.getAttribute("name"),
    field.getAttribute("autocomplete"),
    field.getAttribute("aria-label"),
  ].filter(Boolean).join(" ");
  if (DRAFT_SECRET_PATTERN.test(identity) || field.getAttribute("autocomplete") === "one-time-code") return false;
  if (field.closest("[data-no-desk-draft], .workspace-overview")) return false;
  return true;
}

function snapshotField(field, index) {
  const type = String(field.type || "").toLowerCase();
  const base = {
    index,
    name: String(field.getAttribute("name") || ""),
    id: String(field.id || ""),
    type,
    value: "",
    checked: null,
    selected: null,
    files: null,
  };
  if (field instanceof HTMLInputElement && ["checkbox", "radio"].includes(type)) {
    base.value = field.value;
    base.checked = field.checked;
  } else if (field instanceof HTMLInputElement && type === "file") {
    base.files = [...(field.files || [])];
  } else if (field instanceof HTMLSelectElement && field.multiple) {
    base.selected = [...field.selectedOptions].map((option) => option.value);
  } else {
    base.value = String(field.value ?? "");
  }
  return base;
}

function snapshotForm(form, route = draftRoute()) {
  if (!isDraftRoute(route) || !(form instanceof HTMLFormElement)) return;
  const root = formRoot();
  if (!root?.contains(form)) return;
  const forms = [...root.querySelectorAll("form")];
  const fields = [...form.elements].filter(eligibleField).map(snapshotField);
  if (!fields.length) return;
  const capturedAt = Date.now();
  const routeDrafts = draftRoutes.get(route) || new Map();
  routeDrafts.set(formKey(form, forms.indexOf(form)), { capturedAt, fields });
  draftRoutes.set(route, routeDrafts);
  form.dataset.workspaceDeskTouched = "true";
  form.dataset.workspaceDeskRestoredAt = String(capturedAt);
  updateDraftIndicators();
}

function snapshotTouchedForms(route = draftRoute()) {
  const root = formRoot();
  if (!root || !isDraftRoute(route)) return;
  [...root.querySelectorAll("form")]
    .filter((form) => form.dataset.workspaceDeskTouched === "true" || form.dataset.dirty === "true")
    .forEach((form) => snapshotForm(form, route));
}

function routeDraftCount(route) {
  return draftRoutes.get(route)?.size || 0;
}

function findSavedField(savedFields, field, index) {
  const type = String(field.type || "").toLowerCase();
  const name = String(field.getAttribute("name") || "");
  const id = String(field.id || "");
  if (id) {
    const byId = savedFields.find((saved) => saved.id === id && saved.type === type);
    if (byId) return byId;
  }
  if (name && ["checkbox", "radio"].includes(type)) {
    return savedFields.find((saved) => saved.name === name && saved.type === type && saved.value === field.value);
  }
  if (name) {
    const byName = savedFields.find((saved) => saved.name === name && saved.type === type);
    if (byName) return byName;
  }
  return savedFields.find((saved) => saved.index === index && saved.type === type) || null;
}

function restoreField(field, saved) {
  if (!saved || !eligibleField(field)) return false;
  const type = String(field.type || "").toLowerCase();
  if (field instanceof HTMLInputElement && ["checkbox", "radio"].includes(type)) {
    if (field.checked === Boolean(saved.checked)) return false;
    field.checked = Boolean(saved.checked);
    return true;
  }
  if (field instanceof HTMLInputElement && type === "file") {
    if (!saved.files?.length || typeof DataTransfer !== "function") return false;
    try {
      const transfer = new DataTransfer();
      saved.files.forEach((file) => transfer.items.add(file));
      field.files = transfer.files;
      return true;
    } catch {
      return false;
    }
  }
  if (field instanceof HTMLSelectElement && field.multiple && Array.isArray(saved.selected)) {
    let changed = false;
    [...field.options].forEach((option) => {
      const selected = saved.selected.includes(option.value);
      if (option.selected !== selected) changed = true;
      option.selected = selected;
    });
    return changed;
  }
  if (String(field.value ?? "") === String(saved.value ?? "")) return false;
  field.value = saved.value ?? "";
  return true;
}

function pruneExpiredDrafts(route, routeDrafts) {
  const now = Date.now();
  routeDrafts.forEach((saved, key) => {
    if (!saved || now - saved.capturedAt > MAX_DRAFT_AGE_MS) routeDrafts.delete(key);
  });
  if (!routeDrafts.size) draftRoutes.delete(route);
}

function restoreRouteDrafts(route = draftRoute()) {
  const routeDrafts = draftRoutes.get(route);
  const root = formRoot();
  if (!routeDrafts?.size || !root) {
    updateDraftIndicators();
    return;
  }
  pruneExpiredDrafts(route, routeDrafts);
  if (!routeDrafts.size) {
    updateDraftIndicators();
    return;
  }

  restoring = true;
  let restoredForms = 0;
  const forms = [...root.querySelectorAll("form")];
  forms.forEach((form, formIndex) => {
    if (form.dataset.busy === "true") return;
    const saved = routeDrafts.get(formKey(form, formIndex));
    if (!saved || form.dataset.workspaceDeskRestoredAt === String(saved.capturedAt)) return;
    let restored = false;
    [...form.elements].filter(eligibleField).forEach((field, fieldIndex) => {
      const fieldChanged = restoreField(field, findSavedField(saved.fields, field, fieldIndex));
      if (!fieldChanged) return;
      restored = true;
      const type = String(field.type || "").toLowerCase();
      field.dispatchEvent(new Event(field instanceof HTMLInputElement && ["checkbox", "radio", "file"].includes(type) ? "change" : "input", { bubbles: true }));
    });
    form.dataset.workspaceDeskRestoredAt = String(saved.capturedAt);
    if (restored) {
      form.dataset.workspaceDeskTouched = "true";
      form.dataset.dirty = "true";
      restoredForms += 1;
    }
  });
  restoring = false;
  updateDraftIndicators();
  if (restoredForms) announceDraft(`Восстановлен черновик: ${restoredForms} ${restoredForms === 1 ? "форма" : "формы"}.`);
}

function clearFormDraft(form, route = draftRoute()) {
  const root = formRoot();
  if (!(form instanceof HTMLFormElement) || !root) return;
  const forms = [...root.querySelectorAll("form")];
  const routeDrafts = draftRoutes.get(route);
  routeDrafts?.delete(formKey(form, forms.indexOf(form)));
  if (routeDrafts && routeDrafts.size === 0) draftRoutes.delete(route);
  delete form.dataset.workspaceDeskTouched;
  delete form.dataset.workspaceDeskRestoredAt;
  updateDraftIndicators();
}

function announceDraft(message) {
  let region = document.querySelector(".workspace-draft-live-region");
  if (!region) {
    region = document.createElement("div");
    region.className = "workspace-draft-live-region";
    region.setAttribute("aria-live", "polite");
    region.setAttribute("aria-atomic", "true");
    document.body.append(region);
  }
  region.textContent = "";
  window.setTimeout(() => { region.textContent = message; }, 20);
}

function setIndicatorText(element, text) {
  if (element.textContent !== text) element.textContent = text;
}

function updateDraftIndicators() {
  const current = draftRoute();
  const count = routeDraftCount(current);
  const copy = document.querySelector(".workspace-deck-current__copy");
  let indicator = copy?.querySelector(".workspace-draft-indicator");
  if (copy && count) {
    const text = `Черновик · ${count}`;
    if (!indicator) {
      indicator = document.createElement("span");
      indicator.className = "workspace-draft-indicator";
      indicator.textContent = text;
      copy.append(indicator);
    } else {
      setIndicatorText(indicator, text);
    }
  } else {
    indicator?.remove();
  }

  document.querySelectorAll("[data-overview-route]").forEach((card) => {
    const route = card.dataset.overviewRoute || "";
    const routeCount = routeDraftCount(route);
    let badge = card.querySelector(".workspace-overview-draft");
    if (routeCount) {
      const text = `${routeCount} ${routeCount === 1 ? "черновик" : "черновика"}`;
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "workspace-overview-draft";
        badge.textContent = text;
        card.querySelector(".workspace-overview-card__copy")?.append(badge);
      } else {
        setIndicatorText(badge, text);
      }
    } else {
      badge?.remove();
    }
  });
}

function scheduleRestore() {
  if (restoreQueued) return;
  restoreQueued = true;
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      restoreQueued = false;
      restoreRouteDrafts(draftRoute());
    });
  });
}

function scheduleIndicatorSync() {
  window.requestAnimationFrame(updateDraftIndicators);
}

function nodeContainsWorkspaceOverview(node) {
  return node instanceof Element && (
    node.matches(".workspace-overview-backdrop")
    || Boolean(node.querySelector(".workspace-overview-backdrop"))
  );
}

function handleFieldEvent(event) {
  if (restoring) return;
  const target = event.target instanceof Element ? event.target : null;
  const form = target?.closest("form");
  if (form && eligibleField(target)) snapshotForm(form);
}

function handleSubmit(event) {
  const form = event.target instanceof HTMLFormElement ? event.target : null;
  if (form) clearFormDraft(form);
}

function handleReset(event) {
  const form = event.target instanceof HTMLFormElement ? event.target : null;
  if (form) window.queueMicrotask(() => clearFormDraft(form));
}

function handleRouteClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  const anchor = target?.closest("a[href^='#/']");
  if (anchor) snapshotTouchedForms(draftRoute());
  if (target?.closest("[data-deck-action='overview'], [data-deck-action='palette']")) {
    scheduleIndicatorSync();
  }
}

function handleShortcut(event) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    scheduleIndicatorSync();
  }
}

function handleHashChange() {
  scheduleRestore();
}

const app = document.querySelector("#app");
if (app) new MutationObserver(() => {
  scheduleRestore();
  window.queueMicrotask(updateDraftIndicators);
}).observe(app, { childList: true, subtree: true });

if (document.body) new MutationObserver((entries) => {
  if (entries.some((entry) => [...entry.addedNodes].some(nodeContainsWorkspaceOverview))) {
    scheduleIndicatorSync();
  }
}).observe(document.body, { childList: true, subtree: true });

document.addEventListener("input", handleFieldEvent, true);
document.addEventListener("change", handleFieldEvent, true);
document.addEventListener("submit", handleSubmit, true);
document.addEventListener("reset", handleReset, true);
document.addEventListener("click", handleRouteClick, true);
document.addEventListener("keydown", handleShortcut, true);
window.addEventListener("hashchange", handleHashChange, { passive: true });
window.addEventListener("beforeunload", () => snapshotTouchedForms(draftRoute()));
scheduleRestore();
