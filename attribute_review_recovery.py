"""Fresh draft from declared data after a proven pre-write conditional stop."""
import re
from attribute_completion import gather,analyze
import attribute_edit_store as store


def eligible(parent):
    report=parent.get('result',{}).get('conditional',{})
    return (parent.get('state')=='rejected' and isinstance(report,dict)
            and report.get('allow_send') is False and report.get('state') in ('unknown','review')
            and bool(parent.get('data',{}).get('manual_inputs')))


def recover(conn,query,cid,item,actor,parent,key,shop,token,get):
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',key):raise ValueError('Recarregue o formulário de revisão.')
    if (parent.get('conexao_id')!=cid or parent.get('item_id')!=item or parent.get('created_by')!=actor):raise ValueError('Revisão de outra loja ou responsável.')
    request=dict(parent_plan=str(parent['id']))
    previous=store.by_key(conn,query,cid,item,actor,key)
    if previous:
        if previous['data'].get('recovery_request')!=request:raise ValueError('Formulário já utilizado para outra revisão.')
        return previous
    if not eligible(parent):raise ValueError('Somente uma consulta interrompida antes da gravação pode ser retomada.')
    data=parent['data']
    if data.get('manual_actor')!=actor or shop.get('status')!='ativa':raise ValueError('Responsável ou conexão não verificados.')
    if store.active(conn,query,cid,item):raise ValueError('Há um envio pendente de confirmação. Confira esse envio antes de continuar.')
    entries=data['manual_inputs']
    if not isinstance(entries,list) or not 1<=len(entries)<=50:raise ValueError('Dados declarados não verificáveis.')
    facts=gather(token(),shop['user_id'],item,get)
    if facts['blocked']:raise ValueError(facts['blocked'])
    current=analyze(facts);available={f['id'] for f in current.get('manual_fields',[])}
    if any(not isinstance(e,dict) or not isinstance(e.get('id'),str) for e in entries):raise ValueError('Dados declarados inválidos.')
    retained=[e for e in entries if e['id'] in available]
    omitted=[e['id'] for e in entries if e['id'] not in available]
    updated=analyze(facts,retained,actor)
    updated.update(recovery_request=request,parent_plan=str(parent['id']))
    child,created=store.create(conn,query,cid,item,actor,key,dict(recovery_request=request))
    if created:
        store.transition(conn,query,child,actor,'ready',dict(message=str(len(retained))+' dados reaproveitados; '+str(len(omitted))+' campos não reaproveitados por indisponibilidade na leitura atual. Confira e selecione novamente antes de enviar.',recovery=dict(retained=[e['id'] for e in retained],omitted=omitted)),data=updated)
        store.transition(conn,query,parent,actor,'stale',dict(message='Nova revisão criada com leitura atualizada.',successor_plan=str(child['id'])))
    return child
