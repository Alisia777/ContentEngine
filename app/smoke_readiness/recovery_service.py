from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.assets.asset_storage import ProductAssetStorage
from app.control_room import ControlRoomSnapshotService
from app.engine_audit import EngineAuditScorecardService
from app.intelligence.errors import IntelligenceError
from app.intelligence.safety import provider_key_status
from app.one_video_acceptance import OneVideoAcceptanceError, OneVideoAcceptanceService
from app.smoke_readiness.blocker_service import SmokeReadinessBlockerService
from app.smoke_readiness.readiness_report_service import ReadinessReportService
from app.smoke_readiness.types import SmokeReadinessBlockerOutput
from app.video_generator.errors import VideoGeneratorError


DEMO_SKU = "BOMBBAR-PRO-DUBAI-MANGO-KUNAFA"


class RecoveryService:
    def __init__(self, db: Session):
        self.db = db

    def recover(
        self,
        *,
        plan_id: int | None = None,
        product_id: int | None = None,
        sku: str | None = None,
        platform: str = "Instagram Reels",
        video_provider: str = "runway",
        rebuild_plan: bool = False,
        seed_demo: bool = False,
        seed_demo_refs: bool = False,
        runway_credits_confirmed: bool = False,
    ) -> models.SmokeReadinessRun:
        run = models.SmokeReadinessRun(
            status="started",
            product_id=product_id,
            sku=sku,
            report_json={
                "requested_plan_id": plan_id,
                "requested_plan_exists": False,
                "rebuilt_plan_id": None,
                "prompt_only_status": "not_run",
                "runway_credits_confirmed": runway_credits_confirmed,
            },
        )
        self.db.add(run)
        self.db.flush()

        blockers: list[SmokeReadinessBlockerOutput] = []
        next_actions: list[str] = []
        facts = dict(run.report_json or {})
        plan = self._requested_plan(plan_id)
        if plan:
            facts["requested_plan_exists"] = True
            product_id = plan.product_id
            sku = plan.sku
            run.product_id = plan.product_id
            run.sku = plan.sku
            run.one_video_render_plan_id = plan.id
            run.prompt_pack_id = plan.prompt_pack_id
        elif plan_id is not None and not rebuild_plan:
            blockers.append(
                SmokeReadinessBlockerOutput(
                    blocker_type="missing_plan",
                    severity="blocker",
                    message=f"OneVideoRenderPlan {plan_id} does not exist in this database.",
                    recommended_action="Run with --product-id and --rebuild-plan, or seed demo data explicitly.",
                )
            )
            next_actions.append("rebuild_one_video_plan_or_select_existing_plan")

        if not plan and rebuild_plan:
            product = self._resolve_product(product_id=product_id, sku=sku, seed_demo=seed_demo)
            if not product:
                blocker_type = "product_seed_required" if seed_demo is False else "missing_product"
                blockers.append(
                    SmokeReadinessBlockerOutput(
                        blocker_type=blocker_type,
                        severity="blocker",
                        message="No product is available for one-video plan rebuild.",
                        recommended_action="Pass --product-id for an existing product or --seed-demo to create the Bombbar demo SKU.",
                    )
                )
                next_actions.append("seed_or_select_product_before_rebuild")
            else:
                run.product_id = product.id
                run.sku = product.sku
                if seed_demo_refs:
                    self._seed_demo_refs(product.id)
                try:
                    plan = OneVideoAcceptanceService(self.db).build_plan(
                        product.id,
                        platform=platform,
                        duration_seconds=15,
                        provider=video_provider,
                    )
                    facts["rebuilt_plan_id"] = plan.id
                    run.one_video_render_plan_id = plan.id
                    run.prompt_pack_id = plan.prompt_pack_id
                    run.product_id = plan.product_id
                    run.sku = plan.sku
                except (OneVideoAcceptanceError, IntelligenceError) as exc:
                    blockers.append(
                        SmokeReadinessBlockerOutput(
                            blocker_type="plan_rebuild_failed",
                            severity="blocker",
                            message=str(exc),
                            recommended_action="Fix product/reference data, then rerun smoke readiness recovery.",
                        )
                    )
                    next_actions.append("fix_plan_rebuild_input")

        if plan:
            self._add_reference_blockers(plan, blockers, next_actions)
            try:
                if plan.status == "prompt_only_ready" and plan.prompt_pack_id:
                    facts["prompt_only_status"] = "already_ready"
                else:
                    plan = OneVideoAcceptanceService(self.db).prompt_only(plan.id, provider=video_provider)
                    facts["prompt_only_status"] = "prompt_only_ready"
                run.prompt_pack_id = plan.prompt_pack_id
                run.one_video_render_plan_id = plan.id
                run.product_id = plan.product_id
                run.sku = plan.sku
            except (OneVideoAcceptanceError, VideoGeneratorError, IntelligenceError) as exc:
                facts["prompt_only_status"] = "failed"
                blockers.append(
                    SmokeReadinessBlockerOutput(
                        blocker_type="prompt_only_failed",
                        severity="blocker",
                        message=str(exc),
                        recommended_action="Fix one-video prompt-only path before any paid provider call.",
                    )
                )
                next_actions.append("fix_prompt_only_before_paid_smoke")

            refreshed_plan = self.db.get(models.OneVideoRenderPlan, plan.id)
            if refreshed_plan:
                facts["reference_policy_status"] = ReadinessReportService._reference_policy(refreshed_plan)
                facts["scene_policy_status"] = ReadinessReportService._scene_policy(refreshed_plan)
                facts["mvp_scorecard"] = (refreshed_plan.prompt_preview_json or {}).get("mvp_scorecard") or {}

        self._add_environment_blockers(
            blockers,
            next_actions,
            video_provider=video_provider,
            runway_credits_confirmed=runway_credits_confirmed,
        )

        blockers = SmokeReadinessBlockerService.dedupe(blockers)
        next_actions = list(dict.fromkeys(next_actions + [blocker.recommended_action for blocker in blockers]))
        final_decision = ReadinessReportService._final_decision(blockers)
        run.status = self._run_status(final_decision, blockers, facts)
        run.blockers_json = SmokeReadinessBlockerService.to_json(blockers)
        run.next_actions_json = next_actions
        facts["final_decision"] = final_decision
        run.report_json = facts
        self._replace_blocker_rows(run, blockers)
        self.db.flush()

        audit_run = EngineAuditScorecardService(self.db).run()
        snapshot = ControlRoomSnapshotService(self.db).refresh(role="owner")
        run.engine_audit_run_id = audit_run.id
        run.control_room_snapshot_id = snapshot.id
        self.db.commit()
        self.db.refresh(run)
        run.report_json = {
            **(run.report_json or {}),
            "engine_audit_run_id": run.engine_audit_run_id,
            "control_room_snapshot_id": run.control_room_snapshot_id,
        }
        self.db.commit()
        self.db.refresh(run)
        return run

    @staticmethod
    def _run_status(final_decision: str, blockers: list[SmokeReadinessBlockerOutput], facts: dict) -> str:
        if final_decision == "ready_for_paid_smoke":
            return "ready"
        blocker_types = {blocker.blocker_type for blocker in blockers}
        if blocker_types.intersection({"plan_rebuild_failed", "prompt_only_failed"}):
            return "failed"
        if facts.get("rebuilt_plan_id"):
            return "rebuilt"
        return "blocked"

    def _requested_plan(self, plan_id: int | None) -> models.OneVideoRenderPlan | None:
        if plan_id is None:
            return None
        return self.db.get(models.OneVideoRenderPlan, plan_id)

    def _resolve_product(self, *, product_id: int | None, sku: str | None, seed_demo: bool) -> models.Product | None:
        product = self.db.get(models.Product, product_id) if product_id else None
        if product:
            return product
        if sku:
            product = self.db.scalar(select(models.Product).where(models.Product.sku == sku))
            if product:
                return product
        if not seed_demo:
            return None
        product = self.db.scalar(select(models.Product).where(models.Product.sku == DEMO_SKU))
        if product:
            return product
        product = models.Product(
            sku=DEMO_SKU,
            brand="Bombbar",
            marketplace="Wildberries",
            title="Bombbar PRO DUBAI Mango & Kunafa protein delicious bar",
            description="Demo product for one-video smoke readiness. Chocolate bar with mango and kunafa filling inside.",
            category="Sports nutrition snack",
            attributes_json={"flavor": "Mango & Kunafa", "format": "chocolate bar with filling", "weight": "45 g"},
            benefits_json=["dessert-style snack format", "convenient to take with coffee or on the go"],
            images_json=[],
            reviews_json=[],
            restrictions_json=["no weight-loss claims", "no medical claims", "human review required"],
            product_url="https://example.com/bombbar-pro-dubai",
        )
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def _seed_demo_refs(self, product_id: int) -> None:
        existing = self.db.scalars(select(models.ProductAsset).where(models.ProductAsset.product_id == product_id)).all()
        approved_types = {asset.asset_type for asset in existing if asset.review_status == "approved"}
        storage = ProductAssetStorage(self.db)
        if "packshot" not in approved_types:
            primary = storage.attach_url(
                product_id,
                url="https://example.com/bombbar-pro-dubai-wrapper-front.png",
                asset_type="packshot",
                manual_label="demo approved wrapper front",
                is_primary_reference=True,
            )
            storage.update_asset(primary.id, review_status="approved", is_primary_reference=True)
        if "label_closeup" not in approved_types:
            label = storage.attach_url(
                product_id,
                url="https://example.com/bombbar-pro-dubai-label-closeup.png",
                asset_type="label_closeup",
                manual_label="demo approved label closeup",
            )
            storage.update_asset(label.id, review_status="approved", asset_type="label_closeup")

    def _add_reference_blockers(
        self,
        plan: models.OneVideoRenderPlan,
        blockers: list[SmokeReadinessBlockerOutput],
        next_actions: list[str],
    ) -> None:
        policy = plan.product_scene_policy_json or {}
        contract = policy.get("asset_contract") or {}
        tier = contract.get("tier") or {}
        requirement = contract.get("requirement") or {}
        ref_policy = policy.get("reference_policy") or {}
        reference_blockers = list(dict.fromkeys([*(plan.blockers_json or []), *(ref_policy.get("blockers") or [])]))
        if reference_blockers:
            blockers.append(
                SmokeReadinessBlockerOutput(
                    blocker_type="missing_refs",
                    severity="blocker",
                    message="Product reference policy is not ready for strict paid smoke.",
                    recommended_action="Attach and approve at least front packshot and label/packaging closeup before paid smoke.",
                )
            )
        if (policy.get("wrapper_reference_count") or 0) < 2:
            blockers.append(
                SmokeReadinessBlockerOutput(
                    blocker_type="missing_refs",
                    severity="blocker",
                    message="Wrapper reference count is below the strict identity threshold.",
                    recommended_action="Add a second approved wrapper or label reference.",
                )
            )
        if requirement and requirement.get("status") != "ready":
            blockers.append(
                SmokeReadinessBlockerOutput(
                    blocker_type="asset_contract_tier_below_required",
                    severity="blocker",
                    message=(
                        f"Product Asset Contract is {tier.get('current_tier', 'tier_0')}; "
                        f"{requirement.get('required_tier', 'tier_2')} is required for {requirement.get('purpose', 'final_ad')}."
                    ),
                    recommended_action="Attach and approve the exact missing identity/use-case assets for this SKU variant.",
                )
            )
            next_actions.append("complete_product_asset_contract_before_paid_smoke")
        if tier.get("variant_mismatch_asset_ids"):
            blockers.append(
                SmokeReadinessBlockerOutput(
                    blocker_type="variant_identity_mismatch",
                    severity="blocker",
                    message="Identity-sensitive references are unverified or belong to another product variant.",
                    recommended_action="Tag each product asset with the exact variant_key and remove mismatched flavor/color/model refs.",
                )
            )
            next_actions.append("separate_product_variant_reference_sets")
        for action in policy.get("next_actions") or []:
            next_actions.append(action)

    @staticmethod
    def _add_environment_blockers(
        blockers: list[SmokeReadinessBlockerOutput],
        next_actions: list[str],
        *,
        video_provider: str,
        runway_credits_confirmed: bool,
    ) -> None:
        status = provider_key_status()
        if status["generation_mode"] != "real":
            blockers.append(
                SmokeReadinessBlockerOutput(
                    blocker_type="generation_mode_not_real",
                    severity="blocker",
                    message="QVF_GENERATION_MODE is not real.",
                    recommended_action="Set QVF_GENERATION_MODE=real only when the operator is ready for a paid smoke.",
                )
            )
            next_actions.append("set_generation_mode_real_for_paid_smoke")
        if not status["allow_real_spend"]:
            blockers.append(
                SmokeReadinessBlockerOutput(
                    blocker_type="spend_gate_off",
                    severity="blocker",
                    message="QVF_ALLOW_REAL_SPEND is disabled.",
                    recommended_action="Keep disabled until the prompt-only plan is accepted, then set QVF_ALLOW_REAL_SPEND=true for one paid smoke.",
                )
            )
            next_actions.append("confirm_real_spend_gate")
        if video_provider == "runway" and not status["runway_api_secret_configured"]:
            blockers.append(
                SmokeReadinessBlockerOutput(
                    blocker_type="runway_key_missing",
                    severity="blocker",
                    message="Runway key is not configured.",
                    recommended_action="Set RUNWAYML_API_SECRET in the local operator environment; never paste it into reports or UI.",
                )
            )
            next_actions.append("configure_runway_secret")
        if video_provider == "runway" and not runway_credits_confirmed:
            blockers.append(
                SmokeReadinessBlockerOutput(
                    blocker_type="runway_credits_unconfirmed",
                    severity="warning",
                    message="Runway credits were not explicitly confirmed for this readiness run.",
                    recommended_action="Confirm Runway credits manually before one paid smoke.",
                )
            )
            next_actions.append("confirm_runway_credits")

    def _replace_blocker_rows(
        self,
        run: models.SmokeReadinessRun,
        blockers: list[SmokeReadinessBlockerOutput],
    ) -> None:
        for existing in list(run.blockers):
            self.db.delete(existing)
        self.db.flush()
        for blocker in blockers:
            self.db.add(
                models.SmokeReadinessBlocker(
                    smoke_readiness_run_id=run.id,
                    blocker_type=blocker.blocker_type,
                    severity=blocker.severity,
                    message=blocker.message,
                    recommended_action=blocker.recommended_action,
                )
            )
