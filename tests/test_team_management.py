from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import get_settings
from app.database import Base, get_db
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.routers import team as team_router
from app.team import (
    SupabaseAdminError,
    SupabaseAdminUser,
    SupabaseAuthAdminClient,
    TeamPermissionError,
    TeamService,
    TeamStateError,
    TeamValidationError,
    build_supabase_admin_client,
)


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    with TestSession() as session:
        yield session


def create_organization(db: Session, *, slug: str) -> models.Organization:
    organization = models.Organization(
        name=slug,
        slug=slug,
        status="active",
        settings_json={},
    )
    db.add(organization)
    db.flush()
    return organization


def create_member(
    db: Session,
    organization: models.Organization,
    *,
    identity: str,
    role: str,
    membership_status: str = "active",
    profile_status: str = "active",
) -> tuple[models.UserProfile, models.Membership]:
    profile = models.UserProfile(
        supabase_user_id=f"team:{identity}",
        email=f"{identity}@example.test",
        display_name=identity.replace("-", " ").title(),
        status=profile_status,
        is_active=profile_status == "active",
        metadata_json={},
    )
    db.add(profile)
    db.flush()
    membership = models.Membership(
        organization_id=organization.id,
        user_profile_id=profile.id,
        role=role,
        status=membership_status,
        permissions_json=[],
    )
    db.add(membership)
    db.flush()
    return profile, membership


def create_owner_scope(db: Session, *, slug: str = "team-org"):
    organization = create_organization(db, slug=slug)
    owner, membership = create_member(
        db,
        organization,
        identity=f"{slug}-owner",
        role="owner",
    )
    db.commit()
    return organization, owner, membership


class FakeAdminClient:
    def __init__(
        self,
        *,
        found: SupabaseAdminUser | None = None,
        invited: SupabaseAdminUser | None = None,
    ) -> None:
        self.found = found
        self.invited = invited
        self.find_calls: list[str] = []
        self.invite_calls: list[dict] = []

    def find_user_by_email(self, email: str) -> SupabaseAdminUser | None:
        self.find_calls.append(email)
        return self.found

    def invite_user(
        self,
        *,
        email: str,
        display_name: str | None = None,
        redirect_to: str | None = None,
    ) -> SupabaseAdminUser:
        self.invite_calls.append(
            {
                "email": email,
                "display_name": display_name,
                "redirect_to": redirect_to,
            }
        )
        if self.invited is None:
            raise AssertionError("invite_user was not expected")
        return self.invited


