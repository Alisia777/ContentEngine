from app.providers.base import NotConfiguredError


class RunwayProvider:
    def generate_clip(self, *args, **kwargs) -> dict:
        raise NotConfiguredError("RunwayProvider is a future official-provider adapter and is not configured.")

    def get_status(self, provider_job_id: str) -> dict:
        raise NotConfiguredError("RunwayProvider is not configured.")

    def download_result(self, provider_job_id: str) -> str:
        raise NotConfiguredError("RunwayProvider is not configured.")


class GeminiVeoProvider:
    def generate_clip(self, *args, **kwargs) -> dict:
        raise NotConfiguredError("GeminiVeoProvider is a future official-provider adapter and is not configured.")

    def get_status(self, provider_job_id: str) -> dict:
        raise NotConfiguredError("GeminiVeoProvider is not configured.")

    def download_result(self, provider_job_id: str) -> str:
        raise NotConfiguredError("GeminiVeoProvider is not configured.")

