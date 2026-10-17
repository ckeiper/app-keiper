"""Free, deterministic freight contestation templates. No AI/API usage."""
from decimal import Decimal, InvalidOperation
from html import escape


def money(value):
    """Normalize a BRL amount supplied as a string, without floating point."""
    raw = (value or "").strip().replace("R$", "").replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        amount = Decimal(raw)
        if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
            return None
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def brl(amount):
    return "R$ " + format(amount, ".2f").replace(".", ",") if amount is not None else "não informado"


def generate_messages(order_id="", listing_id="", shipment_id="", expected="", charged=""):
    """User-entered values are references, not verified evidence of overcharging."""
    expected_amount, charged_amount = money(expected), money(charged)
    diff = (charged_amount - expected_amount
            if expected_amount is not None and charged_amount is not None else None)
    if diff is not None and diff <= 0:
        diff = None
    order = order_id.strip() or "não informado"
    listing = listing_id.strip() or "não informado"
    shipment = shipment_id.strip() or "não informado"
    details = (
        "Pedido: " + order + "\n"
        "Anúncio: " + listing + "\n"
        "Envio: " + shipment + "\n"
        "Frete de referência informado: " + brl(expected_amount) + "\n"
        "Frete cobrado informado: " + brl(charged_amount) + "\n"
        "Possível diferença positiva: " + brl(diff) + "\n"
    )
    caution = ("Os valores acima foram informados manualmente e precisam ser "
               "confirmados considerando data da venda, modalidade logística, "
               "quantidade, descontos e composição do envio.\n")
    return [
        ("Contestação inicial",
         "Olá! Solicito uma conferência da cobrança de frete desta operação.\n\n"
         + details + "\n" + caution
         + "Peço o detalhamento do cálculo aplicado ao vendedor, incluindo tarifa, "
         "peso, dimensões, modalidade e eventuais ajustes. Se houver cobrança "
         "incorreta confirmada, solicito a correção e restituição cabível."),
        ("Resposta para justificativa genérica",
         "Obrigado pelo retorno. Solicito uma análise específica da operação, "
         "pois a resposta recebida ainda não esclareceu os valores apresentados.\n\n"
         + details + "\n" + caution
         + "Por favor, indiquem a base de cálculo, o valor debitado do vendedor "
         "e os critérios aplicados, em vez de apenas uma orientação geral."),
        ("Pedido de reanálise",
         "Solicito reanálise do chamado relacionado ao frete abaixo, pois a "
         "divergência apontada não foi esclarecida de forma individualizada.\n\n"
         + details + "\n" + caution
         + "Peço nova conferência, resposta fundamentada e, caso seja comprovado "
         "erro na cobrança, o ajuste e a restituição correspondente.")
    ]


def render_generator(values):
    """HTML fragment; escaped input, editable textarea and copy buttons."""
    keys = (("order_id", "Número do pedido"), ("listing_id", "Código do anúncio (MLB)"),
            ("shipment_id", "Número do envio"), ("expected", "Frete de referência (R$)"),
            ("charged", "Frete cobrado (R$)"))
    html = ['<div class="card"><h2>Gerador gratuito de contestações de frete</h2>',
            '<p>Preencha os dados para montar três mensagens editáveis. '
            'Valores informados aqui não são verificados automaticamente; '
            'não comprovam cobrança indevida.</p>',
            '<form method="get">']
    for key, label in keys:
        html.append('<label style="display:block;margin:12px 0 4px">' + escape(label) + '</label>')
        html.append('<input style="width:100%;max-width:440px" name="' + key
                    + '" maxlength="100" value="' + escape(str(values.get(key, "")), quote=True)
                    + '">')
    html.append('<p><button class="btn" type="submit">Gerar mensagens</button></p></form></div>')
    for idx, (title, message) in enumerate(generate_messages(
            *(str(values.get(key, ""))[:100] for key, _ in keys))):
        field_id = "contestacao_" + str(idx)
        html.extend(['<div class="card"><h3>', escape(title), '</h3>',
                     '<textarea id="', field_id,
                     '" style="width:100%;min-height:300px;box-sizing:border-box">',
                     escape(message), '</textarea>',
                     '<p><button class="btn" type="button" onclick="'
                     'navigator.clipboard.writeText(document.getElementById(\'', field_id,
                     '\').value).then(()=>{this.textContent=\'Copiado!\'})">',
                     'Copiar mensagem editada</button></p></div>'])
    return "".join(html)
