"""Additive schema and bounded order synchronization, with explicit coverage."""
import datetime
import json
import time
from sales_metrics import created_day, order_fields, reporting_today


def init_sales_schema(conn, execute):
    for column in ("criado_em TEXT", "pagamentos_json JSONB", "unidades INTEGER",
                   "vendas_verificado_em BIGINT", "vendas_dia_coleta TEXT"):
        execute(conn, "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS " + column)
    execute(conn, """CREATE TABLE IF NOT EXISTS vendas_cobertura (
        conexao_id INTEGER NOT NULL, dia TEXT NOT NULL, atualizado_em BIGINT NOT NULL,
        PRIMARY KEY (conexao_id, dia))""")


def _read_window(token, user_id, api_get, lower, upper, budget):
    offset, rows, complete = 0, {}, False
    reason = "limite de paginação de 1000 resultados atingido"
    expected_total = None
    while offset < 1000:
        if budget[0] <= 0:
            return rows, False, 'limite de requisições da recuperação atingido'
        budget[0] -= 1
        data, error = api_get(token, "/orders/search", {
            "seller": user_id, "sort": "date_desc", "limit": 50, "offset": offset,
            "order.date_created.from": lower.isoformat(timespec="milliseconds"),
            "order.date_created.to": upper.isoformat(timespec="milliseconds")})
        if error or not isinstance(data, dict):
            reason = error or "resposta inválida"
            break
        results = data.get("results")
        total = (data.get("paging") or {}).get("total")
        if not isinstance(results, list) or type(total) is not int or total < 0:
            reason = "resposta inválida: results ou paging.total"
            break
        if expected_total is not None and total != expected_total:
            reason = "total alterado durante a paginação; nova coleta necessária"
            break
        expected_total = total
        valid = True
        before = len(rows)
        for order in results:
            if not isinstance(order, dict) or not order.get("id"):
                valid = False
                reason = "resposta inválida: pedido sem identificador"
                break
            rows[str(order["id"])] = order
        if not valid:
            break
        if results and len(rows) - before != len(results):
            reason = "paginação repetida: identificadores duplicados"
            break
        offset += len(results)
        if offset >= total:
            complete = len(rows) == total
            if not complete:
                reason = "quantidade recebida diferente de paging.total"
            break
        if not results:
            reason = "página vazia antes de paging.total"
            break
    return rows, complete, reason


