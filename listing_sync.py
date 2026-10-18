"""Promotion snapshots and compatibility cache, committed atomically."""
import json
import time

from listing_details import get_json, normalize_promotions, read_json


def pages(token, path, params, request_get):
    """Support both documented offset and searchAfter pagination, without silent caps."""
    output, seen = [], set()
    params = dict(params, limit=50, app_version='v2')
    for _ in range(1000):
        data, error = get_json(token, path, params, request_get)
        if error:
            raise ValueError(error)
        if (not isinstance(data, dict) or not isinstance(data.get('results'), list)
                or any(not isinstance(r, dict) for r in data['results'])):
            raise ValueError('resposta paginada inválida em %s: formato=%s, results=%s' % (path, type(data).__name__, type(data.get('results')).__name__ if isinstance(data, dict) else 'ausente'))
        records = data['results']
        signature = json.dumps(records, sort_keys=True)
        if records and signature in seen:
            raise ValueError('paginação repetida')
        seen.add(signature)
        output.extend(records)
        paging = data.get('paging') or {}
        cursor = paging.get('searchAfter') or paging.get('search_after')
        if not records:
            return output
        if cursor:
            params.pop('offset', None)
            params['search_after'] = cursor
        elif len(output) < (paging.get('total') or 0):
            params.pop('search_after', None)
            params['offset'] = len(output)
        else:
            return output
    raise ValueError('paginação incompleta: limite de proteção atingido')


def sync_campaign_cache(cid, token, user_id, banco, executar, request_get):
    """Preserve the full Promoções tab, including campaigns with no linked listings."""
    campaigns = pages(token, '/seller-promotions/users/' + str(user_id), {}, request_get)
    collected = []
    for campaign in campaigns:
        if not isinstance(campaign, dict) or not campaign.get('id') or not campaign.get('type'):
            raise ValueError('campanha sem identificação')
        pid = str(campaign['id'])
        items = pages(token, '/seller-promotions/promotions/' + pid + '/items',
                      {'promotion_type': campaign['type']}, request_get)
        collected.append((campaign, items))
    now = int(time.time())
    with banco() as conn:
        executar(conn, 'DELETE FROM promocoes_itens WHERE conexao_id=%s', (cid,))
        executar(conn, 'DELETE FROM promocoes WHERE conexao_id=%s', (cid,))
        for campaign, items in collected:
            active = {str(p['id']): p for p in items if p.get('id') and
                      str(p.get('status')).lower() in ('started', 'active')}
            status = str(campaign.get('status') or '').lower()
            executar(conn, '''INSERT INTO promocoes
                (conexao_id, promocao_id, tipo, nome, status, inicio, fim, qtd_itens, atualizado_em)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (cid, str(campaign['id']), campaign['type'], campaign.get('name'),
                 {'started': 'active', 'pending': 'candidate'}.get(status, status),
                 campaign.get('start_date'), campaign.get('finish_date') or campaign.get('end_date'), len(active), now))
            for item_id, item in active.items():
                executar(conn, '''INSERT INTO promocoes_itens
                    (conexao_id, item_id, promocao_id, preco_promocional, atualizado_em)
                    VALUES (%s,%s,%s,%s,%s)''', (cid, item_id, str(campaign['id']), item.get('price'), now))


def sync_promotions(cid, token, banco, consultar, executar, request_get, registrar_erro, user_id=None, include_sale_price=True):
    with banco() as conn:
        items = consultar(conn, 'SELECT item_id, status, promocoes_json FROM anuncios WHERE conexao_id=%s', (cid,))
    now = int(time.time())
    snapshots = []
    circuit_error = None
    price_circuit_error = None
    for item in items:
        item_id = item['item_id']
        item_status = str(item.get('status') or '').lower()
        if item_status in ('closed', 'under_review'):
            snap = {'checked_at': int(time.time()), 'error': None, 'promotions': [],
                    'not_applicable': ('Anúncio encerrado — promoções não se aplicam' if item_status == 'closed'
                                       else 'Anúncio em análise — participação promocional indisponível')}
            snapshots.append((item_id, snap))
            with banco() as conn:
                executar(conn, 'UPDATE anuncios SET promocoes_json=%s WHERE conexao_id=%s AND item_id=%s',
                         (json.dumps(snap, ensure_ascii=False), cid, item_id))
            continue
        error = circuit_error
        data = None
        if not error:
            data, error = get_json(token, '/seller-promotions/items/' + item_id,
                                   {'app_version': 'v2'}, request_get)
        if not error:
            try:
                promotions = normalize_promotions(data)
            except ValueError as exc:
                error = str(exc)
        if error:
            if any(code in error for code in ('HTTP 401', 'HTTP 403', 'HTTP 429')):
                circuit_error = error
            snap = dict(read_json(item.get('promocoes_json'), {}))
            snap.update(error=error, attempted_at=now)
        else:
            snap = {'checked_at': int(time.time()), 'promotions': promotions, 'error': None,
                    'source': '/seller-promotions/items/' + item_id + '?app_version=v2'}
        if include_sale_price:
            price, price_error = None, price_circuit_error
            if not price_error:
                price, price_error = get_json(token, '/items/' + item_id + '/sale_price',
                                              {'context': 'channel_marketplace'}, request_get)
                if price_error and any(code in price_error for code in ('HTTP 401', 'HTTP 403', 'HTTP 429')):
                    price_circuit_error = price_error
            snap['sale_price'] = {'checked_at': int(time.time()), 'error': price_error,
                                 'data': price if isinstance(price, dict) else {}}
        snapshots.append((item_id, snap))
        # Persist each result so progress survives interruptions and long stores.
        with banco() as conn:
            executar(conn, 'UPDATE anuncios SET promocoes_json=%s WHERE conexao_id=%s AND item_id=%s',
                     (json.dumps(snap, ensure_ascii=False), cid, item_id))
    errors = [snap['error'] for _, snap in snapshots if snap.get('error')]
    with banco() as conn:
        if not errors:
            executar(conn, "DELETE FROM erros WHERE conexao_id=%s AND categoria='promocoes'", (cid,))
    if not errors and user_id is not None:
        try:
            sync_campaign_cache(cid, token, user_id, banco, executar, request_get)
        except ValueError as exc:
            registrar_erro(cid, 'promocoes', 'Campanhas anteriores preservadas: ' + str(exc))
            return False
    if errors:
        registrar_erro(cid, 'promocoes', '%d/%d anúncios sem confirmação: %s' % (len(errors), len(items), errors[0]))
    return not errors
