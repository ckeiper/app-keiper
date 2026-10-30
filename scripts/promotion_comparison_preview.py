"""Synthetic previews: actual store shell, no external API or production access."""
from catalog_preview import page,dest
from test_promotion_observations import reading,TODAY
from promotion_comparison import render
from promotion_observations import periods
from decimal import Decimal
s=reading();selection=periods(s['promotions'][0],TODAY)
paired=[dict(start=selection['previous_start'],end=selection['previous_end'],sales=dict(orders=5,units=5,gross_items=Decimal(500),ticket=100),visits=100,visits_days=7),dict(start=selection['start'],end=selection['end'],sales=dict(orders=8,units=8,gross_items=Decimal(640),ticket=80),visits=140,visits_days=7)]
result=dict(selection,periods=paired,finance=dict(available=False,reason='A comparação exige custos documentados nas duas janelas.'))
for mode in ['ready','empty','unknown','naive','removed']:
    selected=s if mode!='empty' else None
    if mode=='unknown':selected=dict(s,available=False,reason='consulta_indisponivel')
    if mode in ['naive','removed']:result_mode=dict(available=False,reason='Datas sem fuso explícito.' if mode=='naive' else 'Item removido não comprova participação integral.')
    else:result_mode=result
    html=render(7,'MLB123','Produto <Teste>',[s] if selected else [],1 if selected else 0,1,1,selected,0,result_mode if selected else None,7,TODAY)
    (dest/('promotion-comparison-'+mode+'.html')).write_text(page('Resultados de promoções',7,'Loja de teste','anuncios',html),encoding='utf-8')
print('Synthetic promotion calendar comparisons rendered.')
