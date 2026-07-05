from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.content_factory.types import AIReviewResult


class AIContentReviewService:
    def __init__(self, db: Session):
        self.db = db

    def review(self, content_run: models.ContentRun) -> models.AIContentReview:
        result = self.evaluate(content_run)
        review = models.AIContentReview(
            content_run_id=content_run.id,
            status=result.status,
            score=result.score,
            human_review_required=result.human_review_required,
            review_json=result.model_dump(mode="json"),
            blockers_json=result.blockers,
            warnings_json=result.warnings,
        )
        self.db.add(review)
        self.db.flush()
        content_run.latest_ai_review_id = review.id
        if result.status == "blocked":
            content_run.status = "blocked"
        elif result.human_review_required:
            content_run.status = "needs_human_review"
        self.db.commit()
        self.db.refresh(review)
        return review

    def evaluate(self, content_run: models.ContentRun) -> AIReviewResult:
        run = content_run.run_json or {}
        prompt_pack = run.get("prompt_pack") or {}
        readiness = run.get("reference_readiness") or {}
        checks = [
            self._check("demand_hypothesis_created", bool(content_run.demand_hypothesis_id)),
            self._check("creative_spec_created", bool(content_run.creative_spec_id)),
            self._check("selected_variant_created", bool(content_run.selected_variant_id)),
            self._check("prompt_pack_created", bool(content_run.prompt_pack_id)),
            self._check("reference_readiness_known", bool(readiness.get("status"))),
            self._check("prompt_has_scene_prompts", bool(prompt_pack.get("scene_prompts"))),
            self._check("safe_promise_exists", bool(run.get("safe_promise"))),
        ]
        blockers = []
        if not content_run.prompt_pack_id:
            blockers.append("prompt_pack_missing")
        if readiness.get("status") not in {"ready", "blocked", "missing"}:
            blockers.append("reference_readiness_unknown")
        if readiness.get("status") != "ready":
            blockers.extend(f"reference:{item}" for item in readiness.get("blockers") or [])

        passed = sum(1 for check in checks if check["passed"])
        score = round(passed / len(checks), 3) if checks else 0
        status = "blocked" if not content_run.prompt_pack_id else "needs_human_review"
        warnings = list(content_run.warnings_json or [])
        notes = [
            "Rules-based AI review only.",
            "No computer vision inspection was performed.",
            "Visual product identity, packaging geometry, and output quality require human review.",
        ]
        return AIReviewResult(
            status=status,
            score=score,
            human_review_required=True,
            checks=checks,
            blockers=list(dict.fromkeys(blockers)),
            warnings=list(dict.fromkeys(warnings)),
            notes=notes,
        )

    @staticmethod
    def _check(key: str, passed: bool) -> dict:
        return {"key": key, "passed": bool(passed), "check_type": "metadata"}
