import unittest
from decimal import Decimal as D
from sales_drivers import build, render
from investigation_evidence import build as evidence
from test_investigation_evidence import END, ranking, visits


def fixture(old_visits=700,new_visits=350,old_orders=14,orders=7,old_value=1400,value=700):
    e=dict(sales_verified=True,traffic=dict(complete=True,previous=dict(totals=dict(visitas=old_visits)),current=dict(totals=dict(visitas=new_visits))))
    sales=dict(previous_orders=old_orders,orders=orders,previous_value=D(str(old_value)),value=D(str(value)))
    return e,sales


def amounts(result):
    return [f['amount'] for f in result['factors']]


class SalesDriversTests(unittest.TestCase):
    def test_visits_only(self):
        result=build(*fixture())
        self.assertEqual(amounts(result),[D('-700'),D('0'),D('0')])
        self.assertEqual(result['main_negative'],'Visitas')

    def test_efficiency_only(self):
        result=build(*fixture(new_visits=700))
        self.assertEqual(amounts(result),[D('0'),D('-700'),D('0')])
        self.assertEqual(result['main_negative'],'Pedidos pagos ÷ visitas')

    def test_listing_value_per_order_only(self):
        result=build(*fixture(new_visits=700,orders=14,value=1120))
        self.assertEqual(amounts(result),[D('0'),D('0'),D('-280')])

    def test_positive_offsets_are_preserved_not_added_as_losses(self):
        result=build(*fixture(old_orders=28,old_value=1000,value=500))
        self.assertEqual(amounts(result),[D('-500'),D('-250'),D('250')])
        self.assertEqual(sum(amounts(result)),result['delta'])
        self.assertEqual(result['delta'],D('-500'))

    def test_displayed_cents_always_reconcile_in_fractional_ratios(self):
        for n in range(1,60):
            result=build(*fixture(old_visits=113+n,new_visits=71+n,old_orders=11,orders=n,old_value='199.99',value='123.45'))
            self.assertEqual(sum(amounts(result)),D('-76.54'))
            self.assertTrue(all(v.as_tuple().exponent==-2 for v in amounts(result)))

    def test_zero_denominators_missing_periods_and_invalid_values_block_estimate(self):
        for field in ('old_visits','new_visits','old_orders','orders'):
            self.assertFalse(build(*fixture(**{field:0}))['available'])
        for bad in (None,True,-1,'NaN','Infinity','1.5'):
            self.assertFalse(build(*fixture(new_visits=bad))['available'])
        e,s=fixture();e['sales_verified']=False
        self.assertFalse(build(e,s)['available'])
        e,s=fixture();e['traffic']['complete']=False
        self.assertFalse(build(e,s)['available'])

    def test_verified_zero_revenue_and_growth_are_allowed_without_dividing_by_revenue(self):
        result=build(*fixture(old_value=0,value=100))
        self.assertEqual(amounts(result),[D('0'),D('0'),D('100')])
        self.assertIsNone(result['main_negative'])
        result=build(*fixture(old_value=100,value=0))
        self.assertEqual(sum(amounts(result)),D('-100'))

    def test_integration_uses_same_listing_sales_and_complete_visits(self):
        e=evidence(ranking(),'MLB1',visits(),[],[],END)
        self.assertTrue(e['drivers']['available'])
        self.assertEqual(e['drivers']['delta'],D('-500'))
        e=evidence(ranking(),'MLB1',visits()[:-1],[],[],END)
        self.assertFalse(e['drivers']['available'])

    def test_stable_total_does_not_headline_an_offset_as_a_decline(self):
        result=build(*fixture(orders=14,value=1400))
        self.assertEqual(result['delta'],0)
        self.assertIsNone(result['main_negative'])
        self.assertNotIn('Maior parcela negativa:',render(result))

    def test_render_shows_offsets_scope_and_escapes_unknown_reason(self):
        output=render(build(*fixture(old_orders=28,old_value=1000,value=500)))
        self.assertIn('+ R$ 250,00',output)
        self.assertIn('não comprova causalidade',output)
        self.assertIn('não equivale ao preço anunciado',output)
        self.assertIn('Variação total do faturamento',output)
        self.assertIn('&lt;script&gt;',render(dict(available=False,reason='<script>')))

if __name__=='__main__':
    unittest.main()
