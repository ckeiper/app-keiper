"""Admin portfolio: synchronized, qualified evidence; no marketplace requests."""
from datetime import timedelta
from decimal import Decimal
from html import escape
from flask import request,session
from sales_metrics import reporting_today,amount,change
from overview import load_overview
from overview_cache import load_cached_overview
from profitability_view import CSS


def dates(args,today=None):
    today=today or reporting_today();choice=args.get('periodo','mes')
    if choice=='hoje':start=end=today
    elif choice=='ontem':start=end=today-timedelta(days=1)
    elif choice=='7':end=today;start=end-timedelta(days=6)
    elif choice=='mes':start=today.replace(day=1);end=today
    elif choice=='anterior':end=today.replace(day=1)-timedelta(days=1);start=end.replace(day=1)
    elif choice=='personalizado':
        from datetime import date
        try:start=date.fromisoformat(args.get('inicio',''));end=date.fromisoformat(args.get('fim',''))
        except (ValueError,TypeError):raise ValueError('Informe datas válidas.')
    else:raise ValueError('Período inválido.')
    if start.toordinal()<=(end-start).days+2 or start>end or end>today or (end-start).days>=366:raise ValueError('Selecione até 366 dias, sem datas futuras.')
    return start,end


def combine(data,ads):
    start,end,_,_=data['bounds'];days=[(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
    grouped={}
    for row in ads:grouped.setdefault(row['conexao_id'],{})[row['data']]=row
    rows=[]
    for report in data['reports']:
        shop=report['shop'];records=grouped.get(shop['id'],{});values=[amount(records[d]['gasto']) if d in records else None for d in days]
        spend=sum(values,Decimal(0)) if all(v is not None for v in values) else None
        sales=report['current']['revenue'];previous=report['previous']['revenue']
        rows.append(dict(id=shop['id'],name=shop['cliente'],sales=sales,ads=spend,
            tacos=spend/sales*100 if spend is not None and sales else None,
            change=change(sales,previous),covered=sum(v is not None for v in values),days=len(days),
            sync=min((records[d].get('atualizado_em') or 0 for d in days if d in records),default=None),
            sales_sync=report.get('last_sync'),reasons=report.get('reasons',[]),
            daily_sales=report['current']['daily'],daily_ads=values))
    rows.sort(key=lambda r:(r['name'].casefold(),r['id']))
    totals={k:sum((r[k] for r in rows),Decimal(0)) if rows and all(r[k] is not None for r in rows) else None for k in ('sales','ads')}
    totals['tacos']=totals['ads']/totals['sales']*100 if totals['ads'] is not None and totals['sales'] else None
    return dict(rows=rows,totals=totals,days=days,start=start,end=end)


def money(value):
    return 'Não disponível' if value is None else 'R$ '+f'{value:,.2f}'.replace(',','X').replace('.',',').replace('X','.')


def help_tip(label,text):
    return '<details class="portfolio-help"><summary aria-label="Ajuda: '+escape(label,quote=True)+'">?</summary><span role="tooltip">'+escape(text)+'</span></details>'


def chart(rows,key,days,title):
    values=[sum((Decimal(str(r[key][i])) for r in rows),Decimal(0)) if rows and all(r[key][i] is not None for r in rows) else None for i in range(len(days))]
    ceiling=max([v for v in values if v is not None]+[Decimal(1)])
    out='<section class="pf-card"><h3>'+title+help_tip(title,'Uma coluna por dia. ? indica cobertura incompleta; os valores podem mudar após sincronização.')+'</h3><svg viewBox="0 0 760 190" role="img" aria-label="'+title+' por dia"><line x1="10" y1="155" x2="750" y2="155" stroke="#7892aa"/>'
    for i,(day,value) in enumerate(zip(days,values)):
        x=10+i*740/len(days);width=max(1,740/len(days)*.7)
        if value is None:out+=f'<text x="{x}" y="150" fill="#c08d54" font-size="10">?</text>'
        else:
            height=float(value/ceiling)*130
            out+=f'<rect x="{x}" y="{155-height}" width="{width}" height="{max(height,1)}" fill="#4a9ccc"><title>{day}: {money(value)}</title></rect>'
    out+='<text x="10" y="180" fill="#7892aa" font-size="12">'+days[0]+'</text><text x="750" y="180" text-anchor="end" fill="#7892aa" font-size="12">'+days[-1]+'</text>'
    return out+'</svg></section>'


def render(model,args):
    esc=lambda v:escape(str(v),quote=True)
    out=CSS+'<main class="pf portfolio"><header class="pf-hero"><h2>Visão da Carteira</h2></header><form class="pf-card portfolio-filter" method="get"><label>Período<select name="periodo">'
    for key,label in [('hoje','Hoje'),('ontem','Ontem'),('7','Últimos 7 dias'),('mes','Mês atual'),('anterior','Mês anterior'),('personalizado','Personalizado')]:
        out+='<option value="'+key+'"'+(' selected' if args.get('periodo','mes')==key else '')+'>'+label+'</option>'
    out+='</select></label><label>Início<input type="date" name="inicio" value="'+esc(args.get('inicio',''))+'"></label><label>Fim<input type="date" name="fim" value="'+esc(args.get('fim',''))+'"></label><button>Aplicar</button></form>'
    out+='<section class="pf-card"><div class="pf-grid">'
    for label,value in [('Faturamento acumulado',money(model['totals']['sales'])),('Investimento em Ads',money(model['totals']['ads'])),('TACOS da carteira','Não disponível' if model['totals']['tacos'] is None else f"{model['totals']['tacos']:.2f}%")]:
        out+='<article class="pf-metric"><span>'+label+help_tip(label,{'Faturamento acumulado':'Soma dos pedidos pagos em BRL com pagamento aprovado, no período em Brasília. Não desconta reembolsos.','Investimento em Ads':'Soma dos gastos diários registrados para as lojas no período. Sem duplicar campanhas.','TACOS da carteira':'Gasto total em Ads dividido pelo faturamento total. Não é média dos TACOS das lojas.'}[label])+'</span><strong>'+esc(value)+'</strong></article>'
    n=len(model['rows']);sales_n=sum(r['sales'] is not None for r in model['rows']);ads_n=sum(r['ads'] is not None for r in model['rows'])
    out+='</div></section>'
    out+=chart(model['rows'],'daily_sales',model['days'],'Faturamento diário')+chart(model['rows'],'daily_ads',model['days'],'Investimento diário em Ads')
    out+='<section class="pf-card"><h3>Clientes</h3><div class="portfolio-scroll"><table><thead><tr><th>Cliente</th><th>Faturamento</th><th>Variação'+help_tip('Variação','Compara com o período anterior de igual duração.')+'</th><th>Ads</th><th>TACOS</th><th>Participação'+help_tip('Participação','Faturamento da loja dividido pelo faturamento completo da carteira.')+'</th><th>Cobertura'+help_tip('Cobertura','Dias com registros e datas de leitura. Totais indisponíveis quando faltam dados de alguma loja. O dia atual pode estar em andamento.')+'</th></tr></thead><tbody>'
    from datetime import datetime
    from sales_metrics import SAO_PAULO
    for r in model['rows']:
        pct='Não disponível' if r['change'] is None else f"{r['change']:+.1f}%"
        if r['change'] is not None:pct='<span class="portfolio-change-'+('up' if r['change']>0 else 'down' if r['change']<0 else 'flat')+'">'+pct+'</span>'
        share='Não disponível' if r['sales'] is None or not model['totals']['sales'] else f"{r['sales']/model['totals']['sales']*100:.1f}%"
        sync='Não informada' if not r['sync'] else datetime.fromtimestamp(r['sync'],SAO_PAULO).strftime('%d/%m %H:%M')
        sales_sync='Não informada' if not r['sales_sync'] else datetime.fromtimestamp(r['sales_sync'],SAO_PAULO).strftime('%d/%m %H:%M')
        url='/vendas/'+str(r['id'])+'?periodo=personalizado&amp;inicio='+str(model['start'])+'&amp;fim='+str(model['end'])
        out+='<tr><td><a class="portfolio-client" href="'+url+'">'+esc(r['name'])+'</a></td><td>'+money(r['sales'])+'</td><td>'+pct+'</td><td>'+money(r['ads'])+'</td><td>'+('Não disponível' if r['tacos'] is None else f"{r['tacos']:.2f}%")+'</td><td>'+share+'</td><td>Ads: '+str(r['covered'])+'/'+str(r['days'])+' dias · leitura '+sync+'<br>Vendas: '+sales_sync+'<br>'+esc('; '.join(r['reasons']))+'</td></tr>'
    out+='</tbody></table></div></section></main>'
    return out+'''<style>.portfolio{min-width:0}.portfolio-filter{display:flex;gap:12px;flex-wrap:wrap;align-items:end}.portfolio-filter label{min-width:130px}.portfolio select{display:block;padding:10px;max-width:100%}.portfolio-scroll{overflow-x:auto}.portfolio table{min-width:1000px}.portfolio-client{display:block;padding:12px;border:1px solid #7892aa;border-radius:8px}.portfolio svg{width:100%;height:auto}.portfolio-help{display:inline-block;position:relative;margin-left:7px;vertical-align:middle;font-size:12px;font-weight:400}.portfolio .portfolio-help summary{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:1px solid #7892aa;border-radius:50%;padding:0;cursor:pointer;list-style:none}.portfolio-help summary::-webkit-details-marker{display:none}.portfolio-help [role=tooltip]{display:none;position:absolute;z-index:10;top:24px;right:0;width:210px;max-width:65vw;padding:12px;border:1px solid #7892aa;border-radius:9px;background:#142940;color:#eff5ff!important;white-space:normal;line-height:1.5;box-shadow:0 5px 18px #0004}.portfolio-help[open] [role=tooltip],.portfolio-help:hover [role=tooltip],.portfolio-help:focus-within [role=tooltip]{display:block}.portfolio-help summary:focus-visible{outline:2px solid #4a9ccc;outline-offset:3px}.portfolio .portfolio-change-up{color:#80f0b7}.portfolio .portfolio-change-down{color:#ffb1b8}html[data-theme=light] body .portfolio .portfolio-change-up{color:#087447!important}html[data-theme=light] body .portfolio .portfolio-change-down{color:#b22539!important}.portfolio :is(p,strong){overflow-wrap:anywhere}html[data-theme=light] body .portfolio .pf-hero{background:#e6f0fd!important;color:#193a60!important}</style>'''


def register(app,login_required,bank,query,page,can_view):
    @app.route('/carteira')
    @login_required
    def portfolio():
        if session.get('tipo')!='admin':return 'Acesso restrito',403
        try:
            start,end=dates(request.args)
            with bank() as conn:shops=query(conn,'SELECT id,cliente,status,user_id FROM conexoes ORDER BY cliente,id',())
            shops=[s for s in shops if can_view(s['id']) and s['cliente'].casefold()!='casamix_store']
            sellers=[s.get('user_id') for s in shops]
            if any(v is None for v in sellers) or len(set(sellers))!=len(sellers):raise ValueError('Há conexões sem conta identificada ou duplicadas. Revise as conexões antes de consolidar a carteira.')
            args=dict(periodo='personalizado',inicio=str(start),fim=str(end))
            sales=load_cached_overview(shops,args,bank,query,load_overview)
            ids=[s['id'] for s in shops]
            with bank() as conn:
                with conn.cursor() as cur:cur.execute("SET LOCAL statement_timeout = '5000ms'")
                ads=query(conn,'SELECT conexao_id,data,gasto,atualizado_em FROM ads_dia WHERE conexao_id=ANY(%s) AND data BETWEEN %s AND %s',(ids,str(start),str(end))) if ids else []
            return page('Visão da Carteira',render(combine(sales,ads),request.args))
        except ValueError as exc:return page('Visão da Carteira','<section class="card"><p>'+escape(str(exc))+'</p><a href="/carteira">Reabrir carteira</a></section>'),400
