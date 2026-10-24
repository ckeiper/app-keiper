import copy
import json
import os
import unittest
from datetime import datetime,timedelta
from decimal import Decimal
from unittest.mock import Mock,MagicMock,patch

from kevia_finance import build_snapshot,load_snapshot,visible_result,review_findings,central_findings,empty_snapshot
from kevia_finance_view import render
from profitability_store import summarize_context
from test_profitability_priority import data,START,END,OLD_START,OLD_END
from sales_metrics import SAO_PAULO

CHECKED=datetime(2026,10,24,10,tzinfo=SAO_PAULO).timestamp()


def snapshot(count=1):
    context,_,records=data(count)
    return build_snapshot(42,context,records,END,CHECKED)


class KeviaFinancialRulesTests(unittest.TestCase):
    def test_documented_negative_contribution_and_margin_are_saved_as_exact_strings(self):
        result=snapshot()
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['documented_current'],1)
        self.assertEqual(result['negative_count'],1)
        self.assertEqual(Decimal(result['negative_contribution_sum']),Decimal('-80'))
        self.assertEqual(result['declining_margin_count'],1)
        self.assertEqual(result['covered_sold_items'],result['current_sold_items'])
        finding=result['findings'][0]
        self.assertEqual(finding['evidence']['margin_current_pct'],'-80')
        self.assertEqual(finding['evidence']['margin_previous_pct'],'70')
        self.assertEqual(finding['code'],'finance_negative_20261023_MLB100')
        self.assertNotIn('sources',json.dumps(result))

    def test_no_records_requires_only_one_read_and_does_not_claim_zero_losses(self):
        query=Mock(return_value=[])
        result=load_snapshot(None,query,42,END,CHECKED)
        self.assertEqual(query.call_count,1)
        self.assertEqual(result['status'],'no_records')
        self.assertIsNone(result['negative_count'])
        self.assertIsNone(result['negative_contribution_sum'])
        self.assertEqual(result['findings'],[])

    def test_documented_subsets_do_not_become_total_store_profit_or_full_coverage(self):
        context,_,records=data(2)
        result=build_snapshot(42,context,records[:2],END,CHECKED)
        self.assertEqual(result['current_sold_items'],2)
        self.assertEqual(result['covered_sold_items'],1)
        self.assertEqual(result['documented_current'],1)
        self.assertEqual(result['negative_count'],1)
        self.assertEqual(Decimal(result['negative_contribution_sum']),-80)
        self.assertNotIn('profit',result)
        output=render(result,42)
        self.assertIn('1 de 2',output)
        self.assertIn('não é o resultado total da loja',output)

    def test_unverified_sales_stale_costs_and_missing_sources_fail_closed(self):
        for problem in ['coverage','pending','stale','source']:
            context,_,records=data()
            if problem=='coverage':context['coverage'].pop()
            if problem=='pending':context['pending']=True
            if problem=='stale':records[0]['sales_fingerprint']='b'*64
            if problem=='source':records[0]['sources']['taxes']=''
            result=build_snapshot(42,context,records,END,CHECKED)
            self.assertNotEqual(result['status'],'ready',problem)
            self.assertIsNone(result['negative_count'])
            self.assertIsNone(result['negative_contribution_sum'])
            self.assertEqual(result['findings'],[])

    def test_current_negative_costs_do_not_invent_a_previous_margin(self):
        context,_,records=data()
        result=build_snapshot(42,context,records[:1],END,CHECKED)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['negative_count'],1)
        self.assertEqual(result['comparable_margins'],0)
        self.assertIsNone(result['declining_margin_count'])
        self.assertIsNone(result['findings'][0]['evidence']['margin_previous_pct'])

    def test_positive_contributions_are_not_added_to_the_negative_subtotal(self):
        context,_,records=data(2)
        records[2]['costs']={key:'0' for key in records[2]['costs']}
        result=build_snapshot(42,context,records,END,CHECKED)
        self.assertEqual(result['documented_current'],2)
        self.assertEqual(result['negative_count'],1)
        self.assertEqual(Decimal(result['negative_contribution_sum']),-80)

    def test_margin_decline_with_positive_contribution_is_separate_from_negative(self):
        context,_,records=data()
        records[0]['costs']={key:'10' for key in records[0]['costs']}
        result=build_snapshot(42,context,records,END,CHECKED)
        self.assertEqual(result['negative_count'],0)
        self.assertEqual(Decimal(result['negative_contribution_sum']),0)
        self.assertEqual(result['declining_margin_count'],1)
        self.assertEqual(result['findings'][0]['kind'],'margin_decline')

    def test_top_three_financial_items_are_unique_and_preserve_total_signal_count(self):
        result=snapshot(4)
        self.assertEqual(result['flagged_count'],4)
        self.assertEqual(len(result['findings']),3)
        self.assertEqual(len({f['item_id'] for f in result['findings']}),3)
        self.assertTrue(all(len(f['code'])<=80 for f in result['findings']))

    def test_foreign_store_wrong_window_and_invalid_item_identifiers_are_ignored(self):
        context,_,records=data()
        for change in [dict(conexao_id=99),dict(item_id='<script>'),dict(inicio=OLD_END)]:
            result=build_snapshot(42,context,[dict(records[0],**change)],END,CHECKED)
            self.assertEqual(result['status'],'no_records')
            self.assertIsNone(result['negative_count'])

    def test_zero_sales_have_no_coverage_division_or_comparative_margin(self):
        context,_,records=data()
        context['orders'][0]['status']='cancelled'
        basis=summarize_context(context,42,'MLB100',START,END)
        records[0].update(gross_items=0,units=0,sales_fingerprint=basis['fingerprint'])
        result=build_snapshot(42,context,records,END,CHECKED)
        self.assertEqual(result['current_sold_items'],0)
        self.assertEqual(result['covered_sold_items'],0)
        self.assertEqual(result['negative_count'],1)
        self.assertEqual(result['comparable_margins'],0)
        output=render(result,42)
        self.assertNotIn('--coverage:',output)
        self.assertIn('0 de 0',output)

    def test_reader_uses_five_scoped_reads_and_reuses_exact_period_data(self):
        context,_,records=data()
        query=Mock(side_effect=[records,context['orders'],context['items'],
            [dict(dia=d) for d in context['coverage']],[dict(pending=False)]])
        result=load_snapshot(None,query,42,END,CHECKED)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(query.call_count,5)
        for call in query.call_args_list:
            self.assertIn('conexao_id=%s',call.args[1]);self.assertEqual(call.args[2][0],42)

    def test_clients_and_default_renderer_never_receive_financial_snapshots(self):
        from keiper_ai import render as render_ai
        stored=dict(start=START.isoformat(),end=END.isoformat(),recommendations=[],financial=snapshot(),interpretation='Texto público')
        original=copy.deepcopy(stored)
        public=visible_result(stored)
        self.assertNotIn('financial',public)
        self.assertEqual(stored,original)
        self.assertIn('financial',visible_result(stored,admin=True))
        self.assertNotIn('id="ky-finance"',render_ai(stored,cid=42))
        self.assertIn('id="ky-finance"',render_ai(stored,cid=42,admin_financial=True))

    def test_old_runs_have_an_admin_placeholder_without_rewriting_history_or_zero_values(self):
        from keiper_ai import render as render_ai
        output=render_ai(dict(recommendations=[]),cid=42,admin_financial=True)
        self.assertIn('Aguardando a primeira execução financeira desta versão',output)
        self.assertNotIn('class="ky-finance-stat"',output)
        self.assertNotIn('Retrato da execução em Data não verificável',output)

    def test_defensive_filter_removes_mixed_financial_rules_and_their_interpretation(self):
        stored=dict(recommendations=[dict(code='revenue'),dict(code='finance_private')],
            financial=snapshot(),interpretation='Uma interpretação de dados privados')
        public=visible_result(stored)
        self.assertEqual(public['recommendations'],[dict(code='revenue')])
        self.assertIsNone(public['interpretation'])

    def test_admin_central_and_manual_reviews_use_documented_financial_findings(self):
        from kyra_central import central_rows
        stored=dict(recommendations=[],financial=snapshot())
        findings=review_findings(stored)
        self.assertEqual(len(findings),1)
        rows=central_rows([dict(id=42,cliente='Loja')],[dict(conexao_id=42,result=stored,day=END)])
        self.assertIn('contribuição documentada negativa',rows[0]['findings'][0]['title'])
        self.assertEqual(rows[0]['priority'],98)
        self.assertEqual(stored['recommendations'],[])
        self.assertEqual(central_findings(empty_snapshot(END,CHECKED)),[])

    def test_view_escapes_fields_and_explains_snapshot_scope(self):
        result=snapshot();result['findings'][0]['title']='<script>x</script>'
        result['findings'][0]['action']='<img src=x onerror=1>'
        output=render(result,42)
        self.assertIn('&lt;script&gt;',output);self.assertIn('&lt;img',output)
        self.assertNotIn('<script>',output);self.assertNotIn('<img',output)
        self.assertIn('alterações posteriores não estão incluídas',output)
        self.assertIn('17/10/2026 a 23/10/2026',output)
        self.assertIn('Revalidar na rentabilidade do anúncio',output)
        self.assertIn('/anuncios/42/MLB100/rentabilidade?inicio=2026-10-17&amp;fim=2026-10-23',output)
        self.assertNotIn('<form',output)

    def test_financial_history_is_opt_in_and_identifies_the_saved_analysis_scope(self):
        from kyra_history import render_history
        stored=dict(recommendations=[],financial=snapshot(),quality=[])
        runs=[dict(day='2026-10-24',status='completed',result=stored)]
        self.assertNotIn('Contribuição documentada negativa',render_history(runs))
        private=render_history(runs,admin_financial=True)
        self.assertIn('Contribuição documentada negativa',private)
        self.assertIn('Documentado na execução',private)
        self.assertIn('Financeiro documentado',private)

    def test_existing_paid_adapter_does_not_send_private_financial_evidence(self):
        from keiper_ai_budget import interpret
        from test_keiper_ai import RulesTests,BudgetTests
        fixture=RulesTests();fixture.setUp();result=fixture.analyze()
        result['financial']=dict(snapshot(),private_marker='never-send-document-reference')
        connection=MagicMock();connection.__enter__.return_value=connection
        bank=Mock(return_value=connection)
        query=Mock(side_effect=[[],[dict(used=Decimal('0'),overrun=False)],[dict(id=1)]])
        response=Mock();response.json.return_value=dict(status='completed',usage=dict(input_tokens=1,output_tokens=1),
            output=[dict(type='message',content=[dict(type='output_text',text='Conferir sinais públicos.')])])
        post=Mock(return_value=response)
        with patch.dict(os.environ,BudgetTests().config(),clear=True):
            self.assertEqual(interpret(1,result,bank,query,Mock(),post)[0],'Conferir sinais públicos.')
        payload=post.call_args.kwargs['json']['input']
        self.assertNotIn('financial',payload)
        self.assertNotIn('never-send-document-reference',payload)
        self.assertNotIn('MLB100',payload)

    def test_financial_failure_does_not_erase_public_output_or_trigger_extra_paid_calls(self):
        from keiper_ai_store import run_one
        connection=MagicMock();connection.__enter__.return_value=connection
        bank=Mock(return_value=connection)
        def read(conn,sql,params=None):
            if 'pg_try_advisory_lock' in sql:return [dict(acquired=True)]
            if sql.startswith('SELECT c.id,c.cliente'):return [dict(id=42,cliente='Loja',status='ativa')]
            if 'INSERT INTO keiper_ai_runs' in sql:return [dict(id=1)]
            if 'FROM ads_dia' in sql:return []
            raise AssertionError(sql)
        execute=Mock();report=dict(eligible=True,reasons=[],current=dict(revenue=100,orders=1),previous=dict(revenue=100,orders=1))
        with patch.dict(os.environ,dict(KEIPER_AI_DAILY_ENABLED='true')),patch('overview.load_overview',return_value=dict(reports=[report])),\
             patch('kevia_finance.load_snapshot',side_effect=RuntimeError('private detail')),patch('keiper_ai_store.interpret',return_value=(None,'desabilitada')) as interpret:
            run_one(bank,read,execute,Mock(),now=CHECKED)
        saved=[json.loads(call.args[2][0]) for call in execute.call_args_list if "status='rules_ready'" in call.args[1]][0]
        self.assertEqual(saved['financial']['status'],'failed')
        self.assertTrue(saved['recommendations'])
        self.assertTrue(any("status='completed'" in call.args[1] for call in execute.call_args_list))
        self.assertFalse(any("status='failed'" in call.args[1] for call in execute.call_args_list))
        self.assertEqual(interpret.call_count,1)
