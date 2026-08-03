/* Keep the mandatory learning route; normalize only the obsolete alias. */
(function normalizeContentEngineEntryRoute() {
  const hash = String(window.location.hash || "");
  if (!/^#\/academy(?:\/|\?|$)/u.test(hash)) return;
  const next = new URL(window.location.href);
  next.hash = hash.replace(/^#\/academy/u, "#/learn");
  window.history.replaceState({}, "", next);
}());
