"""Signed ledger arithmetic, not bank reconciliation or profit calculation."""
from decimal import Decimal,InvalidOperation
from freight_comparison import format_brl


def signed_amount(value):
    if value is None or isinstance(value,bool) or value=='':
        return None
    try:
        number=Decimal(str(value))
        if not number.is_finite() or abs(number)>Decimal('999999999999.99'):
            return None
        return number if number==number.quantize(Decimal('.01')) else None
    except (ValueError,TypeError,InvalidOperation):
        return None


def empty(available):
    return dict(available=available,valid_rows=0,invalid_rows=0,inconsistent_rows=0,
        gross_total='0.00',fees_total='0.00',net_total='0.00',difference_total='0.00',groups={},review_rows=[])


def _add(result,gross,fees,net):
    values=[signed_amount(v) for v in (gross,fees,net)]
    if any(v is None for v in values):
        result['invalid_rows']+=1
        return
    gross,fees,net=values
    diff=gross-fees-net
    result['valid_rows']+=1
    # One cent is a real discrepancy; no rounding away a documented cent.
    result['inconsistent_rows']+=abs(diff)>=Decimal('.01')
    for key,value in [('gross_total',gross),('fees_total',fees),('net_total',net),('difference_total',diff)]:
        result[key]=str(Decimal(result[key])+value)


GROUPS = {'vendas':'Vendas','ads':'Publicidade','full':'Serviços Full','envios':'Envios',
          'tributos':'Tributos','pagamentos':'Pagamento de faturas','outros':'Outros / tipo não identificado'}
TYPES = {'venda':'vendas','anuncios mclicks':'ads','armazenamento full':'full',
         'coleta full':'full','envio':'envios','cobranca de difal':'tributos',
         'pagamento de faturas':'pagamentos'}


def accumulate(result,gross,fees,net,operation_type=None,line_number=None):
    from freight_reconciliation import normalize
    category=TYPES.get(normalize(operation_type),'outros')
    group=result['groups'].setdefault(category,{k:v for k,v in empty(True).items() if k not in ('available','groups','review_rows')})
    values=[signed_amount(v) for v in (gross,fees,net)]
    invalid=[label for label,value in zip(('Bruto','Tarifas','Líquido após tarifas'),values) if value is None]
    difference=not invalid and abs(values[0]-values[1]-values[2])>=Decimal('.01')
    if (invalid or difference) and type(line_number) is int and line_number>=4 and len(result['review_rows'])<20:
        result['review_rows'].append(dict(line=line_number,category=category,
            reason='Valores ausentes ou inválidos: '+', '.join(invalid) if invalid else 'Diferença aritmética de pelo menos R$ 0,01'))
    _add(result,gross,fees,net)
    _add(group,gross,fees,net)


def render_groups(result):
    groups=result.get('groups') or {}
    if not groups:
        return ''
    out='<h3>Movimentos por grupo</h3><p>Tipos conhecidos do relatório separados por finalidade. Tipos não mapeados ficam em Outros, sem presumir que sejam ajustes. Quantidades representam lançamentos, não pedidos únicos.</p><div style="overflow-x:auto"><table class="ledger-groups" style="min-width:750px;width:100%"><thead><tr><th>Grupo</th><th>Linhas válidas</th><th>Linhas inválidas</th><th>Diferenças</th><th>Bruto</th><th>Tarifas</th><th>Líquido após tarifas</th></tr></thead><tbody>'
    for key,label in GROUPS.items():
        group=groups.get(key)
        if not group:
            continue
        out+='<tr><th scope="row">'+label+'</th>'
        for field in ('valid_rows','invalid_rows','inconsistent_rows'):
            out+='<td>'+str(group[field])+'</td>'
        for field in ('gross_total','fees_total','net_total'):
            out+='<td>'+(format_brl(group[field]) if group['valid_rows'] else 'Indisponível')+'</td>'
        out+='</tr>'
    out+='</tbody></table></div>'
    if result.get('review_rows'):
        out+='<details><summary>Linhas para conferir no arquivo original</summary><ul>'
        for row in result['review_rows']:
            out+='<li>Linha '+str(row['line'])+' · '+GROUPS[row['category']]+' · '+row['reason']+'</li>'
        out+='</ul><p>Primeiras '+str(len(result['review_rows']))+' linhas com problema, limitadas a 20. Os números são as linhas da aba DAILY_CONCILIATION, incluindo os cabeçalhos. Não armazenamos aqui os valores ou identificadores dessas linhas.</p></details>'
    return out+'<p>Bruto, tarifas e líquido de cada grupo usam somente suas linhas com os três valores válidos. Sinais negativos e repetições são preservados. Não somar esse relatório a outros com datas sobrepostas; não comprova recebimento bancário.</p>'


def render(result):
    if not result:
        return '' # older imported versions have no financial diagnostic
    out='<style>.conteudo .ledger-check{background:#102238;color:#eaf2ff;border:1px solid #34516e}.conteudo .ledger-check h3{color:#eaf2ff}.ledger-check p{color:#bdcce1;line-height:1.65}.ledger-check .frete-metricas{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:12px}.ledger-check .frete-metrica{display:flex;flex-direction:column;gap:8px;padding:16px;background:#182e49;border:1px solid #34516e;border-radius:12px}.ledger-check strong{font-size:22px;overflow-wrap:anywhere}.ledger-check span{color:#bdcce1}.conteudo .ledger-check .ledger-groups th{background:#182e49;color:#eaf2ff}.ledger-groups td,.ledger-groups th{padding:12px;border-bottom:1px solid #34516e;text-align:left;color:#eaf2ff}</style><section class="card frete-resultado ledger-check"><h3>Conferência de bruto, tarifas e líquido</h3>'
    if not result['available']:
        return out+'<p>Coluna Valor bruto (=) ausente ou ambígua. Conferência financeira indisponível para este arquivo.</p></section>'
    if not result['valid_rows']:
        return out+'<p>Nenhuma linha com os três valores financeiros válidos. Valores ausentes ou inválidos não são zero.</p>'+render_groups(result)+'</section>'
    out+='<p>'+str(result['valid_rows'])+' lançamentos comparáveis; '+str(result['invalid_rows'])+' com valores incompletos ou inválidos; '+str(result['inconsistent_rows'])+' com diferença de pelo menos R$ 0,01.</p><div class="frete-metricas">'
    for label,key in [('Bruto informado','gross_total'),('Tarifas informadas','fees_total'),('Líquido após tarifas informado','net_total')]:
        out+='<div class="frete-metrica"><span>'+label+'</span><strong>'+format_brl(result[key])+'</strong></div>'
    return out+'</div><p>Conferência por linha: valor bruto menos tarifas versus líquido após tarifas. Sinais negativos são preservados. A contagem de diferenças não é compensada entre linhas; sua soma algébrica é '+format_brl(result['difference_total'])+'.</p><p>Totais apenas das linhas com os três valores válidos, incluindo repetições. O arquivo mistura tipos de movimento; estes totais não são faturamento de vendas, lucro, saldo bancário ou repasse recebido. Tarifas pós-pagas não são descontadas novamente nesta identidade. Uma diferença pede conferência do relatório, sem comprovar cobrança indevida.</p>'+render_groups(result)+'</section>'
