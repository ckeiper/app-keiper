from auth_test_support import database_session
import os
import unittest


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL URL not configured')
class ListingPaginationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m=main
        if main.scheduler.running: main.scheduler.shutdown(wait=False)
        main.iniciar_banco()
        main.app.config['TESTING']=True

    def test_authenticated_pages_keep_store_totals_and_permissions(self):
        m=self.m
        with m.banco() as conn:
            cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES('Pagination','ativa') RETURNING id")[0]['id']
            m.executar(conn,'''INSERT INTO anuncios(conexao_id,item_id,titulo,preco,
                quantidade,fotos,vendidos,status)
                SELECT %s,'PAGE-'||n,'Pagination product '||n,10,1,10,100-n,'active'
                FROM generate_series(1,45) n''',(cid,))
        client=m.app.test_client()
        with database_session(client) as session:
            session['usuario_id']=1
            session['tipo']='admin'
        try:
            for suffix,count,label in [('',20,'Mostrando 1–20 de 45'),
                                        ('?pagina=2',20,'Mostrando 21–40 de 45'),
                                        ('?pagina=999',5,'Mostrando 41–45 de 45'),
                                        ('?por_pagina=50',45,'Mostrando 1–45 de 45')]:
                response=client.get('/anuncios/'+str(cid)+suffix)
                self.assertEqual(response.status_code,200)
                view=response.get_data(as_text=True)
                self.assertEqual(view.count('Pagination product '),count)
                self.assertIn(label,view)
                self.assertIn("<div class='num'>45</div>",view)
                self.assertIn('Peso cadastrado',view)
                self.assertIn('Peso logístico',view)
            with database_session(client) as session:
                session['tipo']='cliente'
                session['conexao_id']=cid+1000
            denied=client.get('/anuncios/'+str(cid)+'?pagina=2').get_data(as_text=True)
            self.assertNotIn('Pagination product',denied)
        finally:
            with m.banco() as conn:
                m.executar(conn,'DELETE FROM anuncios WHERE conexao_id=%s',(cid,))
                m.executar(conn,'DELETE FROM conexoes WHERE id=%s',(cid,))
