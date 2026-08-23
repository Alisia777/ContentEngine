"""Фаза 0 контура авторазмещения: реестр владения аккаунтами компании.

docs/PUBLISHING_ACCOUNTS_CONTOUR_2026-08-23.md §4.1 и §5.4. Поля владения,
связь размещения с аккаунтом, RPC владения и задачи хранителю при увольнении —
всё без единого секрета в таблицах.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202608230024_publishing_accounts_ownership_v1.sql"
PGTAP = ROOT / "supabase/tests/publishing_accounts_ownership_v1_test.sql"
ADMIN_VIEW = ROOT / "web/app/admin-people-view.js"
API = ROOT / "web/app/supabase-api.js"
APP = ROOT / "web/app/app.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_migration_adds_ownership_fields_without_secrets() -> None:
    source = text(MIGRATION)
    for column in (
        "ownership_kind",
        "custodian_profile_id",
        "registration_email_alias",
        "registration_phone_ref",
        "external_account_id",
        "posting_mode",
        "connection_status",
    ):
        assert f"add column if not exists {column}" in source
    assert "'business_portfolio', 'brand_account', 'community', 'channel_bot'," in source
    assert "posting_mode in ('api', 'assisted', 'disabled')" in source
    assert "references content_factory.memberships (organization_id, profile_id)" in source
    # Словарь площадок закрыт и совпадает с размещениями плюс кабинеты и «другое».
    assert "'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'," in source
    assert "'ozon', 'rutube', 'other'" in source
    # Ни одного секрета: токены, пароли, cookies в таблице не появляются.
    for forbidden in ("token text", "password", "cookie", "refresh_token", "access_token"):
        assert forbidden not in source.lower()


def test_placements_link_to_the_company_account() -> None:
    source = text(MIGRATION)
    assert "add column if not exists managed_account_id uuid" in source
    assert "placements_managed_account_fk" in source
    assert "references content_factory.managed_accounts (organization_id, id)" in source
    assert "placements_managed_account_idx" in source


def test_ownership_rpc_is_admin_only_and_fails_closed() -> None:
    source = text(MIGRATION)
    rpc = source.split("create or replace function public.creator_admin_account_ownership(", 1)[1]
    rpc = rpc.split("revoke all on function public.creator_admin_account_ownership", 1)[0]
    assert "content_factory_private.require_admin_actor(organization_id)" in rpc
    assert "content_factory_private.begin_command(" in rpc
    assert "content_factory_private.finish_command(" in rpc
    assert "message = 'account_changed_concurrently'" in rpc
    # Режим api включается только подключением, не рукой.
    assert "message = 'posting_mode_requires_connection'" in rpc
    assert "member.role in ('owner', 'admin', 'producer')" in rpc
    assert "message = 'custodian_not_eligible'" in rpc
    assert "grant execute on function public.creator_admin_account_ownership(jsonb)\n  to authenticated, service_role;" in source


def test_offboarding_creates_a_custodian_task_per_revoked_account() -> None:
    source = text(MIGRATION)
    block = source.split("do $offboarding_tasks$", 1)[1].split("$offboarding_tasks$;", 1)[0]
    assert "get diagnostics account_assignments_revoked_count = row_count;" in block
    assert "''publishing_account_offboarding''" in block
    assert "account.ownership_kind = ''personal_issued''" in block
    assert "then account.custodian_profile_id else actor_id end" in block
    assert "assignment.revoked_at = now()" in block


def test_pgtap_covers_the_ownership_contract() -> None:
    source = text(PGTAP)
    for marker in (
        "platform vocabulary is closed",
        "api posting requires a connection",
        "an operator cannot be the custodian",
        "the admin snapshot exposes ownership fields",
        "the custodian receives the platform-role removal task",
        "placements carry the company account",
    ):
        assert marker in source


def test_admin_ui_exposes_ownership_without_secret_fields() -> None:
    view = text(ADMIN_VIEW)
    assert "export const ADMIN_OWNERSHIP_KINDS" in view
    assert 'class="admin-form admin-account-ownership-form"' in view
    for field in (
        'name="ownership_kind"',
        'name="custodian_profile_id"',
        'name="registration_email_alias"',
        'name="registration_phone_ref"',
        'name="external_account_id"',
        'name="posting_mode"',
    ):
        assert field in view
    # Режим api в форме недоступен, пока аккаунт не подключён.
    assert 'value === "api" && !apiAllowed ? "disabled" : ""' in view
    api = text(API)
    assert 'adminAccountOwnership: "creator_admin_account_ownership"' in api
    assert "setManagedAccountOwnership(accountId, expectedUpdatedAt, ownership = {})" in api
    assert 'action: "set_ownership"' in api
    app = text(APP)
    assert 'form.classList.contains("admin-account-ownership-form")' in app
    assert "state.api.setManagedAccountOwnership(accountId, expectedUpdatedAt, {" in app
