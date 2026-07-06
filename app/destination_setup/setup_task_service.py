from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_setup.account_checklist_builder import AccountChecklistBuilder, OFFICIAL_API_PLATFORMS
from app.destination_setup.errors import DestinationSetupDataError
from app.destination_setup.types import DestinationSetupTaskResult
from app.publishing import PublishingDestinationService


class DestinationSetupTaskService:
    VALID_STATUSES = {
        "needs_manual_setup",
        "needs_auth",
        "in_progress",
        "completed_pending_destination",
        "destination_created",
        "cancelled",
    }

    def __init__(self, db: Session):
        self.db = db
        self.checklists = AccountChecklistBuilder()

    def create_task(self, profile_pack_id: int, *, owner_name: str | None = None) -> DestinationSetupTaskResult:
        pack = self._pack(profile_pack_id)
        existing = self.db.scalar(
            select(models.DestinationSetupTask)
            .where(models.DestinationSetupTask.profile_pack_id == pack.id)
            .order_by(models.DestinationSetupTask.id.desc())
        )
        if existing:
            return self._result(existing)
        task = models.DestinationSetupTask(
            campaign_id=pack.campaign_id,
            profile_pack_id=pack.id,
            platform=pack.platform,
            status=self.checklists.initial_task_status(pack.platform),
            owner_name=owner_name,
            checklist_json=self.checklists.build(pack.platform),
            notes="External account setup is manual/off-platform. ContentEngine does not auto-register accounts.",
        )
        pack.status = "task_created"
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return self._result(task)

    def create_tasks_for_campaign(self, campaign_id: int, *, owner_name: str | None = None) -> list[DestinationSetupTaskResult]:
        packs = self.db.scalars(
            select(models.DestinationProfilePack)
            .where(models.DestinationProfilePack.campaign_id == campaign_id)
            .order_by(models.DestinationProfilePack.id)
        ).all()
        if not packs:
            raise DestinationSetupDataError("Create destination profile packs before setup tasks.")
        return [self.create_task(pack.id, owner_name=owner_name) for pack in packs]

    def list(self, *, campaign_id: int | None = None, status: str | None = None) -> list[DestinationSetupTaskResult]:
        query = select(models.DestinationSetupTask).order_by(models.DestinationSetupTask.id.desc())
        if campaign_id is not None:
            query = query.where(models.DestinationSetupTask.campaign_id == campaign_id)
        if status is not None:
            query = query.where(models.DestinationSetupTask.status == status)
        tasks = self.db.scalars(query).all()
        return [self._result(task) for task in tasks]

    def update(self, task_id: int, **values) -> DestinationSetupTaskResult:
        task = self._task(task_id)
        for field in ["status", "owner_name", "final_account_url", "final_handle", "notes"]:
            if field in values and values[field] is not None:
                setattr(task, field, values[field])
        if "checklist" in values and values["checklist"] is not None:
            task.checklist_json = values["checklist"]
        self._validate_status(task.status)
        self.db.commit()
        self.db.refresh(task)
        return self._result(task)

    def mark_complete(
        self,
        task_id: int,
        *,
        url: str | None = None,
        handle: str | None = None,
        owner_name: str | None = None,
        notes: str | None = None,
    ) -> DestinationSetupTaskResult:
        task = self._task(task_id)
        if not url and not handle:
            raise DestinationSetupDataError("Final account URL or handle is required to complete setup.")
        if url:
            task.final_account_url = url
        if handle:
            task.final_handle = handle
        if owner_name:
            task.owner_name = owner_name
        if notes:
            task.notes = notes
        task.status = "completed_pending_destination"
        task.checklist_json = [dict(item, status="done") for item in (task.checklist_json or [])]
        self.db.commit()
        self.db.refresh(task)
        return self._result(task)

    def create_destination(self, task_id: int) -> models.PublishingDestination:
        task = self._task(task_id)
        if task.status not in {"completed_pending_destination", "destination_created"}:
            raise DestinationSetupDataError("Destination setup task must be completed before creating an internal destination.")
        if not task.final_account_url and not task.final_handle:
            raise DestinationSetupDataError("Final account URL or handle is required before creating an internal destination.")
        pack = self._pack(task.profile_pack_id)
        campaign = self._campaign(task.campaign_id)
        destination = self._existing_destination(campaign, task)
        if not destination:
            destination = PublishingDestinationService(self.db).create(
                brand=campaign.brand,
                platform=task.platform,
                name=pack.suggested_name,
                handle=task.final_handle or pack.suggested_handle,
                url=task.final_account_url,
                owner_name=task.owner_name,
                status="active",
                posting_mode="manual",
                auth_status="manual_only",
                allowed_formats=["vertical_video"],
                daily_limit=1,
                weekly_limit=3,
                notes=self._destination_notes(task.platform),
            )
        task.status = "destination_created"
        task.notes = self._append_note(task.notes, f"internal_destination_id={destination.id}")
        pack.status = "destination_created"
        self.db.commit()
        self.db.refresh(destination)
        return destination

    def _existing_destination(self, campaign: models.Campaign, task: models.DestinationSetupTask) -> models.PublishingDestination | None:
        query = select(models.PublishingDestination).where(
            models.PublishingDestination.brand == campaign.brand,
            models.PublishingDestination.platform == task.platform,
        )
        if task.final_handle:
            found = self.db.scalar(query.where(models.PublishingDestination.handle == task.final_handle))
            if found:
                return found
        if task.final_account_url:
            return self.db.scalar(query.where(models.PublishingDestination.url == task.final_account_url))
        return None

    def _pack(self, profile_pack_id: int) -> models.DestinationProfilePack:
        pack = self.db.get(models.DestinationProfilePack, profile_pack_id)
        if not pack:
            raise DestinationSetupDataError(f"Destination profile pack {profile_pack_id} not found.")
        return pack

    def _task(self, task_id: int) -> models.DestinationSetupTask:
        task = self.db.get(models.DestinationSetupTask, task_id)
        if not task:
            raise DestinationSetupDataError(f"Destination setup task {task_id} not found.")
        return task

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise DestinationSetupDataError(f"Campaign {campaign_id} not found.")
        return campaign

    def _validate_status(self, status: str) -> None:
        if status not in self.VALID_STATUSES:
            raise DestinationSetupDataError(f"Invalid destination setup task status: {status}.")

    @staticmethod
    def _destination_notes(platform: str) -> str:
        if platform in OFFICIAL_API_PLATFORMS:
            return (
                "Created from Destination Setup Factory after operator confirmation. "
                "Official API upload is preferred when token_valid; manual-assisted upload remains available."
            )
        return "Created from Destination Setup Factory after operator confirmation. Manual-assisted upload destination."

    @staticmethod
    def _append_note(existing: str | None, note: str) -> str:
        return f"{existing}\n{note}" if existing else note

    @staticmethod
    def _result(task: models.DestinationSetupTask) -> DestinationSetupTaskResult:
        return DestinationSetupTaskResult(
            id=task.id,
            campaign_id=task.campaign_id,
            profile_pack_id=task.profile_pack_id,
            platform=task.platform,
            status=task.status,
            owner_name=task.owner_name,
            checklist=task.checklist_json or [],
            final_account_url=task.final_account_url,
            final_handle=task.final_handle,
            notes=task.notes,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
