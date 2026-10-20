"""Colorful management layout. Presentation only; no database or metric changes."""
from html import escape
from urllib.parse import urlencode
from sales_view import fmt

STYLE = """<style>
body:has(.mgmt-dashboard){background:#eef1f8;color:#202941}
body:has(.mgmt-dashboard) .top{background:#111a32;box-shadow:none;min-height:68px;padding:12px 28px;border:0}
body:has(.mgmt-dashboard) .top h1{font-size:17px}
body:has(.mgmt-dashboard) .wrap{max-width:1680px;margin:22px auto}
.layout:has(.mgmt-dashboard){background:transparent;gap:22px;border-radius:0}
.layout:has(.mgmt-dashboard)>.menu-lateral{width:205px;flex-shrink:0;background:#111a32;border-radius:16px;padding:16px 10px;top:18px}
.layout:has(.mgmt-dashboard)>.menu-lateral a.item{display:flex;align-items:center;gap:10px;padding:11px 12px;font-size:12px;border-radius:9px}
.layout:has(.mgmt-dashboard)>.menu-lateral a.item.atual{background:linear-gradient(110deg,#5265de,#7760df);box-shadow:0 5px 14px #030a1d44}
.layout:has(.mgmt-dashboard)>.conteudo{padding:8px 0 30px;background:transparent}
.mgmt-dashboard{--ink:#202941;--muted:#7c879e;--line:#e8ecf4;--brand:#6265dc;color:var(--ink)}
.mgmt-dashboard h2{color:var(--ink);font-size:16px;line-height:1.4;letter-spacing:-.35px;margin:0 0 16px}
.mgmt-dashboard .card{background:#fff;padding:22px;border:1px solid var(--line);border-radius:16px;box-shadow:0 4px 22px #23355704;margin-bottom:20px}
.mgmt-dashboard p{font-size:12px;line-height:1.65;color:#78849a}
.mgmt-dashboard .muted{font-size:11px;color:#8290a5;line-height:1.6}
.mgmt-header{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:21px}
.mgmt-header h2{font-size:27px;letter-spacing:-.8px;margin:3px 0 5px;font-weight:750}
.mgmt-header p{margin:0}.mgmt-eyebrow{color:#7c88a0;font-size:10px;font-weight:750;letter-spacing:1.8px;text-transform:uppercase}
.mgmt-header .mgmt-links{margin:0}
.mgmt-dashboard .btn-acoes{background:#6265dc;color:white;border:1px solid #6265dc;padding:10px 15px;font-size:11px;font-weight:650;border-radius:9px;box-shadow:none}
.mgmt-dashboard .btn-acoes:hover{background:#5154cc}
.mgmt-dashboard .btn-acoes.cinza{background:#fff;border-color:#e3e7f1;color:#63718b}
.mgmt-period{padding:12px 16px!important;background:#ffffffb8!important;box-shadow:none!important}
.mgmt-filter{display:flex;gap:12px;align-items:end;flex-wrap:wrap}
.mgmt-filter label{display:grid;gap:6px;font-size:10px;font-weight:650;color:#77849b}
.mgmt-filter input,.mgmt-filter select{box-sizing:border-box;max-width:100%;min-height:36px;border:1px solid #e3e8f2;border-radius:8px;background:#fff;font:inherit;font-size:12px;color:#3b4863;padding:8px 10px}
.mgmt-filter input:focus,.mgmt-filter select:focus{outline:3px solid #e9e8fd;border-color:#8077e4}
.mgmt-period-dates{font-size:11px;align-self:center}.mgmt-period-dates summary{cursor:pointer;color:#656dd4}
.mgmt-period-dates[open]{display:flex}.mgmt-period-dates label{display:inline-grid;margin:8px 8px 0 0}
.mgmt-tabs{display:flex;align-items:center;gap:22px;border-bottom:1px solid #dfe5f0;margin:20px 0 24px;overflow:auto;white-space:nowrap}
.mgmt-tabs a{padding:13px 2px;color:#8590a6;border-bottom:3px solid transparent;text-decoration:none;font-size:12px;font-weight:650;flex-shrink:0}
.mgmt-tabs a[aria-selected=true]{color:#5d60d7;border-color:#6c67df}
.mgmt-tabs a:focus-visible{outline:3px solid #d6d5fc;outline-offset:2px}
.mgmt-tab-count{padding:3px 7px;border-radius:6px;background:#e7e8f8;color:#6367ca;font-size:10px;margin-left:6px}
.mgmt-panel[hidden]{display:none!important}.mgmt-panel{min-width:0}
.mgmt-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:15px;margin:0 0 20px}
.mgmt-dashboard .stat{position:relative;min-width:0;border:1px solid var(--line);border-radius:15px;background:#fff;box-shadow:0 4px 18px #25355403;padding:19px 18px;transition:none;overflow:hidden}
.mgmt-dashboard .stat:before{display:none}.mgmt-dashboard .stat:hover{transform:none;box-shadow:0 4px 18px #25355403}
.mgmt-dashboard .stat .lab{font-size:10px;font-weight:650;color:#8490a4;max-width:80%;letter-spacing:0}
.mgmt-dashboard .stat .num{font-size:27px;letter-spacing:-.8px;line-height:1.25;font-weight:750;color:#26334c;margin:12px 0 8px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.mgmt-dashboard .stat small{display:block;font-size:10px;color:#8a95a8;line-height:1.65}
.mgmt-dashboard .mgmt-stat-empty .num{font-size:19px;color:#9ba6b7;letter-spacing:-.4px;min-height:34px}
.mgmt-metric-icon{position:absolute;right:15px;top:14px;width:29px;height:29px;display:grid;place-items:center;border-radius:9px;background:#eeedff;color:#7770d9}
.mgmt-metric-icon svg{width:15px;height:15px}
.mgmt-dashboard .mgmt-tone-revenue{background:linear-gradient(125deg,#5062d9 0%,#7a60df 100%);border-color:transparent;box-shadow:0 9px 24px #6260cf24}
.mgmt-dashboard .mgmt-tone-revenue .lab,.mgmt-dashboard .mgmt-tone-revenue small{color:#e3e2ff}
.mgmt-dashboard .mgmt-tone-revenue .num{color:white}
.mgmt-tone-revenue .mgmt-metric-icon{background:#ffffff24;color:#fff}
.mgmt-tone-teal .mgmt-metric-icon{background:#e3f7ef;color:#20a381}
.mgmt-tone-amber .mgmt-metric-icon{background:#fff1dc;color:#d6a04b}
.mgmt-tone-blue .mgmt-metric-icon{background:#e7f0ff;color:#568adb}
.mgmt-ads-strip{background:#fff;border:1px solid var(--line);padding:7px 2px;border-radius:15px;margin:0 0 12px}
.mgmt-ads-strip .mgmt-kpis{gap:0;margin:0}
.mgmt-dashboard .mgmt-ads-strip .stat{border:0;border-radius:0;box-shadow:none;padding:13px 17px}
.mgmt-ads-strip .stat+.stat{border-left:1px solid #eef1f6!important}
.mgmt-dashboard .mgmt-ads-strip .num{font-size:23px;margin:8px 0 5px}
.mgmt-ads-strip .mgmt-tone-teal .num{color:#1e9b80}.mgmt-ads-strip .mgmt-tone-amber .num{color:#bf9353}.mgmt-ads-strip .mgmt-tone-blue .num{color:#5783d1}
.mgmt-links{display:flex;flex-wrap:wrap;gap:8px;margin:15px 0}
.mgmt-dashboard nav.mgmt-links .btn-acoes{background:transparent;border-color:#dce2ee;font-size:10px}
.mgmt-overview-bottom{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:20px;align-items:stretch;margin-top:20px}
.mgmt-overview-bottom>.card{margin-bottom:0}.mgmt-overview-bottom:has(>.card:only-child){grid-template-columns:1fr}
.mgmt-catalog .mgmt-kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.mgmt-dashboard .mgmt-catalog .stat{border:0;border-radius:10px;background:#f7f9fd;padding:13px}
.mgmt-dashboard .mgmt-catalog .num{font-size:21px;margin:9px 0 5px}
.mgmt-catalog .mgmt-metric-icon{display:none}
.mgmt-dashboard details summary{cursor:pointer;font-size:11px;color:#787cbd}
.mgmt-leaders ol{list-style:none;margin:0;padding:0;counter-reset:leaders}
.mgmt-leaders li{position:relative;padding:14px 0 14px 35px;border-bottom:1px solid #eef1f7;font-size:11px;line-height:1.8;color:#8490a4;counter-increment:leaders}
.mgmt-leaders li:last-child{border:0}
.mgmt-leaders li:before{content:counter(leaders,decimal-leading-zero);position:absolute;left:0;top:15px;font-size:12px;font-weight:700;color:#a8b0c6}
.mgmt-leaders li:first-child:before{color:#b68b4d}.mgmt-leaders a{display:block;color:#394965;font-weight:650;font-size:12px;text-decoration:none}
.mgmt-notice{background:#fff8e9;border:1px solid #f3e6c8;border-radius:10px;padding:11px 14px;margin:10px 0 16px}
.mgmt-notice summary{font-size:11px!important;color:#aa8443!important}.mgmt-notice ul{font-size:11px;line-height:1.7;color:#9b855c}
.mgmt-chart{margin-top:20px}.mgmt-chart-header{display:flex;justify-content:space-between;gap:12px;align-items:center}
.mgmt-chart-header h2{margin:0}.mgmt-chart-legend{display:flex;gap:14px;font-size:10px;color:#8b96ab}
.mgmt-chart-legend span:before{content:'';display:inline-block;width:7px;height:7px;border-radius:50%;background:#7a6ae0;margin-right:5px}
.mgmt-chart-legend span+span:before{background:#61c2b0}
.mgmt-chart-body{display:flex;gap:12px;margin:25px 0 15px}.mgmt-chart-y{display:flex;flex-direction:column;justify-content:space-between;height:170px;font-size:10px;color:#9ba6b8;padding-bottom:12px;text-align:right;min-width:64px}.mgmt-chart-plot{flex:1;min-width:0}.mgmt-chart svg{display:block;width:100%;height:160px;overflow:visible}.mgmt-chart-x{display:flex;justify-content:space-between;font-size:10px;color:#9ba6b8;margin-top:10px}
.mgmt-chart-axis{font-size:9px;fill:#9ba6b8;font-family:inherit}
.mgmt-chart-empty{min-height:110px;display:grid;place-items:center;border:1px dashed #e3e7f1;border-radius:12px;margin-top:18px;color:#9ca6b9;font-size:12px}
.mgmt-priorities{margin-top:22px}.mgmt-section-title{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:0 0 14px}
.mgmt-section-title h2{margin:0}.mgmt-section-title>a{font-size:11px;color:#7775cc;text-decoration:none}
.mgmt-preview-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.mgmt-preview-card{border:1px solid #e8e6f8;background:#faf9ff;border-radius:14px;padding:17px;min-width:0}
.mgmt-preview-card.mgmt-preview-high{border-color:#f4dfd9;background:#fff8f5}
.mgmt-preview-card h3{font-size:12px;line-height:1.5;margin:11px 0 8px;color:#48516b}
.mgmt-preview-card p{font-size:10px;margin:0 0 10px}.mgmt-preview-card a{font-size:10px;font-weight:650;text-decoration:none;color:#8272cf}
.mgmt-preview-label{font-size:9px;text-transform:uppercase;letter-spacing:1px;color:#b89378}
.mgmt-preview-title{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#8c96a9;display:block;margin-top:7px}
.mgmt-pill{display:inline-block;padding:4px 8px;border-radius:5px;font-size:10px;font-weight:650;background:#f0edfc;color:#8a7bbb}
.mgmt-high{background:#fff0e9;color:#cb8364}.mgmt-medium{background:#fff4dd;color:#b58e4c}
.mgmt-table{width:100%;min-width:850px;border-collapse:collapse;font-size:11px}
.mgmt-table th{font-size:9px;letter-spacing:.5px;color:#919bae;background:#f8f9fd;text-transform:uppercase;padding:13px 12px;border-bottom:1px solid #e8edf5}
.mgmt-table td{vertical-align:top;white-space:normal;padding:16px 12px;border-bottom:1px solid #eef1f7;color:#62718a;font-size:11px;line-height:1.7}
.mgmt-table tbody tr:hover{background:#fafbfe}.mgmt-table td:first-child{max-width:300px;color:#394861}
.mgmt-table small{display:block;font-size:10px;color:#98a1b3;margin-top:4px}.mgmt-table a{color:#6f72c5;text-decoration:none}
.mgmt-scroll{overflow-x:auto;border:1px solid #edf0f6;border-radius:10px;margin-top:18px}
.mgmt-pager{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:18px;font-size:10px;color:#9aa3b5}
.mgmt-filter{margin-bottom:8px}
.mgmt-small-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
@media(max-width:1200px){.mgmt-overview-bottom{grid-template-columns:1fr}.mgmt-kpis{gap:10px}.mgmt-dashboard .stat{padding:15px 13px}.mgmt-dashboard .stat .num{font-size:23px}}
@media(max-width:1000px){.mgmt-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.mgmt-preview-grid{grid-template-columns:1fr}.mgmt-ads-strip .stat:nth-child(3){border-left:0!important}.mgmt-ads-strip .stat:nth-child(n+3){border-top:1px solid #eef1f6!important}}
@media(max-width:820px){.layout:has(.mgmt-dashboard){gap:14px}.layout:has(.mgmt-dashboard)>.menu-lateral{width:100%;position:static;border-radius:12px}.layout:has(.mgmt-dashboard)>.menu-lateral a.item{display:inline-flex;flex-shrink:0}.mgmt-header h2{font-size:23px}.mgmt-dashboard .card{padding:17px}.mgmt-chart-header{align-items:start;flex-direction:column}.mgmt-tabs{gap:18px}}
@media(max-width:500px){body:has(.mgmt-dashboard) .wrap{padding:0 12px;margin:12px auto}.mgmt-kpis{gap:9px}.mgmt-dashboard .stat{padding:14px 11px}.mgmt-dashboard .stat .num{font-size:21px}.mgmt-dashboard .stat .lab{font-size:10px}.mgmt-metric-icon{width:24px;height:24px;right:10px;top:10px}.mgmt-filter label{flex:1;min-width:125px}.mgmt-header .mgmt-links{width:100%}.mgmt-section-title h2{font-size:14px}}
@media(prefers-reduced-motion:reduce){.mgmt-dashboard *{scroll-behavior:auto!important;transition:none!important}}
</style>"""

