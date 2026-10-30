"""Disposable synthetic review states through the real store shell."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_buyer_reviews import inspect,render
from test_listing_buyer_reviews import requester,item,payload,review,NOW
for mode in ('initial','ready','catalog','empty','unknown','incomplete','page2'):
    p=payload(reviews=[review(id=i+1,content='Opinião fictícia para verificar leitura e apresentação. '+('Texto longo. '*60 if i==0 else 'Material conforme descrição.')) for i in range(5)])
    product=item()
    if mode=='catalog':
        product=item(catalog_product_id='MLB456',catalog_listing=True)
        for row in p['reviews']:row['reviewable_object']=dict(type='product',id='MLB456')
    if mode=='empty':p.update(reviews=[],paging=dict(total=0,total_pageable=0,offset=0,limit=5),rating_average=0,rating_levels=dict(one_star=0,two_star=0,three_star=0,four_star=0,five_star=0))
    if mode=='incomplete':p.update(rating_average=None,rating_levels=None,paging=dict(offset=0,limit=5));p['reviews'][0]['status']='blocked'
    offset=5 if mode=='page2' else 0
    if offset:p['paging']['offset']=offset
    result=inspect('test-only',7,'MLB123',requester([dict(id=7),product,p]),offset,NOW)
    if mode=='unknown':result=dict(state='unknown',checked_at=NOW,message='Limite de consultas atingido. Aguarde antes de tentar novamente.')
    if mode=='initial':result=None
    (dest/('buyer-reviews-'+mode+'.html')).write_text(page('Avaliações do produto',1,'Loja fictícia','anuncios',render(1,'MLB123','Produto de demonstração','csrf-test',result),refresh=False),encoding='utf-8')
