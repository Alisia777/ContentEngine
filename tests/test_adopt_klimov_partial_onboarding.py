from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace

import pytest

import scripts.adopt_klimov_partial_onboarding as adoption
from scripts.provision_supabase_member import (
    MEMBER_PROVISION_MARKER,
    PASSWORD_CHANGE_REQUIRED_MARKER,
    ProvisioningAuthority,
)


ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"
USER_ID = "33333333-3333-4333-8333-333333333333"
MEMBERSHIP_ID = "44444444-4444-4444-8444-444444444444"
EVENT_ID = "55555555-5555-4555-8555-555555555555"
RECEIPT_ID = "66666666-6666-4666-8666-666666666666"
WAIVER_ID = "77777777-7777-4777-8777-777777777777"
EMAIL = "employee@example.com"
OWNER_EMAIL = "owner@example.com"
DISPLAY_NAME = "Viktor"
PUBLISHABLE_KEY = "sb_publishable_browser_safe_test_key"
SERVER_KEY = "sb_secret_service_role_secret_must_not_leak"
AUTHORITY = ProvisioningAuthority(ORGANIZATION_ID, OWNER_ID)


def _snapshot(**changes: object) -> adoption.PartialAdoptionSnapshot:
    snapshot = adoption.PartialAdoptionSnapshot(
        auth_match_count=1,
        user_id=USER_ID,
        auth_email=EMAIL,
        auth_created_at="2026-08-11 19:12:29.123+00",
        auth_created_in_source_window=True,
        email_confirmed=False,
        auth_active=True,
        signed_in=False,
        no_encrypted_password=True,
        app_metadata={
            "provider": "email",
            "providers": ["email"],
            MEMBER_PROVISION_MARKER: True,
            PASSWORD_CHANGE_REQUIRED_MARKER: True,
        },
        raw_user_meta_data={"display_name": DISPLAY_NAME},
        auth_display_name=DISPLAY_NAME,
        auth_provider="email",
        auth_providers=("email",),
        profile_id=USER_ID,
        profile_email=EMAIL,
        profile_display_name=DISPLAY_NAME,
        profile_status="active",
        organization_id=ORGANIZATION_ID,
        organization_slug="altea-content-factory",
        organization_status="active",
        authority_id=OWNER_ID,
        authority_email=OWNER_EMAIL,
        authority_auth_email=OWNER_EMAIL,
        authority_is_active_owner=True,
        membership_id=MEMBERSHIP_ID,
        membership_organization_id=ORGANIZATION_ID,
        membership_profile_id=USER_ID,
        membership_role="trainee",
        membership_status="active",
        membership_permissions=(),
        membership_created_at="2026-08-11 19:20:00+00",
        membership_updated_at="2026-08-11 19:20:00+00",
        membership_count=1,
        waiver_count=0,
        waiver_id="",
        waiver_organization_id="",
        waiver_profile_id="",
        waiver_status="",
        waiver_scope="",
        waiver_previous_role="",
        waiver_granted_role="",
        waiver_grant_reason="",
        waiver_granted_by="",
        training_attempt_count=0,
        training_certification_count=0,
        project_membership_count=0,
        provenance_events=(),
        provenance_receipts=(),
    )
    return replace(snapshot, **changes)


AUDIT_CONTEXT = adoption.GitHubAuditContext(
    repository=adoption.EXPECTED_REPOSITORY,
    run_id="31599999999",
    run_attempt="1",
    actor="reviewed-operator",
    sha="a" * 40,
)


def _reason(
    classification: str = adoption.CLASS_NO_PROVENANCE,
) -> str:
    return adoption._adoption_reason(classification, AUDIT_CONTEXT)


def _confirmed_trainee(
    **changes: object,
) -> adoption.PartialAdoptionSnapshot:
    snapshot = _snapshot(
        email_confirmed=True,
        raw_user_meta_data={
            "display_name": DISPLAY_NAME,
            "email_verified": True,
        },
    )
    return replace(snapshot, **changes)


def _missing_name(
    **changes: object,
) -> adoption.PartialAdoptionSnapshot:
    snapshot = _snapshot(
        raw_user_meta_data={},
        auth_display_name="",
        profile_display_name="",
    )
    return replace(snapshot, **changes)


def _confirmed_missing_name(
    **changes: object,
) -> adoption.PartialAdoptionSnapshot:
    snapshot = _missing_name(
        email_confirmed=True,
        raw_user_meta_data={"email_verified": True},
    )
    return replace(snapshot, **changes)


def _retry_profile_sync(
    *,
    email_confirmed: bool = False,
    **changes: object,
) -> adoption.PartialAdoptionSnapshot:
    snapshot = _snapshot(
        email_confirmed=email_confirmed,
        raw_user_meta_data={
            "display_name": DISPLAY_NAME,
            **({"email_verified": True} if email_confirmed else {}),
        },
        profile_display_name="",
    )
    return replace(snapshot, **changes)


def _operator(
    *,
    reason: str | None = None,
    **changes: object,
) -> adoption.PartialAdoptionSnapshot:
    return _snapshot(
        email_confirmed=True,
        raw_user_meta_data={
            "display_name": DISPLAY_NAME,
            "email_verified": True,
        },
        membership_role="operator",
        membership_updated_at="2026-08-11 20:00:00+00",
        waiver_count=1,
        waiver_id=WAIVER_ID,
        waiver_organization_id=ORGANIZATION_ID,
        waiver_profile_id=USER_ID,
        waiver_status="active",
        waiver_scope="workspace_generation",
        waiver_previous_role="trainee",
        waiver_granted_role="operator",
        waiver_grant_reason=reason or _reason(),
        waiver_granted_by=OWNER_ID,
        **changes,
    )


