import contextlib
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_sku_variations import load, render, register
NOW = 1793337000


def fixture():
    return dict(stats=dict(total=8, read=5, partial=1), total=1,
                groups=[dict(code='ABC', n=2, occurrences=3)],
                members=[dict(code='ABC', item_id='MLB123', titulo='Produto', collected_at=str(NOW), coverage='partial', variations=['principal', '12'], occurrences=2)],
                page=1, pages=1, sku='')


class OfficialSkuViewTests(unittest.TestCase):
    def test_queries_scope_exact_filter_and_limits(self):
        attack = "A' OR 1=1 --"
        query = Mock(side_effect=[[dict(total=1, read=1, partial=0)], [dict(n=11)], [dict(code=attack, n=2, occurrences=3)], []])
        result = load(None, query, 7, dict(sku=attack, pagina=999))
        self.assertEqual(result['page'], 2)
        self.assertNotIn(attack, query.call_args_list[1].args[1])
        self.assertEqual(query.call_args_list[1].args[2], (7, attack))
        self.assertIn('COUNT(DISTINCT item_id)>1', query.call_args_list[1].args[1])
        self.assertEqual(query.call_args.args[2], (7, [attack]))
        self.assertIn('rn<=10', query.call_args.args[1])
        self.assertIn('[1:10]', query.call_args.args[1])

    def test_empty_and_filter_validation(self):
        query = Mock(side_effect=[[dict(total=1, read=0, partial=0)], [dict(n=0)], []])
        result = load(None, query, 7, {})
        self.assertEqual(query.call_count, 3)
        self.assertEqual(result['pages'], 1)
        for sku in ('x'*201, 'A\x00'):
            with self.assertRaises(ValueError):
                load(None, Mock(), 7, dict(sku=sku))

    def test_fresh_partial_unknown_and_escaped_content(self):
        data = fixture()
        data['groups'][0]['code'] = '<script>'
        data['members'][0].update(code='<script>', titulo='<img>')
        text = render(7, data, NOW)
        self.assertNotIn('<script>', text)
        self.assertNotIn('<img>', text)
        self.assertIn('variação 12', text)
        self.assertIn('cobertura parcial', text)
        self.assertIn('Sem leitura verificável: 2', text)
        self.assertIn('não prova de produto equivalente', text)
        data['members'][0]['collected_at'] = 'invalid'
        data['members'][0]['occurrences'] = 11
        text = render(7, data, NOW)
        self.assertIn('atualidade não verificada', text)
        self.assertIn('dez de 11', text)

    def test_role_shop_readonly_and_no_post(self):
        app = Flask(__name__)
        app.secret_key = 'isolated'
        query = Mock()
        execute = Mock()
        register(app, lambda f:f, lambda cid:cid==7, lambda:contextlib.nullcontext(None), query, execute, lambda *a:a[-1])
        client = app.test_client()
        path = '/anuncios/7/skus-variacoes'
        self.assertEqual(client.get(path).status_code, 403)
        with client.session_transaction() as session:
            session['tipo'] = 'admin'
        self.assertEqual(client.get(path.replace('/7/', '/8/')).status_code, 403)
        query.assert_not_called()
        query.return_value = []
        self.assertEqual(client.get(path).status_code, 404)
        self.assertIn('READ ONLY', execute.call_args.args[1])
        self.assertEqual(client.post(path).status_code, 405)
