from catalog_preview import page,dest
from listing_content_snapshot import inspect,render
from test_listing_content_snapshot import item,requester,NOW
from test_content_number_attributes import rule
for mode in ('matched','review','unknown','variation','managed','category-failure','compound'):
    listing=item();listing.update(category_id='MLB200',attributes=[dict(id='COUNT',value_name='dez' if mode in ('review','managed') else '-1.5')],variations=[])
    if mode=='unknown':listing['attributes'][0].update(value_name=None,value_id='5')
    if mode=='compound':listing['attributes'][0]['values']=[dict(name='2'),dict(name='3')]
    if mode=='variation':listing.update(attributes=[],variations=[dict(id=12,attributes=[],attribute_combinations=[dict(id='COUNT',value_name='2 unidades')])])
    rules=[rule(tags=dict(read_only=True) if mode=='managed' else {})]
    result=inspect('synthetic',123,'MLB123',requester([dict(id=123),listing,{},{} if mode=='category-failure' else rules]),NOW)
    (dest/('content-number-'+mode+'.html')).write_text(page('Conteúdo atual',7,'Loja fictícia','anuncios',render(7,'MLB123','Produto de demonstração','csrf',result)),encoding='utf-8')
