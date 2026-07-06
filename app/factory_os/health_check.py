from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.campaign_batch.safety_gates import SAFE_BATCH_ACTIONS, UNSAFE_BATCH_ACTIONS
from app.config import get_settings
from app.factory_os.types import FactoryHealthStatus
from app.intelligence.safety import provider_key_status


class FactoryHealthCheck:
    def __init__(self, db: Session):
        self.db = db

    def run(self) -> FactoryHealthStatus:
        checks = [
            self._db_check(),
            self._media_check(),
            self._module_check("product_matrix_import", "app.campaign_autopilot.product_matrix_importer"),
            self._module_check("content_autopilot", "app.content_factory.content_run_orchestrator"),
            self._module_check("campaign_autopilot", "app.campaign_autopilot.campaign_runner"),
            self._module_check("execution_control", "app.campaign_execution.execution_state_service"),
            self._module_check("batch_executor", "app.campaign_batch.batch_executor"),
            self._module_check("publishing_foundation", "app.publishing.package_service"),
            self._module_check("performance_loop", "app.campaign_performance.report_service"),
        ]
        overall = "ready" if all(item["status"] == "ready" for item in checks) else "degraded"
        return FactoryHealthStatus(
            overall_status=overall,
            checks=checks,
            provider_keys=provider_key_status(),
            safety_gates={
                "paid_provider_calls_default_blocked": True,
                "auto_publish_unreviewed_videos": False,
                "safe_batch_actions": sorted(SAFE_BATCH_ACTIONS),
                "unsafe_batch_actions": sorted(UNSAFE_BATCH_ACTIONS),
            },
        )

    def _db_check(self) -> dict:
        try:
            self.db.execute(text("SELECT 1")).scalar()
            return {"name": "db", "status": "ready"}
        except Exception as exc:  # pragma: no cover - defensive health branch
            return {"name": "db", "status": "blocked", "detail": str(exc)}

    @staticmethod
    def _media_check() -> dict:
        settings = get_settings()
        try:
            settings.media_root.mkdir(parents=True, exist_ok=True)
            probe = Path(settings.media_root) / ".factory_os_write_check"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return {"name": "media_dir", "status": "ready", "path": str(settings.media_root)}
        except Exception as exc:  # pragma: no cover - defensive health branch
            return {"name": "media_dir", "status": "blocked", "detail": str(exc)}

    @staticmethod
    def _module_check(name: str, module_path: str) -> dict:
        try:
            __import__(module_path)
            return {"name": name, "status": "ready"}
        except Exception as exc:  # pragma: no cover - defensive health branch
            return {"name": name, "status": "blocked", "detail": str(exc)}
