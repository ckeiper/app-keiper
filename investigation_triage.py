"""Order checks by operational scope; never rank unproven causes or promise recovery."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from competitor_monitor import money
from offer_history import price_events

BR = ZoneInfo('America/Sao_Paulo')
FOLLOW_UP = {
    'full': 'Após conferir a reposição, acompanhar novas leituras de Full, prazo e pedidos pagos. Uma leitura com estoque não comprova recuperação.',
    'preco': 'Conferir a oferta final e acompanhar pedidos pagos por visita e valor vendido por pedido nos próximos 7 dias encerrados com cobertura completa.',
    'eficiencia': 'Comparar pedidos pagos por visita nos próximos 7 dias encerrados, mantendo visitas e vendas com cobertura completa. Registrar também mudanças de preço, frete e prazo.',
    'trafego': 'Comparar visitas e pedidos pagos nos próximos 7 dias encerrados com cobertura completa; verificar se mais visitas também geram mais pedidos.',
    'ads_loja': 'Confirmar primeiro o vínculo com a campanha. Depois acompanhar investimento, vendas Ads e vendas totais, sem atribuir os números da loja a este anúncio.',
}


def build(evidence, sales, offers, stock, end, days=7):
    """Return a suggested checking order and explicit limitations from existing data."""
    e = evidence
    actions = [dict(action) for action in e['actions']]
    start = end - timedelta(days=2*days-1)
    current_start = end - timedelta(days=days-1)
    rows = []
    latest_by_day = {}
    for row in offers or []:
        stamp = row.get('observed_at')
        if type(stamp) is not int or stamp <= 0:
            continue
        observed = datetime.fromtimestamp(stamp, BR).date()
        if start <= observed <= end:
            rows.append(row)
            if observed not in latest_by_day or stamp > latest_by_day[observed]['observed_at']:
                latest_by_day[observed] = row
    rows.sort(key=lambda row: row['observed_at'])
    latest = rows[-1] if rows else None
    events = [event for event in price_events(rows)
              if datetime.fromtimestamp(event['at'], BR).date() >= current_start]
    # A later failed reading or reversal blocks suggesting that this increase persists.
    if events and latest and latest.get('confirmed') and money(latest.get('price')) is not None:
        event = events[-1]
        if event['delta'] >= 5 and money(latest['price']) == event['after']:
            actions.append(dict(code='preco',title='Revisar aumento de preço observado',
                evidence='Preço próprio: R$ %.2f → R$ %.2f (%+.1f%%), detectado em %s.' % (
                    event['before'],event['after'],event['delta'],datetime.fromtimestamp(event['at'],BR).strftime('%d/%m %H:%M')),
                action='Conferir se a oferta final e a promoção continuam válidas; comparar frete, prazo e concorrentes vinculados antes de decidir qualquer ajuste de preço.',
                scope='Leituras consecutivas com intervalo de até 6 horas; aumento mínimo de 5% para triagem. Não comprova perda de conversão nem recomenda desconto automático.'))
    known = [value for value in stock[-days:] if value is not None]
    full_recovered = bool(known and known[-1] == 1)
    order = {'full': 70 if full_recovered else 10, 'preco': 20,
             'eficiencia': 30, 'trafego': 40, 'ads_loja': 90}
    for action in actions:
        action['follow_up'] = FOLLOW_UP.get(action['code'], 'Conferir a fonte e acompanhar o indicador após a ação.')
        action['context'] = action['code'] == 'ads_loja'
        if action['code'] == 'full' and full_recovered:
            action['title'] = 'Revisar o período de Full zerado observado'
            action['action'] = 'A leitura mais recente do recorte já mostra Full com estoque. Conferir a reposição e o prazo; investigar se os pedidos se recuperaram depois das leituras de estoque zerado.'
    actions.sort(key=lambda action: order.get(action['code'], 80))
    gaps = []
    if not e['sales_verified']:
        gaps.append('Vendas: concluir a verificação dos pedidos e a cobertura dos dois períodos antes de confirmar uma queda de faturamento.')
    traffic = e['traffic']
    if not traffic['complete']:
        gaps.append('Visitas: %s/%s dias anteriores e %s/%s atuais válidos. Sem comparação de tráfego ou eficiência até completar a cobertura; lacunas não são zero.' % (
            traffic['previous']['covered'], days, traffic['current']['covered'], days))
    if e['full']['current_known'] < days:
        gaps.append('Full: %s/%s dias atuais com leitura válida. Os dias restantes não confirmam disponibilidade nem ruptura.' % (e['full']['current_known'], days))
    price_days = sum(bool(row.get('confirmed')) and money(row.get('price')) is not None
                     for row in latest_by_day.values())
    if price_days < 2*days:
        gaps.append('Preço próprio: %s/%s dias com última leitura confirmada. O histórico começa nas novas coletas e não reconstrói promoções anteriores.' % (price_days, 2*days))
    if not e['ads']['complete']:
        gaps.append('Ads: cobertura incompleta da loja. Antes de usar esse contexto, conferir a sincronização e o vínculo entre anúncio e campanha.')
    loss = sales['previous_value']-sales['value'] if sales and e['declining'] else None
    return dict(actions=actions, gaps=gaps, loss=loss,
                status='queda' if e['declining'] else 'sem_queda' if e['sales_verified'] else 'incompleto')
