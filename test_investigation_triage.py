import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from investigation_evidence import build, render
from test_investigation_evidence import END, DATES, ranking, visits, stock, advertising


def offer(day=END, hour=12, price=100, confirmed=True):
    return dict(observed_at=int(datetime.combine(day,datetime.min.time(),ZoneInfo('America/Sao_Paulo')).replace(hour=hour).timestamp()),price=price,confirmed=confirmed)


def evidence(offers=None, full=None, verified=True, traffic=None):
    return build(ranking() if verified else dict(available=False),'MLB1',visits() if traffic is None else traffic,
                 full or [],advertising(),END,offers=offers)


class InvestigationTriageTests(unittest.TestCase):
    def test_prioritize_listing_checks_and_keep_shop_ads_last(self):
        result=evidence([offer(hour=9,price=80),offer(price=100)],[stock(END,'empty')])
        self.assertEqual([a['code'] for a in result['actions']],['full','preco','eficiencia','trafego','ads_loja'])
        self.assertEqual(result['triage']['loss'],Decimal('500'))
        self.assertTrue(all(a['follow_up'] for a in result['actions']))
        self.assertIn('não atribuído',result['actions'][-1]['scope'])

    def test_recovered_full_is_not_the_first_replenishment_recommendation(self):
        result=evidence(full=[stock(DATES[-2],'empty'),stock(END,'available')])
        self.assertEqual([a['code'] for a in result['actions']],['eficiencia','trafego','full','ads_loja'])
        full=next(a for a in result['actions'] if a['code']=='full')
        self.assertIn('já mostra Full com estoque',full['action'])

    def test_price_requires_threshold_and_six_hour_adjacent_observations(self):
        for rows in ([offer(hour=9,price=100),offer(price=104)],
                     [offer(hour=1,price=80),offer(price=100)]):
            self.assertNotIn('preco',[a['code'] for a in evidence(rows)['actions']])
        self.assertIn('preco',[a['code'] for a in evidence([offer(hour=9,price=100),offer(price=105)])['actions']])

    def test_later_unknown_or_reversal_blocks_price_recommendation(self):
        for last in (offer(hour=15,price=None,confirmed=False),offer(hour=15,price=80)):
            result=evidence([offer(hour=9,price=80),offer(price=100),last])
            self.assertNotIn('preco',[a['code'] for a in result['actions']])

    def test_old_or_future_increases_are_not_in_this_period(self):
        for day in (END-timedelta(days=8),END+timedelta(days=1)):
            result=evidence([offer(day,hour=9,price=80),offer(day,price=100)])
            self.assertNotIn('preco',[a['code'] for a in result['actions']])

    def test_missing_data_does_not_become_a_cause_or_zero(self):
        result=evidence(verified=False,traffic=[])
        self.assertEqual(result['triage']['status'],'incompleto')
        self.assertIsNone(result['triage']['loss'])
        self.assertEqual(result['actions'],[])
        output=render(result,1,END)
        self.assertIn('Primeira verificação sugerida:</b> validar cobertura',output)
        self.assertIn('lacunas não são zero',output)
        self.assertNotIn('Queda confirmada:',output)

    def test_price_coverage_uses_latest_daily_reading_including_invalid(self):
        result=evidence([offer(hour=9,price=80),offer(price=None,confirmed=False)])
        self.assertTrue(any('Preço próprio: 0/14 dias' in gap for gap in result['triage']['gaps']))

    def test_duplicate_visit_day_stays_unknown_in_daily_inspection(self):
        traffic=visits()+[dict(dia=END,visitas=999)]
        output=render(evidence(traffic=traffic),1,END)
        self.assertIn('<td>20/10/2026</td><td>Sem dado válido</td>',output)
        self.assertNotIn('<td>999</td>',output)

    def test_no_decline_has_no_loss_amount(self):
        rank=ranking();rank['rows']['MLB1']['value']=Decimal('1200')
        result=build(rank,'MLB1',visits(),[],advertising(),END)
        self.assertEqual(result['triage']['status'],'sem_queda')
        self.assertIsNone(result['triage']['loss'])
        self.assertIn('Sem queda confirmada neste recorte',render(result,1,END))

    def test_render_loss_follow_up_and_no_recovery_promise(self):
        result=evidence([offer(hour=9,price=80),offer(price=100)])
        result['actions'][0]['follow_up']='<script>unsafe</script>'
        output=render(result,1,END)
        self.assertIn('Queda confirmada: R$ 500,00',output)
        self.assertIn('não é uma estimativa de recuperação',output)
        self.assertIn('Como acompanhar:',output)
        self.assertIn('&lt;script&gt;unsafe&lt;/script&gt;',output)
        self.assertNotIn('<script>unsafe',output)
        self.assertEqual(output.count("<article class='evidence-action'>"),output.count('</article>'))

if __name__=='__main__':
    unittest.main()
