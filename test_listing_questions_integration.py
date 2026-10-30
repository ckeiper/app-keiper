"""Question collection and report in the disposable PostgreSQL database."""
import os
import unittest
from unittest.mock import patch
from types import SimpleNamespace
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
        for table in ('perguntas_coleta','perguntas','anuncios','erros'):self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
        self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))
 def payload(self,i,status='UNANSWERED',text='Serve neste modelo?'):
    return dict(id=i,seller_id=123,deleted_from_listing=False,hold=False,item_id='MLB123',text=text,status=status,answer={'text':'Sim, confira a especificação.'} if status=='ANSWERED' else None,date_created='2026-10-26T00:00:00Z')
 def reply(self,questions):
    payload=dict(questions=questions,total=len(questions),limit=50,filters=dict(offset=0))
    return patch.object(self.m.requests,'get',return_value=SimpleNamespace(status_code=200,json=lambda:payload))
 def rows(self):
    with self.m.banco() as conn:return self.m.consultar(conn,'SELECT * FROM perguntas WHERE conexao_id=%s ORDER BY pergunta_id',(self.ids[0],))
 def test_collection_preserves_old_empty_invalid_and_atomic_failure(self):
    m=self.m;cid=self.ids[0]
    with self.reply([self.payload(1)]):self.assertTrue(m.puxar_perguntas(cid,'synthetic-token',123))
    with self.reply([self.payload(2)]):self.assertTrue(m.puxar_perguntas(cid,'synthetic-token',123))
    self.assertEqual(len(self.rows()),2)
    with self.reply([]):self.assertTrue(m.puxar_perguntas(cid,'synthetic-token',123))
    self.assertEqual(len(self.rows()),2)
    with self.reply([self.payload(1,'ANSWERED')]):self.assertTrue(m.puxar_perguntas(cid,'synthetic-token',123))
    self.assertEqual(self.rows()[0]['status'],'ANSWERED')
    with self.reply([self.payload(3),dict(id=None)]):self.assertFalse(m.puxar_perguntas(cid,'synthetic-token',123))
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
 def test_old_pending_rechecks_and_failed_lookup_do_not_preserve_false_alert(self):
    import time
    from question_sync import collect,pending_count
    m=self.m;cid=self.ids[0];now=int(time.time())
    with m.banco() as conn:
        m.executar(conn,'UPDATE conexoes SET user_id=123 WHERE id=%s',(cid,))
        persist(conn,m.executar,cid,dict(questions=[self.payload(1),self.payload(2)]),now-22000,123)
    replies=[SimpleNamespace(status_code=200,json=lambda:dict(total=0,limit=50,filters=dict(offset=0),questions=[])),
             SimpleNamespace(status_code=200,json=lambda:self.payload(1,'ANSWERED')),
             SimpleNamespace(status_code=404,json=lambda:{})]
    with patch.object(m.requests,'get',side_effect=replies) as get:
        self.assertTrue(collect(cid,'synthetic',123,m.banco,m.consultar,m.executar,m.requests.get,m.registrar_erro,now))
        self.assertEqual(get.call_count,3)
    rows=self.rows();self.assertEqual(rows[0]['status'],'ANSWERED');self.assertEqual(rows[1]['status'],'UNANSWERED')
    self.assertEqual(rows[1]['consulta_estado'],'unknown')
    self.assertEqual(rows[1]['texto'],'Serve neste modelo?')
    self.assertEqual(rows[1]['consulta_em'],now)
    with m.banco() as conn:
        self.assertEqual(pending_count(conn,m.consultar,cid,123,now),0)
        fresh=[self.payload(3),self.payload(4,'BANNED'),self.payload(5,'DELETED'),self.payload(6)]
        fresh[-1]['hold']=True
        persist(conn,m.executar,cid,dict(questions=fresh),now,123)
        self.assertEqual(pending_count(conn,m.consultar,cid,123,now),1)
        self.assertEqual(pending_count(conn,m.consultar,cid,999,now),0)
        coverage=m.consultar(conn,'SELECT * FROM perguntas_coleta WHERE conexao_id=%s',(cid,))[0]
        self.assertEqual(coverage['revisadas'],1);self.assertEqual(coverage['indisponiveis'],1)
    with patch.object(m.requests,'get',side_effect=AssertionError('network during report')):
        text=self.c.get(self.path).get_data(as_text=True)
        self.assertIn('Última coleta da loja',text)
        self.assertIn('Status sem verificação recente',text)
        self.assertNotIn('private@example.invalid',text)
 def test_refresh_round_robin_and_wrong_owner_never_update_question_content(self):
    import time
    from question_sync import collect
    m=self.m;cid=self.ids[0];now=int(time.time())
    with m.banco() as conn:
        persist(conn,m.executar,cid,dict(questions=[self.payload(i) for i in range(1,5)]),now-22000,123)
    empty=SimpleNamespace(status_code=200,json=lambda:dict(total=0,limit=50,filters=dict(offset=0),questions=[]))
    foreign=self.payload(1);foreign['seller_id']=999;foreign['text']='SEGREDO DE OUTRA CONTA'
    with patch.object(m.requests,'get',side_effect=[empty,SimpleNamespace(status_code=200,json=lambda:foreign)]):
        self.assertFalse(collect(cid,'synthetic',123,m.banco,m.consultar,m.executar,m.requests.get,m.registrar_erro,now))
    self.assertEqual(self.rows()[0]['texto'],'Serve neste modelo?')
    # First question was attempted and must not monopolize the next selection.
    replies=[empty,SimpleNamespace(status_code=200,json=lambda:self.payload(2,'ANSWERED')),
             SimpleNamespace(status_code=200,json=lambda:self.payload(3,'ANSWERED'))]
    with patch.object(m.requests,'get',side_effect=replies) as get:
        self.assertTrue(collect(cid,'synthetic',123,m.banco,m.consultar,m.executar,m.requests.get,m.registrar_erro,now+1))
        self.assertTrue(get.call_args_list[1].args[0].endswith('/questions/2'))
        self.assertTrue(get.call_args_list[2].args[0].endswith('/questions/3'))
    self.assertNotIn('SEGREDO DE OUTRA CONTA',str(self.rows()))
