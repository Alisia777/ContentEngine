from pathlib import Path

from app.intelligence.errors import ProviderConfigurationError
from app.intelligence.types import PromptPackOutput, ProviderVideoJob, ProviderVideoStatus


class GeminiVideoProvider:
    provider_name = "gemini"

    def create_generation(self, prompt_pack: PromptPackOutput) -> ProviderVideoJob:
        raise ProviderConfigurationError("Gemini video provider adapter is scaffolded but not configured yet.")

    def get_status(self, provider_job_id: str) -> ProviderVideoStatus:
        raise ProviderConfigurationError("Gemini video provider adapter is scaffolded but not configured yet.")

    def download_outputs(self, provider_job_id: str, target_dir: Path) -> list[Path]:
        raise ProviderConfigurationError("Gemini video provider adapter is scaffolded but not configured yet.")

