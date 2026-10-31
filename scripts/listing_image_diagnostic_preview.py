from catalog_preview import page,dest
from test_listing_image_diagnostic import item,payload,requester,poster,read_result,NOW,ID
from listing_image_diagnostic import render
from unittest.mock import Mock
for mode in ('initial','findings','empty','catalog','unknown','rate-limit','wrong-role'):
    p=payload('empty' if mode=='empty' else 'diagnostic')
    if mode=='wrong-role':p['diagnostics'][0]['picture_type']='other'
    result=read_result(get=requester([dict(id=7),item(catalog_listing=mode=='catalog')]),post=poster(p))
    if mode=='unknown':result=dict(state='unknown',checked_at=NOW,message='Diagnóstico indisponível. Nenhuma aprovação ou ausência foi presumida.')
    if mode=='rate-limit':result=read_result(post=Mock(return_value=Mock(status_code=429)))
    if mode=='initial':result=None
    (dest/('image-diagnostic-'+mode+'.html')).write_text(page('Diagnóstico da imagem principal',1,'Loja fictícia','anuncios',render(1,'MLB123','Produto de demonstração','csrf-test',result),refresh=False),encoding='utf-8')
