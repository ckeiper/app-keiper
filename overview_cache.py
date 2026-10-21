"""Very short per-worker read-through cache for the store overview.

The key includes the authorized store scope and effective filter parameters.
Never cache errors or return a broader store set than the caller requested.
"""
from collections import OrderedDict
import threading
import time

TTL_SECONDS = 20
MAX_ENTRIES = 24
_cache = OrderedDict()
_lock = threading.Lock()

def load_cached_overview(shops, args, banco, query, loader, clock=time.monotonic):
    scope = tuple(sorted((int(s["id"]), str(s.get("status") or "")) for s in shops))
    filters = tuple(sorted((str(key), str(value)) for key, value in args.items()))
    key = (scope, filters)
    now = clock()
    with _lock:
        saved = _cache.get(key)
        if saved is not None and now - saved[0] < TTL_SECONDS:
            _cache.move_to_end(key)
            return saved[1]
        if saved is not None:
            del _cache[key]
    # Calculation stays outside the mutex. Do not cache partial failures.
    data = loader(shops, args, banco, query)
    with _lock:
        _cache[key] = (clock(), data)
        _cache.move_to_end(key)
        while len(_cache) > MAX_ENTRIES:
            _cache.popitem(last=False)
    return data
