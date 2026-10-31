from catalog_preview import page,dest
from listing_content_snapshot import inspect,render
from test_listing_content_snapshot import item,requester,NOW
from test_content_list_attributes import rule
for mode in ('matched','review','unknown','variation','managed','category-failure','compound','limited'):
    listing=item();listing.update(category_id='MLB200',attributes=[dict(id='COLOR',value_id='9' if mode in ('review','managed') else '1',value_name='Texto personalizado')],variations=[])
    if mode=='unknown':listing['attributes'][0]['value_id']=None
    if mode=='compound':listing['attributes'][0]['values']=[dict(id='1'),dict(id='2')]
    if mode=='variation':listing.update(attributes=[],variations=[dict(id=12,attributes=[],attribute_combinations=[dict(id='COLOR',value_id='9')])])
    rules=[rule(tags=dict(read_only=True) if mode=='managed' else {})]
    if mode=='limited':
        listing['attributes']=[dict(id=str(i),value_id='9') for i in range(101)]
        rules=[rule(id=str(i)) for i in range(101)]
    result=inspect('synthetic',123,'MLB123',requester([dict(id=123),listing,{},{} if mode=='category-failure' else rules]),NOW)
    (dest/('content-list-'+mode+'.html')).write_text(page('Conteúdo atual',7,'Loja fictícia','anuncios',render(7,'MLB123','Produto de demonstração','csrf',result)),encoding='utf-8')
