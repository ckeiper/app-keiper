"""Append-only evaluations of saved sales goals during order synchronization."""
from datetime import datetime,timedelta
from sales_metrics import SAO_PAULO
from listing_sales_goals import evaluate
from profitability_store import load_sales

LABELS={'alert':'Prazo encerrado · meta não atingida','met':'Meta atingida na base verificada','unknown':'Resultado não verificado','progress':'Em andamento'}

def init_schema(conn,execute):
    execute(conn,'SELECT pg_advisory_xact_lock(186144302)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_sales_goal_observations(
        id BIGSERIAL PRIMARY KEY,goal_id BIGINT NOT NULL REFERENCES listing_sales_goals(id),
        conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,evaluated_at BIGINT NOT NULL,
        cutoff DATE NOT NULL,value NUMERIC(18,2),state TEXT NOT NULL CHECK(state IN ('alert','met','unknown','progress')),
        sales_fingerprint CHAR(64) NOT NULL,
        CHECK((state='unknown' AND value IS NULL) OR (state<>'unknown' AND value>=0)),
        UNIQUE(goal_id,evaluated_at))''')
    execute(conn,'CREATE INDEX IF NOT EXISTS listing_sales_goal_observations_scope ON listing_sales_goal_observations(conexao_id,item_id,goal_id,id DESC)')


def collect(cid,bank,query,execute,now):
    day=datetime.fromtimestamp(now,SAO_PAULO).date();yesterday=day-timedelta(days=1);last=0
    # Revisit ended goals for 30 days to capture recent order corrections.
    oldest=day-timedelta(days=30)
    while True:
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            rows=query(conn,'''SELECT * FROM listing_sales_goals WHERE conexao_id=%s AND id>%s
                AND cancelled_at IS NULL AND start_date<=%s AND end_date>=%s AND created_at<=%s
                ORDER BY id LIMIT 100''',(cid,last,yesterday,oldest,now))
            for goal in rows:
                cutoff=min(goal['end_date'],yesterday)
                summary=load_sales(conn,query,cid,goal['item_id'],goal['start_date'],cutoff)
                state,_,value,cutoff=evaluate(goal,summary,day)
                execute(conn,'''INSERT INTO listing_sales_goal_observations(goal_id,conexao_id,item_id,evaluated_at,cutoff,value,state,sales_fingerprint)
                    SELECT id,conexao_id,item_id,%s,%s,%s,%s,%s FROM listing_sales_goals
                    WHERE id=%s AND conexao_id=%s AND item_id=%s AND cancelled_at IS NULL
                    AND start_date<=%s AND end_date>=%s AND created_at<=%s
                    ON CONFLICT(goal_id,evaluated_at) DO NOTHING''',
                    (now,cutoff,value,state,summary['fingerprint'],goal['id'],cid,goal['item_id'],yesterday,oldest,now))
        if len(rows)<100:return True
        last=rows[-1]['id']


def load(conn,query,cid,item,gid,args):
    goals=query(conn,'SELECT * FROM listing_sales_goals WHERE id=%s AND conexao_id=%s AND item_id=%s',(gid,cid,item))
    if not goals:raise LookupError('Meta não encontrada neste anúncio.')
    n=query(conn,'SELECT COUNT(*) AS n FROM listing_sales_goal_observations WHERE goal_id=%s AND conexao_id=%s AND item_id=%s',(gid,cid,item))[0]['n'];pages=max(1,(n+9)//10)
    try:p=max(1,min(pages,int(args.get('pagina','1'))))
    except (TypeError,ValueError):p=1
    rows=query(conn,'''SELECT * FROM listing_sales_goal_observations WHERE goal_id=%s AND conexao_id=%s AND item_id=%s
        ORDER BY id DESC LIMIT 10 OFFSET %s''',(gid,cid,item,(p-1)*10))
    return dict(goal=goals[0],rows=rows,total=n,page=p,pages=pages)


def render(cid,item,data):
    from html import escape
    from listing_calendar import STYLE
    from listing_sales_goal_view import LABELS as METRICS
    esc=lambda v:escape(str(v),quote=True);g=data['goal'];path=f'/anuncios/{int(cid)}/{item}/metas-vendas'
    out=STYLE+'<section class="lc sales-goal-history"><h2>Histórico da meta de vendas</h2><a href="'+path+'">Voltar às metas</a><p>'+METRICS[g['metric']]+': '+esc(g['target'])+' · '+esc(g['responsible'])+'</p><p>'+esc(g['start_date'])+' a '+esc(g['end_date'])+'</p><p>Avaliações registradas nas sincronizações, usando dias completos de Brasília. Não há reconstrução retroativa ou garantia de coleta contínua. Metas encerradas são revisitadas por até 30 dias. Abrir esta tela não grava avaliações. Não verificado não significa zero; correções posteriores não apagam registros anteriores.</p><p>'+str(data['total'])+' avaliações.</p>'
    for row in data['rows']:
        stamp=datetime.fromtimestamp(row['evaluated_at'],SAO_PAULO).strftime('%d/%m/%Y %H:%M:%S')
        out+='<article style="border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere"><strong>'+LABELS[row['state']]+'</strong><p>Avaliado em '+stamp+' · dias completos até '+esc(row['cutoff'])+'</p><p>Apurado: '+(esc(row['value']) if row['value'] is not None else 'não verificado')+'</p></article>'
    if not data['rows']:out+='<p>Nenhuma avaliação registrada; aguarde uma sincronização elegível. Ausência de registro não comprova meta atingida.</p>'
    out+='<nav aria-label="Paginação">Página '+str(data['page'])+' de '+str(data['pages'])
    for label,p in [('Anterior',data['page']-1),('Próxima',data['page']+1)]:
        if 1<=p<=data['pages']:out+=' <a href="'+path+'/historico/'+str(g['id'])+'?pagina='+str(p)+'">'+label+'</a>'
    return out+'</nav></section>'


def register_history(app,login_required,can_view,bank,query,execute,shop_page):
    from flask import session,request
    import re
    @app.route('/anuncios/<int:cid>/<item_id>/metas-vendas/historico/<int:goal_id>',methods=['GET'])
    @login_required
    def listing_sales_goal_history(cid,item_id,goal_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id) or not 0<goal_id<2**63:return 'Meta não encontrada',404
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            shops=query(conn,'SELECT cliente FROM conexoes WHERE id=%s',(cid,))
            if not shops:return 'Loja não encontrada',404
            try:data=load(conn,query,cid,item_id,goal_id,request.args)
            except LookupError:return 'Meta não encontrada neste anúncio.',404
        return shop_page('Histórico da meta de vendas',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,data))
