"""Витрина согласования (ступень 1): контракт схемы и RPC.

Пины: таблицы под FORCE RLS без грантов (доступ только через RPC), токен
генерируется в БД и показывается один раз (в строке — только sha256),
replay по idempotency_key не возвращает токен, анти-энумерация (единый
not_found), идемпотентность решений по client_request_id, append-only
решения, комментарий проходит sensitive-фильтр, уведомление команде.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (
    ROOT / "supabase/migrations/202609030008_client_review_showcase_v1.sql"
).read_text(encoding="utf-8")
LINK_RPCS = (
    ROOT / "supabase/migrations/202609030009_client_review_link_rpcs_v1.sql"
).read_text(encoding="utf-8")
PUBLIC_RPCS = (
    ROOT / "supabase/migrations/202609030010_client_review_public_rpcs_v1.sql"
).read_text(encoding="utf-8")


def test_schema_is_server_only_and_append_only() -> None:
    assert "force row level security" in SCHEMA
    assert "from public, anon, authenticated, service_role" in SCHEMA
    assert "token_hash ~ '^[0-9a-f]{64}$'" in SCHEMA
    assert "client_review_decision_append_only" in SCHEMA
    # Журнал доступа без FK — живёт и для несуществующих токенов.
    assert "НИКАКИХ FK" in SCHEMA
    # Поля контракта ступени 2 заведены сразу.
    assert "intake_enabled" in SCHEMA
    assert "intake_owner_profile_id" in SCHEMA
    assert "check (decision <> 'returned' or comment is not null)" in SCHEMA


def test_issue_link_token_lifecycle() -> None:
    # Токен: 256 бит из БД, наружу один раз; в строку — только sha256.
    assert "gen_random_bytes(32)" in LINK_RPCS
    assert "'crv1_'" in LINK_RPCS
    assert "digest(token_value, 'sha256')" in LINK_RPCS
    # Replay без токена: восстановить нельзя, только отозвать и выдать.
    replay_block = LINK_RPCS.split("'replayed', true", 1)[1].split(
        "end if;", 1
    )[0]
    assert "token" not in replay_block
    # QA-гейт: approved ИЛИ явная кураторская аттестация.
    assert "client_review_media_not_accepted" in LINK_RPCS
    assert "curator_attested" in LINK_RPCS
    # Роли канона и запрет anon.
    assert "array['owner', 'admin', 'producer', 'operator']" in LINK_RPCS
    assert "client_review_anon_leak_" in LINK_RPCS


def test_public_rpcs_are_anti_enumeration() -> None:
    # Единый ответ на несуществующую/отозванную/истёкшую ссылку.
    assert PUBLIC_RPCS.count("'client_review_not_found'") >= 3
    # Rate-limit по журналу отвечает ДО раскрытия судьбы токена.
    assert "client_review_rate_limited" in PUBLIC_RPCS
    assert "retry_after_seconds" in PUBLIC_RPCS
    # Идемпотентность решения и отсутствие дублей уведомлений.
    assert "client_request_id" in PUBLIC_RPCS
    assert "'replayed', true" in PUBLIC_RPCS
    # Комментарий клиента проходит sensitive-фильтр v491.
    assert "notification_payload_sensitive_v491" in PUBLIC_RPCS
    # Уведомление команде с дедупом.
    assert "'client_review_decision'" in PUBLIC_RPCS
    assert "on conflict (organization_id, recipient_id, dedupe_key)" in (
        PUBLIC_RPCS
    )
    # Системные RPC — только service_role.
    assert "grant execute on function public.system_client_review_view(jsonb)" in PUBLIC_RPCS
    assert "to service_role" in PUBLIC_RPCS
    # Верификация поведением на фейковом токене.
    assert "client_review_view_enumeration_leak" in PUBLIC_RPCS
