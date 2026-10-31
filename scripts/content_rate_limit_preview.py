"""Synthetic per-request rate-limit boundaries, without network or production data."""
from catalog_preview import page,dest
from listing_content_snapshot import inspect,render
from test_content_rate_limit import requester,conditional,response,responses,NOW
from unittest.mock import Mock
for mode in ('account','item','description','category','conditional','sheet','normal'):
    get=requester(dict(account=0,item=1,description=2,category=3,sheet=4).get(mode))
    post=conditional(429 if mode=='conditional' else 200)
    if mode=='conditional':get=Mock(side_effect=[response(value) for value in responses()[:4]])
    result=inspect('synthetic',123,'MLB123',get,NOW,post,True)
    (dest/('content-rate-'+mode+'.html')).write_text(page('Conteúdo atual',7,'Loja fictícia','anuncios',render(7,'MLB123','Produto de demonstração','csrf',result)),encoding='utf-8')
