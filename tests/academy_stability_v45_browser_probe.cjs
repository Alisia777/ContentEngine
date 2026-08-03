const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");

const [playwrightPath, browserName, executablePath, rootDirectory] = process.argv.slice(2);
if (!playwrightPath || !browserName || !executablePath || !rootDirectory) {
  throw new Error(
    "Usage: node academy_stability_v45_browser_probe.cjs <playwright> <chromium|webkit> <executable> <repo-root>",
  );
}

const playwright = require(playwrightPath);
const browserType = playwright[browserName];
if (!browserType) throw new Error(`Unsupported browser: ${browserName}`);

async function startServer() {
  const root = path.resolve(rootDirectory);
  const server = http.createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
      const target = path.resolve(root, `.${pathname}`);
      if (target !== root && !target.startsWith(`${root}${path.sep}`)) {
        response.writeHead(403).end("Forbidden");
        return;
      }
      const body = await fs.readFile(target);
      const type = target.endsWith(".js") ? "text/javascript; charset=utf-8" : "text/html; charset=utf-8";
      response.writeHead(200, { "content-type": type, "cache-control": "no-store" });
      response.end(body);
    } catch {
      response.writeHead(404).end("Not found");
    }
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  return { server, baseUrl: `http://127.0.0.1:${address.port}` };
}

(async () => {
  const { server, baseUrl } = await startServer();
  let browser = null;
  try {
    browser = await browserType.launch({ headless: true, executablePath });
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    await page.goto(
      `${baseUrl}/tests/fixtures/academy_practical_file_v45_harness.html`,
      { waitUntil: "load" },
    );
    await page.waitForFunction(() => typeof window.runAcademyPracticalPatch === "function");
    await page.setInputFiles("#practical-file", {
      name: "academy-practical.mp4",
      mimeType: "video/mp4",
      buffer: Buffer.from("academy-practical-file"),
    });
    const checks = await page.evaluate(() => window.runAcademyPracticalPatch());
    const passed = Object.values(checks).every(Boolean);
    process.stdout.write(`${JSON.stringify({ browser: browserName, passed, checks })}\n`);
    if (!passed) process.exitCode = 1;
  } finally {
    await browser?.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
