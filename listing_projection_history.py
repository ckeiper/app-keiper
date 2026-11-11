"""Retrospective fixed-mean check on verified sales; never forecasts future dates."""
from datetime import date,timedelta
from decimal import Decimal
from html import escape
from section_help import STYLE as HELP_STYLE, section_help
from listing_weekly_pattern import STYLE


def evaluate(data):
    result=dict(available=False,reason=data.get('reason') or 'Série diária não verificável.',rows=[])
    if data.get('available') is not True:return result
    start,end=data.get('start'),data.get('end');daily=data.get('daily')
    if (type(start) is not date or type(end) is not date or end!=start+timedelta(days=55)
            or data.get('covered')!=56 or not isinstance(daily,list) or len(daily)!=56):return result
    if any(not isinstance(r,dict) or r.get('day')!=start+timedelta(days=i)
           or type(r.get('units')) is not int or r['units']<0 for i,r in enumerate(daily)):return result
    rows=[]
    for offset in (0,7,14,21):
        training=daily[offset:offset+28];test=daily[offset+28:offset+35]
        training_units=sum(r['units'] for r in training)
        estimate=Decimal(training_units)/4;actual=sum(r['units'] for r in test)
        error=estimate-actual
        previous_week_units = sum(r['units'] for r in training[-7:])
        rows.append(dict(training_start=training[0]['day'],training_end=training[-1]['day'],
                         test_start=test[0]['day'],test_end=test[-1]['day'],training_units=training_units,
                         estimate=estimate,actual=actual,error=error,absolute_error=abs(error),
                         previous_week_units=previous_week_units,
                         previous_week_absolute_error=abs(previous_week_units-actual)))
    absolute=sum(r['absolute_error'] for r in rows);actual=sum(r['actual'] for r in rows)
    return dict(available=True,reason=None,rows=rows,estimate=sum(r['estimate'] for r in rows),actual=actual,
                mae=absolute/4,previous_week_mae=Decimal(sum(r['previous_week_absolute_error'] for r in rows))/4,
                bias=sum(r['error'] for r in rows)/4,
                absolute_error_percent=absolute*100/actual if actual else None)


