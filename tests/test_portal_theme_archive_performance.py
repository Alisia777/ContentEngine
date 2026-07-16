import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
EXPERIENCE = (ROOT / "web" / "app" / "portal-experience.js").read_text(encoding="utf-8")
EXPERIENCE_CSS = (ROOT / "web" / "app" / "portal-experience.css").read_text(encoding="utf-8")
THEME_BOOTSTRAP = (ROOT / "web" / "app" / "theme-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web" / "app" / "index.html").read_text(encoding="utf-8")
BRAND_ASSETS = ROOT / "web" / "app" / "assets" / "brand"


def _run_module_javascript(module_source: str, body: str, *, timeout: int = 10):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable portal contracts")

    with tempfile.TemporaryDirectory() as temporary_directory:
        module_directory = Path(temporary_directory)
        (module_directory / "subject.mjs").write_text(module_source, encoding="utf-8")
        (module_directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const payload = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(payload));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=module_directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )

    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_four_themes_normalize_and_storage_failures_never_block_the_portal() -> None:
    result = _run_module_javascript(
        EXPERIENCE,
        """
        const writes = [];
        const readable = { getItem: () => "BORDEAUX" };
        const writable = { setItem: (key, value) => writes.push([key, value]) };
        const readFailure = { getItem: () => { throw new Error("blocked"); } };
        const writeFailure = { setItem: () => { throw new Error("blocked"); } };
        Object.defineProperty(globalThis, "localStorage", {
          configurable: true,
          get: () => { throw new Error("getter blocked"); },
        });
        const blockedGlobalRead = subject.readPortalThemePreference();
        const blockedGlobalWrite = subject.persistPortalThemePreference("sapphire");
        delete globalThis.localStorage;

        return {
          themes: subject.PORTAL_THEMES.map((theme) => theme.id),
          labels: subject.PORTAL_THEMES.map((theme) => theme.label),
          frozen: Object.isFrozen(subject.PORTAL_THEMES)
            && subject.PORTAL_THEMES.every((theme) => Object.isFrozen(theme)),
          normalized: [
            subject.normalizePortalTheme(" emerald "),
            subject.normalizePortalTheme("BORDEAUX"),
            subject.normalizePortalTheme("Sapphire"),
            subject.normalizePortalTheme(" ALTEA-DARK "),
          ],
          fallback: [
            subject.normalizePortalTheme("unknown"),
            subject.normalizePortalTheme(null),
          ],
          read: subject.readPortalThemePreference(readable),
          readFailure: subject.readPortalThemePreference(readFailure),
          persisted: subject.persistPortalThemePreference("sapphire", writable),
          persistedFallback: subject.persistPortalThemePreference("unsafe", writable),
          writeFailure: subject.persistPortalThemePreference("bordeaux", writeFailure),
          blockedGlobalRead,
          blockedGlobalWrite,
          writes,
        };
        """,
    )

    assert result == {
        "themes": ["emerald", "bordeaux", "sapphire", "altea-dark"],
        "labels": ["Изумруд", "Бордо", "Сапфир", "Тёмная"],
        "frozen": True,
        "normalized": ["emerald", "bordeaux", "sapphire", "altea-dark"],
        "fallback": ["emerald", "emerald"],
        "read": "bordeaux",
        "readFailure": "emerald",
        "persisted": "sapphire",
        "persistedFallback": "emerald",
        "writeFailure": "bordeaux",
        "blockedGlobalRead": "emerald",
        "blockedGlobalWrite": "sapphire",
        "writes": [
            ["contentengine.portal-theme.v1", "sapphire"],
            ["contentengine.portal-theme.v1", "emerald"],
        ],
    }


