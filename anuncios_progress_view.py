"""A single, read-only evolution chart; no lists or external links."""
from datetime import date
from html import escape

COLORS={'concluida':'#69d6b5','parcial':'#f2bf68','pendente':'#849bb8','em_andamento':'#65b4ff','bloqueada':'#ed929e'}
LABELS={'concluida':'Concluídas','parcial':'Parciais','pendente':'Pendentes','em_andamento':'Em desenvolvimento','bloqueada':'Bloqueadas'}


def render(data,model):
    esc=lambda v:escape(str(v),quote=True)
    original=data['lista_original_completa']
    total=model['total'];done=model['counts'].get('concluida',0)
    out=STYLE+"<main class='ap-progress'><header><span class='ap-eyebrow'>Anúncios 2.0</span><h2>Evolução das melhorias</h2><p>Atualizado junto das publicações do sistema.</p></header><section class='ap-chart-card' aria-label='Gráfico de evolução das melhorias'>"
    out+='<div class="ap-chart-head"><div><strong>'+str(done)+'</strong><span>'+('melhorias da lista original concluídas' if original else 'frentes auditadas concluídas')+'</span><small>'+str(total)+(' melhorias mapeadas' if original else ' frentes identificadas')+'</small></div><p>Última medição<br><b>'+date.fromisoformat(data['historico'][-1]['data']).strftime('%d/%m/%Y')+'</b></p></div>'
    if not original:
        out+='<p class="ap-scope">Meta original: 90 sugestões. A contagem das 90 está em consolidação; este gráfico acompanha as '+str(total)+' frentes identificadas.</p>'
    records=[event for event in data['historico'] if event['base']==model['base']][-12:]
    ceiling=max([total,1]+[event['total'] for event in records])
    left,right,top,bottom=64,716,28,270
    chart='<svg viewBox="0 0 760 365" role="img" aria-labelledby="ap-chart-title ap-chart-desc"><title id="ap-chart-title">Evolução das frentes concluídas</title><desc id="ap-chart-desc">'+str(done)+' de '+str(total)+' frentes auditadas concluídas. '+('Primeira medição; o histórico começa nesta publicação.' if len(records)==1 else 'Cada ponto é uma medição registrada numa publicação.')+'</desc>'
    for step in range(5):
        value=ceiling*step/4;y=bottom-(bottom-top)*step/4
        chart+='<line x1="'+str(left)+'" y1="'+str(y)+'" x2="'+str(right)+'" y2="'+str(y)+'" stroke="#304760"/><text x="50" y="'+str(y+5)+'" text-anchor="end">'+str(round(value))+'</text>'
    coords=[]
    for index,event in enumerate(records):
        x=(left+right)/2 if len(records)==1 else left+(right-left)*index/(len(records)-1)
        value=event['contagens'].get('concluida',0);y=bottom-(bottom-top)*value/ceiling
        coords.append((x,y,value,event))
    if len(coords)>1:
        chart+='<polyline points="'+' '.join(str(x)+','+str(y) for x,y,_,_ in coords)+'" fill="none" stroke="#69d6b5" stroke-width="4"/>'
    for index,(x,y,value,event) in enumerate(coords):
        label=date.fromisoformat(event['data']).strftime('%d/%m')
        chart+='<circle cx="'+str(x)+'" cy="'+str(y)+'" r="7" fill="#69d6b5" stroke="#0e2035" stroke-width="3"><title>'+esc(label+': '+str(value)+' concluídas. '+event['resumo'])+'</title></circle><text class="ap-value" x="'+str(x)+'" y="'+str(max(top,y-18))+'" text-anchor="middle">'+str(value)+'</text>'
        if len(coords)<=6 or index in (0,len(coords)-1):chart+='<text x="'+str(x)+'" y="299" text-anchor="middle">'+label+'</text>'
    chart+='<text x="390" y="350" text-anchor="middle">Publicações registradas</text></svg>'
    out+='<div class="ap-chart">'+chart+'</div><div class="ap-legend" aria-label="Situação atual">'
    for code in ('concluida','em_andamento','parcial','pendente','bloqueada'):
        n=model['counts'].get(code,0)
        if not n and code not in ('concluida','parcial','pendente'):continue
        out+='<span><i style="background:'+COLORS[code]+'" aria-hidden="true"></i>'+LABELS[code]+': <b>'+str(n)+'</b></span>'
    out+='</div>'
    if len(records)==1:out+='<p class="ap-footnote">Primeira medição. As próximas publicações formarão o histórico de evolução.</p>'
    return out+'</section></main>'


STYLE='''<style>
body:has(.ap-progress){background:#0b1426;color:#eaf2ff;color-scheme:dark}body:has(.ap-progress) .top{background:#0d192d;border-bottom:1px solid #34516e}body:has(.ap-progress) .top :is(h1,.brand){color:#eaf2ff}body:has(.ap-progress) .top .btn{background:#244a80;color:#fff;border-color:#426184}body:has(.ap-progress) .wrap{max-width:1200px}.ap-progress{min-width:0;max-width:100%;padding:12px 0 30px;color:#eaf2ff}.ap-progress h2{color:#eaf2ff;font-size:27px;margin:10px 0}.ap-progress p{color:#bdcce1;font-size:13px;line-height:1.7}.ap-eyebrow{font-size:12px;color:#a4d9ff}.ap-chart-card{background:#102238;border:1px solid #34516e;border-radius:16px;padding:24px;margin-top:24px;max-width:100%;box-sizing:border-box}.ap-chart-head{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}.ap-chart-head div{display:grid;gap:6px}.ap-chart-head strong{font-size:42px;color:#69d6b5}.ap-chart-head span{font-size:15px;color:#eaf2ff}.ap-chart-head small{color:#9fb4cf;font-size:12px}.ap-chart-head p{font-size:12px;text-align:right}.ap-scope{background:#182e49;border:1px solid #426184;border-radius:10px;padding:12px 14px}.ap-chart{width:100%;margin:20px 0}.ap-chart svg{width:100%;height:auto;display:block}.ap-chart text{fill:#bdcce1;font-size:17px;font-family:Inter,'Segoe UI',Arial,sans-serif}.ap-chart .ap-value{fill:#b9f5df;font-weight:700;font-size:22px}.ap-legend{display:flex;gap:20px;flex-wrap:wrap;font-size:12px;color:#c5d6eb;padding:14px 0}.ap-legend span{display:flex;align-items:center;gap:7px}.ap-legend i{width:10px;height:10px;display:inline-block;border-radius:3px}.ap-legend b{color:#eaf2ff}.ap-footnote{font-size:12px!important;border-top:1px solid #34516e;padding-top:14px}@media(max-width:700px){.ap-chart-card{padding:16px}.ap-progress h2{font-size:23px}.ap-chart-head strong{font-size:36px}.ap-chart-head p{text-align:left}.ap-chart text{font-size:28px}.ap-chart .ap-value{font-size:32px}.ap-legend{gap:12px}}
</style>'''
