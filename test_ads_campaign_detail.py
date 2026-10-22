import unittest
from datetime import date,timedelta
from ads_campaign_detail import metrics,render

class CampaignDetailTests(unittest.TestCase):
    def test_chart_dates_use_day_month_and_keep_unknown_values(self):
        today=date(2026,1,3)
        html=render(7,{"campanha_id":"10"},[],7,today)
        self.assertIn('labels:["28/12", "29/12", "30/12", "31/12", "01/01", "02/01", "03/01"]',html)
        self.assertNotIn('2026-01-03',html)
        self.assertIn('currency.format(context.parsed.y)',html)
        self.assertIn('"data": [null, null, null, null, null, null, null]',html)

    def test_chart_uses_official_campaign_counts_not_store_revenue(self):
        today=date(2026,10,20)
        campaign={"campanha_id":"10","nome":"Teste","status":"active"}
        history=[{"data":today.isoformat(),"gasto":10,"faturamento":20,
                  "vendas_atribuidas":3,"outras_vendas":7}]
        html=render(7,campaign,history,7,today,
                    shop_daily={today.isoformat():100},
                    ads_total_daily={today.isoformat():40})
        self.assertIn('"label": "Outras vendas"',html)
        self.assertIn('"data": [null, null, null, null, null, null, 3]',html)
        self.assertIn('"data": [null, null, null, null, null, null, 7]',html)
        self.assertIn("Métricas oficiais de vendas disponíveis em 1 de 7 dias",html)
        self.assertNotIn('estimativa sem Ads',html)
        self.assertIn('Vendas em quantidade no eixo esquerdo',html)

    def test_missing_official_metrics_do_not_become_zero_or_store_estimates(self):
        today=date(2026,10,20)
        html=render(7,{"campanha_id":"10"},[{"data":today.isoformat(),"gasto":10,"faturamento":20}],7,today,
                    shop_daily={today.isoformat():100},ads_total_daily={today.isoformat():40})
        self.assertIn('Métricas oficiais de vendas disponíveis em 0 de 7 dias',html)
        self.assertNotIn('"data": [null, null, null, null, null, null, 60',html)

    def test_official_zero_sales_are_not_treated_as_missing(self):
        today=date(2026,10,20)
        html=render(7,{"campanha_id":"10"},[{"data":today.isoformat(),"gasto":10,"faturamento":20,
            "vendas_atribuidas":0,"outras_vendas":0}],1,today)
        self.assertIn('"data": [0]',html)
        self.assertNotIn('Métricas oficiais de vendas disponíveis',html)

    def test_metrics_use_campaign_spend_and_attributed_revenue(self):
        m=metrics([{"gasto":20,"faturamento":100},{"gasto":30,"faturamento":50}])
        self.assertEqual(m["spent"],50)
        self.assertEqual(m["revenue"],150)
        self.assertEqual(m["roas"],3)
        self.assertAlmostEqual(m["acos"],100/3)

    def test_no_denominator_no_fabricated_tacos(self):
        today=date(2026,10,20)
        campaign={"campanha_id":"C1","nome":"Teste","status":"active","orcamento":100,"roas_objetivo":5}
        html=render(7,campaign,[{"data":today.isoformat(),"gasto":10,"faturamento":20}],7,today)
        self.assertIn("TACOS da campanha",html)
        self.assertIn("Vendas totais da loja ainda não validadas",html)
        self.assertIn("Cobertura diária incompleta",html)
        self.assertIn("Campanha",html)

    def test_escapes_campaign_label_and_preserves_navigation(self):
        today=date(2026,10,20)
        campaign={"campanha_id":"A&B","nome":"<script>alert(1)</script>","status":"active"}
        html=render(7,campaign,[],30,today)
        self.assertNotIn("<script>alert(1)</script>",html)
        self.assertIn("&lt;script&gt;",html)
        self.assertIn("/ads/7/campanha/A%26B?dias=30",html)

    def test_complete_comparison_uses_same_number_of_days(self):
        today=date(2026,10,20)
        campaign={"campanha_id":"10","nome":"Teste","status":"active"}
        rows=[{"data":(today-timedelta(days=i)).isoformat(),"gasto":10,"faturamento":20} for i in range(14)]
        html=render(7,campaign,rows,7,today)
        self.assertNotIn("Cobertura diária incompleta",html)
        self.assertIn("vs. período anterior",html)

if __name__=="__main__":
    unittest.main()
