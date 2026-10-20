"""Per-store management facts and actions from cached, qualified data only."""
import time
from datetime import datetime, timedelta
from decimal import Decimal

from sales_metrics import SAO_PAULO, amount, change, reporting_today, summarize
from listing_ranking import ranking_metrics
from overview_read import bounded_query

MAX_LISTINGS = 10000
MAX_ORDERS = 20000
MAX_ITEMS = 60000


def selection(args, today=None):
    """Default to completed dates so a partial today cannot look like a decline."""
    today = today or reporting_today()
    days = args.get('dias', '7')
    days = int(days) if days in ('7','15','30','60','90') else 7
    end = today - timedelta(days=1)
    start = end - timedelta(days=days-1)
    if args.get('inicio') or args.get('fim'):
        try:
            start = datetime.strptime(args.get('inicio',''),'%Y-%m-%d').date()
            end = datetime.strptime(args.get('fim',''),'%Y-%m-%d').date()
            if end < start or end >= today or (end-start).days >= 90:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError('Selecione de 1 a 90 dias completos, com fim até ontem.')
        days = (end-start).days+1
    return start,end,start-timedelta(days=days),start-timedelta(days=1)


def fresh(stamp, now, seconds):
    return isinstance(stamp,(int,float)) and 0 <= now-stamp <= seconds


def reliable(summary):
    return summary['revenue'] is not None and not summary['unallocated_dates']


def advertising(rows, start, end):
    days = {(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)}
    by_day = {str(r['data']):r for r in rows if str(r['data']) in days}
    result = dict(spend=None,revenue=None,roas=None,acos=None,clicks=None,impressions=None,
                  ctr=None,coverage=len(by_day),expected=len(days))
    if set(by_day) != days:
        return result
    for key,source in [('spend','gasto'),('revenue','faturamento'),('clicks','cliques'),('impressions','impressoes')]:
        numbers = [amount(row.get(source)) for row in by_day.values()]
        if all(n is not None for n in numbers):
            result[key] = sum(numbers,Decimal(0))
    if result['spend'] is not None and result['revenue'] is not None:
        result['roas'] = result['revenue']/result['spend'] if result['spend'] else None
        result['acos'] = result['spend']/result['revenue']*100 if result['revenue'] else None
    if result['clicks'] is not None and result['impressions']:
        result['ctr'] = result['clicks']/result['impressions']*100
    return result


