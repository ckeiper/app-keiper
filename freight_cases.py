"""Persistence helpers for freight support cases; no AI or ML support integration."""
from html import escape

STATUSES = ("Pendente", "Em análise", "Resolvido")
TEMPLATES = ("Contestação inicial", "Resposta para justificativa genérica", "Pedido de reanálise")


def init_case_schema(conn, execute):
    execute(conn, """CREATE TABLE IF NOT EXISTS frete_chamados (
        id BIGSERIAL PRIMARY KEY,
        conexao_id INTEGER NOT NULL,
        pedido_id TEXT,
        anuncio_id TEXT,
        envio_id TEXT,
        protocolo TEXT,
        status TEXT NOT NULL DEFAULT 'Pendente',
        criado_por INTEGER NOT NULL,
        criado_em BIGINT NOT NULL,
        atualizado_em BIGINT NOT NULL,
        CHECK (status IN ('Pendente', 'Em análise', 'Resolvido'))
    )""")
    execute(conn, """CREATE INDEX IF NOT EXISTS idx_frete_chamados_loja
        ON frete_chamados (conexao_id, atualizado_em DESC)""")
    execute(conn, """CREATE TABLE IF NOT EXISTS frete_chamados_historico (
        id BIGSERIAL PRIMARY KEY,
        conexao_id INTEGER NOT NULL,
        chamado_id BIGINT NOT NULL REFERENCES frete_chamados(id),
        usuario_id INTEGER NOT NULL,
        tipo TEXT NOT NULL,
        detalhe TEXT NOT NULL,
        criado_em BIGINT NOT NULL
    )""")
    execute(conn, """CREATE TABLE IF NOT EXISTS frete_evidencias (
        id BIGSERIAL PRIMARY KEY,
        conexao_id INTEGER NOT NULL,
        chamado_id BIGINT NOT NULL REFERENCES frete_chamados(id),
        valor_referencia NUMERIC(12,2),
        valor_cobrado NUMERIC(12,2),
        data_referencia TEXT,
        origem_cobranca TEXT,
        contexto_confirmado BOOLEAN NOT NULL DEFAULT FALSE,
        itens_envio INTEGER,
        avaliacao TEXT NOT NULL,
        diferenca NUMERIC(12,2),
        justificativa TEXT NOT NULL,
        usuario_id INTEGER NOT NULL,
        criado_em BIGINT NOT NULL
    )""")
    execute(conn, """CREATE INDEX IF NOT EXISTS idx_frete_evidencias_chamado
        ON frete_evidencias (conexao_id, chamado_id, id DESC)""")
    execute(conn, """CREATE INDEX IF NOT EXISTS idx_frete_historico_chamado
        ON frete_chamados_historico (conexao_id, chamado_id, criado_em)""")


def render_cases(cases, cid):
    if not cases:
        return '<div class="card"><h3>Chamados salvos</h3><p>Nenhum chamado registrado.</p></div>'
    result = ['<div class="card"><h3>Chamados salvos</h3>']
    for case in cases:
        cid_case = str(case["id"])
        assessment = case.get("ultima_avaliacao")
        alert = ""
        if assessment == "Possível divergência":
            difference = case.get("ultima_diferenca")
            amount = ("R$ " + format(difference, ".2f").replace(".", ",")
                      if difference is not None else "valor não informado")
            alert = ('<p><strong>Possível divergência (conferência manual): '
                     + escape(amount) + '</strong>. Requer validação pelo Mercado Livre.</p>')
        elif assessment:
            alert = '<p>Última conferência manual: ' + escape(str(assessment)) + '</p>'
        api_cost = case.get("custo_api")
        if api_cost is not None:
            alert += ('<p>Custo consultado na API do Mercado Livre: R$ '
                      + escape(format(api_cost, ".2f").replace(".", ","))
                      + ' (não comprova tarifa histórica esperada)</p>')
        result.append('<div style="padding:12px;border-top:1px solid #ddd">'
                      '<b>Chamado #' + escape(cid_case) + '</b> — '
                      + escape(case.get("status") or "") + '<br>Pedido: '
                      + escape(case.get("pedido_id") or "não informado")
                      + ' | Envio: ' + escape(case.get("envio_id") or "não informado")
                      + ' | Protocolo: ' + escape(case.get("protocolo") or "não informado")
                      + alert
                      + '<br><a href="/fretes/' + str(cid) + '/chamado/' + cid_case
                      + '">Abrir histórico e atualizar</a></div>')
    return "".join(result) + "</div>"
