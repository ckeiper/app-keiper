import contextlib
from datetime import date,timedelta
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_goals import validate,create,cancel,load,evaluate
from listing_goal_routes import register_goals
from listing_goal_view import render
DAY=date(2026,10,26);NOW=1793012400

def form():return dict(minimum='5',start_date=DAY.isoformat(),end_date=(DAY+timedelta(days=29)).isoformat(),responsible='Equipe da loja',submission_key='k'*32)
def goal(**changes):
 r=dict(id=1,minimum=5,start_date=DAY,end_date=DAY+timedelta(days=29),responsible='Equipe da loja',created_at=NOW,created_by=1,cancelled_at=None,cancelled_by=None);r.update(changes);return r
def shop(**changes):
 r=dict(cliente='Loja',titulo='Produto',item_id='MLB1',quantidade=2,atualizado_em=NOW);r.update(changes);return r
class GoalTests(unittest.TestCase):
 def test_validation_requires_explicit_fields(self):
    self.assertEqual(validate(form(),DAY)['minimum'],5)
    for change in [dict(minimum='1.5'),dict(minimum='-1'),dict(minimum='NaN'),dict(minimum='1000001'),dict(start_date='bad'),dict(end_date=(DAY-timedelta(days=1)).isoformat()),dict(end_date=(DAY+timedelta(days=90)).isoformat()),dict(responsible=''),dict(submission_key='bad')]:
        with self.subTest(change=change),self.assertRaises(ValueError):validate(dict(form(),**change),DAY)
    self.assertEqual(validate(dict(form(),minimum='0'),DAY)['minimum'],0)
 def test_create_retry_conflict_and_cancel_preserves_audit(self):
    v=validate(form(),DAY);q=Mock(return_value=[dict(id=1)])
    self.assertEqual(create(None,q,7,'MLB1',v,1),1);self.assertEqual(q.call_args.args[2][:3],(7,'MLB1',5))
    self.assertEqual(create(None,Mock(side_effect=[[],[dict(v,id=1)]]),7,'MLB1',v,1),1)
    with self.assertRaises(ValueError):create(None,Mock(side_effect=[[],[dict(v,id=1,minimum=9)]]),7,'MLB1',v,1)
    q=Mock(return_value=[dict(id=1)]);cancel(None,q,7,'MLB1',1,3)
    self.assertEqual(q.call_args.args[2][1:],(3,1,7,'MLB1'));self.assertIn('cancelled_at IS NULL',q.call_args.args[1])
    with self.assertRaises(LookupError):cancel(None,Mock(side_effect=[[],[]]),7,'MLB1',1,3)
 def test_evaluation_zero_stale_future_invalid_and_lifecycle(self):
    self.assertEqual(evaluate(goal(),shop(),DAY,NOW)[0],'alert')
    self.assertEqual(evaluate(goal(minimum=0),shop(quantidade=0),DAY,NOW)[0],'met')
    for change in [dict(quantidade=None),dict(quantidade=-1),dict(quantidade=1.5),dict(quantidade=True),dict(atualizado_em=NOW-21601),dict(atualizado_em=NOW+1),dict(atualizado_em=None)]:
        self.assertEqual(evaluate(goal(),shop(**change),DAY,NOW)[0],'unknown')
    self.assertEqual(evaluate(goal(),shop(),DAY+timedelta(days=30),NOW)[0],'ended')
    self.assertEqual(evaluate(goal(),shop(),DAY-timedelta(days=1),NOW)[0],'scheduled')
    self.assertEqual(evaluate(goal(cancelled_at=NOW),shop(),DAY,NOW)[0],'cancelled')
 def test_scoped_pagination_render_and_no_assumed_target(self):
    q=Mock(side_effect=[[dict(n=23)],[goal()]]);m=load(None,q,7,'MLB1',dict(pagina='999'))
    self.assertEqual(m['page'],3);self.assertEqual(q.call_args.args[2],(7,'MLB1',20))
    text=render(7,'MLB1',shop(titulo='<script>'),m,DAY,NOW,'token')
    self.assertNotIn('<script>',text);self.assertIn('Alerta · estoque observado',text);self.assertIn('pagina=2',text);self.assertIn('name="_csrf"',text)
    text=render(7,'MLB1',shop(),dict(rows=[],page=1,pages=1,total=0),DAY,NOW,'token')
    self.assertIn('Nenhum limite é presumido',text)
 def test_route_roles_csrf_readonly_and_missing_store(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_goals(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1],today=lambda:DAY);c=app.test_client();path='/anuncios/7/MLB1/metas'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin',usuario_id=1,_csrf='token')
    self.assertEqual(c.get('/anuncios/8/MLB1/metas').status_code,403)
    self.assertEqual(c.post(path,data=form()).status_code,400);q.assert_not_called()
    q.return_value=[];self.assertEqual(c.get(path).status_code,404)
    q.side_effect=[[shop()],[dict(n=0)],[]];self.assertEqual(c.get(path).status_code,200);self.assertIn('READ ONLY',e.call_args.args[1])
