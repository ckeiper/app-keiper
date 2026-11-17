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
        if created is None or (last_gap and last_gap >= max(start, created)):
            insufficient += 1
            continue
        metadata = listing['full_metadata_json'] or {}
        kind = metadata.get('logistic_type')
        logistics = {'fulfillment': 'Full', 'self_service': 'Flex'}.get(kind)
        rows.append(dict(listing, recent=created > start, logistics=logistics or ('Outra' if kind else None),
                         effective_start=max(start, created)))
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
        bounds = (cid, start, end)
        orders = read(conn, """SELECT conexao_id,pedido_id,status,moeda,total,criado_em,
            pagamentos_json,unidades,vendas_dia_coleta FROM pedidos
            WHERE conexao_id=%s AND vendas_verificado_em IS NOT NULL AND status='paid'
            AND (keiper_overview_day_v1(criado_em) BETWEEN %s AND %s
                 OR keiper_overview_day_v1(criado_em) IS NULL) LIMIT 20001""", bounds)
        items = read(conn, """SELECT pi.pedido_id,pi.item_id,pi.quantidade FROM pedidos_itens pi
            JOIN pedidos p USING(conexao_id,pedido_id)
            WHERE p.conexao_id=%s AND p.vendas_verificado_em IS NOT NULL AND p.status='paid'
            AND (keiper_overview_day_v1(p.criado_em) BETWEEN %s AND %s
                 OR keiper_overview_day_v1(p.criado_em) IS NULL)
            AND pi.atualizado_em=p.vendas_verificado_em LIMIT 60001""", bounds)
        if len(orders) > 20_000 or len(items) > 60_000:
            raise ValueError('O volume de pedidos excede o limite do relatório. Selecione um período menor.')
        coverage = read(conn, """SELECT dia FROM vendas_cobertura WHERE conexao_id=%s
            AND dia BETWEEN %s AND %s""", (cid, start.isoformat(), end.isoformat()))
        sold, last_gap = sales_evidence(orders, items, [r['dia'] for r in coverage], start, end)
        rows, insufficient = classify(listings, sold, last_gap, start, end)
        if not rows:
            return rows, insufficient, len(listings)
        ids = [r['item_id'] for r in rows]
        latest = read(conn, """SELECT pi.item_id,MAX(keiper_overview_day_v1(p.criado_em)) AS dia
            FROM pedidos_itens pi JOIN pedidos p USING(conexao_id,pedido_id)
            WHERE p.conexao_id=%s AND pi.item_id=ANY(%s) AND p.status='paid' AND p.moeda='BRL'
            AND pi.quantidade>0 AND pi.atualizado_em=p.vendas_verificado_em
            AND p.pagamentos_json @> '[{"status":"approved"}]'::jsonb
            AND keiper_overview_day_v1(p.criado_em)<%s GROUP BY pi.item_id""", (cid, ids, start))
        visits = read(conn, """SELECT item_id,dia,visitas FROM item_visits_daily
            WHERE conexao_id=%s AND dia BETWEEN %s AND %s AND item_id=ANY(%s)""", (*bounds, ids))
        ads = read(conn, """SELECT DISTINCT item_id FROM ads_metricas
            WHERE conexao_id=%s AND item_id=ANY(%s) AND atualizado_em IS NOT NULL""", (cid, ids))
    last_by_item = {r['item_id']: r['dia'] for r in latest}
    visits_by_item = defaultdict(dict)
    for row in visits:
        visits_by_item[row['item_id']][row['dia']] = row['visitas']
    with_ads = {r['item_id'] for r in ads}
    for row in rows:
        iid = row['item_id']
        history = visits_by_item[iid]
        observed = [count for day, count in history.items() if row['effective_start'] <= day <= end]
        days = (end - row['effective_start']).days + 1
        row.update(last_sale=last_by_item.get(iid), visits=sum(observed) if len(observed) == days else None,
                   ads='Vínculo registrado' if iid in with_ads else None)
    return rows, insufficient, len(listings)
