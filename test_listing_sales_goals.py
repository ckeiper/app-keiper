import contextlib
from datetime import date,timedelta
from decimal import Decimal
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_sales_goals import validate,create,cancel,evaluate,evaluate_current
from listing_sales_goal_routes import register_sales_goals
from listing_sales_goal_view import render
DAY=date(2026,10,29)
def form(**kw):
    return dict(dict(metric='units',target='10',start_date='2026-10-20',end_date='2026-10-28',responsible='Equipe',submission_key='k'*32),**kw)
def goal(**kw):return dict(dict(validate(form(),DAY),id=1,created_by=1,cancelled_at=None),**kw)
class SalesGoalTests(unittest.TestCase):
 def test_validation_integer_money_and_ranges(self):
    self.assertEqual(validate(form(metric='gross_items',target='15,32'),DAY)['target'],Decimal('15.32'))
    for kw in [dict(metric='profit'),dict(target='0'),dict(target='NaN'),dict(target='Infinity'),dict(target='1.5'),dict(target='-2'),dict(target='1000000001'),dict(target='1e3'),dict(target='2.001'),dict(responsible=''),dict(submission_key='bad'),dict(end_date='2027-10-29')]:
        with self.subTest(kw=kw),self.assertRaises(ValueError):validate(form(**kw),DAY)
 def test_closed_days_deadline_unknown_and_zero(self):
    g=goal()
    self.assertEqual(evaluate(g,{'units':0},DAY)[0],'alert')
    self.assertEqual(evaluate(g,{},DAY)[0],'unknown')
    self.assertEqual(evaluate(g,{'units':10},DAY)[0],'met')
    self.assertEqual(evaluate(goal(end_date=DAY),{'units':0},DAY)[0],'progress')
    self.assertEqual(evaluate(goal(start_date=DAY,end_date=DAY),{},DAY)[0],'waiting')
    self.assertEqual(evaluate(goal(start_date=DAY+timedelta(days=1)),{},DAY)[0],'scheduled')
    self.assertEqual(evaluate(goal(cancelled_at=1),{'units':0},DAY)[0],'cancelled')
    for val in ('NaN','Infinity',-1):self.assertEqual(evaluate(g,{'units':val},DAY)[0],'unknown')
    self.assertEqual(evaluate(goal(end_date=DAY),{'units':0},DAY)[3],DAY-timedelta(days=1))
 def test_idempotent_scope_cancel(self):
    v=validate(form(),DAY);q=Mock(return_value=[dict(id=2)])
    self.assertEqual(create(None,q,7,'MLB1',v,1),2)
    self.assertEqual(q.call_args.args[2][:4],(7,'MLB1','units',Decimal(10)))
    self.assertEqual(create(None,Mock(side_effect=[[],[dict(v,id=2)]]),7,'MLB1',v,1),2)
    with self.assertRaises(ValueError):create(None,Mock(side_effect=[[],[dict(v,id=2,target=11)]]),7,'MLB1',v,1)
    cancel(None,q,7,'MLB1',2,1);self.assertEqual(q.call_args.args[2][1:],(1,2,7,'MLB1'))
 def test_no_sales_read_for_cancelled_or_future(self):
    q=Mock();evaluate_current(None,q,7,'MLB1',goal(cancelled_at=1),DAY);q.assert_not_called()
 def test_auth_csrf_readonly_escape(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_sales_goals(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1],today=lambda:DAY)
    c=app.test_client();path='/anuncios/7/MLB1/metas-vendas'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin',usuario_id=1,_csrf='token')
    self.assertEqual(c.get(path.replace('/7/','/8/')).status_code,403)
    self.assertEqual(c.post(path,data=form()).status_code,400);q.assert_not_called()
    q.side_effect=[[dict(cliente='Loja',titulo='<script>')],[dict(n=0)],[]]
    result=c.get(path);self.assertEqual(result.status_code,200);self.assertIn('READ ONLY',e.call_args.args[1]);self.assertNotIn('<script>',result.text)
 def test_view_does_not_display_unknown_as_zero(self):
    g=goal();model=dict(rows=[g],page=1,pages=1,total=1,evaluations={1:evaluate(g,{},DAY)})
    text=render(7,'MLB1',dict(titulo='Produto'),model,DAY,0,'token')
    self.assertIn('não verificado',text);self.assertNotIn('Apurado:',text)
