"""Read-only conditional requirement query using Mercado Livre's official endpoint."""
import json
import re
import requests


def evaluate(token, category, item, description, request_post):
    unknown = {'state': 'unknown', 'message': 'Aplicabilidade condicional não verificada.'}
    # A partial item cannot safely establish that a condition is not applicable.
    required = ('title', 'category_id', 'price', 'currency_id', 'available_quantity',
                'buying_mode', 'condition', 'listing_type_id', 'attributes', 'variations', 'pictures')
    if (not isinstance(category, str) or not re.fullmatch(r'MLB[0-9]{1,20}', category)
            or not isinstance(item, dict) or item.get('category_id') != category
            or not isinstance(description, str) or request_post is None
            or any(k not in item or item[k] is None for k in required)):
        return unknown
    payload = dict(item, description={'plain_text': description})
    try:
        if len(json.dumps(payload, ensure_ascii=False)) > 1_000_000:
            return unknown
        response = request_post('https://api.mercadolibre.com/categories/'+category+'/attributes/conditional',
            headers={'Authorization': 'Bearer '+token}, json=payload, timeout=(3, 8), allow_redirects=False)
        if response.status_code == 429:
            return dict(unknown,rate_limited=True)
        if response.status_code != 200:
            return unknown
        result = response.json()
        rows = result.get('required_attributes') if isinstance(result, dict) else None
        if not isinstance(rows, list) or len(rows) > 2000:
            return unknown
        ids = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip() or len(row['id']) > 200 or row['id'] in ids:
                return unknown
            ids.append(row['id'])
        return {'state': 'read', 'required_ids': ids}
    except (requests.RequestException, TypeError, ValueError, OverflowError):
        return unknown
