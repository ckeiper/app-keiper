"""Descriptive ABC concentration from verified same-store listing gross values."""
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from html import escape
from itertools import groupby
from urllib.parse import urlencode

from freight_comparison import format_brl

CLASSES = {'todos': 'Todas as classes', 'A': 'Classe A', 'B': 'Classe B',
           'C': 'Classe C', 'sem_valor': 'Sem valor bruto'}


def classify(values):
    """Keep equal-value groups together; the group crossing a cutoff stays in it."""
    total = sum(values.values(), Decimal(0))
    result = {}
    cumulative = Decimal(0)
    ordered = sorted(values, key=lambda item: (-values[item], item))
    for value, group in groupby(ordered, key=values.get):
        ids = list(group)
        category = ('sem_valor' if value == 0 else
                    'A' if cumulative * 100 < total * 80 else
                    'B' if cumulative * 100 < total * 95 else 'C')
        for item in ids:
            cumulative += value
            result[item] = dict(category=category, value=value,
                                share=value * 100 / total if total else None)
    return dict(total=total, rows=result)


def build(ranking):
    pending = dict(available=False, reason='A curva ABC aguarda cobertura e vendas verificadas nos dois períodos. Dados incompletos não são zero.')
    if not ranking.get('available'):
        return pending
    values = {'current': {}, 'previous': {}}
    for item, metrics in (ranking.get('rows') or {}).items():
        if not re.fullmatch(r'MLB[0-9]{1,20}', str(item)):
            return pending
        for period, key in [('current', 'value'), ('previous', 'previous_value')]:
            raw = metrics.get(key)
            if raw is None or isinstance(raw, bool):
                return pending
            try:
                value = Decimal(str(raw))
            except (ValueError, TypeError, InvalidOperation):
                return pending
            if not value.is_finite() or value < 0:
                return pending
            values[period][item] = value
    result = {period: classify(rows) for period, rows in values.items()}
    result['available'] = True
    return result


