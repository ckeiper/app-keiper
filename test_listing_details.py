import ast
import contextlib
import html
import json
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock, patch

import listing_details as details
from listing_sync import sync_promotions, sync_campaign_cache, pages


def attr(value='1500 g', kind='WEIGHT'):
    return {'id': kind, 'value_name': value}


def response(code=200, data=None, headers=None):
    return SimpleNamespace(status_code=code, json=lambda: data, headers=headers or {})


def main_function(name, namespace):
    """Exercise actual production functions without starting DB/scheduler on import."""
    tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), namespace)
    return namespace[name]


class WeightTests(unittest.TestCase):
    def test_attributes_struct_and_raw_trace(self):
        raw = {'id': 'SELLER_PACKAGE_WEIGHT', 'value_struct': {'number': 1250, 'unit': 'g'}}
        result = details.registered_weights({'attributes': [raw]})
        self.assertEqual(details.legacy_weight(result), 1.25)
        self.assertEqual(result['item'][0]['raw'], raw)
        self.assertIn('SELLER_PACKAGE_WEIGHT', details.render_weights(result))

    def test_units_and_invalid_values(self):
        for text, expected in [('1,5 kg', 1.5), ('1500 g', 1.5), ('1000 mg', .001), ('1 lb', .45359237)]:
            with self.subTest(text=text):
                self.assertAlmostEqual(details.legacy_weight(details.registered_weights({'attributes': [attr(text)]})), expected)
        for text in ['100', '5 stone', '-1 kg', '0 kg', 'NaN kg', 'inf kg', '1.000,50 g']:
            self.assertIsNone(details.legacy_weight(details.registered_weights({'attributes': [attr(text)]})))

    def test_dimensions_and_sale_terms(self):
        result = details.registered_weights({'shipping': {'dimensions': '10x20x30,650'}})
        self.assertEqual(details.legacy_weight(result), .65)
        self.assertEqual(details.legacy_weight(details.registered_weights({'sale_terms': [attr('2 kg')]})), 2)
        self.assertEqual(details.render_weights(None), 'Não disponível')

    def test_priority_and_conflicts_preserve_all_sources(self):
        result = details.registered_weights({'attributes': [attr('1 kg'), attr('2 kg', 'SELLER_PACKAGE_WEIGHT')],
                                             'shipping': {'dimensions': '10x10x10,3000'}})
        self.assertEqual(details.legacy_weight(result), 2)
        self.assertEqual(len(result['item']), 3)

    def test_variants_never_averaged_or_blindly_inherited(self):
        result = details.registered_weights({'attributes': [attr('9 kg')], 'variations': [
            {'id': 1, 'attributes': [attr('1 kg')]}, {'id': 2, 'attributes': [attr('2 kg')]}]})
        self.assertIsNone(details.legacy_weight(result))
        self.assertIn('Variação 2: 2 kg', details.render_weights(result))
        result['variations'][1]['weights'] = []
        self.assertIsNone(details.legacy_weight(result))
        result['variations'][0]['weights'] = []
        self.assertEqual(details.legacy_weight(result), 9)

    def test_nested_values_and_html_escaping(self):
        result = details.registered_weights({'attributes': [{'id': 'WEIGHT', 'values': [
            {'struct': {'number': 500, 'unit': 'g'}}]}], 'variations': [{'id': '<script>', 'attributes': []}]})
        self.assertEqual(details.legacy_weight(result), .5)
        self.assertNotIn('<script>', details.render_weights(result))


