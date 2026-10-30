"""Read-only history of KEVIA daily runs; no extra data collection."""
from html import escape


def render_history(runs, admin_financial=False):
    html = '<section class="card"><h2>Histórico da KEVIA</h2><p>Até 30 análises mais recentes, incluindo falhas e dias sem recomendações.</p>'
    if not runs:
        return html + '<p>Nenhuma análise registrada.</p></section>'
    html += '<div style="overflow-x:auto"><table><thead><tr><th>Dia</th><th>Execução</th><th>Recomendações</th><th>Qualidade de vendas/Ads</th>'+('<th>Financeiro documentado</th>' if admin_financial else '')+'</tr></thead><tbody>'
    for run in runs:
        result = run.get('result') or {}
        if not isinstance(result, dict):
            result = {}
        if admin_financial:
            from kevia_finance import review_findings
            findings = review_findings(result)
        else:
            findings = result.get('recommendations') or []
        if not isinstance(findings, list):
            findings = []
        titles = ', '.join(str(item.get('title', 'Recomendação')) for item in findings if isinstance(item, dict))
        html += '<tr><td>'+escape(str(run.get('day') or '—'))+'</td>'
        html += '<td>'+escape(str(run.get('status') or '—'))+'</td>'
        html += '<td>'+escape(titles or 'Nenhuma')+'</td>'
        html += '<td>'+('Com ressalvas' if result.get('quality') else ('Validada' if result else 'Indisponível'))+'</td>'
        if admin_financial:
            financial=result.get('financial') or {}
            status=str(financial.get('status') or 'pending') if isinstance(financial,dict) else 'pending'
            label={'ready':'Documentado na execução','no_records':'Sem custos no recorte','unverified_sales':'Vendas não verificáveis','unverified_costs':'Custos não verificáveis','failed':'Indisponível','pending':'Não analisado nesta versão'}.get(status,'Indisponível')
            html += '<td>'+escape(label)+'</td>'
        html += '</tr>'
    return html+'</tbody></table></div></section>'
