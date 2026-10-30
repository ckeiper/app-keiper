import unittest
from copy import deepcopy
from decimal import Decimal as D
from listing_comparison_stock import cells, render
from listing_comparison import render as comparison
from test_listing_comparison import sample, END

NOW = 1792846800

class ComparisonStockTests(unittest.TestCase):
    def fixture(self):
        ranking, listings = sample()
        for row in listings:
            row.update(quantidade=12, atualizado_em=NOW)
        return ranking, listings

    def test_exact_observed_basis_two_windows_never_mixed_and_immutable(self):
        ranking, listings = self.fixture()
        original = deepcopy([ranking, listings])
        values = cells(listings, ranking, ['MLB1','MLB2'], 7, NOW)
        self.assertEqual(values['MLB1'][0], '12 unidades')
        self.assertEqual(values['MLB1'][2], '3 unidades em 7 dias encerrados')
        self.assertEqual(values['MLB1'][3], '28,00 dias')
        self.assertEqual(values['MLB2'][3], '14,00 dias')
        self.assertIn('Brasília', values['MLB1'][1])
        self.assertEqual([ranking,listings], original)

    def test_stale_future_invalid_missing_and_duplicate_never_show_stock(self):
        ranking, listings = self.fixture()
        for stamp in [NOW-21601,NOW+1,True,0,None,'bad',float('nan'),NOW-.5]:
            listings[0]['atualizado_em']=stamp
            self.assertEqual(cells(listings,ranking,['MLB1'],7,NOW)['MLB1'],['Indisponível']*4)
        listings[0]['atualizado_em']=NOW-21600
        self.assertEqual(cells(listings,ranking,['MLB1'],7,NOW)['MLB1'][0],'12 unidades')
        self.assertEqual(cells(listings+[listings[0]],ranking,['MLB1'],7,NOW)['MLB1'],['Indisponível']*4)
        self.assertEqual(cells([],ranking,['MLB1'],7,NOW)['MLB1'],['Indisponível']*4)

    def test_zero_stock_preserved_and_zero_sales_never_infinite(self):
        ranking, listings = self.fixture();listings[0]['quantidade']=0
        self.assertEqual(cells(listings,ranking,['MLB1'],7,NOW)['MLB1'][3],'0,00 dias')
        for units in [0,True,-1,D('1.5'),None]:
            ranking['rows']['MLB1']['units']=units
            values=cells(listings,ranking,['MLB1'],7,NOW)['MLB1']
            self.assertEqual(values[0],'0 unidades')
            self.assertEqual(values[2],'Sem vendas positivas verificadas')
            self.assertEqual(values[3],'Indisponível')

    def test_invalid_stock_and_unverified_sales_do_not_produce_coverage(self):
        ranking,listings=self.fixture()
        for stock in [True,-1,D('.5'),None,'bad']:
            listings[0]['quantidade']=stock
            self.assertEqual(cells(listings,ranking,['MLB1'],7,NOW)['MLB1'],['Indisponível']*4)
        listings[0]['quantidade']=12;ranking['available']=False
        self.assertEqual(cells(listings,ranking,['MLB1'],7,NOW)['MLB1'][3],'Indisponível')

    def test_coverage_truncates_and_uses_selected_thirty_day_period(self):
        ranking,listings=self.fixture();listings[0]['quantidade']=1
        ranking['rows']['MLB1']['units']=10000
        self.assertEqual(cells(listings,ranking,['MLB1'],7,NOW)['MLB1'][3],'<0,01 dias')
        ranking['rows']['MLB1']['units']=7
        self.assertEqual(cells(listings,ranking,['MLB1'],30,NOW)['MLB1'][3],'4,28 dias')

    def test_render_scope_escaping_and_pending_selection(self):
        ranking,listings=self.fixture()
        text=render(listings,ranking,['MLB1','MLB2'],{'MLB1':'<script>'},7,NOW)
        self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text)
        self.assertNotIn('MLB3',text)
        self.assertIn('não o estoque histórico',text)
        self.assertIn('não comprova saldo específico do Full',text)
        self.assertNotIn('lc-stock',comparison(1,ranking,listings,{},END,now=NOW))
        text=comparison(1,ranking,listings,dict(comparar1='MLB1',comparar2='MLB2'),END,now=NOW)
        self.assertIn('12 unidades',text);self.assertIn('lc-stock',text)
