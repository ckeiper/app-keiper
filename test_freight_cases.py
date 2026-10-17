"""Database schema and safe rendering tests without a live database."""
import unittest
from freight_cases import init_case_schema, render_cases


class FreightCasesTests(unittest.TestCase):
    def test_schema_is_idempotent_and_scoped(self):
        statements = []
        init_case_schema(None, lambda conn, sql: statements.append(sql))
        self.assertEqual(len(statements), 6)
        self.assertTrue(all("IF NOT EXISTS" in sql for sql in statements))
        for table in ("frete_chamados", "frete_chamados_historico", "frete_evidencias"):
            self.assertTrue(any("CREATE TABLE IF NOT EXISTS " + table in sql for sql in statements))
        self.assertTrue(all("conexao_id" in sql for sql in statements))
        self.assertTrue(any("CHECK (status IN" in sql for sql in statements))

    def test_case_list_escapes_untrusted_content(self):
        html = render_cases([{
            "id": 3,
            "status": "Pendente",
            "pedido_id": "<script>alert(1)</script>",
            "envio_id": '"><img src=x onerror=alert(1)>',
            "protocolo": "<b>123</b>",
        }], 7)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<b>123</b>", html)
        self.assertIn("/fretes/7/chamado/3", html)

    def test_manual_discrepancy_is_flagged_without_claiming_confirmation(self):
        from decimal import Decimal
        html = render_cases([{
            "id": 9, "status": "Pendente", "pedido_id": "123",
            "envio_id": "456", "protocolo": None,
            "ultima_avaliacao": "Possível divergência",
            "ultima_diferenca": Decimal("3.25"),
        }], 7)
        self.assertIn("R$ 3,25", html)
        self.assertIn("conferência manual", html)
        self.assertIn("Requer validação", html)

    def test_empty_list(self):
        self.assertIn("Nenhum chamado registrado", render_cases([], 4))


if __name__ == "__main__":
    unittest.main()
