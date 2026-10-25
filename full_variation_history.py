"""Bounded per-variation history from existing cached Full evidence only."""
from collections import defaultdict
from datetime import datetime, time, timedelta
from html import escape
import re
from full_report_components import snapshot, paginate, PAGE_KEYS
from sales_metrics import SAO_PAULO

MAX_READS = 500
MAX_GAP = 6 * 3600


def build(observations,item_id,start,end,selected=None):
    lower=int(datetime.combine(start,time.min,SAO_PAULO).timestamp())
    upper=int(datetime.combine(end+timedelta(days=1),time.min,SAO_PAULO).timestamp())
    grouped=defaultdict(list)
    for row in observations:
        stamp=row.get('observed_at')
        if row.get('item_id')==item_id and type(stamp) is int and lower<=stamp<upper:
            grouped[stamp].append(row)
    stamps=sorted(grouped,reverse=True)
    limited=len(stamps)>MAX_READS
    models={stamp:snapshot(grouped[stamp],item_id,start,end) for stamp in stamps[:MAX_READS]}
    choices=sorted({row['variation'] for model in models.values() for row in model['rows']
                    if re.fullmatch(r'[0-9]{1,20}',row['variation']) and int(row['variation'])>0},key=int)
    selected=choices[0] if selected is None and choices else str(selected or '').strip()
    result=dict(choices=choices,selected=selected,rows=[],limited=limited,loaded=len(models),available=False)
    if not re.fullmatch(r'[0-9]{1,20}',selected) or selected not in choices:
        result['reason']='Selecione um código de variação presente nas consultas carregadas deste anúncio.'
        return result
    rows=[];previous=None
    for stamp,model in sorted(models.items()):
        matches=[row for row in model['rows'] if row['variation']==selected]
        value=matches[0] if len(matches)==1 else None
        row=dict(at=stamp,inventory=value['inventory'] if value else None,
                 quantity=value['quantity'] if value else None,
                 reason=value['reason'] if value else 'Variação ausente, vínculo inválido ou consulta não confirmada',delta=None)
        if (previous and row['quantity'] is not None and previous['quantity'] is not None
                and row['inventory']==previous['inventory'] and 0<stamp-previous['at']<=MAX_GAP):
            row['delta']=row['quantity']-previous['quantity']
        rows.append(row);previous=row
    result.update(available=True,rows=list(reversed(rows)))
    return result


def render(cid,args,listing,observations,start,end):
    args=dict(args,item_id=listing['item_id'])
    model=build(observations,listing['item_id'],start,end,args.get('full_variacao'))
    esc=lambda value:escape(str(value),quote=True)
    out=STYLE+'<details class="card full-variation-history" id="full-historico-variacao"'+(' open' if args.get('full_variacao') or args.get('full_historico_variacao') else '')+'><summary>Histórico de quantidade por variação</summary>'
    out+='<p>'+str(model['loaded'])+' observações carregadas deste anúncio no período, das mais recentes para as antigas; até '+str(MAX_READS)+' observações para esta análise. Quantidades são históricas, sem confirmação do saldo atual.</p>'
    if model['limited']:
        out+='<p>Recorte limitado às '+str(MAX_READS)+' observações mais recentes. Reduza ou altere o período para consultar outro recorte. As demais consultas continuam em Consultas e rastreabilidade.</p>'
    if not model['choices']:
        return out+'<p>Sem código de variação confirmado nas consultas carregadas.</p></details>'
    out+='<form class="full-variation-form" method="get" action="/full/'+str(int(cid))+'#full-historico-variacao">'
    for key in ('item_id','periodo','inicio','fim')+tuple(k for k in PAGE_KEYS if k!='full_historico_variacao'):
        if key in args:out+='<input type="hidden" name="'+key+'" value="'+esc(args[key])+'">'
    out+='<label>Código da variação<input name="full_variacao" value="'+esc(model['selected'][:20])+'" list="full-variation-choices" pattern="[0-9]{1,20}" maxlength="20" required></label><datalist id="full-variation-choices">'+''.join('<option value="'+code+'"></option>' for code in model['choices'][:200])+'</datalist><button>Conferir histórico</button></form>'
    if len(model['choices'])>200:out+='<p>Sugestões limitadas a duzentos códigos; é possível informar outro código presente nas consultas carregadas.</p>'
    if not model['available']:return out+'<p role="status">'+model['reason']+'</p></details>'
    rows,nav=paginate(model['rows'],cid,dict(args,full_variacao=model['selected']),'full_historico_variacao',20,'full-historico-variacao')
    known=sum(row['quantity'] is not None for row in model['rows'])
    out+='<p>Variação '+esc(model['selected'])+': '+str(known)+'/'+str(len(model['rows']))+' observações com quantidade confirmada. Falha ou ausência não equivale a zero. Deslize a tabela no celular.</p><div class="full-table-scroll full-variation-history-scroll" tabindex="0" role="region" aria-label="Histórico de estoque da variação"><table><thead><tr><th scope="col">Quando · Brasília</th><th scope="col">Inventário</th><th scope="col">Quantidade</th><th scope="col">Diferença entre consultas</th><th scope="col">Confirmação</th></tr></thead><tbody>'
    for row in rows:
        delta=row['delta']
        out+='<tr><th scope="row">'+datetime.fromtimestamp(row['at'],SAO_PAULO).strftime('%d/%m/%Y %H:%M:%S')+'</th><td>'+esc(row['inventory'] or 'Não confirmado')+'</td><td>'+('Indisponível' if row['quantity'] is None else str(row['quantity']))+'</td><td>'+('Sem par consecutivo comparável' if delta is None else ('+' if delta>0 else '')+str(delta)+' unidades')+'</td><td>'+esc(row['reason'])+'</td></tr>'
    return out+'</tbody></table></div>'+nav+'<p>Diferença aritmética entre duas consultas consecutivas válidas do mesmo inventário, separadas por até seis horas. Falha, ausência, duplicidade, vínculo compartilhado ou troca de inventário interrompe a comparação. Não identifica entradas, saídas, reposição, reservas ou vendas da variação; não mede duração de ruptura nem prevê demanda.</p></details>'


STYLE='''<style>.full-variation-form{display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin:14px 0}.full-variation-form label{display:grid;gap:6px;font-size:12px;min-width:0;flex:1 1 180px}.full-variation-form input{box-sizing:border-box;width:100%;min-width:0;background:#0b192c;color:#eaf2ff;border:1px solid #426184;border-radius:8px;padding:11px}.full-variation-form button{background:#287ac1;color:#fff;border:0;border-radius:8px;padding:12px 18px;cursor:pointer}.full-variation-history table{min-width:950px}.full-variation-history td,.full-variation-history th{min-width:140px}</style>'''