def _limited_provenance() -> tuple[
    tuple[adoption.ProvenanceEvent, ...],
    tuple[adoption.ProvenanceReceipt, ...],
]:
    key = "github-member:test-provenance"
    return (
        (
            adoption.ProvenanceEvent(
                event_id=EVENT_ID,
                organization_id=ORGANIZATION_ID,
                profile_id=OWNER_ID,
                event_name="limited_member_provisioned",
                source="system",
                entity_type="membership",
                entity_id=MEMBERSHIP_ID,
                properties={
                    "target_user_id": USER_ID,
                    "role": "trainee",
                    "already_active": False,
                },
                idempotency_key=key,
                occurred_at="2026-08-11 19:20:00+00",
            ),
        ),
        (
            adoption.ProvenanceReceipt(
                receipt_id=RECEIPT_ID,
                organization_id=ORGANIZATION_ID,
                actor_id=OWNER_ID,
                command_name="system_provision_limited_member",
                idempotency_key=key,
                result={
                    "ok": True,
                    "organization_id": ORGANIZATION_ID,
                    "user_id": USER_ID,
                    "membership_id": MEMBERSHIP_ID,
                    "role": "trainee",
                    "status": "active",
                    "already_active": False,
                },
                created_at="2026-08-11 19:20:00+00",
            ),
        ),
    )


def _invited_provenance() -> tuple[
    tuple[adoption.ProvenanceEvent, ...],
    tuple[adoption.ProvenanceReceipt, ...],
]:
    key = "invite:test-provenance"
    return (
        (
            adoption.ProvenanceEvent(
                event_id=EVENT_ID,
                organization_id=ORGANIZATION_ID,
                profile_id=OWNER_ID,
                event_name="member_invited_provisioned",
                source="system",
                entity_type="membership",
                entity_id=MEMBERSHIP_ID,
                properties={"target_user_id": USER_ID, "role": "trainee"},
                idempotency_key=f"system-invite:{key}",
                occurred_at="2026-08-11 19:20:00+00",
            ),
        ),
        (
            adoption.ProvenanceReceipt(
                receipt_id=RECEIPT_ID,
                organization_id=ORGANIZATION_ID,
                actor_id=OWNER_ID,
                command_name="system_provision_invited_member",
                idempotency_key=key,
                result={
                    "ok": True,
                    "organization_id": ORGANIZATION_ID,
                    "user_id": USER_ID,
                    "membership_id": MEMBERSHIP_ID,
                    "role": "trainee",
                    "status": "active",
                },
                created_at="2026-08-11 19:20:00+00",
            ),
        ),
    )


def _row(snapshot: adoption.PartialAdoptionSnapshot) -> dict[str, object]:
    row = asdict(snapshot)
    row["auth_providers"] = list(snapshot.auth_providers)
    row["membership_permissions"] = list(snapshot.membership_permissions)
    row["provenance_events"] = [
        asdict(value) for value in snapshot.provenance_events
    ]
    row["provenance_receipts"] = [
        asdict(value) for value in snapshot.provenance_receipts
    ]
    return row


class ReadOnlyManagement:
    def __init__(self, row: dict[str, object]) -> None:
        self.row = row
        self.queries: list[dict[str, object]] = []

    def execute(self, sql: str, *, read_only: bool = False) -> list[object]:
        self.queries.append({"sql": sql, "read_only": read_only})
        return [self.row]


def test_snapshot_query_is_read_only_and_captures_every_boundary() -> None:
    management = ReadOnlyManagement(_row(_snapshot()))

    result = adoption._read_snapshot(
        management,
        email=EMAIL,
        organization_id=ORGANIZATION_ID,
        authority_id=OWNER_ID,
    )

    assert result == _snapshot()
    assert len(management.queries) == 1
    query = management.queries[0]
    assert query["read_only"] is True
    sql = str(query["sql"])
    for required in (
        "auth.users",
        "encrypted_password",
        "raw_user_meta_data",
        "profiles",
        "memberships",
        "membership_permissions",
        "membership_created_at",
        "membership_updated_at",
        "training_access_waivers",
        "waiver_grant_reason",
        "training_attempts",
        "training_certifications",
        "workspace_project_memberships",
        "factory_events",
        "command_receipts",
        adoption.SOURCE_CREATED_AFTER_SQL,
        adoption.SOURCE_CREATED_BEFORE_SQL,
    ):
        assert required in sql
    assert not any(
        token in sql.casefold()
        for token in ("insert into", "update ", "delete from")
    )
    assert "coalesce(auth_user.raw_user_meta_data, " not in sql


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("auth_match_count", "SENSITIVE_INVALID_VALUE"),
        ("auth_created_in_source_window", "SENSITIVE_INVALID_VALUE"),
        ("app_metadata", "SENSITIVE_INVALID_VALUE"),
        ("raw_user_meta_data", "SENSITIVE_INVALID_VALUE"),
        ("raw_user_meta_data", None),
        ("auth_providers", "SENSITIVE_INVALID_VALUE"),
        ("membership_permissions", "SENSITIVE_INVALID_VALUE"),
        ("membership_id", "SENSITIVE_INVALID_VALUE"),
    ],
)
def test_snapshot_parser_reports_only_the_invalid_top_level_field(
    field_name: str,
    invalid_value: object,
) -> None:
    row = _row(_snapshot())
    row[field_name] = invalid_value

    with pytest.raises(adoption.KlimovPartialAdoptionError) as caught:
        adoption._read_snapshot(
            ReadOnlyManagement(row),
            email=EMAIL,
            organization_id=ORGANIZATION_ID,
            authority_id=OWNER_ID,
        )

    assert str(caught.value) == (
        f"Partial-adoption snapshot is invalid: field={field_name}"
    )
    assert "SENSITIVE_INVALID_VALUE" not in str(caught.value)
    assert EMAIL not in str(caught.value)
    assert DISPLAY_NAME not in str(caught.value)


