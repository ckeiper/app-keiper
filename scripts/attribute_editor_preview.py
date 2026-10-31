"""Isolated fixtures; never reads a connected marketplace account."""
from catalog_preview import page,dest
from attribute_edit_view import render
from test_attribute_completion import facts,analyze,definition,listing
from copy import deepcopy
base=analyze(facts(definitions=[definition(tags=dict(hidden=True))]))
for mode in ('initial','ready','empty','blocked','uncertain','confirmed','xss','prose','ambiguous','na'):
    plan=None
    if mode!='initial':
        plan=dict(id='11111111-1111-4111-8111-111111111111',data=deepcopy(base),state=mode if mode in ('uncertain','confirmed') else 'ready',selected=[],result={})
        if mode=='empty':plan['data']['proposals']=[];plan['data']['proposal_total']=0
        if mode=='blocked':plan['data']['blocked']='User Product compartilhado: envio bloqueado para não alterar outros anúncios.'
        if mode=='confirmed':plan['result']=dict(message='Atualização confirmada por nova leitura.',fields=[dict(id='MATERIAL',name='Material',confirmed=True)])
        if mode=='prose':plan['data']=analyze(facts(definitions=[definition(tags=dict(hidden=True)),definition('WIDTH',name='Largura',value_type='number_unit',allowed_units=[dict(id='cm')])],description='O material é de aço. A largura mede 12,5 cm.'))
        if mode=='ambiguous':plan['data']=analyze(facts(definitions=[definition(tags=dict(hidden=True))],description='Material: Aço\nO material pode ser plástico.'))
        if mode=='na':plan['data']=analyze(facts(item=listing(attributes=[dict(id='MATERIAL',value_id='-1',value_name=None)]),definitions=[definition(tags=dict(hidden=True))],description='O material é aço.'))
        if mode=='xss':plan['data']['proposals'][0].update(name='<script>window.injected=1</script>',value='<img src=x onerror=window.injected=1>',evidence=[dict(source='Descrição',text='</blockquote><script>window.injected=1</script>')])
    body=render(7,'MLB123','Produto de teste','csrf','k'*24,plan)
    (dest/('attribute-editor-'+mode+'.html')).write_text(page('Completar ficha técnica',7,'Loja de teste','anuncios',body,refresh=False))
