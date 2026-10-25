"""Read-only sales and sampled competitiveness context; no causal attribution."""
from datetime import timedelta
from decimal import Decimal
from html import escape
from investigation_evidence import number
from listing_competitiveness import build as price_pairs
from freight_comparison import format_brl


def build(ranking, item_id, offers, end, days=7):
    result = dict(available=False, reason='A comparação aguarda vendas verificadas nos dois períodos. Dados incompletos não são zero.', rows=[])
    if not ranking.get('available'):
        return result
    metrics = (ranking.get('rows') or {}).get(item_id)
    if not metrics:
        return result
    values = {}
    for field in ('value','previous_value','orders','previous_orders','units','previous_units'):
        value = number(metrics.get(field))
        if value is None or (field not in ('value','previous_value') and value != value.to_integral_value()):
            return result
        values[field] = value
    delta = values['value'] - values['previous_value']
    limited = bool(offers.get('history_limited') or offers.get('targets_limited'))
    rows = []
    for row in price_pairs(offers,end,days):
        before, after = row['periods']['previous'], row['periods']['current']
        old = Decimal(before['above']) * 100 / before['valid'] if before['valid'] else None
        new = Decimal(after['above']) * 100 / after['valid'] if after['valid'] else None
        change = new - old if old is not None and new is not None else None
        if limited:
            status='Histórico limitado: ampliar a conferência'
        elif change is None:
            status='Comparação competitiva pendente'
        elif delta >= 0:
            status='Sem queda bruta entre os períodos'
        elif change > 0:
            status='Queda bruta e maior proporção de pares com preço próprio acima'
        else:
            status='Queda bruta sem aumento dessa proporção amostrada'
        rows.append(dict(label=row['label'],item_id=row['item_id'],previous=before,current=after,
                         previous_above_pct=old,current_above_pct=new,change_pp=change,status=status))
    return dict(available=True,values=values,delta=delta,
                delta_pct=delta*100/values['previous_value'] if values['previous_value'] else None,
                declining=delta<0,limited=limited,rows=rows)


def render(ranking,item_id,offers,end,days=7):
    model=build(ranking,item_id,offers,end,days)
    esc=lambda value:escape(str(value),quote=True)
    out=STYLE+'<section class="competitive-sales" aria-label="Vendas e competitividade observadas"><h3>Vendas e competitividade observadas</h3>'
    if not model['available']:
        return out+'<p role="status">'+model['reason']+'</p></section>'
    start=end-timedelta(days=days-1);old_end=start-timedelta(days=1);old_start=old_end-timedelta(days=days-1)
    out+='<p>Anterior: '+old_start.strftime('%d/%m/%Y')+' a '+old_end.strftime('%d/%m/%Y')+' · Atual: '+start.strftime('%d/%m/%Y')+' a '+end.strftime('%d/%m/%Y')+'.</p><div class="competitive-sales-cards">'
    values=model['values']
    for label,key in [('Valor bruto dos itens','value'),('Pedidos pagos com o anúncio','orders'),('Unidades vendidas','units')]:
        old,new=values['previous_'+key],values[key]
        text=format_brl(old)+' → '+format_brl(new) if key=='value' else str(int(old))+' → '+str(int(new))
        out+='<article><small>'+label+'</small><strong>'+esc(text)+'</strong></article>'
    percent='Sem base percentual anterior' if model['delta_pct'] is None else format(model['delta_pct'],'.2f').replace('.',',')+'%'
    out+='</div><p class="competitive-sales-delta">Variação bruta: '+esc(format_brl(model['delta']))+' · '+percent+'.</p>'
    if not model['rows']:
        return out+'<p>Sem concorrentes vinculados no recorte carregado. As vendas acima não permitem concluir perda de competitividade.</p></section>'
    out+='<details><summary>Conferir amostras por concorrente</summary><p>Deslize a tabela no celular. A proporção usa apenas pares válidos: preço próprio acima ÷ pares comparados. É distribuição das leituras carregadas, sem ponderação por tempo ou vendas.</p><div class="competitive-sales-scroll" tabindex="0" role="region" aria-label="Vendas e amostras competitivas por concorrente"><table><thead><tr><th scope="col">Concorrente vinculado</th><th scope="col">Anterior</th><th scope="col">Atual</th><th scope="col">Diferença da proporção</th><th scope="col">Conferência sugerida</th></tr></thead><tbody>'
    for row in model['rows']:
        out+='<tr><th scope="row">'+esc(row['label'])+'<small>'+esc(row['item_id'])+'</small></th>'
        for name in ('previous','current'):
            sample=row[name];pct=row[name+'_above_pct']
            text=str(sample['valid'])+'/'+str(sample['observed'])+' pares válidos / leituras'
            detail='Sem pares comparáveis' if pct is None else str(sample['above'])+'/'+str(sample['valid'])+' com preço próprio acima · '+format(pct,'.2f').replace('.',',')+'%'
            out+='<td>'+text+'<small>'+detail+'</small></td>'
        change=row['change_pp']
        out+='<td>'+('Indisponível' if change is None else format(change,'.2f').replace('.',',')+' p.p.')+'</td><td>'+esc(row['status'])+'</td></tr>'
    out+='</tbody></table></div></details><p>Conferir equivalência de produto, quantidade, variação, preço final, frete e prazo antes de agir. As janelas de vendas e leituras são as mesmas, mas amostras podem ter horários e quantidades diferentes. Coincidência não comprova causa da queda, conversão perdida, vendas perdidas por preço ou posição de mercado. Nenhum preço é alterado.</p>'
    if model['limited']:out+='<p>Histórico limitado aos vínculos e observações carregados; nenhuma conclusão de aumento de exposição competitiva é emitida.</p>'
    return out+'</section>'


STYLE='''<style>
body .conteudo .competitive-sales{background:#102238;color:#eaf2ff;border:1px solid #34516e;border-radius:14px;padding:20px;margin:18px 0;max-width:100%;min-width:0;box-sizing:border-box}body .conteudo .competitive-sales h3{color:#eaf2ff;margin-top:0}.competitive-sales p,.competitive-sales small{color:#bdcce1;font-size:12px;line-height:1.7}.competitive-sales-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.competitive-sales article{background:#182e49;border:1px solid #426184;border-radius:10px;padding:14px;display:grid;gap:10px;overflow-wrap:anywhere}.competitive-sales strong{font-size:17px}.competitive-sales small{display:block}.competitive-sales summary{color:#b9e5ff;cursor:pointer;padding:12px 0;font-weight:700}.competitive-sales-scroll{overflow-x:auto;max-width:100%}.competitive-sales table{width:100%;min-width:920px;border-collapse:collapse}.competitive-sales th,.competitive-sales td{padding:12px;border-bottom:1px solid #426184;text-align:left;font-size:12px;vertical-align:top;min-width:140px;overflow-wrap:anywhere}body .conteudo .competitive-sales :is(th,td){background:#182e49;color:#eaf2ff}.competitive-sales :focus-visible{outline:3px solid #85c8ec;outline-offset:3px}@media(max-width:700px){.competitive-sales-cards{grid-template-columns:1fr}body .conteudo .competitive-sales{padding:14px}}
</style>'''
