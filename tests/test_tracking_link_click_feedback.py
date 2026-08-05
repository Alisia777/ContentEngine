from pathlib import Path

import yaml
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase/migrations/202607250005_tracking_link_click_feedback.sql"
)
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/tracking_link_click_feedback_test.sql"
).read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-click/index.ts"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
CONFIG = (ROOT / "supabase/config.toml").read_text(encoding="utf-8")
CI_PATH = ROOT / ".github/workflows/ci.yml"
DEPLOY_PATH = ROOT / ".github/workflows/supabase-pages.yml"
CI = CI_PATH.read_text(encoding="utf-8")
DEPLOY = DEPLOY_PATH.read_text(encoding="utf-8")


def test_tracking_sql_and_pgtap_are_parseable() -> None:
    assert len(parse_sql(MIGRATION)) >= 20
    assert len(parse_sql(PGTAP)) >= 35


def test_tracking_capability_is_random_immutable_and_org_scoped() -> None:
    for token in (
        "placements_tracking_slug_uq",
        "'ce1_' || encode(extensions.gen_random_bytes(12), 'hex')",
        "tracking_link_target_immutable",
        "placement.organization_id = organization_id",
        "placement_row.assigned_to <> user_id",
        "actor_role <> all(array['owner', 'admin', 'producer', 'reviewer'])",
        "placement_row.status not in ('scheduled', 'ready', 'published')",
        "creator_configure_tracking_link",
        "begin_command(",
        "finish_command(",
    ):
        assert token in MIGRATION


def test_public_click_receipt_is_bounded_private_and_bot_aware() -> None:
    for token in (
        "interval '10 seconds'",
        "interval '1 minute'",
        "recent_count >= 120",
        "'social_preview'",
        "'crawler'",
        "'automation'",
        "accepted_for_human_kpi",
        "visitor_fingerprint",
        "user_agent_hash",
        "referrer_origin",
        "extensions.digest(",
        "grant execute on function public.system_record_public_tracking_click(jsonb)",
        "to service_role",
    ):
        assert token in MIGRATION
    for forbidden in (
        "ip_address",
        "x-forwarded-for",
        "cf-connecting-ip",
        "raw_user_agent",
        "raw_referrer",
    ):
        assert forbidden not in MIGRATION.lower()
    assert "from public, anon, authenticated" in MIGRATION


def test_workspace_uses_live_human_clicks_without_claiming_platform_views() -> None:
    for token in (
        "'tracked_clicks'",
        "greatest(",
        "'tracking_link'",
        "'mixed'",
        "'ctr'",
        "click.accepted_for_human_kpi",
        "creator_workspace_section_tracking_v1",
    ):
        assert token in MIGRATION
    assert "views" not in EDGE
    assert "orders" not in EDGE


def test_edge_redirect_has_no_secret_or_raw_identifier_telemetry() -> None:
    for token in (
        'auth: "none"',
        '"system_record_public_tracking_click"',
        "context.supabaseAdmin.rpc(",
        "status: 307",
        '"location"',
        '"set-cookie"',
        "HttpOnly; SameSite=Lax",
        '"referrer-policy": "no-referrer"',
        '"x-robots-tag": "noindex, nofollow, noarchive"',
    ):
        assert token in EDGE
    for forbidden in (
        "SUPABASE_SERVICE_ROLE_KEY",
        "x-forwarded-for",
        "cf-connecting-ip",
        "x-real-ip",
        "localStorage",
    ):
        assert forbidden not in EDGE


def test_portal_creates_copies_and_autofills_tracking_clicks() -> None:
    for token in (
        "configureTrackingLink",
        "creator_configure_tracking_link",
        "tracking-link-form",
        "copy-tracking-link",
        "trackingRedirectUrl",
        "syncManualMetricClicks",
        "data-tracked-clicks",
        "Переходы портал подставит сам",
        "боты и быстрые повторы не входят",
        "tracking_link: \"Ссылка\"",
        "mixed: \"Ссылка + снимок\"",
    ):
        assert token in APP or token in API
    assert "./supabase-api.js?v=20260805.os4.22" in APP
    assert "./app.js?v=20260805.os4.22" in INDEX


def test_public_redirect_is_linted_checked_and_deployed() -> None:
    yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))
    yaml.safe_load(DEPLOY_PATH.read_text(encoding="utf-8"))
    assert "[functions.creator-click]" in CONFIG
    assert "verify_jwt = false" in CONFIG.split(
        "[functions.creator-click]", 1
    )[1].split("[", 1)[0]
    for token in (
        '"creator-click"',
        "deno fmt --check supabase/functions/creator-click",
        "deno lint supabase/functions/creator-click/index.ts",
        "deno check supabase/functions/creator-click/index.ts",
        'SUPABASE_TELEMETRY_DISABLED: "1"',
    ):
        assert token in CI
    assert "supabase functions deploy creator-click" in DEPLOY
    assert "--no-verify-jwt" in DEPLOY
    assert 'SUPABASE_TELEMETRY_DISABLED: "1"' in DEPLOY


def test_database_contract_covers_real_redirect_feedback() -> None:
    for token in (
        "select plan(17)",
        "'recorded'",
        "'duplicate'",
        "'false'",
        "'tracking-v1'",
        "'0.50'",
        "training_access_waivers",
        "tracking_link_target_immutable",
        "has_function_privilege(",
    ):
        assert token in PGTAP
