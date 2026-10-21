import unittest
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal as D
from unittest.mock import Mock
from offer_history import record,price_events,load,render

BASE=int(datetime(2026,10,19,12,tzinfo=timezone(timedelta(hours=-3))).timestamp())

def observed(stamp,price,promotion=False,confirmed=True):
    return dict(observed_at=stamp,price=price,promotion=promotion,confirmed=confirmed)

class OfferHistoryTests(unittest.TestCase):
    def capture(self,data,error=None,status='active'):
        execute=Mock()
        record(None,execute,42,'MLB1',{'sale_price':dict(checked_at=BASE,data=data,error=error)},listing_status=status)
        return execute.call_args.args[2]

    def test_records_final_promo_price_and_no_invented_old_dates(self):
        params=self.capture(dict(amount=80,regular_amount=100,currency_id='BRL',metadata={'promotion_id':'promo'}))
        self.assertEqual(params,(42,'MLB1',BASE,D('80'),D('100'),True,True))
        params=self.capture(dict(amount=100,regular_amount=100,currency_id='BRL'))
        self.assertIs(params[-2],False)

    def test_failure_currency_invalid_price_or_inactive_never_reuses_old_price(self):
        for payload,error,status in [({'amount':80,'currency_id':'USD'},None,'active'),({'amount':80,'currency_id':'BRL'},'HTTP 403','active'),({'amount':'NaN','currency_id':'BRL'},None,'active'),({'amount':80,'currency_id':'BRL'},None,'paused')]:
            params=self.capture(payload,error,status)
            self.assertIsNone(params[3]);self.assertFalse(params[-1])

    def test_net_price_uses_tax_inclusive_amount_but_does_not_compare_net_regular(self):
        params=self.capture(dict(amount=80,amount_with_taxes=100,regular_amount=120,amount_tax_inclusion_type='net',currency_id='BRL'))
        self.assertEqual(params[3],100)
        self.assertIsNone(params[4]);self.assertIsNone(params[5])

    def test_observed_promotion_end_and_price_change(self):
        events=price_events([observed(BASE,80,True),observed(BASE+3600,100,False)])
        self.assertEqual(events[0]['delta'],25)
        self.assertTrue(events[0]['promotion_ended'])
        self.assertEqual(price_events([observed(BASE,80),observed(BASE+3600,80)]),[])

    def test_unknown_or_large_gap_breaks_comparison(self):
        self.assertEqual(price_events([observed(BASE,80),observed(BASE+100,None,confirmed=False),observed(BASE+3600,100)]),[])
        self.assertEqual(price_events([observed(BASE,80),observed(BASE+7*3600,100)]),[])
        self.assertEqual(price_events([observed(BASE,80)]),[])

    def test_reads_are_scoped_to_store_item_and_completed_dates(self):
        query=Mock(side_effect=[[],[],[],[]]);data=load(None,query,42,'MLB1',date(2026,10,20))
        self.assertEqual(query.call_count,4)
        for call in query.call_args_list:
            self.assertEqual(call.args[2][:2],(42,'MLB1'))
        self.assertIn('own_item_id=%s',query.call_args_list[2].args[1])
        self.assertIn('conexao_id=%s',query.call_args_list[3].args[1])
        self.assertEqual(data['own'],[])

    def test_empty_state_never_claims_stable_price(self):
        output=render(dict(own=[],targets=[],competitors=[],targets_limited=False,history_limited=False),42,'MLB1',date(2026,10,20))
        self.assertIn('não é possível afirmar',output)
        self.assertIn('meu_anuncio=MLB1',output)

    def test_competitor_changes_are_paged_filtered_and_escaped(self):
        rows=[dict(target_id=1,competitor_label='<script>',observed_at=BASE,price=D(80),previous_price=D(100),price_changed=True,full_changed=False,error='') for _ in range(21)]
        data=dict(own=[],targets=[],competitors=rows,targets_limited=False,history_limited=False)
        output=render(data,42,'MLB1',date(2026,10,20),args={'pagina_oferta':'2','alteracao_oferta':'preco'})
        self.assertIn('Página 2 de 3',output)
        self.assertEqual(output.count('<tr>'),11)
        self.assertNotIn('<script>',output)
        self.assertIn('alteracao_oferta=preco',output)
        output=render(data,42,'MLB1',date(2026,10,20),args={'alteracao_oferta':'full'})
        self.assertNotIn('<table>',output)

if __name__=='__main__':
    unittest.main()
