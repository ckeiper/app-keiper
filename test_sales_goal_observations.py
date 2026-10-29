import contextlib,unittest
from unittest.mock import Mock,patch
from datetime import datetime,timedelta
from decimal import Decimal
from flask import Flask
from sales_goal_observations import collect,load,render,register_history
from test_listing_sales_goals import goal,DAY
from sales_metrics import SAO_PAULO
NOW=int(datetime(2026,10,29,12,tzinfo=SAO_PAULO).timestamp())
class SalesGoalObservationTests(unittest.TestCase):
 def test_collection_scoped_closed_period_idempotent_insert(self):
    g=goal(item_id='MLB1');q=Mock(return_value=[g]);e=Mock()
    with patch('sales_goal_observations.load_sales',return_value=dict(units=0,fingerprint='a'*64)) as source:
        self.assertTrue(collect(7,lambda:contextlib.nullcontext(None),q,e,NOW))
    self.assertEqual(source.call_args.args[2:],(7,'MLB1',g['start_date'],g['end_date']))
    self.assertEqual(e.call_args.args[2][2:4],(Decimal(0),'alert'));self.assertIn('ON CONFLICT',e.call_args.args[1]);self.assertIn('cancelled_at IS NULL',e.call_args.args[1]);self.assertEqual(q.call_args.args[2][0],7)
 def test_unknown_preserves_null_and_keyset_pagination(self):
    rows=[goal(id=i,item_id='MLB1') for i in range(1,101)];q=Mock(side_effect=[rows,[]]);e=Mock()
    with patch('sales_goal_observations.load_sales',return_value=dict(units=None,fingerprint='b'*64)):
        collect(7,lambda:contextlib.nullcontext(None),q,e,NOW)
    inserts=[c for c in e.call_args_list if 'INSERT' in c.args[1]]
    self.assertEqual(len(inserts),100);self.assertEqual(inserts[0].args[2][2:4],(None,'unknown'));self.assertEqual(q.call_args.args[2][1],100)
 def test_history_scope_pagination_escape_unknown(self):
    g=goal(responsible='<script>');q=Mock(side_effect=[[g],[dict(n=21)],[dict(state='unknown',value=None,evaluated_at=NOW,cutoff=DAY-timedelta(days=1))]])
    data=load(None,q,7,'MLB1',1,dict(pagina='999'));self.assertEqual(data['page'],3);self.assertEqual(q.call_args.args[2],(1,7,'MLB1',20))
    text=render(7,'MLB1',data);self.assertNotIn('<script>',text);self.assertIn('Apurado: não verificado',text);self.assertIn('pagina=2',text)
    with self.assertRaises(LookupError):load(None,Mock(return_value=[]),8,'MLB1',1,{})
 def test_history_admin_scope_readonly_no_writes(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_history(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1]);c=app.test_client();path='/anuncios/7/MLB1/metas-vendas/historico/1'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s['tipo']='admin'
    self.assertEqual(c.get(path.replace('/7/','/8/')).status_code,403)
    q.side_effect=[[dict(cliente='Loja')],[goal()],[dict(n=0)],[]];self.assertEqual(c.get(path).status_code,200);self.assertIn('READ ONLY',e.call_args.args[1]);self.assertEqual(e.call_count,1)
