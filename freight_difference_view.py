"""A store-scoped, per-order review for preparing freight support cases."""
import csv
import io
import json
from datetime import date,datetime
from decimal import Decimal
from html import escape
from urllib.parse import urlencode
from flask import request,session,Response
from freight_comparison import format_brl
from sales_metrics import SAO_PAULO


def show_date(value):
    try:return date.fromisoformat(str(value)).strftime('%d/%m/%Y')
    except (ValueError,TypeError):return 'Data não informada'


def show_stamp(value):
    try:
        stamp=datetime.fromisoformat(str(value))
        return stamp.astimezone(SAO_PAULO).strftime('%d/%m/%Y às %H:%M · Brasília') if stamp.tzinfo else 'Horário não verificado'
    except (ValueError,TypeError):return 'Horário não informado'


def filtered(review,args):
    direction=args.get('direcao','above');source=args.get('fonte','all')
    if direction not in ('all','above','below'):direction='above'
    if source not in ('all','real','estimado'):source='all'
    rows=[r for r in review.get('details',[]) if (direction=='all' or r['status']==direction) and (source=='all' or r['source']==source)]
    rows.sort(key=lambda r:(0 if r['status']=='above' else 1,-abs(Decimal(r['delta'])),str(r['order_id'])))
    return rows,direction,source


