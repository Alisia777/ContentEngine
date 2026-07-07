from __future__ import annotations

from app import models


class MarkdownRenderer:
    def render(self, brief: models.AIProductionBrief) -> str:
        scenes = sorted(brief.scene_blueprints, key=lambda item: item.scene_order)
        lines = [
            f"# AI Production Brief: {brief.sku}",
            "",
            "## Final Brief Contract",
            f"- Thesis: {brief.one_sentence_thesis or 'missing'}",
            f"- Viewer takeaway: {brief.viewer_takeaway or 'missing'}",
            f"- Buyer situation: {brief.buyer_situation or 'missing'}",
            f"- Main objection: {brief.main_objection or 'missing'}",
            f"- Reason to believe: {brief.reason_to_believe or 'missing'}",
            f"- Proof moment: {brief.proof_moment or 'missing'}",
            f"- CTA: {brief.cta or 'missing'}",
            f"- Product lock mode: {brief.product_lock_mode or 'missing'}",
            "",
            "## Must Show",
            *[f"- {item}" for item in (brief.must_show_json or [])],
            "",
            "## Must Say",
            *[f"- {item}" for item in (brief.must_say_json or [])],
            "",
            "## Must Avoid",
            *[f"- {item}" for item in (brief.must_avoid_json or [])],
            "",
            "## Scene Blueprint",
        ]
        for scene in scenes:
            lines.extend(
                [
                    "",
                    f"### Scene {scene.scene_order}: {scene.scene_role}",
                    f"- Timing: {scene.start_second:g}-{scene.end_second:g} sec",
                    f"- Viewer goal: {scene.viewer_goal or 'missing'}",
                    f"- Visual action: {scene.visual_action or 'missing'}",
                    f"- Spoken line: {scene.spoken_line or 'missing'}",
                    f"- On-screen text: {scene.onscreen_text or 'missing'}",
                    f"- Caption: {scene.caption_text or 'missing'}",
                    f"- Product visibility: {scene.product_visibility or 'missing'}",
                    f"- Must show: {', '.join(scene.must_show_json or []) or 'missing'}",
                    f"- Must avoid: {', '.join(scene.must_avoid_json or []) or 'missing'}",
                ]
            )
        lines.extend(
            [
                "",
                "## Failure Conditions",
                *[f"- {item}" for item in (brief.failure_conditions_json or [])],
            ]
        )
        return "\n".join(lines).strip() + "\n"
