import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608120003_employee_account_admin.sql"
)
EDGE_PATH = ROOT / "supabase" / "functions" / "creator-invite" / "index.ts"
CREATOR_FACTORY_TEST_PATH = ROOT / "supabase" / "tests" / "creator_factory_test.sql"
CONFIG_PATH = ROOT / "supabase" / "config.toml"
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"
DEPLOY_PATH = ROOT / ".github" / "workflows" / "supabase-pages.yml"

MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")
MIGRATION_LOWER = MIGRATION.casefold()
EDGE = EDGE_PATH.read_text(encoding="utf-8")
CREATOR_FACTORY_TEST = CREATOR_FACTORY_TEST_PATH.read_text(encoding="utf-8")


def _flat(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _sql_function(name: str, schema: str = "public") -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+{re.escape(schema)}\.{re.escape(name)}\s*\(",
        MIGRATION_LOWER,
    )
    if not match:
        raise ValueError(f"SQL function not found: {schema}.{name}")
    start = match.start()
    end = MIGRATION_LOWER.index("\n$$;", start) + len("\n$$;")
    return MIGRATION[start:end]


def _table_definition(name: str) -> str:
    marker = f"create table if not exists content_factory.{name} ("
    start = MIGRATION_LOWER.index(marker)
    end = MIGRATION_LOWER.index("\n);", start) + len("\n);")
    return MIGRATION[start:end]


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    return node


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _node(),
            "--experimental-vm-modules",
            "--input-type=module",
            "-e",
            script,
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )


def test_employee_account_admin_migration_is_parseable_and_transactional() -> None:
    statements = parse_sql(MIGRATION)
    assert len(statements) >= 40
    assert MIGRATION_LOWER.lstrip().startswith("begin;")
    assert MIGRATION_LOWER.rstrip().endswith("commit;")


def test_managed_accounts_and_assignment_history_are_private_rls_tables() -> None:
    managed_accounts = _table_definition("managed_accounts")
    assignments = _table_definition("member_account_assignments")
    flat_migration = _flat(MIGRATION)

    assert "organization_id uuid not null" in managed_accounts
    assert "status text not null default 'active'" in managed_accounts
    assert "check (status in ('active', 'archived'))" in _flat(managed_accounts)
    assert (
        "constraint managed_accounts_org_id_uq unique (organization_id, id)"
        in _flat(managed_accounts)
    )
    assert (
        "references content_factory.memberships(organization_id, profile_id)"
        in _flat(managed_accounts)
    )
    assert "archive_reason" in managed_accounts
    assert (
        "btrim(url) !~* '^https?://[^/?#[:space:]]+@'"
        in _flat(managed_accounts)
    )

    assert "organization_id uuid not null" in assignments
    assert "account_id uuid not null" in assignments
    assert "profile_id uuid not null" in assignments
    assert "check (status in ('active', 'revoked'))" in _flat(assignments)
    assert (
        "references content_factory.managed_accounts(organization_id, id)"
        in _flat(assignments)
    )
    assert (
        "references content_factory.memberships(organization_id, profile_id)"
        in _flat(assignments)
    )
    assert "revoked_at timestamptz" in assignments
    assert "revoke_reason text" in assignments

    assert (
        "create unique index if not exists "
        "member_account_assignments_one_active_uq on "
        "content_factory.member_account_assignments "
        "(organization_id, account_id) where status = 'active'"
        in flat_migration
    )
    for table in ("managed_accounts", "member_account_assignments"):
        assert f"alter table content_factory.{table} enable row level security" in flat_migration
        assert f"alter table content_factory.{table} force row level security" in flat_migration
        assert (
            f"revoke all on content_factory.{table} from public, anon, authenticated"
            in flat_migration
        )
        assert f"grant all on content_factory.{table} to service_role" in flat_migration

    for definition in (managed_accounts, assignments):
        assert not re.search(
            r"(?im)^\s*(?:password|secret|access_token|refresh_token|cookie|"
            r"credential|recovery_code|two_factor_code)\s+",
            definition,
        )
    assert "never store passwords, tokens, cookies" in MIGRATION_LOWER


