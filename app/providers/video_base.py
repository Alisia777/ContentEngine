from pathlib import Path
from typing import Protocol

from app.intelligence.types import PromptPackOutput, ProviderVideoJob, ProviderVideoStatus


class VideoProvider(Protocol):
    provider_name: str

    def create_generation(self, prompt_pack: PromptPackOutput) -> ProviderVideoJob: ...

    def get_status(self, provider_job_id: str) -> ProviderVideoStatus: ...

    def download_outputs(self, provider_job_id: str, target_dir: Path) -> list[Path]: ...

