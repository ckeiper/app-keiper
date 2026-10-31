import unittest
from decimal import Decimal
from portfolio_charts import aggregate,chart

class ChartTests(unittest.TestCase):
 def test_partial_is_unknown_and_zero_is_known(self):
  self.assertEqual(aggregate([{'daily_sales':[0,None]},{'daily_sales':[0,2]}],'daily_sales',2),[Decimal(0),None])
 def test_missing_previous_breaks_comparison_line(self):
  rows=[dict(daily_sales=[1,2,3],previous_daily_sales=[2,None,4])]
  html=chart(rows,'daily_sales',['2026-10-01','2026-10-02','2026-10-03'],'Faturamento')
  self.assertNotIn('stroke-dasharray=',html)
  self.assertEqual(html.count('class="portfolio-day"'),3)
  self.assertIn('Anterior: Não disponível',html)
 def test_complete_comparison_and_escaped_label(self):
  html=chart([dict(daily_sales=[1,2],previous_daily_sales=[2,1])],'daily_sales',['2026-10-01','2026-10-02'],'<img>')
  self.assertIn('stroke-dasharray=',html);self.assertNotIn('<img>',html)
