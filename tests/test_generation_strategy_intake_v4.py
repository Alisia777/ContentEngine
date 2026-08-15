from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT / "web/app/generation-strategy-intake-v4.js"
CSS = ROOT / "web/app/generation-strategy-intake-v4.css"
ENTRY = ROOT / "web/app/generation-strategy-intake-v2.js"
LOADER = ROOT / "web/app/workspace-os-v4-loader.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_three_routes_have_separate_operator_forms() -> None:
    source = text(V4)

    assert '"copy_video"' in source
    assert '"avatar_video"' in source
    assert '"strategy_video"' in source
    assert 'panel.dataset.generationIntakePanel = "copy_video"' in source
    assert 'panel.dataset.generationIntakePanel = "avatar_video"' in source
    assert 'panel.dataset.generationIntakePanel = "strategy_video"' in source
    assert "Скопировать ролик" in source
    assert "Сделать с аватаром" in source
    assert "Создать видео по стратегии" in source


def test_copy_is_mp4_first_and_url_is_optional_metadata() -> None:
    source = text(V4)

    assert 'input.accept = "video/mp4,.mp4"' in source
    assert 'input.dataset.generationIntakeMp4 = multiple ? "strategy" : "single"' in source
    assert "Источник публикации — по желанию" in source
    assert "Система анализирует загруженный MP4" in source
    assert "canonicalGenerationIntakeSourceUrl" not in source
    assert "contentengine_register_exact_youtube_source" not in source
    assert "youtube.com/watch" not in source


def test_copy_builds_complete_product_swap_handoff() -> None:
    source = text(V4)

    assert 'const PAID_AUTHORITY = "creator-generate"' in source
    assert 'const COPY_AUTHORITY_STRATEGY = "viral_product_swap"' in source
    assert 'role: "source_video"' in source
    assert 'role: "original_product_image"' in source
    assert 'role: "new_product_image"' in source
    assert "original_product_media_id" in source
    assert "generation_strategy_prefill_assets" in source
    assert "contentengine:generation-strategy-handoff" in source
    assert "openNativeLaunch(form, handoff)" in source


def test_mp4_analysis_generates_storyboard_and_selectable_product_frame() -> None:
    source = text(V4)

    assert "async function assertMp4" in source
    assert 'signature.includes("ftyp")' in source
    assert "async function captureStoryboard" in source
    assert "STORYBOARD_FRAME_COUNT = 8" in source
    assert "frameScore" in source
    assert "recommendedIndex" in source
    assert "data.frameIndex" not in source
    assert "button.dataset.frameIndex" in source
    assert "frameAsFile" in source


def test_avatar_never_silently_falls_back_to_product_ugc() -> None:
    source = text(V4)

    assert 'strategy_id: "character_performance"' in source
    assert 'provider_feature_flag: CHARACTER_PERFORMANCE_FEATURE' in source
    assert 'launch_enabled: false' in source
    assert "не подменяется Product UGC" in source
    assert "viral_avatar_ugc" not in source
    assert "product_ugc" not in source


def test_strategy_accepts_up_to_ten_mp4_sources_and_keeps_full_constructor() -> None:
    source = text(V4)

    assert "MAX_STRATEGY_FILES = 10" in source
    assert "input.multiple = multiple" in source
    assert "files.length > MAX_STRATEGY_FILES" in source
    assert 'bindRoleAsset(form, "source_video", mediaId)' in source
    assert "refreshStrategyAssets" in source
    assert 'const STRATEGY_AUTHORITY_STRATEGY = "viral_rebuild"' in source
    assert "Ниже остаётся действующая шестишаговая форма" in source
    assert "reference_media_ids" in source


def test_generation_intake_does_not_create_second_paid_authority() -> None:
    source = text(V4)
    repository_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in [V4, ENTRY, LOADER]
        if path.exists()
    )

    assert "creator-generate" in source
    assert "contentengine-generation-intake" not in repository_text
    assert "generation_intake_spend_ledger" not in repository_text
    assert "fetch(" not in source
    assert "RUNWAYML_API_SECRET" not in source
    assert "provider POST" not in source


def test_generation_intake_video_select_refresh_is_mutation_idempotent() -> None:
    source = text(V4)

    # The module observes the entire document for child-list changes. Replacing
    # these options on every scheduled mount creates an endless observer loop on
    # the real generation route, so an unchanged projection must not mutate.
    assert "const unchanged = options.length === desired.length" in source
    assert "if (!unchanged)" in source
    assert "select.replaceChildren(...desired.map" in source


def test_direct_upload_uses_existing_private_media_runtime() -> None:
    source = text(V4)

    assert "ContentEngineWorkspaceRuntime?.getApi" in source
    assert "contentengine_attach_generation_direct_mp4" in source
    assert "api.uploadPrivateObject" in source
    assert "api.registerMedia" in source
    assert "api.removePrivateObject" in source
    assert "api?.storagePrefix" in source
    assert "api.storageBucket" in source
    assert "sha256Hex" in source


def test_compact_routes_do_not_submit_legacy_generation_form() -> None:
    source = text(V4)

    assert 'form.addEventListener("submit"' not in source
    assert ".submit()" not in source
    assert ".requestSubmit()" not in source
    assert "/v1/recipes/" not in source
    assert "RUNWAYML_API_SECRET" not in source


def test_interface_is_responsive_and_reduced_motion_safe() -> None:
    styles = text(CSS)

    assert "@media (max-width: 900px)" in styles
    assert "@media (max-width: 560px)" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles
    assert '[data-generation-intake-v4-mode="compact"]' in styles


def test_javascript_is_parseable() -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI contracts"
    result = subprocess.run(
        [node, "--check", str(V4)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
