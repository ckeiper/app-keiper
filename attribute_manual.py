"""Create a reviewed successor draft without writing to the marketplace."""
import re
import time
from attribute_completion import analyze,gather,EXTRACTOR_VERSION
import attribute_edit_store as store


def add(conn,query,cid,item,actor,parent,form,shop,token,get):
    names=('manual_key','manual_field','manual_value','manual_note')
    if any(len(form.getlist(k))!=1 for k in names):raise ValueError('Formulário de preenchimento inválido.')
    key,code,value,note=(form[k] for k in names)
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',key):raise ValueError('Recarregue o formulário de preenchimento.')
    request=dict(parent_plan=str(parent['id']),field=code,value=value,note=note)
    previous=store.by_key(conn,query,cid,item,actor,key)
    if previous:
        if previous['data'].get('manual_request')!=request:raise ValueError('Este formulário já foi usado com outros dados.')
        return previous
    data=parent['data']
    if parent['state']!='ready' or data.get('extractor_version')!=EXTRACTOR_VERSION or int(time.time())-parent['created_at']>900 or data.get('blocked'):raise ValueError('Faça uma nova leitura antes de informar dados.')
    if shop.get('status')!='ativa':raise ValueError('Conexão inativa.')
    if code not in {f['id'] for f in data.get('manual_fields',[])}:raise ValueError('Campo indisponível para preenchimento nesta análise.')
    if store.active(conn,query,cid,item):raise ValueError('Há um envio pendente de confirmação.')
    if data.get('manual_inputs') and data.get('manual_actor')!=actor:raise ValueError('Responsável divergente.')
    inputs=[v for v in data.get('manual_inputs',[]) if v['id']!=code]+[dict(id=code,value=value,note=note)]
    facts=gather(token(),shop['user_id'],item,get)
    if facts['fingerprint']!=data['fingerprint'] or facts['blocked']:
        store.transition(conn,query,parent,actor,'stale',dict(message='O anúncio ou suas regras mudaram. Faça uma nova leitura.'))
        return parent
    updated=analyze(facts,inputs,actor)
    updated.update(manual_request=request,parent_plan=str(parent['id']))
    child,created=store.create(conn,query,cid,item,actor,key,dict(manual_request=request))
    if created:
        store.transition(conn,query,child,actor,'ready',dict(message='Dado adicionado à revisão. Confira e selecione antes de enviar.'),data=updated)
        store.transition(conn,query,parent,actor,'stale',dict(message='Revisão substituída após inclusão de dado.',successor_plan=str(child['id'])))
    return child
