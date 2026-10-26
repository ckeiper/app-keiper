"""Synthetic, isolated snapshots. Never reads production or marketplace data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_content_snapshot import inspect,render
from test_listing_content_snapshot import item,requester,NOW

for mode in ('blank','read','empty','partial','unknown'):
    value=item(); description=dict(plain_text='Produto fictício.\nMedidas e conteúdo da embalagem para conferência manual.')
    if mode=='empty':value.update(pictures=[],attributes=[],title='');description=dict(plain_text='')
    if mode=='partial':value.update(pictures=None,attributes=None);description={}
    result=inspect('synthetic-token',123,'MLB123',requester([dict(id=123),value,description]),NOW)
    if mode=='blank':result=None
    if mode=='unknown':result=dict(state='unknown',checked_at=NOW,message='Leitura temporariamente indisponível.')
    (dest/('content-snapshot-'+mode+'.html')).write_text(page('Conteúdo atual',1,'Loja fictícia','anuncios',
        '<p>Dados fictícios de teste.</p>'+render(1,'MLB123','Produto fictício','csrf',result)),encoding='utf-8')
