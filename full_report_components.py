"""Presentation helpers for cached Full history, with no reads or stock allocation."""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from html import escape
import re
from urllib.parse import urlencode
from sales_metrics import SAO_PAULO
from full_monitor import METADATA_MAX_AGE

PAGE_KEYS = ('full_dias', 'full_consultas', 'full_variacoes')


def paginate(rows, cid, args, key, size, anchor):
    pages = max(1, (len(rows) + size - 1) // size)
    try:
        page = max(1, min(pages, int(args.get(key, '1'))))
    except (TypeError, ValueError):
        page = 1
    params = {k: str(args[k]) for k in ('item_id','periodo','inicio','fim') + PAGE_KEYS if k in args}
    nav = '<nav class="full-pages" aria-label="Paginação de ' + anchor + '">Página ' + str(page) + ' de ' + str(pages)
    for label, target in [('Anterior', page - 1), ('Próxima', page + 1)]:
        if 1 <= target <= pages:
            params[key] = str(target)
            url = '/full/' + str(int(cid)) + '?' + urlencode(params) + '#' + anchor
            nav += ' <a href="' + escape(url, quote=True) + '">' + label + '</a>'
    return rows[(page - 1) * size:page * size], nav + '</nav>'


def snapshot(observations, item_id, start, end):
    lower = int(datetime.combine(start,time.min,SAO_PAULO).timestamp())
    upper = int(datetime.combine(end+timedelta(days=1),time.min,SAO_PAULO).timestamp())
    selected = [r for r in observations if r.get('item_id') == item_id
                and type(r.get('observed_at')) is int and lower <= r['observed_at'] < upper]
    pending = dict(rows=[], reason='Sem vínculo e consulta de inventário confirmados na última observação do período.', stamp=None, partial=True)
    if not selected:
        return pending
    latest = max(r['observed_at'] for r in selected)
    selected = [r for r in selected if r['observed_at'] == latest]
    pending['stamp'] = latest
    if len(selected) != 1:
        return pending
    evidence = selected[0].get('evidence')
    if not isinstance(evidence, dict):
        return pending
    meta = evidence.get('metadata')
    if not isinstance(meta, dict):
        return pending
    stamp = meta.get('collected_at')
    if (type(stamp) is not int or not 0 <= latest - stamp <= METADATA_MAX_AGE
            or meta.get('logistics') != 'fulfillment'):
        return pending
    mappings = meta.get('inventories')
    readings = evidence.get('inventories')
    if not isinstance(mappings, list) or not isinstance(readings, list):
        return pending
    mappings = [r for r in mappings if isinstance(r, dict)]
    inventory_counts = Counter(r.get('inventory_id') for r in mappings if isinstance(r.get('inventory_id'),str))
    variation_counts = Counter(str(r.get('variation_id')) for r in mappings)
    by_inventory = defaultdict(list)
    for row in readings:
        if isinstance(row, dict) and isinstance(row.get('inventory_id'), str):
            by_inventory[row['inventory_id']].append(row)
    result = []
    for row in mappings:
        inventory, variation = row.get('inventory_id'), row.get('variation_id')
        quantity, reason = None, 'Consulta não confirmada'
        valid_id = isinstance(inventory, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', inventory)
        valid_variation = variation is None or (type(variation) is int and variation > 0)
        if not valid_id or not valid_variation:
            reason = 'Vínculo inválido'
        elif inventory_counts[inventory] != 1 or variation_counts[str(variation)] != 1:
            reason = 'Vínculo compartilhado ou duplicado; sem atribuição por variação'
        else:
            matches = by_inventory[inventory]
            if len(matches) == 1:
                reading = matches[0]
                value = reading.get('quantity')
                if type(value) is int and value >= 0 and not reading.get('reason'):
                    quantity = value
                    reason = 'Quantidade confirmada nesta consulta'
                else:
                    reason = str(reading.get('reason') or reason)
            elif len(matches) > 1:
                reason = 'Consultas duplicadas; quantidade não confirmada'
        result.append(dict(variation=str(variation) if valid_variation and variation is not None else 'Sem código confirmado',
                           inventory=inventory if isinstance(inventory,str) else 'Não disponível', quantity=quantity, reason=reason))
    return dict(rows=result, stamp=latest, partial=bool(evidence.get('partial') or meta.get('missing')),
                reason=pending['reason'] if not result else None)


def render_snapshot(cid,args,listing,observations,start,end):
    model = snapshot(observations,listing['item_id'],start,end)
    out = '<details class="card full-variations" id="full-variacoes"' + (' open' if args.get('full_variacoes') else '') + '><summary>Inventários e variações na última observação do período</summary>'
    if model['stamp'] is not None:
        out += '<p>Observação: ' + datetime.fromtimestamp(model['stamp'],SAO_PAULO).strftime('%d/%m/%Y %H:%M:%S') + ' · Brasília. Leitura histórica selecionada; não comprova o saldo atual.</p>'
    if not model['rows']:
        return out + '<p>' + model['reason'] + ' Uma leitura anterior não substitui essa pendência.</p></details>'
    rows, nav = paginate(model['rows'],cid,args,'full_variacoes',20,'full-variacoes')
    out += '<div class="full-table-scroll" tabindex="0" role="region" aria-label="Inventários e variações Full"><table><thead><tr><th scope="col">Variação</th><th scope="col">Inventário</th><th scope="col">Quantidade observada</th><th scope="col">Confirmação</th></tr></thead><tbody>'
    for row in rows:
        out += '<tr><th scope="row">' + escape(row['variation']) + '</th><td>' + escape(row['inventory']) + '</td><td>' + (str(row['quantity']) if row['quantity'] is not None else 'Indisponível') + '</td><td>' + escape(row['reason']) + '</td></tr>'
    out += '</tbody></table></div>' + nav
    if model['partial']:
        out += '<p>Coleta ou metadados incompletos: as linhas disponíveis não representam todas as variações.</p>'
    return out + '<p>Não some inventários compartilhados nem atribua o saldo do anúncio a cada variação. Zero confirmado é zero; ausência ou falha fica indisponível. Os códigos são os registrados na coleta, sem inferir cor, tamanho ou SKU.</p></details>'


def render_summary(days):
    values = [('Dias com vendas verificadas',sum(d['units'] is not None for d in days)),
              ('Dias com estado Full conhecido',sum(d['state'] in ('available','empty') for d in days)),
              ('Dias observados com estoque Full',sum(d['state']=='available' for d in days)),
              ('Dias observados sem estoque Full',sum(d['state']=='empty' for d in days))]
    return '<div class="full-summary">' + ''.join('<article><strong>' + str(value) + '/' + str(len(days)) + '</strong><small>' + label + '</small></article>' for label,value in values) + '</div><p>Dias sem leitura, com consulta desconhecida ou divergente não entram como estado Full conhecido. As contagens descrevem consultas diárias, não duração de disponibilidade.</p>'


STYLE='''<style>
body .conteudo .full-report{background:#102238;color:#eaf2ff;border:1px solid #34516e;border-radius:15px;padding:20px;margin:18px 0;max-width:100%;min-width:0;box-sizing:border-box}body .conteudo .full-report :is(h2,h3,b,summary){color:#eaf2ff}.full-report p,.full-report small{font-size:12px;line-height:1.7;color:#bdcce1}.full-report .card{background:#182e49;color:#eaf2ff;border:1px solid #426184;box-shadow:none;min-width:0}.full-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}.full-summary article{background:#182e49;border:1px solid #426184;border-radius:10px;padding:14px;display:grid;gap:8px;overflow-wrap:anywhere}.full-summary strong{font-size:22px}.full-summary small{display:block}.full-report summary{cursor:pointer;padding:10px 0;font-weight:700}.full-table-scroll,.full-chart-scroll{overflow-x:auto;max-width:100%;min-width:0}.full-report table{min-width:750px;width:100%;border-collapse:collapse}.full-report th,.full-report td{padding:12px;border-bottom:1px solid #426184;text-align:left;vertical-align:top;font-size:12px;overflow-wrap:anywhere;max-width:400px}body .conteudo .full-report :is(th,td){background:#182e49;color:#eaf2ff}.full-report svg text{fill:#dcecff}.full-pages{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;margin:16px 0}body .conteudo .full-report a{color:#b9e5ff;text-decoration:none}.full-report :focus-visible{outline:3px solid #85c8ec;outline-offset:3px}@media(max-width:700px){.full-summary{grid-template-columns:repeat(2,minmax(0,1fr))}body .conteudo .full-report{padding:14px}}
</style>'''
