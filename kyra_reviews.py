"""Manual review status for deterministic KYRA recommendation codes."""
from html import escape

ALLOWED = ('pendente', 'em_analise', 'resolvido')


def init_schema(conn, execute):
    execute(conn, """CREATE TABLE IF NOT EXISTS kyra_reviews (
        conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        code TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'pendente'
          CHECK (state IN ('pendente','em_analise','resolvido')),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (conexao_id,code))""")


def render_review(cid, findings, saved, csrf):
    html = '<section class="card"><h2>Acompanhamento das recomendações</h2><p>O status é manual e permanece associado ao tipo de recomendação desta loja.</p>'
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        code = str(finding.get('code') or '')
        if not code or len(code) > 80:
            continue
        state = saved.get(code, 'pendente')
        html += '<form method="post" action="/kyra/revisar/'+str(int(cid))+'">'
        html += '<input type="hidden" name="csrf" value="'+escape(csrf, quote=True)+'">'
        html += '<input type="hidden" name="code" value="'+escape(code, quote=True)+'">'
        html += '<label>'+escape(str(finding.get('title') or code))+' <select name="state">'
        for option in ALLOWED:
            html += '<option value="'+option+'"'+(' selected' if option == state else '')+'>'+option.replace('_',' ').title()+'</option>'
        html += '</select></label> <button type="submit">Salvar</button></form>'
    return html+'</section>'
