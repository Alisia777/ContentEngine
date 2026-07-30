/* Task badges for the system Dock. Reads only the existing tab-scoped UI registry. */

const PRODUCTIVITY_KEY = "contentengine.workspace-productivity.v1";
let queued = false;

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function store() {
  try { return window.sessionStorage; } catch { return null; }
}

function tone(task) {
  const text = `${task?.status || ""} ${task?.statusLabel || ""} ${task?.parked?.reason || ""}`.toLocaleLowerCase("ru-RU");
  if (/блок|ошиб|отклон|просроч|failed|rejected/.test(text)) return "blocked";
  if (task?.parked) {
    const due = task.parked.returnAt ? new Date(task.parked.returnAt).getTime() <= Date.now() : false;
    return due ? "return" : "waiting";
  }
  return "active";
}

function readSummary() {
  try {
    const parsed = JSON.parse(store()?.getItem(PRODUCTIVITY_KEY) || "{}");
    const tasks = Object.values(parsed?.tasks || {}).filter((task) => task && (task.pinned || task.parked));
    const result = new Map();
    tasks.forEach((task) => {
      const route = String(task.route || "");
      if (!route) return;
      const current = result.get(route) || { count: 0, tone: "active" };
      current.count += 1;
      const nextTone = tone(task);
      const rank = { active: 0, waiting: 1, return: 2, blocked: 3 };
      if (rank[nextTone] > rank[current.tone]) current.tone = nextTone;
      result.set(route, current);
    });
    return result;
  } catch {
    return new Map();
  }
}

function sync() {
  queued = false;
  const dock = q(".ce-mac-dock");
  if (!dock) return;
  const summary = readSummary();
  qa("[data-ce-dock-route]", dock).forEach((item) => {
    q(":scope > .ce-mac-dock__badge", item)?.remove();
    const data = summary.get(String(item.dataset.ceDockRoute || ""));
    item.removeAttribute("data-task-tone");
    if (!data?.count) return;
    item.dataset.taskTone = data.tone;
    const badge = document.createElement("b");
    badge.className = "ce-mac-dock__badge";
    badge.dataset.tone = data.tone;
    badge.textContent = data.count > 9 ? "9+" : String(data.count);
    badge.setAttribute("aria-label", `${data.count} активных задач`);
    item.append(badge);
  });
}

function queueSync() {
  if (queued) return;
  queued = true;
  window.requestAnimationFrame(sync);
}

const observer = new MutationObserver(queueSync);
observer.observe(document.querySelector("#app") || document.body, { childList: true, subtree: true });
document.addEventListener("contentengine:productivity-changed", queueSync);
window.addEventListener("hashchange", queueSync, { passive: true });
window.addEventListener("storage", (event) => {
  if (event.key === PRODUCTIVITY_KEY) queueSync();
});
window.setInterval(queueSync, 60_000);
queueSync();
