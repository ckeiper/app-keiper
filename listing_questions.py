"""Bounded analysis of saved questions, without semantic/AI inference."""
from collections import Counter
from datetime import datetime
from html import escape
from urllib.parse import urlencode
from sales_metrics import SAO_PAULO
from listing_calendar import STYLE

LIMIT=1000

def persist(conn,execute,cid,payload,now):
    """Validate whole fetched batch before any write. Caller owns the transaction."""
    if not isinstance(payload,dict) or not isinstance(payload.get('questions'),list):raise ValueError('Formato de perguntas inválido.')
    rows=[];seen=set()
    for q in payload['questions']:
        if not isinstance(q,dict) or not str(q.get('id','')).isdigit() or int(q['id'])<=0:raise ValueError('Pergunta sem identificador válido.')
        if str(q['id']) in seen:raise ValueError('Pergunta duplicada no lote.')
        seen.add(str(q['id']));answer=q.get('answer') or {}
        if not isinstance(answer,dict):raise ValueError('Resposta inválida.')
        item=q.get('item_id');text=q.get('text');status=q.get('status');stamp=q.get('date_created');reply=answer.get('text')
        import re
        if not isinstance(item,str) or not re.fullmatch(r'MLB[0-9]{1,20}',item):raise ValueError('Anúncio inválido na pergunta.')
        if any(v is not None and (not isinstance(v,str) or '\x00' in v) for v in (text,status,stamp,reply)):raise ValueError('Campos de pergunta inválidos.')
        rows.append((cid,str(q['id']),item,text,status,reply,stamp,now))
    for values in rows:
        execute(conn,'''INSERT INTO perguntas(conexao_id,pergunta_id,item_id,texto,status,resposta,data,atualizado_em)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(conexao_id,pergunta_id) DO UPDATE SET
            item_id=EXCLUDED.item_id,texto=EXCLUDED.texto,status=EXCLUDED.status,resposta=EXCLUDED.resposta,
            data=EXCLUDED.data,atualizado_em=EXCLUDED.atualizado_em''',values)
    return len(rows)


