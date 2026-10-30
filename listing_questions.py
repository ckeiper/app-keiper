"""Bounded analysis of saved questions, without semantic/AI inference."""
from collections import Counter
from datetime import datetime
from html import escape
from urllib.parse import urlencode
from sales_metrics import SAO_PAULO
from listing_calendar import STYLE
from question_sync import STATUSES,FRESH_SECONDS

LIMIT=1000
STATUS_LABELS={'UNANSWERED':'Sem resposta','ANSWERED':'Respondida','CLOSED_UNANSWERED':'Encerrada sem resposta','BANNED':'Bloqueada','DELETED':'Excluída','DISABLED':'Desativada','UNDER_REVIEW':'Em análise'}

def persist(conn,execute,cid,payload,now,expected_seller=None):
    """Validate the entire fetched batch before writing only question/answer evidence."""
    import re
    if not isinstance(payload,dict) or not isinstance(payload.get('questions'),list) or len(payload['questions'])>1000:
        raise ValueError('Formato de perguntas inválido.')
    if type(now) is not int or now<=0:raise ValueError('Data de consulta inválida.')
    if expected_seller is not None and (isinstance(expected_seller,bool) or not re.fullmatch(r'[1-9][0-9]{0,19}',str(expected_seller))):
        raise ValueError('Vendedor esperado não verificável.')
    rows=[];seen=set()
    for q in payload['questions']:
        if not isinstance(q,dict):raise ValueError('Pergunta não verificável.')
        qid=q.get('id')
        if isinstance(qid,bool) or not isinstance(qid,(str,int)) or not re.fullmatch(r'[0-9]{1,20}',str(qid)) or int(qid)<=0:
            raise ValueError('Pergunta sem identificador válido.')
        qid=str(int(qid))
        if qid in seen:raise ValueError('Pergunta duplicada no lote.')
        seen.add(qid)
        if expected_seller is not None and (isinstance(q.get('seller_id'),bool) or str(q.get('seller_id'))!=str(expected_seller)):
            raise ValueError('Vendedor da pergunta não confirmado.')
        if any(key not in q for key in ('text','status','date_created','answer')):
            raise ValueError('Campos da pergunta não verificáveis.')
        answer=q['answer'] if q['answer'] is not None else {}
        if not isinstance(answer,dict):raise ValueError('Resposta inválida.')
        item=q.get('item_id');text=q['text'];status=q['status'];stamp=q['date_created'];reply=answer.get('text')
        if not isinstance(item,str) or not re.fullmatch(r'MLB[0-9]{1,20}',item):raise ValueError('Anúncio inválido na pergunta.')
        for value,limit in ((text,20000),(reply,20000),(status,100),(stamp,100),(answer.get('status'),100)):
            if value is not None and (not isinstance(value,str) or '\x00' in value or len(value)>limit):
                raise ValueError('Campos de pergunta inválidos.')
        deleted=q.get('deleted_from_listing');hold=q.get('hold')
        if any(value is not None and type(value) is not bool for value in (deleted,hold)):
            raise ValueError('Visibilidade da pergunta não verificável.')
        verified=expected_seller is not None and status in STATUSES
        rows.append((cid,qid,item,text,status,reply,stamp,now,now,now if verified else None,
            'read' if verified else 'unknown',None if verified else 'Status não verificado.',
            str(expected_seller) if expected_seller is not None else None,deleted,hold,answer.get('status')))
    for values in rows:
        execute(conn,'''INSERT INTO perguntas(conexao_id,pergunta_id,item_id,texto,status,resposta,data,atualizado_em,
            consulta_em,status_confirmado_em,consulta_estado,consulta_erro,vendedor_confirmado,excluida_do_anuncio,em_espera,resposta_status)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(conexao_id,pergunta_id) DO UPDATE SET item_id=EXCLUDED.item_id,texto=EXCLUDED.texto,
            status=EXCLUDED.status,resposta=EXCLUDED.resposta,data=EXCLUDED.data,atualizado_em=EXCLUDED.atualizado_em,
            consulta_em=EXCLUDED.consulta_em,status_confirmado_em=EXCLUDED.status_confirmado_em,
            consulta_estado=EXCLUDED.consulta_estado,consulta_erro=EXCLUDED.consulta_erro,
            vendedor_confirmado=EXCLUDED.vendedor_confirmado,excluida_do_anuncio=EXCLUDED.excluida_do_anuncio,
            em_espera=EXCLUDED.em_espera,resposta_status=EXCLUDED.resposta_status''',values)
    return len(rows)


