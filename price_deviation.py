"""Explicit sample-reference price rule, not a causal or predictive anomaly model."""
from datetime import datetime,timedelta
from decimal import Decimal,ROUND_HALF_UP
from html import escape
import time
from offer_history import BR,grouped_readings,confirmed_price
from price_stability import build as coverage

THRESHOLD=Decimal('20')


def build(rows,end,now=None):
    now=int(time.time()) if now is None else now
    pending=lambda reason:dict(status='unknown',reason=reason)
    data=coverage(rows,end,now=now)
    if data['limited']:return pending('Base superior a 5.000 registros; conferência pendente.')
    previous=data['previous']
    if previous['score'] is None:return pending('Período anterior sem amostra suficiente pelos critérios de cobertura do painel de constância.')
    first=int(datetime.combine(end-timedelta(days=6),datetime.min.time(),BR).timestamp())
    stop=int(datetime.combine(end+timedelta(days=1),datetime.min.time(),BR).timestamp())
    groups=grouped_readings([r for r in rows if isinstance(r,dict)])
    current=[(stamp,group) for stamp,group in groups if first<=stamp<stop]
    if not current:return pending('Nenhuma leitura no período atual; preço ausente não é zero.')
    stamp,last=current[-1]
    if not 0<=now-stamp<=21600:return pending('A última leitura está antiga ou no futuro; confirme o preço atual.')
    price=confirmed_price(last[0]) if len(last)==1 else None
    if price is None:return pending('A última leitura não tem preço único e confirmado; não usamos uma leitura anterior como substituta.')
    baseline=[]
    old_start=int(datetime.combine(previous['start'],datetime.min.time(),BR).timestamp())
    for t,group in groups:
        if old_start<=t<first and len(group)==1:
            p=confirmed_price(group[0])
            if p is not None:baseline.append(p)
    baseline.sort();n=len(baseline)
    if not n:return pending('Referência anterior não verificada.')
    median=baseline[n//2] if n%2 else (baseline[n//2-1]+baseline[n//2])/2
    delta=(price-median)*100/median
    outside=price<baseline[0] or price>baseline[-1]
    alert=outside and abs(delta)>=THRESHOLD
    return dict(status='alert' if alert else 'no_signal',price=price,stamp=stamp,median=median,
                low=baseline[0],high=baseline[-1],count=n,days=previous['days'],delta=delta,
                outside=outside,old_start=previous['start'],old_end=previous['end'])


def render(rows,end,now=None):
    data=build(rows,end,now);esc=lambda v:escape(str(v),quote=True)
    def money(v):return 'R$ '+format(v.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP),'f').replace('.',',')
    out=STYLE+'<section class="price-deviation"><h3>Desvio de preço contra a referência anterior</h3><p>Regra de conferência: preço recente fora do menor/maior preço confirmado anterior e diferença absoluta de pelo menos 20% da mediana anterior. Não é um modelo de anomalias validado nem recomendação de alteração de preço.</p>'
    if data['status']=='unknown':return out+'<p role="status">'+data['reason']+'</p></section>'
    label='Sinal para conferir o preço e sua origem' if data['status']=='alert' else 'Regra não acionada nesta leitura'
    out+='<p class="pd-state"><strong>'+label+'</strong></p><div class="pd-cards">'
    for label,value in [('Último preço confirmado',money(data['price'])),('Mediana anterior',money(data['median'])),('Diferença da mediana',format(data['delta'].quantize(Decimal('0.1'),rounding=ROUND_HALF_UP),'f').replace('.',',')+'%')]:out+='<article><small>'+label+'</small><strong>'+esc(value)+'</strong></article>'
    out+='</div><p>Leitura: '+datetime.fromtimestamp(data['stamp'],BR).strftime('%d/%m/%Y %H:%M')+' · Brasília. Referência: '+data['old_start'].strftime('%d/%m/%Y')+' a '+data['old_end'].strftime('%d/%m/%Y')+', '+str(data['count'])+' leituras confirmadas em '+str(data['days'])+' dias; menor '+money(data['low'])+' e maior '+money(data['high'])+'.</p><details><summary>Critérios e limites</summary><p>Usa a mediana das leituras anteriores, com peso igual por leitura. Exige a suficiência do painel de constância e última leitura única, positiva e confirmada com até seis horas. Falha recente não é substituída por preço anterior. Ausência de sinal não comprova preço correto ou ausência de anomalia. Promoções, mudanças legítimas e lacunas podem explicar diferenças; não atribuímos causa, margem ou impacto em vendas.</p></details></section>'
    return out

STYLE='''<style>.price-deviation{background:#102238;border:1px solid #34516e;border-radius:14px;color:#eaf2ff;padding:20px;margin:20px 0;min-width:0}.price-deviation :is(h3,strong){color:#eaf2ff}.price-deviation p,.price-deviation small{color:#bdcce1;font-size:12px;line-height:1.7}.pd-state{padding:12px;border:1px solid #426184;border-radius:8px;background:#182e49}.pd-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.pd-cards article{display:grid;gap:8px;padding:14px;background:#182e49;border:1px solid #426184;border-radius:10px;overflow-wrap:anywhere}.pd-cards strong{font-size:20px}.price-deviation summary{padding:12px 0;cursor:pointer;color:#b9e5ff}.price-deviation :focus-visible{outline:3px solid #85c8ec;outline-offset:3px}@media(max-width:700px){.pd-cards{grid-template-columns:1fr}.price-deviation{padding:14px}}</style>'''
