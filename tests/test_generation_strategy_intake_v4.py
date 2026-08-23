from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile


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
    assert "Видео по стратегии" in source
    assert "host.dataset.generationIntakeStrategyHost" in source


def test_copy_is_single_mp4_first_without_remote_source_dependency() -> None:
    source = text(V4)
    copy_panel = between(source, "function copyPanel()", "function avatarPanel()")

    assert 'input.accept = "video/mp4,.mp4"' in source
    assert 'input.dataset.generationIntakeMp4 = multiple ? "strategy" : "single"' in source
    # Заголовок блока задаёт карточка экрана, поэтому вызов передаёт heading=null;
    # инвариант прежний — вход для исходника в панели ровно один.
    assert copy_panel.count('sourceChooser("copy_video"') == 1
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
    assert "openNativeLaunch(activeForm, handoff)" in source


def test_copy_compact_form_requires_one_mp4_one_to_five_product_images_and_preferences() -> None:
    source = text(V4)
    copy_panel = between(source, "function copyPanel()", "function avatarPanel()")
    prepare_copy = between(
        source,
        "async function prepareCopy(form)",
        "async function prepareAvatar(form)",
    )

    # Заголовок блока задаёт карточка экрана, поэтому вызов передаёт heading=null;
    # инвариант прежний — вход для исходника в панели ровно один.
    assert copy_panel.count('sourceChooser("copy_video"') == 1
    assert "productSlot()" in copy_panel
    assert "executionControls()" in copy_panel
    assert 'recommendationSlot("copy_video")' in copy_panel
    assert "const MIN_PRODUCT_IMAGES = 1" in source
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


def test_routes_move_one_native_brief_but_keep_three_isolated_drafts() -> None:
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
    assert "const BRIEF_ROUTES" in source
    assert "routeBriefDraftsMemory" in source
    assert "briefDrafts: initialRouteBriefDrafts(form, briefControl)" in mount
    assert "briefDraftReady: false" in mount
    assert "if (state.briefDraftReady === false)" in set_route
    assert "captureBriefDraft(form, state, state.briefRoute || state.route)" in set_route
    assert "restoreBriefDraft(form, state, route)" in set_route
    assert set_route.index("captureBriefDraft(") < set_route.index("state.route = route")
    assert set_route.index("state.route = route") < set_route.index("restoreBriefDraft(")
    assert "BRIEF_CONTROL_DATASET_KEYS" in source
    assert "BRIEF_FORM_DATASET_KEYS" in source
    assert "refreshRecommendationUi(form, state)" in set_route
    assert 'action === "generation-intake-apply-recommendation"' in binding
    assert "cloneNode" not in mover
    assert "function descriptionField" not in source
    assert 'dataset.generationIntakeField = "description"' not in source


def test_route_brief_drafts_restore_text_and_ai_provenance_independently() -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI contracts"
    source = text(V4)
    contract = source[
        source.index("function briefDatasetSnapshot"):
        source.index("function currentRecommendation(form)")
    ]
    script = f"""
globalThis.HTMLTextAreaElement = class {{
  constructor() {{ this.value = ""; this.dataset = {{}}; }}
}};
const BRIEF_ROUTES = Object.freeze(["copy_video", "avatar_video", "strategy_video"]);
const BRIEF_CONTROL_DATASET_KEYS = Object.freeze([
  "researchRecommendationApplied",
  "researchRecommendationField",
  "researchRecommendationEdited",
  "generationIntakeOperatorOwned",
]);
const BRIEF_FORM_DATASET_KEYS = Object.freeze([
  "researchRecommendationLineage",
  "researchRecommendationVerificationState",
  "researchRecommendationAppliedFields",
]);
const routeBriefDraftsMemory = new Map();
const formStates = new WeakMap();
const projectId = () => "10000000-0000-4000-8000-000000000001";
{contract}

const brief = new HTMLTextAreaElement();
const form = {{
  dataset: {{}},
  elements: {{ brief, generation_intake_route: {{ value: "copy_video" }} }},
}};
const state = {{
  briefDraftMemoryKey: projectId(),
  briefDrafts: cloneRouteBriefDrafts(),
  briefRoute: "copy_video",
  route: "copy_video",
}};
formStates.set(form, state);

brief.value = "COPY ONLY";
brief.dataset.researchRecommendationApplied = "copy-selection";
form.dataset.researchRecommendationLineage = "active";
form.dataset.researchRecommendationVerificationState = "verified";
form.dataset.researchRecommendationAppliedFields = "brief";
captureBriefDraft(form, state, "copy_video");

restoreBriefDraft(form, state, "avatar_video");
if (brief.value !== "") throw new Error("copy_leaked_into_avatar");
if (brief.dataset.researchRecommendationApplied) throw new Error("copy_lineage_leaked_into_avatar");
brief.value = "AVATAR ONLY";
brief.dataset.generationIntakeOperatorOwned = "true";
captureBriefDraft(form, state, "avatar_video");

restoreBriefDraft(form, state, "copy_video");
if (brief.value !== "COPY ONLY") throw new Error("copy_text_not_restored");
if (brief.dataset.researchRecommendationApplied !== "copy-selection") {{
  throw new Error("copy_lineage_not_restored");
}}
if (brief.dataset.generationIntakeOperatorOwned) throw new Error("avatar_lineage_leaked_into_copy");
if (form.dataset.generationScenarioIntent !== "COPY ONLY") throw new Error("scenario_mirror_stale");

restoreBriefDraft(form, state, "strategy_video");
if (brief.value !== "") throw new Error("compact_text_leaked_into_strategy");
if (form.dataset.researchRecommendationLineage) throw new Error("compact_form_lineage_leaked");
console.log("route-brief-drafts-ok");
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "route-brief-drafts-ok"


def test_local_brief_template_requires_an_explicit_human_action() -> None:
    source = text(V4)
    set_route = between(source, "function setRoute", "function bind(")
    binding = between(source, "function bind(form, state)", "function mount(form)")

    assert "const DEFAULT_BRIEF_TEMPLATES" in source
    assert "Стартовая заготовка" in source
    assert "Базовый шаблон" in source
    assert "Локальный шаблон, не рекомендация ИИ-центра." in source
    assert "Вставить базовый шаблон" in source
    assert "function prefillCopyRecommendation" not in source
    assert "DEFAULT_BRIEF_TEMPLATES.copy_video" not in set_route
    assert 'action === "generation-intake-apply-recommendation"' in binding
    assert "markBriefAsOperatorOwned(form, brief)" in binding
    assert "brief.value = DEFAULT_BRIEF_TEMPLATES[route]" in binding


def test_local_brief_template_detaches_stale_ai_lineage_at_runtime() -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI contracts"
    source = text(V4)
    start = source.index("function currentRecommendation(form)")
    end = source.index("function currentRequestedModel(panel)")
    contract = source[start:end]
    script = f"""
const cleanText = (value, limit) => String(value || "").trim().slice(0, limit);
{contract}
const brief = {{
  value: "",
  dataset: {{
    researchRecommendationApplied: "selection-old",
    researchRecommendationField: "brief",
    researchRecommendationEdited: "true",
  }},
}};
const form = {{
  elements: {{ brief }},
  dataset: {{
    researchRecommendationLineage: "active",
    researchRecommendationVerificationState: "verified",
    researchRecommendationAppliedFields: "brief,mode",
  }},
}};
markBriefAsOperatorOwned(form, brief);
brief.value = "Локальный базовый шаблон";
if (recommendationSource(form) !== "operator") throw new Error("local_template_not_operator");
if (brief.dataset.researchRecommendationApplied) throw new Error("stale_brief_lineage");
if (form.dataset.researchRecommendationAppliedFields !== "mode") throw new Error("stale_applied_field");
brief.dataset.researchRecommendationApplied = "selection-new";
brief.dataset.researchRecommendationEdited = "true";
if (recommendationSource(form) !== "ai_center_edited") throw new Error("new_ai_lineage_blocked");
console.log("local-template-lineage-ok");
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "local-template-lineage-ok"


