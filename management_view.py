"""Decision-focused store report: evidence, priority, action, and drill-down links."""
from datetime import datetime
from decimal import Decimal
from html import escape
from urllib.parse import urlencode

from sales_metrics import SAO_PAULO, change
from sales_view import fmt

KINDS={'':'Todas as áreas','vendas':'Vendas','estoque':'Estoque','status':'Status',
       'margem':'Rentabilidade','qualidade':'Qualidade','dados':'Dados'}
PRIORITIES={'':'Todas as prioridades','alta':'Alta','media':'Média','oportunidade':'Oportunidade','dados':'Validar dados'}
VIEWS={'todos':'Todos os anúncios','campeoes':'Mais vendidos em valor','alta':'Em alta em pedidos',
       'queda':'Em queda em pedidos','sem_vendas':'Sem vendas no período','estoque':'Estoque até 7 dias',
       'sem_custo':'Vendidos sem custo cadastrado'}
STYLE="""<style>
.mgmt-header{display:flex;justify-content:space-between;align-items:start;gap:16px;flex-wrap:wrap}
.mgmt-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}
.mgmt-kpis .stat{min-width:0;padding:16px}.mgmt-kpis .num{font-size:23px;overflow-wrap:anywhere}
.mgmt-kpis small,.mgmt-table small{display:block;font-size:12px;color:#64748b;margin-top:5px}
.mgmt-filter{display:flex;gap:12px;align-items:end;flex-wrap:wrap}.mgmt-filter label{display:grid;gap:5px;font-size:12px}
.mgmt-filter input,.mgmt-filter select{max-width:100%;box-sizing:border-box}
.mgmt-links{display:flex;flex-wrap:wrap;gap:9px;margin:12px 0}
.mgmt-table{width:100%;min-width:850px}.mgmt-table td{vertical-align:top;white-space:normal}
.mgmt-table td:first-child{max-width:320px}.mgmt-scroll{overflow-x:auto}
.mgmt-pill{display:inline-block;padding:4px 9px;border-radius:6px;font-size:11px;font-weight:700;background:#e9eef9;color:#334155}
.mgmt-high{background:#fff0eb;color:#9a3412}.mgmt-medium{background:#fff9df;color:#854d0e}
.mgmt-pager{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:14px}
.mgmt-small-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
@media(max-width:1050px){.mgmt-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){.mgmt-small-grid{grid-template-columns:1fr}.mgmt-kpis .stat{padding:12px}.mgmt-kpis .num{font-size:19px}.mgmt-filter label{flex:1;min-width:130px}}
</style>"""


def number(value,digits=1,suffix=''):
    return 'Indisponível' if value is None else f'{value:,.{digits}f}'.replace(',','x').replace('.',',').replace('x','.')+suffix


def compare(current, previous, money=False):
    delta=change(current,previous)
    text='Sem base de comparação' if delta is None else ('+' if delta>0 else '')+number(delta,1,'%')
    return 'Anterior: '+fmt(previous,money)+' · '+text


def card(label,value,note):
    return "<div class='stat'><div class='lab'>"+escape(label)+"</div><div class='num'>"+escape(value)+"</div><small>"+escape(note)+"</small></div>"


def select(name,options,value):
    return "<select name='"+name+"'>"+''.join("<option value='"+escape(k,quote=True)+"'"+(' selected' if k==value else '')+'>'+escape(v)+'</option>' for k,v in options.items())+'</select>'


def hidden(args, exclude):
    return ''.join("<input type='hidden' name='"+escape(k,quote=True)+"' value='"+escape(v,quote=True)+"'>" for k,v in args.items() if k not in exclude)


