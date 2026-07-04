from app.creative.types import QualityRubric, QualityRubricItem


def default_quality_rubric(reference_images_required: bool) -> QualityRubric:
    items = [
        QualityRubricItem(key="output_file_exists", label="Output file exists"),
        QualityRubricItem(key="output_file_non_empty", label="Output file is non-empty"),
        QualityRubricItem(key="generation_report_exists", label="Generation report exists"),
        QualityRubricItem(key="provider_status_successful", label="Provider status is successful"),
        QualityRubricItem(key="scene_captions_exist", label="Scene captions exist"),
        QualityRubricItem(key="cta_exists", label="CTA exists"),
        QualityRubricItem(key="forbidden_claims_not_used", label="Forbidden claims are not used"),
        QualityRubricItem(key="first_frame_requirements_exist", label="First-frame requirements exist in prompts"),
    ]
    if reference_images_required:
        items.append(QualityRubricItem(key="reference_image_included", label="Reference image is included"))
    return QualityRubric(
        items=items,
        notes=["Metadata-only score. It does not claim visual inspection or packaging accuracy verification."],
    )
