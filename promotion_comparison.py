"""Observed promotion calendars and descriptive, non-causal sales comparisons."""
import re
import time
from datetime import datetime
from html import escape
from urllib.parse import urlencode
from sales_metrics import SAO_PAULO,reporting_today
from sales_view import SALES_STYLE
from profitability_store import read_sales_context,summarize_context
from profitability_action import load as load_finance
from investigation_evidence import window,change
from freight_comparison import format_brl
from promotion_observations import periods


def stamp(value):
    try:return datetime.fromtimestamp(int(value),SAO_PAULO).strftime('%d/%m/%Y %H:%M')+' (Brasília)'
    except (ValueError,TypeError,OverflowError,OSError):return 'Data não verificável'


def comparison(conn,query,cid,item,promotion,today,days):
    selection=periods(promotion,today,days)
    if not selection['available']:return selection
    context=read_sales_context(conn,query,cid,selection['previous_start'],selection['end'])
    visits=query(conn,'''SELECT dia,visitas FROM item_visits_daily
        WHERE conexao_id=%s AND item_id=%s AND dia BETWEEN %s AND %s ORDER BY dia''',
        (cid,item,selection['previous_start'].isoformat(),selection['end'].isoformat()))
    from datetime import timedelta
    paired=[]
    for start,end in [(selection['previous_start'],selection['previous_end']),(selection['start'],selection['end'])]:
        sales=summarize_context(context,cid,item,start,end)
        dates=[(start+timedelta(days=i)).isoformat() for i in range(days)]
        traffic=window(visits,dates,['visitas'],'dia')
        paired.append(dict(start=start,end=end,sales=sales,visits=traffic['totals']['visitas'] if traffic['complete'] else None,visits_days=traffic['covered']))
    finance=load_finance(conn,query,cid,item,paired,context['orders'],context['items'],today)
    return dict(selection,periods=paired,finance=finance)


