"""Tenant-scoped HTML and Excel views of the same unsold-listing results."""
from datetime import timedelta
from html import escape
from io import BytesIO
from urllib.parse import urlencode

from flask import redirect, request, send_file, session, url_for

from listing_image_selection import preview_url
from sales_metrics import reporting_today
from section_help import STYLE, section_help
from unsold_report import PERIODS, read_report


TITLE = 'Anúncios sem vendas nos últimos 30 dias'
PAGE_SIZE = 100
PATH = '/relatorios/anuncios-sem-vendas'
HEADERS = ('Anúncio', 'MLB', 'SKU', 'Estoque', 'Última venda registrada')
FILTERS = {
    'logistica': ('Logística', {'Full': 'Full', 'Flex': 'Flex', 'Outra': 'Outra', '?': 'Indisponível'}),
    'ads': ('Ads', {'sim': 'Com vínculo registrado', '?': 'Sem informação'}),
    'estoque': ('Estoque', {'sim': 'Com estoque', 'zero': 'Sem estoque', '?': 'Indisponível'}),
}
METHOD = ('<p>O relatório cruza os anúncios ativos da última sincronização com pedidos pagos e aprovados '
          'no Mercado Livre. A janela é móvel, inclui o dia atual até a coleta mais recente e usa o horário de Brasília.</p>'
          '<p>Para publicações recentes, a análise começa no dia da publicação. A última venda é a mais recente '
          'registrada no histórico disponível. As visitas só aparecem quando todos os dias aplicáveis têm registros. '
          'Ads mostra vínculos registrados com o anúncio. Ausência de vínculo no histórico é informação indisponível.</p>')


REPORT_STYLE = '''<style>
.report-hero .section-help{margin-bottom:0}
.report-toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:6px 0 16px}
.report-toolbar p{margin:0;font-size:.88rem;opacity:.82}
.report-filters,.report-cards{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(145px,100%),1fr))}
.report-filters{align-items:end}
.report-filters label{display:grid;gap:6px;font-size:.82rem;font-weight:600;min-width:0}
.report-filters select{width:100%;min-width:0;min-height:42px;border:1px solid #becbdf;border-radius:8px;background:#fff;color:#253b58;padding:0 10px;font:inherit;color-scheme:light}
.report-button{box-sizing:border-box;display:inline-flex;justify-content:center;align-items:center;min-height:42px;padding:8px 14px;border:1px solid #b8cbe5;border-radius:8px;background:#edf4ff;color:#174b8a;font:inherit;font-size:.84rem;font-weight:700;text-decoration:none;cursor:pointer}
.report-download,.report-download:hover{background:#145bb5;border-color:#145bb5;color:#fff}
.report-button:hover{filter:brightness(.96)}
.report-button:focus-visible,.report-filters select:focus-visible{outline:2px solid #5596ee;outline-offset:2px}
.report-cards .card{padding:16px 18px;font-size:.87rem}
.report-cards strong{display:block;font-size:1.5rem;margin-bottom:4px}
.report-table{overflow:auto;margin-top:12px}
.report-table th,.report-table td{white-space:nowrap}
.report-table td:first-child{min-width:200px;white-space:normal}
.report-table img{width:42px;height:42px;object-fit:contain;vertical-align:middle;margin-right:8px}
html[data-theme=dark] .report-filters select{background:#142940;color:#edf5ff;border-color:#496686;color-scheme:dark}
html[data-theme=dark] .report-button:not(.report-download){background:#213c5b;color:#edf5ff;border-color:#496686}
@media(max-width:640px){.report-toolbar .report-download{flex:1 0 100%}}
</style>'''


def e(value):
    return escape(str(value), quote=True)


def values(row):
    return row['titulo'], row['item_id'], row['sku'], row['quantidade'], row['last_sale']


def option_list(label, name, options, selected):
    options_html = ''.join(
        f"<option value='{e(key)}'{' selected' if str(key) == str(selected) else ''}>{e(text)}</option>"
        for key, text in options.items())
    return f"<label>{e(label)} <select name='{e(name)}'>{options_html}</select></label>"


