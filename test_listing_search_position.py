from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock
from urllib.parse import urlencode

from flask import Flask

from listing_search_position import observation, register


class ListingSearchPositionTests(unittest.TestCase):
    path = '/anuncios/7/MLB123/posicao-busca'

    def setUp(self):
        app = Flask(__name__)
        app.secret_key = 'isolated-test'
        self.conn = MagicMock()
        self.query = MagicMock(side_effect=self.read)
        self.execute = MagicMock()
        self.rows = []
        register(app, lambda fn: fn, lambda cid: cid in (7, 8), lambda: self.conn,
                 self.query, self.execute, lambda *a, **kw: a[-1])
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session.update(tipo='admin', usuario_id=11, _csrf='test-csrf')
        self.form = dict(_csrf='test-csrf', submission_key='a'*43, keyword=' Fone   Bluetooth ',
                         result='organic', page='2', slot='3', cep='01234-567', filters='Frete grátis')

    def read(self, conn, sql, args):
        if 'JOIN anuncios' in sql:
            return [dict(cliente='Loja A', titulo='Fone')] if args == (7, 'MLB123') else []
        return self.rows

    def test_save_position_scoped_to_shop_listing_and_actor(self):
        response = self.client.post(self.path, data=self.form)
        self.assertEqual(response.status_code, 303)
        self.assertIn('?q=Fone+Bluetooth#historico', response.location)
        sql, args = self.execute.call_args.args[1:]
        self.assertIn('ON CONFLICT (conexao_id,item_id,submission_key) DO NOTHING', sql)
        self.assertEqual(args, (7, 'MLB123', 'Fone Bluetooth', 'fone bluetooth', '01234567',
                                'Frete grátis', 'organic', 2, 3, 11, 'a'*43))
        self.conn.close.assert_called_once()

    def test_role_csrf_and_cross_store_access_cannot_save(self):
        self.assertEqual(self.client.post(self.path, data=dict(self.form, _csrf='wrong')).status_code, 400)
        self.query.assert_not_called()
        self.assertEqual(self.client.post(self.path.replace('/7/', '/8/'), data=self.form).status_code, 404)
        self.assertEqual(self.client.post(self.path.replace('/7/', '/9/'), data=self.form).status_code, 403)
        with self.client.session_transaction() as session:
            session['tipo'] = 'cliente'
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.execute.assert_not_called()

    def test_invalid_result_never_persisted_and_absence_is_bounded(self):
        for changes in (dict(cep='123'), dict(page='0'), dict(slot='201'), dict(keyword=' '),
                        dict(result='not_seen'), dict(filters='x'*201)):
            with self.subTest(changes=changes):
                response = self.client.post(self.path, data=dict(self.form, **changes))
                self.assertEqual(response.status_code, 400)
                self.assertIn('role="alert"', response.get_data(as_text=True))
        self.execute.assert_not_called()
        self.assertEqual(observation(dict(self.form, result='not_seen', slot=''))[-3:], ('not_seen', 2, None))

    def test_history_filter_pagination_and_escaping(self):
        self.rows = [dict(id=i, keyword='<fone>', cep='', filters='<script>alert(1)</script>',
                          result='sponsored' if i == 40 else 'not_seen', slot=3 if i == 40 else None,
                          page=2, observed_at=datetime(2026, 11, 6, 1, 0, tzinfo=timezone.utc))
                     for i in range(40, 19, -1)]
        response = self.client.get(self.path + '?' + urlencode(dict(q='<fone>', antes=41)))
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.query.call_args.args[-1], (7, 'MLB123', '<fone>', 41, 21))
        self.assertIn('https://lista.mercadolivre.com.br/%3Cfone%3E', html)
        self.assertIn('Página 2 · 3ª posição · Patrocinado', html)
        self.assertIn('Até a página 2 · Não localizado nas páginas conferidas', html)
        self.assertIn('05/11/2026 às 22:00', html)
        self.assertIn('antes=21', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.execute.assert_not_called()
