import os,time,unittest
from unittest.mock import patch
from auth_test_support import database_session
from listing_kits import init_schema
from test_listing_kits import form
from sales_metrics import reporting_today

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class KitIntegrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
    main.app.config['TESTING']=True
 def test_save_repeat_versions_scope_links_and_no_marketplace_calls(self):
    m=self.m;ids=[];now=int(time.time())
    try:
        with m.banco() as conn:
            init_schema(conn,m.executar);init_schema(conn,m.executar)
            for label in ('Kit A','SEGREDO OUTRA LOJA'):
                ids.append(m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'])
                for item in ['MLB1','MLB2']:
                    m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo,quantidade,atualizado_em,status) VALUES(%s,%s,%s,8,%s,'active')",(ids[-1],item,label,now))
            m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,'MLB99','Somente outra loja')",(ids[1],))
        c=m.app.test_client()
        with database_session(c) as s:s.update(usuario_id=1,tipo='admin',_csrf='csrf-test')
        url=f'/anuncios/{ids[0]}/MLB1/kits';f=dict(form(),_csrf='csrf-test',source_date=reporting_today().isoformat())
        with patch.object(m.requests,'get',side_effect=AssertionError('remote call')):
            self.assertEqual(c.post(url,data=dict(f,_csrf='bad')).status_code,400)
            self.assertEqual(c.post(url,data=dict(f,item_0='MLB99')).status_code,400)
            first=c.post(url,data=f);self.assertEqual(first.status_code,303)
            repeat=c.post(url,data=f);self.assertEqual(repeat.headers['Location'],first.headers['Location'])
            html=c.get(first.headers['Location']);self.assertEqual(html.status_code,200)
            text=html.get_data(as_text=True);self.assertIn('Demanda do kit proposto ainda não validada',text);self.assertIn('4</strong> kit(s)',text);self.assertNotIn('SEGREDO OUTRA LOJA',text)
            changed=c.post(url,data=dict(f,price='60'));self.assertEqual(changed.status_code,400)
            fresh=c.post(url,data=dict(f,price='60',submission_key='n'*32));self.assertEqual(fresh.status_code,303)
        with m.banco() as conn:
            rows=m.consultar(conn,'SELECT id,composition FROM listing_kit_analyses WHERE conexao_id=%s ORDER BY id',(ids[0],))
            self.assertEqual(len(rows),2);self.assertEqual(rows[0]['composition']['costs']['price'],'50');self.assertEqual(rows[1]['composition']['costs']['price'],'60')
            m.executar(conn,"INSERT INTO listing_kit_analyses(conexao_id,item_id,composition,created_by,created_at,submission_key,payload_hash) VALUES(%s,'MLB1',%s::jsonb,1,%s,'foreign','hash')",(ids[1],__import__('json').dumps(rows[0]['composition']),now))
            foreign=m.consultar(conn,'SELECT id FROM listing_kit_analyses WHERE conexao_id=%s',(ids[1],))[0]['id']
        with m.banco() as conn:
            for i in range(10):m.executar(conn,"INSERT INTO listing_kit_analyses(conexao_id,item_id,composition,created_by,created_at,submission_key,payload_hash) VALUES(%s,'MLB1',%s::jsonb,1,%s,%s,'hash')",(ids[0],__import__('json').dumps(rows[0]['composition']),now,'history-'+str(i)))
        first_page=c.get(url).get_data(as_text=True);second_page=c.get(url+'?pagina=2').get_data(as_text=True)
        self.assertEqual(first_page.count('/kits?analise='),10);self.assertEqual(second_page.count('/kits?analise='),2);self.assertIn('Página 2 de 2',c.get(url+'?pagina=999').get_data(as_text=True))
        self.assertEqual(c.get(url+'?analise='+str(foreign)).status_code,404)
        self.assertEqual(c.get(url.replace('MLB1','MLB2')+'?analise='+str(rows[0]['id'])).status_code,404)
        self.assertEqual(m.app.test_client().get(url).status_code,302)
        other=m.app.test_client()
        with database_session(other) as s:s.update(usuario_id=2,tipo='cliente',conexao_id=ids[0])
        self.assertEqual(other.get(url).status_code,403)
    finally:
        with m.banco() as conn:
            for table in ['listing_kit_analyses','anuncios']:m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(ids,))
            m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(ids,))
