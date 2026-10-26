"""Navy task dashboard. All user-entered fields are escaped."""
from datetime import datetime,timedelta
from html import escape
import secrets
from urllib.parse import urlencode
from sales_metrics import SAO_PAULO
from listing_tasks import STATES,TRANSITIONS

LABELS={'done':'Concluir','cancelled':'Cancelar tarefa','open':'Reabrir'}
FILTERS=dict(open='Abertas',overdue='Atrasadas',done='Concluídas',cancelled='Canceladas',all='Todas')


def render(cid,item_id,shop,model,today,token,values=None,message=''):
    values=values or {};esc=lambda v:escape(str(v),quote=True)
    path=f'/anuncios/{int(cid)}/{item_id}/tarefas'
    out=STYLE+'<section class="listing-tasks"><h2>Tarefas do anúncio</h2><p>'+esc(shop.get('titulo') or item_id)+' · '+esc(item_id)+'</p><nav class="lt-links"><a href="/anuncios/'+str(int(cid))+'/'+item_id+'/calendario">Calendário de tarefas</a><a href="/diagnostico/'+str(int(cid))+'/'+item_id+'">Diagnóstico</a><a href="/anuncios/'+str(int(cid))+'/'+item_id+'/acoes">Ações já realizadas</a></nav><p>Planejamento interno. Marcar uma tarefa como concluída não altera o anúncio nem registra automaticamente uma ação executada.</p>'
    if message:out+='<p class="lt-notice" role="status">'+esc(message)+'</p>'
    counts={row['status']:row['n'] for row in model['counts']}
    overdue=sum(row['overdue'] for row in model['counts'])
    out+='<div class="lt-cards">'+''.join('<a href="'+path+'?status='+code+'#lt-lista"><article><strong>'+str(value)+'</strong><small>'+label+'</small></article></a>' for code,label,value in [('open','Abertas',counts.get('open',0)),('overdue','Atrasadas',overdue),('done','Concluídas',counts.get('done',0)),('cancelled','Canceladas',counts.get('cancelled',0))])+'</div>'
    out+='<details class="lt-create"'+(' open' if values else '')+'><summary>Nova tarefa</summary><form method="post" class="lt-form"><input type="hidden" name="_csrf" value="'+esc(token)+'"><input type="hidden" name="operation" value="create"><input type="hidden" name="submission_key" value="'+esc(values.get('submission_key') or secrets.token_urlsafe(24))+'">'
    for name,label,limit in [('title','Tarefa',120),('responsible','Responsável informado',80)]:
        out+='<label>'+label+'<input name="'+name+'" maxlength="'+str(limit)+'"'+(' minlength="5"' if name=='title' else '')+' required value="'+esc(values.get(name,''))+'"></label>'
    out+='<label>Prazo · Brasília<input type="date" name="due_date" required min="'+(today-timedelta(days=366)).isoformat()+'" max="'+(today+timedelta(days=366)).isoformat()+'" value="'+esc(values.get('due_date',''))+'"></label><label class="lt-wide">Descrição opcional<textarea name="description" maxlength="1500" rows="3">'+esc(values.get('description',''))+'</textarea></label><button>Criar tarefa</button></form><p>Título, responsável, prazo e descrição ficam preservados. Para corrigir o escopo, cancele a tarefa e crie outra; o histórico permanece disponível.</p></details>'
    out+='<form class="lt-filter" id="lt-lista" method="get"><label>Status<select name="status">'+''.join('<option value="'+code+'"'+(' selected' if model['status']==code else '')+'>'+label+'</option>' for code,label in FILTERS.items())+'</select></label><button>Filtrar</button></form><p>Tarefas neste filtro: '+str(model['total'])+'. Cards usam todas as tarefas do anúncio.</p>'
    if not model['rows']:out+='<p role="status">Nenhuma tarefa neste filtro.</p>'
    else:
        out+='<div class="lt-scroll" tabindex="0" role="region" aria-label="Tarefas com rolagem"><table><thead><tr><th scope="col">Tarefa</th><th scope="col">Responsável</th><th scope="col">Prazo</th><th scope="col">Status</th><th scope="col">Atualizar</th></tr></thead><tbody>'
        for row in model['rows']:
            url=path+'?'+urlencode(dict(status=model['status'],pagina=model['page'],tarefa=row['id']))+'#lt-historico'
            out+='<tr><th scope="row"><a href="'+esc(url)+'">'+esc(row['title'])+'</a>'
            if row['description']:out+='<details><summary>Descrição</summary><p class="lt-note">'+esc(row['description'])+'</p></details>'
            out+='</th><td>'+esc(row['responsible'])+'</td><td>'+row['due_date'].strftime('%d/%m/%Y')+('<small class="lt-overdue">Atrasada</small>' if row['status']=='open' and row['due_date']<today else '')+'</td><td>'+STATES[row['status']]+'</td><td class="lt-operations">'
            for target in TRANSITIONS[row['status']]:
                out+='<form method="post">'+''.join('<input type="hidden" name="'+key+'" value="'+esc(value)+'">' for key,value in dict(_csrf=token,operation='status',task_id=row['id'],version=row['version'],previous=row['status'],target=target).items())+'<button>'+LABELS[target]+'</button></form>'
            out+='</td></tr>'
        out+='</tbody></table></div>'
    def pages(page,total,key,extra,anchor):
        text='<nav class="lt-pages" aria-label="Paginação de '+anchor+'">Página '+str(page)+' de '+str(total)
        for label,target in [('Anterior',page-1),('Próxima',page+1)]:
            if 1<=target<=total:
                params=dict(status=model['status'],**extra);params[key]=target
                text+=' <a href="'+esc(path+'?'+urlencode(params)+'#'+anchor)+'">'+label+'</a>'
        return text+'</nav>'
    out+=pages(model['page'],model['pages'],'pagina',{},'lt-lista')
    if model['history']:
        task=model['history']
        out+='<section id="lt-historico" class="lt-history"><h3>Histórico: '+esc(task['title'])+'</h3><p>Estado atual: '+STATES[task['status']]+' · versão '+str(task['version'])+'. Datas em Brasília. Cancelamento preserva os registros.</p><div class="lt-scroll" tabindex="0" role="region" aria-label="Histórico de status da tarefa"><table><thead><tr><th scope="col">Quando</th><th scope="col">Mudança</th><th scope="col">Autor</th><th scope="col">Versão</th></tr></thead><tbody>'
        for row in model['events']:
            out+='<tr><td>'+datetime.fromtimestamp(row['created_at'],SAO_PAULO).strftime('%d/%m/%Y %H:%M:%S')+'</td><td>'+STATES.get(row['from_status'],'Criação')+' → '+STATES[row['to_status']]+'</td><td>Usuário #'+str(row['created_by'])+'</td><td>'+str(row['version'])+'</td></tr>'
        out+='</tbody></table></div>'+pages(model['event_page'],model['event_pages'],'historico_pagina',dict(pagina=model['page'],tarefa=task['id']),'lt-historico')+'</section>'
    return out+'</section>'


