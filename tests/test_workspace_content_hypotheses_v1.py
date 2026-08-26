"""Папка «Гипотезы» (контур №3 ТЗ, v1): хребет данных и Dock-приложение.

Гипотеза — проверяемое утверждение «Если X, то метрика Y, потому что Z»:
identity с жизненным циклом, append-only версии с canonical hash, решения
только человеческие и только с причиной. Confirmed не ставит ни один RPC
автоматически. Прод проверен транзакционной пробой: создание H-001, вторая
версия, утверждение, отбитая попытка правки формулировки, решение rework —
всё работало и откатилось.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
CORE = (APP / "workspace-os-v4.js").read_text(encoding="utf-8")
CONTRACT = (APP / "workspace-dock-contract.js").read_text(encoding="utf-8")
REGISTRY = (APP / "workspace-command-registry.js").read_text(encoding="utf-8")
CATALOG = (APP / "catalog.js").read_text(encoding="utf-8")
PORTAL = (APP / "app.js").read_text(encoding="utf-8")
API = (APP / "supabase-api.js").read_text(encoding="utf-8")
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
SPRITE = (APP / "assets" / "workspace_dock_icon_sprite_v4_7_1.svg").read_text(
    encoding="utf-8"
)
SPINE = (
    ROOT / "supabase/migrations/202608260009_content_hypotheses_v1.sql"
).read_text(encoding="utf-8")
RPCS = (
    ROOT / "supabase/migrations/202608260010_content_hypotheses_rpcs_v1.sql"
).read_text(encoding="utf-8")


def test_hypotheses_app_is_registered_across_the_shell() -> None:
    assert 'route: "/workspace/hypotheses"' in CORE
    assert '"hypotheses",' in CORE  # canonical dock order
    assert 'key: "hypotheses"' in CORE
    assert '"/workspace/hypotheses",' in CORE  # project-required routes
    assert 'id="ce-dock-hypotheses"' in SPRITE
    assert 'key: "hypotheses", kind: "app", appId: "hypotheses"' in CONTRACT
    assert "hypotheses: []" in REGISTRY
    assert '["hypotheses", "Гипотезы", "∴"]' in CATALOG
    loader_entry = LOADER.split("hypotheses: Object.freeze({", 1)[1].split("})", 1)[0]
    assert "/workspace/hypotheses" in loader_entry
    assert "modules: []" in loader_entry


def test_hypothesis_spine_is_versioned_append_only_and_human_decided() -> None:
    # Identity: код и авторство неизменяемы, удаление запрещено.
    assert "content_hypothesis_identity_immutable" in SPINE
    assert "content_hypothesis_delete_forbidden" in SPINE
    # Версии: формулировка append-only, hash самопроверяется, один approved.
    assert "content_hypothesis_version_append_only" in SPINE
    assert (
        "version_hash = content_factory_private.json_hash(jsonb_build_object("
        in SPINE
    )
    assert "content_hypothesis_versions_one_approved" in SPINE
    # Решения: append-only, причина обязательна, итог identity — из решения.
    assert "content_hypothesis_decision_append_only" in SPINE
    assert "length(btrim(reason)) between 10 and 2000" in SPINE
    assert "apply_content_hypothesis_decision" in SPINE
    # Шаблон формулировки закреплён минимальной длиной.
    assert "length(btrim(statement)) between 20 and 2000" in SPINE


def test_hypothesis_rpcs_are_acl_gated_and_never_auto_confirm() -> None:
    for name in (
        "creator_content_hypotheses",
        "creator_content_hypothesis",
        "creator_save_content_hypothesis",
        "creator_approve_content_hypothesis_version",
        "creator_decide_content_hypothesis",
    ):
        assert f"create or replace function public.{name}" in RPCS
        assert f"grant execute on function" in RPCS
    assert RPCS.count("\nvolatile\n") == 5
    assert "require_workspace_project_access" in RPCS
    # Решение и утверждение — только owner/admin/producer.
    assert RPCS.count("array['owner', 'admin', 'producer']") == 2
    # Автоподтверждения нет нигде: confirmed приходит только из decide.
    assert "'auto_confirmation', false" in RPCS
    assert "when 'confirm' then 'confirmed'" in SPINE
    assert "confirmed" not in RPCS.replace("'auto_confirmation', false", "")
    # Привязка запусков читается из манифестов происхождения.
    assert "generation_provenance_manifests" in RPCS


def test_hypotheses_screen_lives_in_the_section_loop() -> None:
    assert "hypotheses: renderHypothesesSection," in PORTAL
    assert 'section === "hypotheses"' in PORTAL
    assert "state.api.contentHypotheses({ projectId })" in PORTAL
    assert "state.api.contentHypothesis({" in PORTAL
    assert "data.key !== hypothesesSectionKey()" in PORTAL
    assert 'safeWorkspaceRouteEntityId("hypothesis")' in PORTAL
    # Форма создания держит шаблон и честные статусы.
    assert "Если [изменение], то [метрика изменится], потому что [обоснование]" in PORTAL
    assert "hypothesis-create" in PORTAL
    assert "hypothesis-approve" in PORTAL
    assert "hypothesis-decide" in PORTAL
    # Вывод — только человек, причина обязательна.
    assert "Вывод — только человек" in PORTAL
    assert "Причина обязательна" in PORTAL
    assert 'contentHypotheses: "creator_content_hypotheses"' in API
    assert 'decideContentHypothesis: "creator_decide_content_hypothesis"' in API
