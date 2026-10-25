"""Synthetic financial evidence fixtures through the production store shell."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from test_profitability import summary,record,START,END
from profitability_store import result_for
from profitability_view import render

for name,entry in [('profitability-ready',record()),('profitability-missing',None),('profitability-stale',dict(record(),sales_fingerprint='b'*64))]:
    body=render(42,'MLB100','Produto de demonstração',START,END,summary(),result_for(summary(),entry),entry,[entry] if entry else [],'preview-only','x'*32)
    (dest/(name+'.html')).write_text(page('Rentabilidade por anúncio',42,'Loja de demonstração','anuncios',body),encoding='utf-8')
unverified=dict(summary(),orders=None,units=None,gross_items=None,reason='Pedidos pendentes de verificação.')
entry=record()
body=render(42,'MLB100','Produto de demonstração',START,END,unverified,result_for(unverified,entry),entry,[entry],'preview-only','x'*32)
(dest/'profitability-unverified.html').write_text(page('Rentabilidade por anúncio',42,'Loja de demonstração','anuncios',body),encoding='utf-8')
print('Synthetic profitability previews rendered.')

from test_profitability_comparison import pair_records
from profitability_comparison import compare
from profitability_units import render_unit_comparison
from profitability_comparison_view import render_comparison
from decimal import Decimal
for mode in ['ready','negative','missing','stale']:
    pair,current,previous=pair_records()
    pair['previous'].update(gross_items=Decimal('200'));previous.update(gross_items=Decimal('200'))
    current['costs']=dict(current['costs'],advertising=Decimal('100'))
    if mode=='negative':current['costs']={k:Decimal('100') for k in current['costs']}
    if mode=='missing':previous=None
    if mode=='stale':previous['sales_fingerprint']='b'*64
    result=compare(pair['current'],pair['previous'],current,previous)
    comparison_html=render_comparison(result,START,END,pair['previous_start'],pair['previous_end'],current,previous)
    comparison_html += render_unit_comparison(result)
    body=render(42,'MLB100','Produto de demonstração',START,END,pair['current'],result['current'],current,[current],'preview-only','x'*32,comparison_html=comparison_html)
    (dest/('profitability-comparison-'+mode+'.html')).write_text(page('Rentabilidade por anúncio',42,'Loja de demonstração','anuncios',body),encoding='utf-8')
print('Synthetic financial comparison previews rendered.')

from profitability_scenarios import render as render_scenario,simulate
from test_profitability_scenarios import form as scenario_form
for mode in ['blank','ready','error']:
    values=scenario_form() if mode!='blank' else {}
    if mode=='ready':values['target_margin']='40'
    scenario=simulate(values) if mode=='ready' else None
    body=render_scenario(42,'MLB100','Produto de demonstração','preview-only',values,scenario,'Informe publicidade por pedido.' if mode=='error' else '')
    (dest/('profitability-scenario-'+mode+'.html')).write_text(page('Simular descontos progressivos',42,'Loja de demonstração','anuncios',body),encoding='utf-8')

old_entry=dict(record(),id=9,sources=dict(record()['sources'],products='Documento sintético da versão anterior'))
current_entry=dict(record(),id=10)
body=render(42,'MLB100','Produto de demonstração',START,END,summary(),result_for(summary(),current_entry),current_entry,[current_entry,old_entry],'preview-only','x'*32,inspected_record=old_entry)
(dest/'profitability-inspection.html').write_text(page('Consulta de registro',42,'Loja de demonstração','anuncios',body),encoding='utf-8')
