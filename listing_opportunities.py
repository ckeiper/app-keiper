"""Conservative opportunity signals from verified per-listing order data."""


ACTION_CHECKLISTS = {
    "interrupcao": (
        "Verificar se o anúncio está ativo, pausado ou sem estoque.",
        "Conferir alterações recentes de preço, frete e prazo de envio.",
        "Revisar exposição e campanhas antes de atribuir a queda à conversão.",
    ),
    "queda": (
        "Comparar preço e condições comerciais entre os períodos.",
        "Verificar estoque, prazo de entrega e eventuais alterações no anúncio.",
        "Conferir visitas e publicidade em fontes próprias, se disponíveis.",
    ),
}


def opportunity_actions(kind):
    """Return investigation steps, not unsupported causal diagnoses."""
    return ACTION_CHECKLISTS.get(kind, ())


def listing_opportunities(rows, limit=5):
    """Return ranked signals without implying traffic, conversion or demand."""
    signals = []
    for item_id, m in rows.items():
        current, previous = m["orders"], m["previous_orders"]
        if previous >= 3 and current == 0:
            kind, priority, detail = ("interrupcao", 0,
                                      "Tinha pedidos no período anterior e nenhum no atual")
        elif previous >= 5 and current < previous:
            kind, priority, detail = ("queda", 1,
                                      "Menos pedidos que no período anterior")
        elif previous == 0 and current == 0:
            # Zero sales alone does not establish demand or a problem.
            continue
        else:
            continue
        signals.append({
            "item_id": str(item_id), "kind": kind, "priority": priority,
            "detail": detail, "orders": current, "previous_orders": previous,
            "lost_orders": previous - current,
        })
    signals.sort(key=lambda x: (x["priority"], -x["lost_orders"], x["item_id"]))
    return signals[:limit]
