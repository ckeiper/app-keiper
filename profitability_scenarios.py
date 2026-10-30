"""Explicit hypothetical discount tiers; no marketplace writes or saved evidence."""
import re
import secrets
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP,ROUND_CEILING
from html import escape
from flask import request,session
from profitability_view import CSS
from freight_comparison import format_brl

FIELDS={
 'price':'Preço base por unidade (R$)',
 'product':'Custo do produto por unidade (R$)',
 'fee_pct':'Tarifa percentual sobre o bruto (%)',
 'fixed_fee':'Tarifas fixas por pedido (R$)',
 'tax_pct':'Imposto sobre o bruto (%)',
 'shipping':'Frete do vendedor por pedido (R$)',
 'ads':'Publicidade por pedido (R$)',
 'adjustments':'Outros descontos e ajustes por pedido (R$)',
}
CENT=Decimal('.01')


def number(value,label,maximum=Decimal('999999.99')):
    text=str(value or '').strip().replace(',','.')
    if not re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,2})?',text):
        raise ValueError('Informe '+label+' com até duas casas decimais, sem separador de milhar.')
    try:n=Decimal(text)
    except InvalidOperation:raise ValueError('Valor inválido: '+label) from None
    if n>maximum:raise ValueError('Valor acima do limite: '+label)
    return n


def simulate(form):
    inputs={key:number(form.get(key),label,Decimal('100') if key.endswith('_pct') else Decimal('999999.99')) for key,label in FIELDS.items()}
    if inputs['price']<=0:raise ValueError('O preço base deve ser maior que zero.')
    if form.get('assumptions')!='yes':raise ValueError('Confirme que os valores são premissas de simulação, não custos históricos verificados.')
    tiers=[]
    for i in range(5):
        qty,discount=str(form.get('qty_'+str(i)) or '').strip(),str(form.get('discount_'+str(i)) or '').strip()
        if not qty and not discount:continue
        if not re.fullmatch(r'[1-9][0-9]{0,3}|10000',qty):raise ValueError('Use quantidades inteiras entre 1 e 10.000 em cada faixa.')
        q=int(qty);d=number(discount,'o desconto da faixa',Decimal('99.99'))
        if tiers and (q<=tiers[-1][0] or d<tiers[-1][1]):
            raise ValueError('As quantidades devem crescer e os descontos não podem diminuir entre faixas.')
        tiers.append((q,d))
    if not tiers:raise ValueError('Informe ao menos uma faixa com quantidade e desconto.')
    def order(q,d):
        price=(inputs['price']*(100-d)/100).quantize(CENT,rounding=ROUND_HALF_UP)
        if price<=0:raise ValueError('O desconto arredonda o preço a zero. Revise a faixa.')
        gross=price*q
        fees=(gross*inputs['fee_pct']/100).quantize(CENT,rounding=ROUND_HALF_UP)+inputs['fixed_fee']
        taxes=(gross*inputs['tax_pct']/100).quantize(CENT,rounding=ROUND_HALF_UP)
        product=inputs['product']*q
        costs=product+fees+taxes+inputs['shipping']+inputs['ads']+inputs['adjustments']
        value=gross-costs
        return dict(price=price,gross=gross,costs=costs,product=product,fees=fees,taxes=taxes,
                    contribution=value,margin=value*100/gross)
    target_text=str(form.get('target_margin') or '').strip()
    target=number(target_text,'a meta de margem',Decimal('100')) if target_text else None
    rows=[]
    for q,d in tiers:
        row=order(q,d);base=order(q,Decimal(0))
        rows.append(dict(row,quantity=q,discount=d,baseline=base['contribution'],
                         delta=row['contribution']-base['contribution']))
    if target is not None:
        for row in rows:
            required=(row['gross']*target/100).quantize(CENT,rounding=ROUND_CEILING)
            row.update(target_contribution=required,target_gap=max(required-row['contribution'],Decimal(0)),target_met=row['contribution']>=required)
    return dict(inputs=inputs,rows=rows,target_margin=target)


