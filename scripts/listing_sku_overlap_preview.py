import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_sku_overlap import render
from test_listing_sku_overlap import fixture,NOW
for mode in ('empty','groups','limited','stale'):
    d=fixture()
    if mode=='empty':d.update(group_total=0,member_total=0,groups=[],members=[])
    if mode=='limited':d['groups'][0]['n']=30;d.update(page=2,pages=3,group_total=21)
    if mode=='stale':d['members'][0]['atualizado_em']=1
    (dest/('listing-sku-overlap-'+mode+'.html')).write_text(page('SKUs repetidos',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(1,d,NOW)))
