"""Read-only KEVIA observatory. All figures come from saved evidence/snapshots."""
from datetime import date, timedelta
from decimal import Decimal
from html import escape

from kyra_theme import STYLE, SCRIPT
from sales_metrics import amount


def safe(value):
    return escape(str(value), quote=True)


def day(value):
    try:
        return date.fromisoformat(str(value)[:10]).strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return 'Aguardando análise'


def money(value):
    return 'R$ ' + format(value, ',.2f').replace(',', '_').replace('.', ',').replace('_', '.')


def chart(rows, end):
    """Two comparable BRL series, optional comparison and accessible raw table.

    Invalid/unobserved days stay missing. Previous revenue is aligned by weekday;
    no interpolation spans gaps, and no estimated daily data is manufactured.
    """
    try:
        last = date.fromisoformat(str(end))
    except (ValueError, TypeError):
        return "<div class='ky-chart-empty'><span class='ky-empty-symbol' aria-hidden='true'>⌁</span><b>O próximo sinal começa nos dados.</b>O gráfico estará disponível quando existir uma análise diária.</div>"
    days = [(last-timedelta(days=i)).isoformat() for i in range(6,-1,-1)]
    by_day = {str(r['data']): r for r in rows}
    series = [('revenue', 'Receita Ads', '#bca2ff', 'faturamento', 0),
              ('spend', 'Investimento', '#65e8dd', 'gasto', 0),
              ('previous', 'Receita anterior', '#eead73', 'faturamento', 7)]
    values = {}
    for key, label, color, field, offset in series:
        values[key] = [amount(by_day.get((date.fromisoformat(d)-timedelta(days=offset)).isoformat(), {}).get(field)) for d in days]
    if not any(v is not None for vals in values.values() for v in vals):
        return "<div class='ky-chart-empty'><span class='ky-empty-symbol' aria-hidden='true'>⌁</span><b>Histórico de Ads indisponível</b>Não há valores válidos registrados nesta janela. Dados ausentes não são tratados como zero.</div>"
    out = "<div class='ky-chart-picks' role='group' aria-label='Informações do gráfico'>"
    for key, label, color, _, _ in series:
        available = sum(v is not None for v in values[key])
        total = money(sum(v for v in values[key] if v is not None)) if available else 'Indisponível'
        out += ("<button type='button' class='ky-chart-pick' aria-pressed='true' data-series-toggle='"+key+"' data-label='"+label+"' style='--series:"+color+"'><span><i aria-hidden='true'></i>"+label+"</span><b>"+total+"</b><span>"+str(available)+"/7 dias · "+('parcial' if available<7 else 'soma registrada')+"</span></button>")
    out += "</div><div class='ky-chart-controls'><span>Clique nos cards para adicionar ou remover séries</span><label><input type='checkbox' data-chart-points checked> Pontos</label><label><input type='checkbox' data-chart-grid checked> Grade</label></div>"
    maximum = max((v for vals in values.values() for v in vals if v is not None), default=Decimal(0))
    scale = max(float(maximum)*1.15, 1)
    out += "<div class='ky-plot'><div class='ky-chart-tip' role='status' hidden></div><svg viewBox='0 0 660 260' role='img' aria-label='Histórico diário de receita Ads e investimento com comparação da receita anterior; valores em reais'><title>Dados diários registrados. Lacunas indicam dados indisponíveis.</title>"
    for i in range(4):
        y = 20+i*65
        out += "<line class='ky-gridline' x1='65' x2='642' y1='"+str(y)+"' y2='"+str(y)+"'/><text x='55' y='"+str(y+4)+"' text-anchor='end'>"+safe(format(scale*(3-i)/3, '.0f'))+"</text>"
    for key, label, color, _, _ in series:
        path = []
        points = []
        connected = False
        for i, value in enumerate(values[key]):
            if value is None:
                connected = False
                continue
            x, y = 76+i*91, 215-float(value)/scale*195
            path.append(('L' if connected else 'M')+f'{x:.1f},{y:.1f}')
            points.append(f"<circle class='ky-point' cx='{x:.1f}' cy='{y:.1f}' r='4' fill='{color}'/>")
            connected = True
        out += "<g class='ky-series' data-series='"+key+"'><path class='ky-line' pathLength='1' stroke='"+color+"' "+("stroke-dasharray='5 6' " if key=='previous' else '')+"d='"+' '.join(path)+"'/>"+''.join(points)+"</g>"
    for i, d in enumerate(days):
        x = 76+i*91
        label = date.fromisoformat(d).strftime('%d/%m')
        attrs = ' '.join('data-'+key+"='"+safe(money(values[key][i]) if values[key][i] is not None else 'Indisponível')+"'" for key, *_ in series)
        description = label+'; '+'; '.join(label_s+': '+(money(values[key][i]) if values[key][i] is not None else 'Indisponível') for key,label_s,*_ in series)
        out += f"<text x='{x}' y='247' text-anchor='middle'>{label}</text><rect class='ky-hit' tabindex='0' x='{x-35}' y='10' width='70' height='215' data-day='{label}' {attrs} aria-label='{safe(description)}'><title>{safe(description)}</title></rect>"
    out += "</svg></div><p class='ky-axis-note'>Valores em R$ · comparação alinhada por dia da semana</p><p class='ky-table-note'>Histórico salvo, não em tempo real. A disponibilidade no gráfico não valida a cobertura necessária às recomendações.</p><details><summary>Explorar os valores diários</summary><div class='ky-data-table'><table><thead><tr><th scope='col'>Dia atual</th><th scope='col'>Receita Ads</th><th scope='col'>Investimento</th><th scope='col'>Dia anterior</th><th scope='col'>Receita anterior</th></tr></thead><tbody>"
    for i, d in enumerate(days):
        out += '<tr><th scope="row">'+day(d)+'</th>'
        out += ''.join('<td>'+safe(money(values[key][i]) if values[key][i] is not None else 'Indisponível')+'</td>' for key in ('revenue','spend'))
        out += '<td>'+day(date.fromisoformat(d)-timedelta(days=7))+'</td><td>'+safe(money(values['previous'][i]) if values['previous'][i] is not None else 'Indisponível')+'</td></tr>'
    return out+'</tbody></table></div></details>'


