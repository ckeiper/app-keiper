from copy import deepcopy
import unittest
from unittest.mock import Mock
import requests
from attribute_completion import gather,analyze,matches,number
from attribute_edit_workflow import apply,verification
from listing_content_snapshot import ContentUnavailable


def definition(code='MATERIAL',**kw):return dict(dict(id=code,name=code.title(),value_type='string',tags={},value_max_length=100),**kw)
def listing(**kw):return dict(dict(id='MLB123',seller_id=123,site_id='MLB',category_id='MLB200',title='Produto',attributes=[],variations=[],tags=[],status='active',condition='new',catalog_listing=False),**kw)
def response(value,status=200):return Mock(status_code=status,json=Mock(return_value=value))
def reader(item=None,definitions=None,description='Material: Aço',sheet=None,extra=None):
 return Mock(side_effect=[response(x) for x in [dict(id=123),item or listing(),dict(plain_text=description),definitions or [definition()],sheet if sheet is not None else dict(groups=[])]+(extra or [])])
def facts(**kw):return gather('private-token',123,'MLB123',reader(**kw))

class CompletionTests(unittest.TestCase):
 def test_hidden_suggestion_source_and_inventory_union(self):
  f=facts(definitions=[definition(tags=dict(hidden=True))]);original=deepcopy(f);d=analyze(f)
  self.assertEqual(d['proposals'][0]['payload'],dict(id='MATERIAL',value_name='Aço'));self.assertTrue(d['proposals'][0]['hidden']);self.assertEqual(d['proposals'][0]['evidence'][0]['source'],'Descrição');self.assertEqual(f,original)
  self.assertIn('Oculto',d['inventory']['rows'][0]['name'])
 def test_only_explicit_unique_labels_no_title_guess(self):
  for description in ['Produto feito de aço','Material: Aço\nMaterial: Plástico','Material: A-B\nMaterial: A B','Material: Aço; Cor: Preto']:
   with self.subTest(description=description):self.assertEqual(analyze(facts(description=description))['proposals'],[])
  self.assertEqual(analyze(facts(item=listing(title='Marca Samsung'),definitions=[definition('BRAND',name='Marca')],description=''))['proposals'],[])
 def test_never_overwrite_existing_na_structures_or_variation_values(self):
  for attr in [dict(value_name='Plástico'),dict(value_id='-1'),dict(value_struct=dict(number=1)),dict(values=[dict(name='Aço')]),dict(value_id='0')]:
   d=analyze(facts(item=listing(attributes=[dict(id='MATERIAL',**attr)])));self.assertEqual(d['proposals'],[])
  variant=dict(id=1,attributes=[dict(id='MATERIAL',value_name='Aço')],attribute_combinations=[])
  self.assertEqual(analyze(facts(item=listing(variations=[variant])))['proposals'],[])
 def test_readonly_inferred_pk_and_unknown_metadata_never_proposed(self):
  for tags in [dict(hidden=True,read_only=True),dict(fixed=True),dict(inferred=True),dict(product_pk=True),dict(variation_attribute=True),dict(hidden='yes')]:
   self.assertEqual(analyze(facts(definitions=[definition(tags=tags)]))['proposals'],[])
  self.assertEqual(analyze(facts(definitions=[definition(hierarchy='PARENT_PK')]))['proposals'],[])
 def test_official_options_units_lengths_and_ambiguous_numbers(self):
  d=analyze(facts(definitions=[definition(value_type='list',values=[dict(id='1',name='Aço')])]))
  self.assertEqual(d['proposals'][0]['payload'],dict(id='MATERIAL',value_id='1'))
  self.assertEqual(analyze(facts(definitions=[definition(value_max_length=2)]))['proposals'],[])
  d=analyze(facts(definitions=[definition(value_type='number_unit',allowed_units=[dict(id='cm')])],description='Material: 12,5 cm'))
  self.assertEqual(d['proposals'][0]['expected'],dict(kind='unit',value='12.5',unit='cm'))
  self.assertIsNone(number('1,000'));self.assertIsNone(number('1.000'));self.assertIsNone(number('1.000,50'))
 def test_scope_checks_and_shared_user_product_block(self):
  for item in [listing(seller_id=999),listing(site_id='MLA'),listing(id='MLB999')]:
   with self.assertRaises(ContentUnavailable):facts(item=item)
  d=analyze(facts(item=listing(user_product_id='MLBU123'),extra=[dict(paging=dict(total=2),results=['MLB123','MLB456'])]))
  self.assertTrue(d['blocked']);self.assertEqual(len(d['proposals']),1)
  d=analyze(facts(item=listing(user_product_id='MLBU123'),extra=[dict(paging=dict(total=1),results=['MLB123'])]))
  self.assertFalse(d['blocked'])
 def test_rate_limit_stops_chain(self):
  get=Mock(side_effect=[response(dict(id=123)),response(listing()),response({},429)])
  with self.assertRaises(ContentUnavailable):gather('private',123,'MLB123',get)
  self.assertEqual(get.call_count,3)
 def test_readback_accepts_single_value_but_not_conflicts_or_multiple(self):
  p=analyze(facts())['proposals'][0]
  good=dict(id='MATERIAL',value_name='Aço',values=[dict(name='Aço',id=None,struct=None)])
  self.assertTrue(matches(p,listing(attributes=[good])))
  self.assertFalse(matches(p,listing(attributes=[dict(good,values=[dict(name='Plástico')])])))
  self.assertFalse(matches(p,listing(attributes=[dict(good,values=[dict(name='Aço'),dict(name='Plástico')])])))

