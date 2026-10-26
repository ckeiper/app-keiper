"""Sample-price constancy, with explicit coverage gates and no forecast."""
from datetime import datetime,timedelta
from decimal import Decimal,ROUND_HALF_UP
from html import escape
import time
from offer_history import BR,confirmed_price

LIMIT=5000


def period(rows,start,end,now):
    first=int(datetime.combine(start,datetime.min.time(),BR).timestamp())
    stop=int(datetime.combine(end+timedelta(days=1),datetime.min.time(),BR).timestamp())
    groups={};rejected=0
    for row in rows:
        if not isinstance(row,dict):rejected+=1;continue
        stamp=row.get('observed_at')
        if type(stamp) is not int or stamp<=0:rejected+=1;continue
        if stamp>now:rejected+=1;continue
        if first<=stamp<stop:groups.setdefault(stamp,[]).append(row)
    daily={start+timedelta(days=i):dict(readings=0,valid=0,pairs=0,same=0,changes=0,low=None,high=None) for i in range((end-start).days+1)}
    valid=0;pairs=0;same=0;previous=None;prices=[]
    for stamp,group in sorted(groups.items()):
        day=datetime.fromtimestamp(stamp,BR).date();bucket=daily[day];bucket['readings']+=len(group)
        price=confirmed_price(group[0]) if len(group)==1 else None
        if price is None:previous=None;continue
        valid+=1;bucket['valid']+=1;prices.append(price)
        bucket['low']=price if bucket['low'] is None else min(bucket['low'],price)
        bucket['high']=price if bucket['high'] is None else max(bucket['high'],price)
        if previous is not None and 0<stamp-previous[0]<=21600:
            pairs+=1;bucket['pairs']+=1
            if price==previous[1]:same+=1;bucket['same']+=1
            else:bucket['changes']+=1
        previous=(stamp,price)
    total=sum(len(g) for g in groups.values());adjacent=max(0,len(groups)-1)
    days=sum(v['valid']>0 for v in daily.values())
    confirmed_share=Decimal(valid)*100/total if total else None
    comparable_share=Decimal(pairs)*100/adjacent if adjacent else None
    sufficient=(rejected==0 and pairs>=10 and days>=3 and confirmed_share is not None and confirmed_share>=80
                and comparable_share is not None and comparable_share>=80)
    score=Decimal(same)*100/pairs if sufficient else None
    return dict(start=start,end=end,total=total,valid=valid,days=days,pairs=pairs,same=same,changes=pairs-same,
                adjacent=adjacent,confirmed_share=confirmed_share,comparable_share=comparable_share,score=score,
                low=min(prices) if prices else None,high=max(prices) if prices else None,
                amplitude=(max(prices)-min(prices))*100/min(prices) if prices else None,daily=daily,rejected=rejected)


def build(rows,end,days=7,now=None):
    now=int(time.time()) if now is None else now
    if type(days) is not int or not 1<=days<=30:raise ValueError('Período inválido.')
    limited=len(rows)>LIMIT
    current_start=end-timedelta(days=days-1);previous_end=current_start-timedelta(days=1)
    if limited:
        # No sampling bias: do not fabricate a score from an arbitrarily truncated list.
        return dict(limited=True,current=None,previous=None)
    return dict(limited=False,current=period(rows,current_start,end,now),previous=period(rows,previous_end-timedelta(days=days-1),previous_end,now))


