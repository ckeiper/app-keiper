"""Read-only, bounded visits KPI for the seven last completed Sao Paulo dates.

Partial coverage is never presented as the total for all shops.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def load_visits_card(banco, shops):
    ids = [int(shop["id"]) for shop in shops]
    if not ids:
        return {"available": False}
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    start = today - timedelta(days=7)
    try:
        with banco() as conn:
            conn.set_session(readonly=True)
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.item_visits_daily')")
                if cur.fetchone()[0] is None:
                    return {"available": False}
                cur.execute("""
                    SELECT COALESCE(SUM(visitas),0), COUNT(*),
                           COUNT(DISTINCT conexao_id), COUNT(DISTINCT dia),
                           MAX(dia)
                    FROM item_visits_daily
                    WHERE conexao_id = ANY(%s)
                      AND dia >= %s AND dia < %s
                """, (ids, start, today))
                total, rows, shops_with_data, days, latest = cur.fetchone()
        if not rows:
            return {"available": False}
        with banco() as conn:
            conn.set_session(readonly=True)
            with conn.cursor() as cur:
                cur.execute("""SELECT conexao_id, dia, SUM(visitas)
                    FROM item_visits_daily
                    WHERE conexao_id = ANY(%s) AND dia >= %s AND dia < %s
                    GROUP BY conexao_id, dia ORDER BY dia, conexao_id""", (ids, start, today))
                daily_rows = cur.fetchall()
        daily = {}
        by_shop = {}
        for cid, day, count in daily_rows:
            key = day.isoformat()
            daily[key] = daily.get(key, 0) + int(count)
            by_shop[cid] = by_shop.get(cid, 0) + int(count)
        return {
            "daily": daily, "by_shop": by_shop,
            "available": True, "visits": int(total),
            "rows": int(rows), "shops_with_data": int(shops_with_data),
            "shops_total": len(ids), "days_with_data": int(days),
            "latest": latest.strftime("%d/%m/%Y"),
            "start": start.strftime("%d/%m/%Y"),
            "end": (today - timedelta(days=1)).strftime("%d/%m/%Y"),
        }
    except Exception:
        # Existing deployments without the visits table must still render.
        return {"available": False}
