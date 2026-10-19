"""Pure, read-only freight charge comparison; no column inference or database access."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class FreightComparisonError(ValueError):
    pass


def money(value):
    if value is None or isinstance(value, bool):
        raise FreightComparisonError("Valor monetario invalido")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise FreightComparisonError("Valor monetario invalido") from exc
    if not amount.is_finite() or amount < 0:
        raise FreightComparisonError("Valor monetario invalido")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compare_freight(charged, expected, tolerance="0.01"):
    paid = money(charged)
    baseline = money(expected)
    margin = money(tolerance)
    difference = paid - baseline
    status = ("acima" if difference > margin else
              "abaixo" if difference < -margin else "dentro_tolerancia")
    return {"charged": str(paid), "expected": str(baseline),
            "difference": str(difference), "status": status}
