"""Presentation only for the store Ads overview; calculations stay in the route."""
from html import escape
from datetime import date
import json


def ratio(value, suffix=''):
    return format(float(value),'.2f').replace('.',',')+suffix

STYLE = """<style>
.ka-ads{font-family:Inter,'Segoe UI',Arial,sans-serif;color:#20324e;--ka-line:#e2eaf5;--ka-muted:#7486a1}
.ka-hero{display:flex;align-items:center;justify-content:space-between;gap:22px;flex-wrap:wrap;padding:28px 30px;border:1px solid #294b76;border-radius:20px;background:radial-gradient(ellipse at 90% 0%,#284e7d,transparent 65%),#12243e;color:#fff;margin-bottom:20px;box-shadow:0 10px 26px #18365912}
.ka-eyebrow{font-size:10px;font-weight:800;letter-spacing:1.8px;text-transform:uppercase;color:#9bbded}.ka-hero h2{font-size:29px;letter-spacing:-1px;line-height:1.2;margin:9px 0;color:#fff}.ka-hero p{margin:0;color:#b6c9e4;font-size:12px;line-height:1.6}.ka-actions{display:flex;gap:8px;flex-wrap:wrap}.ka-actions a{font-size:12px;font-weight:700;text-decoration:none;border:1px solid #59789e;border-radius:10px;color:#e3edfc;padding:11px 15px;background:#ffffff0b}.ka-actions a:first-child{background:#e9f1ff;color:#224574;border-color:#e9f1ff}.ka-actions a:hover{filter:brightness(1.08)}
.ka-ads .card{border:1px solid var(--ka-line);border-radius:17px;padding:23px;margin-bottom:19px;box-shadow:0 5px 20px #17334e04}.ka-ads h3{font-size:16px;letter-spacing:-.3px;color:#233c5d;margin:0 0 10px}.ka-ads .muted{color:var(--ka-muted);font-size:11px;line-height:1.6}.ka-ads p{line-height:1.65}.ka-ads form{gap:12px!important}.ka-ads label{display:flex;flex-direction:column;gap:7px;font-size:10px;font-weight:750;color:#647a99}.ka-ads input,.ka-ads select{min-height:40px;box-sizing:border-box;max-width:100%;border:1px solid #d8e3f2;border-radius:9px;padding:8px 11px;background:#f9fbff;color:#2b4365;font:inherit;font-size:12px;outline:none}.ka-ads input:focus,.ka-ads select:focus{border-color:#6e98e1;box-shadow:0 0 0 3px #517ee41c}.ka-ads button.btn{min-height:40px;border:0;border-radius:9px;background:#315fd2;color:white;font-size:11px;font-weight:750;padding:10px 17px;cursor:pointer}.ka-ads a:focus-visible,.ka-ads summary:focus-visible,.ka-ads button:focus-visible{outline:3px solid #6d9bea;outline-offset:3px}
.ka-ads .ka-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 23px}.ka-ads .stat{border:1px solid #dfe8f5;border-radius:15px;padding:21px;background:#fff;box-shadow:0 6px 18px #19395d05;min-width:0;position:relative}.ka-ads .stat:before{display:none}.ka-ads .stat .num{font-size:27px;font-weight:800;line-height:1.25;letter-spacing:-.8px;color:#233b61;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}.ka-ads .stat .lab{font-size:10px;font-weight:750;color:#7a8ca8;margin:10px 0 0;letter-spacing:.5px;text-transform:uppercase}.ka-ads .stat:nth-child(2){background:#eaf2ff;border-color:#cadcff}.ka-ads .stat:nth-child(2) .num{color:#315fc4}.ka-ads .stat small{display:block;font-size:10px;margin-top:8px}.ka-section-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:25px 0 13px}.ka-section-title h3{font-size:17px;margin:0}.ka-section-title span{font-size:10px;color:#8295ae}
.ka-alert-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;margin-bottom:24px}.ka-alert{border:1px solid #e0e8f2;border-radius:13px;background:#fff;overflow:hidden;align-self:start}.ka-alert summary{display:flex;align-items:center;justify-content:space-between;gap:10px;cursor:pointer;list-style:none;padding:16px 18px;font-size:12px;font-weight:750;color:#3f5677}.ka-alert summary::-webkit-details-marker{display:none}.ka-alert summary:after{content:'+';color:#8aa0bf;font-size:18px}.ka-alert[open] summary:after{content:'−'}.ka-alert-count{padding:4px 8px;border-radius:7px;background:#eef3fa;color:#7185a2;font-size:10px;margin-left:auto}.ka-alert.has-items{border-color:#efd6ae;background:#fffcf6}.ka-alert.has-items .ka-alert-count{background:#fff0d9;color:#ab7228}.ka-alert.ka-opportunity.has-items{border-color:#bbdfd9;background:#f5fcfa}.ka-alert.ka-opportunity.has-items .ka-alert-count{background:#ddf3ed;color:#23816d}.ka-alert-body{padding:0 18px 16px;font-size:11px;color:#647a96}.ka-alert-body p{margin:0 0 10px}.ka-alert-body ol{padding-left:17px;margin-bottom:0}.ka-alert-body li{padding:7px 0;border-top:1px solid #e9edf3}.ka-alert-body li b{font-size:12px;color:#354c6c}
.ka-ads .kc-campaigns .kc-campaign-table th{background:#f1f5fc;color:#7185a3;font-size:10px;text-transform:uppercase;padding:14px 12px}.ka-ads .kc-campaigns .kc-campaign-table td{padding:19px 12px}.ka-ads .kc-campaigns .kc-campaign-table td:nth-child(5){font-weight:800;color:#2c6e67}.ka-ads nav[aria-label^='Paginação']{font-size:11px;line-height:1.8;color:#7186a4;margin-top:15px}.ka-ads .grafico-box{height:300px;margin-top:24px;position:relative;min-width:0}.ka-ads .grafico-box canvas{max-width:100%}.ka-ads .aviso{background:#fff9ec;border-color:#f0dfbc;border-radius:11px;padding:13px;font-size:11px;color:#886d3b}.ka-ads table{font-variant-numeric:tabular-nums}.ka-ads table th{white-space:nowrap}
@media(max-width:960px){.ka-hero{padding:24px}.ka-actions{width:100%}.ka-ads .stat .num{font-size:24px}}
@media(max-width:640px){.ka-hero{padding:22px 18px;border-radius:16px;gap:15px}.ka-hero h2{font-size:25px}.ka-actions a{flex:1;text-align:center;padding:10px}.ka-ads .card{padding:17px}.ka-ads .ka-kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.ka-ads .stat{padding:15px 12px}.ka-ads .stat .num{font-size:21px}.ka-ads .stat .lab{font-size:9px;letter-spacing:0}.ka-alert-grid{grid-template-columns:1fr}.ka-ads form>label{flex:1;min-width:115px}.ka-ads form>.btn{align-self:end}.ka-section-title{align-items:start}.ka-section-title span{max-width:100px;text-align:right}}
.ka-ads .ka-budget-mini{margin-top:8px;max-width:210px;font-size:10px;color:#7186a4}.ka-ads .ka-budget-head{display:flex;justify-content:space-between;gap:8px;margin-bottom:5px}.ka-ads .ka-budget-head b{font-weight:800}.ka-ads .ka-budget-track{height:6px;border-radius:8px;background:#e7edf6;overflow:hidden}.ka-ads .ka-budget-track span{display:block;height:100%;border-radius:8px}.ka-ads .ka-budget-mini small,.ka-ads .ka-budget-na{display:block;margin-top:5px;font-size:9px;color:#8b9ab0}
/* Ads overview follows the store's navy theme; scoped to this screen. */
body:has(.ka-ads),body:has(.ka-ads) .layout,body:has(.ka-ads) .layout>.conteudo{background:#081426;color:#eaf2ff}
.ka-ads{color:#eaf2ff;--ka-line:#2d4864;--ka-muted:#b2c7da}
body:has(.ks-store-sidebar) .conteudo .ka-ads h2,body:has(.ks-store-sidebar) .conteudo .ka-ads h3{color:#edf5ff}
.ka-ads .card{background:#11243a;border-color:#2d4864;box-shadow:0 12px 30px #030b1b30}
body:has(.ks-store-sidebar) .conteudo .ka-ads .card,body:has(.ks-store-sidebar) .conteudo .ka-ads .stat{border-color:#2d4864}
body:has(.ks-store-sidebar) .conteudo .ka-ads .stat{background:#13283f;border-color:#2d4864}
body:has(.ks-store-sidebar) .conteudo .ka-ads .stat:nth-child(2){background:linear-gradient(125deg,#155b9d,#247eb4);border-color:#438cc0}
body:has(.ks-store-sidebar) .conteudo .ka-ads .stat .num{color:#f4f9ff}
body:has(.ks-store-sidebar) .conteudo .ka-ads .stat .lab{color:#bdd0e4}
.ka-ads .stat small,.ka-ads .muted,.ka-section-title span{color:#b2c7da}
.ka-ads label{color:#bdd0e4}.ka-ads input,.ka-ads select{background:#0d1d30;border-color:#3a5772;color:#f1f7ff;color-scheme:dark}
.ka-alert,.ka-alert.has-items,.ka-alert.ka-opportunity.has-items{background:#142b42;border-color:#35536d}.ka-alert.has-items{border-color:#957552}.ka-alert.ka-opportunity.has-items{border-color:#448b80}
.ka-alert summary,.ka-alert-body,.ka-alert-body li b{color:#e4f1ff}.ka-alert-body li{border-color:#35516b}.ka-alert-count,.ka-alert.has-items .ka-alert-count,.ka-alert.ka-opportunity.has-items .ka-alert-count{background:#284861;color:#e4f5ff}
body:has(.ks-store-sidebar) .conteudo .ka-ads th, .ka-ads .kc-campaigns .kc-campaign-table th{background:#1b344e;color:#d0dfef;border-color:#39536c}
body:has(.ks-store-sidebar) .conteudo .ka-ads td{color:#d7e6f5;border-color:#30465c}.ka-ads .kc-campaigns .kc-campaign-table td:nth-child(5){color:#8de2c3}
.ka-ads a{color:#93ceff}.ka-ads .aviso{background:#382e21;border-color:#80653c;color:#ffe0ae}.ka-ads .ka-budget-track{background:#35516c}
body:has(.ks-store-sidebar) .conteudo .ka-ads .kc-campaigns a.kc-campaign-name,body:has(.ks-store-sidebar) .conteudo .ka-ads .kc-campaigns a.kc-campaign-name:visited{color:#e6f3ff!important}
body:has(.ks-store-sidebar) .conteudo .ka-ads .kc-campaigns .kc-campaign-row:hover,body:has(.ks-store-sidebar) .conteudo .ka-ads .kc-campaigns .kc-campaign-row:focus-visible{background:#1d3a56;box-shadow:inset 3px 0 #79c9ff}
@media(max-width:760px){body:has(.ks-store-sidebar) .conteudo .ka-ads .kc-campaigns .kc-campaign-row{background:#142b42;border-color:#35536d}}
</style>"""