def test_browser_admin_authority_is_owner_or_admin_without_training_gate() -> None:
    guard = _sql_function("require_admin_actor", "content_factory_private")
    guard_flat = _flat(guard)
    snapshot = _sql_function("creator_admin_snapshot")
    mutate = _sql_function("creator_admin_mutate")
    grants = _flat(MIGRATION)

    assert "security definer" in guard_flat
    assert "set search_path = ''" in guard_flat
    assert "actor_id uuid := auth.uid()" in guard_flat
    assert "message = 'authentication_required'" in guard_flat
    assert "from auth.users auth_user" in guard_flat
    assert "auth_user.email_confirmed_at is not null" in guard_flat
    assert "auth_user.deleted_at is null" in guard_flat
    assert "auth_user.banned_until" in guard_flat
    assert (
        "membership_role( organization_id, false, array['owner', 'admin'] )"
        in guard_flat
    )
    for forbidden in (
        "training_certifications",
        "training_access_waivers",
        "operator_final_exam",
        "final_exam",
        "workspace_open",
    ):
        assert forbidden not in guard.casefold()

    for function_source in (snapshot, mutate):
        function_flat = _flat(function_source)
        assert "security definer" in function_flat
        assert "set search_path = ''" in function_flat
        assert "content_factory_private.require_admin_actor(organization_id)" in function_flat
    assert snapshot.casefold().index("require_admin_actor") < snapshot.casefold().index(
        "training_certifications"
    )
    for forbidden in (
        "training_certifications",
        "operator_final_exam",
        "final_exam",
        "workspace_open",
    ):
        assert forbidden not in mutate.casefold()
    assert "insert into content_factory.training_" not in mutate.casefold()
    waiver_cleanup = _flat(
        mutate[
            mutate.casefold().index("update content_factory.training_access_waivers") :
            mutate.casefold().index(
                "update content_factory.member_account_assignments",
                mutate.casefold().index("update content_factory.training_access_waivers"),
            )
        ]
    )
    assert "set status = 'revoked'" in waiver_cleanup
    assert not re.search(r"\bset\s+status\s*=\s*'active'", waiver_cleanup)

    for name in ("creator_admin_snapshot", "creator_admin_mutate"):
        assert (
            f"revoke all on function public.{name}(jsonb) "
            "from public, anon, authenticated"
            in grants
        )
        assert (
            f"grant execute on function public.{name}(jsonb) "
            "to authenticated, service_role"
            in grants
        )


def test_member_removal_is_a_protected_soft_revoke_with_audit_history() -> None:
    mutate = _sql_function("creator_admin_mutate")
    flat = _flat(mutate)

    assert "elsif action_value = 'revoke_member'" in flat
    assert "confirmation_value <> 'revoke_member'" in flat
    assert "message = 'revocation_confirmation_invalid'" in flat
    assert (
        "update content_factory.memberships member set status = 'revoked'"
        in flat
    )
    assert (
        "update content_factory.member_account_assignments assignment set "
        "status = 'revoked', revoked_by = actor_id, revoked_at = now(), "
        "revoke_reason = 'member_revoked: ' || reason_value"
        in flat
    )
    assert "event_name := 'admin_member_revoked'" in flat
    assert "delete from" not in flat
    assert "delete content_factory" not in flat
    assert "auth.users" in flat
    assert "deleteuser" not in flat

    assert "message = 'self_membership_change_forbidden'" in flat
    assert "message = 'owner_membership_protected'" in flat
    assert "actor_role = 'admin' and target_member.role = 'admin'" in flat
    assert "message = 'admin_membership_protected'" in flat
    assert "revoked_member_cannot_be_reactivated" in flat
    assert "content_factory_private.emit_event" in flat
    assert "content_factory_private.finish_command" in flat


