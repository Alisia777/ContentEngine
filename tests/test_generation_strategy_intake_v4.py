from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT / "web/app/generation-strategy-intake-v4.js"
CSS = ROOT / "web/app/generation-strategy-intake-v4.css"
ENTRY = ROOT / "web/app/generation-strategy-intake-v2.js"
LOADER = ROOT / "web/app/workspace-os-v4-loader.js"
GUIDED = ROOT / "web/app/workspace-os-v4-generation-guided.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def between(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


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


def test_copy_is_single_mp4_first_without_remote_source_dependency() -> None:
    source = text(V4)
    copy_panel = between(source, "function copyPanel()", "function avatarPanel()")

    assert 'input.accept = "video/mp4,.mp4"' in source
    assert 'input.dataset.generationIntakeMp4 = multiple ? "strategy" : "single"' in source
    assert copy_panel.count('sourceChooser("copy_video")') == 1
    assert "optionalSourceUrl()" not in copy_panel
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


def test_copy_compact_form_requires_one_mp4_three_to_five_product_images_and_preferences() -> None:
    source = text(V4)
    copy_panel = between(source, "function copyPanel()", "function avatarPanel()")
    prepare_copy = between(
        source,
        "async function prepareCopy(form)",
        "async function prepareAvatar(form)",
    )

    assert copy_panel.count('sourceChooser("copy_video")') == 1
    assert "productSlot()" in copy_panel
    assert "executionControls()" in copy_panel
    assert 'recommendationSlot("copy_video")' in copy_panel
    assert "const MIN_PRODUCT_IMAGES = 3" in source
    assert "const MAX_PRODUCT_IMAGES = 5" in source
    assert (
        "const productCount = existingProductMediaIds.length + productFiles.length"
        in prepare_copy
    )
    assert "productCount < MIN_PRODUCT_IMAGES" in prepare_copy
    assert "productCount > MAX_PRODUCT_IMAGES" in prepare_copy
    assert 'input.dataset.generationIntakeImage = purpose' in source
    assert 'imageInput({ multiple: true, purpose: "product" })' in source
    assert 'model.dataset.generationIntakeField = "model"' in source
    assert 'audio.dataset.generationIntakeField = "audio"' in source
    assert "currentRequestedModel(panel)" in prepare_copy
    assert "currentAudio(panel)" in prepare_copy
    assert "currentRecommendation(form)" in prepare_copy
    assert "recommendationSource(form)" in prepare_copy


def test_copy_and_avatar_move_the_same_native_brief_instead_of_creating_route_copies() -> None:
    source = text(V4)
    mover = between(source, "function moveSharedBrief", "function refreshRecommendationUi")
    mount = between(source, "function mount(form)", "function scheduleMount()")
    set_route = between(source, "function setRoute", "function bind(")
    binding = between(source, "function bind(form, state)", "function mount(form)")

    assert "form.elements?.brief" in source
    assert "briefField" in mount
    assert "briefOrigin" in mount
    assert "state.briefField" in mover
    assert "slot.append(state.briefField)" in mover
    assert "state.briefOrigin.after(state.briefField)" in mover
    assert "refreshRecommendationUi(form, state)" in set_route
    assert 'action === "generation-intake-apply-recommendation"' in binding
    assert "cloneNode" not in mover
    assert "function descriptionField" not in source
    assert 'dataset.generationIntakeField = "description"' not in source


def test_avatar_compact_form_is_mp4_plus_photo_or_description_without_product_storyboard() -> None:
    source = text(V4)
    avatar_panel = between(source, "function avatarPanel()", "function strategyPanel()")
    prepare_avatar = between(
        source,
        "async function prepareAvatar(form)",
        "async function uploadStrategySources(form)",
    )

    assert avatar_panel.count('sourceChooser("avatar_video")') == 1
    assert "avatarIdentityChooser()" in avatar_panel
    assert "storyboardNode()" not in avatar_panel
    assert "productSlot()" not in avatar_panel
    assert 'imageInput({ purpose: "avatar" })' in source
    assert 'input.dataset.generationIntakeAvatarMode = value' in source
    assert "avatarInputMode(panel)" in prepare_avatar
    assert "selectedAvatarFile(panel)" in prepare_avatar
    assert "currentAvatarWishes(panel)" in prepare_avatar
    assert 'mode === "photo" && Boolean(avatarFile) === Boolean(existingAvatarMediaId)' in prepare_avatar
    assert 'mode === "description" && avatarWishes.length < 10' in prepare_avatar
    assert 'uploadProjectMedia(avatarFile, "creator_reference")' in prepare_avatar
    assert "avatar_mode" in prepare_avatar
    assert "avatar_media_id" in prepare_avatar
    assert 'strategy_id: "character_performance"' in prepare_avatar
    assert "provider_feature_flag: CHARACTER_PERFORMANCE_FEATURE" in prepare_avatar
    assert "launch_enabled: false" in prepare_avatar
    assert "original_product_image" not in prepare_avatar
    assert "new_product_image" not in prepare_avatar


def test_compact_route_hides_legacy_shell_and_disables_inactive_form_controls() -> None:
    source = text(V4)
    styles = " ".join(text(CSS).split())
    controls = between(
        source,
        "function setPanelControlsActive",
        "function applyCompactPreferences",
    )
    set_route = between(source, "function setRoute", "function bind(")

    assert 'qa("input, select, textarea", panel)' in controls
    assert "control.disabled = !active" in controls
    assert (
        "setPanelControlsActive(panel, panel.dataset.generationIntakePanel === route)"
        in set_route
    )
    assert "refreshModelSelects(form, state)" in set_route
    assert (
        '#mock-batch-form[data-generation-intake-v4-mode="compact"] '
        '> [data-ce-v4-generation-guided-shell]'
        in styles
    )