def render(cid,item,title,readings,total,page,pages,selected,offer_index,result,days,today):
    esc=lambda v:escape(str(v),quote=True);base=f'/anuncios/{cid}/{item}/promocoes-resultados'
    out=SALES_STYLE+STYLE+'<section class="card"><h2>Resultados e calendário de promoções</h2><p>'+esc(title or item)+' · '+esc(item)+'</p><a href="/diagnostico/'+str(cid)+'/'+item+'">Voltar ao diagnóstico</a></section>'
    out+='<section class="card"><h3>Consultas preservadas</h3><p>Calendário informado pela API e participação observada na consulta. A data de leitura não substitui o início da oferta.</p>'
    if not readings:out+='<p>O histórico começa nas próximas atualizações de anúncios/promoções. Nenhuma consulta histórica foi reconstruída.</p>'
    for r in readings:
        out+='<p><a href="'+base+'?'+urlencode(dict(consulta=r['id'],pagina=page,dias=days))+'">Consulta #'+str(r['id'])+'</a> · '+stamp(r['observed_at'])+' · '+('Resposta disponível' if r['available'] else 'Não confirmada')+'</p>'
    out+='<nav aria-label="Paginação de consultas">Página '+str(page)+' de '+str(pages)+' · '+str(total)+' consulta(s)'
    for n,label in [(page-1,'Anterior'),(page+1,'Próxima')]:
        if 1<=n<=pages:out+=' <a href="'+base+'?pagina='+str(n)+'">'+label+'</a>'
    out+='</nav></section>'
    if selected:
        out+='<section class="card"><h3>Consulta #'+str(selected['id'])+'</h3><p>Lida em '+stamp(selected['observed_at'])+'. Fonte: consulta de promoções do item na API oficial. Esta leitura histórica não certifica participação atual.</p>'
        if not selected['available']:
            reason={'nao_aplicavel':'Anúncio encerrado ou em análise; consulta não aplicável.','consulta_indisponivel':'Consulta indisponível. Dados anteriores não foram reutilizados como confirmação.','resposta_nao_verificavel':'Resposta não verificável ou acima do limite de preservação.'}.get(selected['reason'],'Consulta não confirmada.')
            return out+'<div class="aviso">'+reason+'</div></section>'
        if not selected['promotions']:return out+'<p>Nenhuma promoção retornada nesta consulta. Não comprova ausência de promoções no histórico.</p></section>'
        out+='<form method="get"><input type="hidden" name="consulta" value="'+str(selected['id'])+'"><div class="pc-fields"><label>Oferta consultada<select name="oferta">'
        for i,p in enumerate(selected['promotions']):out+='<option value="'+str(i)+'"'+(' selected' if i==offer_index else '')+'>'+esc(str(p.get('id') or 'Sem identificador')+' · '+str(p.get('type') or 'Tipo não informado'))+'</option>'
        out+='</select></label><label>Janela de comparação<select name="dias">'+''.join('<option value="'+str(n)+'"'+(' selected' if n==days else '')+'>'+str(n)+' dias inteiros</option>' for n in (7,30))+'</select></label><button>Comparar</button></div></form>'
        p=selected['promotions'][offer_index]
        out+='<div class="pc-scroll"><table class="pc-meta"><tbody>'
        for label,value in [('Status do item na leitura',p.get('status')),('Início informado pelo item',p.get('start')),('Fim informado pelo item',p.get('end')),('Preço na leitura',p.get('price')),('Preço original na leitura',p.get('original')),('Variação',p.get('variation_id'))]:out+='<tr><th>'+label+'</th><td>'+esc(value if value is not None else 'Não informado')+'</td></tr>'
        out+='</tbody></table></div><details><summary>Condições retornadas</summary>'
        for k,v in p.get('conditions',{}).items():out+='<p>'+esc(k)+': '+esc(v)+'</p>'
        out+='<p>Condições pertencem à leitura selecionada. Não confirmam preço praticado em todas as vendas nem condições constantes durante o período.</p></details></section>'
        if result and not result['available']:out+='<section class="card"><div class="aviso">'+esc(result['reason'])+'</div></section>'
        elif result:
            old,current=result['periods']
            out+='<section class="card"><h3>Comparação descritiva por calendário informado</h3><p>Antes: '+old['start'].strftime('%d/%m/%Y')+' a '+old['end'].strftime('%d/%m/%Y')+' · Dentro do calendário: '+current['start'].strftime('%d/%m/%Y')+' a '+current['end'].strftime('%d/%m/%Y')+'. Dias parciais, de hoje e futuros ficam de fora.</p><div class="aviso">São todas as vendas verificadas deste anúncio nas janelas, não vendas atribuídas exclusivamente à promoção. O calendário não comprova participação contínua, condições constantes ou efeito causal. Outras ofertas podem coexistir.</div><div class="pc-scroll"><table><thead><tr><th>Indicador</th><th>Antes</th><th>Dentro do calendário</th></tr></thead><tbody>'
            for key,label,money in [('orders','Pedidos pagos',False),('units','Unidades',False),('gross_items','Bruto dos itens',True),('ticket','Ticket por pedido',True)]:
                def value(period):
                    v=period['sales'].get(key);return 'Indisponível' if v is None else format_brl(v) if money else str(v)
                out+='<tr><th>'+label+'</th><td>'+value(old)+'</td><td>'+value(current)+'</td></tr>'
            out+='<tr><th>Visitas verificadas</th><td>'+str(old['visits'] if old['visits'] is not None else 'Indisponível')+'</td><td>'+str(current['visits'] if current['visits'] is not None else 'Indisponível')+'</td></tr></tbody></table></div>'
            for period in result['periods']:
                if period['sales'].get('reason'):out+='<p class="muted">'+esc(period['sales']['reason'])+'</p>'
            out+='</section>'+finance_section(result['finance'],cid,item,result['periods'])
    return out



def finance_section(result,cid,item,paired):
    out='<section class="card"><h3>Contribuição documentada nas duas janelas</h3><p>Custos do mesmo anúncio e das datas exatas comparadas, conferidos contra a base de vendas. Não é lucro líquido nem ganho causado pela promoção.</p>'
    if not result['available']:
        out+='<div class="aviso">'+escape(result['reason'])+'</div>'
    else:
        out+='<div class="pc-scroll"><table><thead><tr><th>Indicador</th><th>Antes</th><th>Dentro do calendário</th></tr></thead><tbody>'
        for key,label in [('total_costs','Custos documentados'),('contribution','Contribuição'),('margin_pct','Margem de contribuição')]:
            out+='<tr><th>'+label+'</th>'
            for p in [result['before'],result['after']]:
                value=p.get(key);text='Indisponível' if value is None else format(value,'.2f').replace('.',',')+'%' if key=='margin_pct' else format_brl(value)
                out+='<td>'+text+'</td>'
            out+='</tr>'
        out+='</tbody></table></div><p>Diferença observada de contribuição: '+format_brl(result['delta'])+'. Inclui diferenças de volume, preço e custos; não mede o efeito exclusivo da promoção.</p>'
    records=result.get('records') or []
    for i,p in enumerate(paired):
        params=dict(inicio=p['start'].isoformat(),fim=p['end'].isoformat())
        if i<len(records) and records[i] is not None:params['registro']=records[i]['id']
        href='/anuncios/'+str(cid)+'/'+item+'/rentabilidade?'+urlencode(params)
        out+='<p><a class="pc-cost-link" href="'+escape(href,quote=True)+'">Conferir custos: '+p['start'].strftime('%d/%m/%Y')+' a '+p['end'].strftime('%d/%m/%Y')+'</a></p>'
    return out+'</section>'


