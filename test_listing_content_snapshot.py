import contextlib
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
from unittest.mock import Mock

import requests
from flask import Flask, session, redirect
from web_security import install_security
from listing_content_snapshot import inspect, render, register

NOW = datetime(2026, 10, 26, 20, tzinfo=timezone.utc)


def item():
    return dict(id='MLB123', seller_id=123, site_id='MLB', title='Produto fictício',
                pictures=[dict(id='PHOTO1')], variations=[],
                attributes=[dict(id='BRAND', name='Marca', value_name='Marca fictícia')])


def requester(values=None):
    return Mock(side_effect=[Mock(status_code=200, json=Mock(return_value=v))
        for v in (values if values is not None else [dict(id=123), item(), dict(plain_text='Descrição fictícia')])])


class ContentSnapshotTests(unittest.TestCase):
    def test_three_bounded_gets_with_verified_ownership_and_no_mutation(self):
        values = [dict(id=123), item(), dict(plain_text='Descrição fictícia')]
        before = deepcopy(values); get = requester(values)
        result = inspect('secret-token', 123, 'MLB123', get, NOW)
        self.assertEqual(result['state'], 'read'); self.assertEqual(result['photos'], 1)
        self.assertEqual(result['attribute_count'], 1); self.assertEqual(result['variations'], 0)
        self.assertEqual(result['description'], 'Descrição fictícia'); self.assertEqual(values, before)
        self.assertEqual([c.args[0] for c in get.call_args_list], [
            'https://api.mercadolibre.com/users/me', 'https://api.mercadolibre.com/items/MLB123',
            'https://api.mercadolibre.com/items/MLB123/description'])
        for call in get.call_args_list:
            self.assertEqual(call.kwargs['timeout'], (3, 8)); self.assertFalse(call.kwargs['allow_redirects'])
        self.assertNotIn('secret-token', str(result))

    def test_invalid_identifiers_and_credentials_never_call_remote(self):
        for token, seller, identifier in [(None, 123, 'MLB123'), ('x', True, 'MLB123'),
                ('x', None, 'MLB123'), ('x', 123, '../users/me'), ('x', 123, None)]:
            get = Mock(); self.assertEqual(inspect(token, seller, identifier, get)['state'], 'unknown'); get.assert_not_called()

    def test_account_and_item_ownership_stop_before_content(self):
        for account in (dict(id=124), {}, [], None):
            get = requester([account]); self.assertEqual(inspect('x', 123, 'MLB123', get)['state'], 'unknown')
            self.assertEqual(get.call_count, 1)
        for patch in (dict(id='MLB124'), dict(seller_id=124), dict(site_id='MLA')):
            value = item(); value.update(patch); get = requester([dict(id=123), value])
            self.assertEqual(inspect('x', 123, 'MLB123', get)['state'], 'unknown'); self.assertEqual(get.call_count, 2)

    def test_missing_malformed_fields_do_not_become_empty_or_zero(self):
        for patch in (dict(title=None, pictures=None, attributes=None, variations=None),
                dict(title=4, pictures=[{}], attributes=[{}], variations=[None])):
            value = item(); value.update(patch)
            result = inspect('x', 123, 'MLB123', requester([dict(id=123), value, {}]))
            for key in ('title', 'photos', 'attribute_count', 'attributes', 'variations', 'description'):
                self.assertIsNone(result[key], key)
        value = item(); value.update(title='', pictures=[], attributes=[], variations=[])
        result = inspect('x', 123, 'MLB123', requester([dict(id=123), value, dict(plain_text='')]))
        self.assertEqual(result['photos'], 0); self.assertEqual(result['attributes'], [])
        self.assertEqual(result['description'], ''); self.assertEqual(result['title'], '')

    def test_description_failure_preserves_verified_item_and_is_not_absence(self):
        for status in (301, 401, 403, 404, 429, 500):
            get = requester([dict(id=123), item()])
            get.side_effect = [Mock(status_code=200,json=Mock(return_value=dict(id=123))),
                Mock(status_code=200,json=Mock(return_value=item())), Mock(status_code=status)]
            result = inspect('x',123,'MLB123',get)
            self.assertEqual(result['state'],'read'); self.assertEqual(result['photos'],1)
            self.assertIsNone(result['description']); self.assertTrue(result['description_message'])
            self.assertEqual(get.call_count,3)

    def test_http_and_network_failures_do_not_leak_or_retry(self):
        for error in (requests.Timeout('secret-token'), requests.ConnectionError('secret-token'), ValueError('secret-token')):
            get = Mock(side_effect=error); result = inspect('secret-token',123,'MLB123',get)
            self.assertEqual(result['state'],'unknown'); self.assertNotIn('secret-token',str(result)); self.assertEqual(get.call_count,1)
        for status in (301,401,403,404,429,500):
            get=Mock(return_value=Mock(status_code=status)); result=inspect('secret-token',123,'MLB123',get)
            self.assertEqual(result['state'],'unknown'); self.assertEqual(get.call_count,1)

    def test_large_content_has_explicit_display_limits_and_no_html_execution(self):
        value=item(); value['title']='<script>alert(1)</script>'
        value['attributes']=[dict(id=str(i),name='<img onerror=x>',value_name='<script>x</script>') for i in range(60)]
        result=inspect('secret-token',123,'MLB123',requester([dict(id=123),value,dict(plain_text='<script>'+('x'*13000))]),NOW)
        html=render(1,'MLB123','<script>','csrf',result)
        self.assertNotIn('<script>',html); self.assertNotIn('<img onerror',html); self.assertNotIn('secret-token',html)
        self.assertIn('Exibidos 50 de 60',html); self.assertIn('primeiros 12.000',html); self.assertIn('17:00:00',html)

    def test_missing_and_zero_render_separately_and_no_remote_images(self):
        value=item(); value.update(pictures=[],attributes=[],title='')
        result=inspect('x',123,'MLB123',requester([dict(id=123),value,dict(plain_text='')]),NOW)
        html=render(1,'MLB123','Produto','csrf',result)
        self.assertIn('Descrição vazia na resposta',html); self.assertIn('Título vazio na resposta',html)
        self.assertIn('<strong>0</strong>',html); self.assertNotIn('<img',html)
        blank=render(1,'MLB123','Produto','csrf'); self.assertNotIn('id="content-snapshot-result"',blank)
        result.update(description=None,description_message='indisponível',photos=None)
        html=render(1,'MLB123','Produto','csrf',result)
        self.assertIn('Descrição não verificada',html); self.assertNotIn('Descrição vazia',html)


class ContentSnapshotRouteTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__); self.app.secret_key='isolated'; self.app.testing=True
        install_security(self.app)
        self.query=Mock(return_value=[dict(user_id=123,titulo='Produto',cliente='Loja')])
        self.resolve=Mock(return_value='secret-token'); self.get=requester()
        def login(fn):
            @wraps(fn)
            def guard(*args,**kwargs):
                return fn(*args,**kwargs) if session.get('usuario_id') else redirect('/login')
            return guard
        register(self.app,login,lambda cid:cid==1,lambda:contextlib.nullcontext(None),self.query,
            lambda *a:a[-1],self.resolve,self.get)
        self.client=self.app.test_client(); self.path='/anuncios/1/MLB123/conteudo-atual'
        with self.client.session_transaction() as s:s.update(usuario_id=1,tipo='admin',_csrf='csrf')

    def test_get_does_not_resolve_token_or_consult_api_post_reads_scoped_listing(self):
        self.assertEqual(self.client.get(self.path).status_code,200)
        self.resolve.assert_not_called(); self.get.assert_not_called()
        result=self.client.post(self.path,data=dict(_csrf='csrf'))
        self.assertEqual(result.status_code,200); self.assertEqual(result.headers['Cache-Control'],'no-store')
        self.assertIn('Descrição fictícia',result.text); self.assertNotIn('secret-token',result.text)
        self.assertEqual(self.get.call_count,3)
        for call in self.query.call_args_list:
            self.assertTrue(call.args[1].lstrip().startswith('SELECT')); self.assertEqual(call.args[2],(1,'MLB123'))

    def test_auth_scope_csrf_and_missing_listing_stop_before_token(self):
        self.assertEqual(self.app.test_client().get(self.path).status_code,302)
        with self.client.session_transaction() as s:s['tipo']='cliente'
        self.assertEqual(self.client.post(self.path,data=dict(_csrf='csrf')).status_code,403)
        with self.client.session_transaction() as s:s['tipo']='admin'
        self.assertEqual(self.client.get(self.path.replace('/1/','/2/')).status_code,403)
        self.assertEqual(self.client.get(self.path.replace('MLB123','bad')).status_code,404)
        self.assertEqual(self.client.post(self.path).status_code,400); self.query.assert_not_called()
        self.query.return_value=[]
        self.assertEqual(self.client.post(self.path,data=dict(_csrf='csrf')).status_code,404)
        self.resolve.assert_not_called(); self.get.assert_not_called()
