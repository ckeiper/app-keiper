"""PostgreSQL persistence and bounded daily runner on existing infrastructure."""
import json
import os
import time
from contextlib import closing, contextmanager
from datetime import datetime, timedelta

from keiper_ai import recommendations
from keiper_ai_budget import interpret
from sales_metrics import SAO_PAULO


def init_schema(conn, execute):
    execute(conn, '''CREATE TABLE IF NOT EXISTS keiper_ai_runs (
        id BIGSERIAL PRIMARY KEY, conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        day DATE NOT NULL, status TEXT NOT NULL DEFAULT 'running', result JSONB,
        api_status TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        finished_at TIMESTAMPTZ, UNIQUE(conexao_id,day))''')
    execute(conn, '''CREATE TABLE IF NOT EXISTS keiper_ai_usage (
        id BIGSERIAL PRIMARY KEY, run_id BIGINT UNIQUE REFERENCES keiper_ai_runs(id) ON DELETE SET NULL,
        month DATE NOT NULL, model TEXT NOT NULL, pricing JSONB NOT NULL,
        reserved_brl NUMERIC NOT NULL CHECK(reserved_brl>=0),
        committed_brl NUMERIC NOT NULL CHECK(committed_brl>=0),
        input_tokens INTEGER, output_tokens INTEGER, status TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now())''')
    execute(conn, 'CREATE INDEX IF NOT EXISTS keiper_ai_usage_month ON keiper_ai_usage(month)')
    from kyra_campaign_store import init_schema as init_campaign_schema
    init_campaign_schema(conn, execute)


def run_one(banco, query, execute, logger, now=None):
    if os.getenv('KEIPER_AI_DAILY_ENABLED', 'true') != 'true':
        return
    now = time.time() if now is None else now
    local = datetime.fromtimestamp(now, SAO_PAULO)
    if local.hour < 8:
        return
    today = local.date()
    # One shop per tick, one shared lock across Gunicorn workers. Dedicated
    # connection closes even on failure, releasing the session advisory lock.
    with closing(banco()) as lock:
        lock.autocommit = True
        if not query(lock, 'SELECT pg_try_advisory_lock(880145) AS acquired')[0]['acquired']:
            return
        with closing(banco()) as conn, conn:
            rows = query(conn, '''SELECT c.id,c.cliente,c.status FROM conexoes c
                WHERE c.status='ativa' AND NOT EXISTS (SELECT 1 FROM keiper_ai_runs r
                    WHERE r.conexao_id=c.id AND r.day=%s)
                ORDER BY c.id LIMIT 1''', (today,))
            if not rows:
                return
            shop = rows[0]
            runs = query(conn, '''INSERT INTO keiper_ai_runs(conexao_id,day)
                VALUES(%s,%s) ON CONFLICT(conexao_id,day) DO NOTHING RETURNING id''', (shop['id'], today))
            if not runs:
                return
            run_id = runs[0]['id']
        try:
            from overview import load_overview
            end = today-timedelta(days=1)
            args = dict(periodo='personalizado', inicio=(end-timedelta(days=6)).isoformat(), fim=end.isoformat())
            @contextmanager
            def read_database():
                with closing(banco()) as conn, conn:
                    yield conn
            report = load_overview([shop], args, read_database, query)['reports'][0]
            with closing(banco()) as conn, conn:
                execute(conn, "SET LOCAL statement_timeout='15s'")
                ads = query(conn, '''SELECT data,gasto,faturamento,atualizado_em FROM ads_dia
                    WHERE conexao_id=%s AND data BETWEEN %s AND %s ORDER BY data''',
                    (shop['id'], (end-timedelta(days=13)).isoformat(), end.isoformat()))
            result = recommendations(report, ads, today, now)
            # Private deterministic evidence never enters the public findings
            # or the optional provider payload. Failure cannot erase good
            # public sales/Ads output or be interpreted as zero costs.
            from kevia_finance import load_snapshot,empty_snapshot
            try:
                with closing(banco()) as conn, conn:
                    execute(conn, 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                    execute(conn, "SET LOCAL statement_timeout='10s'")
                    financial = load_snapshot(conn,query,shop['id'],end,now)
            except Exception:
                financial = empty_snapshot(end,now,status='failed')
                logger.warning('kevia_financial_unavailable run_id=%s',run_id)
            result['financial'] = financial
            # Persist useful deterministic output before optional paid work.
            with closing(banco()) as conn, conn:
                execute(conn, "UPDATE keiper_ai_runs SET result=%s::jsonb,status='rules_ready' WHERE id=%s",
                        (json.dumps(result), run_id))
            text, api_status = interpret(run_id, result, banco, query, execute)
            result['interpretation'] = text
            with closing(banco()) as conn, conn:
                execute(conn, '''UPDATE keiper_ai_runs SET status='completed',result=%s::jsonb,
                    api_status=%s,finished_at=now() WHERE id=%s''', (json.dumps(result), api_status, run_id))
        except Exception:
            with closing(banco()) as conn, conn:
                execute(conn, "UPDATE keiper_ai_runs SET status='failed',finished_at=now() WHERE id=%s", (run_id,))
            logger.warning('keiper_ai_daily_failed run_id=%s', run_id)
