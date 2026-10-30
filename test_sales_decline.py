import unittest
from datetime import date
from decimal import Decimal as D
from sales_decline import investigate, render


def metrics(previous, current, before_units, units):
    return dict(previous_value=D(previous), value=D(current), previous_units=before_units, units=units)


class SalesDeclineTests(unittest.TestCase):
    def test_volume_price_mix_decomposition_and_gains(self):
        source = dict(available=True, rows={
            'MLB1': metrics('1000', '600', 10, 8),
            'MLB2': metrics('100', '300', 1, 3)})
        result = investigate(source)
        row = result['rows'][0]
        self.assertEqual(result['net'], D('200'))
        self.assertEqual(result['lost'], D('400'))
        self.assertEqual(row['volume_effect'], D('-200'))
        self.assertEqual(row['price_effect'], D('-200'))
        self.assertEqual(row['volume_effect']+row['price_effect'], -row['loss'])
        self.assertEqual(row['share'], 100)

    def test_zero_sales_and_new_listing(self):
        result = investigate(dict(available=True, rows={
            'MLB1': metrics('100','0',2,0), 'MLB2': metrics('0','50',0,1)}))
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(result['rows'][0]['price_effect'],0)
        self.assertEqual(result['net'],50)

    def test_higher_units_can_still_lose_revenue(self):
        result = investigate(dict(available=True, rows={'MLB1':metrics('100','90',1,2)}))
        self.assertEqual(result['rows'][0]['hypothesis'],'Menor valor médio por unidade')

    def test_incomplete_data_never_becomes_zero(self):
        result = investigate(dict(available=False,reason='Cobertura incompleta',rows={}))
        self.assertFalse(result['available'])
        self.assertNotIn('net',result)

    def test_pagination_and_escaped_search(self):
        ranking = dict(available=True,rows={str(i): metrics('100','50',2,1) for i in range(25)})
        page = render(ranking,[],1,{'pagina_queda':'2'},date(2026,10,20))
        self.assertIn('13–24 de 25', page)
        self.assertEqual(page.count("class='decline-item'"),12)
        self.assertIn('pagina_queda=3',page)
        filtered = render(ranking,[],1,{'busca_queda':"'><script>"},date(2026,10,20))
        self.assertNotIn('<script>', filtered)
        self.assertIn('0–0 de 0',filtered)

    def test_single_listing_uses_store_loss_denominator(self):
        ranking = dict(available=True,rows={'MLB1':metrics('100','0',1,0),'MLB2':metrics('300','0',3,0)})
        page = render(ranking,[],1,{},date(2026,10,20),item_id='MLB1')
        self.assertIn('25.0% das perdas',page)
        self.assertEqual(page.count("class='decline-item'"),1)

class DeclineRouteTests(unittest.TestCase):
    def test_ranking_route_uses_closed_days(self):
        import contextlib
        import datetime
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from test_listing_details import main_function
        from page_performance import ranking_query_bounds
        from sales_metrics import reporting_today
        query = Mock(side_effect=[[{'cliente':'Teste'}],[],[],[],[],[{'n':False}]])
        ranking = Mock(return_value=dict(available=False,reason='Sem cobertura'))
        ns = dict(pode_ver_loja=lambda cid:True, request=SimpleNamespace(args={}),
                  datetime=datetime, ranking_query_bounds=ranking_query_bounds,
                  banco=lambda:contextlib.nullcontext(None),consultar=query,
                  ranking_metrics=ranking,esc=lambda s:s,pagina_loja=lambda *args:args[-1],executar=Mock())
        route = main_function('ranking_anuncios', ns)
        output = route(1)
        self.assertIn('Ranking indisponível',output)
        self.assertEqual(ranking.call_args.kwargs['end'],reporting_today()-datetime.timedelta(days=1))

if __name__=='__main__':
    unittest.main()
