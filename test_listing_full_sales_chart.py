import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from listing_full_sales_chart import daily_full_status,daily_sales,render

def stamp(y,m,d,h=12):
    return int(datetime(y,m,d,h,tzinfo=ZoneInfo("America/Sao_Paulo")).timestamp())

class FullSalesChartTests(unittest.TestCase):
    def test_daily_stock_never_carries_forward(self):
        days=["2026-10-19","2026-10-20","2026-10-21"]
        rows=[{"observed_at":stamp(2026,10,19),"logistics":"fulfillment","state":"available"},
              {"observed_at":stamp(2026,10,21),"logistics":"fulfillment","state":"empty"}]
        self.assertEqual(daily_full_status(rows,days),[1,None,0])

    def test_latest_daily_observation_wins(self):
        dates=["2026-10-20"]
        rows=[{"observed_at":stamp(2026,10,20,9),"logistics":"fulfillment","state":"available"},
              {"observed_at":stamp(2026,10,20,18),"logistics":"fulfillment","state":"empty"}]
        self.assertEqual(daily_full_status(rows,dates),[0])

    def test_other_logistics_and_unknown_not_full(self):
        dates=["2026-10-19","2026-10-20"]
        rows=[{"observed_at":stamp(2026,10,19),"logistics":"other","state":"available"},
              {"observed_at":stamp(2026,10,20),"logistics":"fulfillment","state":"unknown"}]
        self.assertEqual(daily_full_status(rows,dates),[None,None])

    def test_pending_orders_leave_sale_series_unknown(self):
        dates,values=daily_sales([],[],[],"MLB123",days=7,today=date(2026,10,21),has_pending=True)
        self.assertEqual(len(dates),7)
        self.assertEqual(values,[None]*7)

    def test_chart_discloses_limited_full_coverage(self):
        html=render("MLB123",[],[],[],[],today=date(2026,10,21),has_pending=True)
        self.assertIn("Vendas do anúncio × Estoque Full",html)
        self.assertIn("não há observações diárias confirmadas",html)
        self.assertIn("Datas não verificadas",html)

if __name__=="__main__":
    unittest.main()
