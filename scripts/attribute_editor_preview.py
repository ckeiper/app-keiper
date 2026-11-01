"""Isolated fixtures; never reads a connected marketplace account."""
from catalog_preview import page,dest
from attribute_edit_view import render
from test_attribute_completion import facts,analyze,definition,listing
from copy import deepcopy
base=analyze(facts(definitions=[definition(tags=dict(hidden=True))]))
for mode in ('initial','ready','empty','blocked','uncertain','confirmed','xss','prose','ambiguous','na','manual','manual-xss','manual-empty','variation','variation-confirmed','variation-unknown','variation-xss','bulk','bulk-error'):
    plan=None;manual_form=None
    if mode!='initial':
        plan=dict(id='11111111-1111-4111-8111-111111111111',data=deepcopy(base),state=mode if mode in ('uncertain','confirmed') else 'ready',selected=[],result={})
        if mode in ('manual','manual-xss'):
            value='<img src=x onerror=window.injected=1>' if mode=='manual-xss' else 'Plástico'
            plan['data']=analyze(facts(description='',definitions=[definition(tags=dict(hidden=True))]),[dict(id='MATERIAL',value=value,note='Ficha do fabricante')],42)
        if mode=='manual-empty':plan['data']=analyze(facts(description=''))
        if mode.startswith('variation'):
            from test_attribute_variations import variant,rule,manual
            variants=[variant(),variant(102)]
            if mode=='variation-unknown':variants[1]['attributes']=None
            if mode=='variation-xss':variants[0]['attribute_combinations'][0]['value_name']='<img src=x onerror=window.injected=1>'
            plan['data']=analyze(facts(item=listing(variations=variants),definitions=[rule()],description=''),[manual()] if mode!='variation-unknown' else None,42)
            if mode=='variation-confirmed':
                plan['state']='confirmed';plan['result']=dict(message='Atualização confirmada por nova leitura.',preserved=True,fields=[dict(id='v:101:GTIN',name='Código de barras · Variação 101 · Azul',confirmed=True)])
        if mode in ('bulk','bulk-error'):
            from test_attribute_variations import variant,rule
            plan['data']=analyze(facts(item=listing(variations=[variant(),variant(102)]),definitions=[definition(),rule()],description=''))
            if mode=='bulk-error':
                from werkzeug.datastructures import MultiDict
                manual_form=MultiDict([('manual_field','MATERIAL'),('manual_value','Aço'),('manual_note','Fonte comum'),('manual_field','v:101:GTIN'),('manual_value','789000001'),('manual_note','Fonte azul'),('manual_field','v:102:GTIN'),('manual_value','<img src=x onerror=window.injected=1>'),('manual_note','<script>window.injected=1</script>')])
        if mode=='empty':plan['data']['proposals']=[];plan['data']['proposal_total']=0
        if mode=='blocked':plan['data']['blocked']='User Product compartilhado: envio bloqueado para não alterar outros anúncios.'
        if mode=='confirmed':plan['result']=dict(message='Atualização confirmada por nova leitura.',fields=[dict(id='MATERIAL',name='Material',confirmed=True)])
        if mode=='prose':plan['data']=analyze(facts(definitions=[definition(tags=dict(hidden=True)),definition('WIDTH',name='Largura',value_type='number_unit',allowed_units=[dict(id='cm')])],description='O material é de aço. A largura mede 12,5 cm.'))
        if mode=='ambiguous':plan['data']=analyze(facts(definitions=[definition(tags=dict(hidden=True))],description='Material: Aço\nO material pode ser plástico.'))
        if mode=='na':plan['data']=analyze(facts(item=listing(attributes=[dict(id='MATERIAL',value_id='-1',value_name=None)]),definitions=[definition(tags=dict(hidden=True))],description='O material é aço.'))
        if mode=='xss':plan['data']['proposals'][0].update(name='<script>window.injected=1</script>',value='<img src=x onerror=window.injected=1>',evidence=[dict(source='Descrição',text='</blockquote><script>window.injected=1</script>')])
    body=render(7,'MLB123','Produto de teste','csrf','k'*24,plan,manual_form=manual_form)
    (dest/('attribute-editor-'+mode+'.html')).write_text(page('Completar ficha técnica',7,'Loja de teste','anuncios',body,refresh=False))
