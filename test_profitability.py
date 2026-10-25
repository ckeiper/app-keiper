import contextlib
import os
import unittest
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from functools import wraps
from unittest.mock import Mock, patch
from flask import Flask, session, redirect
from web_security import install_security
from listing_profitability import COMPONENTS, period_contribution
from profitability_store import period, validate, result_for, load_sales, init_schema, save
from profitability_routes import register_profitability
from profitability_view import stamp

DAY = date(2026,10,24)
START, END = DAY-timedelta(days=7), DAY-timedelta(days=1)


def summary():
    return dict(orders=2, units=3, gross_items=Decimal('300'), fingerprint='a'*64, start=START.isoformat(), end=END.isoformat())



def fixture_pair():
    previous_start,previous_end=START-timedelta(days=7),START-timedelta(days=1)
    return dict(current=summary(), previous=dict(summary(),start=previous_start.isoformat(),end=previous_end.isoformat()),
                previous_start=previous_start,previous_end=previous_end)


def form():
    values = dict(submission_key='k'*32, confirmed='yes', basis='a'*64, _csrf='test-token')
    for field in COMPONENTS:
        values[field] = '10,00'
        values[field+'_source'] = 'Relatório conferido de 17 a 23/10 deste anúncio'
    return values


def record():
    costs,sources,_ = validate(form())
    return dict(id=1, gross_items=Decimal('300'), units=3, sales_fingerprint='a'*64,
                costs=costs, sources=sources, inicio=START, fim=END,
                created_at=datetime(2026,10,24,tzinfo=timezone.utc))


class FinancialEvidenceTests(unittest.TestCase):
    def test_timestamps_use_brazilian_timezone_and_do_not_guess_naive_dates(self):
        self.assertEqual(stamp(datetime(2026,10,24,tzinfo=timezone.utc)), '23/10/2026 às 21:00 · Brasília')
        self.assertEqual(stamp(datetime(2026,10,24)), 'Data não verificável')

    def test_period_costs_use_total_products_and_include_adjustments(self):
        result = result_for(summary(),record())
        self.assertTrue(result['available'])
        self.assertEqual(result['total_costs'],Decimal('60'))
        self.assertEqual(result['contribution'],Decimal('240'))
        self.assertEqual(result['margin_pct'],Decimal('80'))

    def test_missing_or_unreferenced_zero_never_produces_contribution(self):
        costs = {key:0 for key in COMPONENTS}
        sources = {key:'Comprovante de isenção ou ausência de cobrança' for key in COMPONENTS}
        self.assertTrue(period_contribution(100,1,costs,sources)['available'])
        for field in COMPONENTS:
            with self.subTest(field=field):
                incomplete = dict(costs);incomplete[field] = None
                self.assertFalse(period_contribution(100,1,incomplete,sources)['available'])
                missing_source = dict(sources);missing_source[field] = ''
                self.assertFalse(period_contribution(100,1,costs,missing_source)['available'])

    def test_no_zero_baseline_percent_or_clamped_negative_margin(self):
        costs,sources,_ = validate(form())
        empty = period_contribution(0,0,costs,sources)
        self.assertEqual(empty['contribution'],-60)
        self.assertIsNone(empty['margin_pct'])
        self.assertEqual(period_contribution(30,1,costs,sources)['margin_pct'],-100)
        for revenue,units in [(None,1),(True,1),(100,'NaN'),(100,'1.5'),(100,-1)]:
            self.assertFalse(period_contribution(revenue,units,costs,sources)['available'])

    def test_form_requires_explicit_sources_confirmation_and_cent_precision(self):
        for change in [dict(confirmed=''),dict(products=''),dict(products='-1'),
                       dict(products='NaN'),dict(products='1e2'),dict(products='1.234'),
                       dict(products='1.234,50'),dict(products='9'*13),
                       dict(products_source=''),dict(products_source='x'*501),
                       dict(submission_key='short')]:
            values=form();values.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):validate(values)
        self.assertEqual(validate(form())[0]['products'],Decimal('10'))

    def test_period_is_closed_bounded_and_requires_two_valid_dates(self):
        self.assertEqual(period({},DAY),(START,END))
        for args in [dict(inicio=START.isoformat()),dict(fim=END.isoformat()),
                     dict(inicio=DAY.isoformat(),fim=DAY.isoformat()),
                     dict(inicio='2026-01-01',fim='2026-10-23'),
                     dict(inicio='2026-10-23',fim='2026-10-17')]:
            with self.assertRaises(ValueError):period(args,DAY)

    def test_changed_sales_invalidate_costs_even_with_same_revenue_and_units(self):
        for change in [dict(fingerprint='b'*64),dict(gross_items=301),dict(units=4),dict(orders=None,reason='Cobertura incompleta')]:
            values=summary();values.update(change)
            result=result_for(values,record())
            self.assertFalse(result['available'])
            self.assertIsNone(result['contribution'])
        self.assertFalse(result_for(summary(),None)['available'])

    def test_loader_reuses_verification_and_keeps_all_reads_tenant_scoped(self):
        query=Mock(side_effect=[[],[],[dict(dia=(START+timedelta(days=i)).isoformat()) for i in range(7)],[dict(pending=False)]])
        result=load_sales(None,query,42,'MLB100',START,END)
        self.assertEqual(result['orders'],0)
        self.assertEqual(result['gross_items'],0)
        for call in query.call_args_list:
            self.assertIn('conexao_id=%s',call.args[1])
            self.assertEqual(call.args[2][0],42)
        query=Mock(side_effect=[[],[],[],[dict(pending=True)]])
        self.assertIsNone(load_sales(None,query,42,'MLB100',START,END)['orders'])

    def test_schema_is_additive_and_saves_are_append_only(self):
        execute=Mock();init_schema(None,execute);init_schema(None,execute)
        for call in execute.call_args_list:
            self.assertIn('IF NOT EXISTS',call.args[1])
            self.assertNotIn('DROP ',call.args[1])
        costs,sources,key=validate(form());execute.reset_mock()
        save(None,execute,42,'MLB100',START,END,summary(),costs,sources,7,key)
        sql=execute.call_args.args[1]
        self.assertIn('ON CONFLICT',sql)
        self.assertNotIn('DO UPDATE',sql)
        self.assertEqual(execute.call_args.args[2][:4],(42,'MLB100',START,END))
        with self.assertRaises(ValueError):
            save(None,execute,42,'MLB100',START,END,dict(orders=None),costs,sources,7,key)


class ProfitabilityRouteTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__);self.app.secret_key='isolated';self.app.testing=True
        install_security(self.app)
        self.execute=Mock();self.record=None;self.found=True
        def login(fn):
            @wraps(fn)
            def guard(*args,**kwargs):
                return fn(*args,**kwargs) if session.get('usuario_id') else redirect('/login')
            return guard
        self.query=Mock(side_effect=self.read)
        register_profitability(self.app,login,lambda cid:cid==42,lambda:contextlib.nullcontext(None),self.query,self.execute,lambda *args:args[-1],today=lambda:DAY)
        self.client=self.app.test_client();self.path='/anuncios/42/MLB100/rentabilidade'
        with self.client.session_transaction() as state:
            state.update(usuario_id=7,tipo='admin',_csrf='test-token')
        self.loader=patch('profitability_routes.load_pair',side_effect=lambda *args: fixture_pair())
        self.loader.start();self.addCleanup(self.loader.stop)

    def read(self,conn,sql,params):
        if 'JOIN anuncios' in sql:
            return [dict(cliente='Loja',titulo='<script>alert(1)</script>')] if self.found else []
        if 'LIMIT 1' in sql:return [self.record] if self.record else []
        return [self.record] if self.record else []

    def test_authenticated_admin_get_is_read_only_and_unknown_is_explicit(self):
        response=self.client.get(self.path)
        self.assertEqual(response.status_code,200)
        self.assertIn('Aguardando custos documentados',response.text)
        self.assertIn('Não representa lucro líquido',response.text)
        self.assertIn('&lt;script&gt;',response.text)
        self.assertNotIn('<script>alert(1)</script>',response.text)
        self.execute.assert_called_once_with(None, 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        self.assertEqual(response.headers['Cache-Control'],'no-store')

    def test_login_client_other_tenant_and_unknown_item_are_blocked(self):
        self.assertEqual(self.client.get(self.path.replace('/42/','/43/')).status_code,403)
        with self.client.session_transaction() as state:state['tipo']='cliente'
        self.assertEqual(self.client.get(self.path).status_code,403)
        self.assertEqual(self.client.post(self.path,data=form()).status_code,403)
        with self.client.session_transaction() as state:state.clear()
        self.assertEqual(self.client.get(self.path).status_code,302)
        self.execute.assert_not_called()

    def test_csrf_cross_site_invalid_dates_and_invalid_input_do_not_write(self):
        self.assertEqual(self.client.post(self.path,data={}).status_code,400)
        self.assertEqual(self.client.post(self.path,data=form(),headers={'Origin':'https://evil.example'}).status_code,400)
        values=form();values['products']='-1'
        self.assertEqual(self.client.post(self.path,data=values).status_code,400)
        values=form();values['basis']='b'*64
        self.assertEqual(self.client.post(self.path,data=values).status_code,400)
        self.assertEqual(self.client.get(self.path+'?inicio=invalid').status_code,400)
        self.execute.assert_not_called()

    def test_append_cost_version_and_render_sources_safely(self):
        response=self.client.post(self.path,data=form())
        self.assertEqual(response.status_code,303)
        self.assertIn('inicio=2026-10-17',response.location)
        self.assertEqual(self.execute.call_args.args[2][0:2],(42,'MLB100'))
        self.record=record();self.record['sources']['products']='<img src=x onerror=alert(1)>'
        response=self.client.get(response.location)
        self.assertIn('R$ 240,00',response.text)
        self.assertIn('&lt;img',response.text)
        self.assertNotIn('<img src=x',response.text)
        self.record['sales_fingerprint']='b'*64
        self.assertIn('As vendas mudaram',self.client.get(self.path).text)
        self.assertNotIn('R$ 240,00',self.client.get(self.path).text)

    def test_no_record_or_cost_write_for_unverified_sales_or_unknown_item(self):
        with patch('profitability_routes.load_pair',return_value=dict(fixture_pair(),current=dict(summary(),orders=None,reason='Sem cobertura'))):
            self.assertEqual(self.client.post(self.path,data=form()).status_code,400)
        self.found=False
        self.assertEqual(self.client.post(self.path,data=form()).status_code,404)
        self.execute.assert_not_called()


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'),'isolated PostgreSQL URL not configured')
class ProfitabilityDatabaseTests(unittest.TestCase):
    def test_idempotent_schema_replays_versions_tenant_isolation_and_real_route(self):
        os.environ['DATABASE_URL']=os.environ['KEIPER_TEST_DATABASE_URL']
        import main
        from auth_test_support import database_session
        if main.scheduler.running:main.scheduler.shutdown(wait=False)
        main.iniciar_banco()
        with main.banco() as conn:
            cid=main.consultar(conn,'INSERT INTO conexoes(cliente) VALUES(%s) RETURNING id',('Teste Rentabilidade',))[0]['id']
            main.executar(conn,'INSERT INTO anuncios(conexao_id,item_id) VALUES(%s,%s)',(cid,'MLB100'))
        try:
            with main.banco() as conn:
                init_schema(conn,main.executar);init_schema(conn,main.executar)
                costs,sources,key=validate(form())
                for _ in range(2):save(conn,main.executar,cid,'MLB100',START,END,summary(),costs,sources,7,key)
                save(conn,main.executar,cid,'MLB100',START,END,summary(),costs,sources,7,'n'*32)
                rows=main.consultar(conn,'SELECT * FROM listing_profitability_records WHERE conexao_id=%s',(cid,))
                self.assertEqual(len(rows),2)
                self.assertEqual(rows[0]['costs']['products'],'10.00')
                self.assertFalse(main.consultar(conn,'SELECT * FROM listing_profitability_records WHERE conexao_id=%s',(-cid,)))
            client=main.app.test_client()
            with database_session(client) as state:state.update(usuario_id=1,tipo='admin')
            with patch('profitability_routes.load_pair',side_effect=lambda *args: fixture_pair()),patch('main.requests.get',side_effect=AssertionError('remote read during render')):
                response=client.get(f'/anuncios/{cid}/MLB100/rentabilidade?inicio={START}&fim={END}')
            self.assertEqual(response.status_code,200)
            self.assertIn('R$ 240,00',response.text)
            inspection_path=f'/anuncios/{cid}/MLB100/rentabilidade?inicio={START}&fim={END}&registro={rows[0]["id"]}'
            with patch('profitability_routes.load_pair',side_effect=lambda *args: fixture_pair()):
                inspected=client.get(inspection_path)
                self.assertEqual(inspected.status_code,200)
                self.assertIn('Consulta do registro #'+str(rows[0]['id']),inspected.text)
                wrong_period=inspection_path.replace(str(START),str(START-timedelta(days=1)))
                self.assertEqual(client.get(wrong_period).status_code,404)
            with main.banco() as conn:
                self.assertEqual(len(main.consultar(conn,'SELECT id FROM listing_profitability_records WHERE conexao_id=%s',(cid,))),2)
            with database_session(client) as state:state.update(tipo='cliente',conexao_id=cid)
            self.assertEqual(client.get(f'/anuncios/{cid}/MLB100/rentabilidade').status_code,403)
        finally:
            with main.banco() as conn:
                main.executar(conn,'DELETE FROM listing_profitability_records WHERE conexao_id=%s',(cid,))
                main.executar(conn,'DELETE FROM anuncios WHERE conexao_id=%s',(cid,))
                main.executar(conn,'DELETE FROM conexoes WHERE id=%s',(cid,))