@pytest.mark.parametrize(
    ("collection_name", "nested_path", "mutate"),
    [
        (
            "provenance_events",
            "provenance_events[0].entity_id",
            lambda item: item.update(entity_id=""),
        ),
        (
            "provenance_events",
            "provenance_events[0].properties",
            lambda item: item.update(properties="SENSITIVE_INVALID_VALUE"),
        ),
        (
            "provenance_receipts",
            "provenance_receipts[0].actor_id",
            lambda item: item.update(actor_id="SENSITIVE_INVALID_VALUE"),
        ),
        (
            "provenance_receipts",
            "provenance_receipts[0].result",
            lambda item: item.update(result="SENSITIVE_INVALID_VALUE"),
        ),
    ],
)
def test_snapshot_parser_reports_only_nested_provenance_field(
    collection_name: str,
    nested_path: str,
    mutate: Callable[[dict[str, object]], object],
) -> None:
    events, receipts = _limited_provenance()
    row = _row(
        _snapshot(
            provenance_events=events,
            provenance_receipts=receipts,
        )
    )
    item = row[collection_name][0]
    assert isinstance(item, dict)
    mutate(item)

    with pytest.raises(adoption.KlimovPartialAdoptionError) as caught:
        adoption._read_snapshot(
            ReadOnlyManagement(row),
            email=EMAIL,
            organization_id=ORGANIZATION_ID,
            authority_id=OWNER_ID,
        )

    assert str(caught.value) == (
        f"Partial-adoption snapshot is invalid: field={nested_path}"
    )
    assert "SENSITIVE_INVALID_VALUE" not in str(caught.value)
    assert EMAIL not in str(caught.value)


def test_provenance_validation_reports_only_the_nested_field() -> None:
    events, receipts = _limited_provenance()
    broken_receipt = replace(
        receipts[0],
        result={
            **receipts[0].result,
            "membership_id": "SENSITIVE_INVALID_VALUE",
        },
    )

    with pytest.raises(adoption.KlimovPartialAdoptionError) as caught:
        adoption._classify_provenance(
            _snapshot(
                provenance_events=events,
                provenance_receipts=(broken_receipt,),
            )
        )

    assert str(caught.value) == (
        "Partial-adoption snapshot is invalid: "
        "field=provenance_receipts[0].result.membership_id"
    )
    assert "SENSITIVE_INVALID_VALUE" not in str(caught.value)


def test_snapshot_field_diagnostic_rejects_an_unsafe_field_label() -> None:
    error = adoption._invalid_snapshot_field(
        "profile_email=secret@example.com"
    )

    assert str(error) == (
        "Partial-adoption snapshot is invalid: field=internal_field"
    )
    assert "secret@example.com" not in str(error)


def test_exact_owner_authority_is_bound_to_fixed_email_and_read_only() -> None:
    class OwnerManagement:
        def __init__(self) -> None:
            self.queries: list[dict[str, object]] = []

        def execute(self, sql: str, *, read_only: bool = False) -> list[object]:
            self.queries.append({"sql": sql, "read_only": read_only})
            return [
                {
                    "organization_id": ORGANIZATION_ID,
                    "invited_by": OWNER_ID,
                }
            ]

    management = OwnerManagement()

    assert adoption._read_exact_owner_authority(
        management,
        owner_email=OWNER_EMAIL,
    ) == AUTHORITY
    assert len(management.queries) == 1
    assert management.queries[0]["read_only"] is True
    sql = str(management.queries[0]["sql"])
    assert OWNER_EMAIL in sql
    assert "owner_membership.role = 'owner'" in sql
    assert "owner_membership.role in ('owner', 'admin')" not in sql


def test_no_provenance_is_explicitly_a_one_off_adoption() -> None:
    classification, phase = adoption._validate_snapshot(
        _snapshot(),
        email=EMAIL,
        display_name=DISPLAY_NAME,
        owner_email=OWNER_EMAIL,
        authority=AUTHORITY,
    )

    assert classification == adoption.CLASS_NO_PROVENANCE
    assert phase == adoption.PHASE_UNCONFIRMED_TRAINEE
    assert "one_off_adoption" in classification
    assert "resume" not in classification


