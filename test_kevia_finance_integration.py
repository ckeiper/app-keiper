"""Private financial snapshot lifecycle against disposable PostgreSQL only."""
import json
import os
import time
import unittest
from datetime import datetime,timedelta,time as day_time
from unittest.mock import Mock,patch
from decimal import Decimal


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class KeviaFinancialDatabaseTests(unittest.TestCase):
    def test_daily_snapshot_privacy_history_central_manual_review_and_no_get_recalculation(self):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        from auth_test_support import database_session
        from listing_profitability import COMPONENTS
        from profitability_store import load_pair,save
        from sales_metrics import reporting_today,SAO_PAULO
        from keiper_ai_store import run_one
        if main.scheduler.running:main.scheduler.shutdown(wait=False)
        today=reporting_today();end=today-timedelta(days=1);start=end-timedelta(days=6)
        previous_start=start-timedelta(days=7);previous_end=start-timedelta(days=1)
        checked=datetime.combine(today,day_time(10),SAO_PAULO).timestamp()
        item_id='MLB88776655'
        with main.banco() as conn:
            cid=main.consultar(conn,'INSERT INTO conexoes(cliente,status) VALUES(%s,%s) RETURNING id',('KEVIA financial integration','ativa'))[0]['id']
            main.executar(conn,'INSERT INTO anuncios(conexao_id,item_id,titulo,status,quantidade,atualizado_em) VALUES(%s,%s,%s,%s,10,%s)',(cid,item_id,'Produto de teste financeiro','active',int(time.time())))
        try:
            with main.banco() as conn:
                for i in range(14):
                    day=previous_start+timedelta(days=i)
                    main.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,%s)',(cid,day.isoformat(),int(time.time())))
                for oid,day,qty in [('old',previous_end,2),('new',end,1)]:
                    main.executar(conn,'''INSERT INTO pedidos(conexao_id,pedido_id,status,total,moeda,criado_em,pagamentos_json,unidades,vendas_verificado_em,vendas_dia_coleta)
                        VALUES(%s,%s,'paid',%s,'BRL',%s,%s::jsonb,%s,%s,%s)''',(cid,oid,qty*100,day.isoformat()+'T12:00:00-03:00',json.dumps([dict(status='approved')]),qty,int(time.time()),day.isoformat()))
                    main.executar(conn,'INSERT INTO pedidos_itens(conexao_id,pedido_id,item_id,quantidade,preco_unitario) VALUES(%s,%s,%s,%s,100)',(cid,oid,item_id,qty))
                pair=load_pair(conn,main.consultar,cid,item_id,start,end)
                for window,name,cost in [((start,end),'current',30),((previous_start,previous_end),'previous',10)]:
                    save(conn,main.executar,cid,item_id,*window,pair[name],{k:Decimal(cost) for k in COMPONENTS},
                        {k:'Documento privado da integração financeira' for k in COMPONENTS},1,name*8)
            original=main.consultar
            def read(conn,sql,params=None):
                if sql.startswith('SELECT c.id,c.cliente,c.status FROM conexoes c'):
                    sql=sql.replace("WHERE c.status='ativa'","WHERE c.id=%s AND c.status='ativa'")
                    params=(cid,)+params
                return original(conn,sql,params)
            report=dict(eligible=True,reasons=[],current=dict(revenue=100,orders=1),previous=dict(revenue=200,orders=1))
            with patch.dict(os.environ,dict(KEIPER_AI_PAID_ENABLED='false',KEIPER_AI_DAILY_ENABLED='true')),\
                 patch('overview.load_overview',return_value=dict(reports=[report])),\
                 patch('requests.post',side_effect=AssertionError('No provider call for financial evidence')):
                run_one(main.banco,read,main.executar,Mock(),now=checked)
                run_one(main.banco,read,main.executar,Mock(),now=checked)
            with main.banco() as conn:
                runs=original(conn,'SELECT status,result FROM keiper_ai_runs WHERE conexao_id=%s AND day=%s',(cid,today))
            self.assertEqual(len(runs),1)
            self.assertEqual(runs[0]['status'],'completed')
            snapshot=runs[0]['result']['financial']
            self.assertEqual(snapshot['status'],'ready')
            self.assertEqual(snapshot['negative_count'],1)
            self.assertEqual(Decimal(snapshot['negative_contribution_sum']),-80)
            code=snapshot['findings'][0]['code']
            self.assertNotIn('Documento privado',json.dumps(runs[0]['result']))
            client=main.app.test_client()
            with database_session(client) as state:state.update(usuario_id=1,tipo='admin')
            with patch('kevia_finance.load_snapshot',side_effect=AssertionError('GET must use the saved snapshot')),\
                 patch('requests.post',side_effect=AssertionError('GET cannot call provider')):
                response=client.get('/ia-keiper/'+str(cid))
            self.assertEqual(response.status_code,200)
            self.assertIn('id="ky-finance"',response.text)
            self.assertIn('R$ -80,00',response.text)
            self.assertIn('alterações posteriores não estão incluídas',response.text)
            self.assertIn('name="code" value="'+code+'"',response.text)
            with client.session_transaction() as state:
                csrf=state['_csrf'];review_csrf=state['kyra_review_csrf']
            response=client.post('/kyra/revisar/'+str(cid),data=dict(_csrf=csrf,csrf=review_csrf,code=code,state='em_analise'))
            self.assertEqual(response.status_code,303)
            with main.banco() as conn:
                row=original(conn,'SELECT state FROM kyra_reviews WHERE conexao_id=%s AND code=%s',(cid,code))[0]
                self.assertEqual(row['state'],'em_analise')
            response=client.get('/kyra')
            self.assertEqual(response.status_code,200)
            self.assertIn('contribuição documentada negativa',response.text)
            with database_session(client) as state:state.update(tipo='cliente',conexao_id=cid)
            response=client.get('/ia-keiper/'+str(cid))
            self.assertEqual(response.status_code,200)
            self.assertNotIn('id="ky-finance"',response.text)
            self.assertNotIn('Contribuição documentada negativa',response.text)
            self.assertNotIn('R$ -80,00',response.text)
            self.assertNotIn('finance_negative_',response.text)
            self.assertEqual(client.get('/ia-keiper/'+str(cid+99999)).status_code,403)
            self.assertEqual(client.get('/kyra').status_code,403)
            self.assertEqual(client.post('/kyra/revisar/'+str(cid),data=dict(_csrf=csrf,csrf=review_csrf,code=code,state='resolvido')).status_code,403)
            with main.banco() as conn:
                self.assertEqual(len(original(conn,'SELECT id FROM listing_profitability_records WHERE conexao_id=%s',(cid,))),2)
        finally:
            with main.banco() as conn:
                for table in ['keiper_ai_runs','kyra_reviews','listing_profitability_records','pedidos_itens','pedidos','vendas_cobertura','anuncios']:
                    main.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=%s',(cid,))
                main.executar(conn,'DELETE FROM conexoes WHERE id=%s',(cid,))