ICON = "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><path d='M4 18V8m5 10V4m5 14v-7m5 7V6M3 21h18'/></svg>"


def metric_card(label,value,note):
    tone = ('revenue' if label=='Faturamento de pedidos pagos' else
            'teal' if label in ('Pedidos pagos','ROAS entregue','Anúncios com vendas') else
            'amber' if label in ('Ticket médio por pedido','ACOS','Sem vendas no período') else
            'blue' if label in ('Unidades vendidas','TACOS da loja','Visitas coletadas') else 'violet')
    empty = " mgmt-stat-empty" if value.startswith(('Indisponível','Aguardando')) else ''
    return ("<div class='stat mgmt-tone-"+tone+empty+"'><span class='mgmt-metric-icon'>"+ICON
            +"</span><div class='lab'>"+escape(label)+"</div><div class='num'>"+escape(value)
            +"</div><small>"+escape(note)+"</small></div>")


def active_tab(args):
    selected=args.get('aba')
    if selected in ('overview','actions','analysis'):
        return selected
    if args.get('visao') or args.get('pagina_anuncios'):
        return 'analysis'
    if args.get('area') or args.get('prioridade') or args.get('busca') or args.get('pagina_acoes'):
        return 'actions'
    return 'overview'


def panel(name,selected):
    return ("<div class='mgmt-panel' id='mgmt-panel-"+name+"' role='tabpanel' aria-labelledby='mgmt-tab-"+name
            +"' data-mgmt-panel='"+name+"'"+(' hidden' if selected!=name else '')+">")


