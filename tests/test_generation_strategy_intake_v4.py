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
    assert "openNativeLaunch(form, handoff)" in source


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


def test_express_copy_auto_selects_campaign_or_links_to_creation() -> None:
    source = text(V4)

    # Кампания выбирается автоматически: единственная или последняя активная.
    # Если активных кампаний нет — честное сообщение со ссылкой на создание.
    assert "function autoSelectCampaign" in source
    campaign = between(
        source,
        "function autoSelectCampaign",
        "function serverPriceLabel",
    )
    assert "campaign_id" in campaign
    assert "options[options.length - 1]" in campaign
    assert 'campaign.dispatchEvent(new Event("change", { bubbles: true }))' in campaign
    assert (
        'const NEW_CAMPAIGN_ROUTE_HASH = "#/workspace/team?view=new-campaign"'
        in source
    )
    assert "generationIntakeCampaignNote" in source
    assert "нет активной кампании" in source


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
    assert "autoSelectCampaign(form, panel)" in launch
    assert "confirmation.click()" in launch
    assert "submitButton.click()" in launch
    binding = between(source, "function bind(form, state)", "function mount(form)")
    assert 'trigger?.dataset.expressPhase === "priced"' in binding
    assert "void startExpressLaunch(form)" in binding
    assert "void prepareCopy(form)" in binding


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
    assert "prefillCopyRecommendation(form, state)" in set_route
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
    restore = between(
        source,
        "function restoreCopyPhotoSelection",
        "async function registerSelectedProductPhotos",
    )
    assert "sessionStorage.getItem(copyPhotoStorageKey()" in restore
    assert "ensureProductCheckbox(" in restore
    mount = between(source, "function mount(form)", "function scheduleMount()")
    assert mount.count("restoreCopyPhotoSelection(form,") == 2
    # Очередь в памяти не даёт потерять ещё не зарегистрированные файлы.
    files = between(source, "function selectedProductFiles", "function selectedAvatarFile")
    assert "pendingCopyProductFiles.get(projectId())" in files


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
    assert "function showChosenFrameNote" in source
    assert "Кадр исходного товара выбран" in source
    assert "noteChosenFrame(form, panel, originalProductMediaId)" in prepare_copy
    assert "загрузите локальный MP4 этого ролика" in prepare_copy


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


def test_copy_engine_choice_is_a_three_step_cascade_from_the_route_registry() -> None:
    source = text(V4)
    render = between(
        source,
        "function renderEngineChoice(form, state, section)",
        "let copyChecklistBusy = false;",
    )
    markup = between(source, "function copyEngineChoice()", "function copyChecklistRow")

    # Три ступени одна под другой: уровень, модели уровня, тайминги модели.
    assert 'cascadeStep("tier", "1", "Уровень", "generation_intake_tier")' in markup
    assert 'cascadeStep("model", "2", "Модель", "generation_intake_generator")' in markup
    assert '"duration",\n    "3",\n    "Длительность ролика",\n    "generation_intake_duration",' in markup

    # Переключатель движка ровно один: прежний ряд «Генератор 1/2/3» стал
    # второй ступенью, ряда «Качество» больше нет.
    assert source.count('"generation_intake_generator"') == 2
    assert "generation_intake_quality" not in source
    assert "Генератор ${index + 1}" not in source

    # Данные — только из реестра маршрутов, без иных источников.
    assert "getStrategyProviderRoutes?.(COPY_AUTHORITY_STRATEGY)" in source
    assert "copyEngineRoutes()" in render
    for field in (
        "route.provider",
        "route.model_key",
        "route.tier",
        "route.price_kind",
        "route.price_rate_minor",
        "route.min_duration_seconds",
        "route.max_duration_seconds",
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

    # Цена видна и у уровня, и у модели; там, где ставки нет, сумма не
    # придумывается.
    render = between(
        source,
        "function renderEngineChoice(form, state, section)",
        "let copyChecklistBusy = false;",
    )
    assert "tierPriceNote(tierEngines)" in render
    assert "routePriceNote(engine)" in render
    assert '"по ступеням кредитов"' in source
    assert '"цену назовёт сервер"' in source


def test_copy_engine_cascade_keeps_duration_where_the_form_already_puts_it() -> None:
    source = text(V4)
    render = between(
        source,
        "function renderEngineChoice(form, state, section)",
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
        "function renderEngineChoice(form, state, section)",
        "let copyChecklistBusy = false;",
    )

    # Каскад не переключает исполнение: маршрут по-прежнему берётся из реестра
    # по отметке recommended, и экран говорит об этом вслух.
    assert "selectStrategy(" not in render
    assert "requested_model" not in render
    assert "spend_confirmation" not in render
    assert "engines.find((engine) => engine.recommended && engine.enabled)" in render
    assert "не переключает запуск" in render