def verified_status(row,now,seller_id):
    stamp=row.get('status_confirmado_em')
    return (row.get('consulta_estado')=='read' and type(stamp) is int and 0<=now-stamp<=FRESH_SECONDS
            and seller_id is not None and row.get('vendedor_confirmado')==str(seller_id)
            and row.get('status') in STATUSES)


def model(rows,args,now=None,seller_id=None):
    import time
    now=int(time.time()) if now is None else now
    limited=len(rows)>LIMIT;rows=rows[:LIMIT]
    selected=args.get('status','all')
    if selected not in ('all','UNANSWERED','ANSWERED'):selected='all'
    counts=Counter(r.get('status') for r in rows)
    verified=[r for r in rows if verified_status(r,now,seller_id)]
    recent=Counter(r.get('status') for r in verified)
    pending=sum(r.get('status')=='UNANSWERED' and r.get('excluida_do_anuncio') is False and r.get('em_espera') is False for r in verified)
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
    return dict(rows=filtered[(p-1)*10:p*10],recent=recent,pending=pending,unknown=len(rows)-len(verified),now=now,seller_id=seller_id,total=len(rows),filtered=len(filtered),counts=counts,limited=limited,
                status=selected,page=p,pages=pages,groups=repeated[(gp-1)*10:gp*10],group_total=len(repeated),group_page=gp,group_pages=gpages)


