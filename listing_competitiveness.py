"""Time-aligned observed price distances, never lost-sales attribution."""
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime,timedelta
from decimal import Decimal
from html import escape
from sales_metrics import SAO_PAULO
from listing_priority_evidence import nonnegative
from freight_comparison import format_brl

MAX_GAP=6*3600


def build(data,end,days=7):
    start=int(datetime.combine(end-timedelta(days=days*2-1),datetime.min.time(),SAO_PAULO).timestamp())
    stop=int(datetime.combine(end+timedelta(days=1),datetime.min.time(),SAO_PAULO).timestamp())
    current=int(datetime.combine(end-timedelta(days=days-1),datetime.min.time(),SAO_PAULO).timestamp())
    own=defaultdict(list)
    for row in data.get('own',[]):
        stamp=row.get('observed_at')
        if type(stamp) is int and start<=stamp<stop:own[stamp].append(row)
    stamps=sorted(own)
    own_prices={};own_segments={};segment=0
    for stamp in stamps:
        records=own[stamp]
        item=records[0] if len(records)==1 else {}
        price=nonnegative(item.get('price'))
        if item.get('confirmed') is not True or price is None or price<=0:
            price=None;segment+=1
        own_prices[stamp]=price
        own_segments[stamp]=segment
    result=[]
    targets={r['id']:r for r in data.get('targets',[])[:20]}
    competitors=defaultdict(lambda:defaultdict(list))
    for row in data.get('competitors',[]):
        stamp=row.get('observed_at');target=row.get('target_id')
        if target in targets and type(stamp) is int and start<=stamp<stop:
            competitors[target][stamp].append(row)
    for tid,target in targets.items():
        previous=None;latest=None;valid=0;observed=0
        periods={name:dict(observed=0,valid=0,above=0,equal=0,below=0)
                 for name in ('previous','current')}
        for stamp,rows in sorted(competitors[tid].items()):
            period=periods['current' if stamp>=current else 'previous']
            period['observed']+=len(rows)
            if stamp>=current:observed+=len(rows)
            point=None;index=bisect_right(stamps,stamp)-1
            row=rows[0] if len(rows)==1 else {}
            competitor=nonnegative(row.get('price'))
            if index>=0 and stamp-stamps[index]<=MAX_GAP and not row.get('error') and competitor is not None and competitor>0:
                own_stamp=stamps[index];price=own_prices[own_stamp]
                if price is not None:
                    gap=price-competitor
                    point=dict(at=stamp,own_at=own_stamp,own=price,competitor=competitor,gap=gap,
                        gap_pct=gap*100/competitor,delta_pp=None,own_segment=own_segments[own_stamp])
                    if previous and 0<stamp-previous['at']<=MAX_GAP and previous['own_segment']==point['own_segment']:
                        point['delta_pp']=point['gap_pct']-previous['gap_pct']
                    period['valid']+=1
                    period['above' if gap>0 else 'below' if gap<0 else 'equal']+=1
                    if stamp>=current:valid+=1
            previous=point # failed/ambiguous observations break the comparison
            if stamp>=current:latest=point
        result.append(dict(item_id=str(target['item_id']),label=str(target.get('label') or target['item_id']),
                           observed=observed,valid=valid,latest=latest,periods=periods))
    return result


