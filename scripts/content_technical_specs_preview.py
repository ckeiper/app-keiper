from catalog_preview import page,dest
from listing_content_snapshot import inspect,render
from test_listing_content_snapshot import item,requester,NOW
from test_content_technical_specs import specs,field,rules
for mode in ['read','partial','unknown','empty','managed','variations']:
    data=item();data.update(category_id='MLB200',attributes=[dict(id='BRAND',value_name='Marca teste')],variations=[],tags=['incomplete_technical_specs'])
    if mode=='partial':data['attributes']=None
    if mode=='variations':data.update(attributes=[],variations=[dict(id=1,attributes=[dict(id='BRAND',value_name='Marca')],attribute_combinations=[]),dict(id=2,attributes=[],attribute_combinations=[])])
    payload=specs(field(),field('MODEL'),field('GTIN'))
    if mode=='empty':payload=specs()
    if mode=='unknown':payload={}
    if mode=='managed':payload=specs(field('MODEL',tags=['required','read_only']))
    result=inspect('synthetic',123,'MLB123',requester([dict(id=123),data,{},rules(),payload]),NOW,include_specs=True)
    (dest/('content-technical-'+mode+'.html')).write_text(page('Ficha técnica',7,'Loja teste','anuncios',render(7,'MLB123','Produto teste','csrf',result)))