def model(rows,args):
    limited=len(rows)>LIMIT;rows=rows[:LIMIT]
    selected=args.get('status','all')
    if selected not in ('all','UNANSWERED','ANSWERED'):selected='all'
    counts=Counter(r.get('status') for r in rows)
    filtered=[r for r in rows if selected=='all' or r.get('status')==selected]
    def page(key,total):
        pages=max(1,(total+9)//10)
        try:p=max(1,min(pages,int(args.get(key,'1'))))
        except (TypeError,ValueError):p=1
        return p,pages
    p,pages=page('pagina',len(filtered));groups={}
    for row in rows:
        text=row.get('texto')
        if not isinstance(text,str) or not text.strip():continue
        key=' '.join(text.split()).casefold()
        if key not in groups:groups[key]=dict(text=text,n=0,pending=0)
        groups[key]['n']+=1;groups[key]['pending']+=row.get('status')=='UNANSWERED'
    repeated=sorted((g for g in groups.values() if g['n']>=2),key=lambda g:(-g['n'],g['text'].casefold()))
    gp,gpages=page('recorrencias',len(repeated))
    return dict(rows=filtered[(p-1)*10:p*10],total=len(rows),filtered=len(filtered),counts=counts,limited=limited,
                status=selected,page=p,pages=pages,groups=repeated[(gp-1)*10:gp*10],group_total=len(repeated),group_page=gp,group_pages=gpages)


def render(cid,item,shop,data):
    esc=lambda x:escape(str(x),quote=True)
    path=f'/anuncios/{int(cid)}/{item}/perguntas'
    out=STYLE+'''<style>.lq-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.lq-cards article,.lq-row{background:#182e49;border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.lq-cards article{display:grid;gap:8px;font-size:12px}.lq-cards strong{font-size:24px}.lq-text{white-space:pre-wrap}@media(max-width:650px){.lq-cards{grid-template-columns:1fr}}</style>'''
    out+='<section class="lc listing-questions"><h2>Perguntas e recorrências</h2><p>'+esc(shop.get('titulo') or item)+' · '+esc(item)+'</p><nav><a href="/anuncios/'+str(int(cid))+'/'+item+'/conteudo">Revisar conteúdo</a><a href="/anuncios/'+str(int(cid))+'/'+item+'/tarefas">Planejar ajustes</a></nav><p>Base local das coletas disponíveis, sem garantia de histórico integral. A coleta atual consulta até 50 perguntas por loja em cada atualização. Registros anteriores passam a ser preservados; perguntas já apagadas não são reconstruídas.</p>'
    if data['limited']:out+='<p role="status">Amostra limitada aos 1.000 registros com coleta mais recente deste anúncio. Cards e recorrências usam somente essa amostra.</p>'
    out+='<div class="lq-cards">'+''.join('<article><strong>'+str(n)+'</strong><span>'+label+'</span></article>' for n,label in [(data['total'],'Perguntas na base analisada'),(data['counts'].get('UNANSWERED',0),'Sem resposta no último registro'),(data['counts'].get('ANSWERED',0),'Respondidas no último registro')])+'</div><p>Outros status: '+str(data['total']-data['counts'].get('UNANSWERED',0)-data['counts'].get('ANSWERED',0))+'. Status antigos podem ter mudado fora da amostra coletada; confira no marketplace antes de agir.</p>'
    def pages(p,total,key,anchor):
        text='<nav aria-label="Paginação de '+anchor+'">Página '+str(p)+' de '+str(total)
        for label,target in [('Anterior',p-1),('Próxima',p+1)]:
            if 1<=target<=total:
                params=dict(status=data['status'],pagina=data['page'],recorrencias=data['group_page']);params[key]=target
                text+=' <a href="'+esc(path+'?'+urlencode(params)+'#'+anchor)+'">'+label+'</a>'
        return text+'</nav>'
    out+='<section id="recorrencias"><h3>Textos repetidos</h3><p>Agrupamento literal: ignora somente maiúsculas e espaços repetidos. Não identifica intenção, objeção, sentimento ou avaliação de compradores. '+str(data['group_total'])+' grupos repetidos na base analisada, considerando todos os status.</p>'
    for group in data['groups']:out+='<article class="lq-row"><strong>'+str(group['n'])+' ocorrências · '+str(group['pending'])+' sem resposta registrada</strong><p class="lq-text">'+esc(group['text'])+'</p></article>'
    if not data['groups']:out+='<p>Nenhum texto repetido identificado nesta base.</p>'
    out+=pages(data['group_page'],data['group_pages'],'recorrencias','recorrencias')+'</section><section id="perguntas"><h3>Perguntas salvas</h3><form method="get"><label>Status<select name="status">'+''.join('<option value="'+s+'"'+(' selected' if data['status']==s else '')+'>'+label+'</option>' for s,label in [('all','Todos'),('UNANSWERED','Sem resposta'),('ANSWERED','Respondidas')])+'</select></label><button>Filtrar</button></form><p>'+str(data['filtered'])+' perguntas neste filtro. Ordenação por coleta mais recente; datas em Brasília.</p>'
    def stamp(value):
        try:
            dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
            if dt.tzinfo is None:return 'Data sem fuso confirmado'
            return dt.astimezone(SAO_PAULO).strftime('%d/%m/%Y %H:%M')
        except (ValueError,TypeError):return 'Data não verificada'
    for row in data['rows']:
        try:collected=datetime.fromtimestamp(int(row['atualizado_em']),SAO_PAULO).strftime('%d/%m/%Y %H:%M')
        except (ValueError,TypeError,KeyError,OverflowError,OSError):collected='não verificada'
        out+='<article class="lq-row"><strong>Pergunta #'+esc(row.get('pergunta_id',''))+'</strong><p>'+stamp(row.get('data'))+' · status '+esc(row.get('status') or 'não informado')+' · coleta '+collected+'</p><p class="lq-text">'+esc(row.get('texto') or 'Texto não disponível')+'</p><p class="lq-text">Resposta registrada: '+esc(row.get('resposta') or 'não disponível')+'</p></article>'
    if not data['rows']:out+='<p>Nenhuma pergunta salva neste filtro. Ausência de registros não comprova ausência de dúvidas.</p>'
    return out+pages(data['page'],data['pages'],'pagina','perguntas')+'</section></section>'


def register_questions(app,login_required,can_view,bank,query,execute,shop_page):
    from flask import session,request
    import re
    @app.route('/anuncios/<int:cid>/<item_id>/perguntas',methods=['GET'])
    @login_required
    def listing_question_report(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            shops=query(conn,'''SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id
                WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
            if not shops:return 'Anúncio não encontrado nesta loja.',404
            rows=query(conn,'''SELECT pergunta_id,texto,status,resposta,data,atualizado_em FROM perguntas
                WHERE conexao_id=%s AND item_id=%s ORDER BY atualizado_em DESC NULLS LAST,pergunta_id DESC LIMIT 1001''',(cid,item_id))
        return shop_page('Perguntas do anúncio',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,shops[0],model(rows,request.args)))
