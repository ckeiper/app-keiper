"""Bounded analysis of saved questions, without semantic/AI inference."""
from collections import Counter
import unicodedata
import re
from datetime import datetime
from html import escape
from urllib.parse import urlencode
from sales_metrics import SAO_PAULO
from listing_calendar import STYLE
from question_sync import STATUSES,FRESH_SECONDS

LIMIT=1000
SEARCH_LIMIT=200
COMMON_MARKS=re.compile(r'[\u0300-\u036f]')
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


def actionable(row,now,seller_id):
    return (verified_status(row,now,seller_id) and row.get('status')=='UNANSWERED'
            and row.get('excluida_do_anuncio') is False and row.get('em_espera') is False)


def waiting_seconds(row,now):
    """Elapsed time since an aware creation date; invalid/future dates stay unknown."""
    value=row.get('data')
    if not isinstance(value,str):return None
    try:
        created=datetime.fromisoformat(value.replace('Z','+00:00'))
        if created.tzinfo is None:return None
        seconds=now-created.timestamp()
        return int(seconds) if seconds>=0 else None
    except (ValueError,TypeError,OverflowError,OSError):return None


def waiting_label(seconds):
    if seconds is None:return 'Tempo de espera não verificado'
    if seconds<60:return 'Aguardando há menos de 1 min'
    days,rest=divmod(seconds,86400);hours,rest=divmod(rest,3600);minutes=rest//60
    parts=([str(days)+' d'] if days else [])+([str(hours)+' h'] if hours else [])
    if not days and minutes:parts.append(str(minutes)+' min')
    return 'Aguardando há '+' '.join(parts)


def search_text(value):
    """Literal text folding, preserving non-Latin text and punctuation."""
    if not isinstance(value,str):return ''
    value=COMMON_MARKS.sub('',unicodedata.normalize('NFKD',value.casefold()))
    if not value.isascii():value=''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(value.split())


def model(rows,args,now=None,seller_id=None):
    import time
    now=int(time.time()) if now is None else now
    limited=len(rows)>LIMIT;rows=rows[:LIMIT]
    selected=args.get('status','all')
    if selected not in ('all','UNANSWERED','ANSWERED','pending'):selected='all'
    search=args.get('q','')
    search=search if isinstance(search,str) else ''
    search_limited=len(search)>SEARCH_LIMIT
    search=search[:SEARCH_LIMIT].strip();needle=search_text(search)
    counts=Counter(r.get('status') for r in rows)
    verified=[r for r in rows if verified_status(r,now,seller_id)]
    recent=Counter(r.get('status') for r in verified)
    queue=[r for r in verified if actionable(r,now,seller_id)]
    pending=len(queue)
    if selected=='pending':
        # Known creation dates first, oldest first. Unknown dates remain visible at the end.
        filtered=sorted(queue,key=lambda r: (waiting_seconds(r,now) is None,-(waiting_seconds(r,now) or 0),str(r.get('pergunta_id',''))))
    else:filtered=[r for r in rows if selected=='all' or r.get('status')==selected]
    if search and not needle:filtered=[]
    elif needle:
        filtered=[r for r in filtered if needle in search_text(r.get('texto'))
                  or (r.get('resposta_status') not in ('BANNED','DISABLED') and needle in search_text(r.get('resposta')))]
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
    return dict(search=search,search_limited=search_limited,rows=filtered[(p-1)*10:p*10],recent=recent,pending=pending,unknown=len(rows)-len(verified),now=now,seller_id=seller_id,total=len(rows),filtered=len(filtered),counts=counts,limited=limited,
                status=selected,page=p,pages=pages,groups=repeated[(gp-1)*10:gp*10],group_total=len(repeated),group_page=gp,group_pages=gpages)