def pagination(rows,args,key,path):
    try:
        size=int(args.get('por_pagina','25'))
        size=size if size in (25,50,100) else 25
        page=max(1,int(args.get(key,'1')))
    except (TypeError,ValueError):
        size,page=25,1
    total=len(rows)
    pages=max(1,(total+size-1)//size)
    page=min(page,pages)
    def link(n,label):
        params=dict(args);params[key]=str(n)
        return "<a class='btn-acoes cinza' href='"+escape(path+'?'+urlencode(params),quote=True)+"'>"+label+'</a>'
    controls=("<div class='mgmt-pager'>"+(link(page-1,'← Anterior') if page>1 else '')
              +f'<span>Página {page} de {pages} · {total} registros</span>'
              +(link(page+1,'Próxima →') if page<pages else '')+'</div>')
    return rows[(page-1)*size:page*size],controls


def render_management(cid,report,args):
    start,end,previous_start,previous_end=report['bounds']
    path=f'/painel/{cid}'
    period_params={'dias':args.get('dias','7')}
    period_params.update({key:args[key] for key in ('inicio','fim') if args.get(key)})
    sales_url=f'/vendas/{cid}?'+urlencode({'periodo':'personalizado','inicio':start.isoformat(),'fim':end.isoformat()})
    ads_url=f'/ads/{cid}?'+urlencode({'de':start.isoformat(),'ate':end.isoformat()})
    body=STYLE+"<header class='mgmt-header'><div><h2>Gestão da loja</h2><p>Vendas, publicidade e prioridades para decidir a próxima ação.</p></div>"
    body+=f"<a class='btn-acoes cinza' href='/painel/{cid}/operacao'>Operação do dia →</a></header>"
    body+=("<form class='card mgmt-filter' method='get'><label>Período "+select('dias',{str(n):str(n)+' dias completos' for n in (7,15,30,60,90)},args.get('dias','7'))+'</label>'
           +"<label>Início<input type='date' name='inicio' value='"+escape(args.get('inicio',''),quote=True)+"'></label>"
           +"<label>Fim<input type='date' name='fim' value='"+escape(args.get('fim',''),quote=True)+"'></label>"
           +"<button class='btn-acoes'>Aplicar período</button><a href='"+path+"'>Últimos 7 dias completos</a></form>"
           +'<p class="muted">'+start.strftime('%d/%m/%Y')+' a '+end.strftime('%d/%m/%Y')+' · comparado a '
           +previous_start.strftime('%d/%m/%Y')+' a '+previous_end.strftime('%d/%m/%Y')
           +'. Datas em Brasília. As datas preenchidas prevalecem sobre o seletor de dias.</p>')
    if report['warnings']:
        body+="<div class='aviso'><b>Disponibilidade dos indicadores</b><ul>"+''.join('<li>'+escape(x)+'</li>' for x in report['warnings'])+'</ul></div>'
    current,previous=report['current'],report['previous']
    body+="<section aria-label='Indicadores de vendas'><div class='mgmt-kpis'>"
    for key,label,is_money in [('revenue','Faturamento de pedidos pagos',True),('orders','Pedidos pagos',False),('units','Unidades vendidas',False),('ticket','Ticket médio por pedido',True)]:
        body+=card(label,fmt(current[key],is_money),compare(current[key],previous[key],is_money))
    body+='</div></section>'
    body+='<p class="muted">Cancelamentos registrados: '+fmt(current['cancellations'],False)+' · anterior: '+fmt(previous['cancellations'],False)+'. Não são subtraídos novamente das vendas pagas.</p>'
    ad,before=report['ads'],report['ads_previous']
    body+="<section aria-label='Indicadores de publicidade'><div class='mgmt-kpis'>"
    body+=card('Investimento em Ads',fmt(ad['spend'],True),compare(ad['spend'],before['spend'],True))
    body+=card('ROAS entregue',number(ad['roas'],2,'x'),'Receita atribuída ao Ads ÷ investimento')
    body+=card('ACOS',number(ad['acos'],1,'%'),'Investimento ÷ receita atribuída ao Ads')
    body+=card('TACOS da loja',number(report['tacos'],1,'%'),'Investimento em Ads ÷ faturamento total do mesmo período')
    body+='</div></section>'
    body+='<p class="muted">Publicidade no período · impressões: '+fmt(ad['impressions'],False)+' · cliques: '+fmt(ad['clicks'],False)+' · CTR: '+number(ad['ctr'],2,'%')+'.</p>'
    if ad['coverage']<ad['expected']:
        body+=f"<p class='muted'>Ads: {ad['coverage']} de {ad['expected']} dias com registros. Totais incompletos ficam indisponíveis.</p>"
    body+="<nav class='mgmt-links' aria-label='Análises detalhadas'>"+''.join("<a class='btn-acoes cinza' href='"+escape(url,quote=True)+"'>"+label+'</a>' for url,label in [(sales_url,'Analisar vendas'),(ads_url,'Ads e alertas de campanhas'),(f'/anuncios/{cid}/concorrencia','Concorrência'),(f'/custos/{cid}','Custos e margens'),(f'/full/{cid}','Full e vendas')])+'</nav>'
    body+="<section class='card'><h2>Catálogo, tráfego e rentabilidade</h2><div class='mgmt-kpis'>"
    body+=card('Anúncios com vendas',fmt(report['selling'],False),f"Entre {report['listing_count']} anúncios cadastrados")
    body+=card('Sem vendas no período',fmt(report['no_sales'],False),'Ausência de vendas não comprova falta de demanda')
    visit_value=(fmt(report['visits'],False) if any(r['visits_days'] for r in report['rows']) else 'Aguardando coleta')
    body+=card('Visitas coletadas',visit_value,f"{report['visits_complete']}/{report['listing_count']} anúncios com todos os dias; a soma pode ser parcial")
    body+=card('Receita de itens com custo',number(report['cost_coverage'],1,'%'),'Cobertura de cadastro, não margem de lucro')
    body+='</div>'
    body+=('<p>Maior anúncio: <b>'+number(report['top_share'],1,'%')+'</b> do valor dos itens cadastrados vendidos. '
           'Vendidos sem custo cadastrado: <b>'+fmt(report['missing_cost_count'],False)+'</b>. '
           'Perguntas sem resposta nos registros sincronizados: <b>'+str(report['questions'])+'</b>.</p>')
    body+='<details><summary>Como interpretar os dados</summary><p>Faturamento usa pedidos pagos e aprovados em reais. '
    body+='O ranking por anúncio usa valor bruto dos itens; frete e cupons do pedido não são rateados. '
    body+='Visitas só geram pedidos por 100 visitas quando todos os dias do anúncio estão presentes. '
    body+='Cobertura de estoque é uma estimativa pelo ritmo de unidades vendidas, sem garantir demanda futura. '
    body+='Custos atuais não comprovam lucro histórico; taxas, frete e Ads precisam entrar na análise de margem. '
    body+='Preço competitivo, posição no catálogo e causa das quedas exigem investigação; não são inferidos destes números.</p></details></section>'
    if report['champions']:
        body+="<section class='card'><h2>Campeões de vendas em valor</h2><ol>"
        for row in report['champions']:
            listing,m=row['listing'],row['metrics']
            body+=f"<li><a href='/diagnostico/{cid}/{escape(listing['item_id'],quote=True)}'>"+escape(listing.get('titulo') or listing['item_id'])+'</a> · '+fmt(m['value'],True)+f" · {m['orders']} pedidos</li>"
        body+='</ol></section>'
    signals=report['signals']
    q=args.get('busca','').strip().casefold()[:200]
    area=args.get('area','')
    priority=args.get('prioridade','')
    filtered=[s for s in signals if (not area or s['kind']==area) and (not priority or s['priority']==priority)
              and (not q or q in (s['label']+' '+s['item_id']+' '+s['title']).casefold())]
    page_rows,pager=pagination(filtered,args,'pagina_acoes',path)
    body+=("<section class='card' id='oportunidades'><h2>Central de Oportunidades</h2><p>"
           +str(len(signals))+" sinais organizados por prioridade. Evidências e verificações sugeridas; causas não confirmadas.</p>"
           +"<form method='get' class='mgmt-filter'>"+hidden(args,{'area','prioridade','busca','por_pagina','pagina_acoes','pagina_anuncios'})
           +'<label>Área'+select('area',KINDS,area)+'</label><label>Prioridade'+select('prioridade',PRIORITIES,priority)+'</label>'
           +"<label>Buscar anúncio<input name='busca' maxlength='200' value='"+escape(args.get('busca','')[:200],quote=True)+"'></label>"
           +'<label>Por página'+select('por_pagina',{str(n):str(n) for n in (25,50,100)},args.get('por_pagina','25'))+'</label>'
           +"<button class='btn-acoes'>Filtrar oportunidades</button></form>"
           +"<div class='mgmt-scroll'><table class='mgmt-table'><thead><tr><th>Anúncio</th><th>Prioridade</th><th>O que foi identificado</th><th>Evidência</th><th>Próxima ação</th></tr></thead><tbody>")
    for signal in page_rows:
        url=signal['path'].format(cid=cid)
        badge='mgmt-high' if signal['priority']=='alta' else ('mgmt-medium' if signal['priority']=='media' else '')
        body+=('<tr><td>'+escape(signal['label'])+'<small>'+escape(signal['item_id'])+'</small></td><td>'
               +"<span class='mgmt-pill "+badge+"'>"+PRIORITIES[signal['priority']]+'</span></td><td>'+escape(signal['title'])
               +'</td><td>'+escape(signal['evidence'])+'</td><td>'+escape(signal['action'])
               +"<br><a href='"+escape(url,quote=True)+"'>Investigar →</a></td></tr>")
    if not page_rows:
        text='Nenhum sinal para estes filtros.' if signals else 'Nenhum sinal confirmado com os dados disponíveis; confira a cobertura acima.'
        body+="<tr><td colspan='5'>"+text+'</td></tr>'
    body+='</tbody></table></div>'+pager+'</section>'
    view=args.get('visao','todos')
    rows=list(report['rows'])
    if q:
        rows=[r for r in rows if q in ((r['listing'].get('titulo') or '')+' '+r['listing']['item_id']).casefold()]
    if view=='alta': rows=[r for r in rows if r['metrics'] and r['metrics']['orders']>r['metrics']['previous_orders'] and r['metrics']['previous_orders']>0]
    elif view=='queda': rows=[r for r in rows if r['metrics'] and r['metrics']['orders']<r['metrics']['previous_orders']]
    elif view=='sem_vendas': rows=[r for r in rows if r['metrics'] and r['metrics']['orders']==0]
    elif view=='estoque': rows=[r for r in rows if r['stock_days'] is not None and r['stock_days']<=7]
    elif view=='sem_custo':
        from sales_metrics import amount
        rows=[r for r in rows if r['metrics'] and r['metrics']['orders'] and not amount(r['listing'].get('custo'))]
    rows.sort(key=lambda r:(-(r['metrics']['value'] if r['metrics'] else 0),r['listing']['item_id']))
    page_rows,pager=pagination(rows,args,'pagina_anuncios',path)
    body+=("<section class='card'><h2>Análise por anúncio</h2><form method='get' class='mgmt-filter'>"
           +hidden(args,{'visao','pagina_anuncios','busca','por_pagina'})+'<label>Visualização'+select('visao',VIEWS,view)+'</label>'
           +"<label>Buscar anúncio<input name='busca' maxlength='200' value='"+escape(args.get('busca','')[:200],quote=True)+"'></label>"
           +'<label>Por página'+select('por_pagina',{str(n):str(n) for n in (25,50,100)},args.get('por_pagina','25'))+'</label>'
           +"<button class='btn-acoes'>Aplicar visualização</button></form>"
           +"<div class='mgmt-scroll'><table class='mgmt-table'><thead><tr><th>Anúncio</th><th>Pedidos atual / anterior</th><th>Valor dos itens atual / anterior</th><th>Unidades</th><th>Visitas / pedidos por 100 visitas</th><th>Estoque / cobertura</th></tr></thead><tbody>")
    for row in page_rows:
        listing,m=row['listing'],row['metrics']
        body+=(f"<tr><td><a href='/diagnostico/{cid}/{escape(listing['item_id'],quote=True)}'>"+escape(listing.get('titulo') or listing['item_id'])+'</a><small>'
               +escape(listing['item_id'])+' · '+escape(listing.get('status') or 'status não confirmado')+'</small></td><td>'
               +(str(m['orders'])+' / '+str(m['previous_orders'])+'<small>'+number(m['growth_pct'],1,'%')+'</small>' if m else 'Indisponível')
               +'</td><td>'+(fmt(m['value'],True)+'<small>Antes: '+fmt(m['previous_value'],True)+'</small>' if m else 'Indisponível')
               +'</td><td>'+(str(m['units']) if m else 'Indisponível')+'</td><td>'+fmt(row['visits'],False)
               +'<small>'+number(row['ratio'],2)+' pedidos / 100 visitas</small></td><td>'
               +(str(int(row['stock'])) if row['stock'] is not None else 'Não confirmado')
               +'<small>'+number(row['stock_days'],1,' dias estimados')+(' · leitura antiga' if not row['fresh'] else '')+'</small></td></tr>')
    if not page_rows:
        body+="<tr><td colspan='6'>Nenhum anúncio disponível para esta visualização.</td></tr>"
    body+='</tbody></table></div>'+pager+'</section>'
    body+='<p class="muted">Status e estoque: leitura mais antiga dos anúncios em '
    body+=(datetime.fromtimestamp(report['last_catalogue'],SAO_PAULO).strftime('%d/%m/%Y %H:%M') if report['last_catalogue'] else 'data não confirmada')+'.</p>'
    body+="""<div id='mgmt-loading' role='status' aria-live='polite' hidden>Atualizando a análise da loja…</div>
    <style>#mgmt-loading:not([hidden]){position:fixed;bottom:20px;right:20px;max-width:calc(100vw - 60px);padding:16px;background:#173b66;color:white;border-radius:10px;z-index:20}</style>
    <script>document.querySelectorAll('form.mgmt-filter').forEach(function(form){
      form.addEventListener('submit',function(event){
        if(form.getAttribute('aria-busy')==='true'){event.preventDefault();return;}
        if(!form.checkValidity())return;
        form.setAttribute('aria-busy','true');document.getElementById('mgmt-loading').hidden=false;
      });
    });window.addEventListener('pageshow',function(){
      document.getElementById('mgmt-loading').hidden=true;
      document.querySelectorAll('form.mgmt-filter').forEach(function(form){form.removeAttribute('aria-busy');});
    });</script>"""
    return body
