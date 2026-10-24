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
    result=[]
    targets={r['id']:r for r in data.get('targets',[])[:20]}
    competitors=defaultdict(lambda:defaultdict(list))
    for row in data.get('competitors',[]):
        stamp=row.get('observed_at');target=row.get('target_id')
        if target in targets and type(stamp) is int and start<=stamp<stop:
            competitors[target][stamp].append(row)
    for tid,target in targets.items():
        previous=None;latest=None;valid=0;observed=0
        for stamp,rows in sorted(competitors[tid].items()):
            if stamp>=current:observed+=len(rows)
            point=None;index=bisect_right(stamps,stamp)-1
            row=rows[0] if len(rows)==1 else {}
            competitor=nonnegative(row.get('price'))
            if index>=0 and stamp-stamps[index]<=MAX_GAP and not row.get('error') and competitor is not None and competitor>0:
                own_stamp=stamps[index];source=own[own_stamp]
                item=source[0] if len(source)==1 else {}
                price=nonnegative(item.get('price'))
                if item.get('confirmed') is True and price is not None and price>0:
                    gap=price-competitor
                    point=dict(at=stamp,own_at=own_stamp,own=price,competitor=competitor,gap=gap,
                        gap_pct=gap*100/competitor,delta_pp=None)
                    if previous and 0<stamp-previous['at']<=MAX_GAP:
                        point['delta_pp']=point['gap_pct']-previous['gap_pct']
                    if stamp>=current:valid+=1
            previous=point # failed/ambiguous observations break the comparison
            if stamp>=current:latest=point
        result.append(dict(item_id=str(target['item_id']),label=str(target.get('label') or target['item_id']),
                           observed=observed,valid=valid,latest=latest))
    return result


def render(data,end,days=7):
    rows=build(data,end,days)
    if not rows:return ''
    def stamp(value):return datetime.fromtimestamp(value,SAO_PAULO).strftime('%d/%m/%Y %H:%M')
    out='<section class="price-comparison"><h3>Histórico da distância entre preços</h3><p>Últimos '+str(days)+' dias encerrados. Cada leitura do concorrente usa somente a última consulta própria anterior ou simultânea, separada por até seis horas. Falha, leitura duplicada ou preço inválido interrompe a comparação.</p><div style="overflow-x:auto"><table style="min-width:950px"><thead><tr><th>Oferta vinculada</th><th>Pares válidos / leituras</th><th>Último par no período</th><th>Preço próprio</th><th>Concorrente</th><th>Distância própria − concorrente</th><th>Variação da distância</th></tr></thead><tbody>'
    for row in rows:
        out+='<tr><th scope="row">'+escape(row['label'])+' · '+escape(row['item_id'])+'</th><td>'+str(row['valid'])+'/'+str(row['observed'])+'</td>'
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
    out+='</tbody></table></div><p>Distância percentual = (preço próprio − concorrente) ÷ preço concorrente. Positiva indica preço próprio acima; negativa, abaixo. A variação usa dois pares consecutivos separados por até seis horas. Não é média do período, posição de mercado ou preço atual.</p><p>Vínculo informado pelo usuário não comprova equivalência de produto, quantidade, variação, frete, prazo ou cupons. Revise essas condições antes de agir. Não diagnostica perda de vendas ou conversão, não atribui causalidade e não recomenda reduzir preço automaticamente.</p>'
    if data.get('targets_limited') or data.get('history_limited'):
        out+='<p>Histórico limitado aos vínculos e observações carregados. Não representa todo o monitoramento.</p>'
    return out+'</section><style>.conteudo .price-comparison{padding:20px;border:1px solid #34516e;border-radius:14px;background:#102238;color:#eaf2ff;margin:18px 0}.conteudo .price-comparison h3{color:#eaf2ff}.price-comparison p{color:#bdcce1;line-height:1.65}.conteudo .price-comparison th,.conteudo .price-comparison td{padding:12px;background:#182e49;color:#eaf2ff;border-bottom:1px solid #34516e;text-align:left}.price-comparison{overflow-wrap:anywhere}</style>'