@pytest.mark.parametrize(
    ("events", "receipts", "expected"),
    [
        (*_limited_provenance(), adoption.CLASS_LIMITED_PROVENANCE),
        (*_invited_provenance(), adoption.CLASS_INVITED_PROVENANCE),
    ],
)
def test_exact_known_provenance_is_classified(
    events: tuple[adoption.ProvenanceEvent, ...],
    receipts: tuple[adoption.ProvenanceReceipt, ...],
    expected: str,
) -> None:
    snapshot = _snapshot(
        provenance_events=events,
        provenance_receipts=receipts,
    )

    assert adoption._classify_provenance(snapshot) == expected


def test_inconsistent_present_provenance_fails_closed() -> None:
    events, receipts = _limited_provenance()
    broken_receipt = replace(
        receipts[0],
        result={**receipts[0].result, "membership_id": EVENT_ID},
    )

    with pytest.raises(
        adoption.KlimovPartialAdoptionError,
        match="provenance",
    ):
        adoption._classify_provenance(
            _snapshot(
                provenance_events=events,
                provenance_receipts=(broken_receipt,),
            )
        )


@pytest.mark.parametrize(
    "unsafe",
    [
        _snapshot(auth_match_count=2),
        _snapshot(auth_created_in_source_window=False),
        _snapshot(auth_created_at="2026-08-11 19:12:31+00"),
        _snapshot(auth_active=False),
        _snapshot(signed_in=True),
        _snapshot(no_encrypted_password=False),
        _snapshot(
            app_metadata={
                **_snapshot().app_metadata,
                "contentengine_unreviewed_marker": True,
            }
        ),
        _snapshot(app_metadata={**_snapshot().app_metadata, "unreviewed": True}),
        _snapshot(auth_provider="phone"),
        _snapshot(auth_providers=("email", "phone")),
        _snapshot(raw_user_meta_data={}),
        _snapshot(
            raw_user_meta_data={
                "display_name": DISPLAY_NAME,
                "unreviewed": True,
            }
        ),
        _snapshot(auth_display_name="Somebody else"),
        _snapshot(profile_email="somebody-else@example.com"),
        _snapshot(profile_display_name="Somebody else"),
        _snapshot(profile_status="suspended"),
        _snapshot(authority_is_active_owner=False),
        _snapshot(authority_email=EMAIL),
        _snapshot(authority_auth_email=EMAIL),
        _snapshot(membership_role="operator"),
        _snapshot(membership_status="suspended"),
        _snapshot(membership_permissions=("workspace:*",)),
        _snapshot(membership_count=2),
        _snapshot(waiver_count=1),
        _snapshot(training_attempt_count=1),
        _snapshot(training_certification_count=1),
        _snapshot(project_membership_count=1),
    ],
)
def test_any_reviewed_boundary_mismatch_stops_before_adoption(
    unsafe: adoption.PartialAdoptionSnapshot,
) -> None:
    with pytest.raises(
        adoption.KlimovPartialAdoptionError,
    ):
        adoption._validate_snapshot(
            unsafe,
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            authority=AUTHORITY,
        )


def test_confirmed_trainee_and_exact_operator_are_resumable_phases() -> None:
    assert _confirmed_trainee().raw_user_meta_data == {
        "display_name": DISPLAY_NAME,
        "email_verified": True,
    }
    assert adoption._validate_snapshot(
        _confirmed_trainee(),
        email=EMAIL,
        display_name=DISPLAY_NAME,
        owner_email=OWNER_EMAIL,
        authority=AUTHORITY,
    ) == (
        adoption.CLASS_NO_PROVENANCE,
        adoption.PHASE_CONFIRMED_TRAINEE,
    )
    assert adoption._validate_snapshot(
        _operator(),
        email=EMAIL,
        display_name=DISPLAY_NAME,
        owner_email=OWNER_EMAIL,
        authority=AUTHORITY,
    ) == (
        adoption.CLASS_NO_PROVENANCE,
        adoption.PHASE_CONFIRMED_OPERATOR,
    )
    assert _operator().raw_user_meta_data == {
        "display_name": DISPLAY_NAME,
        "email_verified": True,
    }


@pytest.mark.parametrize(
    "unsafe",
    [
        _snapshot(
            raw_user_meta_data={
                "display_name": DISPLAY_NAME,
                "email_verified": True,
            }
        ),
        replace(
            _confirmed_trainee(),
            raw_user_meta_data={"display_name": DISPLAY_NAME},
        ),
        replace(
            _confirmed_trainee(),
            raw_user_meta_data={
                "display_name": DISPLAY_NAME,
                "email_verified": False,
            },
        ),
        replace(
            _confirmed_trainee(),
            raw_user_meta_data={
                "display_name": DISPLAY_NAME,
                "email_verified": "true",
            },
        ),
        replace(
            _confirmed_trainee(),
            raw_user_meta_data={
                "display_name": DISPLAY_NAME,
                "email_verified": True,
                "unexpected": True,
            },
        ),
        replace(
            _confirmed_missing_name(),
            raw_user_meta_data={},
        ),
        replace(
            _operator(),
            raw_user_meta_data={"display_name": DISPLAY_NAME},
        ),
    ],
)
def test_email_verified_metadata_is_exact_and_phase_aware(
    unsafe: adoption.PartialAdoptionSnapshot,
) -> None:
    with pytest.raises(adoption.KlimovPartialAdoptionError):
        adoption._validate_snapshot(
            unsafe,
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            authority=AUTHORITY,
        )


