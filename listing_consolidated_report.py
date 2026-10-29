"""Snapshot-consistent listing report and actual server-generated PDF download."""
import io
import re
import time
from datetime import datetime,timedelta
from html import escape
from sales_metrics import reporting_today,SAO_PAULO,created_day
from profitability_store import summarize_context,read_sales_context,result_for
from listing_sales import listing_sales_summary
from investigation_evidence import window
from listing_full_sales_chart import daily_full_status
from offer_history import daily_readings,confirmed_price
from listing_review_report import load as load_operational
from listing_content import CRITERIA,STATES as REVIEW_STATES
from listing_tasks import STATES as TASK_STATES
from listing_profitability import COMPONENTS
from listing_priority_sources import listing_signals


def stamp(value):
    try:return datetime.fromtimestamp(int(value),SAO_PAULO).strftime('%d/%m/%Y %H:%M')+' (Brasília)'
    except (ValueError,TypeError,OverflowError,OSError):return 'não informada'


def number(value,money=False):
    if value is None:return 'Indisponível'
    if money:return 'R$ '+format(value,',.2f').replace(',','_').replace('.',',').replace('_','.')
    return str(value)


def load(conn,query,cid,item,days=30,today=None):
    today=today or reporting_today();end=today-timedelta(days=1);start=end-timedelta(days=days-1)
    data=load_operational(conn,query,cid,item)
    if data is None:return None
    previous_end=start-timedelta(days=1);previous_start=previous_end-timedelta(days=days-1)
    context=read_sales_context(conn,query,cid,previous_start,end)
    pair=dict(current=summarize_context(context,cid,item,start,end),previous=summarize_context(context,cid,item,previous_start,previous_end),previous_start=previous_start,previous_end=previous_end)
    bounds=(cid,item,previous_start.isoformat(),end.isoformat())
    visits=query(conn,'''SELECT dia,visitas FROM item_visits_daily WHERE conexao_id=%s AND item_id=%s
        AND dia BETWEEN %s AND %s ORDER BY dia''',bounds)
    lower=int(datetime.combine(start,datetime.min.time(),SAO_PAULO).timestamp())
    upper=int(datetime.combine(end+timedelta(days=1),datetime.min.time(),SAO_PAULO).timestamp())
    full=query(conn,'''SELECT observed_at,state,logistics,quantity FROM full_observations
        WHERE conexao_id=%s AND item_id=%s AND observed_at >= %s AND observed_at < %s ORDER BY observed_at LIMIT 5001''',(cid,item,lower,upper))
    offers=query(conn,'''SELECT observed_at,price,regular_price,promotion,confirmed FROM listing_offer_observations
        WHERE conexao_id=%s AND item_id=%s AND observed_at >= %s AND observed_at < %s ORDER BY observed_at LIMIT 5001''',(cid,item,lower,upper))
    financial=query(conn,'''SELECT * FROM listing_profitability_records WHERE conexao_id=%s AND item_id=%s
        AND inicio=%s AND fim=%s ORDER BY id DESC LIMIT 1''',(cid,item,start,end))
    history=query(conn,'''SELECT event_date,kind,note,void_at FROM listing_interventions WHERE conexao_id=%s AND item_id=%s
        AND event_date BETWEEN %s AND %s ORDER BY event_date DESC,id DESC LIMIT 51''',(cid,item,start,end))
    ads=query(conn,'''SELECT data,gasto,faturamento,impressoes,cliques FROM ads_dia WHERE conexao_id=%s
        AND data BETWEEN %s AND %s ORDER BY data''',(cid,start.isoformat(),end.isoformat()))
    record=financial[0] if financial else None
    return dict(operational=data,pair=pair,context=context,visits=visits,full=full[:5000],offers=offers[:5000],observations_limited=len(full)>5000 or len(offers)>5000,
                financial=record,contribution=result_for(pair['current'],record),history=history[:50],history_limited=len(history)>50,ads=ads,
                start=start,end=end,days=days)


