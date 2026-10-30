"""Read-only geographic sales panel with explicit destination and sales coverage."""
import json
from functools import lru_cache
from html import escape
from pathlib import Path
from urllib.parse import urlencode
from sales_geography import STATES, summarize
from sales_metrics import period
from sales_view import SALES_STYLE, fmt


@lru_cache(maxsize=1)
def paths():
    return json.loads((Path(__file__).parent/'assets/brazil_states_paths.json').read_text())


def load(bank,query,cid,args):
    start,end,_,_=period(args)
    with bank() as conn:
        shops=query(conn,'SELECT cliente FROM conexoes WHERE id=%s',(cid,))
        if not shops:return None
        rows=query(conn,'''SELECT p.pedido_id,p.status,p.total,p.moeda,p.criado_em,p.pagamentos_json,p.unidades,d.uf
            FROM pedidos p LEFT JOIN vendas_destinos d ON d.conexao_id=p.conexao_id AND d.pedido_id=p.pedido_id
            WHERE p.conexao_id=%s AND p.vendas_verificado_em IS NOT NULL''',(cid,))
        coverage=query(conn,'SELECT dia FROM vendas_cobertura WHERE conexao_id=%s',(cid,))
    return shops[0]['cliente'],start,end,summarize(rows,start,end,{r['dia'] for r in coverage})


