from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
RECOVERY = APP / "workspace-research-failure-recovery.js"
BOOTSTRAP = APP / "workspace-research-training-bootstrap.js"
INDEX = APP / "index.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_failed_research_can_be_closed_and_replaced_with_a_fresh_form() -> None:
    source = read(RECOVERY)
    assert (
        'from "./product-research-view.js?v=20260823.copy-engines.46"'
        in source
    )
    for marker in (
        "data-research-youtube-failure-guard",
        "Закрыть ошибочный запуск",
        "Начать заново без ролика",
        "recovery: \"1\"",
        "productResearchInputMarkup",
        "researchRecoveryPaidContext",
        "exactPaidAuthorizationRequired",
        "paidTariff: paidContext.paidTariff",
        "workspace-project-flow-snapshot",
        "can_start_paid_own",
        "paidContext.allowed",
        "Ошибочный результат больше не блокирует работу",
        "Предыдущий terminal-failure закрыт",
        "clearPendingSource",
        "Повторного платного запуска нет",
        'guard.dataset.failureMode === "exact-video-provider-terminal"',
        "must never rewrite recovery into another upload or generic paid form",
    ):
        assert marker in source
    assert "savedStatus.focus" not in source


def test_mp4_handoff_opens_the_real_media_upload_form() -> None:
    source = read(RECOVERY)
    for marker in (
        'const MEDIA_ROUTE = "/workspace/media"',
        'document.getElementById("media-upload-form")',
        'form.querySelector(\'input[type="file"]\')',
        'input.accept = "video/mp4,.mp4"',
        "input.multiple = false",
        "Выбрать MP4",
        "Загрузить MP4 и продолжить",
        "Сначала выберите один MP4",
        "workspace/board",
        "youtube_source",
    ):
        assert marker in source
    assert "#/workspace/board?" not in source


def test_recovery_module_is_loaded_on_every_handoff_route() -> None:
    bootstrap = read(BOOTSTRAP)
    index = read(INDEX)
    assert (
        '"workspace-research-failure-recovery.js":\n'
        '      "20260814.os4.41"'
        in bootstrap
    )
    for marker in (
        'route === "/workspace/research"',
        'route === "/workspace/media"',
        'route === "/workspace/review"',
        'route === "/workspace/ai"',
        "workspace-research-failure-recovery.css",
        "workspace-research-failure-recovery.js",
        'const BUILD = "20260814.os4.41"',
    ):
        assert marker in bootstrap
    assert (
        "workspace-research-training-bootstrap.js?"
        "v=sha256-"
        in index
    )


def test_recovery_hashes_point_to_real_routes() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    script = """
      const mod = await import('./web/app/workspace-research-failure-recovery.js');
      const projectId = '11111111-1111-4111-8111-111111111111';
      const sourceId = '22222222-2222-4222-8222-222222222222';
      const upload = mod.mediaHandoffHash({
        projectId,
        sourceId,
        canonicalUrl: 'https://youtube.com/watch?v=CXssfXBVInw'
      });
      const fresh = mod.freshResearchHash(projectId);
      process.stdout.write(JSON.stringify({ upload, fresh }));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    value = json.loads(result.stdout)
    assert value["upload"].startswith("#/workspace/media?")
    assert "youtube_source=22222222-2222-4222-8222-222222222222" in value["upload"]
    assert value["fresh"] == (
        "#/workspace/research?project_id="
        "11111111-1111-4111-8111-111111111111&recovery=1"
    )


def test_operator_recovery_requires_exact_current_server_tariff() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    project_id = "11111111-1111-4111-8111-111111111111"
    tariff = {
        "version": "openai-api-2026-08-13-gpt-5.5-standard-context-v3",
        "provider": "openai",
        "provider_key": "openai_web_search",
        "adapter_version": "openai-responses-web-search-v1",
        "model": "gpt-5.5",
        "currency": "USD",
        "billing_mode": "metered_actual_usage",
        "service_tier": "default",
        "input_usd_per_million_tokens": "5.00",
        "output_usd_per_million_tokens": "30.00",
        "long_context_threshold_input_tokens": 272000,
        "long_context_input_usd_per_million_tokens": "10.00",
        "long_context_output_usd_per_million_tokens": "45.00",
        "web_search_usd_per_call": "0.01",
        "max_output_tokens": 18000,
        "max_provider_attempts": 1,
        "fixed_total": False,
        "confirmation_value": (
            "OPENAI_GPT_5_5_WEB_RESEARCH_20260813_"
            "DEFAULT_SHORT_IN_5_OUT_30_LONG_GT272K_IN_10_OUT_45_SEARCH_0_01_MAXOUT_18000"
        ),
    }
    script = f"""
      const subject = await import('./web/app/workspace-research-failure-recovery.js');
      const projectId = '{project_id}';
      const paidTariff = {json.dumps(tariff)};
      const flow = {{
        project_id: projectId,
        capabilities: {{ product_research: {{
          can_open: true,
          can_start_paid_own: true,
          can_read_own: true,
          run_scope: 'own',
        }} }},
        research_context: {{ paid_tariff: paidTariff }},
      }};
      const exact = subject.researchRecoveryPaidContext({{
        projectId, workspaceRole: 'operator', projectFlow: flow,
      }});
      const staleProject = subject.researchRecoveryPaidContext({{
        projectId, workspaceRole: 'operator',
        projectFlow: {{ ...flow, project_id: '22222222-2222-4222-8222-222222222222' }},
      }});
      const missingTariff = subject.researchRecoveryPaidContext({{
        projectId, workspaceRole: 'operator',
        projectFlow: {{ ...flow, research_context: {{}} }},
      }});
      const manager = subject.researchRecoveryPaidContext({{
        projectId, workspaceRole: 'producer', projectFlow: {{}},
      }});
      process.stdout.write(JSON.stringify({{ exact, staleProject, missingTariff, manager }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    value = json.loads(result.stdout)
    assert value["exact"] == {
        "allowed": True,
        "exactPaidAuthorizationRequired": True,
        "paidTariff": tariff,
        "scope": "own",
    }
    assert value["staleProject"] == {
        "allowed": False,
        "exactPaidAuthorizationRequired": True,
        "paidTariff": None,
        "scope": "none",
    }
    assert value["missingTariff"] == {
        "allowed": True,
        "exactPaidAuthorizationRequired": True,
        "paidTariff": None,
        "scope": "own",
    }
    assert value["manager"] == {
        "allowed": True,
        "exactPaidAuthorizationRequired": False,
        "paidTariff": None,
        "scope": "project",
    }


def test_new_browser_modules_are_valid_javascript() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    for path in (RECOVERY, BOOTSTRAP):
        subprocess.run([node, "--check", str(path)], check=True)