def test_generation_filters_cover_all_period_status_and_search_modes() -> None:
    result = _run_module_javascript(
        EXPERIENCE,
        """
        const now = new Date("2026-07-15T12:00:00Z").getTime();
        const items = [
          { id: "week", status: "queued", sku: "WB-100", product_name: "Кровавый пилинг", created_at: "2026-07-14T12:00:00Z" },
          { id: "four", status: "succeeded", sku: "WB-200", product_name: "Протеин", created_at: "2026-06-30T12:00:00Z" },
          { id: "twelve", status: "failed", sku: "WB-300", product_name: "Крем", created_at: "2026-05-20T12:00:00Z" },
          { id: "all", status: "completed", sku: "WB-400", product_name: "Сыворотка", created_at: "2026-02-01T12:00:00Z" },
        ];
        const ids = (filters) => subject.filterGenerationBatches(items, filters, now).map((item) => item.id);
        const normalized = subject.normalizeGenerationFilters({
          period: "invalid",
          status: "invalid",
          query: `  ${"x".repeat(140)}  `,
          visible: 999,
        });
        return {
          periods: {
            week: ids({ period: "week" }),
            four: ids({ period: "4w" }),
            twelve: ids({ period: "12w" }),
            all: ids({ period: "all" }),
          },
          statuses: {
            active: ids({ period: "all", status: "active" }),
            ready: ids({ period: "all", status: "ready" }),
            issue: ids({ period: "all", status: "issue" }),
          },
          search: {
            product: ids({ period: "all", query: "кРОВавый" }),
            sku: ids({ period: "all", query: "wb-300" }),
            missing: ids({ period: "all", query: "нет-такого" }),
          },
          normalized,
        };
        """,
    )

    assert result["periods"] == {
        "week": ["week"],
        "four": ["week", "four"],
        "twelve": ["week", "four", "twelve"],
        "all": ["week", "four", "twelve", "all"],
    }
    assert result["statuses"] == {
        "active": ["week"],
        "ready": ["four", "all"],
        "issue": ["twelve"],
    }
    assert result["search"] == {
        "product": ["week"],
        "sku": ["twelve"],
        "missing": [],
    }
    assert result["normalized"] == {
        "period": "4w",
        "status": "all",
        "query": "x" * 120,
        "visible": 200,
    }


def test_generation_page_merge_is_stable_deduplicated_and_cursor_safe() -> None:
    result = _run_module_javascript(
        EXPERIENCE,
        """
        const current = [
          { id: "a", version: "current" },
          { id: "b", version: "current" },
        ];
        const incoming = [
          { id: "b", version: "incoming" },
          { id: "c", version: "incoming" },
          { public_id: "d", version: "incoming" },
          { version: "missing-id" },
        ];
        const currentSnapshot = JSON.stringify(current);
        const incomingSnapshot = JSON.stringify(incoming);
        const merged = subject.mergeGenerationPages(current, incoming);
        const validCursor = subject.generationArchiveCursor([
          { id: "cursor", _cursor: { at: "2026-07-15T10:00:00Z", id: "job-id" } },
        ]);
        return {
          ids: merged.map((item) => item.id || item.public_id),
          bVersion: merged.find((item) => item.id === "b")?.version,
          unchanged: currentSnapshot === JSON.stringify(current) && incomingSnapshot === JSON.stringify(incoming),
          validCursor,
          invalidCursor: subject.generationArchiveCursor([{ id: "missing" }]),
          emptyCursor: subject.generationArchiveCursor([]),
        };
        """,
    )

    assert result == {
        "ids": ["a", "b", "c", "d"],
        "bVersion": "current",
        "unchanged": True,
        "validCursor": {
            "generation_batches": {"at": "2026-07-15T10:00:00Z", "id": "job-id"}
        },
        "invalidCursor": None,
        "emptyCursor": None,
    }


