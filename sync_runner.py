"""Run independent collection stages without aborting remaining stages/shops."""


def run_stages(cid, stages, log, resolve, clock):
    ok = True
    for category, collect in stages:
        started = int(clock())
        try:
            success = collect()
        except Exception as exc:
            # Do not persist exception text: API clients can include credentials.
            log(cid, category, 'Falha na coleta: ' + type(exc).__name__)
            ok = False
            continue
        if success is True:
            resolve(cid, category, started)
        else:
            ok = False
    return ok
