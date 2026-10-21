"""One completed-day timeline for verified item sales and independently observed signals."""
import json
from datetime import datetime,timedelta
from html import escape
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from listing_full_sales_chart import daily_sales,daily_full_status
from investigation_evidence import window
from competitor_monitor import money
from offer_history import price_events

BR=ZoneInfo('America/Sao_Paulo')


def build(item_id,orders,items,coverage,full,visits,offers,end,days=14,pending=False):
    dates,sales=daily_sales(orders,items,coverage,item_id,days=days,today=end,has_pending=pending)
    traffic=[]
    for day in dates:
        reading=window(visits,[day],['visitas'],'dia')
        traffic.append(int(reading['totals']['visitas']) if reading['complete'] else None)
    latest={}
    for row in offers:
        day=datetime.fromtimestamp(row['observed_at'],BR).date().isoformat()
        if day in dates and (day not in latest or row['observed_at']>latest[day]['observed_at']):
            latest[day]=row
    prices=[]
    for day in dates:
        row=latest.get(day)
        price=money(row.get('price')) if row and row.get('confirmed') else None
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
</style><section class='item-timeline'><h3>Linha do tempo do anúncio</h3>"""
    out+='<p class="timeline-meta">Vendas verificadas e sinais observados nas mesmas datas · %s dias encerrados até %s. Os pontos de Full mostram a última leitura de cada dia, não a duração do estoque.</p>' % (days,end.strftime('%d/%m/%Y'))
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
    datasets=[dict(type='bar',label='Vendas brutas dos itens (R$)',data=data['sales'],backgroundColor='#4778cbaa',borderRadius=4,yAxisID='sales',order=3)]
    if mode=='visitas':
        datasets.append(dict(type='line',label='Visitas registradas',data=data['visits'],borderColor='#297b9a',backgroundColor='#297b9a',pointRadius=3,tension=0,spanGaps=False,yAxisID='extra',order=2))
    elif mode=='preco':
        datasets.append(dict(type='line',label='Último preço observado do dia (R$)',data=data['prices'],borderColor='#8766be',backgroundColor='#8766be',pointRadius=4,tension=0,spanGaps=False,showLine=False,yAxisID='extra',order=2))
    for value,label,color in [(1,'Full com estoque observado','#159674'),(0,'Full zerado observado','#d86560')]:
        datasets.append(dict(type='line',label=label,data=[1.1 if v==value else None for v in data['full']],showLine=False,pointRadius=5,pointStyle='rectRot',borderColor=color,backgroundColor=color,yAxisID='markers',isFull=True,order=1))
    event_by_day={event['day']:event for event in data['events']}
    event_points=[]
    for day in data['dates']:
        event=event_by_day.get(day)
        event_points.append(dict(x=day,y=event['after'] if mode=='preco' else .95,
            note='Preço R$ %.2f → R$ %.2f · %s' % (event['before'],event['after'],event['at'])) if event else None)
    datasets.append(dict(type='line',label='Mudança de preço detectada',data=event_points,showLine=False,pointRadius=6,pointStyle='triangle',backgroundColor='#db9a39',borderColor='#db9a39',yAxisID='extra' if mode=='preco' else 'markers',isEvent=True,order=0))
    payload=json.dumps(dict(labels=data['dates'],datasets=datasets),ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    out+="<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'></script>"
    out+="<script>(function(){var el=document.getElementById("+json.dumps(identifier)+");if(!el)return;if(typeof Chart==='undefined'){document.getElementById(el.id+'-notice').hidden=false;el.hidden=true;return;}new Chart(el,{data:"+payload+",options:{locale:'pt-BR',animation:false,responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{position:'bottom'},tooltip:{callbacks:{label:function(c){if(c.dataset.isFull)return c.dataset.label;if(c.dataset.isEvent)return c.raw&&c.raw.note||'Mudança detectada';return c.dataset.label+': '+c.formattedValue;}}}},scales:{x:{ticks:{callback:function(v){var s=this.getLabelForValue(v);return s.slice(8)+'/'+s.slice(5,7);}}},sales:{beginAtZero:true,position:'left',title:{display:true,text:'Vendas (R$)'}},extra:{display:"+('false' if mode=='nenhum' else 'true')+",beginAtZero:true,position:'right',grid:{drawOnChartArea:false},title:{display:true,text:"+json.dumps('Preço observado (R$)' if mode=='preco' else 'Visitas')+"}},markers:{display:false,min:0,max:1.3}}}})})();</script>"
    out+='<p class="timeline-meta">Posição dos marcadores Full serve apenas para visualizar o estado. A marca de preço mostra a última mudança detectada no dia, não o horário exato da alteração. Dados ausentes permanecem como lacunas.</p>'
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
    out+='</tbody></table></div></details><nav class="timeline-pages" aria-label="Paginação dos dados da linha do tempo">Dados diários · Página %s de %s' % (page,pages)
    for label,n in [('Anterior',page-1),('Próxima',page+1)]:
        if 1<=n<=pages:
            params=dict(args);params['pagina_linha']=n
            out+=" <a class='filtro' href='?%s'>%s</a>" % (escape(urlencode(params),quote=True),label)
    return out+'</nav></section>'
