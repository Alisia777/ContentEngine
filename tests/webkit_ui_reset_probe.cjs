const [playwrightPath, executablePath, baseUrl] = process.argv.slice(2);
if (!playwrightPath || !executablePath || !baseUrl) {
  throw new Error("Usage: node webkit_ui_reset_probe.cjs <playwright> <webkit> <base-url>");
}

const { webkit } = require(playwrightPath);
const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function fixtureResult(context, name) {
  const page = await context.newPage();
  await page.goto(`${baseUrl}/tests/fixtures/${name}`, { waitUntil: "load" });
  await page.waitForFunction(() => document.querySelector("#result")?.dataset.passed);
  const result = await page.evaluate(() => ({ ...document.querySelector("#result").dataset }));
  await page.close();
  return result;
}

async function routeMotionResult(context) {
  await context.route("**/workspace-os-v4-finder.js*", async (route) => {
    await sleep(180);
    await route.continue();
  });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/tests/fixtures/workspace_route_motion_harness.html`, { waitUntil: "load" });
  await page.waitForFunction(() => (
    window.ContentEngineDesktopV4
    && document.documentElement.dataset.ceV4Ready === "true"
  ));
  await page.waitForTimeout(500);
  const result = await page.evaluate(async () => {
    const qa = document.querySelector("#runtime-qa");
    qa.dataset.routeReadyCount = "0";
    qa.dataset.readyRoute = "";
    const shell = document.querySelector(".workspace-shell");
    const menubar = document.querySelector(".ce-v4-menubar");
    const dock = document.querySelector(".ce-v4-dock");
    const rect = (node) => {
      const value = node.getBoundingClientRect();
      return { x: value.x, y: value.y, width: value.width, height: value.height };
    };
    const before = { menubar: rect(menubar), dock: rect(dock) };
    const starts = [];
    const cancels = [];
    const inMain = (event) => (
      event.target instanceof Element
      && Boolean(event.target.closest("#main-content"))
    );
    document.addEventListener("animationstart", (event) => {
      if (inMain(event)) starts.push(event.animationName);
    });
    document.addEventListener("animationcancel", (event) => {
      if (inMain(event)) cancels.push(event.animationName);
    });

    const matrixParts = (value) => {
      if (!value || value === "none") return { y: 0, scale: 1 };
      const Matrix = window.DOMMatrixReadOnly || window.WebKitCSSMatrix;
      const matrix = new Matrix(value);
      return { y: Number(matrix.m42 || 0), scale: Number(matrix.m11 || 1) };
    };
    const samples = [];
    location.hash = "#/workspace/board";
    const startedAt = performance.now();
    await new Promise((resolve) => {
      const sample = (now) => {
        const routePage = document.querySelector(".ce-v4-page");
        if (routePage) {
          const pageStyle = getComputedStyle(routePage);
          const mainStyle = getComputedStyle(document.querySelector("#main-content"));
          samples.push({
            at: now - startedAt,
            loading: document.documentElement.dataset.ceV4Loading === "true",
            opacity: Number(pageStyle.opacity),
            animation: pageStyle.animationName,
            mainOpacity: Number(mainStyle.opacity),
            mainTransform: mainStyle.transform,
            ...matrixParts(pageStyle.transform),
          });
        }
        if (now - startedAt < 650) requestAnimationFrame(sample);
        else resolve();
      };
      requestAnimationFrame(sample);
    });

    const after = {
      menubar: rect(document.querySelector(".ce-v4-menubar")),
      dock: rect(document.querySelector(".ce-v4-dock")),
    };
    const maxDrift = (left, right) => Math.max(
      Math.abs(left.x - right.x),
      Math.abs(left.y - right.y),
      Math.abs(left.width - right.width),
      Math.abs(left.height - right.height),
    );
    return {
      samples,
      starts,
      cancels,
      loadingSamples: samples.filter((sample) => sample.loading).length,
      routeEnterPresent: document.querySelector("#main-content").classList.contains("route-enter"),
      routeReadyCount: Number(qa.dataset.routeReadyCount || 0),
      readyRoute: qa.dataset.readyRoute,
      shellSame: document.querySelector(".workspace-shell") === shell,
      menubarSame: document.querySelector(".ce-v4-menubar") === menubar,
      dockSame: document.querySelector(".ce-v4-dock") === dock,
      menubarDrift: maxDrift(before.menubar, after.menubar),
      dockDrift: maxDrift(before.dock, after.dock),
    };
  });
  await page.close();

  const yMonotonic = result.samples.every((sample, index, rows) => (
    index === 0 || sample.y <= rows[index - 1].y + 0.5
  ));
  const opacityMonotonic = result.samples.every((sample, index, rows) => (
    index === 0 || sample.opacity >= rows[index - 1].opacity - 0.01
  ));
  const mainAnchored = result.samples.every((sample) => (
    sample.mainOpacity === 1 && sample.mainTransform === "none"
  ));
  return {
    ...result,
    firstLoading: result.samples.find((sample) => sample.loading),
    last: result.samples.at(-1),
    sampleCount: result.samples.length,
    yMonotonic,
    opacityMonotonic,
    mainAnchored,
    samples: undefined,
  };
}

async function desktopMenuResult(context) {
  const page = await context.newPage();
  await page.goto(`${baseUrl}/tests/fixtures/workspace_v43_harness.html`, { waitUntil: "load" });
  await page.waitForFunction(() => (
    window.ContentEngineDesktopV4
    && document.querySelector("[data-ce-v4-tools-menu]")
  ));
  await page.waitForTimeout(350);
  await page.click("[data-ce-v4-tools-trigger]");
  const opened = await page.evaluate(() => {
    const menu = document.querySelector("[data-ce-v4-tools-menu]");
    return {
      hidden: menu.hidden,
      expanded: document.querySelector("[data-ce-v4-tools-trigger]").getAttribute("aria-expanded"),
      routeCount: menu.querySelectorAll("[data-ce-v4-tools-route]").length,
      animation: getComputedStyle(menu).animationName,
      dialogCount: document.querySelectorAll('[role="dialog"]').length,
      backdropCount: document.querySelectorAll('[class$="-backdrop"]').length,
    };
  });

  await page.focus("[data-ce-v4-tools-trigger]");
  await page.keyboard.press("ArrowDown");
  const firstFocused = await page.evaluate(() => document.activeElement?.dataset.ceV4ToolsRoute || "");
  await page.keyboard.press("End");
  const lastFocused = await page.evaluate(() => document.activeElement?.dataset.ceV4ToolsRoute || "");
  await page.keyboard.press("Escape");
  const escaped = await page.evaluate(() => ({
    hidden: document.querySelector("[data-ce-v4-tools-menu]").hidden,
    triggerFocused: document.activeElement === document.querySelector("[data-ce-v4-tools-trigger]"),
  }));

  await page.click("[data-ce-v4-tools-trigger]");
  await page.evaluate(() => {
    [...document.querySelectorAll("[data-ce-v4-tools-route]")]
      .find((item) => item.dataset.ceV4ToolsRoute === "/workspace/work")
      .click();
  });
  await page.waitForFunction(() => location.hash === "#/workspace/work");
  await page.evaluate(() => window.ContentEngineDesktopV4.flush());
  const navigation = await page.evaluate(() => {
    const work = [...document.querySelectorAll("[data-ce-v4-tools-route]")]
      .find((item) => item.dataset.ceV4ToolsRoute === "/workspace/work");
    return {
      hidden: document.querySelector("[data-ce-v4-tools-menu]").hidden,
      current: work.getAttribute("aria-current"),
      dockRoutes: document.querySelectorAll(".ce-v4-dock [data-ce-v4-route]").length,
      academy: document.querySelectorAll(".learning-gate-shell, .academy-os-window").length,
      shellCount: document.querySelectorAll(".workspace-shell").length,
      menubarCount: document.querySelectorAll(".ce-v4-menubar").length,
      dockCount: document.querySelectorAll(".ce-v4-dock").length,
      horizontalOverflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
    };
  });

  await page.click("[data-ce-v4-tools-trigger]");
  await page.mouse.click(12, 180);
  const outsideClosed = await page.evaluate(() => document.querySelector("[data-ce-v4-tools-menu]").hidden);
  await page.close();
  return { opened, firstFocused, lastFocused, escaped, navigation, outsideClosed };
}

async function mobileMenuResult(browser) {
  const context = await browser.newContext({
    reducedMotion: "no-preference",
    viewport: { width: 320, height: 568 },
  });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/tests/fixtures/workspace_v43_harness.html`, { waitUntil: "load" });
  await page.waitForFunction(() => window.ContentEngineDesktopV4 && document.querySelector("[data-ce-v4-tools-menu]"));
  await page.click("[data-ce-v4-tools-trigger]");
  const result = await page.evaluate(() => {
    const rect = document.querySelector("[data-ce-v4-tools-menu]").getBoundingClientRect();
    return {
      rect: { x: rect.x, y: rect.y, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height },
      viewport: { width: innerWidth, height: innerHeight },
      routeCount: document.querySelectorAll("[data-ce-v4-tools-route]").length,
      horizontalOverflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
    };
  });
  await context.close();
  return result;
}