def test_duet_form_is_mp4_plus_registered_presenter_without_avatar_photo() -> None:
    """«Дуэт» (с 23.08.2026): исходник + ведущий проекта, без фото/описания
    аватара и без товара в ассетах. Ведущий регистрируется из каталога
    провайдера прямо в форме; запуск открыт ровно при выбранном ведущем."""
    source = text(V4)
    avatar_panel = between(source, "function avatarPanel()", "function strategyPanel()")
    prepare_avatar = between(
        source,
        "async function prepareAvatar(form)",
        "async function uploadStrategySources(form)",
    )

    assert avatar_panel.count('sourceChooser("avatar_video")') == 1
    assert "avatarIdentityChooser()" not in avatar_panel
    assert "duetPresenterChooser()" in avatar_panel
    assert "storyboardNode()" not in avatar_panel
    assert "productSlot()" not in avatar_panel
    assert "Character Performance" not in avatar_panel
    assert "речь ведущего" in avatar_panel

    # Ведущий обязателен; фото/описание аватара не спрашиваются и не грузятся.
    assert "duetPresenterIdFromForm(state)" in prepare_avatar
    assert "заведите его ниже" in prepare_avatar
    assert "avatarInputMode(panel)" not in prepare_avatar
    assert "uploadProjectMedia(avatarFile" not in prepare_avatar
    assert 'mode === "photo"' not in prepare_avatar
    assert "strategy_id: AVATAR_AUTHORITY_STRATEGY" in prepare_avatar
    assert 'strategy_id: "character_performance"' not in prepare_avatar
    assert "duet_presenter_id: duetPresenterIdFromForm(state)" in prepare_avatar
    assert "openNativeLaunch(form, handoff)" in prepare_avatar
    assert "launch_enabled: Boolean(duetPresenterIdFromForm(state))" in prepare_avatar
    assert "launch_enabled: false" not in prepare_avatar

    # Товара у стратегии нет ни в каком виде.
    assert "original_product_image" not in prepare_avatar
    assert "new_product_image" not in prepare_avatar
    assert "product_media_ids: []" in prepare_avatar

    # Регистрация ведущего из каталога провайдера: ключ живёт на сервере.
    registration = between(
        source,
        "function duetPresenterRegistration()",
        "function applyDuetPresenterLayout(",
    )
    assert "api.duetPresenterCatalog()" in registration
    assert "api.registerDuetPresenter(projectId()" in registration
    assert "duet_provider_key_missing" in registration
    assert "providerAvatarKind: kind" in registration
    # Шаблон брифа — речь, а не задание модели.
    template = between(source, "const DEFAULT_BRIEF_TEMPLATES", "});")
    assert "Сохранить сцены" not in template
    assert "Смотрите, как он держит товар" in template


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
        '[data-ce-v4-generation-guided-shell]'
        in styles
    )


def test_v4_owns_one_guided_shell_and_moves_it_without_cloning_controls() -> None:
    source = text(V4)
    mount = between(source, "function mount(form)", "function scheduleMount()")
    placement = between(
        source,
        "function placeGuidedShell",
        "function ensureStrategyAuthority",
    )

    assert 'q("[data-ce-v4-generation-guided-shell]", form)' in placement
    assert 'q("[data-generation-intake-strategy-host]", state?.shell)' in placement
    assert 'route === "strategy_video"' in placement
    assert "host.append(guidedShell)" in placement
    assert "state.shell.after(guidedShell)" in placement
    assert "cloneNode" not in placement
    assert "placeGuidedShell(form, existing, existing.route)" in mount


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
    """«Аватар» не должен молча исполняться маршрутом «Копии».

    Прежняя редакция стерегла это грубо: запрещала упоминать `viral_avatar_ugc`
    в файле вообще. Смысл был верный — пока у формы не было настоящего моста к
    стратегии, любое такое упоминание означало бы подмену. Но запрет на ИМЯ
    запрещал заодно и правильную работу: каскад выбора движка обязан спрашивать
    маршруты у той стратегии, чью панель он рисует, а значит обязан её называть.

    Проверяется то же самое, но по существу: панель аватара принадлежит своей
    стратегии, а не «Копии», и её маршруты берутся по её же идентификатору.
    """

    source = text(V4)

    assert "provider_feature_flag: CHARACTER_PERFORMANCE_FEATURE" in source
    assert "launch_enabled: false" in source

    # Панель аватара привязана к своей стратегии, и связь объявлена данными, а
    # не разбросана литералами по обработчикам.
    assert 'const AVATAR_AUTHORITY_STRATEGY = "viral_avatar_ugc"' in source
    assert "avatar_video: AVATAR_AUTHORITY_STRATEGY" in source
    assert "copy_video: COPY_AUTHORITY_STRATEGY" in source

    # Каскад спрашивает маршруты у переданной стратегии. Литерал «Копии» внутри
    # чтения маршрутов означал бы ровно ту подмену, от которой стоит этот тест.
    routes = between(
        source,
        "function guidedEngineRoutes(strategyId)",
        "function engineRoutesFor(strategyId)",
    )
    assert "getStrategyProviderRoutes?.(strategyId)" in routes
    assert "strategyProviderRoutes?.[strategyId]" in routes
    assert "COPY_AUTHORITY_STRATEGY" not in routes


def test_strategy_uses_one_from_zero_constructor_and_exact_authority() -> None:
    source = text(V4)
    guided = text(GUIDED)

    assert "MAX_STRATEGY_FILES = 10" in source
    assert "input.multiple = multiple" in source
    assert "files.length > MAX_STRATEGY_FILES" in source
    assert 'bindRoleAsset(form, "source_video", mediaId)' in source
    assert "refreshStrategyAssets" in source
    upload = between(
        source,
        "async function uploadStrategySources(form)",
        "function setRoute",
    )
    assert "strategy_id" not in upload
    assert "viral_rebuild" not in upload
    assert 'const STRATEGY_AUTHORITY_STRATEGY = "viral_rebuild"' in source
    assert 'strategy_video: STRATEGY_AUTHORITY_STRATEGY' in source
    assert "state.strategyAuthorityRequested = nextRoute === \"strategy_video\"" in source
    assert "ensureStrategyAuthority(form, state)" in source
    assert "Ниже остаётся действующая шестишаговая форма" not in source
    assert "generation-intake-v4__strategy-host" in source
    assert 'q("[data-ce-v4-generation-guided-shell]", form)' in guided
    assert ':scope > [data-ce-v4-generation-guided-shell]' not in guided
    assert 'label: "Модель ИИ"' in guided
    assert "Как создать ролик по вирусному референсу" not in guided
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


def test_strategy_and_engine_choices_have_local_visual_cards() -> None:
    source = text(V4)
    styles = text(CSS)

    # Route and model heroes are generated project assets, not provider
    # hotlinks. Journey glyphs remain lightweight inline SVG.
    assert "const VISUAL_ICON_PATHS" in source
    assert "const STRATEGY_VISUALS" in source
    for visual in ('swap: Object.freeze', 'avatar: Object.freeze', 'strategy: Object.freeze'):
        assert visual in source
    route_assets = (
        "content-factory-strategy-copy-v1.png",
        "content-factory-strategy-avatar-v1.png",
        "content-factory-strategy-builder-v1.png",
    )
    for asset_name in route_assets:
        assert f'image: "./assets/{asset_name}"' in source
        asset = ROOT / "web/app/assets" / asset_name
        assert asset.exists()
        assert asset.stat().st_size > 500_000
        assert asset.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    for visual in ('return "pika"', 'return "kling"', 'return "runway"'):
        assert visual in source
    assert "const MODEL_VISUALS" in source
    model_assets = (
        "content-factory-model-pika-v1.png",
        "content-factory-model-kling-v1.png",
        "content-factory-model-runway-v1.png",
    )
    for asset_name in model_assets:
        assert f'image: "./assets/{asset_name}"' in source
        asset = ROOT / "web/app/assets" / asset_name
        assert asset.exists()
        assert asset.stat().st_size > 500_000
        assert asset.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert "createElementNS" in source
    visual_contract = source[
        source.index("const VISUAL_ICON_PATHS"):source.index("function routeButton")
    ]
    assert 'document.createElement("img")' in visual_contract
    assert "image.src = new URL(visual.image, import.meta.url).href" in visual_contract
    assert 'image.alt = ""' in visual_contract
    assert 'image.loading = "eager"' in visual_contract
    assert 'image.decoding = "async"' in visual_contract
    assert "https://" not in visual_contract
    assert ".generation-intake-v4__route-scene-image" in styles
    assert "object-fit: cover" in styles
    assert "aspect-ratio: 16 / 9" in styles
    assert "@keyframes gi-route-cinematic-push" in styles

    render = between(
        source,
        "function renderChoiceChips",
        "function cascadeStep",
    )
    assert "ИИ-центр рекомендует" in render
    assert 'input.type = "radio"' in render
    assert "Выбрать модель" in render
    assert "modelVisualNode(visual)" in render
    assert 'chip.dataset.visual = visual' in render
    for fact in ("Цена", "Длина", "Условия"):
        assert fact in render
    assert '.gi-model-choice:has(input:checked)' in styles
    assert ".gi-model-choice__visual" in styles
    assert ".gi-model-choice__image" in styles
    assert "object-fit: cover" in styles
    assert ":has(input:focus-visible)" in styles
    assert "gi-model-cinematic-drift" in styles
    assert '@keyframes gi-model-glow' in styles