def test_owner_admin_policy_matrix_is_consistent_for_people_and_assignments() -> None:
    mutate = _sql_function("creator_admin_mutate")
    flat = _flat(mutate)

    lifecycle_start = flat.index("if action_value in ( 'suspend_member'")
    lifecycle_end = flat.index("elsif action_value in ('create_account'", lifecycle_start)
    lifecycle = flat[lifecycle_start:lifecycle_end]
    assert "if target_member.role = 'owner' then" in lifecycle
    assert "message = 'owner_membership_protected'" in lifecycle
    assert (
        "if actor_role = 'admin' and target_member.role = 'admin' then"
        in lifecycle
    )
    assert "message = 'admin_membership_protected'" in lifecycle
    assert "if target_member.role = 'admin' then" not in lifecycle

    # Account cards already assigned to leadership are protected from every
    # mutating path for an admin. Owners intentionally do not match these
    # actor_role predicates and can manage another administrator.
    assert flat.count("if actor_role = 'admin' and exists (") >= 2
    assert (
        "if actor_role = 'admin' and target_member.role in ('owner', 'admin') then"
        in flat
    )
    assert (
        "if actor_role = 'admin' and assignment_row.id is not null and exists ("
        in flat
    )
    assert flat.count("message = 'account_assignment_protected'") >= 4


def test_suspend_preserves_durable_assignments_while_revoke_closes_every_scope() -> None:
    mutate = _sql_function("creator_admin_mutate")
    lower = mutate.casefold()
    decision_anchor = lower.index("previous_status := target_member.status")
    suspend_start = lower.index(
        "if action_value = 'suspend_member' then",
        decision_anchor,
    )
    reactivate_start = lower.index(
        "elsif action_value = 'reactivate_member' then",
        suspend_start,
    )
    confirmation_start = lower.index(
        "confirmation_value := content_factory_private.require_text(",
        reactivate_start,
    )
    revoke_end = lower.index(
        "event_name := 'admin_member_revoked'",
        confirmation_start,
    )
    suspend_branch = _flat(mutate[suspend_start:reactivate_start])
    revoke_branch = _flat(mutate[confirmation_start:revoke_end])

    assert "set status = 'suspended'" in suspend_branch
    for durable_scope in (
        "member_account_assignments",
        "workspace_project_memberships",
        "training_access_waivers",
    ):
        assert durable_scope not in suspend_branch

    assert "update content_factory.workspace_project_memberships" in revoke_branch
    assert "project_access.status = 'active'" in revoke_branch
    assert "update content_factory.training_access_waivers" in revoke_branch
    assert "waiver.status = 'active'" in revoke_branch
    assert "update content_factory.member_account_assignments" in revoke_branch
    assert "assignment.status = 'active'" in revoke_branch
    assert "set status = 'revoked'" in revoke_branch
    assert "revoke_reason = 'member_revoked: ' || reason_value" in revoke_branch
    for counter in (
        "project_access_revoked_count",
        "training_waivers_revoked_count",
        "account_assignments_revoked_count",
    ):
        assert f"get diagnostics {counter} = row_count" in revoke_branch


