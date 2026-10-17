"""Verified paid order counts per listing, with explicit completeness gates.

Traffic/conversion cannot be inferred from these order counts.
"""
from datetime import timedelta
from decimal import Decimal
from sales_metrics import created_day, reporting_today, summarize


def listing_sales_summary(orders, items, covered, item_id, end=None, days=30):
    end = end or reporting_today()
    start = end - timedelta(days=days - 1)
    result = {"start": start.isoformat(), "end": end.isoformat(),
              "orders": None, "units": None, "gross_items": None,
              "ticket": None, "reason": None}
    summary = summarize(orders, start, end, set(covered))
    if not summary["complete"] or summary["orders"] is None:
        result["reason"] = "Período sem cobertura completa ou com pedidos não verificáveis."
        return result
    if summary["unknown_units"]:
        result["reason"] = "Há pedidos pagos sem quantidade verificável."
        return result
    paid = {}
    for row in orders:
        day = created_day(row.get("criado_em"))
        if not day or not start <= day <= end:
            continue
        if row.get("status") != "paid" or row.get("moeda") != "BRL":
            continue
        payments = row.get("pagamentos_json")
        if not isinstance(payments, list) or not any(
                isinstance(p, dict) and p.get("status") == "approved"
                for p in payments):
            continue
        paid[(row.get("conexao_id"), str(row.get("pedido_id")))] = row
    by_order = {}
    for item in items:
        key = (item.get("conexao_id"), str(item.get("pedido_id")))
        if key not in paid:
            continue
        qty = item.get("quantidade")
        if type(qty) is not int or qty <= 0 or not item.get("item_id"):
            result["reason"] = "Há itens de pedidos sem identificação ou quantidade confiável."
            return result
        by_order.setdefault(key, []).append(item)
    # A paid order without complete item mapping cannot be used to claim
    # an item has zero sales. Compare against the verified order unit count.
    for key, order in paid.items():
        if sum(i["quantidade"] for i in by_order.get(key, [])) != order.get("unidades"):
            result["reason"] = "Há pedidos pagos com vínculo de anúncios incompleto."
            return result
    # The order's total can include freight, coupons and other items. Only
    # sum the verified per-item unit price; never allocate the order total.
    gross = Decimal(0)
    for key, group in by_order.items():
        for item in group:
            try:
                price = Decimal(str(item.get("preco_unitario")))
            except (TypeError, ValueError, ArithmeticError):
                result["reason"] = "Preço unitário de item vendido não verificável."
                return result
            if not price.is_finite() or price < 0:
                result["reason"] = "Preço unitário de item vendido não verificável."
                return result
            if str(item["item_id"]) == str(item_id):
                gross += price * item["quantidade"]
    matched = [i for key, group in by_order.items() for i in group
               if str(i["item_id"]) == str(item_id)]
    result["orders"] = len({(i["conexao_id"], str(i["pedido_id"])) for i in matched})
    result["units"] = sum(i["quantidade"] for i in matched)
    result["gross_items"] = gross
    result["ticket"] = gross / result["orders"] if result["orders"] else None
    return result
