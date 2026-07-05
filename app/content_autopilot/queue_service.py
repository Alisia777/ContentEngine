from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.content_autopilot.action_executor import ActionExecutor
from app.content_autopilot.decision_engine import DecisionEngine
from app.content_autopilot.decision_log import DecisionLog
from app.content_autopilot.errors import ContentAutopilotDataError
from app.content_autopilot.state_inspector import StateInspector
from app.content_autopilot.types import AutopilotDashboard, AutopilotDecisionResult, AutopilotRunResult, ContentStateSnapshot


class AutopilotQueueService:
    def __init__(self, db: Session):
        self.db = db
        self.inspector = StateInspector(db)
        self.engine = DecisionEngine()
        self.log = DecisionLog(db)

    def state(self, product_id: int) -> ContentStateSnapshot:
        return self.inspector.inspect_product(product_id)

    def decide(self, product_id: int, *, create_queue: bool = True) -> models.AutopilotDecision:
        snapshot = self.inspector.inspect_product(product_id)
        decision = self.engine.decide(snapshot)
        record = self.log.record(decision)
        if create_queue:
            self.ensure_queue_item(snapshot, decision)
        return record

    def run(
        self,
        *,
        product_ids: list[int] | None = None,
        execute_safe: bool = False,
        allow_paid: bool = False,
    ) -> AutopilotRunResult:
        products = self._products(product_ids)
        run = models.AutopilotRun(
            status="running",
            scope_type="selected_products" if product_ids else "all_products",
            product_ids_json=[product.id for product in products],
            summary_json={"decisions": []},
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        decisions_summary = []
        total_ready = 0
        total_blocked = 0
        total_human = 0
        total_executed = 0
        for product in products:
            snapshot = self.inspector.inspect_product(product.id)
            decision = self.engine.decide(snapshot)
            record = self.log.record(decision)
            execution = None
            if execute_safe and decision.can_execute_safely:
                execution = ActionExecutor(self.db).execute(record.id, allow_paid=allow_paid)
                if execution.executed:
                    total_executed += 1
            if not execution or not execution.executed:
                self.ensure_queue_item(snapshot, decision)
            total_ready += int(not snapshot.blockers and not snapshot.human_review_required)
            total_blocked += int(bool(snapshot.blockers))
            total_human += int(snapshot.human_review_required or decision.human_review_required)
            decisions_summary.append(
                {
                    "product_id": product.id,
                    "sku": product.sku,
                    "decision_id": record.id,
                    "recommended_action": decision.recommended_action,
                    "status": execution.status if execution else record.status,
                    "human_review_required": decision.human_review_required,
                    "blockers": decision.blockers or snapshot.blockers,
                }
            )

        run.status = "completed"
        run.total_checked = len(products)
        run.total_ready = total_ready
        run.total_blocked = total_blocked
        run.total_needs_human_review = total_human
        run.total_actions_executed = total_executed
        run.summary_json = {"decisions": decisions_summary}
        self.db.commit()
        self.db.refresh(run)
        return self._run_result(run)

    def ensure_queue_item(
        self,
        snapshot: ContentStateSnapshot,
        decision: AutopilotDecisionResult,
    ) -> models.AutopilotQueueItem:
        existing = self.db.scalar(
            select(models.AutopilotQueueItem)
            .where(
                models.AutopilotQueueItem.product_id == snapshot.product_id,
                models.AutopilotQueueItem.content_run_id == snapshot.content_run_id,
                models.AutopilotQueueItem.recommended_action == decision.recommended_action,
                models.AutopilotQueueItem.status == "open",
            )
            .order_by(models.AutopilotQueueItem.id.desc())
        )
        blockers = list(dict.fromkeys([*decision.blockers, *snapshot.blockers]))
        if existing:
            existing.queue_type = decision.queue_type
            existing.priority = decision.priority
            existing.blockers_json = blockers
            self.db.commit()
            self.db.refresh(existing)
            return existing
        item = models.AutopilotQueueItem(
            product_id=snapshot.product_id,
            sku=snapshot.sku,
            content_run_id=snapshot.content_run_id,
            queue_type=decision.queue_type,
            priority=decision.priority,
            status="open",
            recommended_action=decision.recommended_action,
            blockers_json=blockers,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def queue(self, *, status: str = "open") -> list[models.AutopilotQueueItem]:
        return self.db.scalars(
            select(models.AutopilotQueueItem)
            .where(models.AutopilotQueueItem.status == status)
            .order_by(models.AutopilotQueueItem.priority, models.AutopilotQueueItem.id.desc())
        ).all()

    def resolve(self, queue_item_id: int) -> models.AutopilotQueueItem:
        item = self.db.get(models.AutopilotQueueItem, queue_item_id)
        if not item:
            raise ContentAutopilotDataError(f"AutopilotQueueItem {queue_item_id} not found.")
        item.status = "resolved"
        self.db.commit()
        self.db.refresh(item)
        return item

    def dashboard(self) -> AutopilotDashboard:
        products = self.db.scalars(select(models.Product).order_by(models.Product.id)).all()
        snapshots = [self.inspector.inspect_product(product.id) for product in products]
        queue = self.queue()
        blocker_counts = Counter(blocker for snapshot in snapshots for blocker in snapshot.blockers)
        decision_counts = Counter(item.recommended_action for item in queue)
        recent_runs = self.db.scalars(select(models.AutopilotRun).order_by(models.AutopilotRun.id.desc()).limit(10)).all()
        return AutopilotDashboard(
            products_checked=len(products),
            ready=sum(1 for snapshot in snapshots if not snapshot.blockers and not snapshot.human_review_required),
            blocked=sum(1 for snapshot in snapshots if snapshot.blockers),
            needs_human_review=sum(1 for snapshot in snapshots if snapshot.human_review_required),
            publishing_ready=sum(1 for snapshot in snapshots if snapshot.publishing_readiness.get("status") == "ready"),
            top_blockers=[{"blocker": key, "count": count} for key, count in blocker_counts.most_common(8)],
            next_actions=[{"action": key, "count": count} for key, count in decision_counts.most_common(8)],
            queue=[self._queue_item_dict(item) for item in queue[:20]],
            human_review_queue=[
                self._queue_item_dict(item)
                for item in queue
                if item.queue_type in {"human_review", "paid_review", "publishing_approval", "exception"}
            ][:20],
            recent_runs=[self._run_dict(run) for run in recent_runs],
        )

    def _products(self, product_ids: list[int] | None) -> list[models.Product]:
        if product_ids:
            products = self.db.scalars(
                select(models.Product)
                .where(models.Product.id.in_(product_ids))
                .order_by(models.Product.id)
            ).all()
            missing = sorted(set(product_ids) - {product.id for product in products})
            if missing:
                raise ContentAutopilotDataError(f"Products not found: {missing}")
            return products
        return self.db.scalars(select(models.Product).order_by(models.Product.id)).all()

    @staticmethod
    def _run_result(run: models.AutopilotRun) -> AutopilotRunResult:
        return AutopilotRunResult(
            id=run.id,
            status=run.status,
            scope_type=run.scope_type,
            product_ids=run.product_ids_json or [],
            total_checked=run.total_checked,
            total_ready=run.total_ready,
            total_blocked=run.total_blocked,
            total_needs_human_review=run.total_needs_human_review,
            total_actions_executed=run.total_actions_executed,
            summary=run.summary_json or {},
        )

    @staticmethod
    def _queue_item_dict(item: models.AutopilotQueueItem) -> dict:
        return {
            "id": item.id,
            "product_id": item.product_id,
            "sku": item.sku,
            "content_run_id": item.content_run_id,
            "queue_type": item.queue_type,
            "priority": item.priority,
            "status": item.status,
            "recommended_action": item.recommended_action,
            "blockers": item.blockers_json or [],
            "assigned_to": item.assigned_to,
        }

    @staticmethod
    def _run_dict(run: models.AutopilotRun) -> dict:
        return {
            "id": run.id,
            "status": run.status,
            "scope_type": run.scope_type,
            "total_checked": run.total_checked,
            "total_blocked": run.total_blocked,
            "total_needs_human_review": run.total_needs_human_review,
            "total_actions_executed": run.total_actions_executed,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
