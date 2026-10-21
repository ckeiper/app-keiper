"""Bounded evidence for a listing's two completed seven-day windows.

No network calls, no campaign-to-item allocation, no filled-in missing days.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import escape
from zoneinfo import ZoneInfo


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def date_key(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        return None


def window(rows, dates, fields, day_field):
    """All expected dates/fields must validate; duplicate days are not summed."""
    lookup = {}
    for row in rows:
        key = date_key(row.get(day_field))
        if key not in dates:
            continue
        if key in lookup:
            lookup[key] = None
            continue
        values = {f: number(row.get(f)) for f in fields}
        # Visits and click/impression counts are integer-valued.
        for field in ('visitas', 'cliques', 'impressoes'):
            if field in values and values[field] is not None and values[field] % 1:
                values[field] = None
        lookup[key] = values if all(v is not None for v in values.values()) else None
    valid = [lookup[d] for d in dates if lookup.get(d) is not None]
    complete = len(valid) == len(dates)
    return dict(complete=complete, covered=len(valid), expected=len(dates),
                totals={f: sum((r[f] for r in valid), Decimal(0)) for f in fields} if complete else None)


def change(current, previous):
    return (current-previous)*100/previous if previous else None


def build(ranking, item_id, visits, observations, ads, end, days=7, offers=None):
    dates = [(end-timedelta(days=2*days-1-i)).isoformat() for i in range(2*days)]
    old_dates, new_dates = dates[:days], dates[days:]
    before = window(visits, old_dates, ['visitas'], 'dia')
    now = window(visits, new_dates, ['visitas'], 'dia')
    traffic = dict(previous=before, current=now, complete=before['complete'] and now['complete'], delta=None)
    if traffic['complete']:
        traffic['delta'] = change(now['totals']['visitas'], before['totals']['visitas'])
    # Ratio is a diagnostic proxy: verified paid orders containing the listing
    # divided by recorded visits. Not the marketplace's official conversion.
    sales = ranking.get('rows',{}).get(str(item_id)) if ranking.get('available') else None
    conversion = dict(complete=False, previous=None, current=None, delta=None)
    if sales and traffic['complete']:
        old_visits, new_visits = before['totals']['visitas'], now['totals']['visitas']
        if old_visits > 0 and new_visits > 0:
            old_ratio = Decimal(sales['previous_orders'])*100/old_visits
            new_ratio = Decimal(sales['orders'])*100/new_visits
            conversion.update(complete=True, previous=old_ratio, current=new_ratio, delta=change(new_ratio,old_ratio))
    from listing_full_sales_chart import daily_full_status
    stock = daily_full_status(observations,dates)
    # Only adjacent calendar days with confirmed states establish a transition.
    transitions = [dates[i] for i in range(1,len(dates))
                   if stock[i-1] == 1 and stock[i] == 0 and dates[i] in new_dates]
    full = dict(previous_known=sum(x is not None for x in stock[:days]),
                current_known=sum(x is not None for x in stock[days:]),
                empty_dates=[d for d,v in zip(dates,stock) if d in new_dates and v == 0],
                transitions=transitions)
    fields = ['gasto','faturamento','impressoes','cliques']
    ads_before, ads_now = window(ads,old_dates,fields,'data'), window(ads,new_dates,fields,'data')
    advertising = dict(previous=ads_before,current=ads_now,complete=ads_before['complete'] and ads_now['complete'])
    advertising['spend_delta'] = (change(ads_now['totals']['gasto'],ads_before['totals']['gasto']) if advertising['complete'] else None)
    actions=[]
    declining = bool(sales and sales['value'] < sales['previous_value'])
    if full['empty_dates']:
        actions.append(dict(code='full',title='Verificar reposição no Full',
            evidence='Full sem estoque observado em '+', '.join(full['empty_dates'])+'.',
            action='Conferir estoque e reposição por variação; verificar o prazo de entrega nas datas observadas.',
            scope='Evidência do anúncio; não comprova a causa da queda.'))
    if traffic['delta'] is not None and traffic['delta'] <= -20 and before['totals']['visitas'] >= 30:
        actions.append(dict(code='trafego',title='Investigar redução de tráfego',
            evidence='Visitas do anúncio: %+.1f%% entre períodos completos.' % traffic['delta'],
            action='Conferir exposição, status do anúncio e participação em catálogo; verificar publicidade específica do produto.',
            scope='Sinal do anúncio; triagem de queda de 20% com pelo menos 30 visitas na base anterior.'))
    if conversion['delta'] is not None and conversion['delta'] <= -20 and sales['previous_orders'] >= 5:
        actions.append(dict(code='eficiencia',title='Investigar eficiência das visitas',
            evidence='Relação pedidos pagos/visitas: %+.1f%%.' % conversion['delta'],
            action='Revisar preço final, frete, prazo e disponibilidade das variações; comparar a oferta com os concorrentes.',
            scope='Triagem de queda de 20% com pelo menos 5 pedidos anteriores; diferente da conversão oficial do Mercado Livre.'))
    if declining and advertising['spend_delta'] is not None and advertising['spend_delta'] <= -20:
        actions.append(dict(code='ads_loja',title='Revisar a redução de Ads da loja',
            evidence='Investimento da loja: %+.1f%%.' % advertising['spend_delta'],
            action='Abrir as campanhas e confirmar se os anúncios afetados pertencem às campanhas com menor investimento.',
            scope='Contexto da loja; não atribuído a este anúncio.'))
    result = dict(traffic=traffic,conversion=conversion,full=full,ads=advertising,actions=actions,
                  sales_verified=bool(sales),declining=declining,dates=dates,visits_rows=visits)
    from investigation_triage import build as build_triage
    result['triage'] = build_triage(result,sales,offers,stock,end,days)
    result['actions'] = result['triage']['actions']
    return result


def load(conn, query, cid, item_id, end, days=7):
    start = (end-timedelta(days=days*2-1)).isoformat()
    visits = query(conn, '''SELECT dia,visitas FROM item_visits_daily
        WHERE conexao_id=%s AND item_id=%s AND dia BETWEEN %s AND %s ORDER BY dia''',
                   (cid,item_id,start,end.isoformat()))
    ads = query(conn, '''SELECT data,gasto,faturamento,impressoes,cliques FROM ads_dia
        WHERE conexao_id=%s AND data BETWEEN %s AND %s ORDER BY data''',
                (cid,start,end.isoformat()))
    return visits,ads


CSS = """<style>
.evidence-panel{margin:20px 0;color:#243651}.evidence-heading{background:#1c3554;color:#fff;padding:22px;border-radius:15px}.evidence-heading h3{color:#fff;margin:0 0 8px}.evidence-heading p{color:#cfdee9;font-size:12px;line-height:1.6;margin:0}.evidence-sources{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:14px 0}.evidence-source{background:#fff;border:1px solid #dfe7f1;border-radius:13px;padding:18px;overflow-wrap:anywhere}.evidence-source h4{margin:8px 0 12px;font-size:15px}.evidence-source p,.evidence-action p{font-size:12px;line-height:1.6}.evidence-badge{display:inline-block;border-radius:6px;padding:4px 7px;font-size:10px;background:#e5f5ef;color:#23775b}.evidence-badge.partial{background:#fff2df;color:#916020}.evidence-badge.context{background:#e9eef9;color:#48618d}.evidence-action{border-left:4px solid #1d9d96;background:#fff;padding:17px;border-radius:10px;margin:10px 0}.evidence-action h4{margin:0 0 8px;color:#245168}.evidence-meta{color:#6b7c92;font-size:11px;line-height:1.6}.evidence-table{width:100%;border-collapse:collapse;font-size:12px}.evidence-table th,.evidence-table td{padding:9px;text-align:left;border-bottom:1px solid #e7edf5}.evidence-next{border:1px solid #c9d8ed;border-radius:13px;background:#eef4ff;padding:18px;margin:14px 0;overflow-wrap:anywhere}.evidence-next h4{margin:0 0 8px;color:#213e68}.evidence-next p{font-size:12px;line-height:1.6;margin:7px 0}.evidence-gaps{background:#fff8ec;border:1px solid #f0dfbb;border-radius:10px;padding:0 14px;margin:12px 0;overflow-wrap:anywhere}.evidence-gaps ul{padding-left:18px;font-size:12px;line-height:1.7}.evidence-panel summary{cursor:pointer;font-size:12px;font-weight:600;padding:12px 0}
</style>"""


def fmt(value, currency=False):
    if value is None:
        return 'Indisponível'
    raw = ('%.2f' % value).replace('.',',')
    return ('R$ ' if currency else '')+raw


def render(evidence, cid, end, days=7):
    e=evidence
    out=CSS+"<section class='evidence-panel'><div class='evidence-heading'><h3>Onde investigar primeiro</h3>"
    out+='<p>Vendas, visitas, Full e publicidade · %s dias encerrados até %s vs. período anterior de mesma duração.</p></div>' % (days,end.strftime('%d/%m/%Y'))
    if not e['sales_verified']:
        out+='<p class="evidence-meta">Vendas sem cobertura verificada: os sinais abaixo descrevem suas próprias fontes e não confirmam queda de vendas.</p>'
    elif not e['declining']:
        out+='<p class="evidence-meta">Sem queda de faturamento verificada neste recorte. Os sinais abaixo podem revelar pontos de atenção.</p>'
    triage=e.get('triage')
    if triage:
        out+="<div class='evidence-next'>"
        if triage['status']=='queda':
            out+='<h4>Queda confirmada: '+fmt(triage['loss'],True)+'</h4><p>Diferença de faturamento bruto dos itens entre as duas janelas; não é uma estimativa de recuperação.</p>'
        elif triage['status']=='sem_queda':
            out+='<h4>Sem queda confirmada neste recorte</h4>'
        else:
            out+='<h4>Concluir a verificação das vendas</h4>'
        if not e['sales_verified']:
            out+='<p><b>Primeira verificação sugerida:</b> validar cobertura e pedidos dos dois períodos. As observações abaixo continuam disponíveis como sinais independentes.</p>'
        elif e['actions']:
            first=e['actions'][0]
            out+='<p><b>Primeira verificação sugerida:</b> '+escape(first['title'])+'</p><p>'+escape(first['action'])+'</p>'
        else:
            out+='<p>Nenhum sinal atingiu as regras de triagem. Confira as lacunas e a linha do tempo antes de escolher uma intervenção.</p>'
        out+='<p class="evidence-meta">A ordem prioriza verificações operacionais do anúncio e deixa Ads da loja como contexto. Não classifica causas comprovadas nem garante impacto em vendas.</p></div>'
        if triage['gaps']:
            out+="<details class='evidence-gaps'><summary>O que falta para concluir (%s)</summary><ul>" % len(triage['gaps'])
            out+=''.join('<li>'+escape(gap)+'</li>' for gap in triage['gaps'])+'</ul></details>'
    out+="<div class='evidence-sources'>"
    traffic=e['traffic']
    out+="<div class='evidence-source'><span class='evidence-badge %s'>%s</span><h4>Visitas do anúncio</h4>" % ('' if traffic['complete'] else 'partial','Cobertura completa' if traffic['complete'] else 'Cobertura parcial')
    for label,period in [('Antes',traffic['previous']),('Agora',traffic['current'])]:
        out+='<p>%s: %s · %s/%s dias válidos</p>' % (label,fmt(period['totals']['visitas']) if period['complete'] else 'Total indisponível',period['covered'],period['expected'])
    out+='<p>Variação: '+(('%+.1f%%' % traffic['delta']) if traffic['delta'] is not None else 'sem base comparável')+'</p></div>'
    conversion=e['conversion']
    out+="<div class='evidence-source'><span class='evidence-badge %s'>%s</span><h4>Pedidos pagos ÷ visitas</h4>" % ('' if conversion['complete'] else 'partial','Indicador calculado' if conversion['complete'] else 'Dados insuficientes')
    out+='<p>Antes: %s · Agora: %s</p><p class="evidence-meta">Exige vendas verificadas, visitas completas e denominadores positivos. Não é a conversão oficial do Mercado Livre.</p></div>' % (fmt(conversion['previous'])+'%' if conversion['complete'] else '—',fmt(conversion['current'])+'%' if conversion['complete'] else '—')
    stock=e['full']
    out+="<div class='evidence-source'><span class='evidence-badge %s'>Observações do anúncio</span><h4>Estoque Full</h4>" % ('' if stock['current_known']==days else 'partial')
    out+='<p>Antes: %s/%s dias conhecidos · Agora: %s/%s.</p><p>Full zerado observado em %s dias atuais.</p>' % (stock['previous_known'],days,stock['current_known'],days,len(stock['empty_dates']))
    out+='<p class="evidence-meta">Última leitura de cada dia. Ausência de leitura não significa estoque zerado. Não mede duração da ruptura.</p></div>'
    ads=e['ads']
    out+="<div class='evidence-source'><span class='evidence-badge context'>Contexto da loja inteira</span><h4>Publicidade</h4>"
    for label,p in [('Antes',ads['previous']),('Agora',ads['current'])]:
        out+='<p>%s: %s/%s dias válidos' % (label,p['covered'],p['expected'])
        if p['complete']:
            t=p['totals']
            out+=' · Investimento '+fmt(t['gasto'],True)+' · Faturamento Ads '+fmt(t['faturamento'],True)+' · '+str(int(t['impressoes']))+' impressões · '+str(int(t['cliques']))+' cliques'
            out+=' · ROAS '+(fmt(t['faturamento']/t['gasto'])+'x' if t['gasto'] else 'sem base')
            out+=' · CTR '+(fmt(t['cliques']*100/t['impressoes'])+'%' if t['impressoes'] else 'sem base')
        out+='</p>'
    out+='<p class="evidence-meta">Ainda não há histórico diário de Ads por anúncio. Os números da loja não são atribuídos a este produto.</p></div></div>'
    if e['actions']:
        for i,action in enumerate(e['actions'],1):
            out+="<article class='evidence-action'><h4>%s. %s</h4><p><b>Evidência:</b> %s</p><p><b>Ação:</b> %s</p><p class='evidence-meta'>%s</p>" % (i,escape(action['title']),escape(action['evidence']),escape(action['action']),escape(action['scope']))
            if action.get('follow_up'):
                out+='<p><b>Como acompanhar:</b> '+escape(action['follow_up'])+'</p>'
            out+='</article>'
    else:
        out+='<p class="evidence-meta">Nenhum sinal atingiu as regras de triagem com os dados disponíveis. Revise a cobertura antes de concluir que não há problemas.</p>'
    if stock['transitions']:
        out+='<p class="evidence-meta">Mudança de Full disponível para zerado entre dias consecutivos com leitura: '+escape(', '.join(stock['transitions']))+'. Data de observação, não horário exato da ruptura.</p>'
    # Every date stays visible, including gaps, so partial history is inspectable.
    out+="<details><summary>Conferir visitas diárias e lacunas (14 dias)</summary><table class='evidence-table'><thead><tr><th>Data</th><th>Visitas registradas</th></tr></thead><tbody>"
    for d in e['dates']:
        reading=window(e['visits_rows'],[d],['visitas'],'dia')
        v=reading['totals']['visitas'] if reading['complete'] else None
        out+='<tr><td>'+date.fromisoformat(d).strftime('%d/%m/%Y')+'</td><td>'+(str(int(v)) if v is not None and v%1==0 else 'Sem dado válido')+'</td></tr>'
    return out+'</tbody></table></details><p class="evidence-meta">Triagem: queda de 20%, com base anterior mínima de 30 visitas para tráfego ou 5 pedidos para eficiência. Estes limites não são um teste de significância. Sinais orientam a investigação; coincidência de datas não comprova causalidade. Preço final, concorrência, prazo e alterações do anúncio ainda precisam ser conferidos.</p></section>'


def load_bulk(conn, query, cid, ranking, end, days=7):
    """Two local reads for all losing listings; never one DB query per item."""
    if not ranking.get('available'):
        return {}
    ids = [str(key) for key,m in ranking['rows'].items() if m['value'] < m['previous_value']]
    if not ids:
        return {}
    start = end-timedelta(days=2*days-1)
    visits = query(conn, """SELECT item_id,dia,visitas FROM item_visits_daily
        WHERE conexao_id=%s AND dia BETWEEN %s AND %s ORDER BY item_id,dia""",
        (cid,start.isoformat(),end.isoformat()))
    start_stamp = int(datetime.combine(start,datetime.min.time(),ZoneInfo('America/Sao_Paulo')).timestamp())
    end_stamp = int(datetime.combine(end+timedelta(days=1),datetime.min.time(),ZoneInfo('America/Sao_Paulo')).timestamp())
    observations = query(conn, """SELECT item_id,observed_at,state,logistics FROM full_observations
        WHERE conexao_id=%s AND observed_at >= %s AND observed_at < %s
        ORDER BY item_id,observed_at""", (cid,start_stamp,end_stamp))
    from collections import defaultdict
    by_visits,by_full=defaultdict(list),defaultdict(list)
    for row in visits:
        by_visits[str(row['item_id'])].append(row)
    for row in observations:
        by_full[str(row['item_id'])].append(row)
    result={}
    for item_id in ids:
        evidence=build(ranking,item_id,by_visits[item_id],by_full[item_id],[],end,days=days)
        result[item_id]=dict(actions=evidence['actions'],
            codes=[a['code'] for a in evidence['actions']],
            visits_days=evidence['traffic']['previous']['covered']+evidence['traffic']['current']['covered'],
            full_days=evidence['full']['previous_known']+evidence['full']['current_known'],expected=2*days)
    return result
