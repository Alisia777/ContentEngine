from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607180004_auth_security_hardening.sql"
).read_text(encoding="utf-8")
RECOVERY_EDGE = (
    ROOT / "supabase" / "functions" / "creator-recovery" / "index.ts"
).read_text(encoding="utf-8")
PROVISION = (ROOT / "scripts" / "provision_supabase_member.py").read_text(
    encoding="utf-8"
)


def test_invite_journal_is_force_rls_and_direct_access_is_default_deny() -> None:
    assert "invite_delivery_attempts enable row level security" in MIGRATION
    assert "invite_delivery_attempts force row level security" in MIGRATION
    assert "invite_delivery_attempts_deny_direct" in MIGRATION
    assert "as restrictive" in MIGRATION
    assert "from public, anon, authenticated, service_role" in MIGRATION


def test_public_recovery_has_hashed_client_and_global_provider_quotas() -> None:
    assert "public_recovery_quota_buckets" in MIGRATION
    assert "bucket.request_count < 8" in MIGRATION
    assert "bucket.request_count < 120" in MIGRATION
    assert "public_recovery_quota_limited" in MIGRATION
    assert "dispatch_required', false" in MIGRATION
    assert "client_key_hash" in RECOVERY_EDGE
    assert "clientAddressMaterial(request)" in RECOVERY_EDGE
    assert "contentengine-public-recovery-client:v1:" in RECOVERY_EDGE
    assert 'console.log' not in RECOVERY_EDGE
    assert 'console.error' not in RECOVERY_EDGE
    legacy = MIGRATION.index(
        "reserve_result := content_factory_private.system_reserve_public_recovery_receipt_pre_abuse_quota("
    )
    dispatch_gate = MIGRATION.index("if not coalesce((reserve_result ->> 'dispatch_required')")
    client_bucket = MIGRATION.index("'client',", dispatch_gate)
    global_bucket = MIGRATION.index("'global',", client_bucket)
    assert legacy < dispatch_gate < client_bucket < global_bucket


def test_member_passwords_are_per_slot_single_dispatch_and_never_journaled_raw() -> None:
    assert "member_password_dispatches" in MIGRATION
    assert "password_fingerprint text not null unique" in MIGRATION
    assert "member_password_dispatches force row level security" in MIGRATION
    assert "_keyed_fingerprint" in PROVISION
    assert '"member-temp-password"' in PROVISION
    assert "_reserve_password_dispatch" in PROVISION
    assert "_transition_password_dispatch" in PROVISION
    assert "_resume_password_dispatch" in PROVISION
    assert "identity_applied" in PROVISION
    assert "PASSWORD_DISPATCH_ID_MARKER" in PROVISION
    assert "temporary_password" not in MIGRATION
