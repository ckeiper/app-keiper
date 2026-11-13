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
.ka-central{max-width:1400px;margin:auto;color:var(--text,#e5e7eb)}
.ka-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:0 0 20px}
.ka-head h2{margin:0;font-size:25px;letter-spacing:-.6px}
.ka-muted{opacity:.7;font-size:12px}
.ka-tabs{display:flex;gap:7px;flex-wrap:wrap}
.ka-tabs a,.ka-action{padding:8px 13px;border:1px solid #64748b55;border-radius:9px;text-decoration:none;color:inherit}
.ka-tabs a[aria-current=page]{background:#2563eb;color:white;border-color:#2563eb}
.ka-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}
.ka-kpi,.ka-panel{background:var(--card-bg,#17243a);border:1px solid #64748b30;border-radius:14px;padding:17px}
.ka-kpi strong{display:block;font-size:clamp(18px,2.4vw,29px);margin-top:9px;letter-spacing:-.7px}
.ka-panel{margin-top:14px}.ka-panel h3{margin:0 0 14px;font-size:16px}
.ka-scroll{overflow-x:auto}.ka-table{width:100%;border-collapse:collapse;white-space:nowrap}
.ka-table td,.ka-table th{text-align:left;padding:11px;border-bottom:1px solid #64748b25;font-size:13px}
.ka-table th{font-size:11px;opacity:.7}.ka-danger{color:#f87171}.ka-warn{color:#fbbf24}
.ka-ok{color:#34d399}.ka-search{padding:9px 12px;border:1px solid #64748b55;border-radius:8px;background:transparent;color:inherit;min-width:210px}
.ka-chart{width:100%;height:190px}.ka-private{display:inline-block;background:#fff;border-radius:2px;height:14px;width:130px;vertical-align:middle}
.ka-present .ka-private-name{display:none}.ka-present .ka-private{display:inline-block}
.ka-private{display:none}.ka-alert{padding:12px 0;border-bottom:1px solid #64748b25}
@media(max-width:760px){.ka-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.ka-kpi{padding:12px}.ka-head h2{font-size:21px}}

.ka-central{color:#eaf2ff}.ka-head h2{color:#14243c}.ka-head .ka-muted{color:#52647a}
.ka-tabs a,.ka-action{color:#253b58;background:#fff}.ka-tabs a[aria-current=page]{color:#fff}
.ka-kpi,.ka-panel{background:#12243d;color:#f1f5f9;border:1px solid #2c4668;box-shadow:0 8px 20px #0f172a12}
.ka-kpi .ka-muted,.ka-panel .ka-muted{color:#b5c6dc;opacity:1}
.ka-table td{color:#e2e8f0}.ka-table th{background:#253c59;color:#cbd5e1;opacity:1}
.ka-chart{width:100%;height:auto;min-width:540px}.ka-chart-scroll{overflow-x:auto}
.ka-legend{display:flex;gap:16px;color:#93c5fd;font-size:12px;margin-bottom:8px}.ka-legend span+span{color:#22d3ee}
.ka-overview{display:grid;grid-template-columns:minmax(0,2fr) minmax(240px,1fr);gap:14px}
.ka-overview .ka-panel{margin-top:14px}
.ka-donut{width:165px;height:165px;border-radius:50%;margin:18px auto;display:grid;place-items:center;background:conic-gradient(#34d399 0 var(--active),#fbbf24 var(--active) var(--paused),#64748b var(--paused) 100%)}
.ka-donut-center{width:115px;height:115px;border-radius:50%;background:#12243d;display:grid;place-items:center;text-align:center;font-size:24px;font-weight:bold}
.ka-donut-key{display:flex;justify-content:space-between;border-bottom:1px solid #ffffff1b;padding:9px 0;font-size:13px}
.ka-alert-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.ka-alert-tile{padding:13px;background:#1d324f;border-radius:10px;border-left:3px solid #fb7185;color:white;text-decoration:none}
.ka-alert-tile:nth-child(2){border-color:#fbbf24}.ka-alert-tile:nth-child(3){border-color:#60a5fa}.ka-alert-tile:nth-child(4){border-color:#c084fc}
.ka-alert-tile strong{display:block;font-size:23px}.ka-alert-tile span{font-size:12px}
.ka-alert-details{margin-top:16px}.ka-alert-details summary{cursor:pointer;color:#93c5fd}
@media(max-width:950px){.ka-overview{grid-template-columns:1fr}.ka-alert-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.ka-central{max-width:1540px}.ka-kpi{background:linear-gradient(145deg,#1b3557,#101e34);border-radius:17px;padding:22px;box-shadow:0 8px 25px #0b142b25}.ka-kpi strong{font-size:clamp(22px,2.5vw,34px);font-weight:800}.ka-kpi .ka-muted{font-size:13px;font-weight:600}.ka-panel{background:linear-gradient(155deg,#192f4e,#101f36);border-radius:17px;padding:22px}.ka-panel h3{font-size:18px;font-weight:750}.ka-table th{text-transform:uppercase;letter-spacing:.05em}.ka-table tbody tr:hover{background:#ffffff10}.ka-table td{padding:13px 11px}.ka-alert-tile{min-height:80px;display:flex;flex-direction:column;justify-content:space-between;transition:transform .15s}.ka-alert-tile:hover{transform:translateY(-2px)}.ka-donut{width:190px;height:190px}.ka-donut-center{width:137px;height:137px}.ka-head h2{font-size:29px;font-weight:800}@media(max-width:760px){.ka-panel{padding:14px}.ka-kpi{padding:14px}.ka-kpi strong{font-size:21px}}.ka-campaign-filters{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:16px}.ka-campaign-filters select{background:#142b48;border:1px solid #3a5476;color:#e2e8f0;border-radius:9px;padding:10px;min-width:130px}.ka-campaign-filters input{background:#142b48;color:#e2e8f0;flex:1;min-width:190px}.ka-campaign-filters .ka-muted{margin-left:auto;color:#b5c6dc}.ka-table-footer{text-align:center;margin-top:14px}.ka-table-footer button{background:#1d4ed8;color:white;border:0;border-radius:9px;padding:10px 18px;cursor:pointer}.ka-table-footer button[hidden]{display:none}
.ka-kpi{position:relative;border:1px solid #38577d;background:linear-gradient(145deg,#203e64,#10223b);padding:22px 20px;min-height:106px}
.ka-kpi:after{content:"";position:absolute;right:20px;top:20px;width:8px;height:8px;border-radius:50%;background:#60a5fa;box-shadow:0 0 18px #60a5fa80}
.ka-kpi:nth-child(2):after{background:#22d3ee}.ka-kpi:nth-child(3):after{background:#34d399}.ka-kpi:nth-child(4):after{background:#fbbf24}
.ka-panel{border:1px solid #365274;background:linear-gradient(150deg,#1b3555,#101f36)}
.ka-alert-tile{background:linear-gradient(135deg,#203d5f,#152943)}
.ka-story-button{background:linear-gradient(120deg,#2563eb,#1d4ed8)!important;color:#fff!important;border-color:#60a5fa!important;font-weight:700}
.ka-story{width:min(100%,520px);max-width:520px;margin:0 auto;background:radial-gradient(circle at 90% 0%,#1e4780 0%,transparent 37%),linear-gradient(170deg,#0d1b31,#091426);padding:26px 20px 34px;border:1px solid #2e4e78;border-radius:24px;box-shadow:0 20px 70px #0005;min-height:900px;color:#fff}
.ka-story .ka-head{display:block;text-align:center;padding:20px 0 18px;margin:0}.ka-story .ka-head h2{color:#fff;font-size:30px}.ka-story .ka-head .ka-muted{color:#9fb9df}
.ka-story .ka-head .ka-action{display:inline-block;margin:14px 4px 0;font-size:11px}.ka-story .ka-tabs{justify-content:center;margin-bottom:18px}
.ka-story .ka-tabs a{background:#203856;color:#cbd5e1;border-color:#365577;padding:7px 12px}.ka-story .ka-tabs a[aria-current=page]{background:#2563eb;color:#fff}
.ka-story .ka-kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:12px 0}.ka-story .ka-kpi{padding:16px 13px;min-height:100px;border-radius:14px}
.ka-story .ka-kpi strong{font-size:clamp(18px,4vw,26px);overflow-wrap:anywhere}.ka-story .ka-overview{display:block}
.ka-story .ka-panel{padding:18px 14px;margin-top:12px;border-radius:16px}.ka-story .ka-overview .ka-panel{margin-top:12px}
.ka-story .ka-chart{min-width:0;width:100%;height:auto}.ka-story .ka-chart-scroll{overflow:hidden}
.ka-story .ka-donut{width:150px;height:150px;margin:8px auto}.ka-story .ka-donut-center{width:108px;height:108px}
.ka-story .ka-alert-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ka-story .ka-alert-tile{min-height:64px;padding:10px}.ka-story .ka-alert-tile strong{font-size:19px}
.ka-story .ka-alert-details,.ka-story #ka-campaign-table,.ka-story .ka-campaign-filters,.ka-story .ka-table-footer{display:none}.ka-story .ka-panel:has(#ka-campaign-table){display:none}
@media(max-width:600px){.ka-story{padding:18px 12px;border-radius:14px;min-height:0}.ka-story .ka-kpi strong{font-size:19px}}
</style>"""

FILTER_SCRIPT = "<script>\n(function(){\nconst table=document.getElementById('ka-campaign-table');if(!table)return;\nconst body=table.tBodies[0],rows=Array.from(body.rows),search=document.getElementById('ka-campaign-search'),store=document.getElementById('ka-store-filter'),status=document.getElementById('ka-status-filter'),order=document.getElementById('ka-order-filter'),count=document.getElementById('ka-campaign-count'),more=document.getElementById('ka-more-campaigns');\nlet limit=30;\nfunction num(t){return Number((t||'').replace(/[^0-9,.-]/g,'').replace(/\\./g,'').replace(',','.'))||0}\nfunction classify(t){t=(t||'').toLowerCase();if(['active','ativa','ativo'].includes(t))return'active';if(['paused','pausada','pausado'].includes(t))return'paused';return'other'}\nfunction update(){\nconst q=search.value.trim().toLocaleLowerCase('pt-BR'),v=store?store.value:'',st=status.value,sort=order.value;\nconst filtered=rows.filter(r=>(!q||r.cells[1].textContent.toLocaleLowerCase('pt-BR').includes(q))&&(!v||r.cells[0].textContent===v)&&(!st||classify(r.cells[6].textContent)===st));\nfiltered.sort((a,b)=>sort==='name'?a.cells[1].textContent.localeCompare(b.cells[1].textContent,'pt-BR'):num(b.cells[sort==='spend'?2:sort==='acos'?4:3].textContent)-num(a.cells[sort==='spend'?2:sort==='acos'?4:3].textContent));\nrows.forEach(r=>r.remove());filtered.slice(0,limit).forEach(r=>body.appendChild(r));\ncount.textContent=filtered.length+' campanhas';more.hidden=filtered.length<=limit;\n}\n[search,store,status,order].filter(Boolean).forEach(el=>el.addEventListener(el===search?'input':'change',()=>{limit=30;update()}));\nmore.addEventListener('click',()=>{limit+=30;update()});update();\n})();\n</script>"

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
    labels="".join(f"<text x='{x(i):.1f}' y='240' text-anchor='middle' fill='#a8bdd6' font-size='12'>{e(str(r['data'])[5:])}</text>" for i,r in enumerate(rows) if len(rows)<=12 or i in (0,len(rows)-1) or i%max(1,len(rows)//6)==0)
    dots="".join(f"<circle cx='{x(i):.1f}' cy='{y(v):.1f}' r='4' fill='#3b82f6'><title>{e(rows[i]['data'])}: Vendas {e(money(v))}; Investimento {e(money(spent[i]))}</title></circle>" for i,v in enumerate(sales))
    return ("<div class='ka-legend'><span>● Vendas Ads</span><span>● Investimento</span></div><div class='ka-chart-scroll'><svg class='ka-chart' viewBox='0 0 850 255' role='img' aria-label='Vendas e investimento por dia'><defs><linearGradient id='ads-fill' x1='0' y1='0' x2='0' y2='1'><stop offset='0%' stop-color='#3b82f6' stop-opacity='.34'/><stop offset='100%' stop-color='#3b82f6' stop-opacity='0'/></linearGradient></defs>"+grid+labels+
            f"<polygon points='78,212 {coords(sales)} {x(len(rows)-1):.1f},212' fill='url(#ads-fill)'/>"+
            f"<polyline points='{coords(sales)}' fill='none' stroke='#3b82f6' stroke-width='3.5'/>"+
            f"<polyline points='{coords(spent)}' fill='none' stroke='#22d3ee' stroke-width='2.8'/>"+dots+"</svg></div>")

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
            used=100*float(r["gasto_hoje"] or 0)/budget if budget>0 else None
            budget_cell=("<strong style="+chr(34)+("color:#fb7185" if used>75 else "color:inherit")+chr(34)+">"+metric(used,"%")+"</strong>" if used is not None else "—")
            return ("<tr><td>"+hidden_name(r["cliente"])+"</td><td>"+hidden_name(r["nome"] or r["campanha_id"])+
                    "</td><td>"+(money(gasto) if observed else "—")+"</td><td>"+(money(fat) if observed else "—")+"</td><td>"+metric(a,"%")+"</td><td>"+budget_cell+
                    "</td><td>"+e(issue or r["status"] or "—")+"</td></tr>")
        table_head="<thead><tr><th>Cliente</th><th>Campanha</th><th>Investimento</th><th>Vendas Ads</th><th>ACOS</th><th>Orçamento gasto (%)</th><th>Situação</th></tr></thead>"
        store_options = "".join("<option value='"+e(name)+"'>"+e(name)+"</option>" for name in sorted({str(r["cliente"] or "") for r in campaigns})) if admin and not presenting else ""
        filters = ("<div class='ka-campaign-filters'><input id='ka-campaign-search' class='ka-search' type='search' placeholder='Buscar campanha...' aria-label='Buscar campanha'>"
                   +("<select id='ka-store-filter' aria-label='Filtrar loja'><option value=''>Todas as lojas</option>"+store_options+"</select>" if store_options else "")
                   +"<select id='ka-status-filter' aria-label='Filtrar status'><option value=''>Todos os status</option><option value='active'>Ativas</option><option value='paused'>Pausadas</option><option value='other'>Outros</option></select>"
                   +"<select id='ka-order-filter' aria-label='Ordenar campanhas'><option value='sales'>Maiores vendas</option><option value='spend'>Maior investimento</option><option value='acos'>Maior ACOS</option><option value='name'>Nome A–Z</option></select>"
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
