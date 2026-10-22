from contextlib import nullcontext
from datetime import date
import ast
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask
import unittest
import os
import threading
import time
from uuid import uuid4
import section_refresh as refresh


def production_function(name, namespace):
    tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), namespace)
    return namespace[name]


def test_ads_collects_only_ads_and_passes_selected_period():
    functions = {name: Mock(return_value=True) for name in (
        'puxar_ads','puxar_anuncios','puxar_pedidos','puxar_envios','puxar_full','puxar_promocoes')}
    collect = production_function('coletar_secao', dict(functions,
        banco=lambda: nullcontext(None), consultar=Mock(return_value=[{'user_id': 10}]),
        token_atual=lambda c: 'token'))
    period = (date(2026,10,1), date(2026,10,22))
    assert collect(12, 'ads', period)
    functions['puxar_ads'].assert_called_once_with(12, 'token', 10, refresh_range=period)
    for name, fn in functions.items():
        if name != 'puxar_ads': fn.assert_not_called()
    functions['puxar_ads'].return_value = False
    assert not collect(12, 'ads', period)


def test_each_scope_has_only_its_dependencies():
    assert refresh.collector_names('anuncios') == ('puxar_anuncios',)
    assert refresh.collector_names('promocoes') == ('puxar_promocoes',)
    assert refresh.collector_names('full') == ('puxar_full',)
    assert 'puxar_ads' not in refresh.collector_names('vendas')
    assert 'puxar_pedidos' not in refresh.collector_names('custos')


def test_period_validation_uses_brazilian_day_and_bounds():
    with patch.object(refresh, 'reporting_today', return_value=date(2026,10,22)):
        assert refresh.selected_range({'dias':'7'}) == (date(2026,10,16),date(2026,10,22))
        for args in ({'dias':'999'}, {'de':'2026-01-01','ate':'2026-10-22'},
                     {'de':'2026-10-22','ate':'2026-10-23'}, {'de':'bad'},
                     {'de':'2026-10-22','ate':'2026-10-01'}):
            with unittest.TestCase().assertRaises(ValueError): refresh.selected_range(args)


def client(allowed=True, active=None):
    app = Flask(__name__)
    app.secret_key = 'test'
    query, execute, collect = Mock(return_value=active or []), Mock(), Mock(return_value=True)
    refresh.register(app, lambda f:f, lambda cid:allowed,
                     lambda: nullcontext(None), query, execute, collect)
    return app.test_client(), query, execute, collect


def test_access_and_scope_validation_precede_work():
    c, query, execute, collect = client(allowed=False)
    for method in (c.get, c.post): assert method('/atualizacoes/12/ads').status_code == 403
    query.assert_not_called()
    collect.assert_not_called()
    c, query, _, _ = client()
    assert c.post('/atualizacoes/12/invalid').status_code == 400
    assert c.post('/atualizacoes/12/ads?dias=999').status_code == 400
    query.assert_not_called()


def test_duplicate_click_reuses_job_and_other_section_is_busy():
    active = [{'id':'existing','secao':'ads','status':'executando','mensagem':'Atualizando'}]
    c, _, _, collect = client(active=active)
    with patch.object(refresh.threading, 'Thread') as thread:
        assert c.post('/atualizacoes/12/ads').json['id'] == 'existing'
        assert c.post('/atualizacoes/12/vendas').status_code == 409
        thread.assert_not_called()
    collect.assert_not_called()


def test_post_launches_background_job_get_never_collects():
    c, _, execute, collect = client()
    with patch.object(refresh.threading, 'Thread') as thread:
        assert c.get('/atualizacoes/12/ads').json['status'] == 'inativa'
        thread.assert_not_called()
        response = c.post('/atualizacoes/12/ads?dias=7')
        assert response.status_code == 202
        thread.return_value.start.assert_called_once()
    collect.assert_not_called()
    assert any('pg_advisory_xact_lock' in call.args[1] for call in execute.call_args_list)


