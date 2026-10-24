"""Read-only history of KEVIA daily runs; no extra data collection."""
from html import escape


def render_history(runs):
    html = '<section class="card"><h2>Histórico da KEVIA</h2><p>Até 30 análises mais recentes, incluindo falhas e dias sem recomendações.</p>'
    if not runs:
        return html + '<p>Nenhuma análise registrada.</p></section>'
    html += '<div style="overflow-x:auto"><table><thead><tr><th>Dia</th><th>Execução</th><th>Recomendações</th><th>Qualidade</th></tr></thead><tbody>'
    for run in runs:
        result = run.get('result') or {}
        if not isinstance(result, dict):
            result = {}
        findings = result.get('recommendations') or []
        if not isinstance(findings, list):
            findings = []
        titles = ', '.join(str(item.get('title', 'Recomendação')) for item in findings if isinstance(item, dict))
        html += '<tr><td>'+escape(str(run.get('day') or '—'))+'</td>'
        html += '<td>'+escape(str(run.get('status') or '—'))+'</td>'
        html += '<td>'+escape(titles or 'Nenhuma')+'</td>'
        html += '<td>'+('Com ressalvas' if result.get('quality') else ('Validada' if result else 'Indisponível'))+'</td></tr>'
    return html+'</tbody></table></div></section>'
