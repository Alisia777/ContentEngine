from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RPC_SQL = (
    ROOT / "supabase/migrations/202607130004_creator_rpcs.sql"
).read_text(encoding="utf-8")
STORAGE_SQL = (
    ROOT / "supabase/migrations/202607130003_rls_and_storage.sql"
).read_text(encoding="utf-8")
CATALOG_SQL = (
    ROOT / "supabase/migrations/202607130002_training_catalog.sql"
).read_text(encoding="utf-8")

EXPECTED_RPCS = (
    "creator_bootstrap",
    "creator_complete_module",
    "creator_submit_exam",
    "creator_workspace_section",
    "creator_create_mock_batch",
    "creator_confirm_placement",
    "creator_record_metric",
    "creator_set_wb_alias",
    "creator_decide_payout",
    "creator_transition_task",
    "creator_create_feedback",
    "creator_register_media",
    "creator_capture_event",
)


def _function_body(name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+public\.{name}"
        rf"\s*\(\s*p_payload\s+jsonb[^)]*\)\s*returns\s+jsonb"
        rf"(?P<header>.*?)as\s+\$\$(?P<body>.*?)\$\$;",
        RPC_SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing {name}(p_payload jsonb)"
    header = match.group("header").casefold()
    assert "security definer" in header
    assert "set search_path = ''" in header
    return match.group("body")


def test_every_browser_rpc_is_one_arg_authenticated_only() -> None:
    declarations = re.findall(
        r"create\s+or\s+replace\s+function\s+public\.(creator_[a-z_]+)",
        RPC_SQL,
        flags=re.IGNORECASE,
    )
    assert set(declarations) == set(EXPECTED_RPCS)

    for name in EXPECTED_RPCS:
        _function_body(name)
        assert re.search(
            rf"revoke\s+all\s+on\s+function\s+public\.{name}"
            rf"\s*\(\s*jsonb\s*\)\s+from\s+public\s*,\s*anon",
            RPC_SQL,
            flags=re.IGNORECASE,
        )
        assert re.search(
            rf"grant\s+execute\s+on\s+function\s+public\.{name}"
            rf"\s*\(\s*jsonb\s*\)\s+to\s+authenticated",
            RPC_SQL,
            flags=re.IGNORECASE,
        )


def test_mutations_are_org_scoped_gated_and_idempotent() -> None:
    mutations = set(EXPECTED_RPCS) - {"creator_bootstrap", "creator_workspace_section"}
    for name in mutations:
        body = _function_body(name)
        assert "current_profile_id()" in body
        assert "resolve_organization(p_payload)" in body
        assert "membership_role(" in body
        assert "idempotency_key" in body
        assert "begin_command(" in body
        assert "finish_command(" in body

    workspace = _function_body("creator_workspace_section")
    assert "membership_role(organization_id, true" in " ".join(workspace.split())


def test_exam_is_catalog_driven_cooled_down_and_does_not_return_keys() -> None:
    bootstrap = _function_body("creator_bootstrap")
    exam = _function_body("creator_submit_exam")

    assert "module.module_type = 'course'" in bootstrap
    assert "module.question_count" in bootstrap
    assert "module.pass_score" in bootstrap
    assert "next_attempt_at" in bootstrap
    assert "attempt_count_24h" in bootstrap
    assert "oldest_attempt_24h + interval '24 hours'" in bootstrap
    assert "cooldown_minutes" in bootstrap
    assert "prerequisite_required" in exam
    assert "declared_question_count" in exam
    assert "exam_cooldown_active" in exam
    assert "attempts_24h >= 5" in exam
    assert "exam_attempt_limit_active" in exam
    assert "make_interval(mins => cooldown_minutes)" in exam
    assert "request_payload := jsonb_build_object(" in exam
    assert exam.count("request_payload, result") >= 2
    assert "pg_advisory_xact_lock(" in exam
    assert exam.index("pg_advisory_xact_lock(") < exam.index("attempts_24h >= 5")
    assert "correct_answers" not in bootstrap
    assert "training_answer_keys" not in bootstrap
    assert "correct_answers" not in RPC_SQL.split("result := jsonb_build_object(", 1)[0]


def test_production_catalog_contains_no_tracked_answer_material() -> None:
    lowered = CATALOG_SQL.casefold()
    assert "training_answer_keys" not in lowered
    assert "correct_answers" not in lowered
    assert "rubric" not in lowered


def test_paid_generation_is_rejected_twice_and_never_persisted() -> None:
    core = (
        ROOT / "supabase/migrations/202607130001_content_factory_core.sql"
    ).read_text(encoding="utf-8")
    batch = _function_body("creator_create_mock_batch")

    assert "mock_only_required" in batch
    assert "p_payload -> 'allow_real_spend' is distinct from 'false'::jsonb" in batch
    assert "'provider_called', false" in batch
    assert "'paid_spend_minor', 0" in batch
    assert "exact_product_media_required" in batch
    assert "media.metadata ->> 'kind' in ('product_photo', 'packshot')" in batch
    assert "'placements_created', requested_count" in batch
    assert "payout_value > 1000000" in batch
    assert "check (mode = 'mock')" in core
    assert "check (allow_real_spend = false)" in core
    assert "check (estimated_cost_minor = 0)" in core
    assert "check (actual_cost_minor = 0)" in core


def test_privileged_money_and_alias_actions_have_explicit_roles() -> None:
    payout = " ".join(_function_body("creator_decide_payout").split())
    aliases = " ".join(_function_body("creator_set_wb_alias").split())

    assert "array['owner', 'admin']" in payout
    assert "self_payout_decision_forbidden" in payout
    assert "payout_must_be_approved_first" in payout
    assert "array['owner', 'admin', 'producer']" in aliases
    assert "wb_alias_product_immutable" in aliases
    assert "set status = 'replaced'" in aliases

    core = (
        ROOT / "supabase/migrations/202607130001_content_factory_core.sql"
    ).read_text(encoding="utf-8")
    assert "wb_article_aliases_one_active_uq" in core
    assert "where status = 'active'" in core
    assert "guard_wb_alias_history" in core


def test_team_rollup_is_owner_admin_only_and_contains_no_exam_answers() -> None:
    workspace = " ".join(_function_body("creator_workspace_section").split())

    assert "requested_section = 'team'" in workspace
    assert "actor_role <> all(array['owner', 'admin'])" in workspace
    for field in (
        "'profile_id'",
        "'courses_completed'",
        "'courses_required'",
        "'exam_passed'",
        "'tasks_total'",
        "'tasks_done'",
        "'published_count'",
    ):
        assert field in workspace
    assert "training_answer_keys" not in workspace
    assert "correct_answers" not in workspace


def test_bootstrap_is_fail_closed_and_never_autojoins_or_reactivates() -> None:
    bootstrap = _function_body("creator_bootstrap")
    assert "'state', 'membership_required'" in bootstrap
    assert "'membership_suspended'" in bootstrap
    assert "'membership_revoked'" in bootstrap
    assert "workspace_open', false" in bootstrap
    assert "insert into content_factory.memberships" not in bootstrap
    assert "insert into content_factory.organizations" not in bootstrap
    assert "do update set\n        status = 'active'" not in bootstrap


def test_system_onboarding_rpcs_are_service_role_only() -> None:
    for name in ("system_initialize_owner", "system_provision_invited_member"):
        assert re.search(
            rf"create\s+or\s+replace\s+function\s+public\.{name}"
            rf"\s*\(\s*p_payload\s+jsonb[^)]*\).*?security\s+definer"
            rf".*?set\s+search_path\s*=\s*''",
            RPC_SQL,
            flags=re.IGNORECASE | re.DOTALL,
        )
        assert re.search(
            rf"revoke\s+all\s+on\s+function\s+public\.{name}\(jsonb\)"
            rf"\s+from\s+public\s*,\s*anon\s*,\s*authenticated",
            RPC_SQL,
            flags=re.IGNORECASE,
        )
        assert re.search(
            rf"grant\s+execute\s+on\s+function\s+public\.{name}\(jsonb\)"
            rf"\s+to\s+service_role",
            RPC_SQL,
            flags=re.IGNORECASE,
        )
    assert "target_membership_history_conflict" in RPC_SQL
    assert "inviter_not_authorized" in RPC_SQL
    assert "'trainee'" in RPC_SQL


def test_storage_is_active_immutable_and_metadata_bound() -> None:
    lowered = STORAGE_SQL.casefold()
    assert "profile.status = 'active'" in lowered
    assert "organization.status = 'active'" in lowered
    assert "create policy contentengine_private_update" not in lowered
    assert "storage_object_is_unregistered" in lowered
    assert "contentengine_private_delete" in lowered

    register_media = _function_body("creator_register_media")
    assert "storage_object.metadata" in register_media
    assert "storage_metadata ->> 'size'" in register_media
    assert "storage_metadata ->> 'mimetype'" in register_media
    assert "storage_metadata_mismatch" in register_media
    assert "hashtext(bucket_value)" in register_media
    assert "media_row.product_id is distinct from product_id_value" in register_media


def test_workspace_collections_are_hard_capped() -> None:
    workspace = _function_body("creator_workspace_section")
    assert workspace.count("limit 100") >= 9
    assert "limit 200" in workspace
    assert "'cap', case when requested_section = 'team' then 200 else 100 end" in workspace


def test_placement_requires_separate_submit_review_and_confirmation() -> None:
    confirm = _function_body("creator_confirm_placement")
    transition = _function_body("creator_transition_task")
    assert "placement_self_confirmation_forbidden" in confirm
    assert "placement_review_required" in confirm
    assert "submitted_for_review" in confirm
    assert "task_row.status <> 'review'" in confirm
    assert "placement_confirmation_required" in transition
    assert "placement_submission_requires_final_url" in transition
    assert "task_row.task_type <> 'placement'" in transition


def test_mock_batch_requires_media_bound_to_same_product() -> None:
    batch = _function_body("creator_create_mock_batch")
    assert batch.count("media.product_id = product_id") >= 2
    assert "exact_product_media_mismatch" in batch