def render(report,cid,report_id,args):
    esc=lambda v:escape(str(v),quote=True)
    review=report.get('freight_review') if report else None
    comp=review['comparison'] if review else report.get('sales_comparison') if report else None
    compared=int(comp.get('compared_orders',0)) if comp else 0
    out="<section class='fa-panel fa-differences' id='fa-differences'><div class='fa-section-head'><div><span class='fa-kicker'>O que merece conferência</span><h3>Diferenças no frete</h3></div>"
    if report:out+="<span class='fa-tag'>"+show_date(report.get('period_start'))+' a '+show_date(report.get('period_end'))+'</span>'
    out+='</div>'
    if not comp:
        return out+"<div class='fa-empty'><h4>Envie um relatório para encontrar diferenças</h4><p>A comparação usa o frete da planilha e o frete registrado na tela de Vendas desta loja.</p><a href='#fa-upload'>Analisar um relatório</a></div></section>"
    attention=int(comp['above'])+int(comp['below'])
    out+='<p>'+('Pedidos com diferença: <strong>'+str(attention)+'</strong> de <strong>'+str(compared)+'</strong> comparáveis.' if compared else 'Ainda não há pedidos com frete comparável. Confira as pendências de vínculo abaixo.')+'</p>'
    out+="<div class='fa-difference-cards'>"
    for label,key,count,kind in [('A mais na planilha','above_total','above','above'),('A menos na planilha','below_total','below','below')]:
        amount=format_brl(comp[key]) if compared and key in comp else 'Não registrado' if compared else 'Não comparável'
        out+="<article class='fa-diff-"+kind+"'><span>"+label+'</span><strong>'+amount+'</strong><small>Pedidos: '+str(comp[count])+' · em relação ao frete em Vendas</small></article>'
    out+="<article><span>Dentro da tolerância</span><strong>"+(str(comp['within']) if compared else '—')+'</strong><small>pedidos · tolerância de R$ 0,01</small></article></div>'
    if compared:
        out+="<p class='fa-caption'>Frete comparado: planilha <b>"+format_brl(comp['charged_total'])+'</b> · Vendas <b>'+format_brl(comp['sales_total'])+'</b>. Referência real em '+str(comp['real_orders'])+' pedidos e estimada em '+str(comp['estimated_orders'])+'.</p>'
    out+="<p class='fa-caption'>Diferença é um sinal para investigar. Referência estimada não equivale a tarifa contratada nem comprova cobrança indevida.</p>"
    if not review:
        out+="<div class='fa-missing-detail'><strong>Este relatório ainda não tem a lista por venda.</strong><p>Selecione novamente o mesmo arquivo e clique em Analisar diferenças. Os indicadores originais serão preservados, sem duplicar a importação.</p><a href='#fa-upload'>Detalhar este relatório</a></div>"
    else:
        rows,direction,source=filtered(review,args)
        try:page=max(1,int(args.get('pagina','1')))
        except (ValueError,TypeError):page=1
        pages=max(1,(len(rows)+49)//50);page=min(page,pages)
        out+="<div class='fa-section-head fa-order-heading'><div><h4>Venda por venda</h4><p>"+str(len(rows))+" diferenças neste filtro. Valores a mais primeiro; maiores diferenças no início de cada grupo.</p></div>"
        params=dict(direcao=direction,fonte=source)
        if report_id:
            out+="<a class='fa-export' href='/auditoria-frete/"+str(int(cid))+'/relatorios/'+str(int(report_id))+'/diferencas.csv?'+esc(urlencode(params))+"'>Baixar diferenças filtradas (CSV)</a>"
        out+="</div><form class='fa-order-filter' method='get'>"
        if report_id:out+="<input type='hidden' name='relatorio' value='"+str(int(report_id))+"'>"
        for name,label,current,options in [('direcao','Diferença',direction,[('above','A mais na planilha'),('below','A menos na planilha'),('all','Todas as diferenças')]),('fonte','Frete de referência',source,[('all','Real e estimado'),('real','Somente real'),('estimado','Somente estimado')])]:
            out+='<label>'+label+'<select name="'+name+'">'+''.join('<option value="'+value+'"'+(' selected' if value==current else '')+'>'+text+'</option>' for value,text in options)+'</select></label>'
        out+="<button class='fa-secondary'>Aplicar filtros</button></form><div class='fa-table-scroll' role='region' aria-label='Diferenças de frete por venda' tabindex='0'><table class='fa-order-table'><thead><tr><th>Pedido</th><th>Envio</th><th>Planilha</th><th>Vendas</th><th>Diferença</th><th>Referência</th><th>Vínculo conferido</th></tr></thead><tbody>"
        for row in rows[(page-1)*50:page*50]:
            out+='<tr><th scope="row" class="fa-order-id">'+esc(row['order_id'])+'</th><td class="fa-order-id">'+esc(row['shipment_id'] or 'Não informado')+'</td><td>'+format_brl(row['charged'])+'</td><td>'+format_brl(row['baseline'])+'</td><td class="fa-delta '+row['status']+'">'+('+' if Decimal(row['delta'])>0 else '')+format_brl(row['delta'])+'</td><td>'+('Real' if row['source']=='real' else 'Estimada')+'</td><td>'+esc(row['matched_by'])+'</td></tr>'
        if not rows:out+='<tr><td colspan="7">Nenhuma diferença neste filtro. Outros pedidos podem estar sem comparação.</td></tr>'
        out+='</tbody></table></div><nav class="fa-pagination" aria-label="Paginação das diferenças">Página '+str(page)+' de '+str(pages)
        for label,target in [('Anterior',page-1),('Próxima',page+1)]:
            if 1<=target<=pages:
                query=dict(params,pagina=target)
                if report_id:query['relatorio']=report_id
                out+=' <a href="?'+esc(urlencode(query))+'#fa-differences">'+label+'</a>'
        out+='</nav><p class="fa-caption">Conferência registrada em '+show_stamp(review['checked_at'])+'. IDs de pedido e envio podem ser selecionados para copiar. Ao abrir o CSV em uma planilha, importe Pedido e Envio como texto para preservar todos os dígitos.</p>'
    out+="<details class='fa-advanced'><summary>Pedidos e lançamentos sem comparação segura</summary><ul>"
    for label,key in [('Lançamentos sem vínculo na base','unmatched_rows'),('Lançamentos com vínculos conflitantes','ambiguous_rows'),('Pedidos com múltiplos lançamentos ou vínculo ambíguo','ambiguous_orders'),('Pedidos sem frete verificável em Vendas','unavailable_orders'),('Pedidos com valores de frete inválidos','invalid_orders')]:
        out+='<li>'+label+': <b>'+str(comp[key])+'</b></li>'
    return out+'</ul><p>Esses casos não entram na lista de diferenças. Não escolhemos uma venda ou somamos movimentos ambíguos para forçar a comparação.</p></details></section>'


def export_csv(report,args):
    review=report.get('freight_review')
    if not review:return None
    rows,_,_=filtered(review,args)
    def safe(value):
        value=str(value or '')
        return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r')) else value
    stream=io.StringIO();writer=csv.writer(stream,delimiter=';')
    writer.writerow(['Pedido','Envio','Frete na planilha (BRL)','Frete em Vendas (BRL)','Diferença (BRL)','Referência','Vínculo','Data da venda','Conferido em','Início do relatório','Fim do relatório'])
    for r in rows:
        writer.writerow([safe(r['order_id']),safe(r['shipment_id']),r['charged'].replace('.',','),r['baseline'].replace('.',','),r['delta'].replace('.',','),r['source'],safe(r['matched_by']),safe(r['sale_date']),review['checked_at'],report['period_start'],report['period_end']])
    return '\ufeff'+stream.getvalue()


def register_export(app,login_required,can_view,bank,query):
    from freight_store import report_detail
    @app.route('/auditoria-frete/<int:cid>/relatorios/<int:rid>/diferencas.csv')
    @login_required
    def freight_difference_export(cid,rid):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if rid<=0 or rid>=2**63:return 'Relatório não encontrado',404
        with bank() as conn:rows=report_detail(conn,query,cid,rid)
        if not rows:return 'Relatório não encontrado nesta loja',404
        data=rows[0]['resumo'];data=json.loads(data) if isinstance(data,str) else data
        content=export_csv(data,request.args)
        if content is None:return 'Reanalise o arquivo para gerar as diferenças por venda.',404
        return Response(content,mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="diferencas-frete-{cid}-{rid}.csv"','Cache-Control':'no-store'})