def header(cid, store, start, end):
    cid=str(int(cid))
    from section_refresh import render as refresh
    return STYLE+"<style>.ka-actions .k-refresh{margin:0!important;max-width:330px;gap:8px!important}.ka-actions .k-refresh button{background:#ffffff0b;color:#e3edfc;border:1px solid #59789e;border-radius:10px;min-height:40px;padding:10px 15px;font-size:12px;cursor:pointer}.ka-actions .k-refresh [role=status]{font-size:10px!important;color:#b6c9e4}</style><div class='ka-ads'><header class='ka-hero'><div><span class='ka-eyebrow'>Product Ads · "+escape(str(store))+"</span><h2>Publicidade</h2><p>"+start.strftime('%d/%m')+' a '+end.strftime('%d/%m')+"</p></div><div class='ka-actions'><a href='#ka-campaign-list'>Ver campanhas</a>"+refresh(cid,'ads')+"</div></header>"


def alert_card(title, description, items, empty, opportunity=False):
    cls='ka-alert'+(' has-items' if items else '')+(' ka-opportunity' if opportunity else '')
    body=('<ol>'+''.join('<li><b>'+name+"</b><div class='muted'>"+detail+'</div></li>' for name,detail in items[:20])+'</ol>') if items else '<p>'+empty+'</p>'
    return "<details class='"+cls+"'"+(' open' if items else '')+"><summary>"+title+"<span class='ka-alert-count'>"+str(len(items))+"</span></summary><div class='ka-alert-body'><p class='muted'>"+description+'</p>'+body+('<p>Primeiros 20 resultados.</p>' if len(items)>20 else '')+'</div></details>'


