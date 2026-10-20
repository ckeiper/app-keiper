"""Verify navigation state, exact chart gaps and escaping without a browser."""
import unittest
from management_design import active_tab,panel,daily_chart,metric_card


class ManagementDesignTests(unittest.TestCase):
    def test_filter_navigation_keeps_the_relevant_panel_visible(self):
        self.assertEqual(active_tab({}),'overview')
        self.assertEqual(active_tab({'area':'estoque'}),'actions')
        self.assertEqual(active_tab({'visao':'queda'}),'analysis')
        self.assertEqual(active_tab({'aba':'analysis','area':'estoque'}),'analysis')
        self.assertEqual(active_tab({'aba':'invalid'}),'overview')
        self.assertNotIn(' hidden',panel('actions','actions'))
        self.assertIn(' hidden',panel('actions','overview'))

    def test_chart_does_not_connect_unknown_days_or_invent_zeroes(self):
        report={'current':{'daily':[100,None,200],'days':['2026-10-17','2026-10-18','2026-10-19']},
                'previous':{'daily':[None,None,None],'days':['2026-10-14','2026-10-15','2026-10-16']}}
        chart=daily_chart(report)
        self.assertEqual(chart.count("<path d='M"),2)
        self.assertIn('R$ 100,00',chart)
        self.assertIn('R$ 200,00',chart)
        self.assertIn('Indisponível',chart)
        self.assertNotIn('nan',chart.lower())
        report['current']['daily']=[None,None,None]
        self.assertNotIn('<svg',daily_chart(report))

    def test_card_escapes_content_and_preserves_no_data_state(self):
        card=metric_card('<script>','Indisponível','texto <b>')
        self.assertIn('&lt;script&gt;',card)
        self.assertIn('mgmt-stat-empty',card)
        self.assertNotIn('<script>',card)
        self.assertIn('R$ 0,00',metric_card('Faturamento de pedidos pagos','R$ 0,00','Valor confirmado'))