class PromotionTests(unittest.TestCase):
    def test_status_origin_and_fields(self):
        records = details.normalize_promotions([
            {'id': '1', 'type': 'SELLER_CAMPAIGN', 'status': 'started', 'price': 80, 'original_price': 100},
            {'type': 'SMART', 'status': 'candidate', 'price': 0},
            {'type': 'FUTURE_TYPE', 'status': 'pending'}])
        self.assertEqual(records[0]['discount'], 20)
        self.assertEqual(records[0]['origin'], 'Vendedor')
        self.assertEqual(records[1]['origin'], 'Plataforma/campanha')
        self.assertIsNone(records[1]['price'])
        self.assertEqual(records[2]['origin'], 'Não disponível')
        snap = {'checked_at': time.time(), 'promotions': records}
        self.assertEqual(len(details.active_promotions(snap)), 1)
        self.assertIn('Vigência: Não disponível', details.render_promotions(snap))
        self.assertIn('candidate', details.render_promotions(snap))

    def test_failures_empty_stale_and_current_price(self):
        self.assertIn('Sem promoções', details.render_promotions({'checked_at': time.time(), 'promotions': []}))
        self.assertIn('Não verificado', details.render_promotions(None))
        self.assertEqual(details.active_promotions({'error': 'HTTP 403'}), [])
        self.assertIn('desatualizados', details.render_promotions({'checked_at': 1}))
        # Current/strike-through prices alone never prove an active promotion.
        self.assertEqual(details.active_promotions({'price': 80, 'original_price': 100}), [])
        with self.assertRaises(ValueError):
            details.normalize_promotions({'results': []})

    def test_end_date_and_escape(self):
        records = details.normalize_promotions([{'type': '<script>', 'status': 'started',
                                                 'finish_date': '2000-01-01T00:00:00Z'}])
        snap = {'checked_at': time.time(), 'promotions': records}
        self.assertEqual(details.active_promotions(snap), [])
        self.assertNotIn('<script>', details.render_promotions(snap))


class RequestTests(unittest.TestCase):
    def test_retry_after_and_recovery(self):
        get = Mock(side_effect=[response(429, headers={'Retry-After': '3'}), response(data=[])])
        sleep = Mock()
        self.assertEqual(details.get_json('secret', '/test', {}, get, sleep), ([], None))
        sleep.assert_called_once_with(3)
        self.assertEqual(get.call_count, 2)

    def test_long_retry_after_defers_and_auth_never_retries(self):
        for code, headers in [(429, {'Retry-After': '600'}), (403, {}), (401, {})]:
            get, sleep = Mock(return_value=response(code, headers=headers)), Mock()
            data, error = details.get_json('secret', '/test', {}, get, sleep)
            self.assertIsNone(data)
            self.assertIn(str(code), error)
            self.assertNotIn('secret', error)
            self.assertEqual(get.call_count, 1)
            sleep.assert_not_called()

    def test_network_and_server_retry_bounded(self):
        for failure in [OSError('secret'), None]:
            get = Mock(side_effect=failure) if failure else Mock(return_value=response(503))
            sleep = Mock()
            data, error = details.get_json('secret', '/test', {}, get, sleep)
            self.assertIsNone(data)
            self.assertNotIn('secret', error)
            self.assertEqual(get.call_count, 3)
            self.assertEqual(sleep.call_count, 2)


