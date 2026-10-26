import contextlib
import unittest
from unittest.mock import Mock
from flask import Flask
from listing_content import validate,save,load,StaleReview,CRITERIA
from listing_content_routes import register_content
from listing_content_view import render

def form(**changes):return dict(criterion='principal',verdict='revise',note='Conferir a legibilidade do produto na imagem principal.',submission_key='k'*32,expected='0',**changes)
class ContentTests(unittest.TestCase):
 def test_validation_rejects_missing_evidence_and_invalid_inputs(self):
    self.assertEqual(validate(form())['expected'],0)
    for change in [dict(criterion='bad'),dict(verdict='bad'),dict(note='curta'),dict(note='x'*1501),dict(note='teste\x00texto'),dict(expected='-1'),dict(expected='x'),dict(submission_key='x')]:
        with self.subTest(change=change),self.assertRaises(ValueError):validate(dict(form(),**change))
 def test_save_append_retry_scope_and_stale(self):
    v=validate(form());q=Mock(side_effect=[[],[],[dict(id=1)]]);e=Mock()
    self.assertEqual(save(None,q,e,7,'MLB1',v,3),1)
    self.assertIn('advisory',e.call_args.args[1]);self.assertEqual(q.call_args.args[2][:3],(7,'MLB1','principal'))
    q=Mock(return_value=[dict(v,id=1)]);self.assertEqual(save(None,q,e,7,'MLB1',v,3),1);self.assertEqual(q.call_count,1)
    with self.assertRaises(StaleReview):save(None,Mock(side_effect=[[],[dict(id=2)]]),e,7,'MLB1',v,3)
    with self.assertRaises(ValueError):save(None,Mock(return_value=[dict(v,id=1,note='outro texto')]),e,7,'MLB1',v,3)
 def test_load_bounds_and_scope(self):
    q=Mock(side_effect=[[],[dict(n=23)],[]]);m=load(None,q,7,'MLB1',dict(pagina='999'))
    self.assertEqual((m['page'],m['pages']),(3,3));self.assertEqual(q.call_args.args[2],(7,'MLB1',20))
    for c in q.call_args_list:self.assertIn('conexao_id=%s AND item_id=%s',c.args[1])
 def test_empty_and_manual_review_escaping_and_stale_form(self):
    m=dict(latest={},history=[],total=0,page=1,pages=1)
    text=render(7,'MLB1',dict(titulo='<script>',fotos=0,clips=None),m,'token')
    self.assertEqual(text.count('name="criterion"'),8);self.assertNotIn('<script>',text);self.assertNotIn(' selected',text)
    self.assertIn('clips não verificados',text);self.assertIn('Nenhum critério é aprovado automaticamente',text)
    row=dict(id=5,criterion='principal',verdict='revise',note='<script>evidência</script>',created_at=1792980000,created_by=3)
    m.update(latest={'principal':row},history=[row],total=1)
    text=render(7,'MLB1',{},m,'token',form(),message='Mudou em outra aba')
    self.assertNotIn('<script>',text);self.assertIn('name="expected" value="0"',text)
    self.assertIn('Precisa de ajuste',text);self.assertIn('Usuário #3',text)
 def test_route_permission_csrf_scope_and_stale(self):
    app=Flask(__name__);app.secret_key='test';q=Mock();e=Mock()
    register_content(app,lambda f:f,lambda cid:cid==7,lambda:contextlib.nullcontext(None),q,e,lambda *a:a[-1]);c=app.test_client();path='/anuncios/7/MLB1/conteudo'
    self.assertEqual(c.get(path).status_code,403)
    with c.session_transaction() as s:s.update(tipo='admin',usuario_id=1,_csrf='token')
    self.assertEqual(c.get('/anuncios/8/MLB1/conteudo').status_code,403)
    self.assertEqual(c.post(path,data=form()).status_code,400);q.assert_not_called()
    q.return_value=[];self.assertEqual(c.get(path).status_code,404)
    q.side_effect=[[dict(cliente='Loja')],[],[dict(n=0)],[]]
    self.assertEqual(c.get(path).status_code,200);self.assertIn('READ ONLY',e.call_args.args[1])
    q.side_effect=[[dict(cliente='Loja')],[],[dict(id=9)],[],[dict(n=0)],[]]
    self.assertEqual(c.post(path,data=dict(form(),_csrf='token')).status_code,409)
