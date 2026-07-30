(() => {
  const allowed = new Set(["obsidian"]);
  let theme = "obsidian";
  try {
    const saved = String(window.localStorage.getItem("contentengine.portal-theme.v1") || "").toLowerCase();
    if (allowed.has(saved)) theme = saved;
  } catch {
    // A blocked appearance preference must not delay authentication or portal loading.
  }
  document.documentElement.dataset.portalTheme = theme;
  const browserColors = {
    obsidian: "#0b0908",
  };
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", browserColors[theme]);
})();
