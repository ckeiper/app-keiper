"""Server-rendered sales report, using only synchronized and qualified data."""
import html
import json
from datetime import datetime
from sales_metrics import SAO_PAULO
from sales_metrics import PRESETS, change, period, summarize

SALES_STYLE = """<style>
body:has(.sales-theme),body:has(.sales-theme) .layout,body:has(.sales-theme) .layout>.conteudo{background:#081426;color:#eaf2ff}
body:has(.sales-theme) .conteudo .card,body:has(.sales-theme) .conteudo .stat{background:#11243a;border:1px solid #2d4864;color:#eaf2ff;border-radius:15px}
body:has(.sales-theme) .conteudo h2,body:has(.sales-theme) .conteudo .stat .num{color:#edf5ff}
body:has(.sales-theme) .conteudo .stat .lab,body:has(.sales-theme) .conteudo .sub,body:has(.sales-theme) .conteudo .muted{color:#bdd0e4}
body:has(.sales-theme) .conteudo input,body:has(.sales-theme) .conteudo select{background:#0d1d30;border:1px solid #3a5772;color:#f1f7ff;color-scheme:dark}
body:has(.sales-theme) .conteudo form.card{display:flex;align-items:end;gap:12px;flex-wrap:wrap}
body:has(.sales-theme) .conteudo form.card label{display:grid;gap:6px;color:#bdd0e4;font-size:12px;font-weight:700;min-width:140px}
body:has(.sales-theme) .conteudo form.card input,body:has(.sales-theme) .conteudo form.card select{min-height:40px;padding:8px 10px;border-radius:8px;max-width:100%;box-sizing:border-box}
@media(max-width:600px){body:has(.sales-theme) .conteudo form.card label{flex:1;min-width:120px}}
body:has(.sales-theme) .conteudo table th{background:#1b344e;color:#d0dfef;border-color:#39536c}
body:has(.sales-theme) .conteudo table td{color:#d7e6f5;border-color:#30465c}
body:has(.sales-theme) .conteudo .link,body:has(.sales-theme) .conteudo summary{color:#9fd5ff}
body:has(.sales-theme) .conteudo .aviso{background:#382e21;border-color:#80653c;color:#ffe0ae}
body:has(.sales-theme) .conteudo #vendasFaturamento{max-width:100%}
body:has(.sales-theme) .conteudo .sales-variation{font-weight:750}body:has(.sales-theme) .conteudo .sales-up{color:#80f0b7}body:has(.sales-theme) .conteudo .sales-down{color:#ffb1b8}body:has(.sales-theme) .conteudo .sales-neutral{color:#d2e0ee}
</style><span class='sales-theme' hidden></span>"""


