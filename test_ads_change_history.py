import unittest
from datetime import date
from ads_change_history import differences, display_history
from ads_campaign_detail import render

class AdsChangeHistoryTests(unittest.TestCase):
    def test_first_snapshot_does_not_create_fake_change(self):
        self.assertEqual(differences(None,{"orcamento":100,"roas_objetivo":8}),[])
    def test_only_real_known_changes_are_reported(self):
        old={"orcamento":200,"roas_objetivo":10}
        self.assertEqual(differences(old,{"orcamento":240,"roas_objetivo":9}),[
            ("orcamento",200.0,240.0),("roas_objetivo",10.0,9.0)])
        self.assertEqual(differences(old,{"orcamento":None,"roas_objetivo":10}),[])
    def test_reject_invalid_and_duplicate_values(self):
        self.assertEqual(differences({"orcamento":100,"roas_objetivo":10},
                                     {"orcamento":100,"roas_objetivo":float("nan")}),[])
        self.assertEqual(differences({"orcamento":100,"roas_objetivo":10},
                                     {"orcamento":-1,"roas_objetivo":10}),[])
    def test_history_labels_sources_and_escapes(self):
        html=display_history([{"campo":"orcamento","valor_anterior":100,
            "valor_novo":120,"observado_em":1792540000,"origem":"api"},
            {"campo":"roas_objetivo","valor_anterior":10,"valor_novo":9,
             "observado_em":1792540010,"origem":"painel"}])
        self.assertIn("Histórico de alterações",html)
        self.assertIn("Sincronização ML",html)
        self.assertIn("Ajuste no painel Keiper (local)",html)
        self.assertIn("10.00x",html)
        self.assertIn("9.00x",html)
    def test_render_shows_audit_and_no_false_preexisting_history(self):
        html=render(7,{"campanha_id":"10","nome":"Teste","status":"active"},
                    [],7,date(2026,10,20),changes=[])
        self.assertIn("Não existe histórico retroativo",html)

if __name__=="__main__":
    unittest.main()
