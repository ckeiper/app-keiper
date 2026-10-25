"""Same-store comparison of up to four already verified listing sales rows."""
import re
from datetime import date, timedelta
from urllib.parse import urlencode
from html import escape
from freight_comparison import format_brl


def selection(ranking,listings,args):
    selected=[]
    known=set(str(row['item_id']) for row in listings)|set(ranking.get('rows') or {})
    for i in range(1,5):
        item=str(args.get('comparar'+str(i),'')).strip().upper()
        if not item:continue
        if not re.fullmatch(r'MLB[0-9]{1,20}',item) or item not in known:
            return dict(available=False,ids=[],reason='Há código inválido ou não encontrado nesta loja. Confira a seleção.')
        if item not in selected:selected.append(item)
    if len(selected)<2:
        return dict(available=False,ids=selected,reason='Selecione de dois a quatro anúncios diferentes para comparar.')
    if not ranking.get('available'):
        return dict(available=False,ids=selected,reason='A comparação aguarda vendas e cobertura verificadas nos dois períodos. Dados incompletos não são zero.')
    if any(item not in ranking['rows'] for item in selected):
        return dict(available=False,ids=selected,reason='Há anúncio sem base verificável no ranking carregado.')
    return dict(available=True,ids=selected,reason=None)


def load_visits(conn,query,cid,ids,end,days=7):
    if (type(days) is not int or days not in (7,30) or not 2<=len(ids)<=4 or len(set(ids))!=len(ids)
            or any(not re.fullmatch(r'MLB[0-9]{1,20}',item) for item in ids)):
        return {}
    from investigation_evidence import window, date_key
    dates=[(end-timedelta(days=2*days-1-i)).isoformat() for i in range(2*days)]
    rows=query(conn,"""SELECT conexao_id,item_id,dia,visitas FROM item_visits_daily
        WHERE conexao_id=%s AND item_id=ANY(%s) AND dia BETWEEN %s AND %s
        ORDER BY item_id,dia""",(cid,ids,dates[0],dates[-1]))
    result={}
    for item in ids:
        selected=[row for row in rows if row.get('conexao_id')==cid and str(row.get('item_id'))==item]
        result[item]={name:window(selected,period,['visitas'],'dia')
                      for name,period in [('previous',dates[:days]),('current',dates[days:])]}
        by_day={}
        for row in selected:by_day.setdefault(date_key(row.get('dia')),[]).append(row)
        daily={}
        for day in dates:
            reading=window(by_day.get(day,[]),[day],['visitas'],'dia')
            daily[day]=reading['totals']['visitas'] if reading['complete'] else None
        result[item]['daily']=daily
    return result


def visit_cell(metrics,visits,key,days):
    before=(visits or {}).get('previous') or dict(complete=False,covered=0,expected=days,totals=None)
    after=(visits or {}).get('current') or dict(complete=False,covered=0,expected=days,totals=None)
    if key=='visit_coverage':
        return str(before['covered'])+'/'+str(days)+' → '+str(after['covered'])+'/'+str(days)+' dias válidos'
    if key=='visits':
        return ' → '.join(str(int(p['totals']['visitas'])) if p['complete'] else 'Indisponível' for p in [before,after])
    if not before['complete'] or not after['complete'] or not before['totals']['visitas'] or not after['totals']['visitas']:
        return 'Indisponível'
    old=metrics['previous_orders']*100/before['totals']['visitas']
    new=metrics['orders']*100/after['totals']['visitas']
    return format(old,'.2f').replace('.',',')+'% → '+format(new,'.2f').replace('.',',')+'%'


