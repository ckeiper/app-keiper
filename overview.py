"""Administrative overview. Pure calculations, bounded batch reads, no API calls."""
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from html import escape
import time

from sales_metrics import SAO_PAULO, change, period, summarize
from sales_view import filters, fmt
from overview_store import PERIOD_ROWS_SQL, UNUSUAL_SQL, LATEST_ERRORS_SQL
from overview_read import bounded_query

EXCEPTION_BATCH_SIZE = 500
STALE_SECONDS = 3 * 60 * 60
HISTORICAL_STALE_SECONDS = 48 * 60 * 60


def load_overview(shops, args, banco, query):
    """Read only selected dates with cheap indexed text-prefix filtering.

    The original daily SQL repeatedly invoked a PL/pgSQL date parser and
    jsonb expansions; on production, 8,328 orders took 19.1 seconds. Use
    the exact existing Python classifier instead, preserving integrity.
    """
    bounds = period(args)
    ids = [s['id'] for s in shops]
    if not ids:
        return build_overview(shops, [], [], [], bounds)
    # ISO 8601 dates can shift by one calendar day in Brasília.
    first = (bounds[2] - timedelta(days=1)).isoformat()
    last = (bounds[1] + timedelta(days=1)).isoformat()
    by_shop = defaultdict(list)
    seen = set()
    with banco() as conn:
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True)
        read = bounded_query(conn, query)
        selected = read(conn, PERIOD_ROWS_SQL, (ids, first, last))
        coverage = read(conn, """SELECT conexao_id, dia, atualizado_em
            FROM vendas_cobertura WHERE conexao_id = ANY(%s)
            AND dia BETWEEN %s AND %s""",
            (ids, bounds[2].isoformat(), bounds[1].isoformat()))
        errors = read(conn, LATEST_ERRORS_SQL, (ids,))
        for row in selected:
            key = (row['conexao_id'], str(row['pedido_id']))
            if key not in seen:
                seen.add(key)
                by_shop[row['conexao_id']].append(row)
        # Noncanonical or invalid timestamps are still checked for unknown
        # dates; they must never silently become zeros or valid totals.
        cursor = None
        while True:
            condition = ' AND (conexao_id,pedido_id) > (%s,%s)' if cursor else ''
            params = (ids,) + (cursor or ()) + (EXCEPTION_BATCH_SIZE,)
            rows = read(conn, UNUSUAL_SQL + condition +
                        ' ORDER BY conexao_id,pedido_id LIMIT %s', params)
            for row in rows:
                key = (row['conexao_id'], str(row['pedido_id']))
                if key not in seen:
                    seen.add(key)
                    by_shop[row['conexao_id']].append(row)
            if len(rows) < EXCEPTION_BATCH_SIZE:
                break
            cursor = (rows[-1]['conexao_id'], rows[-1]['pedido_id'])
    covered = defaultdict(dict)
    for row in coverage:
        covered[row['conexao_id']][row['dia']] = row['atualizado_em']
    summaries = {cid: [
        summarize(by_shop[cid], start, end, covered[cid])
        for start, end in ((bounds[0], bounds[1]), (bounds[2], bounds[3]))
    ] for cid in ids}
    return build_overview(shops, [], coverage, errors, bounds,
                          summaries=summaries)


def daily_summary(rows, start, end, covered):
    result = summarize([], start, end, covered)
    selected = {r['dia'].isoformat(): r for r in rows if start <= r['dia'] <= end}
    result['invalid'] = sum(r['invalid'] for r in selected.values())
    result['unknown_units'] = sum(r['unknown_units'] for r in selected.values())
    for key in ('revenue','orders','units','cancellations'):
        result[key] = sum((r[key] for r in selected.values()), Decimal(0) if key == 'revenue' else 0)
    result['daily'] = [None if d not in covered or selected.get(d,{}).get('invalid',0)
                       else float(selected.get(d,{}).get('revenue',0)) for d in result['days']]
    if not result['complete'] or result['invalid']:
        for key in ('revenue','orders','units'):
            result[key] = None
    if not result['complete']:
        result['cancellations'] = None
    if result['unknown_units']:
        result['units'] = None
    return recalculate(result)