def tabs(cid,args,count,selected):
    out="<nav class='mgmt-tabs' role='tablist' aria-label='Análises da loja'>"
    for name,label in [('overview','Visão geral'),('actions','Oportunidades'),('analysis','Análise por anúncio')]:
        params=dict(args);params['aba']=name
        url='/painel/'+str(cid)+'?'+urlencode(params)
        out+=("<a role='tab' id='mgmt-tab-"+name+"' aria-controls='mgmt-panel-"+name
              +"' aria-selected='"+('true' if selected==name else 'false')+"' href='"+escape(url,quote=True)
              +"' data-mgmt-tab='"+name+"'>"+label
              +("<span class='mgmt-tab-count'>"+str(count)+"</span>" if name=='actions' else '')+"</a>")
    return out+'</nav>'


def daily_chart(report):
    current,previous=report['current'],report['previous']
    series=[current['daily'],previous['daily']]
    valid=[float(value) for values in series for value in values if value is not None]
    out=("<section class='card mgmt-chart'><div class='mgmt-chart-header'><h2>Evolução do faturamento</h2>"
         "<div class='mgmt-chart-legend'><span>Período atual</span><span>Período anterior</span></div></div>")
    if not valid:
        return out+"<div class='mgmt-chart-empty'>O gráfico aparece quando há dias de vendas verificados.</div></section>"
    ceiling=max(valid) or 1
    width,height=700,150
    out+="<div class='mgmt-chart-body'><div class='mgmt-chart-y'>"
    for level in (1,.5,0):
        out+="<span>"+escape(fmt(ceiling*level,True))+"</span>"
    out+="</div><div class='mgmt-chart-plot'><svg viewBox='0 0 700 150' preserveAspectRatio='none' role='img' aria-label='Faturamento diário dos períodos comparados; lacunas são dias sem dados'>"
    for level in (0,.5,1):
        y=height*(1-level)
        out+="<line x1='0' x2='700' y1='"+str(y)+"' y2='"+str(y)+"' stroke='#edf0f7' vector-effect='non-scaling-stroke'/>"
    for values,color in zip(series,('#7b6be1','#62c3b0')):
        segment=[]
        for index,value in enumerate(values):
            if value is None:
                if segment:
                    out+="<path d='"+" ".join(segment)+"' fill='none' stroke='"+color+"' stroke-width='2.6' stroke-linejoin='round' stroke-linecap='round' vector-effect='non-scaling-stroke'/>"
                    segment=[]
                continue
            x=(index/max(1,len(values)-1))*width
            y=height*(1-float(value)/ceiling)
            segment.append(('M' if not segment else 'L')+f'{x:.2f},{y:.2f}')
            out+="<circle cx='"+f'{x:.2f}'+"' cy='"+f'{y:.2f}'+"' r='2' fill='"+color+"'><title>"+escape(fmt(value,True))+"</title></circle>"
        if segment:
            out+="<path d='"+" ".join(segment)+"' fill='none' stroke='"+color+"' stroke-width='2.6' stroke-linejoin='round' stroke-linecap='round' vector-effect='non-scaling-stroke'/>"
    out+="</svg><div class='mgmt-chart-x'>"
    for day in (current['days'][0],current['days'][-1]):
        out+="<span>"+escape(day[8:10]+'/'+day[5:7])+"</span>"
    out+="</div></div></div><details><summary>Ver valores e datas comparados</summary><div class='mgmt-scroll'><table class='mgmt-table'><thead><tr><th>Data atual</th><th>Faturamento</th><th>Data anterior</th><th>Faturamento anterior</th></tr></thead><tbody>"
    for index,day in enumerate(current['days']):
        out+='<tr><td>'+escape(day)+'</td><td>'+escape(fmt(current['daily'][index],True))+'</td><td>'+escape(previous['days'][index])+'</td><td>'+escape(fmt(previous['daily'][index],True))+'</td></tr>'
    return out+'</tbody></table></div></details></section>'


