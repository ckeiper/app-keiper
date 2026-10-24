"""Observed final offer prices; never reconstruct past promotions from today's price."""
from collections import defaultdict
from datetime import datetime,timedelta
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from zoneinfo import ZoneInfo
from competitor_monitor import money

BR=ZoneInfo('America/Sao_Paulo')


def init_schema(conn,execute):
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_offer_observations (
        conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        item_id TEXT NOT NULL,observed_at BIGINT NOT NULL,
        price NUMERIC(14,2),regular_price NUMERIC(14,2),promotion BOOLEAN,
        confirmed BOOLEAN NOT NULL,PRIMARY KEY(conexao_id,item_id,observed_at))''')


def record(conn,execute,cid,item_id,snapshot,listing_status="active"):
    sale=snapshot.get('sale_price') or {}
    stamp=sale.get('checked_at')
    if type(stamp) is not int or stamp<=0:
        return
    data=sale.get('data') or {}
    price=None
    if listing_status=='active' and not sale.get('error') and data.get('currency_id')=='BRL':
        price=money(data.get('amount_with_taxes') if data.get('amount_tax_inclusion_type')=='net' else data.get('amount'))
    regular=money(data.get('regular_amount')) if price is not None and data.get('amount_tax_inclusion_type')!='net' else None
    promo=None
    if price is not None and regular is not None:
        metadata=data.get('metadata') if isinstance(data.get('metadata'),dict) else {}
        if price>=regular and not metadata.get('promotion_id'):
            promo=False
        elif price<regular and metadata.get('promotion_id'):
            promo=True
    from automatic_history import record as record_changes
    record_changes(conn,execute,cid,item_id,'price',stamp,dict(preco_final=str(price.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)) if price is not None else None,promocao=promo))
    execute(conn,'''INSERT INTO listing_offer_observations
        (conexao_id,item_id,observed_at,price,regular_price,promotion,confirmed)
        VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
        (cid,item_id,stamp,price,regular,promo,price is not None))



def confirmed_price(row):
    price = money(row.get('price')) if row.get('confirmed') is True else None
    return price if price is not None and price > 0 else None


def grouped_readings(rows):
    groups = defaultdict(list)
    for row in rows:
        stamp = row.get('observed_at')
        if type(stamp) is int and stamp > 0:
            groups[stamp].append(row)
    return sorted(groups.items())


def price_events(rows):
    """Compare unique, explicitly confirmed cent prices; failures break continuity."""
    previous = None
    events = []
    for stamp, readings in grouped_readings(rows):
        row = readings[0] if len(readings) == 1 else {}
        price = confirmed_price(row)
        if price is None:
            previous = None
            continue
        if previous and 0 < stamp-previous['at'] <= 6*3600:
            before = previous['price']
            if before != price:
                events.append(dict(at=stamp, previous_at=previous['at'],
                    before=before, after=price, delta=(price-before)*100/before,
                    promotion_ended=previous['promotion'] is True and row.get('promotion') is False))
        previous = dict(at=stamp,price=price,promotion=row.get('promotion'))
    return events


def reading_coverage(rows, end, days=7):
    """Counts describe loaded readings, never time in promotion or sales coverage."""
    start=int(datetime.combine(end-timedelta(days=days*2-1),datetime.min.time(),BR).timestamp())
    middle=int(datetime.combine(end-timedelta(days=days-1),datetime.min.time(),BR).timestamp())
    stop=int(datetime.combine(end+timedelta(days=1),datetime.min.time(),BR).timestamp())
    summary={name:dict(readings=0,confirmed=0,changes=0,promotion=0) for name in ('previous','current')}
    for stamp, readings in grouped_readings(rows):
        if not start<=stamp<stop:continue
        period=summary['current' if stamp>=middle else 'previous']
        period['readings']+=len(readings)
        if len(readings)==1 and confirmed_price(readings[0]) is not None:
            period['confirmed']+=1
            if readings[0].get('promotion') is True:period['promotion']+=1
    for event in price_events(rows):
        if start<=event['at']<stop:
            summary['current' if event['at']>=middle else 'previous']['changes']+=1
    return summary