def collect_day(token, user_id, api_get, day):
    """Recover pagination with hour-aligned, half-open reporting windows.

    Orders search discards minutes/seconds in date filters. Query complete
    hours (including the next boundary) and assign returned orders locally
    to [start, end), after validating every raw page and paging.total.
    """
    zone = datetime.timezone(datetime.timedelta(hours=-3))
    lower = datetime.datetime.combine(day, datetime.time(), zone)
    upper = lower + datetime.timedelta(days=1)
    budget = [80]
    hour = datetime.timedelta(hours=1)

    def read(start, end, depth=0):
        rows, complete, reason = _read_window(token, user_id, api_get, start, end, budget)
        assigned = {}
        for oid, row in rows.items():
            try:
                stamp = datetime.datetime.fromisoformat(row.get('date_created', '').replace('Z', '+00:00'))
                valid = stamp.tzinfo is not None
            except (TypeError, ValueError, AttributeError):
                valid = False
            if not valid:
                if depth:
                    return rows, False, 'resposta fora do intervalo solicitado ou sem data verificável'
                # Preserve unknown dates for the existing integrity indicators.
                assigned[oid] = row
                continue
            if not start <= stamp < end + hour:
                return rows, False, 'resposta fora do intervalo solicitado ou sem data verificável'
            if stamp < end:
                assigned[oid] = row
        if complete:
            return assigned, True, reason
        recoverable = any(text in reason for text in
                          ('identificadores duplicados', 'total alterado', '1000 resultados'))
        hours = int((end-start).total_seconds()//3600)
        if not recoverable or not rows or hours < 2 or budget[0] < 2:
            return rows, False, reason
        if any(created_day(row.get('date_created')) is None for row in rows.values()):
            return rows, False, reason
        middle = start + hour * (hours//2)
        left, ok, failure = read(start, middle, depth+1)
        if not ok:
            return rows, False, failure
        right, ok, failure = read(middle, end, depth+1)
        if not ok:
            return rows, False, failure
        if left.keys() & right.keys():
            return rows, False, 'identificadores duplicados entre intervalos'
        return {**left, **right}, True, ''

    return read(lower, upper)


def sync_orders(cid, token, user_id, banco, query, execute, api_get, log):
    now = int(time.time())
    today = reporting_today()
    with banco() as conn:
        saved = query(conn, "SELECT dia, atualizado_em FROM vendas_cobertura WHERE conexao_id=%s", (cid,))
    coverage = {r["dia"]: r["atualizado_em"] for r in saved}
    selected = select_sync_days(today, now, coverage)
    success = True
    for day in selected:
        iso = day.isoformat()
        rows, complete, reason = collect_day(token, user_id, api_get, day)
        with banco() as conn:
            for oid, order in rows.items():
                created, payments, units = order_fields(order)
                if created_day(created) is None or payments is None or units is None:
                    detail, error = api_get(token, "/orders/" + oid)
                    if not error and isinstance(detail, dict) and str(detail.get("id")) == oid:
                        order = detail
                        created, payments, units = order_fields(order)
                execute(conn, """INSERT INTO pedidos
                    (conexao_id, pedido_id, status, total, moeda, fechado_em,
                     atualizado_em, criado_em, pagamentos_json, unidades, vendas_verificado_em,
                     vendas_dia_coleta)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                    ON CONFLICT (conexao_id, pedido_id) DO UPDATE SET
                      status=EXCLUDED.status, total=EXCLUDED.total, moeda=EXCLUDED.moeda,
                      fechado_em=EXCLUDED.fechado_em, atualizado_em=EXCLUDED.atualizado_em,
                      criado_em=EXCLUDED.criado_em, pagamentos_json=EXCLUDED.pagamentos_json,
                      unidades=EXCLUDED.unidades, vendas_verificado_em=EXCLUDED.vendas_verificado_em,
                      vendas_dia_coleta=EXCLUDED.vendas_dia_coleta""",
                    (cid, oid, order.get("status"), order.get("total_amount"),
                     order.get("currency_id"), order.get("date_closed") or created, now,
                     created, json.dumps(payments) if payments is not None else None, units, now, iso))
                # Refresh every available item, summing variations of the same listing.
                items = order.get("order_items")
                if isinstance(items, list) and units is not None:
                    grouped = {}
                    for item in items:
                        iid = (item.get("item") or {}).get("id")
                        price = item.get("unit_price")
                        if not iid or not isinstance(price, (int, float)):
                            grouped = None
                            break
                        qty, gross = grouped.get(str(iid), (0, 0))
                        grouped[str(iid)] = (qty + item["quantity"], gross + price * item["quantity"])
                    if grouped:
                        execute(conn, "DELETE FROM pedidos_itens WHERE conexao_id=%s AND pedido_id=%s", (cid, oid))
                        for iid, (qty, gross) in grouped.items():
                            execute(conn, """INSERT INTO pedidos_itens
                                (conexao_id, pedido_id, item_id, quantidade, preco_unitario, atualizado_em)
                                VALUES (%s,%s,%s,%s,%s,%s)""", (cid, oid, iid, qty, gross / qty, now))
            if complete:
                execute(conn, """INSERT INTO vendas_cobertura (conexao_id, dia, atualizado_em)
                    VALUES (%s,%s,%s) ON CONFLICT (conexao_id, dia)
                    DO UPDATE SET atualizado_em=EXCLUDED.atualizado_em""", (cid, iso, now))
            else:
                # A failed refresh invalidates old coverage rather than showing a false zero.
                execute(conn, "DELETE FROM vendas_cobertura WHERE conexao_id=%s AND dia=%s", (cid, iso))
                success = False
                log(cid, "pedidos", iso + ": janela incompleta — " + reason)
    return success



def select_sync_days(today, now, coverage, older_limit=4):
    """Keep seven newest days fresh and backfill only the last 30 calendar days; retain older data."""
    recent = [today - datetime.timedelta(days=i) for i in range(7)]
    older = [today - datetime.timedelta(days=i) for i in range(7, 30)]
    eligible = [d for d in older if now - coverage.get(d.isoformat(), 0) >= 86400]
    eligible.sort(key=lambda d: (
        0 if d.isoformat() not in coverage and (today - d).days < 30 else 1,
        0 if (today - d).days < 60 else 1,
        coverage.get(d.isoformat(), 0), -d.toordinal()))
    return recent + eligible[:older_limit]

