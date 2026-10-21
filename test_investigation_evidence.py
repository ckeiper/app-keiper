import contextlib
import datetime as dt
import html
import time
import unittest
from decimal import Decimal as D
from unittest.mock import Mock, patch
from investigation_evidence import build, load, render, window

END=dt.date(2026,10,20)
DATES=[END-dt.timedelta(days=13-i) for i in range(14)]


def visits(before=100,now=50):
    return [dict(dia=d,visitas=before if i<7 else now) for i,d in enumerate(DATES)]


def advertising(before=20,now=10):
    return [dict(data=d.isoformat(),gasto=before if i<7 else now,
                 faturamento=100,impressoes=1000,cliques=30) for i,d in enumerate(DATES)]


def ranking():
    return dict(available=True,rows={'MLB1':dict(value=D('500'),previous_value=D('1000'),orders=7,previous_orders=28)})


def stock(day,state):
    stamp=dt.datetime.combine(day,dt.time(12),dt.timezone(dt.timedelta(hours=-3))).timestamp()
    return dict(observed_at=int(stamp),logistics='fulfillment',state=state)


class EvidenceTests(unittest.TestCase):
    def test_complete_sources_identify_traffic_efficiency_and_shop_ads_separately(self):
        result=build(ranking(),'MLB1',visits(),[],advertising(),END)
        self.assertEqual(result['traffic']['delta'],-50)
        self.assertEqual(result['conversion']['delta'],-50)
        self.assertEqual(result['ads']['spend_delta'],-50)
        self.assertEqual(len(result['actions']),3)
        self.assertIn('não atribuído',result['actions'][-1]['scope'])

    def test_partial_coverage_never_imputes_visits_or_ad_spend(self):
        result=build(ranking(),'MLB1',visits()[:-1],[],advertising()[:-1],END)
        self.assertFalse(result['traffic']['complete'])
        self.assertFalse(result['conversion']['complete'])
        self.assertFalse(result['ads']['complete'])
        self.assertIsNone(result['traffic']['current']['totals'])
        self.assertEqual(result['actions'],[])

    def test_full_transitions_require_adjacent_confirmed_days(self):
        observations=[stock(DATES[5],'available'),stock(DATES[7],'empty'),stock(DATES[8],'available'),stock(DATES[9],'empty')]
        result=build(ranking(),'MLB1',[],observations,[],END)
        self.assertEqual(result['full']['transitions'],[DATES[9].isoformat()])
        self.assertEqual(len(result['full']['empty_dates']),2)
        self.assertEqual(result['full']['current_known'],3)
        self.assertIn('não comprova',result['actions'][0]['scope'])

    def test_invalid_and_duplicate_daily_values_block_comparison(self):
        for invalid in (None,-1,'NaN',True,'1.5'):
            data=visits();data[0]['visitas']=invalid
            self.assertFalse(build(ranking(),'MLB1',data,[],[],END)['traffic']['complete'])
        data=visits()+[visits()[0]]
        self.assertFalse(build(ranking(),'MLB1',data,[],[],END)['traffic']['complete'])

    def test_zero_denominator_and_unverified_sales_never_produce_conversion(self):
        result=build(ranking(),'MLB1',visits(0,0),[],[],END)
        self.assertTrue(result['traffic']['complete'])
        self.assertIsNone(result['traffic']['delta'])
        self.assertFalse(result['conversion']['complete'])
        result=build(dict(available=False),'MLB1',visits(),[],advertising(),END)
        self.assertFalse(result['sales_verified'])
        self.assertFalse(result['conversion']['complete'])
        self.assertFalse(any('Ads' in a['title'] for a in result['actions']))

    def test_small_samples_do_not_create_traffic_or_efficiency_actions(self):
        low=ranking();low['rows']['MLB1'].update(orders=0,previous_orders=1)
        result=build(low,'MLB1',visits(1,1),[],[],END)
        self.assertEqual(result['conversion']['delta'],-100)
        self.assertEqual(result['actions'],[])
        result=build(low,'MLB1',visits(1,0),[],[],END)
        self.assertEqual(result['actions'],[])

    def test_ad_invalid_metrics_are_unknown_not_zero(self):
        data=advertising();data[-1]['faturamento']=None
        result=build(ranking(),'MLB1',[],[],data,END)
        self.assertFalse(result['ads']['complete'])

    def test_bounded_tenant_scoped_reads(self):
        query=Mock(side_effect=[[],[]])
        self.assertEqual(load(None,query,42,'MLB1',END),([],[]))
        self.assertEqual(query.call_count,2)
        self.assertEqual(query.call_args_list[0].args[2],(42,'MLB1','2026-10-07','2026-10-20'))
        self.assertEqual(query.call_args_list[1].args[2],(42,'2026-10-07','2026-10-20'))
        for call in query.call_args_list:
            self.assertIn('conexao_id=%s',call.args[1])

    def test_render_discloses_gaps_scope_and_escapes_actions(self):
        result=build(ranking(),'MLB1',visits()[-2:],[],advertising(),END)
        result['actions'].append(dict(title='<script>x</script>',evidence='<img>',action='Revisar',scope='Teste'))
        output=render(result,1,END)
        self.assertIn('Contexto da loja inteira',output)
        self.assertIn('Sem dado válido',output)
        self.assertIn('Total indisponível',output)
        self.assertNotIn('<script>',output)
        self.assertEqual(output.count('<tr>'),15)


class EvidenceRouteTests(unittest.TestCase):
    def test_actual_diagnostic_route_renders_evidence_without_network(self):
        from test_listing_details import main_function
        from listing_sales import listing_sales_summary
        from listing_trends import comparison
        from listing_ranking import ranking_metrics
        query=Mock(side_effect=[[{'cliente':'Teste'}],[{'item_id':'MLB1','titulo':'Produto'}],[],[],[],[{'n':False}],[],[],[]])
        ns=dict(pode_ver_loja=lambda cid:True,banco=lambda:contextlib.nullcontext(None),
                consultar=query,diagnose_listing=lambda item:[],listing_sales_summary=listing_sales_summary,
                comparison=comparison,ranking_metrics=ranking_metrics,datetime=dt,time=time,
                esc=html.escape,pagina_loja=lambda *args:args[-1])
        route=main_function('diagnostico_saude_anuncio',ns)
        with patch('requests.get',side_effect=AssertionError('Network during render')):
            output=route(42,'MLB1')
        self.assertIn('Onde investigar primeiro',output)
        self.assertLess(output.index('Onde investigar primeiro'),output.index('Indicadores de vendas por anúncio'))
        self.assertIn('Vendas sem cobertura verificada',output)
        self.assertEqual(query.call_count,9)

if __name__=='__main__':
    unittest.main()
