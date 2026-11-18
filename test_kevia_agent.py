import copy
import unittest
from datetime import date
from kevia_agent import plan, render

TODAY = date(2026, 11, 2)


def run(code='revenue', priority=80, **fields):
    item = dict(code=code, priority=priority, title='Investigar', action='Conferir fontes',
                evidence={'current': 100, 'previous': 200})
    item.update(fields)
    return dict(day=TODAY, status='completed', result=dict(start='2026-10-26', end='2026-11-01',
                recommendations=[item]))


class AgentTests(unittest.TestCase):
    def test_mission_ranks_sources_and_prepares_scoped_campaign(self):
        campaign = run('below_target', 90, campaign_id='a/b', current={'roas': 2})
        result = plan(run(), campaign, TODAY)
        self.assertEqual([t['priority'] for t in result['tasks']], [90, 80])
        output = render(result, 42)
        self.assertIn('/ads/42/campanha/a%2Fb', output)
        self.assertIn('2026-10-26', output)
        self.assertIn('plano preparado', output)

    def test_stale_future_partial_and_wrong_period_sources_are_blocked(self):
        for changes in [dict(day='2026-11-01'), dict(day='2026-11-03'),
                        dict(status='running'), dict(status='rules_ready'), dict(status='failed')]:
            source = run(); source.update(changes)
            self.assertFalse(plan(source, None, TODAY)['tasks'])
        source = run(); source['result']['end'] = '2026-10-31'
        self.assertFalse(plan(source, None, TODAY)['tasks'])

    def test_limited_campaigns_blocked_and_private_findings_excluded(self):
        campaign = run('below_target', 90); campaign['result']['limited'] = True
        self.assertFalse(plan(run('finance_private'), campaign, TODAY)['tasks'])

    def test_missions_keep_quality_and_filter_irrelevant_signals(self):
        self.assertFalse(plan(run(), None, TODAY, 'ads')['tasks'])
        self.assertFalse(plan(None, run('below_target'), TODAY, 'vendas')['tasks'])
        self.assertEqual(plan(run('data_quality'), None, TODAY, 'ads')['tasks'][0]['category'], 'qualidade')
        self.assertEqual(plan(None, None, TODAY, 'unexpected')['mission'], 'prioridades')

    def test_bound_dedup_and_no_mutation(self):
        source = run(); finding = source['result']['recommendations'][0]
        source['result']['recommendations'] = [finding, finding, dict(finding, code='orders')]
        before = copy.deepcopy(source)
        result = plan(source, run('below_target', 90), TODAY)
        self.assertEqual(len(result['tasks']), 3)
        self.assertEqual(source, before)

    def test_missing_evidence_not_invented_and_html_escaped(self):
        self.assertFalse(plan(run(evidence={}), None, TODAY)['tasks'])
        output = render(plan(run(title='<script>alert(1)</script>', action='<img src=x>'), None, TODAY), 42)
        self.assertNotIn('<script>', output)
        self.assertNotIn('<img src=x>', output)
        self.assertIn('&lt;script&gt;', output)
        self.assertNotIn('method=\'post\'', output)

    def test_no_result_and_empty_object_never_mean_valid_analysis(self):
        for result in [None, {}, 'bad']:
            self.assertFalse(plan(dict(day=TODAY, status='completed', result=result), None, TODAY)['tasks'])


if __name__ == '__main__':
    unittest.main()
