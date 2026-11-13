"""Central de Ads: leitura apenas, com isolamento por conexão."""
import html
from datetime import datetime, timedelta, timezone
from flask import request, session

BR = timezone(timedelta(hours=-3))
def e(v):
    return html.escape(str(v if v is not None else ""), quote=True)
def money(v):
    return "R$ " + f"{float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
def metric(v, suffix=""):
    return "—" if v is None else f"{v:.2f}".replace(".", ",") + suffix

STYLE = """<style>
/* Central Ads is a dark-only dashboard surface; scope the page shell as well. */
html body:has(.ka-central){background:#09192d!important;color:#edf5ff!important;color-scheme:dark!important}
html body:has(.ka-central) > .wrap{background:#09192d!important;color:#edf5ff!important;max-width:1600px}
html body:has(.ka-central) .ka-central{color:#edf5ff!important}
html body:has(.ka-central) .ka-head h2{color:#edf5ff!important}
html body:has(.ka-central) .ka-head .ka-muted{color:#91a7c5!important}
html[data-theme=light] body:has(.ka-central){background:#09192d!important;color:#edf5ff!important}

.ka-central{--ink:#edf5ff;--muted:#91a7c5;--line:#284366;--surface:#10243e;--surface2:#152d4b;max-width:1510px;margin:0 auto;color:var(--ink);font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}
.ka-central *{box-sizing:border-box}.ka-central .ka-head{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;padding:14px 0 20px}
.ka-head h2{font-size:clamp(25px,2.5vw,34px);font-weight:850;letter-spacing:-1.2px;margin:0;color:var(--ink)}
.ka-head .ka-muted{display:block;margin-top:5px}.ka-muted{font-size:12px;color:var(--muted);line-height:1.5}
.ka-tabs{display:flex;gap:7px;flex-wrap:wrap;align-items:center}.ka-tabs a,.ka-action{display:inline-flex;align-items:center;justify-content:center;padding:9px 14px;border:1px solid #385374;border-radius:10px;text-decoration:none;color:#bfd0e9;background:#142941;font-weight:650;font-size:12px;transition:background .2s,transform .2s}
.ka-tabs a:hover,.ka-action:hover{background:#1c3a60;transform:translateY(-1px)}.ka-tabs a[aria-current=page]{background:#2467eb;color:#fff;border-color:#4b8bff;box-shadow:0 4px 16px #2563eb30}
.ka-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:18px 0 8px}
.ka-kpi,.ka-panel{position:relative;overflow:hidden;background:linear-gradient(148deg,#172f4e 0%,#10233d 65%,#0f2037 100%);border:1px solid #2d4b70;border-radius:18px;box-shadow:0 12px 28px #0612242a;color:var(--ink)}
.ka-kpi{min-height:138px;padding:22px 21px}.ka-kpi:before{content:"";position:absolute;right:-44px;top:-54px;width:150px;height:150px;background:radial-gradient(circle,#4a8fff21,transparent 70%);pointer-events:none}
.ka-kpi:after{content:"";position:absolute;top:23px;right:23px;width:11px;height:11px;border-radius:50%;background:#5b9bff;box-shadow:0 0 0 6px #4d8fff1b,0 0 22px #3b82f666}
.ka-kpi:nth-child(2):after{background:#2dd4bf;box-shadow:0 0 0 6px #2dd4bf18}.ka-kpi:nth-child(3):after{background:#a78bfa;box-shadow:0 0 0 6px #a78bfa18}.ka-kpi:nth-child(4):after{background:#fbbf24;box-shadow:0 0 0 6px #fbbf2418}
.ka-kpi .ka-muted{font-size:13px;font-weight:650;color:#b4c9e3}.ka-kpi strong{display:block;margin-top:20px;font-size:clamp(21px,2.25vw,33px);font-weight:850;letter-spacing:-1.1px;line-height:1.12;overflow-wrap:anywhere}
.ka-panel{padding:22px 23px;margin-top:15px}.ka-panel h3{margin:0 0 18px;font-size:17px;font-weight:750;letter-spacing:-.35px}
.ka-overview{display:grid;grid-template-columns:minmax(0,1.95fr) minmax(270px,.85fr);gap:15px}.ka-overview .ka-panel{margin-top:15px}
.ka-chart-scroll{overflow-x:auto;scrollbar-color:#3b5b81 transparent}.ka-chart{width:100%;height:auto;min-width:510px;display:block}
.ka-legend{display:flex;gap:19px;margin:0 0 10px;font-size:12px;font-weight:750;color:#62a2ff}.ka-legend span+span{color:#26d7d2}
.ka-donut{width:184px;height:184px;border-radius:50%;margin:14px auto 23px;display:grid;place-items:center;background:conic-gradient(#27d1a5 0 var(--active),#f7bc52 var(--active) var(--paused),#627b9d var(--paused) 100%);box-shadow:0 0 0 9px #ffffff05}
.ka-donut-center{width:130px;height:130px;border-radius:50%;background:#10233d;display:grid;place-items:center;font-size:30px;font-weight:850;letter-spacing:-1px}
.ka-donut-key{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid #ffffff16;padding:11px 0;font-size:13px;color:#c5d7ee}.ka-donut-key strong{color:#fff}
.ka-alert-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.ka-alert-tile{min-height:95px;padding:15px 16px;border:1px solid #3a4d68;border-left:4px solid #fb7185;border-radius:12px;background:linear-gradient(125deg,#223653,#182b46);color:#fff;text-decoration:none;display:flex;flex-direction:column;justify-content:space-between;transition:transform .2s,border-color .2s}
.ka-alert-tile:hover{transform:translateY(-3px);border-color:#8dbaff}.ka-alert-tile:nth-child(2){border-left-color:#fbbf24}.ka-alert-tile:nth-child(3){border-left-color:#60a5fa}.ka-alert-tile:nth-child(4){border-left-color:#c084fc}
.ka-alert-tile span{font-size:12px;font-weight:650;color:#c7d7ed}.ka-alert-tile strong{display:block;font-size:26px;font-weight:850}
.ka-alert-details{margin-top:17px}.ka-alert-details summary{cursor:pointer;color:#93c5fd;font-weight:650;font-size:12px}
.ka-scroll{overflow-x:auto;border:1px solid #2b4262;border-radius:12px}.ka-table{width:100%;border-collapse:collapse;white-space:nowrap}
.ka-table th,.ka-table td{text-align:left;padding:13px 14px;border-bottom:1px solid #ffffff0d;font-size:12px}.ka-table th{background:#203956;color:#b5c9e5;text-transform:uppercase;font-weight:750;font-size:10px;letter-spacing:.055em}
.ka-table td{color:#e2ecfa}.ka-table tbody tr:nth-child(even){background:#ffffff04}.ka-table tbody tr:hover{background:#3563a222}
.ka-campaign-filters{display:flex;align-items:center;flex-wrap:wrap;gap:9px;margin-bottom:17px}
.ka-search,.ka-campaign-filters select{background:#0e2037;border:1px solid #385375;border-radius:10px;color:#e8f3ff;padding:11px 12px;min-height:40px;font-size:12px}
.ka-search{min-width:210px;flex:1}.ka-campaign-filters select{min-width:125px}.ka-campaign-filters .ka-muted{margin-left:auto}
.ka-table-footer{text-align:center;padding-top:14px}.ka-table-footer button{border:1px solid #3972cd;border-radius:9px;background:#2055b8;color:#fff;padding:10px 20px;cursor:pointer;font-weight:700}.ka-table-footer button[hidden]{display:none}
.ka-budget{display:grid;grid-template-columns:minmax(64px,1fr) auto;align-items:center;gap:10px;color:#80b6ff;font-variant-numeric:tabular-nums}
.ka-budget strong{text-align:right;min-width:7ch}.ka-budget-danger{color:#ff8b9d}
.ka-budget meter{appearance:none;width:100%;height:9px;border:0;border-radius:9px;background:#304866}
.ka-budget meter::-webkit-meter-bar{background:#304866;border:0;border-radius:9px}
.ka-budget meter::-webkit-meter-optimum-value{background:currentColor;border-radius:9px}
.ka-budget meter::-moz-meter-bar{background:currentColor;border-radius:9px}
.ka-budget meter{color:inherit}
.ka-chart-day line{opacity:0;stroke:#adc8eb;stroke-dasharray:4 4;pointer-events:none}
.ka-chart-day.ka-chart-current line,.ka-chart-day:focus-visible line{opacity:1}
.ka-chart-readout{min-height:2.6em;padding:4px 0;color:#edf5ff;font-size:12px;font-variant-numeric:tabular-nums}
.ka-private{display:none;width:125px;height:14px;background:#fff;border-radius:2px}.ka-present .ka-private{display:inline-block}.ka-present .ka-private-name{display:none}
.ka-story-button{background:linear-gradient(120deg,#2563eb,#1649b8);color:white;border-color:#4f8bff}
.ka-story{max-width:520px;width:min(100%,520px);margin:auto;padding:24px 18px;background:radial-gradient(circle at 80% 0%,#204e86,transparent 40%),#09182c;border:1px solid #35567f;border-radius:22px;min-height:900px}
.ka-story .ka-head{display:block;text-align:center}.ka-story .ka-head h2{color:#fff}.ka-story .ka-head .ka-action{margin:12px 4px 0}
.ka-story .ka-tabs{justify-content:center}.ka-story .ka-kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.ka-story .ka-kpi{min-height:105px;padding:14px}.ka-story .ka-kpi strong{font-size:21px;margin-top:16px}
.ka-story .ka-overview{display:block}.ka-story .ka-panel{padding:16px;margin-top:12px}.ka-story .ka-chart{min-width:0}.ka-story .ka-chart-scroll{overflow:hidden}
.ka-story .ka-donut{width:150px;height:150px}.ka-story .ka-donut-center{width:108px;height:108px}.ka-story .ka-alert-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.ka-story .ka-alert-tile{min-height:70px;padding:10px}.ka-story .ka-alert-tile strong{font-size:20px}.ka-story .ka-alert-details,.ka-story .ka-panel:has(#ka-campaign-table){display:none}
@media(max-width:1050px){.ka-overview{grid-template-columns:1fr}.ka-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:600px){.ka-central{padding:0 2px}.ka-head h2{font-size:25px}.ka-panel{padding:15px}.ka-kpi{min-height:110px;padding:15px}.ka-kpi strong{font-size:21px;margin-top:17px}.ka-alert-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ka-alert-tile{min-height:82px;padding:12px}.ka-chart{min-width:480px}.ka-story .ka-chart{min-width:0}.ka-story{min-height:0;padding:14px 10px}}
</style>"""
FILTER_SCRIPT = "<script>\n(function(){\nconst table=document.getElementById('ka-campaign-table');if(!table)return;\nconst body=table.tBodies[0],rows=Array.from(body.rows),search=document.getElementById('ka-campaign-search'),store=document.getElementById('ka-store-filter'),status=document.getElementById('ka-status-filter'),order=document.getElementById('ka-order-filter'),count=document.getElementById('ka-campaign-count'),more=document.getElementById('ka-more-campaigns');\nlet limit=30;\nfunction num(t){return Number((t||'').replace(/[^0-9,.-]/g,'').replace(/\\./g,'').replace(',','.'))||0}\nfunction classify(t){t=(t||'').toLowerCase();if(['active','ativa','ativo'].includes(t))return'active';if(['paused','pausada','pausado'].includes(t))return'paused';return'other'}\nfunction update(){\nconst q=search.value.trim().toLocaleLowerCase('pt-BR'),v=store?store.value:'',st=status.value,sort=order.value;\nconst filtered=rows.filter(r=>(!q||r.cells[1].textContent.toLocaleLowerCase('pt-BR').includes(q))&&(!v||r.cells[0].textContent===v)&&(!st||classify(r.cells[6].textContent)===st));\nfunction budgetOrder(a,b){\nconst first=a.querySelector('[data-budget-used]'),second=b.querySelector('[data-budget-used]');\nif(!first||!second)return Number(Boolean(second))-Number(Boolean(first));\nconst diff=Number(first.dataset.budgetUsed)-Number(second.dataset.budgetUsed);\nreturn sort==='budget-asc'?diff:-diff;\n}\nfiltered.sort((a,b)=>sort.startsWith('budget-')?budgetOrder(a,b):sort==='name'?a.cells[1].textContent.localeCompare(b.cells[1].textContent,'pt-BR'):num(b.cells[sort==='spend'?2:sort==='acos'?4:3].textContent)-num(a.cells[sort==='spend'?2:sort==='acos'?4:3].textContent));\nrows.forEach(r=>r.remove());filtered.slice(0,limit).forEach(r=>body.appendChild(r));\ncount.textContent=filtered.length+' campanhas';more.hidden=filtered.length<=limit;\n}\n[search,store,status,order].filter(Boolean).forEach(el=>el.addEventListener(el===search?'input':'change',()=>{limit=30;update()}));\nmore.addEventListener('click',()=>{limit+=30;update()});update();\n})();\n</script>"

