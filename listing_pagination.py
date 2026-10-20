"""Bound the listing table while retaining store-wide summary cards."""

SIZES = (10, 20, 50, 100)


def listing_page(rows, args, cid):
    try:
        size = int(args.get('por_pagina', 20))
    except (ValueError, TypeError):
        size = 20
    if size not in SIZES:
        size = 20
    pages = max(1, (len(rows) + size - 1) // size)
    try:
        page = int(args.get('pagina', 1))
    except (ValueError, TypeError):
        page = 1
    page = min(pages, max(1, page))
    start = (page - 1) * size
    end = min(start + size, len(rows))
    path = '/anuncios/' + str(int(cid))
    options = ''.join(f"<option value='{n}'{' selected' if n == size else ''}>{n}</option>" for n in SIZES)
    controls = (f"<form method='get' action='{path}' style='display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:16px 0'>"
                "<label for='anuncios-por-pagina'>Anúncios por página</label>"
                f"<select id='anuncios-por-pagina' name='por_pagina'>{options}</select>"
                "<button class='btn-salvar' type='submit'>Aplicar</button></form>")
    nav = "<nav aria-label='Paginação dos anúncios' style='display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin:16px 0'>"
    nav += f"<span>Mostrando {start + 1 if rows else 0}–{end} de {len(rows)} anúncios · Página {page} de {pages}</span>"
    for label, target, enabled in (('Anterior', page - 1, page > 1), ('Próxima', page + 1, page < pages)):
        if enabled:
            nav += f"<a class='link' href='{path}?por_pagina={size}&amp;pagina={target}'>{label}</a>"
        else:
            nav += f"<span aria-disabled='true' class='muted'>{label}</span>"
    nav += '</nav>'
    return rows[start:end], controls + nav, nav if pages > 1 else ''


def paginate_table(rows, args, path, *, preserved=()):
    """Reusable bounded table output and navigation, preserving filter values."""
    from html import escape
    from urllib.parse import urlencode
    try:
        size = int(args.get("por_pagina", 20))
    except (TypeError, ValueError):
        size = 20
    if size not in SIZES:
        size = 20
    total = len(rows)
    pages = max(1, (total + size - 1) // size)
    try:
        page = int(args.get("pagina", 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, min(page, pages))
    start = (page - 1) * size
    def page_url(n):
        values = {key: str(args.get(key, "")) for key in preserved if args.get(key)}
        values.update({"por_pagina": size, "pagina": n})
        return escape(path + "?" + urlencode(values), quote=True)
    options = "".join(
        "<option value='" + str(n) + "'" + (" selected" if n == size else "") + ">"
        + str(n) + "</option>" for n in SIZES)
    hidden = "".join(
        "<input type='hidden' name='" + escape(key, quote=True) + "' value='"
        + escape(str(args.get(key, "")), quote=True) + "'>"
        for key in preserved if args.get(key))
    top = ("<form method='get' action='" + escape(path, quote=True)
           + "' class='table-page-size' style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:12px 0'>"
           + hidden + "<label>Registros por página <select name='por_pagina'>"
           + options + "</select></label><button class='btn' type='submit'>Aplicar</button></form>")
    nav = ("<nav aria-label='Paginação' style='display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:12px 0'>"
           + "<span>Exibindo " + str(start + 1 if total else 0) + "–"
           + str(min(total, start + size)) + " de " + str(total)
           + " · Página " + str(page) + " de " + str(pages) + "</span>")
    if page > 1:
        nav += "<a class='link' href='" + page_url(page - 1) + "'>← Anterior</a>"
    if page < pages:
        nav += "<a class='link' href='" + page_url(page + 1) + "'>Próxima →</a>"
    nav += "</nav>"
    return rows[start:start + size], top + nav, nav if pages > 1 else ""
