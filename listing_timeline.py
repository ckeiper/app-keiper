"""One completed-day timeline for verified item sales and independently observed signals."""
import json
from datetime import datetime,timedelta
from html import escape
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from listing_full_sales_chart import daily_sales,daily_full_status
from full_sales_view_chart import LABELS, STYLE as FULL_CHART_STYLE
from investigation_evidence import window
from offer_history import price_events, confirmed_price, daily_readings, period_readings
from section_help import STYLE as HELP_STYLE, section_help

BR=ZoneInfo('America/Sao_Paulo')


def build(item_id,orders,items,coverage,full,visits,offers,end,days=14,pending=False):
    dates,sales=daily_sales(orders,items,coverage,item_id,days=days,today=end,has_pending=pending)
    traffic=[]
    for day in dates:
        reading=window(visits,[day],['visitas'],'dia')
        traffic.append(int(reading['totals']['visitas']) if reading['complete'] else None)
    offers=period_readings(offers,end,days+1)
    latest=daily_readings(offers)
    prices=[]
    for day in dates:
        row=latest.get(day)
        price=confirmed_price(row) if row else None
        prices.append(float(price) if price is not None else None)
    events=[]
    for event in price_events(offers):
        stamp=datetime.fromtimestamp(event['at'],BR)
        day=stamp.date().isoformat()
        if day in dates:
            events.append(dict(day=day,at=stamp.strftime('%d/%m %H:%M'),
                               before=float(event['before']),after=float(event['after'])))
    return dict(dates=dates,sales=sales,visits=traffic,prices=prices,
                full=daily_full_status(full,dates),events=events)


