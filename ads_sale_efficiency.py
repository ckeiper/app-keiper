"""Closed-window attributed-sales averages; no acquisition or profit inference."""
from decimal import Decimal
from html import escape
from listing_priority_evidence import nonnegative
from freight_comparison import format_brl


def metrics(window):
    if not isinstance(window,dict):
        return dict(available=False,reason='Período sem dados completos.')
    count=nonnegative(window.get('attributed_sales'))
    spend=nonnegative(window.get('spend'));revenue=nonnegative(window.get('revenue'))
    if count is None or count!=count.to_integral_value() or spend is None or revenue is None:
        return dict(available=False,reason='Vendas atribuídas oficiais ou valores do período incompletos.')
    if count==0:
        return dict(available=False,reason='Nenhuma venda atribuída registrada: médias por venda indisponíveis.')
    return dict(available=True,count=count,cost=spend/count,revenue=revenue/count)


def comparison(current,previous):
    now,before=metrics(current),metrics(previous)
    result=dict(current=now,previous=before,available=now['available'] and before['available'],rows=[])
    if result['available']:
        for key in ['cost','revenue']:
            delta=now[key]-before[key]
            result['rows'].append(dict(key=key,current=now[key],previous=before[key],delta=delta,
                percent=delta*100/before[key] if before[key]>0 else None))
    return result


def render(current,previous):
    result=comparison(current,previous)
    out='<section class="ky-sale-efficiency" aria-label="Eficiência por venda atribuída"><h4>Investimento e receita por venda atribuída</h4><p>Médias dos períodos encerrados, com a contagem oficial de vendas atribuídas da campanha.</p>'
    if not result['available']:
        for label,key in [('Atual','current'),('Anterior','previous')]:
            if not result[key]['available']:
                out+='<p>'+label+': '+escape(result[key]['reason'])+'</p>'
        out+='<p>Não há comparação válida das médias nos dois períodos. Ausência de dados não é zero.</p>'
    else:
        out+='<div class="ky-data-table"><table><caption>R$ por venda atribuída · arredondamento a centavos</caption><thead><tr><th>Indicador</th><th>Anterior</th><th>Atual</th><th>Variação</th></tr></thead><tbody>'
        for row in result['rows']:
            label='Investimento médio' if row['key']=='cost' else 'Receita atribuída média'
            pct='Sem base percentual anterior' if row['percent'] is None else format(row['percent'],'.2f').replace('.',',')+'%'
            out+='<tr><th scope="row">'+label+'</th><td>'+format_brl(row['previous'])+'</td><td>'+format_brl(row['current'])+'</td><td>'+format_brl(row['delta'])+' ('+pct+')</td></tr>'
        out+='</tbody></table></div><p>Vendas atribuídas oficiais: '+str(result['previous']['count'])+' → '+str(result['current']['count'])+'.</p>'
    return out+'<p class="ky-camp-caveat">Não é custo de aquisição de cliente novo, ticket por pedido ou lucro. Atribuição pode mudar; mix de anúncios e condições de venda alteram as médias. Antes de rever orçamento, confira anúncios atendidos, maturação da atribuição, estoque e custos documentados. A comparação não comprova causalidade nem prevê resultado.</p></section>'
