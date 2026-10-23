"""Store-scoped individual Ads campaign dashboard using saved daily snapshots."""
import json
from datetime import date, timedelta
from decimal import Decimal
from html import escape
from urllib.parse import quote

CSS="""<style>
.k-camp{--ink:#1c2d4a;--muted:#71839e;--blue:#3763ed;--cyan:#00aabb;color:var(--ink)}
.k-camp .kc-hero{border:1px solid #dfe8f5;border-left:5px solid #4669e9;border-radius:18px;background:linear-gradient(118deg,#ffffff,#eef4ff);padding:22px 24px;box-shadow:0 9px 30px #2438600a}
.k-camp .kc-eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:#687d9f;font-weight:800}
.k-camp .kc-hero h2{font-size:24px;line-height:1.3;margin:8px 0;color:#183354}
.k-camp .kc-sub{color:#75849b;font-size:12px;line-height:1.6}
.k-camp .kc-head{display:flex;flex-wrap:wrap;align-items:start;justify-content:space-between;gap:12px}
.k-camp .kc-back{color:#4166d9;border:1px solid #ccdaf5;border-radius:9px;background:white;padding:9px 12px;text-decoration:none;font-size:11px;font-weight:800}
.k-camp .kc-back:hover{background:#e8efff}
.k-camp .kc-badge{display:inline-block;font-size:10px;padding:5px 9px;border-radius:9px;color:#24677c;background:#daf4f7;font-weight:800;margin:6px 5px 0 0}
.k-camp .kc-period{display:flex;flex-wrap:wrap;gap:8px;margin:19px 0}
.k-camp .kc-period a{text-decoration:none;font-size:12px;font-weight:700;padding:9px 16px;border-radius:9px;color:#52617a;border:1px solid #e2e8f2;background:white}
.k-camp .kc-period a[aria-current=page]{background:#4165e7;color:#fff;border-color:#4165e7}
.k-camp .kc-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:12px 0}
.k-camp .kc-kpi{background:white;border:1px solid #e6ebf4;border-radius:11px;padding:11px 13px;min-width:0;box-shadow:0 5px 20px #213b6208}
.k-camp .kc-kpi:nth-child(4n+1){border-top:3px solid #26a8b4}.k-camp .kc-kpi:nth-child(4n+2){border-top:3px solid #4873ed}.k-camp .kc-kpi:nth-child(4n+3){border-top:3px solid #f59a43}.k-camp .kc-kpi:nth-child(4n){border-top:3px solid #8299ba}
.k-camp .kc-kpi label{display:block;font-size:10px;color:#7b88a2;margin-bottom:5px;font-weight:750}
.k-camp .kc-kpi strong{display:block;font-size:21px;letter-spacing:-.6px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere;color:#1c3252}
.k-camp .kc-kpi small{font-size:11px;color:#7a8aa3;display:block;margin-top:4px}
.k-camp .kc-down{color:#c94e50!important}.k-camp .kc-up{color:#138769!important}
.k-camp .kc-section{background:white;border:1px solid #e2eaf3;border-radius:17px;padding:22px;margin:18px 0;box-shadow:0 7px 25px #223b5d08}
.k-camp .kc-section h3{font-size:16px;color:#24395a;margin:0 0 8px}
.k-camp .kc-layout{display:grid;grid-template-columns:1.3fr 1fr;gap:15px}
.k-camp .kc-chart{position:relative;height:350px;margin-top:24px;padding:18px 10px 8px;border:1px solid #e8eef8;border-radius:16px;background:linear-gradient(180deg,#f8faff,#fff);box-sizing:border-box}.k-camp .kc-chart canvas{max-width:100%}
@media(max-width:570px){.k-camp .kc-chart{height:310px;padding:12px 4px 4px}}
.k-camp .kc-tasks{display:grid;gap:10px;margin-top:15px}
.k-camp .kc-task{border-radius:12px;padding:16px;border:1px solid #e0e7f2;border-left:4px solid #4970e6;background:#f7f9ff}
.k-camp .kc-task.warn{border-left-color:#f5a049;background:#fffaf1}.k-camp .kc-task.good{border-left-color:#18a889;background:#f3fbf8}
.k-camp .kc-task strong{display:block;margin-bottom:7px;font-size:13px;color:#233956}
.k-camp .kc-task p{font-size:12px;line-height:1.6;color:#5e718c;margin:0}
.k-camp .kc-table{width:100%;border-collapse:collapse}.k-camp .kc-table th,.k-camp .kc-table td{padding:11px 9px;border-bottom:1px solid #e8eef6;text-align:left;font-size:11px}.k-camp .kc-table th{color:#7e8aa1}
.k-camp .kc-stale{border-radius:11px;background:#fff5e6;border:1px solid #f0d5aa;padding:13px;font-size:12px;color:#855c2d;margin-top:12px}
@media(max-width:980px){.k-camp .kc-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.k-camp .kc-layout{grid-template-columns:1fr}}
@media(max-width:570px){.k-camp .kc-hero{padding:16px}.k-camp .kc-section{padding:16px}.k-camp .kc-kpi{padding:12px}.k-camp .kc-kpi strong{font-size:19px}}
.k-camp .kc-change-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(225px,1fr));gap:11px;margin-top:17px}
.k-camp .kc-change{background:#f8faff;border:1px solid #e1e9f7;border-radius:11px;padding:16px;display:grid;gap:8px}
.k-camp .kc-change-type{font-size:10px;font-weight:800;color:#687a9d;text-transform:uppercase;letter-spacing:.05em}
.k-camp .kc-change strong{font-size:15px;color:#26406f}.k-camp .kc-change small{font-size:10px;color:#7e8ba2}
</style>"""

