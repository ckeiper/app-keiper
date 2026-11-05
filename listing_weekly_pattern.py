"""Descriptive weekday distribution over eight closed calendar weeks. No prediction."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from html import escape
from statistics import median
import re

from listing_sales import listing_sales_summary
from profitability_store import read_sales_context
from sales_metrics import created_day, reporting_today

WEEKS=8
WEEKDAYS=('Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo')


def window(today):
    end=today-timedelta(days=today.weekday()+1)
    return end-timedelta(days=WEEKS*7-1),end


def analyze(context,cid,item,today):
    start,end=window(today)
    days=[start+timedelta(days=i) for i in range(WEEKS*7)]
    covered={str(day) for day in context['coverage']}
    result=dict(start=start,end=end,coverage=[dict(day=d,covered=d.isoformat() in covered) for d in days],
                covered=sum(d.isoformat() in covered for d in days),available=False,reason=None,rows=[],daily=[])
    if context['pending']:
        result['reason']='Há pedidos ainda não verificados nesta loja.'
        return result
    orders,items=context['orders'],context['items']
    if any(r.get('conexao_id')!=cid for r in orders+items):
        result['reason']='Escopo da base de vendas não verificável.'
        return result
    # Reuse the strict existing gates across the whole window before describing any day.
    summary=listing_sales_summary(orders,items,covered,item,end=end,days=len(days))
    if summary['orders'] is None:
        result['reason']=summary['reason']
        return result
    by_day=defaultdict(list);by_item_day=defaultdict(list);order_days={}
    for row in orders:
        day=created_day(row.get('criado_em'))
        if day and start<=day<=end:
            by_day[day].append(row)
            order_days[(row['conexao_id'],str(row['pedido_id']))]=day
    for row in items:
        day=order_days.get((row['conexao_id'],str(row['pedido_id'])))
        if day:by_item_day[day].append(row)
    daily=[dict(day=d,**listing_sales_summary(by_day[d],by_item_day[d],covered,item,end=d,days=1)) for d in days]
    if any(r['units'] is None for r in daily):
        result['reason']='Distribuição diária não verificável.'
        return result
    rows=[]
    for weekday,label in enumerate(WEEKDAYS):
        sample=[r for r in daily if r['day'].weekday()==weekday]
        values=[r['units'] for r in sample];total=sum(values)
        rows.append(dict(label=label,total=total,mean=Decimal(total)/WEEKS,median=median([Decimal(v) for v in values]),
            minimum=min(values),maximum=max(values),selling_weeks=sum(v>0 for v in values),
            share=Decimal(total)*100/summary['units'] if summary['units'] else None))
    result.update(available=True,rows=rows,daily=daily,summary=summary)
    return result


def render(cid,item,shop,data):
    esc=lambda v:escape(str(v),quote=True)
    number=lambda v:format(v,'.1f').replace('.',',')
    fmt=lambda d:d.strftime('%d/%m/%Y')
    path=f'/anuncios/{int(cid)}/{item}'
    out=STYLE+'<section class="wp"><header><h2>Padrão semanal de vendas</h2><p>'+esc(shop.get('titulo') or item)+' · '+esc(item)+'</p><p>'+fmt(data['start'])+' a '+fmt(data['end'])+' · oito semanas completas, de segunda a domingo · Brasília</p><a class="wp-back" href="/diagnostico/'+str(int(cid))+'/'+esc(item)+'">Voltar ao diagnóstico</a></header>'
    out+='<div class="wp-coverage"><strong>Cobertura da loja: '+str(data['covered'])+' de 56 dias</strong><progress max="56" value="'+str(data['covered'])+'" aria-label="Dias com cobertura de vendas">'+str(data['covered'])+'/56</progress></div>'
    if not data['available']:
        out+='<p class="wp-notice" role="status">Análise indisponível · '+esc(data['reason'])+'</p><p>A distribuição será exibida quando os 56 dias tiverem cobertura e os pedidos e itens forem verificáveis.</p>'
    else:
        s=data['summary']
        out+='<div class="wp-stats"><article><strong>'+str(s['units'])+'</strong><span>Unidades vendidas</span></article><article><strong>'+str(s['orders'])+'</strong><span>Pedidos com este anúncio</span></article><article><strong>8</strong><span>Ocorrências de cada dia da semana</span></article></div>'
        out+='<h3>Unidades por dia da semana</h3><p>Média por ocorrência do dia, incluindo os dias sem venda. As barras usam a mesma escala.</p><div class="wp-chart" role="img" aria-label="Média de unidades vendidas por dia da semana; valores detalhados na tabela abaixo">'
        maximum=max([r['mean'] for r in data['rows']]+[Decimal(1)])
        for row in data['rows']:
            width=number(row['mean']*100/maximum).replace(',','.')
            out+='<div class="wp-bar-row"><span>'+row['label']+'</span><div class="wp-track"><div class="wp-bar" style="width:'+width+'%"></div></div><strong>'+number(row['mean'])+'</strong></div>'
        out+='</div><div class="wp-table-wrap" role="region" aria-label="Distribuição semanal detalhada" tabindex="0"><table><caption>Unidades vendidas · oito observações por dia da semana</caption><thead><tr><th scope="col">Dia</th><th scope="col">Total</th><th scope="col">Média</th><th scope="col">Mediana</th><th scope="col">Mín.–máx.</th><th scope="col">Semanas com venda</th><th scope="col">Participação</th></tr></thead><tbody>'
        for row in data['rows']:
            out+='<tr><th scope="row">'+row['label']+'</th><td>'+str(row['total'])+'</td><td>'+number(row['mean'])+'</td><td>'+number(row['median'])+'</td><td>'+str(row['minimum'])+'–'+str(row['maximum'])+'</td><td>'+str(row['selling_weeks'])+'/8</td><td>'+(number(row['share'])+'%' if row['share'] is not None else '—')+'</td></tr>'
        out+='</tbody></table></div>'
        if not s['units']:out+='<p class="wp-notice">Nenhuma unidade vendida na base verificada desta janela. Participação não calculada.</p>'
    out+='<details><summary>Cobertura diária e critérios</summary><p>Fonte: pedidos pagos em BRL, com pagamento aprovado e itens mapeados. Data de criação do pedido em Brasília; cancelados e pagamentos não aprovados ficam fora. A cobertura é da coleta de vendas da loja, sem medir disponibilidade do anúncio. A semana em curso fica fora.</p><p>Média = unidades totais do dia ÷ 8. Mediana = centro das oito observações. Participação = unidades do dia ÷ unidades da janela. Dias sem venda entram como zero somente com a base integral verificada.</p><p>Histórico descritivo da janela, sem previsão ou sazonalidade anual validada. Não desconta períodos antes da criação, pausas ou ruptura; não controla promoções, preço, feriados ou campanhas e não identifica causas.</p><div class="wp-days">'
    for row in data['coverage']:
        out+='<span class="'+('wp-covered' if row['covered'] else 'wp-missing')+'" title="'+fmt(row['day'])+'">'+fmt(row['day'])+' · '+('coleta coberta' if row['covered'] else 'sem cobertura')+'</span>'
    return out+'</div></details></section>'


def register(app,login_required,can_view,bank,query,execute,shop_page,today=reporting_today):
    from flask import session
    @app.route('/anuncios/<int:cid>/<item_id>/padrao-semanal',methods=['GET'])
    @login_required
    def listing_weekly_pattern(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        day=today();start,end=window(day)
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            shops=query(conn,'''SELECT c.cliente,a.titulo FROM conexoes c JOIN anuncios a ON a.conexao_id=c.id
                WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
            if not shops:return 'Anúncio não encontrado nesta loja.',404
            context=read_sales_context(conn,query,cid,start,end)
        return shop_page('Padrão semanal de vendas',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,shops[0],analyze(context,cid,item_id,day)))


STYLE='''<style>.wp{background:#102238;color:#eaf2ff;border:1px solid #34516e;border-radius:16px;padding:22px;min-width:0;box-sizing:border-box}.wp :is(h2,h3,strong){color:inherit}.wp h2{font-size:23px}.wp h3{font-size:17px}.wp p,.wp span,.wp td,.wp th,.wp summary,.wp a{font-size:12px;line-height:1.6}.wp p{color:#bdcce1}.wp a{color:#b9e5ff}.wp header{margin-bottom:20px}.wp-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:20px 0}.wp-stats article{display:grid;gap:7px;background:#182e49;border:1px solid #426184;border-radius:12px;padding:16px;overflow-wrap:anywhere}.wp-stats strong{font-size:25px}.wp-coverage{display:grid;gap:10px;font-size:13px}.wp progress{width:100%;height:9px;accent-color:#5daff0}.wp-chart{display:grid;gap:12px;margin:22px 0}.wp-bar-row{display:grid;grid-template-columns:65px 1fr 50px;gap:10px;align-items:center}.wp-bar-row strong{font-size:13px;text-align:right}.wp-track{background:#2b425c;height:12px;border-radius:6px;overflow:hidden}.wp-bar{height:100%;background:linear-gradient(90deg,#4989ed,#55c8d3);border-radius:6px}.wp-table-wrap{overflow-x:auto;max-width:100%;margin:22px 0}.wp table{border-collapse:collapse;min-width:660px;width:100%}.wp th,.wp td{text-align:right;padding:11px;border-bottom:1px solid #426184;white-space:nowrap}.wp th:first-child{text-align:left}.wp caption{text-align:left;font-size:12px;margin-bottom:10px}.wp-notice{border-left:3px solid #e6bb68;padding:12px;background:#182e49}.wp details{margin-top:24px}.wp summary{cursor:pointer;font-weight:bold}.wp-days{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.wp-days span{padding:8px;border:1px solid #426184;border-radius:7px;overflow-wrap:anywhere}.wp-missing{border-style:dashed!important}.wp :focus-visible{outline:3px solid #6bbcf4;outline-offset:3px}@layer keiper-appearance{html[data-theme=light] body .wp{background:#fff!important;color:#172d47!important;border-color:#d4dfec!important}html[data-theme=light] body .wp :is(.wp-stats article,.wp-notice){background:#f2f6fb!important;color:#172d47!important}html[data-theme=light] body .wp .wp-track{background:#e2eaf5!important}}@media(max-width:650px){.wp{padding:14px}.wp-stats{grid-template-columns:1fr}.wp-stats article{grid-template-columns:70px 1fr;align-items:center}.wp-days{grid-template-columns:repeat(2,minmax(0,1fr))}.wp-bar-row{grid-template-columns:54px 1fr 45px;gap:7px}}</style>'''