def render_coverage(rows,end,days):
    summary=reading_coverage(rows,end,days)
    out='<div class="offer-coverage" aria-label="Cobertura do histórico de preço">'
    for name,label,first,last in [
        ('current','Período atual',end-timedelta(days=days-1),end),
        ('previous','Período anterior',end-timedelta(days=days*2-1),end-timedelta(days=days))]:
        period=summary[name]
        out+='<article><h4>'+label+'</h4><small>'+first.strftime('%d/%m/%Y')+' a '+last.strftime('%d/%m/%Y')+'</small>'
        if not period['readings']:
            out+='<p>Sem leituras no período</p>'
        else:
            out+='<p><b>'+str(period['confirmed'])+' de '+str(period['readings'])+'</b> leituras com preço confirmado</p>'
            out+='<p>'+str(period['changes'])+' mudanças entre leituras comparáveis · '+str(period['promotion'])+' leituras com promoção confirmada</p>'
        out+='</article>'
    return out+'</div><p class="muted">Contagens da amostra coletada, sem ponderação por tempo ou vendas. Não indicam dias em promoção, duração do preço ou cobertura financeira. Falhas e duplicidades não contam como preço confirmado; ausência de mudanças não comprova estabilidade.</p>'


def load(conn,query,cid,item_id,end,days=7):
    start=int(datetime.combine(end-timedelta(days=days*2-1),datetime.min.time(),BR).timestamp())
    stop=int(datetime.combine(end+timedelta(days=1),datetime.min.time(),BR).timestamp())
    own=query(conn,'''SELECT observed_at,price,regular_price,promotion,confirmed
        FROM listing_offer_observations WHERE conexao_id=%s AND item_id=%s
        AND observed_at >= %s AND observed_at < %s ORDER BY observed_at''',(cid,item_id,start,stop))
    current=query(conn,'''SELECT observed_at,price,regular_price,promotion,confirmed
        FROM listing_offer_observations WHERE conexao_id=%s AND item_id=%s
        ORDER BY observed_at DESC LIMIT 1''',(cid,item_id))
    targets=query(conn,'''SELECT t.id,t.item_id,t.label,t.price,t.price_at,t.full_state,t.full_at,t.error
        FROM competitor_targets t WHERE t.conexao_id=%s AND t.own_item_id=%s
        AND t.active ORDER BY t.id LIMIT 21''',(cid,item_id))
    rows=query(conn,'''SELECT t.item_id AS competitor_item_id,t.label AS competitor_label,o.target_id,o.observed_at,o.price,o.previous_price,o.full_state,
        o.previous_full,o.price_changed,o.full_changed,o.error
        FROM competitor_observations o JOIN competitor_targets t ON t.id=o.target_id
        WHERE t.conexao_id=%s AND t.own_item_id=%s AND t.active
        AND o.observed_at >= %s AND o.observed_at < %s
        ORDER BY o.observed_at DESC LIMIT 301''',(cid,item_id,start,stop))
    return dict(own=own,current=current[0] if current else None,targets=targets[:20],targets_limited=len(targets)>20,
                competitors=rows[:300],history_limited=len(rows)>300)


def time_label(stamp):
    return datetime.fromtimestamp(int(stamp),BR).strftime('%d/%m/%Y %H:%M')


