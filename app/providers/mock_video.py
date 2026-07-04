from pathlib import Path
from uuid import uuid4

from app.intelligence.types import PromptPackOutput, ProviderVideoJob, ProviderVideoStatus


class MockGeneratorVideoProvider:
    provider_name = "mock"

    def create_generation(self, prompt_pack: PromptPackOutput) -> ProviderVideoJob:
        provider_job_id = f"mock-generator-video-{uuid4().hex[:12]}"
        return ProviderVideoJob(
            provider=self.provider_name,
            provider_job_id=provider_job_id,
            status="completed",
            raw_response={"scene_count": len(prompt_pack.scene_prompts)},
        )

    def get_status(self, provider_job_id: str) -> ProviderVideoStatus:
        return ProviderVideoStatus(provider_job_id=provider_job_id, status="completed")

    def download_outputs(self, provider_job_id: str, target_dir: Path) -> list[Path]:
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{provider_job_id}.txt"
        path.write_text("Mock generator video output placeholder.", encoding="utf-8")
        return [path]

