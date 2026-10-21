import json
import re
import unittest
from datetime import date,datetime,timedelta,timezone
from listing_timeline import build,render

END=date(2026,10,20)

def stamp(day,h=12):
    return int(datetime.combine(day,datetime.min.time(),timezone(timedelta(hours=-3))).replace(hour=h).timestamp())

class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.covered=[(END-timedelta(days=i)).isoformat() for i in range(14)]

    def test_completed_dates_and_known_zero_never_replace_gaps(self):
        visits=[dict(dia=END,visitas=0)]
        data=build('MLB1',[],[],self.covered,[],visits,[],END)
        self.assertEqual(data['dates'][-1],END.isoformat())
        self.assertEqual(data['dates'][0],'2026-10-07')
        self.assertEqual(data['sales'],[0.0]*14)
        self.assertEqual(data['visits'],[None]*13+[0])
        self.assertEqual(data['prices'],[None]*14)

    def test_latest_unknown_price_is_a_gap_and_never_carries_to_next_day(self):
        offers=[dict(observed_at=stamp(END-timedelta(days=2)),confirmed=True,price=100),
                dict(observed_at=stamp(END,9),confirmed=True,price=90),
                dict(observed_at=stamp(END,18),confirmed=False,price=None)]
        data=build('MLB1',[],[],self.covered,[],[],offers,END)
        self.assertEqual(data['prices'][-3:],[100.0,None,None])

    def test_full_is_only_explicit_daily_observation(self):
        full=[dict(observed_at=stamp(END),state='empty',logistics='fulfillment')]
        data=build('MLB1',[],[],self.covered,full,[],[],END)
        self.assertEqual(data['full'],[None]*13+[0])

    def test_unverified_sales_and_invalid_traffic_remain_unknown(self):
        data=build('MLB1',[],[],self.covered,[],[dict(dia=END,visitas=-1)],[],END,pending=True)
        self.assertEqual(data['sales'],[None]*14)
        self.assertIsNone(data['visits'][-1])

    def test_event_points_are_aligned_to_category_dates_for_tooltip_accuracy(self):
        offers=[dict(observed_at=stamp(END,9),confirmed=True,price=80,promotion=True),dict(observed_at=stamp(END,12),confirmed=True,price=100,promotion=False)]
        output=render('MLB1',[],[],self.covered,[],[],offers,END)
        raw=re.search(r'new Chart\(el,\{data:(.*?),options:',output).group(1)
        payload=json.loads(raw)
        for dataset in payload['datasets']:
            self.assertEqual(len(dataset['data']),len(payload['labels']))
        events=payload['datasets'][-1]['data']
        self.assertEqual(events[:-1],[None]*13)
        self.assertEqual(events[-1]['x'],END.isoformat())
        self.assertIn('80.00 → R$ 100.00',events[-1]['note'])

    def test_daily_table_pagination_and_filters_are_preserved(self):
        output=render('MLB1',[],[],self.covered,[],[],[],END,args={'comparar_linha':'preco','pagina_linha':'2','busca_queda':'"><script>'})
        self.assertIn('Página 2 de 2',output)
        self.assertEqual(output.count('<tr>'),8)
        self.assertIn('comparar_linha=preco',output)
        self.assertNotIn('value=\'"><script>',output)
        output=render('MLB1',[],[],self.covered,[],[],[],END,args={'janela_linha':'7'})
        self.assertIn('Página 1 de 1',output)
        self.assertIn('Vendas: 7/7 dias',output)

if __name__=='__main__':
    unittest.main()