class SyncTests(unittest.TestCase):
    def setup_sync(self, count=2):
        self.sql, self.errors = [], []
        self.items = [{'item_id': 'MLB' + str(i), 'promocoes_json': json.dumps({'checked_at': 10, 'promotions': []})}
                      for i in range(count)]
        self.banco = lambda: contextlib.nullcontext(object())
        self.consultar = lambda *args: self.items
        self.executar = lambda conn, sql, params=None: self.sql.append((sql, params))
        self.error = lambda *args: self.errors.append(args)

    def test_success_snapshot_and_local_endpoint(self):
        self.setup_sync()
        get = Mock(side_effect=[response(data=[{'id': 'C1', 'type': 'SELLER_CAMPAIGN', 'status': 'started', 'price': 70}]),
                                response(data=[{'id': 'C1', 'type': 'SELLER_CAMPAIGN', 'status': 'candidate'}])])
        self.assertTrue(sync_promotions(1, 'secret', self.banco, self.consultar, self.executar, get, self.error))
        self.assertEqual(get.call_args_list[0].args[0], 'https://api.mercadolibre.com/seller-promotions/items/MLB0')
        self.assertEqual(get.call_args_list[0].kwargs['params'], {'app_version': 'v2'})
        snapshots = [json.loads(params[0]) for sql, params in self.sql if 'UPDATE anuncios' in sql]
        self.assertEqual(len(details.active_promotions(snapshots[0])), 1)
        self.assertEqual(len(details.active_promotions(snapshots[1])), 0)

    def test_campaign_cache_keeps_empty_campaign_and_only_active_items(self):
        self.setup_sync()
        get = Mock(side_effect=[response(data={'results': [{'id': 'C1', 'type': 'SELLER_CAMPAIGN', 'status': 'started'},
                                                           {'id': 'C2', 'type': 'DEAL', 'status': 'pending'}]}),
                               response(data={'results': [{'id': 'MLB1', 'status': 'started', 'price': 80},
                                                           {'id': 'MLB2', 'status': 'candidate'}]}),
                               response(data={'results': []})])
        sync_campaign_cache(1, 'secret', 2, self.banco, self.executar, get)
        self.assertEqual(sum('INSERT INTO promocoes\n' in sql for sql, _ in self.sql), 2)
        self.assertEqual(sum('INSERT INTO promocoes_itens' in sql for sql, _ in self.sql), 1)

    def test_campaign_failure_preserves_all_previous_cache(self):
        self.setup_sync()
        get = Mock(side_effect=[response(data={'results': [{'id': 'C1', 'type': 'DEAL'}]}), response(403)])
        with self.assertRaises(ValueError):
            sync_campaign_cache(1, 'secret', 2, self.banco, self.executar, get)
        self.assertEqual(self.sql, [])

    def test_offset_cursor_and_repeated_pages(self):
        get = Mock(side_effect=[response(data={'results': [{'id': 1}], 'paging': {'searchAfter': 'abc'}}),
                               response(data={'results': [{'id': 2}], 'paging': {'total': 3}}),
                               response(data={'results': [{'id': 3}]})])
        self.assertEqual(len(pages('secret', '/test', {}, get)), 3)
        self.assertEqual(get.call_args_list[1].kwargs['params']['search_after'], 'abc')
        repeated = Mock(return_value=response(data={'results': [{'id': 1}], 'paging': {'total': 3}}))
        with self.assertRaises(ValueError):
            pages('secret', '/test', {}, repeated)

    def test_forbidden_opens_circuit_preserves_cache_and_marks_all_unconfirmed(self):
        self.setup_sync()
        get = Mock(return_value=response(403))
        self.assertFalse(sync_promotions(1, 'secret', self.banco, self.consultar, self.executar, get, self.error))
        self.assertEqual(get.call_count, 1)
        self.assertFalse(any('DELETE FROM promocoes' in sql for sql, _ in self.sql))
        snapshots = [json.loads(params[0]) for sql, params in self.sql if 'UPDATE anuncios' in sql]
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0]['checked_at'], 10)
        self.assertTrue(all(s['error'] for s in snapshots))
        self.assertEqual(len(self.errors), 1)

    def test_individual_failure_does_not_block_other_items(self):
        self.setup_sync()
        get = Mock(side_effect=[response(404), response(data=[])])
        self.assertFalse(sync_promotions(1, 'secret', self.banco, self.consultar, self.executar, get, self.error))
        self.assertEqual(get.call_count, 2)
        snapshots = [json.loads(params[0]) for sql, params in self.sql if 'UPDATE anuncios' in sql]
        self.assertIsNone(snapshots[1]['error'])

    def test_listing_single_upsert_and_weight_not_overwritten(self):
        self.setup_sync(0)
        api = Mock(side_effect=[({'results': ['MLB1'], 'paging': {'total': 1}}, None),
                               ([{'code': 200, 'body': {'id': 'MLB1', 'attributes': [attr('2 kg')]}}], None)])
        namespace = dict(time=time, json=json, banco=self.banco, consultar=self.consultar,
                         executar=self.executar, registrar_erro=self.error, get_json=api,
                         requests=SimpleNamespace(get=Mock()), registered_weights=details.registered_weights,
                         legacy_weight=details.legacy_weight)
        main_function('puxar_anuncios', namespace)(1, 'secret', 2)
        inserts = [params for sql, params in self.sql if 'INSERT INTO anuncios' in sql]
        self.assertEqual(len(inserts), 1)
        self.assertEqual(inserts[0][11], 2)
        self.assertEqual(len(inserts[0]), 15)
        self.assertEqual(api.call_args_list[1].args[2]['include_attributes'], 'all')

    def test_incomplete_search_never_deletes(self):
        self.setup_sync()
        namespace = dict(time=time, banco=self.banco, consultar=self.consultar, executar=self.executar,
                         registrar_erro=self.error, get_json=Mock(return_value=(None, 'HTTP 429')),
                         requests=SimpleNamespace(get=Mock()))
        main_function('puxar_anuncios', namespace)(1, 'secret', 2)
        self.assertEqual(self.sql, [])

    def test_scan_loads_beyond_200_and_handles_null_end(self):
        self.setup_sync(0)
        first = ['MLB' + str(i) for i in range(100)]
        second = ['MLB' + str(i) for i in range(100, 201)]
        calls = []
        def api(token, path, params, request_get):
            calls.append((path, dict(params)))
            if path.endswith('/items/search'):
                page = sum(p.endswith('/items/search') for p, _ in calls)
                return ({'results': first, 'scroll_id': 'a'} if page == 1 else
                        {'results': second, 'scroll_id': 'b'} if page == 2 else {'results': None}), None
            return [{'code': 200, 'body': {'id': item_id}} for item_id in params['ids'].split(',')], None
        namespace = dict(time=time, json=json, banco=self.banco, consultar=self.consultar,
                         executar=self.executar, registrar_erro=self.error, get_json=api,
                         requests=SimpleNamespace(get=Mock()), registered_weights=details.registered_weights,
                         legacy_weight=details.legacy_weight)
        main_function('puxar_anuncios', namespace)(1, 'secret', 2)
        self.assertEqual(sum('INSERT INTO anuncios' in sql for sql, _ in self.sql), 201)
        self.assertEqual(calls[1][1]['scroll_id'], 'a')
        self.assertEqual(calls[2][1]['scroll_id'], 'b')

    def test_view_columns_no_current_price_promotion_and_html(self):
        self.setup_sync()
        row = dict(item_id='MLB1', titulo='Produto <script>', preco=80, original_price=100, quantidade=1,
                   fotos=1, clips=0, status='active', tags='[]', vendidos=1, peso=2,
                   pesos_json=None, promocoes_json=None)
        query = Mock(side_effect=[[{'cliente': 'Loja'}], [row], []])
        namespace = dict(banco=self.banco, consultar=query, pode_ver_loja=lambda cid: True,
                         pagina_loja=lambda *args: args[-1], ultima_atualizacao=lambda cid: None,
                         barra_atualizar=lambda *args: '', esc=html.escape, json=json,
                         render_promotions=details.render_promotions, read_json=details.read_json,
                         active_promotions=details.active_promotions, render_weights=details.render_weights,
                         frete_esperado=lambda *args: 10, TAGS_RUINS=set(), TAGS_BOAS=set())
        output = main_function('anuncios', namespace)(1)
        self.assertIn('<th>Peso cadastrado</th><th>Peso logístico</th>', output)
        self.assertIn('<td>Não disponível</td>', output)
        self.assertNotIn('de R$ 100.00', output)
        self.assertNotIn('<script>', output)
        self.assertEqual(output.count('<th>'), 12)
        self.assertEqual(output.count('<td>'), 12)


if __name__ == '__main__':
    unittest.main()
