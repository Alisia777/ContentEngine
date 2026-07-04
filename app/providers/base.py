from typing import Protocol


class NotConfiguredError(RuntimeError):
    """Raised by real-provider stubs until credentials and official APIs are configured."""


class LLMClient(Protocol):
    def generate_script(self, input_payload: dict) -> dict: ...

    def validate_script(self, script_json: dict, product_data: dict, brand_rules: dict) -> dict: ...


class VideoProvider(Protocol):
    def generate_clip(
        self,
        scene_prompt: str,
        negative_prompt: str,
        image_refs: list[str],
        aspect_ratio: str,
        duration_seconds: int,
    ) -> dict: ...

    def get_status(self, provider_job_id: str) -> dict: ...

    def download_result(self, provider_job_id: str) -> str: ...


class UploadProvider(Protocol):
    def validate_package(self, publishing_package: dict, account: dict) -> dict: ...

    def upload_or_schedule(self, publishing_job: dict) -> dict: ...

    def get_status(self, provider_post_id: str) -> dict: ...

    def collect_analytics(self, provider_post_id: str) -> dict: ...

