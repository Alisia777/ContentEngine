from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607240004_generation_archive_read_reliability.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")


def test_archive_volatility_repair_is_transactional_and_explicit() -> None:
    assert MIGRATION.exists()
    assert SQL.lstrip().casefold().startswith("begin;")
    assert SQL.rstrip().casefold().endswith("commit;")
    assert "alter function public.creator_generation_archive(jsonb) volatile" in LOWER
    assert "procedure.provolatile" in LOWER
    assert "archive_volatility is distinct from 'v'" in LOWER


def test_browser_lets_the_server_timestamp_product_telemetry() -> None:
    track = APP[
        APP.index("async function track(") :
        APP.index("function validateConfig", APP.index("async function track("))
    ]

    assert "state.api.captureEvent({" in track
    assert "Promise.resolve(capture).catch(() => {});" in track
    assert "await state.api.captureEvent({" not in track
    assert "event_name: eventName" in track
    assert "route: state.route.path" in track
    assert "occurred_at:" not in track
