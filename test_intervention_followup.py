import unittest
from datetime import date, timedelta

from intervention_followup import assess, render
from listing_interventions import compare

DAY=date(2026,9,20)
ITEM='MLB100'


def scenario(first=200, second=180, baseline=100, missing=False, pending=False):
    orders=[]; items=[]; coverage=[]; visits=[]
    for offset in list(range(-7,0))+list(range(1,15)):
        day=DAY+timedelta(days=offset)
        amount=baseline if offset<0 else first if offset<=7 else second
        if missing and offset==13:
            continue
        key=day.isoformat()
        coverage.append(key)
        orders.append(dict(conexao_id=1,pedido_id=key,status='paid',total=amount,
                           moeda='BRL',criado_em=key+'T12:00:00-03:00',
                           pagamentos_json=[dict(status='approved')],unidades=1))
        items.append(dict(conexao_id=1,pedido_id=key,item_id=ITEM,quantidade=1,preco_unitario=amount))
        visits.append(dict(dia=day,visitas=30))
    today=DAY+timedelta(days=15)
    first_comparison=compare(ITEM,DAY,orders,items,coverage,visits,today,pending=pending)
    return assess(ITEM,DAY,today,orders,items,coverage,visits,first_comparison,pending=pending)


class SustainedFollowupTests(unittest.TestCase):
    def test_two_complete_weeks_are_sustained_without_claiming_causality(self):
        result=scenario()
        self.assertEqual(result['state'],'sustentada')
        page=render(result)
        self.assertIn('A recuperação se manteve?',page)
        self.assertIn('não comprova',page)
        self.assertIn('R$ 700,00',page)

    def test_reversal_and_oscillation(self):
        self.assertEqual(scenario(first=200,second=80)['state'],'reversao')
        self.assertEqual(scenario(first=200,second=110)['state'],'oscilacao')

    def test_no_recovery(self):
        self.assertEqual(scenario(first=90,second=85)['state'],'sem_recuperacao')

    def test_missing_coverage_and_unverified_orders_never_become_zero(self):
        self.assertEqual(scenario(missing=True)['state'],'indisponivel')
        self.assertEqual(scenario(pending=True)['state'],'indisponivel')

    def test_second_week_requires_all_completed_days(self):
        rows=scenario()
        self.assertEqual(rows['state'],'sustentada')
        # No query should be needed to know that the last day remains open.
        from listing_interventions import compare
        first=compare(ITEM,DAY,[],[],[],[],DAY+timedelta(days=14))
        result=assess(ITEM,DAY,DAY+timedelta(days=14),[],[],[],[],first)
        self.assertEqual(result['state'],'aguardando')
        self.assertEqual(result['closed_days'],6)

if __name__=='__main__':
    unittest.main()
