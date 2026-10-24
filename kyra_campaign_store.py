"""Bounded daily campaign analysis; shares PostgreSQL/scheduler with KYRA.

Separate daily records allow rollout without rerunning store analyses or LLMs.
"""
import json
import os
import time
from contextlib import closing
from datetime import datetime, timedelta

from kyra_campaigns import analyze, MAX_CAMPAIGNS, MAX_DAILY_ROWS
from sales_metrics import SAO_PAULO


def init_schema(conn, execute):
    execute(conn, '''CREATE TABLE IF NOT EXISTS keiper_ai_campaign_runs (
        id BIGSERIAL PRIMARY KEY,
        conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        day DATE NOT NULL, status TEXT NOT NULL DEFAULT 'running', result JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ,
        UNIQUE(conexao_id,day))''')


def run_one(banco, query, execute, logger, now=None):
    if os.getenv('KEIPER_AI_DAILY_ENABLED','true')!='true' or os.getenv('KEIPER_AI_CAMPAIGNS_ENABLED','true')!='true':
        return
    now = time.time() if now is None else now
    local = datetime.fromtimestamp(now, SAO_PAULO)
    if local.hour<8:
        return
    today = local.date()
    # Same shared session lock as the store analyzer: no parallel scans.
    with closing(banco()) as lock:
        lock.autocommit = True
        if not query(lock,'SELECT pg_try_advisory_lock(880145) AS acquired')[0]['acquired']:
            return
        with closing(banco()) as conn, conn:
            shops = query(conn, '''SELECT c.id FROM conexoes c WHERE c.status='ativa'
                AND NOT EXISTS(SELECT 1 FROM keiper_ai_campaign_runs r
                    WHERE r.conexao_id=c.id AND r.day=%s)
                ORDER BY c.id LIMIT 1''', (today,))
            if not shops:
                return
            cid = shops[0]['id']
            runs = query(conn, '''INSERT INTO keiper_ai_campaign_runs(conexao_id,day)
                VALUES(%s,%s) ON CONFLICT(conexao_id,day) DO NOTHING RETURNING id''', (cid,today))
            if not runs:
                return
            run_id = runs[0]['id']
        try:
            with closing(banco()) as conn, conn:
                conn.set_session(isolation_level='REPEATABLE READ',readonly=True)
                execute(conn,"SET LOCAL statement_timeout='15s'")
                campaigns = query(conn, '''SELECT campanha_id,nome,status,orcamento,roas_objetivo,atualizado_em
                    FROM ads_campanhas WHERE conexao_id=%s ORDER BY campanha_id LIMIT %s''',
                    (cid,MAX_CAMPAIGNS+1))
                end = today-timedelta(days=1)
                rows = query(conn, '''SELECT campanha_id,data,gasto,faturamento,atualizado_em,
                    vendas_atribuidas,faturamento_sem_ads,metricas_vendas_coletadas_em
                    FROM ads_campanha_dia WHERE conexao_id=%s AND data BETWEEN %s AND %s
                    ORDER BY campanha_id,data LIMIT %s''',
                    (cid,(end-timedelta(days=13)).isoformat(),end.isoformat(),MAX_DAILY_ROWS+1))
            limited = len(campaigns)>MAX_CAMPAIGNS or len(rows)>MAX_DAILY_ROWS
            result = analyze(campaigns[:MAX_CAMPAIGNS],rows[:MAX_DAILY_ROWS],today,now,limited)
            with closing(banco()) as conn, conn:
                execute(conn, '''UPDATE keiper_ai_campaign_runs SET status='completed',result=%s::jsonb,
                    finished_at=now() WHERE id=%s''', (json.dumps(result),run_id))
        except Exception:
            with closing(banco()) as conn, conn:
                execute(conn,"UPDATE keiper_ai_campaign_runs SET status='failed',finished_at=now() WHERE id=%s",(run_id,))
            logger.warning('kyra_campaign_daily_failed run_id=%s',run_id)
