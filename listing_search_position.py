"""Manual observations of the Mercado Livre results page, scoped to a listing."""
from contextlib import closing
from hmac import compare_digest
from html import escape
import re
from secrets import token_urlsafe
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from flask import redirect, request, session
from profitability_view import CSS


TITLE = 'Posição na busca'
LABELS = {'organic': 'Orgânico', 'sponsored': 'Patrocinado',
          'unknown': 'Tipo não identificado', 'not_seen': 'Não localizado nas páginas conferidas'}
PAGE_SIZE = 20
BRASILIA = ZoneInfo('America/Sao_Paulo')


def init_schema(conn, execute):
    execute(conn, 'SELECT pg_advisory_xact_lock(186144287)')
    execute(conn, """
        CREATE TABLE IF NOT EXISTS listing_search_observations (
            id BIGSERIAL PRIMARY KEY, conexao_id INTEGER NOT NULL, item_id TEXT NOT NULL,
            keyword TEXT NOT NULL CHECK (char_length(keyword) BETWEEN 1 AND 120),
            keyword_key TEXT NOT NULL, cep TEXT NOT NULL, filters TEXT NOT NULL,
            result TEXT NOT NULL CHECK (result IN ('organic','sponsored','unknown','not_seen')),
            page INTEGER NOT NULL CHECK (page BETWEEN 1 AND 100),
            slot INTEGER,
            observed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            actor_id INTEGER NOT NULL, submission_key TEXT NOT NULL,
            UNIQUE(conexao_id,item_id,submission_key),
            CHECK ((result='not_seen' AND slot IS NULL) OR
                   (result<>'not_seen' AND slot IS NOT NULL AND slot BETWEEN 1 AND 200))
        )
    """)
    execute(conn, """CREATE INDEX IF NOT EXISTS listing_search_observations_history
        ON listing_search_observations(conexao_id,item_id,keyword_key,id DESC)""")
    execute(conn, """CREATE INDEX IF NOT EXISTS listing_search_observations_recent
        ON listing_search_observations(conexao_id,item_id,id DESC)""")


def text_field(value, limit):
    if len(value) > limit or any(not c.isprintable() for c in value):
        raise ValueError('Confira o tamanho e os caracteres dos campos de texto.')
    return ' '.join(value.split())


def number(raw, maximum, label):
    if not re.fullmatch(r'[0-9]{1,3}', raw) or not 1 <= int(raw) <= maximum:
        raise ValueError(f'Informe {label} entre 1 e {maximum}.')
    return int(raw)


def observation(form):
    keyword = text_field(form.get('keyword', ''), 120)
    if not keyword:
        raise ValueError('Informe a palavra-chave usada na busca.')
    cep = form.get('cep', '').strip()
    if cep and not re.fullmatch(r'[0-9]{5}-?[0-9]{3}', cep):
        raise ValueError('Informe um CEP com oito dígitos ou deixe o campo vazio.')
    result = form.get('result', '')
    if result not in LABELS:
        raise ValueError('Selecione o resultado observado.')
    page = number(form.get('page', ''), 100, 'uma página')
    raw_slot = form.get('slot', '').strip()
    if result == 'not_seen' and raw_slot:
        raise ValueError('Deixe a posição em branco quando o anúncio não for localizado.')
    slot = None if result == 'not_seen' else number(raw_slot, 200, 'uma posição')
    return keyword, keyword.casefold(), cep.replace('-', ''), text_field(form.get('filters', ''), 200), result, page, slot


