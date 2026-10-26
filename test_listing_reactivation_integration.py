import os,time
import unittest
from unittest.mock import patch
from auth_test_support import database_session
from automatic_history import record
from sales_metrics import reporting_today
from listing_reactivation import TITLE

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class ReactivationIntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
    main.app.config['TESTING']=True
 def test_review_task_retry_and_observed_transition_without_marketplace_write(self):
    m=self.m;ids=[];now=int(time.time())
    try:
        with m.banco() as conn:
            for label in ('Reactivation A','Reactivation B'):
                cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'];ids.append(cid)
                m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo,status,quantidade,atualizado_em) VALUES(%s,'MLB123',%s,'paused',0,%s)",(cid,label,now))
        c=m.app.test_client()
        with database_session(c) as s:s.update(usuario_id=1,tipo='admin')
        path=f'/anuncios/{ids[0]}/MLB123/reativacao';self.assertEqual(c.get(path).status_code,200)
        with c.session_transaction() as s:token=s['_csrf']
        data=dict(_csrf=token,responsible='Equipe',due_date=reporting_today().isoformat(),description='Conferir motivo e condições no marketplace.',submission_key='reactivation-key-1234567890')
        with patch.object(m.requests,'get',side_effect=AssertionError('network')),patch.object(m.requests,'put',side_effect=AssertionError('marketplace write')):
            self.assertEqual(c.post(path,data=data).status_code,303);self.assertEqual(c.post(path,data=data).status_code,303)
        with m.banco() as conn:
            tasks=m.consultar(conn,'SELECT * FROM listing_tasks WHERE conexao_id=%s',(ids[0],));self.assertEqual(len(tasks),1);self.assertEqual(tasks[0]['title'],TITLE)
            self.assertEqual(m.consultar(conn,'SELECT status FROM anuncios WHERE conexao_id=%s',(ids[0],))[0]['status'],'paused')
            for stamp,status in [(now-1,'paused'),(now,'active')]:record(conn,m.executar,ids[0],'MLB123','listing',stamp,dict(status=dict(value=status,label='Status',kind='outro')))
        text=c.get(path).get_data(as_text=True);self.assertIn('Pausado → Ativo',text)
        self.assertIn('Nenhuma conferência planejada',c.get(path.replace('/'+str(ids[0])+'/', '/'+str(ids[1])+'/')).get_data(as_text=True))
        self.assertEqual(c.post(path,data=dict(data,_csrf='bad')).status_code,400)
        other=m.app.test_client()
        with database_session(other) as s:s.update(usuario_id=2,tipo='cliente',conexao_id=ids[0])
        self.assertEqual(other.get(path).status_code,403)
        self.assertEqual(c.get(path.replace('MLB123','MLB999')).status_code,404)
    finally:
        with m.banco() as conn:
            for table in ('listing_task_events','listing_tasks','anuncios'):m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(ids,))
            m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(ids,))