def render(cid,item,shop,data):
    model=evaluate(data);esc=lambda v:escape(str(v),quote=True)
    number=lambda v:format(v,'.1f').replace('.',',')
    signed=lambda v:('+' if v>0 else '')+number(v)
    fmt=lambda d:d.strftime('%d/%m/%Y')
    path='/anuncios/'+str(int(cid))+'/'+item
    help_copy = (
        '<p>Simulação retrospectiva. Em cada rodada, a estimativa semanal usa as unidades dos 28 dias anteriores divididas por quatro. A segunda referência usa os sete dias imediatamente anteriores. A semana em curso fica fora.</p>'
        '<p>Janelas fixas: 28 dias de base e os sete dias seguintes para conferência, avançando uma semana em cada rodada. Todas as quatro rodadas aparecem, sem escolher as mais favoráveis. Erro absoluto médio = soma dos erros absolutos ÷ 4; desvio médio = soma de estimado menos realizado ÷ 4. O percentual usa soma dos erros absolutos ÷ soma das unidades realizadas × 100 e pode superar 100%.</p>'
        '<p>As estimativas podem ter frações de unidade porque são médias. Valores são exibidos com uma casa decimal; cálculos usam os valores completos. Sem unidades realizadas, não há denominador para o percentual.</p>'
        '<p>Usa registros atualmente verificados. Não reconstitui quais informações estavam disponíveis nas datas passadas. Mede vendas observadas, sem estimar demanda reprimida ou descontar pausas, ruptura, preço, promoções e feriados. Quatro rodadas não certificam precisão futura, sazonalidade ou data de ruptura; nenhuma projeção futura ou alteração de estoque é produzida.</p>'
    )
    out=STYLE+LOCAL_STYLE+HELP_STYLE+'<section class="wp ph"><header>'+section_help('Conferência histórica da média de vendas','Método e limites da conferência histórica',help_copy)+'<p>'+esc(shop.get('titulo') or item)+' · '+esc(item)+'</p><p>'+fmt(data['start'])+' a '+fmt(data['end'])+' · oito semanas completas · Brasília</p><nav class="ph-links"><a href="'+esc(path+'/padrao-semanal')+'">Padrão semanal e cobertura</a><a href="/diagnostico/'+str(int(cid))+'/'+esc(item)+'">Diagnóstico</a></nav></header>'
    out+='<div class="wp-coverage"><strong>Cobertura da loja: '+str(data['covered'])+' de 56 dias</strong><progress max="56" value="'+str(data['covered'])+'" aria-label="Dias com cobertura de vendas">'+str(data['covered'])+'/56</progress></div>'
    if not model['available']:
        out+='<p class="wp-notice" role="status">Conferência indisponível · '+esc(model['reason'])+'</p><p>As quatro comparações serão exibidas somente com a janela diária inteira verificada.</p>'
    else:
        percentage=number(model['absolute_error_percent'])+'%' if model['absolute_error_percent'] is not None else '—'
        out+='<div class="wp-stats"><article><strong>'+number(model['mae'])+'</strong><span>Erro absoluto médio · unidades por semana</span></article><article><strong>'+signed(model['bias'])+'</strong><span>Desvio médio · estimado menos realizado</span></article><article><strong>'+percentage+'</strong><span>Erro absoluto acumulado ÷ unidades realizadas</span></article></div>'
        out+='<p>Somatório das quatro semanas: '+number(model['estimate'])+' unidades estimadas e '+str(model['actual'])+' realizadas. Desvio positivo indica estimativa acima do realizado; negativo indica abaixo.</p>'
        if model['absolute_error_percent'] is None:out+='<p class="ph-zero">Nenhuma unidade realizada nas semanas testadas. O percentual não é calculado; os erros em unidades continuam disponíveis.</p>'
        out+='<div class="ph-chart" role="img" aria-label="Unidades estimadas pela média anterior e realizadas em cada semana testada; valores detalhados na tabela">'
        maximum=max([max(r['estimate'],Decimal(r['actual'])) for r in model['rows']]+[Decimal(1)])
        for row in model['rows']:
            out+='<div class="wp-cmp-day"><h3>'+fmt(row['test_start'])+' a '+fmt(row['test_end'])+'</h3><p>Base anterior: '+fmt(row['training_start'])+' a '+fmt(row['training_end'])+'</p>'
            for value,label,cls in [(row['estimate'],'Estimado','wp-cmp-previous'),(Decimal(row['actual']),'Real','wp-cmp-recent')]:
                width=number(value*100/maximum).replace(',','.')
                out+='<div class="wp-cmp-series"><span>'+label+'</span><div class="wp-cmp-track"><div class="'+cls+'" style="width:'+width+'%"></div></div><strong>'+number(value)+'</strong></div>'
            out+='</div>'
        out+='</div><div class="wp-table-wrap ph-table" role="region" aria-label="Erros das quatro semanas testadas" tabindex="0"><table><caption>Estimado pela média dos 28 dias anteriores × realizado na semana seguinte</caption><thead><tr><th scope="col">Base anterior</th><th scope="col">Semana testada</th><th scope="col">Estimado</th><th scope="col">Real</th><th scope="col">Erro: estimado − real</th><th scope="col">Erro absoluto</th></tr></thead><tbody>'
        for r in model['rows']:
            out+='<tr><th scope="row">'+fmt(r['training_start'])+' a '+fmt(r['training_end'])+'</th><td>'+fmt(r['test_start'])+' a '+fmt(r['test_end'])+'</td><td>'+number(r['estimate'])+'</td><td>'+str(r['actual'])+'</td><td>'+signed(r['error'])+'</td><td>'+number(r['absolute_error'])+'</td></tr>'
        out+='</tbody></table></div>'
        out+='<h3>Comparação com a semana anterior</h3>'
        out+='<p>Erro absoluto médio nas mesmas quatro rodadas · média de quatro semanas: <strong>'+number(model['mae'])+'</strong> · semana anterior: <strong>'+number(model['previous_week_mae'])+'</strong> unidades por semana.</p>'
        out+='<div class="wp-table-wrap" role="region" aria-label="Comparação dos erros por semana" tabindex="0"><table style="min-width:560px"><caption>Erros absolutos por semana testada</caption><thead><tr><th scope="col">Semana testada</th><th scope="col">Média de quatro semanas</th><th scope="col">Semana anterior</th></tr></thead><tbody>'
        for row in model['rows']:
            out+='<tr><th scope="row">'+fmt(row['test_start'])+' a '+fmt(row['test_end'])+'</th><td>'+number(row['absolute_error'])+'</td><td>'+number(row['previous_week_absolute_error'])+'</td></tr>'
        out+='</tbody></table></div>'
    out+='</section>'
    return out


LOCAL_STYLE='''<style>.ph-links{display:flex;gap:16px;flex-wrap:wrap}.ph-chart{display:grid;gap:22px;margin:24px 0}.ph-chart h3,.ph-chart p{margin:0}.ph .wp-cmp-series{grid-template-columns:64px 1fr 78px;min-width:0}.ph .wp-cmp-series>strong{overflow-wrap:anywhere;min-width:0}.ph table{min-width:850px}.ph-zero{border-left:3px solid #e6bb68;padding-left:12px}@media(max-width:650px){.ph .wp-cmp-series{grid-template-columns:55px 1fr 68px}}</style>'''
