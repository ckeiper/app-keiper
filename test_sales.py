import ast
import contextlib
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from sales_metrics import change, created_day, order_fields, period, summarize
from sales_sync import init_sales_schema, sync_orders
from sales_view import render_sales


def row(oid='1', **changes):
    data = dict(conexao_id=4, pedido_id=oid, status='paid', total='120.00', moeda='BRL',
                criado_em='2026-10-10T12:00:00-03:00', unidades=3,
                pagamentos_json=[{'id': 1, 'status': 'approved'}])
    data.update(changes)
    return data


class MetricsTests(unittest.TestCase):
    def summarize(self, rows, covered=None):
        return summarize(rows, date(2026, 10, 10), date(2026, 10, 11),
                         {'2026-10-10', '2026-10-11'} if covered is None else covered)

    def test_presets_and_previous_window(self):
        for n in (7, 15, 30, 60, 90):
            start, end, before, before_end = period({'periodo': str(n)}, date(2026, 10, 15))
            self.assertEqual((end-start).days + 1, n)
            self.assertEqual((before_end-before).days + 1, n)
            self.assertEqual(before_end + timedelta(days=1), start)

    def test_custom_leap_and_single_day(self):
        self.assertEqual(period({'periodo': 'personalizado', 'inicio': '2024-02-29', 'fim': '2024-03-01'}, date(2026, 10, 15)),
                         (date(2024, 2, 29), date(2024, 3, 1), date(2024, 2, 27), date(2024, 2, 28)))
        self.assertEqual(period({'periodo': 'personalizado', 'inicio': '2026-10-10', 'fim': '2026-10-10'}, date(2026, 10, 15))[2], date(2026, 10, 9))

    def test_invalid_ranges(self):
        for args in ({'periodo': '8'}, {'periodo': 'personalizado'},
                     {'periodo': 'personalizado', 'inicio': '2026-10-16', 'fim': '2026-10-15'},
                     {'periodo': 'personalizado', 'inicio': '2026-10-15', 'fim': '2026-10-16'},
                     {'periodo': 'personalizado', 'inicio': '2020-01-01', 'fim': '2026-10-15'}):
            with self.assertRaises(ValueError):
                period(args, date(2026, 10, 15))

    def test_metrics_are_order_based_not_payment_or_item_based(self):
        first = row(pagamentos_json=[{'status': 'approved'}, {'status': 'approved'}])
        report = self.summarize([first, first, row('2', total='80', unidades=1)])
        self.assertEqual(report['revenue'], Decimal('200'))
        self.assertEqual(report['orders'], 2)
        self.assertEqual(report['units'], 4)
        self.assertEqual(report['ticket'], Decimal('100'))
        self.assertEqual(report['unit_price'], Decimal('50'))
        self.assertEqual(report['daily'], [200.0, 0.0])

    def test_only_paid_orders_with_approved_payments(self):
        report = self.summarize([row(), row('2', status='confirmed'),
                                 row('3', pagamentos_json=[{'status': 'pending'}]),
                                 row('4', status='cancelled'),
                                 row('5', status='cancelled', pagamentos_json=[{'status': 'refunded'}]),
                                 row('6', pagamentos_json=[{'status': 'refunded'}])])
        self.assertEqual(report['revenue'], 120)
        self.assertEqual(report['cancellations'], 2)
        self.assertIsNone(report['refunds'])
        self.assertIsNone(report['returns'])

    def test_missing_units_do_not_become_one(self):
        report = self.summarize([row(unidades=None)])
        self.assertEqual(report['revenue'], 120)
        self.assertEqual(report['ticket'], 120)
        self.assertIsNone(report['units'])
        self.assertIsNone(report['unit_price'])

    def test_uncovered_days_are_null_not_zero(self):
        report = self.summarize([row()], {'2026-10-10'})
        self.assertIsNone(report['revenue'])
        self.assertIsNone(report['orders'])
        self.assertIsNone(report['cancellations'])
        self.assertEqual(report['daily'], [120.0, None])

    def test_invalid_financial_fields_never_become_zero(self):
        for changes in ({'total': None}, {'total': 'NaN'}, {'total': '-1'}, {'moeda': 'USD'},
                        {'pagamentos_json': None}, {'pagamentos_json': []},
                        {'pagamentos_json': [None]}, {'criado_em': None}, {'criado_em': '2026-10-10'}):
            report = self.summarize([row(**changes)])
            self.assertIsNone(report['revenue'], changes)

    def test_timezone_and_creation_not_close_date(self):
        self.assertEqual(created_day('2026-10-11T01:00:00Z'), date(2026, 10, 10))
        report = self.summarize([row(criado_em='2026-10-10T23:59:59-03:00', fechado_em='2026-10-12T00:00:00-03:00'),
                                 row('2', criado_em='2026-10-12T00:00:00-03:00')])
        self.assertEqual(report['daily'], [120.0, 0.0])

    def test_zero_and_decimal_precision(self):
        empty = self.summarize([])
        self.assertEqual(empty['revenue'], 0)
        self.assertIsNone(empty['ticket'])
        self.assertIsNone(empty['unit_price'])
        self.assertEqual(change(Decimal(0), Decimal(0)), 0)
        self.assertIsNone(change(Decimal(1), Decimal(0)))
        self.assertIsNone(change(None, Decimal(1)))
        self.assertEqual(change(Decimal(90), Decimal(100)), -10)
        self.assertEqual(self.summarize([row(total='0.1'), row('2', total='0.2')])['revenue'], Decimal('0.3'))

    def test_normalization_missing_and_variations(self):
        self.assertEqual(order_fields({}), (None, None, None))
        self.assertIsNone(order_fields({'order_items': [{'quantity': None}]})[2])
        self.assertEqual(order_fields({'order_items': [{'quantity': 2}, {'quantity': 3}]})[2], 5)
        self.assertEqual(order_fields({'payments': [{'id': 1, 'status': 'approved', 'payer': 'private'}]})[1],
                         [{'id': 1, 'status': 'approved'}])


