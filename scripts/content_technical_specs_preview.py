from catalog_preview import page,dest
from listing_content_snapshot import inspect,render
from test_listing_content_snapshot import item,requester,NOW
from test_content_technical_specs import specs,field,rules
for mode in ['read','partial','unknown','empty','managed','variations','complementary','many','xss','structured','api']:
    data=item();data.update(category_id='MLB200',attributes=[dict(id='BRAND',value_name='Marca teste')],variations=[],tags=['incomplete_technical_specs'])
    if mode=='partial':data['attributes']=None
    if mode=='variations':data.update(attributes=[],variations=[dict(id=1,attributes=[dict(id='BRAND',value_name='Marca')],attribute_combinations=[]),dict(id=2,attributes=[],attribute_combinations=[])])
    payload=specs(field(),field('MODEL'),field('GTIN'))
    if mode=='complementary':payload=specs(field(),field('EXTRA',tags=[]),field('OTHER',tags=[]))
    if mode=='many':payload=specs(*[field('FIELD_'+str(i),tags=[] if i%2 else ['required']) for i in range(115)])
    if mode=='xss':payload=specs(field(name='</script><script>window.injected=1</script>'))
    if mode=='structured':
        payload=specs(field('EXTRA',tags=[]));data['attributes']=[dict(id='EXTRA',value_struct=dict(number=12,unit='cm'))]
    if mode=='empty':payload=specs()
    if mode=='unknown':payload={}
    if mode=='managed':payload=specs(field('MODEL',tags=['required','read_only']))
    category_rules=[r for r in rules() if any(r['id']==f['id'] for group in payload.get('groups',[]) for component in group['components'] for f in component['attributes'])]
    if mode=='api':
        payload=specs(field());category_rules=[rules()[0],dict(id='HIDDEN_NEW',name='Detalhe para novos',tags=dict(new_hidden=True)),dict(id='INTERNAL',name='Controle interno',tags=dict(hidden=True,read_only=True)),dict(id='MANDATORY',name='Obrigatório API',tags=dict(required=True))]
    result=inspect('synthetic',123,'MLB123',requester([dict(id=123),data,{},category_rules,payload]),NOW,include_specs=True)
    (dest/('content-technical-'+mode+'.html')).write_text(page('Ficha técnica',7,'Loja teste','anuncios',render(7,'MLB123','Produto teste','csrf',result)))
