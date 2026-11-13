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
</style>"""

def chart(rows):
    if not rows:
        return "<p class='ka-muted'>Sem histórico disponível no período.</p>"
    values = [float(r["faturamento"] or 0) for r in rows]
    maximum = max(values) or 1
    count = len(values)
    points = " ".join(f"{20+i*760/max(1,count-1):.1f},{170-145*v/maximum:.1f}" for i,v in enumerate(values))
    return ("<svg class='ka-chart' viewBox='0 0 800 190' role='img' aria-label='Evolução diária de vendas atribuídas aos Ads'>"
            "<path d='M20 170 H780' stroke='#64748b' opacity='.35'/>"
            f"<polyline points='{points}' fill='none' stroke='#38bdf8' stroke-width='3' stroke-linejoin='round' stroke-linecap='round'/>"
            f"<text x='20' y='185' fill='currentColor' font-size='12'>{e(rows[0]['data'])}</text>"
            f"<text x='700' y='185' fill='currentColor' font-size='12'>{e(rows[-1]['data'])}</text></svg>")

def register_ads_central(app, login_required, banco, consultar, pagina):
    @app.route("/central-ads")
    @login_required
    def central_ads():
        admin = session.get("tipo") == "admin"
        days = request.args.get("periodo", "7")
        days = int(days) if days in ("1", "7", "15", "30") else 7
        presenting = admin and request.args.get("apresentacao") == "1"
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
            """, (start,end)+args)
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
                        for label,value in (("Vendas Ads",money(sales)),("Investimento",money(spent)),
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
            elif days==1 and budget>0 and gasto>=budget:
                issue="Gasto atingiu o orçamento cadastrado"
            if issue: alerts.append((r,issue))
        def hidden_name(name):
            return f"<span class='ka-private-name'>{e(name)}</span><span class='ka-private' aria-label='Nome oculto'></span>"
        def row(r,issue=""):
            gasto=float(r["gasto"] or 0); fat=float(r["faturamento"] or 0)
            a=100*gasto/fat if fat>0 else None
            return ("<tr><td>"+hidden_name(r["cliente"])+"</td><td>"+hidden_name(r["nome"] or r["campanha_id"])+
                    "</td><td>"+money(gasto)+"</td><td>"+money(fat)+"</td><td>"+metric(a,"%")+
                    "</td><td>"+e(issue or r["status"] or "—")+"</td></tr>")
        table_head="<thead><tr><th>Cliente</th><th>Campanha</th><th>Investimento</th><th>Vendas Ads</th><th>ACOS</th><th>Situação</th></tr></thead>"
        if admin:
            table = ("<section class='ka-panel'><h3>Todas as campanhas</h3><div class='ka-scroll'><table class='ka-table'>"+
                     table_head+"<tbody>"+ "".join(row(r) for r in campaigns)+"</tbody></table></div></section>")
        else:
            table=""
        alert_rows="".join(row(r,issue) for r,issue in alerts)
        alert_section=("<section class='ka-panel'><h3>Campanhas que precisam de atenção ("+str(len(alerts))+
                       ")</h3>"+("<div class='ka-scroll'><table class='ka-table'>"+table_head+
                       "<tbody>"+alert_rows+"</tbody></table></div>" if alerts else
                       "<p class='ka-muted'>Nenhum alerta identificado nos dados disponíveis.</p>")+"</section>")
        present_link=("<a class='ka-action' href='/central-ads?periodo="+str(days)+
                      ("" if presenting else "&amp;apresentacao=1")+"'>"+
                      ("Desativar apresentação" if presenting else "Modo apresentação")+"</a>") if admin else ""
        dates=set(str(r["data"]) for r in daily)
        coverage=f"{len(dates)} de {days} dias com dados consolidados"
        body=(STYLE+"<main class='ka-central"+(" ka-present" if presenting else "")+"'>"+
              "<div class='ka-head'><div><h2>Central de Ads</h2><span class='ka-muted'>"+
              ("Visão da carteira" if admin else "Sua performance de publicidade")+
              "</span></div>"+present_link+"</div><nav class='ka-tabs'>"+periods+"</nav>"+
              "<div class='ka-kpis'>"+cards+"</div>"+
              "<section class='ka-panel'><h3>Evolução das vendas Ads</h3>"+chart(daily)+
              "<p class='ka-muted'>"+coverage+" · Dados históricos armazenados; podem ter defasagem.</p></section>"+
              alert_section+table+"</main>")
        return pagina("Central de Ads",body)
