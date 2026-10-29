"""Opt-in goal e-mail, with persisted claims and no automatic retry of uncertain sends."""
import os
import re
import smtplib
import ssl
from email.mime.text import MIMEText
from datetime import datetime,timedelta
from sales_metrics import SAO_PAULO

SOURCES={
    'stock':('listing_stock_goals','listing_goal_observations'),
    'sales':('listing_sales_goals','listing_sales_goal_observations'),
}


def email_valid(value):
    return isinstance(value,str) and len(value)<=254 and bool(re.fullmatch(r'[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}',value))


def configured():
    return bool(os.getenv('SMTP_HOST') and os.getenv('SMTP_USER') and os.getenv('SMTP_PASS'))


def send_smtp(address,subject,body):
    if not configured() or not email_valid(address):return False
    try:
        sender=os.getenv('SMTP_FROM',os.environ['SMTP_USER'])
        msg=MIMEText(body,'plain','utf-8');msg['Subject']=subject;msg['From']=sender;msg['To']=address
        with smtplib.SMTP(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','587')),timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context());smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASS'])
            return not smtp.sendmail(sender,[address],msg.as_string())
    except Exception:
        # SMTP failure after DATA may mean acceptance: never retry this claim.
        return False


def init_schema(conn,execute):
    execute(conn,'SELECT pg_advisory_xact_lock(186144303)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_goal_subscriptions(
        id BIGSERIAL PRIMARY KEY,kind TEXT NOT NULL CHECK(kind IN ('stock','sales')),
        goal_id BIGINT NOT NULL,conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,email TEXT NOT NULL,enabled BOOLEAN NOT NULL DEFAULT FALSE,
        enabled_at BIGINT NOT NULL,updated_at BIGINT NOT NULL,
        UNIQUE(kind,goal_id,user_id))''')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_goal_notifications(
        id BIGSERIAL PRIMARY KEY,subscription_id BIGINT NOT NULL REFERENCES listing_goal_subscriptions(id),
        notification_day DATE NOT NULL,observation_id BIGINT NOT NULL,
        attempted_at BIGINT NOT NULL,finished_at BIGINT,
        state TEXT NOT NULL CHECK(state IN ('sending','accepted','uncertain')),
        UNIQUE(subscription_id,notification_day))''')
    execute(conn,"CREATE INDEX IF NOT EXISTS listing_goal_subscriptions_enabled ON listing_goal_subscriptions(kind,id) WHERE enabled=TRUE")
    execute(conn,'CREATE INDEX IF NOT EXISTS listing_goal_subscriptions_scope ON listing_goal_subscriptions(conexao_id,item_id,user_id)')
    execute(conn,'CREATE INDEX IF NOT EXISTS listing_goal_notifications_history ON listing_goal_notifications(subscription_id,id DESC)')


def parent(conn,query,cid,item,kind,gid):
    if kind not in SOURCES or not 0<gid<2**63:raise LookupError('Meta não encontrada.')
    table=SOURCES[kind][0] # Constant allowlist, never user-supplied SQL.
    rows=query(conn,'SELECT * FROM '+table+' WHERE id=%s AND conexao_id=%s AND item_id=%s',(gid,cid,item))
    if not rows:raise LookupError('Meta não encontrada neste anúncio.')
    return rows[0]


def preference(conn,query,cid,item,kind,gid,uid):
    rows=query(conn,'''SELECT * FROM listing_goal_subscriptions WHERE kind=%s AND goal_id=%s
        AND conexao_id=%s AND item_id=%s AND user_id=%s''',(kind,gid,cid,item,uid))
    return rows[0] if rows else None


def save(conn,query,cid,item,kind,gid,uid,form,now):
    goal=parent(conn,query,cid,item,kind,gid)
    rows=query(conn,"SELECT email FROM usuarios WHERE id=%s AND tipo='admin'",(uid,))
    email=rows[0]['email'] if rows else None
    enabled=form.get('enabled')=='yes'
    if enabled:
        if goal.get('cancelled_at') is not None:raise ValueError('Meta cancelada. Os avisos não podem ser ativados.')
        if not email_valid(email):raise ValueError('Cadastre um e-mail válido na sua conta administrativa.')
        if form.get('confirmed_email')!=email:raise ValueError('O e-mail da conta mudou. Recarregue e confira o destinatário.')
        query(conn,'''INSERT INTO listing_goal_subscriptions(kind,goal_id,conexao_id,item_id,user_id,email,enabled,enabled_at,updated_at)
            VALUES(%s,%s,%s,%s,%s,%s,TRUE,%s,%s)
            ON CONFLICT(kind,goal_id,user_id) DO UPDATE SET email=EXCLUDED.email,enabled=TRUE,
            enabled_at=EXCLUDED.enabled_at,updated_at=EXCLUDED.updated_at RETURNING id''',(kind,gid,cid,item,uid,email,now,now))
    else:
        query(conn,'''UPDATE listing_goal_subscriptions SET enabled=FALSE,updated_at=%s
            WHERE kind=%s AND goal_id=%s AND conexao_id=%s AND item_id=%s AND user_id=%s RETURNING id''',(now,kind,gid,cid,item,uid))