async function reducedMotionResult(browser) {
  const context = await browser.newContext({
    reducedMotion: "reduce",
    viewport: { width: 1280, height: 720 },
  });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/tests/fixtures/workspace_v43_harness.html`, { waitUntil: "load" });
  await page.waitForFunction(() => window.ContentEngineDesktopV4 && document.querySelector("[data-ce-v4-tools-menu]"));
  await page.click("[data-ce-v4-tools-trigger]");
  const result = await page.evaluate(() => {
    const menu = document.querySelector("[data-ce-v4-tools-menu]");
    return {
      animation: getComputedStyle(menu).animationName,
      transform: getComputedStyle(menu).transform,
      menubarAnimation: getComputedStyle(document.querySelector(".ce-v4-menubar")).animationName,
      dockAnimation: getComputedStyle(document.querySelector(".ce-v4-dock__glass")).animationName,
    };
  });
  await context.close();
  return result;
}

(async () => {
  const browser = await webkit.launch({ headless: true, executablePath });
  try {
    const normal = await browser.newContext({
      reducedMotion: "no-preference",
      viewport: { width: 1440, height: 900 },
    });
    const domPatch = await fixtureResult(normal, "workspace_dom_patch_harness.html");
    const finderPatch = await fixtureResult(normal, "workspace_finder_patch_harness.html");
    const scroll = await fixtureResult(normal, "workspace_scroll_order_harness.html");
    const motion = await routeMotionResult(normal);
    const menu = await desktopMenuResult(normal);
    await normal.close();
    const mobileMenu = await mobileMenuResult(browser);
    const reducedMotion = await reducedMotionResult(browser);

    const checks = {
      domPatch: domPatch.passed === "true",
      finderPatch: finderPatch.passed === "true",
      scroll: scroll.passed === "true"
        && scroll.capturedTop === "137"
        && scroll.restoredTop === "137"
        && scroll.preservedLiveTop === "83",
      motionLoading: motion.loadingSamples >= 2
        && Math.abs(motion.firstLoading.opacity - 0.74) <= 0.01
        && Math.abs(motion.firstLoading.y - 8) <= 0.6
        && Math.abs(motion.firstLoading.scale - 0.995) <= 0.002,
      motionSingle: [...new Set(motion.starts)].join(",") === "ce-v4-route-enter"
        && !motion.cancels.includes("ce-v4-content-reveal"),
      motionTrajectory: motion.yMonotonic
        && motion.opacityMonotonic
        && motion.mainAnchored
        && Math.abs(motion.last.opacity - 1) <= 0.01
        && Math.abs(motion.last.y) <= 0.1,
      motionCleanup: !motion.routeEnterPresent
        && motion.routeReadyCount === 1
        && motion.readyRoute === "/workspace/board",
      motionIdentity: motion.shellSame
        && motion.menubarSame
        && motion.dockSame
        && motion.menubarDrift <= 0.5
        && motion.dockDrift <= 0.5,
      menuOpen: !menu.opened.hidden
        && menu.opened.expanded === "true"
        && menu.opened.routeCount === 7
        && menu.opened.animation === "ce-v4-tools-menu-enter"
        && menu.opened.dialogCount === 0
        && menu.opened.backdropCount === 0,
      menuKeyboard: menu.firstFocused === "/workspace/tasks"
        && menu.lastFocused === "/workspace/team"
        && menu.escaped.hidden
        && menu.escaped.triggerFocused,
      menuNavigation: menu.navigation.hidden
        && menu.navigation.current === "page"
        && menu.navigation.dockRoutes === 6
        && menu.navigation.academy === 0
        && menu.navigation.shellCount === 1
        && menu.navigation.menubarCount === 1
        && menu.navigation.dockCount === 1
        && menu.navigation.horizontalOverflow === 0
        && menu.outsideClosed,
      menuMobile: mobileMenu.routeCount === 7
        && mobileMenu.rect.x >= 7
        && mobileMenu.rect.right <= 313
        && mobileMenu.horizontalOverflow === 0,
      reducedMotion: reducedMotion.animation === "none"
        && reducedMotion.transform === "none"
        && reducedMotion.menubarAnimation === "none"
        && reducedMotion.dockAnimation === "none",
    };
    const passed = Object.values(checks).every(Boolean);
    console.log(JSON.stringify({
      passed,
      checks,
      domPatch,
      finderPatch,
      scroll,
      motion,
      menu,
      mobileMenu,
      reducedMotion,
    }, null, 2));
    if (!passed) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});
