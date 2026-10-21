"""Shared browser protections for legacy HTML forms and same-origin fetch calls."""
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import os
import re
import secrets
import time
from urllib.parse import urljoin, urlsplit

from flask import abort, request, session

SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
# These handlers already enforce a session-bound token before every write.
SCOPED_CSRF = {'competitor_list', 'competitor_state', 'listing_interventions',
               'auditoria_frete', 'crm_edit', 'crm_contact', 'crm_import',
               'crm_review', 'crm_link_draft', 'crm_settings'}


def session_key():
    key = os.getenv('SECRET_KEY', '')
    if key and key != 'troque-esta-chave':
        return key
    if os.getenv('RENDER') or os.getenv('DATABASE_URL'):
        raise RuntimeError('Configure a private SECRET_KEY before starting the application.')
    # Local previews must never share a publicly known signing key.
    return secrets.token_urlsafe(48)


def init_security_schema(conn, execute):
    execute(conn, '''CREATE TABLE IF NOT EXISTS auth_rate_limits (
        bucket TEXT NOT NULL, window_id BIGINT NOT NULL, attempts INTEGER NOT NULL,
        PRIMARY KEY(bucket, window_id))''')


def auth_attempt_allowed(bank, execute, scope, identity):
    """Persistent, atomic limits shared by Gunicorn workers; no raw identities stored."""
    window = int(time.time()) // 900
    buckets = [(scope + ':identity:' + identity.strip().casefold(), 20),
               (scope + ':peer:' + (request.remote_addr or 'unknown'), 100)]
    allowed = True
    with bank() as conn:
        execute(conn, 'DELETE FROM auth_rate_limits WHERE window_id < %s', (window - 1,))
        for value, limit in buckets:
            key = hashlib.sha256(value.encode()).hexdigest()
            row = execute(conn, '''INSERT INTO auth_rate_limits(bucket,window_id,attempts)
                VALUES (%s,%s,1) ON CONFLICT(bucket,window_id) DO UPDATE
                SET attempts=LEAST(auth_rate_limits.attempts+1,10000)
                RETURNING attempts''', (key, window)).fetchone()
            allowed = allowed and row[0] <= limit
    return allowed


class FormTokens(HTMLParser):
    """Insert only into real local POST forms, never script strings or external forms."""
    def __init__(self, source, token):
        super().__init__(convert_charrefs=False)
        self.source, self.token, self.insertions = source, token, []
        self.offsets = [0]
        self.offsets.extend(m.end() for m in re.finditer('\n', source))

    def handle_starttag(self, tag, attrs):
        if tag != 'form':
            return
        attrs = dict(attrs)
        action = urlsplit(urljoin(request.url, attrs.get('action') or request.url))
        here = urlsplit(request.url)
        if (attrs.get('method', 'get').lower() == 'post'
                and (action.scheme, action.netloc) == (here.scheme, here.netloc)):
            line, col = self.getpos()
            self.insertions.append(self.offsets[line - 1] + col + len(self.get_starttag_text()))

    def render(self):
        result = self.source
        field = "<input type='hidden' name='_csrf' value='" + html.escape(self.token, quote=True) + "'>"
        for position in reversed(self.insertions):
            result = result[:position] + field + result[position:]
        return result


def install_security(app):
    production = bool(os.getenv('RENDER'))
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=dt.timedelta(hours=12),
        SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        MAX_FORM_MEMORY_SIZE=512 * 1024, MAX_FORM_PARTS=100,
    )
    if production:
        app.config['TRUSTED_HOSTS'] = ['app.keiperconsultoria.com.br', 'app-keiper.onrender.com']

    @app.before_request
    def browser_request_security():
        # Existing individually protected modules retain their own scoped tokens.
        scoped = request.endpoint in SCOPED_CSRF
        if request.method not in SAFE_METHODS:
            if request.headers.get('Sec-Fetch-Site') == 'cross-site':
                abort(400, 'Requisição de outro site bloqueada.')
            origin = request.headers.get('Origin')
            if origin and urlsplit(origin).netloc != request.host:
                abort(400, 'Origem inválida.')
            if not scoped:
                expected = session.get('_csrf', '')
                supplied = request.headers.get('X-CSRF-Token') or request.form.get('_csrf', '')
                if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
                    abort(400, 'Formulário expirado. Recarregue a página e tente novamente.')
        # Legacy refresh links must not be triggered by embedding or cross-site navigation.
        if request.endpoint in {'atualizar', 'atualizar_tipo', 'logout'} and request.headers.get('Sec-Fetch-Site') in {'cross-site', 'same-site'}:
            abort(400)

    @app.after_request
    def browser_response_security(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'"
        if production or request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if response.mimetype in {'text/html', 'application/json'} and not response.direct_passthrough:
            response.headers['Cache-Control'] = 'no-store'
            if response.mimetype == 'text/html' and response.status_code < 400:
                token = session.setdefault('_csrf', secrets.token_urlsafe(32))
                source = response.get_data(as_text=True)
                parser = FormTokens(source, token)
                parser.feed(source)
                source = parser.render()
                # Install before page scripts so existing fetch-based forms also work.
                script = '''<script>(function(){const token=TOKEN,original=window.fetch;
window.fetch=function(input,init){const req=new Request(input,init),url=new URL(req.url);
if(url.origin===location.origin&&!['GET','HEAD','OPTIONS'].includes(req.method.toUpperCase())){
const headers=new Headers(req.headers);headers.set('X-CSRF-Token',token);
return original.call(this,new Request(req,{headers}));}return original.call(this,req);};})();</script>'''.replace('TOKEN', json.dumps(token))
                match = re.search(r'<head\b[^>]*>', source, re.I)
                if match:
                    source = source[:match.end()] + script + source[match.end():]
                else:
                    source = script + source
                response.set_data(source)
        return response
