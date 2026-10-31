from copy import deepcopy
import unittest
from unittest.mock import Mock,patch
from attribute_completion import analyze
from attribute_edit_workflow import apply
from test_attribute_completion import facts,definition,listing,reader

class ProseTests(unittest.TestCase):
 def test_positive_assertions_preserve_context_and_values(self):
  text='O material é de aço. A largura mede 12,5 cm.'
  data=analyze(facts(definitions=[definition(tags=dict(hidden=True)),definition('WIDTH',name='Largura',value_type='number_unit',allowed_units=[dict(id='cm')])],description=text))
  by_id={p['id']:p for p in data['proposals']}
  self.assertEqual(by_id['MATERIAL']['value'],'aço');self.assertTrue(by_id['MATERIAL']['hidden'])
  self.assertEqual(by_id['WIDTH']['expected'],dict(kind='unit',value='12.5',unit='cm'))
  self.assertEqual(by_id['MATERIAL']['evidence'][0]['text'],text);self.assertEqual(by_id['WIDTH']['evidence'][0]['reading'],'assertion')
 def test_articles_possessives_and_official_field_names(self):
  for text in ['O material é aço.','A sua material é aço.','Seu material é aço.','MATERIAL É AÇO.','- O material é aço.']:
   self.assertEqual(len(analyze(facts(description=text))['proposals']),1,text)
 def test_questions_negation_alternatives_conditions_and_multiple_assertions_abstain(self):
  for text in ['O material não é aço.','O material pode ser aço.','O material talvez seja aço.','O material é aço?','O material é aço ou plástico.','O material é aproximadamente aço.','O material é aço e a cor é azul.','O material é um aço.']:
   self.assertEqual(analyze(facts(description=text))['proposals'],[],text)
 def test_conflicts_between_formats_and_uncertain_assertions_abstain(self):
  for text in ['Material: Aço\nO material é plástico.','Material: Aço\nO material pode ser plástico.','Material: Aço\nO material não é plástico.']:
   data=analyze(facts(description=text));self.assertEqual(data['proposals'],[],text);self.assertIn('texto precisa de conferência',data['inventory']['rows'][0]['message'])
 def test_other_product_package_and_variant_contexts_are_not_promoted(self):
  for prefix in ['Compatibilidade','Conteúdo da embalagem','Medidas da embalagem','Variação azul','Exemplo','Referência','Compatível com Produto X.']:
   self.assertEqual(analyze(facts(description=prefix+'\nO material é aço.'))['proposals'],[],prefix)
  variants=[dict(id=1,attributes=[],attribute_combinations=[])]
  self.assertEqual(analyze(facts(item=listing(variations=variants),description='O material é aço.'))['proposals'],[])
 def test_prose_still_requires_official_values_units_and_unique_alias(self):
  self.assertEqual(analyze(facts(description='O material é verde.',definitions=[definition(value_type='list',values=[dict(id='1',name='Aço')])]))['proposals'],[])
  self.assertEqual(analyze(facts(description='A largura mede 12 kg.',definitions=[definition('WIDTH',name='Largura',value_type='number_unit',allowed_units=[dict(id='cm')])]))['proposals'],[])
  self.assertEqual(analyze(facts(description='O material é aço.',definitions=[definition(),definition('OTHER',name='Material')]))['proposals'],[])
 def test_title_reading_is_explicit_and_no_brand_keyword_guess(self):
  self.assertEqual(len(analyze(facts(item=listing(title='O material é aço.'),description=''))['proposals']),1)
  self.assertEqual(analyze(facts(item=listing(title='Capa compatível com Samsung'),definitions=[definition('BRAND',name='Marca')],description=''))['proposals'],[])
 def test_policy_version_or_reviewed_payload_change_blocks_put(self):
  data=analyze(facts());plan=dict(state='ready',created_at=100,data=data);put=Mock();persist=Mock()
  old=deepcopy(plan);old['data'].pop('extractor_version')
  get=reader();apply(old,['MATERIAL'],'p',123,'MLB123',get,put,persist,now=101)
  get.assert_not_called()
  self.assertEqual(persist.call_args.args[0],'stale');put.assert_not_called()
  changed=deepcopy(data);changed['proposals'][0]['payload']['value_name']='Outro valor'
  with patch('attribute_edit_workflow.analyze',return_value=changed):apply(plan,['MATERIAL'],'p',123,'MLB123',reader(),put,persist,now=101)
  self.assertEqual(persist.call_args.args[0],'stale');put.assert_not_called()

 def test_official_string_option_uses_id_and_verifies_normalized_readback(self):
  from test_attribute_completion import response
  defs=[definition(values=[dict(id='mat1',name='Aço')])];description='O material é aço.'
  data=analyze(facts(definitions=defs,description=description));plan=dict(state='ready',created_at=100,data=data)
  self.assertEqual(data['proposals'][0]['payload'],dict(id='MATERIAL',value_id='mat1'))
  get=reader(definitions=defs,description=description);get.side_effect=list(get.side_effect)+[response(dict(id=123)),response(listing(attributes=[dict(id='MATERIAL',value_id='mat1',value_name='Aço')]))]
  put=Mock(return_value=response({}));persist=Mock();apply(plan,['MATERIAL'],'p',123,'MLB123',get,put,persist,now=101)
  self.assertEqual(put.call_count,1);self.assertEqual(persist.call_args.args[0],'confirmed')

 def test_context_carries_across_paragraphs_until_explicit_product_section(self):
  self.assertEqual(analyze(facts(description='Compatibilidade\n\nO material é aço.'))['proposals'],[])
  data=analyze(facts(description='Compatibilidade\n\nO material é plástico.\n\nCaracterísticas do produto\n\nO material é aço.'))
  self.assertEqual(data['proposals'][0]['value'],'aço')

 def test_internal_na_is_requested_and_never_replaced(self):
  from test_attribute_completion import response
  from attribute_completion import gather
  def get(url,**kwargs):
   if url.endswith('/users/me'):return response(dict(id=123))
   if url.endswith('/description'):return response(dict(plain_text='O material é aço.'))
   if url.endswith('/attributes'):return response([definition()])
   if url.endswith('/technical_specs/input'):return response(dict(groups=[]))
   self.assertTrue(url.endswith('/items/MLB123?include_internal_attributes=true'))
   return response(listing(attributes=[dict(id='MATERIAL',value_id='-1',value_name=None)]))
  read=Mock(side_effect=get);data=analyze(gather('private',123,'MLB123',read))
  self.assertEqual(read.call_count,5);self.assertEqual(data['proposals'],[]);self.assertIn('Não aplicável declarado',data['inventory']['rows'][0]['message'])

 def test_symbols_and_unit_prefix_case_are_never_inferred(self):
  rule=definition(value_type='number_unit',allowed_units=[dict(id='%',name='Porcentagem')])
  self.assertEqual(analyze(facts(definitions=[rule],description='Material: 12 @'))['proposals'],[])
  self.assertEqual(analyze(facts(definitions=[rule],description='Material: 12 %'))['proposals'][0]['expected']['unit'],'%')
  rule=definition(value_type='number_unit',allowed_units=[dict(id='MB',name='MB')])
  self.assertEqual(analyze(facts(definitions=[rule],description='Material: 12 Mb'))['proposals'],[])
  self.assertEqual(analyze(facts(definitions=[rule],description='Material: 12 MB'))['proposals'][0]['expected']['unit'],'MB')
 def test_official_option_punctuation_is_preserved(self):
  rule=definition(value_type='list',values=[dict(id='1',name='A-B')])
  self.assertEqual(analyze(facts(definitions=[rule],description='O material é A B.'))['proposals'],[])
  self.assertEqual(analyze(facts(definitions=[rule],description='O material é A-B.'))['proposals'][0]['payload']['value_id'],'1')
