from app.intelligence.types import GeneratedSceneOutput, GeneratedScriptOutput, ScriptBriefOutput


class MockLLMProvider:
    provider_name = "mock"
    model = "mock-structured-script-v1"

    def generate_script(self, brief: ScriptBriefOutput) -> GeneratedScriptOutput:
        self.last_request_json = {"brief": brief.model_dump(mode="json")}
        claim = brief.allowed_claims[0] if brief.allowed_claims else None
        claim_text = claim.claim if claim else "Add verified product benefit before publishing."
        claim_ref = f"product.{claim.source_key}" if claim else "needs_data.product.benefits_json"
        scene_count = max(1, brief.scene_count)
        scene_duration = max(2, brief.duration_seconds // scene_count)
        scenes = []
        for index in range(scene_count):
            start = index * scene_duration
            end = brief.duration_seconds if index == scene_count - 1 else start + scene_duration
            scenes.append(
                GeneratedSceneOutput(
                    scene_number=index + 1,
                    time_start=float(start),
                    time_end=float(end),
                    visual_description=f"{brief.creative_angle} scene for {brief.product_title}",
                    voiceover=claim_text if index == 1 else brief.reasoning_summary[:120],
                    caption=claim_text if index == 1 else brief.creative_angle.replace("_", " ").title(),
                    claim_refs=[claim_ref] if claim else [],
                    video_prompt=(
                        f"Vertical {brief.aspect_ratio} realistic product video, "
                        f"{brief.creative_angle}, clear product framing, scene {index + 1}"
                    ),
                    negative_prompt="unsupported claims, distorted product, unreadable text, low quality",
                )
            )
        output = GeneratedScriptOutput(
            creative_angle=brief.creative_angle,
            hook=f"{brief.product_title}: what should shoppers understand first?",
            key_message=claim_text,
            scenes=scenes,
            final_cta="Open the product card",
            compliance_notes=["Generated from source-backed ScriptBrief."],
            missing_data_notes=brief.missing_data,
        )
        self.last_response_json = output.model_dump(mode="json")
        return output
