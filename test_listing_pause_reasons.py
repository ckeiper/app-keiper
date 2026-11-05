import contextlib
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_pause_reasons import inspect, render
from listing_reactivation_routes import register_reactivation
from test_listing_reactivation import fixture, DAY


def response(data, status=200):
    return Mock(status_code=status, json=Mock(return_value=data))


class PauseReasonTests(unittest.TestCase):
    def reader(self, codes, **kwargs):
        item=dict(id='MLB1', seller_id=7, site_id='MLB', status='paused', sub_status=codes)
        item.update(kwargs)
        return Mock(side_effect=[response(dict(id=7)), response(item)])

    def test_bounded_authenticated_read_and_escaping(self):
        get=self.reader(['out_of_stock', '<script>', 'out_of_stock'])
        result=inspect('secret', 7, 'MLB1', get)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(result['codes'], ['out_of_stock','<script>'])
        for call in get.call_args_list:
            self.assertEqual(call.kwargs['headers'], {'Authorization':'Bearer secret'})
            self.assertFalse(call.kwargs['allow_redirects'])
        html=render('csrf',result)
        self.assertIn('Falta de estoque',html)
        self.assertNotIn('<script>',html)
        self.assertNotIn('secret',html)
        self.assertIn('Código sem interpretação local',html)

    def test_absent_malformed_and_empty_are_distinct(self):
        for codes in (None, 'out_of_stock', [1], ['x'*201], ['a']*101):
            self.assertIsNone(inspect('token',7,'MLB1',self.reader(codes))['codes'])
        result=inspect('token',7,'MLB1',self.reader([]))
        self.assertEqual(result['codes'],[])
        self.assertIn('não comprova ausência', render('csrf',result))

    def test_wrong_account_stops_before_item_and_failure_stops(self):
        for first in (response(dict(id=8)),response({},429),response({},503)):
            get=Mock(return_value=first)
            self.assertEqual(inspect('token',7,'MLB1',get)['state'],'unknown')
            self.assertEqual(get.call_count,1)
        for values in (dict(seller_id=8),dict(id='MLB2'),dict(site_id='MLA')):
            self.assertEqual(inspect('token',7,'MLB1',self.reader([],**values))['state'],'unknown')

    def test_invalid_inputs_do_not_call_api(self):
        get=Mock()
        for token,seller,item in [('',7,'MLB1'),('token',True,'MLB1'),('token',7,'../1')]:
            self.assertEqual(inspect(token,seller,item,get)['state'],'unknown')
        get.assert_not_called()

    def test_route_explicit_post_csrf_scope_and_no_task_creation(self):
        app=Flask(__name__);app.secret_key='test'
        q=Mock();execute=Mock();get=self.reader(['paused_by_seller']);resolve=Mock(return_value='token')
        register_reactivation(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,execute,lambda *a:a[-1],today=lambda:DAY,resolve_token=resolve,request_get=get)
        c=app.test_client();path='/anuncios/7/MLB1/reativacao'
        with c.session_transaction() as s:s.update(tipo='admin',usuario_id=1,_csrf='csrf')
        self.assertEqual(c.post(path,data=dict(action='consultar_motivos',_csrf='bad')).status_code,400)
        q.assert_not_called();get.assert_not_called()
        q.side_effect=[[fixture()['shop']],[dict(n=0)],[],[]]
        self.assertEqual(c.get(path).status_code,200);get.assert_not_called();resolve.assert_not_called()
        q.side_effect=[[fixture()['shop']],[dict(n=0)],[],[],[dict(user_id=7)]]
        result=c.post(path,data=dict(action='consultar_motivos',_csrf='csrf'))
        self.assertEqual(result.status_code,200);self.assertIn('Pausa pelo vendedor',result.get_data(as_text=True))
        self.assertTrue(all('INSERT' not in call.args[1] for call in execute.call_args_list))
        self.assertEqual(c.post(path.replace('/7/','/8/'),data=dict(action='consultar_motivos',_csrf='csrf')).status_code,403)
