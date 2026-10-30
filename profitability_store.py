"""Append-only, tenant-scoped financial evidence. No marketplace writes."""
import hashlib
import json
import re
from datetime import date, timedelta
from decimal import Decimal
from listing_profitability import COMPONENTS, amount, period_contribution
from listing_sales import listing_sales_summary
from sales_metrics import created_day


def init_schema(conn, execute):
    # Retain financial history if a connection is explicitly removed later;
    # no cascading deletion and no FK that blocks the existing removal flow.
    execute(conn, '''CREATE TABLE IF NOT EXISTS listing_profitability_records (
        id BIGSERIAL PRIMARY KEY,
        conexao_id INTEGER NOT NULL,
        item_id TEXT NOT NULL,
        inicio DATE NOT NULL, fim DATE NOT NULL CHECK(fim >= inicio),
        gross_items NUMERIC NOT NULL CHECK(gross_items >= 0),
        units BIGINT NOT NULL CHECK(units >= 0),
        sales_fingerprint CHAR(64) NOT NULL,
        costs JSONB NOT NULL, sources JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_by INTEGER NOT NULL,
        submission_key TEXT NOT NULL,
        UNIQUE(conexao_id, submission_key))''')
    execute(conn, '''CREATE INDEX IF NOT EXISTS listing_profitability_period_idx
        ON listing_profitability_records(conexao_id,item_id,inicio,fim,id DESC)''')


def period(args, today):
    end = today - timedelta(days=1)
    start = end - timedelta(days=6)
    if args.get('inicio') or args.get('fim'):
        try:
            start = date.fromisoformat(args.get('inicio', ''))
            end = date.fromisoformat(args.get('fim', ''))
        except (ValueError, TypeError):
            raise ValueError('Informe as duas datas do período.') from None
    if not 1 <= (end-start).days+1 <= 90 or end >= today or start < today-timedelta(days=366):
        raise ValueError('Selecione até 90 dias encerrados, dentro dos últimos 366 dias.')
    return start, end


def read_sales_context(conn, query, cid, start, end):
    # Match existing strict listing-sales gates; no remote API or writes.
    bounds = (cid,(start-timedelta(days=1)).isoformat(),
              (end+timedelta(days=1)).isoformat(),start.isoformat(),end.isoformat())
    orders = query(conn, '''SELECT conexao_id,pedido_id,status,total,moeda,criado_em,
        pagamentos_json,unidades,vendas_dia_coleta FROM pedidos
        WHERE conexao_id=%s AND vendas_verificado_em IS NOT NULL
          AND (LEFT(criado_em,10) BETWEEN %s AND %s
               OR vendas_dia_coleta BETWEEN %s AND %s)''', bounds)
    items = query(conn, '''SELECT pi.conexao_id,pi.pedido_id,pi.item_id,
        pi.quantidade,pi.preco_unitario FROM pedidos_itens pi JOIN pedidos p
        ON p.conexao_id=pi.conexao_id AND p.pedido_id=pi.pedido_id
        WHERE pi.conexao_id=%s AND p.vendas_verificado_em IS NOT NULL
          AND (LEFT(p.criado_em,10) BETWEEN %s AND %s
               OR p.vendas_dia_coleta BETWEEN %s AND %s)''', bounds)
    coverage = query(conn, '''SELECT dia FROM vendas_cobertura
        WHERE conexao_id=%s AND dia BETWEEN %s AND %s''',
        (cid,start.isoformat(),end.isoformat()))
    pending = query(conn, '''SELECT EXISTS(SELECT 1 FROM pedidos
        WHERE conexao_id=%s AND vendas_verificado_em IS NULL) AS pending''', (cid,))
    return dict(orders=orders, items=items, coverage=[r['dia'] for r in coverage],
                pending=bool(pending and pending[0]['pending']))


def summarize_context(context, cid, item_id, start, end):
    orders, items = context['orders'], context['items']
    summary = listing_sales_summary(orders, items, context['coverage'],
                                   item_id, end=end, days=(end-start).days+1)
    if context['pending']:
        summary.update(orders=None, units=None, gross_items=None,
                       reason='Há pedidos ainda não verificados nesta loja.')
    summary['fingerprint'] = fingerprint_for(cid,item_id,start,end,orders,items)
    return summary


