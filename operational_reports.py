"""Store reports backed by reconciled item sales and daily platform metrics."""
from collections import Counter, defaultdict
from datetime import timedelta

from overview_read import bounded_query
from sales_metrics import amount, created_day
from unsold_report import approved, read_sales, sales_evidence


REPORTS = {
    'pararam-de-vender': ('Anúncios que pararam de vender',
        ('Anúncio', 'MLB', 'SKU', 'Unidades no período anterior', 'Unidades no período atual'),
        'Anúncios ativos que venderam no período anterior e zeraram no atual. Os dois períodos têm a mesma duração e precisam ter vendas verificáveis.'),
    'estoque-baixo': ('Anúncios com estoque baixo e vendas recentes',
        ('Anúncio', 'MLB', 'SKU', 'Estoque atual', 'Unidades vendidas'),
        'Anúncios ativos com estoque sincronizado de 1 a 5 unidades e pelo menos uma unidade vendida no período.'),
    'visitas-poucas-vendas': ('Anúncios com visitas e poucas vendas',
        ('Anúncio', 'MLB', 'SKU', 'Visitas', 'Unidades vendidas'),
        'Anúncios ativos com pelo menos 100 visitas e até uma unidade vendida. As visitas precisam ter registros em todos os dias aplicáveis desde a publicação.'),
    'queda-nas-vendas': ('Anúncios com queda nas vendas',
        ('Anúncio', 'MLB', 'SKU', 'Unidades no período anterior', 'Unidades no período atual', 'Unidades a menos'),
        'Ordena anúncios ativos pela perda de unidades entre dois períodos consecutivos e de mesma duração. Os dois períodos precisam ter vendas verificáveis.'),
    'ads-sem-vendas': ('Campanhas de Ads com gasto e sem vendas atribuídas',
        ('Campanha', 'ID da campanha', 'Gasto (R$)', 'Unidades atribuídas'),
        'Campanhas com gasto positivo e zero unidades atribuídas pelo Mercado Livre. Exige métricas de gasto e atribuição para todos os dias do período.'),
}
COMPARISONS = {'pararam-de-vender', 'queda-nas-vendas'}


def period_units(read, conn, cid, start, end):
    orders, items, coverage = read_sales(read, conn, cid, start, end)
    _, gap = sales_evidence(orders, items, [row['dia'] for row in coverage], start, end)
    if gap:
        return None
    orders_in_period = {row['pedido_id'] for row in orders if approved(row)
                        and (day := created_day(row['criado_em'])) and start <= day <= end}
    units = Counter()
    for item in items:
        if item['pedido_id'] in orders_in_period:
            units[item['item_id']] += item['quantidade']
    return units


def listing_rows(key, listings, current, prior, visits):
    output, insufficient = [], 0
    for row in listings:
        iid = row['item_id']
        units = current[iid]
        stock = row['quantidade']
        label = (row['titulo'], iid, row['sku'])
        if key in COMPARISONS:
            before = prior[iid]
            if before > units and (key == 'queda-nas-vendas' or units == 0):
                output.append((*label, before, units, before - units) if key == 'queda-nas-vendas'
                              else (*label, before, units))
        elif key == 'estoque-baixo' and units:
            if stock is None:
                insufficient += 1
            elif 1 <= stock <= 5:
                output.append((*label, stock, units))
        elif key == 'visitas-poucas-vendas' and units <= 1:
            if iid not in visits:
                insufficient += 1
            elif visits[iid] >= 100:
                output.append((*label, visits[iid], units))
    if key == 'estoque-baixo':
        output.sort(key=lambda row: (row[3], -row[4]))
    elif key in COMPARISONS or key == 'visitas-poucas-vendas':
        output.sort(key=lambda row: -(row[-1] if key == 'queda-nas-vendas' else row[3]))
    return output, insufficient


def campaign_rows(records, days):
    campaigns = defaultdict(list)
    for row in records:
        campaigns[row['campanha_id']].append(row)
    output, insufficient = [], 0
    for cid, rows in campaigns.items():
        spend = [amount(row['gasto']) for row in rows]
        sales = [row['vendas_atribuidas'] for row in rows]
        if len(rows) != days or None in spend or any(type(n) is not int or n < 0 for n in sales):
            insufficient += 1
        elif sum(spend) > 0 and sum(sales) == 0:
            output.append((rows[0]['nome'] or cid, cid, sum(spend), 0))
    return sorted(output, key=lambda row: -row[2]), insufficient, len(campaigns)


def read_operation(bank, query, cid, key, start, end):
    days = (end - start).days + 1
    with bank() as conn:
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True)
        read = bounded_query(conn, query)
        if key == 'ads-sem-vendas':
            rows = read(conn, """SELECT d.campanha_id,c.nome,d.gasto,d.vendas_atribuidas
                FROM ads_campanha_dia d LEFT JOIN ads_campanhas c USING(conexao_id,campanha_id)
                WHERE d.conexao_id=%s AND d.data BETWEEN %s AND %s LIMIT 60001""",
                        (cid, start.isoformat(), end.isoformat()))
            if len(rows) > 60_000:
                raise ValueError('Volume de campanhas acima do limite. Reduza o período.')
            return campaign_rows(rows, days)
        listings = read(conn, """SELECT item_id,titulo,sku,quantidade,publicado_em FROM anuncios
            WHERE conexao_id=%s AND status='active' ORDER BY titulo NULLS LAST,item_id LIMIT 10001""", (cid,))
        if not listings:
            return [], 0, 0
        if len(listings) > 10_000:
            raise ValueError('O catálogo ativo excede 10 mil anúncios.')
        current = period_units(read, conn, cid, start, end)
        if current is None:
            return [], len(listings), len(listings)
        prior = None
        if key in COMPARISONS:
            prior = period_units(read, conn, cid, start - timedelta(days=days), start - timedelta(days=1))
            if prior is None:
                return [], len(listings), len(listings)
        visits = {}
        if key == 'visitas-poucas-vendas':
            eligible = [(row['item_id'], max(start, created_day(row['publicado_em']) or start))
                        for row in listings if current[row['item_id']] <= 1]
            rows = read(conn, """SELECT v.item_id,SUM(v.visitas) AS visitas FROM item_visits_daily v
                JOIN unnest(%s::text[],%s::date[]) AS items(item_id,inicio) USING(item_id)
                WHERE v.conexao_id=%s AND v.dia BETWEEN items.inicio AND %s
                GROUP BY v.item_id,items.inicio HAVING COUNT(*)=(%s-items.inicio+1)""",
                        ([item for item, _ in eligible], [day for _, day in eligible], cid, end, end))
            visits = {row['item_id']: row['visitas'] for row in rows}
    rows, insufficient = listing_rows(key, listings, current, prior, visits)
    return rows, insufficient, len(listings)