def test_supabase_admin_invite_keeps_secret_in_headers_and_parses_user():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["apikey"] = request.headers.get("apikey")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "supabase-user-42",
                "email": "creator@example.com",
                "user_metadata": {"display_name": "Creator"},
            },
        )

    secret = "server-only-supabase-secret"
    client = SupabaseAuthAdminClient(
        project_url="https://project.supabase.co",
        secret_key=secret,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    user = client.invite_user(
        email="creator@example.com",
        display_name="Creator",
        redirect_to="https://factory.example.com/login",
    )

    assert user.user_id == "supabase-user-42"
    assert user.display_name == "Creator"
    assert seen["method"] == "POST"
    assert seen["url"] == "https://project.supabase.co/auth/v1/invite"
    assert seen["authorization"] == f"Bearer {secret}"
    assert seen["apikey"] == secret
    assert secret not in json.dumps(seen["body"])


def test_supabase_admin_error_does_not_reflect_response_body_or_secret():
    secret = "never-log-this-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            request=request,
            text=f"provider echoed {secret} and creator@example.com",
        )

    client = SupabaseAuthAdminClient(
        project_url="https://project.supabase.co",
        secret_key=secret,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(SupabaseAdminError) as error:
        client.invite_user(email="creator@example.com")

    assert "HTTP 500" in str(error.value)
    assert secret not in str(error.value)
    assert "creator@example.com" not in str(error.value)


def test_missing_admin_configuration_is_a_provider_error():
    with pytest.raises(SupabaseAdminError):
        build_supabase_admin_client(
            settings=SimpleNamespace(supabase_url=None),
            environ={},
        )


def test_owner_invites_new_identity_and_persists_provider_user_id(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    fake = FakeAdminClient(
        invited=SupabaseAdminUser(
            user_id="provider-created-user-id",
            email="new.creator@example.com",
            display_name="Provider Name",
        )
    )
    service = TeamService(db, admin_client_factory=lambda: fake)

    result = service.invite_or_add(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        email=" New.Creator@Example.com ",
        display_name="New Creator",
        role="producer",
        redirect_to="https://factory.example.com/welcome",
    )

    profile = db.get(models.UserProfile, result.user_profile_id)
    membership = db.get(models.Membership, result.membership_id)
    audit = db.scalar(
        select(models.AuditLog).where(models.AuditLog.action == "team_member_invite")
    )
    assert result.invited is True
    assert result.membership_created is True
    assert profile.supabase_user_id == "provider-created-user-id"
    assert profile.email == "new.creator@example.com"
    assert membership.organization_id == organization.id
    assert membership.role == "producer"
    assert membership.status == "active"
    assert fake.find_calls == ["new.creator@example.com"]
    assert fake.invite_calls == [
        {
            "email": "new.creator@example.com",
            "display_name": "New Creator",
            "redirect_to": "https://factory.example.com/welcome",
        }
    ]
    assert audit.status == "allowed"
    assert audit.entity_id == str(membership.id)
    assert audit.metadata_json["invite_method"] == "supabase_invite"
    assert "new.creator@example.com" not in json.dumps(audit.metadata_json)


def test_exact_existing_provider_subject_is_added_to_another_org_without_repeat_invite(
    db: Session,
):
    first_org, existing, _first_membership = create_owner_scope(db, slug="first-org")
    second_org, second_owner, _second_owner_membership = create_owner_scope(db, slug="second-org")
    assert first_org.id != second_org.id
    fake = FakeAdminClient(
        found=SupabaseAdminUser(
            user_id=existing.supabase_user_id,
            email=existing.email,
            display_name=existing.display_name,
        )
    )
    service = TeamService(db, admin_client_factory=lambda: fake)
    result = service.invite_or_add(
        organization_id=second_org.id,
        actor_user_profile_id=second_owner.id,
        email=existing.email,
        role="reviewer",
    )

    assert result.invited is False
    assert result.user_profile_id == existing.id
    assert result.membership_created is True
    assert fake.find_calls == [existing.email]
    assert fake.invite_calls == []
    memberships = list(
        db.scalars(
            select(models.Membership).where(
                models.Membership.user_profile_id == existing.id
            )
        )
    )
    assert {membership.organization_id for membership in memberships} == {
        first_org.id,
        second_org.id,
    }


def test_existing_supabase_identity_is_added_without_invitation(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    fake = FakeAdminClient(
        found=SupabaseAdminUser(
            user_id="existing-provider-id",
            email="known@example.com",
            display_name="Known Creator",
        )
    )
    service = TeamService(db, admin_client_factory=lambda: fake)

    result = service.invite_or_add(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        email="known@example.com",
        role="operator",
    )

    assert result.invited is False
    assert result.membership_created is True
    assert fake.find_calls == ["known@example.com"]
    assert fake.invite_calls == []
    profile = db.get(models.UserProfile, result.user_profile_id)
    assert profile.supabase_user_id == "existing-provider-id"


def test_stale_local_email_for_provider_subject_fails_closed(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    existing = models.UserProfile(
        supabase_user_id="provider-renamed-id",
        email="old-address@example.test",
        display_name="Old Name",
        status="active",
        is_active=True,
        metadata_json={},
    )
    db.add(existing)
    db.commit()
    fake = FakeAdminClient(
        found=SupabaseAdminUser(
            user_id="provider-renamed-id",
            email="current-address@example.com",
            display_name="Provider Name",
        )
    )

    with pytest.raises(TeamStateError):
        TeamService(db, admin_client_factory=lambda: fake).invite_or_add(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            email="current-address@example.com",
            display_name="Current Name",
            role="reviewer",
        )

    db.refresh(existing)
    assert existing.email == "old-address@example.test"
    assert existing.display_name == "Old Name"
    assert fake.find_calls == ["current-address@example.com"]
    assert fake.invite_calls == []
    assert db.scalar(
        select(models.Membership).where(
            models.Membership.organization_id == organization.id,
            models.Membership.user_profile_id == existing.id,
        )
    ) is None


def test_local_profile_without_provider_subject_is_not_reinvited(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    local = models.UserProfile(
        supabase_user_id="local:creator@example.com",
        email="creator@example.com",
        display_name="Local Creator",
        status="active",
        is_active=True,
        metadata_json={},
    )
    db.add(local)
    db.commit()
    fake = FakeAdminClient(
        invited=SupabaseAdminUser(
            user_id="provider-created-duplicate",
            email="creator@example.com",
        )
    )

    with pytest.raises(TeamStateError):
        TeamService(db, admin_client_factory=lambda: fake).invite_or_add(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            email="creator@example.com",
            role="producer",
        )

    assert fake.find_calls == ["creator@example.com"]
    assert fake.invite_calls == []
    assert db.scalar(
        select(models.Membership).where(
            models.Membership.organization_id == organization.id,
            models.Membership.user_profile_id == local.id,
        )
    ) is None


def test_provider_identity_mismatch_fails_closed_and_is_audited(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    fake = FakeAdminClient(
        found=SupabaseAdminUser(
            user_id="wrong-user-id",
            email="different@example.com",
        )
    )

    with pytest.raises(SupabaseAdminError):
        TeamService(db, admin_client_factory=lambda: fake).invite_or_add(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            email="requested@example.com",
            role="operator",
        )

    assert db.scalar(
        select(models.UserProfile).where(
            models.UserProfile.supabase_user_id == "wrong-user-id"
        )
    ) is None
    audit = db.scalar(
        select(models.AuditLog).where(models.AuditLog.action == "team_member_invite")
    )
    assert audit.status == "error"
    assert audit.reason == "supabase_admin_unavailable"


def test_inactive_profile_found_by_provider_id_is_not_reactivated(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    inactive = models.UserProfile(
        supabase_user_id="inactive-provider-id",
        email="inactive-now@example.com",
        display_name="Inactive User",
        status="suspended",
        is_active=False,
        metadata_json={},
    )
    db.add(inactive)
    db.commit()
    fake = FakeAdminClient(
        found=SupabaseAdminUser(
            user_id="inactive-provider-id",
            email="inactive-now@example.com",
        )
    )

    with pytest.raises(TeamStateError):
        TeamService(db, admin_client_factory=lambda: fake).invite_or_add(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            email="inactive-now@example.com",
            role="viewer",
        )

    db.refresh(inactive)
    assert inactive.email == "inactive-now@example.com"
    assert inactive.status == "suspended"
    assert inactive.is_active is False
    assert db.scalar(
        select(models.Membership).where(
            models.Membership.organization_id == organization.id,
            models.Membership.user_profile_id == inactive.id,
        )
    ) is None


def test_role_allowlist_and_admin_authority_are_fail_closed(db: Session):
    organization, _owner, _owner_membership = create_owner_scope(db)
    admin, _admin_membership = create_member(
        db,
        organization,
        identity="workspace-admin",
        role="admin",
    )
    db.commit()
    service = TeamService(db, admin_client_factory=lambda: FakeAdminClient())

    with pytest.raises(TeamValidationError):
        service.invite_or_add(
            organization_id=organization.id,
            actor_user_profile_id=admin.id,
            email="creator@example.com",
            role="superuser",
        )
    with pytest.raises(TeamPermissionError):
        service.invite_or_add(
            organization_id=organization.id,
            actor_user_profile_id=admin.id,
            email="creator@example.com",
            role="admin",
        )


def test_admin_cannot_downgrade_existing_owner_or_admin_by_reinvite(db: Session):
    organization, _owner, _owner_membership = create_owner_scope(db)
    protected_owner, protected_owner_membership = create_member(
        db,
        organization,
        identity="protected-owner",
        role="owner",
    )
    actor, _actor_membership = create_member(
        db,
        organization,
        identity="workspace-admin",
        role="admin",
    )
    protected_admin, protected_admin_membership = create_member(
        db,
        organization,
        identity="protected-admin",
        role="admin",
    )
    db.commit()

    for target, requested_role in (
        (protected_owner, "viewer"),
        (protected_admin, "reviewer"),
    ):
        fake = FakeAdminClient(
            found=SupabaseAdminUser(
                user_id=target.supabase_user_id,
                email=target.email,
            )
        )
        with pytest.raises(TeamPermissionError):
            TeamService(db, admin_client_factory=lambda: fake).invite_or_add(
                organization_id=organization.id,
                actor_user_profile_id=actor.id,
                email=target.email,
                role=requested_role,
            )
        assert fake.find_calls == [target.email]
        assert fake.invite_calls == []

    db.refresh(protected_owner_membership)
    db.refresh(protected_admin_membership)
    assert protected_owner_membership.role == "owner"
    assert protected_admin_membership.role == "admin"


def test_owner_can_change_existing_admin_role_when_policy_allows(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    target, target_membership = create_member(
        db,
        organization,
        identity="role-change-admin",
        role="admin",
    )
    db.commit()
    fake = FakeAdminClient(
        found=SupabaseAdminUser(
            user_id=target.supabase_user_id,
            email=target.email,
        )
    )

    result = TeamService(db, admin_client_factory=lambda: fake).invite_or_add(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        email=target.email,
        role="reviewer",
    )

    db.refresh(target_membership)
    assert result.membership_created is False
    assert result.role == "reviewer"
    assert target_membership.role == "reviewer"
    assert fake.find_calls == [target.email]
    assert fake.invite_calls == []


def test_provider_failure_writes_only_generic_audit_data(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    leaked_secret = "provider-secret-must-not-persist"

    def unavailable_factory():
        raise SupabaseAdminError(f"upstream failure: {leaked_secret}")

    service = TeamService(db, admin_client_factory=unavailable_factory)
    with pytest.raises(SupabaseAdminError):
        service.invite_or_add(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            email="creator@example.com",
            role="producer",
        )

    audit = db.scalar(
        select(models.AuditLog).where(models.AuditLog.action == "team_member_invite")
    )
    assert audit.status == "error"
    assert audit.reason == "supabase_admin_unavailable"
    serialized = json.dumps(audit.metadata_json)
    assert leaked_secret not in serialized
    assert "creator@example.com" not in serialized


def test_suspend_and_reactivate_are_org_scoped_and_audited(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    target, target_membership = create_member(
        db,
        organization,
        identity="video-producer",
        role="producer",
    )
    other_organization = create_organization(db, slug="other-org")
    _other_user, other_membership = create_member(
        db,
        other_organization,
        identity="other-producer",
        role="producer",
    )
    db.commit()
    service = TeamService(db)

    suspended = service.suspend_membership(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        membership_id=target_membership.id,
    )
    assert suspended.status == "suspended"
    assert target.is_active is True
    assert target.status == "active"

    reactivated = service.reactivate_membership(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        membership_id=target_membership.id,
    )
    assert reactivated.status == "active"

    audit_actions = list(
        db.scalars(
            select(models.AuditLog.action).where(
                models.AuditLog.organization_id == organization.id,
                models.AuditLog.entity_id == str(target_membership.id),
            )
        )
    )
    assert audit_actions == ["team_membership_suspend", "team_membership_reactivate"]
    with pytest.raises(TeamStateError):
        service.suspend_membership(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            membership_id=other_membership.id,
        )


def test_revoked_membership_cannot_be_reactivated_by_generic_team_controls(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    target, target_membership = create_member(
        db,
        organization,
        identity="revoked-user",
        role="viewer",
        membership_status="revoked",
    )
    db.commit()
    fake = FakeAdminClient(
        found=SupabaseAdminUser(
            user_id=target.supabase_user_id,
            email=target.email,
        )
    )
    service = TeamService(db, admin_client_factory=lambda: fake)

    with pytest.raises(TeamStateError):
        service.reactivate_membership(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            membership_id=target_membership.id,
        )
    with pytest.raises(TeamStateError):
        service.invite_or_add(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            email=target.email,
            role="viewer",
        )

    db.refresh(target_membership)
    assert target_membership.status == "revoked"


def test_self_and_last_owner_protections(db: Session):
    organization, owner, owner_membership = create_owner_scope(db)
    fake = FakeAdminClient(
        found=SupabaseAdminUser(
            user_id=owner.supabase_user_id,
            email=owner.email,
        )
    )
    service = TeamService(db, admin_client_factory=lambda: fake)

    with pytest.raises(TeamStateError):
        service.suspend_membership(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            membership_id=owner_membership.id,
        )
    with pytest.raises(TeamStateError):
        service.invite_or_add(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            email=owner.email,
            role="viewer",
        )
    db.refresh(owner_membership)
    assert owner_membership.role == "owner"
    assert owner_membership.status == "active"


def test_roster_supports_more_than_fifty_creators(db: Session):
    organization, owner, _owner_membership = create_owner_scope(db)
    for index in range(55):
        create_member(
            db,
            organization,
            identity=f"creator-{index:02d}",
            role="producer" if index % 2 else "operator",
        )
    db.commit()

    roster = TeamService(db).roster(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
    )

    assert len(roster) == 56
    assert {member.email for member in roster if member.role != "owner"} == {
        f"creator-{index:02d}@example.test" for index in range(55)
    }


@pytest.fixture
def team_http_app(monkeypatch):
    previous_auth_required = get_settings().auth_required
    monkeypatch.setenv("QVF_AUTH_REQUIRED", "true")
    get_settings.cache_clear()

    with TestSession() as db:
        organization, owner, owner_membership = create_owner_scope(db, slug="http-team")
        _target, target_membership = create_member(
            db,
            organization,
            identity="http-target",
            role="producer",
        )
        db.commit()
        user = PublicPilotUser(
            profile=owner,
            organization=organization,
            membership=owner_membership,
        )
        target_membership_id = target_membership.id

    def local_db():
        with TestSession() as db:
            yield db

    api = FastAPI()
    api.mount("/static", StaticFiles(directory="app/static"), name="static")
    api.include_router(team_router.router)
    api.dependency_overrides[get_db] = local_db
    api.dependency_overrides[get_current_public_user] = lambda: user
    client = TestClient(api, follow_redirects=False)
    yield client, target_membership_id
    client.close()
    if previous_auth_required:
        monkeypatch.setenv("QVF_AUTH_REQUIRED", "true")
    else:
        monkeypatch.setenv("QVF_AUTH_REQUIRED", "false")
    get_settings.cache_clear()


def test_team_write_requires_session_bound_csrf(team_http_app):
    client, membership_id = team_http_app

    response = client.post(
        f"/team/memberships/{membership_id}/suspend",
        data={"confirm_action": "true"},
    )

    assert response.status_code == 403
    with TestSession() as db:
        assert db.get(models.Membership, membership_id).status == "active"


def test_team_suspend_with_valid_csrf_and_confirmation(team_http_app):
    client, membership_id = team_http_app
    session_token = "signed-browser-session"
    csrf = hmac.new(
        b"qvf-public-pilot-form-csrf-v1",
        session_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    client.cookies.set(get_settings().session_cookie_name, session_token)

    page = client.get("/team")
    response = client.post(
        f"/team/memberships/{membership_id}/suspend",
        data={"confirm_action": "true", "csrf_token": csrf},
    )

    assert page.status_code == 200
    assert "Команда креаторов" in page.text
    assert response.status_code == 303
    assert response.headers["location"] == "/team?notice=suspended"
    with TestSession() as db:
        assert db.get(models.Membership, membership_id).status == "suspended"
