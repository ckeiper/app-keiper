import contextlib
import io
import zipfile
from functools import wraps
from unittest import TestCase
from unittest.mock import Mock, patch
from flask import Flask, session, redirect
from title_optimizer_routes import register, render
from title_optimizer_identity import identify
from listing_content_snapshot import ContentUnavailable


class TitleOptimizerRoutes(TestCase):
    def setUp(self):
        self.app = Flask(__name__); self.app.secret_key = 'test'; self.app.testing = True
        self.query = Mock(return_value=[]); self.get = Mock(); self.resolve = Mock(return_value='secret')
        def login(fn):
            @wraps(fn)
            def guard(*args, **kw):
                return fn(*args, **kw) if session.get('usuario_id') else redirect('/login')
            return guard
        register(self.app, login, lambda cid: cid == 1, lambda: contextlib.nullcontext(None), self.query,
                 lambda title, body: body, lambda title, cid, shop, active, body: body, self.resolve, self.get)
        self.client = self.app.test_client()
        with self.client.session_transaction() as state:
            state.update(usuario_id=1, _csrf='csrf')

    def test_manual_clients_need_no_store_or_api(self):
        self.assertEqual(self.app.test_client().get('/otimizador-titulos').status_code, 302)
        response = self.client.get('/otimizador-titulos')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Título original', response.text)
        self.query.assert_not_called(); self.get.assert_not_called(); self.resolve.assert_not_called()

    def test_render_escapes_title_without_recursive_substitution(self):
        html = render('<script>bad</script>{{lookup}}', '<b>trusted</b>')
        self.assertIn('&lt;script&gt;bad&lt;/script&gt;{{lookup}}', html)
        self.assertEqual(html.count('<b>trusted</b>'), 1)

    def test_scope_csrf_and_input_validation_before_database(self):
        path = '/otimizador-titulos/1/identificar'
        self.assertEqual(self.client.post(path.replace('/1/', '/2/'), json={'item':'MLB123'}).status_code, 403)
        self.assertEqual(self.client.post(path, json={'item':'MLB123'}).status_code, 400)
        self.assertEqual(self.client.post(path, json={'item':'../users'}, headers={'X-CSRF-Token':'csrf'}).status_code, 400)
        self.query.assert_not_called(); self.get.assert_not_called(); self.resolve.assert_not_called()

    def test_foreign_listing_is_not_read(self):
        response = self.client.post('/otimizador-titulos/1/identificar', json={'item':'MLB123'}, headers={'X-CSRF-Token':'csrf'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.query.call_args.args[2], (1, 'MLB123'))
        self.get.assert_not_called(); self.resolve.assert_not_called()

    def test_identification_has_only_selects_and_safe_response(self):
        self.query.return_value = [dict(user_id=12)]
        with patch('title_optimizer_routes.identify', return_value=dict(product='Produto', brand='Marca')) as identify_mock:
            response = self.client.post('/otimizador-titulos/1/identificar', json={'item':'MLB123'}, headers={'X-CSRF-Token':'csrf'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('secret', response.text)
        identify_mock.assert_called_once_with('secret', 12, 'MLB123', self.get)
        self.assertTrue(self.query.call_args.args[1].startswith('SELECT'))

    def test_unavailable_api_is_reported_without_fabricated_metadata(self):
        self.query.return_value = [dict(user_id=12)]
        with patch('title_optimizer_routes.identify', side_effect=ContentUnavailable('Indisponível')):
            response = self.client.post('/otimizador-titulos/1/identificar', json={'item':'MLB123'}, headers={'X-CSRF-Token':'csrf'})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json, dict(error='Indisponível'))

    def test_store_get_is_read_only_and_options_escaped(self):
        self.query.side_effect = [[dict(cliente='Loja')], [dict(item_id='MLB123', titulo='<img src=x>')]]
        response = self.client.get('/otimizador-titulos/1')
        self.assertEqual(response.status_code, 200)
        self.assertIn('&lt;img src=x&gt;', response.text)
        self.get.assert_not_called(); self.resolve.assert_not_called()
        self.assertTrue(all(call.args[1].lstrip().startswith('SELECT') for call in self.query.call_args_list))

    def test_extension_download_is_authenticated_and_complete(self):
        self.assertEqual(self.app.test_client().get('/otimizador-titulos/extensao.zip').status_code, 302)
        response = self.client.get('/otimizador-titulos/extensao.zip')
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(set(archive.namelist()), {'manifest.json','dashboard.js','search.js','collector.js','README.md'})
            self.assertIn(b'0.2.0', archive.read('manifest.json'))


class TitleIdentity(TestCase):
    def item(self, **changes):
        return dict(title='Kit 2 Travesseiros Fibrasca Grafeno', category_id='MLB123', catalog_listing=False,
                    attributes=[dict(id='BRAND',value_name='Fibrasca'),dict(id='MODEL',value_name='Grafeno')], **changes)

    def test_brand_and_model_come_from_attributes_and_category_is_checked(self):
        with patch('title_optimizer_identity.owned', return_value=self.item()), patch('title_optimizer_identity.read', return_value=[dict(id='MODEL',tags={},value_type='string',value_max_length=60)]):
            data = identify('token', 12, 'MLB123', Mock())
        self.assertEqual((data['product'],data['brand'],data['model']), ('Kit 2 Travesseiros','Fibrasca','Grafeno'))
        self.assertEqual(data['model_policy']['state'], 'review')

    def test_catalog_suppresses_category_and_model_suggestions(self):
        item = self.item(); item['catalog_listing'] = True
        with patch('title_optimizer_identity.owned', return_value=item), patch('title_optimizer_identity.read') as read:
            data = identify('token', 12, 'MLB123', Mock())
        self.assertEqual(data['model_policy']['state'], 'blocked'); read.assert_not_called()

    def test_category_constraints_and_failures_remain_explicit(self):
        for rule in [dict(id='MODEL',tags={'read_only':True},value_type='string'),dict(id='MODEL',tags={},value_type='list'),None]:
            with self.subTest(rule=rule), patch('title_optimizer_identity.owned', return_value=self.item()), patch('title_optimizer_identity.read',return_value=[rule] if rule else []):
                self.assertEqual(identify('token',12,'MLB123',Mock())['model_policy']['state'],'blocked')
        with patch('title_optimizer_identity.owned',return_value=self.item()),patch('title_optimizer_identity.read',side_effect=ContentUnavailable('Indisponível')):
            self.assertEqual(identify('token',12,'MLB123',Mock())['model_policy']['state'],'unknown')
