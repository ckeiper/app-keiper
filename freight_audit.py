"""Conservative freight reconciliation: never infer historical tariff from current tables."""
from decimal import Decimal
from freight_contestation import money


def assess_freight(expected, charged, *, reference_date=None, charge_source=None,
                   comparable=False, shipment_items=None):
    """Assess only a verified historical seller tariff against verified seller charge.

    Expected and charged must be amounts; caller must explicitly verify that
    they concern the same shipment, logistics context, date and seller.
    Unknown/multi-item composition cannot be assumed comparable.
    """
    expected_value, charged_value = money(str(expected) if expected is not None else "")
    charged_value = money(str(charged) if charged is not None else "")
    base = {
        "status": "Não foi possível conferir",
        "difference": None,
        "reason": "",
    }
    if expected_value is None or charged_value is None:
        base["reason"] = "Valor esperado histórico ou cobrança ao vendedor ausente/inválido"
        return base
    if not reference_date or not charge_source:
        base["reason"] = "Falta data da tarifa histórica ou origem verificável da cobrança"
        return base
    if not comparable or shipment_items is None or shipment_items != 1:
        base["reason"] = "Contexto logístico ou composição do envio não confirmados"
        return base
    delta = (charged_value - expected_value).quantize(Decimal("0.01"))
    if delta >= Decimal("0.01"):
        return {
            "status": "Possível divergência",
            "difference": delta,
            "reason": "Cobrança superior à referência histórica; requer validação pelo Mercado Livre",
        }
    return {
        "status": "Sem diferença positiva",
        "difference": Decimal("0.00"),
        "reason": "Cobrança igual ou inferior à referência informada",
    }