STYLE='''<style>body .conteudo .listing-tasks{background:#102238;color:#eaf2ff;border:1px solid #34516e;border-radius:15px;padding:20px;max-width:100%;min-width:0;box-sizing:border-box}body .conteudo .listing-tasks :is(h2,h3,strong){color:#eaf2ff}.listing-tasks p,.listing-tasks small{color:#bdcce1;font-size:12px;line-height:1.7}.lt-links,.lt-pages{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;margin:14px 0}body .conteudo .listing-tasks a{color:#b9e5ff;text-decoration:none}.lt-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}.lt-cards article{padding:14px;background:#182e49;border:1px solid #426184;border-radius:10px;display:grid;gap:8px;overflow-wrap:anywhere}.lt-cards strong{font-size:24px}.lt-create,.lt-history{margin:18px 0;padding:14px;border:1px solid #426184;border-radius:10px;background:#182e49}.listing-tasks summary{cursor:pointer;color:#b9e5ff;padding:10px 0}.lt-form{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.lt-form label,.lt-filter label{display:grid;gap:6px;font-size:12px;min-width:0}.lt-form input,.lt-form textarea,.lt-filter select{box-sizing:border-box;width:100%;min-width:0;padding:11px;border:1px solid #426184;border-radius:8px;background:#0b192c;color:#eaf2ff;font:inherit;color-scheme:dark}.lt-wide{grid-column:1/-1}.listing-tasks button{background:#287ac1;color:#fff;border:0;border-radius:8px;padding:11px 15px;cursor:pointer}.lt-filter{display:flex;align-items:end;gap:12px;margin:18px 0}.lt-scroll{max-width:100%;overflow-x:auto}.listing-tasks table{width:100%;min-width:900px;border-collapse:collapse}.listing-tasks th,.listing-tasks td{padding:12px;border-bottom:1px solid #426184;text-align:left;vertical-align:top;font-size:12px;min-width:130px;max-width:300px;overflow-wrap:anywhere}body .conteudo .listing-tasks :is(th,td){background:#182e49;color:#eaf2ff}.lt-operations{min-width:240px}.lt-operations form{display:inline-block;margin:0 6px 6px 0}.lt-cards a{min-width:0}.lt-note{white-space:pre-wrap}.listing-tasks .lt-overdue{display:block;color:#ffd391}.lt-notice{padding:12px;border:1px solid #8c784c;border-radius:8px;background:#3b3020}.listing-tasks :focus-visible{outline:3px solid #85c8ec;outline-offset:3px}@media(max-width:700px){.lt-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.lt-form{grid-template-columns:1fr}body .conteudo .listing-tasks{padding:14px}}</style>'''
