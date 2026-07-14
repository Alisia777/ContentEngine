from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607140001_limited_member_provisioning.sql"
).read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+(?:public|content_factory)\.{name}"
        rf"\s*\([^)]*\).*?as\s+\$\$(.*?)\$\$\s*;",
        MIGRATION,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing function {name}"
    return match.group(1).casefold()


def test_limited_member_rpc_is_service_role_only_and_privilege_narrow() -> None:
    assert re.search(
        r"create\s+or\s+replace\s+function\s+public\.system_provision_limited_member"
        r"\s*\(\s*p_payload\s+jsonb[^)]*\).*?security\s+definer"
        r".*?set\s+search_path\s*=\s*''",
        MIGRATION,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert re.search(
        r"revoke\s+all\s+on\s+function\s+public\.system_provision_limited_member"
        r"\(jsonb\)\s+from\s+public\s*,\s*anon\s*,\s*authenticated",
        MIGRATION,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+public\.system_provision_limited_member"
        r"\(jsonb\)\s+to\s+service_role",
        MIGRATION,
        flags=re.IGNORECASE,
    )

    body = _function_body("system_provision_limited_member")
    assert "requested_role not in ('viewer', 'trainee')" in body
    for privileged_role in ("owner", "admin", "producer", "reviewer", "operator"):
        assert f"requested_role = '{privileged_role}'" not in body
    assert "limited_member_role_invalid" in body


def test_limited_member_rpc_fails_closed_on_identity_and_membership_drift() -> None:
    body = _function_body("system_provision_limited_member")

    assert "organization.status = 'active'" in body
    assert "membership.role in ('owner', 'admin')" in body
    assert "profile.status = 'active'" in body
    assert "provisioner_auth.email_confirmed_at is not null" in body
    assert "provisioner_auth.deleted_at is null" in body
    assert "provisioner_auth.banned_until" in body
    assert "target_email_confirmed_at is null" in body
    assert "target_deleted_at is not null" in body
    assert "target_banned_until" in body
    assert "target_membership_history_conflict" in body
    assert "target_membership_role_conflict" in body
    assert "pg_advisory_xact_lock" in body
    assert "system_provision_limited_member" in body
    assert "content_factory_private.begin_command" in body
    assert "content_factory_private.finish_command" in body


def test_certified_viewer_can_read_own_storage_but_cannot_mutate_it() -> None:
    body = _function_body("storage_access_allowed")

    assert "p_allow_team_read" in body
    assert "p_owner_id = auth.uid()::text" in body
    assert "not p_allow_team_read" in body
    assert (
        "membership.role in (\n            'owner', 'admin', 'producer', "
        "'reviewer', 'operator'\n          )"
    ) in body
    assert "'viewer'" not in body
    assert "'trainee'" not in body
