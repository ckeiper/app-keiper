"""Tenant-scoped HTML and Excel views of the same unsold-listing results."""
from datetime import timedelta
from html import escape
from io import BytesIO
from urllib.parse import urlencode

from flask import redirect, request, send_file, session, url_for

from listing_image_selection import preview_url
from sales_metrics import amount, reporting_today
from section_help import STYLE, section_help
from unsold_report import PERIODS, read_report


TITLE = 'Anúncios sem vendas nos últimos 30 dias'
PAGE_SIZE = 100
PATH = '/relatorios/anuncios-sem-vendas'
HEADERS = ('Anúncio', 'MLB', 'SKU', 'Categoria', 'Logística', 'Preço (R$)', 'Estoque',
           'Última venda registrada', 'Visitas', 'Ads', 'Publicado durante o período')
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


def e(value):
    return escape(str(value), quote=True)


def values(row):
    return (row['titulo'], row['item_id'], row['sku'], row['categoria_id'], row['logistics'],
            amount(row['preco']), row['quantidade'], row['last_sale'], row['visits'],
            row['ads'], 'Sim' if row['recent'] else 'Não')


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


def xlsx(rows, shop, start, end, insufficient):
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
    notes.append(('Ativos com dados insuficientes', insufficient))
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
    recent = sum(r['recent'] for r in matches)
    export_url = url_for('unsold_listings', cid=cid) + '?' + urlencode(dict(params, formato='xlsx'))
    heading = section_help(TITLE, 'Como o relatório é calculado', METHOD)
    form = option_list('Loja', 'loja', shops, cid)
    form += option_list('Período', 'dias', {n: f'{n} dias' for n in PERIODS}, args.get('dias', '30'))
    form += option_list('Categoria', 'categoria', options, params.get('categoria', ''))
    for key, (label, choices) in FILTERS.items():
        form += option_list(label, key, {'': 'Todos', **choices}, params.get(key, ''))
    html = (STYLE + "<style>.report-filters{display:flex;align-items:end;gap:12px;flex-wrap:wrap}"
            ".report-filters label{display:grid;gap:5px}.report-cards{display:grid;gap:12px;"
            "grid-template-columns:repeat(auto-fit,minmax(min(165px,100%),1fr))}"
            ".report-cards strong{display:block;font-size:1.45rem}.report-table{overflow:auto}"
            ".report-table img{width:48px;height:48px;object-fit:contain;vertical-align:middle;margin-right:8px}"
            "</style>"
            f"<section class='card'>{heading}<p>{start:%d/%m/%Y} a {end:%d/%m/%Y}</p>"
            f"<form class='report-filters' action='{PATH}' method='get'>{form}"
            "<button class='btn' type='submit'>Filtrar</button></form></section>")
    if not active:
        return html + "<section class='card'>Nenhum anúncio ativo disponível no catálogo sincronizado desta loja.</section>"
    count = len(matches) if rows or not insufficient else '—'
    recent_display = recent if rows or not insufficient else '—'
    cards = (('Anúncios ativos na loja', active), ('Sem vendas com os filtros', count),
             ('Publicados durante o período', recent_display), ('Ativos com dados insuficientes', insufficient))
    html += "<div class='report-cards'>" + ''.join(
        f"<div class='card'><strong>{e(value)}</strong>{e(label)}</div>" for label, value in cards) + '</div>'
    if insufficient:
        html += ("<section class='card' role='status'>Parte do catálogo está fora dos resultados por falta "
                 "de data de publicação ou de histórico verificável de pedidos no período aplicável.</section>")
    if not matches:
        if insufficient and not rows:
            return html
        return html + "<section class='card'>Nenhum anúncio sem vendas encontrado com estes filtros.</section>"
    html += (f"<section class='card'><a class='btn' href='{e(export_url)}'>Exportar Excel</a>"
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
        if data[5] is not None:
            data[5] = f'{data[5]:,.2f}'.translate(str.maketrans(',.', '.,'))
        if data[7] is not None:
            data[7] = data[7].strftime('%d/%m/%Y')
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
            if not matches:
                return 'Nenhum resultado verificável para exportar.', 422
            return xlsx(matches, shops[cid], start, end, insufficient)
        page_number = max(1, request.args.get('pagina', default=1, type=int))
        body = report_body(cid, shops, start, end, rows, insufficient, active, request.args, page_number)
        response = app.make_response(store_page(TITLE, cid, shops[cid], 'relatorios', body))
        response.headers['Cache-Control'] = 'no-store'
        return response
