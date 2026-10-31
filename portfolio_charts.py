"""Portfolio charts rendered from already qualified daily series."""
from decimal import Decimal
from html import escape
from portfolio_view import money,help_tip


def aggregate(rows,key,count):
    return [sum((Decimal(str(r[key][i])) for r in rows),Decimal(0)) if rows and all(r.get(key) is not None and len(r[key])>i and r[key][i] is not None for r in rows) else None for i in range(count)]


def chart(rows,key,days,title):
    values=aggregate(rows,key,len(days))
    prior=aggregate(rows,'previous_daily_sales',len(days)) if key=='daily_sales' else [None]*len(days)
    maximum=max([v for v in values+prior if v is not None]+[Decimal(1)])
    esc=lambda x:escape(str(x),quote=True)
    out='<section class="pf-card portfolio-chart"><h3>'+esc(title)+help_tip(title,'Uma coluna por dia. Toque ou use o seletor para consultar os valores. A linha tracejada compara os dias correspondentes do período anterior de igual duração. Dados incompletos ficam indisponíveis.')+'</h3>'
    out+='<div class="portfolio-chart-legend"><span>● Período selecionado</span>'+('<span>┄ Período anterior</span>' if key=='daily_sales' else '')+'</div><svg viewBox="0 0 760 230" role="img" aria-label="'+esc(title)+'">'
    for fraction in (0,.5,1):
        y=180-fraction*150
        out+=f'<line x1="80" y1="{y}" x2="750" y2="{y}" stroke="#7892aa" opacity=".3"/><text x="72" y="{y+4}" text-anchor="end" fill="currentColor" font-size="11">{esc(money(maximum*Decimal(str(fraction))))}</text>'
    step=670/len(days)
    # A missing value breaks the line, never interpolates through unknown data.
    for i in range(1,len(days)):
        if prior[i-1] is not None and prior[i] is not None:
            out+=f'<line x1="{80+(i-.5)*step}" y1="{180-float(prior[i-1]/maximum)*150}" x2="{80+(i+.5)*step}" y2="{180-float(prior[i]/maximum)*150}" stroke="#c08d54" stroke-width="2" stroke-dasharray="5 4"/>'
    for i,(day,value) in enumerate(zip(days,values)):
        x=80+i*step;height=0 if value is None else float(value/maximum)*150
        label=day[8:10]+'/'+day[5:7]+' · '+money(value)
        if key=='daily_sales':label+=' · Anterior: '+money(prior[i])
        out+=f'<g class="portfolio-day" data-index="{i}" data-label="{esc(label)}"><rect x="{x}" y="20" width="{step}" height="165" fill="transparent"/>'
        if value is not None:out+=f'<rect x="{x+step*.15}" y="{180-max(height,1)}" width="{step*.7}" height="{max(height,1)}" fill="#4a9ccc"/>'
        else:out+=f'<text x="{x+step*.5}" y="175" text-anchor="middle" fill="currentColor">?</text>'
        out+='<title>'+esc(label)+'</title></g>'
    out+='<text x="80" y="214" fill="currentColor" font-size="12">'+esc(days[0][8:10]+'/'+days[0][5:7])+'</text><text x="750" y="214" text-anchor="end" fill="currentColor" font-size="12">'+esc(days[-1][8:10]+'/'+days[-1][5:7])+'</text></svg>'
    out+='<label class="portfolio-day-picker">Consultar dia<input type="range" min="0" max="'+str(len(days)-1)+'" value="0" aria-label="Dia em '+esc(title)+'"></label><output aria-live="polite">'+esc(days[0][8:10]+'/'+days[0][5:7]+' · '+money(values[0])+(' · Anterior: '+money(prior[0]) if key=='daily_sales' else ''))+'</output></section>'
    return out


SCRIPT='''<style>.portfolio-chart-legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12px}.portfolio-chart output{display:block;min-height:2.8em;margin-top:10px;font-weight:600;overflow-wrap:anywhere}.portfolio-day-picker{display:flex;align-items:center;gap:12px;font-size:13px}.portfolio-day-picker input{flex:1;min-width:0;accent-color:#4a9ccc}.portfolio-day{cursor:pointer}.portfolio-day:hover{opacity:.7}.portfolio-day.is-selected rect:last-of-type{stroke:currentColor;stroke-width:1}</style><script>document.querySelectorAll('.portfolio-chart').forEach(card=>{const slider=card.querySelector('input[type=range]'),out=card.querySelector('output'),days=card.querySelectorAll('.portfolio-day');function select(i){days.forEach(d=>d.classList.toggle('is-selected',Number(d.dataset.index)===i));slider.value=i;out.textContent=days[i].dataset.label;slider.setAttribute('aria-valuetext',days[i].dataset.label)}slider.addEventListener('input',()=>select(Number(slider.value)));days.forEach((d,i)=>{d.addEventListener('pointerenter',()=>select(i));d.addEventListener('click',()=>select(i))});select(0)});</script>'''
