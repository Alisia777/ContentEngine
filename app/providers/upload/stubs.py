class ManualUploadStub:
    provider_name = "manual"

    def validate_package(self, publishing_package: dict, account: dict) -> dict:
        return {"valid": True, "manual_upload_required": True, "message": self.message()}

    def upload_or_schedule(self, publishing_job: dict) -> dict:
        return {"status": "manual_upload_required", "manual_upload_required": True, "message": self.message()}

    def get_status(self, provider_post_id: str) -> dict:
        return {"status": "manual_upload_required", "message": self.message()}

    def collect_analytics(self, provider_post_id: str) -> dict:
        return {"status": "manual_upload_required", "message": self.message()}

    def message(self) -> str:
        return f"{self.provider_name} is not configured. Prepare a manual upload task or add official API credentials."


class YouTubeUploadProvider(ManualUploadStub):
    provider_name = "YouTubeUploadProvider"


class TikTokUploadProvider(ManualUploadStub):
    provider_name = "TikTokUploadProvider"


class InstagramReelsUploadProvider(ManualUploadStub):
    provider_name = "InstagramReelsUploadProvider"


class TelegramUploadProvider(ManualUploadStub):
    provider_name = "TelegramUploadProvider"


class VKUploadProvider(ManualUploadStub):
    provider_name = "VKUploadProvider"


class WildberriesMediaProvider(ManualUploadStub):
    provider_name = "WildberriesMediaProvider"


class OzonMediaProvider(ManualUploadStub):
    provider_name = "OzonMediaProvider"