def priorities(cid,report,args):
    params=dict(args);params['aba']='actions'
    out=("<section class='mgmt-priorities'><div class='mgmt-section-title'><h2>Seu próximo passo</h2><a href='"
         +escape('/painel/'+str(cid)+'?'+urlencode(params),quote=True)+"'>Ver todas as oportunidades →</a></div><div class='mgmt-preview-grid'>")
    seen=set()
    chosen=[]
    for signal in report['signals']:
        if signal['item_id'] not in seen:
            chosen.append(signal);seen.add(signal['item_id'])
        if len(chosen)==3:
            break
    for signal in chosen:
        url=signal['path'].format(cid=cid)
        priority={'alta':'Prioridade alta','media':'Atenção','oportunidade':'Oportunidade','dados':'Validar dados'}[signal['priority']]
        out+=("<article class='mgmt-preview-card "+('mgmt-preview-high' if signal['priority']=='alta' else '')+"'>"
              "<span class='mgmt-preview-label'>"+priority+"</span><h3>"+escape(signal['title'])+"</h3>"
              "<p>"+escape(signal['evidence'])+"</p><a href='"+escape(url,quote=True)+"'>Investigar anúncio →</a>"
              "<span class='mgmt-preview-title' title='"+escape(signal['label'],quote=True)+"'>"+escape(signal['label'])+"</span></article>")
    if not chosen:
        out+="<article class='mgmt-preview-card'><h3>Nenhuma prioridade confirmada</h3><p>Confira a cobertura dos dados e explore a análise por anúncio.</p></article>"
    return out+'</div></section>'


