"""Guarded Mercado Livre DEAL participation.

Only traditional invited DEAL campaigns are writable. Never infer that an API
POST succeeded without a subsequent fresh read of the item's participation.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape
import re

ITEM_RE=re.compile(r'^ML[A-Z]{1,2}[0-9]{6,18}$')
PROMO_RE=re.compile(r'^P-ML[A-Z]{1,2}[0-9]{1,18}$')


def parse_price(raw):
    try:
        value=Decimal(str(raw).strip().replace(',','.'))
    except (InvalidOperation,ValueError):
        raise ValueError('Informe um preço válido.')
    if not value.is_finite() or value<=0 or value>Decimal('100000000'):
        raise ValueError('Preço inválido.')
    if value!=value.quantize(Decimal('0.01')):
        raise ValueError('O preço deve ter no máximo duas casas decimais.')
    return value.quantize(Decimal('0.01'))


def find_deal(rows, promotion_id):
    if not isinstance(rows,list):
        raise ValueError('Resposta de promoções inválida.')
    for item in rows:
        if (isinstance(item,dict) and str(item.get('id'))==promotion_id
                and item.get('type')=='DEAL'):
            return item
    return None


def margin_pct(price, cost, tax, commission):
    price=Decimal(str(price))
    cost=Decimal(str(cost))
    tax=Decimal(str(tax))
    commission=Decimal(str(commission))
    if price<=0 or cost<0 or not all(x.is_finite() for x in (price,cost,tax,commission)):
        raise ValueError('Dados financeiros inválidos.')
    if tax<0 or tax>100 or commission<0 or commission>100:
        raise ValueError('Alíquotas inválidas.')
    return ((price-cost-price*(tax+commission)/100)*100/price).quantize(
        Decimal('0.01'),rounding=ROUND_HALF_UP)


def check_candidate(row, price):
    if row is None or str(row.get('status','')).lower()!='candidate':
        raise ValueError('O anúncio não está mais disponível como candidato a esta promoção.')
    lo=row.get('min_discounted_price')
    hi=row.get('max_discounted_price')
    if lo is not None and price<Decimal(str(lo)):
        raise ValueError('Preço inferior ao mínimo permitido pelo Mercado Livre.')
    if hi is not None and price>Decimal(str(hi)):
        raise ValueError('Preço superior ao máximo permitido pelo Mercado Livre.')
    original=row.get('original_price')
    if original is not None and Decimal(str(original))>0 and price>=Decimal(str(original)):
        raise ValueError('O preço promocional deve ser inferior ao preço original.')


def safe_item(item_id):
    if not ITEM_RE.fullmatch(item_id or ''):
        raise ValueError('Identificador do anúncio inválido.')
    return item_id


def safe_promo(promotion_id):
    if not PROMO_RE.fullmatch(promotion_id or ''):
        raise ValueError('Identificador da campanha inválido.')
    return promotion_id


def is_participating(row):
    return row is not None and str(row.get('status','')).lower() in ('pending','started','active')


def candidate_table(cid, promotion_id, items, names, err=''):
    base='/promocoes/participar/'+str(int(cid))+'/'+escape(promotion_id,quote=True)+'/'
    out='<h2>Produtos convidados</h2><p class="sub">Campanha tradicional (DEAL). Confira preço e margem antes de confirmar. A participação não é automática.</p>'
    if err:
        out+='<div class="aviso" role="alert">'+escape(err)+'</div>'
    out+='<div class="card"><table><thead><tr><th>Anúncio</th><th>Preço original</th><th>Preço sugerido</th><th>Participação</th></tr></thead><tbody>'
    shown=0
    for item in items:
        if not isinstance(item,dict) or str(item.get('status','')).lower()!='candidate':
            continue
        item_id=str(item.get('id') or '')
        if not ITEM_RE.fullmatch(item_id) or item_id not in names:
            continue
        shown+=1
        name=escape(str(names[item_id] or item_id))
        original=item.get('original_price')
        suggested=item.get('suggested_discounted_price')
        out+='<tr><td>'+name+'<br><small>'+escape(item_id)+'</small></td>'
        out+='<td>'+('R$ %.2f'%float(original) if original is not None else '—')+'</td>'
        out+='<td>'+('R$ %.2f'%float(suggested) if suggested is not None else '—')+'</td>'
        out+='<td><a class="filtro-btn" href="'+base+escape(item_id,quote=True)+'">Analisar e participar</a></td></tr>'
    if not shown:
        out+='<tr><td colspan="4">Nenhum anúncio candidato nesta página.</td></tr>'
    return out+'</tbody></table></div>'


def confirmation_form(cid,promotion_id,item_id,price,mc,goal,original):
    c=str(int(cid));pid=escape(promotion_id,quote=True);item=escape(item_id,quote=True)
    return ("<div class='card' style='max-width:690px'>"
        "<h2>Confirme a participação no Mercado Livre</h2>"
        "<p class='sub'>Esta ação envia uma adesão real à campanha DEAL. "
        "Não é uma simulação e poderá alterar o preço de venda do anúncio.</p>"
        "<p>Anúncio: <b>"+item+"</b> · Campanha: <b>"+pid+"</b></p>"
        "<p>Preço normal: R$ %.2f · Preço promocional: <b>R$ %.2f</b></p>"%(float(original),float(price))
        +"<p>MC estimada: <b>%.2f%%</b> · Meta mínima: %.2f%%</p>"%(float(mc),float(goal))
        +"<p class='sub'>Estimativa não inclui frete, tarifa fixa e outras despesas. "
        "Verifique sua margem líquida antes de aderir.</p>"
        "<form method='post' action='/promocoes/participar/"+c+"/"+pid+"/"+item+"'>"
        "<input type='hidden' name='deal_price' value='"+str(price)+"'>"
        "<label><input type='checkbox' name='confirmar' value='sim' required> "
        "Autorizo enviar esta participação e o preço acima ao Mercado Livre.</label>"
        "<div style='margin-top:16px'><button class='filtro-btn' type='submit'>Confirmar participação</button></div>"
        "</form></div>")
