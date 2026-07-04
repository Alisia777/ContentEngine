from app import models
from app.intelligence.metrics import coalesce_rate


CTR_THRESHOLD = 0.02
CONVERSION_THRESHOLD = 0.03
RETURN_RATE_THRESHOLD = 0.08
LOW_STOCK_QTY = 20
LOW_DAYS_OF_STOCK = 14


def score_intelligence(
    latest_metric: models.ProductMetricSnapshot | None,
    market_signals: list[models.MarketSignal],
) -> dict:
    flags: list[str] = []
    angles: list[str] = []
    market_risks: list[str] = []
    warnings: list[str] = []
    objective = "balanced_product_explanation"
    stock_risk = None
    price_positioning = "unknown"

    if latest_metric:
        ctr = coalesce_rate(latest_metric.ctr, latest_metric.clicks, latest_metric.views)
        conversion = coalesce_rate(latest_metric.conversion_rate, latest_metric.orders, latest_metric.clicks)
        if ctr is not None and ctr < CTR_THRESHOLD:
            flags.append("low_ctr")
            objective = "improve_clickability"
            angles += ["strong_hook", "curiosity_gap", "benefit_first_frame"]
        if (ctr is None or ctr >= CTR_THRESHOLD) and conversion is not None and conversion < CONVERSION_THRESHOLD:
            flags.append("low_conversion")
            objective = "improve_conversion"
            angles += ["objection_handling", "trust_builder", "use_case_explanation"]
        if (
            latest_metric.days_of_stock is not None
            and latest_metric.days_of_stock < LOW_DAYS_OF_STOCK
            or latest_metric.stock_qty is not None
            and latest_metric.stock_qty < LOW_STOCK_QTY
        ):
            flags.append("stock_risk")
            stock_risk = "low_stock"
            warnings.append("avoid aggressive demand generation")
        if latest_metric.returns_rate is not None and latest_metric.returns_rate > RETURN_RATE_THRESHOLD:
            flags.append("high_returns")
            angles += ["expectation_setting", "usage_instruction", "size_fit_clarity"]
        if latest_metric.ad_spend and latest_metric.ad_spend > 0:
            weak_orders = latest_metric.ad_orders is None or latest_metric.ad_orders < 1
            weak_revenue = latest_metric.ad_revenue is not None and latest_metric.ad_revenue < latest_metric.ad_spend
            if weak_orders or weak_revenue:
                flags.append("paid_traffic_efficiency_risk")
                angles += ["landing_message_alignment", "offer_clarity"]

    for signal in market_signals:
        notes = (signal.notes or "").lower()
        competitor_cheaper = "cheaper" in notes or "дешев" in notes
        if latest_metric and signal.competitor_price and latest_metric.avg_price:
            competitor_cheaper = competitor_cheaper or signal.competitor_price < latest_metric.avg_price
        if competitor_cheaper or signal.signal_type == "price_pressure":
            market_risks.append("competitor_price_pressure")
            price_positioning = "competitor_cheaper"
            angles += ["value_explanation", "quality_difference", "bundle_value"]

    if not angles:
        angles = ["value_explanation", "use_case_explanation"]

    return {
        "performance_flags": _unique(flags),
        "recommended_objective": objective,
        "recommended_creative_angles": _unique(angles),
        "market_risks": _unique(market_risks),
        "warnings": _unique(warnings),
        "stock_risk": stock_risk,
        "price_positioning": price_positioning,
    }


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))