def sections(data):
    d=data['operational'];shop=d['shop'];pair=data['pair'];start,end=data['start'],data['end'];days=data['days']
    old_dates=[(pair['previous_start']+timedelta(days=i)).isoformat() for i in range(days)]
    dates=[(start+timedelta(days=i)).isoformat() for i in range(days)]
    traffic=[window(data['visits'],period,['visitas'],'dia') for period in (old_dates,dates)]
    metrics=[]
    for label,key,money in [('Pedidos pagos','orders',False),('Unidades','units',False),('Valor bruto dos itens','gross_items',True),('Ticket por pedido do anúncio','ticket',True)]:
        metrics.append([label,number(pair['previous'].get(key),money),number(pair['current'].get(key),money)])
    metrics.append(['Visitas']+[number(p['totals']['visitas']) if p['complete'] else 'Indisponível' for p in traffic])
    conversion=[]
    for sales,vis in zip([pair['previous'],pair['current']],traffic):
        count=vis['totals']['visitas'] if vis['complete'] else None
        conversion.append(format(sales['orders']*100/count,'.2f').replace('.',',')+'%' if count and sales.get('orders') is not None else 'Indisponível')
    metrics.append(['Pedidos / visitas (observacional)']+conversion)
    sections=[dict(title='Desempenho e comparação',note='Períodos encerrados equivalentes. Anterior: '+str(pair['previous_start'])+' a '+str(pair['previous_end'])+'. Somente pedidos pagos/aprovados com vínculo completo dos itens. Valor dos itens não inclui rateio de frete, cupons ou taxas; razão pedidos/visitas não é conversão oficial do Mercado Livre. '+str(pair['current'].get('reason') or '')+' '+str(pair['previous'].get('reason') or ''),columns=['Indicador','Anterior','Atual'],rows=metrics)]
    stock_signal=listing_signals([shop],{},1,now=int(time.time()))[shop['item_id']]
    sections.append(dict(title='Catálogo e revisão de conteúdo',note='Fonte: catálogo sincronizado; estoque atual não reconstrói o histórico. Fotos/clips são contagens e não notas de qualidade.',columns=['Critério','Parecer / leitura','Evidência'],rows=[['Estoque observado',str(stock_signal['stock']) if stock_signal['stock_verified'] else 'Não verificado','Coleta: '+stamp(shop.get('atualizado_em'))],['Fotos / clips',number(shop.get('fotos'))+' / '+number(shop.get('clips')),'Leitura do catálogo']]+[[label,REVIEW_STATES[d['reviews'][code]['verdict']],d['reviews'][code]['note']] if code in d['reviews'] else [label,'Sem revisão',''] for code,(label,_) in CRITERIA.items()]))
    full=daily_full_status(data['full'],dates);prices=daily_readings(data['offers']);daily=[]
    # Classify once; retain invalid dates in each window for the canonical integrity gates.
    by_day={};keys_to_day={};unknown=[];items_by_day={}
    for order in data['context']['orders']:
        day=created_day(order.get('criado_em'))
        if day is None:unknown.append(order);continue
        key=day.isoformat();by_day.setdefault(key,[]).append(order);keys_to_day[(order.get('conexao_id'),str(order.get('pedido_id')))]=key
    for item_row in data['context']['items']:
        day=keys_to_day.get((item_row.get('conexao_id'),str(item_row.get('pedido_id'))))
        if day:items_by_day.setdefault(day,[]).append(item_row)
    for i,day in enumerate(dates):
        sales=listing_sales_summary(by_day.get(day,[])+unknown,items_by_day.get(day,[]),data['context']['coverage'],shop['item_id'],end=start+timedelta(days=i),days=1)
        if data['context']['pending']:sales.update(orders=None,gross_items=None)
        visit=window(data['visits'],[day],['visitas'],'dia')
        price=confirmed_price(prices[day]) if day in prices else None
        daily.append([day,number(sales['orders']),number(sales['gross_items'],True),number(visit['totals']['visitas']) if visit['complete'] else 'Indisp.',('Disponível' if full[i]==1 else 'Sem estoque') if full[i] is not None else 'Não observado',number(price,True)])
    sections.append(dict(title='Série diária: vendas, visitas, Full e preço',note='Ausência de observação não é zero. Full e preço são leituras observadas; não provam disponibilidade contínua nem explicam causalmente vendas.'+(' Limite: primeiras 5.000 observações do período.' if data['observations_limited'] else ''),columns=['Dia','Pedidos','Bruto itens','Visitas','Full observado','Preço final'],rows=daily))
    advertising=window(data['ads'],dates,['gasto','faturamento','impressoes','cliques'],'data')
    adsrows=[]
    for label,key,money in [('Investimento da loja','gasto',True),('Receita atribuída da loja','faturamento',True),('Impressões da loja','impressoes',False),('Cliques da loja','cliques',False)]:adsrows.append([label,number(advertising['totals'][key],money) if advertising['complete'] else 'Indisponível'])
    sections.append(dict(title='Publicidade: contexto da loja',note='Escopo da conta, não deste anúncio. Não há série histórica Ads por item nesta base; esses valores não são rateados nem usados para calcular ROAS/ACOS do anúncio. Cobertura: '+str(advertising['covered'])+'/'+str(days)+' dias.',columns=['Indicador','Valor'],rows=adsrows))
    record=data['financial'];result=data['contribution']
    finance=[['Contribuição documentada',number(result.get('contribution'),True)],['Margem de contribuição',format(result['margin_pct'],'.2f').replace('.',',')+'%' if result.get('margin_pct') is not None else 'Indisponível']]
    if record:
        finance += [[label,number(record['costs'].get(key),True)+' | Fonte: '+str(record['sources'].get(key) or 'não informada')] for key,label in COMPONENTS.items()]
    sections.append(dict(title='Rentabilidade documentada',note='Não é lucro líquido. Custos pertencem ao mesmo anúncio/período e são conferidos contra a versão das vendas. '+str(result.get('reason') or '')+(' Registro #'+str(record['id'])+' em '+str(record['created_at'])+'.' if record else ''),columns=['Componente','Resultado / fonte'],rows=finance))
    sections.append(dict(title='Histórico de ações',note='Registros internos, não confirmação de execução no marketplace. '+('Exibidos os 50 registros mais recentes do período.' if data['history_limited'] else 'Sem reconstrução retroativa.'),columns=['Data','Tipo','Registro'],rows=[[str(r['event_date']),r['kind'],('Desconsiderado: ' if r['void_at'] else '')+r['note']] for r in data['history']] or [['—','—','Sem ações registradas no período.']]))
    sections.append(dict(title='Plano de ação e acompanhamento',note='Totais: '+(' / '.join(TASK_STATES[r['status']]+': '+str(r['n']) for r in d['counts']) or 'sem tarefas')+'. Conclusão humana não comprova alteração no marketplace. '+('Exibidas dez tarefas por prazo; totais incluem todas.' if d['tasks_limited'] else ''),columns=['Prazo','Tarefa','Responsável / situação'],rows=[[str(r['due_date']),r['title'],r['responsible']+' / '+TASK_STATES[r['status']]] for r in d['tasks']] or [['—','Sem tarefas registradas','—']]))
    sections.append(dict(title='Perguntas e limites das fontes',note='Base local preservada, sem ampliar a coleta. Avaliações, posicionamento, sazonalidade e previsão de demanda não têm fonte validada neste relatório. Dados ausentes são indisponíveis, nunca preenchidos por estimativa.',columns=['Status registrado','Quantidade'],rows=[[r['status'] or 'Não informado',str(r['n'])] for r in d['questions']] or [['Sem perguntas na base','Não comprova ausência de dúvidas']]))
    return sections


