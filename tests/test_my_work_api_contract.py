from pathlib import Path
import json
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")


def _run_api(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required")
    with tempfile.TemporaryDirectory() as temporary_directory:
        workdir = Path(temporary_directory)
        (workdir / "subject.mjs").write_text(API, encoding="utf-8")
        (workdir / "contract.mjs").write_text(
            """
            import { CreatorApi } from "./subject.mjs";
            globalThis.window = {
              sessionStorage: {
                values: new Map(),
                getItem(key) { return this.values.get(key) || null; },
                setItem(key, value) { this.values.set(key, value); },
              },
            };
            const calls = [];
            const supabase = {
              schema: () => ({
                rpc: async (name, args) => {
                  calls.push([name, args.p_payload]);
                  return { data: { ok: true }, error: null };
                },
              }),
            };
            const api = new CreatorApi(supabase, {
              RPC_SCHEMA: "public",
              STORAGE_BUCKET: "private",
            });
            api.organizationId = "00000000-0000-4000-8000-000000000001";
            """
            + f"const result = await (async () => {{\n{body}\n}})();\n"
            + "process.stdout.write(JSON.stringify({ result, calls }));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_my_work_read_contract_is_scoped_filtered_and_paginated() -> None:
    payload = _run_api(
        """
        await api.myWork({
          query: "Bombbar",
          item_types: ["task", "generation", "task"],
          statuses: ["blocked", "awaiting_decision"],
          page_size: 25,
          cursor: { updated_at: "2026-07-16T12:00:00Z", item_type: "task", id: "task-1" },
        });
        return true;
        """
    )
    name, request_payload = payload["calls"][0]
    assert name == "creator_my_work"
    assert request_payload["organization_id"].endswith("0001")
    assert request_payload["query"] == "Bombbar"
    assert request_payload["item_types"] == ["task", "generation"]
    assert request_payload["statuses"] == ["blocked", "awaiting_decision"]
    assert request_payload["page_size"] == 25
    assert request_payload["cursor"]["id"] == "task-1"


def test_notification_mutation_is_idempotent_and_org_scoped() -> None:
    payload = _run_api(
        """
        await api.notifications({ unread_only: true });
        await api.markNotificationsRead([
          "11111111-1111-4111-8111-111111111111",
          "11111111-1111-4111-8111-111111111111",
        ]);
        await api.markAllNotificationsRead();
        return true;
        """
    )
    read_name, read_payload = payload["calls"][0]
    write_name, write_payload = payload["calls"][1]
    assert read_name == "creator_notifications"
    assert read_payload["unread_only"] is True
    assert write_name == "creator_mark_notifications_read"
    assert write_payload["notification_ids"] == [
        "11111111-1111-4111-8111-111111111111"
    ]
    assert write_payload["is_read"] is True
    assert write_payload["organization_id"].endswith("0001")
    assert write_payload["idempotency_key"]
    mark_all_name, mark_all_payload = payload["calls"][2]
    assert mark_all_name == "creator_mark_notifications_read"
    assert mark_all_payload["all_unread"] is True
    assert mark_all_payload["is_read"] is True
    assert "notification_ids" not in mark_all_payload
    assert mark_all_payload["idempotency_key"]


def test_saved_view_and_training_progress_mutations_use_narrow_payloads() -> None:
    payload = _run_api(
        """
        await api.savedWorkViews({
          action: "upsert",
          name: "Блокеры",
          filters: { itemTypes: ["task", "unknown"], statuses: ["blocked"] },
          is_default: true,
        });
        await api.saveTrainingProgress({
          module_code: "factory_basics",
          walkthrough_id: "first_shift",
          current_frame_id: "frame_2",
          position_seconds: 14.5,
          completed_frame_ids: ["frame_1"],
        });
        return true;
        """
    )
    saved_name, saved_payload = payload["calls"][0]
    training_name, training_payload = payload["calls"][1]
    assert saved_name == "creator_saved_work_views"
    assert saved_payload["filters"]["item_types"] == ["task"]
    assert saved_payload["filters"]["statuses"] == ["blocked"]
    assert saved_payload["is_default"] is True
    assert training_name == "creator_save_training_progress"
    assert training_payload["walkthrough_id"] == "first_shift"
    assert training_payload["position_seconds"] == 14.5
    assert saved_payload["idempotency_key"]
    assert training_payload["idempotency_key"]


def test_new_rpc_names_are_centralized_in_the_browser_api_boundary() -> None:
    for rpc_name in (
        "creator_my_work",
        "creator_notifications",
        "creator_mark_notifications_read",
        "creator_training_progress",
        "creator_save_training_progress",
        "creator_saved_work_views",
    ):
        assert f'"{rpc_name}"' in API
