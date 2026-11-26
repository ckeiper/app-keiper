from html import escape

from flask import abort, request

from section_help import STYLE, section_help


TITLE = 'Otimizador de Títulos'
PATH = '/otimizador-titulos'

FORM = """
<style>
.title-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:12px;margin:12px 0}
.title-tool label{display:grid;gap:5px;margin-bottom:8px}
.title-tool input{width:100%;box-sizing:border-box;padding:9px;border-radius:8px;border:1px solid currentColor;background:transparent;color:inherit}
.title-tool button{padding:8px 12px;cursor:pointer}
.title-tool li{overflow-wrap:anywhere;margin-bottom:8px}
</style>
<section class="card title-tool">
{help}
{lookup}
<form id="title-search">
<label>Título original <input name="original" value="{title}" maxlength="300" required></label>
<div class="title-fields">
<label>Produto <input name="product" maxlength="100" required></label>
<label>Marca <input name="brand" maxlength="60"></label>
<label>Modelo <input name="model" maxlength="60"></label>
</div>
<button type="submit">Buscar concorrentes</button>
</form>
<p id="title-status" role="status"></p>
</section>
<section class="card title-tool" id="title-results" hidden></section>
<script type="module" src="/static/title_optimizer_view.mjs"></script>
"""


def register(app, login_required, can_view, bank, query, page, store_page):
    @app.get(PATH)
    @app.get(PATH + '/<int:cid>')
    @login_required
    def title_optimizer(cid=None):
        title = ''
        lookup = ''
        if cid is not None:
            if not can_view(cid):
                abort(403)
            with bank() as conn:
                shops = query(conn, 'SELECT cliente FROM conexoes WHERE id=%s', (cid,))
                if not shops:
                    abort(404)
                listings = query(conn, """
                    SELECT item_id,titulo FROM anuncios
                    WHERE conexao_id=%s AND item_id LIKE 'MLB%%'
                    ORDER BY titulo,item_id LIMIT 100
                """, (cid,))
                selected = request.args.get('item', '')
                if selected:
                    rows = query(conn, """
                        SELECT titulo FROM anuncios WHERE conexao_id=%s
                        AND item_id=%s AND item_id LIKE 'MLB%%'
                    """, (cid, selected))
                    if not rows:
                        abort(404)
                    title = rows[0]['titulo'] or ''
            options = ''.join(
                f'<option value="{escape(row["item_id"])}">{escape(row["titulo"] or row["item_id"])}</option>'
                for row in listings
            )
            lookup = ('<form method="get"><label>Anúncio integrado (opcional)'
                      '<input name="item" list="title-items" placeholder="Título ou código MLB" required></label>'
                      f'<datalist id="title-items">{options}</datalist>'
                      '<button>Carregar anúncio</button></form>')
        help_text = section_help(TITLE, 'Como funciona', '<p>Informe produto, marca e modelo para a busca. A extensão coleta títulos públicos. As frequências descrevem a amostra consultada.</p>')
        body = STYLE + FORM.replace('{help}', help_text).replace('{title}', escape(title)).replace('{lookup}', lookup)
        if cid is None:
            return page(TITLE, body)
        return store_page(TITLE, cid, shops[0]['cliente'], 'otimizador', body)
