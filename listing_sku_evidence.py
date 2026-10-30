"""Official SELLER_SKU snapshots from existing item reads, never internal custom fields."""
import re

SOURCE = 'https://developers.mercadolivre.com.br/pt_br/variacoes'


def init_schema(conn, execute):
    execute(conn, 'ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS sku_metadata_json JSONB')


def code_from_attributes(attributes):
    if not isinstance(attributes, list) or len(attributes) > 2000:
        return None, False
    matches = []
    for attribute in attributes:
        if not isinstance(attribute, dict) or not isinstance(attribute.get('id'), str) or not attribute['id'].strip():
            return None, False
        if attribute.get('id') == 'SELLER_SKU':
            matches.append(attribute)
    if not matches:
        return None, True  # No SKU returned, never a confirmed publication error.
    if len(matches) != 1:
        return None, False
    row = matches[0]
    if str(row.get('value_id')) == '-1':
        return None, False
    value = row.get('value_name')
    if value is None or value == '':
        return None, not bool(row.get('values'))
    if not isinstance(value, str) or len(value) > 200 or '\x00' in value:
        return None, False
    values = row.get('values')
    if values:
        if (not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict)
                or values[0].get('name') != value):
            return None, False
    value = value.strip(' \t\r\n')
    return value or None, True


def snapshot(item, seller_id, item_id, now):
    result = dict(version=1, collected_at=now, state='unknown', entries=[])
    if (not isinstance(item, dict) or item.get('id') != item_id
            or not isinstance(item_id, str) or not re.fullmatch(r'MLB[0-9]{1,20}', item_id)
            or isinstance(seller_id, bool) or isinstance(item.get('seller_id'), bool)
            or not re.fullmatch(r'[1-9][0-9]{0,19}', str(seller_id))
            or str(item.get('seller_id')) != str(seller_id) or item.get('site_id') != 'MLB'
            or type(now) is not int or now < 0):
        return result
    code, complete = code_from_attributes(item.get('attributes'))
    if code:
        result['entries'].append(dict(code=code, variation='principal'))
    variations = item.get('variations')
    if not isinstance(variations, list) or len(variations) > 1000:
        result['state'] = 'partial'
        return result
    seen = set()
    for variation in variations:
        vid = variation.get('id') if isinstance(variation, dict) else None
        if (isinstance(vid, bool) or not isinstance(vid, (int, str))
                or not re.fullmatch(r'[1-9][0-9]{0,19}', str(vid)) or str(vid) in seen):
            result['state'] = 'partial'
            return result  # Discard the ambiguous variation set, preserving only principal.
        seen.add(str(vid))
    for variation in variations:
        code, verified = code_from_attributes(variation.get('attributes'))
        complete = complete and verified
        if code:
            result['entries'].append(dict(code=code, variation=str(variation['id'])))
    result['state'] = 'read' if complete else 'partial'
    return result
