"""Copas-only bounded daily visits collector and coverage tracking."""
import datetime as dt
import json
import os
import urllib.error
import urllib.request

import psycopg2

CONNECTION_ID = 5
API = "https://api.mercadolibre.com"


def _parse_day(value):
    return dt.date.fromisoformat(value[:10])


def collect(limit=10, offset=0):
    if not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError("limit must be 1..10")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be nonnegative")
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT cliente, status, access_token FROM conexoes WHERE id=%s", (CONNECTION_ID,))
            record = cur.fetchone()
            if not record or record[0] != "Copas Ind" or record[1] != "ativa" or not record[2]:
                raise RuntimeError("Copas connection unavailable")
            token = record[2]
            cur.execute(
                "SELECT item_id FROM anuncios WHERE conexao_id=%s AND status='active' "
                "AND item_id ~ '^MLB[0-9]+$' ORDER BY item_id LIMIT %s OFFSET %s",
                (CONNECTION_ID, limit, offset),
            )
            items = [row[0] for row in cur.fetchall()]
            cur.execute("""
                CREATE TABLE IF NOT EXISTS item_visits_daily (
                    conexao_id INTEGER NOT NULL, item_id TEXT NOT NULL,
                    dia DATE NOT NULL, visitas INTEGER NOT NULL CHECK (visitas >= 0),
                    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (conexao_id, item_id, dia)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS item_visits_checked (
                    conexao_id INTEGER NOT NULL, item_id TEXT NOT NULL,
                    consultado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (conexao_id, item_id)
                )
            """)
        conn.commit()
        results = {"loja": "Copas Ind", "offset": offset, "proximo_offset": offset + len(items),
                   "itens_solicitados": len(items), "itens_atualizados": 0,
                   "dias_gravados": 0, "falhas": 0}
        today = dt.datetime.now(dt.timezone.utc).date()
        for item in items:
            req = urllib.request.Request(
                f"{API}/items/{item}/visits/time_window?last=7&unit=day",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict) or payload.get("item_id") != item or not isinstance(payload.get("results"), list):
                    raise ValueError("Unexpected API response")
                parsed = []
                for entry in payload["results"]:
                    day = _parse_day(entry["date"])
                    visits = entry["total"]
                    if type(visits) is not int or visits < 0:
                        raise ValueError("Invalid daily visits")
                    if today - dt.timedelta(days=7) <= day < today:
                        parsed.append((CONNECTION_ID, item, day, visits))
                with conn.cursor() as cur:
                    for row in parsed:
                        cur.execute("""
                            INSERT INTO item_visits_daily (conexao_id, item_id, dia, visitas)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (conexao_id, item_id, dia) DO UPDATE
                            SET visitas=EXCLUDED.visitas, atualizado_em=NOW()
                        """, row)
                    cur.execute("""
                        INSERT INTO item_visits_checked (conexao_id, item_id)
                        VALUES (%s, %s)
                        ON CONFLICT (conexao_id, item_id) DO UPDATE SET consultado_em=NOW()
                    """, (CONNECTION_ID, item))
                conn.commit()
                results["itens_atualizados"] += 1
                results["dias_gravados"] += len(parsed)
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError, TypeError, TimeoutError):
                conn.rollback()
                results["falhas"] += 1
        return results


def progress():
    """Read-only coverage snapshot; distinguishes checked items from items with visits."""
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM anuncios
                WHERE conexao_id=%s AND status='active' AND item_id ~ '^MLB[0-9]+$'
            """, (CONNECTION_ID,))
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT COUNT(DISTINCT v.item_id), COUNT(*), COALESCE(SUM(v.visitas),0),
                       MIN(v.dia), MAX(v.dia)
                FROM item_visits_daily v
                JOIN anuncios a ON a.conexao_id=v.conexao_id AND a.item_id=v.item_id
                WHERE v.conexao_id=%s AND a.status='active'
                  AND v.dia >= (CURRENT_DATE - INTERVAL '7 days')
                  AND v.dia < CURRENT_DATE
            """, (CONNECTION_ID,))
            covered, rows, visits, first, last = cur.fetchone()
            cur.execute("""
                SELECT COUNT(*), MAX(c.consultado_em)
                FROM item_visits_checked c
                JOIN anuncios a ON a.conexao_id=c.conexao_id AND a.item_id=c.item_id
                WHERE c.conexao_id=%s AND a.status='active'
            """, (CONNECTION_ID,))
            checked, latest = cur.fetchone()
    return {
        "loja": "Copas Ind", "anuncios_ativos": total,
        "anuncios_consultados": checked, "anuncios_pendentes": max(0, total-checked),
        "anuncios_com_visitas": covered,
        "anuncios_sem_registros": max(0, total-covered),
        "registros_diarios": rows, "visitas_registradas": visits,
        "primeiro_dia": first.isoformat() if first else None,
        "ultimo_dia": last.isoformat() if last else None,
        "ultima_consulta": latest.isoformat() if latest else None,
        "cobertura_completa": checked == total and total > 0,
        "aviso": "Consultados contam apenas execucoes registradas a partir desta atualizacao."
    }