def render(cid,args,start,end,data):
    metric=args.get('metrica','receita')
    key='orders' if metric=='pedidos' else 'revenue'
    title='Pedidos pagos' if key=='orders' else 'Faturamento bruto'
    money=lambda v:fmt(v,True)
    out=SALES_STYLE+STYLE+"<section class='card'><h2>Mapa de vendas por estado</h2><p>Destino do envio · "+start.strftime('%d/%m/%Y')+' a '+end.strftime('%d/%m/%Y')+"</p><a href='/vendas/"+str(cid)+"'>Voltar às vendas</a></section>"
    out+="<form class='card' method='get'><label>Período<select name='periodo'>"+''.join("<option value='"+str(n)+"'"+(' selected' if args.get('periodo','30')==str(n) else '')+">"+str(n)+' dias</option>' for n in (7,15,30,60,90))+"<option value='personalizado'"+(' selected' if args.get('periodo')=='personalizado' else '')+">Personalizado</option></select></label>"
    for name,label,value in [('inicio','De',start.isoformat()),('fim','Até',end.isoformat())]:out+="<label>"+label+"<input type='date' name='"+name+"' value='"+value+"'></label>"
    out+="<label>Colorir por<select name='metrica'><option value='receita'"+(' selected' if key=='revenue' else '')+">Faturamento</option><option value='pedidos'"+(' selected' if key=='orders' else '')+">Pedidos</option></select></label><button type='submit'>Aplicar</button></form>"
    share=100*data['known']/data['total'] if data['total'] else None
    out+="<div class='grid'>"
    for label,value in [('Pedidos pagos registrados',str(data['total'])),('Faturamento bruto registrado',money(data['revenue'])),('Pedidos com UF confirmada',str(data['known'])),('Cobertura de destinos',format(share,'.1f').replace('.',',')+'%' if share is not None else 'Sem pedidos')]:out+="<article class='stat'><div class='lab'>"+label+"</div><div class='num'>"+value+"</div></article>"
    out+='</div>'
    out+="<details class='card'><summary>Critérios e cobertura</summary><p>Dias com coleta de vendas completa: <strong>"+str(data['covered'])+' de '+str(data['days'])+"</strong>. Valores dos pedidos pagos em BRL com pagamento aprovado e data de criação válida, em Brasília. São registros disponíveis, sem estimar vendas ausentes nem subtrair devoluções e reembolsos.</p>"
    out+='<p>UF é o destino do envio, não o domicílio do comprador. Cada pedido conta uma vez, inclusive em envios compartilhados. Pedidos sem UF confirmada ficam separados do mapa.</p>'
    out+='<p>O histórico de destinos é preenchido progressivamente nas atualizações de Vendas.</p>'
    if data['covered']<data['days'] or data['invalid'] or data['unlocated']:out+="<div class='aviso'>Base parcial: "+str(data['days']-data['covered'])+' dia(s) sem cobertura completa; '+str(data['invalid'])+' pedido(s) do período excluídos por campos inválidos; '+str(data['unlocated'])+' registro(s) sem data utilizável na base. Não representam zero vendas.</div>'
    out+='</details>'
    out+="<section class='card'><h3>"+title+" por UF</h3><p>Azul mais intenso indica maior valor registrado. Cinza indica nenhuma venda com destino confirmado na base selecionada.</p><svg class='sg-map' viewBox='0 0 580 590' role='img' aria-labelledby='sg-title sg-desc'><title id='sg-title'>Distribuição das vendas por estado brasileiro</title><desc id='sg-desc'>Valores completos e acessíveis na tabela abaixo. Estados sem vendas localizadas não comprovam ausência de vendas.</desc>"
    maximum=max((r[key] for r in data['states'].values()),default=0)
    for uf,path in paths().items():
        row=data['states'][uf];value=row[key]
        color='#62758b' if not value else ['#9ed3ff','#65b4f4','#338fda','#1b66b0','#114b87'][min(4,int(float(value/maximum)*4))]
        label=STATES[uf]+': '+(str(value)+' pedidos' if key=='orders' else money(value))
        out+="<path class='sg-state' data-uf='"+uf+"' d='"+path+"' fill='"+color+"'><title>"+escape(label)+"</title></path>"
    out+="</svg><p class='muted'>Limites geográficos simplificados.</p><div class='sg-scroll'><table><thead><tr><th>Estado</th><th>Pedidos</th><th>Faturamento bruto</th><th>Participação no total registrado</th><th>Ticket por pedido</th></tr></thead><tbody>"
    ranking=sorted(data['states'].items(),key=lambda pair:(-pair[1][key],STATES[pair[0]]))
    for uf,row in ranking+[(None,data['missing'])]:
        label=STATES[uf]+' ('+uf+')' if uf else 'Destino não identificado'
        share=100*row['revenue']/data['revenue'] if data['revenue'] else None
        out+='<tr><th scope="row">'+label+'</th><td>'+str(row['orders'])+'</td><td>'+money(row['revenue'])+'</td><td>'+(format(share,'.1f').replace('.',',')+'%' if share is not None else '—')+'</td><td>'+(money(row['revenue']/row['orders']) if row['orders'] else '—')+'</td></tr>'
    return out+'</tbody></table></div><p>Participação calculada sobre todo o faturamento registrado, incluindo destinos não identificados. Não é participação no mercado.</p></section>'


def register(app,login_required,can_view,bank,query,page):
    from flask import request
    @app.get('/vendas/<int:cid>/estados')
    @login_required
    def sales_state_map(cid):
        if not can_view(cid):return 'Acesso restrito',403
        try:data=load(bank,query,cid,request.args)
        except ValueError as error:return escape(str(error)),400
        if data is None:return 'Loja não encontrada',404
        shop,start,end,report=data
        return page('Vendas por estado',cid,shop,'vendas',render(cid,request.args,start,end,report))

STYLE='''<style>.sg-map{display:block;width:100%;max-width:660px;height:auto;margin:16px auto}.sg-state{stroke:#edf5ff;stroke-width:.8;vector-effect:non-scaling-stroke}.sg-state:hover{stroke:#ffc765;stroke-width:2}.sg-scroll{overflow-x:auto}.sg-scroll table{width:100%;min-width:650px;border-collapse:collapse}.sg-scroll th,.sg-scroll td{padding:12px;text-align:left;border-bottom:1px solid #3a5772;font-size:12px}</style>'''