def render_daily(cid,ids,names,visits,args,end,days):
    if visits is None:return ''
    dates=[(end-timedelta(days=i)).isoformat() for i in range(2*days)]
    pages=(len(dates)+6)//7
    try:page=max(1,min(pages,int(args.get('leituras_pagina','1'))))
    except (ValueError,TypeError):page=1
    esc=lambda value:escape(str(value),quote=True)
    current_start=(end-timedelta(days=days-1)).isoformat()
    out='<details class="lc-daily" id="lc-leituras"'+(' open' if args.get('leituras_pagina') else '')+'><summary>Conferir visitas por dia e lacunas</summary><p>Sete datas por página, das mais recentes às mais antigas. Sem dado válido indica leitura ausente, inválida ou duplicada; não equivale a zero.</p><div class="lc-scroll lc-daily-scroll" tabindex="0" role="region" aria-label="Leituras diárias de visitas"><table><thead><tr><th scope="col">Data e período</th>'
    for item in ids:out+='<th scope="col">'+esc(names.get(item,item))+'<small>'+esc(item)+'</small></th>'
    out+='</tr></thead><tbody>'
    for day in dates[(page-1)*7:page*7]:
        out+='<tr><th scope="row">'+date.fromisoformat(day).strftime('%d/%m/%Y')+'<small>'+('Atual' if day>=current_start else 'Anterior')+'</small></th>'
        for item in ids:
            value=(visits.get(item) or {}).get('daily',{}).get(day)
            out+='<td>'+('Sem dado válido' if value is None else esc(int(value)))+'</td>'
        out+='</tr>'
    out+='</tbody></table></div><nav class="lc-daily-pages" aria-label="Paginação das visitas comparadas">Página '+str(page)+' de '+str(pages)
    for label,target in [('Anterior',page-1),('Próxima',page+1)]:
        if 1<=target<=pages:
            params={'comparar'+str(i):item for i,item in enumerate(ids,1)}
            params.update(dias=str(days),leituras_pagina=str(target))
            out+=' <a href="/ranking-anuncios/'+str(int(cid))+'?'+esc(urlencode(params))+'#lc-leituras">'+label+'</a>'
    return out+'</nav></details>'


def render(cid,ranking,listings,args,end,days=7,visits=None):
    esc=lambda value:escape(str(value),quote=True)
    result=selection(ranking,listings,args)
    path='/ranking-anuncios/'+str(int(cid))
    names={str(row['item_id']):str(row.get('titulo') or row['item_id']) for row in listings}
    out=STYLE+'<section class="lc" id="lc-comparacao" aria-label="Comparar anúncios"><h3>Comparar anúncios lado a lado</h3><p>Dois a quatro anúncios da mesma loja, nos mesmos períodos encerrados. Códigos repetidos aparecem uma vez.</p><form class="lc-form" method="get" action="'+path+'#lc-comparacao">'
    for i in range(1,5):
        value=str(args.get('comparar'+str(i),'')).strip()[:23]
        out+='<label>Anúncio '+str(i)+'<input name="comparar'+str(i)+'" list="lc-products-'+str(int(cid))+'" maxlength="23" pattern="[Mm][Ll][Bb][0-9]{1,20}" placeholder="Código MLB" value="'+esc(value)+'"></label>'
    out+='<label>Período<select name="dias">'+''.join('<option value="'+str(n)+'"'+(' selected' if days==n else '')+'>'+str(n)+' dias</option>' for n in (7,30))+'</select></label><button>Comparar</button><a href="'+path+'?dias='+str(days)+'#lc-comparacao">Limpar seleção</a></form>'
    suggestions=sorted(names,key=lambda key:(names[key].casefold(),key))[:200]
    out+='<datalist id="lc-products-'+str(int(cid))+'">'+''.join('<option value="'+esc(item)+'" label="'+esc(names[item])+'"></option>' for item in suggestions)+'</datalist>'
    if len(names)>200:out+='<p>Sugestões limitadas a 200 anúncios. Você pode informar o código completo de outro anúncio desta loja.</p>'
    if not result['available']:return out+'<p class="lc-notice" role="status">'+esc(result['reason'])+'</p></section>'
    start=end-timedelta(days=days-1);old_end=start-timedelta(days=1);old_start=old_end-timedelta(days=days-1)
    out+='<p>Anterior: '+old_start.strftime('%d/%m/%Y')+' a '+old_end.strftime('%d/%m/%Y')+' · Atual: '+start.strftime('%d/%m/%Y')+' a '+end.strftime('%d/%m/%Y')+'.</p><p>Deslize a tabela no celular para conferir todas as colunas. Em cada célula: anterior → atual.</p><div class="lc-scroll lc-main-scroll" tabindex="0" role="region" aria-label="Tabela comparativa com rolagem"><table><thead><tr><th scope="col">Indicador</th>'
    for item in result['ids']:
        out+='<th scope="col"><a href="/diagnostico/'+str(int(cid))+'/'+item+'">'+esc(names.get(item,item))+'</a><small>'+esc(item)+'</small></th>'
    out+='</tr></thead><tbody>'
    for label,key in [('Valor bruto dos itens','value'),('Pedidos com este anúncio','orders'),('Unidades vendidas','units'),('Valor dos itens por pedido','ticket'),('Variação do valor bruto','delta'),('Visitas registradas','visits'),('Cobertura das visitas','visit_coverage'),('Pedidos pagos ÷ visitas','orders_per_visit')]:
        out+='<tr><th scope="row">'+label+'</th>'
        for item in result['ids']:
            row=ranking['rows'][item]
            if key in ('visits','visit_coverage','orders_per_visit'):
                text=visit_cell(row,(visits or {}).get(item),key,days)
            elif key=='ticket':
                before=row['previous_value']/row['previous_orders'] if row['previous_orders'] else None
                after=row['value']/row['orders'] if row['orders'] else None
                text=('Sem pedidos' if before is None else format_brl(before))+' → '+('Sem pedidos' if after is None else format_brl(after))
            elif key=='delta':
                delta=row['value']-row['previous_value']
                percent=delta*100/row['previous_value'] if row['previous_value'] else None
                text=('+ ' if delta>0 else '')+format_brl(delta)+' · '+(format(percent,'.2f').replace('.',',')+'%' if percent is not None else 'Sem base percentual anterior')
            else:
                before,after=row['previous_'+key],row[key]
                text=(format_brl(before)+' → '+format_brl(after)) if key=='value' else str(before)+' → '+str(after)
            out+='<td>'+esc(text)+'</td>'
        out+='</tr>'
    out+='</tbody></table></div>'
    out+=render_daily(cid,result['ids'],names,visits,args,end,days)
    return out+'<p>Valor bruto dos itens vendidos, sem cálculo de lucro, margem ou Ads. Pedidos pagos ÷ visitas é um indicador observacional, não a conversão oficial do Mercado Livre. Cobertura parcial não é somada como total; zero visitas não gera taxa. A taxa exige cobertura completa e visitas positivas nos dois períodos. Um pedido com mais de um anúncio pode aparecer em mais de uma coluna; não some os pedidos das colunas. O valor por pedido pode variar por quantidade, variações e descontos. Comparação descritiva, sem atribuição causal.</p></section>'


