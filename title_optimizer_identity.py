"""Read-only identification from the seller's actual listing and category rules."""
import re
from attribute_completion import owned
from content_required_attributes import attributes
from listing_content_snapshot import ContentUnavailable, read


def identify(token, seller, item_id, get):
    item = owned(token, seller, item_id, get)
    rows = attributes(item.get('attributes')) or {}
    def value(code):
        raw = rows.get(code, {}).get('value_name')
        return raw.strip() if isinstance(raw, str) and 0 < len(raw) <= 100 else ''
    brand, model = value('BRAND'), value('MODEL')
    title = item.get('title')
    if not isinstance(title, str) or not title.strip() or len(title) > 300:
        raise ContentUnavailable('Título do anúncio não verificável.')
    product = title
    # Remove only exact attribute phrases, never infer a brand from a dictionary.
    for phrase in (brand, model):
        if phrase:
            product = re.sub(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', ' ', product, flags=re.I)
    product = ' '.join(product.split()).strip(' -|,') or title
    policy = dict(state='unknown', message='Categoria não verificada; confira o campo Modelo no Mercado Livre.')
    category = item.get('category_id')
    if item.get('catalog_listing') is True:
        policy = dict(state='blocked', message='Anúncio de catálogo: preserve o Modelo definido pelo catálogo.')
    elif isinstance(category, str) and re.fullmatch(r'MLB[0-9]{1,20}', category):
        try:
            definitions = attributes(read(token, '/categories/'+category+'/attributes', get, list))
            rule = definitions.get('MODEL') if definitions is not None else None
            if definitions is not None and rule is None:
                policy = dict(state='blocked', message='A categoria não oferece o campo Modelo.')
            elif rule:
                tags = rule.get('tags')
                blocked = ('read_only', 'fixed', 'inferred', 'hidden', 'restricted_values', 'product_pk', 'parent_pk', 'child_pk')
                if not isinstance(tags, dict) or any(tags.get(key) for key in blocked) or rule.get('value_type') != 'string':
                    policy = dict(state='blocked', message='Modelo possui restrições na categoria; preserve o valor atual.')
                elif item.get('catalog_listing') is False:
                    limit = rule.get('value_max_length')
                    policy = dict(state='review', message='A categoria aceita texto em Modelo. Use apenas termos que descrevam o modelo real; confirme antes de copiar.', max_length=limit if type(limit) is int and limit > 0 else None)
        except ContentUnavailable as exc:
            policy['message'] = str(exc) + ' Modelo não verificado.'
    return dict(original=title, product=product, brand=brand, model=model, model_policy=policy)
