"""Campaign evidence in KYRA; all links and data remain scoped to the shop."""
from html import escape
from urllib.parse import quote

from keiper_ai_view import day, money, safe
from ads_sale_efficiency import render as render_sale_efficiency


STYLE = """<style>
.kyra .ky-campaigns{margin-top:27px}.kyra .ky-campaign-stats{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px}.kyra .ky-campaign-stats>div{flex:1;min-width:125px;border:1px solid #313049;background:linear-gradient(120deg,#1c1831,#111724);padding:15px 19px;border-radius:12px}.kyra .ky-campaign-stats strong{font:25px Consolas,monospace;color:#c3aaff;display:block}.kyra .ky-campaign-stats span{font-size:10px;color:#9cabc6}.kyra .ky-campaign-card{border:1px solid #383348;background:radial-gradient(ellipse at 100% 0,#5b367c22,transparent 55%),#121622;border-radius:17px;padding:24px;margin:13px 0}.kyra .ky-campaign-heading{display:flex;gap:12px;justify-content:space-between;align-items:start}.kyra .ky-campaign-card h3{font-size:19px;line-height:1.35;margin:8px 0 10px;overflow-wrap:anywhere;letter-spacing:-.3px}.kyra .ky-campaign-card h4{font-size:14px;color:#e5dcf7;margin:17px 0 8px}.kyra .ky-campaign-card p{font-size:12px;color:#acbad1}.kyra .ky-campaign-card .ky-campaign-why{color:#c0b2d8;font-size:11px}.kyra .ky-camp-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:19px}.kyra .ky-camp-metric{padding:12px;background:#090e1880;border:1px solid #293045;border-radius:9px;min-width:0}.kyra .ky-camp-metric small{display:block;font-size:9px;color:#93a2bf}.kyra .ky-camp-metric strong{display:block;font-size:17px;letter-spacing:-.5px;color:#d5c5ff;font-weight:550;margin:5px 0;overflow-wrap:anywhere}.kyra .ky-camp-metric span{font-size:9px;color:#8e9db8;display:block}.kyra .ky-campaign-meta{display:flex;flex-wrap:wrap;gap:7px;margin-top:14px}.kyra .ky-camp-bars{margin:16px 0;min-height:0;padding:12px 0;border-top:1px solid #282e41;border-bottom:1px solid #282e41}.kyra .ky-camp-bars .ky-muted{font-size:10px;margin-bottom:9px}.kyra .ky-cbar-row{display:grid;grid-template-columns:70px 1fr 55px;gap:12px;align-items:center;margin:7px 0;font-size:10px;color:#a4b1cb}.kyra .ky-cbar-track{height:6px;background:#252a3a;border-radius:6px;overflow:hidden}.kyra .ky-cbar{height:100%;width:var(--bar);background:#bfa4ff;border-radius:6px;transform-origin:left}.kyra .ky-cbar.previous{background:#658091}.kyra .ky-camp-bars:not(.ky-visible) .ky-cbar{transform:scaleX(0)}.kyra .ky-camp-bars.ky-visible .ky-cbar{animation:ky-bar-in 1s ease both}.kyra .ky-campaign-card details{border-top:1px solid #2b3043;margin-top:18px;padding-top:6px}.kyra .ky-campaign-cta{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-top:18px}.kyra .ky-campaign-cta small{font-size:10px;color:#95a4c0}.kyra .ky-campaign-blocked{border-top:1px solid #333448;padding:13px 0}.kyra .ky-campaign-blocked strong{font-size:12px;color:#d3c9e3;font-weight:500}.kyra .ky-campaign-blocked p{font-size:11px;color:#9cabc3;margin-top:5px}.kyra .ky-camp-caveat{margin-top:12px!important;font-size:10px!important;color:#a6a1ba!important}.kyra .ky-camp-window{font:10px Consolas,monospace;color:#9eabc4;margin:15px 0}.kyra .ky-campaign-card .ky-data-table table{font-size:10px}.kyra .ky-campaign-card .ky-data-table th:first-child{text-align:left}.kyra .ky-campaign-card .ky-tag{white-space:normal}.kyra .ky-campaign-card .ky-campaign-heading>.ky-rank{font-size:28px}
@keyframes ky-bar-in{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@media(max-width:640px){.kyra .ky-campaign-card{padding:18px}.kyra .ky-camp-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.kyra .ky-campaign-card h3{font-size:17px}.kyra .ky-campaign-card .ky-campaign-heading>.ky-rank{font-size:21px}.kyra .ky-cbar-row{grid-template-columns:60px 1fr 45px;gap:8px}.kyra .ky-campaign-stats{gap:7px}.kyra .ky-campaign-stats>div{min-width:100px;padding:12px}}
@media(prefers-reduced-motion:reduce){.kyra .ky-cbar{transform:none!important;animation:none!important}}
</style>"""