def filtered(rows, args):
    for row in rows:
        stock = row['quantidade']
        states = {'categoria': row['categoria_id'] or '?',
                  'logistica': row['logistics'] or '?',
                  'ads': 'sim' if row['ads'] else '?',
                  'estoque': '?' if stock is None else ('sim' if stock > 0 else 'zero')}
        if all(not args.get(key) or args[key] == value for key, value in states.items()):
            yield row


def xlsx(rows, shop, start, end, insufficient, active):
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet('Anúncios')
    sheet.freeze_panes = 'A2'
    sheet.append(HEADERS)
    for row in rows:
        cells = []
        for value in values(row):
            cell = WriteOnlyCell(sheet, value=value)
            if isinstance(value, str):
                cell.data_type = 's'
            cells.append(cell)
        sheet.append(cells)
    notes = workbook.create_sheet('Período')
    shop_cell = WriteOnlyCell(notes, value=shop)
    shop_cell.data_type = 's'
    notes.append(('Loja', shop_cell))
    notes.append(('Início', start.isoformat()))
    notes.append(('Fim', end.isoformat()))
    notes.append(('Anúncios ativos na loja', active))
    notes.append(('Sem vendas confirmadas com os filtros', len(rows)))
    notes.append(('Ativos com dados insuficientes', insufficient))
    if not rows:
        notes.append(('Resultado', 'Nenhum anúncio ativo no catálogo sincronizado.' if not active else
                      'Nenhum anúncio sem vendas confirmado com os filtros. Consulte a contagem de dados insuficientes.'))
    file = BytesIO()
    workbook.save(file)
    file.seek(0)
    response = send_file(file, as_attachment=True, download_name='anuncios-sem-vendas.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response.headers['Cache-Control'] = 'no-store'
    return response


def report_body(cid, shops, start, end, rows, insufficient, active, args, page_number):
    categories = {r['categoria_id'] for r in rows if r['categoria_id']}
    options = {'': 'Todas', **{cat: cat for cat in sorted(categories)}, '?': 'Indisponível'}
    params = {key: args[key] for key in ('dias', 'categoria', *FILTERS) if args.get(key)}
    matches = list(filtered(rows, params))
    recent = sum(r['recent'] is True for r in matches)
    export_url = url_for('unsold_listings', cid=cid) + '?' + urlencode(dict(params, formato='xlsx'))
    heading = section_help(TITLE, 'Como o relatório é calculado', METHOD)
    form = option_list('Loja', 'loja', shops, cid)
    form += option_list('Período', 'dias', {n: f'{n} dias' for n in PERIODS}, args.get('dias', '30'))
    form += option_list('Categoria', 'categoria', options, params.get('categoria', ''))
    for key, (label, choices) in FILTERS.items():
        form += option_list(label, key, {'': 'Todos', **choices}, params.get(key, ''))
    html = (STYLE + REPORT_STYLE +
            f"<section class='card report-hero'>{heading}"
            f"<div class='report-toolbar'><p>{start:%d/%m/%Y} a {end:%d/%m/%Y}</p>"
            f"<a class='report-button report-download' href='{e(export_url)}'>Baixar Excel</a></div>"
            f"<form class='report-filters' action='{PATH}' method='get'>{form}"
            "<button class='report-button' type='submit'>Aplicar filtros</button></form></section>")
    if not active:
        return html + "<section class='card'>Nenhum anúncio ativo disponível no catálogo sincronizado desta loja.</section>"
    count = len(matches)
    recent_display = recent
    cards = (('Anúncios ativos na loja', active), ('Sem vendas confirmadas', count),
             ('Publicados durante o período', recent_display), ('Ativos com dados insuficientes', insufficient))
    html += "<div class='report-cards'>" + ''.join(
        f"<div class='card'><strong>{e(value)}</strong>{e(label)}</div>" for label, value in cards) + '</div>'
    if insufficient:
        html += ("<section class='card' role='status'>Parte do catálogo está fora dos resultados por falta "
                 "de data de publicação ou de histórico verificável de pedidos no período aplicável.</section>")
    if not matches:
        return html + ("<section class='card'><h3>Anúncios sem vendas</h3>"
                       "<p>Nenhum anúncio sem vendas confirmado com os filtros selecionados. "
                       "O Excel inclui o resumo do período.</p></section>")
    html += ("<section class='card'><h3>Anúncios sem vendas</h3>"
             "<div class='report-table' tabindex='0' role='region' aria-label='Anúncios sem vendas'>"
             "<table><thead><tr>" + ''.join(f"<th scope='col'>{e(h)}</th>" for h in HEADERS) +
             "</tr></thead><tbody>")
    page_count = (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE
    page_number = min(page_number, page_count)
    offset = (page_number - 1) * PAGE_SIZE
    for row in matches[offset:offset + PAGE_SIZE]:
        photo = preview_url(row['thumbnail'])
        img = f"<img src='{e(photo)}' alt='' loading='lazy'>" if photo else ''
        data = list(values(row))
        if data[4] is not None:
            data[4] = data[4].strftime('%d/%m/%Y')
        html += '<tr>' + ''.join(
            f"<td>{img if i == 0 else ''}{e(value) if value is not None else '—'}</td>"
            for i, value in enumerate(data)) + '</tr>'
    html += '</tbody></table></div>'
    if page_count > 1:
        html += f"<p>Página {page_number} de {page_count}</p><nav aria-label='Paginação dos resultados'>"
        for target, label in ((page_number - 1, 'Anterior'), (page_number + 1, 'Próxima')):
            if 1 <= target <= page_count:
                href = url_for('unsold_listings', cid=cid) + '?' + urlencode(dict(params, pagina=target))
                html += f"<a class='btn' href='{e(href)}'>{label}</a> "
        html += '</nav>'
    return html + '</section>'


def register(app, login_required, can_view, bank, query, page, store_page):
    def shops_for_user():
        with bank() as conn:
            if session.get('tipo') == 'admin':
                rows = query(conn, 'SELECT id,cliente FROM conexoes ORDER BY cliente,id')
            else:
                rows = query(conn, 'SELECT id,cliente FROM conexoes WHERE id=%s', (session.get('conexao_id'),))
        return {r['id']: r['cliente'] for r in rows if can_view(r['id'])}

    @app.get(PATH)
    @login_required
    def unsold_directory():
        shop = request.args.get('loja', type=int)
        if 'loja' in request.args and shop is None:
            return page(TITLE, "<div class='card'>Loja inválida.</div>"), 400
        if shop is not None and not can_view(shop):
            return page(TITLE, "<div class='card'>Acesso restrito.</div>"), 403
        shops = shops_for_user()
        if shop is None and not shops:
            return page(TITLE, f"<div class='card'><h2>{TITLE}</h2>Nenhuma loja disponível.</div>")
        params = {key: request.args[key] for key in ('dias', 'categoria', *FILTERS) if key in request.args}
        return redirect(url_for('unsold_listings', cid=shop if shop is not None else next(iter(shops)), **params))

    @app.get(PATH + '/<int:cid>')
    @login_required
    def unsold_listings(cid):
        if not can_view(cid):
            return page(TITLE, "<div class='card'>Acesso restrito.</div>"), 403
        shops = shops_for_user()
        if cid not in shops:
            return page(TITLE, "<div class='card'>Loja não encontrada.</div>"), 404
        end = reporting_today()
        try:
            days = request.args.get('dias', '30')
            if days not in tuple(map(str, PERIODS)):
                raise ValueError('Selecione 7, 15 ou 30 dias.')
            start = end - timedelta(days=int(days) - 1)
            rows, insufficient, active = read_report(bank, query, cid, start, end)
        except ValueError as exc:
            return store_page(TITLE, cid, shops[cid], 'relatorios',
                              f"<div class='card' role='status'>{e(exc)}</div>"), 400
        if request.args.get('formato') == 'xlsx':
            matches = list(filtered(rows, request.args))
            return xlsx(matches, shops[cid], start, end, insufficient, active)
        page_number = max(1, request.args.get('pagina', default=1, type=int))
        body = report_body(cid, shops, start, end, rows, insufficient, active, request.args, page_number)
        response = app.make_response(store_page(TITLE, cid, shops[cid], 'relatorios', body))
        response.headers['Cache-Control'] = 'no-store'
        return response