def render(cid, ranking, listings, args, end, days=7):
    esc = lambda value: escape(str(value), quote=True)
    model = build(ranking)
    out = STYLE + '<section class="abc" id="abc-anuncios" aria-label="Curva ABC de anúncios"><h3>Curva ABC por valor bruto</h3>'
    if not model['available']:
        return out + '<p role="status">' + esc(model['reason']) + '</p></section>'
    current, previous = model['current'], model['previous']
    names = {str(row['item_id']): str(row.get('titulo') or row['item_id']) for row in listings}
    selected = args.get('abc_classe', 'todos')
    if selected not in CLASSES:
        selected = 'todos'
    search = str(args.get('abc_busca', '')).strip()[:120]
    ordered = sorted(current['rows'], key=lambda item: (-current['rows'][item]['value'], item))
    ids = [item for item in ordered if (selected == 'todos' or current['rows'][item]['category'] == selected)
           and (not search or search.casefold() in (names.get(item, item) + ' ' + item).casefold())]
    pages = max(1, (len(ids) + 19) // 20)
    try:
        page = max(1, min(pages, int(args.get('abc_pagina', '1'))))
    except (TypeError, ValueError):
        page = 1
    path = '/ranking-anuncios/' + str(int(cid))
    preserved = {'dias': str(days)}
    for i in range(1, 5):
        key = 'comparar' + str(i)
        value = str(args.get(key, '')).strip().upper()
        if re.fullmatch(r'MLB[0-9]{1,20}', value):
            preserved[key] = value
    start = end - timedelta(days=days - 1)
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    out += '<p>Atual: ' + start.strftime('%d/%m/%Y') + ' a ' + end.strftime('%d/%m/%Y') + ' · Anterior: ' + previous_start.strftime('%d/%m/%Y') + ' a ' + previous_end.strftime('%d/%m/%Y') + '.</p>'
    out += '<div class="abc-cards">'
    for category in ['A', 'B', 'C', 'sem_valor']:
        group = [row for row in current['rows'].values() if row['category'] == category]
        value = sum((row['value'] for row in group), Decimal(0))
        share = value * 100 / current['total'] if current['total'] else None
        out += '<div class="abc-card"><b>' + esc(CLASSES[category]) + '</b><strong>' + str(len(group)) + (' anúncio' if len(group) == 1 else ' anúncios') + '</strong><span>' + esc(format_brl(value)) + '</span><small>' + ('Sem base percentual' if share is None else format(share, '.2f').replace('.', ',') + '% do valor bruto') + '</small></div>'
    out += '</div><p>Total verificado: ' + esc(format_brl(current['total'])) + ' no período atual e ' + esc(format_brl(previous['total'])) + ' no anterior. Cards e classes usam a base completa, mesmo ao filtrar a lista.</p>'
    out += '<form class="abc-form" method="get" action="' + path + '#abc-anuncios">'
    out += ''.join('<input type="hidden" name="' + key + '" value="' + esc(value) + '">' for key, value in preserved.items())
    out += '<label>Classe atual<select name="abc_classe">' + ''.join('<option value="' + key + '"' + (' selected' if selected == key else '') + '>' + label + '</option>' for key, label in CLASSES.items()) + '</select></label><label>Nome ou código<input name="abc_busca" maxlength="120" value="' + esc(search) + '"></label><button>Filtrar</button><a href="' + path + '?' + esc(urlencode(preserved)) + '#abc-anuncios">Limpar filtros</a></form>'
    if not ids:
        out += '<p role="status">Nenhum anúncio corresponde aos filtros.</p>'
    else:
        out += '<p>Deslize a tabela no celular para conferir todas as colunas.</p><div class="abc-scroll" tabindex="0" role="region" aria-label="Classificação ABC com rolagem"><table><thead><tr><th scope="col">Anúncio</th><th scope="col">Classe anterior → atual</th><th scope="col">Valor bruto atual</th><th scope="col">Participação atual</th></tr></thead><tbody>'
        for item in ids[(page - 1) * 20:page * 20]:
            row = current['rows'][item]
            before = previous['rows'][item]
            label = lambda category: 'Sem valor' if category == 'sem_valor' else category
            before_label = label(before['category']) if previous['total'] else 'Sem base anterior'
            out += '<tr><th scope="row"><a href="/diagnostico/' + str(int(cid)) + '/' + item + '">' + esc(names.get(item, item)) + '</a><small>' + item + '</small></th><td>' + before_label + ' → ' + label(row['category']) + '</td><td>' + esc(format_brl(row['value'])) + '</td><td>' + ('Sem base percentual' if row['share'] is None else format(row['share'], '.2f').replace('.', ',') + '%') + '</td></tr>'
        out += '</tbody></table></div>'
    out += '<nav class="abc-pages" aria-label="Paginação da curva ABC">' + str(len(ids)) + (' anúncio' if len(ids) == 1 else ' anúncios') + ' · Página ' + str(page) + ' de ' + str(pages)
    for title, target in [('Anterior', page - 1), ('Próxima', page + 1)]:
        if 1 <= target <= pages:
            params = dict(preserved, abc_classe=selected, abc_busca=search, abc_pagina=str(target))
            out += ' <a href="' + path + '?' + esc(urlencode(params)) + '#abc-anuncios">' + title + '</a>'
    return out + '</nav><details><summary>Critério e limites da classificação</summary><p>Ordenação pelo valor bruto decrescente. A inclui o grupo que alcança ou ultrapassa 80%; B segue até alcançar ou ultrapassar 95%; C contém o restante com valor positivo. Empates ficam na mesma classe, por isso os limites podem ser ultrapassados e uma classe pode ficar vazia. Valor zero fica separado em Sem valor bruto e não comprova ausência de pedidos. Sem total positivo não há participação percentual. A classe anterior usa a distribuição própria do período anterior. Mudança de classe não comprova crescimento ou queda: depende também dos demais anúncios. Não mede lucro, margem, estoque ou prioridade de reposição.</p></details></section>'


STYLE = '''<style>
body .conteudo .abc{background:#102238;color:#eaf2ff;border:1px solid #34516e;border-radius:15px;padding:20px;margin:18px 0;max-width:100%;min-width:0;box-sizing:border-box}body .conteudo .abc h3{color:#eaf2ff;margin-top:0}.abc p,.abc small{color:#bdcce1;font-size:12px;line-height:1.7}.abc-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.abc-card{background:#182e49;border:1px solid #426184;border-radius:10px;padding:14px;display:grid;gap:8px;overflow-wrap:anywhere}.abc-card b{color:#a4d9ff;font-size:12px}.abc-card strong{font-size:18px}.abc-form{display:flex;flex-wrap:wrap;gap:12px;align-items:end}.abc-form label{display:grid;gap:6px;font-size:12px;min-width:0;flex:1 1 160px}.abc-form input,.abc-form select{box-sizing:border-box;min-width:0;width:100%;padding:11px;background:#0b192c;color:#eaf2ff;border:1px solid #426184;border-radius:8px}.abc-form button{padding:12px 18px;background:#287ac1;color:#fff;border:0;border-radius:8px;cursor:pointer}body .conteudo .abc a{color:#b9e5ff;text-decoration:none}.abc-scroll{overflow-x:auto;margin-top:16px;max-width:100%}.abc table{width:100%;min-width:650px;border-collapse:collapse}.abc th,.abc td{padding:13px;border-bottom:1px solid #426184;text-align:left;font-size:12px;overflow-wrap:anywhere;max-width:350px}body .conteudo .abc th,body .conteudo .abc td{background:#182e49;color:#eaf2ff}.abc small{display:block}.abc-pages{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;margin:16px 0}.abc summary{cursor:pointer;color:#b9e5ff;padding:10px 0}.abc :focus-visible{outline:3px solid #85c8ec;outline-offset:3px}@media(max-width:700px){.abc-cards{grid-template-columns:repeat(2,minmax(0,1fr))}body .conteudo .abc{padding:14px}}
</style>'''