def test_account_crud_and_assignment_mutations_are_validated_and_history_preserving() -> None:
    mutate = _sql_function("creator_admin_mutate")
    flat = _flat(mutate)
    assignment_guard = _flat(
        _sql_function(
            "guard_member_account_assignment",
            "content_factory_private",
        )
    )

    for action in (
        "create_account",
        "update_account",
        "archive_account",
        "bind_account",
        "unbind_account",
    ):
        assert f"'{action}'" in flat
    assert "'creator_admin_' || action_value" in flat
    for event_name in (
        "admin_managed_account_created",
        "admin_managed_account_updated",
        "admin_managed_account_archived",
        "admin_managed_account_bound",
        "admin_managed_account_unbound",
    ):
        assert event_name in flat

    assert "message = 'admin_action_invalid'" in flat
    assert "message = 'platform_invalid'" in flat
    assert "message = 'url_invalid'" in flat
    assert "url_value ~* '^https?://[^/?#[:space:]]+@'" in flat
    assert "message = 'expected_updated_at_invalid'" in flat
    assert "message = 'managed_account_stale'" in flat
    assert "confirmation_value <> 'archive_account'" in flat
    assert "message = 'archive_confirmation_invalid'" in flat
    assert "message = 'managed_account_archived'" in flat

    assert "message = 'assignment_history_is_immutable'" in assignment_guard
    assert "old.status = 'revoked'" in assignment_guard
    assert "message = 'account_not_active'" in assignment_guard
    assert "message = 'target_membership_not_active'" in assignment_guard
    assert "auth_user.email_confirmed_at is not null" in assignment_guard
    assert "auth_user.deleted_at is null" in assignment_guard

    assert "message = 'account_assignment_protected'" in flat
    assert "target_member.role in ('owner', 'admin')" in flat
    assert flat.count("member.role in ('owner', 'admin')") >= 3
    assert "revoke_reason = 'reassigned_by_admin'" in flat
    assert "revoke_reason = 'unassigned_by_admin'" in flat
    assert "revoke_reason = 'account_archived: ' || reason_value" in flat
    assert "insert into content_factory.member_account_assignments" in flat
    assert "delete from content_factory.member_account_assignments" not in flat
    assert "delete from content_factory.managed_accounts" not in flat


def test_service_role_invite_rpcs_are_trainee_only_and_training_independent() -> None:
    functions = {
        "system_admin_provision_member": _sql_function(
            "system_admin_provision_member"
        ),
        "system_admin_reconcile_member": _sql_function(
            "system_admin_reconcile_member"
        ),
        "system_admin_record_invite_delivery_attempts": _sql_function(
            "system_admin_record_invite_delivery_attempts"
        ),
    }
    migration_flat = _flat(MIGRATION)

    for name, source in functions.items():
        flat = _flat(source)
        assert "security definer" in flat
        assert "set search_path = ''" in flat
        assert "coalesce(auth.role(), '') <> 'service_role'" in flat
        assert "message = 'service_role_required'" in flat
        assert (
            f"revoke all on function public.{name}(jsonb) "
            "from public, anon, authenticated, service_role"
            in migration_flat
        )
        assert (
            f"grant execute on function public.{name}(jsonb) to service_role"
            in migration_flat
        )
        for forbidden in (
            "training_certifications",
            "training_access_waivers",
            "operator_final_exam",
            "final_exam",
            "workspace_open",
        ):
            assert forbidden not in source.casefold()

    provision = _flat(functions["system_admin_provision_member"])
    reconcile = _flat(functions["system_admin_reconcile_member"])
    journal = _flat(functions["system_admin_record_invite_delivery_attempts"])

    assert "member.role in ('owner', 'admin')" in provision
    assert "member.status = 'active'" in provision
    assert "profile.status = 'active'" in provision
    assert "auth_user.email_confirmed_at is not null" in provision
    assert "auth_user.deleted_at is null" in provision
    assert "message = 'inviter_not_authorized'" in provision
    assert "<> 'trainee'" in provision
    assert "message = 'admin_member_role_invalid'" in provision
    assert "'role', 'trainee'" in provision
    assert "'trainee', 'active'" in provision
    assert "insert into content_factory.training" not in provision
    assert "update content_factory.training" not in provision

    assert "lower(btrim(auth_user.email)) = email_value" in reconcile
    assert "message = 'reconciliation_email_not_confirmed'" in reconcile
    assert "return public.system_admin_provision_member" in reconcile
    assert "membership.role in ('owner', 'admin')" in journal
    assert "membership.status = 'active'" in journal
    assert "message = 'inviter_not_authorized'" in journal