def test_ten_thousand_archive_items_filter_and_merge_in_under_one_second() -> None:
    result = _run_module_javascript(
        EXPERIENCE,
        """
        const items = Array.from({ length: 10_000 }, (_, index) => ({
          id: `job-${index}`,
          status: index % 3 === 0 ? "processing" : index % 3 === 1 ? "succeeded" : "failed",
          sku: `SKU-${String(index).padStart(5, "0")}`,
          product_name: `Product ${index}`,
          created_at: "2026-07-15T10:00:00Z",
        }));
        const started = performance.now();
        const filtered = subject.filterGenerationBatches(items, {
          period: "all",
          status: "all",
          query: "SKU-09999",
        });
        const merged = subject.mergeGenerationPages(items.slice(0, 7_500), items.slice(5_000));
        const elapsed = performance.now() - started;
        return { elapsed, filtered: filtered.length, filteredId: filtered[0]?.id, merged: merged.length };
        """,
    )

    assert result["filtered"] == 1
    assert result["filteredId"] == "job-9999"
    assert result["merged"] == 10_000
    assert result["elapsed"] < 1_000


def test_archive_dom_window_is_twenty_rows_with_a_hard_two_hundred_row_cap() -> None:
    runtime = _run_module_javascript(
        EXPERIENCE,
        """
        return {
          pageSize: subject.GENERATION_ARCHIVE_PAGE_SIZE,
          step: subject.GENERATION_VISIBLE_STEP,
          cap: subject.GENERATION_VISIBLE_CAP,
          visible: [undefined, 19, 20, 40, 199, 999].map((value) => (
            subject.normalizeGenerationFilters({ period: "all", visible: value }).visible
          )),
        };
        """,
    )

    assert runtime == {
        "pageSize": 50,
        "step": 20,
        "cap": 200,
        "visible": [20, 20, 20, 40, 199, 200],
    }
    render_generation = _between(APP, "function renderGenerationSection", "function generationArchiveMarkup")
    archive_markup = _between(APP, "function generationArchiveMarkup", "function submitGenerationArchiveFilters")
    click_actions = _between(APP, 'if (action === "reset-generation-filters")', 'if (action === "reload-page")')
    assert "filteredBatches.slice(0, archiveFilters.visible)" in render_generation
    assert "filters.visible < GENERATION_VISIBLE_CAP" in archive_markup
    assert "filters.visible >= GENERATION_VISIBLE_CAP" in archive_markup
    assert "visible: GENERATION_VISIBLE_STEP" in click_actions
    assert "+ GENERATION_VISIBLE_STEP" in click_actions


def test_generation_archive_avoids_eager_video_work_and_caps_status_polling() -> None:
    polling = _between(APP, "async function runRealGenerationPolling", "function requestRealGenerationStatus")
    result = _run_module_javascript(
        EXPERIENCE,
        """
        const jobs = Array.from({ length: 7 }, (_, index) => `job-${index + 1}`);
        const first = subject.boundedRoundRobinWindow(jobs, 0, 4);
        const second = subject.boundedRoundRobinWindow(jobs, first.nextCursor, 4);
        const third = subject.boundedRoundRobinWindow(jobs, second.nextCursor, 4);
        return {
          first,
          second,
          third,
          empty: subject.boundedRoundRobinWindow([], 12, 4),
        };
        """,
    )
    assert "localStorage" not in polling
    assert "primeCompletedGenerationResults" not in APP
    assert "boundedRoundRobinWindow" in polling
    assert ".slice(0, 4)" not in polling
    assert result == {
        "first": {
            "items": ["job-1", "job-2", "job-3", "job-4"],
            "nextCursor": 4,
        },
        "second": {
            "items": ["job-5", "job-6", "job-7", "job-1"],
            "nextCursor": 1,
        },
        "third": {
            "items": ["job-2", "job-3", "job-4", "job-5"],
            "nextCursor": 5,
        },
        "empty": {"items": [], "nextCursor": 0},
    }
    assert 'preload="none"' in APP
    assert APP.count('preload="none"') >= 2
    assert 'preload="metadata"' not in APP