def render(data,end,days=7):
    rows=build(data,end,days)
    if not rows:return ''
    def stamp(value):return datetime.fromtimestamp(value,SAO_PAULO).strftime('%d/%m/%Y %H:%M')
    out='<section class="price-comparison"><h3>Histórico da distância entre preços</h3><p>Últimos '+str(days)+' dias encerrados. Cada leitura do concorrente usa somente a última consulta própria anterior ou simultânea, separada por até seis horas. Falha, leitura duplicada ou preço inválido interrompe a comparação.</p><div style="overflow-x:auto"><table style="min-width:950px"><thead><tr><th>Oferta vinculada</th><th>Amostras comparadas</th><th>Último par no período</th><th>Preço próprio</th><th>Concorrente</th><th>Distância própria − concorrente</th><th>Variação da distância</th></tr></thead><tbody>'
    def sample(period):
        if not period['observed']:
            return 'Sem leituras no período'
        text=str(period['valid'])+'/'+str(period['observed'])+' pares válidos / leituras'
        if period['valid']:
            text+='<br>Próprio acima: '+str(period['above'])+' · igual: '+str(period['equal'])+' · abaixo: '+str(period['below'])
        else:text+='<br>Sem pares comparáveis'
        return text
    for row in rows:
        out+='<tr><th scope="row">'+escape(row['label'])+' · '+escape(row['item_id'])+'</th><td class="price-samples">'+'<b>Atual: '+(end-timedelta(days=days-1)).strftime('%d/%m')+' a '+end.strftime('%d/%m/%Y')+'</b><br>'+sample(row['periods']['current'])+'<br><b>Anterior: '+(end-timedelta(days=days*2-1)).strftime('%d/%m')+' a '+(end-timedelta(days=days)).strftime('%d/%m/%Y')+'</b><br>'+sample(row['periods']['previous'])+'</td>'
        p=row['latest']
        if p is None:
            out+='<td colspan="5">Última leitura do período sem par comparável, ou sem observações no período. Não usar um par anterior como confirmação atual.</td></tr>'
            continue
        out+='<td>Concorrente: '+stamp(p['at'])+'<br>Próprio: '+stamp(p['own_at'])+' · Brasília</td><td>'+format_brl(p['own'])+'</td><td>'+format_brl(p['competitor'])+'</td><td>'+format_brl(p['gap'])+' ('+format(p['gap_pct'],'.2f').replace('.',',')+'%)</td><td>'
        if p['delta_pp'] is None:out+='Sem dois pares consecutivos próximos'
        else:
            direction='Aumentou' if p['delta_pp']>0 else 'Diminuiu' if p['delta_pp']<0 else 'Sem variação entre os pares'
            out+=direction+': '+format(p['delta_pp'],'.2f').replace('.',',')+' p.p.'
        out+='</td></tr>'
    out+='</tbody></table></div><p>Distância percentual = (preço próprio − concorrente) ÷ preço concorrente. Positiva indica preço próprio acima; negativa, abaixo. A variação usa dois pares consecutivos separados por até seis horas. As contagens acima/igual/abaixo descrevem somente os pares válidos carregados, sem ponderação por tempo ou vendas. Não representam dias, participação de mercado ou tempo em cada condição. O total de leituras refere-se às consultas dos concorrentes. Falhas e leituras duplicadas entram nesse total, mas não nos pares válidos. Sem leituras não significa preço estável. Não é média do período, posição de mercado ou preço atual.</p><p>Vínculo informado pelo usuário não comprova equivalência de produto, quantidade, variação, frete, prazo ou cupons. Revise essas condições antes de agir. Não diagnostica perda de vendas ou conversão, não atribui causalidade e não recomenda reduzir preço automaticamente.</p>'
    if data.get('targets_limited') or data.get('history_limited'):
        out+='<p>Histórico limitado aos vínculos e observações carregados. Não representa todo o monitoramento.</p>'
    return out+'</section><style>.conteudo .price-comparison{padding:20px;border:1px solid #34516e;border-radius:14px;background:#102238;color:#eaf2ff;margin:18px 0}.conteudo .price-comparison h3{color:#eaf2ff}.price-comparison p{color:#bdcce1;line-height:1.65}body .conteudo section.price-comparison table th,body .conteudo section.price-comparison table td{padding:12px;background:#182e49;color:#eaf2ff;border-bottom:1px solid #34516e;text-align:left}.price-comparison{overflow-wrap:anywhere}.price-comparison .price-samples{min-width:230px;line-height:1.8}.price-comparison td,.price-comparison th{vertical-align:top}</style>'
