"""Reactivate one verified item using the connected seller's authorization."""
import re

import requests

from listing_content_snapshot import ContentUnavailable, read
from listing_pause_reasons import inspect


def reactivate(token, seller, item_id, request_get, request_put):
    current = inspect(token, seller, item_id, request_get)
    if current['state'] != 'read':
        return current['message'], 409
    if current['status'] != 'paused':
        return 'A reativação exige um anúncio pausado. Confira o status atual.', 409
    if current['account_permission']['allow'] is False:
        return 'O Mercado Livre indica restrição de publicação nesta conta.', 409
    if 'out_of_stock' in (current['codes'] or []):
        return 'O Mercado Livre indica falta de estoque. Confira a reposição antes de reativar.', 409

    path = '/items/' + item_id
    response = None
    try:
        response = request_put(
            'https://api.mercadolibre.com' + path,
            headers={'Authorization': 'Bearer ' + token},
            json={'status': 'active'}, timeout=(3, 8), allow_redirects=False,
        )
    except requests.RequestException:
        pass  # The request may have reached the marketplace. Read back before reporting.

    if response is not None and 400 <= response.status_code < 500:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        causes = payload.get('cause')
        causes = causes if isinstance(causes, list) else []
        codes = [entry.get('code') for entry in causes[:5] if isinstance(entry, dict)]
        codes.append(payload.get('error'))
        codes = [code for code in codes if isinstance(code, str)
                 and re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', code) and token not in code]
        reason = payload.get('message')
        reason = ' '.join(reason.replace(token, '[oculto]').split())[:240] if isinstance(reason, str) else ''
        details = ' · '.join(filter(None, (reason, ', '.join(dict.fromkeys(codes)))))
        message = f'Mercado Livre recusou a reativação (HTTP {response.status_code}).'
        return message + (' ' + details if details else ''), 409

    try:
        updated = read(token, path, request_get)
    except ContentUnavailable:
        updated = {}
    if (updated.get('id') == item_id and str(updated.get('seller_id')) == str(seller)
            and updated.get('site_id') == 'MLB' and updated.get('status') == 'active'):
        return 'Anúncio ativo. Status confirmado no Mercado Livre.', 200
    return 'O Mercado Livre ainda não confirmou a reativação. Consulte o status antes de tentar novamente.', 409
