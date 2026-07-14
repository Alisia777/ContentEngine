from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607140007_placement_compliance_ack.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def test_placement_rpc_requires_and_audits_compliance_acknowledgement() -> None:
    lowered = MIGRATION.casefold()
    assert "alter function public.creator_confirm_placement(jsonb)" in lowered
    assert "set schema content_factory_private" in lowered
    assert "placement_compliance_ack_required" in lowered
    assert "#variable_conflict use_variable" in lowered
    assert "jsonb_typeof(p_payload -> 'compliance_ack')" in lowered
    assert "p_payload -> 'compliance_ack' is distinct from 'true'::jsonb" in lowered
    assert "result := content_factory_private.creator_confirm_placement(p_payload)" in lowered
    assert "compliance_submission_ack" in lowered
    assert "compliance_confirmation_ack" in lowered
    assert "checklist_version" in lowered
    assert "decision_source" in lowered
    assert "update content_factory.placements" in lowered
    assert "update content_factory.creator_tasks" in lowered
    assert "placement_compliance_acknowledged" in lowered
    assert "placement_compliance_audit_failed" in lowered
    assert "not (coalesce(placement.metadata, '{}'::jsonb) ? acknowledgement_key)" in lowered
    assert "not (coalesce(task.result, '{}'::jsonb) ? acknowledgement_key)" in lowered
    assert "grant execute on function public.creator_confirm_placement(jsonb)" in lowered
    assert "to authenticated" in lowered
    assert "from public, anon, authenticated" in lowered


def test_placement_ui_makes_the_compliance_gate_explicit() -> None:
    assert 'name="compliance_ack" value="confirmed" required' in APP
    assert "Рекламный статус проверен по инструкции задачи" in APP
    assert "Если в задаче нет решения по рекламе" in APP
    assert "await state.api.confirmPlacement(taskId, finalUrl, complianceAck)" in APP
    assert "confirmPlacement(taskId, finalUrl, complianceAck)" in ADAPTER
    assert "compliance_ack: complianceAck === true" in ADAPTER
    assert "placement_compliance_ack_required" in ADAPTER
