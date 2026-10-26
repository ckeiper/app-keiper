from datetime import datetime,timedelta
from html import escape
import secrets
from sales_metrics import SAO_PAULO
from listing_calendar import STYLE
from listing_goals import evaluate


def render(cid,item,shop,model,today,now,token,values=None,message=''):
    esc=lambda v:escape(str(v),quote=True);values=values or {};path=f'/anuncios/{int(cid)}/{item}'
    out=STYLE+'''<style>.sg-row{background:#182e49;border:1px solid #426184;border-radius:10px;padding:16px;margin:14px 0;overflow-wrap:anywhere}.sg-alert{border-left:4px solid #ffc570}.sg-met{border-left:4px solid #70d8b2}.stock-goals form{flex-wrap:wrap}.stock-goals label{max-width:100%}.stock-goals input{min-width:0}@media(max-width:700px){.stock-goals form{flex-direction:column;align-items:stretch}}</style>'''
    out+='<section class="lc stock-goals"><h2>Metas de estoque mínimo</h2><p>'+esc(shop.get('titulo') or item)+' · '+esc(item)+'</p><nav><a href="'+path+'/tarefas">Planejar ações</a><a href="/diagnostico/'+str(int(cid))+'/'+item+'">Diagnóstico</a></nav><p>Limite operacional informado pelo administrador. Alertas são calculados ao abrir esta tela, usando estoque do catálogo com até seis horas de coleta. Não são enviados por e-mail ou WhatsApp. Recarregue para conferir novas leituras.</p><p>Não prevê ruptura, não garante disponibilidade atual e não representa estoque por variação ou inventário Full. Metas encerradas não recebem resultado histórico a partir do estoque de hoje.</p>'
    if message:out+='<p role="status">'+esc(message)+'</p>'
    out+='<details'+(' open' if values else '')+'><summary>Cadastrar meta</summary><form method="post">'
    for name,val in dict(_csrf=token,operation='create',submission_key=values.get('submission_key') or secrets.token_urlsafe(24)).items():out+='<input type="hidden" name="'+name+'" value="'+esc(val)+'">'
    out+='<label>Estoque mínimo · unidades<input type="number" name="minimum" min="0" max="1000000" step="1" required value="'+esc(values.get('minimum',''))+'"></label>'
    for key,label in [('start_date','Início'),('end_date','Fim')]:out+='<label>'+label+' · Brasília<input type="date" name="'+key+'" required value="'+esc(values.get(key,''))+'"></label>'
    out+='<label>Responsável informado<input name="responsible" maxlength="80" required value="'+esc(values.get('responsible',''))+'"></label><button>Salvar meta</button></form><p>Período de 1 a 90 dias. Valores ficam preservados; para corrigir, cancele a meta e cadastre outra. Meta zero é permitida e não dispara alerta para estoque zero.</p></details><h3>Metas registradas</h3><p>'+str(model['total'])+' registros. A avaliação atual usa a leitura disponível nesta abertura. As sincronizações também registram avaliações no histórico, sem garantia de monitoramento contínuo.</p>'
    def stamp(t):return datetime.fromtimestamp(t,SAO_PAULO).strftime('%d/%m/%Y %H:%M')
    for row in model['rows']:
        code,label,stock=evaluate(row,shop,today,now)
        out+='<article class="sg-row sg-'+code+'"><strong>Mínimo de '+str(row['minimum'])+' unidades</strong><p>'+row['start_date'].strftime('%d/%m/%Y')+' a '+row['end_date'].strftime('%d/%m/%Y')+' · '+esc(row['responsible'])+'</p><p><strong>'+label+'</strong></p>'
        if stock is not None:out+='<p>Estoque observado: '+str(stock)+' · coleta: '+stamp(int(shop['atualizado_em']))+'</p>'
        out+='<p>Cadastrada em '+stamp(row['created_at'])+' · Usuário #'+str(row['created_by'])+'</p>'
        if row.get('cancelled_at') is not None:out+='<p>Cancelada em '+stamp(row['cancelled_at'])+' · Usuário #'+str(row['cancelled_by'])+'</p>'
        else:out+='<form method="post">'+''.join('<input type="hidden" name="'+k+'" value="'+esc(v)+'">' for k,v in dict(_csrf=token,operation='cancel',goal_id=row['id']).items())+'<button>Cancelar meta e preservar registro</button></form>'
        out+='<p><a href="'+path+'/metas/historico/'+str(row['id'])+'">Histórico das avaliações</a></p></article>'
    if not model['rows']:out+='<p>Nenhuma meta cadastrada. Nenhum limite é presumido automaticamente.</p>'
    out+='<nav aria-label="Paginação de metas">Página '+str(model['page'])+' de '+str(model['pages'])
    for label,p in [('Anterior',model['page']-1),('Próxima',model['page']+1)]:
        if 1<=p<=model['pages']:out+=' <a href="'+path+'/metas?pagina='+str(p)+'">'+label+'</a>'
    return out+'</nav></section>'
