import unittest
import contextlib
from datetime import date
from decimal import Decimal
from copy import deepcopy
from functools import wraps
from unittest.mock import Mock, patch
from flask import Flask, session, redirect
from web_security import install_security
from installment_comparison import simulate, render, register, COMMON, SCENARIO


def form():
    out = dict(product='40', taxes='5', shipping='10', ads='5', adjustments='0',
               assumptions='yes', _csrf='test-token')
    for i, (fee, financing, installments) in enumerate((('10', '0', '1'), ('15', '5', '6'))):
        out.update({f'label_{i}': 'Opção '+str(i+1), f'installments_{i}': installments,
                    f'gross_{i}': '100', f'fee_{i}': fee, f'financing_{i}': financing,
                    f'source_{i}': 'Simulação manual de teste', f'source_date_{i}': '2026-10-25'})
    return out


class InstallmentComparisonTests(unittest.TestCase):
    def test_total_fee_already_includes_financing_and_exact_deltas(self):
        f = form(); before = deepcopy(f); result = simulate(f, date(2026, 10, 26))
        a, b = result['rows']
        self.assertEqual(a['costs'], Decimal('70'))
        self.assertEqual(a['contribution'], Decimal('30'))
        self.assertEqual(b['costs'], Decimal('75'))
        self.assertEqual(b['contribution'], Decimal('25'))
        self.assertEqual(b['delta'], Decimal('-5'))
        self.assertEqual(a['delta'], 0)
        self.assertEqual(f, before)

    def test_price_changes_cents_negative_and_zero_are_explicit(self):
        f = form(); f.update(gross_1='99,99', fee_1='0', financing_1='0', product='200.01')
        a, b = simulate(f)['rows']
        self.assertEqual(b['contribution'], Decimal('-120.02'))
        self.assertEqual(b['delta'], Decimal('9.99'))
        self.assertLess(a['contribution'], 0)
        f.update(fee_1='5', financing_1='5')
        self.assertEqual(simulate(f)['rows'][1]['fee'], Decimal('5'))

    def test_missing_invalid_and_nonfinite_costs_never_become_zero(self):
        for key in [*COMMON, *(k+'_0' for k in SCENARIO)]:
            for value in ('', None, 'NaN', '-1', '1e2', '1.001', '1.000,00', True):
                f = form(); f[key] = value
                with self.assertRaises(ValueError, msg=(key, value)):
                    simulate(f)
        for updates in (dict(gross_0='0'), dict(financing_1='15.01'), dict(assumptions='no')):
            f = form(); f.update(updates)
            with self.assertRaises(ValueError): simulate(f)

    def test_two_required_third_all_or_nothing_and_reference_dates(self):
        for updates in (dict(label_0=''), dict(source_0='curta'), dict(source_date_1='2026-10-27'),
                        dict(source_date_0='invalid'), dict(installments_0='0'), dict(installments_0='49'),
                        dict(installments_0='1.5'), dict(label_2='Parcial')):
            f = form(); f.update(updates)
            with self.assertRaises(ValueError): simulate(f, date(2026, 10, 26))
        f = form()
        for key in ['label', 'source', 'source_date', 'installments', *SCENARIO]:
            f[key+'_2'] = f[key+'_1']
        f['installments_2'] = '48'
        self.assertEqual(len(simulate(f)['rows']), 3)

    def test_renderer_escapes_and_does_not_invent_results(self):
        f = form(); f.update(label_0='<script>', source_0='<script>alert(1)</script>')
        page = render(1, 'MLB100', '<script>', 'token', f, simulate(f))
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('Financiamento incluído', page)
        self.assertIn('referência declarada não é verificada', page)
        self.assertIn('não é lucro líquido', page)
        empty = render(1, 'MLB100', 'Título', 'token')
        self.assertNotIn('id="installment-results"', empty)
        self.assertNotIn('R$ 0,00', empty)


class InstallmentRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__); self.app.secret_key = 'isolated'; self.app.testing = True
        install_security(self.app)
        self.query = Mock(return_value=[dict(cliente='Loja', titulo='Teste')])
        def login(fn):
            @wraps(fn)
            def guard(*args, **kwargs):
                return fn(*args, **kwargs) if session.get('usuario_id') else redirect('/login')
            return guard
        register(self.app, login, lambda cid: cid == 1, lambda: contextlib.nullcontext(None),
                 self.query, lambda *args: args[-1])
        self.client = self.app.test_client(); self.path = '/anuncios/1/MLB100/parcelamento'
        with self.client.session_transaction() as s:
            s.update(usuario_id=1, tipo='admin', _csrf='test-token')

    def test_get_post_no_network_no_writes_and_scoped_sql(self):
        with patch('requests.get', side_effect=AssertionError('No remote reads')), \
             patch('requests.post', side_effect=AssertionError('No writes')):
            page = self.client.get(self.path)
            self.assertEqual(page.status_code, 200)
            self.assertNotIn('id="installment-results"', page.text)
            response = self.client.post(self.path, data=form())
            self.assertEqual(response.status_code, 200)
            self.assertIn('R$ 25,00', response.text)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertTrue(all(c.args[1].lstrip().startswith('SELECT') and c.args[2] == (1, 'MLB100')
                            for c in self.query.call_args_list))

    def test_auth_scope_csrf_unknown_and_bad_id(self):
        self.assertEqual(self.app.test_client().get(self.path).status_code, 302)
        with self.client.session_transaction() as s: s['tipo'] = 'cliente'
        self.assertEqual(self.client.get(self.path).status_code, 403)
        with self.client.session_transaction() as s: s['tipo'] = 'admin'
        self.assertEqual(self.client.get(self.path.replace('/1/', '/2/')).status_code, 403)
        self.assertEqual(self.client.get(self.path.replace('MLB100', 'bad')).status_code, 404)
        f = form(); f.pop('_csrf')
        self.assertEqual(self.client.post(self.path, data=f).status_code, 400)
        self.query.assert_not_called()
        self.query.return_value = []
        self.assertEqual(self.client.get(self.path).status_code, 404)

    def test_errors_preserve_form_without_results(self):
        f = form(); f['financing_1'] = '16'
        response = self.client.post(self.path, data=f)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('id="installment-results"', response.text)
        self.assertIn('value="16"', response.text)
