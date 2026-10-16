"""Read-only listing enrichment. No database or application startup side effects."""
import datetime
import html
import json
import math
import re
import time


def positive(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    except (ValueError, TypeError):
        return None


def weight(value, unit, source, raw):
    factors = {'kg': 1, 'g': .001, 'mg': .000001, 'lb': .45359237,
               'oz': .028349523125, 'gr': .001, 'gramas': .001}
    number = positive(value)
    unit = str(unit or '').strip().lower()
    if number is None or unit not in factors:
        return None
    return {'kg': number * factors[unit], 'value': value, 'unit': unit,
            'source': source, 'raw': raw}


def attribute_weights(item, prefix):
    records = []
    # Package and product weights remain distinct, with their exact attribute IDs.
    for group in ('attributes', 'sale_terms', 'attribute_combinations'):
        for attr in item.get(group) or []:
            if not isinstance(attr, dict) or attr.get('id') not in (
                    'SELLER_PACKAGE_WEIGHT', 'PACKAGE_WEIGHT', 'WEIGHT'):
                continue
            source = prefix + '.' + group + '.' + attr['id']
            values = [attr] + (attr.get('values') or [])
            for value in values:
                struct = value.get('value_struct') or value.get('struct') or {}
                record = weight(struct.get('number'), struct.get('unit'), source, value)
                if record is None:
                    text = str(value.get('value_name') or value.get('name') or '')
                    match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z]+)\s*', text)
                    if match:
                        record = weight(match[1].replace(',', '.'), match[2], source, value)
                if record:
                    records.append(record)
                    break
    dims = (item.get('shipping') or {}).get('dimensions')
    if isinstance(dims, str) and re.fullmatch(r'\s*[\d.]+x[\d.]+x[\d.]+,\s*[\d.]+\s*', dims):
        record = weight(dims.split(',')[-1], 'g', prefix + '.shipping.dimensions', dims)
        if record:
            records.append(record)
    return records


def registered_weights(item):
    result = {'item': attribute_weights(item, 'item'), 'variations': []}
    for variant in item.get('variations') or []:
        result['variations'].append({'id': variant.get('id'),
                                     'weights': attribute_weights(variant, 'variation')})
    return result


def legacy_weight(details):
    """Only keep a scalar when all variants have an unambiguous common value."""
    def choose(records):
        for suffix in ('SELLER_PACKAGE_WEIGHT', 'shipping.dimensions', 'PACKAGE_WEIGHT', 'WEIGHT'):
            found = [r['kg'] for r in records if r['source'].endswith(suffix)]
            if found:
                return found[0] if len(set(found)) == 1 else None
        return None
    variants = details['variations']
    if variants:
        values = [choose(v['weights']) for v in variants]
        # Common item weight cannot override explicit but incomplete variant data.
        if any(v['weights'] for v in variants):
            return values[0] if None not in values and len(set(values)) == 1 else None
    return choose(details['item'])


def read_json(value, default):
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if isinstance(parsed, type(default)) else default
    except (ValueError, TypeError):
        return default


def render_weights(value):
    details = read_json(value, {})
    rows = []
    groups = [('Anúncio', details.get('item', []))]
    groups += [('Variação ' + str(v['id']), v['weights']) for v in details.get('variations', [])]
    for label, records in groups:
        if not records and label != 'Anúncio':
            rows.append(html.escape(label) + ': Não disponível (consulte o peso comum do anúncio)')
        for record in records:
            rows.append(html.escape('%s: %.6g kg (%s %s; %s)' % (
                label, record['kg'], record['value'], record['unit'], record['source'])))
    return '<br>'.join(rows) or 'Não disponível'


def render_weight_column(value, attribute_id):
    """User-selected mapping: exact attribute IDs, never substitute another weight."""
    details = read_json(value, {})
    rows = []
    groups = [('Anúncio', details.get('item', []))]
    groups += [('Variação ' + str(v['id']), v['weights']) for v in details.get('variations', [])]
    for label, records in groups:
        matched = [r for r in records if r.get('source', '').split('.')[-1] == attribute_id]
        for record in matched:
            text = '%s: %.6g kg' % (label, record['kg'])
            trace = '%s %s; %s' % (record['value'], record['unit'], record['source'])
            rows.append('<span title="' + html.escape(trace, quote=True) + '">' + html.escape(text) + '</span>')
        if label != 'Anúncio' and not matched:
            rows.append(html.escape(label) + ': Não disponível')
    return '<br>'.join(rows) or 'Não disponível'