def test_invite_edge_uses_admin_journal_and_provisioning_without_workspace_gate() -> None:
    bootstrap_reader = EDGE[
        EDGE.index("type BootstrapResult") : EDGE.index("async function inviteIdentityKey")
    ]
    reservation_index = EDGE.index("const reservation = await persistResults(pendingResults)")
    delivery_index = EDGE.index(".auth.admin.inviteUserByEmail")

    assert 'auth: "user"' in EDGE
    assert 'new Set(["owner", "admin"])' in EDGE
    assert "organizationId: string" in bootstrap_reader
    assert "role: string" in bootstrap_reader
    assert "workspaceOpen" not in bootstrap_reader
    assert "final_exam" not in EDGE.casefold()
    assert "workspaceopen" not in EDGE.casefold()
    assert "workspace_open" not in EDGE.casefold()
    assert "training_certifications" not in EDGE.casefold()

    assert (
        'const INVITE_ATTEMPT_RPC = "system_admin_record_invite_delivery_attempts"'
        in EDGE
    )
    assert '"system_admin_provision_member"' in EDGE
    assert '"system_admin_reconcile_member"' in EDGE
    assert "context.supabaseAdmin.rpc(" in EDGE
    assert reservation_index < delivery_index
    assert 'code: "invite_journal_unavailable"' in EDGE
    assert "persistResults([result])" in EDGE
    assert "persistResults(retryResults)" in EDGE

    assert ".auth.admin.inviteUserByEmail" in EDGE
    assert "inviteData.user?.id" in EDGE
    assert "ADMIN_MEMBER_PROVISIONED_MARKER" in EDGE
    assert '[PASSWORD_CHANGE_REQUIRED_MARKER]: true' in EDGE
    assert 'intended_role: "trainee"' in EDGE
    assert 'role: "trainee"' in EDGE
    assert "idempotency_key:" in EDGE
    assert "deleteUser" not in EDGE


def test_invite_edge_requires_an_explicit_exact_organization_scope() -> None:
    flat = _flat(EDGE)

    assert "const uuid_pattern =" in flat
    assert (
        'object.keys(payload).some((key) => !["emails", "organization_id"].includes(key) )'
        in flat
    )
    assert 'typeof payload.organization_id === "string"' in flat
    assert "!uuid_pattern.test(requestedorganizationid)" in flat
    assert 'code: "organization_invalid"' in flat
    assert (
        '"creator_bootstrap", { p_payload: { organization_id: requestedorganizationid } }'
        in flat
    )
    assert (
        'bootstrap.organizationid.tolocalelowercase("en-us") !== requestedorganizationid'
        in flat
    )
    assert "const organizationid = bootstrap.organizationid" in flat
    assert 'rpc( "creator_bootstrap", { p_payload: {} }' not in flat


def test_existing_member_reconcile_idempotency_is_scoped_to_the_manager() -> None:
    identity_key = EDGE[
        EDGE.index("async function inviteIdentityKey(") : EDGE.index(
            "const inviteCreators",
            EDGE.index("async function inviteIdentityKey("),
        )
    ]
    flat_key = _flat(identity_key)
    flat_edge = _flat(EDGE)

    assert "organizationid: string, invitedby: string, email: string" in flat_key
    assert "`${organizationid}:${invitedby}:${email}`" in flat_key
    assert (
        "idempotency_key: await inviteidentitykey( organizationid, invitedby, email, )"
        in flat_edge
    )


def test_admin_invite_history_is_server_recoverable_and_independently_guarded() -> None:
    history = _sql_function("creator_invite_delivery_attempts")
    history_flat = _flat(history)
    grants = _flat(MIGRATION)

    assert "content_factory_private.require_admin_actor(organization_id)" in history_flat
    assert "from content_factory.invite_delivery_attempts attempt" in history_flat
    assert "where attempt.organization_id = organization_id" in history_flat
    assert "attempt.request_id = latest_request_id" in history_flat
    for field in (
        "reason_code",
        "delivery_status",
        "membership_provisioned",
        "persistence",
    ):
        assert f"'{field}'" in history_flat
    for forbidden in (
        "training_certifications",
        "operator_final_exam",
        "workspace_open",
    ):
        assert forbidden not in history.casefold()
    assert (
        "revoke all on function public.creator_invite_delivery_attempts(jsonb) "
        "from public, anon, authenticated, service_role"
        in grants
    )
    assert (
        "grant execute on function public.creator_invite_delivery_attempts(jsonb) "
        "to authenticated, service_role"
        in grants
    )


