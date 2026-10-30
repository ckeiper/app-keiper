import contextlib
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_questions import persist,model,render,register_questions

def row(i=1,**changes):
 r=dict(pergunta_id=str(i),texto=' Serve neste modelo? ',status='UNANSWERED',resposta=None,data='2026-10-26T00:00:00Z',atualizado_em=1792980000);r.update(changes);return r
class QuestionTests(unittest.TestCase):
 def test_batch_validated_before_writes_and_never_deletes(self):
    q=dict(id=1,item_id='MLB1',text='Serve?',status='UNANSWERED',answer=None,date_created='2026-10-26')
    e=Mock();self.assertEqual(persist(None,e,7,dict(questions=[q]),123),1)
    self.assertEqual(e.call_args.args[2][:3],(7,'1','MLB1'));self.assertNotIn('DELETE',e.call_args.args[1])
    for payload in [{},dict(questions={}),dict(questions=[q,dict(q,id=None)]),dict(questions=[q,q]),dict(questions=[dict(q,text=['bad'])]),dict(questions=[dict(q,answer={'text':'bad\x00'})])]:
        e=Mock()
        with self.assertRaises(ValueError):persist(None,e,7,payload,123)
        e.assert_not_called()
    e=Mock();self.assertEqual(persist(None,e,7,dict(questions=[]),123),0);e.assert_not_called()
 def test_literal_groups_status_and_paging(self):
    rows=[row(1),row(2,texto='serve  neste MODELO?',status='ANSWERED'),row(3,texto='Serve em outro modelo?',status='CLOSED'),row(4,texto=None)]
    data=model(rows,dict(status='ANSWERED',pagina='999'))
    self.assertEqual(data['total'],4);self.assertEqual(data['filtered'],1);self.assertEqual(data['group_total'],1)
    self.assertEqual(data['groups'][0]['n'],2);self.assertEqual(data['groups'][0]['pending'],1)
    data=model([row(i,texto='texto '+str(i)) for i in range(1001)],dict(pagina='999',recorrencias='bad'))
    self.assertTrue(data['limited']);self.assertEqual(data['total'],1000);self.assertEqual(data['page'],100);self.assertEqual(len(data['rows']),10)
 def test_render_escape_limits_unknown_dates_and_no_inference(self):
    data=model([row(texto='<script>',resposta='<img>',status='CLOSED',data='invalid')],{})
    text=render(7,'MLB1',dict(titulo='<script>'),data)
    self.assertNotIn('<script>',text);self.assertNotIn('<img>',text);self.assertIn('Data não verificada',text)
    self.assertIn('Outros status: 1',text);self.assertIn('Não identifica intenção',text);self.assertIn('Até duas páginas de 50 perguntas',text)
    text=render(7,'MLB1',{},model([],{}));self.assertIn('não comprova ausência de dúvidas',text)
 def test_route_scope_readonly_and_roles(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_questions(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1]);c=app.test_client();path='/anuncios/7/MLB1/perguntas'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin')
    self.assertEqual(c.get('/anuncios/8/MLB1/perguntas').status_code,403);q.assert_not_called()
    q.return_value=[];self.assertEqual(c.get(path).status_code,404)
    q.side_effect=[[dict(cliente='Loja')],[],[row()]];self.assertEqual(c.get(path).status_code,200)
    self.assertEqual(q.call_args.args[2],(7,'MLB1'));self.assertIn('LIMIT 1001',q.call_args.args[1]);self.assertIn('READ ONLY',e.call_args.args[1])
    self.assertEqual(c.post(path).status_code,405)
