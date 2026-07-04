from __future__ import annotations

from datetime import datetime
import re

from sqlalchemy.orm import Session

from app import models
from app.enums import WorkflowStatus
from app.providers.llm import MockLLMClient


class ScriptEngine:
    def __init__(self, db: Session, llm_client: MockLLMClient | None = None):
        self.db = db
        self.llm_client = llm_client or MockLLMClient()

    def generate(self, product_id: int, template_id: int, brand_guide_id: int) -> models.ScriptJob:
        product = self.db.get(models.Product, product_id)
        template = self.db.get(models.CreativeTemplate, template_id)
        brand_guide = self.db.get(models.BrandGuide, brand_guide_id)
        if not product or not template or not brand_guide:
            missing = [
                name
                for name, value in {"product": product, "template": template, "brand_guide": brand_guide}.items()
                if not value
            ]
            raise ValueError(f"Missing input: {', '.join(missing)}")

        input_payload = {
            "product": self._model_payload(product),
            "template": self._model_payload(template),
            "brand_rules": self._model_payload(brand_guide),
        }
        script_json = self.llm_client.generate_script(input_payload)
        validation_report = self.llm_client.validate_script(
            script_json,
            input_payload["product"],
            input_payload["brand_rules"],
        )

        script_job = models.ScriptJob(
            product_id=product.id,
            template_id=template.id,
            brand_guide_id=brand_guide.id,
            status=WorkflowStatus.script_generated.value,
            input_payload_json=input_payload,
            output_script_json=script_json,
            validation_report_json=validation_report,
        )
        self.db.add(script_job)
        self.db.flush()

        variant = models.ScriptVariant(
            script_job_id=script_job.id,
            variant_number=1,
            creative_angle=script_json.get("creative_angle"),
            hook=script_json.get("hook"),
            key_message=script_json.get("key_message"),
            final_cta=script_json.get("final_cta"),
            full_script_json=script_json,
            status=WorkflowStatus.script_generated.value,
        )
        self.db.add(variant)
        self.db.flush()

        for scene in script_json.get("scenes", []):
            start, end = self._parse_time_range(scene.get("time_range", "0-3s"))
            self.db.add(
                models.Scene(
                    script_variant_id=variant.id,
                    scene_number=scene.get("scene_number", 1),
                    time_start=start,
                    time_end=end,
                    visual_description=scene.get("visual"),
                    voiceover=scene.get("voiceover"),
                    caption=scene.get("caption"),
                    video_prompt=scene.get("video_prompt"),
                    negative_prompt=scene.get("negative_prompt"),
                    source_fields_json=scene.get("source_fields") or [],
                )
            )

        self.db.commit()
        self.db.refresh(script_job)
        return script_job

    def validate(self, script_job: models.ScriptJob) -> dict:
        report = self.llm_client.validate_script(
            script_job.output_script_json,
            script_job.input_payload_json.get("product", {}),
            script_job.input_payload_json.get("brand_rules", {}),
        )
        script_job.validation_report_json = report
        self.db.commit()
        return report

    def approve_variant(self, variant: models.ScriptVariant, reviewer_name: str = "admin") -> models.ScriptVariant:
        variant.status = WorkflowStatus.script_approved.value
        variant.script_job.status = WorkflowStatus.script_approved.value
        self.db.add(
            models.Review(
                entity_type="script_variant",
                entity_id=variant.id,
                reviewer_name=reviewer_name,
                status="approved",
                comment="Script approved for video generation.",
            )
        )
        self.db.commit()
        self.db.refresh(variant)
        return variant

    def reject_variant(
        self,
        variant: models.ScriptVariant,
        reviewer_name: str = "admin",
        rejection_reason: str = "Needs revision",
    ) -> models.ScriptVariant:
        variant.status = "rejected"
        self.db.add(
            models.Review(
                entity_type="script_variant",
                entity_id=variant.id,
                reviewer_name=reviewer_name,
                status="rejected",
                rejection_reason=rejection_reason,
            )
        )
        self.db.commit()
        self.db.refresh(variant)
        return variant

    @staticmethod
    def _parse_time_range(value: str) -> tuple[float, float]:
        matches = re.findall(r"\d+(?:\.\d+)?", value)
        if len(matches) >= 2:
            return float(matches[0]), float(matches[1])
        return 0.0, 3.0

    @staticmethod
    def _model_payload(model) -> dict:
        payload = {}
        for column in model.__table__.columns:
            value = getattr(model, column.name)
            payload[column.name] = value.isoformat() if isinstance(value, datetime) else value
        return payload
