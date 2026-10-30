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


def format_brl(value):
    """Format an already validated decimal amount for Brazilian display."""
    amount = Decimal(str(value))
    sign = "-" if amount < 0 else ""
    formatted = format(abs(amount), ",.2f").replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + sign + formatted


def render_freight_comparison_demo():
    """Static demonstration only; never represents charges from a real store."""
    from html import escape

    examples = [
        ("Exemplo A", "18.50", "15.00"),
        ("Exemplo B", "9.00", "12.00"),
        ("Exemplo C", "10.01", "10.00"),
    ]
    labels = {"acima": "Acima do esperado", "abaixo": "Abaixo do esperado",
              "dentro_tolerancia": "Dentro da tolerancia"}
    rows = []
    for name, charged, expected in examples:
        result = compare_freight(charged, expected)
        rows.append("<tr><td>" + escape(name) + "</td><td>"
                    + format_brl(result["charged"]) + "</td><td>"
                    + format_brl(result["expected"]) + "</td><td>"
                    + format_brl(result["difference"]) + "</td><td>"
                    + escape(labels[result["status"]]) + "</td></tr>")
    return ("<section class='card'><h3>Demonstracao de divergencias de frete</h3>"
            "<p><strong>Dados ficticios.</strong> Os valores abaixo sao exemplos "
            "para validar a apresentacao. Nao representam cobrancas de nenhuma loja.</p>"
            "<div style='overflow-x:auto'><table><thead><tr><th>Exemplo</th>"
            "<th>Cobrado</th><th>Esperado</th><th>Diferenca</th><th>Situacao</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
            "<p>Tolerancia ilustrativa: R$ 0,01. Nenhuma conciliacao real foi "
            "executada.</p></section>")


def compare_freight_orders(records, tolerance="0.01"):
    """Compare previously verified per-order charges, without reading uploads."""
    if not isinstance(records, (list, tuple)):
        raise FreightComparisonError("Lista de pedidos invalida")
    margin = money(tolerance)
    seen = set()
    results = []
    for item in records:
        if not isinstance(item, dict):
            raise FreightComparisonError("Pedido invalido")
        order_id = item.get("order_id")
        if not isinstance(order_id, str) or not order_id.strip():
            raise FreightComparisonError("Identificador de pedido invalido")
        order_id = order_id.strip()
        if order_id in seen:
            raise FreightComparisonError("Pedido duplicado")
        seen.add(order_id)
        result = compare_freight(item.get("charged"), item.get("expected"), margin)
        results.append({"order_id": order_id, **result})
    return results


def summarize_freight_orders(records, tolerance="0.01"):
    """Summarize verified per-order charges; values are strings in BRL units."""
    rows = compare_freight_orders(records, tolerance)
    statuses = {"acima": 0, "abaixo": 0, "dentro_tolerancia": 0}
    excess = Decimal("0.00")
    savings = Decimal("0.00")
    for row in rows:
        status = row["status"]
        statuses[status] += 1
        delta = Decimal(row["difference"])
        if status == "acima":
            excess += delta
        elif status == "abaixo":
            savings += -delta
    return {"total_orders": len(rows), "counts": statuses,
            "excess_charges": str(excess.quantize(Decimal("0.01"))),
            "below_expected": str(savings.quantize(Decimal("0.01")))}
