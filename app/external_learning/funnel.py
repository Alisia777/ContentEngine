"""QEEP funnel diagnosis mapping."""

from __future__ import annotations

from ._common import normalise_text
from .schema import FunnelDecision, FunnelObservation


_QEEP_STATUS_MAP: dict[str, FunnelDecision] = {
    "чинить карточку": FunnelDecision.CREATIVE,
    "риск oos": FunnelDecision.SUPPLY,
    "чинить выкуп": FunnelDecision.EXPECTATION,
    "оптимизировать рекламу": FunnelDecision.ADVERTISING,
    "суперзвезда": FunnelDecision.SCALE,
    "масштабировать": FunnelDecision.SCALE,
    "наблюдать": FunnelDecision.OBSERVE,
    "мало данных": FunnelDecision.MEASUREMENT,
}


def map_funnel_decision(observation: FunnelObservation) -> FunnelDecision:
    """Resolve an action, preferring the source workbook's governed status."""

    source_status = normalise_text(observation.source_status)
    if source_status in _QEEP_STATUS_MAP:
        return _QEEP_STATUS_MAP[source_status]

    source_action = normalise_text(observation.source_action)
    if "перв" in source_action and (
        "экран" in source_action or "контент" in source_action
    ):
        return FunnelDecision.CREATIVE
    if "остат" in source_action or "постав" in source_action:
        return FunnelDecision.SUPPLY
    if "выкуп" in source_action or "ожидани" in source_action:
        return FunnelDecision.EXPECTATION
    if "реклам" in source_action or "дрр" in source_action:
        return FunnelDecision.ADVERTISING
    if "масштаб" in source_action or "увеличить трафик" in source_action:
        return FunnelDecision.SCALE

    if observation.stock is not None and observation.stock <= 0:
        return FunnelDecision.SUPPLY
    if observation.orders is None or observation.orders < 30:
        return FunnelDecision.MEASUREMENT
    if (
        observation.conversion_visit_to_order is not None
        and observation.conversion_visit_to_order < 0.02
    ):
        return FunnelDecision.CREATIVE
    if observation.buyout_rate is not None and observation.buyout_rate < 0.65:
        return FunnelDecision.EXPECTATION
    if observation.drr is not None and observation.drr > 0.35:
        return FunnelDecision.ADVERTISING
    return FunnelDecision.OBSERVE