def daily_chart(rows):
    ordered=list(reversed(rows))
    labels=[date.fromisoformat(str(r['data'])).strftime('%d/%m') for r in ordered]
    datasets=[dict(label='Faturamento atribuído',data=[float(r['faturamento'] or 0) for r in ordered],borderColor='#4e7be6',backgroundColor='#4e7be61a',fill=True,tension=.3,borderWidth=3,pointRadius=0,pointHoverRadius=5),
              dict(label='Investimento',data=[float(r['gasto'] or 0) for r in ordered],borderColor='#21a39d',borderDash=[5,4],tension=.3,borderWidth=2,pointRadius=0,pointHoverRadius=4)]
    return """<section class='card'><h3>Evolução diária</h3><p class='muted'>Faturamento atribuído e investimento em reais, nos dias com registros.</p><div class='grafico-box'><canvas id='ads-historico' role='img' aria-label='Evolução diária do faturamento atribuído e investimento em reais'></canvas></div>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'></script><script>(function(){if(typeof Chart==='undefined')return;var currency=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'});new Chart(document.getElementById('ads-historico'),{type:'line',data:{labels:"""+json.dumps(labels)+",datasets:"+json.dumps(datasets)+"""},options:{locale:'pt-BR',responsive:true,maintainAspectRatio:false,animation:matchMedia('(prefers-reduced-motion:reduce)').matches?false:{duration:350},interaction:{intersect:false,mode:'index'},plugins:{legend:{position:'bottom',align:'start',labels:{usePointStyle:true,boxWidth:8,padding:20,color:'#b5cce0',font:{size:11}}},tooltip:{backgroundColor:'#14243b',cornerRadius:10,padding:13,callbacks:{label:function(c){return c.dataset.label+': '+currency.format(c.parsed.y)}}}},scales:{x:{grid:{display:false},border:{display:false},ticks:{maxRotation:0,maxTicksLimit:7,color:'#b5cce0',font:{size:10}}},y:{beginAtZero:true,border:{display:false},grid:{color:'#304860'},ticks:{maxTicksLimit:5,color:'#b5cce0',font:{size:10},callback:function(v){return currency.format(v)}}}}}});})();</script></section>"""

