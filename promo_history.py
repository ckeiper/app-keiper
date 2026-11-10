"""Readable audit history for promotion participation, without any API writes."""
from html import escape
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
from zoneinfo import ZoneInfo
from section_help import STYLE as HELP_STYLE, section_help

LABELS={'confirmed':('Confirmada','ok'),'rejected':('Recusada','urgente'),
        'uncertain':('Aguardando confirmação','atencao'),
        'sending':('Envio em andamento','atencao')}

def render_history(rows,cid):
    cid=int(cid)
    rows=(rows or [])[:100]
    counts={key:sum(1 for r in rows if r.get('status')==key) for key in LABELS}
    html=HELP_STYLE+'<section class="card" id="historico-adesoes" style="margin-bottom:20px">'
    html+=section_help('Histórico de participações', 'Como ler o histórico de participações',
        '<p>Use Verificar status para consultar uma pendência sem reenviar a adesão.</p>'
        '<p>A MC é a estimativa registrada no envio. Exclui frete, tarifa fixa, publicidade e outros custos. '
        'A estimativa não representa lucro líquido nem margem atual.</p>')
    html+='<p class="sub">Últimas 100 solicitações</p>'
    html+='<div class="grid" style="margin:14px 0">'
    for key in ('confirmed','uncertain','rejected','sending'):
        title,_=LABELS[key]
        html+='<div class="stat"><div class="num">'+str(counts[key])+'</div><div class="lab">'+title+'</div></div>'
    html+='</div>'
    if not rows:
        return html+'<p class="sub">Nenhuma participação enviada por esta loja ainda.</p></section>'
    html+='<div style="overflow-x:auto"><table><thead><tr><th>Anúncio</th><th>Campanha</th><th>Preço enviado</th><th>MC estimada</th><th>Situação</th><th>Quando</th><th>Verificar</th></tr></thead><tbody>'
    for r in rows[:100]:
        raw_item=str(r.get('item_id') or '')
        raw_pid=str(r.get('promocao_id') or '')
        item=escape(raw_item)
        pid=escape(raw_pid)
        title=escape(str(r.get('titulo') or raw_item))
        status=str(r.get('status') or '')
        label,cls=LABELS.get(status,('Em análise','atencao'))
        stamp=r.get('criado_em')
        try:
            when=datetime.fromtimestamp(int(stamp),ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M · Brasília')
        except (TypeError,ValueError,OverflowError,OSError):
            when='—'
        price=number(r.get('preco'),money=True)
        margin=number(r.get('margem_pct'))
        html+='<tr><td>'+title+'<br><small>'+item+'</small></td><td>'+pid+'</td><td>'+price+'</td><td>'+margin+'</td>'
        html+='<td><span class="alerta '+cls+'">'+label+'</span></td><td>'+when+'</td>'
        html+='<td><a class="filtro-btn" href="/promocoes/participar/'+str(cid)+'/'+escape(quote(raw_pid,safe=''),quote=True)+'/'+escape(quote(raw_item,safe=''),quote=True)+'">Verificar status</a></td></tr>'
    return html+'</tbody></table></div></section>'


def number(value, money=False):
    if value is None or isinstance(value,bool):
        return '—'
    try:
        result=Decimal(str(value))
        if not result.is_finite() or abs(result)>Decimal('1000000000000') or (money and result<0):
            return '—'
    except (ValueError,TypeError,InvalidOperation):
        return '—'
    if money:
        from freight_comparison import format_brl
        return format_brl(result)
    return format(result,'.2f').replace('.',',')+'%'
