"""Adapt synchronized listing snapshots to verified priority signals.

Only recent catalogue readings are accepted. Sales velocity requires a
complete verified ranking period. No margin history is inferred from cost.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def _number(value):
    try:
        n = Decimal(str(value))
        return n if n.is_finite() and n >= 0 else None
    except (TypeError, ValueError, InvalidOperation):
        return None


def listing_signals(listings, ranking, days, now=None, max_age_seconds=21600):
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    result = {}
    for listing in listings:
        item_id = str(listing["item_id"])
        stamp = _number(listing.get("atualizado_em"))
        stock = _number(listing.get("quantidade"))
        fresh = stamp is not None and 0 <= Decimal(str(now)) - stamp <= max_age_seconds
        verified = bool(fresh and stock is not None and stock == stock.to_integral_value())
        signals = {"stock_verified": verified}
        if verified:
            signals["stock"] = stock
            metrics = (ranking.get("rows") or {}).get(item_id) if ranking.get("available") else None
            if metrics and isinstance(days, int) and days > 0:
                units = _number(metrics.get("units"))
                if units is not None and units > 0:
                    signals["daily_units"] = units / days
        result[item_id] = signals
    return result
