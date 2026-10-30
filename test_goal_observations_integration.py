import os,time
import unittest
from datetime import timedelta
from auth_test_support import database_session
from listing_goals import create,validate,cancel
from goal_observations import collect,init_schema
from sales_metrics import reporting_today
from test_listing_goals import form

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class ObservationIntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
    main.app.config['TESTING']=True
 def test_records_lifecycle_scope_retry_and_readonly_history(self):
    m=self.m;ids=[];now=int(time.time());day=reporting_today();goals=[]
    try:
        with m.banco() as conn:
            init_schema(conn,m.executar);init_schema(conn,m.executar)
            for label in ('Observation A','Observation B'):
                cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'];ids.append(cid)
                m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo,quantidade,atualizado_em) VALUES(%s,'MLB123',%s,0,%s)",(cid,label,now))
                data=validate(dict(form(),start_date=day.isoformat(),end_date=(day+timedelta(days=1)).isoformat()),day)
                goals.append(create(conn,m.consultar,cid,'MLB123',data,1))
        now=int(time.time())
        collect(ids[0],m.banco,m.consultar,m.executar,now);collect(ids[0],m.banco,m.consultar,m.executar,now)
        with m.banco() as conn:
            rows=m.consultar(conn,'SELECT * FROM listing_goal_observations WHERE goal_id=%s',(goals[0],))
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['stock'],0);self.assertEqual(rows[0]['state'],'alert')
            m.executar(conn,"UPDATE anuncios SET atualizado_em=1 WHERE conexao_id=%s",(ids[0],))
        collect(ids[0],m.banco,m.consultar,m.executar,now+1)
        with m.banco() as conn:
            rows=m.consultar(conn,'SELECT * FROM listing_goal_observations WHERE goal_id=%s ORDER BY id',(goals[0],));self.assertEqual(len(rows),2);self.assertIsNone(rows[-1]['stock'])
            cancel(conn,m.consultar,ids[0],'MLB123',goals[0],1)
        collect(ids[0],m.banco,m.consultar,m.executar,now+2)
        c=m.app.test_client()
        with database_session(c) as s:s.update(usuario_id=1,tipo='admin')
        path=f'/anuncios/{ids[0]}/MLB123/metas/historico/{goals[0]}'
        self.assertIn('2 avaliações',c.get(path).get_data(as_text=True));self.assertEqual(c.get(f'/anuncios/{ids[0]}/MLB123/metas/historico/{goals[1]}').status_code,404)
        with m.banco() as conn:self.assertEqual(m.consultar(conn,'SELECT COUNT(*) AS n FROM listing_goal_observations WHERE goal_id=%s',(goals[0],))[0]['n'],2)
    finally:
        with m.banco() as conn:
            for table in ('listing_goal_observations','listing_stock_goals','anuncios'):m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(ids,))
            m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(ids,))
