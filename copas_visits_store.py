"""Copas-only visits collector. Persist the last 7 complete UTC days idempotently."""
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
            cur.execute("SELECT item_id FROM anuncios WHERE conexao_id=%s AND status = 'active' AND item_id ~ '^MLB[0-9]+
            items = [row[0] for row in cur.fetchall()]
        # DDL and writes are restricted to this collector, invoked explicitly by an administrator.
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS item_visits_daily (
                    conexao_id INTEGER NOT NULL,
                    item_id TEXT NOT NULL,
                    dia DATE NOT NULL,
                    visitas INTEGER NOT NULL CHECK (visitas >= 0),
                    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (conexao_id, item_id, dia)
                )
            """)
        conn.commit()
        results = {"loja": "Copas Ind", "offset": offset, "proximo_offset": offset + len(items), "itens_solicitados": len(items), "itens_atualizados": 0, "dias_gravados": 0, "falhas": 0}
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
                # All dates are explicitly returned by ML; exclude current UTC day.
                parsed = []
                for entry in payload["results"]:
                    day = _parse_day(entry["date"])
                    visits = entry["total"]
                    if type(visits) is not int or visits < 0:
                        raise ValueError("Invalid daily visits")
                    if day < today and day >= today - dt.timedelta(days=7):
                        parsed.append((CONNECTION_ID, item, day, visits))
                with conn.cursor() as cur:
                    for row in parsed:
                        cur.execute("""
                            INSERT INTO item_visits_daily (conexao_id, item_id, dia, visitas)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (conexao_id, item_id, dia) DO UPDATE
                            SET visitas=EXCLUDED.visitas, atualizado_em=NOW()
                        """, row)
                conn.commit()
                results["itens_atualizados"] += 1
                results["dias_gravados"] += len(parsed)
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError, TypeError, TimeoutError):
                conn.rollback()
                results["falhas"] += 1
        return results
 ORDER BY item_id LIMIT %s OFFSET %s", (CONNECTION_ID, limit, offset))
            items = [row[0] for row in cur.fetchall()]
        # DDL and writes are restricted to this collector, invoked explicitly by an administrator.
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS item_visits_daily (
                    conexao_id INTEGER NOT NULL,
                    item_id TEXT NOT NULL,
                    dia DATE NOT NULL,
                    visitas INTEGER NOT NULL CHECK (visitas >= 0),
                    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (conexao_id, item_id, dia)
                )
            """)
        conn.commit()
        results = {"loja": "Copas Ind", "itens_solicitados": len(items), "itens_atualizados": 0, "dias_gravados": 0, "falhas": 0}
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
                # All dates are explicitly returned by ML; exclude current UTC day.
                parsed = []
                for entry in payload["results"]:
                    day = _parse_day(entry["date"])
                    visits = entry["total"]
                    if type(visits) is not int or visits < 0:
                        raise ValueError("Invalid daily visits")
                    if day < today and day >= today - dt.timedelta(days=7):
                        parsed.append((CONNECTION_ID, item, day, visits))
                with conn.cursor() as cur:
                    for row in parsed:
                        cur.execute("""
                            INSERT INTO item_visits_daily (conexao_id, item_id, dia, visitas)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (conexao_id, item_id, dia) DO UPDATE
                            SET visitas=EXCLUDED.visitas, atualizado_em=NOW()
                        """, row)
                conn.commit()
                results["itens_atualizados"] += 1
                results["dias_gravados"] += len(parsed)
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError, TypeError, TimeoutError):
                conn.rollback()
                results["falhas"] += 1
        return results