def check_background(locked,result,status):
    c, _, execute, collect = client()
    collect.return_value = result
    with patch.object(refresh.threading, 'Thread') as thread:
        c.post('/atualizacoes/12/ads?dias=7')
        kwargs = thread.call_args.kwargs
    with patch.object(refresh, 'store_sync_lock', return_value=nullcontext(locked)), \
         patch.object(refresh.threading, 'Thread'):
        kwargs['target'](*kwargs['args'])
    if locked: collect.assert_called_once()
    else: collect.assert_not_called()
    assert any(call.args[2][0] == status for call in execute.call_args_list
               if len(call.args)>2 and isinstance(call.args[2], tuple))


def test_background_lock_and_results_are_persisted():
    for values in [(False,True,'ocupada'),(True,True,'concluida'),(True,False,'falhou')]:
        check_background(*values)


def test_ui_has_explicit_post_status_and_preserves_filters():
    ui=refresh.render(12,'ads')
    assert "type='button'" in ui and 'Atualizar Ads' in ui
    assert "method:'POST'" in ui and 'location.search' in ui
    assert 'location.reload()' in ui and "role='status'" in ui
    assert refresh.render(12,'crm') == ''


def test_manual_ads_refresh_is_limited_to_selected_days_and_reports_partial_failure():
    from test_ads_reporting_day import AdsReportingDayTests
    harness = AdsReportingDayTests()
    collect = harness.collector(failed_day='2026-10-19')
    period = (date(2026,10,19), date(2026,10,21))
    with patch('sales_metrics.reporting_today', return_value=date(2026,10,21)):
        assert not collect(5, 'token', 1, refresh_range=period)
    assert harness.requested == ['2026-10-21','2026-10-20','2026-10-19']
    snapshots = [p for sql,p in harness.written if 'INSERT INTO ads_dia' in sql]
    assert [p[1] for p in snapshots] == ['2026-10-21','2026-10-20']


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn) for name,fn in globals().items()
                               if name.startswith('test_') and callable(fn))
    suite.addTests(loader.loadTestsFromTestCase(SectionRefreshStorageTests))
    return suite


@unittest.skipUnless(os.getenv('KEIPER_TEST_DATABASE_URL'), 'isolated PostgreSQL URL not configured')
class SectionRefreshStorageTests(unittest.TestCase):
    def test_schema_duplicate_requests_and_background_completion(self):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        url = os.environ['KEIPER_TEST_DATABASE_URL']
        schema = 'refresh_test_' + uuid4().hex
        def execute(conn, sql, params=None):
            cur=conn.cursor();cur.execute(sql,params);return cur
        with psycopg2.connect(url) as conn:
            execute(conn, 'CREATE SCHEMA ' + schema)
        def bank():
            return psycopg2.connect(url, options='-c search_path=' + schema)
        def query(conn, sql, params=None):
            cur=conn.cursor(cursor_factory=RealDictCursor);cur.execute(sql,params);return cur.fetchall()
        release, entered = threading.Event(), threading.Event()
        def collect(*args):
            entered.set()
            return release.wait(5)
        try:
            with bank() as conn:
                execute(conn,'CREATE TABLE conexoes(id INTEGER PRIMARY KEY)')
                execute(conn,'INSERT INTO conexoes VALUES (12)')
                refresh.init_schema(conn,execute);refresh.init_schema(conn,execute)
            app=Flask(__name__)
            refresh.register(app,lambda f:f,lambda cid:True,bank,query,execute,collect)
            c=app.test_client()
            first=c.post('/atualizacoes/12/ads?dias=7')
            self.assertEqual(first.status_code,202)
            self.assertTrue(entered.wait(5))
            self.assertEqual(c.post('/atualizacoes/12/ads').json['id'],first.json['id'])
            self.assertEqual(c.post('/atualizacoes/12/vendas').status_code,409)
            release.set()
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                state=c.get('/atualizacoes/12/ads').json
                if state['status']=='concluida':break
                time.sleep(.02)
            self.assertEqual(state['status'],'concluida')
        finally:
            release.set()
            with psycopg2.connect(url) as conn:
                execute(conn,'DROP SCHEMA '+schema+' CASCADE')