def render(cid, item_id, title, csrf, submission_key, keyword, rows, before, values, error=''):
    def e(value):
        return escape(str(value), quote=True)

    def value(name, default=''):
        return e(values.get(name, default))

    path = f'/anuncios/{cid}/{item_id}/posicao-busca'
    search = ('https://lista.mercadolivre.com.br/' + quote(keyword.replace(' ', '-'), safe='')
              if keyword else '')
    options = ''.join(f'<option value="{key}"{" selected" if values.get("result") == key else ""}>{e(label)}</option>'
                      for key, label in LABELS.items())
    out = CSS + STYLE + f'''<div class="pf lsp">
        <header class="pf-hero"><span class="pf-eyebrow">Anúncios · Visibilidade</span>
          <h2>{TITLE}</h2><p>{e(title or item_id)} · {e(item_id)}</p>
          <a href="/diagnostico/{cid}/{e(item_id)}">Voltar ao diagnóstico</a>
        </header>
        <section class="pf-card"><h3>Conferir no Mercado Livre</h3>
          <p>Digite o termo que um comprador usaria. Abra a busca e confira o código do seu anúncio.
          A posição registrada é a que você observou nessa busca.</p>
          <form method="get" class="lsp-form">
            <label>Palavra-chave<input type="search" name="q" maxlength="120" value="{e(keyword)}"
                placeholder="Ex.: fone bluetooth"></label>
            <button type="submit">Preparar busca e filtrar histórico</button>
          </form>'''
    if search:
        out += f'<p><a href="{e(search)}" target="_blank" rel="noopener noreferrer">Abrir busca no Mercado Livre ↗</a></p>'
    out += f'''</section><section class="pf-card"><h3>Registrar posição observada</h3>
        <p>Conte os anúncios na ordem em que aparecem na página, incluindo os patrocinados.
        Se não localizar o anúncio, informe até qual página conferiu, começando pela primeira.</p>'''
    if error:
        out += f'<p role="alert">{e(error)}</p>'
    out += f'''<form method="post" action="{e(path)}" class="lsp-form">
        <input type="hidden" name="_csrf" value="{e(csrf)}">
        <input type="hidden" name="submission_key" value="{e(submission_key)}">
        <label>Palavra-chave<input name="keyword" required maxlength="120" value="{value('keyword', keyword)}"></label>
        <label>Resultado<select name="result" required><option value="">Selecione</option>{options}</select></label>
        <label>Página ou última página conferida<input type="number" min="1" max="100" name="page"
          required value="{value('page', 1)}"></label>
        <label>Posição na página<input type="number" min="1" max="200" name="slot" value="{value('slot')}"
          aria-describedby="lsp-slot-help"></label>
        <small id="lsp-slot-help">Deixe em branco se o anúncio não foi localizado.</small>
        <label>CEP usado, se houver<input name="cep" inputmode="numeric" maxlength="9" value="{value('cep')}"></label>
        <label>Filtros ou contexto, se houver<input name="filters" maxlength="200" value="{value('filters')}"
          placeholder="Ex.: frete grátis, ordem por relevância"></label>
        <button type="submit">Salvar observação</button>
        </form></section><section class="pf-card" id="historico"><h3>Histórico de observações</h3>
        <p>Registros manuais · horário de Brasília. Compare buscas com a mesma palavra-chave, CEP e filtros.</p>'''
    if keyword:
        out += f'<p>Palavra-chave: <strong>{e(keyword)}</strong> · <a href="{e(path)}#historico">Ver todos os termos</a></p>'
    if not rows:
        out += '<p>Nenhuma observação neste histórico.</p>'
    else:
        out += '<ul class="lsp-history">'
        for row in rows[:PAGE_SIZE]:
            stamp = row['observed_at'].astimezone(BRASILIA).strftime('%d/%m/%Y às %H:%M')
            position = (f"Até a página {row['page']}" if row['result'] == 'not_seen'
                        else f"Página {row['page']} · {row['slot']}ª posição")
            cep = row['cep'] or 'Não informado'
            out += f'''<li><strong>{e(row['keyword'])}</strong>
                <span>{e(position)} · {e(LABELS[row['result']])}</span>
                <small>{e(stamp)} · CEP: {e(cep)} · Filtros: {e(row['filters'] or 'Não informados')}</small></li>'''
        out += '</ul>'
    if len(rows) > PAGE_SIZE:
        params = urlencode({'q': keyword, 'antes': rows[PAGE_SIZE-1]['id']})
        out += f'<a href="{e(path + "?" + params)}#historico">Observações anteriores</a>'
    if before:
        out += f' <a href="{e(path + "?" + urlencode({"q": keyword}))}#historico">Observações recentes</a>'
    return out + '</section></div>'


