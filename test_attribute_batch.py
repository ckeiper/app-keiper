"""Batch drafts are atomic, scoped, bounded and never marketplace writes."""
from copy import deepcopy
import time
import unittest
from unittest.mock import Mock,patch
from werkzeug.datastructures import MultiDict
from attribute_manual import parse,add
from attribute_manual_view import render
from attribute_completion import analyze
from test_attribute_completion import facts,definition


def form(entries=None,key='k'*24):
 entries=entries if entries is not None else [('MATERIAL','Aço','Fabricante'),('WIDTH','12 cm','Medido')]
 return MultiDict([('manual_key',key)]+[(name,value) for entry in entries for name,value in zip(('manual_field','manual_value','manual_note'),entry)])


class BatchTests(unittest.TestCase):
 def setUp(self):
  self.facts=facts(definitions=[definition(),definition('WIDTH',name='Largura',value_type='number_unit',allowed_units=[dict(id='cm')])],description='')
  self.parent=dict(id='11111111-1111-4111-8111-111111111111',state='ready',created_at=int(time.time()),created_by=42,data=analyze(self.facts))
 def call(self,submitted=None,previous=None):
  self.read=Mock(return_value=deepcopy(self.facts))
  with patch('attribute_manual.store') as store,patch('attribute_manual.gather',self.read):
   store.by_key.return_value=previous;store.active.return_value=[];store.create.return_value=(dict(id='22222222-2222-4222-8222-222222222222'),True)
   result=add(None,Mock(),7,'MLB123',42,self.parent,submitted or form(),dict(status='ativa',user_id=123),Mock(return_value='private'),Mock())
   return result,self.read,store.create,store.transition
 def test_batch_creates_one_successor_after_one_read(self):
  result,read,create,transition=self.call()
  self.assertEqual(read.call_count,1);self.assertEqual(create.call_count,1);self.assertEqual(transition.call_count,2)
  data=transition.call_args_list[0].kwargs['data'];self.assertEqual(len(data['manual_inputs']),2);self.assertEqual(data['manual_actor'],42)
  self.assertEqual({p['id'] for p in data['proposals']},{'MATERIAL','WIDTH'})
  self.assertEqual(transition.call_args_list[1].args[4],'stale')
 def test_invalid_official_value_does_not_create_partial_draft(self):
  with patch('attribute_manual.gather',return_value=self.facts) as read,patch('attribute_manual.store.by_key',return_value=None),patch('attribute_manual.store.active',return_value=[]),patch('attribute_manual.store.create') as create,patch('attribute_manual.store.transition') as transition:
   with self.assertRaises(ValueError):add(None,Mock(),7,'MLB123',42,self.parent,form([('MATERIAL','Aço',''),('WIDTH','12 kg','')]),dict(status='ativa',user_id=123),lambda:'private',Mock())
   self.assertEqual(read.call_count,1);create.assert_not_called();transition.assert_not_called()
 def test_parse_rejects_duplicate_blank_misaligned_and_oversized_batches(self):
  cases=[form([]),form([('MATERIAL','Aço','')]*2),form([('','Aço','')]),form([('MATERIAL','','')]),form([('MATERIAL','x'*1001,'')]),form([('MATERIAL','Aço','x'*501)]),form([('MATERIAL','Aço\x00','')]),form([('MATERIAL','Aço','\n')]),form([(str(i),'v','') for i in range(51)]),MultiDict([('manual_key','k'*24),('manual_field','MATERIAL'),('manual_value','Aço')])]
  for data in cases:
   with self.subTest(data=data):
    with self.assertRaises(ValueError):parse(data)
 def test_parse_accepts_fifty_distinct_targets_and_separate_variations(self):
  _,entries=parse(form([(str(i),'valor','') for i in range(50)]));self.assertEqual(len(entries),50)
  self.assertEqual(len(parse(form([('v:101:GTIN','789001',''),('v:102:GTIN','789002','')]))[1]),2)
 def test_single_legacy_form_is_compatible(self):
  _,read,create,transition=self.call(form([('MATERIAL','Aço','Fonte')]))
  request=transition.call_args_list[0].kwargs['data']['manual_request']
  self.assertEqual(request,dict(parent_plan=self.parent['id'],field='MATERIAL',value='Aço',note='Fonte'))
 def test_duplicate_batch_returns_same_draft_without_reads(self):
  _,entries=parse(form());request=dict(parent_plan=self.parent['id'],entries=entries)
  previous=dict(id='child',data=dict(manual_request=request));self.parent['state']='stale'
  result,read,create,transition=self.call(previous=previous)
  self.assertEqual(result,previous);read.assert_not_called();create.assert_not_called();transition.assert_not_called()
 def test_reusing_key_with_different_values_is_rejected(self):
  with self.assertRaises(ValueError):self.call(previous=dict(data=dict(manual_request=dict(parent_plan=self.parent['id'],entries=[]))))
 def test_total_declared_limit_is_checked_before_read(self):
  self.parent['data']['manual_inputs']=[dict(id='OTHER'+str(i),value='v',note='') for i in range(49)];self.parent['data']['manual_actor']=42
  with self.assertRaises(ValueError):self.call()
  self.read.assert_not_called()
 def test_unavailable_target_rejected_before_read(self):
  with self.assertRaises(ValueError):self.call(form([('MATERIAL','Aço',''),('UNKNOWN','x','')]))
  self.read.assert_not_called()
 def test_existing_declared_values_are_kept_and_selected_ones_replaced_in_new_draft(self):
  self.parent['data']=analyze(self.facts,[dict(id='MATERIAL',value='Plástico',note='antigo')],42)
  _,_,_,transition=self.call(form([('WIDTH','12 cm','Medido')]))
  inputs=transition.call_args_list[0].kwargs['data']['manual_inputs'];self.assertEqual(inputs[0]['value'],'Plástico');self.assertEqual(len(inputs),2)
 def test_view_recovers_all_rows_and_escapes_values_and_sources(self):
  fields=self.parent['data']['manual_fields'];submitted=form([('MATERIAL','<img src=x onerror=bad()>','<script>bad()</script>'),('WIDTH','12 kg','segunda fonte')])
  html=render(fields,'csrf',self.parent['id'],'k'*24,submitted)
  self.assertEqual(html.count('class="ae-manual-row"'),2);self.assertIn('value="12 kg"',html);self.assertIn('segunda fonte',html);self.assertNotIn('<img src=',html);self.assertNotIn('<script>bad()',html)
  self.assertIn('value="WIDTH" selected',html);self.assertIn('2 de 50',html)
 def test_view_caps_untrusted_recovery_rows(self):
  html=render(self.parent['data']['manual_fields'],'csrf',self.parent['id'],'k'*24,form([(str(i),'v','') for i in range(100)]))
  self.assertEqual(html.count('class="ae-manual-row"'),50);self.assertIn('class="ae-add-row" disabled',html)
