"""Persist evaluations from scheduled sync, without retroactive reconstruction."""
from datetime import datetime
from sales_metrics import SAO_PAULO
from listing_goals import evaluate

LABELS={'alert':'Abaixo do mínimo','met':'Atende ao mínimo observado','unknown':'Não verificado'}


def init_schema(conn,execute):
    execute(conn,'SELECT pg_advisory_xact_lock(186144284)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_goal_observations(
        id BIGSERIAL PRIMARY KEY,goal_id BIGINT NOT NULL REFERENCES listing_stock_goals(id),
        conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,evaluated_at BIGINT NOT NULL,
        source_at BIGINT,stock BIGINT,state TEXT NOT NULL CHECK(state IN ('alert','met','unknown')),
        CHECK((state='unknown' AND stock IS NULL) OR (state IN ('alert','met') AND stock>=0)),
        UNIQUE(goal_id,evaluated_at))''')
    execute(conn,'CREATE INDEX IF NOT EXISTS listing_goal_observations_scope ON listing_goal_observations(conexao_id,item_id,goal_id,id DESC)')


def collect(cid,bank,query,execute,now):
    day=datetime.fromtimestamp(now,SAO_PAULO).date();last=0
    while True:
        with bank() as conn:
            rows=query(conn,'''SELECT g.*,a.quantidade,a.atualizado_em FROM listing_stock_goals g
                LEFT JOIN anuncios a ON a.conexao_id=g.conexao_id AND a.item_id=g.item_id
                WHERE g.conexao_id=%s AND g.id>%s AND g.cancelled_at IS NULL
                AND g.start_date<=%s AND g.end_date>=%s AND g.created_at<=%s ORDER BY g.id LIMIT 200''',(cid,last,day,day,now))
            for row in rows:
                state,_,stock=evaluate(row,row,day,now)
                stamp=row.get('atualizado_em')
                source=stamp if type(stamp) is int and 0<stamp<=now else None
                execute(conn,'''INSERT INTO listing_goal_observations(goal_id,conexao_id,item_id,evaluated_at,source_at,stock,state)
                    SELECT id,conexao_id,item_id,%s,%s,%s,%s FROM listing_stock_goals
                    WHERE id=%s AND conexao_id=%s AND item_id=%s AND cancelled_at IS NULL
                    AND start_date<=%s AND end_date>=%s AND created_at<=%s
                    ON CONFLICT(goal_id,evaluated_at) DO NOTHING''',
                    (now,source,stock,state,row['id'],cid,row['item_id'],day,day,now))
        if len(rows)<200:return True
        last=rows[-1]['id']


def load(conn,query,cid,item,gid,args):
    goals=query(conn,'SELECT * FROM listing_stock_goals WHERE id=%s AND conexao_id=%s AND item_id=%s',(gid,cid,item))
    if not goals:raise LookupError('Meta não encontrada neste anúncio.')
    n=query(conn,'SELECT COUNT(*) AS n FROM listing_goal_observations WHERE goal_id=%s AND conexao_id=%s AND item_id=%s',(gid,cid,item))[0]['n'];pages=max(1,(n+9)//10)
    try:p=max(1,min(pages,int(args.get('pagina','1'))))
    except (TypeError,ValueError):p=1
    rows=query(conn,'''SELECT * FROM listing_goal_observations WHERE goal_id=%s AND conexao_id=%s AND item_id=%s
        ORDER BY id DESC LIMIT 10 OFFSET %s''',(gid,cid,item,(p-1)*10))
    return dict(goal=goals[0],rows=rows,total=n,page=p,pages=pages)


def render(cid,item,data):
    from html import escape
    from listing_calendar import STYLE
    esc=lambda v:escape(str(v),quote=True);goal=data['goal'];path=f'/anuncios/{int(cid)}/{item}/metas'
    def stamp(value):return datetime.fromtimestamp(value,SAO_PAULO).strftime('%d/%m/%Y %H:%M:%S') if value is not None else 'não verificada'
    out=STYLE+'<section class="lc goal-history"><h2>Histórico das avaliações de estoque</h2><a href="'+path+'">Voltar às metas</a><p>'+esc(item)+' · mínimo de '+str(goal['minimum'])+' unidades · responsável '+esc(goal['responsible'])+'</p><p>Período: '+goal['start_date'].strftime('%d/%m/%Y')+' a '+goal['end_date'].strftime('%d/%m/%Y')+'. Datas em Brasília.</p><p>Avaliações gravadas pelas sincronizações a partir desta funcionalidade. Não há reconstrução retroativa, garantia de coletas contínuas. Avisos por e-mail exigem ativação na meta. Abrir a tela não grava avaliação. Resultado confirmado exige estoque inteiro e leitura com até seis horas; não verificado não significa estoque zero.</p><p>'+str(data['total'])+' avaliações registradas.</p>'
    for row in data['rows']:
        out+='<article style="background:#182e49;border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere"><strong>'+LABELS[row['state']]+'</strong><p>Avaliado em '+stamp(row['evaluated_at'])+' · leitura: '+stamp(row['source_at'])+'</p><p>Estoque observado: '+(str(row['stock']) if row['stock'] is not None else 'não verificado')+'</p></article>'
    if not data['rows']:out+='<p>Nenhuma avaliação registrada. A próxima sincronização elegível poderá iniciar o histórico; ausência de registro não comprova meta atendida.</p>'
    out+='<nav aria-label="Paginação das avaliações">Página '+str(data['page'])+' de '+str(data['pages'])
    for label,p in [('Anterior',data['page']-1),('Próxima',data['page']+1)]:
        if 1<=p<=data['pages']:out+=' <a href="'+path+'/historico/'+str(goal['id'])+'?pagina='+str(p)+'">'+label+'</a>'
    return out+'</nav></section>'


def register_history(app,login_required,can_view,bank,query,execute,shop_page):
    from flask import session,request
    import re
    @app.route('/anuncios/<int:cid>/<item_id>/metas/historico/<int:goal_id>',methods=['GET'])
    @login_required
    def listing_goal_history(cid,item_id,goal_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id) or not 0<goal_id<2**63:return 'Meta não encontrada',404
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            shops=query(conn,'SELECT cliente FROM conexoes WHERE id=%s',(cid,))
            if not shops:return 'Loja não encontrada',404
            try:data=load(conn,query,cid,item_id,goal_id,request.args)
            except LookupError:return 'Meta não encontrada neste anúncio.',404
        return shop_page('Histórico da meta',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,data))