def test_only_exact_empty_name_state_is_a_resumable_repair_phase() -> None:
    assert adoption._display_name_state(
        _missing_name(),
        display_name=DISPLAY_NAME,
    ) == adoption.NAME_STATE_NEEDS_AUTH_NAME
    assert adoption._display_name_state(
        _missing_name(profile_display_name=DISPLAY_NAME),
        display_name=DISPLAY_NAME,
    ) == adoption.NAME_STATE_NEEDS_AUTH_NAME
    assert adoption._display_name_state(
        _retry_profile_sync(),
        display_name=DISPLAY_NAME,
    ) == adoption.NAME_STATE_RETRY_PROFILE_SYNC
    assert adoption._display_name_state(
        _snapshot(),
        display_name=DISPLAY_NAME,
    ) == adoption.NAME_STATE_READY
    assert adoption._validate_snapshot(
        _missing_name(),
        email=EMAIL,
        display_name=DISPLAY_NAME,
        owner_email=OWNER_EMAIL,
        authority=AUTHORITY,
    ) == (
        adoption.CLASS_NO_PROVENANCE,
        adoption.PHASE_UNCONFIRMED_TRAINEE_MISSING_NAME,
    )
    assert adoption._validate_snapshot(
        _missing_name(profile_display_name=DISPLAY_NAME),
        email=EMAIL,
        display_name=DISPLAY_NAME,
        owner_email=OWNER_EMAIL,
        authority=AUTHORITY,
    ) == (
        adoption.CLASS_NO_PROVENANCE,
        adoption.PHASE_UNCONFIRMED_TRAINEE_MISSING_NAME,
    )
    assert adoption._validate_snapshot(
        _retry_profile_sync(),
        email=EMAIL,
        display_name=DISPLAY_NAME,
        owner_email=OWNER_EMAIL,
        authority=AUTHORITY,
    ) == (
        adoption.CLASS_NO_PROVENANCE,
        adoption.PHASE_UNCONFIRMED_TRAINEE_MISSING_NAME,
    )
    assert adoption._validate_snapshot(
        _confirmed_missing_name(),
        email=EMAIL,
        display_name=DISPLAY_NAME,
        owner_email=OWNER_EMAIL,
        authority=AUTHORITY,
    ) == (
        adoption.CLASS_NO_PROVENANCE,
        adoption.PHASE_CONFIRMED_TRAINEE_MISSING_NAME,
    )


@pytest.mark.parametrize(
    "unsafe",
    [
        _missing_name(raw_user_meta_data={"display_name": ""}),
        _missing_name(raw_user_meta_data={"unexpected": True}),
        _missing_name(auth_display_name=DISPLAY_NAME),
        _retry_profile_sync(auth_display_name=""),
        _retry_profile_sync(profile_display_name="Somebody else"),
        _missing_name(membership_role="operator"),
    ],
)
def test_partial_or_nonempty_missing_name_state_fails_closed(
    unsafe: adoption.PartialAdoptionSnapshot,
) -> None:
    with pytest.raises(adoption.KlimovPartialAdoptionError):
        adoption._validate_snapshot(
            unsafe,
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            authority=AUTHORITY,
        )


def test_operator_phase_requires_exact_prior_one_off_reason() -> None:
    with pytest.raises(
        adoption.KlimovPartialAdoptionError,
        match="not safely resumable",
    ):
        adoption._validate_snapshot(
            _operator(reason="Unreviewed waiver reason"),
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            authority=AUTHORITY,
        )


class ApplyManagement:
    def __init__(self) -> None:
        self.server_key_calls = 0

    def get_server_key(self) -> str:
        self.server_key_calls += 1
        return SERVER_KEY


class ApplyAuth:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.recovery_emails: list[str] = []

    def _admin_request(
        self,
        path: str,
        *,
        method: str,
        payload: dict[str, object],
    ) -> None:
        self.calls.append(
            {"path": path, "method": method, "payload": dict(payload)}
        )

    def send_password_recovery(self, *, email: str) -> None:
        self.recovery_emails.append(email)


def _set_github_apply_context(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": adoption.EXPECTED_REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_WORKFLOW": adoption.EXPECTED_WORKFLOW,
        "GITHUB_JOB": "adopt",
        "GITHUB_RUN_ID": "31599999999",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR": "reviewed-operator",
        "GITHUB_SHA": "a" * 40,
        "SUPABASE_PROJECT_REF": "iyckwryrucqrxwlowxow",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


class ApplyHarness:
    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        snapshots: list[adoption.PartialAdoptionSnapshot],
    ) -> None:
        self.management = ApplyManagement()
        self.auth = ApplyAuth()
        self.auth_builds = 0
        self.reads = 0
        self.grants: list[dict[str, object]] = []
        self.verifications: list[dict[str, object]] = []
        iterator = iter(snapshots)
        monkeypatch.setattr(
            adoption,
            "_read_exact_owner_authority",
            lambda _client, *, owner_email: (
                AUTHORITY
                if owner_email == OWNER_EMAIL
                else pytest.fail("unexpected owner email")
            ),
        )

        def read_snapshot(*_args: object, **_kwargs: object) -> object:
            self.reads += 1
            try:
                return next(iterator)
            except StopIteration:
                pytest.fail("unexpected extra adoption snapshot read")

        monkeypatch.setattr(adoption, "_read_snapshot", read_snapshot)
        def build_auth(**_kwargs: object) -> ApplyAuth:
            self.auth_builds += 1
            return self.auth

        monkeypatch.setattr(adoption, "SupabaseAuthClient", build_auth)

        def grant(**kwargs: object) -> tuple[str, str]:
            self.grants.append(dict(kwargs))
            return "operator", "not_requested"

        monkeypatch.setattr(adoption, "grant_training_access_waiver", grant)

        def verify(*_args: object, **kwargs: object) -> None:
            self.verifications.append(dict(kwargs))

        monkeypatch.setattr(adoption, "_verify_training_waiver", verify)

    def run(self, *, apply: bool) -> adoption.PartialAdoptionResult:
        return adoption.adopt_klimov_partial_onboarding(
            management_client=self.management,
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            publishable_key=PUBLISHABLE_KEY,
            apply=apply,
        )


