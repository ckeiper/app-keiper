"""Synthetic 30-day plans, no writes."""
import sys
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from test_listing_onboarding import fixture,DAY
from listing_onboarding_view import render
for mode in ('empty','active','future','late','done'):
    data=fixture();today=DAY
    if mode=='empty':data=dict(plan=None,steps=[])
    if mode=='future':today-=timedelta(days=1)
    if mode=='late':today+=timedelta(days=40);data['steps'][1]['status']='cancelled'
    if mode=='done':
        for r in data['steps']:r['status']='done'
    (dest/('listing-onboarding-'+mode+'.html')).write_text(page('Primeiros 30 dias',1,'Loja fictícia','anuncios','<p>Dados fictícios para teste.</p>'+render(1,'MLB123',dict(titulo='Produto de demonstração'),data,today,'token')))