def render(result, run_day=None, status=None, api_status=None, budget=None, cid=None, daily=None, campaign_run=None, admin_financial=False):
    from keiper_ai import evidence_text
    result = result or {}
    findings = result.get('recommendations', [])
    quality = result.get('quality', [])
    ready = bool(result)
    finance_nav = "<a href='#ky-finance'>Financeiro documentado</a>" if admin_financial else ''
    cid = str(int(cid)) if cid is not None else None
    run_label = {'completed':'Análise concluída','failed':'Execução com falha','running':'Análise em andamento','rules_ready':'Regras concluídas'}.get(status, 'Análise disponível' if ready else 'Aguardando análise')
    out = STYLE+"<div class='kyra' id='kyra-top'><div class='ky-topline'><div class='ky-overline'>KEIPER / INTELIGÊNCIA APLICADA</div><span class='ky-chip'><span class='ky-dot' aria-hidden='true'></span>Decisão humana</span></div>"
    out += "<header class='ky-hero ky-reveal'><div class='ky-hero-copy'><div class='ky-overline'>SEU PRÓXIMO PASSO, COM EVIDÊNCIAS</div><h2 class='ky-wordmark'>KEV<span>IA</span></h2><p class='ky-tagline'>Menos ruído.<br>Mais clareza para decidir.</p><p class='ky-description'>Sinais de vendas e publicidade reunidos para revelar o que merece a sua atenção.</p><div class='ky-actions'><a class='ky-button' href='#ky-recommendations'>Explorar recomendações <span aria-hidden='true'>↗</span></a>"
    if cid:
        out += "<a class='ky-button secondary' href='/ads/"+cid+"'>Abrir publicidade <span aria-hidden='true'>↗</span></a>"
    out += "</div></div><div class='ky-orbit' aria-hidden='true'><svg viewBox='0 0 270 270'><circle cx='135' cy='135' r='125' fill='none' stroke='#baa0ff22' stroke-dasharray='2 8'/><ellipse cx='135' cy='135' rx='125' ry='77' fill='none' stroke='#bda3ff55' transform='rotate(-35 135 135)'/><circle class='ky-orbit-light' cx='238' cy='72' r='4' fill='#8ff2e1'/><circle cx='37' cy='207' r='3' fill='#c1a8ff'/><path d='M135 0v15M135 255v15M0 135h15M255 135h15' stroke='#c9b4ff66'/></svg><div class='ky-core'>K</div><span class='ky-orbit-caption'>OBSERVAR · ENTENDER · DECIDIR</span></div></header>"
    out += "<nav class='ky-nav' aria-label='Seções da KEVIA'><a href='#ky-overview'>Visão do dia</a><a href='#ky-signals'>Sinais de Ads</a><a href='#ky-campaigns'>Campanhas</a>"+finance_nav+"<a href='#ky-recommendations'>Sinais da loja</a><a href='#ky-transparency'>Transparência</a></nav>"
    out += "<section id='ky-overview' class='ky-section'><div class='ky-summary'><div class='ky-stat ky-reveal'><span class='ky-stat-label'>Sinais de vendas e Ads</span><strong class='ky-purple'>"+str(len(findings)).zfill(2)+"</strong><small>Até três recomendações por análise</small></div><div class='ky-stat ky-reveal'><span class='ky-stat-label'>Qualidade de vendas e Ads</span><strong class='"+('ky-amber' if quality else 'ky-cyan')+"'>"+('Com ressalvas' if quality else ('Validada' if ready else 'Aguardando'))+"</strong><small>"+(str(len(quality))+' observações na análise' if quality else ('Para os sinais de vendas e Ads' if ready else 'Sem classificação disponível'))+"</small></div><div class='ky-stat ky-reveal'><span class='ky-stat-label'>Última análise</span><strong>"+day(run_day)+"</strong><small>"+safe(run_label)+" · horário de Brasília</small></div></div></section>"
    out += "<section id='ky-signals' class='ky-section'><div class='ky-section-head'><div><p class='ky-overline'>01 / OBSERVAR</p><h2>O movimento por trás dos números</h2></div><span class='ky-tag'>HISTÓRICO ADS</span></div><div class='ky-main-grid'><div class='ky-panel'><div class='ky-panel-top'><h3>Receita × investimento</h3><span class='ky-muted'>7 dias encerrados</span></div>"+chart(daily or [], result.get('end'))+"</div><aside class='ky-panel'><p class='ky-overline'>ANTES DE DECIDIR</p><h3 class='ky-quality-title'>"+('Dados pedem atenção.' if quality else ('Base pronta para leitura.' if ready else 'Esperando o primeiro sinal.'))+"</h3><p class='ky-muted'>"+('A KEVIA limita conclusões quando a base não sustenta uma comparação.' if quality else ('Cobertura validada para as regras da análise, sem garantia de resultado futuro.' if ready else 'A rotina diária prepara as evidências, sem depender desta página aberta.'))+"</p><ul class='ky-quality-list'>"
    for index, reason in enumerate(quality):
        out += '<li><span>'+str(index+1).zfill(2)+'</span><span>'+safe(reason)+'</span></li>'
    out += "</ul><p class='ky-quality-foot'>Dados ausentes não viram zero. Evidências não comprovam causalidade.</p></aside></div></section>"
    if cid is not None:
        from kyra_campaign_view import render as render_campaigns
        out += render_campaigns(campaign_run, cid)
    if admin_financial:
        from kevia_finance_view import render as render_financial
        financial = result.get('financial')
        out += render_financial(financial if isinstance(financial,dict) else dict(status='pending'),cid)
    out += "<section id='ky-recommendations' class='ky-section'><div class='ky-section-head'><div><p class='ky-overline'>02 / ENTENDER</p><h2>Sua próxima investigação começa aqui</h2></div><span class='ky-muted'>"+str(len(findings))+" recomendações</span></div>"
    if findings:
        out += "<div class='ky-filters' role='group' aria-label='Filtrar recomendações'>"+''.join("<button type='button' data-ky-filter='"+key+"' aria-pressed='"+('true' if key=='all' else 'false')+"'>"+label+"</button>" for key,label in [('all','Todas'),('ads','Publicidade'),('sales','Vendas'),('quality','Qualidade')])+"</div><div class='ky-findings'>"
        for index, item in enumerate(findings):
            category = 'quality' if item['code']=='data_quality' else ('sales' if item['code'] in ('revenue','orders') else 'ads')
            label = {'quality':'Qualidade dos dados','sales':'Vendas da loja','ads':'Publicidade'}[category]
            out += "<article class='ky-finding' data-ky-category='"+category+"'><div class='ky-rank'>"+str(index+1).zfill(2)+"</div><div><div class='ky-finding-top'><span class='ky-category'>"+label+"</span><span class='ky-tag'>REVISÃO HUMANA</span></div><h3>"+safe(item['title'])+"</h3><p>"+safe(item['action'])+"</p><details"+(' open' if index==0 else '')+"><summary>Examinar evidências</summary><p>"+safe(evidence_text(item['evidence']))+"</p><span class='ky-evidence-label'>"+day(result.get('start'))+' — '+day(result.get('end'))+"</span></details>"
            if cid:
                href = '/ads/'+cid if category=='ads' else ('/vendas/'+cid if category=='sales' else '/painel/'+cid)
                out += "<a href='"+href+"'>"+('Investigar publicidade' if category=='ads' else ('Investigar vendas' if category=='sales' else 'Conferir dados da loja'))+" ↗</a>"
            out += '</div></article>'
        out += "</div><p class='ky-no-results' data-filter-empty hidden>Nenhuma recomendação desta categoria nesta análise.</p>"
    else:
        out += "<div class='ky-panel'><h3>"+('Nenhuma anomalia atingiu os critérios.' if ready else 'Análise ainda não disponível.')+"</h3><p class='ky-muted'>"+('Não há recomendações adicionais apenas para preencher o painel.' if ready else safe(run_label)+'. A próxima análise depende da rotina diária e do serviço ativo.')+"</p></div>"
    if result.get('interpretation'):
        out += "<div class='ky-panel' style='margin-top:16px'><p class='ky-overline'>INTERPRETAÇÃO POR IA · REVISAR</p><p class='ky-interpretation'>"+safe(result['interpretation'])+"</p></div>"
    out += "</section><section id='ky-transparency' class='ky-section ky-bottom'><div class='ky-panel'><p class='ky-overline'>03 / DECIDIR COM CONTEXTO</p><h3 style='margin-top:9px'>Duas janelas. Uma comparação justa.</h3><div class='ky-period-grid'><div class='ky-period'><span>Período analisado</span><b>"+day(result.get('start'))+' — '+day(result.get('end'))+"</b></div><div class='ky-period previous'><span>Período anterior</span><b>"+day(result.get('previous_start'))+' — '+day(result.get('previous_end'))+"</b></div></div><p class='ky-table-note'>Regras determinísticas sobre dados persistidos da loja. Esta seção reúne os sinais agregados da loja. As campanhas possuem uma análise separada nesta página.</p></div><div class='ky-panel'><p class='ky-overline'>CONTROLE DE INTERPRETAÇÃO</p><h3 style='margin-top:9px'>Você mantém o comando.</h3><p class='ky-muted' style='margin-top:10px'>API: "+safe(api_status or 'desabilitada')+"</p>"
    if budget is not None:
        used, cap = Decimal(str(budget['used'])), Decimal(str(budget['limit']))
        percent = min(max(float(used/cap*100),0),100) if cap>0 else 100
        out += "<div class='ky-budget-value'>"+money(used)+" <small>/ "+money(cap)+"</small></div><div class='ky-meter' style='--used:"+format(percent,'.2f')+"%' aria-label='"+safe(format(percent,'.1f'))+"% do orçamento comprometido'><span></span></div><p class='ky-muted'>API no mês, todas as lojas · "+safe(budget['alert'])+"</p><p class='ky-table-note'>Inclui reservas incertas. Valores estimados; não representam uma fatura fixa.</p>"
    else:
        out += "<p class='ky-table-note'>Nenhuma campanha é alterada automaticamente. As recomendações precisam da sua avaliação.</p>"
    out += "</div></section><footer class='ky-footer'><strong>KEVIA / KEIPER</strong><span>Nome provisório, aguardando análise jurídica de marca.</span><span>Análise diária · Toda decisão exige revisão humana.</span></footer></div>"
    return out+SCRIPT

