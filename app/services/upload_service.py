from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.enums import WorkflowStatus
from app.providers.upload import MockUploadProvider
from app.providers.upload.stubs import ManualUploadStub


class UploadService:
    def __init__(self, db: Session):
        self.db = db

    def run_job(self, job: models.PublishingJob) -> models.PublishingJob:
        provider = self._provider(job.provider)
        package_payload = self._package_payload(job.publishing_package)
        account_payload = self._account_payload(job.account)
        validation = provider.validate_package(package_payload, account_payload)
        if not validation.get("valid", True):
            job.status = WorkflowStatus.failed.value
            job.error_message = "; ".join(validation.get("errors", ["Package validation failed"]))
            job.raw_response_json = {"validation": validation}
            self.db.commit()
            self.db.refresh(job)
            return job

        result = provider.upload_or_schedule(
            {
                "job_id": job.id,
                "scheduled_at": job.scheduled_at.isoformat(),
                "package": package_payload,
                "account": account_payload,
            }
        )
        if result.get("manual_upload_required") or result.get("status") == WorkflowStatus.manual_upload_required.value:
            job.status = WorkflowStatus.manual_upload_required.value
            job.manual_upload_required = True
            job.raw_response_json = {"validation": validation, "provider_result": result}
        else:
            job.status = WorkflowStatus.published.value
            job.manual_upload_required = False
            job.provider_post_id = result.get("provider_post_id")
            job.provider_post_url = result.get("provider_post_url")
            job.raw_response_json = {"validation": validation, "provider_result": result}
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_manual_uploaded(self, job: models.PublishingJob, provider_post_url: str, operator_name: str) -> models.PublishingJob:
        job.status = WorkflowStatus.published_manual.value
        job.provider_post_url = provider_post_url
        job.provider_post_id = provider_post_url.rstrip("/").split("/")[-1]
        job.manual_upload_required = False
        job.operator_name = operator_name
        job.raw_response_json = {
            **(job.raw_response_json or {}),
            "manual_upload": {
                "operator_name": operator_name,
                "provider_post_url": provider_post_url,
                "status": WorkflowStatus.published_manual.value,
            },
        }
        self.db.commit()
        self.db.refresh(job)
        return job

    def cancel(self, job: models.PublishingJob) -> models.PublishingJob:
        job.status = "cancelled"
        self.db.commit()
        self.db.refresh(job)
        return job

    def retry(self, job: models.PublishingJob) -> models.PublishingJob:
        job.status = WorkflowStatus.scheduled.value
        job.error_message = None
        self.db.commit()
        self.db.refresh(job)
        return job

    @staticmethod
    def _provider(name: str):
        if name == "mock":
            return MockUploadProvider()
        return ManualUploadStub()

    @staticmethod
    def _package_payload(package: models.PublishingPackage) -> dict:
        return {column.name: getattr(package, column.name) for column in package.__table__.columns}

    @staticmethod
    def _account_payload(account: models.PublishingAccount) -> dict:
        return {column.name: getattr(account, column.name) for column in account.__table__.columns}

