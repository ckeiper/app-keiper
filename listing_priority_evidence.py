"""Evidence-aware priority enrichment for Anúncios 2.0.

Pure functions: no database access, API requests, or marketplace writes.
Never infer missing margin, stock or operational data as zero.
"""
from decimal import Decimal, InvalidOperation


def nonnegative(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def enrich_priorities(queue, signals_by_item=None):
    """Keep verified-revenue ranking; attach actionable evidence without changing its order.

    signals_by_item maps item_id to optional:
      stock (nonnegative integer), daily_units (positive observed rate),
      margin_current_pct, margin_previous_pct (observed percentages),
      margin_verified (bool), stock_verified (bool).

    Margin is a *signal* only; no fabricated monetary recovery estimate.
    """
    signals_by_item = signals_by_item or {}
    if not queue.get("available"):
        return dict(queue)
    enriched = []
    for row in queue.get("items", []):
        item = dict(row)
        signals = signals_by_item.get(str(item["item_id"])) or {}
        findings = []
        if signals.get("stock_verified") is True:
            stock = nonnegative(signals.get("stock"))
            velocity = nonnegative(signals.get("daily_units"))
            if stock is not None and stock == stock.to_integral_value():
                if stock == 0:
                    findings.append({"code": "stockout", "urgency": "alta",
                                     "evidence": "Estoque confirmado em zero",
                                     "action": "Conferir reposição e disponibilidade logística"})
                elif velocity is not None and velocity > 0:
                    coverage = stock / velocity
                    if coverage < 7:
                        findings.append({"code": "stock_coverage", "urgency": "alta",
                                         "evidence": "Cobertura estimada inferior a 7 dias com velocidade observada",
                                         "action": "Verificar reposição e prazo de abastecimento"})
        if signals.get("margin_verified") is True:
            current = nonnegative(signals.get("margin_current_pct"))
            previous = nonnegative(signals.get("margin_previous_pct"))
            if current is not None and previous is not None and current < previous:
                findings.append({"code": "margin_decline", "urgency": "revisar",
                                 "evidence": "Margem observada caiu em relação ao período anterior",
                                 "action": "Conferir custo, tarifas, promoções e frete"})
        item["additional_findings"] = findings
        item["data_limitations"] = [
            name for name, verified in (
                ("estoque", signals.get("stock_verified") is True),
                ("margem", signals.get("margin_verified") is True))
            if not verified
        ]
        enriched.append(item)
    return dict(queue, items=enriched)
