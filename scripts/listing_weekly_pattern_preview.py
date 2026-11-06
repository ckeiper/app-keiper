"""Synthetic weekday distributions; never writes to the production database."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_weekly_pattern import analyze,render
from test_listing_weekly_pattern import fixture,TODAY

for mode in ('ready','zero','partial','pending','invalid','spike','change','zero-base'):
    context=fixture()
    if mode=='zero':context.update(orders=[],items=[])
    if mode=='partial':context['coverage']=context['coverage'][10:]
    if mode=='pending':context['pending']=True
    if mode=='invalid':context['items'].pop()
    if mode=='spike':
        context['items'][0]['quantidade']=500
        context['orders'][0].update(unidades=500,total=5000)
    if mode in ('change','zero-base'):
        for i,order in enumerate(context['orders']):
            if mode=='zero-base' and i<28:order['status']='cancelled'
            elif mode=='change' and i>=28:
                if i%7==6:order['status']='cancelled'
                else:
                    qty=2*(i%7+1);order.update(unidades=qty,total=qty*10);context['items'][i]['quantidade']=qty
    data=analyze(context,7,'MLB1',TODAY)
    (dest/('listing-weekly-pattern-'+mode+'.html')).write_text(page('Padrão semanal de vendas',7,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(7,'MLB1',dict(titulo='Produto de demonstração'),data)),encoding='utf-8')
