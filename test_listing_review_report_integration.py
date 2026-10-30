import os
import unittest
from unittest.mock import patch
from auth_test_support import database_session

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class ReportIntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
    main.app.config['TESTING']=True
 def test_report_isolates_store_and_preserves_data(self):
    m=self.m;ids=[]
    try:
        with m.banco() as conn:
            for label in ('Report A','Report B'):
                cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'];ids.append(cid)
                m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,'MLB123',%s)",(cid,label))
                for i in range(11):m.executar(conn,"INSERT INTO listing_tasks(conexao_id,item_id,title,responsible,due_date,description,created_at,created_by,submission_key) VALUES(%s,'MLB123',%s,'Equipe',CURRENT_DATE,'',123,1,%s)",(cid,'Tarefa '+str(i) if len(ids)==1 else 'SEGREDO OUTRA LOJA',str(i)))
        c=m.app.test_client()
        with database_session(c) as s:s.update(usuario_id=1,tipo='admin')
        path=f'/anuncios/{ids[0]}/MLB123/relatorio-revisao'
        with patch.object(m.requests,'get',side_effect=AssertionError('network')):r=c.get(path)
        text=r.get_data(as_text=True);self.assertEqual(r.status_code,200);self.assertNotIn('SEGREDO OUTRA LOJA',text)
        self.assertIn('Aberta: 11',text);self.assertIn('primeiras dez tarefas',text);self.assertEqual(text.count(' · tarefa #'),10)
        self.assertEqual(c.get(path.replace('MLB123','MLB999')).status_code,404)
        self.assertEqual(m.app.test_client().get(path).status_code,302)
        other=m.app.test_client()
        with database_session(other) as s:s.update(usuario_id=2,tipo='cliente',conexao_id=ids[0])
        self.assertEqual(other.get(path).status_code,403)
        with m.banco() as conn:self.assertEqual(m.consultar(conn,'SELECT COUNT(*) AS n FROM listing_tasks WHERE conexao_id=ANY(%s)',(ids,))[0]['n'],22)
    finally:
        with m.banco() as conn:
            for table in ('listing_tasks','anuncios','conexoes'):
                m.executar(conn,'DELETE FROM '+table+' WHERE '+('id' if table=='conexoes' else 'conexao_id')+'=ANY(%s)',(ids,))