class SyncTests(unittest.TestCase):
    def run_sync(self, api):
        writes, logs = [], []
        def execute(conn, sql, params=()):
            writes.append((sql, params))
        with patch('sales_sync.reporting_today', return_value=date(2026, 10, 15)):
            result = sync_orders(4, 'token', 5, lambda: contextlib.nullcontext(None),
                                 lambda *a: [], execute, api, lambda *a: logs.append(a))
        return result, writes, logs

    def test_empty_day_is_covered_and_scope_is_bounded(self):
        calls = []
        def api(*args):
            calls.append(args)
            return {'results': [], 'paging': {'total': 0}}, None
        success, writes, logs = self.run_sync(api)
        self.assertTrue(success)
        self.assertEqual(len(calls), 37)
        self.assertEqual(len([s for s, p in writes if 'INSERT INTO vendas_cobertura' in s]), 37)
        self.assertIn('-03:00', calls[0][2]['order.date_created.from'])

    def test_api_failure_invalidates_coverage(self):
        success, writes, logs = self.run_sync(lambda *a: (None, 'HTTP 403'))
        self.assertFalse(success)
        self.assertTrue(logs)
        self.assertFalse(any('INSERT INTO vendas_cobertura' in s for s, p in writes))
        self.assertTrue(any('DELETE FROM vendas_cobertura' in s for s, p in writes))

    def test_pagination_cap_not_marked_complete(self):
        def api(token, path, params):
            return {'results': [{'id': params['offset'] + i + 1,
                                 'date_created': '2026-10-15T12:00:00-03:00',
                                 'payments': [], 'order_items': [{'quantity': 1}]} for i in range(50)],
                    'paging': {'total': 1001}}, None
        success, writes, _ = self.run_sync(api)
        self.assertFalse(success)
        self.assertFalse(any('INSERT INTO vendas_cobertura' in s for s, p in writes))

    def test_multiple_pages_and_variations(self):
        def api(token, path, params):
            offset = params['offset']
            results = [{'id': offset+i+1, 'date_created': '2026-10-15T12:00:00-03:00',
                        'payments': [{'id': 1, 'status': 'approved'}],
                        'order_items': [{'item': {'id': 'MLB1'}, 'quantity': 2, 'unit_price': 10},
                                        {'item': {'id': 'MLB1'}, 'quantity': 1, 'unit_price': 40}]} for i in range(50 if offset == 0 else 1)]
            return {'results': results, 'paging': {'total': 51}}, None
        success, writes, _ = self.run_sync(api)
        self.assertTrue(success)
        items = [p for s, p in writes if 'INSERT INTO pedidos_itens' in s]
        self.assertEqual(items[0][3:5], (3, 20))
        self.assertEqual(len(items), 51 * 37)

    def test_schema_is_additive_idempotent(self):
        statements = []
        init_sales_schema(None, lambda conn, sql: statements.append(sql))
        self.assertEqual(len(statements), 5)
        self.assertTrue(all('IF NOT EXISTS' in s for s in statements))


class ViewTests(unittest.TestCase):
    def test_view_gaps_accessible_table_and_filters(self):
        def query(conn, sql, params):
            if 'COUNT(*)' in sql:
                return [{'n': 1}]
            return []
        view = render_sales(4, {'periodo': '7'}, lambda: contextlib.nullcontext(None), query)
        self.assertIn('Histórico incompleto', view)
        self.assertIn('Ver dados do gráfico', view)
        self.assertIn('spanGaps:false', view)
        self.assertIn('Devoluções: indisponível', view)
        self.assertIn("value='90'", view)
        self.assertNotIn('conversão', view)

    def test_validation_escapes_input_without_query(self):
        def forbidden(*args):
            self.fail('invalid filter must not query database')
        view = render_sales(4, {'periodo': 'invalid', 'inicio': "' onfocus='alert(1)"}, forbidden, forbidden)
        self.assertIn('&#x27;', view)
        self.assertNotIn("value='' onfocus=", view)

    def test_main_compiles_and_keeps_existing_routes(self):
        source = Path('main.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        compile(tree, 'main.py', 'exec')
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for name in ('vendas', 'exportar_vendas', 'painel_detalhe', 'calcular_vendas'):
            self.assertIn(name, functions)
        route = ast.get_source_segment(source, functions['vendas'])
        self.assertLess(route.index('pode_ver_loja'), route.index('render_sales'))


if __name__ == '__main__':
    unittest.main()
