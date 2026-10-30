import unittest
from copy import deepcopy
from decimal import Decimal as D
from datetime import timedelta
from test_profitability import summary,record
from profitability_revisions import compare_versions,render

class RevisionComparisonTests(unittest.TestCase):
 def records(self):
  old=record();new=deepcopy(old);new['id']=2
  new['costs']['products']=D(25);new['costs']['advertising']=D(5)
  new['sources']['products']='Nova referência documental'
  return old,new
 def test_exact_changes_and_sources_without_mutation(self):
  old,new=self.records();before=deepcopy([old,new]);r=compare_versions(summary(),new,old)
  self.assertTrue(r['available']);self.assertEqual(r['cost_delta'],10)
  self.assertEqual(r['contribution_delta'],-10)
  self.assertEqual((r['changed_values'],r['changed_sources']),(2,1))
  self.assertEqual(sum(row['delta'] for row in r['rows']),r['cost_delta'])
  self.assertEqual([old,new],before)
 def test_same_version_is_not_a_revision(self):
  self.assertFalse(compare_versions(summary(),record(),record())['available'])
  self.assertIn('já é a última versão',render(summary(),record(),record()))
 def test_different_basis_incomplete_sources_or_unverified_sales_block(self):
  for updates in [dict(sales_fingerprint='changed'),dict(units=4),dict(gross_items=D(301)),dict(sources={})]:
   old,new=self.records();old.update(updates)
   self.assertFalse(compare_versions(summary(),new,old)['available'])
  old,new=self.records();self.assertFalse(compare_versions(dict(summary(),orders=None),new,old)['available'])
 def test_different_tenant_item_or_period_and_subcent_costs_block(self):
  for key,value in [('conexao_id',43),('item_id','MLB2'),('inicio',record()['inicio']-timedelta(days=1))]:
   old,new=self.records();old[key]=value
   self.assertFalse(compare_versions(summary(),new,old)['available'])
  old,new=self.records();old['costs']['products']=D('1.001')
  self.assertFalse(compare_versions(summary(),new,old)['available'])
 def test_source_only_change_has_zero_money_delta_and_limits_are_visible(self):
  old,new=self.records();new['costs']=deepcopy(old['costs'])
  r=compare_versions(summary(),new,old)
  self.assertEqual(r['cost_delta'],0);self.assertEqual(r['changed_values'],0);self.assertEqual(r['changed_sources'],1)
  html=render(summary(),new,old)
  self.assertIn('Não representam evolução operacional',html)
  self.assertNotIn('<form',html)
  self.assertEqual(render(summary(),new,None),'')
