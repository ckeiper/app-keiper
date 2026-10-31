"""Declared data remains distinct from extracted evidence and requires review."""
from copy import deepcopy
import unittest
from unittest.mock import Mock
from attribute_completion import analyze
from attribute_edit_workflow import apply
from attribute_edit_view import render
from test_attribute_completion import facts,listing,definition,reader,response


def entry(value='Aço',code='MATERIAL',note='Ficha do fabricante'):
 return dict(id=code,value=value,note=note)


class ManualTests(unittest.TestCase):
 def test_explicit_source_and_no_mutation_of_facts(self):
  f=facts(description='');before=deepcopy(f);d=analyze(f,[entry()],42)
  p=d['proposals'][0]
  self.assertEqual(p['payload'],dict(id='MATERIAL',value_name='Aço'));self.assertTrue(p['manual'])
  self.assertEqual(p['evidence'][0]['source'],'Informado por você');self.assertEqual(d['manual_actor'],42)
  self.assertEqual(p['evidence'][0]['text'],'Ficha do fabricante');self.assertEqual(f,before)
 def test_declared_value_overrides_only_draft_suggestion(self):
  d=analyze(facts(),[entry('Plástico')],42)
  self.assertEqual(len(d['proposals']),1);self.assertEqual(d['proposals'][0]['value'],'Plástico')
  self.assertEqual(d['proposals'][0]['before'],None)
 def test_every_existing_safety_gate_still_applies(self):
  fixtures=[facts(item=listing(attributes=[dict(id='MATERIAL',value_name='Aço')])),facts(item=listing(attributes=[dict(id='MATERIAL',value_id='-1')])),facts(item=listing(variations=[dict(id=1,attributes=[dict(id='MATERIAL',value_name='Aço')],attribute_combinations=[])]))]
  fixtures.extend(facts(definitions=[definition(tags={tag:True})]) for tag in ['read_only','fixed','inferred','product_pk','variation_attribute','restricted_values'])
  fixtures.append(facts(definitions=[definition(value_type='unknown')]))
  for f in fixtures:
   with self.subTest(f=f):
    self.assertEqual(analyze(f)['manual_fields'],[])
    with self.assertRaises(ValueError):analyze(f,[entry()],42)
 def test_official_options_units_numbers_and_length(self):
  for rule,value,ok in [(definition(value_type='list',values=[dict(id='9',name='Aço')]),'Aço',True),(definition(value_type='list',values=[dict(id='9',name='Aço')]),'Ferro',False),(definition(value_type='boolean',values=[dict(id='1',name='Sim')]),'Talvez',False),(definition(value_type='number_unit',allowed_units=[dict(id='cm')]),'12,5 cm',True),(definition(value_type='number_unit',allowed_units=[dict(id='cm')]),'12,5 kg',False),(definition(value_type='number'),'1,000',False),(definition(value_type='number'),'12,5',True),(definition(value_max_length=2),'Aço',False)]:
   with self.subTest(value=value,rule=rule):
    if ok:self.assertEqual(len(analyze(facts(definitions=[rule],description=''),[entry(value)],42)['proposals']),1)
    else:
     with self.assertRaises(ValueError):analyze(facts(definitions=[rule]),[entry(value)],42)
 def test_bounded_schema_unique_fields_and_actor(self):
  for inputs in ['bad',{},[entry(),entry()], [dict(entry(),payload={})], [entry('')],[entry('\x00')],[entry('x'*1001)],[entry(note='x'*501)],[entry(note='a\n')], [entry(code='UNKNOWN')], [entry()]*51]:
   with self.subTest(inputs=inputs):
    with self.assertRaises(ValueError):analyze(facts(),inputs,42)
  for actor in [None,True,0,'42']:
   with self.assertRaises(ValueError):analyze(facts(),[entry()],actor)
 def test_manual_survives_cap_and_keeps_other_auto_proposals(self):
  defs=[definition('FIELD'+str(i),name='Campo'+str(i)) for i in range(60)]
  d=analyze(facts(definitions=defs,description='\n'.join('FIELD'+str(i)+': valor' for i in range(60))),[entry('informado','FIELD59')],42)
  self.assertEqual(len(d['proposals']),50);self.assertEqual(d['proposal_total'],60)
  self.assertEqual(d['proposals'][0]['id'],'FIELD59');self.assertEqual(len(d['manual_fields']),60)
 def test_writer_revalidates_stored_input_and_confirms_selected_only(self):
  data=analyze(facts(description=''),[entry()],42)
  p=dict(state='ready',created_at=100,created_by=42,data=data);put=Mock(return_value=response({}));persist=Mock()
  get=reader(description='',extra=[dict(id=123),listing(attributes=[dict(id='MATERIAL',value_name='Aço')])])
  apply(p,['MATERIAL'],'private',123,'MLB123',get,put,persist,now=101)
  self.assertEqual(put.call_args.kwargs['json'],dict(attributes=[dict(id='MATERIAL',value_name='Aço')]))
  self.assertEqual(persist.call_args.args[0],'confirmed')
 def test_changed_input_actor_or_payload_never_sends(self):
  data=analyze(facts(),[entry()],42)
  for change in ['input','actor','payload']:
   d=deepcopy(data)
   if change=='input':d['manual_inputs'][0]['value']='Plástico'
   elif change=='actor':d['manual_actor']=99
   else:d['proposals'][0]['payload']['value_name']='Plástico'
   put=Mock();persist=Mock()
   apply(dict(state='ready',created_at=100,created_by=42,data=d),['MATERIAL'],'private',123,'MLB123',reader(),put,persist,now=101)
   put.assert_not_called();self.assertIn(persist.call_args.args[0],['stale','rejected'])
 def test_view_escapes_declared_data_and_never_selects_it(self):
  data=analyze(facts(description=''),[entry('<img src=x onerror=alert(1)>',note='<script>bad()</script>')],42)
  p=dict(id='11111111-1111-4111-8111-111111111111',state='ready',data=data)
  html=render(7,'MLB123','Produto','csrf','k'*24,p)
  self.assertIn('Informado:',html);self.assertIn('Informado por você',html);self.assertNotIn('<script>bad()',html);self.assertNotIn('<img src=',html);self.assertNotIn(' checked',html)
  self.assertIn('Adicionar à revisão',html)
  p['state']='confirmed';self.assertNotIn('Adicionar à revisão',render(7,'MLB123','Produto','csrf','k'*24,p))