def render(cid,item,shop,data):
    esc=lambda x:escape(str(x),quote=True)
    path=f'/anuncios/{int(cid)}/{item}/perguntas'
    from section_refresh import render as render_refresh
    out=render_refresh(cid,'perguntas')+STYLE+'''<style>.lq-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.lq-cards article,.lq-row{background:#182e49;border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.lq-cards{margin:16px 0}.lq-cards article{display:grid;gap:8px;font-size:12px;margin:0}.lq-cards strong{font-size:24px}.lq-card-link{display:grid;gap:8px;height:100%}.lq-cards article:has(a):hover{border-color:#85c8ec}.listing-questions .lq-wait{font-weight:700;color:#b9e5ff}.listing-questions .lq-cards article:has(a){padding:0}.listing-questions .lq-card-link{padding:14px;box-sizing:border-box}@layer keiper-appearance{html[data-theme="light"] .listing-questions{background:#fff!important;color:#172c46!important;border-color:#c7d6e7!important}html[data-theme="light"] .listing-questions :is(h2,h3,strong){color:#172c46!important}html[data-theme="light"] .listing-questions :is(p,small){color:#405775!important}html[data-theme="light"] .listing-questions a{color:#175d98!important}html[data-theme="light"] .listing-questions :is(.lq-cards article,.lq-row){background:#f2f6fb!important;border-color:#c7d6e7!important}html[data-theme="light"] .listing-questions :is(select,input[type=search]){background:#fff!important;color:#172c46!important;color-scheme:light!important;border-color:#8aa5c3!important}html[data-theme="light"] .listing-questions :focus-visible{outline-color:#175d98!important}}.lq-search-form{display:grid;gap:12px;min-width:0}.lq-search-form input{width:100%;max-width:100%;min-width:0;box-sizing:border-box;padding:10px;border:1px solid #8aa5c3;border-radius:8px;font-size:16px}.lq-text{white-space:pre-wrap}@media(max-width:650px){.lq-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>'''
    out+='<section class="lc listing-questions"><h2>Perguntas e recorrências</h2><p>'+esc(shop.get('titulo') or item)+' · '+esc(item)+'</p><nav><a href="/anuncios/'+str(int(cid))+'/'+item+'/conteudo">Revisar conteúdo</a><a href="/anuncios/'+str(int(cid))+'/'+item+'/tarefas">Planejar ajustes</a><a href="/anuncios/'+str(int(cid))+'/'+item+'/avaliacoes">Avaliações do produto</a></nav><p>Perguntas salvas e status conferidos nas coletas.</p>'
    if data['limited']:out+='<p role="status">Amostra limitada aos 1.000 registros com coleta mais recente deste anúncio. Cards e recorrências usam somente essa amostra.</p>'
    out+='<div class="lq-cards">'
    for n,label,key in [(data['total'],'Perguntas na base analisada','all'),(data['pending'],'Aguardando resposta · consulta recente','pending'),(data['recent'].get('ANSWERED',0),'Respondidas · consulta recente',None),(data['unknown'],'Sem verificação recente',None)]:
        content='<strong>'+str(n)+'</strong><span>'+label+'</span>'
        if key is not None:content='<a class="lq-card-link" href="'+esc(path+'?'+urlencode(dict(status=key))+'#perguntas')+'">'+content+'</a>'
        out+='<article>'+content+'</article>'
    out+='</div>'
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
                if data['search']:params['q']=data['search']
                text+=' <a href="'+esc(path+'?'+urlencode(params)+'#'+anchor)+'">'+label+'</a>'
        return text+'</nav>'
    out+='<section id="recorrencias"><h3>Textos repetidos</h3><p>'+str(data['group_total'])+' grupos de textos iguais na base analisada, considerando todos os status salvos.</p>'
    for group in data['groups']:out+='<article class="lq-row"><strong>'+str(group['n'])+' ocorrências · '+str(group['pending'])+' sem resposta registrada</strong><p class="lq-text">'+esc(group['text'])+'</p></article>'
    if not data['groups']:out+='<p>Nenhum texto repetido identificado nesta base.</p>'
    out+=pages(data['group_page'],data['group_pages'],'recorrencias','recorrencias')+'</section><section id="perguntas"><h3>'+('Aguardando resposta' if data['status']=='pending' else 'Perguntas salvas')+'</h3><form method="get" class="lq-search-form"><label>Exibir perguntas<select name="status">'+''.join('<option value="'+s+'"'+(' selected' if data['status']==s else '')+'>'+label+'</option>' for s,label in [('all','Todos'),('pending','Aguardando resposta · consulta recente'),('UNANSWERED','Sem resposta no registro'),('ANSWERED','Respondidas no registro')])+'</select></label><label>Buscar na pergunta ou resposta<input type="search" name="q" maxlength="200" value="'+esc(data['search'])+'" placeholder="Ex.: voltagem"></label><button>Filtrar</button></form><p>'+str(data['filtered'])+' perguntas neste filtro. '+('Mais antigas primeiro pela data da pergunta; datas não verificáveis no final.' if data['status']=='pending' else 'Ordenação por coleta mais recente; datas em Brasília.')+'</p>'
    out+='<p>A busca procura um trecho, ignorando acentos, maiúsculas e espaços repetidos, somente nos textos disponíveis desta amostra. Cards e textos repetidos continuam mostrando a amostra inteira.</p>'
    if data['search']:
        out+='<p>Busca: <strong>'+esc(data['search'])+'</strong> · <a href="'+esc(path+'?'+urlencode(dict(status=data['status']))+'#perguntas')+'">Limpar busca</a></p>'
    if data['search_limited']:out+='<p role="status">Busca limitada aos primeiros 200 caracteres.</p>'
    if data['status']=='pending':out+='<p>A fila usa a amostra local e status consultados nas últimas seis horas. Tempo de espera desde a criação da pergunta, até a abertura desta página.</p>'
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
        wait='<p class="lq-wait">'+waiting_label(waiting_seconds(row,data['now']))+'</p>' if actionable(row,data['now'],data.get('seller_id')) else ''
        draft='';qid=str(row.get('pergunta_id',''));question=row.get('texto')
        if re.fullmatch(r'[1-9][0-9]{0,19}',qid) and isinstance(question,str) and question.strip() and len(question)<=20000 and '\x00' not in question:
            url='/anuncios/'+str(int(cid))+'/'+item+'/tarefas?'+urlencode(dict(pergunta=qid))+'#lt-criar'
            draft='<p><a href="'+esc(url)+'" aria-label="Planejar ajuste da pergunta #'+qid+'">Planejar ajuste desta pergunta</a></p>'
        out+='<article class="lq-row"><strong>Pergunta #'+esc(row.get('pergunta_id',''))+'</strong>'+wait+'<p>'+stamp(row.get('data'))+' · '+evidence+' · '+esc(STATUS_LABELS.get(row.get('status'),row.get('status') or 'não informado'))+' · coleta '+collected+'</p><p>'+esc(visibility)+'</p><p class="lq-text">'+esc(row.get('texto') or 'Texto não disponível')+'</p><p class="lq-text">Resposta registrada: '+esc('não disponível · '+str(row['resposta_status']) if row.get('resposta_status') in ('BANNED','DISABLED') else row.get('resposta') or 'não disponível')+'</p>'+draft+'</article>'
    if not data['rows']:out+='<p>'+('Nenhuma pergunta encontrada para este trecho e filtro na amostra disponível. Isso não comprova ausência de dúvidas.' if data['search'] else 'Nenhuma pergunta aguardando resposta confirmada nesta amostra. Atualize Perguntas para conferir o status.' if data['status']=='pending' else 'Nenhuma pergunta salva neste filtro. Ausência de registros não comprova ausência de dúvidas.')+'</p>'
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
