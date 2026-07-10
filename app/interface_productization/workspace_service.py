from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.control_room import ControlRoomSnapshotService
from app.interface_productization.mvp_navigation_service import MVPNavigationService
from app.interface_productization.types import MVPAction, MVPModuleLink, MVPWorkspaceSnapshotOutput
from app.smoke_readiness import ReadinessReportService


class MVPWorkspaceService:
    """Composes existing audit, control-room and readiness outputs for the product UI."""

    def __init__(self, db: Session):
        self.db = db
        self.navigation = MVPNavigationService()

    def build(self, *, role: str = "owner") -> models.MVPWorkspaceSnapshot:
        control_service = ControlRoomSnapshotService(self.db)
        control = control_service.output(control_service.refresh(role=role))
        smoke_service = ReadinessReportService(self.db)
        smoke_run = smoke_service.latest()
        smoke = smoke_service.output(smoke_run) if smoke_run else None
        primary = self.navigation.primary_action(control, smoke)
        blockers = self.navigation.blockers(control, smoke)
        status = "blocked" if any(item.severity == "blocker" for item in blockers) else "ready"
        if control.review_queue:
            status = "needs_review"

        modules = self._module_links(control, smoke)
        secondary = [
            MVPAction(
                action_type="open_workbench",
                label="Открыть рабочую область",
                url="/workbench",
                detail="Вся готовность SKU в одном месте.",
            ),
            MVPAction(
                action_type="check_access",
                label="Проверить доступ",
                url="/settings/access",
                detail="Роли, сертификаты и spend gates.",
            ),
        ]
        context = {
            "engine_score": control.summary.get("engine_audit_total_score"),
            "video_quality": (control.summary.get("dimension_scores") or {}).get("video_quality", {}),
            "paid_smoke_status": control.summary.get("paid_smoke_status"),
            "ready_count": len(control.ready_items),
            "blocked_count": len(control.blocked_items),
            "review_count": len(control.review_queue),
            "smoke_decision": smoke.report.final_decision if smoke else "not_checked",
            "product_id": smoke.product_id if smoke else None,
            "sku": smoke.sku if smoke else None,
            "technical": {
                "engine_audit_run_id": control.engine_audit_run_id,
                "control_room_snapshot_id": control.id,
                "smoke_readiness_run_id": smoke.id if smoke else None,
            },
        }
        record = models.MVPWorkspaceSnapshot(
            role=role,
            status=status,
            current_step=primary.action_type,
            primary_action_json=primary.model_dump(mode="json"),
            secondary_actions_json=[item.model_dump(mode="json") for item in secondary],
            blockers_json=[item.model_dump(mode="json") for item in blockers],
            module_links_json=[item.model_dump(mode="json") for item in modules],
            context_json=context,
            control_room_snapshot_id=control.id,
            smoke_readiness_run_id=smoke.id if smoke else None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def output(self, record: models.MVPWorkspaceSnapshot) -> MVPWorkspaceSnapshotOutput:
        return MVPWorkspaceSnapshotOutput(
            id=record.id,
            role=record.role,
            status=record.status,
            current_step=record.current_step,
            primary_action=record.primary_action_json,
            secondary_actions=record.secondary_actions_json or [],
            blockers=record.blockers_json or [],
            module_links=record.module_links_json or [],
            context=record.context_json or {},
            control_room_snapshot_id=record.control_room_snapshot_id,
            smoke_readiness_run_id=record.smoke_readiness_run_id,
        )

    @staticmethod
    def _module_links(control, smoke) -> list[MVPModuleLink]:
        video_status = (control.summary.get("dimension_scores") or {}).get("video_quality", {}).get("status", "unknown")
        smoke_status = smoke.report.final_decision if smoke else "not_checked"
        return [
            MVPModuleLink(key="product", label="Готовность товара", url="/mvp-launch", status=smoke_status, summary="Фото, SKU и разрешённые сцены.", internal_route="/one-video-acceptance"),
            MVPModuleLink(key="creative", label="Креативное ТЗ", url="/mvp-launch", status="guided", summary="Сценарий и prompt-only без платного вызова.", internal_route="/ai-brief-studio"),
            MVPModuleLink(key="video-quality", label="Качество видео", url="/workbench?tab=video-quality", status=video_status, summary="Результат, drift и ручное решение.", internal_route="/output-acceptance"),
            MVPModuleLink(key="publishing", label="Публикация", url="/workbench?tab=publishing", status="human_gated", summary="Только approved video и traceable URL."),
            MVPModuleLink(key="metrics", label="Метрики", url="/workbench?tab=metrics", status="available", summary="Импорт и атрибуция после публикации.", internal_route="/metrics-intake"),
            MVPModuleLink(key="people", label="Люди и обучение", url="/workbench?tab=people", status="available", summary="Роли, задания и сертификация.", internal_route="/participant-portal"),
            MVPModuleLink(key="access", label="Доступ", url="/settings/access", status="gated", summary="Роли, права и подтверждение расходов."),
        ]

