(() => {
  const allowed = new Set(["emerald", "bordeaux", "sapphire", "altea-dark"]);
  let theme = "emerald";
  try {
    const saved = String(window.localStorage.getItem("contentengine.portal-theme.v1") || "").toLowerCase();
    if (allowed.has(saved)) theme = saved;
  } catch {
    // A blocked appearance preference must not delay authentication or portal loading.
  }
  document.documentElement.dataset.portalTheme = theme;
  const browserColors = {
    emerald: "#183a35",
    bordeaux: "#5a2538",
    sapphire: "#183b63",
    "altea-dark": "#0b1513",
  };
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", browserColors[theme]);
})();
