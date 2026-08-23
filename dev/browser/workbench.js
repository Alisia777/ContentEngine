const config = window.CONTENTENGINE_CONFIG || {};
const routes = Object.freeze({
  copy: {
    title: "Copy · Product Swap",
    subtitle: "Точный MP4 проходит локальный storyboard и замену товара без платного запроса.",
    state: "mock archive ready",
    feature: "viral_product_swap",
    steps: ["MP4 intake", "Storyboard", "Original-product frame", "New-product references", "Preflight", "Mock generation", "Archive"],
  },
  avatar: {
    title: "Avatar · Character Performance",
    subtitle: "UX доступен для проверки, но provider adapter намеренно не активирован.",
    state: "feature gated",
    feature: "character_performance",
    steps: ["Avatar consent", "Source performance", "Product references", "Adapter verification", "Controlled enablement"],
  },
  strategy: {
    title: "Strategy · Viral Rebuild",
    subtitle: "Механика референса превращается в новый mock storyboard с неизменяемым spend gate.",
    state: "mock preflight",
    feature: "viral_rebuild",
    steps: ["Reference set", "Mechanics extraction", "Creative brief", "Preflight", "Mock result", "Archive"],
  },
});

function selectedRoute() {
  const key = location.hash.replace(/^#\//u, "").split(/[?\/]/u)[0];
  return Object.hasOwn(routes, key) ? key : "copy";
}

function render() {
  const key = selectedRoute();
  const route = routes[key];
  document.body.dataset.route = key;
  document.querySelectorAll("[data-route-link]").forEach((link) => {
    if (link.dataset.routeLink === key) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  const gated = key === "avatar" && config.CHARACTER_PERFORMANCE_ENABLED !== true;
  document.querySelector("#app").innerHTML = `
    <section class="hero" data-smoke-route="${key}">
      <div>
        <span class="route-id">#/workbench/${key} · ${route.feature}</span>
        <h2>${route.title}</h2>
        <p>${route.subtitle}</p>
        <div class="flow">${route.steps.map((step, index) => `
          <div class="step"><span class="num">${index + 1}</span><div><strong>${step}</strong><small>${gated && index >= 3 ? "Ожидает подтверждённый adapter contract" : "Локальный deterministic contract"}</small></div><span class="${gated && index >= 3 ? "gated" : "done"}">${gated && index >= 3 ? "GATED" : "READY"}</span></div>`).join("")}</div>
      </div>
      <aside>
        <div class="metric"><span>Provider mode</span><strong>MOCK ONLY</strong></div>
        <div class="metric"><span>Paid authority</span><strong>creator-generate</strong></div>
        <div class="metric"><span>Route status</span><strong>${route.state}</strong></div>
        <div class="metric"><span>Supabase</span><strong>${config.SUPABASE_URL || "local overlay"}</strong></div>
        <div class="refs" aria-label="Product references"><span class="ref"></span><span class="ref"></span><span class="ref"></span></div>
      </aside>
    </section>`;
}

window.addEventListener("hashchange", render);
if (!location.hash) location.hash = "#/copy";
render();
