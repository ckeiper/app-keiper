import contextlib
import datetime
import json
import unittest
from unittest.mock import Mock
from flask import Flask
from sales_geography import destination,summarize,sync,init_schema
from sales_geography_view import register,render,paths

DAY=datetime.date(2026,10,28)
def shipment(uf='SP',seller=9):return dict(type='forward',status='delivered',sender_id=seller,receiver_address=dict(country=dict(id='BR'),state=dict(id='BR-'+uf)))
def row(oid='1',**kw):
    r=dict(pedido_id=oid,status='paid',total=100,moeda='BRL',criado_em='2026-10-28T15:00:00-03:00',pagamentos_json=[dict(status='approved')],unidades=2,uf='SP');r.update(kw);return r

class SalesGeographyTests(unittest.TestCase):
 def test_ufs_only_with_seller_and_country_and_forward(self):
    self.assertEqual(destination([shipment()],9),('SP','confirmado'))
    for payload in ([],None,{},[shipment(seller=10)],[shipment('XX')],[dict(shipment(),type='return')],[dict(shipment(),destination='bad')]):
        self.assertIsNone(destination(payload,9)[0])
    self.assertIsNone(destination([shipment(),shipment('RJ')],9)[0])
    self.assertEqual(destination([shipment(),shipment()],9)[0],'SP')
    s=shipment();s['destination']=dict(shipping_address=s.pop('receiver_address'));self.assertEqual(destination([s],9)[0],'SP')
    s['destination']['shipping_address']['country']['id']='AR';self.assertIsNone(destination([s],9)[0])
 def test_totals_unknown_and_deduplication(self):
    r=summarize([row(),row(),row('2',uf=None,total=50),row('3',status='cancelled'),row('4',moeda='USD'),row('5',criado_em=None)],DAY,DAY,{DAY.isoformat()})
    self.assertEqual((r['total'],r['known'],r['missing']['orders'],r['revenue']),(2,1,1,150))
    self.assertEqual((r['invalid'],r['unlocated']),(1,1))
    self.assertEqual(r['states']['SP']['orders'],1)
 def test_partial_coverage_no_fake_zero_and_invalid_payments(self):
    r=summarize([row(pagamentos_json=[]),row('2',total=float('nan')),row('3',unidades=None)],DAY,DAY,set())
    self.assertEqual(r['invalid'],2);self.assertEqual(r['covered'],0);self.assertEqual(r['states']['SP']['unknown_units'],1)
    text=render(7,{},DAY,DAY,r);self.assertIn('Base parcial',text);self.assertIn('Destino não identificado',text)
    self.assertEqual(len(paths()),27);self.assertEqual(text.count("class='sg-state'"),27)
 def test_collector_account_budget_scope_headers_no_pii(self):
    q=Mock(return_value=[dict(pedido_id='123')]);e=Mock()
    get=Mock(side_effect=[Mock(status_code=200,json=lambda:dict(id=9)),Mock(status_code=200,json=lambda:[shipment()])])
    self.assertTrue(sync(7,'secret',9,lambda:contextlib.nullcontext(None),q,e,get,now=100000))
    self.assertEqual(q.call_args.args[2],(7,100000));self.assertIn('LIMIT 8',q.call_args.args[1])
    self.assertEqual(get.call_args.kwargs['params'],{'views':'destination'})
    self.assertEqual(get.call_args.kwargs['headers']['X-New-Domain'],'true');self.assertFalse(get.call_args.kwargs['allow_redirects'])
    self.assertEqual(e.call_args.args[2],(7,'123','SP','confirmado',100000,100000))
    self.assertNotIn('receiver',str(e.call_args));self.assertNotIn('secret',str(e.call_args))
 def test_account_mismatch_and_rate_limit(self):
    q=Mock(return_value=[dict(pedido_id='1'),dict(pedido_id='2')]);e=Mock()
    get=Mock(return_value=Mock(status_code=200,json=lambda:dict(id=10)))
    self.assertFalse(sync(7,'x',9,lambda:contextlib.nullcontext(None),q,e,get));q.assert_not_called()
    get=Mock(side_effect=[Mock(status_code=200,json=lambda:dict(id=9)),Mock(status_code=429)])
    sync(7,'x',9,lambda:contextlib.nullcontext(None),q,e,get,now=100000)
    self.assertEqual(get.call_count,2);self.assertIsNone(e.call_args.args[2][2])
 def test_get_route_authorization_period_and_read_only(self):
    app=Flask(__name__);q=Mock()
    register(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,lambda *a:a[-1]);c=app.test_client()
    self.assertEqual(c.get('/vendas/8/estados').status_code,403);q.assert_not_called()
    self.assertEqual(c.get('/vendas/7/estados?periodo=bad').status_code,400)
    q.side_effect=[[dict(cliente='<script>')],[row()],[dict(dia=DAY.isoformat())]]
    response=c.get('/vendas/7/estados?periodo=personalizado&inicio=2026-10-28&fim=2026-10-28');self.assertEqual(response.status_code,200)
    for call in q.call_args_list:self.assertEqual(call.args[2],(7,))
    self.assertEqual(c.post('/vendas/7/estados').status_code,405)
 def test_schema_is_additive(self):
    e=Mock();init_schema(None,e);self.assertNotIn('DROP',e.call_args.args[1]);self.assertIn('PRIMARY KEY(conexao_id,pedido_id)',e.call_args.args[1])
