import io
import unittest
from unittest.mock import patch
from openpyxl import Workbook
from freight_import import PreviewError
from freight_reconciliation import FIELDS, inspect_sales_reconciliation, schema_columns


class SalesReconciliationTests(unittest.TestCase):
    def workbook(self, entries, headers=None):
        wb = Workbook()
        ws = wb.active
        ws.title = 'DAILY_CONCILIATION'
        ws.append(['Descrição sintética'])
        ws.append(['Operação', 'Envio'])
        ws.append(headers or list(FIELDS.values()))
        for entry in entries:
            values = dict(operation_id='synthetic-operation', gross_shipping=20,
                          shipping_discount=5, seller_shipping=15, buyer_shipping=8)
            values.update(entry)
            ws.append([values.get(key) for key in FIELDS])
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    def inspect(self, entries):
        return inspect_sales_reconciliation('synthetic.xlsx', self.workbook(entries))

    def test_preserves_movements_and_separates_buyer_shipping(self):
        result = self.inspect([{}, {}, {'operation_id': 'synthetic-other',
                                       'seller_shipping': 16}])
        self.assertEqual(result['rows'], 3)
        self.assertEqual(result['shipping_rows'], 3)
        self.assertEqual(result['repeated_operation_rows'], 1)
        self.assertEqual(result['inconsistent_shipping_rows'], 1)
        self.assertNotIn('expected', result)
        self.assertNotIn('synthetic-operation', str(result))

    def test_invalid_values_do_not_become_zero(self):
        for value in (None, '=10+5', -1, True, 'R$ 15,00', 15.001):
            with self.subTest(value=value):
                self.assertEqual(self.inspect([{'seller_shipping': value}])[
                    'invalid_shipping_rows'], 1)
        self.assertEqual(self.inspect([{'gross_shipping': 0, 'shipping_discount': 0,
                                       'seller_shipping': 0}])['shipping_rows'], 0)

    def test_tolerance_and_missing_identifiers(self):
        result = self.inspect([{'seller_shipping': 15.01, 'operation_id': None},
                               {'seller_shipping': 15.02, 'operation_id': 123}])
        self.assertEqual(result['inconsistent_shipping_rows'], 1)
        self.assertEqual(result['missing_operation_rows'], 2)

    def test_exact_unambiguous_schema_and_reordering(self):
        headers = list(reversed(list(FIELDS.values())))
        self.assertEqual(schema_columns(headers)['operation_date'], len(headers) - 1)
        for invalid in (headers[:-1], headers + [headers[0]]):
            with self.assertRaises(PreviewError):
                schema_columns(invalid)

    def test_unknown_format_and_row_limit(self):
        with self.assertRaises(PreviewError):
            inspect_sales_reconciliation('unknown.csv', b'A;B\n1;2')
        with patch('freight_reconciliation.MAX_LEDGER_ROWS', 1):
            with self.assertRaises(PreviewError):
                self.inspect([{}, {}])

    def test_absent_shipping_is_separate_from_partial_values_and_zero(self):
        result = self.inspect([
            dict(gross_shipping='', shipping_discount='', seller_shipping=''),
            dict(gross_shipping=None, shipping_discount=None, seller_shipping=None),
            dict(gross_shipping=20, shipping_discount='', seller_shipping=15),
            dict(gross_shipping=0, shipping_discount=0, seller_shipping=0)])
        self.assertEqual(result['absent_shipping_rows'], 2)
        self.assertEqual(result['invalid_shipping_rows'], 1)
        self.assertEqual(result['shipping_rows'], 0)
        self.assertEqual(result['seller_shipping_total'], '0.00')

    def test_dates_are_parsed_chronologically_and_totals_exclude_invalid(self):
        result = self.inspect([dict(operation_date='30/09/2026'),
                               dict(operation_date='01/10/2026'),
                               dict(operation_date='31/09/2026', seller_shipping=None)])
        self.assertEqual(result['period_start'], '2026-09-30')
        self.assertEqual(result['period_end'], '2026-10-01')
        self.assertEqual(result['invalid_date_rows'], 1)
        self.assertEqual(result['seller_shipping_total'], '30.00')
        self.assertEqual(result['gross_shipping_total'], '40.00')


if __name__ == '__main__':
    unittest.main()