def test_strategy_cards_keep_rich_scenes_without_a_duplicate_route_map() -> None:
    source = text(V4)
    styles = text(CSS)

    assert "function routeSceneNode" in source
    assert 'routeButton("copy_video"' in source
    assert 'routeButton("avatar_video"' in source
    assert 'routeButton("strategy_video"' in source

    # Keep the three visual strategy choices, but do not repeat their workflow
    # in a second, cheaper-looking "path to decision" block below the cards.
    assert "const ROUTE_JOURNEYS" not in source
    assert "function routeJourney" not in source
    assert "Путь до решения" not in source
    assert "data-generation-intake-journey" not in source
    assert ".generation-intake-v4__journey" not in styles

    for fact in (
        "5 этапов · 5–7 мин",
        "4 этапа · 5–6 мин",
        "6 этапов · 10–15 мин",
    ):
        assert fact in source

    assert ".generation-intake-v4__route-scene" in styles
    assert "@keyframes gi-route-cinematic-push" in styles
    assert "@container (max-width: 920px)" in styles


def test_ai_center_recommendation_stays_an_editable_human_decision() -> None:
    source = text(V4)
    styles = text(CSS)
    recommendation = between(source, "function recommendationSlot", "function rightsConfirmation")

    assert "function humanAuthorityStrip" in source
    assert 'strip.dataset.generationIntakeHumanAuthority = ""' in source
    assert "ИИ-центр" in source
    assert "Рекомендует черновик" in source
    assert "Правит под задачу" in source
    assert "Фиксирует решение" in source
    assert "Рекомендация приходит из ИИ-центра как редактируемый черновик" in recommendation
    assert "Автозапуска нет" in recommendation
    assert "humanAuthorityStrip()" in recommendation
    assert ".generation-intake-v4__authority" in styles
    assert '.generation-intake-v4__authority-step[data-state="human"]' in styles


def test_product_photo_cards_keep_three_columns_and_stable_media_geometry() -> None:
    styles = " ".join(text(CSS).split())

    # Markup is checkbox + thumbnail + copy, so the scoped grid must have all
    # three columns. This prevents filenames collapsing into one-letter lines.
    assert "grid-template-columns: 18px minmax(68px, 82px) minmax(0, 1fr);" in styles
    assert "aspect-ratio: 1;" in styles
    assert "object-fit: contain;" in styles
    assert "grid-auto-rows: max-content;" in styles
    assert "-webkit-line-clamp: 2;" in styles
    assert "overflow-wrap: anywhere;" in styles
    assert ".generation-intake-v4__product-items .generation-media-option:hover" in styles


def test_route_tab_and_strategy_upload_never_select_a_paid_strategy() -> None:
    source = text(V4)
    set_route = between(source, "function setRoute", "function bind(")
    upload = between(
        source,
        "async function uploadStrategySources(form)",
        "function setRoute",
    )

    # Route tabs and source upload only prepare editable material. The exact
    # strategy remains a separate human choice in the full constructor.
    assert "selectStrategy" not in set_route
    assert "selectStrategy" not in upload
    assert "userInitiated" not in source
    assert "selectStrategy(form, handoff.strategy_id)" in source
    assert "Стратегия не выбрана" in upload
    assert 'action === "generation-intake-prepare-copy"' in source


def test_route_busy_state_is_announced_and_disables_the_exact_action() -> None:
    source = text(V4)
    analyze = between(source, "async function analyzeRoute", "async function ensureSourceMedia")
    copy = between(source, "async function prepareCopy(form)", "async function prepareAvatar(form)")
    avatar = between(source, "async function prepareAvatar(form)", "async function uploadStrategySources(form)")
    strategy = between(source, "async function uploadStrategySources(form)", "function setRoute")

    assert 'setAttribute("aria-busy", "true")' in source
    assert "generationIntakeBusyPreviousDisabled" in source
    assert "Операция уже выполняется" in source
    for body in (analyze, copy, avatar, strategy):
        assert "reportRouteBusy" in body
        assert "beginRouteBusy" in body
        assert "finishRouteBusy" in body


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