def recalculate(result):
    revenue = result['revenue']
    result['ticket'] = revenue / result['orders'] if revenue is not None and result['orders'] else None
    result['unit_price'] = revenue / result['units'] if revenue is not None and result['units'] else None
    return result


def merge_summary(left, right):
    result = dict(left)
    for key in ('revenue','orders','units','cancellations'):
        result[key] = left[key] + right[key] if left[key] is not None and right[key] is not None else None
    for key in ('invalid','unknown_units','invalid_dates','unallocated_dates'):
        result[key] = left[key] + right[key]
    result['daily'] = [a+b if a is not None and b is not None else None
                       for a,b in zip(left['daily'],right['daily'])]
    return recalculate(result)


def build_overview(shops, rows, coverage, errors, bounds, now=None, limited=False, summaries=None):
    start, end, prev_start, prev_end = bounds
    now = int(time.time()) if now is None else now
    recent_start = datetime.fromtimestamp(now, SAO_PAULO).date() - timedelta(days=6)
    # Defense in depth: discard any data not belonging to the authorized shop list.
    allowed = {s['id'] for s in shops}
    by_shop, by_day, by_error = defaultdict(list), defaultdict(dict), defaultdict(list)
    for row in rows:
        if row['conexao_id'] in allowed:
            by_shop[row['conexao_id']].append(row)
    for row in coverage:
        if row['conexao_id'] in allowed:
            by_day[row['conexao_id']][row['dia']] = row['atualizado_em']
    for row in errors:
        if row['conexao_id'] in allowed:
            by_error[row['conexao_id']].append(row)
    reports, alerts = [], []
    for shop in shops:
        cid = shop['id']
        days = by_day[cid]
        current, previous = summaries[cid] if summaries is not None else (
            summarize(by_shop[cid], start, end, days), summarize(by_shop[cid], prev_start, prev_end, days))
        selected_days = current['days'] + previous['days']
        selected_stamps = [days[d] for d in selected_days if d in days]
        # Every selected day must satisfy its own freshness rule. A success on
        # another day must not validate stale data or clear an unresolved error.
        last = min(selected_stamps, default=None)
        stale_days = [d for d in selected_days if d in days and
                      now - days[d] > (STALE_SECONDS if d >= recent_start.isoformat()
                                       else HISTORICAL_STALE_SECONDS)]
        reasons = []
        if limited:
            reasons.append('Limite de leitura atingido; totais não calculados')
        if not current['complete'] or not previous['complete']:
            reasons.append('Cobertura incompleta em um dos períodos')
        if current['invalid'] or previous['invalid'] or current['unallocated_dates']:
            reasons.append('Problema de integridade dos pedidos')
        if shop.get('status') != 'ativa':
            reasons.append('Conexão inativa')
        if last is None or stale_days:
            reasons.append('Sincronização dos períodos desatualizada (3h recentes / 48h históricos)')
        if any(e.get('quando') is None or e['quando'] >= (last or 0) for e in by_error[cid]):
            reasons.append('Erro de sincronização sem resolução confirmada')
        eligible = not reasons and current['revenue'] is not None and previous['revenue'] is not None
        pct = change(current['revenue'], previous['revenue']) if eligible else None
        report = dict(shop=shop, current=current, previous=previous, eligible=eligible,
                      reasons=reasons, change=pct, last_sync=last, limited=limited)
        reports.append(report)
        if not eligible:
            alerts.append(dict(cid=cid, name=shop['cliente'], kind='sync',
                               text='; '.join(reasons), impact=None))
            continue
        impact = max(previous['revenue'] - current['revenue'], Decimal(0))
        if pct is not None and pct <= -15:
            alerts.append(dict(cid=cid, name=shop['cliente'], kind='revenue',
                               text=f'Faturamento caiu {abs(pct):.1f}%', impact=impact))
        orders_pct = change(current['orders'], previous['orders'])
        if (orders_pct is not None and orders_pct <= -20 and
                previous['orders'] - current['orders'] >= 5):
            alerts.append(dict(cid=cid, name=shop['cliente'], kind='orders',
                               text=f'Pedidos caíram {abs(orders_pct):.1f}% '
                                    f"({previous['orders'] - current['orders']} pedidos)", impact=impact))
    cohort = [r for r in reports if r['eligible']]
    totals = {}
    for which in ('current', 'previous'):
        revenue = sum((r[which]['revenue'] for r in cohort), Decimal(0)) if cohort else None
        orders = sum(r[which]['orders'] for r in cohort) if cohort else None
        totals[which] = dict(revenue=revenue, orders=orders,
                             ticket=revenue / orders if orders else None)
    alerts.sort(key=lambda a: (a['impact'] is None, -(a['impact'] or 0), a['name'].casefold(), a['kind']))
    return dict(reports=reports, alerts=alerts, totals=totals, included=len(cohort),
                excluded=len(shops)-len(cohort), bounds=bounds, limited=limited)


