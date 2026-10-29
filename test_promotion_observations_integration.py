import os,time,json,unittest
from datetime import timedelta
from unittest.mock import Mock,patch
from types import SimpleNamespace
from auth_test_support import database_session
from promotion_observations import init_schema,record
from sales_metrics import reporting_today
from test_promotion_observations import promotion

@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class PromotionReadingDatabaseTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
    import main
    cls.m=main
    if main.scheduler.running:main.scheduler.shutdown(wait=False)
    main.app.config['TESTING']=True
 def test_collector_history_error_scope_and_exact_period_costs(self):
    m=self.m;ids=[];now=int(time.time());today=reporting_today();first=today-timedelta(days=14)
    p=promotion(start=first.isoformat()+'T00:00:00-03:00',end=(today-timedelta(days=1)).isoformat()+'T00:00:00-03:00')
    try:
        with m.banco() as conn:
            init_schema(conn,m.executar);init_schema(conn,m.executar)
            for name in ['Promo A','SEGREDO OUTRA LOJA']:
                cid=m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(name,))[0]['id'];ids.append(cid)
                m.executar(conn,"INSERT INTO anuncios(conexao_id,item_id,titulo,status) VALUES(%s,'MLB123',%s,'active')",(cid,name))
                snap=dict(checked_at=now,promotions=[p],error=None)
                record(conn,m.executar,cid,'MLB123',snap);record(conn,m.executar,cid,'MLB123',snap);record(conn,m.executar,cid,'MLB123',dict(snap,checked_at=now+1))
            # Complete empty sales/visit history yields true zero, never guessed costs.
            for n in range(7,22):
                day=(today-timedelta(days=n)).isoformat()
                m.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,%s)',(ids[0],day,now))
            records=m.consultar(conn,'SELECT id FROM listing_promotion_readings WHERE conexao_id=%s',(ids[0],));self.assertEqual(len(records),1);reading=records[0]['id']
            foreign=m.consultar(conn,'SELECT id FROM listing_promotion_readings WHERE conexao_id=%s',(ids[1],))[0]['id']
        c=m.app.test_client()
        with database_session(c) as s:s.update(usuario_id=1,tipo='admin')
        url=f'/anuncios/{ids[0]}/MLB123/promocoes-resultados'
        with patch.object(m.requests,'get',side_effect=AssertionError('network during report')):
            response=c.get(url+'?consulta='+str(reading));self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True);self.assertIn('Comparação descritiva por calendário informado',text);self.assertIn('R$ 0,00',text);self.assertNotIn('SEGREDO OUTRA LOJA',text);self.assertIn('custos documentados',text)
        self.assertEqual(c.get(url+'?consulta='+str(foreign)).status_code,404)
        with m.banco() as conn:
            record(conn,m.executar,ids[0],'MLB123',dict(checked_at=now,attempted_at=now+1,error='HTTP 403 private',promotions=[p]))
        text=c.get(url).get_data(as_text=True);self.assertIn('Consulta indisponível',text);self.assertNotIn('Oferta consultada',text);self.assertNotIn('private',text)
        self.assertEqual(m.app.test_client().get(url).status_code,302)
        # Exercise real collector hook without extra requests or marketplace writes.
        from listing_sync import sync_promotions
        get=Mock(return_value=SimpleNamespace(status_code=200,headers={},json=lambda:[]))
        sync_promotions(ids[0],'synthetic',m.banco,m.consultar,m.executar,get,m.registrar_erro,include_sale_price=False)
        self.assertEqual(get.call_count,1)
        with m.banco() as conn:self.assertGreaterEqual(m.consultar(conn,'SELECT COUNT(*) AS n FROM listing_promotion_readings WHERE conexao_id=%s',(ids[0],))[0]['n'],3)
    finally:
        with m.banco() as conn:
            for table in ['listing_promotion_readings','vendas_cobertura','anuncios']:m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(ids,))
            m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(ids,))
