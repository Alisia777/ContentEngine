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
    const flowbar = document.querySelector(".ce-v4-flowbar");
    const dock = document.querySelector(".ce-v4-dock");
    const rect = (node) => {
      const value = node.getBoundingClientRect();
      return { x: value.x, y: value.y, width: value.width, height: value.height };
    };
    const before = { menubar: rect(menubar), flowbar: rect(flowbar), dock: rect(dock) };
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
      flowbar: rect(document.querySelector(".ce-v4-flowbar")),
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
      flowbarSame: document.querySelector(".ce-v4-flowbar") === flowbar,
      dockSame: document.querySelector(".ce-v4-dock") === dock,
      menubarDrift: maxDrift(before.menubar, after.menubar),
      flowbarDrift: maxDrift(before.flowbar, after.flowbar),
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
      .find((item) => item.dataset.ceV4ToolsRoute === "/workspace/feedback")
      .click();
  });
  await page.waitForFunction(() => location.hash === "#/workspace/feedback");
  await page.evaluate(() => window.ContentEngineDesktopV4.flush());
  const navigation = await page.evaluate(() => {
    const feedback = [...document.querySelectorAll("[data-ce-v4-tools-route]")]
      .find((item) => item.dataset.ceV4ToolsRoute === "/workspace/feedback");
    return {
      hidden: document.querySelector("[data-ce-v4-tools-menu]").hidden,
      current: feedback.getAttribute("aria-current"),
      dockRoutes: document.querySelectorAll(".ce-v4-dock [data-ce-v4-route]").length,
      dockLabels: [...document.querySelectorAll(".ce-v4-dock__label")].map((item) => item.textContent),
      flowbarRoutes: document.querySelectorAll("[data-ce-v4-flow-route]").length,
      flowbarCount: document.querySelectorAll(".ce-v4-flowbar").length,
      academy: document.querySelectorAll(".learning-gate-shell, .academy-os-window").length,
      shellCount: document.querySelectorAll(".workspace-shell").length,
      menubarCount: document.querySelectorAll(".ce-v4-menubar").length,
      dockCount: document.querySelectorAll(".ce-v4-dock").length,
      horizontalOverflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
    };
  });

  await page.evaluate(() => { location.hash = "#/workspace/tasks"; });
  await page.waitForFunction(() => location.hash === "#/workspace/tasks");
  await page.evaluate(() => window.ContentEngineDesktopV4.flush());
  const alias = await page.evaluate(() => ({
    dock: document.querySelector(".ce-v4-dock__item.is-active")?.dataset.ceV4Route || "",
    flowbar: document.querySelector(".ce-v4-flowbar__link.is-active")?.dataset.ceV4FlowRoute || "",
  }));

  await page.click('[data-ce-v4-flow-route="/workspace/review"]');
  await page.waitForFunction(() => location.hash === "#/workspace/review");
  await page.evaluate(() => window.ContentEngineDesktopV4.flush());
  const switched = await page.evaluate(() => ({
    route: location.hash,
    current: document.querySelector('[data-ce-v4-flow-route="/workspace/review"]')?.getAttribute("aria-current"),
  }));

  await page.click("[data-ce-v4-tools-trigger]");
  await page.mouse.click(12, 180);
  const outsideClosed = await page.evaluate(() => document.querySelector("[data-ce-v4-tools-menu]").hidden);
  await page.close();
  return { opened, firstFocused, lastFocused, escaped, navigation, alias, switched, outsideClosed };
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
    const flowbar = document.querySelector(".ce-v4-flowbar").getBoundingClientRect();
    const dock = document.querySelector(".ce-v4-dock").getBoundingClientRect();
    return {
      rect: { x: rect.x, y: rect.y, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height },
      flowbar: { x: flowbar.x, right: flowbar.right, width: flowbar.width },
      dock: { x: dock.x, right: dock.right, width: dock.width },
      viewport: { width: innerWidth, height: innerHeight },
      routeCount: document.querySelectorAll("[data-ce-v4-tools-route]").length,
      flowbarRoutes: document.querySelectorAll("[data-ce-v4-flow-route]").length,
      dockLabels: document.querySelectorAll(".ce-v4-dock__label").length,
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
    const flowLink = document.querySelector(".ce-v4-flowbar__link.is-active");
    return {
      animation: getComputedStyle(menu).animationName,
      transform: getComputedStyle(menu).transform,
      menubarAnimation: getComputedStyle(document.querySelector(".ce-v4-menubar")).animationName,
      dockAnimation: getComputedStyle(document.querySelector(".ce-v4-dock__glass")).animationName,
      flowTransition: getComputedStyle(flowLink).transitionDuration,
      flowTransform: getComputedStyle(flowLink).transform,
    };
  });
  await context.close();
  return result;
}