STYLE='''<style>
body .conteudo .lc{background:#102238;color:#eaf2ff;border:1px solid #34516e;border-radius:15px;padding:20px;margin:18px 0;min-width:0;max-width:100%;box-sizing:border-box}
body .conteudo .lc h3{color:#eaf2ff;margin:0 0 12px}body .conteudo .lc p{color:#bdcce1;font-size:12px;line-height:1.7}.lc-form{display:flex;gap:10px;flex-wrap:wrap;align-items:end}.lc-form label{display:grid;gap:6px;font-size:12px;color:#bdcce1;flex:1 1 130px;min-width:0}.lc-form input,.lc-form select{box-sizing:border-box;width:100%;min-width:0;background:#0b192c;color:#eaf2ff;border:1px solid #426184;border-radius:8px;padding:11px;font:inherit}.lc-form button{background:#287ac1;color:#fff;border:0;border-radius:8px;padding:12px 18px;cursor:pointer}body .conteudo .lc a{color:#b9e5ff;text-decoration:none}.lc small{display:block;color:#bdcce1;margin-top:6px}.lc-scroll{overflow-x:auto;max-width:100%;margin-top:14px}.lc table{width:100%;min-width:650px;border-collapse:collapse}.lc th,.lc td{padding:13px;border-bottom:1px solid #426184;text-align:left;font-size:12px;min-width:145px;overflow-wrap:anywhere}body .conteudo .lc table th,body .conteudo .lc table td{background:#182e49;color:#eaf2ff}.lc-daily{margin-top:16px;border-top:1px solid #426184;padding-top:12px}.lc-daily summary{cursor:pointer;color:#b9e5ff;padding:10px 0;font-weight:700}.lc-daily-pages{display:flex;gap:16px;flex-wrap:wrap;margin:14px 0;color:#bdcce1;font-size:12px}.lc-notice{padding:12px;background:#3b3020;border:1px solid #836b34;border-radius:9px}.lc :focus-visible{outline:3px solid #85c8ec;outline-offset:3px}@media(max-width:600px){body .conteudo .lc{padding:14px}.lc-form label{flex-basis:calc(50% - 10px)}}
</style>'''
