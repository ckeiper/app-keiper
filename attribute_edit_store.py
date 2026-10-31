"""Durable plans and append-only events; advisory scope lock spans commits/HTTP."""
from contextlib import contextmanager
from uuid import uuid4
import time
from psycopg2.extras import Json


def init_schema(conn,execute):
    execute(conn,'SELECT pg_advisory_xact_lock(186144291)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_attribute_plans (
        id UUID PRIMARY KEY,conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,created_by INTEGER NOT NULL,
        analysis_key VARCHAR(64) NOT NULL,created_at BIGINT NOT NULL,updated_at BIGINT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('reading','ready','sending','confirmed','uncertain','rejected','stale','closed')),
        data JSONB NOT NULL DEFAULT '{}',selected JSONB NOT NULL DEFAULT '[]',result JSONB NOT NULL DEFAULT '{}',
        UNIQUE(conexao_id,item_id,created_by,analysis_key))''')
    execute(conn,'''CREATE UNIQUE INDEX IF NOT EXISTS listing_attribute_active_write
        ON listing_attribute_plans(item_id) WHERE state IN ('sending','uncertain')''')
    execute(conn,'''CREATE INDEX IF NOT EXISTS listing_attribute_history
        ON listing_attribute_plans(conexao_id,item_id,created_by,created_at DESC)''')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_attribute_events (
        id BIGSERIAL PRIMARY KEY,plan_id UUID NOT NULL REFERENCES listing_attribute_plans(id),
        created_at BIGINT NOT NULL,created_by INTEGER NOT NULL,state TEXT NOT NULL,details JSONB NOT NULL)''')


@contextmanager
def locked(bank,query,cid,item):
    conn=bank()
    try:
        conn.cursor().execute("SET statement_timeout='5000ms'")
        rows=query(conn,'SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS locked',(f'attribute-edit:{item}',))
        conn.commit()
        if not rows or rows[0]['locked'] is not True:raise ValueError('Há uma análise ou envio em andamento para este anúncio.')
        yield conn
    finally:
        # Dedicated connection, never pooled. Closing releases the session lock,
        # including when a transaction or network operation failed.
        conn.close()


def load(conn,query,cid,item,actor,plan):
    rows=query(conn,'SELECT * FROM listing_attribute_plans WHERE id=%s AND conexao_id=%s AND item_id=%s AND created_by=%s',(plan,cid,item,actor))
    if not rows:raise ValueError('Análise não encontrada nesta loja e sessão.')
    return rows[0]


def create(conn,query,cid,item,actor,key):
    identifier=str(uuid4());now=int(time.time())
    rows=query(conn,'''INSERT INTO listing_attribute_plans(id,conexao_id,item_id,created_by,analysis_key,created_at,updated_at,state)
        VALUES(%s,%s,%s,%s,%s,%s,%s,'reading') ON CONFLICT(conexao_id,item_id,created_by,analysis_key) DO NOTHING RETURNING *''',(identifier,cid,item,actor,key,now,now))
    if not rows:rows=query(conn,'SELECT * FROM listing_attribute_plans WHERE conexao_id=%s AND item_id=%s AND created_by=%s AND analysis_key=%s',(cid,item,actor,key))
    conn.commit();return rows[0],str(rows[0]['id'])==identifier


def transition(conn,query,plan,actor,state,result=None,data=None,selected=None):
    fields=['state=%s','updated_at=%s','result=%s'];params=[state,int(time.time()),Json(result or {})]
    if data is not None:fields.append('data=%s');params.append(Json(data))
    if selected is not None:fields.append('selected=%s');params.append(Json(selected))
    params.append(str(plan['id']))
    query(conn,'UPDATE listing_attribute_plans SET '+','.join(fields)+' WHERE id=%s RETURNING id',tuple(params))
    query(conn,'''INSERT INTO listing_attribute_events(plan_id,created_at,created_by,state,details)
        VALUES(%s,%s,%s,%s,%s) RETURNING id''',(str(plan['id']),int(time.time()),actor,state,Json(dict(result or {},selected=selected) if selected is not None else result or {})))
    conn.commit()


def active(conn,query,cid,item):
    return query(conn,"SELECT id,conexao_id FROM listing_attribute_plans WHERE item_id=%s AND state IN ('sending','uncertain')",(item,))
