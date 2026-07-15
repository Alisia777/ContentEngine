import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEW_PATH = ROOT / "web" / "app" / "account-launch-view.js"
GUIDES_PATH = ROOT / "web" / "app" / "account-launch-guides.js"
VIEW = VIEW_PATH.read_text(encoding="utf-8")
GUIDES = GUIDES_PATH.read_text(encoding="utf-8")
STYLES = (ROOT / "web" / "app" / "account-launch.css").read_text(encoding="utf-8")


def _run_view_javascript(body: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable account-launch contracts")

    with tempfile.TemporaryDirectory() as temporary_directory:
        module_directory = Path(temporary_directory)
        (module_directory / "account-launch-guides.mjs").write_text(GUIDES, encoding="utf-8")
        (module_directory / "account-launch-view.mjs").write_text(
            VIEW.replace("./account-launch-guides.js?v=20260715.6", "./account-launch-guides.mjs"),
            encoding="utf-8",
        )
        (module_directory / "contract.mjs").write_text(
            "import * as view from './account-launch-view.mjs';\n"
            f"const payload = (() => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(payload));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=module_directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_center_routes_accept_only_the_three_exact_platform_paths():
    assert 'export const ACCOUNT_LAUNCH_PATH = "/learn/accounts"' in VIEW
    assert r"/^\/learn\/accounts\/(instagram|youtube|vk)$/u" in VIEW

    routes = _run_view_javascript(
        """
        const paths = [
          "/learn/accounts",
          "/learn/accounts/",
          "/learn/accounts/instagram",
          "/learn/accounts/youtube/",
          "/learn/accounts/vk",
          "/learn/accounts/tiktok",
          "/learn/accounts/YOUTUBE",
          "/learn/accounts/youtube/extra",
          "",
        ];
        return paths.map((path) => view.accountLaunchSlugFromPath(path));
        """
    )
    assert routes == ["", "", "instagram", "youtube", "vk", None, None, None, None]


def test_checklist_dom_ids_and_storage_keys_are_platform_scoped():
    markup = _run_view_javascript(
        """
        return {
          instagram: view.accountLaunchGuideMarkup("instagram", ["instagram-registration-1"]),
          youtube: view.accountLaunchGuideMarkup("youtube", ["youtube-registration-1"]),
          vk: view.accountLaunchGuideMarkup("vk", ["vk-registration-1"]),
        };
        """
    )

    platform_keys = {}
    for platform, html in markup.items():
        keys = re.findall(r'data-account-check="([^"]+)"', html)
        ids = re.findall(r'id="(account-check-[^"]+)"', html)
        assert keys
        assert all(key.startswith(f"{platform}-") for key in keys)
        assert all(identifier.startswith(f"account-check-{platform}-") for identifier in ids)
        assert len(ids) == len(set(ids)) == len(keys)
        assert f'data-account-platform="{platform}"' in html
        assert f'id="account-check-{platform}-registration-1"' in html
        assert re.search(
            rf'id="account-check-{platform}-registration-1"[^>]*\schecked\s*/>',
            html,
        )
        platform_keys[platform] = set(keys)

    assert platform_keys["instagram"].isdisjoint(platform_keys["youtube"])
    assert platform_keys["instagram"].isdisjoint(platform_keys["vk"])
    assert platform_keys["youtube"].isdisjoint(platform_keys["vk"])


def test_center_is_written_for_a_true_beginner():
    for phrase in (
        "Для полного новичка",
        "от регистрации и защиты входа до первой проверенной публикации",
        "Регистрация и доступ",
        "Профиль готов к работе",
        "Первая публикация",
        "Официальная справка площадки",
    ):
        assert phrase in VIEW
    assert "data-account-visual-root" in VIEW


def test_warmup_explicitly_rejects_fake_platform_quotas():
    assert "Площадки не публикуют гарантированных «безопасных чисел»" in VIEW
    assert "не по выдуманной норме лайков в день" in VIEW
    assert "Безопасный прогрев — это не накрутка" in VIEW


def test_ad_checker_executes_all_incomplete_review_and_document_branches():
    decisions = _run_view_javascript(
        """
        const allNo = {
          value_exchange: "no",
          brand_control: "no",
          product_focus: "no",
        };
        const stepIds = Object.keys(allNo);
        const results = {
          empty: view.evaluateAdvertisingAnswers({}),
          partial: view.evaluateAdvertisingAnswers({ value_exchange: "no" }),
          invalid: view.evaluateAdvertisingAnswers({ ...allNo, product_focus: "maybe" }),
          allNo: view.evaluateAdvertisingAnswers(allNo),
          eachYes: stepIds.map((stepId) => view.evaluateAdvertisingAnswers({ ...allNo, [stepId]: "yes" })),
        };
        return {
          results,
          frozen: [
            results.empty,
            results.partial,
            results.invalid,
            results.allNo,
            ...results.eachYes,
          ].every(Object.isFrozen),
        };
        """
    )

    results = decisions["results"]
    assert results["empty"]["status"] == "incomplete"
    assert results["partial"]["status"] == "incomplete"
    assert results["invalid"]["status"] == "incomplete"
    assert results["allNo"]["status"] == "document"
    assert "не автоматическое освобождение от маркировки" in results["allNo"]["message"]
    assert [result["status"] for result in results["eachYes"]] == ["review", "review", "review"]
    assert all("Не публикуйте" in result["message"] for result in results["eachYes"])
    assert decisions["frozen"] is True


def test_checklists_and_decision_result_are_accessible():
    assert 'id="account-check-${escapeHtml(id)}" type="checkbox"' in VIEW
    assert 'data-account-check="${escapeHtml(id)}"' in VIEW
    assert 'type="radio"' in VIEW
    assert '<legend><span class="account-ad-question">' in VIEW
    assert 'role="status" aria-live="polite"' in VIEW
    assert 'aria-labelledby="account-ad-title"' in VIEW
    assert "display: contents" not in STYLES
    assert ".account-ad-options" in STYLES
    assert "focus-visible" in STYLES


def test_layout_has_narrow_mobile_and_reduced_motion_support():
    assert "@media (max-width: 680px)" in STYLES
    assert "grid-template-columns: minmax(0, 1fr)" in STYLES
    assert "@media (prefers-reduced-motion: reduce)" in STYLES
