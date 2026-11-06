"""Synthetic retrospective mean checks; no production data or requests."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_weekly_pattern import analyze
from listing_projection_history import render
from test_listing_weekly_pattern import fixture,TODAY
from test_listing_projection_history import daily_context

for mode in ('ready','shift','zero','zero-real','partial','pending','invalid','spike'):
    context=daily_context() if mode=='shift' else daily_context(0,0) if mode=='zero' else daily_context(1,0) if mode=='zero-real' else fixture()
    if mode=='partial':context['coverage']=context['coverage'][1:]
    if mode=='pending':context['pending']=True
    if mode=='invalid':context['items'].pop()
    if mode=='spike':
        context['orders'][0].update(unidades=5000,total=50000);context['items'][0]['quantidade']=5000
    data=analyze(context,7,'MLB1',TODAY)
    (dest/('listing-projection-history-'+mode+'.html')).write_text(page('Conferência histórica da média',7,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(7,'MLB1',dict(titulo='Produto de demonstração'),data)),encoding='utf-8')
