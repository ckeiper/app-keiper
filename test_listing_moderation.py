import contextlib
import unittest
from unittest.mock import Mock
import requests
from flask import Flask
from listing_pause_reasons import inspect,render
from listing_moderation import normalize
from listing_reactivation_routes import register_reactivation
from test_listing_pause_reasons import response
from test_listing_reactivation import fixture,DAY


def sample():
    return [dict(name='PAUSED_PREVENTION_PRICE',date_created='2026-11-04 15:57:46.0',
        wordings=[dict(type='REASON',value='Preço incomum <script>alert(1)</script>'),dict(type='REMEDY',value='Confira o preço.')],
        evidences=[dict(section_name='item',text_matched='Preço: 100')])]


class ModerationTests(unittest.TestCase):
    def reader(self,last):
        return Mock(side_effect=[response(dict(id=7)),response(dict(id='MLB1',seller_id=7,site_id='MLB',status='paused',sub_status=[])),last])

    def test_owned_item_only_three_reads_and_escaped_official_text(self):
        get=self.reader(response(sample()));r=inspect('secret',7,'MLB1',get,include_moderation=True)
        self.assertEqual(get.call_count,3)
        self.assertTrue(get.call_args.args[0].endswith('/moderations/last_moderation/MLB1-ITM'))
        self.assertFalse(get.call_args.kwargs['allow_redirects'])
        self.assertEqual(get.call_args.kwargs['timeout'],(3,8))
        html=render('csrf',r)
        self.assertIn('Ação sugerida pelo Mercado Livre',html);self.assertIn('Confira o preço.',html)
        self.assertIn('2026-11-04 15:57:46.0',html);self.assertIn('Preço: 100',html)
        self.assertNotIn('<script>',html);self.assertNotIn('secret',html)

    def test_failure_preserves_status_without_retry_or_false_absence(self):
        for last in (response({},403),response({},404),response({},429),response({},503),response({}),requests.Timeout()):
            get=self.reader(last);r=inspect('token',7,'MLB1',get,include_moderation=True)
            self.assertEqual(get.call_count,3);self.assertEqual(r['status'],'paused')
            self.assertEqual(r['moderation']['state'],'unknown')
            html=render('csrf',r);self.assertIn('Moderação não verificada',html)
            self.assertNotIn('Nenhuma moderação retornada',html)

    def test_empty_and_missing_remedy_do_not_certify_recovery(self):
        r=inspect('token',7,'MLB1',self.reader(response([])),include_moderation=True)
        self.assertIn('não comprova ausência',render('csrf',r))
        data=sample();data[0]['wordings']=data[0]['wordings'][:1]
        r=inspect('token',7,'MLB1',self.reader(response(data)),include_moderation=True)
        self.assertIn('possibilidade de recuperação não foi determinada',render('csrf',r))

    def test_bounds_partial_and_singular_evidence(self):
        data=sample();data[0]['wordings'][0]['value']='x'*3000
        data[0]['evidence']=data[0].pop('evidences')
        data[0]['evidence']*=10
        r=normalize(data*11)
        self.assertTrue(r['limited']);self.assertEqual(len(r['rows']),10)
        self.assertEqual(len(r['rows'][0]['messages'][0]['value']),2000)
        self.assertEqual(len(r['rows'][0]['evidence']),5)
        for malformed in ([None],[{}],[dict(wordings=[1])],[dict(wordings=[dict(type='OTHER',value='x')])],[dict(wordings=[],evidences='x')]):
            self.assertTrue(normalize(malformed)['partial'])

    def test_wrong_account_and_item_stop_before_moderation(self):
        get=Mock(return_value=response(dict(id=8)))
        self.assertEqual(inspect('token',7,'MLB1',get,include_moderation=True)['state'],'unknown');self.assertEqual(get.call_count,1)
        get=Mock(side_effect=[response(dict(id=7)),response(dict(id='MLB1',seller_id=8,site_id='MLB'))])
        self.assertEqual(inspect('token',7,'MLB1',get,include_moderation=True)['state'],'unknown');self.assertEqual(get.call_count,2)

    def test_route_action_csrf_and_connection_scope(self):
        app=Flask(__name__);app.secret_key='test';q=Mock();execute=Mock();get=self.reader(response(sample()))
        register_reactivation(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,execute,lambda *a:a[-1],today=lambda:DAY,resolve_token=lambda s:'token',request_get=get)
        c=app.test_client();path='/anuncios/7/MLB1/reativacao'
        with c.session_transaction() as s:s.update(tipo='admin',usuario_id=1,_csrf='csrf')
        self.assertEqual(c.post(path,data=dict(action='consultar_moderacao',_csrf='bad')).status_code,400);q.assert_not_called();get.assert_not_called()
        q.side_effect=[[fixture()['shop']],[dict(n=0)],[],[],[dict(user_id=7)]]
        r=c.post(path,data=dict(action='consultar_moderacao',_csrf='csrf'))
        self.assertEqual(r.status_code,200);self.assertIn('Confira o preço.',r.get_data(as_text=True))
        self.assertEqual(q.call_args.args[2],(7,'ativa'));self.assertEqual(get.call_count,3)
        self.assertTrue(all('INSERT' not in call.args[1] for call in execute.call_args_list))
        get.reset_mock();q.side_effect=[[fixture()['shop']],[dict(n=0)],[],[],[]]
        self.assertEqual(c.post(path,data=dict(action='consultar_moderacao',_csrf='csrf')).status_code,409);get.assert_not_called()
