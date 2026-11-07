import unittest
from copy import deepcopy
from datetime import date,datetime
from promotion_overlap import analyze,render
from test_promotion_observations import promotion,reading,TODAY
from promotion_comparison import render as render_report

START=date(2026,10,1);END=date(2026,10,7)


class OverlapTests(unittest.TestCase):
    def test_intersection_clipping_timezone_and_exclusive_boundaries(self):
        rows=[promotion(),promotion(id='partial',start='2026-10-02T15:00:00Z',end='2026-10-04T18:00:00-03:00'),
            promotion(id='entire',start='2026-09-01T00:00:00-03:00',end='2026-11-01T00:00:00-03:00'),
            promotion(id='before',end='2026-10-01T03:00:00Z',start='2026-09-01T00:00:00Z'),
            promotion(id='after',start='2026-10-08T03:00:00Z')]
        before=deepcopy(rows);data=analyze(rows,0,START,END)
        self.assertEqual(rows,before);self.assertTrue(data['available'])
        self.assertEqual((data['total'],data['counts']['checked']),(2,4))
        whole,partial=data['rows']
        self.assertEqual((whole['id'],whole['start'],whole['end']),('entire',data['start'],data['end']))
        self.assertEqual(partial['start'].isoformat(),'2026-10-02T12:00:00-03:00')
        self.assertEqual(partial['end'].isoformat(),'2026-10-04T18:00:00-03:00')

    def test_unverified_inactive_variation_and_conditional_are_separate(self):
        rows=[promotion(),promotion(id='bad-date',start='2026-10-02T00:00:00'),
            promotion(id='reversed',start='2026-10-06T00:00:00Z',end='2026-10-05T00:00:00Z'),
            promotion(id='candidate',status='candidate'),promotion(id='finished',status='finished'),
            promotion(id='variation',variation_id='123'),promotion(id='conditional',type='BANK'),promotion(id=None)]
        data=analyze(rows,0,START,END)
        self.assertEqual(data['counts'],dict(unknown=3,not_active=2,variation=1,unsupported=1,checked=0))
        self.assertEqual(data['total'],0)
        self.assertIn('Nenhuma coincidência verificável',render(data))
        self.assertIn('não comprova ausência',render(data))

    def test_before_and_during_keep_their_own_windows_and_shared_offer_is_not_added(self):
        rows=[promotion(),promotion(id='OLD',start='2026-09-20T00:00:00-03:00',end='2026-09-28T00:00:00-03:00'),
              promotion(id='NEW',start='2026-10-02T00:00:00-03:00'),
              promotion(id='BOTH',start='2026-09-20T00:00:00-03:00')]
        old=analyze(rows,0,date(2026,9,24),date(2026,9,30),phase='before')
        current=analyze(rows,0,START,END)
        self.assertEqual({r['id'] for r in old['rows']},{'OLD','BOTH'})
        self.assertEqual({r['id'] for r in current['rows']},{'NEW','BOTH'})
        self.assertTrue(all(r['end']<=old['end'] for r in old['rows']))
        text=render(current,old)
        self.assertEqual(text.count('BOTH</td>'),2)
        self.assertIn('Antes · coincidências verificadas: <strong>2',text)
        self.assertIn('Dentro do calendário · coincidências verificadas: <strong>2',text)
        self.assertFalse(analyze(rows,0,START,END,phase='before')['available'])
        self.assertFalse(analyze(rows,0,START,END,phase='unknown')['available'])

    def test_duplicate_identities_are_deduplicated_or_flagged_not_arbitrarily_selected(self):
        other=promotion(id='P2')
        data=analyze([promotion(),promotion(),other,deepcopy(other)],0,START,END)
        self.assertEqual((data['total'],data['duplicates']),(1,2))
        conflict=dict(other,status='finished')
        data=analyze([promotion(),other,conflict],0,START,END)
        self.assertEqual((data['total'],data['counts']['unknown']),(0,1))
        self.assertFalse(analyze([promotion(),promotion(price='79')],0,START,END)['available'])
        # An explicit different offer ID distinguishes two offers in the same campaign.
        data=analyze([promotion(conditions=dict(offer_id='a')),promotion(conditions=dict(offer_id='b'))],0,START,END)
        self.assertEqual(data['total'],1);self.assertEqual(data['rows'][0]['offer_id'],'b')

    def test_incomplete_selected_identity_or_window_never_produces_zero_claim(self):
        cases=[([],0,START,END),([promotion()],True,START,END),([promotion()],1,START,END),
            ([promotion()],0,END,START),([promotion()],0,datetime(2026,10,1),END),
            ([promotion()],0,START,date.max),([promotion(id=None)],0,START,END),
            ([promotion(status='candidate')],0,START,END),([promotion(variation_id='1')],0,START,END),
            ([promotion(start='2026-10-02T00:00:00-03:00')],0,START,END),
            ([promotion(conditions=None)],0,START,END),([promotion()]*201,0,START,END)]
        for args in cases:
            with self.subTest(args=str(args)[:100]):
                data=analyze(*args);self.assertFalse(data['available'])
                self.assertNotIn('coincidências verificadas:',render(data).lower())

    def test_display_cap_does_not_silently_shrink_total_or_change_order(self):
        rows=[promotion()]+[promotion(id='P'+str(i)) for i in range(2,201)]
        data=analyze(rows,0,START,END)
        self.assertEqual(data['total'],199);self.assertEqual(len(data['rows']),20)
        self.assertTrue(data['limited']);self.assertIn('primeiras 20 interseções de 199',render(data))

    def test_markup_escapes_and_no_sales_or_discount_attribution(self):
        data=analyze([promotion(),promotion(id='<script>bad()</script>',conditions=dict(offer_id='<img>'),name='<svg>')],0,START,END)
        text=render(data)
        self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text)
        self.assertNotIn('<img>',text);self.assertNotIn('<svg>',text);self.assertIn('descontos não são somados',text)
        self.assertIn('participação contínua',text);self.assertIn('tabindex="0"',text)
        self.assertIn('fim exclusivo',text)

    def test_report_uses_only_selected_reading_and_comparison_window(self):
        s=reading();s['promotions']+=[promotion(id='THIS_READING')]
        older=reading();older['id']=2;older['promotions']=[promotion(id='OTHER_READING')]
        from promotion_observations import periods
        selection=periods(promotion(),TODAY)
        paired=[dict(start=selection['previous_start'],end=selection['previous_end'],sales={},visits=None),
                dict(start=selection['start'],end=selection['end'],sales={},visits=None)]
        result=dict(available=True,periods=paired,finance=dict(available=False,reason='Sem custos'))
        text=render_report(7,'MLB1','Produto',[older,s],2,1,1,s,0,result,7,TODAY)
        section=text.split('class="card pc-overlap">')[1].split('</section>')[0]
        self.assertIn('THIS_READING',section);self.assertNotIn('OTHER_READING',section)