@pytest.mark.parametrize(
    ("snapshot", "expected_phase", "expected_role"),
    [
        (
            _snapshot(),
            adoption.PHASE_UNCONFIRMED_TRAINEE,
            "trainee",
        ),
        (
            _missing_name(),
            adoption.PHASE_UNCONFIRMED_TRAINEE_MISSING_NAME,
            "trainee",
        ),
        (
            _confirmed_trainee(),
            adoption.PHASE_CONFIRMED_TRAINEE,
            "trainee",
        ),
        (
            _confirmed_missing_name(),
            adoption.PHASE_CONFIRMED_TRAINEE_MISSING_NAME,
            "trainee",
        ),
        (
            _retry_profile_sync(),
            adoption.PHASE_UNCONFIRMED_TRAINEE_MISSING_NAME,
            "trainee",
        ),
        (
            _operator(),
            adoption.PHASE_CONFIRMED_OPERATOR,
            "operator",
        ),
    ],
)
def test_read_only_preflight_never_creates_auth_or_mutates_in_any_phase(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: adoption.PartialAdoptionSnapshot,
    expected_phase: str,
    expected_role: str,
) -> None:
    harness = ApplyHarness(monkeypatch, [snapshot])

    result = harness.run(apply=False)

    assert result == adoption.PartialAdoptionResult(
        classification=adoption.CLASS_NO_PROVENANCE,
        phase=expected_phase,
        identity_status="preflight_only",
        membership_role=expected_role,
        recovery_status="not_requested",
    )
    assert harness.reads == 1
    assert harness.management.server_key_calls == 0
    assert harness.auth_builds == 0
    assert harness.auth.calls == []
    assert harness.auth.recovery_emails == []
    assert harness.grants == []
    assert harness.verifications == []


def test_apply_rereads_same_snapshot_puts_only_email_confirm_and_binds_waiver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    before = _snapshot()
    confirmed = _confirmed_trainee()
    operator = _operator()
    assert confirmed == replace(
        before,
        email_confirmed=True,
        raw_user_meta_data={
            "display_name": DISPLAY_NAME,
            "email_verified": True,
        },
    )
    harness = ApplyHarness(
        monkeypatch,
        [before, before, confirmed, operator, operator],
    )

    result = harness.run(apply=True)

    assert result == adoption.PartialAdoptionResult(
        classification=adoption.CLASS_NO_PROVENANCE,
        phase=adoption.PHASE_CONFIRMED_OPERATOR,
        identity_status="confirmed_by_one_off_adoption",
        membership_role="operator",
        recovery_status="requested",
    )
    assert harness.reads == 5
    assert harness.management.server_key_calls == 1
    assert harness.auth.calls == [
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {"email_confirm": True},
        }
    ]
    assert harness.auth.recovery_emails == [EMAIL]
    assert len(harness.grants) == 1
    grant = harness.grants[0]
    assert grant["expected_user_id"] == USER_ID
    assert grant["expected_membership_id"] == MEMBERSHIP_ID
    assert grant["expected_organization_id"] == ORGANIZATION_ID
    assert grant["expected_authority_id"] == OWNER_ID
    assert grant["expected_pre_role"] == "trainee"
    assert grant["send_recovery"] is False
    reason = str(grant["reason"])
    assert "not a generic resume" in reason
    assert f"classification={adoption.CLASS_NO_PROVENANCE}" in reason
    assert f"source_creation_run={adoption.SOURCE_CREATION_RUN_ID}" in reason
    assert "actions/runs/31599999999" in reason
    assert len(harness.verifications) == 1
    assert harness.verifications[0]["expected_reason"] == reason
    assert harness.verifications[0]["expected_pre_role"] == "trainee"


def test_apply_repairs_exact_missing_name_before_separate_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    missing_name = _missing_name()
    named = _snapshot()
    confirmed = _confirmed_trainee()
    operator = _operator()
    harness = ApplyHarness(
        monkeypatch,
        [
            missing_name,
            missing_name,
            named,
            confirmed,
            operator,
            operator,
        ],
    )

    result = harness.run(apply=True)

    assert result == adoption.PartialAdoptionResult(
        classification=adoption.CLASS_NO_PROVENANCE,
        phase=adoption.PHASE_CONFIRMED_OPERATOR,
        identity_status=(
            "display_name_repaired_and_confirmed_by_one_off_adoption"
        ),
        membership_role="operator",
        recovery_status="requested",
    )
    assert harness.reads == 6
    assert harness.management.server_key_calls == 1
    assert harness.auth.calls == [
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {
                "user_metadata": {"display_name": DISPLAY_NAME},
            },
        },
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {"email_confirm": True},
        },
    ]
    assert harness.auth.recovery_emails == [EMAIL]
    assert len(harness.grants) == 1
    assert len(harness.verifications) == 1


