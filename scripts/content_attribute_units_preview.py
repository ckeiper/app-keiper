from catalog_preview import page,dest
from listing_content_snapshot import inspect,render
from test_listing_content_snapshot import item,requester,NOW
from test_content_attribute_units import definition,value
for mode in ['matched','review','unknown','variation','managed','category-failure']:
    data=item();data.update(category_id='MLB200',attributes=[value('kg' if mode in ('review','managed') else 'cm')],variations=[])
    if mode=='unknown':data['attributes']=[value(value_struct=None)]
    if mode=='variation':data.update(attributes=[],variations=[dict(id=1,attributes=[value('kg')],attribute_combinations=[])])
    rule=definition(tags=dict(read_only=True) if mode=='managed' else {})
    result=inspect('synthetic',123,'MLB123',requester([dict(id=123),data,dict(plain_text='Produto de teste'),{} if mode=='category-failure' else [rule]]),NOW)
    (dest/('content-units-'+mode+'.html')).write_text(page('Conteúdo atual',7,'Loja teste','anuncios',render(7,'MLB123','Produto teste','csrf',result)))
