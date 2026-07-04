from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app import models
from app.enums import WorkflowStatus


class WarmupScheduler:
    BLOCKING_ACCOUNT_STATUSES = {"paused", "limited", "needs_reauth", "disabled"}
    COUNTED_JOB_STATUSES = {
        WorkflowStatus.scheduled.value,
        WorkflowStatus.upload_queued.value,
        WorkflowStatus.uploading.value,
        WorkflowStatus.uploaded.value,
        WorkflowStatus.published.value,
        WorkflowStatus.published_manual.value,
        WorkflowStatus.manual_upload_required.value,
    }

    def __init__(self, db: Session):
        self.db = db

    def validate_schedule(
        self,
        package: models.PublishingPackage,
        account: models.PublishingAccount,
        scheduled_at: datetime,
        manual_override: bool = False,
    ) -> dict:
        reasons = []
        rule = self._active_rule(account)
        day_count = self._count_jobs(account.id, self._day_window(scheduled_at))
        week_count = self._count_jobs(account.id, self._week_window(scheduled_at))
        daily_limit = min(account.daily_publish_limit, rule.max_posts_per_day if rule else account.daily_publish_limit)
        weekly_limit = min(account.weekly_publish_limit, rule.max_posts_per_week if rule else account.weekly_publish_limit)

        if package.video_job.status != WorkflowStatus.video_approved.value:
            reasons.append("Video must be approved before scheduling.")
        if package.status != WorkflowStatus.publishing_package_ready.value:
            reasons.append("Publishing package must be approved before scheduling.")
        if account.warmup_status in self.BLOCKING_ACCOUNT_STATUSES:
            reasons.append(f"Account status blocks scheduling: {account.warmup_status}.")
        if package.brand != account.brand:
            reasons.append("Package brand does not match account brand.")
        if package.target_platform.lower() not in account.platform.lower() and account.platform.lower() not in package.target_platform.lower():
            reasons.append("Target platform does not match the selected account.")
        if day_count >= daily_limit:
            reasons.append(f"Daily warm-up limit reached: {day_count}/{daily_limit}.")
        if week_count >= weekly_limit:
            reasons.append(f"Weekly warm-up limit reached: {week_count}/{weekly_limit}.")

        allowed = not reasons or manual_override
        return {
            "allowed": allowed,
            "manual_override": manual_override,
            "reasons": reasons,
            "rule_phase": rule.phase if rule else account.warmup_phase,
            "daily_count": day_count,
            "weekly_count": week_count,
            "daily_limit": daily_limit,
            "weekly_limit": weekly_limit,
        }

    def schedule(
        self,
        package: models.PublishingPackage,
        account: models.PublishingAccount,
        scheduled_at: datetime,
        provider: str = "mock",
        manual_override: bool = False,
        operator_name: str | None = None,
    ) -> models.PublishingJob:
        validation = self.validate_schedule(package, account, scheduled_at, manual_override)
        if not validation["allowed"]:
            raise ValueError("; ".join(validation["reasons"]))
        job = models.PublishingJob(
            publishing_package_id=package.id,
            account_id=account.id,
            scheduled_at=scheduled_at,
            status=WorkflowStatus.scheduled.value,
            provider=provider,
            manual_upload_required=provider != "mock",
            operator_name=operator_name,
            raw_response_json={"warmup_validation": validation},
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def _active_rule(self, account: models.PublishingAccount) -> models.WarmupRule | None:
        plan = self.db.scalar(
            select(models.WarmupPlan)
            .where((models.WarmupPlan.account_id == account.id) | (models.WarmupPlan.account_id.is_(None)))
            .order_by(models.WarmupPlan.account_id.desc().nullslast())
        )
        if not plan:
            return None
        return self.db.scalar(
            select(models.WarmupRule)
            .where(
                models.WarmupRule.warmup_plan_id == plan.id,
                models.WarmupRule.phase == account.warmup_phase,
            )
            .order_by(models.WarmupRule.day_from)
        )

    def _count_jobs(self, account_id: int, window: tuple[datetime, datetime]) -> int:
        start, end = window
        return (
            self.db.scalar(
                select(func.count())
                .select_from(models.PublishingJob)
                .where(
                    and_(
                        models.PublishingJob.account_id == account_id,
                        models.PublishingJob.scheduled_at >= start,
                        models.PublishingJob.scheduled_at < end,
                        models.PublishingJob.status.in_(self.COUNTED_JOB_STATUSES),
                    )
                )
            )
            or 0
        )

    @staticmethod
    def _day_window(value: datetime) -> tuple[datetime, datetime]:
        start = datetime.combine(value.date(), time.min)
        return start, start + timedelta(days=1)

    @staticmethod
    def _week_window(value: datetime) -> tuple[datetime, datetime]:
        day_start = datetime.combine(value.date(), time.min)
        start = day_start - timedelta(days=day_start.weekday())
        return start, start + timedelta(days=7)

