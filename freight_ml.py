"""Parse Mercado Livre shipment costs without confusing buyer and seller charges."""
from freight_contestation import money


def seller_shipping_cost(payload, seller_id):
    """Return (Decimal amount, reason); never fall back to receiver or gross_amount."""
    if not isinstance(payload, dict):
        return None, "Resposta inválida da API de custos."
    senders = payload.get("senders")
    if not isinstance(senders, list):
        return None, "A API não informou a lista de vendedores."
    seller = str(seller_id).strip()
    if not seller or seller == "None":
        return None, "Identificador do vendedor indisponível."
    matched = [entry for entry in senders if isinstance(entry, dict)
               and str(entry.get("user_id")) == seller]
    if len(matched) != 1:
        return None, "Não foi possível identificar um único custo deste vendedor."
    amount = money(str(matched[0].get("cost"))
                   if matched[0].get("cost") is not None else "")
    if amount is None:
        return None, "Custo do vendedor ausente ou inválido."
    return amount, None


def seller_shipment_item_count(payload, seller_id):
    """Count units belonging to the seller; unknown responses must not imply one item."""
    if not isinstance(payload, list):
        return None
    seller = str(seller_id).strip()
    units = 0
    for item in payload:
        if not isinstance(item, dict) or str(item.get("sender_id")) != seller:
            return None
        quantity = item.get("quantity")
        if type(quantity) is not int or quantity < 1:
            return None
        units += quantity
    return units if units > 0 else None
