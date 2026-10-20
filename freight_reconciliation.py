"""Read-only diagnostics for the verified DAILY_CONCILIATION sales export.

Rows are ledger movements, not unique orders. No expected shipping price is
available in this export. Never feed these rows directly to compare_freight_orders.
"""
import io
import unicodedata
import datetime
from decimal import Decimal, InvalidOperation

from freight_import import PreviewError, validate_xlsx_payload, _preview_rows

MAX_LEDGER_ROWS = 25000
DAILY_COUNTS = ('rows', 'shipping_rows', 'invalid_shipping_rows',
                'absent_shipping_rows', 'inconsistent_shipping_rows')
DAILY_AMOUNTS = ('gross_shipping_total', 'shipping_discount_total', 'seller_shipping_total')


def empty_day():
    return {**dict.fromkeys(DAILY_COUNTS, 0), **dict.fromkeys(DAILY_AMOUNTS, '0.00')}


FIELDS = {
    'operation_date': 'Data da operação',
    'operation_id': 'Número da operação',
    'operation_type': 'Tipo de operação',
    'operation_status': 'Status da operação',
    'sale_date': 'Data da venda',
    'buyer_shipping': 'Envio pago pelo comprador (+)',
    'total_fees': 'Valor total de tarifas (desconto já aplicado)',
    'postpaid_fees': 'Valor total de tarifas pós-pagas',
    'net_after_fees': 'Valor líquido após tarifas',
    'fee_details': 'Detalhes de tarifas',
    'shipment_id': 'Número do envio',
    'package_id': 'Número do pacote',
    'shipping_method': 'Método de envio',
    'gross_shipping': 'Valor bruto do envio',
    'shipping_discount': 'Desconto sobre o envio',
    'seller_shipping': 'Envio pago pelo vendedor',
}


def normalize(value):
    return ' '.join(''.join(c for c in unicodedata.normalize(
        'NFKD', str(value or '').casefold()) if not unicodedata.combining(c)).split())


def schema_columns(row):
    labels = [normalize(v) for v in row]
    wanted = {key: normalize(label) for key, label in FIELDS.items()}
    if not all(labels.count(label) == 1 for label in wanted.values()):
        raise PreviewError('Esquema de conciliação ausente, incompleto ou ambíguo.')
    return {key: labels.index(label) for key, label in wanted.items()}


def _amount(value):
    if value is None or isinstance(value, bool):
        raise ValueError
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError from None
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('.01')):
        raise ValueError
    return amount


