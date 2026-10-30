import contextlib
from datetime import datetime
import unittest
from unittest.mock import Mock
from flask import Flask
from goal_observations import collect,load,render,register_history
from test_listing_goals import goal,shop,DAY,NOW
from sales_metrics import SAO_PAULO

class GoalObservationTests(unittest.TestCase):
 def test_collection_records_valid_zero_and_unknown_without_http(self):
    rows=[dict(goal(),**{k:v for k,v in shop(quantidade=0).items() if k not in goal()})]
    rows.append(dict(rows[0],id=2,atualizado_em=1))
    q=Mock(return_value=rows);e=Mock()
    self.assertTrue(collect(7,lambda:contextlib.nullcontext(None),q,e,NOW))
    self.assertEqual(e.call_count,2)
    self.assertEqual(e.call_args_list[0].args[2][:4],(NOW,NOW,0,'alert'))
    self.assertEqual(e.call_args_list[1].args[2][:4],(NOW,1,None,'unknown'))
    self.assertIn('ON CONFLICT(goal_id,evaluated_at) DO NOTHING',e.call_args.args[1])
    self.assertIn('cancelled_at IS NULL',e.call_args.args[1]);self.assertIn('created_at<=%s',e.call_args.args[1])
 def test_batches_keyset_and_empty_no_write(self):
    q=Mock(side_effect=[[dict(goal(id=i),**{k:v for k,v in shop().items() if k not in goal()}) for i in range(1,201)],[]]);e=Mock()
    collect(7,lambda:contextlib.nullcontext(None),q,e,NOW)
    self.assertEqual(q.call_count,2);self.assertEqual(q.call_args.args[2][1],200);self.assertEqual(e.call_count,200)
 def test_scoped_history_pagination_and_render_unknown(self):
    row=dict(evaluated_at=NOW,source_at=1,stock=None,state='unknown')
    q=Mock(side_effect=[[goal()],[dict(n=23)],[row]])
    data=load(None,q,7,'MLB1',1,dict(pagina='999'));self.assertEqual(data['page'],3)
    self.assertEqual(q.call_args.args[2],(1,7,'MLB1',20))
    text=render(7,'MLB1',data);self.assertIn('não verificado',text);self.assertNotIn('Estoque observado: 0',text)
    with self.assertRaises(LookupError):load(None,Mock(return_value=[]),7,'MLB1',99,{})
 def test_route_roles_readonly_and_no_mutation(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_history(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1]);c=app.test_client();path='/anuncios/7/MLB1/metas/historico/1'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin')
    self.assertEqual(c.get(path.replace('/7/','/8/')).status_code,403);q.assert_not_called()
    q.side_effect=[[dict(cliente='Loja')],[goal()],[dict(n=0)],[]]
    self.assertEqual(c.get(path).status_code,200);self.assertIn('READ ONLY',e.call_args.args[1]);self.assertEqual(c.post(path).status_code,405)
