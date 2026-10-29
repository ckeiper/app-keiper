"""Administrator sales goals evaluated against verified closed days only."""
from datetime import date,timedelta
import re
import time
from decimal import Decimal, InvalidOperation
from profitability_store import load_sales


def init_schema(conn,execute):
    execute(conn,'SELECT pg_advisory_xact_lock(186144301)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_sales_goals(
        id BIGSERIAL PRIMARY KEY,conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,
        metric TEXT NOT NULL CHECK(metric IN ('orders','units','gross_items')),
        target NUMERIC(18,2) NOT NULL CHECK(target>0 AND target<=1000000000),
        start_date DATE NOT NULL,end_date DATE NOT NULL CHECK(end_date>=start_date),
        responsible TEXT NOT NULL CHECK(char_length(responsible) BETWEEN 1 AND 80),
        created_at BIGINT NOT NULL,created_by INTEGER NOT NULL,
        cancelled_at BIGINT,cancelled_by INTEGER,submission_key VARCHAR(64) NOT NULL,
        UNIQUE(conexao_id,item_id,submission_key))''')
    execute(conn,'CREATE INDEX IF NOT EXISTS listing_sales_goals_scope ON listing_sales_goals(conexao_id,item_id,id DESC)')


def validate(form,today):
    metric=form.get('metric')
    if metric not in ('orders','units','gross_items'):raise ValueError('Selecione a métrica.')
    raw=str(form.get('target','')).strip().replace(',','.')
    try:
        if not re.fullmatch(r'[0-9]{1,10}(?:\.[0-9]{1,2})?',raw):raise ValueError
        target=Decimal(raw)
        if not 0<target<=1000000000 or (metric!='gross_items' and target!=target.to_integral_value()):raise ValueError
        start=date.fromisoformat(form.get('start_date',''));end=date.fromisoformat(form.get('end_date',''))
    except (ValueError,TypeError,InvalidOperation):raise ValueError('Informe uma meta positiva, inteira para pedidos e unidades, e datas válidas.') from None
    if not today-timedelta(days=90)<=start<=today+timedelta(days=90) or not start<=end<=start+timedelta(days=89):raise ValueError('Início: até 90 dias antes ou depois de hoje. Período: de 1 a 90 dias.')
    owner=str(form.get('responsible','')).strip();key=str(form.get('submission_key',''))
    if not 1<=len(owner)<=80 or '\x00' in owner:raise ValueError('Informe o responsável, com até 80 caracteres.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',key):raise ValueError('Recarregue o formulário.')
    return dict(metric=metric,target=target,start_date=start,end_date=end,responsible=owner,submission_key=key)


def create(conn,query,cid,item,values,actor):
    rows=query(conn,'''INSERT INTO listing_sales_goals(conexao_id,item_id,metric,target,start_date,end_date,responsible,created_at,created_by,submission_key)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(conexao_id,item_id,submission_key) DO NOTHING RETURNING id''',
        (cid,item,values['metric'],values['target'],values['start_date'],values['end_date'],values['responsible'],int(time.time()),actor,values['submission_key']))
    if rows:return rows[0]['id']
    old=query(conn,'SELECT * FROM listing_sales_goals WHERE conexao_id=%s AND item_id=%s AND submission_key=%s',(cid,item,values['submission_key']))
    if not old or any(old[0][k]!=values[k] for k in ('metric','target','start_date','end_date','responsible')):raise ValueError('Formulário já utilizado com outros dados. Recarregue a página.')
    return old[0]['id']


def cancel(conn,query,cid,item,goal_id,actor):
    try:gid=int(goal_id)
    except (ValueError,TypeError):raise ValueError('Meta inválida.') from None
    if not 0<gid<2**63:raise ValueError('Meta inválida.')
    rows=query(conn,'''UPDATE listing_sales_goals SET cancelled_at=%s,cancelled_by=%s
        WHERE id=%s AND conexao_id=%s AND item_id=%s AND cancelled_at IS NULL RETURNING id''',(int(time.time()),actor,gid,cid,item))
    if not rows and not query(conn,'SELECT id FROM listing_sales_goals WHERE id=%s AND conexao_id=%s AND item_id=%s',(gid,cid,item)):raise LookupError('Meta não encontrada neste anúncio.')


def load(conn,query,cid,item,args):
    n=query(conn,'SELECT COUNT(*) AS n FROM listing_sales_goals WHERE conexao_id=%s AND item_id=%s',(cid,item))[0]['n'];pages=max(1,(n+9)//10)
    try:p=max(1,min(pages,int(args.get('pagina','1'))))
    except (TypeError,ValueError):p=1
    rows=query(conn,'SELECT * FROM listing_sales_goals WHERE conexao_id=%s AND item_id=%s ORDER BY id DESC LIMIT 10 OFFSET %s',(cid,item,(p-1)*10))
    return dict(rows=rows,page=p,pages=pages,total=n)


def evaluate(goal,summary,today):
    cutoff=min(goal['end_date'],today-timedelta(days=1))
    if goal.get('cancelled_at') is not None:return ('cancelled','Cancelada · registro preservado',None,cutoff)
    if today<goal['start_date']:return ('scheduled','Programada',None,cutoff)
    if cutoff<goal['start_date']:return ('waiting','Aguardando primeiro dia completo',None,cutoff)
    value=summary.get(goal['metric']) if summary else None
    if value is None:return ('unknown','Resultado não verificado · cobertura incompleta',None,cutoff)
    try:value=Decimal(str(value))
    except InvalidOperation:return ('unknown','Resultado inválido',None,cutoff)
    if not value.is_finite() or value<0:return ('unknown','Resultado inválido',None,cutoff)
    if value>=goal['target']:return ('met','Meta atingida na base verificada',value,cutoff)
    if today>goal['end_date']:return ('alert','Prazo encerrado · meta não atingida',value,cutoff)
    return ('progress','Em andamento · período ainda aberto',value,cutoff)


def evaluate_current(conn,query,cid,item,goal,today):
    cutoff=min(goal['end_date'],today-timedelta(days=1))
    summary={}
    if goal.get('cancelled_at') is None and cutoff>=goal['start_date']:
        summary=load_sales(conn,query,cid,item,goal['start_date'],cutoff)
    return evaluate(goal,summary,today)
