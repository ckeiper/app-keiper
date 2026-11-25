"""Durable receipt for one explicitly confirmed reactivation request."""
import re
import time

from listing_interventions import record_reactivation


def init_schema(conn, execute):
    execute(conn, """CREATE TABLE IF NOT EXISTS listing_reactivation_requests (
        conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        item_id TEXT NOT NULL, request_key VARCHAR(48) NOT NULL,
        created_by INTEGER NOT NULL, created_at BIGINT NOT NULL,
        sent_to_marketplace BOOLEAN NOT NULL DEFAULT FALSE,
        history_id BIGINT REFERENCES listing_interventions(id) ON DELETE SET NULL,
        PRIMARY KEY(conexao_id,item_id,request_key))""")


def validate_key(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{24,48}', value):
        raise ValueError('Atualize a página e confirme novamente a reativação.')
    return value


def reserve(bank, query, cid, item_id, actor, key):
    # Commit the receipt before sending an external command. A process crash
    # leaves a receipt that allows status verification, but never another PUT.
    with bank() as conn:
        rows = query(conn, """INSERT INTO listing_reactivation_requests
            (conexao_id,item_id,request_key,created_by,created_at)
            VALUES(%s,%s,%s,%s,%s)
            ON CONFLICT(conexao_id,item_id,request_key) DO NOTHING RETURNING request_key""",
            (cid, item_id, key, actor, int(time.time())))
    return bool(rows)


def mark_sent(bank, query, cid, item_id, key):
    with bank() as conn:
        query(conn, """UPDATE listing_reactivation_requests SET sent_to_marketplace=TRUE
            WHERE conexao_id=%s AND item_id=%s AND request_key=%s RETURNING request_key""",
            (cid, item_id, key))


def was_sent(conn, query, cid, item_id, key):
    rows = query(conn, """SELECT sent_to_marketplace FROM listing_reactivation_requests
        WHERE conexao_id=%s AND item_id=%s AND request_key=%s""", (cid, item_id, key))
    return bool(rows and rows[0]['sent_to_marketplace'])


def confirm(conn, query, cid, item_id, key):
    receipt = query(conn, """SELECT created_by,created_at,history_id
        FROM listing_reactivation_requests WHERE conexao_id=%s AND item_id=%s AND request_key=%s""",
        (cid, item_id, key))[0]
    if receipt['history_id'] is not None:
        return receipt['history_id']
    history_id = record_reactivation(
        conn, query, cid, item_id, receipt['created_by'],
        int(time.time()), 'reactivate_' + key,
    )
    query(conn, """UPDATE listing_reactivation_requests SET history_id=%s
        WHERE conexao_id=%s AND item_id=%s AND request_key=%s RETURNING history_id""",
        (history_id, cid, item_id, key))
    return history_id