def test_v4_shell_mounts_as_a_direct_form_child_before_the_legacy_guided_shell() -> None:
    source = text(V4)
    mount = between(source, "function mount(form)", "function scheduleMount()")

    assert 'const guidedShell = q("[data-ce-v4-generation-guided-shell]", form)' in mount
    assert "guidedShell?.parentElement === form" in mount
    assert "guidedShell.before(shell)" in mount
    assert "else form.prepend(shell)" in mount
    assert "strategyView.before(shell)" not in mount


def test_guided_adapter_never_adopts_the_direct_intake_shell() -> None:
    guided = text(GUIDED)
    organize = between(
        guided,
        "function organizeOriginalNodes",
        "function exposeProviderReadinessControl",
    )
    adopt = between(
        guided,
        "function adoptDirectChildren",
        "function panelControls",
    )

    assert 'node.matches?.("[data-generation-intake-v4]")' in organize
    assert '!node.matches?.("[data-generation-intake-v4]")' in adopt


def test_compact_intake_has_no_provider_post_or_form_submission_path() -> None:
    source = text(V4)

    assert 'const PAID_AUTHORITY = "creator-generate"' in source
    assert "fetch(" not in source
    assert "XMLHttpRequest" not in source
    assert "navigator.sendBeacon" not in source
    assert 'form.addEventListener("submit"' not in source
    assert ".submit()" not in source
    assert ".requestSubmit()" not in source


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


def test_route_tab_click_never_selects_paid_strategy() -> None:
    source = text(V4)
    set_route = between(source, "function setRoute", "function bind(")

    # Фикс 4 (ТЗ Этапа 1): переключение вкладки маршрута не выбирает платную
    # стратегию — выбор происходит только из подготовки/загрузки материалов.
    assert "selectStrategy" not in set_route
    assert "userInitiated" not in source
    assert "selectStrategy(form, handoff.strategy_id)" in source
    assert "selectStrategy(form, STRATEGY_AUTHORITY_STRATEGY)" in source
    assert 'action === "generation-intake-prepare-copy"' in source


def test_catalog_errors_are_recoverable_without_reload() -> None:
    guided = text(GUIDED)
    view = text(ROOT / "web/app/generation-strategy-view.js")

    # Фикс 1 (ТЗ Этапа 1): ошибка каталога стратегий/моделей не должна
    # оставлять страницу мёртвой до F5.
    assert "CATALOG_RETRY_DELAYS_MS = Object.freeze([2_000, 5_000, 15_000])" in guided
    assert "function scheduleCatalogRetry" in guided
    assert "data-ce-v4-model-catalog-retry" in guided
    assert "data-generation-strategy-catalog-retry" in guided
    assert "data-generation-strategy-catalog-retry" in view
    assert "Повторить загрузку" in view


def test_fresh_product_uploads_bind_visibly_or_warn() -> None:
    source = text(V4)

    # Фикс 2 (ТЗ Этапа 1): свежезагруженные фото либо привязываются через
    # синтезированные чекбоксы из подтверждённого серверного состояния,
    # либо сотрудник видит явное предупреждение — молчаливая потеря запрещена.
    assert "function ensureProductCheckbox" in source
    assert "function pruneSyntheticProductOptions" in source
    assert "не привязались автоматически" in source
    assert "refreshStrategyAssets" in source


def test_compact_copy_carries_product_identity() -> None:
    source = text(V4)
    prepare_copy = between(
        source,
        "async function prepareCopy(form)",
        "async function prepareAvatar(form)",
    )

    # Фикс 3 (ТЗ Этапа 1): артикул и название вводятся в компактной «Копии»
    # и синхронизируются с шагом «Товар» мастера.
    assert "Артикул (SKU) вашего товара" in source
    assert "Название товара" in source
    assert "function syncIdentityToForm" in source
    assert "function prefillIdentityFields" in source
    assert "productFiles.length && !productIdentity" in prepare_copy


def test_intake_handoff_contract_has_guided_consumer() -> None:
    source = text(V4)
    guided = text(GUIDED)

    # Фикс 5 (ТЗ Этапа 1): handoff-контракт компактной формы обязан иметь
    # читателя. Гид читает скрытые поля, sessionStorage и живое событие,
    # предзаполняет пустой «Замысел» и показывает происхождение данных.
    assert 'const HANDOFF_VERSION = "generation-intake-mp4-v4"' in source
    assert (
        'const INTAKE_HANDOFF_EVENT = "contentengine:generation-strategy-handoff"'
        in guided
    )
    assert (
        'const INTAKE_HANDOFF_STORAGE_PREFIX = "generation-intake-mp4-v4:"'
        in guided
    )
    assert "function intakeHandoffFromHiddenFields" in guided
    assert '"generation_intake_source_url"' in guided
    assert '"generation_intake_recommendation_source"' in guided
    assert "function intakeHandoffFromSession" in guided
    assert "consumeIntakeHandoff(form)" in guided
    assert "window.addEventListener(INTAKE_HANDOFF_EVENT" in guided
    assert "q('[data-ce-v4-generation-content=\"brief\"]', form)" in guided
    assert "data-ce-v4-intake-provenance" in guided
    assert 'rel = "noreferrer noopener"' in guided


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