def render(cid,item_id,title,csrf,values=None,result=None,error=''):
    values=values or {};esc=lambda v:escape(str(v),quote=True)
    out=CSS+'<style>.conteudo .pf .scenario-tiers tbody tr,.conteudo .pf .scenario-tiers tbody td{background:#102238}.scenario-tiers input{margin:0}.pf form>label{margin:12px 0}</style><div class="pf"><header class="pf-hero"><span class="pf-eyebrow">Anúncios 2.0 · Cenários manuais</span><h2>Simular descontos progressivos</h2><p>'+esc(title or item_id)+' · '+esc(item_id)+'</p><a href="/anuncios/'+str(cid)+'/'+item_id+'/rentabilidade">Voltar à rentabilidade ↗</a><p>Premissas preenchidas pelo administrador. Esta simulação não lê custos históricos, não publica faixas e não altera o anúncio.</p></header>'
    if error:out+='<p class="pf-alert" role="alert">'+esc(error)+'</p>'
    out+='<section class="pf-card"><h3>Premissas do pedido simulado</h3><p>Preencha todos os custos, inclusive zero. Percentuais incidem sobre o valor bruto simulado. Tarifas fixas, frete, publicidade e ajustes são totais por pedido; custo do produto é por unidade.</p><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'">'
    for key,label in FIELDS.items():
        out+='<label>'+label+'<input name="'+key+'" inputmode="decimal" maxlength="9" required value="'+esc(values.get(key,''))+'"></label>'
    out+='<label>Meta de margem de contribuição (%) · opcional<input name="target_margin" inputmode="decimal" maxlength="6" value="'+esc(values.get('target_margin',''))+'"></label><p>Meta definida por você, sem percentual recomendado pelo sistema. Não representa lucro líquido.</p>'
    out+='<h3>Faixas propostas</h3><p>Até cinco faixas em ordem crescente de quantidade e desconto não decrescente. Cada linha representa um pedido com aquela quantidade exata; não prevê o comportamento do comprador.</p><div class="pf-table"><table class="scenario-tiers"><thead><tr><th>Quantidade</th><th>Desconto (%)</th></tr></thead><tbody>'
    for i in range(5):
        out+='<tr><td><input aria-label="Quantidade faixa '+str(i+1)+'" name="qty_'+str(i)+'" inputmode="numeric" maxlength="5" value="'+esc(values.get('qty_'+str(i),''))+'"></td><td><input aria-label="Desconto faixa '+str(i+1)+'" name="discount_'+str(i)+'" inputmode="decimal" maxlength="5" value="'+esc(values.get('discount_'+str(i),''))+'"></td></tr>'
    out+='</tbody></table></div><label><input type="checkbox" name="assumptions" value="yes" required'+(' checked' if values.get('assumptions')=='yes' else '')+'>Conferi as premissas e entendo que não são custos históricos verificados.</label><p><button>Calcular cenários</button></p></form></section>'
    if result:
        out+='<section class="pf-card" id="discount-results"><h3>Contribuição simulada por faixa</h3><div class="pf-table"><table style="min-width:900px"><caption>Pedidos hipotéticos · valores em R$ · role a tabela no celular</caption><thead><tr><th>Quantidade</th><th>Desconto</th><th>Preço unitário</th><th>Bruto</th><th>Custos</th><th>Contribuição</th><th>Margem</th><th>Sem desconto, mesma quantidade</th><th>Diferença da contribuição</th></tr></thead><tbody>'
        for r in result['rows']:
            out+='<tr><td>'+str(r['quantity'])+'</td><td>'+format(r['discount'],'.2f').replace('.',',')+'%</td>'
            for k in ['price','gross','costs','contribution']:out+='<td>'+format_brl(r[k])+'</td>'
            out+='<td>'+format(r['margin'],'.2f').replace('.',',')+'%</td><td>'+format_brl(r['baseline'])+'</td><td>'+format_brl(r['delta'])+'</td></tr>'
        out+='</tbody></table></div><details><summary>Conferir composição de cada pedido</summary>'
        for r in result['rows']:
            out+='<p>'+str(r['quantity'])+' unidades: produtos '+format_brl(r['product'])+'; tarifas '+format_brl(r['fees'])+'; impostos '+format_brl(r['taxes'])+'; frete '+format_brl(result['inputs']['shipping'])+'; publicidade '+format_brl(result['inputs']['ads'])+'; ajustes '+format_brl(result['inputs']['adjustments'])+'.</p>'
        out+='</details>'
        if result.get('target_margin') is not None:
            out+='<h3>Conferência da meta informada</h3><p>Meta: '+format(result['target_margin'],'.2f').replace('.',',')+'%. Comparação aritmética nas premissas do pedido, sem garantia de resultado.</p><ul class="scenario-target">'
            for row in result['rows']:
                out+='<li>'+str(row['quantity'])+' unidades: '+('atinge a meta nas premissas' if row['target_met'] else 'abaixo da meta nas premissas')+'. Contribuição necessária: '+format_brl(row['target_contribution'])+'; distância para a meta: '+format_brl(row['target_gap'])+'.</li>'
            out+='</ul><p>A distância não é economia disponível, preço recomendado ou promessa de recuperação. Contribuição necessária arredondada para cima a centavos para não aprovar margem abaixo da meta.</p>'
        out+='</section>'
    return out+'<section class="pf-card"><p>Contribuição simulada não é lucro líquido nem previsão de vendas. Despesas fixas não incluídas. Preço unitário arredondado a centavos antes de multiplicar pela quantidade; tarifas percentuais e impostos arredondados por pedido. O modelo não reproduz regras específicas de tarifas mínimas, faixas logísticas, cupons cumulativos ou financiamento do marketplace. Ajuste as premissas para cada contexto. Não há recomendação automática de melhor faixa ou garantia de demanda.</p></section></div>'


def register(app,login_required,can_view,bank,query,shop_page):
    @app.route('/anuncios/<int:cid>/<item_id>/simulacao-descontos',methods=['GET','POST'])
    @login_required
    def listing_discount_simulation(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito ao administrador.',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado.',404
        with bank() as conn:
            shops=query(conn,'''SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a
                ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
        if not shops:return 'Anúncio não encontrado nesta loja.',404
        token=session.setdefault('_csrf',secrets.token_urlsafe(32))
        result=None;error='';status=200
        if request.method=='POST':
            try:result=simulate(request.form)
            except ValueError as exc:error=str(exc);status=400
        return shop_page('Simular descontos progressivos',cid,shops[0]['cliente'],'anuncios',
            render(cid,item_id,shops[0]['titulo'],token,request.form if request.method=='POST' else None,result,error)),status
