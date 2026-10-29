"""Admin kit analysis: explicit composition, sources, immutable versions, local reads."""
import hmac
import re
import secrets
import time
from datetime import date
from html import escape
from urllib.parse import urlencode
from sales_metrics import reporting_today,SAO_PAULO
from sales_view import SALES_STYLE
from freight_comparison import format_brl
from profitability_store import read_sales_context
from listing_kits import COSTS,validate,check_links,save,economics,evidence


def listing_rows(conn,query,cid,ids):
    return query(conn,'''SELECT item_id,titulo,status,quantidade,atualizado_em FROM anuncios
        WHERE conexao_id=%s AND item_id=ANY(%s) ORDER BY item_id''',(cid,ids))


def flatten(composition):
    values={k:composition[k] for k in ('mode','source','source_date','days')};values.update(composition['costs'])
    for i,c in enumerate(composition['components']):
        for key in ('label','item','qty','cost'):values[key+'_'+str(i)]=c[key] if c[key] is not None else ''
        values['reference_'+str(i)]=c['reference']
    return values


def render(cid,item,title,csrf,key,values,record,proof,history,page,pages,error=''):
    esc=lambda v:escape(str(v),quote=True);base='/anuncios/'+str(cid)+'/'+item+'/kits'
    out=SALES_STYLE+STYLE+'<div class="kit"><section class="card"><h2>Análise de kits</h2><p>'+esc(title or item)+' · '+esc(item)+'</p><p><a href="/diagnostico/'+str(cid)+'/'+item+'">Voltar ao diagnóstico</a></p></section>'
    if error:out+='<div class="aviso" role="alert">'+esc(error)+'</div>'
    if record:
        c=record['composition'];result=economics(c)
        from datetime import datetime
        stamp=datetime.fromtimestamp(record['created_at'],SAO_PAULO).strftime('%d/%m/%Y %H:%M')
        out+='<section class="card" id="kit-result"><h3>Análise salva #'+str(record['id'])+'</h3><p>'+('Proposta de kit' if c['mode']=='proposal' else 'Anúncio declarado como kit existente')+' · '+stamp+' (Brasília) · responsável #'+str(record['created_by'])+'</p><div class="grid">'
        for label,value in [('Preço por kit',result['price']),('Custo dos componentes',result['products']),('Custos totais por kit',result['total']),('Contribuição simulada por kit',result['contribution'])]:
            tone=' sales-up' if label.startswith('Contribuição') and value>=0 else ' sales-down' if label.startswith('Contribuição') else ''
            out+='<article class="stat"><div class="lab">'+label+'</div><div class="num'+tone+'">'+format_brl(value)+'</div></article>'
        out+='</div><p>Margem de contribuição simulada: <strong>'+format(result['margin'],'.2f').replace('.',',')+'%</strong>. Não é lucro líquido nem resultado histórico.</p><div class="kit-scroll"><table><thead><tr><th>Componente</th><th>Quantidade por kit</th><th>Custo unitário</th><th>Custo no kit</th><th>Fonte declarada</th></tr></thead><tbody>'
        from decimal import Decimal
        for component in c['components']:
            out+='<tr><th scope="row">'+esc(component['label'])+'</th><td>'+str(component['qty'])+'</td><td>'+format_brl(Decimal(component['cost']))+'</td><td>'+format_brl(Decimal(component['cost'])*component['qty'])+'</td><td>'+esc(component['reference'])+'</td></tr>'
        out+='</tbody></table></div><details><summary>Demais custos e referências</summary><p>Referência em '+esc(c['source_date'])+': '+esc(c['source'])+'</p>'
        for k,label in COSTS.items():out+='<p>'+label+': '+esc(c['costs'][k])+('%' if k.endswith('_pct') else ' R$')+'</p>'
        out+='</details></section>'
        out+='<section class="card"><h3>Evidências de vendas e estoque</h3><p>'+esc(c['start'])+' a '+esc(c['end'])+' · dias encerrados em Brasília. Os dados abaixo são reavaliados na consulta; a composição e as premissas da versão permanecem preservadas.</p>'
        if c['mode']=='proposal':out+='<div class="aviso">Demanda do kit proposto ainda não validada. As vendas do anúncio de referência e dos componentes não comprovam procura pela nova composição.</div>'
        else:out+='<p>Vendas verificadas do anúncio identificado pelo consultor como kit. A composição foi declarada pelo responsável; não foi certificada pela API.</p>'
        actual=proof['sales']
        out+='<p>Pedidos pagos do anúncio de referência: <strong>'+esc(actual['orders'] if actual['orders'] is not None else 'Indisponível')+'</strong> · Unidades do anúncio: '+esc(actual['units'] if actual['units'] is not None else 'Indisponível')+' · Valor bruto dos itens: '+(format_brl(actual['gross_items']) if actual['gross_items'] is not None else 'Indisponível')+'.</p>'
        if actual.get('reason'):out+='<p class="muted">'+esc(actual['reason'])+'</p>'
        out+='<div class="kit-scroll"><table><thead><tr><th>Componente</th><th>Anúncio vinculado</th><th>Unidades vendidas</th><th>Estoque geral recente</th></tr></thead><tbody>'
        for r in proof['components']:
            sales=r['sales'];out+='<tr><th>'+esc(r['component']['label'])+'</th><td>'+esc(r['component']['item'] or 'Sem vínculo')+'</td><td>'+esc(sales['units'] if sales and sales['units'] is not None else 'Indisponível')+'</td><td>'+esc(r['stock'] if r['stock'] is not None else 'Não verificado')+'</td></tr>'
        out+='</tbody></table></div><p>Limite aritmético pela composição e pelos estoques gerais recentes: <strong>'+esc(proof['capacity'] if proof['capacity'] is not None else 'Não verificável')+'</strong> kit(s). Não verifica reservas, estoques compartilhados, inventários Full nem variações.</p><h4>Próximas conferências</h4><ul>'
        if result['contribution']<0:out+='<li>Rever preço e custos: as premissas informadas resultam em contribuição negativa.</li>'
        if proof['capacity']==0:out+='<li>Conferir reposição dos componentes: o limite aritmético atual é zero.</li>'
        if proof['capacity'] is None:out+='<li>Conferir disponibilidade dos componentes sem vínculo ou sem estoque recente.</li>'
        if c['mode']=='proposal':out+='<li>Validar aceitação da composição antes de ampliar estoque; esta simulação não prevê vendas.</li>'
        elif actual['orders']==0:out+='<li>O anúncio não registrou pedidos pagos na janela verificada; revisar oferta e tráfego antes de ampliar estoque.</li>'
        elif actual['orders'] is None:out+='<li>Completar a cobertura das vendas antes de concluir sobre a demanda observada.</li>'
        out+='<li>Conferir fontes e custos específicos do kit; publicar ou alterar a oferta permanece uma decisão do consultor.</li></ul></section>'
    out+='<section class="card"><h3>'+('Criar outra versão' if record else 'Definir composição e custos')+'</h3><p>Até cinco componentes, com pelo menos duas unidades no total. O vínculo MLB é opcional e permite consultar o histórico do componente nesta loja.</p><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="submission_key" value="'+esc(key)+'">'
    out+='<div class="kit-grid"><label>Tipo de análise<select name="mode" required><option value="">Selecione</option>'+''.join('<option value="'+v+'"'+(' selected' if values.get('mode')==v else '')+'>'+label+'</option>' for v,label in [('proposal','Proposta de novo kit'),('existing','Anúncio existente declarado como kit')])+'</select></label><label>Histórico<select name="days">'+''.join('<option value="'+str(n)+'"'+(' selected' if str(values.get('days','30'))==str(n) else '')+'>'+str(n)+' dias encerrados</option>' for n in (7,30))+'</select></label></div>'
    def field(name,label,kind='text',maxlen=100,required=False,decimal=False):
        return '<label>'+label+'<input name="'+name+'" type="'+kind+'" maxlength="'+str(maxlen)+'"'+(' required' if required else '')+(' inputmode="decimal"' if decimal else '')+' value="'+esc(values.get(name,''))+'"></label>'
    for i in range(5):
        out+='<details class="kit-component"'+(' open' if i==0 or values.get('label_'+str(i)) else '')+'><summary>Componente '+str(i+1)+(' · obrigatório' if i==0 else ' · opcional')+'</summary><div class="kit-grid">'
        for name,label,maxlen in [('label','Identificação / SKU',100),('item','Anúncio vinculado MLB (opcional)',23),('qty','Quantidade por kit',4),('cost','Custo de uma unidade (R$)',9),('reference','Fonte do custo unitário',300)]:out+=field(name+'_'+str(i),label,maxlen=maxlen,required=i==0 and name!='item',decimal=name=='cost')
        out+='</div></details>'
    out+='<h4>Premissas de uma venda de kit</h4><p>Preencha todos os custos, inclusive zero quando confirmado. Tarifas e frete são premissas manuais, sem cotação oficial automática.</p><div class="kit-grid">'
    for name,label in COSTS.items():out+=field(name,label+(' (R$)' if not name.endswith('_pct') else ''),maxlen=9,required=True,decimal=True)
    out+='</div>'+field('source','Referência da composição e dos custos gerais',maxlen=500,required=True)+field('source_date','Data das referências',kind='date',maxlen=10,required=True)
    out+='<label class="kit-confirm"><input type="checkbox" name="confirmed" value="yes" required>Conferi a composição e as referências. Os valores financeiros são premissas de simulação e não custos históricos certificados.</label><button type="submit">Salvar análise de kit</button></form></section>'
    out+='<section class="card"><h3>Versões preservadas</h3>'
    for r in history:out+='<p><a href="'+base+'?'+urlencode(dict(analise=r['id'],pagina=page))+'">Análise #'+str(r['id'])+'</a> · responsável #'+str(r['created_by'])+'</p>'
    if not history:out+='<p>Nenhuma análise salva para este anúncio.</p>'
    out+='<nav aria-label="Paginação das análises">Página '+str(page)+' de '+str(pages)
    for n,label in [(page-1,'Anterior'),(page+1,'Próxima')]:
        if 1<=n<=pages:out+=' <a href="'+base+'?pagina='+str(n)+'">'+label+'</a>'
    return out+'</nav></section></div>'


