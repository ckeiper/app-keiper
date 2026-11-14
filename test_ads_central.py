import unittest
from flask import Flask
from ads_central import budget_indicator, chart, register_ads_central

class FakeDB:
    def __enter__(self): return self
    def __exit__(self, *args): return False

class CentralAdsTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "testing-only"
        self.queries = []
        def consultar(conn, sql, args=()):
            self.queries.append((sql,args))
            if "FROM ads_campanhas" in sql:
                return [dict(cliente="CLIENTE-SECRETO", conexao_id=17, campanha_id="a1",
                             nome="CAMPANHA-SECRETA", status="active", orcamento=100,
                             roas_objetivo=3, atualizado_em=0, gasto=20,
                             faturamento=80, dias_observados=1, gasto_hoje=76)]
            return [dict(data="2026-11-13", gasto=20, faturamento=80)]
        def login_required(f): return f
        register_ads_central(self.app,login_required,lambda:FakeDB(),consultar,
                             lambda title,body:body)
        self.client=self.app.test_client()
    def session(self,kind,cid):
        with self.client.session_transaction() as s:
            s["tipo"]=kind
            s["conexao_id"]=cid
    def test_client_queries_scoped(self):
        self.session("cliente",17)
        res=self.client.get("/central-ads")
        self.assertEqual(res.status_code,200)
        self.assertEqual(len(self.queries),3)
        for sql,args in self.queries:
            self.assertIn("AND c.id=%s",sql)
            self.assertEqual(args[-1],17)
    def test_admin_can_see_all(self):
        self.session("admin",None)
        res=self.client.get("/central-ads")
        self.assertEqual(res.status_code,200)
        self.assertTrue(all("AND c.id=%s" not in q for q,a in self.queries))
    def test_daily_budget_uses_today_even_for_long_period(self):
        self.session("admin", None)
        page = self.client.get("/central-ads?periodo=30").get_data(as_text=True)
        self.assertIn("data-budget-used='76.0'", page)
        self.assertIn("aria-valuetext='76,00%'", page)
        self.assertIn("value='budget-desc'", page)
        self.assertIn("value='budget-asc'", page)

    def test_daily_budget_threshold_and_overflow(self):
        self.assertNotIn("ka-budget-danger", budget_indicator(75))
        self.assertIn("ka-budget-danger", budget_indicator(75.01))
        self.assertIn("value='100'", budget_indicator(125))
        self.assertIn("aria-valuetext='125,00%'", budget_indicator(125))
        self.assertNotIn("<meter", budget_indicator(None))

    def test_chart_formats_dates_and_exposes_both_daily_values(self):
        page = chart([dict(data="2026-11-07", faturamento=80, gasto=20)])
        self.assertIn(">07/11</text>", page)
        self.assertIn("tabindex='0'", page)
        self.assertIn("07/11 · Vendas Ads R$ 80,00 · Investimento R$ 20,00", page)
        self.assertNotIn("11-07", page)
    def test_presentation_does_not_send_private_names(self):
        self.session("admin",None)
        res=self.client.get("/central-ads?apresentacao=1")
        self.assertNotIn(b"CLIENTE-SECRETO",res.data)
        self.assertNotIn(b"CAMPANHA-SECRETA",res.data)
        self.assertIn(b"Nome oculto",res.data)
    def test_client_cannot_enable_presentation(self):
        self.session("cliente",17)
        res=self.client.get("/central-ads?apresentacao=1")
        self.assertIn(b"CLIENTE-SECRETO",res.data)
        self.assertNotIn(b"Nome oculto",res.data)
    def test_client_without_connection_denied(self):
        self.session("cliente",None)
        res=self.client.get("/central-ads")
        self.assertEqual(res.status_code,403)
        self.assertEqual(self.queries,[])
if __name__=="__main__":
    unittest.main()
