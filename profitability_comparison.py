"""Arithmetic financial comparisons, never a causal diagnosis or promised recovery."""
from decimal import Decimal
from datetime import date, timedelta
from listing_profitability import COMPONENTS
from profitability_store import result_for

ACTIONS = {
    'products': 'Conferir o custo das unidades vendidas e o mix de variações em cada período.',
    'marketplace_fees': 'Conferir tarifas fixas, modalidade do anúncio e os documentos de cobrança.',
    'seller_shipping': 'Conferir fretes do vendedor, modalidade logística, peso e ajustes de cobrança.',
    'taxes': 'Conferir a base tributária e os documentos fiscais dos dois períodos.',
    'advertising': 'Conferir o gasto exclusivo do anúncio, cobertura e janela de atribuição antes de decidir.',
    'adjustments': 'Conferir descontos, devoluções e ajustes adicionais, evitando dupla contagem.',
}


def compare(current_sales, previous_sales, current_record, previous_record):
    current = result_for(current_sales,current_record)
    previous = result_for(previous_sales,previous_record)
    result = dict(available=False, current=current, previous=previous,
                  rows=[], findings=[], contribution_delta=None, margin_delta_pp=None)
    # A negative contribution is a verified arithmetic result, not a forecast.
    if current['available'] and Decimal(format(current['contribution'],'.2f')) < 0:
        result['findings'].append(dict(code='negative_contribution',
            title='Contribuição documentada negativa',
            evidence=current['contribution'],
            action='Conferir os componentes e as fontes antes de alterar preço, promoção ou publicidade.'))
    try:
        start,end = (date.fromisoformat(current_sales[k]) for k in ('start','end'))
        old_start,old_end = (date.fromisoformat(previous_sales[k]) for k in ('start','end'))
        windows_valid = (end >= start and old_end >= old_start
            and end-start == old_end-old_start and old_end+timedelta(days=1)==start)
    except (ValueError,TypeError,KeyError):
        windows_valid = False
    if not windows_valid:
        return dict(result,reason='Períodos não comparáveis: selecione janelas consecutivas de mesma duração.')
    if not current['available'] or not previous['available']:
        return dict(result, reason='A comparação exige vendas verificadas e custos documentados nos dois períodos.')
    revenue_delta = current['revenue']-previous['revenue']
    rows = [dict(key='revenue',label='Valor bruto dos itens',current=current['revenue'],
                 previous=previous['revenue'],delta=revenue_delta,impact=revenue_delta,
                 current_share=None,previous_share=None,share_delta_pp=None)]
    for key,label in COMPONENTS.items():
        now,before = current['costs'][key],previous['costs'][key]
        share = now*100/current['revenue'] if current['revenue'] else None
        old_share = before*100/previous['revenue'] if previous['revenue'] else None
        rows.append(dict(key=key,label=label,current=now,previous=before,delta=now-before,
            impact=before-now,current_share=share,previous_share=old_share,
            share_delta_pp=share-old_share if share is not None and old_share is not None else None))
    delta = current['contribution']-previous['contribution']
    if sum((r['impact'] for r in rows),Decimal(0)) != delta:
        # Fail closed on an inconsistent financial identity.
        return dict(result,reason='A composição financeira não pôde ser reconciliada.')
    margin_delta = (current['margin_pct']-previous['margin_pct']
        if current['margin_pct'] is not None and previous['margin_pct'] is not None else None)
    if margin_delta is not None and Decimal(format(margin_delta,'.2f')) < 0:
        result['findings'].append(dict(code='margin_decline',title='Margem documentada menor',
            evidence=margin_delta,
            action='Revisar os componentes cuja participação no valor bruto aumentou. A comparação não comprova causa.'))
    increases = sorted([r for r in rows[1:] if r['share_delta_pp'] is not None
                        and Decimal(format(r['share_delta_pp'],'.2f'))>0],
                       key=lambda r:(-r['share_delta_pp'],r['key']))
    for row in increases[:2]:
        result['findings'].append(dict(code=row['key'],title=row['label']+' com maior participação',
            evidence=row['share_delta_pp'],action=ACTIONS[row['key']]))
    return dict(result,available=True,rows=rows,contribution_delta=delta,
                margin_delta_pp=margin_delta,reason=None,
                current_units=current_sales.get('units'),previous_units=previous_sales.get('units'))
