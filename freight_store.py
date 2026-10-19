"""Store-scoped report summaries; never store customer rows or upload bytes."""
import hashlib
import json
import datetime
from html import escape


def init_freight_schema(conn, execute):
    execute(conn, '''CREATE TABLE IF NOT EXISTS frete_importacoes (
        id BIGSERIAL PRIMARY KEY,
        conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        arquivo_sha256 CHAR(64) NOT NULL,
        importado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        resumo JSONB NOT NULL,
        UNIQUE (conexao_id, arquivo_sha256))''')
    execute(conn, '''CREATE TABLE IF NOT EXISTS frete_consolidacoes (
        importacao_id BIGINT PRIMARY KEY REFERENCES frete_importacoes(id) ON DELETE CASCADE,
        inicio DATE NOT NULL, fim DATE NOT NULL)''')
    execute(conn, '''CREATE TABLE IF NOT EXISTS frete_dias (
        conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        dia DATE NOT NULL,
        importacao_id BIGINT NOT NULL REFERENCES frete_importacoes(id),
        resumo JSONB NOT NULL, PRIMARY KEY(conexao_id,dia))''')


def confirmed_days(summary, start, end, confirmed):
    from freight_reconciliation import empty_day
    try:
        first, last = datetime.date.fromisoformat(start), datetime.date.fromisoformat(end)
    except (TypeError, ValueError):
        raise ValueError('Informe as datas de início e fim do relatório completo.') from None
    from sales_metrics import reporting_today
    if (not confirmed or last < first or (last - first).days > 30 or
            last > reporting_today() or summary['invalid_date_rows'] or
            not summary.get('daily') or any(not first.isoformat() <= day <= last.isoformat()
                                          for day in summary['daily'])):
        raise ValueError('Confirme um relatório completo de até 31 dias, sem datas futuras ou lançamentos fora do período.')
    return {day.isoformat(): summary['daily'].get(day.isoformat(), empty_day())
            for day in (first + datetime.timedelta(days=i)
                        for i in range((last - first).days + 1))}


def consolidate_report(conn, query, store_id, payload, summary, start, end, confirmed):
    """Replace complete daily snapshots atomically; never add overlapping reports."""
    days = confirmed_days(summary, start, end, confirmed)
    query(conn, 'SELECT pg_advisory_xact_lock(72593,%s)', (store_id,))
    save_report(conn, query, store_id, payload, summary)
    report = query(conn, '''SELECT id FROM frete_importacoes
        WHERE conexao_id=%s AND arquivo_sha256=%s''',
        (store_id, hashlib.sha256(payload).hexdigest()))[0]['id']
    claimed = query(conn, '''INSERT INTO frete_consolidacoes (importacao_id,inicio,fim)
        VALUES (%s,%s,%s) ON CONFLICT (importacao_id) DO NOTHING RETURNING importacao_id''',
        (report, start, end))
    if not claimed:
        return False
    for day, values in days.items():
        query(conn, '''INSERT INTO frete_dias (conexao_id,dia,importacao_id,resumo)
            VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT (conexao_id,dia) DO UPDATE
            SET importacao_id=EXCLUDED.importacao_id,resumo=EXCLUDED.resumo RETURNING dia''',
            (store_id, day, report, json.dumps(values)))
    return True


def consolidated_history(conn, query, store_id):
    from sales_metrics import reporting_today
    last = reporting_today()
    return query(conn, '''SELECT dia,resumo FROM frete_dias WHERE conexao_id=%s
        AND dia BETWEEN %s AND %s ORDER BY dia''',
        (store_id, last - datetime.timedelta(days=29), last))


def render_consolidated(reports):
    from decimal import Decimal
    from freight_comparison import format_brl
    summaries = [row['resumo'] if isinstance(row['resumo'], dict)
                 else json.loads(row['resumo']) for row in reports]
    total = sum((Decimal(r['seller_shipping_total']) for r in summaries), Decimal('0'))
    return ('<section class="card"><h3>Conciliação dos últimos 30 dias</h3><p>'
            + str(len(reports)) + ' de 30 dias com relatório completo confirmado. '
            'Dias sem relatório não são considerados zero.</p><p>Frete informado nos dias cobertos: '
            + format_brl(total) + '</p><p>A atualização substitui somente os dias '
            'confirmados; preserva o histórico anterior e não soma sobreposições. '
            'Totais incluem somente linhas com valores válidos.</p></section>')


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
