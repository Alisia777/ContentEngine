from __future__ import annotations

from app import models
from app.output_acceptance.types import FAIL_STATUSES, PASS_STATUSES, OutputQualityResult


class OutputQualityChecker:
    def check(
        self,
        *,
        video_job: models.VideoJob,
        brief: models.AIProductionBrief,
        frame_result: models.FrameExtractionResult | None,
        decision: str = "needs_human_review",
        product_identity_status: str = "needs_review",
        packaging_status: str = "needs_review",
        geometry_status: str = "needs_review",
        blogger_authenticity_status: str = "needs_review",
        scene_match_status: str = "needs_review",
        proof_moment_status: str = "needs_review",
        cta_status: str = "needs_review",
    ) -> OutputQualityResult:
        statuses = {
            "product_identity_status": self._normalize(product_identity_status),
            "packaging_status": self._normalize(packaging_status),
            "geometry_status": self._normalize(geometry_status),
            "blogger_authenticity_status": self._normalize(blogger_authenticity_status),
            "scene_match_status": self._normalize(scene_match_status),
            "proof_moment_status": self._normalize(proof_moment_status),
            "cta_status": self._normalize(cta_status),
        }
        blockers: list[str] = []
        required_fixes: list[str] = []
        if not video_job.output_video_path:
            blockers.append("video_output_missing")
            required_fixes.append("download_or_attach_video_output")
        if not frame_result or not frame_result.contact_sheet_path:
            blockers.append("contact_sheet_missing")
            required_fixes.append("extract_frames_before_review")
        if statuses["product_identity_status"] not in PASS_STATUSES:
            blockers.append("human_review_required_for_product_identity")
            required_fixes.append("manual_product_identity_review")
        if statuses["packaging_status"] in FAIL_STATUSES:
            blockers.append("packaging_drift")
            required_fixes.append("regenerate_or_switch_to_packshot_overlay")
        if statuses["geometry_status"] in FAIL_STATUSES:
            blockers.append("geometry_drift")
            required_fixes.append("regenerate_with_geometry_feedback")
        if statuses["blogger_authenticity_status"] in FAIL_STATUSES:
            blockers.append("generic_ai_or_low_blogger_authenticity")
            required_fixes.append("rewrite_or_regenerate_blogger_context")
        if statuses["scene_match_status"] not in PASS_STATUSES:
            blockers.append("scene_blueprint_mismatch")
            required_fixes.append("match_output_to_scene_blueprint")
        if statuses["proof_moment_status"] not in PASS_STATUSES:
            blockers.append("missing_proof_moment")
            required_fixes.append("add_visible_proof_moment")
        if statuses["cta_status"] not in PASS_STATUSES:
            blockers.append("cta_missing_or_unclear")
            required_fixes.append("add_clear_cta_or_end_card")
        if not brief.scene_blueprints:
            blockers.append("scene_blueprint_missing")
            required_fixes.append("build_scene_blueprint")

        blockers = list(dict.fromkeys(blockers))
        required_fixes = list(dict.fromkeys(required_fixes))
        score = max(0, 100 - 10 * len(blockers) - 4 * len(required_fixes))
        if "contact_sheet_missing" in blockers:
            status = "blocked"
        elif decision == "reject":
            status = "rejected"
        elif blockers:
            status = "needs_regeneration"
        elif decision == "approve":
            status = "approved"
        else:
            status = "needs_human_review"
        publishing_readiness = "ready" if status == "approved" and not blockers else "blocked"
        return OutputQualityResult(
            status=status,
            publishing_readiness=publishing_readiness,
            score=score,
            blockers=blockers,
            required_fixes=required_fixes,
            normalized_statuses=statuses,
        )

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "needs_review").strip().lower()
