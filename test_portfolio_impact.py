import unittest
from decimal import Decimal as D
from portfolio_impact import contributions,render
from portfolio_view import combine

class ContributionTests(unittest.TestCase):
 def test_offsetting_changes_keep_meaningful_denominator(self):
  d=contributions([dict(sales=D(200),previous_sales=D(100)),dict(sales=D(0),previous_sales=D(100))])
  self.assertEqual(d['delta'],0);self.assertEqual([r['points'] for r in d['rows']],[50,-50])
 def test_missing_baseline_preserves_known_delta_but_hides_portfolio(self):
  d=contributions([dict(sales=D(200),previous_sales=D(100)),dict(sales=D(10),previous_sales=None)])
  self.assertIsNone(d['delta']);self.assertEqual(d['rows'][0]['delta'],100);self.assertIsNone(d['rows'][0]['points']);self.assertIsNone(d['rows'][1]['delta'])
 def test_zero_baseline_is_not_missing_but_has_no_percentage(self):
  d=contributions([dict(sales=D(20),previous_sales=D(0))]);self.assertEqual(d['delta'],20);self.assertIsNone(d['rows'][0]['points'])
 def test_empty_has_no_total(self):self.assertIsNone(contributions([])['delta'])
 def test_render_links_escape_and_order(self):
  from test_portfolio_view import PortfolioTests
  m=combine(PortfolioTests().data(),[]);m['rows'][0]['name']='<script>Alfa</script>'
  html=render(m);self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;Alfa',html);self.assertIn('/vendas/2?periodo=personalizado&amp;inicio=2026-10-30',html);self.assertIn('+R$ 800,00',html)
