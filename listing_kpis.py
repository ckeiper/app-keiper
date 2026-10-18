"""Aggregate verified listing ranking metrics for a compact performance header."""
from decimal import Decimal


def listing_kpis(rows):
    values = list(rows.values())
    active = [r for r in values if r["orders"] > 0]
    total = sum((r["value"] for r in values), Decimal(0))
    orders = sum(r["orders"] for r in values)
    units = sum(r["units"] for r in values)
    leading = max(values, key=lambda r: r["value"]) if values else None
    rising = sum(1 for r in values if r["previous_orders"] > 0 and r["orders"] > r["previous_orders"])
    falling = sum(1 for r in values if r["previous_orders"] > 0 and r["orders"] < r["previous_orders"])
    newly_selling = sum(1 for r in values if r["previous_orders"] == 0 and r["orders"] > 0)
    return {
        "value": total,
        "orders_by_listing": orders,
        "units": units,
        "selling_listings": len(active),
        "listed": len(values),
        "rising": rising,
        "falling": falling,
        "newly_selling": newly_selling,
        "average_value_per_listing_order": total / orders if orders else None,
        "top_listing_share_pct": (
            leading["value"] * 100 / total if total else None),
    }
