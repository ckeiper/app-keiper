"""Human review of paused listings; never changes a marketplace offer."""
from datetime import datetime
from html import escape
import secrets
from sales_metrics import SAO_PAULO
from listing_priority_sources import listing_signals
from listing_tasks import STATES
from listing_calendar import STYLE

TITLE='Conferir elegibilidade de reativação'
STATUS={'paused':'Pausado','active':'Ativo','closed':'Encerrado','under_review':'Em revisão','inactive':'Inativo'}


def load(conn,query,cid,item,args):
    shops=query(conn,'''SELECT c.cliente,a.item_id,a.titulo,a.status,a.quantidade,a.atualizado_em
        FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s''',(cid,item))
    if not shops:return None
    n=query(conn,'SELECT COUNT(*) AS n FROM listing_tasks WHERE conexao_id=%s AND item_id=%s AND title=%s',(cid,item,TITLE))[0]['n'];pages=max(1,(n+9)//10)
    try:p=max(1,min(pages,int(args.get('pagina','1'))))
    except (TypeError,ValueError):p=1
    tasks=query(conn,'''SELECT id,responsible,due_date,status,description FROM listing_tasks
        WHERE conexao_id=%s AND item_id=%s AND title=%s ORDER BY id DESC LIMIT 10 OFFSET %s''',(cid,item,TITLE,(p-1)*10))
    events=query(conn,'''SELECT previous_at,observed_at,before_value,after_value FROM listing_change_events
        WHERE conexao_id=%s AND item_id=%s AND stream='listing' AND field='status'
        ORDER BY observed_at DESC,id DESC LIMIT 11''',(cid,item))
    return dict(shop=shops[0],tasks=tasks,total=n,page=p,pages=pages,events=events[:10],events_limited=len(events)>10)


def render(cid,item,data,today,now,token,values=None,message=''):
    values=values or {};esc=lambda v:escape(str(v),quote=True);shop=data['shop'];path=f'/anuncios/{int(cid)}/{item}'
    def stamp(v):
        try:return datetime.fromtimestamp(int(v),SAO_PAULO).strftime('%d/%m/%Y %H:%M')
        except (TypeError,ValueError,OverflowError,OSError):return 'não verificada'
    raw=shop.get('atualizado_em');fresh=type(raw) is int and raw>0 and 0<=now-raw<=21600
    status=STATUS.get(shop.get('status'),'Não identificado') if fresh else 'Não verificado · leitura ausente ou antiga'
    signal=listing_signals([shop],{},1,now=now)[item]
    stock=str(int(signal['stock'])) if signal['stock_verified'] else 'não verificado'
    out=STYLE+'''<style>.reactivation article{background:#182e49;border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.reactivation textarea{background:#0b192c;color:#eaf2ff;border:1px solid #426184;border-radius:8px;padding:10px;max-width:100%;width:100%;box-sizing:border-box}.reactivation label{max-width:100%;flex:1}.reactivation .rr-note{white-space:pre-wrap}.reactivation form{align-items:end}.rr-wide{flex-basis:100%!important}@media(max-width:700px){.reactivation form{flex-direction:column;align-items:stretch}}</style>'''
    out+='<section class="lc reactivation"><h2>Revisão de reativação</h2><p>'+esc(shop.get('titulo') or item)+' · '+esc(item)+'</p><nav><a href="/diagnostico/'+str(int(cid))+'/'+item+'">Diagnóstico</a><a href="'+path+'/conteudo">Checklist de conteúdo</a><a href="'+path+'/tarefas">Tarefas e histórico</a></nav><article class="rr-source"><strong>Status observado: '+status+'</strong><p>Estoque geral observado: '+stock+' · coleta: '+stamp(raw)+'. A leitura não comprova disponibilidade atual, inventário Full ou estoque por variação.</p></article>'
    out+='<p>Conferência interna antes de decidir no marketplace. O status pausado não informa o motivo, nem prova que a oferta está elegível para reativação. Esta tela não ativa, pausa ou altera anúncios.</p>'
    if fresh and shop.get('status')!='paused':out+='<p role="status">A leitura recente não indica anúncio pausado. A tarefa, se criada, será apenas uma conferência; não registra uma reativação.</p>'
    out+='<h3>Antes de decidir</h3><article><strong>1. Motivo e restrições</strong><p>Confira o motivo exibido no marketplace e eventuais restrições da conta ou da oferta. Não foi coletado um motivo oficial nesta tela.</p></article><article><strong>2. Oferta e disponibilidade</strong><p>Confira preço final, custos documentados, disponibilidade real e condições logísticas. Estoque positivo isolado não garante elegibilidade.</p></article><article><strong>3. Conteúdo e acompanhamento</strong><p>Revise o checklist e registre o que foi conferido. Se houver uma ação executada no marketplace, documente-a no histórico de ações; concluir a tarefa não substitui esse registro.</p></article>'
    if message:out+='<p role="status">'+esc(message)+'</p>'
    out+='<details'+(' open' if values else '')+'><summary>Planejar conferência</summary><form method="post">'
    for k,v in dict(_csrf=token,submission_key=values.get('submission_key') or secrets.token_urlsafe(24)).items():out+='<input type="hidden" name="'+k+'" value="'+esc(v)+'">'
    out+='<label>Responsável informado<input name="responsible" maxlength="80" required value="'+esc(values.get('responsible',''))+'"></label><label>Prazo · Brasília<input type="date" name="due_date" required value="'+esc(values.get('due_date',''))+'"></label><label class="rr-wide">O que precisa ser conferido<textarea name="description" minlength="10" maxlength="1500" required rows="3">'+esc(values.get('description',''))+'</textarea></label><button>Criar tarefa de conferência</button></form><p>A tarefa terá o título “'+TITLE+'” e ficará disponível no calendário. O responsável e o prazo não são presumidos.</p></details><h3>Conferências planejadas</h3><p>'+str(data['total'])+' tarefas com esse título neste anúncio. Status das tarefas é independente do status da oferta.</p>'
    for row in data['tasks']:
        out+='<article class="rr-task"><strong>'+STATES[row['status']]+'</strong><p>'+esc(row['responsible'])+' · prazo '+row['due_date'].strftime('%d/%m/%Y')+'</p><p class="rr-note">'+esc(row['description'])+'</p><a href="'+path+'/tarefas?status=all&amp;tarefa='+str(row['id'])+'#lt-historico">Gerenciar tarefa e consultar histórico</a></article>'
    if not data['tasks']:out+='<p>Nenhuma conferência planejada.</p>'
    out+='<nav aria-label="Paginação de conferências">Página '+str(data['page'])+' de '+str(data['pages'])
    for label,p in [('Anterior',data['page']-1),('Próxima',data['page']+1)]:
        if 1<=p<=data['pages']:out+=' <a href="'+path+'/reativacao?pagina='+str(p)+'">'+label+'</a>'
    out+='</nav><h3>Mudanças de status observadas</h3><p>Fonte: histórico das coletas. Datas em Brasília indicam detecção; não identificam autor, motivo ou horário exato da ação. Sem eventos não significa ausência de mudanças.</p>'
    if data['events_limited']:out+='<p>Exibidas somente as dez mudanças mais recentes. Histórico completo disponível na tela de ações.</p>'
    def status_label(value):return STATUS.get(value,value) if isinstance(value,str) else 'Não identificado'
    for row in data['events']:
        out+='<article class="rr-event"><strong>'+esc(status_label(row['before_value']))+' → '+esc(status_label(row['after_value']))+'</strong><p>Leitura anterior: '+stamp(row['previous_at'])+' · mudança detectada: '+stamp(row['observed_at'])+'</p></article>'
    if not data['events']:out+='<p>Nenhuma mudança de status registrada nas coletas disponíveis.</p>'
    return out+'<p><a href="'+path+'/acoes">Consultar histórico de ações e alterações</a></p></section>'
