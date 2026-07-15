(() => {
  const allowed = new Set(["emerald", "bordeaux", "sapphire"]);
  let theme = "emerald";
  try {
    const saved = String(window.localStorage.getItem("contentengine.portal-theme.v1") || "").toLowerCase();
    if (allowed.has(saved)) theme = saved;
  } catch {
    // A blocked appearance preference must not delay authentication or portal loading.
  }
  document.documentElement.dataset.portalTheme = theme;
})();
