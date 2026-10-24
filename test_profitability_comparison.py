import contextlib
import json
import os
import unittest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock,patch

from listing_profitability import COMPONENTS
from profitability_store import load_pair,load_sales,save,result_for
from profitability_comparison import compare
from profitability_comparison_view import render_comparison
from test_profitability import DAY,START,END,fixture_pair,record,summary


def pair_records():
    pair=fixture_pair()
    current=record()
    previous=dict(record(),id=2,inicio=pair['previous_start'],fim=pair['previous_end'])
    return pair,current,previous


class ProfitabilityComparisonTests(unittest.TestCase):
    def test_decomposition_reconciles_and_compares_margin_in_percentage_points(self):
        pair,current,previous=pair_records()
        pair['previous'].update(gross_items=Decimal('200'))
        previous.update(gross_items=Decimal('200'))
        current['costs']=dict(current['costs'],advertising=Decimal('100'))
        result=compare(pair['current'],pair['previous'],current,previous)
        self.assertTrue(result['available'])
        self.assertEqual(result['contribution_delta'],Decimal('10'))
        self.assertEqual(result['margin_delta_pp'],Decimal('-20'))
        self.assertEqual(sum(r['impact'] for r in result['rows']),Decimal('10'))
        ads=next(r for r in result['rows'] if r['key']=='advertising')
        self.assertEqual(ads['delta'],Decimal('90'))
        self.assertEqual(ads['impact'],Decimal('-90'))
        self.assertEqual([f['code'] for f in result['findings']],['margin_decline','advertising'])
        self.assertEqual(result['current']['contribution'],Decimal('150'))
        self.assertEqual(result['previous']['contribution'],Decimal('140'))

    def test_volume_growth_alone_does_not_generate_cost_pressure_findings(self):
        pair,current,previous=pair_records()
        pair['current'].update(gross_items=600,units=6)
        current.update(gross_items=600,units=6,costs={k:Decimal('20') for k in COMPONENTS})
        result=compare(pair['current'],pair['previous'],current,previous)
        self.assertTrue(result['available'])
        self.assertEqual(result['margin_delta_pp'],0)
        self.assertEqual(result['findings'],[])
        self.assertEqual(result['contribution_delta'],240)
        self.assertTrue(all(r['share_delta_pp']==0 for r in result['rows'][1:]))

    def test_missing_cost_source_coverage_or_stale_sales_do_not_become_zero(self):
        for broken in ['no_record','no_source','stale','unverified']:
            pair,current,previous=pair_records()
            if broken=='no_record':previous=None
            if broken=='no_source':previous['sources']=dict(previous['sources'],advertising='')
            if broken=='stale':previous['sales_fingerprint']='b'*64
            if broken=='unverified':pair['previous'].update(orders=None,reason='Sem cobertura')
            result=compare(pair['current'],pair['previous'],current,previous)
            with self.subTest(broken=broken):
                self.assertFalse(result['available'])
                self.assertIsNone(result['contribution_delta'])
                self.assertEqual(result['rows'],[])
                self.assertEqual(result['findings'],[])

    def test_negative_margins_are_comparable_without_clamping(self):
        pair,current,previous=pair_records()
        current['costs']={k:Decimal('100') for k in COMPONENTS}
        previous['costs']={k:Decimal('75') for k in COMPONENTS}
        result=compare(pair['current'],pair['previous'],current,previous)
        self.assertEqual(result['current']['margin_pct'],-100)
        self.assertEqual(result['previous']['margin_pct'],-50)
        self.assertEqual(result['margin_delta_pp'],-50)
        self.assertIn('negative_contribution',[f['code'] for f in result['findings']])
        self.assertIn('margin_decline',[f['code'] for f in result['findings']])

    def test_verified_zero_revenue_has_no_margin_or_cost_share_inference(self):
        pair,current,previous=pair_records()
        pair['previous'].update(gross_items=0,units=0)
        previous.update(gross_items=0,units=0)
        result=compare(pair['current'],pair['previous'],current,previous)
        self.assertTrue(result['available'])
        self.assertIsNone(result['margin_delta_pp'])
        self.assertTrue(all(r['share_delta_pp'] is None for r in result['rows']))
        self.assertEqual(result['findings'],[])
        self.assertEqual(result['contribution_delta'],300)

    def test_nonadjacent_overlapping_and_different_length_periods_are_rejected(self):
        for change in [dict(end=END.isoformat()),dict(start=(START-timedelta(days=6)).isoformat()),dict(start='invalid'),dict(end='1900-01-01')]:
            pair,current,previous=pair_records();pair['previous'].update(change)
            self.assertFalse(compare(pair['current'],pair['previous'],current,previous)['available'])

    def test_revenue_unchanged_cost_decrease_has_positive_arithmetic_effect(self):
        pair,current,previous=pair_records()
        current['costs']=dict(current['costs'],seller_shipping=Decimal('5'))
        result=compare(pair['current'],pair['previous'],current,previous)
        row=next(r for r in result['rows'] if r['key']=='seller_shipping')
        self.assertEqual(row['impact'],5)
        self.assertEqual(result['contribution_delta'],5)
        self.assertEqual(result['findings'],[])

    def test_current_negative_contribution_can_be_shown_without_inventing_previous_costs(self):
        pair,current,previous=pair_records()
        current['costs']={k:Decimal('100') for k in COMPONENTS}
        result=compare(pair['current'],pair['previous'],current,None)
        self.assertFalse(result['available'])
        self.assertEqual([f['code'] for f in result['findings']],['negative_contribution'])
        self.assertIsNone(result['margin_delta_pp'])

    def test_view_is_read_only_explains_limits_and_links_to_exact_previous_period(self):
        pair,current,previous=pair_records()
        current['costs']=dict(current['costs'],advertising=Decimal('100'))
        result=compare(pair['current'],pair['previous'],current,previous)
        result['findings'][0]['title']='<script>x</script>'
        output=render_comparison(result,START,END,pair['previous_start'],pair['previous_end'],current,previous)
        self.assertIn('&lt;script&gt;',output)
        self.assertNotIn('<script>',output)
        self.assertNotIn('<form',output)
        self.assertIn('sem sobreposição',output)
        self.assertIn('não é uma projeção de recuperação',output)
        self.assertIn('inicio=2026-10-10',output)
        self.assertIn('fim=2026-10-16',output)
        self.assertIn('registro atual #1',output)
        self.assertIn('registro anterior #2',output)

    def test_sub_display_precision_does_not_create_a_zero_point_alert(self):
        pair,current,previous=pair_records()
        for name,entry in [('current',current),('previous',previous)]:
            pair[name]['gross_items']=Decimal('1000000');entry['gross_items']=Decimal('1000000')
        current['costs']=dict(current['costs'],advertising=Decimal('10.01'))
        result=compare(pair['current'],pair['previous'],current,previous)
        self.assertEqual(result['contribution_delta'],Decimal('-.01'))
        self.assertEqual(result['findings'],[])
        from profitability_comparison_view import points,signed_money
        self.assertEqual(points(Decimal('-0.0001')),'0,00 p.p.')
        self.assertEqual(signed_money(Decimal('-0.0001')),'R$ 0,00')

    def test_comparison_outside_supported_history_does_not_read_extra_old_orders(self):
        query=Mock(side_effect=[[],[],[],[dict(pending=False)]])
        pair=load_pair(None,query,42,'MLB100',START,END,earliest=START)
        self.assertEqual(query.call_count,4)
        self.assertTrue(pair['previous']['outside_window'])
        self.assertEqual(query.call_args_list[0].args[2][3],START.isoformat())
        current=record();result=compare(pair['current'],pair['previous'],current,None)
        output=render_comparison(result,START,END,pair['previous_start'],pair['previous_end'],previous_accessible=False)
        self.assertNotIn('pf-source-link" href=',output)
        self.assertIn('fora da janela',output)

    def test_one_context_keeps_four_reads_and_separate_period_fingerprints(self):
        coverage=[dict(dia=(START-timedelta(days=7)+timedelta(days=i)).isoformat()) for i in range(14)]
        query=Mock(side_effect=[[],[],coverage,[dict(pending=False)]])
        pair=load_pair(None,query,42,'MLB100',START,END)
        self.assertEqual(query.call_count,4)
        self.assertEqual(pair['current']['gross_items'],0)
        self.assertEqual(pair['previous']['gross_items'],0)
        self.assertNotEqual(pair['current']['fingerprint'],pair['previous']['fingerprint'])
        self.assertEqual(query.call_args_list[0].args[2][1:],('2026-10-09','2026-10-24','2026-10-10','2026-10-23'))
        for call in query.call_args_list:
            self.assertIn('conexao_id=%s',call.args[1]);self.assertEqual(call.args[2][0],42)

    def test_current_fingerprint_is_unchanged_by_extra_previous_window_rows(self):
        orders=[];items=[]
        for i,day in enumerate([START-timedelta(days=1),END]):
            orders.append(dict(conexao_id=42,pedido_id=str(i),status='paid',total=100,moeda='BRL',criado_em=day.isoformat()+'T12:00:00-03:00',pagamentos_json=[dict(status='approved')],unidades=1))
            items.append(dict(conexao_id=42,pedido_id=str(i),item_id='MLB100',quantidade=1,preco_unitario=100))
        coverage=[dict(dia=(START-timedelta(days=7)+timedelta(days=i)).isoformat()) for i in range(14)]
        query=Mock(side_effect=[orders,items,coverage,[dict(pending=False)]])
        pair=load_pair(None,query,42,'MLB100',START,END)
        query=Mock(side_effect=[orders[-1:],items[-1:],coverage[7:],[dict(pending=False)]])
        single=load_sales(None,query,42,'MLB100',START,END)
        self.assertEqual(pair['current'],single)
        self.assertEqual(pair['previous']['gross_items'],100)


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class ProfitabilityComparisonDatabaseTests(unittest.TestCase):
    def test_actual_page_rechecks_both_periods_and_suppresses_stale_comparison(self):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        from auth_test_support import database_session
        from sales_metrics import reporting_today
        if main.scheduler.running:main.scheduler.shutdown(wait=False)
        end=reporting_today()-timedelta(days=1);start=end-timedelta(days=6)
        previous_end=start-timedelta(days=1);previous_start=start-timedelta(days=7)
        with main.banco() as conn:
            cid=main.consultar(conn,'INSERT INTO conexoes(cliente) VALUES(%s) RETURNING id',('Teste Comparação Financeira',))[0]['id']
            main.executar(conn,'INSERT INTO anuncios(conexao_id,item_id) VALUES(%s,%s)',(cid,'MLB99887766'))
        try:
            with main.banco() as conn:
                for n in range(14):
                    day=previous_start+timedelta(days=n)
                    main.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,%s)',(cid,day.isoformat(),1))
                for oid,day,price in [('old',previous_end,100),('new',end,150)]:
                    main.executar(conn,'''INSERT INTO pedidos(conexao_id,pedido_id,status,total,moeda,criado_em,pagamentos_json,unidades,vendas_verificado_em)
                        VALUES(%s,%s,'paid',%s,'BRL',%s,%s::jsonb,2,1)''',(cid,oid,price*2,day.isoformat()+'T12:00:00-03:00',json.dumps([dict(status='approved')])))
                    main.executar(conn,'''INSERT INTO pedidos_itens(conexao_id,pedido_id,item_id,quantidade,preco_unitario) VALUES(%s,%s,%s,2,%s)''',(cid,oid,'MLB99887766',price))
                pair=load_pair(conn,main.consultar,cid,'MLB99887766',start,end)
                for name,first,last,ads in [('current',start,end,100),('previous',previous_start,previous_end,10)]:
                    costs={k:Decimal('10') for k in COMPONENTS};costs['advertising']=Decimal(ads)
                    sources={k:'Documento do período e anúncio de teste' for k in COMPONENTS}
                    save(conn,main.executar,cid,'MLB99887766',first,last,pair[name],costs,sources,1,name*8)
            client=main.app.test_client()
            with database_session(client) as state:state.update(usuario_id=1,tipo='admin')
            path=f'/anuncios/{cid}/MLB99887766/rentabilidade?inicio={start}&fim={end}'
            with patch('main.requests.get',side_effect=AssertionError('API request during financial view')):
                response=client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertIn('Evolução da contribuição e da margem',response.text)
            self.assertIn('+ R$ 10,00',response.text)
            self.assertIn('-20,00 p.p.',response.text)
            self.assertIn('Publicidade do anúncio com maior participação',response.text)
            with main.banco() as conn:
                main.executar(conn,'UPDATE pedidos_itens SET preco_unitario=170 WHERE conexao_id=%s AND pedido_id=%s',(cid,'new'))
            response=client.get(path)
            self.assertIn('As vendas mudaram',response.text)
            self.assertNotIn('class="pf-comparison-table"',response.text)
            with main.banco() as conn:
                records=main.consultar(conn,'SELECT id FROM listing_profitability_records WHERE conexao_id=%s',(cid,))
                self.assertEqual(len(records),2)
            with database_session(client) as state:state.update(tipo='cliente',conexao_id=cid)
            self.assertEqual(client.get(path).status_code,403)
        finally:
            with main.banco() as conn:
                for table in ['listing_profitability_records','pedidos_itens','pedidos','vendas_cobertura','anuncios']:
                    main.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=%s',(cid,))
                main.executar(conn,'DELETE FROM conexoes WHERE id=%s',(cid,))