def build_management(listings, orders, items, coverage, visits, ads, pending,
                     bounds, now=None, sales_limited=False):
    now = int(time.time()) if now is None else now
    start,end,previous_start,previous_end = bounds
    days = (end-start).days+1
    covered = {str(row['dia']):row['atualizado_em'] for row in coverage}
    current = summarize(orders,start,end,set(covered))
    previous = summarize(orders,previous_start,previous_end,set(covered))
    for report in (current,previous):
        if pending or sales_limited or report['unallocated_dates']:
            for key in ('revenue','orders','units','ticket','unit_price','cancellations'):
                report[key] = None
            for key in ('daily','daily_orders','daily_units','daily_ticket'):
                report[key] = [None]*len(report['days'])
    ranking = ranking_metrics(orders,items,set(covered),[a['item_id'] for a in listings],
                              end=end,days=days,pending=pending or sales_limited)
    if current['unallocated_dates'] or previous['unallocated_dates']:
        ranking.update(available=False,reason='Há pedidos sem data verificável; revalide o histórico.',rows={})
    recent_start = datetime.fromtimestamp(now,SAO_PAULO).date()-timedelta(days=6)
    selected_dates = current['days']+previous['days']
    sales_fresh = all(fresh(covered.get(day),now,3*3600 if day >= recent_start.isoformat() else 7*86400)
                      for day in selected_dates)
    warnings = []
    if pending:
        warnings.append('Há pedidos antigos ainda não verificados; indicadores de vendas aguardam revalidação.')
    if sales_limited:
        warnings.append('Limite de leitura atingido. Nenhum total parcial de vendas foi apresentado; selecione um período menor.')
    if not reliable(current) or not reliable(previous):
        warnings.append('Cobertura ou integridade de vendas incompleta em um dos períodos. Ausência de coleta não é venda zerada.')
    elif not sales_fresh:
        warnings.append('As vendas exibidas são a última leitura confirmada. Atualize a sincronização antes de agir sobre tendências.')
    if not ranking['available']:
        warnings.append(ranking['reason'] or 'Análise por anúncio aguardando vínculo completo dos pedidos.')
    ad_current,ad_previous = advertising(ads,start,end),advertising(ads,previous_start,previous_end)
    tacos = (ad_current['spend']/current['revenue']*100
             if reliable(current) and current['revenue'] and ad_current['spend'] is not None else None)
    visits_by_id = {str(v['item_id']):v for v in visits}
    rows,signals = [],[]
    revenue_items = Decimal(0)
    cost_known_value = Decimal(0)
    missing_cost_count = 0
    total_visits = 0
    visits_complete = 0
    for listing in listings:
        item_id = str(listing['item_id'])
        metrics = ranking['rows'].get(item_id) if ranking['available'] else None
        seen = visits_by_id.get(item_id,{})
        visits_current = int(seen.get('visits_current') or 0)
        visits_known = seen.get('days_current',0) == days
        total_visits += visits_current
        visits_complete += int(visits_known)
        stock = amount(listing.get('quantidade'))
        stock = stock if stock is not None and stock == stock.to_integral_value() else None
        price = amount(listing.get('preco'))
        cost = amount(listing.get('custo'))
        catalogue_fresh = fresh(listing.get('atualizado_em'),now,6*3600)
        status = str(listing.get('status') or '').lower()
        stock_days = (stock*days/metrics['units'] if metrics and metrics['units'] and stock is not None else None)
        entry = dict(listing=listing,metrics=metrics,stock=stock,stock_days=stock_days,
                     visits=visits_current if visits_known else None,
                     observed_visits=visits_current,visits_days=seen.get('days_current',0),
                     ratio=(Decimal(metrics['orders'])*100/visits_current
                            if metrics and visits_known and visits_current else None),
                     fresh=catalogue_fresh)
        rows.append(entry)
        def add(kind,priority,title,evidence,action,path,impact=None):
            signals.append(dict(item_id=item_id,title=title,kind=kind,priority=priority,
                                evidence=evidence,action=action,path=path,impact=impact,
                                label=listing.get('titulo') or item_id))
        detail=f'/diagnostico/{{cid}}/{item_id}'
        if not catalogue_fresh:
            add('dados','dados','Atualizar dados do anúncio','Sem leitura recente de status e estoque (até 6h).',
                'Atualize a loja antes de confirmar indisponibilidade.',detail)
        elif stock == 0 and status in ('active','paused'):
            sold = metrics and (metrics['orders'] or metrics['previous_orders']) and sales_fresh
            add('estoque','alta' if sold else 'media','Estoque zerado',
                'Quantidade disponível registrada: 0.' + (' Houve vendas em um dos períodos.' if sold else ''),
                'Verifique reposição e disponibilidade de venda.',detail)
        elif (stock_days is not None and stock_days <= 7 and status == 'active' and sales_fresh):
            add('estoque','alta' if stock_days<=3 else 'media','Cobertura de estoque curta',
                f'{int(stock)} unidades disponíveis; cobertura estimada de {stock_days:.1f} dias ao ritmo do período.',
                'Planeje reposição; a estimativa supõe o mesmo ritmo de vendas.',detail)
        if catalogue_fresh and status == 'paused':
            add('status','alta' if metrics and metrics['previous_orders'] and sales_fresh else 'media',
                'Anúncio pausado','Status sincronizado: pausado.',
                'Confira o motivo da pausa e se é possível retomar as vendas.',detail)
        if metrics:
            revenue_items += metrics['value']
            if metrics['orders'] and cost and cost > 0:
                cost_known_value += metrics['value']
            elif metrics['orders']:
                missing_cost_count += 1
                add('margem','media','Vendas sem custo cadastrado',
                    f"{metrics['orders']} pedidos no período; custo unitário ausente ou zerado.",
                    'Cadastre o custo para avaliar margem; faturamento não representa lucro.',
                    '/custos/{cid}',metrics['value'])
            if sales_fresh and metrics['previous_orders']>=3 and metrics['orders']==0:
                add('vendas','alta','Vendas interrompidas no período',
                    f"{metrics['previous_orders']} pedidos antes e nenhum no período atual.",
                    'Compare estoque, preço, frete, exposição e Ads. A causa ainda precisa ser verificada.',
                    detail,metrics['previous_value'])
            elif (sales_fresh and metrics['previous_orders']>=5
                  and metrics['orders']*100 <= metrics['previous_orders']*70):
                add('vendas','media','Queda de pelo menos 30% nos pedidos',
                    f"{metrics['previous_orders']} → {metrics['orders']} pedidos em períodos de mesma duração.",
                    'Confira visitas, preço, estoque e campanhas antes de alterar o anúncio.',
                    detail,max(Decimal(0),metrics['previous_value']-metrics['value']))
        photos=amount(listing.get('fotos'))
        if catalogue_fresh and status=='active' and photos is not None and photos<5:
            add('qualidade','oportunidade','Revisar apresentação do produto',
                f'{int(photos)} fotos registradas; referência editorial de 5, não regra do Mercado Livre.',
                'Avalie fotos de dimensões, aplicações, detalhes e respostas às objeções.',detail)
    order={'alta':0,'media':1,'oportunidade':2,'dados':3}
    signals.sort(key=lambda s:(order[s['priority']],-(s['impact'] or 0),s['item_id'],s['kind']))
    selling = [r for r in rows if r['metrics'] and r['metrics']['orders']]
    champions = sorted(selling,key=lambda r:(-r['metrics']['value'],r['listing']['item_id']))[:5]
    share=(champions[0]['metrics']['value']/revenue_items*100 if champions and revenue_items else None)
    return dict(bounds=bounds,days=days,current=current,previous=previous,ranking=ranking,
                rows=rows,signals=signals,warnings=list(dict.fromkeys(warnings)),
                ads=ad_current,ads_previous=ad_previous,tacos=tacos,champions=champions,
                top_share=share,selling=len(selling) if ranking['available'] else None,
                no_sales=sum(r['metrics']['orders']==0 for r in rows) if ranking['available'] else None,
                cost_coverage=cost_known_value/revenue_items*100 if revenue_items else None,
                missing_cost_count=missing_cost_count if ranking['available'] else None,
                visits=total_visits,visits_complete=visits_complete,listing_count=len(listings),
                sales_fresh=sales_fresh,
                last_catalogue=min((a.get('atualizado_em') or 0 for a in listings),default=None))


