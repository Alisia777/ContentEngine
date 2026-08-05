/*
 * Canonical identity for one visible workspace action.
 *
 * Query parameters that do not select a real view or a supported UUID entity
 * are deliberately ignored. This keeps rerenders of one action stable while
 * making every genuine action switch an explicit state boundary.
 */

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

const ACTION_ROUTES = Object.freeze({
  "/workspace/home": Object.freeze({ defaultView: "today", views: ["today"] }),
  "/workspace/work": Object.freeze({ defaultView: "next", views: ["next", "queue", "views", "notifications"] }),
  "/workspace/board": Object.freeze({
    defaultView: "browse",
    views: ["browse", "organize", "trash"],
    entities: { folder: ["browse", "organize"] },
  }),
  "/workspace/media": Object.freeze({ defaultView: "upload", views: ["upload", "recent"] }),
  "/workspace/generation": Object.freeze({
    defaultView: "create",
    views: ["create", "history", "products"],
    entities: { job: ["history", "create"], media: ["create"], review: ["create"] },
  }),
  "/workspace/review": Object.freeze({
    defaultView: "new",
    views: ["new", "current", "history"],
    entities: { review: ["current", "history"], media: ["new"] },
  }),
  "/workspace/placement": Object.freeze({ defaultView: "next", views: ["next", "history"], entities: { placement: ["next", "history"] } }),
  "/workspace/stats": Object.freeze({ defaultView: "overview", views: ["overview", "new"], entities: { placement: ["overview", "new"] } }),
  "/workspace/payouts": Object.freeze({ defaultView: "next", views: ["next", "history"], entities: { payout: ["next", "history"] } }),
  "/workspace/tasks": Object.freeze({ defaultView: "next", views: ["next", "queue"], entities: { item: ["next", "queue"] } }),
  "/workspace/research": Object.freeze({
    defaultView: "evidence",
    views: ["evidence", "corrections", "brief", "approve", "handoff"],
    entities: { run: ["evidence", "corrections", "brief", "approve", "handoff"] },
  }),
  "/workspace/ai": Object.freeze({
    defaultView: "overview",
    views: ["overview", "knowledge", "teach", "cases", "history"],
    entities: { scope: ["overview", "knowledge", "teach", "cases", "history"] },
    qualifiers: {
      category: Object.freeze({
        defaultValue: "cosmetics",
        values: ["cosmetics", "baa", "sports_food", "food", "household", "apparel", "electronics", "other"],
      }),
    },
  }),
  "/workspace/feedback": Object.freeze({ defaultView: "new", views: ["new", "history"] }),
  "/workspace/team": Object.freeze({
    defaultView: "members",
    views: ["invite", "access", "members", "reviews", "review", "budget", "campaigns", "campaign", "new-campaign", "health"],
    entities: { campaign: ["campaign"], review: ["review"] },
  }),
});

function normalizePath(value) {
  const raw = String(value || "/").replace(/^#/, "").split("?")[0] || "/";
  return (`/${raw}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function routeParts(input) {
  if (input && typeof input === "object" && "path" in input) {
    const query = input.query instanceof URLSearchParams
      ? new URLSearchParams(input.query)
      : new URLSearchParams(String(input.query || ""));
    return { path: normalizePath(input.path), query };
  }
  const raw = String(input ?? (typeof window !== "undefined" ? window.location.hash : "/"));
  const withoutHash = raw.replace(/^#/, "");
  const splitAt = withoutHash.indexOf("?");
  return {
    path: normalizePath(splitAt >= 0 ? withoutHash.slice(0, splitAt) : withoutHash),
    query: new URLSearchParams(splitAt >= 0 ? withoutHash.slice(splitAt + 1) : ""),
  };
}

function singleQueryValue(query, name) {
  const values = query.getAll(name);
  return values.length === 1 ? String(values[0] || "").trim().toLowerCase() : "";
}

export function workspaceActionDescriptor(input) {
  const { path, query } = routeParts(input);
  const definition = ACTION_ROUTES[path];
  if (!definition) {
    return Object.freeze({
      path,
      view: "default",
      projectId: "",
      qualifiers: Object.freeze({}),
      entityParameter: "",
      entityId: "",
      key: `${path}?view=default`,
    });
  }

  const requestedProjectId = singleQueryValue(query, "project_id");
  const projectId = UUID_PATTERN.test(requestedProjectId) ? requestedProjectId : "";

  const entityCandidates = Object.entries(definition.entities || {}).map(([parameter, views]) => ({
    parameter,
    views,
    value: singleQueryValue(query, parameter),
  }));
  const validEntityCandidates = entityCandidates.filter((candidate) => UUID_PATTERN.test(candidate.value));
  const requestedView = singleQueryValue(query, "view");
  let view = definition.views.includes(requestedView) ? requestedView : definition.defaultView;

  if (!requestedView && path === "/workspace/generation" && validEntityCandidates.some((candidate) => candidate.parameter === "job")) {
    view = "history";
  } else if (!requestedView && path === "/workspace/review" && validEntityCandidates.some((candidate) => candidate.parameter === "review")) {
    view = "current";
  }

  const qualifiers = Object.freeze(Object.fromEntries(
    Object.entries(definition.qualifiers || {}).map(([parameter, contract]) => {
      const requested = singleQueryValue(query, parameter);
      const value = contract.values.includes(requested) ? requested : contract.defaultValue;
      return [parameter, value];
    }),
  ));
  const qualifierSuffix = Object.entries(qualifiers)
    .map(([parameter, value]) => `&${parameter}=${encodeURIComponent(value)}`)
    .join("");
  const entities = validEntityCandidates.filter((candidate) => candidate.views.includes(view));
  const entity = entities[0] || null;
  const projectSuffix = projectId ? `&project_id=${encodeURIComponent(projectId)}` : "";
  const entitySuffix = entities
    .map((candidate) => `&${candidate.parameter}=${encodeURIComponent(candidate.value)}`)
    .join("");
  return Object.freeze({
    path,
    view,
    projectId,
    qualifiers,
    entityParameter: entity?.parameter || "",
    entityId: entity?.value || "",
    key: `${path}?view=${encodeURIComponent(view)}${projectSuffix}${qualifierSuffix}${entitySuffix}`,
  });
}

export function workspaceActionKey(input) {
  return workspaceActionDescriptor(input).key;
}

export function isWorkspaceActionKey(value) {
  return String(value || "").startsWith("/workspace/");
}
