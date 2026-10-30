import contextlib
from datetime import date,timedelta
import unittest
from unittest.mock import Mock,patch
from flask import Flask
from listing_onboarding import validate,create_plan,load,STEPS
from listing_onboarding_routes import register_onboarding
from listing_onboarding_view import render
DAY=date(2026,10,26)
def form():return dict(start_date=DAY.isoformat(),responsible='Equipe da loja',submission_key='k'*32)
def fixture():
 return dict(plan=dict(id=1,start_date=DAY,responsible='Equipe'),steps=[dict(id=i+1,step=i,title=t,responsible='Equipe',description=d,status='open',due_date=DAY+timedelta(days=o)) for i,(o,t,d) in enumerate(STEPS)])
class OnboardingTests(unittest.TestCase):
 def test_validate(self):
    self.assertEqual(validate(form(),DAY)['start_date'],DAY)
    for change in [dict(start_date='bad'),dict(start_date=(DAY+timedelta(days=91)).isoformat()),dict(responsible=''),dict(responsible='x\x00'),dict(submission_key='bad')]:
        with self.subTest(change=change),self.assertRaises(ValueError):validate(dict(form(),**change),DAY)
 def test_create_atomic_sequence_retry_and_conflict(self):
    data=validate(form(),DAY);q=Mock(return_value=[dict(id=9)]);e=Mock()
    with patch('listing_onboarding.create',return_value=7) as task:
        self.assertEqual(create_plan(None,q,e,3,'MLB1',data,1),9)
        self.assertEqual(task.call_count,4);self.assertEqual(e.call_count,4)
        self.assertEqual([c.args[5]['due_date'] for c in task.call_args_list],[DAY+timedelta(days=d) for d in (0,6,13,29)])
    q=Mock(side_effect=[[],[dict(id=9,**data)]]);e=Mock()
    self.assertEqual(create_plan(None,q,e,3,'MLB1',data,1),9);e.assert_not_called()
    with self.assertRaises(ValueError):create_plan(None,Mock(side_effect=[[],[dict(id=9,start_date=DAY,responsible='Outro')]]),e,3,'MLB1',data,1)
 def test_load_scope(self):
    q=Mock(side_effect=[[dict(id=9)],[]]);load(None,q,3,'MLB1')
    self.assertEqual(q.call_args.args[2],(9,3,'MLB1'));self.assertIn('t.conexao_id=%s AND t.item_id=%s',q.call_args.args[1])
 def test_render_empty_future_overdue_cancelled_and_done(self):
    text=render(3,'MLB1',dict(titulo='<script>'),dict(plan=None,steps=[]),DAY,'token')
    self.assertNotIn('<script>',text);self.assertIn('name="_csrf"',text);self.assertIn('value=""',text)
    data=fixture();data['steps'][0]['status']='done';data['steps'][1]['status']='cancelled'
    text=render(3,'MLB1',{},data,DAY+timedelta(days=40),'token')
    self.assertIn('1 de 4 etapas concluídas',text);self.assertIn('Janela de 30 dias encerrada',text);self.assertIn('2 atrasadas · 1 canceladas',text)
    self.assertIn('ainda não iniciado',render(3,'MLB1',{},fixture(),DAY-timedelta(days=1),'token'))
 def test_route_auth_csrf_and_existing_scope(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_onboarding(app,lambda f:f,lambda cid:cid==3,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1],today=lambda:DAY);c=app.test_client();path='/anuncios/3/MLB1/primeiros-30-dias'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin',usuario_id=1,_csrf='token')
    self.assertEqual(c.get('/anuncios/4/MLB1/primeiros-30-dias').status_code,403)
    self.assertEqual(c.post(path,data=form()).status_code,400);q.assert_not_called()
    q.return_value=[];self.assertEqual(c.get(path).status_code,404)
    q.side_effect=[[dict(cliente='Loja')],[]];self.assertEqual(c.get(path).status_code,200);self.assertIn('READ ONLY',e.call_args.args[1])