def register(app, login_required, can_view, bank, query, execute, shop_page):
    @app.route('/anuncios/<int:cid>/<item_id>/posicao-busca', methods=['GET', 'POST'])
    @login_required
    def listing_search_position(cid, item_id):
        if session.get('tipo') != 'admin' or not can_view(cid):
            return 'Acesso restrito', 403
        if not re.fullmatch(r'MLB[0-9]{1,20}', item_id):
            return 'Anúncio não encontrado', 404
        csrf = session.setdefault('_csrf', token_urlsafe(32))
        values = request.form if request.method == 'POST' else {}
        submission = values.get('submission_key', '')
        if request.method == 'POST' and (
            not compare_digest(csrf.encode(), values.get('_csrf', '').encode())
            or not re.fullmatch(r'[A-Za-z0-9_-]{32,64}', submission)
        ):
            return 'Formulário expirado. Recarregue a página.', 400
        before = request.args.get('antes', '')
        if before and not re.fullmatch(r'[1-9][0-9]{0,17}', before):
            return 'Página de histórico inválida.', 400
        error = ''
        keyword = ''
        try:
            keyword = text_field(request.args.get('q', ''), 120)
            data = observation(values) if request.method == 'POST' else None
        except ValueError as exc:
            error, data = str(exc), None
        with closing(bank()) as conn, conn:
            shops = query(conn, """SELECT c.cliente, a.titulo FROM conexoes c JOIN anuncios a
                ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s""", (cid, item_id))
            if not shops:
                return 'Anúncio não encontrado nesta loja.', 404
            if data:
                execute(conn, """INSERT INTO listing_search_observations
                    (conexao_id,item_id,keyword,keyword_key,cep,filters,result,page,slot,actor_id,submission_key)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (conexao_id,item_id,submission_key) DO NOTHING""",
                    (cid,item_id,*data,session['usuario_id'],submission))
                params = urlencode({'q': data[0]})
                return redirect(f'/anuncios/{cid}/{item_id}/posicao-busca?{params}#historico', code=303)
            conditions, args = ['conexao_id=%s', 'item_id=%s'], [cid, item_id]
            if keyword:
                conditions.append('keyword_key=%s')
                args.append(keyword.casefold())
            if before:
                conditions.append('id<%s')
                args.append(int(before))
            rows = query(conn, """SELECT id, keyword, cep, filters, result, page, slot, observed_at
                FROM listing_search_observations WHERE """ + ' AND '.join(conditions) +
                ' ORDER BY id DESC LIMIT %s', (*args, PAGE_SIZE+1))
        body = render(cid, item_id, shops[0]['titulo'], csrf, submission or token_urlsafe(32),
                      keyword, rows, before, values, error)
        return shop_page(TITLE, cid, shops[0]['cliente'], 'anuncios', body, refresh=False), 400 if error else 200


STYLE = """<style>
.lsp :is(p,li,a){overflow-wrap:anywhere}
.lsp .pf-hero a{color:inherit;text-decoration:underline}
.lsp-form{display:grid;gap:12px;max-width:540px;margin:16px 0}
.lsp-form label{display:grid;gap:5px;min-width:0}
.lsp-form :is(input,select){min-width:0;width:100%;box-sizing:border-box;padding:10px;font:inherit}
.lsp-form button{justify-self:start;white-space:normal}
.lsp-history{padding:0;list-style:none}
.lsp-history li{display:grid;gap:5px;padding:12px 0;border-top:1px solid #8496ae}
html[data-theme=light] body .lsp .pf-hero{background:#e6f0fd!important;color:#193a60!important}
</style>"""