def test_member_offboarding_races_are_serialized_for_account_and_project_grants() -> None:
    lock = _sql_function("lock_admin_member", "content_factory_private")
    assignment_guard = _sql_function(
        "guard_member_account_assignment",
        "content_factory_private",
    )
    project_guard = _sql_function(
        "serialize_admin_project_membership",
        "content_factory_private",
    )
    mutate = _sql_function("creator_admin_mutate")
    lock_flat = _flat(lock)
    assignment_flat = _flat(assignment_guard)
    project_flat = _flat(project_guard)
    migration_flat = _flat(MIGRATION)

    assert "pg_catalog.pg_advisory_xact_lock(" in lock_flat
    assert "organization_id::text || ':' || profile_id::text" in lock_flat
    expected_trigger_lock = (
        "content_factory_private.lock_admin_member( "
        "new.organization_id, new.profile_id )"
    )
    assert expected_trigger_lock in assignment_flat
    assert expected_trigger_lock in project_flat
    assignment_lock = assignment_flat.index(expected_trigger_lock)
    assert assignment_flat.index(
        "if tg_op = 'insert' and new.status = 'active'"
    ) < assignment_lock
    project_lock = project_flat.index(expected_trigger_lock)
    assert project_flat.index("if new.status <> 'active' then return new") < project_lock
    assert project_flat.index(
        "if tg_op = 'update' and old.status = 'active' then return new"
    ) < project_lock
    assert "for update of member" in project_flat
    assert "workspace_project_member_not_operational" in project_flat
    assert (
        "create trigger guard_member_account_assignment before insert or update on "
        "content_factory.member_account_assignments"
        in migration_flat
    )
    assert (
        "create trigger admin_serialize_workspace_project_membership before insert or update on "
        "content_factory.workspace_project_memberships"
        in migration_flat
    )

    mutate_flat = _flat(mutate)
    lifecycle_lock = mutate_flat.index(
        "content_factory_private.lock_admin_member( organization_id, target_profile_id )"
    )
    lifecycle_row_lock = mutate_flat.index(
        "select member.* into target_member",
        lifecycle_lock,
    )
    assert lifecycle_lock < lifecycle_row_lock
    bind_start = mutate_flat.index("elsif action_value in ('bind_account', 'unbind_account')")
    bind_lock = mutate_flat.index(
        "content_factory_private.lock_admin_member( organization_id, target_profile_id )",
        bind_start,
    )
    bind_member_lock = mutate_flat.index(
        "select member.* into target_member",
        bind_lock,
    )
    assert bind_lock < bind_member_lock
    assert "for update" in mutate_flat[bind_member_lock:]


def test_migration_notifies_postgrest_after_registering_the_new_rpcs() -> None:
    flat = _flat(MIGRATION)
    notify_index = flat.rindex("notify pgrst, 'reload schema'")
    assert notify_index > flat.index(
        "grant execute on function public.creator_admin_snapshot(jsonb)"
    )
    assert notify_index > flat.index(
        "grant execute on function public.creator_admin_mutate(jsonb)"
    )
    assert notify_index > flat.index(
        "grant execute on function public.creator_invite_delivery_attempts(jsonb)"
    )
    assert notify_index < flat.rindex("commit")


def test_creator_rpc_inventory_counts_the_two_new_authenticated_admin_rpcs() -> None:
    flat = _flat(CREATOR_FACTORY_TEST)

    assert "'creator_admin_snapshot', 'creator_admin_mutate'" in flat
    assert "91, 'all browser rpcs expose exactly p_payload jsonb'" in flat
    assert "114, 'authenticated can execute all creator rpcs'" in flat


