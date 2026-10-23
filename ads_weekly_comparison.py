"""Week-to-date comparison with compact visual bars."""
from datetime import timedelta
from html import escape
from ads_official_metrics import value

def render_weekly(history, today):
    start = today - timedelta(days=today.weekday())
    length = (today-start).days+1
    old = start-timedelta(days=7)
    by_day = {r["data"]:r for r in history}
    weeks = [[by_day.get((base+timedelta(days=i)).isoformat()) for i in range(length)] for base in (old,start)]
    out = "<section class='kc-section'><h3>Comparativo semanal</h3><p class='kc-sub'>Semana atual e os mesmos dias da semana anterior</p>"
    if any(r is None for week in weeks for r in week):
        return out+"<div class='kc-stale'>Comparação indisponível: histórico diário incompleto.</div></section>"
    def summarize(rows):
        spent=sum(float(r.get("gasto") or 0) for r in rows)
        revenue=sum(float(r.get("faturamento") or 0) for r in rows)
        counts=[value(r,"vendas_atribuidas",integer=True) for r in rows]
        return {"spent":spent,"revenue":revenue,"sales":sum(counts) if all(v is not None for v in counts) else None,
                "roas":revenue/spent if spent else None,"acos":100*spent/revenue if revenue else None}
    before,after=map(summarize,weeks)
    from ads_campaign_detail import money,num
    out+="<p class='kc-sub'>"+old.strftime("%d/%m")+" a "+(old+timedelta(days=length-1)).strftime("%d/%m")+" × "+start.strftime("%d/%m")+" a "+today.strftime("%d/%m")+"</p>"
    out+="<div style='overflow-x:auto'><table class='kc-table' style='min-width:610px'><thead><tr><th>Indicador</th><th>Anterior</th><th>Atual</th><th>Variação</th><th>Comparação visual</th></tr></thead><tbody>"
    for label,key,kind in [("Vendas Ads","sales","int"),("Faturamento Ads","revenue","money"),("Investimento","spent","money"),("ROAS","roas","ratio"),("ACOS","acos","percent")]:
        a,b=before[key],after[key]
        def fmt(v):
            if v is None:return "—"
            if kind=="money":return money(v)
            if kind=="int":return str(int(v))
            return num(v)+("x" if kind=="ratio" else "%")
        change=(b/a-1)*100 if a is not None and b is not None and a>0 else None
        variation=(("+" if change>0 else "")+num(change)+"%") if change is not None else "—"
        favorable=change is not None and ((change>0 and key not in ("spent","acos")) or (change<0 and key=="acos"))
        unfavorable=change is not None and ((change<0 and key not in ("spent","acos")) or (change>0 and key=="acos"))
        color="#12856d" if favorable else "#c94e50" if unfavorable else "#71839e"
        bars="—"
        if key in ("sales","revenue","spent") and a is not None and b is not None:
            scale=max(a,b,0.000001)
            bars="<div style='min-width:105px;display:grid;gap:5px' aria-label='Anterior e atual'><span style='display:block;height:8px;border-radius:5px;background:#91a5c3;width:"+str(round(a/scale*100,1))+"%'></span><span style='display:block;height:8px;border-radius:5px;background:#19aa9b;width:"+str(round(b/scale*100,1))+"%'></span></div>"
        out+="<tr><td><strong>"+escape(label)+"</strong></td><td>"+fmt(a)+"</td><td>"+fmt(b)+"</td><td style='color:"+color+";font-weight:800'>"+variation+"</td><td>"+bars+"</td></tr>"
    return out+"</tbody></table></div><p class='kc-sub'>Cinza: semana anterior · Verde-água: semana atual. Valores ausentes não são considerados zero.</p></section>"
