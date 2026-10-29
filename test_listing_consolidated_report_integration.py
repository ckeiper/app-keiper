import os,unittest,io
from unittest.mock import patch
from pypdf import PdfReader
from auth_test_support import database_session

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class ConsolidatedDatabaseTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
    main.app.config['TESTING']=True
 def test_actual_pdf_queries_and_scope(self):
    m=self.m;ids=[]
    try:
        with m.banco() as conn:
            for label in ('Consolidated A','SEGREDO OUTRA LOJA'):
                cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'];ids.append(cid)
                m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,'MLB123',%s)",(cid,label))
        c=m.app.test_client()
        with database_session(c) as s:s.update(usuario_id=1,tipo='admin')
        url=f'/anuncios/{ids[0]}/MLB123/relatorio-consolidado'
        with patch.object(m.requests,'get',side_effect=AssertionError('network during report')):
            response=c.get(url+'.pdf?dias=7')
        self.assertEqual(response.status_code,200)
        text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages)
        self.assertIn('Consolidated A',text);self.assertNotIn('SEGREDO OUTRA LOJA',text);self.assertIn('Indisponível',text)
        self.assertEqual(c.get(url.replace('MLB123','MLB999')).status_code,404)
        self.assertEqual(m.app.test_client().get(url).status_code,302)
        other=m.app.test_client()
        with database_session(other) as s:s.update(usuario_id=2,tipo='cliente',conexao_id=ids[0])
        self.assertEqual(other.get(url).status_code,403)
    finally:
        with m.banco() as conn:
            m.executar(conn,'DELETE FROM anuncios WHERE conexao_id=ANY(%s)',(ids,));m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(ids,))
