import copy
import unittest
from datetime import date, datetime, timedelta

from kyra_campaigns import analyze
from kyra_campaign_view import render
from sales_metrics import SAO_PAULO


class CampaignRulesTests(unittest.TestCase):
    def setUp(self):
        self.today=date(2026,10,23)
        self.now=datetime(2026,10,23,10,tzinfo=SAO_PAULO).timestamp()
        self.campaigns=[]
        self.rows=[]

    def add(self,cid='a',spend=100,revenue=600,old_revenue=1400,target=10,sales=3,organic=100):
        self.campaigns.append(dict(campanha_id=cid,nome='Campanha '+cid,status='active',roas_objetivo=target,orcamento=150,atualizado_em=self.now))
        self.rows.extend(dict(campanha_id=cid,data=(self.today-timedelta(days=i)).isoformat(),gasto=spend,
                              faturamento=revenue if i<=7 else old_revenue,vendas_atribuidas=sales,
                              faturamento_sem_ads=organic,atualizado_em=self.now,metricas_vendas_coletadas_em=self.now)
                         for i in range(1,15))

    def result(self,limited=False):
        return analyze(self.campaigns,self.rows,self.today,self.now,limited)

    def test_ranks_distinct_campaigns_and_keeps_only_one_investigation_each(self):
        self.add('drop');self.add('waste',revenue=0);self.add('scale',revenue=1500,old_revenue=1400,sales=5);self.add('extra',revenue=100)
        result=self.result()
        self.assertEqual([r['code'] for r in result['recommendations']],['spend_without_revenue','roas_drop','roas_drop'])
        self.assertEqual(len({r['campaign_id'] for r in result['recommendations']}),3)
        self.assertEqual(result['flagged'],4)
        self.assertEqual(result['start'],'2026-10-16');self.assertEqual(result['end'],'2026-10-22')
        self.assertEqual(result['recommendations'][0]['current']['spend'],700)

    def test_zero_previous_roas_is_not_a_decline_or_scaling_evidence(self):
        self.add(revenue=1500,old_revenue=0,sales=5)
        codes=[r['code'] for r in self.result()['recommendations']]
        self.assertNotIn('roas_drop',codes);self.assertNotIn('scale_review',codes)

    def test_scale_requires_complete_official_sales_and_no_large_roas_drop(self):
        self.add(revenue=1500,old_revenue=1400,sales=5)
        self.assertEqual(self.result()['recommendations'][0]['code'],'scale_review')
        self.rows[0]['vendas_atribuidas']=None
        self.assertFalse(self.result()['recommendations'])
        self.rows[0]['vendas_atribuidas']=True
        self.assertFalse(self.result()['recommendations'])
        self.rows[0]['vendas_atribuidas']=5
        self.rows[0]['metricas_vendas_coletadas_em']=self.now-9*86400
        self.assertFalse(self.result()['recommendations'])

    def test_invalid_partial_future_stale_or_duplicate_days_suppress_comparisons(self):
        for mutation in ('missing','negative','nan','future','old','unclosed','duplicate'):
            self.setUp();self.add()
            if mutation=='missing':self.rows.pop()
            if mutation=='negative':self.rows[-1]['gasto']=-1
            if mutation=='nan':self.rows[-1]['faturamento']=float('nan')
            if mutation=='future':self.rows[-1]['atualizado_em']=self.now+1
            if mutation=='old':self.rows[-1]['atualizado_em']=self.now-8*86400
            if mutation=='unclosed':self.rows[-1]['atualizado_em']=datetime(2026,10,9,12,tzinfo=SAO_PAULO).timestamp()
            if mutation=='duplicate':self.rows.append(dict(self.rows[-1]))
            with self.subTest(mutation=mutation):
                result=self.result();self.assertEqual(result['comparable'],0)
                self.assertNotIn('roas_drop',[r['code'] for r in result['recommendations']])
                self.assertTrue(result['campaigns'][0]['quality'])

    def test_current_only_rules_do_not_require_previous_window(self):
        self.add(revenue=0);self.rows=self.rows[:7]
        result=self.result()
        self.assertEqual(result['recommendations'][0]['code'],'spend_without_revenue')
        self.assertIsNone(result['recommendations'][0]['previous'])
        self.rows.pop()
        self.assertFalse(self.result()['recommendations'])

    def test_small_spend_and_stale_metadata_cannot_generate_actions(self):
        self.add(spend=1,revenue=0)
        self.assertFalse(self.result()['recommendations'])
        self.campaigns[0]['atualizado_em']=self.now-2*86400
        self.assertEqual(self.result()['current_ready'],0)
        self.campaigns[0]['atualizado_em']=self.now
        self.campaigns[0]['status']='paused'
        self.assertEqual(self.result()['active'],0)

    def test_tacos_uses_only_official_campaign_organic_and_can_be_suppressed(self):
        self.add(revenue=1000,old_revenue=1000,target=0,organic=100)
        for row in self.rows[7:]:row['faturamento_sem_ads']=10000
        result=self.result()
        self.assertEqual(result['recommendations'][0]['code'],'tacos_rise')
        self.assertAlmostEqual(result['recommendations'][0]['current']['tacos'],100/1100*100)
        self.rows[0]['faturamento_sem_ads']=None
        self.assertFalse(self.result()['recommendations'])

    def test_read_limit_never_ranks_a_partial_portfolio(self):
        self.add(revenue=0)
        result=self.result(limited=True)
        self.assertFalse(result['recommendations']);self.assertTrue(result['limited'])

    def test_render_escapes_names_actions_and_model_free_evidence(self):
        self.add('a/b?<x>',revenue=0)
        self.campaigns[0]['nome']='<img src=x onerror=alert(1)>'
        html=render(dict(day=self.today,status='completed',result=self.result()),5)
        self.assertNotIn('<img',html)
        self.assertIn('&lt;img',html)
        self.assertIn('/ads/5/campanha/a%2Fb%3F%3Cx%3E',html)
        self.assertIn('R$ 700,00',html)
        self.assertNotIn('<form',html)

    def test_future_days_and_other_campaign_rows_do_not_change_results(self):
        self.add()
        before=copy.deepcopy(self.result())
        self.rows.extend([dict(self.rows[0],campanha_id='other',gasto=10**9),dict(self.rows[0],data=self.today.isoformat(),gasto=10**9)])
        self.assertEqual(before,self.result())
