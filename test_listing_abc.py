import html
import unittest
from copy import deepcopy
from decimal import Decimal as D
from urllib.parse import urlsplit, parse_qs
from listing_abc import build, classify, render
from test_listing_comparison import END


def fixture():
    values=[800,100,60,20,10]+[1]*20+[0]*3
    ranking=dict(available=True,rows={f'MLB{i}':dict(value=D(value),previous_value=D(value)) for i,value in enumerate(values,1)})
    listings=[dict(item_id=item,titulo='Produto '+item) for item in ranking['rows']]
    return ranking,listings


class ListingABCTests(unittest.TestCase):
    def test_exact_cutoffs_and_group_crossing_stays_in_category(self):
        c=classify({'MLB1':D(80),'MLB2':D(15),'MLB3':D(5)})
        self.assertEqual([r['category'] for r in c['rows'].values()],['A','B','C'])
        c=classify({'MLB1':D(79),'MLB2':D(10),'MLB3':D(7),'MLB4':D(4)})
        self.assertEqual([r['category'] for r in c['rows'].values()],['A','A','B','C'])
        self.assertEqual(sum(r['share'] for r in c['rows'].values()),D(100))

    def test_ties_never_split_and_order_is_deterministic(self):
        values={'MLB4':D(5),'MLB3':D(5),'MLB2':D(45),'MLB1':D(45)}
        c=classify(values)
        self.assertEqual(list(c['rows']),['MLB1','MLB2','MLB3','MLB4'])
        self.assertEqual([r['category'] for r in c['rows'].values()],['A','A','B','B'])
        self.assertEqual(c,classify(dict(reversed(list(values.items())))))

    def test_zero_total_and_zero_item_do_not_invent_share_or_sales(self):
        c=classify({'MLB1':D(0),'MLB2':D(0)})
        self.assertTrue(all(r['category']=='sem_valor' and r['share'] is None for r in c['rows'].values()))
        c=classify({'MLB1':D(10),'MLB2':D(0)})
        self.assertEqual(c['rows']['MLB2']['category'],'sem_valor')
        self.assertEqual(c['rows']['MLB2']['share'],0)
        r,l=fixture()
        for row in r['rows'].values():row.update(value=D(0),previous_value=D(0))
        text=render(1,r,l,{},END)
        self.assertIn('Sem base percentual',text);self.assertNotIn('0,00%',text)
        self.assertIn('não comprova ausência de pedidos',text)

    def test_invalid_or_partial_source_is_pending_and_never_partial_classification(self):
        for value in [None,True,'bad',D('NaN'),D('Infinity'),-1]:
            r,l=fixture();r['rows']['MLB1']['value']=value
            self.assertFalse(build(r)['available'])
            self.assertNotIn('<table',render(1,r,l,{},END))
        r,l=fixture();r['available']=False
        self.assertIn('Dados incompletos não são zero',render(1,r,l,{},END))
        r,l=fixture();r['rows']['MLB1'].pop('previous_value')
        self.assertFalse(build(r)['available'])
        r,l=fixture();r['rows']['<script>']=r['rows'].pop('MLB1')
        self.assertFalse(build(r)['available'])

    def test_independent_previous_classification_and_immutable_inputs(self):
        r,l=fixture();r['rows']['MLB1']['previous_value']=D(0)
        r['rows']['MLB3']['previous_value']=D(10000)
        original=deepcopy([r,l]);model=build(r)
        self.assertEqual(model['current']['rows']['MLB1']['category'],'A')
        self.assertEqual(model['previous']['rows']['MLB1']['category'],'sem_valor')
        self.assertEqual(model['previous']['rows']['MLB3']['category'],'A')
        render(1,r,l,{},END)
        self.assertEqual([r,l],original)

    def test_filter_and_search_keep_global_classes_and_totals(self):
        r,l=fixture()
        text=render(1,r,l,dict(abc_classe='C',abc_busca='MLB4'),END)
        self.assertIn('Total verificado: R$ 1.010,00',text)
        self.assertIn('MLB4</small>',text);self.assertNotIn('MLB1</small>',text)
        self.assertIn('C → C',text)
        self.assertIn('Nenhum anúncio',render(1,r,l,dict(abc_busca='inexistente'),END))
        self.assertIn('Sem valor → Sem valor',render(1,r,l,dict(abc_classe='sem_valor'),END))

    def test_pagination_clamping_and_parameter_whitelist(self):
        r,l=fixture()
        text=render(1,r,l,dict(abc_pagina='1',comparar1='MLB1',comparar2='MLB2',modo='prioridades',foreign='secret'),END,30)
        self.assertEqual(text.count('<tr><th scope="row">'),20)
        import re
        url=html.unescape(re.search(r'<a href="([^"]+)">Próxima',text).group(1))
        params=parse_qs(urlsplit(url).query)
        self.assertEqual(params['dias'],['30']);self.assertEqual(params['comparar2'],['MLB2'])
        self.assertEqual(params['abc_pagina'],['2']);self.assertNotIn('foreign',params);self.assertNotIn('modo',params)
        text=render(1,r,l,dict(abc_pagina='999'),END)
        self.assertIn('Página 2 de 2',text);self.assertEqual(text.count('<tr><th scope="row">'),8)
        for page in ['bad','0','-1',None]:
            self.assertIn('Página 1 de 2',render(1,r,l,dict(abc_pagina=page),END))

    def test_escaping_names_search_and_correct_windows(self):
        r,l=fixture();l[0]['titulo']='<script>alert(1)</script>'
        text=render(1,r,l,{},END)
        self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text)
        self.assertIn('17/10/2026 a 23/10/2026',text);self.assertIn('10/10/2026 a 16/10/2026',text)
        text=render(1,r,l,dict(abc_busca='" onfocus="alert(1)'),END,30)
        self.assertIn('&quot; onfocus=&quot;',text)
        self.assertIn('24/09/2026 a 23/10/2026',text);self.assertIn('25/08/2026 a 23/09/2026',text)

    def test_previous_zero_shows_absence_of_percentage_basis(self):
        r,l=fixture()
        for row in r['rows'].values():row['previous_value']=D(0)
        text=render(1,r,l,{},END)
        self.assertIn('Sem base anterior → A',text)
        self.assertIn('não comprova crescimento ou queda',text)

    def test_empty_verified_store_is_explicit_and_no_database_work(self):
        text=render(1,dict(available=True,rows={}),[],{},END)
        self.assertIn('0 anúncios',text);self.assertIn('Total verificado: R$ 0,00',text)
        self.assertNotIn('<table',text)