SCRIPT = """<script>
(function(){
  var links=Array.from(document.querySelectorAll('[data-mgmt-tab]'));
  var panels=Array.from(document.querySelectorAll('[data-mgmt-panel]'));
  if(!links.length)return;
  function activate(name,update){
    links.forEach(function(link){link.setAttribute('aria-selected',String(link.dataset.mgmtTab===name));link.setAttribute('tabindex',link.dataset.mgmtTab===name?'0':'-1');});
    panels.forEach(function(panel){
      panel.hidden=panel.dataset.mgmtPanel!==name;
      panel.querySelectorAll('form').forEach(function(form){
        var input=form.querySelector('input[name=aba]');
        if(!input){input=document.createElement('input');input.type='hidden';input.name='aba';form.appendChild(input);}
        input.value=panel.dataset.mgmtPanel;
      });
      panel.querySelectorAll('.mgmt-pager a').forEach(function(link){
        var url=new URL(link.href,location.href);url.searchParams.set('aba',panel.dataset.mgmtPanel);link.href=url.toString();
      });
    });
    if(update){var url=new URL(location.href);url.searchParams.set('aba',name);history.replaceState(null,'',url);}
  }
  links.forEach(function(link,index){
    link.addEventListener('click',function(event){
      if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
      event.preventDefault();activate(link.dataset.mgmtTab,true);
    });
    link.addEventListener('keydown',function(event){
      var next=event.key==='ArrowRight'?(index+1)%links.length:event.key==='ArrowLeft'?(index+links.length-1)%links.length:event.key==='Home'?0:event.key==='End'?links.length-1:null;
      if(next!==null){event.preventDefault();links[next].focus();activate(links[next].dataset.mgmtTab,true);}
    });
  });
  var selected=links.find(function(link){return link.getAttribute('aria-selected')==='true';});
  activate(selected?selected.dataset.mgmtTab:'overview',false);
  document.querySelectorAll('.mgmt-dashboard .mgmt-priorities a').forEach(function(link){
    if(link.textContent.indexOf('Ver todas')<0)return;
    link.addEventListener('click',function(event){
      if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
      event.preventDefault();activate('actions',true);links[1].focus();
    });
  });
})();
</script>"""