def budget_progress(budget, spent, updated, now_ts, exhausted_at=None):
    """Show observed daily spend only when the snapshot is recent."""
    import math
    try:
        budget, spent, updated, now_ts = map(float, (budget, spent, updated, now_ts))
    except (TypeError, ValueError, OverflowError):
        return "<small class='ka-budget-na'>Consumo de hoje indisponível</small>"
    if not all(map(math.isfinite, (budget, spent, updated, now_ts))) or budget <= 0 or spent < 0 or not 0 <= now_ts-updated <= 7200:
        return "<small class='ka-budget-na'>Consumo de hoje indisponível</small>"
    percent = spent / budget * 100
    tone = '#dc646d' if percent >= 100 else '#e2a646' if percent >= 80 else '#2da99d'
    width = min(100, round(percent, 1))
    label = ('%.0f%%' % percent)
    from datetime import datetime
    from zoneinfo import ZoneInfo
    exhausted_label = ""
    if percent >= 100 and exhausted_at is not None:
        try:
            stamp = datetime.fromtimestamp(int(exhausted_at), ZoneInfo("America/Sao_Paulo")).strftime("%Hh%M")
            exhausted_label = "<small>Limite detectado às "+stamp+"</small>"
        except (ValueError, TypeError, OverflowError, OSError):
            pass
    return ("<div class='ka-budget-mini' title='Gasto de hoje / orçamento diário'>"
            "<div class='ka-budget-head'><span>Orçamento hoje</span><b style='color:"+tone+"'>"+label+"</b></div>"
            "<div class='ka-budget-track' role='progressbar' aria-label='Consumo do orçamento diário' aria-valuemin='0' aria-valuemax='100' aria-valuenow='"+str(round(width))+"'>"
            "<span style='width:"+str(width)+"%;background:"+tone+"'></span></div>"
            "<small>R$ "+format(spent,'.2f').replace('.',',')+" / R$ "+format(budget,'.2f').replace('.',',')+"</small>"+exhausted_label+"</div>")


def campaign_configuration(campaign):
    """Current saved config, independent of the selected performance period.

    Official Product Ads equivalence: ACOS target = 100 / ROAS target.
    Missing/invalid targets must never become a fabricated zero-percent goal.
    """
    import math

    def number(key):
        raw = campaign.get(key)
        if raw is None or isinstance(raw, bool):
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError, OverflowError):
            return None
        return value if math.isfinite(value) and value >= 0 else None

    budget = number('orcamento')
    roas = number('roas_objetivo')
    target = 100 / roas if roas and roas > 0 else None
    if target is not None and not math.isfinite(target):
        target = None
    money = ('R$ ' + format(budget, ',.2f').replace(',', '_').replace('.', ',').replace('_', '.')) if budget is not None else 'Não informado'
    acos = format(target, '.2f').replace('.', ',') + '%' if target is not None else 'Não informado'
    return money, acos