def test_workspace_api_scopes_pagination_and_rejects_bad_options_before_rpc() -> None:
    result = _run_module_javascript(
        API,
        """
        const calls = [];
        const rpcClient = {
          rpc: async (functionName, args) => {
            calls.push({ functionName, args });
            return { data: { ok: true }, error: null };
          },
        };
        const supabase = { schema: () => rpcClient };
        const api = new subject.CreatorApi(supabase, {
          RPC_SCHEMA: "public",
          STORAGE_BUCKET: "creator-private",
        });
        api.organizationId = "organization-1";
        const cursor = {
          generation_batches: { at: "2026-07-15T10:00:00Z", id: "batch-1" },
        };
        await api.workspaceSection("generation", { page_size: 50, cursor });

        const errorCode = (operation) => {
          try {
            operation();
            return null;
          } catch (error) {
            return error.code;
          }
        };
        const beforeInvalid = calls.length;
        const invalid = {
          zero: errorCode(() => api.workspaceSection("generation", { page_size: 0 })),
          high: errorCode(() => api.workspaceSection("generation", { page_size: 101 })),
          fraction: errorCode(() => api.workspaceSection("generation", { page_size: 1.5 })),
          nullCursor: errorCode(() => api.workspaceSection("generation", { cursor: null })),
          arrayCursor: errorCode(() => api.workspaceSection("generation", { cursor: [] })),
        };
        return { calls, beforeInvalid, afterInvalid: calls.length, invalid };
        """,
    )

    assert result["beforeInvalid"] == 1
    assert result["afterInvalid"] == 1
    assert result["invalid"] == {
        "zero": "workspace_page_size_invalid",
        "high": "workspace_page_size_invalid",
        "fraction": "workspace_page_size_invalid",
        "nullCursor": "workspace_cursor_invalid",
        "arrayCursor": "workspace_cursor_invalid",
    }
    assert result["calls"] == [
        {
            "functionName": "creator_workspace_section",
            "args": {
                "p_payload": {
                    "section": "generation",
                    "page_size": 50,
                    "cursor": {
                        "generation_batches": {
                            "at": "2026-07-15T10:00:00Z",
                            "id": "batch-1",
                        }
                    },
                    "organization_id": "organization-1",
                }
            },
        }
    ]


def test_theme_archive_motion_and_brand_asset_hooks_are_wired_into_the_spa() -> None:
    assert re.search(r'from "\./portal-experience\.js\?v=\d+\.\d+";', APP)
    for hook in (
        "PORTAL_THEMES",
        "themePickerMarkup",
        'data-action="set-portal-theme"',
        "applyPortalTheme",
        "brandAtmosphereMarkup",
        'id="generation-archive-filter-form"',
        'data-action="show-more-generation"',
        'data-action="load-more-generation"',
        "generationArchiveCursor",
        "mergeGenerationPages",
    ):
        assert hook in APP

    for theme in ("emerald", "bordeaux", "sapphire", "altea-dark"):
        assert f':root[data-portal-theme="{theme}"]' in EXPERIENCE_CSS
    assert 'color-scheme: dark' in EXPERIENCE_CSS
    assert '"altea-dark"' in THEME_BOOTSTRAP
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr))' in EXPERIENCE_CSS
    for hook in (
        ".portal-theme-picker",
        ".generation-archive-toolbar",
        ".generation-archive-actions",
        ".brand-atmosphere",
        "@media (prefers-reduced-motion: no-preference)",
        "@media (prefers-reduced-motion: reduce)",
        'url("./assets/brand/altea_flower.svg")',
        'url("./assets/brand/petal.svg")',
    ):
        assert hook in EXPERIENCE_CSS

    assert 'data-portal-theme="emerald"' in INDEX
    assert re.search(r'<script src="\./theme-bootstrap\.js\?v=\d+\.\d+"></script>', INDEX)
    assert re.search(r'<link rel="stylesheet" href="\./portal-experience\.css\?v=\d+\.\d+"', INDEX)
    assert "try" in THEME_BOOTSTRAP and "catch" in THEME_BOOTSTRAP

    for filename in ("logo_mark.svg", "altea_flower.svg", "petal.svg"):
        asset = BRAND_ASSETS / filename
        assert asset.is_file()
        source = asset.read_text(encoding="utf-8")
        assert source.lstrip().startswith("<svg")
        assert "<script" not in source.lower()
    assert 'src="./assets/brand/logo_mark.svg"' in APP