def claim(conn,query,kind,now,day):
    goals,observations=SOURCES[kind]
    if kind=='stock':
        extra='''AND g.start_date<=%s AND g.end_date>=%s AND o.source_at IS NOT NULL
            AND o.source_at BETWEEN %s AND %s AND o.stock IS NOT NULL
            AND EXISTS(SELECT 1 FROM anuncios a WHERE a.conexao_id=s.conexao_id AND a.item_id=s.item_id
                AND a.atualizado_em=o.source_at AND a.quantidade=o.stock)'''
        params=(day,day,now-21600,now)
        fields='o.stock AS observed,g.minimum AS target,o.source_at,o.evaluated_at'
    else:
        extra='''AND g.end_date<%s AND g.end_date>=%s AND o.cutoff=g.end_date AND o.value IS NOT NULL'''
        params=(day,day-timedelta(days=30))
        fields='o.value AS observed,g.target,g.metric,o.cutoff,o.evaluated_at'
    rows=query(conn,'''SELECT s.id AS subscription_id,s.email,s.item_id,o.id AS observation_id,'''+fields+'''
        FROM listing_goal_subscriptions s JOIN usuarios u ON u.id=s.user_id AND u.tipo='admin' AND u.email=s.email
        JOIN conexoes c ON c.id=s.conexao_id AND c.status='ativa'
        JOIN '''+goals+''' g ON g.id=s.goal_id AND g.conexao_id=s.conexao_id AND g.item_id=s.item_id
        JOIN LATERAL (SELECT * FROM '''+observations+''' z WHERE z.goal_id=g.id
            AND z.conexao_id=s.conexao_id AND z.item_id=s.item_id ORDER BY z.id DESC LIMIT 1) o ON TRUE
        WHERE s.kind=%s AND s.enabled=TRUE AND g.cancelled_at IS NULL AND o.state='alert'
        AND o.evaluated_at>s.enabled_at AND o.evaluated_at BETWEEN %s AND %s
        '''+extra+''' AND NOT EXISTS(SELECT 1 FROM listing_goal_notifications n
            WHERE n.subscription_id=s.id AND n.notification_day=%s)
        ORDER BY s.id LIMIT 1 FOR UPDATE OF s SKIP LOCKED''',(kind,now-86400,now,*params,day))
    if not rows:return None
    row=rows[0]
    if not email_valid(row['email']):return None
    inserted=query(conn,'''INSERT INTO listing_goal_notifications(subscription_id,notification_day,observation_id,attempted_at,state)
        VALUES(%s,%s,%s,%s,'sending') ON CONFLICT(subscription_id,notification_day) DO NOTHING RETURNING id''',
        (row['subscription_id'],day,row['observation_id'],now))
    if not inserted:return None
    return dict(row,notification_id=inserted[0]['id'],kind=kind)


def dispatch(bank,query,execute,now,sender=send_smtp,ready=configured):
    if not ready():return 0 # No configuration changes or real send during setup.
    day=datetime.fromtimestamp(now,SAO_PAULO).date();attempts=0
    with bank() as conn:
        execute(conn,"UPDATE listing_goal_notifications SET state='uncertain',finished_at=%s WHERE state='sending' AND attempted_at<%s",(now,now-600))
    for kind in SOURCES:
        for _ in range(2): # Bound SMTP time; at most four attempts per minute/job.
            with bank() as conn:row=claim(conn,query,kind,now,day)
            if row is None:break
            stamp=datetime.fromtimestamp(row['evaluated_at'],SAO_PAULO).strftime('%d/%m/%Y %H:%M:%S')
            if kind=='stock':
                body=f"Anúncio {row['item_id']}\nEstoque observado: {row['observed']} unidades. Mínimo: {row['target']}.\nLeitura de estoque até seis horas; não é previsão de ruptura."
            else:
                metric={'orders':'pedidos pagos','units':'unidades','gross_items':'valor bruto dos itens (R$)'}[row['metric']]
                body=f"Anúncio {row['item_id']}\nPrazo encerrado: {row['cutoff']}. Meta de {metric}: {row['target']}. Apurado: {row['observed']}.\nCobertura do período verificada; valor bruto não é lucro."
            body+=f"\nAvaliação registrada em {stamp} (Brasília). O estado pode ter mudado desde essa avaliação.\nVocê ativou este aviso no Dashboard Keiper. Para desativar, abra Avisos por e-mail nesta meta."
            try:accepted=sender(row['email'],'Keiper · alerta da meta do anúncio',body) is True
            except Exception:accepted=False
            with bank() as conn:
                execute(conn,"UPDATE listing_goal_notifications SET state=%s,finished_at=%s WHERE id=%s AND state='sending'",('accepted' if accepted else 'uncertain',now,row['notification_id']))
            attempts+=1
    return attempts
