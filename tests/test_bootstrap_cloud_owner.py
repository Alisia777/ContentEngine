from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.public_pilot.auth import active_public_pilot_user_from_payload
from app.team import SupabaseAdminError, SupabaseAdminUser
from scripts.bootstrap_cloud_owner import (
    CloudOwnerBootstrapError,
    bootstrap_cloud_owner,
    main,
)


ROOT = Path(__file__).resolve().parents[1]
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


def current_migration_head() -> str:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1
    return heads[0]


def stamp_database(revision: str | None = None) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": revision or current_migration_head()},
        )


@pytest.fixture(autouse=True)
def migrated_database():
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    stamp_database()
    yield
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    Base.metadata.drop_all(bind=engine)


class FakeAdminClient:
    def __init__(self, users: list[SupabaseAdminUser] | None = None) -> None:
        self.users = {user.email.casefold(): user for user in users or []}
        self.find_calls: list[str] = []
        self.invite_calls: list[dict] = []

    def find_user_by_email(self, email: str) -> SupabaseAdminUser | None:
        self.find_calls.append(email)
        return self.users.get(email.casefold())

    def invite_user(
        self,
        *,
        email: str,
        display_name: str | None = None,
        redirect_to: str | None = None,
    ) -> SupabaseAdminUser:
        user = SupabaseAdminUser(
            user_id="supabase-first-owner-id",
            email=email,
            display_name=display_name,
        )
        self.users[email.casefold()] = user
        self.invite_calls.append(
            {
                "email": email,
                "display_name": display_name,
                "redirect_to": redirect_to,
            }
        )
        return user


BOOTSTRAP_ARGS = {
    "email": "First.Owner@Example.com",
    "display_name": "First Owner",
    "organization_name": "Content Factory",
    "organization_slug": "content-factory",
}


def run_bootstrap(db: Session, fake: FakeAdminClient, **overrides):
    arguments = {**BOOTSTRAP_ARGS, **overrides}
    return bootstrap_cloud_owner(
        db,
        **arguments,
        admin_client_factory=lambda: fake,
        require_postgresql=False,
    )


def test_fresh_bootstrap_invites_once_and_repeat_is_idempotent():
    fake = FakeAdminClient()
    with TestSession() as db:
        first = run_bootstrap(db, fake)
        db.commit()
        second = run_bootstrap(db, fake)
        db.commit()

        assert first.status == "created"
        assert first.identity_status == "invited"
        assert second.status == "unchanged"
        assert second.identity_status == "existing"
        assert second.organization_id == first.organization_id
        assert second.user_profile_id == first.user_profile_id
        assert second.membership_id == first.membership_id
        assert db.scalar(select(func.count()).select_from(models.Organization)) == 1
        assert db.scalar(select(func.count()).select_from(models.UserProfile)) == 1
        assert db.scalar(select(func.count()).select_from(models.Membership)) == 1

        profile = db.get(models.UserProfile, first.user_profile_id)
        membership = db.get(models.Membership, first.membership_id)
        assert profile.supabase_user_id == "supabase-first-owner-id"
        assert profile.email == "first.owner@example.com"
        assert profile.display_name == "First Owner"
        assert membership.role == "owner"
        assert membership.status == "active"

    assert fake.find_calls == ["first.owner@example.com", "first.owner@example.com"]
    assert fake.invite_calls == [
        {
            "email": "first.owner@example.com",
            "display_name": "First Owner",
            "redirect_to": None,
        }
    ]


def test_existing_supabase_identity_is_not_invited_again():
    fake = FakeAdminClient(
        [
            SupabaseAdminUser(
                user_id="already-in-supabase",
                email="first.owner@example.com",
                display_name="Existing Identity",
            )
        ]
    )
    with TestSession() as db:
        result = run_bootstrap(db, fake)
        db.commit()

        assert result.status == "created"
        assert result.identity_status == "existing"
        assert db.get(models.UserProfile, result.user_profile_id).supabase_user_id == (
            "already-in-supabase"
        )
    assert fake.invite_calls == []


def test_bootstrapped_non_default_owner_resolves_from_sole_db_membership():
    fake = FakeAdminClient()
    with TestSession() as db:
        result = run_bootstrap(db, fake)
        db.commit()

        user = active_public_pilot_user_from_payload(
            db,
            {
                "sub": "supabase-first-owner-id",
                "email": "first.owner@example.com",
                "app_metadata": {},
            },
        )

        assert user.profile.id == result.user_profile_id
        assert user.organization.id == result.organization_id
        assert user.organization.slug == "content-factory"
        assert user.membership.id == result.membership_id
        assert user.role == "owner"


