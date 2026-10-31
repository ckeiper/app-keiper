import unittest
from datetime import date
from decimal import Decimal as D
from portfolio_view import dates,combine,render

class PortfolioTests(unittest.TestCase):
 def data(self):
  def report(cid,name,revenue):return dict(shop=dict(id=cid,cliente=name),current=dict(revenue=revenue,daily=[float(revenue) if revenue is not None else None]),previous=dict(revenue=D(100),daily=[100]),reasons=[],last_sync=1793420000)
  return dict(bounds=(date(2026,10,30),date(2026,10,30),date(2026,10,29),date(2026,10,29)),reports=[report(1,'Zeta',D(100)),report(2,'Alfa',D(900))])
 def test_weighted_tacos_not_average_and_alphabetical(self):
  model=combine(self.data(),[dict(conexao_id=1,data='2026-10-30',gasto=10),dict(conexao_id=2,data='2026-10-30',gasto=9)])
  self.assertEqual(model['totals']['sales'],1000);self.assertEqual(model['totals']['ads'],19);self.assertEqual(model['totals']['tacos'],D('1.9'));self.assertEqual(model['rows'][0]['name'],'Alfa')
 def test_missing_ads_not_zero_and_sales_independent(self):
  m=combine(self.data(),[]);self.assertIsNone(m['totals']['ads']);self.assertIsNone(m['totals']['tacos']);self.assertEqual(m['totals']['sales'],1000)
 def test_missing_sales_hides_total_and_share(self):
  d=self.data();d['reports'][0]['current']['revenue']=None
  self.assertIsNone(combine(d,[])['totals']['sales'])
 def test_periods_and_bounds(self):
  today=date(2026,10,30);self.assertEqual(dates({},today),(date(2026,10,1),today));self.assertEqual(dates(dict(periodo='anterior'),today),(date(2026,9,1),date(2026,9,30)))
  for a in [dict(periodo='bad'),dict(periodo='personalizado',inicio='2020-01-01',fim='2026-10-30'),dict(periodo='personalizado',inicio='2027-01-01',fim='2027-01-01')]:
   with self.assertRaises(ValueError):dates(a,today)
 def test_escape_and_no_external_scripts(self):
  d=self.data();d['reports'][0]['shop']['cliente']='<script>alert(1)</script>';html=render(combine(d,[]),{})
  self.assertNotIn('<script>alert(1)</script>',html);self.assertNotIn('<script src=',html);self.assertIn('&lt;script&gt;',html);self.assertIn('/vendas/1?periodo=personalizado',html)
 def test_admin_gate_precedes_database(self):
  from flask import Flask
  from portfolio_view import register
  from unittest.mock import Mock
  app=Flask(__name__);app.secret_key='test';bank=Mock()
  register(app,lambda f:f,bank,Mock(),Mock(),Mock())
  c=app.test_client();self.assertEqual(c.get('/carteira').status_code,403);bank.assert_not_called()
