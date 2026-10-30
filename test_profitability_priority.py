import copy
import json
import os
import time
import unittest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock,patch

from listing_profitability import COMPONENTS
from listing_ranking import ranking_metrics
from listing_priority_queue import prioritize,render
from listing_priority_evidence import enrich_priorities
from profitability_store import summarize_context,save
from profitability_priority import build_signals,load_signals
from test_profitability import START,END

OLD_START=START-timedelta(days=7);OLD_END=START-timedelta(days=1)


def data(count=1):
    ids=['MLB'+str(100+i) for i in range(count)]
    orders=[];items=[]
    for oid,day,quantity in [('new',END,1),('old',OLD_END,2)]:
        orders.append(dict(conexao_id=42,pedido_id=oid,status='paid',total=quantity*100*count,
            moeda='BRL',criado_em=day.isoformat()+'T12:00:00-03:00',pagamentos_json=[dict(status='approved')],
            unidades=quantity*count,vendas_dia_coleta=day.isoformat()))
        for item_id in ids:
            items.append(dict(conexao_id=42,pedido_id=oid,item_id=item_id,quantidade=quantity,preco_unitario=100))
    coverage=[(OLD_START+timedelta(days=i)).isoformat() for i in range(14)]
    context=dict(orders=orders,items=items,coverage=coverage,pending=False)
    ranking=ranking_metrics(orders,items,coverage,ids,end=END,days=7)
    records=[]
    for item_id in ids:
        for window,cost in [((START,END),30),((OLD_START,OLD_END),10)]:
            basis=summarize_context(context,42,item_id,*window)
            records.append(dict(id=len(records)+1,conexao_id=42,item_id=item_id,inicio=window[0],fim=window[1],
                gross_items=basis['gross_items'],units=basis['units'],sales_fingerprint=basis['fingerprint'],
                costs={key:str(cost) for key in COMPONENTS},sources={key:'Documento conferido deste anúncio e período' for key in COMPONENTS}))
    return context,ranking,records


def signals(context,ranking,records):
    return build_signals(42,ranking,context['orders'],context['items'],records,START,END,OLD_START,OLD_END)