def html_report(cid,item,data,now):
    from listing_review_report import STYLE
    from theme_switcher import HEAD,SCRIPT
    shop=data['operational']['shop'];params='?dias='+str(data['days'])
    out='<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Relatório consolidado</title>'+HEAD+STYLE+'</head><body><main class="lr-report card"><div class="top" style="display:flex;justify-content:flex-end;margin-bottom:16px"></div><nav class="lr-controls"><a href="/diagnostico/'+str(cid)+'/'+item+'">Voltar ao anúncio</a><a href="/anuncios/'+str(cid)+'/'+item+'/relatorio-consolidado.pdf'+params+'">Baixar PDF</a><button onclick="window.print()">Imprimir</button></nav><header><h1>Relatório consolidado do anúncio</h1><h2>'+escape(shop.get('titulo') or item)+'</h2><p>'+escape(shop['cliente'])+' / '+item+'</p><p>'+str(data['start'])+' a '+str(data['end'])+' / emissão '+datetime.fromtimestamp(now,SAO_PAULO).strftime('%d/%m/%Y %H:%M')+' (Brasília)</p><p><a href="?dias=7">7 dias</a> / <a href="?dias=30">30 dias</a></p></header>'
    for s in sections(data):
        out+='<section><h2>'+s['title']+'</h2><p>'+escape(s['note'])+'</p><div style="overflow-x:auto"><table><thead><tr>'+''.join('<th>'+escape(c)+'</th>' for c in s['columns'])+'</tr></thead><tbody>'
        for r in s['rows']:out+='<tr>'+''.join('<td>'+escape(str(c))+'</td>' for c in r)+'</tr>'
        out+='</tbody></table></div></section>'
    return out+'<footer>Keiper Consultoria / '+item+'</footer></main>'+SCRIPT+'</body></html>'


