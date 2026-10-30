"""Exercise the real Ads route with isolated stored campaign observations."""
import ast
import contextlib
import datetime
import html
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from flask import Flask, request


class AdsOpportunityTests(unittest.TestCase):
    def page(self, coverage=2, previous=100, current=50, status='active', today_only=False):
        tree=ast.parse(Path('main.py').read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='painel_ads')
        fn.decorator_list=[]
        self.queries=[]
        def query(conn,sql,params):
            self.queries.append((sql,params))
            if 'SELECT id, cliente FROM conexoes' in sql:return [dict(id=7,cliente='Store')]
            if 'AS gasto_periodo' in sql:return [dict(campanha_id='9',nome='<script>x</script>',status=status,orcamento=0,roas_objetivo=2,esgotado_em=None,gasto_periodo=10,fat_periodo=0,gasto_hoje=0,hoje_atualizado=None,gasto_ontem=0,fat_ontem=0,tem_ontem=0)]
            if 'AS dias_atual' in sql:return [dict(campanha_id='9',gasto_atual=10,receita_atual=current,gasto_anterior=10,receita_anterior=previous,dias_atual=coverage,dias_anterior=2)]
            return []
        namespace=dict(request=request,datetime=datetime,time=time,esc=html.escape,pode_ver_loja=lambda cid:True,banco=lambda:contextlib.nullcontext(None),consultar=query,pagina=lambda *a:a[-1],pagina_loja=lambda *a:a[-1])
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'main.py','exec'),namespace)
        app=Flask(__name__)
        end='2026-10-30' if today_only else '2026-10-29'
        start=end if today_only else '2026-10-28'
        with app.test_request_context('/ads/7?de='+start+'&ate='+end),patch('sales_metrics.reporting_today',return_value=datetime.date(2026,10,30)):
            return namespace['painel_ads'](7)

    def test_complete_equal_windows_and_escaped_campaign(self):
        page=self.page()
        self.assertIn('queda de 50%',page)
        self.assertIn('Gasto sem retorno atribuído',page)
        self.assertNotIn('<script>x</script>',page)
        self.assertIn('&lt;script&gt;x&lt;/script&gt;',page)
        sql,params=next((s,p) for s,p in self.queries if 'AS dias_atual' in s)
        self.assertEqual(params[:8],('2026-10-28','2026-10-29','2026-10-28','2026-10-29','2026-10-26','2026-10-27','2026-10-26','2026-10-27'))
        self.assertIn('faturamento >= 0',sql)
        self.assertEqual(params[-3:],(7,'2026-10-26','2026-10-29'))

    def test_partial_coverage_or_zero_baseline_cannot_assert_drop(self):
        for args in [dict(coverage=1),dict(previous=0),dict(status='paused'),dict(current=80)]:
            with self.subTest(args=args):self.assertNotIn('queda de ',self.page(**args))

    def test_today_alone_has_no_complete_comparison(self):
        self.assertNotIn('queda de ',self.page(today_only=True))
        self.assertFalse(any('AS dias_atual' in s for s,p in self.queries))
