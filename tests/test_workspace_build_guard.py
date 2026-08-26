from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP_INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
ROOT_INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-build-guard.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-build-guard.css").read_text(encoding="utf-8")
MANIFEST = json.loads((APP_DIR / "build.json").read_text(encoding="utf-8"))
DESKTOP_ASSET_BUILD = "20260826.rebuild-clean.18"
APP_SCRIPT = (APP_DIR / "app.js").read_text(encoding="utf-8")
LOADER = (APP_DIR / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
INTAKE_ENTRY = (APP_DIR / "generation-strategy-intake-v2.js").read_text(
    encoding="utf-8"
)
INTAKE = (APP_DIR / "generation-strategy-intake-v4.js").read_text(
    encoding="utf-8"
)
GUIDED = (APP_DIR / "workspace-os-v4-generation-guided.js").read_text(
    encoding="utf-8"
)
QUEUE = (APP_DIR / "generation-strategy-queue.js").read_text(encoding="utf-8")


def test_build_id_is_consistent_across_entrypoints() -> None:
    build_id = MANIFEST["id"]
    assert build_id == "20260826.rebuild-clean.18"
    assert f'content="{build_id}"' in APP_INDEX
    assert f'content="{build_id}"' in ROOT_INDEX
    assert f'const CURRENT_BUILD = "{build_id}"' in SCRIPT
    assert MANIFEST["label"] == (
        "ContentEngine Desktop v4.41 · Copy engines 43"
    )
    assert MANIFEST["released_at"] == "2026-08-23"
    assert 'const BUILD_BADGE = "Desktop · 21.08.17"' in SCRIPT


def test_desktop_flag_loader_runs_before_app_and_build_guard_runs_last() -> None:
    build_id = MANIFEST["id"]
    shell_cache_key = DESKTOP_ASSET_BUILD
    loader_cache_key = DESKTOP_ASSET_BUILD
    app_cache_key = build_id
    assert (
        f'<link rel="stylesheet" href="./workspace-os-v4.css?v={shell_cache_key}" />'
        in APP_INDEX
    )
    assert (
        f'<script type="module" src="./workspace-os-v4-loader.js?v={loader_cache_key}"></script>'
        in APP_INDEX
    )
    assert (
        f'<script type="module" src="./app.js?v={app_cache_key}"></script>'
        in APP_INDEX
    )
    assert f'./workspace-build-guard.css?v={build_id}' in APP_INDEX
    assert f'./workspace-build-guard.js?v={build_id}' in APP_INDEX
    assert APP_INDEX.index(
        f'./workspace-os-v4.css?v={shell_cache_key}'
    ) < APP_INDEX.index('./workspace-build-guard.css')
    assert APP_INDEX.index(
        f'./workspace-os-v4-loader.js?v={loader_cache_key}'
    ) < APP_INDEX.index(f'./app.js?v={app_cache_key}')
    assert APP_INDEX.index('./app.js') < APP_INDEX.index(
        f'./workspace-build-guard.js?v={build_id}'
    )
    assert "window.CONTENTENGINE_DESKTOP_V4 = true" in (
        APP_DIR / "workspace-os-v4-loader.js"
    ).read_text(encoding="utf-8")


def test_provider_reconciliation_release_busts_the_complete_changed_module_path() -> None:
    build_id = MANIFEST["id"]
    versioned = f"?v={build_id}"

    for asset in ("app.js", "workspace-build-guard.js", "workspace-build-guard.css"):
        assert f"./{asset}{versioned}" in APP_INDEX

    assert f"./workspace-os-v4-loader.js?v={DESKTOP_ASSET_BUILD}" in APP_INDEX
    assert f"./workspace-os-v4.css?v={DESKTOP_ASSET_BUILD}" in APP_INDEX
    assert f"./workspace-ui-reference-v1.css?v={DESKTOP_ASSET_BUILD}" in APP_INDEX

    for asset in (
        "supabase-api.js",
        "generation-spend-view.js",
        "generation-strategy-runtime.js",
        "generation-strategy-queue.js",
    ):
        assert f'"./{asset}{versioned}"' in APP_SCRIPT

    assert f'GENERATION_HOTFIX_BUILD = "{build_id}"' in LOADER
    assert f'GENERATION_INTAKE_BUILD = "{build_id}"' in LOADER
    assert f'DESKTOP_CORE_BUILD = "{DESKTOP_ASSET_BUILD}"' in LOADER
    assert 'workspace-os-v4.js?v=${DESKTOP_CORE_BUILD}' in LOADER
    assert f'"./generation-strategy-intake-v4.js{versioned}"' in INTAKE_ENTRY
    assert f'"./generation-strategy-intake-v4.css{versioned}"' in INTAKE
    assert f'"./generation-strategy-view.js{versioned}"' in GUIDED
    assert f'"./generation-strategy-runtime.js{versioned}"' in QUEUE

    assert "20260816.adaptive.4" not in APP_INDEX
    assert "20260814.os4.41.strategy-interactions-1" not in APP_SCRIPT


def test_guard_checks_only_the_same_origin_static_manifest() -> None:
    for marker in (
        'new URL("./build.json", import.meta.url)',
        'cache: "no-store"',
        'credentials: "same-origin"',
        'url.searchParams.set("t", String(Date.now()))',
        'url.searchParams.set("build", id)',
        'window.location.replace(url.toString())',
        'window.CONTENTENGINE_BUILD',
    ):
        assert marker in SCRIPT
    assert "supabase" not in SCRIPT.lower()
    assert "/api/" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert "localStorage" not in SCRIPT
    assert "sessionStorage" not in SCRIPT


def test_build_guard_has_accessible_update_and_manual_status() -> None:
    for marker in (
        'role", "status"',
        'aria-live", "polite"',
        'Рабочее место обновилось',
        'открытые серверные задачи продолжат работу',
        'ContentEngineBuildGuard',
        '.ce-build-update',
        '.ce-build-pill',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in SCRIPT or marker in CSS


def test_build_guard_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-build-guard.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_build_guard_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")


def test_update_banner_survives_v4_windows_and_reloads_itself_when_idle() -> None:
    """Владелица сутки работала на устаревшей сборке и не видела баннер: окно
    v4 (слои до ~900) перекрывало z-index 400. Баннер обязан быть поверх
    всего, а свободное от ввода рабочее место — перезапускаться само."""
    assert "z-index: 2147482000;" in CSS
    assert "function interfaceIsBusy()" in SCRIPT
    assert "'form[data-dirty], form[data-busy=\"true\"], [data-busy=\"true\"], dialog[open]'" in SCRIPT
    assert "function scheduleAutoReload(id, banner)" in SCRIPT
    assert "scheduleAutoReload(id, banner);" in SCRIPT
    assert "Обновится само через" in SCRIPT


def test_mixed_build_guard_hands_the_tab_to_one_epoch_and_forces_reload() -> None:
    """Страж смеси сборок (боевой случай 25.08.2026): кэш собрал вкладку из
    модулей двух эпох — списки «Создания» рисовал один экземпляр guided, клики
    перехватывал второй с пустым состоянием: «галка не ставится», секции
    двоятся, док пустой. Закон: именем адаптера и привязкой формы владеет
    ПЕРВАЯ эпоха; второй экземпляр не подменяет её молча, а объявляет смесь,
    и build-guard форсирует баннер перезагрузки даже при совпадении манифеста
    с собственной эпохой."""
    os_v4 = (ROOT / "web/app/workspace-os-v4.js").read_text(encoding="utf-8")
    assert "function reportMixedBuildEpoch" in os_v4
    assert "contentengine:mixed-build-detected" in os_v4
    assert "existing.epoch !== epoch" in os_v4
    registry_guard = os_v4.split("existing.epoch !== epoch", 1)[1]
    assert "reportMixedBuildEpoch(`adapter:${name}`" in registry_guard
    assert "return () => {};" in registry_guard.split("runtime.adapters.set", 1)[0]
    assert "desktopEpochHeld.build !== BUILD" in os_v4
    assert "? desktopEpochHeld" in os_v4

    guided = (ROOT / "web/app/workspace-os-v4-generation-guided.js").read_text(
        encoding="utf-8"
    )
    assert 'const GUIDED_EPOCH = "' in guided
    assert "existing.owner !== handleFormClick" in guided
    binding_guard = guided.split("existing.owner !== handleFormClick", 1)[1]
    assert "contentengine:mixed-build-detected" in binding_guard
    assert "epoch: GUIDED_EPOCH" in guided
    assert 'registerAdapter("generation-guided", mount, {' in guided

    guard = (ROOT / "web/app/workspace-build-guard.js").read_text(encoding="utf-8")
    assert '"contentengine:mixed-build-detected"' in guard
    assert "force = false" in guard
    assert "id === CURRENT_BUILD && !force" in guard
    assert "force: true" in guard