def budget_indicator(used):
    if used is None:
        return "<span aria-label='Orçamento diário indisponível'>—</span>"
    value = metric(used, "%")
    level = min(100, max(0, used))
    danger = " ka-budget-danger" if used > 75 else ""
    return (
        f"<span class='ka-budget{danger}' data-budget-used='{used}'>"
        f"<meter min='0' max='100' value='{level}' aria-label='Orçamento diário consumido' "
        f"aria-valuetext='{value}'></meter><strong aria-hidden='true'>{value}</strong></span>"
    )

CHART_SCRIPT = """<script>
(function () {
    const chart = document.querySelector('.ka-chart');
    if (!chart) return;
    const readout = document.getElementById('ka-chart-readout');
    const days = Array.from(chart.querySelectorAll('.ka-chart-day'));
    function show(day) {
        readout.textContent = day ? day.getAttribute('aria-label') : '';
        days.forEach(point => point.classList.toggle('ka-chart-current', point === day));
    }
    days.forEach(day => {
        day.addEventListener('pointerenter', () => show(day));
        day.addEventListener('focus', () => show(day));
        day.addEventListener('blur', () => show(null));
        day.addEventListener('keydown', event => {
            if (event.key === 'Escape') show(null);
        });
    });
    chart.addEventListener('pointerleave', () => {
        show(days.includes(document.activeElement) ? document.activeElement : null);
    });
})();
</script>"""