def test_confirmed_missing_name_resume_repairs_name_without_confirmation_put(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    missing_name = _confirmed_missing_name()
    named = _confirmed_trainee()
    operator = _operator()
    harness = ApplyHarness(
        monkeypatch,
        [missing_name, missing_name, named, operator, operator],
    )

    result = harness.run(apply=True)

    assert result.identity_status == "display_name_repaired"
    assert result.phase == adoption.PHASE_CONFIRMED_OPERATOR
    assert harness.management.server_key_calls == 1
    assert harness.auth.calls == [
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {
                "user_metadata": {"display_name": DISPLAY_NAME},
            },
        }
    ]
    assert harness.auth.recovery_emails == [EMAIL]
    assert len(harness.grants) == 1


def test_missing_auth_name_with_already_exact_profile_is_repaired_resumably(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    needs_auth_name = _missing_name(profile_display_name=DISPLAY_NAME)
    named = _snapshot()
    confirmed = _confirmed_trainee()
    operator = _operator()
    harness = ApplyHarness(
        monkeypatch,
        [
            needs_auth_name,
            needs_auth_name,
            named,
            confirmed,
            operator,
            operator,
        ],
    )

    result = harness.run(apply=True)

    assert result.identity_status == (
        "display_name_repaired_and_confirmed_by_one_off_adoption"
    )
    assert harness.auth.calls[:2] == [
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {
                "user_metadata": {"display_name": DISPLAY_NAME},
            },
        },
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {"email_confirm": True},
        },
    ]
    assert harness.auth.recovery_emails == [EMAIL]


def test_retry_after_swallowed_profile_trigger_repeats_only_name_put(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    retry_profile_sync = _retry_profile_sync(email_confirmed=True)
    named = _confirmed_trainee()
    operator = _operator()
    harness = ApplyHarness(
        monkeypatch,
        [
            retry_profile_sync,
            retry_profile_sync,
            named,
            operator,
            operator,
        ],
    )

    result = harness.run(apply=True)

    assert result.identity_status == "display_name_repaired"
    assert harness.auth.calls == [
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {
                "user_metadata": {"display_name": DISPLAY_NAME},
            },
        }
    ]
    assert harness.auth.recovery_emails == [EMAIL]
    assert len(harness.grants) == 1


def test_unconfirmed_retry_after_swallowed_profile_trigger_reaches_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    retry_profile_sync = _retry_profile_sync()
    named = _snapshot()
    confirmed = _confirmed_trainee()
    operator = _operator()
    harness = ApplyHarness(
        monkeypatch,
        [
            retry_profile_sync,
            retry_profile_sync,
            named,
            confirmed,
            operator,
            operator,
        ],
    )

    result = harness.run(apply=True)

    assert result.identity_status == (
        "display_name_repaired_and_confirmed_by_one_off_adoption"
    )
    assert harness.auth.calls == [
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {
                "user_metadata": {"display_name": DISPLAY_NAME},
            },
        },
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {"email_confirm": True},
        },
    ]
    assert harness.auth.recovery_emails == [EMAIL]
    assert len(harness.grants) == 1


def test_confirmed_trainee_resume_skips_put_then_waives_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    confirmed = _confirmed_trainee()
    operator = _operator()
    harness = ApplyHarness(
        monkeypatch,
        [confirmed, confirmed, operator, operator],
    )

    result = harness.run(apply=True)

    assert result.identity_status == "confirmation_already_complete"
    assert result.phase == adoption.PHASE_CONFIRMED_OPERATOR
    assert harness.auth.calls == []
    assert harness.auth.recovery_emails == [EMAIL]
    assert len(harness.grants) == 1
    assert harness.grants[0]["send_recovery"] is False
    assert len(harness.verifications) == 1


def test_operator_resume_skips_put_and_waiver_but_reverifies_before_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    operator = _operator()
    harness = ApplyHarness(monkeypatch, [operator, operator, operator])

    result = harness.run(apply=True)

    assert result.identity_status == "waiver_already_complete"
    assert result.phase == adoption.PHASE_CONFIRMED_OPERATOR
    assert harness.auth.calls == []
    assert harness.grants == []
    assert len(harness.verifications) == 1
    assert harness.verifications[0]["expected_reason"] == operator.waiver_grant_reason
    assert harness.auth.recovery_emails == [EMAIL]


