import unittest
from copy import deepcopy
from decimal import Decimal
from unittest.mock import Mock
from datetime import timedelta
from test_listing_interventions import sample,DAY,ITEM
from listing_interventions import compare,load_comparison
from profitability_store import fingerprint_for
from listing_profitability import COMPONENTS
from profitability_action import load,render

TODAY=DAY+timedelta(days=15)
def fixture():
 orders,items,covered,visits=sample()
 periods=compare(ITEM,DAY,orders,items,covered,visits,TODAY)['periods']
 records=[]
 for i,p in enumerate(periods):
  records.append(dict(id=i+1,conexao_id=1,item_id=ITEM,inicio=p['start'],fim=p['end'],gross_items=p['sales']['gross_items'],units=p['sales']['units'],
   sales_fingerprint=fingerprint_for(1,ITEM,p['start'],p['end'],orders,items),
   costs={k:Decimal(10) for k in COMPONENTS},sources={k:'Documento sintético conferido' for k in COMPONENTS}))
 return periods,orders,items,records

class ActionFinanceTests(unittest.TestCase):
 def test_exact_periods_exclude_action_day_and_bulk_read(self):
  periods,orders,items,records=fixture();query=Mock(return_value=records)
  result=load(None,query,1,ITEM,periods,orders,items,TODAY)
  self.assertTrue(result['available']);self.assertEqual(result['delta'],700)
  self.assertEqual(result['before']['contribution'],640);self.assertEqual(result['after']['contribution'],1340)
  self.assertEqual(query.call_count,1)
  self.assertEqual(query.call_args.args[2],(1,ITEM,DAY-timedelta(days=7),DAY-timedelta(days=1),DAY+timedelta(days=1),DAY+timedelta(days=7)))
 def test_future_and_unverified_sales_block_before_cost_reads(self):
  for future in [True,False]:
   periods,orders,items,records=fixture();query=Mock()
   if not future:periods[0]['sales']['orders']=None
   r=load(None,query,1,ITEM,periods,orders,items,DAY if future else TODAY)
   self.assertFalse(r['available']);query.assert_not_called()
 def test_missing_stale_foreign_and_wrong_window_records_never_claim_margin(self):
  for kind in ['missing','stale','foreign','item','window']:
   periods,orders,items,records=fixture()
   if kind=='missing':records=[]
   elif kind=='stale':records[-1]['sales_fingerprint']='stale'
   elif kind=='foreign':records[-1]['conexao_id']=2
   elif kind=='item':records[-1]['item_id']='MLB2'
   else:records[-1]['inicio']=DAY
   r=load(None,Mock(return_value=records),1,ITEM,periods,orders,items,TODAY)
   self.assertFalse(r['available']);self.assertIsNone(r['delta'])
 def test_newest_version_and_negative_margins_preserved(self):
  periods,orders,items,records=fixture();new=deepcopy(records[-1]);new['id']=10;new['costs']={k:Decimal(300) for k in COMPONENTS}
  r=load(None,Mock(return_value=records+[new]),1,ITEM,periods,orders,items,TODAY)
  self.assertTrue(r['available']);self.assertEqual(r['after']['contribution'],-400)
  self.assertLess(r['margin_delta'],0)
 def test_zero_revenue_has_no_margin_difference(self):
  periods,orders,items,records=fixture()
  periods[-1]['sales']['gross_items']=Decimal(0);records[-1]['gross_items']=Decimal(0)
  r=load(None,Mock(return_value=records),1,ITEM,periods,orders,items,TODAY)
  self.assertTrue(r['available']);self.assertIsNone(r['margin_delta'])
 def test_links_exact_dates_scope_and_no_profit_or_causality_claim(self):
  periods,orders,items,records=fixture();r=load(None,Mock(return_value=records),1,ITEM,periods,orders,items,TODAY)
  html=render(r,1,ITEM,periods,TODAY)
  self.assertIn('inicio=2026-10-05&amp;fim=2026-10-11',html)
  self.assertIn('inicio=2026-10-13&amp;fim=2026-10-19',html)
  self.assertIn('não é lucro líquido',html.lower());self.assertIn('não comprova que a mesma promoção',html)
 def test_default_comparison_has_no_financial_query_or_data(self):
  query=Mock(side_effect=[[],[],[],[],[dict(pending=False)],[dict(n=0)]])
  r=load_comparison(None,query,1,ITEM,DAY,TODAY)
  self.assertEqual(query.call_count,6);self.assertNotIn('financial',r)

class ActionFinancePrivacyTests(unittest.TestCase):
 def test_admin_only_financial_context_and_consistent_read_snapshot(self):
  import test_listing_interventions as fixtures
  from unittest.mock import patch
  case=fixtures.InterventionRouteTests();case.setUp()
  case.total=1;case.rows=[dict(id=1,event_date=DAY,kind='preco',note='Preço alterado manualmente para teste.',created_at=1,void_at=None,source='manual')]
  periods,orders,items,records=fixture()
  def comparison(*args,**kwargs):
   result=compare(ITEM,DAY,*sample(),TODAY);result['other_actions']=0
   if kwargs.get('financial'):
    result['financial']=load(None,Mock(return_value=records),1,ITEM,periods,orders,items,TODAY)
   return result
  with patch('intervention_routes.load_comparison',side_effect=comparison) as loaded:
   admin=case.client.get(case.path)
   self.assertEqual(admin.status_code,200)
   self.assertIn('action-finance',admin.text);self.assertIn('R$ 1.340,00',admin.text)
   self.assertTrue(loaded.call_args.kwargs['financial'])
   case.execute.assert_called_with(None,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
   with case.client.session_transaction() as state:state.update(tipo='cliente',conexao_id=1)
   client=case.client.get(case.path)
   self.assertEqual(client.status_code,200);self.assertFalse(loaded.call_args.kwargs['financial'])
   self.assertNotIn('action-finance',client.text);self.assertNotIn('R$ 1.340,00',client.text)