def variation(current, previous):
    pct = change(current, previous)
    if pct is not None:
        return f'{pct:+.1f}%'
    if current is not None and previous == 0:
        return 'Sem base percentual'
    return 'Indisponível'


STYLE = """<style>
.overview-hero{background:#122d3b;color:white;border-radius:18px;padding:28px;margin-bottom:20px}
.overview-hero h2{color:white;margin:4px 0 12px;font-size:30px}.overview-hero p{color:#cbdce3}
.overview-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:20px 0}
.overview-kpis .stat{border-top:4px solid #159f88}.overview-kpis .num{font-size:28px}
.overview-table td,.overview-table th{padding:14px 12px;text-align:left;vertical-align:top}
.overview-table{width:100%}.overview-alert{border-left:4px solid #db9630;padding:14px;margin:10px 0;background:#fff8eb}
.overview-status{font-size:12px;color:#6b7280;display:block;margin-top:5px}
.overview-actions{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}
@media(max-width:700px){.overview-kpis{grid-template-columns:1fr}.overview-hero{padding:18px}}
</style>"""


def overview_layout(shops, body, admin=False):
    """Keep authorized accounts reachable even when the report cannot load."""
    menu = "<nav class='menu-lateral' aria-label='Contas conectadas'>"
    menu += "<a class='item atual' href='/painel' aria-current='page'>Visão Geral</a>"
    menu += "<div class='voltar' style='margin-top:14px'>Contas conectadas</div>"
    for shop in shops:
        color = '#1a9d5c' if shop.get('status') == 'ativa' else '#d64545'
        menu += ("<a class='item' href='/painel/" + str(int(shop['id'])) + "'>"
                 "<span aria-hidden='true' style='display:inline-block;width:8px;"
                 "height:8px;border-radius:50%;margin-right:8px;background:"
                 + color + "'></span>" + escape(str(shop['cliente'])) + "</a>")
    if admin:
        menu += "<hr><a class='item' href='/usuarios'>Usuários</a>"
        menu += "<a class='item' href='/diagnostico'>Diagnóstico</a>"
    menu += "</nav>"
    return "<div class='layout'>" + menu + "<div class='conteudo'>" + body + "</div></div>"