class FinancialPriorityTests(unittest.TestCase):
    def test_reuses_page_fingerprint_and_matches_documented_negative_margin(self):
        context,ranking,records=data()
        result=signals(context,ranking,records)['MLB100']
        self.assertTrue(result['margin_verified'])
        self.assertEqual(result['margin_current_pct'],-80)
        self.assertEqual(result['margin_previous_pct'],70)
        self.assertEqual(result['contribution_current'],-80)
        queue=prioritize(ranking,verified_signals_by_item={'MLB100':result})
        findings=queue['items'][0]['additional_findings']
        self.assertEqual([f['code'] for f in findings],['negative_contribution','margin_decline'])
        self.assertIn('70,00% para -80,00%',findings[1]['evidence'])

    def test_missing_previous_costs_do_not_become_zero_or_suppress_current_negative_evidence(self):
        context,ranking,records=data()
        result=signals(context,ranking,records[:1])['MLB100']
        self.assertFalse(result['margin_verified'])
        self.assertIsNone(result['margin_previous_pct'])
        queue=prioritize(ranking,verified_signals_by_item={'MLB100':result})
        self.assertEqual([f['code'] for f in queue['items'][0]['additional_findings']],['negative_contribution'])
        self.assertIn('margem',queue['items'][0]['data_limitations'])

    def test_newest_invalid_record_never_falls_back_to_an_old_valid_version(self):
        context,ranking,records=data()
        newer=dict(copy.deepcopy(records[0]),id=99,sales_fingerprint='b'*64)
        result=signals(context,ranking,records+[newer])['MLB100']
        self.assertFalse(result['margin_verified'])
        self.assertFalse(result['contribution_verified'])
        queue=prioritize(ranking,verified_signals_by_item={'MLB100':result})
        self.assertEqual(queue['items'][0]['additional_findings'],[])

    def test_missing_source_blocks_only_the_affected_financial_evidence(self):
        context,ranking,records=data()
        records[0]['sources']['taxes']=''
        result=signals(context,ranking,records)['MLB100']
        self.assertFalse(result['margin_verified'])
        self.assertFalse(result['contribution_verified'])
        self.assertEqual(result['margin_previous_pct'],70)

    def test_same_revenue_and_units_with_different_order_identity_invalidates_record(self):
        context,ranking,records=data()
        context['orders'][0]['pedido_id']='other-id'
        context['items'][0]['pedido_id']='other-id'
        new_ranking=ranking_metrics(context['orders'],context['items'],context['coverage'],['MLB100'],end=END,days=7)
        self.assertEqual(new_ranking['rows'],ranking['rows'])
        self.assertFalse(signals(context,new_ranking,records)['MLB100']['margin_verified'])

    def test_foreign_store_unknown_listing_and_wrong_period_records_are_ignored(self):
        context,ranking,records=data()
        changed=[dict(records[0],conexao_id=43),dict(records[0],item_id='MLB999'),dict(records[0],inicio=OLD_END)]
        self.assertEqual(signals(context,ranking,changed),{})

    def test_incomplete_ranking_and_unsupported_window_do_not_query_financial_records(self):
        context,ranking,records=data();query=Mock()
        self.assertEqual(load_signals(None,query,42,dict(available=False),[],[],END,7),{})
        self.assertEqual(load_signals(None,query,42,ranking,[],[],END,90),{})
        query.assert_not_called()

    def test_many_listings_use_one_store_and_period_scoped_financial_read(self):
        context,ranking,records=data(10);query=Mock(return_value=records)
        result=load_signals(None,query,42,ranking,context['orders'],context['items'],END,7)
        self.assertEqual(query.call_count,1)
        self.assertEqual(len(result),10)
        self.assertTrue(all(r['margin_verified'] for r in result.values()))
        self.assertIn('WHERE conexao_id=%s',query.call_args.args[1])
        self.assertIn('DISTINCT ON (item_id,inicio,fim)',query.call_args.args[1])
        self.assertEqual(query.call_args.args[2],(42,START,END,OLD_START,OLD_END))

    def test_financial_evidence_does_not_reorder_existing_gross_loss_queue(self):
        context,ranking,records=data(2)
        ranking['rows']['MLB101']['previous_value']=Decimal('1000')
        result=signals(context,ranking,records)
        before=prioritize(ranking);after=prioritize(ranking,verified_signals_by_item=result)
        self.assertEqual([r['item_id'] for r in before['items']],[r['item_id'] for r in after['items']])
        self.assertEqual(after['items'][0]['item_id'],'MLB101')

    def test_invalid_flags_and_non_finite_values_do_not_claim_confirmed_evidence(self):
        queue=dict(available=True,items=[dict(item_id='MLB1')])
        for value in [None,True,'NaN','Infinity']:
            output=enrich_priorities(queue,{'MLB1':dict(stock_verified=True,stock=value,
                margin_verified=True,margin_current_pct=value,margin_previous_pct=20)})
            self.assertEqual(output['items'][0]['additional_findings'],[])
            self.assertEqual(output['items'][0]['data_limitations'],['estoque','margem'])

    def test_legacy_signed_margins_can_fall_below_zero(self):
        queue=dict(available=True,items=[dict(item_id='MLB1')])
        output=enrich_priorities(queue,{'MLB1':dict(margin_verified=True,margin_current_pct=-5,margin_previous_pct=5)})
        self.assertEqual(output['items'][0]['additional_findings'][0]['code'],'margin_decline')


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class FinancialPriorityDatabaseTests(unittest.TestCase):
    def test_actual_queue_matches_recorded_costs_and_never_exposes_them_to_clients(self):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        from auth_test_support import database_session
        from sales_metrics import reporting_today
        from profitability_store import load_pair
        if main.scheduler.running:main.scheduler.shutdown(wait=False)
        end=reporting_today()-timedelta(days=1);start=end-timedelta(days=6)
        previous_end=start-timedelta(days=1);previous_start=start-timedelta(days=7)
        item_id='MLB55443322'
        with main.banco() as conn:
            cid=main.consultar(conn,'INSERT INTO conexoes(cliente) VALUES(%s) RETURNING id',('Teste Fila Financeira',))[0]['id']
            main.executar(conn,'INSERT INTO anuncios(conexao_id,item_id,titulo,status,quantidade,atualizado_em) VALUES(%s,%s,%s,%s,20,%s)',(cid,item_id,'Produto com custo documentado','active',int(time.time())))
        try:
            with main.banco() as conn:
                for i in range(14):
                    day=previous_start+timedelta(days=i)
                    main.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,1)',(cid,day.isoformat()))
                for oid,day,qty in [('old',previous_end,2),('new',end,1)]:
                    main.executar(conn,'''INSERT INTO pedidos(conexao_id,pedido_id,status,total,moeda,criado_em,pagamentos_json,unidades,vendas_verificado_em,vendas_dia_coleta)
                        VALUES(%s,%s,'paid',%s,'BRL',%s,%s::jsonb,%s,1,%s)''',(cid,oid,qty*100,day.isoformat()+'T12:00:00-03:00',json.dumps([dict(status='approved')]),qty,day.isoformat()))
                    main.executar(conn,'INSERT INTO pedidos_itens(conexao_id,pedido_id,item_id,quantidade,preco_unitario) VALUES(%s,%s,%s,%s,100)',(cid,oid,item_id,qty))
                pair=load_pair(conn,main.consultar,cid,item_id,start,end)
                for window,name,cost in [((start,end),'current',30),((previous_start,previous_end),'previous',10)]:
                    save(conn,main.executar,cid,item_id,*window,pair[name],{k:Decimal(cost) for k in COMPONENTS},
                         {k:'Fonte financeira privada de teste' for k in COMPONENTS},1,name*8)
            client=main.app.test_client()
            with database_session(client) as state:state.update(usuario_id=1,tipo='admin')
            url=f'/ranking-anuncios/{cid}?dias=7&modo=prioridades'
            with patch('main.requests.get',side_effect=AssertionError('No API during queue render')):
                output=client.get(url)
            self.assertEqual(output.status_code,200)
            self.assertIn('Contribuição documentada negativa: R$ -80,00',output.text)
            self.assertIn('70,00% para -80,00%',output.text)
            self.assertNotIn('Fonte financeira privada de teste',output.text)
            with database_session(client) as state:state.update(tipo='cliente',conexao_id=cid)
            original=main.consultar
            financial_reads=[]
            def read(conn,sql,params=None):
                if 'listing_profitability_records' in sql:financial_reads.append(sql)
                return original(conn,sql,params)
            with patch.object(main,'consultar',side_effect=read):
                output=client.get(url)
            self.assertEqual(output.status_code,200)
            self.assertNotIn('Contribuição documentada negativa',output.text)
            self.assertNotIn('Margem documentada',output.text)
            self.assertEqual(financial_reads,[])
            with database_session(client) as state:state.update(tipo='admin')
            with main.banco() as conn:
                main.executar(conn,'UPDATE pedidos_itens SET preco_unitario=110 WHERE conexao_id=%s AND pedido_id=%s',(cid,'new'))
            output=client.get(url)
            self.assertNotIn('Contribuição documentada negativa',output.text)
            self.assertNotIn('Margem documentada caiu',output.text)
            with main.banco() as conn:
                self.assertEqual(len(main.consultar(conn,'SELECT id FROM listing_profitability_records WHERE conexao_id=%s',(cid,))),2)
        finally:
            with main.banco() as conn:
                for table in ['listing_profitability_records','pedidos_itens','pedidos','vendas_cobertura','anuncios']:
                    main.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=%s',(cid,))
                main.executar(conn,'DELETE FROM conexoes WHERE id=%s',(cid,))
