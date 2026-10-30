"""Administrator stock thresholds. No forecast or automatic marketplace writes."""
from datetime import date,timedelta
import re
import time
from listing_priority_sources import listing_signals


def init_schema(conn,execute):
    execute(conn,'SELECT pg_advisory_xact_lock(186144281)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_stock_goals(
        id BIGSERIAL PRIMARY KEY,conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,
        minimum INTEGER NOT NULL CHECK(minimum BETWEEN 0 AND 1000000),
        start_date DATE NOT NULL,end_date DATE NOT NULL CHECK(end_date>=start_date),
        responsible TEXT NOT NULL CHECK(char_length(responsible) BETWEEN 1 AND 80),
        created_at BIGINT NOT NULL,created_by INTEGER NOT NULL,
        cancelled_at BIGINT,cancelled_by INTEGER,submission_key VARCHAR(64) NOT NULL,
        UNIQUE(conexao_id,item_id,submission_key))''')
    execute(conn,'CREATE INDEX IF NOT EXISTS listing_stock_goals_scope ON listing_stock_goals(conexao_id,item_id,id DESC)')


def validate(form,today):
    try:
        raw=str(form.get('minimum',''))
        if not re.fullmatch(r'[0-9]{1,7}',raw):raise ValueError
        n=int(raw);start=date.fromisoformat(form.get('start_date',''));end=date.fromisoformat(form.get('end_date',''))
    except (ValueError,TypeError):raise ValueError('Informe estoque mínimo inteiro e datas válidas.') from None
    if not 0<=n<=1000000:raise ValueError('O estoque mínimo deve estar entre zero e um milhão.')
    if not today-timedelta(days=90)<=start<=today+timedelta(days=90) or not start<=end<=start+timedelta(days=89):raise ValueError('Início: até 90 dias antes ou depois de hoje. Período: de 1 a 90 dias.')
    owner=str(form.get('responsible','')).strip();key=str(form.get('submission_key',''))
    if not 1<=len(owner)<=80 or '\x00' in owner:raise ValueError('Informe o responsável, com até 80 caracteres.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',key):raise ValueError('Recarregue o formulário.')
    return dict(minimum=n,start_date=start,end_date=end,responsible=owner,submission_key=key)


def create(conn,query,cid,item,values,actor):
    rows=query(conn,'''INSERT INTO listing_stock_goals(conexao_id,item_id,minimum,start_date,end_date,responsible,created_at,created_by,submission_key)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(conexao_id,item_id,submission_key) DO NOTHING RETURNING id''',
        (cid,item,values['minimum'],values['start_date'],values['end_date'],values['responsible'],int(time.time()),actor,values['submission_key']))
    if rows:return rows[0]['id']
    old=query(conn,'SELECT * FROM listing_stock_goals WHERE conexao_id=%s AND item_id=%s AND submission_key=%s',(cid,item,values['submission_key']))
    if not old or any(old[0][k]!=values[k] for k in ('minimum','start_date','end_date','responsible')):raise ValueError('Formulário já utilizado com outros dados. Recarregue a página.')
    return old[0]['id']


def cancel(conn,query,cid,item,goal_id,actor):
    try:gid=int(goal_id)
    except (ValueError,TypeError):raise ValueError('Meta inválida.') from None
    if not 0<gid<2**63:raise ValueError('Meta inválida.')
    rows=query(conn,'''UPDATE listing_stock_goals SET cancelled_at=%s,cancelled_by=%s
        WHERE id=%s AND conexao_id=%s AND item_id=%s AND cancelled_at IS NULL RETURNING id''',(int(time.time()),actor,gid,cid,item))
    if not rows and not query(conn,'SELECT id FROM listing_stock_goals WHERE id=%s AND conexao_id=%s AND item_id=%s',(gid,cid,item)):raise LookupError('Meta não encontrada neste anúncio.')


def load(conn,query,cid,item,args):
    n=query(conn,'SELECT COUNT(*) AS n FROM listing_stock_goals WHERE conexao_id=%s AND item_id=%s',(cid,item))[0]['n'];pages=max(1,(n+9)//10)
    try:p=max(1,min(pages,int(args.get('pagina','1'))))
    except (TypeError,ValueError):p=1
    rows=query(conn,'SELECT * FROM listing_stock_goals WHERE conexao_id=%s AND item_id=%s ORDER BY id DESC LIMIT 10 OFFSET %s',(cid,item,(p-1)*10))
    return dict(rows=rows,page=p,pages=pages,total=n)


def evaluate(goal,listing,today,now):
    if goal.get('cancelled_at') is not None:return ('cancelled','Cancelada · registro preservado',None)
    if today<goal['start_date']:return ('scheduled','Programada · período ainda não iniciado',None)
    if today>goal['end_date']:return ('ended','Encerrada · resultado histórico não verificado',None)
    signal=listing_signals([listing],{},1,now=now)[listing['item_id']]
    if not signal['stock_verified']:return ('unknown','Estoque não verificado · leitura ausente, inválida ou com mais de seis horas',None)
    stock=int(signal['stock'])
    return ('alert','Alerta · estoque observado abaixo do mínimo',stock) if stock<goal['minimum'] else ('met','Leitura atual atende ao mínimo · não garante cobertura futura',stock)
