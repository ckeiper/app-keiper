"""Conservative second-week follow-up after recorded listing interventions.

Only two complete consecutive post-action windows can support a sustained trend.
Comparisons are observational, never causal attribution to an intervention.
"""
from datetime import timedelta
from decimal import Decimal
from html import escape

from investigation_evidence import window, date_key
from listing_sales import listing_sales_summary
from sales_drivers import money


def assess(item_id, action_day, today, orders, items, covered, visits, first, pending=False):
    second_start = action_day + timedelta(days=8)
    second_end = action_day + timedelta(days=14)
    if today <= second_end:
        return dict(state='aguardando', closed_days=max(0, min(7, (today-second_start).days)),
                    reason='A segunda semana após a alteração ainda não terminou.')
    if pending or first['delta'] is None:
        return dict(state='indisponivel',reason='Faltam pedidos verificados nos dois períodos iniciais.')
    before = first['periods'][0]['sales']['gross_items']
    first_week = first['periods'][1]['sales']['gross_items']
    if before is None or first_week is None:
        return dict(state='indisponivel',reason='A comparação inicial não possui cobertura completa.')
    sales = listing_sales_summary(orders,items,covered,item_id,end=second_end,days=7)
    if sales['gross_items'] is None:
        return dict(state='indisponivel',reason='A segunda semana não possui cobertura completa de vendas.')
    dates=[(second_start+timedelta(days=i)).isoformat() for i in range(7)]
    valid_visits=[r for r in visits if date_key(r.get('dia')) and date_key(r.get('dia'))<today.isoformat()]
    traffic=window(valid_visits,dates,['visitas'],'dia')
    value=sales['gross_items']
    if first_week > before and value < before:
        state='reversao'
    elif first_week > before and value < first_week:
        state='oscilacao'
    elif value >= before and first_week >= before and (first_week > before or value > before):
        state='sustentada'
    else:
        state='sem_recuperacao'
    return dict(state=state,before=before,first=first_week,second=value,
                visits=traffic['totals']['visitas'] if traffic['complete'] else None,
                visits_covered=traffic['covered'],
                orders=sales['orders'],reason=None)


def render(result):
    state=result['state']
    out='<section class="iv-card" aria-label="Acompanhamento após alteração"><h3>A recuperação se manteve?</h3>'
    if state=='aguardando':
        return out+'<p class="iv-status warn">Aguardando a segunda semana encerrada após a alteração: '+str(result['closed_days'])+'/7 dias completos.</p></section>'
    if state=='indisponivel':
        return out+'<p class="iv-status warn">Acompanhamento indisponível: '+escape(result['reason'])+'</p></section>'
    messages={
        'sustentada':'Melhora observada nas duas semanas completas após o registro.',
        'reversao':'Houve melhora na primeira semana, mas a segunda ficou abaixo da referência anterior.',
        'oscilacao':'A segunda semana recuou em relação à primeira. A melhora ainda não é estável.',
        'sem_recuperacao':'Não há evidência de recuperação sustentada nas duas semanas.',
    }
    out+='<p class="iv-status">'+escape(messages[state])+'</p>'
    out+='<div class="iv-scroll"><table class="iv-table"><thead><tr><th>7 dias antes</th><th>1ª semana depois</th><th>2ª semana depois</th></tr></thead><tbody><tr>'
    out+=''.join('<td>'+money(result[k])+'</td>' for k in ('before','first','second'))
    out+='</tr></tbody></table></div>'
    if result['visits'] is None:
        out+='<p class="iv-meta">Visitas da segunda semana: '+str(result['visits_covered'])+'/7 dias válidos. Não interpretar lacunas como zero.</p>'
    else:
        out+='<p class="iv-meta">Segunda semana: '+str(int(result['visits']))+' visitas observadas e '+str(result['orders'])+' pedidos pagos verificados.</p>'
    return out+'<p class="iv-meta">Recuperação significa apenas que o valor bruto dos itens atingiu ou superou a referência anterior nas duas semanas completas; não há garantia de tendência futura. A comparação exclui o dia do registro e não comprova que a alteração gerou resultado. Mudanças simultâneas, demanda e concorrência podem influenciar as vendas.</p></section>'
