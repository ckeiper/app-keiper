"""Temporal comparison of observed Full stock and verified listing sales."""
from collections import defaultdict
from datetime import datetime, timedelta
from html import escape

from sales_metrics import SAO_PAULO, period, reporting_today, created_day
from listing_sales import listing_sales_summary

from full_sales_view_chart import LABELS, chart


def daily_comparison(item_id, start, end, observations, orders, items, coverage, legacy=False):
    by_day = defaultdict(list)
    for row in observations:
        if row.get('item_id') == item_id:
            day = datetime.fromtimestamp(row['observed_at'], SAO_PAULO).date()
            if start <= day <= end:
                by_day[day].append(row)
    order_days, item_days, order_keys, unlocated = defaultdict(list), defaultdict(list), {}, []
    for order in orders:
        date = created_day(order.get('criado_em'))
        key = (order.get('conexao_id'), str(order.get('pedido_id')))
        if date is None:
            unlocated.append(order)
        else:
            order_days[date].append(order)
            order_keys[key] = date
    for item in items:
        date = order_keys.get((item.get('conexao_id'),str(item.get('pedido_id'))))
        if date is not None:
            item_days[date].append(item)
    output, day = [], start
    while day <= end:
        snapshots = by_day[day]
        states = {s['state'] for s in snapshots}
        state = ('unknown' if not states or 'unknown' in states else
                 next(iter(states)) if len(states) == 1 else 'mixed')
        sales = listing_sales_summary(order_days[day] + unlocated, item_days[day], coverage, item_id, end=day, days=1)
        if legacy or day >= reporting_today():
            sales.update(units=None, orders=None,
                         reason='Dia em andamento ou pedidos ainda não verificados.')
        output.append(dict(day=day.isoformat(), state=state, observations=len(snapshots),
                           units=sales['units'], reason=sales['reason']))
        day += timedelta(days=1)
    return output


def render_full(cid, args, listing, observations, orders, items, coverage, first, legacy=False):
    start, end, _, _ = period(args)
    if (end-start).days >= 180:
        raise ValueError('Selecione no máximo 180 dias para comparar Full e vendas.')
    args = dict(args,item_id=listing['item_id'])
    days = daily_comparison(listing['item_id'], start, end, observations, orders, items, coverage, legacy)
    title = escape(str(listing.get('titulo') or listing['item_id']))
    from full_report_components import PAGE_KEYS, STYLE, render_snapshot, render_summary
    out = STYLE + (f"<section class='full-report'><header class='full-report-item'><h3>{title}</h3>"
                   f"<small>{escape(listing['item_id'])}</small></header>")
    if not observations:
        note = 'Nenhuma consulta Full neste período.' if first and first.get('first') is not None else 'Ainda não há coletas Full para este anúncio.'
        out += f'<p>{note}</p>'
    out += chart(days)
    out += "<p>O estoque Full reflete as consultas registradas em cada dia.</p>"
    details_open = ' open' if any(args.get(key) for key in (*PAGE_KEYS, 'full_variacao')) else ''
    out += f"<details class='card full-report-details'{details_open}><summary>Dados e consultas do período</summary>"
    out += "<details class='card'><summary>Cobertura e primeira coleta</summary>"
    if first and first.get('first') is not None:
        stamp = datetime.fromtimestamp(first['first'], SAO_PAULO).strftime('%d/%m/%Y %H:%M')
        out += '<p>Primeira coleta registrada: ' + stamp + ' (Brasília).</p>'
        if first.get('first_known') is not None:
            confirmed = datetime.fromtimestamp(first['first_known'], SAO_PAULO).strftime('%d/%m/%Y %H:%M')
            out += '<p>Primeira confirmação de estoque Full: ' + confirmed + ' (Brasília). A cobertura é por consulta, sem histórico contínuo.</p>'
        else:
            out += '<p>Ainda não houve confirmação de estoque Full pela API.</p>'
    elif observations:
        out += '<p>Há observações no período selecionado; a data da primeira coleta histórica não está disponível.</p>'
    else:
        out += '<p>Ainda não há coletas Full. O histórico começará na próxima sincronização desta loja.</p>'
    out += ("<p>As vendas são do anúncio. Registramos o estoque Full nas consultas e não preenchemos o intervalo entre elas. "
            "O total de vendas do dia atual fica disponível após o fechamento e a verificação.</p>")
    out += render_summary(days)
    out += '</details>'
    out += render_snapshot(cid,args,listing,observations,start,end)
    from full_variation_history import render as render_variation_history
    out += render_variation_history(cid,args,listing,observations,start,end)
    return out + '</details></section>'
