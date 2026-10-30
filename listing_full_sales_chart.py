"""Verified item sales overlaid with observed Full inventory status.

No inference before observation, no carry-forward of unknown status, no
assumption that stock changes caused sales changes.
"""
import json
from datetime import timedelta
from html import escape
from listing_sales import listing_sales_summary
from sales_metrics import reporting_today

STYLES = """<style>
.full-sales{border:1px solid #e3eaf5;border-radius:16px;background:#fff;padding:22px;margin:18px 0}
.full-sales h3{font-size:16px;color:#213653;margin:0 0 8px}
.full-sales p{color:#6b7e99;font-size:12px;line-height:1.6}
.full-sales .full-legend{display:flex;flex-wrap:wrap;gap:13px;margin:12px 0 17px;font-size:11px;color:#52647e}
.full-sales .full-legend strong{width:10px;height:10px;display:inline-block;border-radius:3px;margin-right:5px}
.full-sales .full-plot{position:relative;height:310px}
.full-sales .full-note{background:#f2f6fd;padding:12px;border-radius:9px;margin-top:13px}
@media(max-width:620px){.full-sales{padding:15px}.full-sales .full-plot{height:270px}}
</style>"""

def daily_full_status(observations, days):
    """One most recent observation per day; unknown and other logistics are gaps."""
    candidates = {}
    for row in observations:
        stamp = row.get("observed_at")
        if not isinstance(stamp, int):
            continue
        from datetime import datetime
        from zoneinfo import ZoneInfo
        day = datetime.fromtimestamp(stamp, ZoneInfo("America/Sao_Paulo")).date().isoformat()
        if day not in days:
            continue
        previous = candidates.get(day)
        if previous is None or int(previous["observed_at"]) < stamp:
            candidates[day] = row
    out = []
    for day in days:
        row = candidates.get(day)
        if row and row.get("logistics") == "fulfillment" and row.get("state") == "available":
            out.append(1)
        elif row and row.get("logistics") == "fulfillment" and row.get("state") == "empty":
            out.append(0)
        else:
            out.append(None)
    return out

def daily_sales(orders, items, coverage, item_id, days=30, today=None,
                has_pending=False):
    today = today or reporting_today()
    dates = [today - timedelta(days=days-1-i) for i in range(days)]
    if has_pending:
        return [d.isoformat() for d in dates], [None] * days
    # Existing verified classifier checks payment, item mapping, quantity and
    # daily coverage. A missing or invalid day never becomes zero.
    gross=[]
    for day in dates:
        summary = listing_sales_summary(orders, items, coverage, item_id,
                                        end=day, days=1)
        gross.append(float(summary["gross_items"])
                     if summary["gross_items"] is not None else None)
    return [d.isoformat() for d in dates], gross

def render(item_id, orders, items, coverage, observations, *, today=None,
           has_pending=False):
    today = today or reporting_today()
    dates, sales = daily_sales(orders,items,coverage,item_id,
                               today=today,has_pending=has_pending)
    stock = daily_full_status(observations,dates)
    valid=sum(value is not None for value in stock)
    sales_valid=sum(value is not None for value in sales)
    identifier="full-sales-"+''.join(c for c in str(item_id) if c.isalnum())[:60]
    if not identifier.endswith(tuple("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")):
        identifier="full-sales-item"
    out=STYLES+"<section class='full-sales'><h3>Vendas do anúncio × Estoque Full</h3>"
    out+="<p>Compare vendas verificadas com observações reais de disponibilidade no Full. A linha verde mostra Full com estoque, e a vermelha mostra Full sem estoque. Sem coleta confiável = situação desconhecida.</p>"
    out+="<div class='full-legend'><span><strong style='background:#4377df'></strong>Vendas brutas dos itens</span>"
    out+="<span><strong style='background:#149772'></strong>Full com estoque</span>"
    out+="<span><strong style='background:#e46a63'></strong>Full sem estoque</span></div>"
    if not valid:
        out+="<p class='full-note'>Ainda não há observações diárias confirmadas de estoque Full dentro dos últimos 30 dias. O gráfico não reconstruirá o passado.</p>"
    if sales_valid<30:
        out+="<p class='full-note'>Vendas verificadas em "+str(sales_valid)+" de 30 dias. Datas não verificadas não são representadas como zero.</p>"
    out+="<div class='full-plot'><canvas id='"+escape(identifier,quote=True)+"' role='img' aria-label='Vendas do anúncio por dia e estado observado de estoque Full'></canvas></div>"
    out+="<p class='full-note'>Uma mudança de estoque Full pode coincidir com uma queda nas vendas, mas não comprova a causa. Observe também preço, disponibilidade de outras variações e investimento em publicidade.</p>"
    data = {"labels":[d[5:] for d in dates],"datasets":[
        {"type":"bar","label":"Vendas do anúncio (R$)","data":sales,
         "backgroundColor":"#4377dfaa","borderRadius":4,"yAxisID":"y"},
        {"type":"line","label":"Full com estoque","data":[v if v==1 else None for v in stock],
         "borderColor":"#149772","backgroundColor":"#149772","showLine":False,"pointRadius":5,"spanGaps":False,"yAxisID":"stock"},
        {"type":"line","label":"Full sem estoque","data":[v if v==0 else None for v in stock],
         "borderColor":"#e46a63","backgroundColor":"#e46a63","showLine":False,"pointRadius":5,"spanGaps":False,"yAxisID":"stock"}]}
    out+="<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'></script>"
    out+="<script>(function(){var canvas=document.getElementById("+json.dumps(identifier)+");if(!canvas||typeof Chart==='undefined')return;new Chart(canvas,{data:"+json.dumps(data)+",options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{position:'bottom'}},scales:{y:{beginAtZero:true,position:'left'},stock:{min:-0.1,max:1.1,position:'right',grid:{drawOnChartArea:false},ticks:{stepSize:1,callback:function(v){return v===1?'Full c/ estoque':v===0?'Full zerado':''}}}}}})})();</script>"
    return out+"</section>"