def money(v):
    return "R$ "+format(v,",.2f").replace(",","X").replace(".",",").replace("X",".")

def num(v):
    return ("%.2f" % v).replace(".",",")

def metrics(rows):
    spent=sum(float(x.get("gasto") or 0) for x in rows)
    revenue=sum(float(x.get("faturamento") or 0) for x in rows)
    return {"spent":spent,"revenue":revenue,"roas":revenue/spent if spent>0 else None,
            "acos":100*spent/revenue if revenue>0 else None}

def render(cid, campaign, history, days, today, store_revenue=None, shop_daily=None, ads_total_daily=None, changes=None):
    # One source of truth: campaign daily snapshots; never fabricate impressions,
    # campaign clicks or attributable sales not present in the database.
    selected_start=today-timedelta(days=days-1)
    prev_start=selected_start-timedelta(days=days)
    prev_end=selected_start-timedelta(days=1)
    current=[x for x in history if selected_start.isoformat()<=x["data"]<=today.isoformat()]
    previous=[x for x in history if prev_start.isoformat()<=x["data"]<=prev_end.isoformat()]
    current.sort(key=lambda x:x["data"])
    previous.sort(key=lambda x:x["data"])
    m=metrics(current)
    pm=metrics(previous)
    complete=len({x["data"] for x in current})==days and len({x["data"] for x in previous})==days
    budget=float(campaign.get("orcamento") or 0)
    target=float(campaign.get("roas_objetivo") or 0)
    today_row=next((x for x in current if x["data"]==today.isoformat()),None)
    today_spent=float(today_row["gasto"] or 0) if today_row else None
    consumption=100*today_spent/budget if budget>0 and today_spent is not None else None
    valid_tacos=store_revenue is not None and store_revenue>0
    tacos=m["spent"]/store_revenue*100 if valid_tacos else None
    def kpi(name,value,key,note=""):
        trend=""
        a=m.get(key)
        b=pm.get(key)
        if complete and a is not None and b is not None and b>0:
            delta=100*(a-b)/b
            cls="kc-up" if delta>=0 else "kc-down"
            trend="<small class='"+cls+"'>"+("%+.1f%%" % delta).replace(".",",")+" vs. período anterior</small>"
        else:
            trend=""
        return "<div class='kc-kpi'><label>"+name+"</label><strong>"+value+"</strong>"+trend+("<small>"+note+"</small>" if note else "")+"</div>"
    name=escape(str(campaign.get("nome") or ("Campanha "+str(campaign["campanha_id"]))))
    status=escape(str(campaign.get("status") or "Sem status"))
    out=CSS+"<div class='k-camp'><header class='kc-hero'><div class='kc-head'><div><div class='kc-eyebrow'>Keiper / Inteligência de Ads</div><h2>"+name+"</h2><p class='kc-sub'>Campanha "+escape(str(campaign["campanha_id"]))+" · "+status+"</p>"
    out+="<span class='kc-badge'>Meta de ROAS: "+(num(target)+"x" if target>0 else "não cadastrada")+"</span>"
    out+="<span class='kc-badge'>Orçamento diário: "+(money(budget) if budget>0 else "não informado")+"</span>"
    out+="</div><a class='kc-back' href='/ads/"+str(cid)+"'>← Voltar à Publicidade</a></div></header>"
    out+=roas_control(cid,campaign['campanha_id'],target)
    out+="<nav class='kc-period' aria-label='Período de análise'>"
    safe_id=quote(str(campaign["campanha_id"]),safe="")
    for option in (7,15,30,60,90):
        out+="<a href='/ads/"+str(cid)+"/campanha/"+safe_id+"?dias="+str(option)+"'"+(" aria-current='page'" if option==days else "")+">"+str(option)+" dias</a>"
    out+="</nav><div class='kc-grid'>"
    out+=kpi("Faturamento atribuído a Ads",money(m["revenue"]),"revenue")
    out+=kpi("Investimento em Ads",money(m["spent"]),"spent")
    out+=kpi("ROAS realizado",num(m["roas"])+"x" if m["roas"] is not None else "—","roas")
    out+=kpi("ACOS",num(m["acos"])+"%" if m["acos"] is not None else "—","acos")
    out+="<div class='kc-kpi'><label>TACOS da campanha</label><strong>"+(num(tacos)+"%" if tacos is not None else "—")+"</strong><small>"+("Gasto da campanha ÷ faturamento total da loja" if tacos is not None else "Vendas totais da loja ainda não validadas")+"</small></div>"
    out+="<div class='kc-kpi'><label>Gasto hoje</label><strong>"+(money(today_spent) if today_spent is not None else "—")+"</strong><small>Última coleta do dia, não em tempo real</small></div>"
    out+="<div class='kc-kpi'><label>Consumo orçamento hoje</label><strong>"+(num(consumption)+"%" if consumption is not None else "—")+"</strong><small>Sobre o orçamento diário cadastrado</small></div>"
    out+="<div class='kc-kpi'><label>Meta de ROAS</label><strong>"+(num(target)+"x" if target>0 else "—")+"</strong><small>Configurada na conta</small></div></div>"
    # Official sales counts scoped to this campaign, never a whole-store residual.
    labels=[(selected_start+timedelta(days=i)).isoformat() for i in range(days)]
    campaign_days={row["data"]:row for row in current}
    from ads_official_metrics import value
    attributed=[value(campaign_days.get(day, {}), 'vendas_atribuidas', integer=True) for day in labels]
    spends=[float(campaign_days[day]["gasto"] or 0) if day in campaign_days else None for day in labels]
    organic=[value(campaign_days.get(day, {}), 'outras_vendas', integer=True) for day in labels]
    available=sum(a is not None and b is not None for a,b in zip(attributed,organic))
    out+="<section class='kc-section'><h3>Vendas e investimento da campanha</h3>"
    out+="<p class='kc-sub'>Barras empilhadas: Vendas Ads e outras vendas dos anúncios desta campanha, conforme informado pelo Mercado Livre. A linha mostra o investimento em reais.</p>"
    out+="<p class='kc-sub'>Vendas em quantidade no eixo esquerdo; investimento no eixo direito. Cada produto diferente no carrinho conta como uma venda, independentemente das unidades.</p>"
    if available<days:
        out+="<div class='kc-stale'>Métricas oficiais de vendas disponíveis em "+str(available)+" de "+str(days)+" dias. O histórico está sendo atualizado nas sincronizações. Dados não fornecidos aparecem como indisponíveis, sem estimativa e sem substituição por zero.</div>"
    out+="<div class='kc-chart'><canvas id='kc-daily-chart' role='img' aria-label='Vendas Ads e outras vendas dos anúncios da campanha empilhadas, com investimento em reais'></canvas></div></section>"
    datasets=[
        {"type":"bar","label":"Vendas Ads","data":attributed,"stack":"sales","backgroundColor":"#3483fa","borderRadius":4,"borderSkipped":False,"maxBarThickness":36,"categoryPercentage":0.7,"barPercentage":0.85,"order":2},
        {"type":"bar","label":"Outras vendas dos anúncios","data":organic,"stack":"sales","backgroundColor":"#bdd7ff","borderRadius":4,"borderSkipped":False,"maxBarThickness":36,"categoryPercentage":0.7,"barPercentage":0.85,"order":3},
        {"type":"line","label":"Investimento","data":spends,"yAxisID":"investment","borderColor":"#194579","backgroundColor":"#194579","tension":0.35,"borderWidth":3,"pointRadius":0,"pointHoverRadius":5,"pointHoverBackgroundColor":"#fff","pointHoverBorderWidth":3,"spanGaps":False,"order":1}
    ]
    out+="<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'></script>"
    display_labels=[date.fromisoformat(day).strftime('%d/%m') for day in labels]
    out+="<script>(function(){var el=document.getElementById('kc-daily-chart');if(!el||typeof Chart==='undefined')return;var datasets="+json.dumps(datasets,ensure_ascii=False)+";"+"""
var currency=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'});
var compact=new Intl.NumberFormat('pt-BR',{notation:'compact',maximumFractionDigits:1});
var quantity=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:0});
datasets.filter(function(d){return d.type==='bar'}).forEach(function(d){var color=d.backgroundColor;d.backgroundColor=function(context){var area=context.chart.chartArea;if(!area)return color;var gradient=context.chart.ctx.createLinearGradient(0,area.top,0,area.bottom);gradient.addColorStop(0,color);gradient.addColorStop(1,color+'80');return gradient;};});
"""+"new Chart(el,{data:{labels:"+json.dumps(display_labels)+",datasets:datasets},"+"""options:{locale:'pt-BR',responsive:true,maintainAspectRatio:false,
animation:matchMedia('(prefers-reduced-motion: reduce)').matches?false:{duration:450},
interaction:{intersect:false,mode:'index'},layout:{padding:{top:8,right:8}},
plugins:{legend:{position:'bottom',align:'start',labels:{color:'#526582',usePointStyle:true,pointStyle:'rectRounded',boxWidth:9,boxHeight:9,padding:18,font:{family:"Inter, 'Segoe UI', sans-serif",size:11}}},
tooltip:{backgroundColor:'#14243b',titleColor:'#fff',bodyColor:'#dce8fb',borderColor:'#314b70',borderWidth:1,cornerRadius:12,padding:14,boxPadding:6,usePointStyle:true,titleMarginBottom:10,bodySpacing:7,titleFont:{size:13,weight:'bold'},bodyFont:{size:12},callbacks:{title:function(items){return items.length?items[0].label:'';},label:function(context){return context.dataset.label+': '+(context.dataset.yAxisID==='investment'?currency.format(context.parsed.y):quantity.format(context.parsed.y)+' vendas');}}}},
scales:{x:{stacked:true,border:{display:false},grid:{display:false},ticks:{color:'#7b8ca6',maxRotation:0,minRotation:0,autoSkip:true,maxTicksLimit:el.clientWidth<500?5:10,font:{size:11},padding:10}},
y:{stacked:true,beginAtZero:true,border:{display:false},title:{display:true,text:'Vendas',color:'#7b8ca6'},grid:{color:'#e9eef6',drawTicks:false},ticks:{precision:0,color:'#7b8ca6',maxTicksLimit:5,padding:8,font:{size:10},callback:function(value){return quantity.format(value);}}},
investment:{position:'right',beginAtZero:true,border:{display:false},title:{display:true,text:'Investimento (R$)',color:'#7b8ca6'},grid:{drawOnChartArea:false,drawTicks:false},ticks:{color:'#7b8ca6',maxTicksLimit:5,padding:8,font:{size:10},callback:function(value){return 'R$ '+compact.format(value);}}}}}});
})();</script>"""
    from ads_weekly_comparison import render_weekly
    out+=render_weekly(history,today)
    from ads_change_history import display_history
    out+=display_history(changes or [])
    out+="<div class='kc-layout'><section class='kc-section'><h3>O que merece atenção</h3><p class='kc-sub'>Sugestões de investigação, não mudanças automáticas de orçamento ou meta.</p><div class='kc-tasks'>"
    suggestions=[]
    if not current:
        suggestions.append(("warn","Aguardando histórico","Ainda não há métricas diárias registradas para este período."))
    else:
        if target>0 and m["roas"] is not None:
            if m["roas"]<target:
                suggestions.append(("warn","ROAS abaixo da meta","Compare anúncios, preços e desempenho antes de alterar a estratégia. Meta: "+num(target)+"x; realizado: "+num(m["roas"])+"x."))
            elif m["roas"]>=target*1.3:
                suggestions.append(("good","Campanha acima do objetivo","ROAS supera a meta em pelo menos 30%. Avalie capacidade de investimento e margem antes de escalar."))
        if consumption is not None and consumption>=80:
            suggestions.append(("warn","Orçamento requer atenção","Gasto observado hoje atingiu "+num(consumption)+"% do orçamento diário. Confirme o valor e a atualização da conta antes de agir."))
        if m["spent"]>0 and m["revenue"]==0:
            suggestions.append(("warn","Investimento sem venda atribuída","Verifique atribuição, produtos e janela de avaliação. Não conclua que não houve venda orgânica."))
        if complete and pm["roas"] and m["roas"] is not None and m["roas"]<=pm["roas"]*.7:
            suggestions.append(("warn","Queda de ROAS entre períodos","O ROAS caiu pelo menos 30% em períodos com todos os dias registrados. Investigue antes de mudar orçamento."))
    if not suggestions:
        suggestions.append(("good","Sem alerta crítico pelas regras atuais","Acompanhe ROAS, orçamento e margens. Ausência de alertas não garante lucro."))
    for typ,title,desc in suggestions:
        out+="<article class='kc-task "+typ+"'><strong>"+title+"</strong><p>"+desc+"</p></article>"
    out+="</div></section><section class='kc-section'><h3>Comparação de períodos</h3><p class='kc-sub'>"+selected_start.strftime("%d/%m")+" a "+today.strftime("%d/%m")+" versus "+prev_start.strftime("%d/%m")+" a "+prev_end.strftime("%d/%m")+"</p>"
    if not complete:
        out+="<div class='kc-stale'>Cobertura diária incompleta em pelo menos um período. A comparação percentual fica indisponível para evitar conclusões enganosas.</div>"
    out+="<table class='kc-table'><thead><tr><th>Indicador</th><th>Atual</th><th>Anterior</th></tr></thead><tbody>"
    out+="<tr><td>Investimento</td><td>"+money(m["spent"])+"</td><td>"+(money(pm["spent"]) if complete else "—")+"</td></tr>"
    out+="<tr><td>Faturamento Ads</td><td>"+money(m["revenue"])+"</td><td>"+(money(pm["revenue"]) if complete else "—")+"</td></tr>"
    out+="<tr><td>ROAS</td><td>"+(num(m["roas"])+"x" if m["roas"] is not None else "—")+"</td><td>"+(num(pm["roas"])+"x" if complete and pm["roas"] is not None else "—")+"</td></tr></tbody></table>"
    out+="<p class='kc-sub' style='margin-top:14px'>Histórico de mudanças de orçamento e meta ainda não é registrado. Não inferimos alterações a partir de resultados.</p></section></div></div>"
    return out


