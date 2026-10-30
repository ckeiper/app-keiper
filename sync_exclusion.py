"""Cross-process exclusion shared by durable, legacy and direct full syncs."""
from contextlib import contextmanager
from threading import local

_owned = local()


@contextmanager
def store_sync_lock(connect, store_id):
    held = getattr(_owned, 'stores', None)
    if held is None:
        held = _owned.stores = set()
    if store_id in held:
        yield True
        return
    # A dedicated session keeps ownership for the whole collection, independently
    # of telemetry leases and commits made by individual collectors.
    conn = connect()
    acquired = False
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(72592, %s)", (store_id,))
            acquired = cur.fetchone()[0]
        if acquired:
            held.add(store_id)
        yield acquired
    finally:
        if acquired:
            held.discard(store_id)
        # Closing the dedicated session releases the lock, including on errors.
        conn.close()