def render_sales(cid, args, banco, query):
    try:
        start, end, prev_start, prev_end = period(args)
    except ValueError as error:
        return SALES_STYLE + "<div class='aviso'>" + html.escape(str(error)) + "</div>" + filters(cid, args)
    with banco() as conn:
        rows = query(conn, """SELECT conexao_id, pedido_id, status, total, moeda,
                   criado_em, pagamentos_json, unidades, vendas_dia_coleta FROM pedidos
                   WHERE conexao_id=%s AND vendas_verificado_em IS NOT NULL""", (cid,))
        coverage = query(conn, "SELECT dia, atualizado_em FROM vendas_cobertura WHERE conexao_id=%s", (cid,))
        legacy = query(conn, "SELECT COUNT(*) AS n FROM pedidos WHERE conexao_id=%s AND vendas_verificado_em IS NULL", (cid,))
    covered = {r["dia"] for r in coverage}
    current = summarize(rows, start, end, covered)
    previous = summarize(rows, prev_start, prev_end, covered)
    out = SALES_STYLE + filters(cid, args)
    timestamps = [r['atualizado_em'] for r in coverage
                  if prev_start.isoformat() <= r['dia'] <= end.isoformat()]
    if timestamps:
        stamp = datetime.fromtimestamp(min(timestamps), SAO_PAULO).strftime('%d/%m/%Y %H:%M')
        out += "<p class='muted'>Sincronização mais antiga dos dias cobertos nesta seleção: " + stamp + " (Brasília).</p>"
    out += ("<div class='card'><h2>Indicadores de vendas pagas</h2><p>"
            + start.strftime('%d/%m/%Y') + " a " + end.strftime('%d/%m/%Y')
            + " · Comparação: " + prev_start.strftime('%d/%m/%Y') + " a " + prev_end.strftime('%d/%m/%Y')
            + "</p><div class='sub'>Data de criação do pedido, horário de Brasília (UTC−3). "
            "Somente pedidos pagos com pagamento aprovado, em BRL. Faturamento = total dos pedidos; "
            "ticket = faturamento ÷ pedidos; preço médio = faturamento ÷ unidades. "
            "O dia de hoje está em andamento e depende da última sincronização. "
            "Valores brutos, sem subtrair cancelamentos, devoluções ou reembolsos.</div></div>")
    if not current["complete"] or not previous["complete"]:
        out += ("<div class='aviso'>Histórico incompleto: indicadores do período sem cobertura "
                "completa aparecem como indisponíveis; lacunas no gráfico não representam zero. "
                "Use Atualizar agora para continuar a carga (até 30 dias históricos por execução, "
                "janela automática de 180 dias). Períodos anteriores a essa janela não têm cobertura garantida.</div>")
    for title, report in (("Período atual", current), ("Período anterior", previous)):
        if report['invalid']:
            out += ("<div class='aviso'>" + title + ": " + str(report['invalid'])
                    + " pedido(s) com campos não verificáveis, incluindo " + str(report['invalid_dates'])
                    + " com data de criação ausente ou inválida. Os indicadores afetados "
                    "ficam indisponíveis; no gráfico, somente os dias afetados têm lacunas.</div>")
    # Both reports receive the same records. Do not count unlocated records twice.
    unallocated = current['unallocated_dates']
    if unallocated:
        out += ("<div class='aviso'>Integridade do histórico: " + str(unallocated)
                + " pedido(s) sem data de criação utilizável e sem dia de origem identificável. "
                "Estão excluídos dos indicadores e não podem ser atribuídos a nenhum período. "
                "Os valores exibidos consideram somente pedidos com data válida; a cobertura "
                "de busca não garante a integridade desses registros. É necessário revalidá-los.</div>")
    if legacy and legacy[0]['n']:
        out += ("<div class='aviso'>Há " + str(legacy[0]['n'])
                + " pedido(s) antigos ainda não revalidados, excluídos dos novos indicadores. "
                "A disponibilidade de cada período depende da sua cobertura de sincronização.</div>")
    if current['unknown_units'] or previous['unknown_units']:
        out += "<div class='aviso'>Há vendas sem quantidades confiáveis; unidades e preço médio ficam indisponíveis.</div>"
    out += "<div class='grid' style='margin-bottom:18px'>"
    for key, title, money in (("revenue", "Faturamento de vendas pagas", True),
                               ("orders", "Pedidos pagos", False),
                               ("units", "Unidades vendidas", False),
                               ("ticket", "Ticket médio por pedido", True),
                               ("unit_price", "Preço médio por unidade", True)):
        value, before = current[key], previous[key]
        pct = change(value, before)
        comparison = "Variação indisponível" if pct is None else f"{pct:+.1f}%".replace('.', ',')
        if before == 0 and value is not None and value > 0:
            comparison = "Sem base percentual (anterior = 0)"
        tone = 'neutral' if pct is None or pct == 0 else 'up' if pct > 0 else 'down'
        out += ("<div class='stat'><div class='num'>" + fmt(value, money)
                + "</div><div class='lab'>" + title + "</div><div class='muted'>Anterior: "
                + fmt(before, money) + " · <span class='sales-variation sales-"+tone+"'>" + comparison + "</span></div></div>")
    out += "</div>"
    chart = {"labels": [f"Dia {i+1}" for i in range(len(current['days']))],
             "current": current['daily'], "previous": previous['daily'],
             "dates": current['days'], "previousDates": previous['days']}
    out += ("<div class='card'><h2>Faturamento diário · períodos alinhados por dia</h2>"
            "<div style='height:300px'><canvas id='vendasFaturamento' role='img' "
            "aria-label='Faturamento diário atual e anterior'></canvas></div>"
            "<details><summary>Ver dados do gráfico</summary><div style='overflow-x:auto'><table>"
            "<thead><tr><th>Data atual</th><th>Faturamento</th><th>Data anterior</th><th>Faturamento anterior</th></tr></thead><tbody>")
    for i, day in enumerate(current['days']):
        out += ("<tr><td>" + day + "</td><td>" + fmt(current['daily'][i], True)
                + "</td><td>" + previous['days'][i] + "</td><td>" + fmt(previous['daily'][i], True) + "</td></tr>")
    out += ("</tbody></table></div></details></div><script src='https://cdn.jsdelivr.net/npm/"
            "chart.js@4.4.1/dist/chart.umd.min.js'></script><script>(function(){const d="
            + json.dumps(chart) + ";if(typeof Chart==='undefined')return;"
            "new Chart(document.getElementById('vendasFaturamento'),{type:'line',data:{labels:d.labels,datasets:["
            "{label:'Atual',data:d.current,borderColor:'#059669',spanGaps:false},"
            "{label:'Anterior',data:d.previous,borderColor:'#64748b',borderDash:[5,5],spanGaps:false}]},"
            "options:{responsive:true,maintainAspectRatio:false,scales:{x:{ticks:{color:'#bdd0e4'},grid:{color:'#304860'}},y:{beginAtZero:true,ticks:{color:'#bdd0e4'},grid:{color:'#304860'},title:{display:true,text:'R$',color:'#bdd0e4'}}},"
            "plugins:{legend:{labels:{color:'#bdd0e4'}},tooltip:{callbacks:{title:function(items){const i=items[0].dataIndex;return d.dates[i]+' / '+d.previousDates[i];}}}}}});})();</script>")
    out += ("<div class='card'><h2>Ocorrências separadas</h2><p>Cancelamentos (status cancelled): "
            + fmt(current['cancellations'], False) + " · Anterior: " + fmt(previous['cancellations'], False)
            + "</p><p>Devoluções: indisponível · Reembolsos: indisponível.</p>"
            "<div class='sub'>O banco e a coleta atual não possuem eventos confiáveis de devolução "
            "ou valores de reembolso. Cancelamento não é tratado como devolução ou reembolso. "
            "Nenhuma ocorrência é subtraída novamente do faturamento.</div></div>"
            "<div class='card'><h2>Análise de margem existente</h2>"
            "<p>A seção abaixo e o CSV mantêm a análise dos últimos 100 pedidos fechados, "
            "sem os filtros acima. São independentes dos indicadores de vendas pagas.</p></div>")
    return out


def fmt(value, money):
    if value is None:
        return "Indisponível"
    number = f"{value:,.2f}" if money else str(value)
    if money:
        number = number.replace(',', 'X').replace('.', ',').replace('X', '.')
    return ("R$ " if money else "") + number


def filters(cid, args, action=None):
    choice = args.get('periodo', '30')
    action = html.escape(action or f'/vendas/{cid}', quote=True)
    out = f"<form method='get' action='{action}' class='card'><label>Período <select name='periodo'>"
    for value, title in [(str(n), f'{n} dias') for n in PRESETS] + [('personalizado', 'Personalizado')]:
        out += "<option value='" + value + "'" + (" selected" if choice == value else "") + ">" + title + "</option>"
    out += "</select></label> "
    for name, title in [('inicio', 'Início'), ('fim', 'Fim')]:
        out += ("<label>" + title + " <input type='date' name='" + name + "' value='"
                + html.escape(args.get(name, ''), quote=True) + "'></label> ")
    return out + "<button type='submit' class='btn-acoes'>Aplicar</button></form>"
