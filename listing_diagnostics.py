"""Narrow, read-only diagnostics: never expose credentials or full account payloads."""
from listing_details import get_json, registered_weights


def inspect_listing(token, seller_id, item_id, request_get):
    result = {'item_id': item_id}
    account, error = get_json(token, '/users/me', {}, request_get)
    result['account_error'] = error
    result['token_matches_seller'] = (str(account.get('id')) == str(seller_id)
                                      if isinstance(account, dict) else None)
    item, error = get_json(token, '/items/' + item_id, {'include_attributes': 'all'}, request_get)
    result['item_error'] = error
    if isinstance(item, dict):
        result['item_matches_seller'] = str(item.get('seller_id')) == str(seller_id)
        result['weights'] = registered_weights(item)
        result['attribute_ids'] = [a.get('id') for a in item.get('attributes') or [] if isinstance(a, dict)]
    promotions, error = get_json(token, '/seller-promotions/items/' + item_id,
                                 {'app_version': 'v2'}, request_get)
    result['promotions_error'] = error
    result['promotion_count'] = len(promotions) if isinstance(promotions, list) else None
    price, error = get_json(token, '/items/' + item_id + '/sale_price',
                            {'context': 'channel_marketplace'}, request_get)
    result['sale_price_error'] = error
    if isinstance(price, dict):
        result['sale_price'] = {key: price.get(key) for key in
                                ('amount', 'regular_amount', 'currency_id', 'metadata')}
    return result
