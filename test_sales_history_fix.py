"""Regression guards for summary history and background refresh wiring."""
import pathlib
import unittest
from unittest.mock import Mock
from test_listing_details import main_function


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

    def test_only_summary_legacy_link_enqueues_full_refresh(self):
        enqueue, connect = Mock(), Mock(side_effect=AssertionError('synchronous collection'))
        ns=dict(pode_ver_loja=lambda cid:True,loja_habilitada_fila_persistente=lambda cid:False,
                enfileirar_atualizacao=enqueue,banco=connect,redirect=lambda path:path)
        route=main_function('atualizar_tipo',ns)
        self.assertEqual(route('vendas',5),'/vendas/5')
        self.assertEqual(route('resumo',5),'/painel/5')
        enqueue.assert_called_once_with(5)
        connect.assert_not_called()

    def test_uncovered_days_are_not_rendered_as_zero(self):
        self.assertIn("dias_cobertos", self.main)
        self.assertIn('else "—"', self.main)
        self.assertIn("Histórico de vendas em sincronização", self.main)


if __name__ == "__main__":
    unittest.main()
