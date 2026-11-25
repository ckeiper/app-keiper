"""Read one page of official item infractions after seller/item verification."""
from html import escape
from urllib.parse import urlencode

from listing_content_snapshot import ContentUnavailable, read

PAGE_SIZE = 20


def inspect(token, seller, item_id, request_get, offset=0):
    params = dict(related_item_id=item_id, element_type='ITM', language='PT',
                  limit=PAGE_SIZE, offset=offset, sort='date_created_desc')
    try:
        payload = read(token, '/moderations/infractions/' + str(seller) + '?' + urlencode(params), request_get)
        rows = payload.get('infractions')
        paging = payload.get('paging')
        if not isinstance(rows, list) or not isinstance(paging, dict):
            raise ContentUnavailable('Resposta do histórico não verificável.')
        total, returned_offset, limit = (paging.get(key) for key in ('total', 'offset', 'limit'))
        if (type(total) is not int or total < 0 or type(returned_offset) is not int
                or returned_offset != offset or type(limit) is not int or not 1 <= limit <= PAGE_SIZE):
            raise ContentUnavailable('Paginação do histórico não verificável.')
        result = []
        partial = len(rows) > min(limit, max(0,total-offset))
        for row in rows[:limit]:
            if (not isinstance(row, dict) or str(row.get('user_id')) != str(seller)
                    or row.get('related_item_id') != item_id or row.get('element_id') != item_id
                    or row.get('element_type') != 'ITM' or row.get('site_id') != 'MLB'):
                partial = True
                continue
            entry = {}
            for key, max_length in (('id',100), ('date_created',100), ('filter_subgroup',200),
                                    ('reason',4000), ('remedy',4000)):
                value = row.get(key)
                if value is not None and not isinstance(value, str):
                    partial = True
                    value = None
                if value is not None and len(value) > max_length:
                    partial = True
                entry[key] = value[:max_length] if value else None
            result.append(entry)
        if len(rows) < min(limit, max(0,total-offset)):
            partial = True
        return dict(state='read', rows=result, total=total, offset=offset, limit=limit,
                    partial=partial)
    except ContentUnavailable as exc:
        return dict(state='unknown', message=str(exc))


def render(token, result=None):
    out = '<section class="rr-history"><h4>Histórico de infrações</h4>'
    def form(offset, label):
        return ('<form method="post"><input type="hidden" name="_csrf" value="'
                + escape(token, quote=True) + '"><input type="hidden" name="history_offset" value="'
                + str(offset) + '"><button name="action" value="consultar_historico">'
                + label + '</button></form>')
    out += form(0, 'Consultar histórico de infrações')
    if result is None:
        return out + '</section>'
    if result['state'] != 'read':
        return out + '<p role="status">' + escape(result['message']) + '</p></section>'
    out += '<p>' + str(result['total']) + ' registros informados pelo Mercado Livre.</p>'
    if result['partial']:
        out += '<p role="status">Resposta parcial. Há dados ausentes, abreviados ou que não correspondem a este anúncio.</p>'
    for row in result['rows']:
        out += '<article><strong>' + escape(row['filter_subgroup'] or 'Infração') + '</strong>'
        out += '<p>' + escape(row['date_created'] or 'Data não informada') + '</p>'
        out += '<p class="rr-note">' + escape(row['reason'] or 'Motivo não informado') + '</p>'
        out += '<p class="rr-note">' + escape(row['remedy'] or 'Correção não informada pelo Mercado Livre') + '</p></article>'
    if not result['rows'] and not result['partial']:
        out += '<p>Nenhuma infração retornada nesta página.</p>'
    out += '<nav aria-label="Páginas de infrações">'
    if result['offset'] > 0:
        out += form(max(0,result['offset']-result['limit']), 'Página anterior')
    if result['offset'] + result['limit'] < result['total']:
        out += form(result['offset']+result['limit'], 'Próxima página')
    out += '</nav><details><summary aria-label="Cobertura do histórico de infrações">?</summary>'
    out += '<p>Consulta sob demanda, com até vinte registros por página. A API exclui itens removidos por duplicidade. As condições atuais são verificadas novamente antes de solicitar a reativação.</p></details>'
    return out + '</section>'
