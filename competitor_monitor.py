"""Competitor observations from official ML endpoints; no checkout/coupon inference.

Sources: developers.mercadolivre.com.br/pt_br/api-de-precos (sale_price.amount)
        developers.mercadolivre.com.br/pt_br/mercado-envios (logistic_type)
"""
import re
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, parse_qs

SLOT_SECONDS = 8640  # Ten slots per São Paulo calendar day, starting at 00:00.
UTC_OFFSET = -10800
API = 'https://api.mercadolibre.com'
HOURS = '00:00, 02:24, 04:48, 07:12, 09:36, 12:00, 14:24, 16:48, 19:12 e 21:36'


def slot_at(now):
    return (int(now) + UTC_OFFSET) // SLOT_SECONDS


def next_slot(now):
    return (slot_at(now) + 1) * SLOT_SECONDS - UTC_OFFSET


def item_from_link(value):
    """Extract a seller-specific item; never fetch user supplied URLs or redirects."""
    value = (value or '').strip()
    if len(value) > 3000:
        raise ValueError('O link deve ter até 3.000 caracteres.')
    if re.fullmatch(r'MLB-?\d{6,15}', value, re.I):
        return value.upper().replace('-', '')
    try:
        url = urlsplit(value)
        if (url.scheme not in ('http', 'https') or url.username or url.password
                or url.port not in (None, 80, 443)
                or url.hostname not in ('mercadolivre.com.br', 'www.mercadolivre.com.br',
                                         'produto.mercadolivre.com.br')):
            raise ValueError()
        args = parse_qs(url.query)
        ids = []
        for wid in args.get('wid', []):
            if not re.fullmatch(r'MLB-?\d{6,15}', wid, re.I):
                raise ValueError()
            ids.append(wid.upper().replace('-', ''))
        for entry in args.get('pdp_filters', []):
            ids += [m.upper().replace('-', '') for m in
                    re.findall(r'(?:^|[|,])item_id:(MLB-?\d{6,15})(?=$|[|,])', entry, re.I)]
        direct = re.match(r'^/(MLB-?\d{6,15})(?:-|/|$)', url.path, re.I)
        if direct:
            ids.append(direct[1].upper().replace('-', ''))
        if ids and len(set(ids)) == 1:
            return ids[0]
    except ValueError:
        pass
    raise ValueError('Cole o link do anúncio do vendedor (com MLB ou wid). '
                     'No catálogo, abra a oferta do concorrente e copie o link dela.')


def money(value):
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        if number.is_finite() and 0 < number < Decimal('1000000000000'):
            return number.quantize(Decimal('.01'))
    except (InvalidOperation, ValueError, TypeError):
        pass
    return None


def observe(item_id, seller_id, token, getter):
    """Partial failures remain unknown. The old /items.price is NOT a fallback."""
    result = dict(price=None, full=None, title=None, seller_id=None, error='')
    errors = []

    def fetch(path, **kwargs):
        try:
            response = getter(API + path, headers={'Authorization': 'Bearer ' + token},
                              timeout=(3, 7), allow_redirects=False, **kwargs)
            if response.status_code != 200:
                errors.append('Consulta não autorizada pelo Mercado Livre (HTTP ' + str(response.status_code) + ')'
                              if response.status_code in (401, 403) else
                              'Mercado Livre: HTTP ' + str(response.status_code))
                return None
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except Exception:
            errors.append('Falha de comunicação ou resposta inválida')
            return None

    item = fetch('/items/' + item_id)
    if item is None:
        result['error'] = '; '.join(errors)
        return result
    actual_seller = item.get('seller_id')
    if (item.get('id') != item_id or type(actual_seller) is not int or actual_seller <= 0
            or (seller_id is not None and actual_seller != seller_id)):
        result['error'] = 'Não foi possível confirmar o anúncio e o vendedor monitorados'
        return result
    result.update(title=str(item.get('title') or item_id)[:500], seller_id=actual_seller)
    logistics = item.get('shipping')
    logistics = logistics.get('logistic_type') if isinstance(logistics, dict) else None
    # Only explicit supported logistics prove non-Full; absence is unknown.
    if logistics == 'fulfillment':
        result['full'] = True
    elif logistics in ('cross_docking', 'drop_off', 'xd_drop_off', 'self_service',
                        'custom', 'not_specified', 'default', 'pickup'):
        result['full'] = False
    else:
        errors.append('Logística Full não confirmada')
    if item.get('status') != 'active':
        errors.append('Anúncio indisponível para compra; preço não confirmado')
    else:
        sale = fetch('/items/' + item_id + '/sale_price',
                     params={'context': 'channel_marketplace', 'quantity': 1})
        if sale is not None:
            price = money(sale.get('amount'))
            # Net prices require taxes to represent the public final amount.
            if sale.get('amount_tax_inclusion_type') == 'net':
                price = money(sale.get('amount_with_taxes'))
            if price is not None and sale.get('currency_id') == 'BRL':
                result['price'] = price
            else:
                errors.append('Preço final em reais não confirmado')
    result['error'] = '; '.join(dict.fromkeys(errors))[:500]
    return result


