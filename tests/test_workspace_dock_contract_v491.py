from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web" / "app" / "workspace-dock-contract.js"
SOURCE = MODULE.read_text(encoding="utf-8")


def _run_node(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the workspace Dock contract")
    result = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            f"""
            import * as subject from {json.dumps(MODULE.as_uri())};
            {body}
            """,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


POLICY_JS = """
const policy = {
  spaces: ["bombbar", "blacktiger"],
  defaultSpace: "bombbar",
  apps: {
    ai: ["today", "decisions"],
    review: ["queue", "source"],
    finder: ["files", "trash"],
  },
};
"""


def test_contract_is_pure_scoped_and_migrates_catalog_before_order_normalization() -> None:
    for forbidden in (
        "document.",
        "globalThis.document",
        "window.",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "fetch(",
        "XMLHttpRequest",
        "location.",
        "history.",
        "pushState",
        "replaceState",
        "FormData",
    ):
        assert forbidden not in SOURCE

    result = _run_node(
        f"""
        {POLICY_JS}
        const scope = {{ organizationId: "org-1", userId: "user-1" }};
        const raw = {{
          version: "contentengine-dock-preferences-v3",
          scope: {{ organization_id: "org-1", user_id: "user-1" }},
          order: ["finder", "external-old", "file-old", "file-duplicate", "review", "trash"],
          shortcuts: {{
            "external-old": {{
              shortcut_id: "external-old",
              shortcut_type: "external_link_shortcut",
              canonical_target: "https://EXAMPLE.com/doc?utm_source=mail&b=2&a=1#section",
              label_override: "   ",
              created_at: "2026-08-01T10:00:00Z",
            }},
            "file-old": {{
              shortcut_id: "file-old",
              shortcut_type: "file_shortcut",
              object_id: "object-7",
              created_at: "2026-08-01T11:00:00Z",
            }},
            "file-duplicate": {{
              shortcut_id: "file-duplicate",
              shortcut_type: "file_shortcut",
              object_id: "object-7",
              created_at: "2026-08-01T12:00:00Z",
            }},
          }},
        }};
        const normalized = subject.normalizeWorkspaceDockPreference(raw, {{ scope, internalPolicy: policy }});
        const foreign = subject.normalizeWorkspaceDockPreference(raw, {{
          scope: {{ organizationId: "org-2", userId: "user-1" }},
          internalPolicy: policy,
        }});
        const legacyArray = subject.normalizeWorkspaceDockPreference(
          ["results", "ai"],
          {{ scope, internalPolicy: policy }},
        );
        const missing = subject.normalizeWorkspaceDockPreference(
          {{}},
          {{ scope, internalPolicy: policy }},
        );
        const explicitMinimal = subject.normalizeWorkspaceDockPreference(
          {{ scope, order: ["ai"], shortcuts: {{}} }},
          {{ scope, internalPolicy: policy }},
        );
        process.stdout.write(JSON.stringify({{
          version: subject.WORKSPACE_DOCK_PREFERENCE_VERSION,
          actions: subject.WORKSPACE_DOCK_ACTIONS,
          normalized,
          foreign,
          legacyArray,
          missing,
          explicitMinimal,
        }}));
        """
    )

    assert result["version"] == "contentengine-dock-preferences-v3.1"
    normalized = result["normalized"]
    assert normalized["preference"]["scope"] == {
        "organizationId": "org-1",
        "userId": "user-1",
    }
    assert normalized["preference"]["order"] == [
        "finder",
        "external-old",
        "file-old",
        "review",
        "trash",
    ]
    assert normalized["preference"]["shortcuts"]["external-old"] == {
        "shortcutId": "external-old",
        "type": "external_link_shortcut",
        "createdAt": "2026-08-01T10:00:00.000Z",
        "canonicalTarget": "https://example.com/doc?a=1&b=2#section",
        "labelOverride": "example.com",
    }
    assert normalized["catalog"]["file-old"]["kind"] == "shortcut"
    assert "file-old" in normalized["preference"]["order"]
    assert normalized["issues"] == ["duplicate_shortcut_target"]
    assert normalized["repairRequired"] is True

    assert result["foreign"]["issues"] == ["scope_mismatch"]
    assert result["foreign"]["preference"]["shortcuts"] == {}
    # 25.08: канонический док читается как конвейер — «Результаты» сразу
    # после «Опубликовать».
    full_default_order = [
        "finder",
        "research",
        "ai",
        "create",
        "review",
        "publish",
        "results",
        "passports",
        "processes",
        "settings",
        "trash",
    ]
    assert result["foreign"]["preference"]["order"] == full_default_order
    assert result["missing"]["preference"]["order"] == full_default_order
    catalog = result["missing"]["catalog"]
    for key in ("results", "research", "ai", "create", "publish", "processes", "settings"):
        assert catalog[key]["protected"] is False
        assert catalog[key]["removable"] is True
    for key in ("finder", "review", "trash"):
        assert catalog[key]["protected"] is True
        assert catalog[key]["removable"] is False
    assert result["explicitMinimal"]["preference"]["order"] == [
        "finder",
        "ai",
        "review",
        "trash",
    ]
    assert result["legacyArray"]["preference"]["order"] == [
        "finder",
        "results",
        "ai",
        "review",
        "trash",
    ]


def test_external_https_normalization_preserves_safe_fragment_and_rejects_secrets() -> None:
    result = _run_node(
        """
        const good = subject.normalizeWorkspaceDockExternalTarget(
          " https://Example.COM:443/path?z=9&utm_campaign=x&a=2&a=1&fbclid=noise#safe-section ",
        );
        const cases = {
          http: subject.normalizeWorkspaceDockExternalTarget("http://example.com/a"),
          credentials: subject.normalizeWorkspaceDockExternalTarget("https://user:pass@example.com/a"),
          sensitiveKey: subject.normalizeWorkspaceDockExternalTarget("https://example.com/a?access_token=value"),
          jwt: subject.normalizeWorkspaceDockExternalTarget(
            "https://example.com/a?state=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop",
          ),
          tokenish: subject.normalizeWorkspaceDockExternalTarget(
            "https://example.com/a?state=AbCdEfGhIjKlMnOpQrStUvWxYz01234567890123456789",
          ),
          fragmentSecret: subject.normalizeWorkspaceDockExternalTarget("https://example.com/a#token=secret"),
          control: subject.normalizeWorkspaceDockExternalTarget("https://example.com/a\u0001bad"),
          encodedControl: subject.normalizeWorkspaceDockExternalTarget("https://example.com/a%0Abad"),
          signed: subject.normalizeWorkspaceDockExternalTarget(
            "https://example.com/a?X-Amz-Signature=abcdef",
          ),
        };
        process.stdout.write(JSON.stringify({ good, cases }));
        """
    )
    assert result["good"] == {
        "ok": True,
        "canonicalTarget": "https://example.com/path?a=1&a=2&z=9#safe-section",
        "hostname": "example.com",
    }
    assert result["cases"]["http"]["error"] == "https_required"
    assert result["cases"]["credentials"]["error"] == "credentials_forbidden"
    assert result["cases"]["sensitiveKey"]["error"] == "sensitive_query_forbidden"
    assert result["cases"]["jwt"]["error"] == "secret_like_value_forbidden"
    assert result["cases"]["tokenish"]["error"] == "secret_like_value_forbidden"
    assert result["cases"]["fragmentSecret"]["error"] == "unsafe_fragment"
    assert result["cases"]["control"]["error"] == "external_target_invalid"
    assert result["cases"]["encodedControl"]["error"] == "external_target_invalid"
    assert result["cases"]["signed"]["error"] == "sensitive_query_forbidden"


def test_internal_targets_normalize_legacy_view_and_enforce_exact_space_and_tab() -> None:
    result = _run_node(
        f"""
        {POLICY_JS}
        const values = {{
          legacyView: subject.normalizeWorkspaceDockInternalTarget(
            "contentengine://app/AI?view=decisions",
            policy,
          ),
          exact: subject.normalizeWorkspaceDockInternalTarget(
            "contentengine://app/review?tab=source&space=blacktiger",
            policy,
          ),
          desktop: subject.normalizeWorkspaceDockInternalTarget(
            "contentengine://desktop/bombbar",
            policy,
          ),
          object: subject.normalizeWorkspaceDockInternalTarget(
            "contentengine://object/object%3A7",
            policy,
          ),
          badTab: subject.normalizeWorkspaceDockInternalTarget(
            "contentengine://app/ai?space=bombbar&tab=admin",
            policy,
          ),
          badSpace: subject.normalizeWorkspaceDockInternalTarget(
            "contentengine://app/ai?space=foreign&tab=today",
            policy,
          ),
          arbitraryQuery: subject.normalizeWorkspaceDockInternalTarget(
            "contentengine://app/ai?space=bombbar&tab=today&execute=1",
            policy,
          ),
        }};
        process.stdout.write(JSON.stringify(values));
        """
    )
    assert result["legacyView"]["canonicalTarget"] == (
        "contentengine://app/ai?space=bombbar&tab=decisions"
    )
    assert result["exact"]["canonicalTarget"] == (
        "contentengine://app/review?space=blacktiger&tab=source"
    )
    assert result["desktop"]["canonicalTarget"] == "contentengine://desktop/bombbar"
    assert result["object"]["canonicalTarget"] == "contentengine://object/object%3A7"
    assert result["badTab"]["error"] == "internal_tab_not_allowed"
    assert result["badSpace"]["error"] == "internal_space_not_allowed"
    assert result["arbitraryQuery"]["error"] == "internal_query_not_allowed"


def test_collision_checked_uuid_ids_and_external_edit_keep_stable_identity() -> None:
    result = _run_node(
        f"""
        {POLICY_JS}
        const firstUuid = "00000000-0000-4000-8000-000000000001";
        const secondUuid = "00000000-0000-4000-8000-000000000002";
        const firstId = `external-link:${{firstUuid}}`;
        const allocated = subject.allocateWorkspaceDockShortcutId(
          "external_link_shortcut",
          [firstId],
          [firstUuid, secondUuid],
        );
        let state = subject.createWorkspaceDockState(
          ["finder", "ai", "review", "trash"],
          {{ scope: {{ organizationId: "org-1", userId: "user-1" }}, internalPolicy: policy }},
        );
        state = subject.workspaceDockReducer(state, {{
          type: "addShortcut",
          now: "2026-08-13T09:00:00Z",
          shortcut: {{
            shortcutId: allocated,
            type: "external_link_shortcut",
            canonicalTarget: "https://example.com/report?b=2&a=1",
            labelOverride: "Отчёт",
          }},
        }});
        const added = JSON.parse(JSON.stringify(state));
        state = subject.workspaceDockReducer(state, {{
          type: "editExternalLink",
          shortcutId: allocated,
          canonicalTarget: "javascript:alert(1)",
          labelOverride: "Bad",
        }});
        const invalid = JSON.parse(JSON.stringify(state));
        state = subject.workspaceDockReducer(state, {{
          type: "editExternalLink",
          shortcutId: allocated,
          canonicalTarget: "https://docs.example.com/x?utm_source=x&z=2",
          labelOverride: " Документ ",
        }});
        process.stdout.write(JSON.stringify({{ allocated, added, invalid, edited: state }}));
        """
    )
    allocated = "external-link:00000000-0000-4000-8000-000000000002"
    assert result["allocated"] == allocated
    assert result["added"]["preference"]["order"][-2:] == [allocated, "trash"]
    assert [effect["type"] for effect in result["added"]["effects"]] == [
        "persist_preference"
    ]
    assert result["invalid"]["issues"] == ["https_required"]
    assert result["invalid"]["preference"] == result["added"]["preference"]
    edited = result["edited"]
    assert list(edited["preference"]["shortcuts"]) == [allocated]
    assert edited["preference"]["shortcuts"][allocated]["canonicalTarget"] == (
        "https://docs.example.com/x?z=2"
    )
    assert edited["preference"]["shortcuts"][allocated]["labelOverride"] == "Документ"
    assert edited["preference"]["order"] == result["added"]["preference"]["order"]
    assert len(edited["effects"]) == 1


def test_edit_snapshot_cancel_done_and_authoritative_purge_have_exact_write_semantics() -> None:
    result = _run_node(
        f"""
        {POLICY_JS}
        const fileId = "file-shortcut:00000000-0000-4000-8000-000000000010";
        const linkId = "external-link:00000000-0000-4000-8000-000000000011";
        const raw = {{
          version: subject.WORKSPACE_DOCK_PREFERENCE_VERSION,
          scope: {{ organizationId: "org-1", userId: "user-1" }},
          order: ["finder", fileId, linkId, "review", "trash"],
          shortcuts: {{
            [fileId]: {{ shortcutId: fileId, type: "file_shortcut", objectId: "object-10", createdAt: "2026-08-01T00:00:00Z" }},
            [linkId]: {{ shortcutId: linkId, type: "external_link_shortcut", canonicalTarget: "https://example.com", createdAt: "2026-08-01T00:00:00Z" }},
          }},
        }};
        const options = {{ scope: raw.scope, internalPolicy: policy }};
        let state = subject.createWorkspaceDockState(raw, options);
        state = subject.workspaceDockReducer(state, {{ type: "enterEdit" }});
        state = subject.workspaceDockReducer(state, {{ type: "unpin", shortcutId: linkId }});
        const afterMutation = JSON.parse(JSON.stringify(state));
        state = subject.workspaceDockReducer(state, {{ type: "enterEdit" }});
        state = subject.workspaceDockReducer(state, {{ type: "cancelEdit" }});
        const cancelled = JSON.parse(JSON.stringify(state));

        state = subject.workspaceDockReducer(state, {{ type: "enterEdit" }});
        state = subject.workspaceDockReducer(state, {{ type: "unpin", shortcutId: linkId }});
        state = subject.workspaceDockReducer(state, {{ type: "doneEdit" }});
        const done = JSON.parse(JSON.stringify(state));

        let invalidation = subject.createWorkspaceDockState(raw, options);
        invalidation = subject.workspaceDockReducer(invalidation, {{ type: "enterEdit" }});
        invalidation = subject.workspaceDockReducer(invalidation, {{ type: "unpin", shortcutId: linkId }});
        invalidation = subject.workspaceDockReducer(invalidation, {{
          type: "authoritativeFileInvalidated",
          objectId: "object-10",
        }});
        const purged = JSON.parse(JSON.stringify(invalidation));
        invalidation = subject.workspaceDockReducer(invalidation, {{ type: "cancelEdit" }});
        process.stdout.write(JSON.stringify({{
          fileId,
          linkId,
          raw,
          afterMutation,
          cancelled,
          done,
          purged,
          afterPurgeCancel: invalidation,
        }}));
        """
    )
    link_id = result["linkId"]
    file_id = result["fileId"]
    assert link_id not in result["afterMutation"]["preference"]["shortcuts"]
    assert result["afterMutation"]["effects"] == []
    assert result["cancelled"]["preference"]["shortcuts"].keys() == (
        result["raw"]["shortcuts"].keys()
    )
    assert result["cancelled"]["effects"] == []
    assert result["done"]["effects"] == [
        {
            "type": "persist_preference",
            "reason": "edit_done",
            "preference": result["done"]["preference"],
        }
    ]
    assert link_id not in result["done"]["preference"]["shortcuts"]

    assert file_id not in result["purged"]["preference"]["shortcuts"]
    assert file_id not in result["purged"]["editSession"]["baseline"]["shortcuts"]
    purge_effect = result["purged"]["effects"][0]
    assert purge_effect["type"] == "authoritative_purge"
    assert purge_effect["shortcutIds"] == [file_id]
    assert purge_effect["objectId"] == "object-10"
    assert purge_effect["preference"] == result["purged"]["editSession"]["baseline"]
    assert file_id not in purge_effect["preference"]["shortcuts"]
    assert link_id in purge_effect["preference"]["shortcuts"]
    assert link_id not in result["purged"]["preference"]["shortcuts"]
    assert file_id not in result["afterPurgeCancel"]["preference"]["shortcuts"]
    assert link_id in result["afterPurgeCancel"]["preference"]["shortcuts"]
    assert purge_effect["preference"] == result["afterPurgeCancel"]["preference"]
    assert result["afterPurgeCancel"]["effects"] == []


def test_pointer_and_keyboard_reorder_obey_slop_halves_boundaries_and_cancel() -> None:
    result = _run_node(
        f"""
        {POLICY_JS}
        const one = "file-shortcut:00000000-0000-4000-8000-000000000021";
        const two = "file-shortcut:00000000-0000-4000-8000-000000000022";
        const raw = {{
          version: subject.WORKSPACE_DOCK_PREFERENCE_VERSION,
          scope: {{ organizationId: "org-1", userId: "user-1" }},
          order: ["finder", one, "ai", two, "review", "trash"],
          shortcuts: {{
            [one]: {{ shortcutId: one, type: "file_shortcut", objectId: "object-21", createdAt: "2026-08-01T00:00:00Z" }},
            [two]: {{ shortcutId: two, type: "file_shortcut", objectId: "object-22", createdAt: "2026-08-01T00:00:00Z" }},
          }},
        }};
        const options = {{ scope: raw.scope, internalPolicy: policy }};
        let state = subject.createWorkspaceDockState(raw, options);
        state = subject.workspaceDockReducer(state, {{ type: "enterEdit" }});
        const before = JSON.parse(JSON.stringify(state));
        state = subject.workspaceDockReducer(state, {{
          type: "pointerReorder", sourceKey: one, targetKey: two, targetHalf: "after", movementPx: 5,
        }});
        const belowSlop = JSON.parse(JSON.stringify(state));
        state = subject.workspaceDockReducer(state, {{
          type: "pointerReorder", sourceKey: one, targetKey: two, targetHalf: "after", movementPx: 6,
        }});
        const pointer = JSON.parse(JSON.stringify(state));
        state = subject.workspaceDockReducer(state, {{ type: "doneEdit" }});
        const committed = JSON.parse(JSON.stringify(state));

        let keyboard = subject.createWorkspaceDockState(raw, options);
        keyboard = subject.workspaceDockReducer(keyboard, {{ type: "enterEdit" }});
        keyboard = subject.workspaceDockReducer(keyboard, {{ type: "keyboardTakeOrDrop", key: two }});
        const taken = JSON.parse(JSON.stringify(keyboard));
        keyboard = subject.workspaceDockReducer(keyboard, {{ type: "keyboardMove", command: "Home" }});
        const movedHome = JSON.parse(JSON.stringify(keyboard));
        keyboard = subject.workspaceDockReducer(keyboard, {{ type: "keyboardMove", command: "End" }});
        const movedEnd = JSON.parse(JSON.stringify(keyboard));
        keyboard = subject.workspaceDockReducer(keyboard, {{ type: "keyboardCancelMove" }});
        const moveCancelled = JSON.parse(JSON.stringify(keyboard));
        keyboard = subject.workspaceDockReducer(keyboard, {{ type: "cancelEdit" }});
        process.stdout.write(JSON.stringify({{
          one, two, before, belowSlop, pointer, committed, taken, movedHome, movedEnd, moveCancelled, cancelled: keyboard,
        }}));
        """
    )
    one = result["one"]
    two = result["two"]
    assert result["belowSlop"]["preference"]["order"] == result["before"]["preference"]["order"]
    assert result["belowSlop"]["effects"] == []
    pointer_order = result["pointer"]["preference"]["order"]
    assert pointer_order.index(one) == pointer_order.index(two) + 1
    assert [effect["type"] for effect in result["pointer"]["effects"]] == [
        "suppress_open",
        "announce",
    ]
    assert [effect["type"] for effect in result["committed"]["effects"]] == [
        "persist_preference"
    ]
    assert result["taken"]["keyboardMove"]["key"] == two
    assert result["movedHome"]["preference"]["order"][1] == two
    assert result["movedEnd"]["preference"]["order"][-2] == two
    assert result["moveCancelled"]["preference"]["order"] == result["before"]["preference"]["order"]
    assert result["cancelled"]["preference"]["order"] == result["before"]["preference"]["order"]
    assert result["cancelled"]["effects"] == []


def test_active_selection_running_unpinned_and_overflow_keep_all_protected_items() -> None:
    result = _run_node(
        f"""
        {POLICY_JS}
        const file = "file-shortcut:00000000-0000-4000-8000-000000000031";
        const internal = "internal-link:00000000-0000-4000-8000-000000000032";
        const external = "external-link:00000000-0000-4000-8000-000000000033";
        const raw = {{
          version: subject.WORKSPACE_DOCK_PREFERENCE_VERSION,
          scope: {{ organizationId: "org-1", userId: "user-1" }},
          order: ["finder", "results", "research", "ai", "create", internal, file, external, "review", "trash"],
          shortcuts: {{
            [file]: {{ shortcutId: file, type: "file_shortcut", objectId: "object-31", createdAt: "2026-08-01T00:00:00Z" }},
            [internal]: {{ shortcutId: internal, type: "internal_link_shortcut", canonicalTarget: "contentengine://app/ai?space=bombbar&tab=decisions", createdAt: "2026-08-01T00:00:00Z" }},
            [external]: {{ shortcutId: external, type: "external_link_shortcut", canonicalTarget: "https://example.com", createdAt: "2026-08-01T00:00:00Z" }},
          }},
        }};
        const state = subject.createWorkspaceDockState(raw, {{ scope: raw.scope, internalPolicy: policy }});
        const selectedInternal = subject.selectWorkspaceDockShortcut(state, {{
          activeInternalTarget: "contentengine://app/ai?view=decisions",
          quickLookObjectId: "object-31",
          finderSelectionObjectId: "object-31",
          activeAppId: "review",
        }}, policy);
        const selectedQuickLook = subject.selectWorkspaceDockShortcut(state, {{
          quickLookObjectId: "object-31",
          finderSelectionObjectId: "object-stale",
          activeAppId: "review",
        }}, policy);
        const staleFinder = subject.selectWorkspaceDockShortcut(state, {{
          finderSelectionObjectId: "object-31",
          activeAppId: "ai",
        }}, policy);
        const activeFinder = subject.selectWorkspaceDockShortcut(state, {{
          finderSelectionObjectId: "object-31",
          activeAppId: "finder",
        }}, policy);
        const presentation = subject.computeWorkspaceDockPresentation(state, {{
          activeAppId: "settings",
          runningAppIds: ["research"],
          selectedShortcutId: file,
          capacity: 5,
        }});
        process.stdout.write(JSON.stringify({{
          file, internal, external, selectedInternal, selectedQuickLook, staleFinder, activeFinder, presentation,
        }}));
        """
    )
    file_id = result["file"]
    assert result["selectedInternal"] == result["internal"]
    assert result["selectedQuickLook"] == file_id
    assert result["staleFinder"] is None
    assert result["activeFinder"] == file_id
    presentation = result["presentation"]
    assert presentation["capacity"] == 6
    assert presentation["activeUnpinnedInjected"] is True
    assert set(("finder", "review", "settings", "trash", file_id, "__more__")).issubset(
        presentation["visibleKeys"]
    )
    assert len(presentation["visibleKeys"]) == 6
    assert presentation["visibleKeys"].index("__more__") < presentation["visibleKeys"].index("trash")
    items = {item["key"]: item for item in presentation["items"]}
    assert items["settings"]["running"] is True
    assert items["settings"]["indicator"] == "app_running"
    assert items[file_id]["selected"] is True
    assert items[file_id]["running"] is False
    assert items[file_id]["indicator"] == "shortcut_selected"


def test_pin_zone_requires_450ms_and_drop_surfaces_are_mutually_exclusive() -> None:
    result = _run_node(
        """
        let pin = subject.createWorkspaceDockPinZoneState();
        pin = subject.workspaceDockPinZoneReducer(pin, {
          type: "enter", surface: "empty_shelf", dragKind: "file", objectId: "object-41", now: 100,
        });
        const entered = JSON.parse(JSON.stringify(pin));
        pin = subject.workspaceDockPinZoneReducer(pin, { type: "tick", now: 549 });
        const early = JSON.parse(JSON.stringify(pin));
        pin = subject.workspaceDockPinZoneReducer(pin, { type: "tick", now: 550 });
        const ready = JSON.parse(JSON.stringify(pin));
        const appDrop = subject.classifyWorkspaceDockDrop(
          { surface: "app_tile", targetKey: "review", dragKind: "file", objectId: "object-41" },
          pin,
        );
        const pinDrop = subject.classifyWorkspaceDockDrop(
          { surface: "pin_zone", targetKey: "", dragKind: "file", objectId: "object-41" },
          pin,
        );
        const shelfDrop = subject.classifyWorkspaceDockDrop(
          { surface: "empty_shelf", dragKind: "file", objectId: "object-41" },
          pin,
        );

        let state = subject.createWorkspaceDockState(
          ["finder", "review", "trash"],
          { scope: { organizationId: "org-1", userId: "user-1" } },
        );
        state = subject.workspaceDockReducer(state, {
          type: "pinZoneEnter", surface: "empty_shelf", dragKind: "file", objectId: "object-41", now: 100,
        });
        state = subject.workspaceDockReducer(state, { type: "pinZoneTick", now: 550 });
        state = subject.workspaceDockReducer(state, {
          type: "pinZoneDrop", surface: "pin_zone", dragKind: "file", objectId: "object-41",
        });
        process.stdout.write(JSON.stringify({ entered, early, ready, appDrop, pinDrop, shelfDrop, state }));
        """
    )
    assert result["entered"]["phase"] == "arming"
    assert result["early"]["phase"] == "arming"
    assert result["ready"]["phase"] == "ready"
    assert result["appDrop"] == {"kind": "app_action", "appKey": "review"}
    assert result["pinDrop"] == {"kind": "pin_shortcut", "objectId": "object-41"}
    assert result["shelfDrop"]["kind"] == "none"
    assert result["state"]["pinZone"]["phase"] == "idle"
    assert result["state"]["effects"] == [
        {
            "type": "dock_drop_intent",
            "classification": {"kind": "pin_shortcut", "objectId": "object-41"},
        }
    ]
    assert all(effect["type"] != "persist_preference" for effect in result["state"]["effects"])


def test_file_resolution_is_live_and_serialization_excludes_transient_or_sensitive_data() -> None:
    result = _run_node(
        f"""
        {POLICY_JS}
        const fileId = "file-shortcut:00000000-0000-4000-8000-000000000051";
        const raw = {{
          version: subject.WORKSPACE_DOCK_PREFERENCE_VERSION,
          scope: {{ organizationId: "org-1", userId: "user-1" }},
          order: ["finder", "project:bombbar", fileId, "review", "trash"],
          shortcuts: {{
            [fileId]: {{
              shortcutId: fileId,
              type: "file_shortcut",
              objectId: "object-51",
              labelOverride: "Старое имя",
              createdAt: "2026-08-01T00:00:00Z",
              signedUrl: "https://secret.example/file?token=private",
              fileContent: "private-content",
            }},
          }},
          editSession: {{ formValues: {{ prompt: "private-prompt" }} }},
          accessToken: "private-token",
        }};
        const rejected = subject.normalizeWorkspaceDockPreference(raw, {{ scope: raw.scope, internalPolicy: policy }});
        const clean = {{
          ...raw,
          shortcuts: {{
            [fileId]: {{
              shortcutId: fileId,
              type: "file_shortcut",
              objectId: "object-51",
              labelOverride: "Старое имя",
              createdAt: "2026-08-01T00:00:00Z",
              arbitrary: "drop-me",
            }},
          }},
        }};
        const state = subject.createWorkspaceDockState(clean, {{
          scope: clean.scope,
          internalPolicy: policy,
          catalog: [
            ...subject.WORKSPACE_DOCK_DEFAULT_CATALOG,
            {{ key: "project:bombbar", kind: "system", removable: true }},
          ],
        }});
        const before = JSON.stringify(state.preference);
        const live = subject.resolveWorkspaceDockFileShortcut(state.preference.shortcuts[fileId], {{
          objectId: "object-51", name: "Новое имя", parentId: "folder-9", permission: "edit",
          rawPath: "private/path", signedUrl: "https://secret.example/live",
        }});
        const trashed = subject.resolveWorkspaceDockFileShortcut(state.preference.shortcuts[fileId], {{
          objectId: "object-51", name: "Новое имя", parentId: "trash", trashed: true,
        }});
        const revoked = subject.resolveWorkspaceDockFileShortcut(state.preference.shortcuts[fileId], {{
          objectId: "object-51", name: "Новое имя", accessState: "revoked",
        }});
        const serialized = subject.serializeWorkspaceDockPreference({{
          ...state,
          editSession: {{ baseline: state.preference, formValues: {{ prompt: "private-prompt" }} }},
          pending: {{ paidConfirmation: true }},
        }});
        process.stdout.write(JSON.stringify({{
          fileId,
          rejected,
          unchanged: before === JSON.stringify(state.preference),
          live,
          trashed,
          revoked,
          serialized,
          encoded: JSON.stringify(serialized),
        }}));
        """
    )
    file_id = result["fileId"]
    assert result["rejected"]["preference"]["shortcuts"] == {}
    assert result["rejected"]["issues"] == ["forbidden_descriptor_field"]
    assert result["unchanged"] is True
    assert result["live"] == {
        "state": "live",
        "objectId": "object-51",
        "label": "Новое имя",
        "parentId": "folder-9",
        "permission": "edit",
        "purgeEligible": False,
    }
    assert result["trashed"]["state"] == "trashed"
    assert result["trashed"]["purgeEligible"] is False
    assert result["revoked"]["state"] == "unavailable"
    assert result["revoked"]["purgeEligible"] is True
    assert result["serialized"]["order"] == [
        "finder",
        "project:bombbar",
        file_id,
        "review",
        "trash",
    ]
    for forbidden in (
        "signedUrl",
        "private-content",
        "private-prompt",
        "accessToken",
        "private-token",
        "paidConfirmation",
        "rawPath",
        "drop-me",
    ):
        assert forbidden not in result["encoded"]


def test_saved_legacy_default_order_upgrades_to_the_conveyor_but_custom_stays() -> None:
    """25.08: «Результаты» переехали после «Опубликовать». 26.08: появились
    «Паспорта». Сохранённый порядок, в точности равный любому старому дефолту,
    — снимок прежнего канона, а не выбор человека: он апгрейдится сам.
    Действительно свой порядок неприкосновенен."""
    result = _run_node(
        """
        const scope = { organizationId: "org-1", userId: "user-1" };
        const legacy = subject.createWorkspaceDockState(JSON.stringify({
          version: 3,
          scope,
          order: [
            "finder", "results", "research", "ai", "create",
            "review", "publish", "processes", "settings", "trash",
          ],
          shortcuts: {},
        }), { scope });
        const custom = subject.createWorkspaceDockState(JSON.stringify({
          version: 3,
          scope,
          order: ["finder", "results", "ai", "review", "trash"],
          shortcuts: {},
        }), { scope });
        process.stdout.write(JSON.stringify({
          legacyOrder: legacy.preference.order,
          customOrder: custom.preference.order,
        }));
        """
    )
    assert result["legacyOrder"] == [
        "finder", "research", "ai", "create", "review",
        "publish", "results", "passports", "processes", "settings", "trash",
    ]
    assert result["customOrder"] == ["finder", "results", "ai", "review", "trash"]
