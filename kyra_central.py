"""Admin-only, read-only consolidated KEVIA snapshot. No marketplace or paid API calls."""
from html import escape


def central_rows(shops, runs):
    latest = {int(r['conexao_id']): r for r in runs}
    output = []
    for shop in shops:
        cid = int(shop['id'])
        run = latest.get(cid)
        result = (run or {}).get('result') or {}
        if not isinstance(result, dict):
            result = {}
        items = result.get('recommendations') or []
        if not isinstance(items, list):
            items = []
        items = [i for i in items if isinstance(i, dict)]
        items.sort(key=lambda i: -int(i.get('priority') or 0))
        quality = bool(result.get('quality'))
        output.append(dict(id=cid, name=str(shop['cliente']), status=(run or {}).get('status'),
                           day=(run or {}).get('day'), findings=items[:3],
                           quality=quality, priority=int(items[0].get('priority') or 0) if items else 0))
    return sorted(output, key=lambda x: (-x['priority'], x['name'].casefold(), x['id']))


def render_central(rows):
    count = sum(bool(r['findings']) for r in rows)
    html = """<style>
    .kyra-head{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}
    .kyra-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:14px;margin-top:18px}
    .kyra-shop{border:1px solid var(--border,#334155);border-radius:14px;padding:18px;background:var(--card,#17233b)}
    .kyra-shop h3{margin:0 0 6px}.kyra-muted{opacity:.75;font-size:.9rem}
    .kyra-shop a{display:inline-block;margin-top:12px;color:inherit;text-decoration:underline;text-underline-offset:3px}
    .kyra-finding{border-top:1px solid var(--border,#334155);padding-top:10px;margin-top:10px}
    </style><section class="card"><div class="kyra-head"><div><h2>KEVIA · Central de Inteligência</h2>
    <p>Nome provisório. Diagnósticos diários para revisão humana; nenhuma campanha é alterada.</p></div></div>"""
    html += '<p>'+str(len(rows))+' lojas · '+str(count)+' com recomendações no último diagnóstico disponível.</p></section>'
    html += '<div class="kyra-grid">'
    for row in rows:
        html += '<section class="kyra-shop"><h3>'+escape(row['name'])+'</h3>'
        html += '<p class="kyra-muted">Última análise: '+escape(str(row['day'] or 'não disponível'))+'</p>'
        if row['status'] in ('running', 'rules_ready', 'failed'):
            html += '<p>Execução: '+escape(str(row['status']))+'</p>'
        if row['quality']:
            html += '<p>Qualidade dos dados com ressalvas</p>'
        if row['findings']:
            for item in row['findings']:
                html += '<div class="kyra-finding"><strong>'+escape(str(item.get('title') or 'Recomendação'))+'</strong>'
                html += '<p>'+escape(str(item.get('action') or ''))+'</p></div>'
        else:
            html += '<p>Nenhuma recomendação registrada nesta análise.</p>' if row['day'] else '<p>Aguardando primeira análise.</p>'
        html += '<a href="/ia-keiper/'+str(row['id'])+'">Ver análise e evidências →</a></section>'
    return html+'</div>'
