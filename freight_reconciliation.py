"""Read-only diagnostics for the verified DAILY_CONCILIATION sales export.

Rows are ledger movements, not unique orders. No expected shipping price is
available in this export. Never feed these rows directly to compare_freight_orders.
"""
import io
import unicodedata
from decimal import Decimal, InvalidOperation

from freight_import import PreviewError, preview_reconciliation_upload

MAX_LEDGER_ROWS = 25000
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


def inspect_sales_reconciliation(filename, payload):
    """Return aggregate structural checks only; never persist or return raw rows."""
    preview_reconciliation_upload(filename, payload)  # shared ZIP/size safeguards
    if not (filename or '').lower().endswith('.xlsx'):
        raise PreviewError('A conferência de lançamentos requer o relatório XLSX por vendas.')
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(payload), read_only=True, data_only=False, keep_links=False)
    try:
        if wb.sheetnames != ['DAILY_CONCILIATION']:
            raise PreviewError('Formato não reconhecido: esperada a aba DAILY_CONCILIATION.')
        ws = wb.active
        if ws.max_row > MAX_LEDGER_ROWS + 3 or ws.max_column > 45:
            raise PreviewError('Relatório excede o limite de linhas ou colunas.')
        columns = schema_columns(next(ws.iter_rows(min_row=3, max_row=3,
                                                   max_col=45, values_only=True)))
        result = dict(rows=0, shipping_rows=0, invalid_shipping_rows=0,
                      inconsistent_shipping_rows=0, repeated_operation_rows=0,
                      missing_operation_rows=0)
        seen = set()
        for row in ws.iter_rows(min_row=4, max_row=MAX_LEDGER_ROWS + 4,
                                max_col=45, values_only=True):
            if all(v is None or v == '' for v in row):
                continue
            result['rows'] += 1
            if result['rows'] > MAX_LEDGER_ROWS:
                raise PreviewError('Relatório excede o limite de lançamentos.')
            operation = row[columns['operation_id']]
            if not isinstance(operation, str) or not operation.strip() or operation.startswith('='):
                result['missing_operation_rows'] += 1
            elif operation in seen:
                result['repeated_operation_rows'] += 1
            else:
                seen.add(operation)
            try:
                gross, discount, seller = [_amount(row[columns[key]]) for key in
                    ('gross_shipping', 'shipping_discount', 'seller_shipping')]
            except (ValueError, InvalidOperation):
                result['invalid_shipping_rows'] += 1
                continue
            if any((gross, discount, seller)):
                result['shipping_rows'] += 1
            if discount > gross or abs(gross - discount - seller) > Decimal('.01'):
                result['inconsistent_shipping_rows'] += 1
        return result
    finally:
        wb.close()


def render_sales_reconciliation(result):
    labels = {
        'rows': 'Lançamentos lidos', 'shipping_rows': 'Lançamentos com frete',
        'repeated_operation_rows': 'Linhas adicionais com a mesma operação',
        'missing_operation_rows': 'Linhas sem identificador textual válido',
        'invalid_shipping_rows': 'Linhas com valor de frete inválido ou ausente',
        'inconsistent_shipping_rows': 'Linhas com diferença entre bruto menos desconto e pago pelo vendedor',
    }
    return ('<section class="card"><h3>Conferência do relatório por vendas</h3><ul>'
            + ''.join('<li>' + label + ': ' + str(int(result[key])) + '</li>'
                      for key, label in labels.items())
            + '</ul><p>Conferência aritmética por lançamento, com tolerância de R$ 0,01. '
            'Operações repetidas não são descartadas nem somadas como pedidos únicos. '
            'O envio pago pelo comprador e as tarifas totais são campos separados. '
            'O relatório não informa o frete esperado: diferenças não comprovam cobrança indevida. '
            'Nenhum dado foi salvo.</p></section>')
