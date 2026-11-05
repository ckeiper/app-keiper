from catalog_preview import page,dest
from test_listing_image_diagnostic import item,payload,requester,poster,read_result,NOW,ID
from listing_image_diagnostic import render
from unittest.mock import Mock
for mode in ('initial','findings','empty','catalog','unknown','rate-limit','wrong-role','selection','secondary','variation'):
    p=payload('empty' if mode=='empty' else 'diagnostic')
    if mode=='wrong-role':p['diagnostics'][0]['picture_type']='other'
    result=read_result(get=requester([dict(id=7),item(catalog_listing=mode=='catalog')]),post=poster(p))
    if mode=='unknown':result=dict(state='unknown',checked_at=NOW,message='Diagnóstico indisponível. Nenhuma aprovação ou ausência foi presumida.')
    if mode=='rate-limit':result=read_result(post=Mock(return_value=Mock(status_code=429)))
    if mode=='initial':result=None
    if mode=='selection':
        result=dict(state='selection',checked_at=NOW,total=3,choices=[dict(id='P'+str(i),role=role,position=i+1) for i,role in enumerate(['thumbnail','other','variation_thumbnail'])])
    if mode in ('secondary','variation'):
        result=read_result();result['picture_type']='other' if mode=='secondary' else 'variation_thumbnail'
    (dest/('image-diagnostic-'+mode+'.html')).write_text(page('Diagnóstico da imagem principal',1,'Loja fictícia','anuncios',render(1,'MLB123','Produto de demonstração','csrf-test',result),refresh=False),encoding='utf-8')
