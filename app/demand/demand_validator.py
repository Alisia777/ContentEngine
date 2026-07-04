from __future__ import annotations

from app.demand.types import DemandHypothesis, DemandValidationReport


UNSAFE_PROMISE_TERMS = {
    "cure",
    "treat",
    "treatment",
    "medical treatment",
    "heal",
    "guaranteed result",
    "guaranteed",
}
AGGRESSIVE_CTA_TERMS = {"buy now", "last chance", "limited offer", "hurry", "urgent", "only today"}


class DemandValidator:
    def validate(
        self,
        hypothesis: DemandHypothesis,
        *,
        forbidden_claims: list[str] | None = None,
        reference_readiness_status: str | None = None,
        reference_blockers: list[str] | None = None,
    ) -> DemandValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        missing_data = list(hypothesis.missing_data)
        blockers: list[str] = []
        forbidden_claims = [claim.lower() for claim in (forbidden_claims or []) if claim]
        text = self._text(hypothesis)
        safe_promise = hypothesis.safe_promise.lower()

        unsafe_hits = [term for term in UNSAFE_PROMISE_TERMS if term in safe_promise]
        if unsafe_hits:
            errors.append("safe_promise contains unsafe medical, treatment, or guaranteed language.")
        forbidden_hits = [claim for claim in forbidden_claims if claim and claim in text]
        if forbidden_hits:
            errors.append("safe_promise or demand text contains forbidden claims.")
        if hypothesis.safe_promise and not hypothesis.source_refs:
            missing_data.append("safe_promise_missing_source_refs")
        if not hypothesis.proof_required or not hypothesis.source_refs:
            missing_data.append("missing_source_backed_proof")
        if hypothesis.stock_risk:
            aggressive_hits = [term for term in AGGRESSIVE_CTA_TERMS if term in text]
            if aggressive_hits:
                errors.append("stock_risk blocks aggressive CTA or urgency language.")
        if reference_readiness_status == "blocked":
            blockers.extend(reference_blockers or ["product_reference_readiness_blocked"])
            warnings.append("Blocked product references make real video generation ineligible.")

        status = "blocked" if errors else ("needs_data" if missing_data else "ready")
        real_video_eligible = status == "ready" and reference_readiness_status in {None, "ready"}
        return DemandValidationReport(
            status=status,
            valid=not errors,
            real_video_eligible=real_video_eligible,
            errors=list(dict.fromkeys(errors)),
            warnings=list(dict.fromkeys(warnings)),
            missing_data=list(dict.fromkeys(missing_data)),
            blocked_promises=list(dict.fromkeys(hypothesis.unsafe_promises_blocked + unsafe_hits + forbidden_hits)),
            blockers=list(dict.fromkeys(blockers)),
        )

    @staticmethod
    def _text(hypothesis: DemandHypothesis) -> str:
        values = [
            hypothesis.buyer_need,
            hypothesis.trigger_situation,
            hypothesis.pain_point,
            hypothesis.objection,
            hypothesis.safe_promise,
            hypothesis.recommended_first_frame,
            " ".join(hypothesis.recommended_hook_types),
        ]
        return " ".join(value for value in values if value).lower()