def render(data,cid,item_id,end,days=7,args=None):
    args=args or {}
    events=price_events(data['own'])
    current_start=int(datetime.combine(end-timedelta(days=days-1),datetime.min.time(),BR).timestamp())
    recent=[r for r in events if r['at']>=current_start]
    out="<section class='card offer-investigation'><h3>Preço, promoções e concorrência</h3>"
    out+="<p class='muted'>Últimos %s dias encerrados até %s, com observações dos %s dias anteriores para comparação. Valores finais públicos por unidade, sem frete ou cupons pessoais.</p>" % (days,end.strftime('%d/%m/%Y'),days)
    current=data.get('current')
    if current:
        if confirmed_price(current) is not None:
            out+="<div class='offer-event'><b>Última oferta observada — contexto separado do período</b><p>R$ %.2f · %s</p><p class='muted'>O horário indica a consulta; não é garantia de preço no momento da compra.</p></div>" % (confirmed_price(current),time_label(current['observed_at']))
        else:
            out+='<p class="muted">Última consulta sem preço confirmado em '+time_label(current['observed_at'])+'. Não utilizamos preço anterior como confirmação atual.</p>'
    out+=render_coverage(data['own'],end,days)
    out+="<p class='muted'>O registro começa nas novas consultas; não reconstruímos promoções passadas.</p>"
    if not data['own']:
        out+='<p>Ainda não há observações de preço neste recorte. A coleta começou agora; não é possível afirmar que o preço permaneceu estável.</p>'
    elif not recent:
        out+='<p>Nenhuma mudança confirmada entre leituras consecutivas comparáveis neste recorte. Lacunas e falhas impedem concluir estabilidade.</p>'
    if len(recent)>5:
        out+='<p class="muted">Últimas 5 de %s mudanças de preço detectadas neste recorte.</p>' % len(recent)
    for event in recent[-5:][::-1]:
        label='Retorno ao preço regular observado' if event['promotion_ended'] else ('Aumento de preço observado' if event['delta']>0 else 'Redução de preço observada')
        out+="<article class='offer-event'><b>%s</b><p>R$ %.2f → R$ %.2f (%+.1f%%) · Detectado em %s</p><p class='muted'>Leitura anterior: %s. Confira visitas e vendas nessas datas; a coincidência não comprova a causa da queda.</p></article>" % (label,event['before'],event['after'],event['delta'],time_label(event['at']),time_label(event['previous_at']))
    out+="<h4>Concorrentes vinculados a este anúncio</h4>"
    if not data['targets']:
        out+='<p>Nenhum concorrente vinculado. Cadastre a oferta concorrente e informe este anúncio como produto próprio.</p>'
    else:
        out+="<details><summary>Ver vínculos e últimas consultas (%s)</summary>" % len(data['targets'])
        for target in data['targets']:
            label=escape(str(target.get('label') or target['item_id']))
            out+="<div class='offer-event'><b>"+label+'</b><p>Código: '+escape(str(target['item_id']))+'</p>'
            if money(target.get('price')) is not None and target.get('price_at'):
                out+='<p>Último preço confirmado: R$ %.2f · %s</p>' % (target['price'],time_label(target['price_at']))
            else:
                out+='<p>Preço ainda não confirmado.</p>'
            if target.get('error'):
                out+='<p class="muted">Consulta com pendência; preço e logística atuais precisam de confirmação.</p>'
            out+='</div>'
        out+='</details>'
    if data['targets_limited'] or data['history_limited']:
        out+='<p class="muted">Exibindo até 20 concorrentes e 300 observações recentes. Consulte o monitoramento para o histórico completo.</p>'
    try:
        page=max(1,int(args.get('pagina_oferta',1)))
    except (TypeError,ValueError):
        page=1
    # Only explicit changes in the monitor's exact observation are evidence.
    # A previous confirmed price can predate a failed read, so disclose its scope.
    changes=[r for r in data['competitors'] if r.get('price_changed') or r.get('full_changed')]
    selected=str(args.get('alteracao_oferta') or 'todas')
    if selected not in ('todas','preco','full'):
        selected='todas'
    out+="<form class='offer-filter' method='get'><label>Alterações dos concorrentes <select name='alteracao_oferta'>"
    for code,label in [('todas','Todas'),('preco','Preço'),('full','Full')]:
        out+="<option value='%s'%s>%s</option>" % (code,' selected' if code==selected else '',label)
    out+="</select></label><button class='filtro-btn'>Filtrar</button></form>"
    if selected!='todas':
        changes=[r for r in changes if r.get('price_changed' if selected=='preco' else 'full_changed')]

    pages=max(1,(len(changes)+9)//10);page=min(page,pages)
    if changes:
        out+="<p class='muted'>Mudanças observadas nos %s dias consultados · Página %s de %s</p><div style='overflow:auto'><table><thead><tr><th>Observação</th><th>Concorrente</th><th>Preço / Full</th></tr></thead><tbody>" % (days*2,page,pages)
        for row in changes[(page-1)*10:page*10]:
            texts=[]
            if row.get('price_changed') and money(row.get('price')) is not None and money(row.get('previous_price')) is not None:
                texts.append('Preço: R$ %.2f → R$ %.2f (último preço confirmado)' % (row['previous_price'],row['price']))
            if row.get('full_changed') and type(row.get('full_state')) is bool and type(row.get('previous_full')) is bool:
                texts.append('Full: %s → %s' % ('Sim' if row['previous_full'] else 'Não','Sim' if row['full_state'] else 'Não'))
            if row.get('error'):
                texts.append('Consulta com pendência; outras informações não confirmadas.')
            out+='<tr><td>'+time_label(row['observed_at'])+'</td><td>'+escape(str(row.get('competitor_label') or row.get('competitor_item_id') or row['target_id']))+'</td><td>'+escape(' · '.join(texts))+'</td></tr>'
        out+='</tbody></table></div>'
        from urllib.parse import urlencode
        out+="<nav aria-label='Paginação de mudanças de oferta'>"
        for label,n in [('Anterior',page-1),('Próxima',page+1)]:
            if 1<=n<=pages:
                params=dict(args);params['pagina_oferta']=n
                out+="<a class='filtro' href='?%s'>%s</a> " % (escape(urlencode(params),quote=True),label)
        out+='</nav>'
    elif data['targets']:
        out+='<p>Nenhuma mudança registrada no recorte consultado. Sem observações suficientes, isso não comprova estabilidade.</p>'
    from urllib.parse import urlencode
    href='/anuncios/%s/concorrencia?' % int(cid)+urlencode({'meu_anuncio':item_id})
    out+="<p><a class='btn-acoes cinza' href='%s'>Vincular concorrente</a></p>" % escape(href,quote=True)
    out+="<p class='muted'>Comparações de preço próprio exigem leituras únicas e explicitamente confirmadas separadas por até seis horas; falhas e duplicidades interrompem a sequência. Full do concorrente indica modalidade logística, não quantidade em estoque. Datas são de detecção, não o horário exato da mudança.</p></section>"
    from listing_competitiveness import render as render_competitiveness
    out+=render_competitiveness(data,end,days)
    return out+"""<style>.offer-investigation{overflow-wrap:anywhere}.offer-event{padding:14px;background:#f2f6fb;border-left:3px solid #258e94;border-radius:9px;margin:10px 0}.offer-event p{font-size:12px;line-height:1.6}.offer-investigation h4{margin-top:20px}.offer-filter{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:15px 0}.offer-filter label{display:grid;gap:5px}.offer-filter select{padding:9px;border:1px solid #dce4ef;border-radius:8px}.offer-coverage{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:16px 0}.offer-coverage article{min-width:0;padding:14px;border:1px solid #426184;border-radius:12px;background:#182e49}.offer-coverage article h4{margin:0 0 6px}.offer-coverage p{font-size:12px;line-height:1.7}.offer-coverage small{color:#bdcce1}@media(max-width:600px){.offer-coverage{grid-template-columns:1fr}}
body .conteudo section.offer-investigation{background:#102238;color:#eaf2ff;border-color:#34516e}
body .conteudo .offer-investigation :is(h3,h4,b,summary){color:#eaf2ff}
body .conteudo .offer-investigation p{color:#dcecff}
body .conteudo .offer-investigation .muted{color:#bdcce1}
body .conteudo .offer-investigation .offer-event,body .conteudo .offer-investigation table th,body .conteudo .offer-investigation table td{background:#182e49;color:#eaf2ff;border-color:#426184}
body .conteudo .offer-investigation select{background:#0b192c;color:#eaf2ff;border-color:#426184;max-width:100%}
body .conteudo .offer-investigation a{color:#b9e5ff}
body .conteudo .offer-investigation :is(a,button,select,summary):focus-visible{outline:3px solid #85c8ec;outline-offset:3px}
</style>"""
