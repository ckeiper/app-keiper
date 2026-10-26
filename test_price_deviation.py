from datetime import timedelta
from decimal import Decimal
import unittest
from price_deviation import build,render
from test_price_stability import END,NOW,readings

def fixture(price=130):return readings(END-timedelta(days=13))+[dict(observed_at=NOW-60,confirmed=True,price=Decimal(price))]
class PriceDeviationTests(unittest.TestCase):
 def test_upper_lower_threshold_and_no_signal(self):
    for price,status in [(130,'alert'),(120,'alert'),(80,'alert'),(119,'no_signal'),(100,'no_signal')]:
        with self.subTest(price=price):self.assertEqual(build(fixture(price),END,NOW)['status'],status)
    d=build(fixture(130),END,NOW);self.assertEqual(d['median'],100);self.assertEqual(d['delta'],30)
 def test_current_failure_no_fallback_and_stale_or_future(self):
    rows=fixture();rows.append(dict(rows[-1],observed_at=NOW-1,confirmed=False))
    self.assertEqual(build(rows,END,NOW)['status'],'unknown')
    for age in (21601,-1):
        rows=fixture();rows[-1]['observed_at']=NOW-age;self.assertEqual(build(rows,END,NOW)['status'],'unknown')
    rows=fixture();rows.append(dict(rows[-1]));self.assertEqual(build(rows,END,NOW)['status'],'unknown')
 def test_reference_range_and_even_median(self):
    rows=fixture(120)
    for i,row in enumerate(rows[:-1]):row['price']=Decimal(80 if i<6 else 120)
    d=build(rows,END,NOW);self.assertEqual(d['median'],100);self.assertFalse(d['outside']);self.assertEqual(d['status'],'no_signal')
 def test_sparse_reference_and_missing_current_stay_pending(self):
    self.assertEqual(build(fixture()[:4]+fixture()[-1:],END,NOW)['status'],'unknown')
    self.assertEqual(build(fixture()[:-1],END,NOW)['status'],'unknown')
    self.assertIn('conferir o preço',render(fixture(),END,NOW));self.assertIn('Regra não acionada',render(fixture(100),END,NOW))
