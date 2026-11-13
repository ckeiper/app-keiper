import unittest
from flask import Flask
from ads_central import register_ads_central

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
                             faturamento=80, dias_observados=1)]
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
        self.assertEqual(len(self.queries),2)
        for sql,args in self.queries:
            self.assertIn("AND c.id=%s",sql)
            self.assertEqual(args[-1],17)
    def test_admin_can_see_all(self):
        self.session("admin",None)
        res=self.client.get("/central-ads")
        self.assertEqual(res.status_code,200)
        self.assertTrue(all("AND c.id=%s" not in q for q,a in self.queries))
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
