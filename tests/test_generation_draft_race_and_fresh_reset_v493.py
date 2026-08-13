import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
RECOMMENDATIONS = (
    ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
).read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _run_node_contract(source: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable generation contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        contract = Path(temporary_directory) / "contract.mjs"
        contract.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [node, str(contract)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_delayed_shared_draft_and_tombstone_cannot_overwrite_user_edits() -> None:
    revision_helpers = _between(
        APP,
        "function generationFormEditRevision(form)",
        "function generationAiResearchSessionPrefix()",
    )
    restore = _between(
        APP,
        "async function restoreGenerationFormDraft(form)",
        "function clearGenerationFormDraft()",
    )
    result = _run_node_contract(
        f"""
        globalThis.HTMLSelectElement = class HTMLSelectElement {{}};
        const projectId = "90000000-0000-4000-8000-000000000001";
        const state = {{api: {{}}}};
        let pendingRead;
        let releaseRead;
        let mutations;

        function currentWorkspaceProjectId() {{ return projectId; }}
        function isWorkspaceProjectId(value) {{ return value === projectId; }}
        async function readGenerationAiResearchWorkingDraft() {{
          return await pendingRead;
        }}
        function overwrite(form, source) {{
          mutations.push(source);
          form.elements.sku.value = "OLD-AIRFRYER-SKU";
          form.elements.product_name.value = "Old Airfryer";
          form.elements.brief.value = "Old Airfryer description";
          form.elements.generation_mode.value = "mock";
        }}
        function restoreLocalGenerationFormDraft(form) {{
          overwrite(form, "local");
          return true;
        }}
        function applyGenerationAiResearchWorkingDraft(form) {{
          overwrite(form, "shared");
          return true;
        }}
        function syncGenerationModeForm() {{ mutations.push("sync-mode"); }}
        function syncGenerationFormReadiness() {{ mutations.push("sync-ready"); }}
        function clearStoredGenerationAiResearchSelectionHints() {{
          mutations.push("clear-hints");
        }}
        function clearGenerationAiResearchLineageFromForm() {{
          mutations.push("clear-lineage");
        }}
        function storedGenerationAiResearchSelectionHint() {{
          mutations.push("read-local-hint");
          return {{selectionId: "hint", recommendationPosition: 1}};
        }}
        function requireGenerationAiResearchSelectionVerification() {{
          mutations.push("require-verification");
        }}

        {revision_helpers}
        {restore}

        function makeForm() {{
          const field = (value) => ({{value}});
          const status = {{textContent: ""}};
          return {{
            dataset: {{}},
            isConnected: true,
            elements: {{
              sku: field("INITIAL-SKU"),
              product_name: field("Initial product"),
              brief: field("Initial description"),
              generation_mode: field("mock"),
              product_category: field("other"),
              platform: field("instagram"),
              duration_seconds: field("15"),
              format: field("9:16"),
              real_spend_confirmation: {{checked: false}},
            }},
            querySelector(selector) {{
              return selector === "#generation-draft-status" ? status : null;
            }},
          }};
        }}

        async function scenario(response) {{
          mutations = [];
          pendingRead = new Promise((resolve) => {{ releaseRead = resolve; }});
          const form = makeForm();
          const hydration = restoreGenerationFormDraft(form);

          form.elements.sku.value = "BAD-LION-001";
          form.elements.product_name.value = "Lion's Mane";
          form.elements.brief.value = "Fresh BAD product description";
          form.elements.generation_mode.value = "real";
          markGenerationFormEdited(form);

          releaseRead(response);
          const restored = await hydration;
          return {{
            restored,
            values: {{
              sku: form.elements.sku.value,
              productName: form.elements.product_name.value,
              brief: form.elements.brief.value,
              mode: form.elements.generation_mode.value,
            }},
            revision: form.dataset.generationUserEditRevision,
            hydration: form.dataset.generationDraftHydration,
            restoredFlag: form.dataset.generationDraftRestored,
            mutations: [...mutations],
          }};
        }}

        const shared = await scenario({{
          revision: 7,
          draft: {{recommendation: {{source_product_sku: "OLD-AIRFRYER-SKU"}}}},
        }});
        const tombstone = await scenario({{revision: 8, draft: null}});
        process.stdout.write(JSON.stringify({{shared, tombstone}}));
        """
    )

    expected_values = {
        "sku": "BAD-LION-001",
        "productName": "Lion's Mane",
        "brief": "Fresh BAD product description",
        "mode": "real",
    }
    for snapshot in (result["shared"], result["tombstone"]):
        assert snapshot["restored"] is False
        assert snapshot["values"] == expected_values
        assert snapshot["revision"] == "1"
        assert snapshot["hydration"] == "deferred"
        assert snapshot["restoredFlag"] == "true"
        assert snapshot["mutations"] == []


def test_user_edit_guard_wraps_await_and_is_wired_to_form_activity() -> None:
    restore = _between(
        APP,
        "async function restoreGenerationFormDraft(form)",
        "function clearGenerationFormDraft()",
    )
    activity = _between(
        APP,
        "function handleFormActivity(event)",
        "function handleGenerationGuidedStepCommitted(event)",
    )

    capture = "const editRevisionAtStart = generationFormEditRevision(form);"
    await_read = "const shared = await readGenerationAiResearchWorkingDraft("
    guard = "if (userEditedSinceStart()) {"
    apply_shared = "restored = applyGenerationAiResearchWorkingDraft(form, shared);"
    tombstone = "} else if (Number(shared?.revision) > 0) {"
    local_fallback = "restored = restoreLocalGenerationFormDraft(form);"

    assert restore.index(capture) < restore.index(await_read) < restore.index(guard)
    assert restore.index(guard) < restore.index(apply_shared)
    assert restore.index(guard) < restore.index(tombstone)
    assert "&& !userEditedSinceStart()" in restore
    assert restore.index("&& !userEditedSinceStart()") < restore.index(local_fallback)
    assert 'form.dataset.generationDraftHydration = "deferred"' in restore
    assert 'form.dataset.generationDraftRestored = "true"' in restore

    generation_activity = activity[activity.index('if (form.id === "mock-batch-form")') :]
    assert generation_activity.index("markGenerationFormEdited(form);") < (
        generation_activity.index("scheduleGenerationFormDraftSave(form")
    )


def test_lazy_recommendation_hydration_cannot_overwrite_late_user_edits() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable generation contracts")
    module_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    result = _run_node_contract(
        f"""
        const {{
          captureGenerationResearchWorkingDraftHydration,
          generationResearchWorkingDraftHydrationUnchanged,
        }} = await import({json.dumps(module_url)});

        const field = (value) => ({{value}});
        const form = {{
          dataset: {{
            generationUserEditRevision: "0",
            identityProductId: "90000000-0000-4000-8000-000000000002",
            generationHandoffSku: "BAD-LION-001",
            generationHandoffProductName: "Lion's Mane",
          }},
          elements: {{
            product_name: field("Lion's Mane"),
            sku: field("BAD-LION-001"),
            product_category: field("baa"),
            platform: field("instagram"),
            generation_mode: field("real_seedance"),
            duration_seconds: field("8"),
            format: field("9:16"),
            brief: field("Fresh BAD product description"),
            media_id: field("90000000-0000-4000-8000-000000000003"),
            primary_media_id: field("90000000-0000-4000-8000-000000000003"),
          }},
        }};

        const captured = captureGenerationResearchWorkingDraftHydration(form);
        const unchanged = generationResearchWorkingDraftHydrationUnchanged(
          form,
          captured,
        );
        form.elements.brief.value = "Human edit after the server read started";
        form.dataset.generationUserEditRevision = "1";
        const edited = generationResearchWorkingDraftHydrationUnchanged(
          form,
          captured,
        );
        form.elements.brief.value = "Fresh BAD product description";
        const revisionOnly = generationResearchWorkingDraftHydrationUnchanged(
          form,
          captured,
        );
        process.stdout.write(JSON.stringify({{unchanged, edited, revisionOnly}}));
        """
    )
    assert result == {
        "unchanged": True,
        "edited": False,
        "revisionOnly": False,
    }

    hydrate = _between(
        RECOMMENDATIONS,
        "async function hydrateSharedWorkingDraft(form, context)",
        "function briefControl(",
    )
    capture = (
        "const hydrationSnapshot = "
        "captureGenerationResearchWorkingDraftHydration(form);"
    )
    await_read = "const shared = await readGenerationAiResearchWorkingDraft("
    guard = "if (!generationResearchWorkingDraftHydrationUnchanged("
    apply_shared = "applySharedWorkingDraft(form, authoritative);"
    assert hydrate.index(capture) < hydrate.index(await_read) < hydrate.index(guard)
    assert hydrate.index(guard) < hydrate.index(apply_shared)
    assert "Поздний общий черновик не применён" in hydrate


def test_fresh_route_clears_only_local_generation_context_and_blocks_active_run() -> None:
    prepare = _between(
        APP,
        "function prepareFreshProductResearchRoute()",
        "function restoreProductResearchSession()",
    )
    result = _run_node_contract(
        f"""
        const projectId = "90000000-0000-4000-8000-000000000001";
        let state;
        let latest;
        let counters;
        const freshContext = {{
          requested: true,
          valid: true,
          projectId,
          productCategory: "baa",
        }};

        function normalizeProductResearchFreshRoute() {{ return freshContext; }}
        function currentWorkspaceProjectId() {{ return projectId; }}
        function productResearchStatusKind(status) {{
          return ["queued", "running", "processing"].includes(status)
            ? "active"
            : "terminal";
        }}
        function latestOwnProjectResearchRun() {{ return latest; }}
        function counted(name, update = () => {{}}) {{
          counters[name] += 1;
          update();
        }}
        function replaceFreshProductResearchRoute(...args) {{
          counted("replaceRoute");
          counters.routeArgs = args;
        }}
        function stopProductResearchPolling() {{ counted("stopPolling"); }}
        function resetResearchStageControl() {{ counted("resetStage"); }}
        function clearProductResearchRunId() {{ counted("clearRunPointer"); }}
        function cancelGenerationFormDraftSave() {{ counted("cancelDraftTimer"); }}
        function clearGenerationFormDraft() {{
          counted("clearFormDraft", () => {{ state.presentation.formDraft = null; }});
        }}
        function clearContentGenerationHandoff() {{
          counted("clearHandoff", () => {{ state.presentation.handoff = null; }});
        }}
        function clearGenerationMediaSelection() {{
          counted("clearMedia", () => {{ state.presentation.media = null; }});
        }}
        function clearGenerationRepair() {{
          counted("clearRepair", () => {{ state.presentation.repair = null; }});
        }}
        function clearStoredGenerationAiResearchSelectionHints() {{
          counted("clearAiHints", () => {{ state.presentation.aiHints = null; }});
        }}
        function resetGenerationSpecState() {{
          counted("resetSpec", () => {{ state.presentation.spec = null; }});
        }}

        {prepare}

        function scenario({{recordStatus = "completed", latestStatus = "completed"}} = {{}}) {{
          counters = {{
            replaceRoute: 0,
            routeArgs: [],
            stopPolling: 0,
            resetStage: 0,
            clearRunPointer: 0,
            cancelDraftTimer: 0,
            clearFormDraft: 0,
            clearHandoff: 0,
            clearMedia: 0,
            clearRepair: 0,
            clearAiHints: 0,
            resetSpec: 0,
            apiReads: 0,
          }};
          const record = recordStatus
            ? {{projectId, status: recordStatus, id: "saved-run"}}
            : null;
          latest = latestStatus ? {{status: latestStatus, id: "latest-run"}} : null;
          state = {{
            api: new Proxy({{}}, {{
              get() {{
                counters.apiReads += 1;
                throw new Error("fresh route must not call a provider or mutate history");
              }},
            }}),
            route: {{query: new URLSearchParams(
              `project_id=${{projectId}}&category=baa&new=1`
            )}},
            productResearch: {{
              record,
              phase: "ready",
              notice: "saved notice",
              error: "saved error",
              requestId: 4,
              restoreAttempted: false,
              prefill: {{productName: "Old Airfryer"}},
              preservedSnapshot: {{productName: "Old Airfryer"}},
            }},
            presentation: {{
              formDraft: {{sku: "OLD-AIRFRYER-SKU"}},
              handoff: {{sku: "OLD-AIRFRYER-SKU"}},
              media: {{id: "old-media"}},
              repair: {{id: "old-repair"}},
              aiHints: {{selectionId: "old-selection"}},
              spec: {{id: "old-spec"}},
            }},
            serverHistory: ["old-run", "old-job", "old-result"],
            aiResearchProviderPromptRequestId: 12,
            aiResearchRecommendation: {{selectionId: "old-selection"}},
            sections: {{generation: {{status: "ready", error: "old-error"}}}},
            realGenerationStartNotice: "old generation notice",
          }};
          const presentationBefore = JSON.stringify(state.presentation);
          const historyBefore = JSON.stringify(state.serverHistory);
          const result = prepareFreshProductResearchRoute();
          return {{
            result,
            counters: {{...counters}},
            presentation: state.presentation,
            presentationBefore,
            serverHistory: JSON.stringify(state.serverHistory),
            historyBefore,
            record: state.productResearch.record,
            phase: state.productResearch.phase,
            prefill: state.productResearch.prefill,
            recommendation: state.aiResearchRecommendation,
            providerRequestId: state.aiResearchProviderPromptRequestId,
          }};
        }}

        const clean = scenario();
        const activeRecord = scenario({{
          recordStatus: "running",
          latestStatus: "completed",
        }});
        const activeLatest = scenario({{
          recordStatus: null,
          latestStatus: "queued",
        }});
        process.stdout.write(JSON.stringify({{clean, activeRecord, activeLatest}}));
        """
    )

    clean = result["clean"]
    assert clean["result"] is True
    assert clean["counters"] == {
        "replaceRoute": 1,
        "routeArgs": ["90000000-0000-4000-8000-000000000001", "baa"],
        "stopPolling": 1,
        "resetStage": 1,
        "clearRunPointer": 1,
        "cancelDraftTimer": 1,
        "clearFormDraft": 1,
        "clearHandoff": 1,
        "clearMedia": 1,
        "clearRepair": 1,
        "clearAiHints": 1,
        "resetSpec": 1,
        "apiReads": 0,
    }
    assert clean["presentation"] == {
        "formDraft": None,
        "handoff": None,
        "media": None,
        "repair": None,
        "aiHints": None,
        "spec": None,
    }
    assert clean["serverHistory"] == clean["historyBefore"]
    assert clean["record"] is None
    assert clean["phase"] == "idle"
    assert clean["prefill"] == {"productCategory": "baa"}
    assert clean["recommendation"] is None
    assert clean["providerRequestId"] == 13

    local_cleanup_keys = {
        "stopPolling",
        "resetStage",
        "clearRunPointer",
        "cancelDraftTimer",
        "clearFormDraft",
        "clearHandoff",
        "clearMedia",
        "clearRepair",
        "clearAiHints",
        "resetSpec",
        "apiReads",
    }
    for active in (result["activeRecord"], result["activeLatest"]):
        assert active["result"] is False
        assert active["counters"]["replaceRoute"] == 1
        assert active["counters"]["routeArgs"] == [
            "90000000-0000-4000-8000-000000000001",
            "baa",
        ]
        assert all(active["counters"][key] == 0 for key in local_cleanup_keys)
        assert json.dumps(active["presentation"], sort_keys=True) == json.dumps(
            json.loads(active["presentationBefore"]), sort_keys=True
        )
        assert active["serverHistory"] == active["historyBefore"]
        assert active["recommendation"] == {"selectionId": "old-selection"}
        assert active["providerRequestId"] == 12
    assert result["activeRecord"]["record"] == {
        "projectId": "90000000-0000-4000-8000-000000000001",
        "status": "running",
        "id": "saved-run",
    }
    assert result["activeLatest"]["record"] is None


def test_fresh_route_has_no_provider_or_server_history_mutation_path() -> None:
    replace_route = _between(
        APP,
        "function replaceFreshProductResearchRoute(",
        "function prepareFreshProductResearchRoute()",
    )
    prepare = _between(
        APP,
        "function prepareFreshProductResearchRoute()",
        "function restoreProductResearchSession()",
    )
    active_guard = "if (activeRecord || activeLatest) {"

    assert prepare.index(active_guard) < prepare.index("stopProductResearchPolling()")
    assert prepare.index(active_guard) < prepare.index("clearGenerationFormDraft()")
    assert "state.api" not in prepare
    assert "startProductResearch" not in prepare
    assert "deleteProductResearch" not in prepare
    assert "deleteGeneration" not in prepare
    assert 'params.set("new"' not in replace_route
    assert "const params = new URLSearchParams({ project_id: projectId });" in (
        replace_route
    )
    for local_cleanup in (
        "clearGenerationFormDraft();",
        "clearContentGenerationHandoff();",
        "clearGenerationMediaSelection();",
        "clearGenerationRepair();",
        "clearStoredGenerationAiResearchSelectionHints();",
        "resetGenerationSpecState();",
    ):
        assert prepare.count(local_cleanup) == 1
