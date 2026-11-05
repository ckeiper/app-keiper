"""Real scoped reads against disposable PostgreSQL, with no external requests."""
import os
import unittest
from datetime import timedelta
from unittest.mock import patch
from auth_test_support import database_session
from sales_metrics import reporting_today
from listing_weekly_pattern import window


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class PatternIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m=main
        if main.scheduler.running:main.scheduler.shutdown(wait=False)
        main.app.config['TESTING']=True

    def test_coverage_store_isolation_and_integrity_gates(self):
        m=self.m;ids=[];start,end=window(reporting_today())
        try:
            with m.banco() as conn:
                for label,qty in [('Weekly A',3),('Weekly B',987)]:
                    cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(label,))[0]['id'];ids.append(cid)
                    m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo) VALUES(%s,'MLB123',%s)",(cid,label))
                    for i in range(56):
                        m.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,1)',(cid,(start+timedelta(days=i)).isoformat()))
                    m.executar(conn,'''INSERT INTO pedidos(conexao_id,pedido_id,status,total,moeda,criado_em,pagamentos_json,unidades,vendas_verificado_em)
                        VALUES(%s,'weekly-test','paid',%s,'BRL',%s,'[{"status":"approved"}]',%s,1)''',(cid,qty*10,start.isoformat()+'T12:00:00-03:00',qty))
                    m.executar(conn,"INSERT INTO pedidos_itens(conexao_id,pedido_id,item_id,quantidade,preco_unitario) VALUES(%s,'weekly-test','MLB123',%s,10)",(cid,qty))
            client=m.app.test_client()
            with database_session(client) as s:s.update(usuario_id=1,tipo='admin')
            path=f'/anuncios/{ids[0]}/MLB123/padrao-semanal'
            with patch.object(m.requests,'get',side_effect=AssertionError('external call')):
                text=client.get(path).get_data(as_text=True)
            self.assertIn('<strong>3</strong><span>Unidades vendidas',text)
            self.assertNotIn('Weekly B',text);self.assertIn('56 de 56 dias',text)
            self.assertEqual(client.get(path.replace('MLB123','MLB999')).status_code,404)
            with m.banco() as conn:m.executar(conn,'DELETE FROM vendas_cobertura WHERE conexao_id=%s AND dia=%s',(ids[0],start.isoformat()))
            text=client.get(path).get_data(as_text=True)
            self.assertIn('55 de 56 dias',text);self.assertNotIn('class="wp-chart"',text)
            with m.banco() as conn:
                m.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,1)',(ids[0],start.isoformat()))
                m.executar(conn,'DELETE FROM pedidos_itens WHERE conexao_id=%s',(ids[0],))
            self.assertIn('vínculo de anúncios incompleto',client.get(path).get_data(as_text=True))
            other=m.app.test_client()
            with database_session(other) as s:s.update(usuario_id=2,tipo='cliente',conexao_id=ids[0])
            self.assertEqual(other.get(path).status_code,403)
        finally:
            with m.banco() as conn:
                for table in ('pedidos_itens','pedidos','vendas_cobertura','anuncios'):
                    m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(ids,))
                m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(ids,))