def load_management(cid,args,bank,query):
    bounds=selection(args)
    start,end,previous_start,_=bounds
    with bank() as conn:
        conn.set_session(isolation_level='REPEATABLE READ',readonly=True)
        read=bounded_query(conn,query)
        shops=read(conn,'SELECT id,cliente,status FROM conexoes WHERE id=%s',(cid,))
        if not shops:
            return None
        listings=read(conn,'''SELECT item_id,titulo,status,quantidade,preco,custo,fotos,clips,tags,atualizado_em,thumbnail
            FROM anuncios WHERE conexao_id=%s ORDER BY item_id LIMIT %s''',(cid,MAX_LISTINGS+1))
        if len(listings)>MAX_LISTINGS:
            raise ValueError('A loja excede 10 mil anúncios nesta análise. Nenhum catálogo parcial foi exibido.')
        orders=read(conn,'''SELECT conexao_id,pedido_id,status,total,moeda,criado_em,
            pagamentos_json,unidades,vendas_dia_coleta FROM pedidos
            WHERE conexao_id=%s AND vendas_verificado_em IS NOT NULL
            AND (keiper_overview_day_v1(criado_em) BETWEEN %s AND %s
                 OR keiper_overview_day_v1(criado_em) IS NULL)
            ORDER BY pedido_id LIMIT %s''',(cid,previous_start,end,MAX_ORDERS+1))
        limited=len(orders)>MAX_ORDERS
        items=[]
        if not limited:
            items=read(conn,'''SELECT pi.conexao_id,pi.pedido_id,pi.item_id,pi.quantidade,pi.preco_unitario
                FROM pedidos_itens pi JOIN pedidos p ON p.conexao_id=pi.conexao_id AND p.pedido_id=pi.pedido_id
                WHERE pi.conexao_id=%s AND p.vendas_verificado_em IS NOT NULL
                AND (keiper_overview_day_v1(p.criado_em) BETWEEN %s AND %s
                     OR keiper_overview_day_v1(p.criado_em) IS NULL)
                ORDER BY pi.pedido_id,pi.item_id LIMIT %s''',(cid,previous_start,end,MAX_ITEMS+1))
            limited=len(items)>MAX_ITEMS
        coverage=read(conn,'''SELECT dia,atualizado_em FROM vendas_cobertura
            WHERE conexao_id=%s AND dia BETWEEN %s AND %s''',(cid,previous_start.isoformat(),end.isoformat()))
        pending=read(conn,'''SELECT EXISTS(SELECT 1 FROM pedidos WHERE conexao_id=%s
            AND vendas_verificado_em IS NULL) AS pending''',(cid,))[0]['pending']
        visits=read(conn,'''SELECT item_id,
            SUM(visitas) FILTER(WHERE dia >= %s) AS visits_current,
            COUNT(*) FILTER(WHERE dia >= %s) AS days_current
            FROM item_visits_daily WHERE conexao_id=%s AND dia BETWEEN %s AND %s
            GROUP BY item_id''',(start,start,cid,start,end))
        ads=read(conn,'''SELECT data,gasto,faturamento,impressoes,cliques,atualizado_em
            FROM ads_dia WHERE conexao_id=%s AND data BETWEEN %s AND %s''',
                  (cid,previous_start.isoformat(),end.isoformat()))
        questions=read(conn,"SELECT COUNT(*) AS n FROM perguntas WHERE conexao_id=%s AND status='UNANSWERED'",(cid,))[0]['n']
    result=build_management(listings,orders,items,coverage,visits,ads,pending,bounds,sales_limited=limited)
    result.update(shop=shops[0],questions=questions)
    return result
