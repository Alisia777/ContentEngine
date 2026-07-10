from __future__ import annotations

from app.control_room.types import ControlRoomSnapshotOutput
from app.interface_productization.types import MVPAction, MVPBlocker
from app.smoke_readiness.types import SmokeReadinessRunOutput


ACTION_LABELS = {
    "product_compositing_required": "Подготовить безопасную сборку товара",
    "add_edible_references": "Добавить фото продукта в разрезе",
    "add_product_references": "Добавить референсы товара",
    "benchmark_candidate_ready": "Проверить эталонный ролик",
    "one_paid_smoke_then_output_acceptance": "Подготовить один тестовый запуск",
    "blocked_by_runway_credits": "Проверить готовность платного запуска",
}


class MVPNavigationService:
    """Turns existing engine state into one human-readable product action."""

    def primary_action(
        self,
        snapshot: ControlRoomSnapshotOutput,
        smoke: SmokeReadinessRunOutput | None,
    ) -> MVPAction:
        if snapshot.review_queue:
            return MVPAction(
                action_type="review_output",
                label="Проверить готовый ролик",
                url="/workbench?tab=video-quality",
                detail="Видео ждёт обязательного решения человека.",
                requires_human=True,
            )

        smoke_decision = smoke.report.final_decision if smoke else None
        if smoke_decision == "blocked_by_missing_references":
            return MVPAction(
                action_type="add_product_references",
                label="Добавить референсы товара",
                url="/mvp-launch",
                status="blocked",
                detail="Без полного набора фото товарные сцены недоступны.",
            )

        next_action = str(snapshot.summary.get("real_video_next_action") or "")
        if next_action == "product_compositing_required":
            return MVPAction(
                action_type=next_action,
                label=ACTION_LABELS[next_action],
                url="/workbench?tab=video-quality",
                detail="Последний real output отклонён: точный packshot должен собираться поверх lifestyle-сцены.",
                requires_human=True,
            )

        if smoke_decision == "ready_for_paid_smoke":
            return MVPAction(
                action_type="review_paid_smoke_readiness",
                label="Проверить готовность одного запуска",
                url="/mvp-launch",
                status="spend_gated",
                detail="Запуск не произойдёт без отдельного подтверждения расходов.",
                safe_to_execute=False,
                requires_human=True,
                requires_spend_gate=True,
            )

        return MVPAction(
            action_type="open_mvp_launch",
            label="Продолжить запуск MVP",
            url="/mvp-launch",
            detail="Система проведёт один SKU по проверкам, prompt-only и review.",
        )

    def blockers(
        self,
        snapshot: ControlRoomSnapshotOutput,
        smoke: SmokeReadinessRunOutput | None,
    ) -> list[MVPBlocker]:
        items: list[MVPBlocker] = []
        if smoke:
            for blocker in smoke.blockers:
                items.append(
                    MVPBlocker(
                        blocker_type=blocker.blocker_type,
                        label=self._blocker_label(blocker.blocker_type),
                        detail=blocker.message,
                        severity=blocker.severity,
                        next_action=blocker.recommended_action,
                    )
                )
        for item in snapshot.blocked_items[:5]:
            items.append(
                MVPBlocker(
                    blocker_type=item.target_module,
                    label=item.label,
                    detail=item.detail or "Нужна проверка рабочего контура.",
                    severity=item.severity,
                    next_action=item.target_url,
                )
            )
        deduped: dict[tuple[str, str], MVPBlocker] = {}
        for item in items:
            deduped[(item.blocker_type, item.detail)] = item
        return list(deduped.values())

    @staticmethod
    def _blocker_label(blocker_type: str) -> str:
        labels = {
            "missing_refs": "Не хватает референсов товара",
            "missing_references": "Не хватает референсов товара",
            "reference_policy_blocked": "Товарные сцены заблокированы",
            "spend_gate_off": "Расходы не подтверждены",
            "generation_mode_not_real": "Реальный режим выключен",
            "runway_key_missing": "Провайдер не настроен",
            "runway_credits_unconfirmed": "Баланс не подтверждён в readiness",
            "prompt_only_failed": "Prompt-only требует исправления",
        }
        return labels.get(blocker_type, blocker_type.replace("_", " ").capitalize())

