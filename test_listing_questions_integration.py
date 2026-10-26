"""Question collection and report in the disposable PostgreSQL database."""
import os
import unittest
from unittest.mock import patch
from auth_test_support import database_session
from listing_questions import persist

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class QuestionIntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
    main.app.config['TESTING']=True
 def setUp(self):
    m=self.m;self.ids=[]
    with m.banco() as conn:
        for label in ('Questions A','Questions B'):
            cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'];self.ids.append(cid)
            m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,'MLB123',%s)",(cid,label))
    self.c=m.app.test_client()
    with database_session(self.c) as s:s.update(usuario_id=1,tipo='admin')
    self.path=f'/anuncios/{self.ids[0]}/MLB123/perguntas'
 def tearDown(self):
    with self.m.banco() as conn:
        for table in ('perguntas','anuncios'):self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
        self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))
 def payload(self,i,status='UNANSWERED',text='Serve neste modelo?'):
    return dict(id=i,item_id='MLB123',text=text,status=status,answer={'text':'Sim, confira a especificação.'} if status=='ANSWERED' else None,date_created='2026-10-26T00:00:00Z')
 def rows(self):
    with self.m.banco() as conn:return self.m.consultar(conn,'SELECT * FROM perguntas WHERE conexao_id=%s ORDER BY pergunta_id',(self.ids[0],))
 def test_collection_preserves_old_empty_invalid_and_atomic_failure(self):
    m=self.m;cid=self.ids[0]
    with patch.object(m,'api_get',return_value=(dict(questions=[self.payload(1)]),None)):self.assertTrue(m.puxar_perguntas(cid,'synthetic-token',123))
    with patch.object(m,'api_get',return_value=(dict(questions=[self.payload(2)]),None)):self.assertTrue(m.puxar_perguntas(cid,'synthetic-token',123))
    self.assertEqual(len(self.rows()),2)
    with patch.object(m,'api_get',return_value=(dict(questions=[]),None)):self.assertTrue(m.puxar_perguntas(cid,'synthetic-token',123))
    self.assertEqual(len(self.rows()),2)
    with patch.object(m,'api_get',return_value=(dict(questions=[self.payload(1,'ANSWERED')]),None)):self.assertTrue(m.puxar_perguntas(cid,'synthetic-token',123))
    self.assertEqual(self.rows()[0]['status'],'ANSWERED')
    with patch.object(m,'api_get',return_value=(dict(questions=[self.payload(3),dict(id=None)]),None)):self.assertFalse(m.puxar_perguntas(cid,'synthetic-token',123))
    self.assertEqual(len(self.rows()),2)
    def fail(conn,sql,params):
        if params[1]=='4':raise RuntimeError('isolated rollback test')
        m.executar(conn,sql,params)
    with self.assertRaises(RuntimeError):
        with m.banco() as conn:persist(conn,fail,cid,dict(questions=[self.payload(3),self.payload(4)]),123)
    self.assertEqual(len(self.rows()),2)
 def test_report_scope_status_pagination_and_roles(self):
    m=self.m
    with m.banco() as conn:
        persist(conn,m.executar,self.ids[0],dict(questions=[self.payload(i,'ANSWERED' if i%2 else 'UNANSWERED') for i in range(1,24)]),1792980000)
        persist(conn,m.executar,self.ids[1],dict(questions=[self.payload(1,text='SEGREDO DA OUTRA LOJA')]),1792980000)
    with patch.object(m.requests,'get',side_effect=AssertionError('network')):r=self.c.get(self.path)
    text=r.get_data(as_text=True);self.assertEqual(r.status_code,200);self.assertNotIn('SEGREDO DA OUTRA LOJA',text)
    self.assertIn('23 ocorrências',text);self.assertEqual(text.count('Resposta registrada:'),10)
    self.assertEqual(self.c.get(self.path+'?pagina=3').get_data(as_text=True).count('Resposta registrada:'),3)
    self.assertIn('12 perguntas neste filtro',self.c.get(self.path+'?status=ANSWERED').get_data(as_text=True))
    self.assertEqual(self.c.get(self.path.replace('MLB123','MLB999')).status_code,404)
    other=m.app.test_client()
    with database_session(other) as s:s.update(usuario_id=2,tipo='cliente',conexao_id=self.ids[0])
    self.assertEqual(other.get(self.path).status_code,403)
