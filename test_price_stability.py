from copy import deepcopy
from datetime import date,datetime,timedelta
from decimal import Decimal
import unittest
from price_stability import build,render
from offer_history import BR
END=date(2026,10,26)
NOW=int(datetime(2026,10,26,23,59,tzinfo=BR).timestamp())
def readings(start=None):
    first=int(datetime.combine(start or END-timedelta(days=6),datetime.min.time(),BR).timestamp())+3600
    return [dict(observed_at=first+i*18000,price=Decimal('100.00'),confirmed=True) for i in range(12)]
class PriceStabilityTests(unittest.TestCase):
 def test_index_requires_explicit_coverage_and_compares_periods(self):
    rows=readings()+readings(END-timedelta(days=13));before=deepcopy(rows)
    data=build(rows,END,now=NOW)
    self.assertEqual(data['current']['score'],100);self.assertEqual(data['previous']['score'],100)
    self.assertEqual(data['current']['pairs'],11);self.assertEqual(data['current']['days'],3)
    self.assertEqual(rows,before)
    rows[-1]['price']=Decimal('110');data=build(rows,END,now=NOW)
    self.assertEqual(data['previous']['changes'],1);self.assertEqual(data['current']['changes'],0)
 def test_zero_score_is_real_not_missing_data(self):
    rows=readings()
    for i,row in enumerate(rows):row['price']=Decimal(100+i)
    data=build(rows,END,now=NOW)['current'];self.assertEqual(data['score'],0);self.assertEqual(data['amplitude'],11)
    self.assertIsNone(build([],END,now=NOW)['current']['score'])
 def test_failures_duplicates_and_gaps_break_pairs(self):
    rows=readings();rows[5]['confirmed']=False
    self.assertEqual(build(rows,END,now=NOW)['current']['pairs'],9)
    self.assertIsNone(build(rows,END,now=NOW)['current']['score'])
    rows=readings();rows.append(deepcopy(rows[5]));data=build(rows,END,now=NOW)['current'];self.assertEqual(data['pairs'],9)
    rows=readings();rows[6:]=[dict(r,observed_at=r['observed_at']+21600) for r in rows[6:]]
    self.assertEqual(build(rows,END,now=NOW)['current']['pairs'],10)
 def test_sparse_invalid_and_future_records_never_certify_stability(self):
    self.assertIsNone(build(readings()[:10],END,now=NOW)['current']['score'])
    rows=readings();rows.extend([dict(observed_at=NOW+1,confirmed=True,price=100),dict(observed_at=True,confirmed=True,price=100),None])
    data=build(rows,END,now=NOW)['current'];self.assertEqual(data['rejected'],3);self.assertIsNone(data['score'])
    for invalid in (None,True,-1,0,'NaN','Infinity'):
        rows=readings();rows[3]['price']=invalid
        self.assertIsNone(build(rows,END,now=NOW)['current']['score'])
 def test_daily_totals_scope_and_display_limit(self):
    data=build(readings(),END,now=NOW)['current']
    self.assertEqual(sum(r['valid'] for r in data['daily'].values()),12)
    self.assertEqual(sum(r['pairs'] for r in data['daily'].values()),11)
    self.assertTrue(build(readings()*500,END,now=NOW)['limited'])
    text=render(readings(),END,now=NOW);self.assertIn('Índice 100,0%',text);self.assertEqual(text.count('<tr><th scope="row">'),7)
    self.assertIn('não significa preço zero',text)
    self.assertIn('Índice não verificado',render([],END,now=NOW))
