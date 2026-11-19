"""Shared navigation and entry point for one store-owned listing."""
import re
from html import escape
from flask import request, session

GROUPS = (
    ('desempenho', 'Desempenho', (
        ('/diagnostico/{cid}/{item}', 'Vendas, visitas e Ads', False),
        ('/anuncios/{cid}/{item}/padrao-semanal', 'Padrão semanal', True),
        ('/anuncios/{cid}/{item}/conferencia-media', 'Tendência de vendas', True),
        ('/anuncios/{cid}/{item}/metas-vendas', 'Metas de vendas', True),
        ('/anuncios/{cid}/{item}/primeiros-30-dias', 'Primeiros 30 dias', True),
        ('/anuncios/{cid}/{item}/relatorio-consolidado', 'Relatório do anúncio', True),
    )),
    ('editar', 'Editar anúncio', (
        ('/anuncios/{cid}/{item}/completar-ficha', 'Ficha técnica e campos ocultos', True),
        ('/anuncios/{cid}/{item}/conteudo-atual', 'Título e descrição', True),
        ('/anuncios/{cid}/{item}/imagem-principal', 'Imagens', True),
        ('/anuncios/{cid}/{item}/perguntas', 'Perguntas', True),
        ('/anuncios/{cid}/{item}/avaliacoes', 'Avaliações', True),
    )),
    ('preco-estoque', 'Preço e estoque', (
        ('/anuncios/{cid}/{item}/rentabilidade', 'Rentabilidade e descontos', True),
        ('/anuncios/{cid}/{item}/cotacao-tarifa', 'Tarifas', True),
        ('/anuncios/{cid}/{item}/parcelamento', 'Parcelamento', True),
        ('/anuncios/{cid}/{item}/metas', 'Metas de estoque', True),
        ('/anuncios/{cid}/{item}/kits', 'Kits', True),
        ('/full/{cid}?item_id={item}', 'Estoque Full', False),
    )),
    ('diagnostico', 'Diagnóstico', (
        ('/anuncios/{cid}/{item}/conteudo', 'Revisão de conteúdo', True),
        ('/anuncios/{cid}/{item}/relatorio-revisao', 'Problemas e recomendações', True),
        ('/diagnostico/anuncios/{cid}/{item}', 'Conferir preço no Mercado Livre', True),
    )),
    ('historico', 'Histórico e tarefas', (
        ('/anuncios/{cid}/{item}/acoes', 'Histórico de alterações', False),
        ('/anuncios/{cid}/{item}/tarefas', 'Tarefas', True),
        ('/anuncios/{cid}/{item}/calendario', 'Calendário', True),
        ('/anuncios/{cid}/{item}/reativacao', 'Reativação', True),
    )),
)

STYLE = """<style>
.listing-workspace{padding:16px;margin-bottom:18px;border:1px solid #34516e;border-radius:14px;background:#102238;color:#eaf2ff;min-width:0}
.listing-workspace header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.listing-workspace h2{margin:0;color:inherit;font-size:18px}.listing-workspace small{display:block;color:#bdcce1;margin-top:6px}
.listing-workspace a{color:#b9e5ff;text-decoration:none}.listing-workspace nav{display:flex;gap:6px;flex-wrap:wrap;margin-top:16px}
.listing-workspace nav a{padding:9px 12px;border:1px solid #34516e;border-radius:8px;font-size:13px}
.listing-workspace nav a[aria-current]{background:#2469a3;color:white;border-color:#76b9e3}
.listing-workspace .lw-functions{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-top:16px}
.listing-workspace .lw-functions a{padding:14px;border:1px solid #34516e;border-radius:9px;background:#182e49}
.conteudo:has(>.listing-workspace) .diag-nav,.conteudo:has(>.listing-workspace) .diag-hint{display:none}
.listing-workspace a:focus-visible{outline:3px solid #85c8ec;outline-offset:3px}
@media(max-width:600px){.listing-workspace{padding:12px}.listing-workspace nav a{flex:1 1 40%;text-align:center}}
html[data-theme=light] .listing-workspace{background:#fff;color:#253a56}
html[data-theme=light] .listing-workspace a{color:#245a8a}
html[data-theme=light] .listing-workspace .lw-functions a{background:#f3f7fc}
html[data-theme=light] .listing-workspace nav a[aria-current]{color:#fff}
</style>"""


def links(group, cid, item, admin):
    return [(path.format(cid=cid, item=item), label)
            for key, name, actions in GROUPS if key == group
            for path, label, restricted in actions if admin or not restricted]


def navigation(cid, item, path, admin, group=None, title=None):
    if not re.fullmatch(r'MLB[0-9]{1,20}', str(item)):
        return ''
    base = f'/anuncios/{int(cid)}/{item}'
    if group is None:
        group = next((key for key, name, actions in GROUPS
                      for target, label, restricted in actions
                      if path == target.format(cid=cid, item=item).split('?')[0]), None)
        if group is None and path.startswith(base+'/'):
            group = 'editar' if 'ficha' in path or 'atributo' in path else 'historico' if '/metas/avisos' in path else None
    if group is None:
        return ''
    out = STYLE + '<section class="listing-workspace" aria-label="Área do anúncio"><header><div><h2>'
    out += escape(title or item) + '</h2><small>' + escape(item) + '</small></div>'
    out += f'<a href="/anuncios/{int(cid)}">Todos os anúncios</a></header><nav aria-label="Funções do anúncio">'
    for key, name, actions in GROUPS:
        current = ' aria-current="page"' if key == group else ''
        out += f'<a href="{base}?aba={key}"{current}>' + name + '</a>'
    out += '</nav><div class="lw-functions">'
    for target, label in links(group, cid, item, admin):
        current = ' aria-current="page"' if path == target.split('?')[0] else ''
        out += '<a href="' + escape(target, quote=True) + '"' + current + '>' + label + '</a>'
    return out + '</div></section>'


def register(app, login_required, can_view, bank, query, shop_page):
    @app.get('/anuncios/<int:cid>/<item_id>')
    @login_required
    def listing_workspace(cid, item_id):
        if not can_view(cid):
            return 'Acesso restrito', 403
        if not re.fullmatch(r'MLB[0-9]{1,20}', item_id):
            return 'Anúncio não encontrado', 404
        group = request.args.get('aba', 'desempenho')
        if group not in {key for key, name, actions in GROUPS}:
            return 'Aba não encontrada', 404
        with bank() as conn:
            rows = query(conn, """SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a
                ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s""", (cid, item_id))
        if not rows:
            return 'Anúncio não encontrado nesta loja', 404
        body = navigation(cid, item_id, request.path, session.get('tipo') == 'admin',
                          group=group, title=rows[0]['titulo'])
        return shop_page('Anúncio', cid, rows[0]['cliente'], 'anuncios', body)
