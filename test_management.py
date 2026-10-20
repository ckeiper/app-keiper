import os
import time
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from management_data import build_management, selection, advertising
from management_view import render_management
from sales_metrics import SAO_PAULO


class ManagementFactsTests(unittest.TestCase):
    def setUp(self):
        self.today=date(2026,10,20)
        self.bounds=selection({},self.today)
        self.now=int(datetime(2026,10,20,12,tzinfo=SAO_PAULO).timestamp())
        self.coverage=[dict(dia=(self.today-timedelta(days=i)).isoformat(),atualizado_em=self.now) for i in range(1,15)]
        self.listings=[dict(item_id='MLB1000001',titulo='Anúncio <script>',status='active',quantidade=2,
                            preco=100,custo=None,fotos=3,clips=0,tags='[]',atualizado_em=self.now)]
        self.orders=[];self.items=[]
        for i in range(6):
            self.add_order('old'+str(i),'2026-10-12',1)
        self.add_order('current','2026-10-19',4)
        self.visits=[dict(item_id='MLB1000001',visits_current=10,days_current=7)]
        self.ads=[dict(data=(self.today-timedelta(days=i)).isoformat(),gasto=10,faturamento=50,
                       impressoes=100,cliques=10) for i in range(1,15)]

    def add_order(self,key,day,qty):
        self.orders.append(dict(conexao_id=1,pedido_id=key,status='paid',total=100*qty,moeda='BRL',
                                criado_em=day+'T12:00:00-03:00',pagamentos_json=[{'status':'approved'}],unidades=qty))
        self.items.append(dict(conexao_id=1,pedido_id=key,item_id='MLB1000001',quantidade=qty,preco_unitario=100))

    def build(self,**changes):
        args=dict(listings=self.listings,orders=self.orders,items=self.items,coverage=self.coverage,
                  visits=self.visits,ads=self.ads,pending=False,bounds=self.bounds,now=self.now)
        args.update(changes)
        report=build_management(**args)
        report.update(shop={'id':1,'cliente':'Loja teste'},questions=2)
        return report

    def test_completed_days_and_custom_period(self):
        start,end,before_start,before_end=selection({},self.today)
        self.assertEqual((start,end),(date(2026,10,13),date(2026,10,19)))
        self.assertEqual((before_start,before_end),(date(2026,10,6),date(2026,10,12)))
        self.assertEqual(selection({'inicio':'2026-10-10','fim':'2026-10-12'},self.today)[0],date(2026,10,10))
        for args in ({'inicio':'2026-10-19','fim':'2026-10-20'}, {'inicio':'2026-10-20','fim':'2026-10-19'},
                     {'inicio':'2026-01-01','fim':'2026-10-19'},{'inicio':'broken'}):
            with self.subTest(args=args),self.assertRaises(ValueError):selection(args,self.today)

    def test_sales_ads_ratio_stock_and_prioritized_actions(self):
        report=self.build()
        self.assertEqual(report['current']['revenue'],Decimal('400'))
        self.assertEqual(report['previous']['orders'],6)
        self.assertEqual(report['ads']['spend'],Decimal('70'))
        self.assertEqual(report['ads']['roas'],Decimal('5'))
        self.assertEqual(report['tacos'],Decimal('17.5'))
        self.assertEqual(report['rows'][0]['ratio'],Decimal('10'))
        self.assertEqual(report['rows'][0]['stock_days'],Decimal('3.5'))
        self.assertEqual(report['missing_cost_count'],1)
        self.assertEqual(report['cost_coverage'],Decimal(0))
        self.assertTrue(any(s['kind']=='vendas' for s in report['signals']))
        self.assertTrue(any(s['kind']=='estoque' for s in report['signals']))
        self.assertTrue(any(s['kind']=='margem' for s in report['signals']))

    def test_missing_sales_days_do_not_become_zero_sales_or_decline(self):
        report=self.build(coverage=self.coverage[1:])
        self.assertIsNone(report['current']['revenue'])
        self.assertIsNone(report['no_sales'])
        self.assertFalse(report['ranking']['available'])
        self.assertFalse(any(s['kind']=='vendas' for s in report['signals']))
        self.assertIsNone(report['tacos'])

    def test_missing_mapping_and_unknown_dates_block_listing_claims(self):
        self.assertFalse(self.build(items=[])['ranking']['available'])
        unknown=dict(self.orders[0],pedido_id='unknown',criado_em=None,vendas_dia_coleta=None)
        report=self.build(orders=self.orders+[unknown])
        self.assertIsNone(report['current']['revenue'])
        self.assertFalse(report['ranking']['available'])
        self.assertFalse(any(s['kind']=='vendas' for s in report['signals']))
        self.assertFalse(self.build(pending=True)['ranking']['available'])
        self.assertIsNone(self.build(sales_limited=True)['current']['orders'])

    def test_partial_visits_and_ads_do_not_create_a_fake_funnel(self):
        report=self.build(visits=[dict(self.visits[0],days_current=6)],ads=self.ads[1:])
        self.assertEqual(report['visits'],10)
        self.assertEqual(report['visits_complete'],0)
        self.assertIsNone(report['rows'][0]['ratio'])
        self.assertIsNone(report['rows'][0]['visits'])
        self.assertIsNone(report['ads']['spend'])
        self.assertIsNone(report['tacos'])
        empty=self.build(visits=[],ads=[])
        self.assertIn('Aguardando coleta',render_management(1,empty,{}))
        all_zero=advertising([dict(r,gasto=0,faturamento=0) for r in self.ads],self.bounds[0],self.bounds[1])
        self.assertEqual(all_zero['spend'],0)
        self.assertIsNone(all_zero['roas'])

    def test_stale_data_does_not_generate_current_stock_or_sales_alarm(self):
        report=self.build(listings=[dict(self.listings[0],quantidade=0,atualizado_em=self.now-86400)],
                          coverage=[dict(c,atualizado_em=self.now-10*86400) for c in self.coverage])
        self.assertFalse(report['sales_fresh'])
        self.assertFalse(any(s['kind'] in ('vendas','estoque') for s in report['signals']))
        self.assertTrue(any(s['kind']=='dados' for s in report['signals']))

    def test_no_sales_and_interruption_need_verified_history(self):
        report=self.build(orders=self.orders[:-1],items=self.items[:-1])
        self.assertEqual(report['no_sales'],1)
        self.assertTrue(any(s['title']=='Vendas interrompidas no período' for s in report['signals']))
        no_history=self.build(orders=[],items=[])
        self.assertFalse(any(s['kind']=='vendas' for s in no_history['signals']))
        self.assertEqual(no_history['no_sales'],1)

    def test_filters_pagination_escaping_and_period_links(self):
        report=self.build()
        report['signals']*=30
        body=render_management(1,report,{'area':'margem','por_pagina':'25','inicio':'2026-10-13','fim':'2026-10-19'})
        self.assertIn('Página 1 de 2 · 30 registros',body)
        self.assertIn('Anúncio &lt;script&gt;',body)
        self.assertNotIn('<script>Anúncio',body)
        self.assertNotIn('Queda de pelo menos 30%',body)
        self.assertIn('periodo=personalizado',body)
        self.assertIn('de=2026-10-13',body)
        self.assertIn("name='por_pagina'",body)
        self.assertIn("name='busca'",body)
        self.assertIn('Nenhum anúncio disponível',render_management(1,report,{'visao':'sem_vendas'}))
        self.assertIn('Nenhum sinal para estes filtros',render_management(1,report,{'busca':'nada'}))


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL not configured')
class ManagementIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        cls.m=main
        if main.scheduler.running:main.scheduler.shutdown(wait=False)
        main.app.config['TESTING']=True

    def setUp(self):
        self.ids=[]
        self.today=datetime.now(SAO_PAULO).date()
        now=int(time.time())
        with self.m.banco() as conn:
            for name in ('Management A','SECRET MANAGEMENT B'):
                cid=self.m.consultar(conn,"INSERT INTO conexoes(cliente,status) VALUES(%s,'ativa') RETURNING id",(name,))[0]['id']
                self.ids.append(cid)
                self.m.executar(conn,'''INSERT INTO anuncios(conexao_id,item_id,titulo,status,quantidade,preco,fotos,atualizado_em)
                    VALUES(%s,'MLB1000001',%s,'active',0,100,2,%s)''',(cid,name,now))
            for i in range(1,15):
                day=(self.today-timedelta(days=i)).isoformat()
                self.m.executar(conn,'INSERT INTO vendas_cobertura(conexao_id,dia,atualizado_em) VALUES(%s,%s,%s)',(self.ids[0],day,now))
                self.m.executar(conn,'INSERT INTO ads_dia(conexao_id,data,gasto,faturamento,impressoes,cliques) VALUES(%s,%s,10,50,100,10)',(self.ids[0],day))
                if i<=7:
                    self.m.executar(conn,"INSERT INTO item_visits_daily(conexao_id,item_id,dia,visitas) VALUES(%s,'MLB1000001',%s,10)",(self.ids[0],day))
            day=(self.today-timedelta(days=1)).isoformat()
            self.m.executar(conn,'''INSERT INTO pedidos(conexao_id,pedido_id,status,total,moeda,criado_em,pagamentos_json,unidades,vendas_verificado_em)
                VALUES(%s,'management-order','paid',400,'BRL',%s,'[{"status":"approved"}]'::jsonb,4,%s)''',(self.ids[0],day+'T12:00:00-03:00',now))
            self.m.executar(conn,"INSERT INTO pedidos_itens(conexao_id,pedido_id,item_id,quantidade,preco_unitario) VALUES(%s,'management-order','MLB1000001',4,100)",(self.ids[0],))
        self.client=self.m.app.test_client()
        with self.client.session_transaction() as s:s.update(usuario_id=1,tipo='cliente',conexao_id=self.ids[0])
        self.path='/painel/'+str(self.ids[0])

    def tearDown(self):
        with self.m.banco() as conn:
            for table in ('pedidos_itens','pedidos','anuncios','vendas_cobertura','ads_dia','item_visits_daily'):
                self.m.executar(conn,'DELETE FROM '+table+' WHERE conexao_id=ANY(%s)',(self.ids,))
            self.m.executar(conn,'DELETE FROM conexoes WHERE id=ANY(%s)',(self.ids,))

    def test_isolation_and_login_before_data_reads(self):
        self.assertEqual(self.m.app.test_client().get(self.path).status_code,302)
        self.assertEqual(self.client.get('/painel/'+str(self.ids[1])).status_code,403)
        response=self.client.get(self.path)
        self.assertEqual(response.status_code,200)
        self.assertNotIn('SECRET MANAGEMENT B',response.text)
        with self.client.session_transaction() as s:s['tipo']='admin'
        self.assertEqual(self.client.get('/painel/2147483647').status_code,404)

    def test_cached_dashboard_with_real_sql_and_scoped_visits(self):
        with patch.object(self.m.requests,'get',side_effect=AssertionError('network during report')):
            response=self.client.get(self.path)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertIn('Central de Oportunidades',response.text)
        self.assertIn('R$ 400,00',response.text)
        self.assertIn('17,5%',response.text)
        self.assertIn('Estoque zerado',response.text)
        self.assertIn('Operação do dia',response.text)

    def test_incomplete_period_and_invalid_selection(self):
        with self.m.banco() as conn:
            self.m.executar(conn,'DELETE FROM vendas_cobertura WHERE conexao_id=%s',(self.ids[0],))
        response=self.client.get(self.path)
        self.assertEqual(response.status_code,200)
        self.assertIn('Cobertura ou integridade',response.text)
        self.assertNotIn('17,5%',response.text)
        self.assertEqual(self.client.get(self.path+'?inicio=invalid&fim=invalid').status_code,400)
        self.assertEqual(self.client.get(self.path+'?visao=sem_vendas').status_code,200)