def render(rows,end,days=7,now=None):
    data=build(rows,end,days,now);esc=lambda v:escape(str(v),quote=True)
    def pct(value):return format(value.quantize(Decimal('0.1'),rounding=ROUND_HALF_UP),'f').replace('.',',')+'%' if value is not None else 'não verificado'
    def money(value):return 'R$ '+format(value.quantize(Decimal('0.01')),'f').replace('.',',') if value is not None else 'não verificado'
    out=STYLE+'<section class="price-stability"><h3>Constância dos preços observados</h3><p>Fonte: leituras confirmadas de preço final em BRL. Índice amostral de 0 a 100: pares sem mudança ÷ pares comparáveis × 100. Pares exigem duas leituras únicas, positivas e confirmadas, com intervalo de até seis horas. Falha, duplicidade e intervalo maior interrompem a comparação.</p>'
    if data['limited']:return out+'<p role="status">Mais de 5.000 registros carregados: índice não verificado. Reduza o período ou confira o histórico; nenhum recorte arbitrário foi usado.</p></section>'
    out+='<p>Para exibir o índice: nenhum registro com horário/formato inválido ou futuro na base carregada, ao menos dez pares comparáveis, leituras válidas em três dias, 80% das leituras confirmadas e 80% dos intervalos entre horários coletados comparáveis. Essas condições não comprovam cobertura contínua do período. Cada par tem o mesmo peso, sem ponderação por tempo ou vendas.</p><div class="ps-cards">'
    for key,label in [('previous','Período anterior'),('current','Período atual')]:
        p=data[key]
        out+='<article><h4>'+label+'</h4><p>'+p['start'].strftime('%d/%m/%Y')+' a '+p['end'].strftime('%d/%m/%Y')+' · Brasília</p><strong>'+('Índice '+pct(p['score']) if p['score'] is not None else 'Índice não verificado')+'</strong><p>'+str(p['same'])+' pares sem mudança de '+str(p['pairs'])+' comparáveis · '+str(p['changes'])+' mudanças observadas.</p><p>'+str(p['valid'])+' de '+str(p['total'])+' leituras confirmadas em '+str(p['days'])+' dias. Leituras confirmadas: '+pct(p['confirmed_share'])+' · intervalos comparáveis: '+pct(p['comparable_share'])+'.</p><p>Menor/maior preço confirmado da amostra: '+money(p['low'])+' / '+money(p['high'])+'. Amplitude: '+pct(p['amplitude'])+' (maior ÷ menor − 1). Não indica duração ou impacto em vendas.</p>'
        if p['rejected']:out+='<p>'+str(p['rejected'])+' registros com formato/horário inválido ou futuro desconsiderados na análise carregada.</p>'
        out+='</article>'
    out+='</div><p>Não mede estabilidade de vendas, qualidade, margem ou mercado e não prevê preços futuros. Índice alto não significa preço adequado ou ausência de mudanças entre coletas. Valores ausentes não são zero; períodos sem base não recebem índice.</p><details><summary>Conferir cobertura diária do período atual</summary><div class="ps-scroll" role="region" tabindex="0" aria-label="Cobertura diária de preços"><table><thead><tr><th>Data</th><th>Leituras</th><th>Confirmadas</th><th>Pares comparáveis</th><th>Sem mudança</th><th>Mudanças</th><th>Menor preço confirmado</th><th>Maior preço confirmado</th></tr></thead><tbody>'
    for day,bucket in sorted(data['current']['daily'].items(),reverse=True):
        out+='<tr><th scope="row">'+day.strftime('%d/%m/%Y')+'</th>'+''.join('<td>'+str(bucket[k])+'</td>' for k in ('readings','valid','pairs','same','changes'))+'<td>'+money(bucket['low'])+'</td><td>'+money(bucket['high'])+'</td></tr>'
    return out+'</tbody></table></div><p>Um par é atribuído ao dia da segunda leitura. Zero leituras significa ausência de registros nesse dia; não significa preço zero ou oferta estável.</p></details></section>'

STYLE='''<style>.price-stability{background:#102238;color:#eaf2ff;border:1px solid #34516e;border-radius:14px;padding:20px;margin:20px 0;min-width:0}.price-stability :is(h3,h4,strong){color:#eaf2ff}.price-stability p{color:#bdcce1;font-size:12px;line-height:1.7}.ps-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:14px 0}.ps-cards article{background:#182e49;border:1px solid #426184;padding:14px;border-radius:10px;overflow-wrap:anywhere}.ps-cards strong{display:block;font-size:19px}.price-stability summary{padding:12px 0;cursor:pointer;color:#b9e5ff}.ps-scroll{overflow-x:auto;max-width:100%}.price-stability table{border-collapse:collapse;width:100%;min-width:650px}.price-stability th,.price-stability td{background:#182e49!important;color:#eaf2ff!important;border-bottom:1px solid #426184;padding:12px;text-align:left;font-size:12px}.price-stability :focus-visible{outline:3px solid #85c8ec;outline-offset:3px}@media(max-width:700px){.ps-cards{grid-template-columns:1fr}.price-stability{padding:14px}}</style>'''
