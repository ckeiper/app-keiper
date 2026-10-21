"""Observed final offer prices; never reconstruct past promotions from today's price."""
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



def price_events(rows):
    """Compare adjacent confirmed observations with at most a six-hour gap."""
    previous=None
    events=[]
    for row in sorted(rows,key=lambda r:r['observed_at']):
        if not row.get('confirmed') or money(row.get('price')) is None:
            previous=None
            continue
        if previous and 0 < row['observed_at']-previous['observed_at'] <= 6*3600:
            before,after=Decimal(str(previous['price'])),Decimal(str(row['price']))
            if before!=after:
                events.append(dict(at=row['observed_at'],previous_at=previous['observed_at'],
                    before=before,after=after,delta=(after-before)*100/before,
                    promotion_ended=previous.get('promotion') is True and row.get('promotion') is False))
        previous=row
    return events


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
        if current.get('confirmed') and money(current.get('price')) is not None:
            out+="<div class='offer-event'><b>Última oferta observada — contexto separado do período</b><p>R$ %.2f · %s</p><p class='muted'>O horário indica a consulta; não é garantia de preço no momento da compra.</p></div>" % (current['price'],time_label(current['observed_at']))
        else:
            out+='<p class="muted">Última consulta sem preço confirmado em '+time_label(current['observed_at'])+'. Não utilizamos preço anterior como confirmação atual.</p>'
    confirmed=sum(r.get('confirmed') is True for r in data['own'])
    out+="<p class='muted'>%s leituras de preço confirmadas no histórico consultado. O registro começa nas novas consultas; não reconstruímos promoções passadas.</p>" % confirmed
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
        out+="<p class='muted'>Mudanças observadas nos 14 dias consultados · Página %s de %s</p><div style='overflow:auto'><table><thead><tr><th>Observação</th><th>Concorrente</th><th>Preço / Full</th></tr></thead><tbody>" % (page,pages)
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
    out+="<p class='muted'>Comparações de preço próprio exigem leituras confirmadas separadas por até seis horas. Full do concorrente indica modalidade logística, não quantidade em estoque. Datas são de detecção, não o horário exato da mudança.</p></section>"
    return out+"<style>.offer-investigation{overflow-wrap:anywhere}.offer-event{padding:14px;background:#f2f6fb;border-left:3px solid #258e94;border-radius:9px;margin:10px 0}.offer-event p{font-size:12px;line-height:1.6}.offer-investigation h4{margin-top:20px}.offer-filter{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:15px 0}.offer-filter label{display:grid;gap:5px}.offer-filter select{padding:9px;border:1px solid #dce4ef;border-radius:8px}</style>"
