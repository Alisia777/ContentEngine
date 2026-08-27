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


def test_hypothesis_launch_link_flows_through_operator_selection() -> None:
    """Замыкание «гипотеза → запуск» (202608260011, проверено живой пробой в
    проде: выбор → bind → манифест с точной версией, всё откатано): оператор
    выбирает утверждённую гипотезу в формах генерации, триггер манифеста
    читает выбор bound_by и вписывает версию. Платный контур не тронут."""
    binding = (
        ROOT / "supabase/migrations/202608260011_hypothesis_launch_binding_v1.sql"
    ).read_text(encoding="utf-8")
    assert "content_hypothesis_operator_selections" in binding
    assert "creator_select_content_hypothesis" in binding
    assert "content_hypothesis_version_not_approved" in binding
    assert "on conflict on constraint content_hypothesis_operator_selections_pk" in binding
    assert "s.profile_id = new.bound_by" in binding
    assert "'hypothesis_version_id', selection_row.hypothesis_version_id" in binding
    intake = (APP / "generation-strategy-intake-v4.js").read_text(encoding="utf-8")
    # Пикер в обеих формах, DOM — только по отпечатку, выбор уходит в RPC.
    assert intake.count("hypothesisPickerCard(") >= 3  # def + два вызова
    assert 'hypothesisPickerCard("copy_video")' in intake
    assert 'hypothesisPickerCard("strategy_video")' in intake
    assert "creator_select_content_hypothesis" in intake
    assert "hypothesisFingerprint" in intake
    assert "Гипотеза запуска" in intake
    # Подписи-путеводители в форме и срезе гипотезы.
    assert "Одно изменение — одна гипотеза" in PORTAL
    assert "Значение метрики ДО теста" in PORTAL
    assert "Путь гипотезы: черновик" in PORTAL


def test_hypothesis_owner_and_passport_hypothesis() -> None:
    """Закрепление человека за гипотезой и гипотеза в паспорте (202608260012,
    живая проба в проде: owner назначен, список отдал assigned, срез — членов
    команды, паспорт показал H-001 v1 из манифеста; всё откатано)."""
    owner = (
        ROOT / "supabase/migrations/202608260012_hypothesis_owner_and_passport_v1.sql"
    ).read_text(encoding="utf-8")
    assert "creator_assign_content_hypothesis_owner" in owner
    assert "content_hypothesis_owner_not_member" in owner
    assert "array['owner', 'admin', 'producer']" in owner
    assert "'assigned', (" in owner.replace("''", "'")
    assert "'members', (" in owner.replace("''", "'")
    # Паспорт берёт гипотезу из МАНИФЕСТА — точная версия момента bind.
    assert "manifest_row.hypothesis_version_id" in owner
    assert "passport_hypothesis_value" in owner
    # Срез: select ответственного с автосохранением; подпись про подстановку.
    assert "data-hypothesis-owner-select" in PORTAL
    assert "assignContentHypothesisOwner" in PORTAL
    assert "подставится в формах генерации сама" in PORTAL
    # Паспорт: гипотеза со ссылкой в папку и формулировкой версии.
    assert "Метрика гипотезы" in PORTAL
    # Intake: автоподстановка назначенной — один раз, без перекрытия выбора.
    intake = (APP / "generation-strategy-intake-v4.js").read_text(encoding="utf-8")
    assert "assignedId" in intake
    assert "autoAppliedFor" in intake
    assert "назначена вам" in intake


def test_hypothesis_sources_and_variant_results() -> None:
    """Источники-доказательства и сравнение вариантов (202608270001, живая
    проба: привязка идемпотентна тем же binding_id, delete отбит guard'ом,
    evidence_sources и launches читаются; откатано)."""
    sources = (
        ROOT / "supabase/migrations/202608270001_hypothesis_sources_and_results_v1.sql"
    ).read_text(encoding="utf-8")
    assert "content_hypothesis_source_bindings" in sources
    assert "content_hypothesis_source_binding_append_only" in sources
    assert "creator_bind_content_hypothesis_source" in sources
    assert "canonical_url_snapshot" in sources
    assert "on conflict on constraint content_hypothesis_source_bindings_uq" in sources
    # Варианты: результат, движок и последний снимок метрик по каждому запуску.
    assert "'result_media_id', (" in sources.replace("''", "'")
    assert "'metrics', (" in sources.replace("''", "'")
    assert "interval '72 hours'" in sources.replace("''", "'")
    # Экран: буквы вариантов, основная метрика гипотезы, лучший только среди
    # зрелых и только по основной метрике; человеческий вывод остаётся внизу.
    assert "Вариант ${letter}" in PORTAL
    assert "metricValueOf" in PORTAL
    assert "content-hypothesis-variant--best" in PORTAL
    assert "лучшее значение основной метрики среди зрелых данных" in PORTAL
    # Привязка ссылки: та же нормализация, реестр источников один.
    assert "hypothesis-bind-source" in PORTAL
    assert "bindContentHypothesisSource" in PORTAL
    assert "contentengine_exact_youtube_source_queue" in PORTAL
    assert "Источники-доказательства" in PORTAL


def test_team_people_show_assigned_hypotheses_and_docs_exist() -> None:
    """«В админке людей закреплять за гипотезой»: таблица «Команда → Люди»
    несёт колонку «Гипотезы» — коды закреплённых, ссылками в срез; данные —
    экранный джойн двух существующих ответов, отказ дозапроса таблицу не
    ломает. Документация трёх контуров (ТЗ раздел 10) существует."""
    assert "<th>Гипотезы</th>" in PORTAL
    assert "teamMemberHypothesesMarkup" in PORTAL
    assert "_hypotheses" in PORTAL
    # Выдача прямо из таблицы («где гипотезу выдать», 27.08): селект в ячейке
    # зовёт тот же RPC закрепления, право проверяет сервер.
    assert "data-team-hypothesis-assign" in PORTAL
    assert "Выдать гипотезу…" in PORTAL
    assert "assignHypothesisFromTeam" in PORTAL
    assert PORTAL.count('"creator_assign_content_hypothesis_owner"') == 2
    for name in (
        "CONTENT_SOURCE_INTAKE_V1.md",
        "CONTENT_RESULT_PASSPORT_V1.md",
        "CONTENT_HYPOTHESES_WORKSPACE_V1.md",
    ):
        doc = (ROOT / "docs" / name).read_text(encoding="utf-8")
        assert len(doc) > 800, name