def get_json(token, path, params, request_get, sleep=time.sleep):
    """At most three requests; honor Retry-After without blocking a worker indefinitely."""
    for attempt in range(3):
        try:
            response = request_get('https://api.mercadolibre.com' + path,
                                   headers={'Authorization': 'Bearer ' + (token or '')},
                                   params=dict(params or {}), timeout=25)
            code = response.status_code
            if code == 200:
                return response.json(), None
            if code == 429 or code >= 500:
                delay = 2 ** attempt
                retry = response.headers.get('Retry-After')
                if retry:
                    try:
                        delay = max(delay, float(retry))
                    except ValueError:
                        # An HTTP-date or unrecognized value: defer to next refresh.
                        return None, 'HTTP %s; nova tentativa na próxima atualização' % code
                if attempt < 2 and delay <= 30:
                    sleep(delay)
                    continue
            hints = {401: 'token expirado ou inválido', 403: 'verifique a permissão funcional de leitura de promoções e a conta autorizada',
                     429: 'limite de requisições; aguarde a próxima atualização'}
            reason = ''
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    reason = '; '.join(str(payload[key]) for key in ('error', 'message', 'description')
                                       if isinstance(payload.get(key), str))
                    if token:
                        reason = reason.replace(token, '[redigido]')
                    reason = re.sub(r'(?i)Bearer\s+\S+', 'Bearer [redigido]', reason)
                    reason = re.sub(r'(?i)(access_token|refresh_token|client_secret)([\s:=]+)[^\s,;]+',
                                    r'\1\2[redigido]', reason)
                    reason = ' '.join(reason.split())[:180]
            except (ValueError, TypeError):
                pass
            message = hints.get(code, 'consulta indisponível')
            return None, 'HTTP %s: %s%s' % (code, message, ('; ' + reason) if reason else '')
        except (OSError, ValueError):
            if attempt < 2:
                sleep(2 ** attempt)
    return None, 'Falha de rede ou resposta JSON inválida'


def normalize_promotions(records):
    if not isinstance(records, list) or any(not isinstance(p, dict) for p in records):
        raise ValueError('resposta de promoções inválida')
    output = []
    for record in records:
        status = str(record.get('status') or 'Não disponível').lower()
        if status == 'started':
            status = 'active'
        kind = record.get('type') or 'Não disponível'
        # Unknown future types stay explicit; do not guess the funding source.
        origin = ('Vendedor' if kind in ('PRICE_DISCOUNT', 'SELLER_CAMPAIGN', 'SELLER_COUPON_CAMPAIGN')
                  else 'Plataforma/campanha' if kind in ('DEAL', 'DOD', 'LIGHTNING', 'MARKETPLACE_CAMPAIGN',
                       'PRE_NEGOTIATED', 'SMART', 'PRICE_MATCHING', 'UNHEALTHY_STOCK', 'VOLUME', 'BANK')
                  else 'Não disponível')
        original, price = positive(record.get('original_price')), positive(record.get('price'))
        discount = round((original - price) * 100 / original, 2) if original and price and original > price else None
        output.append({'id': record.get('id'), 'type': kind, 'status': status,
                       'origin': origin, 'original': original, 'price': price, 'discount': discount,
                       'start': record.get('start_date'),
                       'end': record.get('end_date') or record.get('finish_date'),
                       'variation_id': record.get('variation_id'), 'raw': record})
    return output


def promotion_status(promotion):
    """Reconcile explicit timezone-aware dates without guessing a timezone."""
    status = promotion.get('status')
    if status != 'active':
        return status
    now = datetime.datetime.now(datetime.timezone.utc)
    for field, label, compare in (
            ('end', 'vigência encerrada', lambda date: date <= now),
            ('start', 'aguardando início', lambda date: date > now)):
        try:
            value = promotion.get(field)
            date = datetime.datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None
            if date is not None and date.tzinfo is not None and compare(date):
                return label
        except (ValueError, TypeError, AttributeError):
            pass
    return status


def active_promotions(snapshot):
    if not snapshot or snapshot.get('error'):
        return []
    # Old snapshots must never silently keep an expired promotion active.
    if time.time() - snapshot.get('checked_at', 0) > 7200:
        return []
    return [p for p in snapshot.get('promotions', []) if promotion_status(p) == 'active']


def render_promotions(value):
    snap = read_json(value, {})
    if not snap:
        return 'Não verificado — atualize os anúncios'
    if snap.get('error'):
        return html.escape('Não disponível — ' + snap['error']) + '<br>Dados anteriores não confirmados'
    if time.time() - snap.get('checked_at', 0) > 7200:
        return 'Dados desatualizados — atualize os anúncios'
    rows = []
    for p in snap.get('promotions', []):
        status = promotion_status(p)
        status_text = status if status == p['status'] else status + ' (API: ' + p['status'] + ')'
        parts = [p['origin'], p['type'], 'Status: ' + status_text]
        for label, key in [('Original', 'original'), ('Promocional', 'price')]:
            if key == 'price' and status != 'active':
                label = 'Preço informado (não ativo)'
            parts.append(label + ': ' + ('R$ %.2f' % p[key] if p.get(key) else 'Não disponível'))
        parts.append('Desconto: ' + ('%.2f%%' % p['discount'] if p.get('discount') is not None else 'Não disponível'))
        parts.append('Vigência: %s até %s' % (p.get('start') or 'Não disponível', p.get('end') or 'Não disponível'))
        if p.get('variation_id'):
            parts.append('Variação: ' + str(p['variation_id']))
        else:
            parts.append('Escopo: anúncio (API não discrimina variações)')
        rows.append(html.escape(' | '.join(parts)))
    return '<br>'.join(rows) or 'Sem promoções associadas'