def test_exact_partial_organization_is_completed_without_inviting_again():
    fake = FakeAdminClient(
        [
            SupabaseAdminUser(
                user_id="existing-partial-owner",
                email="first.owner@example.com",
            )
        ]
    )
    with TestSession() as db:
        organization = models.Organization(
            name="Content Factory",
            slug="content-factory",
            status="active",
            settings_json={},
        )
        db.add(organization)
        db.commit()

        result = run_bootstrap(db, fake)
        db.commit()

        assert result.status == "completed"
        assert result.identity_status == "existing"
        assert result.organization_id == organization.id
        assert db.scalar(select(func.count()).select_from(models.Organization)) == 1
        assert db.scalar(select(func.count()).select_from(models.UserProfile)) == 1
        assert db.scalar(select(func.count()).select_from(models.Membership)) == 1
    assert fake.invite_calls == []


def test_exact_rerun_remains_idempotent_after_second_creator_is_added():
    fake = FakeAdminClient()
    with TestSession() as db:
        first = run_bootstrap(db, fake)
        db.commit()
        second_profile = models.UserProfile(
            supabase_user_id="second-creator-id",
            email="second.creator@example.com",
            display_name="Second Creator",
            status="active",
            is_active=True,
            metadata_json={},
        )
        db.add(second_profile)
        db.flush()
        db.add(
            models.Membership(
                organization_id=first.organization_id,
                user_profile_id=second_profile.id,
                role="producer",
                status="active",
                permissions_json=[],
            )
        )
        db.commit()

        repeated = run_bootstrap(db, fake)
        db.commit()

        assert repeated.status == "unchanged"
        assert repeated.organization_id == first.organization_id
        assert repeated.user_profile_id == first.user_profile_id
        assert repeated.membership_id == first.membership_id
        assert db.scalar(select(func.count()).select_from(models.Organization)) == 1
        assert db.scalar(select(func.count()).select_from(models.UserProfile)) == 2
        assert db.scalar(select(func.count()).select_from(models.Membership)) == 2
    assert len(fake.invite_calls) == 1


def test_bootstrap_refuses_unmigrated_or_stale_schema_before_provider_call():
    fake = FakeAdminClient()
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'stale-revision'"))

    with TestSession() as db, pytest.raises(CloudOwnerBootstrapError) as error:
        run_bootstrap(db, fake)

    assert error.value.code == "alembic_head_required"
    assert fake.find_calls == []
    assert fake.invite_calls == []


def test_cloud_bootstrap_requires_postgresql_by_default():
    fake = FakeAdminClient()
    with TestSession() as db, pytest.raises(CloudOwnerBootstrapError) as error:
        bootstrap_cloud_owner(
            db,
            **BOOTSTRAP_ARGS,
            admin_client_factory=lambda: fake,
        )

    assert error.value.code == "postgresql_required"
    assert fake.find_calls == []


def test_unrelated_organization_fails_before_provider_or_writes():
    fake = FakeAdminClient()
    with TestSession() as db:
        db.add(
            models.Organization(
                name="Another Workspace",
                slug="another-workspace",
                status="active",
                settings_json={},
            )
        )
        db.commit()

        with pytest.raises(CloudOwnerBootstrapError) as error:
            run_bootstrap(db, fake)

        assert error.value.code == "organization_conflict"
        assert db.scalar(select(func.count()).select_from(models.Organization)) == 1
        assert db.scalar(select(func.count()).select_from(models.UserProfile)) == 0
        assert db.scalar(select(func.count()).select_from(models.Membership)) == 0
    assert fake.find_calls == []


def test_existing_email_with_different_supabase_id_fails_closed():
    fake = FakeAdminClient(
        [
            SupabaseAdminUser(
                user_id="provider-owner-id",
                email="first.owner@example.com",
            )
        ]
    )
    with TestSession() as db:
        profile = models.UserProfile(
            supabase_user_id="different-local-id",
            email="first.owner@example.com",
            display_name="First Owner",
            status="active",
            is_active=True,
            metadata_json={},
        )
        db.add(profile)
        db.commit()

        with pytest.raises(CloudOwnerBootstrapError) as error:
            run_bootstrap(db, fake)
        db.rollback()

        assert error.value.code == "identity_conflict"
        assert db.scalar(select(func.count()).select_from(models.Organization)) == 0
        assert db.scalar(select(func.count()).select_from(models.Membership)) == 0


def test_local_identity_missing_from_provider_is_not_reinvited():
    fake = FakeAdminClient()
    with TestSession() as db:
        organization = models.Organization(
            name="Content Factory",
            slug="content-factory",
            status="active",
            settings_json={},
        )
        profile = models.UserProfile(
            supabase_user_id="claimed-provider-id",
            email="first.owner@example.com",
            display_name="First Owner",
            status="active",
            is_active=True,
            metadata_json={},
        )
        db.add_all([organization, profile])
        db.commit()

        with pytest.raises(CloudOwnerBootstrapError) as error:
            run_bootstrap(db, fake)

        assert error.value.code == "provider_identity_conflict"
        assert db.scalar(select(func.count()).select_from(models.Membership)) == 0
    assert fake.find_calls == ["first.owner@example.com"]
    assert fake.invite_calls == []


