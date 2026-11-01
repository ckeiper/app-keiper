"""Create a reviewed successor draft without writing to the marketplace."""
import re
import time
from attribute_completion import analyze,gather,EXTRACTOR_VERSION
import attribute_edit_store as store


def add(conn,query,cid,item,actor,parent,form,shop,token,get):
    key,entries=parse(form)
    request=dict(parent_plan=str(parent['id']),entries=entries) if len(entries)>1 else dict(parent_plan=str(parent['id']),field=entries[0]['id'],value=entries[0]['value'],note=entries[0]['note'])
    previous=store.by_key(conn,query,cid,item,actor,key)
    if previous:
        if previous['data'].get('manual_request')!=request:raise ValueError('Este formulário já foi usado com outros dados.')
        return previous
    data=parent['data']
    if parent['state']!='ready' or data.get('extractor_version')!=EXTRACTOR_VERSION or int(time.time())-parent['created_at']>900 or data.get('blocked'):raise ValueError('Faça uma nova leitura antes de informar dados.')
    if shop.get('status')!='ativa':raise ValueError('Conexão inativa.')
    eligible={f['id'] for f in data.get('manual_fields',[])}
    if any(entry['id'] not in eligible for entry in entries):raise ValueError('Campo indisponível para preenchimento nesta análise.')
    if store.active(conn,query,cid,item):raise ValueError('Há um envio pendente de confirmação.')
    if data.get('manual_inputs') and data.get('manual_actor')!=actor:raise ValueError('Responsável divergente.')
    codes={entry['id'] for entry in entries}
    inputs=[v for v in data.get('manual_inputs',[]) if v['id'] not in codes]+entries
    if len(inputs)>50:raise ValueError('A revisão aceita até 50 campos informados no total.')
    facts=gather(token(),shop['user_id'],item,get)
    if facts['fingerprint']!=data['fingerprint'] or facts['blocked']:
        store.transition(conn,query,parent,actor,'stale',dict(message='O anúncio ou suas regras mudaram. Faça uma nova leitura.'))
        return parent
    updated=analyze(facts,inputs,actor)
    updated.update(manual_request=request,parent_plan=str(parent['id']))
    child,created=store.create(conn,query,cid,item,actor,key,dict(manual_request=request))
    if created:
        store.transition(conn,query,child,actor,'ready',dict(message=('Dado adicionado' if len(entries)==1 else str(len(entries))+' dados adicionados')+' à revisão. Confira e selecione antes de enviar.'),data=updated)
        store.transition(conn,query,parent,actor,'stale',dict(message='Revisão substituída após inclusão de dado.',successor_plan=str(child['id'])))
    return child


def parse(form):
    keys=form.getlist('manual_key')
    if len(keys)!=1 or not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',keys[0]):raise ValueError('Recarregue o formulário de preenchimento.')
    fields,values,notes=(form.getlist(k) for k in ('manual_field','manual_value','manual_note'))
    if not 1<=len(fields)<=50 or len(fields)!=len(values) or len(fields)!=len(notes):raise ValueError('Informe de 1 a 50 campos completos no lote.')
    entries=[];seen=set()
    for code,value,note in zip(fields,values,notes):
        if not isinstance(code,str) or not code or len(code)>250 or code in seen:raise ValueError('Selecione campos diferentes para cada linha do lote.')
        if not isinstance(value,str) or not value.strip() or len(value)>1000 or any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError('Preencha um valor válido em cada linha do lote.')
        if not isinstance(note,str) or len(note)>500 or any(ord(c)<32 or ord(c)==127 for c in note):raise ValueError('Fonte informada inválida.')
        seen.add(code);entries.append(dict(id=code,value=value,note=note))
    return keys[0],entries
