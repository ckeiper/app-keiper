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
        gross_total='0.00',fees_total='0.00',net_total='0.00',difference_total='0.00')


def accumulate(result,gross,fees,net):
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


def render(result):
    if not result:
        return '' # older imported versions have no financial diagnostic
    out='<style>.conteudo .ledger-check{background:#102238;color:#eaf2ff;border:1px solid #34516e}.conteudo .ledger-check h3{color:#eaf2ff}.ledger-check p{color:#bdcce1;line-height:1.65}.ledger-check .frete-metricas{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:12px}.ledger-check .frete-metrica{display:flex;flex-direction:column;gap:8px;padding:16px;background:#182e49;border:1px solid #34516e;border-radius:12px}.ledger-check strong{font-size:22px;overflow-wrap:anywhere}.ledger-check span{color:#bdcce1}</style><section class="card frete-resultado ledger-check"><h3>Conferência de bruto, tarifas e líquido</h3>'
    if not result['available']:
        return out+'<p>Coluna Valor bruto (=) ausente ou ambígua. Conferência financeira indisponível para este arquivo.</p></section>'
    if not result['valid_rows']:
        return out+'<p>Nenhuma linha com os três valores financeiros válidos. Valores ausentes ou inválidos não são zero.</p></section>'
    out+='<p>'+str(result['valid_rows'])+' lançamentos comparáveis; '+str(result['invalid_rows'])+' com valores incompletos ou inválidos; '+str(result['inconsistent_rows'])+' com diferença de pelo menos R$ 0,01.</p><div class="frete-metricas">'
    for label,key in [('Bruto informado','gross_total'),('Tarifas informadas','fees_total'),('Líquido após tarifas informado','net_total')]:
        out+='<div class="frete-metrica"><span>'+label+'</span><strong>'+format_brl(result[key])+'</strong></div>'
    return out+'</div><p>Conferência por linha: valor bruto menos tarifas versus líquido após tarifas. Sinais negativos são preservados. A contagem de diferenças não é compensada entre linhas; sua soma algébrica é '+format_brl(result['difference_total'])+'.</p><p>Totais apenas das linhas com os três valores válidos, incluindo repetições. O arquivo mistura tipos de movimento; estes totais não são faturamento de vendas, lucro, saldo bancário ou repasse recebido. Tarifas pós-pagas não são descontadas novamente nesta identidade. Uma diferença pede conferência do relatório, sem comprovar cobrança indevida.</p></section>'