def number(value, kind='ratio'):
    if value is None:
        return 'Indisponível'
    if kind=='money':
        return money(value)
    if kind=='count':
        return str(int(value))
    return format(value,'.2f').replace('.',',')+('%' if kind=='percent' else 'x')


def render(run, cid):
    result = (run or {}).get('result')
    status = (run or {}).get('status')
    out = STYLE+"<section class='ky-section ky-campaigns' id='ky-campaigns'><div class='ky-section-head'><div><p class='ky-overline'>FOCO / CAMPANHAS INDIVIDUAIS</p><h2>Onde vale abrir uma investigação</h2></div><span class='ky-tag'>ANÁLISE POR CAMPANHA</span></div>"
    if not result:
        message = {'failed':'A análise de campanhas falhou nesta execução. Nenhuma conclusão foi gerada; a rotina tentará uma nova análise no próximo dia ativo.',
                   'running':'A análise de campanhas está em andamento ou foi interrompida. Os resultados só aparecem após a conclusão.'}.get(status,'A análise individual está aguardando a próxima rodada da rotina diária. Esta página não dispara processamento nem chamadas de API.')
        return out+"<div class='ky-panel'><h3>Preparando a leitura das campanhas</h3><p class='ky-muted' style='margin-top:10px'>"+message+"</p></div></section>"
    out += "<p class='ky-muted'>Até três campanhas priorizadas, com uma investigação principal por campanha. Recomendações para revisão humana, sem execução automática.</p><p class='ky-camp-window'>Análise: "+day(run.get('day'))+' · '+day(result['start'])+' — '+day(result['end'])+' / comparação: '+day(result['previous_start'])+' — '+day(result['previous_end'])+"</p><div class='ky-campaign-stats'>"
    for value,label in [(result['active'],'ativas no cadastro lido'),(result['comparable'],'com comparação validada'),(result['flagged'],'com sinal pelas regras')]:
        out += '<div><strong>'+safe(value)+'</strong><span>'+label+'</span></div>'
    out += '</div>'
    if result.get('limited'):
        out += "<div class='ky-panel'><h3>Leitura limitada</h3><p class='ky-muted'>O limite seguro de leitura foi atingido. Não há ranking de recomendações para uma carteira parcialmente lida.</p></div>"
    for index,item in enumerate(result['recommendations']):
        current, previous = item['current'], item.get('previous') or {}
        out += "<article class='ky-campaign-card'><div class='ky-campaign-heading'><div><span class='ky-category'>"+('OPORTUNIDADE PARA AVALIAR' if item['code']=='scale_review' else 'ATENÇÃO PARA INVESTIGAR')+"</span><h3>"+safe(item['name'])+"</h3><span class='ky-tag'>"+safe(item['title'])+"</span></div><span class='ky-rank' aria-label='Prioridade "+str(index+1)+"'>"+str(index+1).zfill(2)+"</span></div><div class='ky-camp-metrics'>"
        for key,label,kind in [('spend','Investimento','money'),('revenue','Receita Ads','money'),('roas','ROAS','ratio'),('acos','ACOS','percent')]:
            out += "<div class='ky-camp-metric'><small>"+label+" · atual</small><strong>"+safe(number(current.get(key),kind))+"</strong><span>Anterior: "+safe(number(previous.get(key),kind))+"</span></div>"
        out += '</div>'
        if current.get('roas') is not None and previous.get('roas') is not None:
            maximum = max(current['roas'],previous['roas'],1)
            out += "<div class='ky-plot ky-camp-bars' role='img' aria-label='ROAS atual "+safe(number(current['roas']))+'; anterior '+safe(number(previous['roas']))+"'><p class='ky-muted'>ROAS · retorno em receita atribuída por real investido</p>"
            for label,value,extra in [('Atual',current['roas'],''),('Anterior',previous['roas'],' previous')]:
                out += "<div class='ky-cbar-row'><span>"+label+"</span><div class='ky-cbar-track'><div class='ky-cbar"+extra+"' style='--bar:"+format(value/maximum*100,'.2f')+"%'></div></div><span>"+safe(number(value))+"</span></div>"
            out += '</div>'
        out += render_sale_efficiency(current, previous)
        out += "<h4>Por que entrou na fila</h4><p class='ky-campaign-why'>"+safe(item['why'])+"</p><h4>O que fazer agora</h4><p>"+safe(item['action'])+"</p>"
        if item.get('target_roas') is not None:
            out += "<div class='ky-campaign-meta'><span class='ky-tag'>Meta atual cadastrada: "+safe(number(item['target_roas']))+"</span></div>"
        out += "<details><summary>Conferir todas as evidências e ressalvas</summary><div class='ky-data-table'><table><thead><tr><th scope='col'>Indicador</th><th scope='col'>Atual</th><th scope='col'>Anterior</th></tr></thead><tbody>"
        for key,label,kind in [('spend','Investimento','money'),('revenue','Receita atribuída','money'),('roas','ROAS','ratio'),('acos','ACOS','percent'),('attributed_sales','Vendas atribuídas oficiais','count'),('organic_revenue','Receita orgânica oficial','money'),('tacos','TACOS da campanha','percent')]:
            out += '<tr><th scope="row">'+label+'</th><td>'+safe(number(current.get(key),kind))+'</td><td>'+safe(number(previous.get(key),kind))+'</td></tr>'
        out += '</tbody></table></div>'
        for reason in item.get('quality',[]):
            out += "<p class='ky-camp-caveat'>"+safe(reason)+'</p>'
        out += "<p class='ky-camp-caveat'>"+safe(' '.join(result.get('caveats',[])))+"</p></details><div class='ky-campaign-cta'><a class='ky-button secondary' href='/ads/"+str(int(cid))+"/campanha/"+quote(str(item['campaign_id']),safe='')+"'>Abrir campanha ↗</a><small>Decisão e alterações permanecem manuais.</small></div></article>"
    if not result['recommendations'] and not result.get('limited'):
        message = ('As campanhas com dados válidos não atingiram os critérios de investigação nesta rodada.' if result['current_ready'] else 'Nenhuma campanha está com dados suficientes e cadastro recente para receber uma recomendação nesta rodada.') if result['active'] else 'Nenhuma campanha ativa consta no cadastro lido para esta loja.'
        out += "<div class='ky-panel'><h3>Sem campanhas priorizadas nesta rodada</h3><p class='ky-muted' style='margin-top:8px'>"+message+"</p></div>"
    blocked = [c for c in result['campaigns'] if c['quality']]
    if blocked:
        out += "<details class='ky-panel' style='margin-top:15px'><summary>Explorar ressalvas de "+str(len(blocked))+" campanhas</summary><p class='ky-muted'>Uma ressalva pode bloquear somente uma regra. Vendas oficiais ausentes não viram zero; TACOS nunca usa faturamento de outra campanha ou da loja.</p>"
        for campaign in blocked[:12]:
            out += "<div class='ky-campaign-blocked'><strong>"+safe(campaign['name'])+"</strong><p>"+safe(' '.join(campaign['quality']))+'</p></div>'
        if len(blocked)>12:
            out += "<p class='ky-muted'>Mais "+str(len(blocked)-12)+" campanhas com ressalvas nesta execução. Consulte os detalhes no painel de publicidade.</p>"
        out += '</details>'
    out += "<p class='ky-camp-caveat'>"+safe(' '.join(result.get('caveats',[])))+"</p></section>"
    return out
