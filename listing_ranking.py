"""Verified bulk listing sales ranking, with no per-listing DB queries."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from sales_metrics import created_day, reporting_today, summarize


def ranking_metrics(orders, items, covered, listing_ids, end=None, days=30,
                    pending=False):
    end = end or reporting_today()
    start = end - timedelta(days=days - 1)
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    result = {"available": False, "reason": None, "rows": {}}
    if pending:
        result["reason"] = "Existem pedidos ainda não verificados."
        return result
    for a, b in ((start, end), (previous_start, previous_end)):
        summary = summarize(orders, a, b, set(covered))
        if not summary["complete"] or summary["orders"] is None or summary["unknown_units"]:
            result["reason"] = "Cobertura ou pedidos não verificáveis em um dos períodos."
            return result
    paid = {}
    for row in orders:
        day = created_day(row.get("criado_em"))
        if day is None or not previous_start <= day <= end:
            continue
        if row.get("status") != "paid" or row.get("moeda") != "BRL":
            continue
        payments = row.get("pagamentos_json")
        if not isinstance(payments, list) or not any(
                isinstance(p, dict) and p.get("status") == "approved"
                for p in payments):
            continue
        paid[(row.get("conexao_id"), str(row.get("pedido_id")))] = row
    by_order = defaultdict(list)
    for item in items:
        key = (item.get("conexao_id"), str(item.get("pedido_id")))
        if key in paid:
            qty = item.get("quantidade")
            if type(qty) is not int or qty <= 0 or not item.get("item_id"):
                result["reason"] = "Há itens sem anúncio ou quantidade verificável."
                return result
            by_order[key].append(item)
    for key, order in paid.items():
        if sum(i["quantidade"] for i in by_order[key]) != order.get("unidades"):
            result["reason"] = "Vínculo incompleto entre pedidos e anúncios."
            return result
    rows = {str(item_id): {
        "orders": 0, "units": 0, "value": Decimal(0),
        "previous_orders": 0, "previous_units": 0,
        "previous_value": Decimal(0)} for item_id in listing_ids}
    seen = set()
    for key, group in by_order.items():
        day = created_day(paid[key]["criado_em"])
        prefix = "" if day >= start else "previous_"
        for item in group:
            item_id = str(item["item_id"])
            if item_id not in rows:
                continue
            try:
                price = Decimal(str(item.get("preco_unitario")))
            except (InvalidOperation, ValueError, TypeError):
                result["reason"] = "Há preços unitários de venda não verificáveis."
                return result
            if not price.is_finite() or price < 0:
                result["reason"] = "Há preços unitários de venda não verificáveis."
                return result
            metrics = rows[item_id]
            metrics[prefix + "units"] += item["quantidade"]
            metrics[prefix + "value"] += price * item["quantidade"]
            distinct_key = (key, item_id)
            if distinct_key not in seen:
                seen.add(distinct_key)
                metrics[prefix + "orders"] += 1
    for metrics in rows.values():
        previous = metrics["previous_orders"]
        current = metrics["orders"]
        metrics["growth_pct"] = (
            Decimal(current - previous) * 100 / previous
            if previous else None)
        metrics["trend"] = (
            "novas" if current and not previous else
            "estavel" if current == previous else
            "alta" if current > previous else "queda")
        metrics["ticket"] = (metrics["value"] / current if current else None)
    result.update(available=True, rows=rows)
    return result
