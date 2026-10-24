"""Historical per-unit averages from already verified listing-period totals."""
from decimal import Decimal
from html import escape
from listing_profitability import COMPONENTS
from freight_comparison import format_brl


def unit_comparison(comparison):
    if not comparison.get('available'):
        return dict(available=False, reason='A comparação por unidade exige os dois períodos documentados.', rows=[])
    current,previous=comparison['current'],comparison['previous']
    units=[previous.get('units'),current.get('units')]
    if any(not isinstance(v,Decimal) or not v.is_finite() or v<=0 or v!=v.to_integral_value() for v in units):
        return dict(available=False, reason='A comparação por unidade exige unidades verificadas maiores que zero nos dois períodos.', rows=[])
    old_count,new_count=units
    values=[('revenue','Valor bruto médio dos itens',previous['revenue'],current['revenue'])]
    values += [(k,label,previous['costs'][k],current['costs'][k]) for k,label in COMPONENTS.items()]
    values += [('contribution','Contribuição média documentada',previous['contribution'],current['contribution'])]
    rows=[]
    for key,label,old,new in values:
        before,now=old/old_count,new/new_count
        rows.append(dict(key=key,label=label,previous=before,current=now,delta=now-before))
    return dict(available=True,rows=rows,previous_units=old_count,current_units=new_count)


def render_unit_comparison(comparison):
    result=unit_comparison(comparison)
    out='<section class="pf-card" id="pf-unidades" aria-label="Comparação financeira por unidade"><h3>Volume e valores médios por unidade</h3>'
    if not result['available']:
        return out+'<p class="pf-alert">'+escape(result['reason'])+'</p></section>'
    out+='<p>Unidades verificadas: '+str(result['previous_units'])+' no período anterior → '+str(result['current_units'])+' no atual. Médias históricas do mesmo anúncio, calculadas com os totais documentados de cada período.</p><div class="pf-table"><table class="pf-unit-table"><caption>R$ por unidade vendida · anterior, atual e variação · role a tabela no celular</caption><thead><tr><th>Componente</th><th>Anterior por unidade</th><th>Atual por unidade</th><th>Variação por unidade</th></tr></thead><tbody>'
    for row in result['rows']:
        out+='<tr><td>'+escape(row['label'])+'</td><td>'+format_brl(row['previous'])+'</td><td>'+format_brl(row['current'])+'</td><td>'+('+' if row['delta']>0 else '')+format_brl(row['delta'])+'</td></tr>'
    return out+'</tbody></table></div><p>A média permite comparar valores com volumes diferentes, mas pode mudar com o mix de variações, descontos e condições das vendas. Não representa o custo individual de cada unidade, preço recomendado ou projeção de recuperação. Despesas fixas não incluídas. Valores exibidos arredondados a centavos; a soma das linhas exibidas pode diferir por arredondamento.</p></section>'
