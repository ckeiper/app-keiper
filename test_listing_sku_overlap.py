import contextlib
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_sku_overlap import load,render,register_overlap
NOW=1793012400

def fixture():return dict(stats=dict(total=5,missing=1),group_total=1,member_total=2,groups=[dict(code='ABC',n=2)],members=[dict(code='ABC',item_id='MLB1',titulo='Produto',status='active',quantidade=0,atualizado_em=NOW)],page=1,pages=1,sku='')
class SkuOverlapTests(unittest.TestCase):
 def test_queries_scope_filter_parameterized_and_bounded(self):
    attack="A' OR 1=1 --"
    q=Mock(side_effect=[[dict(total=20,missing=1)],[dict(n=11,members=22)],[dict(code=attack,n=2)],[]])
    data=load(None,q,7,dict(sku=attack,pagina='999'))
    self.assertEqual(data['page'],2);self.assertEqual(q.call_count,4)
    self.assertNotIn(attack,q.call_args_list[1].args[1]);self.assertEqual(q.call_args_list[1].args[2],(7,attack))
    self.assertIn('LIMIT 10 OFFSET %s',q.call_args_list[2].args[1]);self.assertIn('rn<=10',q.call_args.args[1]);self.assertEqual(q.call_args.args[2],(7,[attack]))
 def test_empty_filter_validation_and_no_extra_member_read(self):
    q=Mock(side_effect=[[dict(total=1,missing=1)],[dict(n=0,members=0)],[]]);data=load(None,q,7,{})
    self.assertEqual(q.call_count,3);self.assertEqual(data['pages'],1)
    with self.assertRaises(ValueError):load(None,Mock(),7,dict(sku='x'*201))
 def test_render_escape_old_stock_limit_and_no_causal_conclusion(self):
    data=fixture();data['groups'][0]['code']='<script>';data['members'][0].update(code='<script>',titulo='<img>')
    text=render(7,data,NOW);self.assertNotIn('<script>',text);self.assertNotIn('<img>',text);self.assertIn('Estoque geral observado: 0',text)
    self.assertIn('não prova de produto equivalente',text)
    data['members'][0]['atualizado_em']=1;data['groups'][0]['n']=20
    text=render(7,data,NOW);self.assertIn('Estoque geral observado: não verificado',text);self.assertIn('primeiros dez anúncios',text)
 def test_admin_scope_and_readonly(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_overlap(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1]);c=app.test_client();path='/anuncios/7/skus-repetidos'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin')
    self.assertEqual(c.get(path.replace('/7/','/8/')).status_code,403);q.assert_not_called()
    q.return_value=[];self.assertEqual(c.get(path).status_code,404)
    q.side_effect=[[dict(cliente='Loja')],[dict(total=0,missing=0)],[dict(n=0,members=0)],[]]
    self.assertEqual(c.get(path).status_code,200);self.assertIn('READ ONLY',e.call_args.args[1]);self.assertEqual(c.post(path).status_code,405)
