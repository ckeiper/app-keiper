import sys
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from test_price_stability import readings,END,NOW
from price_stability import render
for mode in ('ready','empty','gaps','changes','limited'):
    rows=readings()
    if mode=='empty':rows=[]
    if mode=='gaps':rows[5]['confirmed']=False
    if mode=='changes':
        for i,row in enumerate(rows):row['price']+=i
    if mode=='limited':rows*=500
    (dest/('price-stability-'+mode+'.html')).write_text(page('Diagnóstico',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(rows,END,now=NOW,cid=1,item_id='MLB1')))