def roas_control(cid, campaign_id, target):
    """Keep the former campaign-list target editor on the individual analysis."""
    url='/salvar_roas/'+str(int(cid))+'/'+quote(str(campaign_id),safe='')
    return """<style>.k-camp .kc-roas-form{display:flex;align-items:end;gap:10px;flex-wrap:wrap;margin:16px 0;padding:16px;border:1px solid #dce6f5;border-radius:12px;background:#fff}.kc-roas-form label{display:grid;gap:6px;font-size:11px;color:#647a99}.kc-roas-form input{width:100px;padding:9px;border:1px solid #ccdaef;border-radius:8px}.kc-roas-form button{background:#315fd2;color:#fff;padding:11px 15px;border:0;border-radius:8px;cursor:pointer}.kc-roas-form [role=status]{font-size:11px;color:#647a99}</style>
<form class='kc-roas-form' action='"""+escape(url,quote=True)+"""' method='post'><label>Meta de ROAS do painel<input name='roas' type='number' min='0' step='0.01' required value='"""+str(target)+"""'></label><button type='submit'>Salvar meta</button><span role='status' aria-live='polite'></span></form>
<script>(function(){const form=document.currentScript.previousElementSibling,button=form.querySelector('button'),status=form.querySelector('[role=status]');form.addEventListener('submit',async function(e){e.preventDefault();if(button.disabled)return;button.disabled=true;status.textContent='Salvando…';try{const response=await fetch(form.getAttribute('action'),{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(form))});const data=await response.json();if(!response.ok||!data.ok)throw Error();location.reload();}catch(e){status.textContent='Não foi possível salvar a meta. Tente novamente.';button.disabled=false;}});})();</script>"""
