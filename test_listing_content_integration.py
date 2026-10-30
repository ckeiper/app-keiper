"""Disposable PostgreSQL only; never writes production reviews."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from auth_test_support import database_session
from listing_content import save,validate,StaleReview,init_schema
from test_listing_content import form

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class ContentIntegrationTests(unittest.TestCase):
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
        for label in ('Content A','Content B'):
            cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'];self.ids.append(cid)
            m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,'MLB123',%s)",(cid,label))
    self.c=m.app.test_client()
    with database_session(self.c) as state:state.update(usuario_id=1,tipo='admin')
    self.path=f'/anuncios/{self.ids[0]}/MLB123/conteudo';self.assertEqual(self.c.get(self.path).status_code,200)
    with self.c.session_transaction() as s:self.token=s['_csrf'];self.actor=s['usuario_id']
 def tearDown(self):
    with self.m.banco() as conn:
        for table in ('listing_content_reviews','anuncios'):self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
        self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))
 def rows(self):
    with self.m.banco() as conn:return self.m.consultar(conn,'SELECT * FROM listing_content_reviews WHERE conexao_id=%s ORDER BY id',(self.ids[0],))
 def test_create_retry_stale_history_scope_csrf_and_roles(self):
    data=dict(form(),_csrf=self.token)
    self.assertEqual(self.c.post(self.path,data=data).status_code,303)
    self.assertEqual(self.c.post(self.path,data=data).status_code,303);self.assertEqual(len(self.rows()),1)
    first=self.rows()[0]
    self.assertEqual(self.c.post(self.path,data=dict(data,submission_key='next-key'.ljust(24,'x'))).status_code,409)
    self.assertEqual(self.c.post(self.path,data=dict(data,expected=first['id'],submission_key='next-key'.ljust(24,'x'),verdict='approved',note='Produto conferido manualmente na oferta.')).status_code,303)
    self.assertEqual(len(self.rows()),2);self.assertEqual(self.rows()[0]['verdict'],'revise')
    foreign=f'/anuncios/{self.ids[1]}/MLB123/conteudo'
    text=self.c.get(foreign).get_data(as_text=True);self.assertNotIn(first['note'],text)
    self.assertEqual(self.c.get(self.path.replace('MLB123','MLB999')).status_code,404)
    self.assertEqual(self.c.post(self.path,data=dict(data,_csrf='wrong')).status_code,400)
    self.assertEqual(self.m.app.test_client().get(self.path).status_code,302)
    other=self.m.app.test_client()
    with database_session(other) as s:s.update(usuario_id=2,tipo='cliente',conexao_id=self.ids[0])
    self.assertEqual(other.get(self.path).status_code,403)
 def test_concurrent_append_one_winner(self):
    barrier=Barrier(2);m=self.m
    def run(key):
        try:
            with m.banco() as conn:
                barrier.wait(timeout=5)
                return save(conn,m.consultar,m.executar,self.ids[0],'MLB123',validate(dict(form(),submission_key=key*24)),self.actor)
        except StaleReview:return 'stale'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,['a','b']))
    self.assertEqual(results.count('stale'),1);self.assertEqual(len(self.rows()),1)
 def test_pagination_and_schema_idempotency(self):
    m=self.m
    with m.banco() as conn:
        init_schema(conn,m.executar);init_schema(conn,m.executar)
        previous=0
        for i in range(13):
            previous=save(conn,m.consultar,m.executar,self.ids[0],'MLB123',validate(dict(form(),expected=previous,submission_key=('history-'+str(i)).ljust(24,'x'))),self.actor)
    text=self.c.get(self.path+'?pagina=2').get_data(as_text=True)
    self.assertIn('13 revisões',text);self.assertIn('Página 2 de 2',text);self.assertEqual(len(self.rows()),13)
