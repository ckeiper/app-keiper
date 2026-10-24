"""Source-gated historical review plan; never a pricing or savings forecast."""
from decimal import Decimal
from html import escape
from listing_profitability import COMPONENTS
from profitability_store import result_for
from freight_comparison import format_brl

ACTIONS = {
 'products': 'Conferir custo e quantidade dos produtos vendidos no documento do período.',
 'marketplace_fees': 'Conferir tarifas efetivas e eventuais ajustes no relatório do marketplace.',
 'seller_shipping': 'Conferir fretes efetivamente pagos, pacotes e ajustes, sem ratear outros anúncios.',
 'taxes': 'Conferir o imposto documentado com o responsável fiscal; não aplicar uma alíquota presumida.',
 'advertising': 'Conferir gasto exclusivo do anúncio e datas; comparar os indicadores de Ads antes de alterar a campanha.',
 'adjustments': 'Conferir devoluções e descontos adicionais e evitar valores já descontados no preço dos itens.',
}


def review_plan(summary, record):
    result = result_for(summary, record)
    if not result['available']:
        return dict(available=False, reason=result['reason'], rows=[], gap=None)
    revenue = result['revenue']
    rows = [dict(key=k, label=COMPONENTS[k], value=v,
                 share=v*100/revenue if revenue else None, action=ACTIONS[k])
            for k,v in result['costs'].items() if v > 0]
    rows.sort(key=lambda row: (-row['value'], row['key']))
    return dict(available=True, gap=max(-result['contribution'], Decimal(0)),
                contribution=result['contribution'], rows=rows[:3], record_id=record['id'])


def render_recovery(summary, record):
    plan=review_plan(summary,record)
    esc=lambda v:escape(str(v),quote=True)
    out='<section class="pf-card" id="pf-recuperacao" aria-label="Plano de revisão da margem"><h3>Plano de revisão da margem</h3>'
    if not plan['available']:
        return out+'<p class="pf-alert">'+esc(plan['reason'])+'</p><a href="#pf-fontes">Conferir custos e fontes do período ↗</a></section>'
    if plan['gap'] > 0:
        out+='<p>Déficit de contribuição documentada no período: <strong>'+format_brl(plan['gap'])+'</strong>. É a diferença aritmética entre os custos registrados e o valor bruto vendido, sem despesas fixas. Não é economia disponível nem recuperação garantida.</p>'
    else:
        out+='<p>Os custos documentados não superaram o valor bruto dos itens neste período. Isso não comprova lucro líquido ou saúde financeira da loja.</p>'
    out+='<p>Conferir primeiro os maiores valores registrados, sem atribuir a eles a causa de uma queda. Registro #'+esc(plan['record_id'])+'. Fontes declaradas pelo administrador, sem auditoria automática.</p><div class="pf-recovery-list">'
    for row in plan['rows']:
        share='Participação indisponível: valor bruto zero.' if row['share'] is None else format(row['share'],'.2f').replace('.',',')+'% do valor bruto dos itens.'
        out+='<article class="pf-metric"><h4>'+esc(row['label'])+'</h4><strong>'+format_brl(row['value'])+'</strong><p>'+esc(share)+'</p><p>'+esc(row['action'])+'</p></article>'
    out+='</div>'
    if not plan['rows']:
        out+='<p>Todos os componentes foram documentados com valor zero. Confira as fontes antes de usar este resultado para decidir.</p>'
    return out+'<p>Após conferir, registre uma nova versão somente se houver documentação corrigida. Para avaliar uma ação futura, acompanhe outro período encerrado; não há estimativa de ganho ou alteração automática de preços, promoções ou Ads.</p><a href="#pf-fontes">Revisar fontes e registrar nova versão ↗</a></section>'