def test_fresh_original_product_frame_is_materialized_before_role_binding() -> None:
    source = text(V4)
    launch = between(source, "async function openNativeLaunch", "function frameAsFile")
    materialize = between(
        source,
        "function ensureOriginalProductOption",
        "async function ensureCopySourceVideos",
    )

    assert 'role === "original_product_image"' in launch
    assert "ensureOriginalProductOption(form, handoffOriginalProduct.media_id)" in launch
    assert launch.index("ensureOriginalProductOption(") < launch.index("let missing")
    assert "bindHandoffAsset(form, handoff, asset)" in launch
    # The synthetic option is transport for an already registered exact UUID,
    # not a browser-side eligibility or rights assertion.
    assert "UUID_PATTERN.test(id)" in materialize
    assert "generation_strategy_original_product_media_id" in materialize
    assert "eligible" not in materialize
    assert "rights" not in materialize
    assert "select.value" not in materialize

    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI contracts"
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(text(V4), encoding="utf-8")
        (directory / "contract.mjs").write_text(
            """
globalThis.window = {
  location: { hash: "#/outside" },
  addEventListener() {},
};
globalThis.document = { documentElement: {} };
globalThis.MutationObserver = class { observe() {} };
globalThis.Option = class {
  constructor(text, value) {
    this.text = text;
    this.value = value;
    this.dataset = {};
    this.disabled = false;
    this.selected = false;
  }
};
globalThis.HTMLSelectElement = class {
  constructor() {
    this.options = [new Option("placeholder", "")];
  }
  append(option) { this.options.push(option); }
};

const subject = await import("./subject.mjs");
const select = new HTMLSelectElement();
const form = {
  elements: { generation_strategy_original_product_media_id: select },
};
const id = "10000000-0000-4000-8000-000000000001";
const first = subject.ensureOriginalProductOption(form, id.toUpperCase());
const second = subject.ensureOriginalProductOption(form, id);
const rejected = subject.ensureOriginalProductOption(form, "not-a-uuid");
process.stdout.write(JSON.stringify({
  count: select.options.length,
  value: first?.value,
  label: first?.text,
  synthetic: first?.dataset?.generationIntakeSynthetic,
  selected: first?.selected,
  idempotent: first === second,
  rejected: rejected === null,
}));
""",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    assert json.loads(result.stdout) == {
        "count": 2,
        "value": "10000000-0000-4000-8000-000000000001",
        "label": "Кадр исходного товара · загружен только что",
        "synthetic": "true",
        "selected": False,
        "idempotent": True,
        "rejected": True,
    }


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


def test_express_copy_single_rights_checkbox_maps_to_four_attestations() -> None:
    source = text(V4)

    # ТЗ владельца: ОДНА консолидированная галка прав. Текст покрывает
    # референс, переработку, изображения товара и согласия людей, а её
    # применение ставит четыре настоящих чекбокса мастера через их обычные
    # change-события. Юридически подтверждения остаются раздельными на сервере.
    assert "const COPY_ATTESTATION_IDS = Object.freeze([" in source
    assert '"source_media_rights_confirmed"' in source
    assert '"transformative_use_confirmed"' in source
    assert '"product_assets_rights_confirmed"' in source
    assert '"depicted_people_consent_confirmed"' in source
    assert "Подтверждаю все права одним действием" in source
    apply_rights = between(
        source,
        "function applyConsolidatedRights",
        "function approvePendingSpecVersions",
    )
    assert "COPY_ATTESTATION_IDS.forEach" in apply_rights
    assert 'input.dispatchEvent(new Event("change", { bubbles: true }))' in apply_rights
    # Fail-closed: недоступное подтверждение попадает в список missing и
    # честно показывается человеку, а не пропускается молча.
    assert apply_rights.count("missing.push(attestationId)") == 2
    assert "return missing" in apply_rights
    assert "Не удалось автоматически проставить подтверждения прав" in source
    assert "COPY_ATTESTATION_LABELS[id] || id" in source

    drive = between(
        source,
        "async function driveStrategyPreflight",
        "function priceButtonFor",
    )
    # Guided renders the server-catalogued strategy attestations asynchronously.
    # Compact waits briefly for those exact controls and retries only SELECT;
    # it still fails closed when they never appear.
    assert "EXPRESS_ATTESTATION_RENDER_POLL_LIMIT" in drive
    assert "attestationRenderPolls += 1" in drive
    assert "selectStrategy(form, COPY_AUTHORITY_STRATEGY)" in drive
    assert "await waitMs(EXPRESS_POLL_INTERVAL_MS)" in drive
    assert 'new Error("express_attestations_unavailable")' in drive


def test_consolidated_rights_require_and_check_exact_strategy_attestations() -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI contracts"
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(text(V4), encoding="utf-8")
        (directory / "contract.mjs").write_text(
            """
globalThis.window = {
  location: { hash: "#/outside" },
  addEventListener() {},
};
globalThis.document = { documentElement: {} };
globalThis.MutationObserver = class { observe() {} };
globalThis.CSS = { escape(value) { return String(value); } };
globalThis.Event = class { constructor(type) { this.type = type; } };
globalThis.HTMLInputElement = class {
  constructor({ checked = false, disabled = false } = {}) {
    this.checked = checked;
    this.disabled = disabled;
    this.dataset = {};
    this.changes = 0;
  }
  dispatchEvent(event) {
    if (event?.type === "change") this.changes += 1;
    return true;
  }
};

const subject = await import("./subject.mjs");
const ids = [
  "source_media_rights_confirmed",
  "transformative_use_confirmed",
  "product_assets_rights_confirmed",
  "depicted_people_consent_confirmed",
];
const consolidated = new HTMLInputElement({ checked: true });
const native = new Map();
const panel = {
  querySelector(selector) {
    return selector === '[data-generation-intake-rights="copy_video"]'
      ? consolidated
      : null;
  },
};
const form = {
  // These two legacy flags are deliberately true: they cannot stand in for
  // the four exact strategy attestations required by the server contract.
  elements: {
    generation_reference_source_access_confirmed: { checked: true },
    generation_reference_transformative_use_confirmed: { checked: true },
  },
  querySelector(selector) {
    const match = selector.match(/data-generation-strategy-attestation="([^"]+)"/u);
    return match ? native.get(match[1]) || null : null;
  },
};

const missingWithLegacyOnly = subject.applyConsolidatedRights(form, panel);
ids.forEach((id) => native.set(id, new HTMLInputElement()));
const applied = subject.applyConsolidatedRights(form, panel);
const checked = ids.map((id) => native.get(id).checked);
const changes = ids.map((id) => native.get(id).changes);
native.get(ids[2]).checked = false;
native.get(ids[2]).disabled = true;
const disabledMissing = subject.applyConsolidatedRights(form, panel);

process.stdout.write(JSON.stringify({
  missingWithLegacyOnly,
  applied,
  checked,
  changes,
  disabledMissing,
}));
""",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    expected_ids = [
        "source_media_rights_confirmed",
        "transformative_use_confirmed",
        "product_assets_rights_confirmed",
        "depicted_people_consent_confirmed",
    ]
    assert payload == {
        "missingWithLegacyOnly": expected_ids,
        "applied": [],
        "checked": [True, True, True, True],
        "changes": [1, 1, 1, 1],
        "disabledMissing": ["product_assets_rights_confirmed"],
    }


def test_express_copy_preserves_explicit_campaign_and_only_defaults_without_choice() -> None:
    source = text(V4)

    # An explicit choice is restored across renders and fails closed when the
    # campaign disappears. Fallback is reserved for never-chosen contexts.
    assert "function autoSelectCampaign" in source
    campaign = between(
        source,
        "function availableCampaignOptions",
        "function serverPriceLabel",
    )
    assert "campaign_id" in campaign
    assert "!option.disabled" in campaign
    assert "campaign_explicit" in campaign
    assert "invalidExplicit: explicit && !target" in campaign
    assert "if (explicit)" in campaign
    assert "options[options.length - 1]" in campaign
    assert "function compactCampaignChoice()" in source
    assert "function commitCompactCampaignSelection" in source
    assert (
        'const NEW_CAMPAIGN_ROUTE_HASH = "#/workspace/team?view=new-campaign"'
        in source
    )
    assert "generationIntakeCampaignNote" in source
    assert "нет активной кампании" in source


def test_express_campaign_selection_contract_executes_fail_closed() -> None:
    node = shutil.which("node")
    if not node:
        raise AssertionError("Node.js is required for the executable campaign contract")

    source = text(V4)
    campaign_function = "function normalizedCampaignId" + between(
        source,
        "function normalizedCampaignId",
        "function setCampaignNote",
    )
    campaign_a = "11111111-1111-4111-8111-111111111111"
    campaign_b = "22222222-2222-4222-8222-222222222222"
    campaign_c = "33333333-3333-4333-8333-333333333333"

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        (directory / "contract.mjs").write_text(
            f"""
class HTMLSelectElement {{
  constructor(options, value = "") {{
    this.options = options;
    this.value = value;
  }}
}}
const UUID_PATTERN = /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-5][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/iu;
const expressDefaultsMemory = new Map();
const projectId = () => "project-1";
{campaign_function}

function run(options, value, saved = null) {{
  expressDefaultsMemory.clear();
  if (saved) expressDefaultsMemory.set("project-1", saved);
  const campaign = new HTMLSelectElement(options, value);
  const resolved = resolveExpressCampaign({{ elements: {{ campaign_id: campaign }} }});
  return {{
    id: resolved.id,
    explicit: resolved.explicit,
    invalidExplicit: resolved.invalidExplicit,
  }};
}}

const currentDefault = run([
  {{ value: "{campaign_a}", disabled: false }},
  {{ value: "{campaign_b}", disabled: false }},
  {{ value: "{campaign_c}", disabled: false }},
], "{campaign_b}");
const explicit = run([
  {{ value: "{campaign_a}", disabled: false }},
  {{ value: "{campaign_b}", disabled: false }},
  {{ value: "{campaign_c}", disabled: false }},
], "{campaign_a}", {{ campaign_id: "{campaign_b}", campaign_explicit: true }});
const explicitDisabled = run([
  {{ value: "{campaign_a}", disabled: false }},
  {{ value: "{campaign_b}", disabled: true }},
  {{ value: "{campaign_c}", disabled: false }},
], "{campaign_a}", {{ campaign_id: "{campaign_b}", campaign_explicit: true }});
const fallback = run([
  {{ value: "not-a-uuid", disabled: false }},
  {{ value: "{campaign_a}", disabled: false }},
  {{ value: "{campaign_c}", disabled: false }},
], "not-a-uuid");
const empty = run([{{ value: "not-a-uuid", disabled: false }}], "not-a-uuid");
console.log(JSON.stringify({{ currentDefault, explicit, explicitDisabled, fallback, empty }}));
""",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["currentDefault"] == {
        "id": campaign_b,
        "explicit": False,
        "invalidExplicit": False,
    }
    assert payload["explicit"] == {
        "id": campaign_b,
        "explicit": True,
        "invalidExplicit": False,
    }
    assert payload["explicitDisabled"] == {
        "id": "",
        "explicit": True,
        "invalidExplicit": True,
    }
    assert payload["fallback"] == {
        "id": campaign_c,
        "explicit": False,
        "invalidExplicit": False,
    }
    assert payload["empty"] == {
        "id": "",
        "explicit": False,
        "invalidExplicit": False,
    }


def test_express_price_button_is_two_phase_and_never_skips_human_launch_click() -> None:
    source = text(V4)

    # «Показать цену» = бесплатные фазы действующего мастера (ТЗ → одобрение →
    # preflight) с точной серверной ценой; после этого кнопка превращается в
    # «Запустить за $X», и платный старт происходит только по явному клику,
    # который ставит настоящий чекбокс подтверждения цены.
    assert "Показать цену" in source
    assert "Запустить за" in source
    assert "const EXPRESS_FREE_SUBMIT_PHASES = Object.freeze([" in source
    assert '"strategy_product_swap_prepare"' in source
    assert '"strategy_product_swap_spec_review"' in source
    assert '"strategy_product_swap_free_preflight"' in source
    drive = between(
        source,
        "async function driveStrategyPreflight",
        "function priceButtonFor",
    )
    assert 'form.dataset.generationStrategyConfirmationReady === "true"' in drive
    assert "EXPRESS_FREE_SUBMIT_PHASES.includes(phase)" in drive
    assert "express_preflight_blocked" in drive
    launch = between(
        source,
        "async function startExpressLaunch",
        "async function prepareCopy(form)",
    )
    assert "autoSelectCampaign(form, panel, state)" in launch
    assert launch.count("expressCampaignMatchesPrice(") == 2
    assert "confirmation.click()" in launch
    assert "submitButton.click()" in launch
    binding = between(source, "function bind(form, state)", "function mount(form)")
    assert 'trigger?.dataset.expressPhase === "priced"' in binding
    assert "void startExpressLaunch(form)" in binding
    assert "void prepareCopy(form)" in binding


def test_compact_paid_cta_fails_closed_after_strategy_authority_is_consumed() -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI contracts"
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(text(V4), encoding="utf-8")
        (directory / "contract.mjs").write_text(
            r'''
class FakeButton {
  constructor() {
    this.dataset = {};
    this.disabled = false;
    this.textContent = "";
    this.title = "";
  }
}

globalThis.HTMLButtonElement = FakeButton;
globalThis.CSS = { escape(value) { return String(value); } };
globalThis.window = {
  location: { hash: "#/outside" },
  addEventListener() {},
};
globalThis.document = { documentElement: {} };
globalThis.MutationObserver = class { observe() {} };

const subject = await import("./subject.mjs");
const compact = new FakeButton();
compact.dataset.expressPhase = "priced";
compact.textContent = "Запустить за $0.47";
const nativeSubmit = new FakeButton();
nativeSubmit.dataset.launchPhase = "strategy_product_swap_paid_locked";
const form = {
  dataset: { generationStrategyPaidLocked: "true" },
  querySelector(selector) {
    return selector === "#generation-submit" ? nativeSubmit : null;
  },
};
const panel = {
  querySelector(selector) {
    return selector === '[data-action="generation-intake-prepare-copy"]'
      ? compact
      : null;
  },
};
const shell = {
  closest(selector) { return selector === "form" ? form : null; },
  querySelector(selector) {
    return selector === '[data-generation-intake-panel="copy_video"]'
      ? panel
      : null;
  },
};
const state = {
  shell,
  express: {
    phase: "priced",
    price: "$0.47",
    spend_confirmation: "PAY $0.47 ONCE",
  },
};

subject.syncExpressPriceButton(state);
const locked = {
  disabled: compact.disabled,
  phase: compact.dataset.expressPhase,
  text: compact.textContent,
  price: state.express.price,
  confirmation: state.express.spend_confirmation,
  helper: subject.expressPaidAuthorityLocked(form),
};

delete form.dataset.generationStrategyPaidLocked;
nativeSubmit.dataset.launchPhase = "strategy_product_swap_free_preflight";
subject.syncExpressPriceButton(state);
const freshContext = {
  disabled: compact.disabled,
  phase: compact.dataset.expressPhase,
  text: compact.textContent,
  helper: subject.expressPaidAuthorityLocked(form),
};

process.stdout.write(JSON.stringify({ locked, freshContext }));
''',
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["locked"] == {
        "disabled": True,
        "phase": "locked",
        "text": "Этот запуск уже использован",
        "price": "",
        "confirmation": "",
        "helper": True,
    }
    assert payload["freshContext"] == {
        "disabled": False,
        "phase": "idle",
        "text": "Подготовить ролик",
        "helper": False,
    }


def test_express_counter_combines_pending_files_and_checked_photos_live() -> None:
    source = text(V4)

    # Грабля владельца: счётчик обязан считать вместе файлы из input и
    # отмеченные готовые фото, показывать «Сейчас: N из 5» живьём и при
    # переборе объяснять, что снять галочки или очистить файлы.
    assert (
        "selectedProductMediaIds(form).length + selectedProductFiles(panel).length"
        in source
    )
    refresh = between(
        source,
        "function refreshProductSelectionCount",
        "function selectedProductIdentityFromCheckboxes",
    )
    assert "`Сейчас: ${count} из ${MAX_PRODUCT_IMAGES}`" in refresh
    assert "Снимите галочки с готовых фото или очистите поле загрузки файлов" in refresh
    prepare_copy = between(
        source,
        "async function prepareCopy(form)",
        "async function prepareAvatar(form)",
    )
    assert "productCount > MAX_PRODUCT_IMAGES" in prepare_copy


def test_express_auto_defaults_survive_re_render_and_hide_known_identity() -> None:
    source = text(V4)

    # Автоматика «под капотом»: звук «Без звука» по умолчанию, формат из
    # серверного каталога; SKU/название спрашиваются только для новых фото без
    # идентичности, категория — только если неизвестна. Значения переживают
    # перерисовку страницы через память экспресс-панели.
    assert 'audio.value = "false"' in source
    assert "function applyAutoOutputDefaults" in source
    assert "const expressDefaultsMemory = new Map()" in source
    assert "function rememberExpressDefaults" in source
    assert "function applyExpressDefaults" in source
    assert "function refreshIdentityVisibility" in source
    assert "function selectedProductIdentityFromCheckboxes" in source
    assert "mediaSku" in source
    assert "mediaProductName" in source
    mount = between(source, "function mount(form)", "function scheduleMount()")
    assert "applyExpressDefaults(form, existing)" in mount
    assert "syncExpressPriceButton(existing)" in mount
    set_route = between(source, "function setRoute", "function bind(")
    assert "applyExpressDefaults(form, state)" in set_route
    assert "prefillCopyRecommendation(form, state)" not in set_route
    assert "refreshIdentityVisibility(form, state)" in set_route


def test_copy_screen_route_renders_no_wizard_steps_at_all() -> None:
    source = text(V4)
    styles = " ".join(text(CSS).split())

    # Вердикт владелицы: «кусок формы болтается» — запрещено. Отдельный экран
    # #/workspace/generation?view=copy показывает ТОЛЬКО пять блоков экспресс-
    # формы; guided-шелл с шагами 01–06, «Режим и бюджет» и модельными
    # карточками, а также шапка «Что нужно сделать?» и вкладки трёх маршрутов
    # не видны вообще. Скрытый #mock-batch-form остаётся движком.
    assert 'const COPY_VIEW_QUERY = "copy"' in source
    assert 'routeParams().get("view") === COPY_VIEW_QUERY' in source
    assert (
        '#mock-batch-form[data-generation-intake-v4-mode="copy"] '
        '> :not([data-generation-intake-v4]) { display: none !important; }'
        in styles
    )
    assert (
        '[data-generation-intake-v4] .generation-intake-v4__head' in styles
    )
    assert (
        '[data-generation-intake-v4] .generation-intake-v4__routes' in styles
    )
    # Подготовка не переключает экран копии в «full»: движок остаётся скрытым.
    launch = between(source, "async function openNativeLaunch", "function frameAsFile")
    assert 'copyScreen ? "copy" : "full"' in launch
    assert "if (!copyScreen) {" in launch
    set_route = between(source, "function setRoute", "function bind(")
    assert "copyViewActive()" in set_route
    # Пять блоков в один столбец.
    assert "grid-template-columns: minmax(0, 1fr)" in styles


def test_copy_screen_photo_selection_survives_re_render() -> None:
    source = text(V4)

    # Санити-контракт на главную жалобу: «теряет фото, опять грузить 2й раз».
    # Файлы регистрируются на сервере сразу при выборе тем же путём, что и
    # подготовка (uploadProjectMedia → api.registerMedia), показываются
    # выбранными чипами, file-инпут очищается, а выбор персистится в
    # sessionStorage по проекту и восстанавливается при каждом монтировании.
    assert 'const COPY_PHOTO_STORAGE_PREFIX = "generation-copy-photos-v1:"' in source
    assert "const pendingCopyProductFiles = new Map()" in source
    register = between(
        source,
        "async function registerSelectedProductPhotos",
        "function generationViewHref",
    )
    assert 'uploadProjectMedia(file, "product_photo", identity)' in register
    assert "ensureProductCheckbox(form, state, mediaId, identity, file.name)" in register
    assert 'input.value = ""' in register
    assert "persistCopyPhotoSelection(form)" in register
    assert "не потеряются" in register or "не потеряны" in register
    persist = between(
        source,
        "function persistCopyPhotoSelection",
        "function restoreCopyPhotoSelection",
    )
    assert "sessionStorage.setItem(copyPhotoStorageKey()" in persist
    assert "orderedCheckedProductInputs(form)" in persist
    assert ".slice(0, MAX_PRODUCT_IMAGES)" in persist
    restore = between(
        source,
        "function restoreCopyPhotoSelection",
        "async function registerSelectedProductPhotos",
    )
    assert "sessionStorage.getItem(copyPhotoStorageKey()" in restore
    assert "ensureProductCheckbox(" in restore
    assert "setProductSelectionOrder(existing, index + 1)" in restore
    assert "setProductSelectionOrder(restored, index + 1)" in restore
    mount = between(source, "function mount(form)", "function scheduleMount()")
    assert mount.count("restoreCopyPhotoSelection(form,") == 2
    # Очередь в памяти не даёт потерять ещё не зарегистрированные файлы.
    files = between(source, "function selectedProductFiles", "function selectedAvatarFile")
    assert "pendingCopyProductFiles.get(projectId())" in files


def test_existing_product_media_use_click_order_across_dom_reorder_and_reselection() -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI contracts"
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            text(V4),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            """
globalThis.window = {
  location: { hash: "#/outside" },
  addEventListener() {},
};
globalThis.document = { documentElement: {} };
globalThis.MutationObserver = class { observe() {} };

const subject = await import("./subject.mjs");
const ids = [
  "00000000-0000-4000-8000-000000000001",
  "00000000-0000-4000-8000-000000000002",
  "00000000-0000-4000-8000-000000000003",
  "00000000-0000-4000-8000-000000000004",
  "00000000-0000-4000-8000-000000000005",
  "00000000-0000-4000-8000-000000000006",
];
let inputs = ids.map((value) => ({
  value,
  checked: false,
  disabled: false,
  dataset: {},
}));
const productRoot = {
  querySelectorAll(selector) {
    return selector === 'input[name="media_id"]:checked'
      ? inputs.filter((input) => input.checked)
      : [];
  },
};
const form = {
  dataset: {},
  querySelector(selector) {
    return selector === ".generation-intake-v4__product-items"
      ? productRoot
      : null;
  },
};
const input = (id) => inputs.find((candidate) => candidate.value === id);
const select = (id) => {
  input(id).checked = true;
  subject.rememberProductSelectionChange(form, input(id));
};
const deselect = (id) => {
  input(id).checked = false;
  subject.rememberProductSelectionChange(form, input(id));
};

const clickOrder = [ids[2], ids[0], ids[4], ids[1], ids[3]];
clickOrder.forEach(select);
const initial = subject.selectedProductMediaIds(form);
inputs = [...inputs].reverse();
const afterDomReorder = subject.selectedProductMediaIds(form);
deselect(ids[0]);
select(ids[0]);
const afterReselect = subject.selectedProductMediaIds(form);
select(ids[5]);
const overflowOrder = subject.selectedProductMediaIds(form);

process.stdout.write(JSON.stringify({
  initial,
  afterDomReorder,
  afterReselect,
  overflowOrder,
}));
""",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    expected = [
        "00000000-0000-4000-8000-000000000003",
        "00000000-0000-4000-8000-000000000001",
        "00000000-0000-4000-8000-000000000005",
        "00000000-0000-4000-8000-000000000002",
        "00000000-0000-4000-8000-000000000004",
    ]
    assert payload["initial"] == expected
    assert payload["afterDomReorder"] == expected
    assert payload["afterReselect"] == [
        expected[0],
        expected[2],
        expected[3],
        expected[4],
        expected[1],
    ]
    # selectedProductMediaIds intentionally exposes one item beyond the cap so
    # prepareCopy can fail closed with the visible "too many" validation.
    assert payload["overflowOrder"] == [
        *payload["afterReselect"],
        "00000000-0000-4000-8000-000000000006",
    ]


def test_product_uncheck_is_persisted_on_input_before_rerender_restore() -> None:
    source = text(V4)
    binding = between(source, "function bind(form, state)", "function mount(form)")
    input_listener = binding.split(
        'state.shell.addEventListener("input", (event) => {',
        1,
    )[1]
    assert "captureProductSelectionChange(form, productCheckbox)" in input_listener
    capture = between(
        source,
        "function captureProductSelectionChange",
        "function selectedProductMediaIds",
    )
    assert "rememberProductSelectionChange(form, input)" in capture
    assert "persistCopyPhotoSelection(form)" in capture

    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI contracts"
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(text(V4), encoding="utf-8")
        (directory / "contract.mjs").write_text(
            """
const projectId = "20000000-0000-4000-8000-000000000001";
const storage = new Map();
globalThis.window = {
  location: { hash: `#/outside?project_id=${projectId}` },
  addEventListener() {},
};
globalThis.document = { documentElement: {} };
globalThis.MutationObserver = class { observe() {} };
globalThis.sessionStorage = {
  getItem(key) { return storage.get(key) ?? null; },
  setItem(key, value) { storage.set(key, String(value)); },
};

const subject = await import("./subject.mjs");
const ids = [
  "20000000-0000-4000-8000-000000000011",
  "20000000-0000-4000-8000-000000000012",
  "20000000-0000-4000-8000-000000000013",
  "20000000-0000-4000-8000-000000000014",
  "20000000-0000-4000-8000-000000000015",
];
const inputs = ids.map((value, index) => ({
  value,
  checked: true,
  disabled: false,
  dataset: { generationIntakeSelectionOrder: String(index + 1) },
  parentElement: null,
  closest() { return null; },
}));
const productRoot = {
  querySelectorAll(selector) {
    return selector === 'input[name="media_id"]:checked'
      ? inputs.filter((input) => input.checked)
      : [];
  },
};
const form = {
  dataset: {},
  querySelector(selector) {
    return selector === ".generation-intake-v4__product-items"
      ? productRoot
      : null;
  },
};
const storageKey = `generation-copy-photos-v1:${projectId}`;

// This is the checkbox state at the earliest bubbling input event.
inputs[0].checked = false;
subject.captureProductSelectionChange(form, inputs[0]);
const afterInput = JSON.parse(storage.get(storageKey));

// Simulate the MutationObserver mount that previously read stale five-item
// storage before the later change handler got a chance to persist the uncheck.
const restoredIds = new Set(afterInput.map((entry) => entry.id));
inputs.forEach((input) => { input.checked = restoredIds.has(input.value); });
const restoredFirstChecked = inputs[0].checked;

inputs[0].checked = true;
subject.captureProductSelectionChange(form, inputs[0]);
const afterReselect = JSON.parse(storage.get(storageKey)).map((entry) => entry.id);

process.stdout.write(JSON.stringify({
  afterInput: afterInput.map((entry) => entry.id),
  restoredFirstChecked,
  afterReselect,
}));
""",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["afterInput"] == [
        "20000000-0000-4000-8000-000000000012",
        "20000000-0000-4000-8000-000000000013",
        "20000000-0000-4000-8000-000000000014",
        "20000000-0000-4000-8000-000000000015",
    ]
    assert payload["restoredFirstChecked"] is False
    assert payload["afterReselect"] == [
        *payload["afterInput"],
        "20000000-0000-4000-8000-000000000011",
    ]


def test_copy_screen_suppresses_legacy_dry_run_hints() -> None:
    source = text(V4)
    styles = " ".join(text(CSS).split())
    guided = text(GUIDED)

    # «Готов только dry-run…», «вернитесь в „Режим и бюджет“» и
    # «Следующий шаг: …» живут внутри guided-шелла и readiness-панели —
    # оба являются потомками #mock-batch-form вне экспресс-шелла, поэтому
    # правило экрана копии скрывает их полностью.
    assert "Готов только dry-run" in guided
    assert "data-ce-v4-generation-launch-status" in guided
    assert (
        '#mock-batch-form[data-generation-intake-v4-mode="copy"] '
        '> :not([data-generation-intake-v4]) { display: none !important; }'
        in styles
    )
    assert "Готов только dry-run" not in source
    assert "Режим и бюджет" not in source


def test_copy_screen_video_priority_auto_analysis_and_sku_conflict() -> None:
    source = text(V4)

    # Ролик: серверно проверенные MP4 первыми и выбраны по умолчанию; для
    # нового MP4 разбор и бесплатная проверка встроены в «Показать цену».
    refresh = between(source, "function refreshVideoSelects", "function refreshAvatarSelect")
    assert "сервером проверен" in refresh
    assert "Number(right.verified) - Number(left.verified)" in refresh
    assert "firstVerified" in refresh
    prepare_copy = between(
        source,
        "async function prepareCopy(form)",
        "async function prepareAvatar(form)",
    )
    assert 'await analyzeRoute(form, "copy_video")' in prepare_copy
    # Товар — авто из выбранных фото; смешение SKU = одна честная ошибка с
    # точным списком, какие фото снять.
    assert "function productSkuConflict" in source
    assert "productSkuConflict(form)" in prepare_copy
    assert "Оставьте один SKU" in prepare_copy


def test_copy_screen_source_select_feeds_from_guided_picker() -> None:
    source = text(V4)

    # Прод-фикс: легаси-селект generation_strategy_source_video_id мёртв
    # (hidden+disabled, один плейсхолдер). Источник правды — чекбоксы пикера
    # guided-мастера: id из dataset.generationStrategySourceToggle, verified —
    # по подписи карточки «сервером проверен». Легаси-селект и разбор DOM
    # остаются fallback; при кандидатах пикера селект копии наполняется,
    # verified идут первыми и автовыбираются.
    picker = between(
        source,
        "function collectPickerVideos",
        "function refreshVideoSelects",
    )
    assert 'qa("input[data-generation-strategy-source-toggle]", form)' in picker
    assert "generationStrategySourceToggle" in picker
    assert "/сервером проверен/iu.test(caption)" in picker
    refresh = between(
        source,
        "function refreshVideoSelects",
        "function refreshAvatarSelect",
    )
    assert "collectPickerVideos(form)" in refresh
    assert "pickerVideos" in refresh
    assert "collectProjectVideos(form)" in refresh
    assert "generation_strategy_source_video_id" in refresh
    assert "Number(right.verified) - Number(left.verified)" in refresh
    assert "const firstVerified = videos.find(({ verified }) => verified)" in refresh
    assert "if (firstVerified) select.value = firstVerified.id" in refresh
    # Без выбранной стратегии guided не грузит кандидатов пикера: экран копии
    # выбирает viral_product_swap в скрытом визарде сразу при монтировании и
    # добирает его на каждом пересинке (кандидаты приходят асинхронно).
    ensure = between(
        source,
        "function ensureCopyEngineStrategy",
        "function generationViewHref",
    )
    assert "copyViewActive()" in ensure
    assert "selectStrategy(form, COPY_AUTHORITY_STRATEGY)" in ensure
    assert "refreshStrategyAssets" in ensure
    mount = between(source, "function mount(form)", "function scheduleMount()")
    assert mount.count("ensureCopyEngineStrategy(form)") == 2


def test_copy_price_gate_accepts_existing_server_frame_without_local_file() -> None:
    source = text(V4)
    prepare_copy = between(
        source,
        "async function prepareCopy(form)",
        "async function prepareAvatar(form)",
    )

    # Прод-разрыв: гейт «Показать цену» требовал локальный storyboard и
    # игнорировал уже выбранный кадр мастера. Контракт: гейт выполнен, если
    # generation_strategy_original_product_media_id содержит валидный uuid —
    # неважно, кто его установил.
    assert "function wizardOriginalProductMediaId" in source
    assert (
        "let originalProductMediaId = wizardOriginalProductMediaId(form)"
        in prepare_copy
    )
    # Серверный ролик + существующие кадры в нативном селекте: первый кадр
    # выбирается автоматически, без ручных действий и без локального файла.
    adopt = between(
        source,
        "function adoptExistingOriginalProductFrame",
        "function findMediaObjectKey",
    )
    assert "generation_strategy_original_product_media_id" in adopt
    assert 'select.dispatchEvent(new Event("change", { bubbles: true }))' in adopt
    assert "adoptExistingOriginalProductFrame(form, panel)" in prepare_copy
    # Пустой селект: серверный разбор — download подтверждённого MP4 из
    # защищённого хранилища и существующий storyboard с автолучшим кадром.
    server = between(
        source,
        "async function serverStoryboardForCopy",
        "// Вторая фаза кнопки цены",
    )
    assert "api.downloadPrivateObject" in server
    assert "api.contentReviewCatalog" in server
    assert "captureStoryboard" in server
    assert "storyboard.recommendedIndex" in server
    assert "serverStoryboardForCopy(state, panel, route.sourceMediaId)" in prepare_copy
    # Человек видит выбранный кадр; честный тупик — одна конкретная инструкция.
    # Повторная загрузка того же MP4 не чинит браузерный декодер, поэтому форма
    # открывает ручной стоп-кадр и просит приложить именно его.
    assert "function showChosenFrameNote" in source
    assert "Кадр исходного товара выбран" in source
    assert "noteChosenFrame(form, panel, originalProductMediaId)" in prepare_copy
    assert "загрузите локальный MP4 этого ролика" not in prepare_copy
    assert "Приложите стоп-кадр сами" in prepare_copy
    assert "frameSlot.hidden = false" in prepare_copy


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


def test_selected_mp4_status_names_the_button_visible_on_each_route() -> None:
    source = text(V4)
    helper = between(
        source,
        "function selectedSourceNextStep",
        "async function reportSelectedSourceDuration",
    )
    report = between(
        source,
        "async function reportSelectedSourceDuration",
        "async function analyzeRoute",
    )

    # Compact Copy has no button called «Разобрать MP4»: its analysis action is
    # labelled «Проверить ролик бесплатно». Read the actual action label instead
    # of sending the operator to a missing CTA. Avatar keeps its own label.
    assert '"generation-intake-analyze-copy"' in helper
    assert '"Проверить ролик бесплатно"' in helper
    assert '"generation-intake-analyze-avatar"' in helper
    assert '"Разобрать MP4"' in helper
    assert "selectedSourceNextStep(panel, route)" in report
    assert "Нажмите ${nextStep}" in report

    # The same source of truth is used after choosing an existing server MP4.
    assert source.count("selectedSourceNextStep(panel, route)") >= 3


def test_copy_engine_choice_is_a_three_step_cascade_from_the_route_registry() -> None:
    source = text(V4)
    render = between(
        source,
        "function renderEngineChoice(form, state, section, strategyId)",
        "let copyChecklistBusy = false;",
    )
    markup = between(source, "function engineCascadeCard()", "function copyChecklistRow")

    # Три ступени одна под другой: сам движок, его сложность, его тайминги.
    # Уровень цены отдельной ступенью не стоит — он подпись у модели, потому
    # что человек выбирает модель, а не «дёшево».
    assert 'cascadeStep("model", "1", "Модель", "generation_intake_generator")' in markup
    assert '"quality",\n    "2",\n    "Сложность",\n    "generation_intake_quality",' in markup
    assert '"duration",\n    "3",\n    "Длительность ролика",\n    "generation_intake_duration",' in markup
    assert "generation_intake_tier" not in source

    # Переключатель движка ровно один: прежний ряд «Генератор 1/2/3» стал
    # первой ступенью.
    assert source.count('"generation_intake_generator"') == 2
    assert "Генератор ${index + 1}" not in source

    # Данные — только из реестра маршрутов, без иных источников. Стратегия при
    # этом приходит параметром: каскад рисуется не только у «Копии».
    assert "getStrategyProviderRoutes?.(strategyId)" in source
    # Маршруты берутся у стратегии панели, а не у «Копии» литералом.
    assert "engineRoutesFor(strategyId)" in render
    for field in (
        "route.provider",
        "route.model_key",
        "route.tier",
        "route.price_kind",
        "route.price_rate_minor",
        "route.min_duration_seconds",
        "route.max_duration_seconds",
        "route.quality_modes",
        "route.recommended",
        "route.enabled",
    ):
        assert field in source

    # Пустой реестр не рисует выдуманный выбор.
    assert "if (!engines.length) {" in render


def test_copy_engine_cascade_shows_human_names_and_prices() -> None:
    source = text(V4)

    assert '"fal:fal-ai/pika/v2/pikaswaps": "Pika Swaps"' in source
    assert '"runway:aleph2": "Runway Aleph"' in source
    assert (
        '"fal:fal-ai/kling-video/o3/pro/video-to-video/edit": "Kling O3 Pro"'
        in source
    )
    # Неизвестная модель получает имя, а не пустое место и не идентификатор.
    assert "function fallbackModelLabel" in source
    assert '|| "Модель без имени"' in source
    assert "MODEL_PUBLIC_LABELS[engineId(route)]\n    || fallbackModelLabel(" in source

    # Цена видна у каждой модели вместе с её уровнем; там, где ставки нет,
    # сумма не придумывается.
    render = between(
        source,
        "function renderEngineChoice(form, state, section, strategyId)",
        "let copyChecklistBusy = false;",
    )
    assert "tierPublicLabel(engine.tier)" in render
    assert "routePriceNote(engine)" in render
    assert '"по ступеням кредитов"' in source
    assert '"цену назовёт сервер"' in source


def test_copy_engine_cascade_keeps_duration_where_the_form_already_puts_it() -> None:
    source = text(V4)
    render = between(
        source,
        "function renderEngineChoice(form, state, section, strategyId)",
        "let copyChecklistBusy = false;",
    )
    apply_duration = between(
        source,
        "function applyCopyDuration(form, seconds)",
        "function refreshEngineChoice(form, state)",
    )

    # Длительность пишется ровно туда, откуда её берёт подписанный выбор:
    # generation_strategy_duration_seconds → selection.duration_seconds.
    assert "generation_strategy_duration_seconds" in source
    assert "control.value = next" in apply_duration
    assert 'new Event("change", { bubbles: true })' in apply_duration

    # Окно модели пересекается с окном мастера: значение вне окна мастера
    # сервер не подпишет.
    window = between(
        source,
        "function engineDurationWindow(engine, form)",
        "// Длительность живёт там же",
    )
    assert "Math.max(wizard.min" in window
    assert "Math.min(wizard.max" in window

    # Несовместимое значение не остаётся молча неверным.
    assert "durations.includes(current) ? current : null" in render
    assert "не подходит для «${selectedEngine.label}»" in render
    assert "Оставили ${chosen} с." in render


def test_copy_engine_cascade_does_not_touch_the_signed_route() -> None:
    source = text(V4)
    render = between(
        source,
        "function renderEngineChoice(form, state, section, strategyId)",
        "let copyChecklistBusy = false;",
    )

    # Каскад переключает исполнение, но не подделывает подпись: выбор уходит
    # ПОЛЕМ ФОРМЫ, а цену, квитанцию и строку подтверждения расхода по-прежнему
    # выписывает сервер. Ни одного платного вызова отсюда не делается.
    assert "selectStrategy(" not in render
    assert "requested_model" not in render
    assert "spend_confirmation" not in render
    assert "generation_intake_engine" in render
    # Значение уходит в поле формы через общий помощник платного контекста.
    # Прямое присваивание value здесь запрещено: именно оно и было дырой —
    # запись без события минует путь инвалидации в app.js, и галка подтверждения
    # траты остаётся от прежнего движка. Помощник шлёт input/change при
    # настоящей смене и молчит при восстановлении того же выбора.
    assert "assignPaidContextValue(" in render
    assert "engineField.value =" not in render

    # Недоступную модель в поле не пишем: сервер такой маршрут не исполнит, и
    # тихо отправить его значило бы отказ вместо запуска.
    assert "selectedEngine?.enabled ? selectedEngine.id : \"\"" in render

    # Отметка «Советуем» осталась подсказкой, а не приговором. С 23.08.2026
    # совет даёт ИИ-центр по фактам запуска, отметка реестра — запасной ответ;
    # фраза «Исполнит …» живёт в engineAdviceNote и называет исполнение отдельно
    # от совета всегда.
    assert "engines.find((engine) => engine.recommended && engine.enabled)" in render
    assert "engineAdviceNote(selectedEngine, activeEngine, advice)" in render
    assert "не переключает запуск" not in render
    assert "Исполнит «${selectedEngine.label}»" in source.split(
        "function engineAdviceNote(", 1
    )[1].split("function engineLabelById(", 1)[0]


def test_duet_form_sends_our_presenter_id_and_never_the_provider_identity() -> None:
    """Форма выбирает ведущего по НАШЕМУ идентификатору.

    Личность у провайдера — `avatar_id` и `voice_id` — живёт на сервере и в
    браузер не приходит вовсе. Поэтому подменить, кто будет говорить в
    оплаченном ролике, из формы невозможно ни ошибкой, ни намеренно. Тот же
    принцип, по которому область замены у «Копии» выводится из проверенной
    сервером категории, а не из операторского текста.
    """

    source = text(V4)
    chooser = between(
        source,
        "function duetPresenterChooser()",
        "function duetLayoutControls()",
    )

    # В форму уходит только наш идентификатор.
    assert 'select.name = "generation_intake_duet_presenter_id"' in chooser
    # И ни одного поля личности провайдера — во всём файле.
    assert "provider_avatar_id" not in source
    assert "provider_voice_id" not in source

    # Читатель выбранного значения принимает только UUID: мусор превращается в
    # пустую строку, которая читается как «ведущий не выбран», а не как ошибка.
    reader = between(
        source,
        "function duetPresenterIdFromForm(state)",
        "function duetLayoutFromForm(state)",
    )
    assert "UUID_PATTERN.test(value)" in reader


def test_duet_layout_controls_stay_inside_the_bounds_the_composer_accepts() -> None:
    """Ползунок не даёт выбрать раскладку, которую отвергнет сборка.

    Значение за пределами отбилось бы всё равно — но уже ПОСЛЕ того, как за
    ведущего заплачено посекундно. Поэтому границы стоят и в разметке, и в
    читателе: разметку можно обойти инструментами браузера.
    """

    source = text(V4)
    controls = between(
        source,
        "function duetLayoutControls()",
        "function labelled(",
    )

    assert 'width.min = String(DUET_WIDTH_MIN)' in controls
    assert 'width.max = String(DUET_WIDTH_MAX)' in controls
    assert "const DUET_WIDTH_MIN = 20;" in source
    assert "const DUET_WIDTH_MAX = 50;" in source

    reader = between(
        source,
        "function duetLayoutFromForm(state)",
        "function avatarIdentityChooser()",
    )
    assert "widthPercent >= DUET_WIDTH_MIN" in reader
    assert "widthPercent <= DUET_WIDTH_MAX" in reader

    # Четыре угла и два вида — ровно те же, что знает сборщик.
    for corner in ("bottom_left", "bottom_right", "top_left", "top_right"):
        assert f'"{corner}"' in source, corner
    for shape in ("cutout", "window"):
        assert f'"{shape}"' in source, shape


def test_choosing_a_presenter_applies_his_own_layout() -> None:
    """У каждого ведущего своя привычная посадка в кадре.

    «Наша Аня всегда слева внизу вырезом» — это свойство ведущего. Подставлять
    при его выборе чужую раскладку было бы сюрпризом, а спрашивать заново при
    каждом запуске — превращать настройку в обязательный шаг, который перестают
    читать.
    """

    source = text(V4)

    assert "function applyDuetPresenterLayout(" in source
    handler = between(
        source,
        "const presenterChoice = event.target.closest?.(",
        "const durationChoice = event.target.closest?.(",
    )
    assert "applyDuetPresenterLayout(" in handler


def test_missing_presenter_disables_the_layout_instead_of_promising_a_run() -> None:
    """Без ведущего дуэт не собрать, и форма обязана сказать это прямо.

    Показывать настройки раскладки там, где запускать нечем, значит обещать
    работу, которой не будет.
    """

    source = text(V4)
    render = between(
        source,
        "function renderDuetPresenters(form, state)",
        "function applyDuetPresenterLayout(",
    )

    assert "Ведущий проекта ещё не заведён" in render
    assert "select.disabled = true" in render
    assert "layout.hidden = true" in render
    # А отказ загрузки списка не ломает форму: панель просто скажет, что
    # ведущего нет, а запуск и без того упрётся в серверную проверку.
    ensure = between(
        source,
        "async function ensureDuetPresenters(form, state)",
        "function renderDuetPresenters(form, state)",
    )
    assert "catch {" in ensure
