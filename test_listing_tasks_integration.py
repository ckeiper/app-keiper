"""Task persistence and isolation in the disposable PostgreSQL database only."""
import os
import unittest
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from auth_test_support import database_session
from sales_metrics import reporting_today
from listing_tasks import create,transition,validate,StaleTask,init_schema
from test_listing_tasks import form

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class ListingTaskIntegrationTests(unittest.TestCase):
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
        for label in ('Task A','Task B'):
            cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id']
            self.ids.append(cid)
            m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,'MLB123',%s)",(cid,label))
    self.client=m.app.test_client()
    with database_session(self.client) as state:state.update(usuario_id=1,tipo='admin')
    self.url=f'/anuncios/{self.ids[0]}/MLB123/tarefas'
    self.assertEqual(self.client.get(self.url).status_code,200)
    with self.client.session_transaction() as state:self.token=state['_csrf'];self.actor=state['usuario_id']
 def tearDown(self):
    with self.m.banco() as conn:
        for table in ('listing_task_events','listing_tasks','anuncios'):
            self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
        self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))
 def payload(self):return dict(form(),due_date=(reporting_today()+timedelta(days=1)).isoformat(),_csrf=self.token)
 def rows(self):
    with self.m.banco() as conn:
        return self.m.consultar(conn,'SELECT * FROM listing_tasks WHERE conexao_id=%s',(self.ids[0],))
 def make(self):
    self.assertEqual(self.client.post(self.url,data=self.payload()).status_code,303)
    return self.rows()[0]
 def test_create_retry_conflicting_payload_and_immutable_details(self):
    with patch.object(self.m.requests,'get',side_effect=AssertionError('network')):row=self.make()
    self.assertEqual(self.client.post(self.url,data=self.payload()).status_code,303)
    self.assertEqual(len(self.rows()),1)
    self.assertEqual(self.client.post(self.url,data=dict(self.payload(),title='Outro escopo')).status_code,400)
    with self.m.banco() as conn:
        events=self.m.consultar(conn,'SELECT * FROM listing_task_events WHERE task_id=%s',(row['id'],))
    self.assertEqual(len(events),1);self.assertIsNone(events[0]['from_status']);self.assertEqual(events[0]['to_status'],'open')
 def test_status_history_stale_version_and_reopen(self):
    row=self.make();data=dict(_csrf=self.token,operation='status',task_id=row['id'],version=1,previous='open',target='done')
    self.assertEqual(self.client.post(self.url,data=data).status_code,303)
    self.assertEqual(self.client.post(self.url,data=data).status_code,409)
    self.assertEqual(self.rows()[0]['status'],'done')
    self.assertEqual(self.client.post(self.url,data=dict(data,version=2,previous='done',target='open')).status_code,303)
    with self.m.banco() as conn:
        events=self.m.consultar(conn,'SELECT version,from_status,to_status FROM listing_task_events WHERE task_id=%s ORDER BY version',(row['id'],))
    self.assertEqual([e['to_status'] for e in events],['open','done','open'])
    self.assertEqual([e['version'] for e in events],[1,2,3])
 def test_anonymous_client_foreign_item_store_and_csrf(self):
    row=self.make();data=dict(_csrf=self.token,operation='status',task_id=row['id'],version=1,previous='open',target='done')
    foreign=f'/anuncios/{self.ids[1]}/MLB123/tarefas'
    self.assertEqual(self.client.post(foreign,data=data).status_code,404)
    self.assertEqual(self.client.get(foreign+'?tarefa='+str(row['id'])).status_code,404)
    self.assertEqual(self.client.get(f'/anuncios/{self.ids[0]}/MLB999/tarefas').status_code,404)
    self.assertEqual(self.client.post(self.url,data=dict(data,_csrf='bad')).status_code,400)
    self.assertEqual(self.m.app.test_client().get(self.url).status_code,302)
    client=self.m.app.test_client()
    with database_session(client) as state:state.update(usuario_id=2,tipo='cliente',conexao_id=self.ids[0])
    self.assertEqual(client.get(self.url).status_code,403);self.assertEqual(self.rows()[0]['status'],'open')
 def test_audit_failure_rolls_back_create_and_status_together(self):
    m=self.m;values=validate(self.payload(),reporting_today())
    def fail(*args,**kwargs):raise RuntimeError('isolated audit failure')
    with self.assertRaises(RuntimeError):
        with m.banco() as conn:create(conn,m.consultar,fail,self.ids[0],'MLB123',values,self.actor)
    self.assertEqual(self.rows(),[])
    row=self.make()
    with self.assertRaises(RuntimeError):
        with m.banco() as conn:transition(conn,m.consultar,fail,self.ids[0],'MLB123',row['id'],1,'open','done',self.actor)
    self.assertEqual(self.rows()[0]['status'],'open');self.assertEqual(self.rows()[0]['version'],1)
 def test_concurrent_updates_commit_one_state_and_one_event(self):
    row=self.make();barrier=Barrier(2);m=self.m
    def update(target):
        try:
            with m.banco() as conn:
                m.executar(conn,'SET LOCAL statement_timeout=5000');barrier.wait(timeout=5)
                transition(conn,m.consultar,m.executar,self.ids[0],'MLB123',row['id'],1,'open',target,self.actor)
            return 'ok'
        except StaleTask:return 'stale'
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(update,target) for target in ('done','cancelled')]
        results=[f.result(timeout=15) for f in futures]
    self.assertCountEqual(results,['ok','stale']);self.assertEqual(self.rows()[0]['version'],2)
    with m.banco() as conn:
        count=m.consultar(conn,'SELECT COUNT(*) AS n FROM listing_task_events WHERE task_id=%s',(row['id'],))[0]['n']
    self.assertEqual(count,2)
 def test_schema_idempotency_and_cancel_preserves_records(self):
    with self.m.banco() as conn:init_schema(conn,self.m.executar);init_schema(conn,self.m.executar)
    row=self.make()
    data=dict(_csrf=self.token,operation='status',task_id=row['id'],version=1,previous='open',target='cancelled')
    self.assertEqual(self.client.post(self.url,data=data).status_code,303)
    text=self.client.get(self.url+'?status=all&tarefa='+str(row['id'])).get_data(as_text=True)
    self.assertIn('Cancelada',text);self.assertIn('Usuário #',text);self.assertEqual(len(self.rows()),1)
    overdue=dict(self.payload(),title='Conferir tarefa atrasada',submission_key='z'*32,due_date=(reporting_today()-timedelta(days=1)).isoformat())
    self.assertEqual(self.client.post(self.url,data=overdue).status_code,303)
    text=self.client.get(self.url+'?status=overdue').get_data(as_text=True)
    self.assertIn('Conferir tarefa atrasada',text);self.assertNotIn('Conferir estoque Full',text)
 def test_calendar_real_counts_isolation_and_preserves_tasks(self):
    row=self.make();m=self.m;due=row['due_date'];month=due.strftime('%Y-%m')
    with m.banco() as conn:
        for i in range(12):
            values=validate(dict(self.payload(),title='Calendário tarefa '+str(i),submission_key=('calendar-'+str(i)).ljust(24,'x')),reporting_today())
            create(conn,m.consultar,m.executar,self.ids[0],'MLB123',values,self.actor)
        values=validate(dict(self.payload(),title='SEGREDO OUTRA LOJA',submission_key='foreign-calendar-key-1234'),reporting_today())
        create(conn,m.consultar,m.executar,self.ids[1],'MLB123',values,self.actor)
    path=self.url.replace('/tarefas','/calendario')+'?mes='+month
    with patch.object(m.requests,'get',side_effect=AssertionError('network')):
        response=self.client.get(path)
    self.assertEqual(response.status_code,200);text=response.get_data(as_text=True)
    self.assertIn('13 tarefas no mês',text);self.assertNotIn('SEGREDO OUTRA LOJA',text)
    self.assertEqual(text.count('class="lc-task"'),10)
    self.assertEqual(self.client.get(path+'&pagina=2').get_data(as_text=True).count('class="lc-task"'),3)
    self.assertEqual(len(self.rows()),13)
    restricted=m.app.test_client()
    with database_session(restricted) as state:state.update(usuario_id=2,tipo='cliente',conexao_id=self.ids[0])
    self.assertEqual(restricted.get(path).status_code,403)