def test_admin_snapshot_exposes_audited_waiver_state_without_secret_material() -> None:
    snapshot = _sql_function("creator_admin_snapshot")
    snapshot_flat = _flat(snapshot)

    assert "'access_waiver_active', active_waiver.grant_reason is not null" in snapshot_flat
    assert "'access_waiver_reason', active_waiver.grant_reason" in snapshot_flat
    assert "from content_factory.training_access_waivers waiver" in snapshot_flat
    assert "waiver.scope = 'workspace_generation'" in snapshot_flat
    assert "waiver.status = 'active'" in snapshot_flat
    assert "content_factory_private.training_access_waiver_active(" in snapshot_flat
    for forbidden in (
        "password_hash",
        "encrypted_password",
        "access_token",
        "refresh_token",
        "session_token",
        "recovery_code",
    ):
        assert forbidden not in snapshot.casefold()


def test_edge_ci_and_production_deploy_keep_the_invite_contract_live() -> None:
    config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    ci = CI_PATH.read_text(encoding="utf-8")
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")
    yaml.safe_load(ci)
    yaml.safe_load(deploy)

    assert config["functions"]["creator-invite"]["verify_jwt"] is True
    assert "deno fmt --check supabase/functions/creator-invite" in ci
    assert "deno lint supabase/functions/creator-invite/index.ts" in ci
    assert "deno check supabase/functions/creator-invite/index.ts" in ci
    assert "supabase db start" in ci
    assert "supabase db lint --local --level error" in ci
    assert "supabase test db" in ci
    assert "python -m pytest -q" in ci

    assert "--migrations-dir supabase/migrations" in deploy
    assert "supabase functions deploy creator-invite" in deploy
    assert deploy.index("--migrations-dir supabase/migrations") < deploy.index(
        "supabase functions deploy creator-invite"
    )
    invite_deploy = deploy.split(
        "- name: Deploy authenticated creator invitation function",
        1,
    )[1].split("\n      - name:", 1)[0]
    assert "--no-verify-jwt" not in invite_deploy
    assert "supabase config push" in deploy


def test_klimov_email_uses_the_generic_invite_and_account_assignment_path() -> None:
    email_pattern = EDGE[
        EDGE.index("const EMAIL_PATTERN") : EDGE.index(";", EDGE.index("const EMAIL_PATTERN")) + 1
    ]
    normalize_email = EDGE[
        EDGE.index("function normalizeEmail(") : EDGE.index(
            "function classifyInviteFailure(",
            EDGE.index("function normalizeEmail("),
        )
    ]
    normalize_email = normalize_email.replace("value: unknown", "value").replace(
        "): string | null",
        ")",
    )
    module_source = (
        f"{email_pattern}\n{normalize_email}\n"
        "export { normalizeEmail };"
    )
    script = f"""
      import assert from 'node:assert/strict';
      import vm from 'node:vm';
      const module = new vm.SourceTextModule({json.dumps(module_source)}, {{
        identifier: 'creator-invite-email-contract.js',
      }});
      await module.link(() => {{ throw new Error('unexpected import'); }});
      await module.evaluate();
      assert.equal(
        module.namespace.normalizeEmail('  V.KLIMOV1313@GMAIL.COM  '),
        'v.klimov1313@gmail.com',
      );
      assert.equal(module.namespace.normalizeEmail('v.klimov1313@gmail.com'),
        'v.klimov1313@gmail.com');
      console.log('klimov-email-regression: PASS');
    """
    result = _run_node(script)
    assert "klimov-email-regression: PASS" in result.stdout

    production_bundle = "\n".join(
        (
            EDGE,
            MIGRATION,
            (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8"),
            (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8"),
        )
    ).casefold()
    assert "v.klimov1313@gmail.com" not in production_bundle
    assert '"system_admin_provision_member"' in EDGE
    assert "insert into content_factory.memberships" in _sql_function(
        "system_admin_provision_member"
    ).casefold()
    assert "'bind_account'" in _sql_function("creator_admin_mutate").casefold()
