"""Opt-in client portal for store-scoped priorities. No writes to marketplace."""
from html import escape

CSS="""<style>
.cp-portal{max-width:1240px;margin:20px auto 44px;padding:0 18px;color:#213653}
.cp-intro{background:linear-gradient(120deg,#10243e,#234a7b);color:white;padding:25px;border-radius:17px;margin-bottom:18px}
.cp-intro small{font-size:10px;font-weight:800;letter-spacing:1.5px;color:#8bc5fa}.cp-intro h2{color:#fff;font-size:24px;margin:8px 0}.cp-intro p{color:#d6e3f2;font-size:13px;line-height:1.6;margin:0}
.cp-card{border:1px solid #dfe6f0;border-radius:13px;padding:17px;margin:10px 0;background:#fff;box-shadow:0 3px 12px #0a2f5209}
.cp-title{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.cp-title strong{font-size:14px}.cp-card p{color:#62738c;font-size:12px;line-height:1.65;margin:7px 0}
.cp-tag{font-size:10px;border-radius:7px;padding:5px 9px;background:#f4eefb;color:#664c9a;font-weight:800}
.cp-tag.ok{background:#e6f5ee;color:#267351}.cp-tag.missing{background:#fff1e6;color:#a46831}
.cp-actions{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:12px}
.cp-actions a{font-size:12px;font-weight:750;color:#2959a1;text-decoration:none}
.cp-actions button{font:inherit;font-size:12px;font-weight:750;padding:9px 12px;border:1px solid #c7d5e9;border-radius:9px;background:#f3f7fc;color:#294e7d;cursor:pointer}
.cp-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}
.cp-note{font-size:12px;color:#687994;line-height:1.7}
@media(max-width:600px){.cp-portal{padding:0 12px}.cp-intro{padding:18px}.cp-intro h2{font-size:20px}}
</style>"""


def intro(title, description):
    return CSS+'<main class="cp-portal"><header class="cp-intro"><small>KEIPER · INTELIGÊNCIA</small><h2>'+escape(title)+'</h2><p>'+escape(description)+'</p></header>'


def admin_index(shops, grants, health, csrf):
    from collection_health import summary
    by_health={int(r['id']):r for r in health}
    alert=summary(health)['attention']
    out=intro('Central de prioridades · carteira',
              '%s loja(s) com sinais técnicos de coleta. Acesse a análise de cada loja ou libere o portal do cliente individualmente.' % alert)
    out+='<p class="cp-note">A visão consolidada abaixo indica saúde de dados. O ranking de vendas por anúncio é calculado ao abrir uma loja; não há comparação financeira agregada sem cobertura confirmada.</p>'
    out+='<div class="cp-list">'
    for shop in sorted(shops,key=lambda r:str(r['cliente']).casefold()):
        cid=int(shop['id'])
        name=escape(str(shop['cliente']))
        enabled=cid in grants
        check=by_health.get(cid,{})
        issues=check.get('issues') or []
        out+='<section class="cp-card"><div class="cp-title"><strong>'+name+'</strong>'
        out+='<span class="cp-tag '+('ok' if enabled else 'missing')+'">'+('Portal liberado' if enabled else 'Portal não liberado')+'</span></div>'
        out+='<p>'+escape(issues[0] if issues else 'Nenhum sinal técnico crítico identificado.')+'</p>'
        out+='<div class="cp-actions"><a href="/prioridades/'+str(cid)+'">Ver prioridades →</a>'
        out+='<form method="post" action="/prioridades/'+str(cid)+'/acesso">'
        out+='<input type="hidden" name="csrf_token" value="'+escape(csrf,quote=True)+'">'
        out+='<input type="hidden" name="enabled" value="'+('0' if enabled else '1')+'">'
        out+='<button type="submit">'+('Suspender acesso' if enabled else 'Liberar ao cliente')+'</button></form></div></section>'
    out+='</div><p class="cp-note">A liberação habilita apenas esta Central de Prioridades. O cliente precisa ter uma conta individual já vinculada à loja. Não cria usuários nem altera permissões de outras telas.</p></main>'
    return out


def store_portal(report, cid, client_view=False):
    from listing_priority_queue import prioritize
    title=str(report['shop']['cliente'])
    out=intro('Prioridades · '+title,
              'Onde agir primeiro: perdas verificadas e alertas operacionais. Informações de 7 dias completos, comparadas aos 7 anteriores.')
    ranking=prioritize(report['ranking'],limit=5)
    out+='<h3>Quedas de faturamento por anúncio</h3>'
    if not ranking['available']:
        out+='<section class="cp-card"><p>Classificação de quedas indisponível: '+escape(str(ranking['reason']))+'. Não tratamos dados ausentes como zero.</p></section>'
    elif not ranking['items']:
        out+='<section class="cp-card"><p>Nenhuma perda de faturamento verificada nos anúncios para este período.</p></section>'
    else:
        labels={str(v['listing']['item_id']):str(v['listing'].get('titulo') or v['listing']['item_id']) for v in report['rows']}
        out+='<div class="cp-list">'
        for k,item in enumerate(ranking['items'],1):
            item_id=item['item_id']
            name=escape(labels.get(item_id,item_id))
            loss='R$ '+format(item['loss'],',.2f').replace(',','_').replace('.',',').replace('_','.')
            out+='<section class="cp-card"><div class="cp-title"><strong>'+str(k)+'. '+name+'</strong><span class="cp-tag missing">Perda verificada</span></div>'
            out+='<p>Diferença no valor bruto dos itens: '+loss+'. Isso não comprova a causa.</p>'
            out+='<div class="cp-actions"><a href="/diagnostico/'+str(int(cid))+'/'+escape(item_id,quote=True)+'">Ver investigação →</a></div></section>'
        out+='</div>'
    out+='<h3>Alertas operacionais</h3>'
    allowed={'vendas','estoque','status','qualidade','dados'}
    alerts=[r for r in report['signals'] if r['kind'] in allowed][:6]
    if not alerts:
        out+='<section class="cp-card"><p>Nenhuma ação operacional prioritária identificada com os dados disponíveis.</p></section>'
    else:
        for signal in alerts:
            out+='<section class="cp-card"><div class="cp-title"><strong>'+escape(str(signal['title']))+'</strong><span class="cp-tag">'+escape(str(signal['priority']))+'</span></div>'
            out+='<p>'+escape(str(signal['label']))+' — '+escape(str(signal['evidence']))+'</p>'
            out+='<p><b>Verificação:</b> '+escape(str(signal['action']))+'</p></section>'
    out+='<p class="cp-note">A Central apresenta sinais observados e ações para investigar. A Keiper não altera anúncios automaticamente e não atribui causalidade sem evidência.</p>'
    if not client_view:
        out+='<p class="cp-note"><a href="/prioridades">← Voltar à carteira</a></p>'
    return out+'</main>'
