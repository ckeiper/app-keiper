"""Synthetic previews: actual store shell, no external API or production access."""
from catalog_preview import page,dest
from test_promotion_observations import reading,TODAY,promotion
from copy import deepcopy
from promotion_comparison import render
from promotion_observations import periods
from decimal import Decimal
s=reading();selection=periods(s['promotions'][0],TODAY)
paired=[dict(start=selection['previous_start'],end=selection['previous_end'],sales=dict(orders=5,units=5,gross_items=Decimal(500),ticket=100),visits=100,visits_days=7),dict(start=selection['start'],end=selection['end'],sales=dict(orders=8,units=8,gross_items=Decimal(640),ticket=80),visits=140,visits_days=7)]
result=dict(selection,periods=paired,finance=dict(available=False,reason='A comparação exige custos documentados nas duas janelas.'))
for mode in ['ready','empty','unknown','naive','removed','coincident','mixed','limited','conflict']:
    selected=deepcopy(s) if mode!='empty' else None
    if mode in ('coincident','mixed'):
        selected['promotions'] += [promotion(id='OLD',start='2026-09-20T00:00:00-03:00',end='2026-09-28T00:00:00-03:00'),promotion(id='NEW',start='2026-10-02T00:00:00-03:00',end='2026-10-06T00:00:00-03:00'),promotion(id='BOTH',start='2026-09-20T00:00:00-03:00')]
    if mode=='mixed':selected['promotions'] += [promotion(id='MISSING',start=None),promotion(id='CANDIDATE',status='candidate'),promotion(id='BANK',type='BANK'),promotion(id='VAR',variation_id='1'),deepcopy(selected['promotions'][-1]),promotion(id='DUPLICATE'),promotion(id='DUPLICATE',price='77')]
    if mode=='limited':selected['promotions'] += [promotion(id='OF'+str(i)) for i in range(2,201)]
    if mode=='conflict':selected['promotions'].append(promotion(price='77'))
    if mode=='unknown':selected=dict(s,available=False,reason='consulta_indisponivel')
    if mode in ['naive','removed']:result_mode=dict(available=False,reason='Datas sem fuso explícito.' if mode=='naive' else 'Item removido não comprova participação integral.')
    else:result_mode=result
    html=render(7,'MLB123','Produto <Teste>',[s] if selected else [],1 if selected else 0,1,1,selected,0,result_mode if selected else None,7,TODAY)
    (dest/('promotion-comparison-'+mode+'.html')).write_text(page('Resultados de promoções',7,'Loja de teste','anuncios',html),encoding='utf-8')
print('Synthetic promotion calendar comparisons rendered.')
