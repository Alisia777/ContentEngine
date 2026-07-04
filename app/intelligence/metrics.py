def safe_rate(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def coalesce_rate(explicit_rate: float | None, numerator: int | None, denominator: int | None) -> float | None:
    return explicit_rate if explicit_rate is not None else safe_rate(numerator, denominator)

