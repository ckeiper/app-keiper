"""Period-over-period comparisons for verified listing sales.

Never infer growth from incomplete periods or use a percentage when the
previous period was zero.
"""
from decimal import Decimal


def comparison(current, previous):
    fields = ("orders", "units", "gross_items")
    if any(current.get(k) is None or previous.get(k) is None for k in fields):
        return {"available": False, "reason":
                current.get("reason") or previous.get("reason") or
                "Um dos períodos não possui dados verificados."}
    result = {"available": True, "reason": None}
    for field in fields:
        now, before = Decimal(str(current[field])), Decimal(str(previous[field]))
        difference = now - before
        if before == 0:
            status = "sem_movimento" if now == 0 else "novas_vendas"
            percent = None
        else:
            percent = difference * 100 / before
            status = ("alta" if difference > 0 else
                      "queda" if difference < 0 else "estavel")
        result[field] = {"current": now, "previous": before,
                         "difference": difference, "percent": percent,
                         "status": status}
    return result
