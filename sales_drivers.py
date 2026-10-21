"""An additive, ordered reading of listing revenue; not causal attribution."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from html import escape

CENT = Decimal('0.01')


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = Decimal(str(value))
        return value if value.is_finite() and value >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def build(evidence, sales):
    unavailable = dict(available=False, reason='Vendas e visitas precisam de cobertura completa nos dois períodos.')
    if not evidence.get('sales_verified') or not sales or not evidence['traffic']['complete']:
        return unavailable
    traffic = evidence['traffic']
    before_visits = number(traffic['previous']['totals']['visitas'])
    visits = number(traffic['current']['totals']['visitas'])
    old_orders, orders = number(sales.get('previous_orders')), number(sales.get('orders'))
    old_value, value = number(sales.get('previous_value')), number(sales.get('value'))
    counts = [before_visits, visits, old_orders, orders]
    if any(v is None or v % 1 for v in counts) or old_value is None or value is None:
        return unavailable
    if not before_visits or not visits:
        return dict(available=False, reason='Há período com zero visitas; não existe relação pedidos/visitas comparável.')
    if not old_orders or not orders:
        return dict(available=False, reason='Há período sem pedidos pagos; não existe valor dos itens por pedido comparável.')
    with localcontext() as ctx:
        ctx.prec = 40
        old_ticket, ticket = old_value / old_orders, value / orders
        old_rate, rate = old_orders / before_visits, orders / visits
        # Sequential substitution: visits, orders/visit, listing value/order.
        traffic_effect = ((visits-before_visits)*old_value/before_visits).quantize(CENT, rounding=ROUND_HALF_UP)
        efficiency_effect = (orders*old_ticket-visits*old_value/before_visits).quantize(CENT, rounding=ROUND_HALF_UP)
        previous = old_value.quantize(CENT, rounding=ROUND_HALF_UP)
        current = value.quantize(CENT, rounding=ROUND_HALF_UP)
        delta = current-previous
        # Put the rounding residual in the last step so displayed cents reconcile.
        ticket_effect = delta-traffic_effect-efficiency_effect
        factors = [
            dict(code='visitas',label='Visitas',before=before_visits,current=visits,unit='count',amount=traffic_effect),
            dict(code='eficiencia',label='Pedidos pagos ÷ visitas',before=old_rate*100,current=rate*100,unit='percent',amount=efficiency_effect),
            dict(code='valor_pedido',label='Valor dos itens por pedido',before=old_ticket,current=ticket,unit='money',amount=ticket_effect),
        ]
    negatives = [factor for factor in factors if factor['amount'] < 0]
    main = min(negatives,key=lambda factor: factor['amount'])['label'] if negatives and delta < 0 else None
    return dict(available=True, previous=previous, current=current, delta=delta,
                factors=factors, main_negative=main)


def money(value, signed=False):
    sign = ('− ' if value < 0 else '+ ' if value > 0 else '') if signed else ''
    formatted = format(abs(value) if signed else value, ',.2f').replace(',','_').replace('.',',').replace('_','.')
    return sign+'R$ '+formatted


def metric(value, unit):
    if unit == 'money':
        return money(value)
    if unit == 'percent':
        return format(value,'.2f').replace('.',',')+'%'
    return str(int(value))


CSS = """<style>
.evidence-drivers{border:1px solid #d8e3f1;background:#fff;border-radius:12px;padding:0 16px;margin:14px 0;min-width:0;max-width:100%;box-sizing:border-box;color:#243651}.evidence-drivers summary{cursor:pointer;padding:15px 0;font-size:13px;font-weight:650;overflow-wrap:anywhere}.drivers-total{display:flex;flex-wrap:wrap;gap:10px 22px;font-size:12px;margin:0 0 12px}.drivers-scroll{overflow-x:auto;max-width:100%;min-width:0}.drivers-table{width:100%;min-width:510px;border-collapse:collapse;font-size:12px}.drivers-table th,.drivers-table td{padding:11px 8px;border-bottom:1px solid #e5ecf4;text-align:right}.drivers-table th:first-child,.drivers-table td:first-child{text-align:left}.drivers-table .negative{color:#ad4949;font-weight:650}.drivers-table .positive{color:#237c65;font-weight:650}.drivers-table tfoot{font-weight:700;background:#f3f7fc}.drivers-method{font-size:11px;color:#63758b;line-height:1.65;margin:12px 0;overflow-wrap:anywhere}.drivers-missing{font-size:12px;line-height:1.6;color:#63758b}
</style>"""


def render(data):
    if not data['available']:
        return '<p class="evidence-meta">Separação entre visitas, eficiência e valor por pedido indisponível: '+escape(data['reason'])+'</p>'
    out = CSS+"<details class='evidence-drivers'><summary>Como o faturamento variou"
    if data['main_negative']:
        out += ' · Maior parcela negativa: '+escape(data['main_negative'])
    out += '</summary><div class="drivers-total"><span>Antes: <b>'+money(data['previous'])+'</b></span><span>Agora: <b>'+money(data['current'])+'</b></span></div>'
    out += '<div class="drivers-scroll"><table class="drivers-table"><thead><tr><th scope="col">Indicador</th><th scope="col">Antes</th><th scope="col">Agora</th><th scope="col">Parcela na variação</th></tr></thead><tbody>'
    for factor in data['factors']:
        tone = 'negative' if factor['amount'] < 0 else 'positive' if factor['amount'] > 0 else 'neutral'
        out += '<tr><th scope="row">'+escape(factor['label'])+'</th><td>'+metric(factor['before'],factor['unit'])+'</td><td>'+metric(factor['current'],factor['unit'])+'</td><td class="'+tone+'">'+money(factor['amount'],True)+'</td></tr>'
    out += '</tbody><tfoot><tr><th scope="row" colspan="3">Variação total do faturamento</th><td>'+money(data['delta'],True)+'</td></tr></tfoot></table></div>'
    out += '<p class="drivers-method">Leitura matemática na ordem: visitas → pedidos pagos por visita → valor dos itens por pedido. Cada etapa troca um indicador e mantém os demais na etapa anterior. A divisão depende dessa ordem; não comprova causalidade nem prevê recuperação. As três parcelas já somam toda a variação, inclusive compensações positivas.</p>'
    out += '<p class="drivers-method">Pedidos contendo este anúncio e valor bruto dos seus itens. O valor por pedido pode mudar por quantidade, variações e descontos; não equivale ao preço anunciado. Pedidos/visitas não é a conversão oficial do Mercado Livre. Comparação dos mesmos dois períodos encerrados exibidos acima; não é um teste estatístico. Ajuste de arredondamento em centavos na última parcela.</p></details>'
    return out
