"""Synthetic, isolated snapshots. Never reads production or marketplace data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_content_snapshot import inspect,render
from test_listing_content_snapshot import item,requester,NOW
from test_listing_content_requirements import definitions,variant
from test_content_conditional_attributes import complete_item
from unittest.mock import Mock

for mode in ('blank','read','empty','partial','unknown','requirements','variants','conditional','category-failure'):
    value=item(); description=dict(plain_text='Produto fictício.\nMedidas e conteúdo da embalagem para conferência manual.')
    if mode=='empty':value.update(pictures=[],attributes=[],title='');description=dict(plain_text='')
    if mode=='partial':value.update(pictures=None,attributes=None);description={}
    payload=[dict(id=123),value,description]
    if mode == 'conditional':
        value=complete_item();payload=[dict(id=123),value,description]
    if mode in ('requirements','variants','conditional','category-failure'):
        value['category_id']='MLB200';payload.append(definitions() if mode!='category-failure' else {})
    if mode=='variants':
        value['attributes']=[]
        first=variant(1);first['attributes']=[dict(id='BRAND',value_name='Marca fictícia')]
        value['variations']=[first,variant(2)]
    post=Mock(return_value=Mock(status_code=200,json=Mock(return_value={'required_attributes':[{'id':'GTIN'}]}))) if mode=='conditional' else None
    result=inspect('synthetic-token',123,'MLB123',requester(payload),NOW,request_post=post)
    if mode=='blank':result=None
    if mode=='unknown':result=dict(state='unknown',checked_at=NOW,message='Leitura temporariamente indisponível.')
    (dest/('content-snapshot-'+mode+'.html')).write_text(page('Conteúdo atual',1,'Loja fictícia','anuncios',
        '<p>Dados fictícios de teste.</p>'+render(1,'MLB123','Produto fictício','csrf',result)),encoding='utf-8')