def render(cid,item,shop,data):
    esc=lambda x:escape(str(x),quote=True)
    path=f'/anuncios/{int(cid)}/{item}/perguntas'
    out=STYLE+'''<style>.lq-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.lq-cards article,.lq-row{background:#182e49;border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.lq-cards{margin:16px 0}.lq-cards article{display:grid;gap:8px;font-size:12px;margin:0}.lq-cards strong{font-size:24px}.lq-text{white-space:pre-wrap}@media(max-width:650px){.lq-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>'''
    out+='<section class="lc listing-questions"><h2>Perguntas e recorrências</h2><p>'+esc(shop.get('titulo') or item)+' · '+esc(item)+'</p><nav><a href="/anuncios/'+str(int(cid))+'/'+item+'/conteudo">Revisar conteúdo</a><a href="/anuncios/'+str(int(cid))+'/'+item+'/tarefas">Planejar ajustes</a></nav><p>Perguntas salvas e status conferidos nas coletas.</p>'
    if data['limited']:out+='<p role="status">Amostra limitada aos 1.000 registros com coleta mais recente deste anúncio. Cards e recorrências usam somente essa amostra.</p>'
    out+='<div class="lq-cards">'+''.join('<article><strong>'+str(n)+'</strong><span>'+label+'</span></article>' for n,label in [(data['total'],'Perguntas na base analisada'),(data['pending'],'Sem resposta · consulta recente'),(data['recent'].get('ANSWERED',0),'Respondidas · consulta recente'),(data['unknown'],'Sem verificação recente')])+'</div>'
    other=data['total']-data['counts'].get('UNANSWERED',0)-data['counts'].get('ANSWERED',0)
    if other:out+='<p>Outros status: '+str(other)+'.</p>'
    coverage=data.get('coverage')
    if coverage and str(coverage.get('vendedor_id'))==str(data.get('seller_id')):
        try:
            collection_stamp=datetime.fromtimestamp(int(coverage.get('consultado_em')),SAO_PAULO).strftime('%d/%m/%Y %H:%M · Brasília')
        except (ValueError,TypeError,OverflowError,OSError):collection_stamp='Data não verificada'
        total=coverage.get('total_informado')
        label='não verificado' if total is None else str(total)
        out+='<section class="lq-coverage"><h3>Última coleta da loja</h3><p>'+esc(collection_stamp)+'</p><p>'+str(coverage['lidas'])+' perguntas observadas · total informado: '+label+' · '+str(coverage['paginas'])+' páginas.</p><p>'+str(coverage['revisadas'])+' status antigos revisados · '+str(coverage['indisponiveis'])+' consultas individuais indisponíveis.</p>'
        if coverage.get('estado')!='read':out+='<p>Coleta parcial ou não verificada. Nenhuma conclusão sobre histórico completo.</p>'
        out+='</section>'
    else:
        out+='<p>Cobertura da coleta ainda não verificada.</p>'
    out+='<details><summary>Critérios de atualização e cobertura</summary><p>Até duas páginas de 50 perguntas e duas consultas individuais por atualização. Perguntas antigas entram em rodízio pela consulta mais antiga. Consulta recente corresponde às últimas seis horas, na mesma conta. O aviso de resposta exige status sem resposta e visibilidade confirmada, sem espera ou remoção.</p><p>Totais da coleta referem-se à loja; cards e filtros referem-se a este anúncio e à amostra local. Paginação lida não certifica histórico integral: perguntas excluídas anteriormente não são reconstruídas e o conjunto pode mudar entre páginas. Uma consulta indisponível não confirma exclusão nem resposta. O agrupamento literal ignora maiúsculas e espaços repetidos. Não identifica intenção, objeção, sentimento ou avaliação de compradores.</p></details>'
    def pages(p,total,key,anchor):
        text='<nav aria-label="Paginação de '+anchor+'">Página '+str(p)+' de '+str(total)
        for label,target in [('Anterior',p-1),('Próxima',p+1)]:
            if 1<=target<=total:
                params=dict(status=data['status'],pagina=data['page'],recorrencias=data['group_page']);params[key]=target
                text+=' <a href="'+esc(path+'?'+urlencode(params)+'#'+anchor)+'">'+label+'</a>'
        return text+'</nav>'
    out+='<section id="recorrencias"><h3>Textos repetidos</h3><p>'+str(data['group_total'])+' grupos de textos iguais na base analisada, considerando todos os status salvos.</p>'
    for group in data['groups']:out+='<article class="lq-row"><strong>'+str(group['n'])+' ocorrências · '+str(group['pending'])+' sem resposta registrada</strong><p class="lq-text">'+esc(group['text'])+'</p></article>'
    if not data['groups']:out+='<p>Nenhum texto repetido identificado nesta base.</p>'
    out+=pages(data['group_page'],data['group_pages'],'recorrencias','recorrencias')+'</section><section id="perguntas"><h3>Perguntas salvas</h3><form method="get"><label>Último status salvo<select name="status">'+''.join('<option value="'+s+'"'+(' selected' if data['status']==s else '')+'>'+label+'</option>' for s,label in [('all','Todos'),('UNANSWERED','Sem resposta no registro'),('ANSWERED','Respondidas no registro')])+'</select></label><button>Filtrar</button></form><p>'+str(data['filtered'])+' perguntas neste filtro. Ordenação por coleta mais recente; datas em Brasília.</p>'
    def stamp(value):
        try:
            dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
            if dt.tzinfo is None:return 'Data sem fuso confirmado'
            return dt.astimezone(SAO_PAULO).strftime('%d/%m/%Y %H:%M')
        except (ValueError,TypeError):return 'Data não verificada'
    for row in data['rows']:
        try:collected=datetime.fromtimestamp(int(row['atualizado_em']),SAO_PAULO).strftime('%d/%m/%Y %H:%M')
        except (ValueError,TypeError,KeyError,OverflowError,OSError):collected='não verificada'
        confirmed=verified_status(row,data['now'],data.get('seller_id'))
        visibility='Retirada do anúncio na última consulta' if row.get('excluida_do_anuncio') is True else 'Em espera na última consulta' if row.get('em_espera') is True else 'Visibilidade não verificada' if row.get('excluida_do_anuncio') is None or row.get('em_espera') is None else ''
        evidence='Status consultado nas últimas seis horas' if confirmed else 'Status sem verificação recente · último registro salvo'
        out+='<article class="lq-row"><strong>Pergunta #'+esc(row.get('pergunta_id',''))+'</strong><p>'+stamp(row.get('data'))+' · '+evidence+' · '+esc(STATUS_LABELS.get(row.get('status'),row.get('status') or 'não informado'))+' · coleta '+collected+'</p><p>'+esc(visibility)+'</p><p class="lq-text">'+esc(row.get('texto') or 'Texto não disponível')+'</p><p class="lq-text">Resposta registrada: '+esc('não disponível · '+str(row['resposta_status']) if row.get('resposta_status') in ('BANNED','DISABLED') else row.get('resposta') or 'não disponível')+'</p></article>'
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
            shops=query(conn,'''SELECT c.cliente,c.user_id,a.titulo FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id
                WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
            if not shops:return 'Anúncio não encontrado nesta loja.',404
            coverage=query(conn,'SELECT * FROM perguntas_coleta WHERE conexao_id=%s',(cid,))
            rows=query(conn,'''SELECT pergunta_id,texto,status,resposta,data,atualizado_em,consulta_em,status_confirmado_em,consulta_estado,vendedor_confirmado,excluida_do_anuncio,em_espera,resposta_status FROM perguntas
                WHERE conexao_id=%s AND item_id=%s ORDER BY atualizado_em DESC NULLS LAST,pergunta_id DESC LIMIT 1001''',(cid,item_id))
        return shop_page('Perguntas do anúncio',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,shops[0],dict(model(rows,request.args,seller_id=shops[0].get('user_id')),coverage=coverage[0] if coverage else None)))
