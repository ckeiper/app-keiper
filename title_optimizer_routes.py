"""Title composition only: no endpoint in this module updates a listing."""
import hmac
import re
import secrets
from html import escape
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from flask import abort, jsonify, request, send_file, session
from title_optimizer_identity import identify
from listing_content_snapshot import ContentUnavailable

TITLE = 'Otimizador de Títulos'
PATH = '/otimizador-titulos'
ROOT = Path(__file__).resolve().parent


def render(title='', lookup='', csrf='', identity_path=''):
    body = (ROOT / 'static/title_optimizer.html').read_text(encoding='utf-8')
    # Single pass prevents user text containing placeholders from becoming markup.
    values = dict(title=escape(title, quote=True), lookup=lookup, csrf=escape(csrf, quote=True), identity_path=escape(identity_path, quote=True))
    return re.sub(r'\{\{(title|lookup|csrf|identity_path)\}\}', lambda match: values[match[1]], body)


def register(app, login_required, can_view, bank, query, page, store_page, resolve_token=None, get=None):
    @app.get(PATH + '/extensao.zip')
    @login_required
    def title_optimizer_extension():
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            for name in ('manifest.json', 'dashboard.js', 'search.js', 'collector.js', 'README.md'):
                archive.write(ROOT / 'extensions/title_optimizer' / name, name)
        output.seek(0)
        return send_file(output, mimetype='application/zip', as_attachment=True, download_name='otimizador-titulos-keiper.zip')

    @app.post(PATH + '/<int:cid>/identificar')
    @login_required
    def title_optimizer_identify(cid):
        if not can_view(cid):
            abort(403)
        token = session.get('_csrf')
        supplied = request.headers.get('X-CSRF-Token', '')
        if not isinstance(token, str) or not hmac.compare_digest(token.encode(), supplied.encode()):
            abort(400)
        payload = request.get_json(silent=True)
        item = payload.get('item') if isinstance(payload, dict) else None
        if not isinstance(item, str) or not re.fullmatch(r'MLB[0-9]{1,20}', item):
            abort(400)
        with bank() as conn:
            rows = query(conn, '''SELECT c.* FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id
                WHERE c.id=%s AND a.item_id=%s''', (cid, item))
        if not rows:
            abort(404)
        if resolve_token is None or get is None:
            return jsonify(error='Leitura do anúncio indisponível.'), 503
        try:
            result = identify(resolve_token(rows[0]), rows[0]['user_id'], item, get)
        except ContentUnavailable as exc:
            return jsonify(error=str(exc)), 502
        return jsonify(result)

    @app.get(PATH)
    @app.get(PATH + '/<int:cid>')
    @login_required
    def title_optimizer(cid=None):
        title = ''; lookup = ''; identity_path = ''
        csrf = session.setdefault('_csrf', secrets.token_urlsafe(32))
        if cid is not None:
            if not can_view(cid):
                abort(403)
            with bank() as conn:
                shops = query(conn, 'SELECT cliente FROM conexoes WHERE id=%s', (cid,))
                if not shops:
                    abort(404)
                listings = query(conn, '''SELECT item_id,titulo FROM anuncios
                    WHERE conexao_id=%s AND item_id LIKE 'MLB%%'
                    ORDER BY titulo,item_id LIMIT 100''', (cid,))
                selected = request.args.get('item', '')
                if selected:
                    rows = query(conn, '''SELECT titulo FROM anuncios WHERE conexao_id=%s
                        AND item_id=%s AND item_id LIKE 'MLB%%' ''', (cid, selected))
                    if not rows:
                        abort(404)
                    title = rows[0]['titulo'] or ''
            options = ''.join(f'<option value="{escape(row["item_id"], quote=True)}">{escape(row["titulo"] or row["item_id"])}</option>' for row in listings)
            lookup = ('<div class="to-integrated"><label for="title-item">Anúncio integrado (opcional)</label>'
                      f'<div class="to-inline"><input id="title-item" list="title-items" value="{escape(selected, quote=True)}" placeholder="Busque pelo título ou informe o código MLB">'
                      '<button type="button" id="title-identify">Identificar produto</button></div>'
                      f'<datalist id="title-items">{options}</datalist></div>')
            identity_path = f'{PATH}/{cid}/identificar'
        body = render(title, lookup, csrf, identity_path)
        return page(TITLE, body) if cid is None else store_page(TITLE, cid, shops[0]['cliente'], 'otimizador', body)
