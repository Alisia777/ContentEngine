"""Гигиена безопасности перед клиентскими ссылками (мастер-план, sec-поток).

Пины: забор portal_* по членству (202609030006) недеструктивен — сид всеми
живыми учётками, anon-политики снапшотов сохранены до пересадки писателя;
гигиена public (202609030007) — default privileges, duet-RPC от anon,
search_path; контракт явных грантов для витрины/ввода зафиксирован доком.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FENCE = (
    ROOT / "supabase/migrations/202609030006_portal_contour_membership_fence_v1.sql"
).read_text(encoding="utf-8")
HYGIENE = (
    ROOT / "supabase/migrations/202609030007_public_default_privileges_hygiene_v1.sql"
).read_text(encoding="utf-8")
CONTRACT = (
    ROOT / "docs/CLIENT_REVIEW_TOKEN_CONTRACT_V1.md"
).read_text(encoding="utf-8")


def test_portal_fence_is_non_destructive() -> None:
    # Сид всеми живыми учётками — команда портала не отрезается.
    assert "not u.is_anonymous" in FENCE
    assert "on conflict (user_id) do nothing" in FENCE
    # Anon-политики снапшотов/вложений сохраняются до пересадки писателя.
    assert "portal_anon_policies_removed_too_early" in FENCE
    # Дизайн-контур с точечными политиками не задет.
    assert "portal_design_policies_damaged" in FENCE
    # Забор — членство, а не удаление данных.
    assert "portal_members" in FENCE
    assert "drop table" not in FENCE.lower()
    assert "delete from public.portal_" not in FENCE.lower()


def test_public_hygiene_covers_grants_and_search_path() -> None:
    for stmt in (
        "alter default privileges for role postgres in schema public",
        "alter default privileges for role postgres in schema storage",
        "revoke execute on function public.creator_register_duet_presenter",
        # rls_auto_enable нёс грант через PUBLIC — revoke обязан включать его.
        "from public, anon, authenticated",
        "alter function public.set_updated_at() set search_path = ''",
        "anon_function_grants_remain",
        "duet_rpc_authenticated_lost",
    ):
        assert stmt in HYGIENE, stmt
    # Машин view намеренно не тронут до ответов команды (см. досье).
    assert "view_portal_masha_status_current" not in HYGIENE.split(
        "-- ПРОВЕРКА ПОВЕДЕНИЕМ."
    )[1]


def test_token_contract_pins_stage2_rules() -> None:
    for rule in (
        "intake_enabled",
        "intake_owner_profile_id",
        "token_hash",
        "подписанным upload-URL",
        "rights_confirmed",
        "brief_",
        "явные гранты",
    ):
        assert rule in CONTRACT, rule
