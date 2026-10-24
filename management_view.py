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
from management_design import STYLE, SCRIPT as DESIGN_SCRIPT, metric_card, active_tab, panel, tabs, daily_chart, priorities, product, product_details



def number(value,digits=1,suffix=''):
    return 'Indisponível' if value is None else f'{value:,.{digits}f}'.replace(',','x').replace('.',',').replace('x','.')+suffix


def compare(current, previous, money=False):
    delta=change(current,previous)
    text='Sem base de comparação' if delta is None else ('+' if delta>0 else '')+number(delta,1,'%')
    return 'Anterior: '+fmt(previous,money)+' · '+text


def card(label,value,note):
    return metric_card(label,value,note)


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
    selected=active_tab(args)
    period_params={'dias':args.get('dias','7')}
    period_params.update({key:args[key] for key in ('inicio','fim') if args.get(key)})
    sales_url=f'/vendas/{cid}?'+urlencode({'periodo':'personalizado','inicio':start.isoformat(),'fim':end.isoformat()})
    ads_url=f'/ads/{cid}?'+urlencode({'de':start.isoformat(),'ate':end.isoformat()})
    body=STYLE+"<div class='mgmt-dashboard'><header class='mgmt-header'><div><span class='mgmt-eyebrow'>Visão de performance</span><h2>"+escape(report['shop']['cliente'])+"</h2><p>Acompanhe os resultados. Escolha o próximo passo.</p></div>"
    body+=f"<div class='mgmt-links'><a class='btn-acoes' href='/atualizar/resumo/{cid}'>Atualizar dados</a><a class='btn-acoes cinza' href='/painel/{cid}/operacao'>Operação do dia →</a></div></header>"
    if report.get('updating'):
        body+="<div class='aviso' role='status'>Sincronização em andamento. Os indicadores mostram a última leitura disponível; recarregue esta página após a conclusão.</div>"
    body+=("<form class='card mgmt-filter mgmt-period' method='get'><label>Período "+select('dias',{str(n):str(n)+' dias completos' for n in (7,15,30,60,90)},args.get('dias','7'))+'</label>'
           +"<details class='mgmt-period-dates'"+(' open' if args.get('inicio') or args.get('fim') else '')+"><summary>Período personalizado</summary><label>Início<input type='date' name='inicio' value='"+escape(args.get('inicio',''),quote=True)+"'></label>"
           +"<label>Fim<input type='date' name='fim' value='"+escape(args.get('fim',''),quote=True)+"'></label>"
           +"</details><button class='btn-acoes'>Aplicar período</button><a href='"+path+"'>Últimos 7 dias completos</a></form>"
           +'<p class="muted">'+start.strftime('%d/%m/%Y')+' a '+end.strftime('%d/%m/%Y')+' · comparado a '
           +previous_start.strftime('%d/%m/%Y')+' a '+previous_end.strftime('%d/%m/%Y')
           +'. Horário de Brasília.</p>')
    if report['warnings']:
        body+="<details class='mgmt-notice'><summary>Alguns indicadores aguardam dados · "+str(len(report['warnings']))+" observações</summary><ul>"+''.join('<li>'+escape(x)+'</li>' for x in report['warnings'])+'</ul></details>'
    body+=tabs(cid,args,len(report['signals']),selected)+panel('overview',selected)
    current,previous=report['current'],report['previous']
    body+="<section aria-label='Indicadores de vendas'><div class='mgmt-kpis'>"
    for key,label,is_money in [('revenue','Faturamento de pedidos pagos',True),('orders','Pedidos pagos',False),('units','Unidades vendidas',False),('ticket','Ticket médio por pedido',True)]:
        body+=card(label,fmt(current[key],is_money),compare(current[key],previous[key],is_money))
    body+='</div></section>'
    body+='<p class="muted">Cancelamentos registrados: '+fmt(current['cancellations'],False)+' · anterior: '+fmt(previous['cancellations'],False)+'. Não são subtraídos novamente das vendas pagas.</p>'
    body+=daily_chart(report)
    ad,before=report['ads'],report['ads_previous']
    body+="<section class='mgmt-ads-strip' aria-label='Indicadores de publicidade'><div class='mgmt-kpis'>"
    body+=card('Investimento em Ads',fmt(ad['spend'],True),compare(ad['spend'],before['spend'],True))
    body+=card('ROAS entregue',number(ad['roas'],2,'x'),'Receita atribuída ao Ads ÷ investimento')
    body+=card('ACOS',number(ad['acos'],1,'%'),'Investimento ÷ receita atribuída ao Ads')
    body+=card('TACOS da loja',number(report['tacos'],1,'%'),'Investimento em Ads ÷ faturamento total do mesmo período')
    body+='</div></section>'
    body+='<p class="muted">Publicidade no período · impressões: '+fmt(ad['impressions'],False)+' · cliques: '+fmt(ad['clicks'],False)+' · CTR: '+number(ad['ctr'],2,'%')+'.</p>'
    if ad['coverage']<ad['expected']:
        missing=ad.get('missing_dates',[])
        dates=', '.join(datetime.strptime(day,'%Y-%m-%d').strftime('%d/%m') for day in missing[:10])
        if len(missing)>10:
            dates+=f' e mais {len(missing)-10}'
        body+=("<div class='mgmt-notice' role='status'><b>Publicidade: histórico incompleto</b>"
               +f"<p>Dados coletados em {ad['coverage']} de {ad['expected']} dias. "
               +"Faltam: "+escape(dates)+". Investimento, ROAS, ACOS e TACOS "
               +"aguardam a recuperação automática; não tratamos lacunas como gasto zero.</p>"
               +f"<a class='btn-acoes cinza' href='/ads/{int(cid)}'>Sincronizar Ads agora</a></div>")
    body+="<nav class='mgmt-links' aria-label='Análises detalhadas'>"+''.join("<a class='btn-acoes cinza' href='"+escape(url,quote=True)+"'>"+label+'</a>' for url,label in [(sales_url,'Analisar vendas'),(ads_url,'Ads e alertas de campanhas'),(f'/anuncios/{cid}/concorrencia','Concorrência'),(f'/custos/{cid}','Custos e margens'),(f'/full/{cid}','Full e vendas')])+'</nav>'
    body+=priorities(cid,report,args)
    # The current store home is /painel/<cid>; the legacy /operacao page is
    # different. Load verified item priorities after the visible dashboard.
    # Do not block KPI rendering on the more expensive ranking calculation.
    priority_url=f'/ranking-anuncios/{int(cid)}?dias=7&modo=prioridades'
    body+=("<section id='mgmt-auto-priorities' aria-label='Anúncios prioritários' "
           "data-priority-url='"+escape(priority_url,quote=True)+"'>"
           "<div class='card'><h2>Anúncios que precisam de atenção</h2>"
           "<p class='muted'>Verificando as quedas de faturamento dos anúncios…</p>"
           "</div></section>")
    body+="""<script>
    (function(){
      var section=document.getElementById('mgmt-auto-priorities');
      if(!section)return;
      var url=section.getAttribute('data-priority-url');
      fetch(url,{credentials:'same-origin'})
        .then(function(response){
          if(!response.ok)throw new Error('priority-load');
          return response.text();
        }).then(function(html){
          if(section)section.innerHTML=html;
        }).catch(function(){
          if(section){
            section.textContent='';
            var error=document.createElement('p');
            error.className='muted';
            error.textContent='Não foi possível carregar as prioridades. Consulte o ranking dos anúncios.';
            var link=document.createElement('a');
            link.href=url.split('?')[0];
            link.textContent='Abrir ranking de anúncios →';
            section.appendChild(error);
            section.appendChild(link);
          }
        });
    })();
    </script>"""
    body+="<div class='mgmt-overview-bottom'><section class='card mgmt-catalog'><h2>Saúde do catálogo</h2><div class='mgmt-kpis'>"
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
        body+="<section class='card mgmt-leaders'><h2>Campeões de vendas em valor</h2><ol>"
        for row in report['champions']:
            listing,m=row['listing'],row['metrics']
            body+="<li>"+product(row,cid)+fmt(m["value"],True)+f" · {m['orders']} pedidos</li>"
        body+='</ol></section>'
    body+='</div></div>'+panel('actions',selected)
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
    body+='</div>'+panel('analysis',selected)
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
        body+=("<tr><td>"+product(row,cid)+'<small>'
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
    body+='</div>'
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
    return body+product_details(cid,dict(report,rows=list({r["listing"]["item_id"]:r for r in report["champions"]+page_rows}.values())))+DESIGN_SCRIPT+'</div>'
