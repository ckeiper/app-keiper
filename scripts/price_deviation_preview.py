import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from test_price_deviation import fixture,END,NOW
from price_deviation import render
for mode in ('alert','normal','stale','sparse','missing'):
    rows=fixture(100 if mode=='normal' else 130)
    if mode=='stale':rows[-1]['observed_at']=NOW-21601
    if mode=='sparse':rows=rows[:4]+rows[-1:]
    if mode=='missing':rows[-1]['confirmed']=False
    (dest/('price-deviation-'+mode+'.html')).write_text(page('Diagnóstico',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(rows,END,NOW)))
