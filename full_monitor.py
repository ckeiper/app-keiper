"""Read-only Full stock observations. No inferred historical availability."""
import json
import re
import time
from urllib.parse import quote

MAX_ITEMS = 50
MAX_REQUESTS = 75
RUN_SECONDS = 45
METADATA_MAX_AGE = 3 * 3600


def init_full_schema(conn, execute):
    execute(conn, 'ALTER TABLE anuncios ADD COLUMN IF NOT EXISTS full_metadata_json JSONB')
    execute(conn, '''CREATE TABLE IF NOT EXISTS full_observations (
        conexao_id INTEGER NOT NULL, item_id TEXT NOT NULL, observed_at BIGINT NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('available','empty','unknown')),
        quantity INTEGER, logistics TEXT NOT NULL, evidence JSONB NOT NULL,
        PRIMARY KEY (conexao_id,item_id,observed_at))''')
    execute(conn, '''CREATE INDEX IF NOT EXISTS idx_full_observations_latest
        ON full_observations(conexao_id,item_id,observed_at DESC)''')


def full_metadata(item, seller_id, now):
    if str(item.get('seller_id')) != str(seller_id):
        return dict(collected_at=now, logistics='unknown', inventories=[], missing=True,
                    reason='Vendedor do item não confirmado')
    shipping = item.get('shipping') or {}
    kind = shipping.get('logistic_type') if isinstance(shipping, dict) else None
    logistics = 'fulfillment' if kind == 'fulfillment' else ('other' if kind else 'unknown')
    variations = item.get('variations')
    entries = variations if isinstance(variations, list) and variations else [item]
    inventories, missing = [], False
    for entry in entries:
        inventory = entry.get('inventory_id') if isinstance(entry, dict) else None
        if not isinstance(inventory, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', inventory):
            missing = True
            continue
        inventories.append(dict(inventory_id=inventory,
                                variation_id=entry.get('id') if entry is not item else None))
    return dict(collected_at=now, logistics=logistics, logistic_type=kind,
                listing_status=item.get('status'), inventories=inventories, missing=missing)


def stock_response(inventory, payload):
    if not isinstance(payload, dict) or payload.get('inventory_id') != inventory:
        return None
    quantity = payload.get('available_quantity')
    return quantity if type(quantity) is int and quantity >= 0 else None


def observe(metadata, lookup, now):
    """A positive known variant proves some stock; zero requires every variant."""
    result = dict(state='unknown', quantity=None, logistics='unknown', evidence={})
    if not isinstance(metadata, dict):
        result['evidence'] = dict(reason='Anúncio ainda não consultado')
        return result
    result['logistics'] = metadata.get('logistics', 'unknown')
    result['evidence'] = dict(metadata=metadata, inventories=[])
    stamp = metadata.get('collected_at')
    if type(stamp) is not int or not 0 <= now - stamp <= METADATA_MAX_AGE:
        result['evidence']['reason'] = 'Metadados ausentes ou desatualizados'
        return result
    known, incomplete, seen = [], bool(metadata.get('missing')), set()
    for entry in metadata.get('inventories', []):
        inventory = entry['inventory_id']
        if inventory in seen:
            continue
        seen.add(inventory)
        quantity, reason = lookup(inventory)
        result['evidence']['inventories'].append(dict(inventory_id=inventory,
                                                     quantity=quantity, reason=reason))
        if quantity is None:
            incomplete = True
        else:
            known.append(quantity)
    if not seen:
        result['evidence']['reason'] = 'Sem inventory_id oficial; estoque geral não utilizado'
    if known and any(q > 0 for q in known):
        result['state'] = 'available'
    elif seen and not incomplete:
        result['state'] = 'empty'
    if seen and not incomplete:
        result['quantity'] = sum(known)
    result['evidence']['partial'] = incomplete
    return result


def sync_full(cid, token, banco, query, execute, getter, clock=time.time,
              monotonic=time.monotonic):
    """Rotate oldest items; cap calls/time; persist failures as unknown, never zero."""
    with banco() as conn:
        rows = query(conn, '''SELECT a.item_id,a.full_metadata_json
            FROM anuncios a LEFT JOIN LATERAL (
              SELECT observed_at FROM full_observations f
              WHERE f.conexao_id=a.conexao_id AND f.item_id=a.item_id
              ORDER BY observed_at DESC LIMIT 1) last ON true
            WHERE a.conexao_id=%s ORDER BY last.observed_at NULLS FIRST,a.item_id LIMIT %s''',
                     (cid, MAX_ITEMS))
    deadline, calls, blocked, cache = monotonic() + RUN_SECONDS, 0, False, {}
    def lookup(inventory):
        nonlocal calls, blocked
        if inventory in cache:
            return cache[inventory]
        remaining = deadline - monotonic()
        if blocked or calls >= MAX_REQUESTS or remaining <= .1:
            return None, 'Coleta limitada; aguardando nova consulta'
        calls += 1
        path = '/inventories/' + quote(inventory, safe='') + '/stock/fulfillment'
        try:
            response = getter('https://api.mercadolibre.com' + path,
                              headers={'Authorization': 'Bearer ' + token},
                              timeout=(min(3, remaining / 2), min(8, remaining / 2)))
            status = response.status_code
            if status in (401, 403, 429):
                blocked = True
            if status != 200:
                answer = (None, 'HTTP ' + str(status))
            else:
                quantity = stock_response(inventory, response.json())
                answer = (quantity, None if quantity is not None else 'Resposta não verificável')
        except Exception:
            answer = (None, 'Falha de comunicação ou resposta inválida')
        cache[inventory] = answer
        return answer
    for row in rows:
        if monotonic() >= deadline or calls >= MAX_REQUESTS or blocked:
            break  # Unvisited items remain gaps; no synthetic snapshots.
        metadata = row.get('full_metadata_json')
        result = observe(metadata, lookup, int(clock()))
        with banco() as conn:
            from automatic_history import record as record_changes, full_values
            record_changes(conn,execute,cid,row['item_id'],'full',int(clock()),full_values(result))
            execute(conn, '''INSERT INTO full_observations
                (conexao_id,item_id,observed_at,state,quantity,logistics,evidence)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING''',
                    (cid,row['item_id'],int(clock()),result['state'],result['quantity'],
                     result['logistics'],json.dumps(result['evidence'], ensure_ascii=False)))
    # Unknown and unvisited observations are represented in this feature, not
    # as a failed sales stage that would suppress the overview's valid totals.
    return True
