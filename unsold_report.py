"""Read the store's synchronized evidence for the unsold listings report."""
from collections import defaultdict
from datetime import timedelta

from overview_read import bounded_query
from sales_metrics import created_day, summarize


LIMIT = 10_000
PERIODS = (7, 15, 30)


def approved(order):
    payments = order['pagamentos_json']
    return (order['status'] == 'paid' and order['moeda'] == 'BRL'
            and isinstance(payments, list) and all(isinstance(p, dict) and p.get('status') for p in payments)
            and any(p['status'] == 'approved' for p in payments))


def sales_evidence(orders, items, coverage, start, end):
    summary = summarize(orders, start, end, set(coverage))
    bad = {start + timedelta(days=i) for i, count in enumerate(summary['daily_orders']) if count is None}
    grouped = defaultdict(list)
    for row in items:
        grouped[row['pedido_id']].append(row)
    sold = set()
    for order in orders:
        day = created_day(order['criado_em'])
        if day is None or not start <= day <= end or not approved(order):
            continue
        lines = grouped[order['pedido_id']]
        if (not lines or any(not line['item_id'] or type(line['quantidade']) is not int or line['quantidade'] <= 0
                             for line in lines)
                or sum(line['quantidade'] for line in lines) != order['unidades']):
            bad.add(day)
        sold.update(line['item_id'] for line in lines if line['item_id'])
    if summary['unallocated_dates']:
        bad.add(end)
    return sold, max(bad, default=None)


def classify(listings, sold, last_gap, start, end):
    rows, insufficient = [], 0
    for listing in listings:
        if listing['item_id'] in sold:
            continue
        created = created_day(listing['publicado_em'])
        if created and created > end:
            continue
        effective_start = max(start, created) if created else start
        if last_gap and last_gap >= effective_start:
            insufficient += 1
            continue
        metadata = listing['full_metadata_json'] or {}
        kind = metadata.get('logistic_type')
        logistics = {'fulfillment': 'Full', 'self_service': 'Flex'}.get(kind)
        rows.append(dict(listing, recent=created > start if created else None,
                         logistics=logistics or ('Outra' if kind else None), effective_start=effective_start))
    return rows, insufficient


def read_report(bank, query, cid, start, end):
    with bank() as conn:
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True)
        read = bounded_query(conn, query)
        listings = read(conn, """SELECT item_id,titulo,sku,preco,quantidade,thumbnail,categoria_id,
            publicado_em,full_metadata_json FROM anuncios WHERE conexao_id=%s AND status='active'
            ORDER BY titulo NULLS LAST,item_id LIMIT %s""", (cid, LIMIT + 1))
        if not listings:
            return [], 0, 0
        if len(listings) > LIMIT:
            raise ValueError('O catálogo ativo excede o limite de 10 mil anúncios do relatório.')
        # Use the indexed raw date prefix to find candidates, leaving exact
        # Brasília date conversion to Python, including unusual timestamps.
        prefix_start = (start - timedelta(days=1)).isoformat()
        prefix_end = (end + timedelta(days=2)).isoformat()
        orders = read(conn, """SELECT conexao_id,pedido_id,status,moeda,total,criado_em,
            pagamentos_json,unidades,vendas_dia_coleta,vendas_verificado_em FROM pedidos
            WHERE conexao_id=%s AND vendas_verificado_em IS NOT NULL AND status='paid'
            AND LEFT(criado_em,10) BETWEEN %s AND %s
            UNION ALL
            SELECT conexao_id,pedido_id,status,moeda,total,criado_em,
            pagamentos_json,unidades,vendas_dia_coleta,vendas_verificado_em FROM pedidos
            WHERE conexao_id=%s AND vendas_verificado_em IS NOT NULL AND status='paid'
            AND keiper_overview_day_v1(criado_em) IS NULL
            AND (LEFT(criado_em,10) BETWEEN %s AND %s) IS NOT TRUE LIMIT 20001""",
                      (cid, prefix_start, prefix_end, cid, prefix_start, prefix_end))
        if len(orders) > 20_000:
            raise ValueError('O volume de pedidos excede o limite do relatório. Selecione um período menor.')
        # Reuse the selected orders and their exact collection version. This keeps
        # the item lookup on its primary key without recalculating order dates.
        relevant = [order for order in orders
                    if (day := created_day(order['criado_em'])) and start <= day <= end and approved(order)]
        items = read(conn, """SELECT pi.pedido_id,pi.item_id,pi.quantidade FROM pedidos_itens pi
            JOIN unnest(%s::text[],%s::bigint[]) AS selected(pedido_id,verified_at)
                ON pi.pedido_id=selected.pedido_id AND pi.atualizado_em=selected.verified_at
            WHERE pi.conexao_id=%s LIMIT 60001""",
                     ([order['pedido_id'] for order in relevant],
                      [order['vendas_verificado_em'] for order in relevant], cid)) if relevant else []
        if len(items) > 60_000:
            raise ValueError('O volume de itens excede o limite do relatório. Selecione um período menor.')
        coverage = read(conn, """SELECT dia FROM vendas_cobertura WHERE conexao_id=%s
            AND dia BETWEEN %s AND %s""", (cid, start.isoformat(), end.isoformat()))
        sold, last_gap = sales_evidence(orders, items, [r['dia'] for r in coverage], start, end)
        rows, insufficient = classify(listings, sold, last_gap, start, end)
        if not rows:
            return rows, insufficient, len(listings)
        ids = [r['item_id'] for r in rows]
        latest = read(conn, """WITH paid AS MATERIALIZED (
            SELECT pedido_id,vendas_verificado_em,criado_em
            FROM pedidos WHERE conexao_id=%s AND vendas_verificado_em IS NOT NULL
            AND status='paid' AND moeda='BRL' AND pagamentos_json @> '[{"status":"approved"}]'::jsonb
        ), candidates AS MATERIALIZED (
            SELECT pedido_id,item_id,atualizado_em FROM pedidos_itens
            WHERE conexao_id=%s AND item_id=ANY(%s) AND quantidade>0
        )
        SELECT candidates.item_id,paid.criado_em FROM candidates
        JOIN paid ON paid.pedido_id=candidates.pedido_id
                 AND paid.vendas_verificado_em=candidates.atualizado_em
        """, (cid, cid, ids))
        ads = read(conn, """SELECT DISTINCT item_id FROM ads_metricas
            WHERE conexao_id=%s AND item_id=ANY(%s) AND atualizado_em IS NOT NULL""", (cid, ids))
    last_by_item = {}
    for record in latest:
        day = created_day(record['criado_em'])
        iid = record['item_id']
        if day and day < start and (iid not in last_by_item or day > last_by_item[iid]):
            last_by_item[iid] = day
    with_ads = {r['item_id'] for r in ads}
    for row in rows:
        iid = row['item_id']
        row.update(last_sale=last_by_item.get(iid), ads='Vínculo registrado' if iid in with_ads else None)
    return rows, insufficient, len(listings)
