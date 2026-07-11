from __future__ import annotations

from typing import Sequence

from app import models
from app.output_acceptance.types import FAIL_STATUSES, PASS_STATUSES, OutputQualityResult
from app.visual_evidence import ReferenceTextInput, VisualEvidencePolicy, VisualEvidenceService


BLOCKING_FRAME_WARNING_MARKERS = (
    "synthetic",
    "placeholder",
    "ffmpeg_extract_failed",
    "video_file_missing",
)


class OutputQualityChecker:
    def __init__(self, visual_evidence_service: VisualEvidenceService | None = None):
        self.visual_evidence_service = visual_evidence_service or VisualEvidenceService()

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
        visual_references: Sequence[ReferenceTextInput | dict] | None = None,
        visual_policy: VisualEvidencePolicy | dict | None = None,
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
        frame_blockers = self._frame_integrity_blockers(frame_result)
        if frame_blockers:
            blockers.extend(frame_blockers)
            required_fixes.append("attach_decodable_non_placeholder_video_output")
        resolved_references, resolved_policy = self._visual_contract(
            brief,
            references=visual_references,
            policy=visual_policy,
        )
        visual_evidence = self.visual_evidence_service.evaluate_frame_result(
            frame_result,
            references=resolved_references,
            policy=resolved_policy,
        )
        blockers.extend(visual_evidence.blockers)
        required_fixes.extend(visual_evidence.required_fixes)
        if str(getattr(video_job, "provider", "") or "").strip().lower() == "mock":
            blockers.append("mock_video_output_not_publishable")
            required_fixes.append("generate_or_attach_real_video_output")
        if statuses["product_identity_status"] not in PASS_STATUSES:
            blockers.append("human_review_required_for_product_identity")
            required_fixes.append("manual_product_identity_review")
        if statuses["packaging_status"] not in PASS_STATUSES:
            blockers.append(
                "packaging_drift"
                if statuses["packaging_status"] in FAIL_STATUSES
                else "human_review_required_for_packaging"
            )
            required_fixes.append("regenerate_or_switch_to_packshot_overlay")
        if statuses["geometry_status"] not in PASS_STATUSES:
            blockers.append(
                "geometry_drift"
                if statuses["geometry_status"] in FAIL_STATUSES
                else "human_review_required_for_geometry"
            )
            required_fixes.append("regenerate_with_geometry_feedback")
        if statuses["blogger_authenticity_status"] not in PASS_STATUSES:
            blockers.append(
                "generic_ai_or_low_blogger_authenticity"
                if statuses["blogger_authenticity_status"] in FAIL_STATUSES
                else "human_review_required_for_blogger_authenticity"
            )
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
            visual_evidence=visual_evidence,
        )

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "needs_review").strip().lower()

    @staticmethod
    def _frame_integrity_blockers(frame_result: models.FrameExtractionResult | None) -> list[str]:
        if not frame_result:
            return []
        blockers = [
            str(warning).strip()
            for warning in (frame_result.warnings_json or [])
            if str(warning).strip()
            and any(marker in str(warning).strip().lower() for marker in BLOCKING_FRAME_WARNING_MARKERS)
        ]
        if any("synthetic_frame" in str(path).lower() for path in (frame_result.frame_paths_json or [])):
            blockers.append("synthetic_frames_used_no_cv")
        if any("placeholder_frame" in str(path).lower() for path in (frame_result.frame_paths_json or [])):
            blockers.append("placeholder_frames_not_publishable")
        return list(dict.fromkeys(blockers))

    @staticmethod
    def _visual_contract(
        brief: models.AIProductionBrief | object,
        *,
        references: Sequence[ReferenceTextInput | dict] | None,
        policy: VisualEvidencePolicy | dict | None,
    ) -> tuple[list[ReferenceTextInput | dict], VisualEvidencePolicy | dict | None]:
        rules = getattr(brief, "product_identity_rules_json", None) or {}
        if not isinstance(rules, dict):
            rules = {}
        contract = rules.get("visual_evidence_contract") or {}
        if not isinstance(contract, dict):
            contract = {}
        contract_requires_ocr = contract.get("ocr_required") is True or rules.get("ocr_required") is True
        if policy is None:
            resolved_policy: VisualEvidencePolicy | dict | None = contract or None
            if resolved_policy is None and rules.get("ocr_required") is not None:
                resolved_policy = {"ocr_required": rules.get("ocr_required")}
        elif isinstance(policy, VisualEvidencePolicy):
            resolved_policy = policy.model_copy(
                update={"ocr_required": True}
                if contract_requires_ocr and not policy.ocr_required
                else None
            )
        else:
            resolved_policy = dict(policy)
            if contract_requires_ocr:
                resolved_policy["ocr_required"] = True

        tokens = contract.get("required_packaging_tokens") or rules.get("required_packaging_tokens") or []
        if isinstance(tokens, str):
            tokens = [tokens]
        declared_text = contract.get("reference_packaging_text") or rules.get("reference_packaging_text")
        asset_path = contract.get("reference_product_asset_path") or rules.get("reference_product_asset_path")
        asset_id = contract.get("reference_product_asset_id") or rules.get("reference_product_asset_id")
        resolved_references: list[ReferenceTextInput | dict] = []
        if any((tokens, declared_text, asset_path, asset_id)):
            resolved_references.append(
                ReferenceTextInput(
                    source_kind="product_asset" if asset_id or asset_path else "product_input",
                    source_ref=f"product_asset:{asset_id}" if asset_id else "ai_production_brief:packaging_text",
                    required_tokens=list(tokens),
                    declared_text=str(declared_text) if declared_text else None,
                    asset_path=str(asset_path) if asset_path else None,
                )
            )
        resolved_references.extend(list(references or []))
        return resolved_references, resolved_policy
