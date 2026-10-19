"""Store-scoped report summaries; never store customer rows or upload bytes."""
import hashlib
import json
from html import escape


def init_freight_schema(conn, execute):
    execute(conn, '''CREATE TABLE IF NOT EXISTS frete_importacoes (
        id BIGSERIAL PRIMARY KEY,
        conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        arquivo_sha256 CHAR(64) NOT NULL,
        importado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        resumo JSONB NOT NULL,
        UNIQUE (conexao_id, arquivo_sha256))''')


def save_report(conn, query, store_id, payload, summary):
    """Caller owns permission checks and transaction; concurrent replays are safe."""
    if summary['invalid_date_rows'] or not summary['period_start'] or not summary['rows']:
        raise ValueError('Importação exige lançamentos com datas válidas.')
    digest = hashlib.sha256(payload).hexdigest()
    return bool(query(conn, '''INSERT INTO frete_importacoes
        (conexao_id, arquivo_sha256, resumo) VALUES (%s,%s,%s::jsonb)
        ON CONFLICT (conexao_id, arquivo_sha256) DO NOTHING RETURNING id''',
        (store_id, digest, json.dumps(summary))))


def report_history(conn, query, store_id):
    return query(conn, '''SELECT id, importado_em, resumo FROM frete_importacoes
        WHERE conexao_id=%s ORDER BY id DESC LIMIT 10''', (store_id,))


def render_history(reports):
    from freight_comparison import format_brl
    body = '<section class="card"><h3>Importações desta loja</h3>'
    body += ('<p>Cada entrada é um relatório independente. Períodos sobrepostos não '
             'são somados. A importação guarda somente indicadores agregados; '
             'não atualiza pedidos nem a cobertura da coleta diária.</p><ul>')
    for report in reports:
        summary = report['resumo']
        if isinstance(summary, str):
            summary = json.loads(summary)
        body += ('<li>' + escape(str(summary['period_start'])) + ' a '
                 + escape(str(summary['period_end'])) + ': '
                 + str(int(summary['rows'])) + ' lançamentos; frete informado '
                 + format_brl(summary['seller_shipping_total']) + '</li>')
    return body + '</ul></section>'
