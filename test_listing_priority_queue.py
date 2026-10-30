import unittest
from decimal import Decimal as D
from listing_priority_queue import prioritize,render


def row(before,now):
    return dict(previous_value=D(before),value=D(now),
                previous_units=10,units=5,
                previous_orders=10,orders=5)


class PriorityQueueTests(unittest.TestCase):
    def test_sorted_by_verified_loss_not_status_badge(self):
        source=dict(available=True,rows={'MLB1':row('200','150'),'MLB2':row('1000','400'),
                                         'MLB3':row('120','100')})
        evidence={'MLB1':{'codes':['full'],'visits_days':14,'expected':14},
                  'MLB2':{'codes':['trafego'],'visits_days':10,'expected':14}}
        result=prioritize(source,evidence)
        self.assertEqual([x['item_id'] for x in result['items']],['MLB2','MLB1','MLB3'])
        self.assertEqual(result['items'][0]['loss'],D('600'))
        page=render(result,[{'item_id':'MLB2','titulo':'Produto teste'}],23)
        self.assertIn('Produto teste',page)
        self.assertIn('Abrir investigação',page)
        self.assertIn('10/14 dias',page)
        self.assertIn('/diagnostico/23/MLB2',page)

    def test_unverified_data_is_not_zero_or_priority(self):
        result=prioritize(dict(available=False,reason='Sem cobertura',rows={}))
        self.assertFalse(result['available'])
        self.assertIn('Aguardando cobertura verificada',render(result,[],23))

    def test_no_loss_does_not_raise_alert(self):
        result=prioritize(dict(available=True,rows={'MLB1':row('100','200')}))
        self.assertEqual(result['total'],0)
        self.assertIn('Não foram identificados',render(result,[],23))

    def test_compact_limits_to_three_without_losing_total(self):
        source=dict(available=True,rows={'MLB'+str(i):row('100','40') for i in range(10)})
        result=prioritize(source)
        output=render(result,[],42,compact=True)
        self.assertEqual(result['total'],10)
        self.assertEqual(output.count('class="kp-item"'),3)
        self.assertIn('10 anúncios com perda verificada',output)

    def test_untrusted_titles_escaped(self):
        result=prioritize(dict(available=True,rows={'MLB1':row('100','40')}))
        page=render(result,[{'item_id':'MLB1','titulo':'<script>x</script>'}],42)
        self.assertIn('&lt;script&gt;',page)
        self.assertNotIn('<script>x</script>',page)


if __name__=='__main__':
    unittest.main()
