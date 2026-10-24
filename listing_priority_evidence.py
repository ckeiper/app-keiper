"""Evidence-aware priority enrichment for Anúncios 2.0.

Pure functions: no database access, API requests, or marketplace writes.
Never infer missing margin, stock or operational data as zero.
"""
from decimal import Decimal, InvalidOperation, ROUND_DOWN, localcontext


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (ValueError, TypeError, InvalidOperation):
        return None



def nonnegative(value):
    result = number(value)
    return result if result is not None and result >= 0 else None


def coverage_evidence(stock, velocity, coverage, signals):
    # Truncate for display so a value below seven never appears as 7.00 days.
    def observed(value):
        with localcontext() as context:
            context.rounding = ROUND_DOWN
            rounded = format(value, '.2f')
        return '<0,01' if 0 < value < Decimal('0.01') else rounded.replace('.', ',')
    evidence = ('Cobertura estimada inferior a 7 dias: ' + observed(coverage) +
                ' dias, com ' + str(int(stock)) + ' unidades registradas e média observada de ' +
                observed(velocity) + ' unidades/dia.')
    units = nonnegative(signals.get('velocity_units'))
    days = signals.get('velocity_days')
    if (units is not None and units == units.to_integral_value() and
            type(days) is int and days > 0 and units / days == velocity):
        evidence += ' Base: ' + str(int(units)) + ' unidades vendidas em ' + str(days) + ' dias encerrados.'
    return evidence + ' Referência pelo ritmo passado, sem previsão de demanda ou confirmação de estoque Full.'


def enrich_priorities(queue, signals_by_item=None):
    """Keep verified-revenue ranking; attach actionable evidence without changing its order.

    signals_by_item maps item_id to optional:
      stock (nonnegative integer), daily_units (positive observed rate),
      margin_current_pct, margin_previous_pct (observed percentages),
      margin_verified (bool), stock_verified (bool),
      margin_documented (bool), contribution_verified (bool),
      contribution_current (documented period contribution).

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
        stock = nonnegative(signals.get("stock"))
        stock_verified = bool(signals.get("stock_verified") is True and stock is not None
                              and stock == stock.to_integral_value())
        current = number(signals.get("margin_current_pct"))
        previous = number(signals.get("margin_previous_pct"))
        margin_verified = bool(signals.get("margin_verified") is True
                               and current is not None and previous is not None)
        if stock_verified:
            velocity = nonnegative(signals.get("daily_units"))
            if stock is not None and stock == stock.to_integral_value():
                if stock == 0:
                    findings.append({"code": "stockout", "urgency": "alta",
                                     "evidence": "Estoque confirmado em zero na leitura recente do catálogo; não comprova saldo no Full.",
                                     "action": "Conferir reposição e disponibilidade logística"})
                elif velocity is not None and velocity > 0:
                    coverage = stock / velocity
                    if coverage < 7:
                        findings.append({"code": "stock_coverage", "urgency": "alta",
                                         "evidence": coverage_evidence(stock, velocity, coverage, signals),
                                         "action": "Verificar reposição e prazo de abastecimento"})
        contribution = number(signals.get("contribution_current"))
        if (signals.get("margin_documented") is True and signals.get("contribution_verified") is True
                and contribution is not None and Decimal(format(contribution,'.2f')) < 0):
            from freight_comparison import format_brl
            findings.append({"code":"negative_contribution", "urgency":"alta",
                "evidence":"Contribuição documentada negativa: "+format_brl(contribution),
                "action":"Conferir fontes, custo, tarifas, frete, impostos, publicidade e ajustes na rentabilidade do anúncio"})
        if margin_verified and Decimal(format(current-previous,'.2f')) < 0:
            evidence = "Margem observada caiu em relação ao período anterior"
            if signals.get("margin_documented") is True:
                evidence = ("Margem documentada caiu de "+format(previous,'.2f').replace('.',',')+
                    "% para "+format(current,'.2f').replace('.',',')+"% ("+
                    format(current-previous,'.2f').replace('.',',')+" p.p.)")
            findings.append({"code": "margin_decline", "urgency": "revisar",
                             "evidence": evidence,
                             "action": ("Abrir a rentabilidade do anúncio e conferir componentes e fontes dos dois períodos"
                                        if signals.get("margin_documented") is True else
                                        "Conferir custo, tarifas, promoções e frete")})
        item["additional_findings"] = findings
        item["data_limitations"] = [
            name for name, verified in (
                ("estoque", stock_verified),
                ("margem", margin_verified))
            if not verified
        ]
        enriched.append(item)
    return dict(queue, items=enriched)