def test_target_profile_with_membership_in_another_org_fails_before_provider():
    fake = FakeAdminClient()
    with TestSession() as db:
        other_organization = models.Organization(
            name="Other Organization",
            slug="other-organization",
            status="active",
            settings_json={},
        )
        profile = models.UserProfile(
            supabase_user_id="foreign-member-id",
            email="first.owner@example.com",
            display_name="First Owner",
            status="active",
            is_active=True,
            metadata_json={},
        )
        db.add_all([other_organization, profile])
        db.flush()
        db.add(
            models.Membership(
                organization_id=other_organization.id,
                user_profile_id=profile.id,
                role="viewer",
                status="active",
                permissions_json=[],
            )
        )
        db.commit()

        with pytest.raises(CloudOwnerBootstrapError) as error:
            run_bootstrap(db, fake)

        assert error.value.code == "membership_conflict"
    assert fake.find_calls == []
    assert fake.invite_calls == []


def test_non_owner_membership_is_never_silently_promoted():
    fake = FakeAdminClient(
        [
            SupabaseAdminUser(
                user_id="existing-local-id",
                email="first.owner@example.com",
            )
        ]
    )
    with TestSession() as db:
        organization = models.Organization(
            name="Content Factory",
            slug="content-factory",
            status="active",
            settings_json={},
        )
        profile = models.UserProfile(
            supabase_user_id="existing-local-id",
            email="first.owner@example.com",
            display_name="First Owner",
            status="active",
            is_active=True,
            metadata_json={},
        )
        db.add_all([organization, profile])
        db.flush()
        membership = models.Membership(
            organization_id=organization.id,
            user_profile_id=profile.id,
            role="viewer",
            status="active",
            permissions_json=[],
        )
        db.add(membership)
        db.commit()

        with pytest.raises(CloudOwnerBootstrapError) as error:
            run_bootstrap(db, fake)

        assert error.value.code == "membership_conflict"
        db.refresh(membership)
        assert membership.role == "viewer"
    assert fake.find_calls == []


def test_cli_output_contains_only_safe_status_and_ids(capsys):
    secret_marker = "server-secret-must-never-print"
    fake = FakeAdminClient()
    fake._secret_marker = secret_marker
    exit_code = main(
        [
            "--email",
            "private.owner@example.com",
            "--display-name",
            "Private Owner Name",
            "--organization-name",
            "Private Organization Name",
            "--organization-slug",
            "private-organization-slug",
        ],
        session_factory=TestSession,
        admin_client_factory=lambda: fake,
        require_postgresql=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "status=created" in captured.out
    assert "identity_status=invited" in captured.out
    assert "organization_id=" in captured.out
    assert "user_profile_id=" in captured.out
    assert "membership_id=" in captured.out
    assert "private.owner@example.com" not in captured.out
    assert "Private Owner Name" not in captured.out
    assert "Private Organization Name" not in captured.out
    assert "private-organization-slug" not in captured.out
    assert secret_marker not in captured.out


def test_cli_hides_provider_exception_text_and_identity(capsys):
    secret_marker = "provider-leaked-secret"

    def failing_factory():
        raise SupabaseAdminError(f"upstream echoed {secret_marker}")

    exit_code = main(
        [
            "--email",
            "private.failure@example.com",
            "--display-name",
            "Private Failure",
            "--organization-name",
            "Private Organization",
            "--organization-slug",
            "private-organization",
        ],
        session_factory=TestSession,
        admin_client_factory=failing_factory,
        require_postgresql=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "status=failed" in captured.err
    assert "code=identity_provider_unavailable" in captured.err
    assert secret_marker not in captured.err
    assert "private.failure@example.com" not in captured.err


def test_script_never_bootstraps_schema_or_accepts_secret_arguments():
    source = (ROOT / "scripts" / "bootstrap_cloud_owner.py").read_text(encoding="utf-8")
    assert "create_all" not in source
    assert "init_db" not in source
    assert 'add_argument("--secret' not in source
    assert 'add_argument("--token' not in source


def test_cloud_runbook_requires_server_side_invite_confirmation_template():
    runbook = (ROOT / "docs" / "CLOUD_DEPLOYMENT.md").read_text(encoding="utf-8")
    assert (
        "<PUBLIC_APP_URL>/auth/accept#token_hash={{ .TokenHash }}&type=invite"
        in runbook
    )
    assert "default fragment redirect is insufficient" in runbook
    assert "python scripts/bootstrap_cloud_owner.py" in runbook
    assert "Exactly one active membership" in runbook
    assert "never falls back" in runbook