def fingerprint_for(cid,item_id,start,end,orders,items):
    # Retain only this listing's period basis; changes to status, quantity,
    # price or payments invalidate the saved evidence, even at equal totals.
    selected_orders = [r for r in orders if (created_day(r.get('criado_em')) is not None
        and start <= created_day(r['criado_em']) <= end)]
    keys = {(r['conexao_id'], str(r['pedido_id'])) for r in selected_orders}
    selected_items = [r for r in items if str(r['item_id']) == item_id
                      and (r['conexao_id'], str(r['pedido_id'])) in keys]
    target_keys = {(r['conexao_id'], str(r['pedido_id'])) for r in selected_items}
    selected_orders = [r for r in selected_orders
                       if (r['conexao_id'], str(r['pedido_id'])) in target_keys]
    canonical = lambda rows: sorted(json.dumps(r, sort_keys=True, default=str) for r in rows)
    return hashlib.sha256(json.dumps(
        [cid,item_id,start.isoformat(),end.isoformat(),canonical(selected_orders),canonical(selected_items)],
        ensure_ascii=True).encode()).hexdigest()



def load_sales(conn, query, cid, item_id, start, end):
    return summarize_context(read_sales_context(conn, query, cid, start, end),
                             cid, item_id, start, end)


def load_pair(conn, query, cid, item_id, start, end, earliest=None):
    """Two equal adjacent periods, sharing four store-scoped reads."""
    days = (end-start).days+1
    previous_end = start-timedelta(days=1)
    previous_start = previous_end-timedelta(days=days-1)
    previous_allowed = earliest is None or previous_start >= earliest
    context = read_sales_context(conn, query, cid, previous_start if previous_allowed else start, end)
    previous = (summarize_context(context,cid,item_id,previous_start,previous_end)
        if previous_allowed else dict(orders=None,units=None,gross_items=None,ticket=None,
            start=previous_start.isoformat(),end=previous_end.isoformat(),outside_window=True,
            reason='Período anterior fora da janela permitida dos últimos 366 dias.'))
    return dict(current=summarize_context(context,cid,item_id,start,end),
                previous=previous,
                previous_start=previous_start, previous_end=previous_end)


def validate(form):
    if form.get('confirmed') != 'yes':
        raise ValueError('Confirme as fontes e a abrangência dos custos do período.')
    key = form.get('submission_key', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{24,80}', key):
        raise ValueError('Formulário inválido. Recarregue a página.')
    costs, sources = {}, {}
    for field, label in COMPONENTS.items():
        raw = str(form.get(field, '')).strip()
        # Disallow ambiguous thousands separators, scientific notation and
        # silent precision loss when persisting currency.
        if not re.fullmatch(r'\d{1,12}(?:[.,]\d{1,2})?', raw):
            raise ValueError(label + ': informe reais sem separador de milhar, com até duas casas.')
        costs[field] = amount(raw.replace(',', '.'))
        source = str(form.get(field+'_source', '')).strip()
        if not 5 <= len(source) <= 500:
            raise ValueError(label + ': informe uma referência de 5 a 500 caracteres.')
        sources[field] = source
    return costs, sources, key


def result_for(summary, record):
    if summary.get('orders') is None:
        return dict(available=False, contribution=None, margin_pct=None,
                    reason=summary.get('reason') or 'Vendas não verificáveis.')
    if not record:
        return dict(available=False, contribution=None, margin_pct=None,
                    reason='Aguardando custos documentados para este anúncio e período.')
    if (record['sales_fingerprint'] != summary['fingerprint']
            or amount(record['gross_items']) != amount(summary['gross_items'])
            or amount(record['units']) != amount(summary['units'])):
        return dict(available=False, contribution=None, margin_pct=None,
                    reason='As vendas mudaram após o registro. Revise os custos e registre uma nova versão.')
    return period_contribution(summary['gross_items'], summary['units'],
                               record['costs'], record['sources'])


def save(conn, execute, cid, item_id, start, end, summary, costs, sources, user_id, key):
    if summary.get('orders') is None:
        raise ValueError('Não é possível registrar custos sem vendas verificáveis no período.')
    execute(conn, '''INSERT INTO listing_profitability_records
        (conexao_id,item_id,inicio,fim,gross_items,units,sales_fingerprint,
         costs,sources,created_by,submission_key)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)
        ON CONFLICT(conexao_id,submission_key) DO NOTHING''',
        (cid,item_id,start,end,summary['gross_items'],summary['units'],summary['fingerprint'],
         json.dumps({k:str(v) for k,v in costs.items()}),json.dumps(sources),user_id,key))
