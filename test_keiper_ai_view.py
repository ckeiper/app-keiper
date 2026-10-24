import unittest
from decimal import Decimal
from keiper_ai_view import chart, render


class ObservatoryTests(unittest.TestCase):
    def test_missing_days_remain_unknown_and_gaps_are_not_connected(self):
        rows=[dict(data='2026-10-16',gasto=5,faturamento=100),dict(data='2026-10-18',gasto=0,faturamento=0)]
        html=chart(rows,'2026-10-22')
        self.assertIn('2/7 dias',html)
        self.assertIn('Indisponível',html)
        self.assertIn('R$ 0,00',html)
        self.assertNotIn('L',html.split("data-series='revenue'",1)[1].split('</g>',1)[0].split("d='",1)[1].split("'",1)[0])

    def test_no_result_still_displays_admin_budget_and_failure_state(self):
        html=render(None,status='failed',budget=dict(used=Decimal('50'),limit=Decimal('50'),alert='Bloqueio de novas chamadas.'))
        self.assertIn('Execução com falha',html)
        self.assertIn('R$ 50,00',html)
        self.assertIn('Bloqueio de novas chamadas.',html)

    def test_customer_budget_is_not_inferred_and_untrusted_fields_escape(self):
        html=render(dict(start='2026-10-16',end='2026-10-22',quality=['<img src=x>'],recommendations=[],interpretation='<script>bad</script>'),api_status='<script>bad</script>')
        self.assertNotIn('<img',html)
        self.assertNotIn('<script>bad',html)
        self.assertIn('&lt;script&gt;bad',html)
        self.assertNotIn('todas as lojas',html)

    def test_invalid_numeric_data_is_not_graphed(self):
        for bad in [float('nan'),float('inf'),-1,None]:
            self.assertIn('Histórico de Ads indisponível',chart([dict(data='2026-10-22',gasto=bad,faturamento=bad)],'2026-10-22'))
