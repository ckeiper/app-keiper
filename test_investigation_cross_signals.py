"""Regression tests for conservative explanation of listing declines."""
import unittest
from copy import deepcopy
from decimal import Decimal as D
from investigation_cross_signals import assess, render
from investigation_evidence import build
from test_investigation_evidence import END, ranking, visits


def fixture(before=100, now=50, old_orders=28, orders=7, old_value=1000, value=500):
    rank=ranking()
    rank['rows']['MLB1'].update(previous_orders=old_orders, orders=orders,previous_value=D(old_value),value=D(value))
    return build(rank,'MLB1',visits(before,now),[],[],END)


class CrossReadingTests(unittest.TestCase):
    def test_two_simultaneous_declines(self):
        data=fixture()
        self.assertEqual(assess(data,data['sales_for_cross'])['state'],'dupla')
        html=render(assess(data,data['sales_for_cross']))
        self.assertIn('Dois sinais simultâneos',html)
        self.assertIn('Visitas',html)
        self.assertIn('Pedidos pagos por visita',html)
        self.assertIn('não estabelece causa',html)

    def test_traffic_only(self):
        data=fixture(before=100,now=50,old_orders=20,orders=10,old_value=1000,value=500)
        self.assertEqual(assess(data,data['sales_for_cross'])['state'],'trafego')

    def test_efficiency_only(self):
        data=fixture(before=100,now=100,old_orders=20,orders=10,old_value=1000,value=500)
        self.assertEqual(assess(data,data['sales_for_cross'])['state'],'eficiencia')

    def test_decline_due_to_value_per_order(self):
        data=fixture(before=100,now=100,old_orders=20,orders=20,old_value=1000,value=500)
        self.assertEqual(assess(data,data['sales_for_cross'])['state'],'outros')

    def test_missing_data_and_small_sample_never_guess(self):
        data=fixture()
        data['traffic']['complete']=False
        self.assertEqual(assess(data,data['sales_for_cross'])['state'],'lacunas')
        data=fixture(before=20,now=10,old_orders=2,orders=1)
        self.assertEqual(assess(data,data['sales_for_cross'])['state'],'amostra')
        data=fixture()
        data['sales_verified']=False
        self.assertEqual(assess(data,data['sales_for_cross'])['state'],'incompleto')

    def test_no_sales_decline_is_not_failure(self):
        data=fixture(old_value=1000,value=1200)
        self.assertEqual(assess(data,data['sales_for_cross'])['state'],'sem_queda')

    def test_html_escaping(self):
        result=assess(fixture(),fixture()['sales_for_cross'])
        result['title']='<script>alert(1)</script>'
        html=render(result)
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>',html)


if __name__=='__main__':
    unittest.main()
