"""Temporal comparison of observed Full stock and verified listing sales."""
from collections import defaultdict
from datetime import datetime, timedelta
from html import escape
from urllib.parse import urlencode

from sales_metrics import SAO_PAULO, period, reporting_today, created_day
from listing_sales import listing_sales_summary

LABELS = dict(available='Com estoque Full', empty='Sem estoque Full',
              unknown='Desconhecido', mixed='Consultas divergentes')
COLORS = dict(available='#15803d', empty='#c2410c', unknown='#64748b', mixed='#7e22ce')


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


def chart(days):
    width, left, base = max(850, len(days) * 25 + 200), 55, 205
    maximum = max([d['units'] or 0 for d in days] + [1])
    right = width - 130
    step = (right - left) / max(1, len(days))
    out = ("<div class='full-chart-scroll' tabindex='0' role='region' aria-label='Gráfico Full com rolagem'><svg xmlns='http://www.w3.org/2000/svg' "
           "role='img' aria-label='Unidades vendidas e observações de estoque Full por dia' "
           f"viewBox='0 0 {width} 315' style='min-width:{width}px;width:100%'>"
           "<title>Barras de vendas e linha de disponibilidade Full observada, com lacunas</title>"
           "<text x='8' y='18' font-size='13'>Unidades vendidas</text>"
           f"<text x='8' y='40' font-size='12'>Máx. {maximum}</text>"
           f"<path d='M{left} 45 V{base} H{right} V45' fill='none' stroke='#94a3b8'/>"
           f"<text x='{right+10}' y='18' font-size='12'>Full observado</text>"
           f"<text x='{right+10}' y='59' font-size='12'>Com estoque</text>"
           f"<text x='{right+10}' y='199' font-size='12'>Sem estoque</text>")
    line, markers, connected = [], [], False
    for i, d in enumerate(days):
        x = left + step * (i + .5)
        label = f"{d['day']}: " + (str(d['units']) + ' unidades' if d['units'] is not None else 'vendas indisponíveis')
        label += '; ' + LABELS[d['state']] + '; ' + str(d['observations']) + ' consultas'
        if d['units'] is not None:
            height = d['units'] / maximum * 150
            out += f"<rect x='{x-step*.3:.2f}' y='{base-height:.2f}' width='{step*.6:.2f}' height='{height:.2f}' fill='#2563eb'><title>{escape(label)}</title></rect>"
        else:
            out += f"<text x='{x:.2f}' y='195' text-anchor='middle' fill='#64748b'>—<title>{escape(label)}</title></text>"
        if d['state'] in ('available','empty'):
            y = 55 if d['state'] == 'available' else 195
            line.append(('L' if connected else 'M') + f'{x:.2f},{y}')
            connected = True
            markers.append(f"<circle cx='{x:.2f}' cy='{y}' r='5' fill='{COLORS[d['state']]}' stroke='white'><title>{escape(label)}</title></circle>")
        else:
            connected = False
            markers.append(f"<text x='{x:.2f}' y='227' text-anchor='middle' fill='{COLORS[d['state']]}' font-size='15'>?<title>{escape(label)}</title></text>")
        if len(days) <= 15 or i % max(1, len(days)//12) == 0:
            out += f"<text x='{x:.2f}' y='250' text-anchor='middle' font-size='11'>{d['day'][8:]}/{d['day'][5:7]}</text>"
    out += "<path data-series='full-availability' d='" + ' '.join(line) + "' fill='none' stroke='#15803d' stroke-width='3'/>"
    return out + ''.join(markers) + '</svg></div>'


def render_full(cid, args, listing, observations, orders, items, coverage, first, legacy=False):
    start, end, _, _ = period(args)
    if (end-start).days >= 180:
        raise ValueError('Selecione no máximo 180 dias para comparar Full e vendas.')
    days = daily_comparison(listing['item_id'], start, end, observations, orders, items, coverage, legacy)
    title = escape(str(listing.get('titulo') or listing['item_id']))
    from full_report_components import STYLE, paginate, render_snapshot, render_summary
    out = STYLE + f"<section class='full-report'><h2>Full e vendas por anúncio</h2><div class='card'><h3>{title}</h3><p>{escape(listing['item_id'])}</p>"
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
    out += ("<p>O gráfico compara vendas do anúncio com o estoque Full observado nas consultas de cada dia. "
            "Logística Full e estoque disponível são informações distintas. Não atribuímos as vendas ao Full "
            "nem preenchemos o intervalo entre consultas. A linha liga os estados diários observados e usa "
            "o eixo à direita; não informa o instante de uma mudança nem garante estoque durante o dia inteiro. "
            "Dias sem informação confiável interrompem a linha.</p></div>")
    out += render_summary(days)
    out += render_snapshot(cid,args,listing,observations,start,end)
    out += chart(days)
    out += "<div class='card'><p>Barras azuis: unidades vendidas (eixo esquerdo). Linha verde: disponibilidade Full (eixo direito). Pontos verdes: com estoque; laranja: sem estoque. ? indica consulta desconhecida ou divergente, com interrupção da linha.</p>"
    out += "<p>O dia atual fica sem total de vendas fechado. Ausência de vendas verificadas é uma lacuna, não zero. Comparação observacional, sem comprovar causa e efeito.</p>"
    selected_days, day_pages = paginate(days,cid,args,'full_dias',20,'full-dias')
    out += '<h3 id="full-dias">Vendas e observações por dia</h3><p>Deslize as tabelas no celular para conferir todas as colunas.</p><div class="full-table-scroll full-days-scroll" tabindex="0" role="region" aria-label="Histórico diário Full"><table><thead><tr><th>Dia</th><th>Unidades vendidas</th><th>Full nas consultas do dia</th><th>Consultas</th></tr></thead><tbody>'
    for d in selected_days:
        value = str(d['units']) if d['units'] is not None else 'Indisponível'
        out += '<tr><td>' + d['day'] + '</td><td title="' + escape(d['reason'] or '', quote=True) + '">' + value + '</td><td>' + LABELS[d['state']] + '</td><td>' + str(d['observations']) + '</td></tr>'
    out += '</tbody></table></div>' + day_pages + '</div>'
    selected_reads, read_pages = paginate(sorted(observations,key=lambda row:row["observed_at"],reverse=True),cid,args,'full_consultas',30,'full-consultas')
    out += '<details class="card full-reads" id="full-consultas"' + (' open' if args.get('full_consultas') else '') + '><summary>Consultas e rastreabilidade</summary><p>Mais recentes primeiro; trinta consultas por página.</p><div class="full-table-scroll" tabindex="0" role="region" aria-label="Consultas Full registradas"><table><thead><tr><th>Quando (Brasília)</th><th>Estoque Full</th><th>Quantidade</th><th>Logística do anúncio</th><th>Detalhes oficiais</th></tr></thead><tbody>'
    for row in selected_reads:
        stamp = datetime.fromtimestamp(row['observed_at'], SAO_PAULO).strftime('%d/%m/%Y %H:%M:%S')
        logistics = {'fulfillment':'Full', 'other':'Outra logística', 'unknown':'Desconhecida'}.get(row['logistics'], 'Desconhecida')
        evidence = row.get('evidence') if isinstance(row.get('evidence'),dict) else {}
        details = [str(evidence.get('reason') or '')]
        inventories = evidence.get('inventories')
        for inv in inventories if isinstance(inventories,list) else []:
            if not isinstance(inv,dict):
                continue
            value = inv.get('quantity')
            detail = str(value) if type(value) is int and value >= 0 and not inv.get('reason') else str(inv.get('reason') or 'Desconhecido')
            details.append(str(inv.get('inventory_id') or 'Inventário não identificado') + ': ' + detail)
        quantity = str(row['quantity']) if type(row.get('quantity')) is int and row['quantity'] >= 0 else 'Não disponível'
        out += '<tr><td>' + stamp + '</td><td>' + LABELS[row['state']] + '</td><td>' + quantity + '</td><td>' + logistics + '</td><td>' + escape('; '.join(filter(None, details))) + '</td></tr>'
    return out + '</tbody></table></div>' + read_pages + '</details></section>'
