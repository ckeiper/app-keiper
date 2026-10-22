"""Store navigation with line icons and native keyboard-accessible submenus."""
from html import escape

PATHS = {
    'home': 'M3 10 12 3l9 7v10H15v-7H9v7H3Z',
    'star': 'm12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z',
    'tag': 'M3 3h8l10 10-8 8L3 11ZM7 7h.01',
    'chart': 'M3 3v18h18M6 15l5-6 4 3 6-8',
    'box': 'm3 7 9-4 9 4v11l-9 4-9-4ZM3 7l9 4 9-4M12 11v11',
    'message': 'M4 3h16v14H9l-5 4ZM8 7h8M8 11h5',
    'speaker': 'M3 9h5l10-5v16L8 15H3ZM8 15l2 6M21 9v6',
    'money': 'M3 5h18v14H3ZM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',
    'truck': 'M2 5h12v12H2ZM14 10h5l3 4v3h-8M6 17a2 2 0 1 0 0 4 2 2 0 0 0 0-4M18 17a2 2 0 1 0 0 4 2 2 0 0 0 0-4',
    'refresh': 'M20 7a9 9 0 1 0 1 9M20 2v6h-6',
    'search': 'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM15 15l6 6',
    'trash': 'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7',
    'back': 'M20 12H4m6-6-6 6 6 6',
}


def icon(name):
    return "<svg class='km-icon' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><path d='" + PATHS[name] + "'/></svg>"


CSS = """<style>
.layout>.menu-lateral{gap:3px;padding:14px 9px}
.layout>.menu-lateral a.item,.layout>.menu-lateral a.voltar,.layout>.menu-lateral summary{display:flex;align-items:center;gap:12px;min-height:44px;padding:10px 12px;font-size:13px;line-height:1.4;border-radius:9px;box-sizing:border-box}
.menu-lateral .km-icon{width:19px;height:19px;flex:0 0 19px}
.menu-lateral details{flex:0 0 auto;margin:2px 0}
.menu-lateral summary{cursor:pointer;list-style:none;color:#d5deeb;user-select:none}
.menu-lateral summary::-webkit-details-marker{display:none}
.menu-lateral summary:after{content:'';width:6px;height:6px;border-right:1px solid currentColor;border-bottom:1px solid currentColor;transform:rotate(45deg);margin-left:auto;margin-right:3px;transition:transform .15s}
.menu-lateral details[open]>summary:after{transform:rotate(225deg)}
.menu-lateral summary:hover{background:#253650;color:#fff}
.menu-lateral details.km-active>summary{background:#1e3352;color:#91bbff}
.layout>.menu-lateral a.item.atual{background:#243e63;color:#81b2ff}
.menu-lateral .km-submenu{margin:4px 0 8px 21px;padding-left:9px;border-left:1px solid #314057}
.layout>.menu-lateral .km-submenu a.item{font-size:12px;padding-left:12px;min-height:38px}
.menu-lateral a:focus-visible,.menu-lateral summary:focus-visible{outline:2px solid #91bbff;outline-offset:2px}
.menu-lateral .km-tools{margin-top:18px;padding-top:10px;border-top:1px solid #314057}
@media(prefers-reduced-motion:reduce){.menu-lateral summary:after{transition:none}}
</style>"""


def render_store_sidebar(cid, section):
    cid = str(int(cid))

    def link(key, label, route, symbol=None, danger=False):
        current = key == section
        return ("<a class='item" + (' atual' if current else '') + (' perigo' if danger else '')
                + "' href='" + escape(route, quote=True) + "'"
                + (" aria-current='page'" if current else '') + ">"
                + (icon(symbol) if symbol else '') + escape(label) + '</a>')

    def item(key, label, route, symbol=None):
        return link(key, label, '/' + route + '/' + cid, symbol)

    def group(label, symbol, entries):
        active = any(key == section for key, _, _ in entries)
        return ("<details" + (" class='km-active' open" if active else '') + "><summary>"
                + icon(symbol) + escape(label) + "</summary><div class='km-submenu'>"
                + ''.join(item(*entry) for entry in entries) + '</div></details>')

    menu = CSS + "<nav class='menu-lateral' aria-label='Menu da loja'>"
    menu += "<a class='voltar' href='/painel'>" + icon('back') + 'Todas as lojas</a>'
    menu += item('resumo', 'Resumo', 'painel', 'home')
    menu += item('prioridades', 'Minhas prioridades', 'prioridades', 'star')
    menu += group('Anúncios', 'tag', [('anuncios', 'Todos os anúncios', 'anuncios'), ('full', 'Full e vendas', 'full')])
    menu += item('demandas', 'Demandas', 'demandas', 'message')
    menu += item('promocoes', 'Promoções', 'promocoes', 'tag')
    menu += group('Publicidade', 'speaker', [('ads', 'Product Ads', 'ads'), ('campanhas', 'Campanhas', 'campanhas')])
    menu += group('Métricas', 'chart', [('desempenho', 'Desempenho', 'desempenho'), ('vendas', 'Vendas', 'vendas')])
    menu += group('Financeiro', 'money', [('custos', 'Custos', 'custos'), ('auditoria_frete', 'Auditoria de frete', 'auditoria-frete')])
    menu += "<div class='km-tools'>" + link('', 'Atualizar dados', '/atualizar?cid=' + cid, 'refresh')
    menu += link('', 'Diagnóstico', '/diagnostico', 'search')
    menu += link('', 'Excluir loja', '/excluir/' + cid, 'trash', danger=True)
    return menu + '</div></nav>'