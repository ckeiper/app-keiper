"""Evidence-based listing diagnostic rules; no causal claims or fabricated metrics.

The caller supplies comparable metrics from verified periods. Missing metrics
produce explicit uncertainty rather than zeros.
"""
from decimal import Decimal, InvalidOperation


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def diagnose_listing_periods(current, previous):
    """Return ordered findings for a listing, without inferring missing data.

    Inputs are dictionaries with visits, orders and revenue. A period's
    conversion rate is calculated only with positive observed visits.
    Thresholds are prioritization heuristics, not proof of causation.
    """
    fields = ("visits", "orders", "revenue")
    c = {key: _number(current.get(key)) for key in fields}
    p = {key: _number(previous.get(key)) for key in fields}
    findings = []
    if any(c[key] is None or p[key] is None for key in fields):
        return [{"code": "insufficient_data", "severity": "info",
                 "title": "Dados insuficientes para comparar os períodos",
                 "detail": "Não atribuir queda a tráfego ou conversão sem dados verificados."}]
    if p["orders"] > 0 and c["orders"] <= p["orders"] * Decimal("0.8"):
        findings.append({"code": "orders_drop", "severity": "warning",
                         "title": "Pedidos caíram pelo menos 20%",
                         "detail": "Comparar tráfego e conversão antes de propor a causa."})
    if p["visits"] > 0 and c["visits"] <= p["visits"] * Decimal("0.8"):
        findings.append({"code": "traffic_drop", "severity": "warning",
                         "title": "Visitas caíram pelo menos 20%",
                         "detail": "Investigar posicionamento, preço, estoque e publicidade; causa não confirmada."})
    if c["visits"] > 0 and p["visits"] > 0:
        current_rate = c["orders"] / c["visits"]
        previous_rate = p["orders"] / p["visits"]
        if previous_rate > 0 and current_rate <= previous_rate * Decimal("0.8"):
            findings.append({"code": "conversion_drop", "severity": "warning",
                             "title": "Conversão caiu pelo menos 20%",
                             "detail": "Revisar oferta, preço, imagens e concorrência; causa não confirmada."})
    else:
        findings.append({"code": "conversion_unavailable", "severity": "info",
                         "title": "Conversão indisponível",
                         "detail": "É necessário ter visitas observadas em ambos os períodos."})
    if not findings:
        findings.append({"code": "no_alert", "severity": "info",
                         "title": "Nenhuma queda acima dos limites configurados",
                         "detail": "Isso não comprova ausência de outras oportunidades."})
    return findings