def render_overview(data, args, admin=False):
    start, end, prev_start, prev_end = data['bounds']
    out = STYLE + "<section class='overview-hero'><small>KEIPER CONSULTORIA · CENTRAL ADMINISTRATIVA</small>"
    out += "<h2>Visão Geral 2.0</h2><p>Desempenho das lojas às quais você tem acesso.</p></section>"
    out += filters(None, args, action='/painel')
    out += (f"<p>{start:%d/%m/%Y} a {end:%d/%m/%Y} · Anterior: "
            f"{prev_start:%d/%m/%Y} a {prev_end:%d/%m/%Y}</p>"
            f"<div class='aviso'><b>{data['included']} de {len(data['reports'])} lojas na consolidação.</b> "
            f"{data['excluded']} excluída(s). Os dois períodos usam as mesmas lojas com dados "
            "completos, íntegros e sincronização recente. Estes valores não incluem as lojas excluídas.</div>")
    out += "<div class='overview-kpis'>"
    for key, title, money in (('revenue','Faturamento de vendas pagas',True),
                               ('orders','Pedidos pagos',False), ('ticket','Ticket médio por pedido',True)):
        value, previous = data['totals']['current'][key], data['totals']['previous'][key]
        out += ("<div class='stat'><div class='lab'>" + title + "</div><div class='num'>"
                + fmt(value,money) + "</div><p>Anterior: " + fmt(previous,money)
                + " · " + variation(value,previous) + "</p></div>")
    out += "</div><section class='card'><h2>Atenção às lojas</h2>"
    if not data['alerts']:
        out += "<p>Nenhum alerta pelos critérios atuais.</p>"
    for a in data['alerts']:
        impact = 'Impacto financeiro não estimado' if a['impact'] is None else 'Queda de faturamento no período: ' + fmt(a['impact'],True)
        out += (f"<div class='overview-alert'><a class='link' href='/painel/{a['cid']}'>"
                + escape(a['name']) + "</a> · " + escape(a['text'])
                + "<span class='overview-status'>" + impact + "</span></div>")
    out += "</section><section class='card'><h2>Desempenho por loja</h2><div style='overflow-x:auto'>"
    out += "<table class='overview-table'><thead><tr><th>Loja</th><th>Faturamento</th><th>Pedidos</th><th>Ticket médio</th><th>Variação de faturamento</th><th>Painel</th></tr></thead><tbody>"
    for r in data['reports']:
        s, cur = r['shop'], r['current']
        # A capped batch is not a usable subtotal even for an apparently complete shop.
        value = lambda key: None if r['limited'] else cur[key]
        status = 'Incluída na consolidação' if r['eligible'] else 'Fora da consolidação: ' + '; '.join(r['reasons'])
        out += (f"<tr><td><b id='nome-{s['id']}'>" + escape(s['cliente']) + "</b><span class='overview-status'>"
                + escape(status) + "</span></td><td>" + fmt(value('revenue'),True)
                + "</td><td>" + fmt(value('orders'),False) + "</td><td>" + fmt(value('ticket'),True)
                + "</td><td>" + (variation(cur['revenue'],r['previous']['revenue']) if r['eligible'] else 'Indisponível')
                + f"</td><td><a class='link' href='/painel/{s['id']}'>Abrir painel</a> "
                + f"<a class='link' href='#' onclick='editarNome({s['id']});return false'>Renomear</a></td></tr>")
    if not data['reports']:
        out += "<tr><td colspan='6'>Nenhuma loja disponível. Conecte uma loja para começar.</td></tr>"
    out += ("</tbody></table></div></section><details class='card'><summary>Critérios e limites</summary>"
            "<p>Faturamento: pedidos pagos com pagamento aprovado em BRL, por criação em Brasília. "
            "Hoje está em andamento. Ticket consolidado = faturamento total ÷ pedidos totais.</p>"
            "<p>Queda de faturamento: pelo menos 15%. Queda de pedidos: pelo menos 20% e 5 pedidos. "
            "Somente lojas elegíveis geram alertas de queda. Base anterior zero não gera queda percentual.</p>"
            "<p>Sincronização: conexão inativa, cobertura ausente, campos inválidos, pedidos sem data "
            "localizável, erro de coleta não superado ou dia da seleção com busca há mais "
            "de 3 horas (últimos 7 dias) ou 48 horas (histórico). Atualizações fora da seleção "
            "não validam seus dados; erros exigem sucesso posterior em todos os dias selecionados. "
            "Alertas são ordenados por queda absoluta do faturamento quando conhecida; os demais "
            "não têm impacto estimado. Alertas da mesma loja não devem ser somados.</p>"
            "<p>Consolidação dos pedidos verificados nos períodos selecionados, sem corte de totais. "
            "Datas não localizáveis continuam sinalizadas. A coleta automática cobre até "
            "180 dias e a carga inicial é gradual.</p></details>")
    out += "<nav class='overview-actions'><a class='btn-acoes cinza' href='/painel/legado'>Visão anterior e recursos existentes</a>"
    if admin:
        out += "<a class='btn-acoes cinza' href='/usuarios'>Usuários</a><a class='btn-acoes cinza' href='/diagnostico'>Diagnóstico</a>"
    return out + "</nav>"
