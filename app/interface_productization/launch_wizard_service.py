from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.interface_productization.errors import InterfaceProductizationError
from app.interface_productization.types import MVPAction, MVPBlocker, MVPLaunchRunOutput, MVPLaunchStep
from app.one_video_acceptance import OneVideoAcceptanceError, OneVideoAcceptanceService
from app.smoke_readiness import ReadinessReportService, RecoveryService, SmokeReadinessError


STEP_DEFINITIONS = [
    ("select_product", "Выбрать товар", "Один SKU и один вариант вкуса."),
    ("check_assets", "Проверить фото", "Система проверит референсы до генерации."),
    ("build_prompt_only", "Собрать ТЗ", "Prompt-only не вызывает платного провайдера."),
    ("check_smoke_readiness", "Проверить запуск", "Ключ, баланс, spend gate и scene policy."),
    ("run_or_block_paid_smoke", "Решить по paid smoke", "Только явное решение оператора; автозапуска нет."),
    ("review_output", "Проверить результат", "Видео нельзя одобрить автоматически."),
    ("decide_next_action", "Зафиксировать решение", "Approve, regeneration, compositing или новые фото."),
]
STEP_KEYS = [item[0] for item in STEP_DEFINITIONS]


class MVPLaunchWizardService:
    """Guided facade over existing services; it never starts a paid provider call."""

    def __init__(self, db: Session):
        self.db = db

    def start(self, *, product_id: int | None = None, sku: str | None = None) -> models.MVPLaunchRun:
        product = self._resolve_product(product_id=product_id, sku=sku)
        completed: list[str] = []
        current_step = "select_product"
        status = "needs_input"
        blockers: list[dict] = []
        if product:
            completed.append("select_product")
            current_step = "check_assets"
            status = "in_progress"
        else:
            blockers.append(self._blocker("product_missing", "Товар не выбран", "Выберите один SKU для управляемого запуска."))
        run = models.MVPLaunchRun(
            product_id=product.id if product else None,
            sku=product.sku if product else sku,
            status=status,
            current_step=current_step,
            completed_steps_json=completed,
            blockers_json=blockers,
            next_action_json=self._next_action(current_step, blocked=not bool(product)),
            context_json={"provider_calls": 0, "paid_provider_called": False},
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get(self, run_id: int) -> models.MVPLaunchRun:
        run = self.db.get(models.MVPLaunchRun, run_id)
        if not run:
            raise InterfaceProductizationError(f"MVPLaunchRun {run_id} not found.")
        return run

    def advance(
        self,
        run_id: int,
        *,
        product_id: int | None = None,
        sku: str | None = None,
        runway_credits_confirmed: bool = False,
    ) -> models.MVPLaunchRun:
        run = self.get(run_id)
        step = run.current_step
        if step == "select_product":
            self._select_product(run, product_id=product_id, sku=sku)
        elif step == "check_assets":
            self._check_assets(run)
        elif step == "build_prompt_only":
            self._build_prompt_only(run)
        elif step == "check_smoke_readiness":
            self._check_smoke_readiness(run, runway_credits_confirmed=runway_credits_confirmed)
        elif step == "run_or_block_paid_smoke":
            self._record_paid_smoke_decision(run)
        elif step == "review_output":
            self._review_output_state(run)
        elif step == "decide_next_action":
            self._finish(run)
        else:
            raise InterfaceProductizationError(f"Unsupported MVP launch step: {step}")
        self.db.commit()
        self.db.refresh(run)
        return run

    def output(self, run: models.MVPLaunchRun) -> MVPLaunchRunOutput:
        completed = run.completed_steps_json or []
        return MVPLaunchRunOutput(
            id=run.id,
            product_id=run.product_id,
            sku=run.sku,
            status=run.status,
            current_step=run.current_step,
            completed_steps=completed,
            blockers=run.blockers_json or [],
            next_action=run.next_action_json,
            steps=[
                MVPLaunchStep(
                    key=key,
                    label=label,
                    status="current" if key == run.current_step else "complete" if key in completed else "pending",
                    detail=detail,
                )
                for key, label, detail in STEP_DEFINITIONS
            ],
            context=run.context_json or {},
            one_video_render_plan_id=run.one_video_render_plan_id,
            smoke_readiness_run_id=run.smoke_readiness_run_id,
            one_video_render_result_id=run.one_video_render_result_id,
            output_acceptance_id=run.output_acceptance_id,
        )

    def _select_product(self, run: models.MVPLaunchRun, *, product_id: int | None, sku: str | None) -> None:
        product = self._resolve_product(product_id=product_id, sku=sku)
        if not product:
            self._set_blocked(run, "product_missing", "Товар не найден", "Выберите существующий SKU.")
            return
        run.product_id = product.id
        run.sku = product.sku
        self._complete(run, "select_product", "check_assets")

    def _check_assets(self, run: models.MVPLaunchRun) -> None:
        if not run.product_id:
            self._set_blocked(run, "product_missing", "Товар не выбран", "Вернитесь к выбору SKU.")
            run.current_step = "select_product"
            return
        try:
            plan = OneVideoAcceptanceService(self.db).build_plan(run.product_id, provider="runway")
        except OneVideoAcceptanceError as exc:
            self._set_blocked(run, "asset_check_failed", "Фото товара не прошли проверку", str(exc))
            return
        run.one_video_render_plan_id = plan.id
        context = dict(run.context_json or {})
        context["scene_policy"] = plan.product_scene_policy_json or {}
        context["asset_check_status"] = "blocked" if plan.blockers_json else "ready"
        run.context_json = context
        if plan.blockers_json:
            run.blockers_json = [
                self._blocker(
                    "missing_product_assets",
                    "Не хватает подтверждённых фото",
                    "Товарные сцены останутся заблокированы, пока reference policy не станет ready.",
                    next_action="add_product_references",
                )
            ]
            run.status = "blocked"
            run.next_action_json = self._next_action("check_assets", blocked=True)
            return
        self._complete(run, "check_assets", "build_prompt_only")

    def _build_prompt_only(self, run: models.MVPLaunchRun) -> None:
        if not run.one_video_render_plan_id:
            self._set_blocked(run, "plan_missing", "План не создан", "Сначала проверьте фото товара.")
            run.current_step = "check_assets"
            return
        try:
            plan = OneVideoAcceptanceService(self.db).prompt_only(run.one_video_render_plan_id, provider="runway")
        except OneVideoAcceptanceError as exc:
            self._set_blocked(run, "prompt_only_failed", "ТЗ требует исправления", str(exc))
            return
        context = dict(run.context_json or {})
        context["prompt_pack_id"] = plan.prompt_pack_id
        context["prompt_only_status"] = plan.status
        run.context_json = context
        self._complete(run, "build_prompt_only", "check_smoke_readiness")

    def _check_smoke_readiness(self, run: models.MVPLaunchRun, *, runway_credits_confirmed: bool) -> None:
        try:
            readiness = RecoveryService(self.db).recover(
                plan_id=run.one_video_render_plan_id,
                product_id=run.product_id,
                sku=run.sku,
                runway_credits_confirmed=runway_credits_confirmed,
            )
        except SmokeReadinessError as exc:
            self._set_blocked(run, "smoke_readiness_failed", "Readiness не собран", str(exc))
            return
        run.smoke_readiness_run_id = readiness.id
        report = ReadinessReportService(self.db).output(readiness)
        context = dict(run.context_json or {})
        context["smoke_decision"] = report.report.final_decision
        context["smoke_status"] = report.status
        run.context_json = context
        run.blockers_json = [
            self._blocker(item.blocker_type, item.blocker_type.replace("_", " "), item.message, severity=item.severity, next_action=item.recommended_action)
            for item in report.blockers
        ]
        self._complete(run, "check_smoke_readiness", "run_or_block_paid_smoke")
        if report.report.final_decision != "ready_for_paid_smoke":
            run.status = "blocked"
            run.next_action_json = MVPAction(
                action_type=report.report.final_decision,
                label="Устранить блокеры запуска",
                url=f"/mvp-launch?run_id={run.id}",
                status="blocked",
                detail="Платный вызов не выполнен.",
                safe_to_execute=True,
            ).model_dump(mode="json")

    def _record_paid_smoke_decision(self, run: models.MVPLaunchRun) -> None:
        context = dict(run.context_json or {})
        context["paid_provider_called"] = False
        context["provider_calls"] = 0
        context["paid_smoke_policy"] = "separate_explicit_operator_command_required"
        run.context_json = context
        latest_result = self.db.scalar(
            select(models.OneVideoRenderResult)
            .where(models.OneVideoRenderResult.plan_id == run.one_video_render_plan_id)
            .order_by(models.OneVideoRenderResult.id.desc())
        ) if run.one_video_render_plan_id else None
        if latest_result:
            run.one_video_render_result_id = latest_result.id
            run.output_acceptance_id = latest_result.output_acceptance_id
            self._complete(run, "run_or_block_paid_smoke", "review_output")
            return
        run.status = "spend_gated"
        run.next_action_json = MVPAction(
            action_type="explicit_paid_smoke_required",
            label="Запросить отдельное подтверждение запуска",
            url=f"/mvp-launch?run_id={run.id}",
            status="spend_gated",
            detail="Мастер не запускает провайдера автоматически.",
            safe_to_execute=False,
            requires_human=True,
            requires_spend_gate=True,
        ).model_dump(mode="json")

    def _review_output_state(self, run: models.MVPLaunchRun) -> None:
        if not run.one_video_render_result_id:
            self._set_blocked(run, "video_result_missing", "Результата пока нет", "Paid smoke должен быть запущен отдельно и только после всех gates.")
            return
        result = self.db.get(models.OneVideoRenderResult, run.one_video_render_result_id)
        if not result or result.human_review_status in {"needs_human_review", "needs_review"}:
            run.status = "needs_review"
            run.next_action_json = MVPAction(
                action_type="review_output",
                label="Проверить видео глазами",
                url="/workbench?tab=video-quality",
                status="needs_review",
                requires_human=True,
            ).model_dump(mode="json")
            return
        self._complete(run, "review_output", "decide_next_action")

    def _finish(self, run: models.MVPLaunchRun) -> None:
        self._complete(run, "decide_next_action", "decide_next_action")
        run.status = "complete"
        run.next_action_json = MVPAction(
            action_type="return_to_control_room",
            label="Вернуться в центр управления",
            url="/control-room",
            detail="Решение по одному SKU зафиксировано.",
        ).model_dump(mode="json")

    def _complete(self, run: models.MVPLaunchRun, completed_step: str, next_step: str) -> None:
        run.completed_steps_json = list(dict.fromkeys([*(run.completed_steps_json or []), completed_step]))
        run.current_step = next_step
        run.status = "in_progress"
        run.blockers_json = []
        run.next_action_json = self._next_action(next_step)

    def _set_blocked(self, run: models.MVPLaunchRun, blocker_type: str, label: str, detail: str) -> None:
        run.status = "blocked"
        run.blockers_json = [self._blocker(blocker_type, label, detail)]
        run.next_action_json = self._next_action(run.current_step, blocked=True)

    @staticmethod
    def _next_action(step: str, *, blocked: bool = False) -> dict:
        labels = {
            "select_product": "Выбрать товар",
            "check_assets": "Проверить фото товара",
            "build_prompt_only": "Собрать prompt-only",
            "check_smoke_readiness": "Проверить готовность запуска",
            "run_or_block_paid_smoke": "Принять решение по paid smoke",
            "review_output": "Проверить результат",
            "decide_next_action": "Зафиксировать следующее действие",
        }
        return MVPAction(
            action_type=step,
            label=labels.get(step, "Продолжить"),
            url="/mvp-launch",
            status="blocked" if blocked else "available",
            detail="Сначала устраните указанный блокер." if blocked else "Безопасно перейти к следующей проверке.",
        ).model_dump(mode="json")

    @staticmethod
    def _blocker(
        blocker_type: str,
        label: str,
        detail: str,
        *,
        severity: str = "blocker",
        next_action: str | None = None,
    ) -> dict:
        return MVPBlocker(
            blocker_type=blocker_type,
            label=label,
            detail=detail,
            severity=severity,
            next_action=next_action,
        ).model_dump(mode="json")

    def _resolve_product(self, *, product_id: int | None, sku: str | None) -> models.Product | None:
        if product_id:
            product = self.db.get(models.Product, product_id)
            if product:
                return product
        if sku:
            return self.db.scalar(select(models.Product).where(models.Product.sku == sku))
        return None

