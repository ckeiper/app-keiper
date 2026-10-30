"""Responsive, accessible week-to-date Ads comparison."""
from datetime import timedelta
from html import escape
from ads_official_metrics import value

STYLE = """<style>
.k-camp .kw-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:15px}
.k-camp .kw-card{min-width:0;border:1px solid #dfe8f5;border-radius:14px;padding:15px;background:linear-gradient(155deg,#f9fbff,#fff)}
.k-camp .kw-top{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.k-camp .kw-title{font-weight:800;font-size:12px;color:#24395a}
.k-camp .kw-delta{font-size:11px;font-weight:800;padding:5px 8px;border-radius:8px;background:#eaf0f8;color:#60728d}
.k-camp .kw-delta.good{background:#e5f8f1;color:#107e61}
.k-camp .kw-delta.bad{background:#fff0ee;color:#b94347}
.k-camp .kw-row{display:grid;grid-template-columns:75px minmax(0,1fr) auto;gap:9px;align-items:center;margin-top:14px}
.k-camp .kw-row+.kw-row{margin-top:11px}
.k-camp .kw-label{font-size:10px;color:#6a7d98}
.k-camp .kw-value{font-size:12px;font-weight:800;color:#24395a;white-space:nowrap;font-variant-numeric:tabular-nums}
.k-camp .kw-track{height:9px;border-radius:8px;background:#e8eef6;overflow:hidden}
.k-camp .kw-fill{height:100%;border-radius:8px;background:#8fa5c2}
.k-camp .kw-fill.current{background:linear-gradient(90deg,#24b4c2,#178b9d)}
.k-camp .kw-ratios{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:12px}
.k-camp .kw-ratio{padding:13px 15px;border:1px solid #e1e9f5;border-radius:12px;background:#f8faff}
.k-camp .kw-ratio strong{display:block;font-size:12px;color:#233956;margin-bottom:8px}
.k-camp .kw-ratio-line{display:flex;gap:12px;justify-content:space-between;font-size:12px;color:#657995;flex-wrap:wrap}
.k-camp .kw-ratio-line b{color:#263e62}
@media(max-width:1000px){.k-camp .kw-grid{grid-template-columns:1fr}}
@media(max-width:570px){.k-camp .kw-card{padding:13px}.k-camp .kw-row{grid-template-columns:65px minmax(0,1fr) auto;gap:7px}.k-camp .kw-value{font-size:11px}.k-camp .kw-ratios{grid-template-columns:1fr}}
</style>"""

def render_weekly(history,today):
    from ads_campaign_detail import money,num
    start=today-timedelta(days=today.weekday())
    length=(today-start).days+1
    prior=start-timedelta(days=7)
    by_day={r["data"]:r for r in history}
    weeks=[[by_day.get((base+timedelta(days=i)).isoformat()) for i in range(length)] for base in (prior,start)]
    dates=prior.strftime("%d/%m")+"–"+(prior+timedelta(days=length-1)).strftime("%d/%m")+" e "+start.strftime("%d/%m")+"–"+today.strftime("%d/%m")
    out=STYLE+"<section class='kc-section'><h3>Comparativo semanal</h3><p class='kc-sub'>Mesmos dias da semana: "+dates+".</p>"
    if any(r is None for w in weeks for r in w):
        return out+"<div class='kc-stale'>Comparação indisponível: histórico diário incompleto.</div></section>"
    def total(rows):
        spent=sum(float(r.get("gasto") or 0) for r in rows)
        revenue=sum(float(r.get("faturamento") or 0) for r in rows)
        sales=[value(r,"vendas_atribuidas",integer=True) for r in rows]
        organic=[value(r,"faturamento_sem_ads") for r in rows]
        organic_sum=sum(organic) if all(v is not None for v in organic) else None
        combined=revenue+organic_sum if organic_sum is not None else None
        return {"spent":spent,"revenue":revenue,"organic":organic_sum,"tacos":100*spent/combined if combined is not None and combined>0 else None,"sales":sum(sales) if all(v is not None for v in sales) else None,
                "roas":revenue/spent if spent else None,"acos":spent/revenue*100 if revenue else None}
    old,now=map(total,weeks)
    def fmt(key,v):
        if v is None:return "—"
        if key in ("spent","revenue","organic"):return money(v)
        if key=="sales":return str(int(v))
        return num(v)+("x" if key=="roas" else "%")
    def delta(key):
        a,b=old[key],now[key]
        if a is None or b is None or a<=0:return "<span class='kw-delta'>—</span>"
        change=(b/a-1)*100
        positive=change>0
        good=(positive and key in ("sales","revenue","roas")) or (change<0 and key in ("acos","tacos"))
        bad=(change<0 and key in ("sales","revenue","roas")) or (positive and key=="acos")
        klass="good" if good else "bad" if bad else ""
        arrow="↗" if positive else "↘" if change<0 else "→"
        return "<span class='kw-delta "+klass+"'>"+arrow+" "+("+" if positive else "")+num(change)+"%</span>"
    out+="<div class='kw-grid'>"
    for label,key in (("Vendas Ads","sales"),("Faturamento Ads","revenue"),("Faturamento orgânico","organic"),("Investimento","spent")):
        out+="<article class='kw-card'><div class='kw-top'><span class='kw-title'>"+escape(label)+"</span>"+delta(key)+"</div>"
        a,b=old[key],now[key]
        if a is None or b is None:
            out+="<p class='kc-sub'>Dados oficiais de vendas ainda indisponíveis para comparar os dois períodos.</p>"
        else:
            maximum=max(a,b,0.000001)
            for title,amount,klass in (("Anterior",a,""),("Atual",b,"current")):
                width=round(amount/maximum*100,1)
                out+="<div class='kw-row'><span class='kw-label'>"+title+"</span><div class='kw-track'><div class='kw-fill "+klass+"' style='width:"+str(width)+"%'></div></div><span class='kw-value'>"+fmt(key,amount)+"</span></div>"
        out+="</article>"
    out+="</div><div class='kw-ratios'>"
    for label,key in (("ROAS","roas"),("ACOS","acos"),("TACOS","tacos")):
        out+="<div class='kw-ratio'><div class='kw-top'><strong>"+label+"</strong>"+delta(key)+"</div><div class='kw-ratio-line'><span>Anterior: <b>"+fmt(key,old[key])+"</b></span><span>Atual: <b>"+fmt(key,now[key])+"</b></span></div></div>"
    return out+"</div><p class='kc-sub'>Barras cinzas: semana anterior · Verde-água: semana atual. Investimento maior não significa necessariamente melhora; avalie junto ao ROAS.</p></section>"