def init_competitor_schema(conn, execute):
    execute(conn, '''CREATE TABLE IF NOT EXISTS competitor_targets (
        id BIGSERIAL PRIMARY KEY, conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        item_id TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', title TEXT,
        seller_id BIGINT, active BOOLEAN NOT NULL DEFAULT TRUE, created_at BIGINT NOT NULL,
        last_slot BIGINT, attempted_at BIGINT, error TEXT NOT NULL DEFAULT '',
        price NUMERIC(14,2), previous_price NUMERIC(14,2), price_at BIGINT, price_changed_at BIGINT,
        full_state BOOLEAN, previous_full BOOLEAN, full_at BIGINT, full_changed_at BIGINT,
        UNIQUE(conexao_id,item_id))''')
    execute(conn, '''CREATE INDEX IF NOT EXISTS idx_competitor_due
        ON competitor_targets(last_slot,id) WHERE active''')
    execute(conn, '''CREATE TABLE IF NOT EXISTS competitor_observations (
        target_id BIGINT NOT NULL REFERENCES competitor_targets(id) ON DELETE CASCADE,
        slot BIGINT NOT NULL, observed_at BIGINT NOT NULL,
        price NUMERIC(14,2), previous_price NUMERIC(14,2), full_state BOOLEAN, previous_full BOOLEAN,
        price_changed BOOLEAN NOT NULL, full_changed BOOLEAN NOT NULL,
        error TEXT NOT NULL DEFAULT '', PRIMARY KEY(target_id,slot))''')
    execute(conn, '''CREATE INDEX IF NOT EXISTS idx_competitor_history
        ON competitor_observations(target_id,observed_at DESC)''')


def collect_due(bank, query, execute, getter, clock=time.time, monotonic=time.monotonic):
    """Persistently claim one target at a time; at most one attempt per target/slot.

    SKIP LOCKED works across Gunicorn workers. No replay of past slots following
    downtime. Commit claims before networking so reads never wait on HTTP calls.
    """
    deadline = monotonic() + 45
    collected = 0
    while collected < 50 and monotonic() + 21 < deadline:
        now = int(clock())
        slot = slot_at(now)
        with bank() as conn:
            rows = query(conn, '''WITH due AS (
                SELECT t.id FROM competitor_targets t JOIN conexoes c ON c.id=t.conexao_id
                WHERE t.active AND c.status='ativa' AND (t.last_slot IS NULL OR t.last_slot < %s)
                ORDER BY t.last_slot NULLS FIRST,t.id
                FOR UPDATE OF t SKIP LOCKED LIMIT 1)
                UPDATE competitor_targets t SET last_slot=%s,attempted_at=%s,error='Consulta em andamento'
                FROM due WHERE t.id=due.id RETURNING t.*''', (slot, slot, now))
            if not rows:
                break
            target = rows[0]
            shops = query(conn, 'SELECT access_token,expires_at FROM conexoes WHERE id=%s',
                          (target['conexao_id'],))
        shop = shops[0] if shops else {}
        if not shop.get('access_token') or (shop.get('expires_at') or 0) <= now + 30:
            result = dict(price=None, full=None, title=None, seller_id=None,
                          error='Aguardando renovação da conexão da loja com o Mercado Livre')
        else:
            result = observe(target['item_id'], target['seller_id'], shop['access_token'], getter)
        stamp = int(clock())
        price_changed = result['price'] is not None and target['price'] is not None and result['price'] != target['price']
        full_changed = result['full'] is not None and target['full_state'] is not None and result['full'] != target['full_state']
        with bank() as conn:
            # A newer slot could have started if a worker was suspended externally.
            # Never let an old completion overwrite the current state.
            current = query(conn, 'SELECT last_slot FROM competitor_targets WHERE id=%s FOR UPDATE', (target['id'],))
            if not current or current[0]['last_slot'] != slot:
                continue
            execute(conn, '''INSERT INTO competitor_observations
                (target_id,slot,observed_at,price,previous_price,full_state,previous_full,price_changed,full_changed,error)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                    (target['id'],slot,stamp,result['price'],target['price'],result['full'],
                     target['full_state'],price_changed,full_changed,result['error']))
            execute(conn, '''UPDATE competitor_targets SET title=COALESCE(%s,title),
                seller_id=COALESCE(%s,seller_id),error=%s,
                previous_price=CASE WHEN %s THEN price ELSE previous_price END,
                price_changed_at=CASE WHEN %s THEN %s ELSE price_changed_at END,
                price=COALESCE(%s,price),price_at=CASE WHEN %s THEN %s ELSE price_at END,
                previous_full=CASE WHEN %s THEN full_state ELSE previous_full END,
                full_changed_at=CASE WHEN %s THEN %s ELSE full_changed_at END,
                full_state=COALESCE(%s,full_state),full_at=CASE WHEN %s THEN %s ELSE full_at END
                WHERE id=%s''',
                    (result['title'],result['seller_id'],result['error'],price_changed,price_changed,stamp,
                     result['price'],result['price'] is not None,stamp,full_changed,full_changed,stamp,
                     result['full'],result['full'] is not None,stamp,target['id']))
        collected += 1
    return collected
