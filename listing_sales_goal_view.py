"""Scoped sales goal forms; no remote calls or writes on render."""
from html import escape
import secrets
from listing_calendar import STYLE

LABELS={'orders':'Pedidos pagos','units':'Unidades vendidas','gross_items':'Valor bruto dos itens · R$'}


def render(cid,item,shop,model,today,now,token,values=None,message=''):
    esc=lambda v:escape(str(v),quote=True)
    values=values or {};base=f'/anuncios/{int(cid)}/{item}'
    out=STYLE+'''<style>.sales-goals{overflow-wrap:anywhere}.sales-goals article{border:1px solid var(--border,#426184);border-radius:12px;padding:16px;margin:16px 0}.sales-goals .goal-met{border-left:4px solid #39b886}.sales-goals .goal-alert{border-left:4px solid #e06a70}.sales-goals form{flex-wrap:wrap}.sales-goals input,.sales-goals select{min-width:0;max-width:100%}@media(max-width:700px){.sales-goals form{flex-direction:column;align-items:stretch}}</style>'''
    out+='<section class="lc sales-goals"><h2>Metas de vendas</h2><p>'+esc(shop.get('titulo') or item)+'</p><nav><a href="'+base+'/metas">Metas de estoque</a><a href="/diagnostico/'+str(cid)+'/'+item+'">Diagnóstico</a></nav>'
    out+='<p>Resultados até o último dia completo, em Brasília. Alertas de meta não atingida aparecem somente após o prazo, com cobertura verificada de todo o período. Dados incompletos ficam sem diagnóstico.</p><p>Valor bruto dos itens considera pedidos pagos e aprovados em reais; não representa receita líquida ou lucro. Avaliações nesta tela usam a base atual e podem mudar após correções dos pedidos. Sem envio de mensagens.</p>'
    if message:out+='<p role="alert">'+esc(message)+'</p>'
    def hidden(fields):return ''.join('<input type="hidden" name="'+k+'" value="'+esc(v)+'">' for k,v in fields.items())
    out+='<details'+(' open' if values else '')+'><summary>Cadastrar meta</summary><form method="post">'+hidden(dict(_csrf=token,operation='create',submission_key=values.get('submission_key') or secrets.token_urlsafe(24)))
    out+='<label>Métrica<select name="metric" required>'
    for key,label in LABELS.items():out+='<option value="'+key+'"'+(' selected' if values.get('metric')==key else '')+'>'+label+'</option>'
    out+='</select></label><label>Meta<input name="target" inputmode="decimal" required maxlength="13" value="'+esc(values.get('target',''))+'"></label>'
    for key,label in [('start_date','Início'),('end_date','Fim')]:out+='<label>'+label+'<input type="date" name="'+key+'" required value="'+esc(values.get(key,''))+'"></label>'
    out+='<label>Responsável<input name="responsible" maxlength="80" required value="'+esc(values.get('responsible',''))+'"></label><button>Salvar meta</button></form><p>Período de 1 a 90 dias. Para corrigir uma meta, cancele e cadastre outra; o registro anterior é preservado.</p></details>'
    for row in model['rows']:
        state,label,value,cutoff=model['evaluations'][row['id']]
        fmt=lambda v:format(v,',.2f').replace(',','X').replace('.',',').replace('X','.') if row['metric']=='gross_items' else str(int(v))
        out+='<article class="goal-'+state+'"><h3>'+LABELS[row['metric']]+': '+fmt(row['target'])+'</h3><p>'+esc(row['start_date'])+' a '+esc(row['end_date'])+' · '+esc(row['responsible'])+'</p><strong>'+label+'</strong>'
        if value is not None:out+='<p>Apurado: '+fmt(value)+' · até '+esc(cutoff)+'</p>'
        out+='<p>Registro #'+str(row['id'])+' · cadastrado pelo usuário #'+str(row['created_by'])+'</p>'
        if row.get('cancelled_at') is None:out+='<form method="post">'+hidden(dict(_csrf=token,operation='cancel',goal_id=row['id']))+'<button>Cancelar meta e preservar registro</button></form>'
        out+='</article>'
    if not model['rows']:out+='<p>Nenhuma meta cadastrada.</p>'
    out+='<nav aria-label="Paginação">Página '+str(model['page'])+' de '+str(model['pages'])
    for label,p in [('Anterior',model['page']-1),('Próxima',model['page']+1)]:
        if 1<=p<=model['pages']:out+=' <a href="'+base+'/metas-vendas?pagina='+str(p)+'">'+label+'</a>'
    return out+'</nav></section>'
