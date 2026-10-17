"""Regression guards for summary history and background refresh wiring."""
import pathlib
import unittest


class SalesHistoryFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = pathlib.Path("main.py").read_text(encoding="utf-8")
        cls.sync = pathlib.Path("sales_sync.py").read_text(encoding="utf-8")

    def test_summary_uses_bounded_seven_day_history_without_100_order_limit(self):
        self.assertIn("calcular_vendas(cid, inicio=inicio_semana)", self.main)
        self.assertIn("AND LEFT(fechado_em,10) >= %s", self.main)
        self.assertIn("ORDER BY fechado_em DESC LIMIT 100", self.main)
        self.assertIn("pi.pedido_id = ANY(%s)", self.main)

    def test_manual_sales_refresh_is_queued(self):
        start = self.main.index("def atualizar_tipo(tipo, cid):")
        route = self.main[start:self.main.index('@app.route("/atualizar")', start)]
        self.assertLess(route.index('if tipo in ("resumo", "vendas"):'),
                        route.index('    with banco() as conn:'))
        self.assertIn("enfileirar_atualizacao(cid)", route)

    def test_uncovered_days_are_not_rendered_as_zero(self):
        self.assertIn("dias_cobertos", self.main)
        self.assertIn('else "—"', self.main)
        self.assertIn("Histórico de vendas em sincronização", self.main)


if __name__ == "__main__":
    unittest.main()
