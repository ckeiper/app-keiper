import contextlib
from datetime import date
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_review_report import load,render,register_report

def fixture():return dict(shop=dict(cliente='Loja',item_id='MLB1',titulo='Produto',quantidade=0,atualizado_em=123,fotos=None,clips=None),reviews={},counts=[],tasks=[],tasks_limited=False,questions=[])
class ReviewReportTests(unittest.TestCase):
 def test_queries_scoped_bounded_and_missing_listing(self):
    q=Mock(side_effect=[[fixture()['shop']],[],[],[],[]]);data=load(None,q,7,'MLB1')
    self.assertEqual(data['tasks'],[])
    for c in q.call_args_list:self.assertEqual(c.args[2],(7,'MLB1'))
    self.assertIn('LIMIT 11',q.call_args_list[3].args[1])
    q=Mock(return_value=[]);self.assertIsNone(load(None,q,7,'MLB1'));self.assertEqual(q.call_count,1)
 def test_escaping_missing_values_and_print_controls(self):
    d=fixture();d['shop']['titulo']='<script>';text=render(7,'MLB1',d,123)
    self.assertNotIn('<script>',text);self.assertIn('Estoque observado: 0',text)
    self.assertIn('clips: não verificados',text);self.assertEqual(text.count('Sem revisão registrada.'),8)
    self.assertIn('window.print()',text);self.assertIn('@page{size:A4',text)
    text=render(7,'MLB1',d,123+21601);self.assertIn('Estoque observado: não verificado',text)
    d['tasks_limited']=True;self.assertIn('primeiras dez tarefas',render(7,'MLB1',d,123))
 def test_admin_scope_readonly_and_method(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_report(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e);c=app.test_client();path='/anuncios/7/MLB1/relatorio-revisao'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin')
    self.assertEqual(c.get('/anuncios/8/MLB1/relatorio-revisao').status_code,403);q.assert_not_called()
    q.return_value=[];self.assertEqual(c.get(path).status_code,404)
    q.side_effect=[[fixture()['shop']],[],[],[],[]];self.assertEqual(c.get(path).status_code,200)
    self.assertIn('READ ONLY',e.call_args.args[1]);self.assertEqual(c.post(path).status_code,405)
