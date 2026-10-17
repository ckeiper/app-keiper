"""Explainable listing health checks from synchronized listing fields only.

No causal attribution to sales, traffic or conversion is made here.
"""
from decimal import Decimal, InvalidOperation


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        n = Decimal(str(value))
        return n if n.is_finite() else None
    except (ValueError, InvalidOperation, TypeError):
        return None


def diagnose_listing(item):
    actions = []
    def add(priority, title, evidence, next_step):
        actions.append({"priority": priority, "title": title,
                        "evidence": evidence, "action": next_step})
    status = str(item.get("status") or "").lower()
    if status == "paused":
        add("alta", "Anúncio pausado", "O status registrado é pausado.",
            "Verifique o motivo da pausa antes de reativar.")
    elif status and status != "active":
        add("revisar", "Status precisa de conferência",
            "Status registrado: " + status[:80] + ".",
            "Confira restrições e situação no Mercado Livre.")
    elif not status:
        add("dados", "Status não disponível", "Status não coletado.",
            "Atualize os dados do anúncio.")

    stock = _number(item.get("quantidade"))
    if stock is None or stock < 0 or stock != stock.to_integral_value():
        add("dados", "Estoque não verificado", "Quantidade ausente ou inválida.",
            "Atualize os dados antes de concluir que o estoque acabou.")
    elif stock == 0:
        add("alta", "Estoque zerado", "Quantidade disponível registrada: 0.",
            "Confira reposição e disponibilidade de venda.")
    elif stock <= 3:
        add("media", "Estoque baixo", "Quantidade registrada: " + str(int(stock)) + ".",
            "Verifique a necessidade de reposição.")

    photos = _number(item.get("fotos"))
    if photos is None or photos < 0 or photos != photos.to_integral_value():
        add("dados", "Fotos não verificadas", "Contagem de fotos ausente ou inválida.",
            "Atualize os dados antes de avaliar as imagens.")
    elif photos == 0:
        add("alta", "Nenhuma foto registrada", "Contagem de fotos registrada: 0.",
            "Verifique se há imagens e se a coleta foi concluída.")
    elif photos < 5:
        add("media", "Poucas fotos", "Foram registradas " + str(int(photos)) +
            " foto(s). O limite de 5 é sugestão editorial, não regra do ML.",
            "Avalie incluir fotos de dimensões, aplicações e detalhes.")

    clips = _number(item.get("clips"))
    if clips is not None and clips == 0:
        add("oportunidade", "Vídeo não identificado", "Nenhum clip foi registrado.",
            "Avalie produzir vídeo demonstrativo, se adequado.")

    price = _number(item.get("preco"))
    if price is None or price <= 0:
        add("dados", "Preço não verificável", "Preço ausente ou inválido.",
            "Atualize o preço; não há comparação de competitividade nesta análise.")

    if not actions:
        add("ok", "Nenhum alerta básico identificado",
            "Status, estoque, fotos e preço não acionaram alertas.",
            "Para avaliar queda de vendas, precisamos de dados históricos confiáveis.")
    order = {"alta": 0, "media": 1, "revisar": 2, "oportunidade": 3, "dados": 4, "ok": 5}
    return sorted(actions, key=lambda a: order[a["priority"]])