async function dockMagnificationResult(browser) {
  const open = async (options = {}) => {
    const context = await browser.newContext({
      reducedMotion: "no-preference",
      viewport: { width: 1440, height: 900 },
      ...options,
    });
    const page = await context.newPage();
    await page.goto(`${baseUrl}/tests/fixtures/workspace_v43_harness.html`, { waitUntil: "load" });
    await page.waitForFunction(() => (
      window.ContentEngineDesktopV4
      && document.querySelectorAll(".ce-v4-dock [data-ce-v4-route]").length >= 5
    ));
    await page.waitForTimeout(500);
    return { context, page };
  };

  const snapshot = (page) => page.evaluate(() => {
    const rect = (node) => {
      const value = node.getBoundingClientRect();
      return { x: value.x, y: value.y, width: value.width, height: value.height };
    };
    const transformParts = (tile) => {
      const transform = getComputedStyle(tile).transform;
      if (!transform || transform === "none") return { scale: 1, y: 0 };
      const Matrix = window.DOMMatrixReadOnly || window.WebKitCSSMatrix;
      const matrix = new Matrix(transform);
      return { scale: Number(matrix.m11 || 1), y: Number(matrix.m42 || 0) };
    };
    const items = [...document.querySelectorAll(".ce-v4-dock [data-ce-v4-route]")];
    const transforms = items.map((item) => transformParts(item.querySelector(".ce-v4-dock__tile")));
    return {
      scales: transforms.map((value) => value.scale),
      translateY: transforms.map((value) => value.y),
      itemRects: items.map(rect),
      glassRect: rect(document.querySelector(".ce-v4-dock__glass")),
      menubarRect: rect(document.querySelector(".ce-v4-menubar")),
      fineHover: matchMedia("(hover: hover) and (pointer: fine)").matches,
    };
  });

  const hierarchy = (values, center = 2) => (
    values[center] > values[center - 1] + 0.02
    && values[center - 1] > values[center - 2] + 0.015
    && values[center] > values[center + 1] + 0.02
    && values[center + 1] > values[center + 2] + 0.015
  );
  const neutral = (values) => values.every((value) => Math.abs(value - 1) <= 0.01);
  const neutralY = (values) => values.every((value) => Math.abs(value) <= 0.1);
  const drift = (left, right) => Math.max(
    Math.abs(left.x - right.x),
    Math.abs(left.y - right.y),
    Math.abs(left.width - right.width),
    Math.abs(left.height - right.height),
  );
  const snapshotDrift = (before, after) => Math.max(
    drift(before.glassRect, after.glassRect),
    drift(before.menubarRect, after.menubarRect),
    ...before.itemRects.map((value, index) => drift(value, after.itemRects[index])),
  );

  const desktop = await open();
  const target = desktop.page.locator(".ce-v4-dock [data-ce-v4-route]").nth(2);
  const before = await snapshot(desktop.page);
  await target.hover();
  await desktop.page.waitForTimeout(240);
  const hovered = await snapshot(desktop.page);
  await desktop.page.mouse.move(1, 1);
  await desktop.page.waitForTimeout(240);
  await desktop.page.keyboard.press("Tab");
  await target.focus();
  const focusVisible = await target.evaluate((item) => item.matches(":focus-visible"));
  await desktop.page.waitForTimeout(240);
  const focused = await snapshot(desktop.page);
  const mixedTarget = desktop.page.locator(".ce-v4-dock [data-ce-v4-route]").nth(3);
  await mixedTarget.hover();
  await desktop.page.waitForTimeout(240);
  const mixedFocusVisible = await target.evaluate((item) => item.matches(":focus-visible"));
  const mixed = await snapshot(desktop.page);
  await desktop.page.mouse.move(1, 1);
  await desktop.page.evaluate(() => document.activeElement?.blur());
  await desktop.page.waitForTimeout(450);
  const cleaned = await snapshot(desktop.page);
  await desktop.context.close();

  const reduced = await open({ reducedMotion: "reduce" });
  const reducedTarget = reduced.page.locator(".ce-v4-dock [data-ce-v4-route]").nth(2);
  await reducedTarget.hover();
  await reduced.page.waitForTimeout(80);
  const reducedHover = await snapshot(reduced.page);
  await reduced.page.mouse.move(1, 1);
  await reduced.page.keyboard.press("Tab");
  await reducedTarget.focus();
  const reducedFocusVisible = await reducedTarget.evaluate((item) => item.matches(":focus-visible"));
  await reduced.page.waitForTimeout(80);
  const reducedFocus = await snapshot(reduced.page);
  await reduced.context.close();

  const touch = await open({ hasTouch: true });
  const touchTarget = touch.page.locator(".ce-v4-dock [data-ce-v4-route]").nth(2);
  await touchTarget.dispatchEvent("pointerover", { bubbles: true, pointerType: "touch" });
  await touchTarget.dispatchEvent("pointermove", { bubbles: true, pointerType: "touch" });
  await touch.page.waitForTimeout(80);
  const touchSnapshot = await snapshot(touch.page);
  await touch.context.close();

  return {
    focusVisible,
    mixedFocusVisible,
    reducedFocusVisible,
    hoverHierarchy: before.fineHover && hierarchy(hovered.scales),
    focusHierarchy: focusVisible && hierarchy(focused.scales),
    mixedHoverPriority: mixedFocusVisible && hierarchy(mixed.scales, 3),
    hoverLift: hovered.translateY[2] < hovered.translateY[1]
      && hovered.translateY[1] < hovered.translateY[0],
    focusLift: focused.translateY[2] < focused.translateY[1]
      && focused.translateY[1] < focused.translateY[0],
    rectDrift: Math.max(
      snapshotDrift(before, hovered),
      snapshotDrift(before, focused),
      snapshotDrift(before, mixed),
      snapshotDrift(before, cleaned),
    ),
    cleanup: neutral(cleaned.scales) && neutralY(cleaned.translateY),
    reducedMotionNone: reducedFocusVisible
      && neutral(reducedHover.scales)
      && neutralY(reducedHover.translateY)
      && neutral(reducedFocus.scales)
      && neutralY(reducedFocus.translateY),
    touchNone: !touchSnapshot.fineHover
      && neutral(touchSnapshot.scales)
      && neutralY(touchSnapshot.translateY),
    before,
    hovered,
    focused,
    mixed,
    cleaned,
    reducedHover,
    reducedFocus,
    touchSnapshot,
  };
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
    const dockMagnification = await dockMagnificationResult(browser);

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
        && motion.flowbarSame
        && motion.dockSame
        && motion.menubarDrift <= 0.5
        && motion.flowbarDrift <= 0.5
        && motion.dockDrift <= 0.5,
      menuOpen: !menu.opened.hidden
        && menu.opened.expanded === "true"
        && menu.opened.routeCount === 3
        && menu.opened.animation === "ce-v4-tools-menu-enter"
        && menu.opened.dialogCount === 0
        && menu.opened.backdropCount === 0,
      menuKeyboard: menu.firstFocused === "/workspace/research"
        && menu.lastFocused === "/workspace/feedback"
        && menu.escaped.hidden
        && menu.escaped.triggerFocused,
      menuNavigation: menu.navigation.hidden
        && menu.navigation.current === "page"
        && menu.navigation.dockRoutes === 6
        && menu.navigation.flowbarRoutes === 6
        && menu.navigation.flowbarCount === 1
        && menu.navigation.dockLabels.join("|") === "Сегодня|Файлы|Создать|Проверить|Опубликовать|Результаты|Корзина"
        && menu.navigation.academy === 0
        && menu.navigation.shellCount === 1
        && menu.navigation.menubarCount === 1
        && menu.navigation.dockCount === 1
        && menu.navigation.horizontalOverflow === 0
        && menu.alias.dock === "/workspace/home"
        && menu.alias.flowbar === "/workspace/home"
        && menu.switched.route === "#/workspace/review"
        && menu.switched.current === "step"
        && menu.outsideClosed,
      menuMobile: mobileMenu.routeCount === 3
        && mobileMenu.flowbarRoutes === 6
        && mobileMenu.dockLabels === 7
        && mobileMenu.rect.x >= 7
        && mobileMenu.rect.right <= 313
        && mobileMenu.flowbar.x >= 0
        && mobileMenu.flowbar.right <= 320
        && mobileMenu.dock.x >= 0
        && mobileMenu.dock.right <= 320
        && mobileMenu.horizontalOverflow === 0,
      reducedMotion: reducedMotion.animation === "none"
        && reducedMotion.transform === "none"
        && reducedMotion.menubarAnimation === "none"
        && reducedMotion.dockAnimation === "none"
        && reducedMotion.flowTransition === "0s"
        && reducedMotion.flowTransform === "none",
      dockMagnification: dockMagnification.hoverHierarchy
        && dockMagnification.focusHierarchy
        && dockMagnification.mixedHoverPriority
        && dockMagnification.hoverLift
        && dockMagnification.focusLift
        && dockMagnification.rectDrift <= 0.5
        && dockMagnification.cleanup
        && dockMagnification.reducedMotionNone
        && dockMagnification.touchNone,
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
      dockMagnification,
    }, null, 2));
    if (!passed) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});