def test_changed_second_snapshot_blocks_auth_put(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    before = _snapshot()
    changed = replace(before, auth_created_at="2026-08-11 19:12:29.124+00")
    harness = ApplyHarness(monkeypatch, [before, changed])

    with pytest.raises(
        adoption.KlimovPartialAdoptionError,
        match="changed before the next saga action",
    ):
        harness.run(apply=True)

    assert harness.management.server_key_calls == 0
    assert harness.auth.calls == []
    assert harness.auth.recovery_emails == []
    assert harness.grants == []


@pytest.mark.parametrize(
    "post",
    [
        replace(
            _confirmed_trainee(),
            raw_user_meta_data={"display_name": DISPLAY_NAME},
        ),
        replace(
            _confirmed_trainee(),
            raw_user_meta_data={
                "display_name": DISPLAY_NAME,
                "email_verified": False,
            },
        ),
        replace(
            _confirmed_trainee(),
            raw_user_meta_data={
                "display_name": DISPLAY_NAME,
                "email_verified": True,
                "unexpected": True,
            },
        ),
        replace(
            _confirmed_trainee(),
            profile_display_name="Somebody else",
        ),
    ],
)
def test_post_put_snapshot_requires_exact_confirmation_transition(
    monkeypatch: pytest.MonkeyPatch,
    post: adoption.PartialAdoptionSnapshot,
) -> None:
    _set_github_apply_context(monkeypatch)
    before = _snapshot()
    harness = ApplyHarness(monkeypatch, [before, before, post])

    with pytest.raises(adoption.KlimovPartialAdoptionError):
        harness.run(apply=True)

    assert len(harness.auth.calls) == 1
    assert harness.auth.recovery_emails == []
    assert harness.grants == []


@pytest.mark.parametrize(
    "post_repair",
    [
        _snapshot(
            raw_user_meta_data={
                "display_name": DISPLAY_NAME,
                "unexpected": True,
            }
        ),
        _snapshot(profile_display_name=""),
        _snapshot(membership_updated_at="2026-08-11 19:20:01+00"),
        _confirmed_trainee(),
    ],
)
def test_name_repair_postread_permits_only_exact_name_fields(
    monkeypatch: pytest.MonkeyPatch,
    post_repair: adoption.PartialAdoptionSnapshot,
) -> None:
    _set_github_apply_context(monkeypatch)
    missing_name = _missing_name()
    harness = ApplyHarness(
        monkeypatch,
        [missing_name, missing_name, post_repair],
    )

    with pytest.raises(adoption.KlimovPartialAdoptionError):
        harness.run(apply=True)

    assert harness.auth.calls == [
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {
                "user_metadata": {"display_name": DISPLAY_NAME},
            },
        }
    ]
    assert harness.auth.recovery_emails == []
    assert harness.grants == []
    assert harness.verifications == []


def test_post_waiver_mismatch_blocks_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    confirmed = _confirmed_trainee()
    unsafe_operator = _operator(project_membership_count=1)
    harness = ApplyHarness(
        monkeypatch,
        [confirmed, confirmed, unsafe_operator],
    )

    with pytest.raises(adoption.KlimovPartialAdoptionError):
        harness.run(apply=True)

    assert len(harness.grants) == 1
    assert harness.grants[0]["send_recovery"] is False
    assert harness.management.server_key_calls == 0
    assert harness.auth.recovery_emails == []


def test_final_snapshot_toctou_blocks_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    operator = _operator()
    changed = replace(
        operator,
        membership_updated_at="2026-08-11 20:00:01+00",
    )
    harness = ApplyHarness(monkeypatch, [operator, operator, changed])

    with pytest.raises(
        adoption.KlimovPartialAdoptionError,
        match="Recovery target changed",
    ):
        harness.run(apply=True)

    assert len(harness.verifications) == 1
    assert harness.management.server_key_calls == 1
    assert harness.auth.recovery_emails == []


def test_final_email_uuid_remap_blocks_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    operator = _operator()
    remapped = replace(
        operator,
        user_id=EVENT_ID,
        profile_id=EVENT_ID,
        membership_profile_id=EVENT_ID,
        waiver_profile_id=EVENT_ID,
    )
    harness = ApplyHarness(monkeypatch, [operator, operator, remapped])

    with pytest.raises(
        adoption.KlimovPartialAdoptionError,
        match="Recovery target changed",
    ):
        harness.run(apply=True)

    assert harness.auth.recovery_emails == []


@pytest.mark.parametrize(
    "unsafe_operator",
    [
        _operator(signed_in=True),
        _operator(no_encrypted_password=False),
        _operator(
            app_metadata={
                "provider": "email",
                "providers": ["email"],
                MEMBER_PROVISION_MARKER: True,
            }
        ),
    ],
)
def test_recovery_retry_requires_unsigned_passwordless_exact_markers(
    monkeypatch: pytest.MonkeyPatch,
    unsafe_operator: adoption.PartialAdoptionSnapshot,
) -> None:
    _set_github_apply_context(monkeypatch)
    harness = ApplyHarness(monkeypatch, [unsafe_operator])

    with pytest.raises(adoption.KlimovPartialAdoptionError):
        harness.run(apply=True)

    assert harness.management.server_key_calls == 0
    assert harness.auth.recovery_emails == []


def test_apply_requires_exact_protected_github_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_github_apply_context(monkeypatch)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/feature")
    harness = ApplyHarness(monkeypatch, [_snapshot()])

    with pytest.raises(
        adoption.KlimovPartialAdoptionError,
        match="protected one-off GitHub workflow",
    ):
        harness.run(apply=True)

    assert harness.reads == 0
    assert harness.management.server_key_calls == 0


def test_cli_exposes_no_arbitrary_identity_or_state_inputs() -> None:
    parser = adoption._parser()

    assert set(parser.parse_args([]).__dict__) == {"apply"}
    with pytest.raises(SystemExit):
        parser.parse_args(["--email", EMAIL])