def register(app,login_required,can_view,bank,query,execute,shop_page):
    from flask import request,session,redirect
    @app.route('/anuncios/<int:cid>/<item_id>/kits',methods=['GET','POST'])
    @login_required
    def listing_kit_analysis(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        csrf=session.setdefault('_csrf',secrets.token_urlsafe(32))
        if request.method=='POST' and not hmac.compare_digest(str(request.form.get('_csrf','')),str(csrf)):return 'Formulário inválido',403
        now=int(time.time());error='';status=200;record=None;proof=None
        values=request.form if request.method=='POST' else {}
        with bank() as conn:
            if request.method=='GET':execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            shops=query(conn,'SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s',(cid,item_id))
            if not shops:return 'Anúncio não encontrado nesta loja',404
            if request.method=='POST':
                try:
                    composition,key=validate(request.form,reporting_today())
                    links=listing_rows(conn,query,cid,[c['item'] for c in composition['components'] if c['item']])
                    check_links(composition,links,item_id)
                    saved=save(conn,query,cid,item_id,composition,key,int(session['usuario_id']),now)
                except ValueError as exc:error,status=str(exc),400
                else:return redirect('/anuncios/'+str(cid)+'/'+item_id+'/kits?analise='+str(saved),code=303)
            count=query(conn,'SELECT COUNT(*) AS n FROM listing_kit_analyses WHERE conexao_id=%s AND item_id=%s',(cid,item_id))[0]['n'];pages=max(1,(count+9)//10)
            try:page=max(1,min(pages,int(request.args.get('pagina','1'))))
            except (ValueError,TypeError):page=1
            history=query(conn,'''SELECT id,created_by,created_at FROM listing_kit_analyses
                WHERE conexao_id=%s AND item_id=%s ORDER BY id DESC LIMIT 10 OFFSET %s''',(cid,item_id,(page-1)*10))
            selected=request.args.get('analise')
            if selected is not None:
                if not re.fullmatch(r'[1-9][0-9]{0,18}',selected) or int(selected)>2**63-1:return 'Análise inválida',404
                records=query(conn,'SELECT * FROM listing_kit_analyses WHERE conexao_id=%s AND item_id=%s AND id=%s',(cid,item_id,int(selected)))
                if not records:return 'Análise não encontrada neste anúncio',404
                record=records[0]
            elif history:
                record=query(conn,'SELECT * FROM listing_kit_analyses WHERE conexao_id=%s AND item_id=%s AND id=%s',(cid,item_id,history[0]['id']))[0]
            if record:
                c=record['composition'];start,end=date.fromisoformat(c['start']),date.fromisoformat(c['end'])
                context=read_sales_context(conn,query,cid,start,end)
                rows=listing_rows(conn,query,cid,[x['item'] for x in c['components'] if x['item']])
                proof=evidence(c,context,rows,item_id,start,end,now)
                if request.method=='GET':values=flatten(c)
        body=render(cid,item_id,shops[0]['titulo'],csrf,secrets.token_urlsafe(24),values,record,proof,history,page,pages,error)
        from flask import make_response
        response=make_response(shop_page('Análise de kits',cid,shops[0]['cliente'],'anuncios',body),status);response.headers['Cache-Control']='private, no-store'
        return response

STYLE='''<style>.kit .kit-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.kit label{display:block;margin:12px 0;min-width:0}.kit input,.kit select{width:100%;box-sizing:border-box;min-width:0;padding:10px;border-radius:8px}.kit input[type=checkbox]{width:auto;margin-right:8px}.kit-component{border:1px solid #426184;border-radius:10px;padding:14px;margin:14px 0}.kit summary{cursor:pointer;font-weight:700}.kit-scroll{overflow-x:auto}.kit table{width:100%;min-width:700px;border-collapse:collapse}.kit td,.kit th{padding:12px;text-align:left;overflow-wrap:anywhere;border-bottom:1px solid #34516e;font-size:12px}.kit .num{overflow-wrap:anywhere}.kit button{min-height:44px;border:1px solid #3389dc;border-radius:9px;background:#2476c7;color:#fff;padding:11px 16px;font:inherit;font-weight:700;cursor:pointer}.kit .num.sales-up{color:#80f0b7!important}.kit .num.sales-down{color:#ffb1b8!important}.kit .kit-confirm{line-height:1.7}@media(max-width:650px){.kit .kit-grid{grid-template-columns:1fr}}</style>'''