def register(app,login_required,can_view,bank,query,execute,page):
    from flask import request,make_response,session
    @app.get('/anuncios/<int:cid>/<item_id>/promocoes-resultados')
    @login_required
    def listing_promotion_comparison(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        if request.args.get('dias','7') not in ('7','30'):return 'Janela inválida',400
        days=int(request.args.get('dias','7'));selected=None;result=None;offer_index=0;today=reporting_today()
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            shops=query(conn,'SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s',(cid,item_id))
            if not shops:return 'Anúncio não encontrado nesta loja',404
            total=query(conn,'SELECT COUNT(*) AS n FROM listing_promotion_readings WHERE conexao_id=%s AND item_id=%s',(cid,item_id))[0]['n'];pages=max(1,(total+9)//10)
            try:pg=max(1,min(pages,int(request.args.get('pagina','1'))))
            except (TypeError,ValueError):pg=1
            readings=query(conn,'''SELECT id,observed_at,available FROM listing_promotion_readings
                WHERE conexao_id=%s AND item_id=%s ORDER BY observed_at DESC,id DESC LIMIT 10 OFFSET %s''',(cid,item_id,(pg-1)*10))
            chosen=request.args.get('consulta')
            if chosen is not None and (not re.fullmatch(r'[1-9][0-9]{0,18}',chosen) or int(chosen)>2**63-1):return 'Consulta inválida',404
            chosen=int(chosen) if chosen else readings[0]['id'] if readings else None
            if chosen is not None:
                rows=query(conn,'SELECT * FROM listing_promotion_readings WHERE conexao_id=%s AND item_id=%s AND id=%s',(cid,item_id,chosen))
                if not rows:return 'Consulta não encontrada neste anúncio',404
                selected=rows[0]
                if selected['available'] and selected['promotions']:
                    raw=request.args.get('oferta','0')
                    if not re.fullmatch(r'[0-9]{1,3}',raw) or int(raw)>=len(selected['promotions']):return 'Oferta inválida',400
                    offer_index=int(raw)
                    result=comparison(conn,query,cid,item_id,selected['promotions'][offer_index],today,days)
        body=render(cid,item_id,shops[0]['titulo'],readings,total,pg,pages,selected,offer_index,result,days,today)
        response=make_response(page('Resultados de promoções',cid,shops[0]['cliente'],'anuncios',body));response.headers['Cache-Control']='private, no-store';return response

STYLE='''<style>.action-finance{background:#11243a;color:#eaf2ff;border:1px solid #2d4864;border-radius:15px;padding:20px;margin:16px 0;min-width:0}.action-finance .iv-scroll{overflow-x:auto}.action-finance table{width:100%;min-width:600px}.action-finance th,.action-finance td{padding:12px;text-align:left}.action-finance p{line-height:1.65}.pc-fields{display:flex;flex-wrap:wrap;gap:14px;align-items:end}.pc-fields label{display:grid;gap:6px;flex:1;min-width:150px}.pc-fields select{max-width:100%;min-width:0;padding:10px}.pc-fields button{padding:12px 16px;border:0;border-radius:9px;background:#2476c7;color:#fff;min-height:44px}.pc-scroll{overflow-x:auto}.pc-scroll table.pc-meta{min-width:0;table-layout:fixed}.pc-meta th{width:45%}.pc-meta td{word-break:break-word}.pc-cost-link{display:inline-block;padding:10px 12px;border:1px solid #416481;border-radius:9px;text-decoration:none}.pc-scroll table{width:100%;min-width:600px;border-collapse:collapse}.pc-scroll th,.pc-scroll td{padding:12px;text-align:left;border-bottom:1px solid #34516e;font-size:12px;overflow-wrap:anywhere}</style>'''
