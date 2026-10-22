"""Readable audit history for promotion participation, without any API writes."""
from html import escape
from datetime import datetime, timezone

LABELS={'confirmed':('Confirmada','ok'),'rejected':('Recusada','urgente'),
        'uncertain':('Aguardando confirmação','atencao'),
        'sending':('Envio em andamento','atencao')}

def render_history(rows,cid):
    cid=int(cid)
    rows=rows or []
    counts={key:sum(1 for r in rows if r.get('status')==key) for key in LABELS}
    html='<section class="card" id="historico-adesoes" style="margin-bottom:20px">'
    html+='<h2>Histórico de participações</h2>'
    html+='<p class="sub">Solicitações enviadas pela Keiper. Estados pendentes podem ser conferidos novamente sem reenviar a adesão.</p>'
    html+='<div class="grid" style="margin:14px 0">'
    for key in ('confirmed','uncertain','rejected','sending'):
        title,_=LABELS[key]
        html+='<div class="stat"><div class="num">'+str(counts[key])+'</div><div class="lab">'+title+'</div></div>'
    html+='</div>'
    if not rows:
        return html+'<p class="sub">Nenhuma participação enviada por esta loja ainda.</p></section>'
    html+='<div style="overflow-x:auto"><table><thead><tr><th>Anúncio</th><th>Campanha</th><th>Preço enviado</th><th>MC estimada</th><th>Situação</th><th>Quando</th><th>Verificar</th></tr></thead><tbody>'
    for r in rows[:100]:
        item=escape(str(r.get('item_id') or ''))
        pid=escape(str(r.get('promocao_id') or ''))
        title=escape(str(r.get('titulo') or item))
        status=str(r.get('status') or '')
        label,cls=LABELS.get(status,('Em análise','atencao'))
        stamp=r.get('criado_em')
        try:
            when=datetime.fromtimestamp(int(stamp),timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
        except (TypeError,ValueError,OverflowError):
            when='—'
        try:
            price='R$ %.2f'%float(r['preco'])
            margin='%.2f%%'%float(r['margem_pct'])
        except (ValueError,TypeError,KeyError):
            price=margin='—'
        html+='<tr><td>'+title+'<br><small>'+item+'</small></td><td>'+pid+'</td><td>'+price+'</td><td>'+margin+'</td>'
        html+='<td><span class="alerta '+cls+'">'+label+'</span></td><td>'+when+'</td>'
        html+='<td><a class="filtro-btn" href="/promocoes/participar/'+str(cid)+'/'+pid+'/'+item+'">Verificar status</a></td></tr>'
    return html+'</tbody></table></div></section>'
