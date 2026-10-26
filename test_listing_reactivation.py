import contextlib
from datetime import date
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_reactivation import load,render,TITLE
from listing_reactivation_routes import register_reactivation
DAY=date(2026,10,26);NOW=1793012400

def fixture():return dict(shop=dict(cliente='Loja',item_id='MLB1',titulo='Produto',status='paused',quantidade=0,atualizado_em=NOW),tasks=[],total=0,page=1,pages=1,events=[],events_limited=False)
class ReactivationTests(unittest.TestCase):
 def test_scoped_bounded_reads(self):
    q=Mock(side_effect=[[fixture()['shop']],[dict(n=15)],[],[]]);d=load(None,q,7,'MLB1',dict(pagina='999'))
    self.assertEqual(d['page'],2);self.assertIn('LIMIT 10 OFFSET',q.call_args_list[2].args[1]);self.assertIn('LIMIT 11',q.call_args.args[1])
    for c in q.call_args_list:self.assertEqual(c.args[2][:2],(7,'MLB1'))
    self.assertEqual(q.call_args_list[2].args[2][-1],10)
 def test_status_stale_zero_and_no_eligibility_claim(self):
    d=fixture();text=render(7,'MLB1',d,DAY,NOW,'token')
    self.assertIn('Status observado: Pausado',text);self.assertIn('Estoque geral observado: 0',text)
    self.assertIn('nem prova que a oferta está elegível',text);self.assertNotIn('checked',text)
    d['shop']['atualizado_em']=1;text=render(7,'MLB1',d,DAY,NOW,'token')
    self.assertIn('Status observado: Não verificado',text);self.assertIn('Estoque geral observado: não verificado',text)
 def test_escape_and_observed_history_and_task_independence(self):
    d=fixture();d['shop']['titulo']='<script>';d['shop']['status']='active'
    d['events']=[dict(before_value='paused',after_value='active',previous_at=NOW-100,observed_at=NOW)]
    text=render(7,'MLB1',d,DAY,NOW,'token')
    self.assertNotIn('<script>',text);self.assertIn('Pausado → Ativo',text);self.assertIn('não indica anúncio pausado',text)
    self.assertIn('não identificam autor, motivo',text)
 def test_route_roles_csrf_scope(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_reactivation(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1],today=lambda:DAY);c=app.test_client();path='/anuncios/7/MLB1/reativacao'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin',usuario_id=1,_csrf='token')
    self.assertEqual(c.get(path.replace('/7/','/8/')).status_code,403)
    self.assertEqual(c.post(path,data={}).status_code,400);q.assert_not_called()
    q.return_value=[];self.assertEqual(c.get(path).status_code,404)
    q.side_effect=[[fixture()['shop']],[dict(n=0)],[],[]];self.assertEqual(c.get(path).status_code,200);self.assertIn('READ ONLY',e.call_args.args[1])
