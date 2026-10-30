"""Clickable, paginated listing-performance cards. Presentation only."""
from html import escape
from urllib.parse import urlencode

CSS = """<style>
.perf-list{margin-top:18px}.perf-filter{display:flex;flex-wrap:wrap;align-items:end;gap:12px;margin:15px 0}
.perf-filter label{display:grid;gap:5px;font-size:11px;color:#718099;min-width:130px}
.perf-filter input,.perf-filter select{border:1px solid #dce3ef;border-radius:9px;padding:10px;color:#263651;background:#fff;width:100%}
.perf-filter button{border:0;border-radius:9px;padding:11px 17px;background:#6265dc;color:#fff;font-weight:700;cursor:pointer}
.perf-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:14px}
.perf-card{display:flex;flex-direction:column;gap:13px;padding:18px;border:1px solid #e4eaf5;border-radius:15px;background:#fff;color:#26334c;text-decoration:none;box-shadow:0 3px 13px #25355408;transition:transform .16s,box-shadow .16s,border-color .16s}
.perf-card:hover{transform:translateY(-3px);border-color:#7776e5;box-shadow:0 12px 28px #4c5aa326}
.perf-card:focus-visible{outline:3px solid #6265dc;outline-offset:3px}
.perf-title{font-size:13px;font-weight:750;line-height:1.5;min-height:40px}.perf-id{font-size:10px;color:#8996ad}
.perf-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px;border-top:1px solid #eff1f6;padding-top:13px}
.perf-stats small{font-size:10px;color:#8893a9;display:block;margin-bottom:5px}
.perf-stats strong{font-size:18px;color:#25344f;font-variant-numeric:tabular-nums}
.perf-bottom{margin-top:auto;display:flex;justify-content:space-between;gap:8px;align-items:center;font-size:11px;color:#5a5bd4;font-weight:700}
.perf-pill{font-size:10px;border-radius:6px;padding:4px 8px;background:#eef1f9;color:#5e6c85;display:inline-block;width:max-content}
.perf-pill.active{background:#e3f7ee;color:#147b52}.perf-pill.paused{background:#fff2df;color:#996114}
.perf-pages{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:18px;font-size:12px}.perf-pages a{color:#5d5acb;font-weight:700}
@media(prefers-reduced-motion:reduce){.perf-card{transition:none}.perf-card:hover{transform:none}}
</style>"""

def render_performance_cards(cid, rows, args, dias=30, de="", ate=""):
    search = str(args.get("busca") or "").strip()[:100]
    status = str(args.get("status") or "todos")
    if status not in ("todos", "active", "paused", "closed"):
        status = "todos"
    sort = str(args.get("ordem") or "pedidos")
    if sort not in ("pedidos", "preco", "titulo"):
        sort = "pedidos"
    visible = [r for r in rows if
               (not search or search.casefold() in
                (str(r.get("titulo") or "")+" "+str(r.get("item_id"))).casefold())
               and (status == "todos" or str(r.get("status") or "").lower() == status)]
    if sort == "preco":
        visible.sort(key=lambda r:(-float(r.get("preco") or 0),str(r["item_id"])))
    elif sort == "titulo":
        visible.sort(key=lambda r:(str(r.get("titulo") or "").casefold(),str(r["item_id"])))
    else:
        visible.sort(key=lambda r:(-int(r.get("pedidos") or 0),str(r["item_id"])))
    try:
        size = int(args.get("por_pagina", 12))
    except (TypeError,ValueError):
        size = 12
    size = size if size in (12,24,48) else 12
    pages = max(1, (len(visible)+size-1)//size)
    try:
        page = max(1,min(pages,int(args.get("pagina",1))))
    except (TypeError,ValueError):
        page = 1
    offset = (page-1)*size
    path = "/desempenho/"+str(cid)
    out = CSS+"<section class='card perf-list'><h2>Desempenho por anúncio</h2>"
    out += "<p class='muted'>Clique em qualquer card para abrir o diagnóstico. Pedidos da base legada; visitas e conversão indisponíveis.</p>"
    out += "<form method='get' action='"+path+"' class='perf-filter'>"
    for name,value in (("dias",dias),("de",de),("ate",ate)):
        out += "<input type='hidden' name='"+name+"' value='"+escape(str(value),quote=True)+"'>"
    out += "<label style='flex:2;min-width:190px'>Buscar anúncio<input type='search' name='busca' placeholder='Título ou código' value='"+escape(search,quote=True)+"'></label>"
    for name,label,choices,selected in (
        ("status","Status",[("todos","Todos"),("active","Ativos"),("paused","Pausados"),("closed","Encerrados")],status),
        ("ordem","Ordenar",[("pedidos","Mais pedidos"),("preco","Maior preço"),("titulo","Título A–Z")],sort),
        ("por_pagina","Por página",[("12","12"),("24","24"),("48","48")],str(size))):
        out += "<label>"+label+"<select name='"+name+"'>"
        out += "".join("<option value='"+key+"'"+(" selected" if key==selected else "")+">"+title+"</option>" for key,title in choices)
        out += "</select></label>"
    out += "<button type='submit'>Aplicar filtros</button></form>"
    out += "<p class='muted'>Mostrando "+str(offset+1 if visible else 0)+"–"+str(min(offset+size,len(visible)))+" de "+str(len(visible))+" anúncios</p><div class='perf-cards'>"
    for r in visible[offset:offset+size]:
        item_id = str(r["item_id"])
        name = str(r.get("titulo") or "Sem título")
        state = str(r.get("status") or "").lower()
        label = {"active":"Ativo","paused":"Pausado","closed":"Encerrado"}.get(state,"Status desconhecido")
        href = "/diagnostico/"+str(cid)+"/"+escape(item_id,quote=True)
        out += "<a class='perf-card' href='"+href+"' aria-label='Ver diagnóstico de "+escape(name,quote=True)+"'>"
        out += "<span class='perf-pill "+(state if state in ("active","paused") else "")+"'>"+label+"</span>"
        out += "<div><div class='perf-title'>"+escape(name)+"</div><div class='perf-id'>"+escape(item_id)+"</div></div>"
        out += "<div class='perf-stats'><div><small>Pedidos registrados</small><strong>"+str(int(r.get("pedidos") or 0))+"</strong></div>"
        out += "<div><small>Preço atual</small><strong>R$ "+format(float(r.get("preco") or 0),".2f")+"</strong></div></div>"
        out += "<div class='perf-bottom'><span>Visitas: indisponíveis</span><span>Diagnóstico ↗</span></div></a>"
    if not visible:
        out += "<p class='muted'>Nenhum anúncio encontrado para esses filtros.</p>"
    out += "</div><nav class='perf-pages' aria-label='Paginação de desempenho'>Página "+str(page)+" de "+str(pages)
    def page_url(n):
        params={k:str(v) for k,v in args.items()}
        params["pagina"]=str(n)
        return escape(path+"?"+urlencode(params),quote=True)
    if page>1:
        out += " · <a href='"+page_url(page-1)+"'>← Anterior</a>"
    if page<pages:
        out += " · <a href='"+page_url(page+1)+"'>Próxima →</a>"
    return out+"</nav></section>"
