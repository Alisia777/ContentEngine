const [playwrightPath, executablePath, baseUrl] = process.argv.slice(2);

if (!playwrightPath || !executablePath || !baseUrl) {
  console.error("usage: node webkit_file_selection_v45_probe.cjs <playwright-path> <webkit-executable> <base-url>");
  process.exit(2);
}

const { webkit } = require(playwrightPath);

(async () => {
  const browser = await webkit.launch({ executablePath, headless: true });
  const page = await browser.newPage();
  try {
    await page.goto(`${baseUrl}/tests/fixtures/workspace_webkit_file_selection_v45_harness.html`, {
      waitUntil: "load",
    });
    await page.waitForFunction(() => typeof window.runFileSelectionPatch === "function");
    await page.setInputFiles("#upload-file", {
      name: "webkit-selected-v45.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("contentengine-webkit-v45", "utf8"),
    });
    await page.focus("#upload-file");

    const before = await page.locator("#upload-file").evaluate(async (input) => ({
      count: input.files?.length || 0,
      name: input.files?.[0]?.name || "",
      text: input.files?.[0] ? await input.files[0].text() : "",
      focused: document.activeElement === input,
    }));

    const patched = await page.evaluate(() => window.runFileSelectionPatch());
    const after = await page.locator("#upload-file").evaluate(async (input) => {
      input.dispatchEvent(new Event("contentengine:file-probe"));
      return {
        sameNode: input === window.originalFileInput,
        count: input.files?.length || 0,
        name: input.files?.[0]?.name || "",
        text: input.files?.[0] ? await input.files[0].text() : "",
        focused: document.activeElement === input,
        listenerCalls: window.fileListenerCalls,
        status: document.querySelector("#upload-status")?.textContent || "",
      };
    });

    const checks = {
      patched: patched === true,
      initialSelection: before.count === 1
        && before.name === "webkit-selected-v45.txt"
        && before.text === "contentengine-webkit-v45",
      initialFocus: before.focused === true,
      nodeIdentity: after.sameNode === true,
      selectionPreserved: after.count === 1
        && after.name === "webkit-selected-v45.txt"
        && after.text === "contentengine-webkit-v45",
      focusPreserved: after.focused === true,
      listenerPreserved: after.listenerCalls === 1,
      markupUpdated: after.status === "После обновления",
    };
    const result = { passed: Object.values(checks).every(Boolean), checks, before, after };
    console.log(JSON.stringify(result, null, 2));
    if (!result.passed) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