def render(item_id,orders,items,coverage,full,visits,offers,end,*,pending=False,args=None):
    args=args or {}
    days=7 if str(args.get('janela_linha'))=='7' else 14
    mode=str(args.get('comparar_linha') or 'visitas')
    if mode not in ('visitas','preco','nenhum'):
        mode='visitas'
    data=build(item_id,orders,items,coverage,full,visits,offers,end,days=days,pending=pending)
    out="""<style>
.item-timeline{min-width:0;max-width:100%;box-sizing:border-box;border:1px solid #dce6f1;border-radius:15px;background:#fff;padding:22px;margin:18px 0;color:#213b56}.item-timeline h3{margin:0 0 8px}.timeline-filter{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:15px 0}.timeline-filter label{display:grid;gap:5px;font-size:12px}.timeline-filter select{padding:9px;border:1px solid #dce6ef;border-radius:8px}.timeline-chart{height:330px;position:relative;width:100%;min-width:0;max-width:100%;overflow:hidden}.timeline-chart canvas{max-width:100%}.timeline-meta{font-size:11px;color:#6d7f94;line-height:1.6}.timeline-coverage{display:flex;flex-wrap:wrap;gap:8px;margin:13px 0}.timeline-coverage span{padding:6px 9px;background:#f0f5fa;border-radius:7px;font-size:11px}.item-timeline summary{padding:12px 0;cursor:pointer;font-size:12px;font-weight:650}.timeline-pages{display:flex;gap:12px;align-items:center;margin-top:12px;font-size:12px}.timeline-table{overflow:auto;min-width:0;max-width:100%}.timeline-table table{width:100%;border-collapse:collapse;font-size:12px}.timeline-table td,.timeline-table th{padding:9px;border-bottom:1px solid #e8eef5;text-align:left;white-space:nowrap}@media(max-width:600px){.item-timeline{padding:14px}.timeline-chart{height:290px}}
body .conteudo section.item-timeline{background:#102238;color:#eaf2ff;border-color:#34516e}
body .conteudo .item-timeline h3,body .conteudo .item-timeline summary{color:#eaf2ff}
body .conteudo .item-timeline .timeline-meta,body .conteudo .item-timeline .timeline-pages{color:#bdcce1}
body .conteudo .item-timeline .timeline-coverage span,body .conteudo .item-timeline table th,body .conteudo .item-timeline table td{background:#182e49;color:#eaf2ff;border-color:#426184}
body .conteudo .item-timeline select{background:#0b192c;color:#eaf2ff;border-color:#426184}
body .conteudo .item-timeline a{color:#b9e5ff}
body .conteudo .item-timeline .timeline-pages a.filtro{background:#1c3552;color:#b9e5ff!important;border-color:#426184}
body .conteudo .item-timeline label,body .conteudo .item-timeline .timeline-chart p{color:#bdcce1}
.timeline-stock-strip{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);box-sizing:border-box}
.timeline-stock-strip[hidden]{display:none}
.item-timeline .timeline-stock-day{display:grid;place-items:center;min-width:0;min-height:26px;padding:0;border:0;background:transparent;cursor:pointer}
.timeline-stock-day .full-chart-stock{max-width:90%}
.timeline-stock-detail{display:block;min-height:1.4em;font-size:12px;margin-top:8px}
body .conteudo .item-timeline :is(a,button,select,summary):focus-visible{outline:3px solid #85c8ec;outline-offset:3px}
</style><section class='item-timeline'>"""
    out=HELP_STYLE+FULL_CHART_STYLE+out+section_help(
        'Linha do tempo do anúncio', 'Como ler a linha do tempo',
        '<p>Vendas verificadas e sinais observados nas mesmas datas. A faixa de Full mostra a última leitura de cada dia. O traço cinza indica situação desconhecida.</p>'
        '<p>A marca de preço mostra a última mudança detectada no dia. O preço diário usa a última leitura única e confirmada. '
        'Duplicidades e falhas ficam como lacunas.</p>',
        subheading=True)
    out+='<p class="timeline-meta">%s dias encerrados até %s</p>' % (days,end.strftime('%d/%m/%Y'))
    out+="<form class='timeline-filter' method='get'>"
    for key,value in args.items():
        if key not in ('janela_linha','comparar_linha','pagina_linha'):
            out+="<input type='hidden' name='%s' value='%s'>" % (escape(str(key),quote=True),escape(str(value),quote=True))
    for name,label,choices,selected in [('janela_linha','Janela',[('14','14 dias'),('7','7 dias')],str(days)),('comparar_linha','Comparar vendas com',[('visitas','Visitas'),('preco','Preço observado'),('nenhum','Somente Full')],mode)]:
        out+='<label>'+label+"<select name='%s'>" % name
        out+=''.join("<option value='%s'%s>%s</option>" % (k,' selected' if k==selected else '',v) for k,v in choices)
        out+='</select></label>'
    out+="<button class='filtro-btn'>Aplicar</button></form><div class='timeline-coverage'>"
    for key,label in [('sales','Vendas'),('visits','Visitas'),('prices','Preço'),('full','Full')]:
        out+='<span>%s: %s/%s dias com dado válido</span>' % (label,sum(v is not None for v in data[key]),days)
    out+='</div>'
    identifier='item-timeline-'+''.join(c for c in str(item_id) if c.isalnum())[:60]
    out+="<div class='timeline-chart'><p id='%s-notice' role='status' hidden>Gráfico indisponível. Confira os dados diários abaixo.</p><canvas id='%s' role='img' aria-label='Linha do tempo de vendas, observações de Full e sinal selecionado'></canvas></div>" % (escape(identifier,quote=True),escape(identifier,quote=True))
    datasets=[dict(type='bar',label='Vendas brutas dos itens (R$)',data=data['sales'],backgroundColor='#4e91ec',hoverBackgroundColor='#83bbff',borderRadius=6,maxBarThickness=28,yAxisID='sales',order=3)]
    if mode=='visitas':
        datasets.append(dict(type='line',label='Visitas registradas',data=data['visits'],borderColor='#297b9a',backgroundColor='#297b9a',pointRadius=3,tension=0,spanGaps=False,yAxisID='extra',order=2))
    elif mode=='preco':
        datasets.append(dict(type='line',label='Último preço observado do dia (R$)',data=data['prices'],borderColor='#8766be',backgroundColor='#8766be',pointRadius=4,tension=0,spanGaps=False,showLine=False,yAxisID='extra',order=2))
    out += "<div class='timeline-stock-strip' role='group' aria-label='Estoque Full por dia' hidden>"
    for day, value in zip(data['dates'], data['full']):
        state = {1: 'available', 0: 'empty', None: 'unknown'}[value]
        date_label = datetime.fromisoformat(day).strftime('%d/%m/%Y')
        label = escape(f'{date_label} · Full: {LABELS[state]}', quote=True)
        out += (f"<button type='button' class='timeline-stock-day' aria-label='{label}' title='{label}'>"
                f"<i class='full-chart-stock' data-state='{state}' aria-hidden='true'></i></button>")
    out += "</div><div class='full-chart-key'><strong>Estoque Full observado</strong>"
    for state in ('available', 'empty', 'unknown'):
        out += f"<span><i class='full-chart-stock' data-state='{state}' aria-hidden='true'></i>{LABELS[state]}</span>"
    out += "</div><output class='timeline-stock-detail'></output>"
    event_by_day={event['day']:event for event in data['events']}
    event_points=[]
    event_notes=[]
    for day in data['dates']:
        event=event_by_day.get(day)
        event_points.append((event['after'] if mode=='preco' else .95) if event else None)
        event_notes.append('Preço R$ %.2f → R$ %.2f · %s' % (event['before'],event['after'],event['at']) if event else None)
    datasets.append(dict(type='line',label='Mudança de preço detectada',data=event_points,eventNotes=event_notes,showLine=False,pointRadius=6,pointStyle='triangle',backgroundColor='#db9a39',borderColor='#db9a39',yAxisID='extra' if mode=='preco' else 'markers',isEvent=True,order=0))
    payload=json.dumps(dict(labels=data['dates'],datasets=datasets),ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    out+="<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'></script>"
    out+=("<script>(function(){var el=document.getElementById("+json.dumps(identifier)+");if(!el)return;if(typeof Chart==='undefined'){document.getElementById(el.id+'-notice').hidden=false;el.hidden=true;return;}var light=document.documentElement.dataset.theme==='light';var ink=light?'#405972':'#bdcce1';var grid=light?'#d3dfeb':'#34516e';"
         "var section=el.closest('.item-timeline');var strip=section.querySelector('.timeline-stock-strip');"
         "var detail=section.querySelector('.timeline-stock-detail');"
         "strip.querySelectorAll('button').forEach(function(day){"
         "function show(){detail.textContent=day.getAttribute('aria-label');}"
         "['focus','pointerenter','click'].forEach(function(event){day.addEventListener(event,show);});});"
         "var stockLayout={id:'timelineStockLayout',afterLayout:function(chart){"
         "strip.style.paddingLeft=chart.chartArea.left+'px';"
         "strip.style.paddingRight=(chart.width-chart.chartArea.right)+'px';strip.hidden=false;}};"
         "new Chart(el,{data:"+payload+",options:{locale:'pt-BR',animation:false,responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{position:'bottom',labels:{color:ink,usePointStyle:true,padding:14}},tooltip:{callbacks:{label:function(c){if(c.dataset.isEvent)return c.dataset.eventNotes[c.dataIndex]||'Mudança detectada';return c.dataset.label+': '+c.formattedValue;}}}},scales:{x:{offset:true,grid:{color:grid},ticks:{color:ink,callback:function(v){var s=this.getLabelForValue(v);return s.slice(8)+'/'+s.slice(5,7);}}},sales:{beginAtZero:true,position:'left',ticks:{color:ink},grid:{color:grid},title:{display:true,color:ink,text:'Vendas (R$)'}},extra:{display:"+('false' if mode=='nenhum' else 'true')+",beginAtZero:true,position:'right',ticks:{color:ink},grid:{drawOnChartArea:false},title:{display:true,color:ink,text:"+json.dumps('Preço observado (R$)' if mode=='preco' else 'Visitas')+"}},markers:{axis:'y',display:false,min:0,max:1.3}}},plugins:[stockLayout]})})();</script>")
    try:
        page=max(1,int(args.get('pagina_linha',1)))
    except (TypeError,ValueError):
        page=1
    pages=(days+6)//7;page=min(page,pages)
    out+=("<details open>" if 'pagina_linha' in args else "<details>")+"<summary>Conferir dados por dia</summary><div class='timeline-table'><table><thead><tr><th>Data</th><th>Vendas</th><th>Visitas</th><th>Preço observado</th><th>Full observado</th></tr></thead><tbody>"
    for i in range((page-1)*7,min(page*7,days)):
        cells=[datetime.fromisoformat(data['dates'][i]).strftime('%d/%m/%Y')]
        for key in ('sales','visits','prices'):
            value=data[key][i]
            cells.append('Sem dado válido' if value is None else (str(value) if key=='visits' else 'R$ %.2f' % value))
        cells.append({1:'Com estoque',0:'Zerado',None:'Desconhecido'}[data['full'][i]])
        out+='<tr>'+''.join('<td>'+escape(c)+'</td>' for c in cells)+'</tr>'
    out+='</tbody></table></div><nav class="timeline-pages" aria-label="Paginação dos dados da linha do tempo">Página %s de %s' % (page,pages)
    for label,n in [('Anterior',page-1),('Próxima',page+1)]:
        if 1<=n<=pages:
            params=dict(args);params['pagina_linha']=n
            out+=" <a class='filtro' href='?%s'>%s</a>" % (escape(urlencode(params),quote=True),label)
    return out+'</nav></details></section>'