class WriterTests(unittest.TestCase):
 def plan(self):return dict(state='ready',created_at=100,data=analyze(facts()))
 def test_selection_stale_and_used_plan_never_send(self):
  for codes in [[],['OTHER'],['MATERIAL','MATERIAL']]:
   put=Mock()
   with self.assertRaises(ValueError):apply(self.plan(),codes,'private',123,'MLB123',reader(),put,Mock(),now=101)
   put.assert_not_called()
  plan=self.plan();put=Mock();persist=Mock();apply(plan,['MATERIAL'],'private',123,'MLB123',reader(description='Material: Plástico'),put,persist,now=101)
  put.assert_not_called();self.assertEqual(persist.call_args.args[0],'stale')
  plan['state']='confirmed'
  with self.assertRaises(ValueError):apply(plan,['MATERIAL'],'private',123,'MLB123',reader(),put,Mock(),now=101)
 def test_one_put_explicit_payload_then_verified_readback(self):
  plan=self.plan();get=reader();get.side_effect=list(get.side_effect)+[response(dict(id=123)),response(listing(attributes=[dict(id='MATERIAL',value_name='Aço')]))]
  put=Mock(return_value=response({}));persist=Mock();apply(plan,['MATERIAL'],'private',123,'MLB123',get,put,persist,now=101)
  self.assertEqual(put.call_count,1);self.assertEqual(put.call_args.kwargs['json'],dict(attributes=[dict(id='MATERIAL',value_name='Aço')]))
  self.assertFalse(put.call_args.kwargs['allow_redirects']);self.assertEqual(persist.call_args.args[0],'confirmed');self.assertEqual(persist.call_args_list[0].args[0],'sending')
 def test_timeout_or_rate_limit_is_uncertain_without_retry_or_readback(self):
  for result in [requests.Timeout(),response({},429),response({},400)]:
   get=reader();put=Mock(side_effect=result if isinstance(result,Exception) else None,return_value=result);persist=Mock()
   apply(self.plan(),['MATERIAL'],'private',123,'MLB123',get,put,persist,now=101)
   self.assertEqual(put.call_count,1);self.assertEqual(get.call_count,5);self.assertEqual(persist.call_args.args[0],'uncertain')
 def test_readback_mismatch_or_failure_never_claims_success(self):
  for suffix in [[response(dict(id=123)),response(listing())],[response({},429)]]:
   get=reader();get.side_effect=list(get.side_effect)+suffix;persist=Mock()
   apply(self.plan(),['MATERIAL'],'private',123,'MLB123',get,Mock(return_value=response({})),persist,now=101)
   self.assertEqual(persist.call_args.args[0],'uncertain')
 def test_expired_or_blocked_or_changed_ownership_no_write(self):
  put=Mock();persist=Mock();apply(self.plan(),['MATERIAL'],'p',123,'MLB123',Mock(),put,persist,now=1001)
  put.assert_not_called();self.assertEqual(persist.call_args.args[0],'stale')
  get=reader(item=listing(seller_id=999));apply(self.plan(),['MATERIAL'],'p',123,'MLB123',get,put,persist,now=101);put.assert_not_called()
 def test_durable_intent_failure_prevents_marketplace_call(self):
  put=Mock()
  with self.assertRaises(RuntimeError):apply(self.plan(),['MATERIAL'],'p',123,'MLB123',reader(),put,Mock(side_effect=RuntimeError()),now=101)
  put.assert_not_called()
