import unittest
from datetime import date,timedelta
from ads_campaign_detail import metrics,render

class CampaignDetailTests(unittest.TestCase):
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