def pdf_report(cid,item,data,now):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle,KeepTogether,CondPageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab
    from pathlib import Path
    fonts=Path(reportlab.__file__).parent/'fonts'
    if 'KeiperSans' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('KeiperSans',str(fonts/'Vera.ttf')))
        pdfmetrics.registerFont(TTFont('KeiperSans-Bold',str(fonts/'VeraBd.ttf')))
        pdfmetrics.registerFontFamily('KeiperSans',normal='KeiperSans',bold='KeiperSans-Bold')
    buffer=io.BytesIO();styles=getSampleStyleSheet()
    for name in styles.byName:
        styles[name].fontName='KeiperSans-Bold' if name in ('Title','Heading1','Heading2') else 'KeiperSans'
    styles.add(ParagraphStyle(name='BodySmall',fontName='KeiperSans',fontSize=8,leading=11,spaceAfter=5,splitLongWords=True))
    width=A4[0]-80;story=[];shop=data['operational']['shop']
    def p(value,style='BodySmall'):return Paragraph(escape(str(value)).replace('\n','<br/>'),styles[style])
    story+=[p('KEIPER CONSULTORIA','Title'),p('Relatório consolidado do anúncio','Heading1'),p(shop.get('titulo') or item,'Heading2'),p(shop['cliente']+' / '+item),p(str(data['start'])+' a '+str(data['end'])+' / emissão '+datetime.fromtimestamp(now,SAO_PAULO).strftime('%d/%m/%Y %H:%M')+' (Brasília)'),Spacer(1,12)]
    for s in sections(data):
        story.append(CondPageBreak(110))
        story.append(KeepTogether([p(s['title'],'Heading2'),p(s['note'])]))
        rows=[[p(c) for c in s['columns']]]+[[p(c) for c in r] for r in s['rows']]
        table=LongTable(rows,colWidths=[width/len(s['columns'])]*len(s['columns']),repeatRows=1,hAlign='LEFT',splitInRow=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6eff9')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f8fc')]),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#7291b2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.extend([table,Spacer(1,14)])
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('KeiperSans',8);canvas.setFillColor(colors.HexColor('#52657c'));canvas.drawString(40,24,'Keiper Consultoria / '+item);canvas.drawRightString(A4[0]-40,24,'Página '+str(doc.page));canvas.restoreState()
    SimpleDocTemplate(buffer,pagesize=A4,rightMargin=40,leftMargin=40,topMargin=40,bottomMargin=42,title='Relatório '+item,author='Keiper Consultoria').build(story,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()


def register(app,login_required,can_view,bank,query,execute):
    from flask import request,session,Response
    @app.get('/anuncios/<int:cid>/<item_id>/relatorio-consolidado')
    @app.get('/anuncios/<int:cid>/<item_id>/relatorio-consolidado.pdf')
    @login_required
    def listing_consolidated_report(cid,item_id):
        if session.get('tipo')!='admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        if request.args.get('dias','30') not in ('7','30'):return 'Selecione 7 ou 30 dias encerrados.',400
        with bank() as conn:
            execute(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            data=load(conn,query,cid,item_id,int(request.args.get('dias','30')))
        if data is None:return 'Anúncio não encontrado nesta loja.',404
        now=int(time.time())
        if request.path.endswith('.pdf'):
            return Response(pdf_report(cid,item_id,data,now),mimetype='application/pdf',headers={'Content-Disposition':'attachment; filename="relatorio-'+item_id+'.pdf"','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
        return Response(html_report(cid,item_id,data,now),headers={'Cache-Control':'private, no-store'})
