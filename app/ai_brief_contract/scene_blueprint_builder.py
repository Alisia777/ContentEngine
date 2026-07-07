from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.ai_brief_contract.errors import AIBriefContractDataError
from app.ai_brief_contract.markdown_renderer import MarkdownRenderer
from app.ai_brief_contract.types import REQUIRED_SCENE_TIMELINE, SceneBlueprintOutput


class SceneBlueprintBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(self, ai_production_brief_id: int) -> list[models.SceneBlueprint]:
        brief = self.db.get(models.AIProductionBrief, ai_production_brief_id)
        if not brief:
            raise AIBriefContractDataError(f"AIProductionBrief {ai_production_brief_id} not found.")
        self.db.query(models.SceneBlueprint).filter(
            models.SceneBlueprint.ai_production_brief_id == brief.id
        ).delete()
        script_scenes = {scene.get("role"): scene for scene in (brief.ugc_script.scene_script_json if brief.ugc_script else [])}
        rows: list[models.SceneBlueprint] = []
        for index, slot in enumerate(REQUIRED_SCENE_TIMELINE, start=1):
            role = slot["role"]
            source = script_scenes.get(role) or {}
            row = models.SceneBlueprint(
                ai_production_brief_id=brief.id,
                scene_order=index,
                scene_role=role,
                start_second=slot["start"],
                end_second=slot["end"],
                viewer_goal=self._viewer_goal(role, brief),
                visual_action=source.get("visual_direction") or self._visual_action(role, brief),
                spoken_line=source.get("spoken_line") or self._fallback_line(role, brief),
                onscreen_text=source.get("onscreen_text") or source.get("caption") or self._onscreen(role),
                caption_text=source.get("caption") or self._onscreen(role),
                product_visibility=self._product_visibility(role, brief.product_lock_mode),
                camera_framing=self._camera_framing(role),
                broll_notes=self._broll(role, brief.product_lock_mode),
                transition_notes=self._transition(role),
                must_show_json=self._must_show(role, brief),
                must_avoid_json=self._must_avoid(role, brief),
            )
            self.db.add(row)
            rows.append(row)
        brief.scene_count = len(rows)
        brief.duration_seconds = 15
        self.db.flush()
        brief.brief_markdown = MarkdownRenderer().render(brief)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def latest_for_brief(self, ai_production_brief_id: int) -> list[models.SceneBlueprint]:
        return self.db.scalars(
            select(models.SceneBlueprint)
            .where(models.SceneBlueprint.ai_production_brief_id == ai_production_brief_id)
            .order_by(models.SceneBlueprint.scene_order)
        ).all()

    @staticmethod
    def as_output(scene: models.SceneBlueprint) -> SceneBlueprintOutput:
        return SceneBlueprintOutput(
            id=scene.id,
            ai_production_brief_id=scene.ai_production_brief_id,
            scene_order=scene.scene_order,
            scene_role=scene.scene_role,
            start_second=scene.start_second,
            end_second=scene.end_second,
            viewer_goal=scene.viewer_goal,
            visual_action=scene.visual_action,
            spoken_line=scene.spoken_line,
            onscreen_text=scene.onscreen_text,
            caption_text=scene.caption_text,
            product_visibility=scene.product_visibility,
            camera_framing=scene.camera_framing,
            broll_notes=scene.broll_notes,
            transition_notes=scene.transition_notes,
            must_show=scene.must_show_json or [],
            must_avoid=scene.must_avoid_json or [],
        )

    @staticmethod
    def _viewer_goal(role: str, brief: models.AIProductionBrief) -> str:
        goals = {
            "hook": brief.viewer_takeaway or "Make the viewer understand the buyer situation.",
            "personal_context": brief.buyer_situation or "Show why this creator personally cares.",
            "product_reason": brief.reason_to_believe or "Explain why this exact product fits.",
            "proof_demo": brief.proof_moment or "Prove the claim with visible product/use-case context.",
            "cta": brief.cta or "Give a clear next step.",
        }
        return goals[role]

    @staticmethod
    def _visual_action(role: str, brief: models.AIProductionBrief) -> str:
        actions = {
            "hook": "Creator opens with a natural first-person line in a realistic vertical frame.",
            "personal_context": "Creator shows the everyday context where the product becomes relevant.",
            "product_reason": "Creator points to the reason this exact item fits the moment.",
            "proof_demo": "Creator shows proof/use-case without changing the product identity.",
            "cta": "End on exact product packshot/end-card and product-card CTA.",
        }
        return actions[role]

    @staticmethod
    def _fallback_line(role: str, brief: models.AIProductionBrief) -> str:
        lines = {
            "hook": brief.viewer_takeaway or "I found this for a real everyday moment.",
            "personal_context": brief.buyer_situation or "I use it in a normal routine moment.",
            "product_reason": brief.reason_to_believe or "That is why this exact product makes sense here.",
            "proof_demo": brief.proof_moment or "I show the real product context and proof moment.",
            "cta": brief.cta or "Check the product card if this fits your routine.",
        }
        return lines[role]

    @staticmethod
    def _onscreen(role: str) -> str:
        return {
            "hook": "Real find",
            "personal_context": "Why I picked it",
            "product_reason": "Why this one",
            "proof_demo": "Proof moment",
            "cta": "See product card",
        }[role]

    @staticmethod
    def _product_visibility(role: str, lock_mode: str | None) -> str:
        if lock_mode == "packshot_overlay":
            if role == "cta":
                return "Use real approved packshot as end card; do not generate packaging."
            return "Contextual human action allowed; exact packaging appears only as real packshot overlay."
        if lock_mode == "end_card_packshot":
            return "Generated scenes may show lifestyle context; exact product appears only on real packshot end card."
        if lock_mode == "reference_i2v":
            return "Use approved product reference image; preserve identity and geometry; human review required."
        return "No exact product generation; use context only until references are approved."

    @staticmethod
    def _camera_framing(role: str) -> str:
        return "vertical 9:16, handheld realistic UGC, product readable when visible" if role != "cta" else "stable end-card framing"

    @staticmethod
    def _broll(role: str, lock_mode: str | None) -> str:
        if role == "proof_demo":
            return "Show texture/use-case proof; keep exact packaging controlled by product visibility policy."
        return f"Support the scene role without violating product lock mode:{lock_mode}"

    @staticmethod
    def _transition(role: str) -> str:
        return "natural cut; no jarring montage"

    @staticmethod
    def _must_show(role: str, brief: models.AIProductionBrief) -> list[str]:
        base = [role, "first-person creator delivery"]
        if role in {"proof_demo", "cta"}:
            base.append(brief.proof_moment or "proof moment")
        return list(dict.fromkeys([*base, *(brief.must_show_json or [])[:3]]))

    @staticmethod
    def _must_avoid(role: str, brief: models.AIProductionBrief) -> list[str]:
        return list(dict.fromkeys([*(brief.must_avoid_json or [])[:8], "generic ad voice", "unsupported claim"]))
