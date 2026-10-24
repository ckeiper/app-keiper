"""Conservative per-listing contribution calculation.

Never present incomplete fee, shipping, tax or advertising inputs as net profit.
Amounts are in BRL, and costs are per unit.
"""
from decimal import Decimal, InvalidOperation


def amount(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def contribution(revenue, units, unit_cost=None, marketplace_fees=None,
                 seller_shipping=None, taxes=None, advertising=None):
    """Return verified components and a contribution only when all costs are known."""
    revenue = amount(revenue)
    units = amount(units)
    inputs = dict(unit_cost=unit_cost, marketplace_fees=marketplace_fees,
                  seller_shipping=seller_shipping, taxes=taxes, advertising=advertising)
    verified = {key: amount(value) for key, value in inputs.items()}
    missing = [key for key, value in verified.items() if value is None]
    if revenue is None or units is None or units != units.to_integral_value():
        return {"available": False, "reason": "Receita ou unidades não verificáveis.",
                "missing": missing, "contribution": None, "margin_pct": None}
    if missing:
        return {"available": False, "reason": "Custos incompletos; lucro não calculado.",
                "missing": missing, "revenue": revenue, "units": units,
                "contribution": None, "margin_pct": None}
    total_costs = (units * verified["unit_cost"] +
                   verified["marketplace_fees"] +
                   verified["seller_shipping"] +
                   verified["taxes"] +
                   verified["advertising"])
    result = revenue - total_costs
    return {"available": True, "revenue": revenue, "units": units,
            "total_costs": total_costs, "contribution": result,
            "margin_pct": (result * 100 / revenue if revenue else None),
            "missing": [], "reason": None}
