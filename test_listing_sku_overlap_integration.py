import os,time
import unittest
from auth_test_support import database_session

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class SkuOverlapIntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
    main.app.config['TESTING']=True
 def test_exact_matching_case_preservation_limits_and_isolation(self):
    m=self.m;ids=[];now=int(time.time())
    try:
        with m.banco() as conn:
            for label in ('SKU A','SKU B'):
                ids.append(m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'])
            for i in range(12):m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo,sku,status,quantidade,atualizado_em) VALUES(%s,%s,%s,%s,'active',0,%s)",(ids[0],'MLB'+str(i),'Produto '+str(i),' ABC ' if i==0 else 'ABC',now))
            for item,sku in [('MLB90','abc'),('MLB91','AB C'),('MLB92',' \t\n'),('MLB93',None)]:m.executar(conn,'INSERT INTO anuncios(conexao_id,item_id,titulo,sku) VALUES(%s,%s,%s,%s)',(ids[0],item,item,sku))
            for i in range(2):m.executar(conn,'INSERT INTO anuncios(conexao_id,item_id,titulo,sku) VALUES(%s,%s,%s,%s)',(ids[1],'MLB'+str(i),'SEGREDO OUTRA LOJA','ABC'))
        c=m.app.test_client()
        with database_session(c) as s:s.update(usuario_id=1,tipo='admin')
        path=f'/anuncios/{ids[0]}/skus-repetidos';r=c.get(path);text=r.get_data(as_text=True)
        self.assertEqual(r.status_code,200);self.assertIn('12 anúncios com esse SKU',text);self.assertEqual(text.count('class="sku-item"'),10);self.assertNotIn('SEGREDO OUTRA LOJA',text)
        self.assertIn('Nenhum SKU repetido',c.get(path+'?sku=abc').get_data(as_text=True))
        self.assertIn('12 anúncios com esse SKU',c.get(path+'?sku=ABC').get_data(as_text=True))
        self.assertIn('Nenhum SKU repetido',c.get(path+"?sku=%27OR1%3D1").get_data(as_text=True))
        other=m.app.test_client()
        with database_session(other) as s:s.update(usuario_id=2,tipo='cliente',conexao_id=ids[0])
        self.assertEqual(other.get(path).status_code,403)
        with m.banco() as conn:self.assertEqual(m.consultar(conn,'SELECT COUNT(*) AS n FROM anuncios WHERE conexao_id=%s',(ids[0],))[0]['n'],16)
    finally:
        with m.banco() as conn:
            m.executar(conn,'DELETE FROM anuncios WHERE conexao_id=ANY(%s)',(ids,));m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(ids,))
