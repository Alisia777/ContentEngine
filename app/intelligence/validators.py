from app.intelligence.errors import ClaimValidationError
from app.intelligence.types import GeneratedScriptOutput, ScriptBriefOutput


def validate_script_claim_refs(script: GeneratedScriptOutput, brief: ScriptBriefOutput) -> dict:
    allowed_refs = {claim.source_key for claim in brief.allowed_claims}
    errors: list[str] = []
    for scene in script.scenes:
        for ref in scene.claim_refs:
            normalized = ref.replace("product.", "")
            if normalized not in allowed_refs:
                errors.append(f"Scene {scene.scene_number} has unsupported claim ref: {ref}")
    if errors:
        raise ClaimValidationError("; ".join(errors))
    return {"valid": True, "checked_claim_refs": sorted(allowed_refs)}