def chart(rows):
    if not rows:
        return "<p class='ka-muted'>Sem histórico disponível.</p>"
    sales=[float(r["faturamento"] or 0) for r in rows]
    spent=[float(r["gasto"] or 0) for r in rows]
    top=max(sales+spent) or 1
    def x(i): return 78+740*i/max(1,len(rows)-1)
    def y(v): return 212-180*v/top
    def coords(vals): return " ".join(f"{x(i):.1f},{y(v):.1f}" for i,v in enumerate(vals))
    grid="".join(f"<line x1='78' x2='818' y1='{y(top*i/4):.1f}' y2='{y(top*i/4):.1f}' stroke='#66809f' opacity='.25'/><text x='70' y='{y(top*i/4)+4:.1f}' text-anchor='end' fill='#a8bdd6' font-size='12'>{e(money(top*i/4))}</text>" for i in range(5))
    dates = [f"{str(r['data'])[8:10]}/{str(r['data'])[5:7]}" for r in rows]
    labels="".join(f"<text x='{x(i):.1f}' y='240' text-anchor='middle' fill='#a8bdd6' font-size='12'>{e(dates[i])}</text>" for i,r in enumerate(rows) if len(rows)<=12 or i in (0,len(rows)-1) or i%max(1,len(rows)//6)==0)
    dots = "".join(f"<circle cx='{x(i):.1f}' cy='{y(v):.1f}' r='4' fill='#3b82f6'/>" for i,v in enumerate(sales))
    targets = []
    for i, day in enumerate(dates):
        left = (x(i - 1) + x(i)) / 2 if i else 55
        right = (x(i) + x(i + 1)) / 2 if i + 1 < len(rows) else 842
        details = e(f"{day} · Vendas Ads {money(sales[i])} · Investimento {money(spent[i])}")
        targets.append(
            f"<g class='ka-chart-day' tabindex='0' role='img' aria-label='{details}'>"
            f"<rect x='{left:.2f}' y='20' width='{right-left:.2f}' height='226' fill='transparent'/>"
            f"<line x1='{x(i):.1f}' x2='{x(i):.1f}' y1='28' y2='212'/></g>"
        )
    return ("<div class='ka-legend'><span>● Vendas Ads</span><span>● Investimento</span></div><div class='ka-chart-scroll'><svg class='ka-chart' viewBox='0 0 850 255' role='group' aria-label='Vendas e investimento por dia'><defs><linearGradient id='ads-fill' x1='0' y1='0' x2='0' y2='1'><stop offset='0%' stop-color='#3b82f6' stop-opacity='.34'/><stop offset='100%' stop-color='#3b82f6' stop-opacity='0'/></linearGradient></defs>"+grid+labels+
            f"<polygon points='78,212 {coords(sales)} {x(len(rows)-1):.1f},212' fill='url(#ads-fill)'/>"+
            f"<polyline points='{coords(sales)}' fill='none' stroke='#3b82f6' stroke-width='3.5'/>"+
            f"<polyline points='{coords(spent)}' fill='none' stroke='#22d3ee' stroke-width='2.8'/>"+dots+"".join(targets)+
            "</svg></div><div id='ka-chart-readout' class='ka-chart-readout'></div>"+CHART_SCRIPT)

def register_ads_central(app, login_required, banco, consultar, pagina):
    @app.route("/central-ads")
    @login_required
    def central_ads():
        admin = session.get("tipo") == "admin"
        days = request.args.get("periodo", "7")
        days = int(days) if days in ("1", "7", "15", "30") else 7
        story = admin and request.args.get("stories") == "1"
        presenting = admin and (request.args.get("apresentacao") == "1" or story)
        cid = session.get("conexao_id")
        if not admin and not isinstance(cid, int):
            return pagina("Central de Ads", "<p>Conta não vinculada.</p>"), 403
        start = (datetime.now(BR).date()-timedelta(days=days-1)).isoformat()
        end = datetime.now(BR).date().isoformat()
        scope = "" if admin else " AND c.id=%s"
        args = () if admin else (cid,)
        with banco() as conn:
            campaigns = consultar(conn, """
                SELECT c.cliente, a.conexao_id, a.campanha_id, a.nome, a.status,
                       a.orcamento, a.roas_objetivo, a.atualizado_em,
                       COALESCE(SUM(CASE WHEN d.data = %s THEN d.gasto ELSE 0 END),0) gasto_hoje,
                       COALESCE(SUM(d.gasto),0) gasto,
                       COALESCE(SUM(d.faturamento),0) faturamento,
                       COUNT(d.data) dias_observados
                FROM ads_campanhas a JOIN conexoes c ON c.id=a.conexao_id
                LEFT JOIN ads_campanha_dia d ON d.conexao_id=a.conexao_id
                    AND d.campanha_id=a.campanha_id AND d.data BETWEEN %s AND %s
                WHERE 1=1 """+scope+"""
                GROUP BY c.cliente,a.conexao_id,a.campanha_id,a.nome,a.status,
                         a.orcamento,a.roas_objetivo,a.atualizado_em
                ORDER BY c.cliente,a.nome LIMIT 3000
            """, (end,start,end)+args)
            daily = consultar(conn, """
                SELECT d.data, SUM(d.gasto) gasto, SUM(d.faturamento) faturamento
                FROM ads_dia d JOIN conexoes c ON c.id=d.conexao_id
                WHERE d.data BETWEEN %s AND %s """+scope+"""
                GROUP BY d.data ORDER BY d.data
            """, (start,end)+args)
        spent = sum(float(r["gasto"] or 0) for r in daily)
        sales = sum(float(r["faturamento"] or 0) for r in daily)
        # Aggregates are from ads_dia, never sum campaign and account metrics together.
        acos = 100*spent/sales if sales>0 else None
        roas = sales/spent if spent>0 else None
        periods = "".join(f"<a href='/central-ads?periodo={n}"+("&amp;apresentacao=1" if presenting else "")+
                          f"' {'aria-current=page' if n==days else ''}>{'Hoje' if n==1 else str(n)+' dias'}</a>"
                          for n in (1,7,15,30))
        cards = "".join(f"<div class='ka-kpi'><span class='ka-muted'>{label}</span><strong>{value}</strong></div>"
                        for label,value in (("Vendas Ads",money(sales) if daily else "—"),("Investimento",money(spent) if daily else "—"),
                                            ("ROAS",metric(roas,"x")),("ACOS",metric(acos,"%"))))
        alerts = []
        for r in campaigns:
            gasto=float(r["gasto"] or 0); fat=float(r["faturamento"] or 0)
            budget=float(r["orcamento"] or 0)
            target=float(r["roas_objetivo"] or 0)
            issue = ""
            if r["dias_observados"] and gasto>0 and fat==0:
                issue="Gasto sem vendas atribuídas"
            elif r["dias_observados"] and target>0 and gasto>0 and fat>0 and fat/gasto<target:
                issue="ROAS abaixo do objetivo"
            elif days==1 and r["dias_observados"] and budget>0 and gasto>=budget:
                issue="Gasto atingiu o orçamento cadastrado"
            if issue: alerts.append((r,issue))
        def hidden_name(name):
            if presenting:
                return "<span class='ka-private' aria-label='Nome oculto'></span>"
            return f"<span class='ka-private-name'>{e(name)}</span>"
        def row(r,issue=""):
            gasto=float(r["gasto"] or 0); fat=float(r["faturamento"] or 0)
            observed=bool(r["dias_observados"])
            a=100*gasto/fat if observed and fat>0 else None
            budget=float(r["orcamento"] or 0)
            used=100*float(r.get("gasto_hoje") or 0)/budget if budget>0 else None
            budget_cell=budget_indicator(used)
            return ("<tr><td>"+hidden_name(r["cliente"])+"</td><td>"+hidden_name(r["nome"] or r["campanha_id"])+
                    "</td><td>"+(money(gasto) if observed else "—")+"</td><td>"+(money(fat) if observed else "—")+"</td><td>"+metric(a,"%")+"</td><td>"+budget_cell+
                    "</td><td>"+e(issue or r["status"] or "—")+"</td></tr>")
        table_head="<thead><tr><th>Cliente</th><th>Campanha</th><th>Investimento</th><th>Vendas Ads</th><th>ACOS</th><th>Orçamento gasto (%)</th><th>Situação</th></tr></thead>"
        store_options = "".join("<option value='"+e(name)+"'>"+e(name)+"</option>" for name in sorted({str(r["cliente"] or "") for r in campaigns})) if admin and not presenting else ""
        filters = ("<div class='ka-campaign-filters'><input id='ka-campaign-search' class='ka-search' type='search' placeholder='Buscar campanha...' aria-label='Buscar campanha'>"
                   +("<select id='ka-store-filter' aria-label='Filtrar loja'><option value=''>Todas as lojas</option>"+store_options+"</select>" if store_options else "")
                   +"<select id='ka-status-filter' aria-label='Filtrar status'><option value=''>Todos os status</option><option value='active'>Ativas</option><option value='paused'>Pausadas</option><option value='other'>Outros</option></select>"
                   +"<select id='ka-order-filter' aria-label='Ordenar campanhas'><option value='sales'>Maiores vendas</option><option value='spend'>Maior investimento</option><option value='acos'>Maior ACOS</option><option value='name'>Nome A–Z</option><option value='budget-desc'>Maior orçamento consumido (%)</option><option value='budget-asc'>Menor orçamento consumido (%)</option></select>"
                   +"<span id='ka-campaign-count' class='ka-muted'></span></div>")
        table = ("<section class='ka-panel'><h3>Desempenho por campanha</h3>"+filters+"<div class='ka-scroll'><table class='ka-table' id='ka-campaign-table'>"+
                 table_head+"<tbody>"+ "".join(row(r) for r in campaigns)+"</tbody></table></div><div class='ka-table-footer'><button type='button' id='ka-more-campaigns'>Mostrar mais</button></div></section>")
        alert_rows="".join(row(r,issue) for r,issue in alerts)
        counts = [sum(1 for r,issue in alerts if issue == label) for label in ("Gasto atingiu o orçamento cadastrado","ROAS abaixo do objetivo","Gasto sem vendas atribuídas")]
        labels = ("Orçamento atingido","Consumo ≥95%","ROAS abaixo da meta","Gasto sem vendas")
        nums = (str(counts[0]),"—",str(counts[1]),str(counts[2]))
        tiles = "".join("<a class='ka-alert-tile' href='#alert-details'><span>"+label+"</span><strong>"+value+"</strong></a>" for label,value in zip(labels,nums))
        alert_section = ("<section class='ka-panel'><h3>Alertas prioritários</h3><div class='ka-alert-grid'>"+tiles+"</div><details class='ka-alert-details' id='alert-details'><summary>Ver campanhas que precisam de atenção ("+str(len(alerts))+")</summary>"+("<div class='ka-scroll'><table class='ka-table'>"+table_head+"<tbody>"+alert_rows+"</tbody></table></div>" if alerts else "<p>Sem alertas.</p>")+"</details></section>")
        active = sum(str(r["status"] or "").lower() in ("active","ativa","ativo") for r in campaigns)
        paused = sum(str(r["status"] or "").lower() in ("paused","pausada","pausado") for r in campaigns)
        total = len(campaigns)
        donut = ("<section class='ka-panel'><h3>Situação das campanhas</h3><div class='ka-donut' style='--active:"+str(round(100*active/total,2) if total else 0)+"%;--paused:"+str(round(100*(active+paused)/total,2) if total else 0)+"%'><div class='ka-donut-center'>"+str(total)+"</div></div><div class='ka-donut-key'><span>Ativas</span><strong>"+str(active)+"</strong></div><div class='ka-donut-key'><span>Pausadas</span><strong>"+str(paused)+"</strong></div><div class='ka-donut-key'><span>Outras</span><strong>"+str(total-active-paused)+"</strong></div></section>")
        story_link = ("<a class='ka-action ka-story-button' href='/central-ads?periodo="+str(days)+
                      ("" if story else "&amp;stories=1")+"'>"+
                      ("Voltar ao painel" if story else "✦ Visual para Stories")+"</a>") if admin else ""
        present_link=("<a class='ka-action' href='/central-ads?periodo="+str(days)+
                      ("" if presenting else "&amp;apresentacao=1")+"'>"+
                      ("Desativar apresentação" if presenting else "Modo apresentação")+"</a>") if admin else ""
        dates=set(str(r["data"]) for r in daily)
        coverage=f"{len(dates)} de {days} dias com dados consolidados"
        body=(STYLE+"<main class='ka-central"+(" ka-present" if presenting else "")+(" ka-story" if story else "")+"'>"+
              "<div class='ka-head'><div><h2>Central de Ads</h2><span class='ka-muted'>"+
              ("Visão da carteira" if admin else "Sua performance de publicidade")+
              "</span></div>"+present_link+"</div><nav class='ka-tabs'>"+periods+"</nav>"+
              "<div class='ka-kpis'>"+cards+"</div>"+
              "<div class='ka-overview'><section class='ka-panel'><h3>Evolução de vendas e investimento</h3>"+chart(daily)+
              "<p class='ka-muted'>"+coverage+" · Dados históricos armazenados; podem ter defasagem.</p></section>"+
              donut+"</div>"+alert_section+table+FILTER_SCRIPT+"</main>")
        return pagina("Central de Ads",body)
