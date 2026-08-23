from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEW_MODULE = ROOT / "web/app/generation-strategy-view.js"
CATALOG_MODULE = ROOT / "supabase/functions/_shared/generation-strategy-catalog.js"
VIEW_SOURCE = VIEW_MODULE.read_text(encoding="utf-8")
CATALOG_SOURCE = CATALOG_MODULE.read_text(encoding="utf-8")


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation strategy view contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "view.mjs").write_text(VIEW_SOURCE, encoding="utf-8")
        (directory / "catalog.mjs").write_text(CATALOG_SOURCE, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as view from './view.mjs';\n"
            "import * as catalogContract from './catalog.mjs';\n"
            "const clone = (value) => JSON.parse(JSON.stringify(value));\n"
            "const enabledCatalog = () => {\n"
            "  const capabilities = Object.fromEntries(\n"
            "    catalogContract.GENERATION_STRATEGY_CATALOG.map((entry) => [\n"
            "      entry.strategy_id,\n"
            "      {\n"
            "        enabled: true,\n"
            "        catalog_version: catalogContract.GENERATION_STRATEGY_CATALOG_VERSION,\n"
            "        strategy_id: entry.strategy_id,\n"
            "        provider: entry.provider,\n"
            "        recipe: entry.recipe,\n"
            "        recipe_version: entry.recipe_version,\n"
            "        provider_path: entry.server.provider_path,\n"
            "        pricing_version: entry.pricing_version,\n"
            "      },\n"
            "    ]),\n"
            "  );\n"
            "  return catalogContract.publicGenerationStrategyCatalog({executionCapabilities: capabilities});\n"
            "};\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_view_is_pure_and_does_not_hardcode_strategy_provider_recipe_or_price() -> None:
    for forbidden in (
        "Deno.env",
        "process.env",
        "document.",
        "window.",
        "localStorage",
        "sessionStorage",
        "fetch(",
        "XMLHttpRequest",
        "/v1/recipes/",
        "viral_avatar_ugc",
        "viral_product_swap",
        "viral_rebuild",
        "product_ugc",
        "product_swap",
        "product_ad",
        "RUNWAYML_API_SECRET",
    ):
        assert forbidden not in VIEW_SOURCE
    for hardcoded_formula in (
        "base_credits: 192",
        "base_credits: 208",
        "base_credits: 212",
        "base_credits: 228",
        "base_credits: 200",
        "base_credits: 216",
    ):
        assert hardcoded_formula not in VIEW_SOURCE

    result = _evaluate(
        """
        ({
          exports: Object.keys(view).sort(),
          version: view.GENERATION_STRATEGY_VIEW_VERSION,
          action: view.GENERATION_STRATEGY_SELECT_ACTION,
        })
        """
    )
    assert result == {
        "exports": [
            "GENERATION_STRATEGY_SELECT_ACTION",
            "GENERATION_STRATEGY_VIEW_VERSION",
            "createGenerationStrategyViewState",
            "generationStrategyViewMarkup",
            "normalizeGenerationStrategyCatalog",
            "reduceGenerationStrategyViewState",
            "selectedGenerationStrategySummary",
            "validateSelectedGenerationStrategyDraft",
        ],
        "version": "2026-08-14.v1",
        "action": "SELECT",
    }


def test_exact_server_projection_normalizes_to_three_deep_frozen_rows() -> None:
    result = _evaluate(
        """
        (() => {
          const raw = catalogContract.publicGenerationStrategyCatalog();
          const normalized = view.normalizeGenerationStrategyCatalog(raw);
          const stateFromNormalized = view.createGenerationStrategyViewState(normalized);
          const forgedState = view.createGenerationStrategyViewState({
            ok: true,
            catalog: {strategies: raw.strategies},
            error: null,
          });
          const deepFrozen = (value) => !value || typeof value !== "object" || (
            Object.isFrozen(value) && Object.values(value).every(deepFrozen)
          );
          return {
            ok: normalized.ok,
            count: normalized.catalog?.strategies.length,
            ids: normalized.catalog?.strategies.map((item) => item.strategy_id),
            enabled: normalized.catalog?.strategies.map((item) => item.enabled),
            frozen: deepFrozen(normalized),
            versions: normalized.catalog ? [
              normalized.catalog.version,
              normalized.catalog.recipe_version,
              normalized.catalog.pricing_version,
            ] : [],
            transformative: normalized.catalog?.strategies.every((strategy) =>
              strategy.required_attestations.some(
                (item) => item.id === "transformative_use_confirmed"
              )
            ),
            normalizedState: stateFromNormalized.catalog_status,
            forgedState: forgedState.catalog_status,
          };
        })()
        """
    )
    assert result == {
        "ok": True,
        "count": 3,
        "ids": ["viral_avatar_ugc", "viral_product_swap", "viral_rebuild"],
        "enabled": [False, False, False],
        "frozen": True,
        "versions": [
            "2026-08-14.v1",
            "2026-06",
            "runway-recipe-credits-2026-08-14.v1",
        ],
        "transformative": True,
        "normalizedState": "ready",
        "forgedState": "invalid",
    }


def test_normalizer_rejects_extra_missing_stale_and_internally_inconsistent_contracts() -> None:
    result = _evaluate(
        """
        (() => {
          const base = catalogContract.publicGenerationStrategyCatalog();
          const extraTop = clone(base); extraTop.server = {};
          const missingRow = clone(base); delete missingRow.strategies[0].public_label;
          const extraRole = clone(base);
          extraRole.strategies[0].asset_roles[0].provider_field = "referenceVideo";
          const count = clone(base); count.strategies.pop();
          const duplicate = clone(base);
          duplicate.strategies[1].strategy_id = duplicate.strategies[0].strategy_id;
          const recipeVersion = clone(base);
          recipeVersion.strategies[0].recipe_version = "unsafe-latest";
          const pricingVersion = clone(base);
          pricingVersion.strategies[0].pricing.pricing_version = "stale";
          const humanReview = clone(base);
          humanReview.strategies[0].human_review_required = false;
          const enabledReason = clone(base);
          enabledReason.strategies[0].enabled = true;
          const disabledReason = clone(base);
          disabledReason.strategies[0].disabled_reason = null;
          const audio = clone(base);
          audio.strategies[0].output_rules.audio.required_explicit_boolean = false;
          const tier = clone(base);
          tier.strategies[0].pricing.tiers["720p"].untrusted = 1;
          const normalize = (value) => view.normalizeGenerationStrategyCatalog(value);
          return Object.fromEntries(Object.entries({
            extraTop,
            missingRow,
            extraRole,
            count,
            duplicate,
            recipeVersion,
            pricingVersion,
            humanReview,
            enabledReason,
            disabledReason,
            audio,
            tier,
          }).map(([key, value]) => [key, normalize(value)]));
        })()
        """
    )
    assert result["extraTop"]["error"]["code"] == "object_keys_mismatch"
    assert result["missingRow"]["error"]["code"] == "object_keys_mismatch"
    assert result["extraRole"]["error"]["code"] == "object_keys_mismatch"
    assert result["count"]["error"]["code"] == "strategy_count_mismatch"
    assert result["duplicate"]["error"]["code"] == "strategy_id_duplicate"
    assert result["recipeVersion"]["error"]["code"] == "recipe_version_mismatch"
    assert result["pricingVersion"]["error"]["code"] == "pricing_version_mismatch"
    assert result["humanReview"]["error"]["code"] == "human_review_contract_required"
    assert result["enabledReason"]["error"]["code"] == "enabled_reason_mismatch"
    assert result["disabledReason"]["error"]["code"] == "text_required"
    assert result["audio"]["error"]["code"] == "explicit_audio_contract_required"
    assert result["tier"]["error"]["code"] == "object_keys_mismatch"
    assert all(item["ok"] is False and item["catalog"] is None for item in result.values())


def test_state_has_no_default_and_only_literal_select_can_change_it() -> None:
    result = _evaluate(
        """
        (() => {
          const catalog = enabledCatalog();
          const state = view.createGenerationStrategyViewState(catalog);
          const firstId = catalog.strategies[0].strategy_id;
          const auto = view.reduceGenerationStrategyViewState(state, {
            type: "AUTO_SELECT", strategy_id: firstId,
          });
          const extra = view.reduceGenerationStrategyViewState(state, {
            type: "SELECT", strategy_id: firstId, automatic: true,
          });
          const unknown = view.reduceGenerationStrategyViewState(state, {
            type: "SELECT", strategy_id: "unknown_strategy",
          });
          const selected = view.reduceGenerationStrategyViewState(state, {
            type: view.GENERATION_STRATEGY_SELECT_ACTION,
            strategy_id: firstId,
          });
          const disabledState = view.createGenerationStrategyViewState(
            catalogContract.publicGenerationStrategyCatalog()
          );
          const disabled = view.reduceGenerationStrategyViewState(disabledState, {
            type: "SELECT", strategy_id: firstId,
          });
          return {
            initial: {
              selected: state.selected_strategy_id,
              origin: state.selection_origin,
              error: state.selection_error,
            },
            auto: {selected: auto.selected_strategy_id, error: auto.selection_error},
            extra: {selected: extra.selected_strategy_id, error: extra.selection_error},
            unknown: {selected: unknown.selected_strategy_id, error: unknown.selection_error},
            selected: {
              id: selected.selected_strategy_id,
              origin: selected.selection_origin,
              error: selected.selection_error,
              frozen: Object.isFrozen(selected),
            },
            originalUnchanged: state.selected_strategy_id,
            disabled: {
              selected: disabled.selected_strategy_id,
              error: disabled.selection_error,
            },
          };
        })()
        """
    )
    assert result["initial"] == {"selected": None, "origin": None, "error": None}
    assert result["auto"] == {"selected": None, "error": "select_action_unsupported"}
    assert result["extra"] == {"selected": None, "error": "select_action_invalid"}
    assert result["unknown"] == {"selected": None, "error": "strategy_unknown"}
    assert result["selected"]["id"] == "viral_avatar_ugc"
    assert result["selected"]["origin"] == "explicit_select_action"
    assert result["selected"]["error"] is None
    assert result["selected"]["frozen"] is True
    assert result["originalUnchanged"] is None
    assert result["disabled"] == {"selected": None, "error": "strategy_disabled"}


def test_renderer_shows_three_manual_cards_requirements_notices_server_price_and_disabled_reason() -> None:
    result = _evaluate(
        """
        (() => {
          const disabledCatalog = catalogContract.publicGenerationStrategyCatalog();
          const disabledState = view.createGenerationStrategyViewState(disabledCatalog);
          const disabledMarkup = view.generationStrategyViewMarkup(disabledState);

          const serverCatalog = clone(enabledCatalog());
          serverCatalog.strategies[0].provider = "server_provider";
          serverCatalog.strategies[0].recipe = "server_recipe";
          serverCatalog.strategies[0].pricing.tiers["720p"].base_credits = 777;
          const enabledState = view.createGenerationStrategyViewState(serverCatalog);
          const initialMarkup = view.generationStrategyViewMarkup(enabledState);
          const selectedState = view.reduceGenerationStrategyViewState(enabledState, {
            type: "SELECT",
            strategy_id: serverCatalog.strategies[1].strategy_id,
          });
          const selectedMarkup = view.generationStrategyViewMarkup(selectedState);
          return {
            cards: (initialMarkup.match(/data-generation-strategy-card=/g) || []).length,
            selectActions: (initialMarkup.match(/data-generation-strategy-action="SELECT"/g) || []).length,
            initialPressed: (initialMarkup.match(/aria-pressed="true"/g) || []).length,
            initialNone: initialMarkup.includes('data-selected-strategy-summary="none"'),
            selectedPressed: (selectedMarkup.match(/aria-pressed="true"/g) || []).length,
            selectedId: selectedMarkup.includes(
              `data-selected-strategy-summary="${serverCatalog.strategies[1].strategy_id}"`
            ),
            allNotices: serverCatalog.strategies.every((item) =>
              initialMarkup.includes(item.preservation_notice)
            ),
            allRoles: serverCatalog.strategies.every((item) => item.asset_roles.every((role) =>
              initialMarkup.includes(`data-generation-strategy-role="${role.role}"`)
            )),
            allAttestations: serverCatalog.strategies.every((item) =>
              item.required_attestations.every((attestation) =>
                initialMarkup.includes(
                  `data-generation-strategy-attestation="${attestation.id}"`
                )
              )
            ),
            transformative: initialMarkup.includes(
              'data-generation-strategy-attestation="transformative_use_confirmed"'
            ),
            serverProvider: initialMarkup.includes("server_provider") &&
              initialMarkup.includes("server_recipe"),
            serverPrice: initialMarkup.includes("777 кредитов за 4 с") &&
              initialMarkup.includes("за каждую следующую секунду"),
            durationRange: initialMarkup.includes("Результат: 4–15 с"),
            disabledReasons: (
              disabledMarkup.match(/data-generation-strategy-disabled-reason=/g) || []
            ).length,
            disabledButtons: disabledMarkup.split("Сейчас недоступно</button>").length - 1,
            noInlineHandlers: !initialMarkup.includes("onclick=") &&
              !initialMarkup.includes("onchange="),
          };
        })()
        """
    )
    assert result == {
        "cards": 3,
        "selectActions": 3,
        "initialPressed": 0,
        "initialNone": True,
        "selectedPressed": 1,
        "selectedId": True,
        "allNotices": True,
        "allRoles": True,
        "allAttestations": True,
        "transformative": True,
        "serverProvider": True,
        "serverPrice": True,
        "durationRange": True,
        "disabledReasons": 3,
        "disabledButtons": 3,
        "noInlineHandlers": True,
    }


def test_renderer_escapes_every_server_owned_copy_field() -> None:
    result = _evaluate(
        """
        (() => {
          const raw = clone(enabledCatalog());
          raw.strategies[0].public_label = '<img src=x onerror="alert(1)">';
          raw.strategies[0].preservation_notice = '<script>alert(2)</script>';
          raw.strategies[0].required_attestations[0].public_label = '<b onmouseover="alert(3)">rights</b>';
          const state = view.createGenerationStrategyViewState(raw);
          const markup = view.generationStrategyViewMarkup(state);
          return {
            ready: state.catalog_status,
            rawImage: markup.includes("<img"),
            rawScript: markup.includes("<script"),
            rawMouseover: /<[^>]+\\sonmouseover=/u.test(markup),
            escapedImage: markup.includes("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;"),
            escapedScript: markup.includes("&lt;script&gt;alert(2)&lt;/script&gt;"),
            escapedRights: markup.includes("&lt;b onmouseover=&quot;alert(3)&quot;&gt;rights&lt;/b&gt;"),
          };
        })()
        """
    )
    assert result == {
        "ready": "ready",
        "rawImage": False,
        "rawScript": False,
        "rawMouseover": False,
        "escapedImage": True,
        "escapedScript": True,
        "escapedRights": True,
    }


def test_selected_summary_and_draft_validation_are_pure_and_fail_closed() -> None:
    result = _evaluate(
        """
        (() => {
          const catalog = enabledCatalog();
          const initial = view.createGenerationStrategyViewState(catalog);
          const noSelection = view.selectedGenerationStrategySummary(initial);
          const strategy = catalog.strategies[1];
          const selected = view.reduceGenerationStrategyViewState(initial, {
            type: "SELECT", strategy_id: strategy.strategy_id,
          });
          const summary = view.selectedGenerationStrategySummary(selected);
          const draft = {
            duration_seconds: strategy.output_rules.duration.default_seconds,
            resolution: strategy.output_rules.resolutions[0],
            audio: strategy.output_rules.audio.provider_default,
            asset_counts: Object.fromEntries(
              strategy.asset_roles.map((role) => [role.role, role.min_count])
            ),
            attestations: Object.fromEntries(
              strategy.required_attestations.map((item) => [item.id, true])
            ),
          };
          const valid = view.validateSelectedGenerationStrategyDraft(selected, draft);
          const invalid = clone(draft);
          invalid.duration_seconds = strategy.output_rules.duration.max_seconds + 1;
          invalid.asset_counts[strategy.asset_roles[0].role] = 0;
          invalid.attestations[strategy.required_attestations[0].id] = false;
          const invalidResult = view.validateSelectedGenerationStrategyDraft(selected, invalid);
          const extra = {...draft, provider_path: "/forbidden"};
          const extraResult = view.validateSelectedGenerationStrategyDraft(selected, extra);
          const withoutSelection = view.validateSelectedGenerationStrategyDraft(initial, draft);
          return {
            noSelection,
            summary: {
              ok: summary.ok,
              id: summary.summary?.strategy_id,
              recipe: summary.summary?.recipe,
              hasProviderPath: summary.summary
                ? Object.hasOwn(summary.summary, "provider_path")
                : false,
              frozen: Object.isFrozen(summary) && Object.isFrozen(summary.summary),
              transformative: summary.summary?.required_attestation_ids.includes(
                "transformative_use_confirmed"
              ),
            },
            valid,
            invalidCodes: invalidResult.errors.map((item) => item.code),
            extraCodes: extraResult.errors.map((item) => item.code),
            withoutSelection: withoutSelection.errors.map((item) => item.code),
          };
        })()
        """
    )
    assert result["noSelection"] == {
        "ok": False,
        "code": "strategy_not_selected",
        "summary": None,
    }
    assert result["summary"] == {
        "ok": True,
        "id": "viral_product_swap",
        "recipe": "product_swap",
        "hasProviderPath": False,
        "frozen": True,
        "transformative": True,
    }
    assert result["valid"]["ok"] is True
    assert result["valid"]["strategy_id"] == "viral_product_swap"
    assert result["valid"]["errors"] == []
    assert result["valid"]["normalized"]["resolution"] == "720p"
    assert result["invalidCodes"] == [
        "duration_unsupported",
        "asset_role_count_invalid",
        "attestation_required",
    ]
    assert result["extraCodes"] == ["draft_field_unknown"]
    assert result["withoutSelection"] == ["strategy_not_selected"]


def test_invalid_catalog_renderer_has_no_cards_or_select_action() -> None:
    result = _evaluate(
        """
        (() => {
          const state = view.createGenerationStrategyViewState({strategies: []});
          const markup = view.generationStrategyViewMarkup(state);
          return {
            status: state.catalog_status,
            selected: state.selected_strategy_id,
            code: state.catalog_error.code,
            invalidMarkup: markup.includes('data-generation-strategy-status="invalid"'),
            cards: markup.includes("data-generation-strategy-card="),
            selectAction: markup.includes('data-generation-strategy-action="SELECT"'),
            failClosedCopy: markup.includes("Ничего не выбрано и не применяется"),
          };
        })()
        """
    )
    assert result == {
        "status": "invalid",
        "selected": None,
        "code": "object_keys_mismatch",
        "invalidMarkup": True,
        "cards": False,
        "selectAction": False,
        "failClosedCopy": True,
    }


def test_failed_normalized_catalog_preserves_exact_safe_diagnostic_fail_closed() -> None:
    result = _evaluate(
        """
        (() => {
          const exact = view.createGenerationStrategyViewState({
            ok: false,
            catalog: null,
            error: {code: "origin_not_allowed", field: "catalog"},
          });
          const malformed = view.createGenerationStrategyViewState({
            ok: false,
            catalog: null,
            error: {
              code: "origin_not_allowed",
              field: "catalog",
              leaked_detail: "must not become trusted state",
            },
          });
          const markup = view.generationStrategyViewMarkup(exact);
          return {
            exact: {
              status: exact.catalog_status,
              catalog: exact.catalog,
              selected: exact.selected_strategy_id,
              error: exact.catalog_error,
            },
            malformedCode: malformed.catalog_error.code,
            renderedCode: markup.includes("Код: origin_not_allowed"),
            hasCard: markup.includes("data-generation-strategy-card="),
            hasSelect: markup.includes('data-generation-strategy-action="SELECT"'),
          };
        })()
        """
    )
    assert result == {
        "exact": {
            "status": "invalid",
            "catalog": None,
            "selected": None,
            "error": {"code": "origin_not_allowed", "field": "catalog"},
        },
        "malformedCode": "catalog_contract_invalid",
        "renderedCode": True,
        "hasCard": False,
        "hasSelect": False,
    }
