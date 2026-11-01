"""Safe missing per-variation values, complete ID preservation and readback."""
from copy import deepcopy
import unittest
from unittest.mock import Mock
import requests
from attribute_completion import analyze,matches
from attribute_edit_workflow import apply,verification,confirmed
from attribute_variations import payload,snapshot
from test_attribute_completion import definition,listing,facts,reader,response


def variant(vid=101,**kw):
 return dict(dict(id=vid,attributes=[dict(id='SELLER_SKU',value_name='sku-'+str(vid))],attribute_combinations=[dict(id='COLOR',value_name='Azul' if vid==101 else 'Preto')],price=80,available_quantity=4,picture_ids=['picture'],sold_quantity=3),**kw)
def rule(**kw):return definition('GTIN',name='Código de barras',tags=dict(variation_attribute=True,hidden=True),**kw)
def fixture(**kw):return facts(item=listing(variations=[variant(),variant(102)]),definitions=[rule()],description='',**kw)
def manual(code='v:101:GTIN',value='789000001',note='Fabricante'):return dict(id=code,value=value,note=note)


class VariationTests(unittest.TestCase):
 def test_fields_identify_variation_and_never_extract_shared_description(self):
  f=fixture();before=deepcopy(f);d=analyze(f)
  self.assertEqual([x['id'] for x in d['manual_fields']],['v:101:GTIN','v:102:GTIN'])
  self.assertIn('Azul',d['manual_fields'][0]['name']);self.assertEqual(d['proposals'],[])
  p=analyze(f,[manual()],42)['proposals'][0]
  self.assertEqual(p['variation_id'],'101');self.assertEqual(p['attribute_id'],'GTIN');self.assertTrue(p['hidden']);self.assertIn('Variação 101',p['evidence'][0]['source']);self.assertEqual(f,before)
 def test_only_explicit_variation_attribute_without_restricted_tags(self):
  for tags in [{},{'allow_variations':True},{'variation_attribute':'true'},*[dict(variation_attribute=True,**{t:True}) for t in ['read_only','fixed','inferred','product_pk','parent_pk','child_pk','restricted_values','others','defines_picture','allow_variations']]]:
   f=facts(item=listing(variations=[variant()]),definitions=[definition('GTIN',tags=tags)],description='')
   self.assertFalse(any(x.get('variation_id') for x in analyze(f)['manual_fields']))
   with self.assertRaises(ValueError):analyze(f,[manual()],42)
 def test_existing_na_complex_main_or_combination_values_never_replaced(self):
  for extra in [dict(value_name='existente'),dict(value_id='-1'),dict(value_id='0'),dict(values=[dict(name='x')]),dict(value_struct=dict(number=1))]:
   for location in ['main','variation','combination']:
    v=variant();item=listing(variations=[v]);row=dict(id='GTIN',**extra)
    if location=='main':item['attributes']=[row]
    elif location=='variation':v['attributes'].append(row)
    else:v['attribute_combinations'].append(row)
    with self.subTest(extra=extra,location=location):
     d=analyze(facts(item=item,definitions=[rule()],description=''));self.assertEqual(d['manual_fields'],[])
     with self.assertRaises(ValueError):analyze(facts(item=item,definitions=[rule()],description=''),[manual()],42)
 def test_missing_malformed_duplicate_ids_and_attributes_fail_closed(self):
  variants=[[variant(True)],[variant('001')],[variant(0)],[variant(),variant('101')],[variant(catalog_product_id='MLB1')],[variant(user_product_id='MLBU1')],[variant(attributes=None)],[variant(attribute_combinations=None)],[variant(attributes=[dict(id='X'),dict(id='X')])],[variant(vid=i+1) for i in range(101)]]
  for rows in variants:
   with self.subTest(rows=rows):
    self.assertIsNone(snapshot(listing(variations=rows)))
    d=analyze(facts(item=listing(variations=rows),definitions=[rule()],description=''));self.assertFalse(any(x.get('variation_id') for x in d['manual_fields']))
    self.assertTrue(d['warnings'])
 def test_payload_preserves_all_ids_all_prior_attributes_and_no_other_properties(self):
  f=fixture();d=analyze(f,[manual()],42);before=deepcopy(f)
  out=payload(d['proposals'],f['item'])
  self.assertEqual(out,dict(variations=[dict(id=101,attributes=[dict(id='SELLER_SKU',value_name='sku-101'),dict(id='GTIN',value_name='789000001')]),dict(id=102)]))
  self.assertEqual(f,before)
  self.assertNotIn('available_quantity',str(out));self.assertNotIn('price',str(out));self.assertNotIn('picture_ids',str(out));self.assertNotIn('attribute_combinations',str(out))
 def test_two_variations_and_common_values_can_be_reviewed_individually(self):
  f=facts(item=listing(variations=[variant(),variant(102)]),definitions=[rule(),definition()],description='Material: Aço')
  d=analyze(f,[manual(),manual('v:102:GTIN','789000002')],42)
  self.assertEqual(len(d['proposals']),3)
  out=payload(d['proposals'],f['item']);self.assertEqual(out['attributes'],[dict(id='MATERIAL',value_name='Aço')]);self.assertEqual(len(out['variations']),2)
  self.assertEqual(out['variations'][1]['attributes'][-1]['value_name'],'789000002')
 def test_value_options_and_units_still_use_official_rules(self):
  for value in ['12 cm','12 kg']:
   f=facts(item=listing(variations=[variant()]),definitions=[rule(value_type='number_unit',allowed_units=[dict(id='cm')])],description='')
   if value=='12 cm':self.assertEqual(analyze(f,[manual(value=value)],42)['proposals'][0]['expected']['unit'],'cm')
   else:
    with self.assertRaises(ValueError):analyze(f,[manual(value=value)],42)
 def test_readback_checks_target_and_preservation_not_http_200(self):
  f=fixture();d=analyze(f,[manual()],42);after=deepcopy(f['item']);after['variations'][0]['attributes'].append(dict(id='GTIN',value_name='789000001'))
  self.assertTrue(confirmed(verification(d,['v:101:GTIN'],after)))
  for change in ['missing_variant','missing_old_attr','changed_old_attr','changed_combination','wrong_target','unknown_attrs']:
   item=deepcopy(after)
   if change=='missing_variant':item['variations'].pop()
   elif change=='missing_old_attr':item['variations'][0]['attributes'].pop(0)
   elif change=='changed_old_attr':item['variations'][1]['attributes'][0]['value_name']='changed'
   elif change=='changed_combination':item['variations'][0]['attribute_combinations'][0]['value_name']='Vermelho'
   elif change=='wrong_target':item['variations'][1]['attributes'].append(item['variations'][0]['attributes'].pop())
   else:item['variations'][1]['attributes']=None
   with self.subTest(change=change):self.assertFalse(confirmed(verification(d,['v:101:GTIN'],item)))
 def test_writer_single_put_targeted_selection_and_verification(self):
  f=fixture();d=analyze(f,[manual(),manual('v:102:GTIN','789000002')],42);p=dict(state='ready',created_at=100,created_by=42,data=d)
  after=deepcopy(f['item']);after['variations'][0]['attributes'].append(dict(id='GTIN',value_name='789000001'))
  get=reader(item=f['item'],definitions=[rule()],description='',extra=[dict(id=123),after]);put=Mock(return_value=response({}));persist=Mock()
  apply(p,['v:101:GTIN'],'private',123,'MLB123',get,put,persist,now=101)
  self.assertEqual(put.call_count,1);self.assertEqual(put.call_args.kwargs['json']['variations'][1],dict(id=102));self.assertEqual(persist.call_args.args[0],'confirmed')
 def test_changed_variation_prevents_put_and_stock_alone_does_not(self):
  f=fixture();d=analyze(f,[manual()],42);p=dict(state='ready',created_at=100,created_by=42,data=d)
  for change in ['add','remove','attr','combination']:
   item=deepcopy(f['item'])
   if change=='add':item['variations'].append(variant(103))
   elif change=='remove':item['variations'].pop()
   elif change=='attr':item['variations'][1]['attributes'][0]['value_name']='other'
   else:item['variations'][0]['attribute_combinations'][0]['value_name']='other'
   put=Mock();persist=Mock();apply(p,['v:101:GTIN'],'private',123,'MLB123',reader(item=item,definitions=[rule()],description=''),put,persist,now=101);put.assert_not_called()
  item=deepcopy(f['item']);item['variations'][0]['available_quantity']=2
  put=Mock(side_effect=requests.Timeout());persist=Mock();apply(p,['v:101:GTIN'],'private',123,'MLB123',reader(item=item,definitions=[rule()],description=''),put,persist,now=101)
  self.assertEqual(put.call_count,1);self.assertEqual(persist.call_args.args[0],'uncertain')
 def test_bound_offered_destinations_and_snapshot_size(self):
  rules=[definition('FIELD'+str(i),tags=dict(variation_attribute=True)) for i in range(100)]
  d=analyze(facts(item=listing(variations=[variant(i+1) for i in range(20)]),definitions=rules,description=''))
  self.assertEqual(len(d['manual_fields']),1000);self.assertTrue(d['warnings'])
  self.assertIsNone(snapshot(listing(variations=[variant(attributes=[dict(id='X',value_name='x'*262144)])])))
 def test_snapshot_or_approved_target_tampering_prevents_put(self):
  d=analyze(fixture(),[manual()],42)
  for change in ['snapshot','target']:
   data=deepcopy(d)
   if change=='snapshot':data['variation_snapshot'][0]['attributes']=[]
   else:data['proposals'][0]['variation_id']='102'
   put=Mock();persist=Mock();apply(dict(state='ready',created_at=100,created_by=42,data=data),['v:101:GTIN'],'private',123,'MLB123',reader(item=fixture()['item'],definitions=[rule()],description=''),put,persist,now=101);put.assert_not_called()