def inspect_sales_reconciliation(filename, payload, bundle=False):
    """Return aggregate structural checks only; never persist or return raw rows."""
    if not (filename or '').lower().endswith('.xlsx'):
        raise PreviewError('A conferência de lançamentos requer o relatório XLSX por vendas.')
    validate_xlsx_payload(payload)
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(payload), read_only=True, data_only=False, keep_links=False)
    except Exception as exc:
        raise PreviewError('Não foi possível ler o arquivo XLSX.') from exc
    try:
        if wb.sheetnames != ['DAILY_CONCILIATION']:
            raise PreviewError('Formato não reconhecido: esperada a aba DAILY_CONCILIATION.')
        ws = wb.active
        if ws.max_row > MAX_LEDGER_ROWS + 3 or ws.max_column > 45:
            raise PreviewError('Relatório excede o limite de linhas ou colunas.')
        columns = schema_columns(next(ws.iter_rows(min_row=3, max_row=3,
                                                   max_col=45, values_only=True)))
        preview = ([{'name': ws.title, **_preview_rows(ws.iter_rows(
            min_row=1,max_row=20,max_col=45,values_only=True))}] if bundle else None)
        comparison_keys = ('operation_type','operation_id','shipment_id',
                           'gross_shipping','shipping_discount','seller_shipping')
        comparison_rows = []
        result = dict(rows=0, shipping_rows=0, invalid_shipping_rows=0,
                      inconsistent_shipping_rows=0, repeated_operation_rows=0,
                      missing_operation_rows=0, absent_shipping_rows=0,
                      invalid_date_rows=0)
        totals = [Decimal('0.00') for _ in range(3)]
        dates = set()
        daily = {}
        seen = set()
        for row in ws.iter_rows(min_row=4, max_row=MAX_LEDGER_ROWS + 4,
                                max_col=45, values_only=True):
            if all(v is None or v == '' for v in row):
                continue
            result['rows'] += 1
            if result['rows'] > MAX_LEDGER_ROWS:
                raise PreviewError('Relatório excede o limite de lançamentos.')
            if bundle:
                comparison_rows.append(tuple(row[columns[key]] for key in comparison_keys))
            value = row[columns['operation_date']]
            bucket = None
            try:
                day = (value.date() if isinstance(value, datetime.datetime) else
                       value if isinstance(value, datetime.date) else
                       datetime.datetime.strptime(value, '%d/%m/%Y').date())
                dates.add(day)
                bucket = daily.setdefault(day.isoformat(), empty_day())
                bucket['rows'] += 1
            except (ValueError, TypeError):
                result['invalid_date_rows'] += 1
            operation = row[columns['operation_id']]
            if not isinstance(operation, str) or not operation.strip() or operation.startswith('='):
                result['missing_operation_rows'] += 1
            elif operation in seen:
                result['repeated_operation_rows'] += 1
            else:
                seen.add(operation)
            values = [row[columns[key]] for key in
                      ('gross_shipping', 'shipping_discount', 'seller_shipping')]
            if all(v is None or v == '' for v in values):
                result['absent_shipping_rows'] += 1
                if bucket is not None:
                    bucket['absent_shipping_rows'] += 1
                continue
            try:
                gross, discount, seller = [_amount(v) for v in values]
            except (ValueError, InvalidOperation):
                result['invalid_shipping_rows'] += 1
                if bucket is not None:
                    bucket['invalid_shipping_rows'] += 1
                continue
            totals = [a + b for a, b in zip(totals, (gross, discount, seller))]
            if bucket is not None:
                for key, amount in zip(DAILY_AMOUNTS, (gross, discount, seller)):
                    bucket[key] = str(Decimal(bucket[key]) + amount)
            if any((gross, discount, seller)):
                result['shipping_rows'] += 1
                if bucket is not None:
                    bucket['shipping_rows'] += 1
            if discount > gross or abs(gross - discount - seller) > Decimal('.01'):
                result['inconsistent_shipping_rows'] += 1
                if bucket is not None:
                    bucket['inconsistent_shipping_rows'] += 1
        result.update(zip(('gross_shipping_total', 'shipping_discount_total',
                           'seller_shipping_total'), map(str, totals)))
        result.update(period_start=min(dates).isoformat() if dates else None,
                      period_end=max(dates).isoformat() if dates else None,
                      operation_days=len(dates))
        result['daily'] = dict(sorted(daily.items()))
        if bundle:
            return result, preview, comparison_rows, {key:i for i,key in enumerate(comparison_keys)}
        return result
    finally:
        wb.close()


def render_sales_reconciliation(result):
    """Decision-oriented summary, with technical diagnostics available on demand."""
    from freight_comparison import format_brl
    def metric(label, value):
        return ('<div class="frete-metrica"><span>' + label + '</span>'
                '<strong>' + str(value) + '</strong></div>')
    counts = (
        ('Lançamentos analisados', result['rows']),
        ('Com frete', result['shipping_rows']),
        ('Frete inválido', result['invalid_shipping_rows']),
        ('Datas inválidas', result['invalid_date_rows']),
    )
    details = (
        ('Operações repetidas', 'repeated_operation_rows'),
        ('Sem identificador', 'missing_operation_rows'),
        ('Sem informação de frete', 'absent_shipping_rows'),
        ('Diferença aritmética', 'inconsistent_shipping_rows'),
    )
    return (
        '<section class="card frete-resultado"><h3>Resumo do arquivo</h3>'
        '<p>Confira o volume processado e os valores informados no relatório.</p>'
        '<div class="frete-metricas">'
        + ''.join(metric(label, int(value)) for label, value in counts)
        + '</div><div class="frete-metricas">'
        + metric('Frete bruto informado', format_brl(result['gross_shipping_total']))
        + metric('Desconto informado', format_brl(result['shipping_discount_total']))
        + metric('Frete pago pelo vendedor', format_brl(result['seller_shipping_total']))
        + '</div><details class="frete-detalhes"><summary>Qualidade e consistência dos lançamentos</summary><ul>'
        + ''.join('<li>' + label + ': <b>' + str(int(result[key])) + '</b></li>'
                  for label, key in details)
        + '</ul><p>Totais consideram linhas com três valores válidos. Repetições não são '
          'descartadas automaticamente. Diferenças aritméticas usam tolerância de R$ 0,01. '
          'O arquivo não informa o frete esperado e não comprova cobranças indevidas.</p>'
        '</details></section>'
    )
