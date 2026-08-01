from app.competitive_intelligence import SourceRelationship
from app.video_localization import (
    LocalizationMode,
    LocalizationProvider,
    VideoSource,
    build_localization_batch,
)


def test_heygen_audio_override_uses_current_translation_rate() -> None:
    source = VideoSource(
        source_id="harly-rate-card",
        sku="HARLY-1",
        category_key="hair_styling",
        duration_seconds=8,
        source_language="ru",
        source_relationship=SourceRelationship.OWNED,
        rights_confirmed=True,
        qa_approved=True,
        asset_sha256="9" * 64,
        speech_present=True,
    )

    plan = build_localization_batch(
        [source],
        target_languages=["en"],
        modes=[LocalizationMode.DUB_AUDIO],
        target_count=1,
        qa_gate_after_sequence=1,
        provider_overrides={
            LocalizationMode.DUB_AUDIO: LocalizationProvider.HEYGEN_AUDIO,
        },
    )

    assert plan.assignments[0].provider is LocalizationProvider.HEYGEN_AUDIO
    assert plan.assignments[0].estimated_cost_microusd == 266_400
