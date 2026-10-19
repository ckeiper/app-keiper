"""Exercise authenticated freight requests with the real store page renderer.

Only database reads are replaced; no production DB, scheduler or customer data.
"""
import contextlib
import html
import io
import secrets
import unittest
from functools import wraps
from unittest.mock import Mock

from flask import Flask, request, redirect, Response, session
from openpyxl import Workbook
import freight_import
import freight_reconciliation
import freight_store
from freight_comparison import render_freight_comparison_demo
from test_listing_details import main_function


class FreightRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY='synthetic-test-key')
        self.query = Mock(return_value=[{'cliente': 'Loja sintética <teste>'}])
        env = dict(session=session, request=request, Response=Response,
                   redirect=redirect, secrets=secrets, wraps=wraps, esc=html.escape,
                   banco=lambda: contextlib.nullcontext(None), consultar=self.query,
                   CSS='', VISUAL_CSS='', SCRIPT='', img_logo=lambda size: '',
                   render_freight_comparison_demo=render_freight_comparison_demo)
        env.update(save_report=freight_store.save_report,
                   report_history=freight_store.report_history,
                   render_history=freight_store.render_history)
        for module in (freight_import, freight_reconciliation):
            env.update({name: getattr(module, name) for name in (
                'PreviewError', 'MAX_UPLOAD_BYTES', 'preview_reconciliation_upload',
                'render_reconciliation_preview', 'render_reconciliation_column_hints',
                'inspect_sales_reconciliation', 'render_sales_reconciliation')
                if hasattr(module, name)})
        for name in ('pagina', 'pagina_loja', 'pode_ver_loja', 'login_required', 'auditoria_frete'):
            main_function(name, env)
        self.app.add_url_rule('/auditoria-frete/<int:cid>', methods=['GET', 'POST'],
                              view_func=env['login_required'](env['auditoria_frete']))
        self.client = self.app.test_client()
        with self.client.session_transaction() as state:
            state.update(usuario_id=1, tipo='cliente', conexao_id=5)

    def test_get_renders_real_store_page_and_active_navigation(self):
        response = self.client.get('/auditoria-frete/5')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        body = response.get_data(as_text=True)
        self.assertIn('Loja sintética &lt;teste&gt;', body)
        self.assertIn("class='item atual' href='/auditoria-frete/5'", body)
        self.assertIn("name='csrf_token'", body)
        self.query.assert_called_once_with(None,
            'SELECT cliente FROM conexoes WHERE id=%s', (5,))

    def test_post_synthetic_workbook_renders_diagnostics(self):
        self.client.get('/auditoria-frete/5')
        with self.client.session_transaction() as state:
            token = state['freight_preview_csrf']
        wb = Workbook()
        ws = wb.active
        ws.title = 'DAILY_CONCILIATION'
        ws.append(['Relatório sintético'])
        ws.append(['Grupos'])
        ws.append(list(freight_reconciliation.FIELDS.values()))
        values = dict(operation_id='synthetic-order', gross_shipping=20,
                      shipping_discount=5, seller_shipping=15)
        ws.append([values.get(key) for key in freight_reconciliation.FIELDS])
        data = io.BytesIO()
        wb.save(data)
        data.seek(0)
        response = self.client.post('/auditoria-frete/5', data={
            'csrf_token': token, 'arquivo': (data, 'synthetic.xlsx')})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Lançamentos lidos: 1', response.get_data(as_text=True))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_unauthorized_access_does_not_read_store(self):
        self.assertEqual(self.client.get('/auditoria-frete/6').status_code, 302)
        self.query.assert_not_called()
        with self.client.session_transaction() as state:
            state.clear()
        self.assertEqual(self.client.get('/auditoria-frete/5').location, '/login')
        self.query.assert_not_called()

    def test_missing_store_returns_404(self):
        self.query.return_value = []
        self.assertEqual(self.client.get('/auditoria-frete/5').status_code, 404)

    def test_invalid_csrf_and_invalid_upload(self):
        response = self.client.post('/auditoria-frete/5', data={'csrf_token': 'invalid'})
        self.assertEqual(response.status_code, 403)
        self.client.get('/auditoria-frete/5')
        with self.client.session_transaction() as state:
            token = state['freight_preview_csrf']
        response = self.client.post('/auditoria-frete/5', data={
            'csrf_token': token, 'arquivo': (io.BytesIO(b'invalid'), 'test.xlsx')})
        self.assertEqual(response.status_code, 400)

    def test_client_cannot_import_even_with_valid_csrf(self):
        self.client.get('/auditoria-frete/5')
        with self.client.session_transaction() as state:
            token = state['freight_preview_csrf']
        response = self.client.post('/auditoria-frete/5', data={
            'csrf_token': token, 'acao': 'importar'})
        self.assertEqual(response.status_code, 403)

    def test_admin_imports_into_selected_store(self):
        with self.client.session_transaction() as state:
            state['tipo'] = 'admin'
        self.query.side_effect = [[{'cliente': 'Loja sintética'}], []]
        response = self.client.get('/auditoria-frete/5')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Importar indicadores desta loja', response.get_data(as_text=True))
        with self.client.session_transaction() as state:
            token = state['freight_preview_csrf']
        from test_freight_reconciliation import SalesReconciliationTests
        payload = SalesReconciliationTests().workbook([dict(operation_date='01/10/2026')])
        self.query.reset_mock()
        self.query.side_effect = [[{'cliente': 'Loja sintética'}], [], [{'id': 1}]]
        response = self.client.post('/auditoria-frete/5', data={
            'csrf_token': token, 'acao': 'importar',
            'arquivo': (io.BytesIO(payload), 'synthetic.xlsx')})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Indicadores importados.', response.get_data(as_text=True))
        self.assertEqual(self.query.call_args.args[2][0], 5)


if __name__ == '__main__':
    unittest.main()
