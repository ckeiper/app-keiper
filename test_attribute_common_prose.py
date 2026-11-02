"""Explicit common product sections must never promote variant-specific facts."""
from copy import deepcopy
import unittest
from unittest.mock import Mock
from attribute_completion import analyze
from attribute_edit_workflow import apply
from test_attribute_completion import facts,definition,listing,reader,response
from test_attribute_variations import variant,rule


def definitions():return [definition(tags=dict(hidden=True)),definition('WIDTH',name='Largura',value_type='number_unit',allowed_units=[dict(id='cm')]),definition('COLOR',name='Cor',tags=dict(allow_variations=True)),rule()]
def item(**kw):return listing(variations=[variant(),variant(102)],**kw)
def data(text,**kw):return analyze(facts(item=item(),definitions=definitions(),description=text,**kw))


class CommonProseTests(unittest.TestCase):
 def test_explicit_product_section_suggests_only_common_empty_fields(self):
  text='Características do produto\nO material é de aço. A largura mede 12,5 cm.\nO código de barras é 789000001.'
  d=data(text);self.assertEqual({p['id'] for p in d['proposals']},{'MATERIAL','WIDTH'})
  p=next(p for p in d['proposals'] if p['id']=='MATERIAL');self.assertTrue(p['hidden']);self.assertEqual(p['evidence'][0]['text'],text);self.assertEqual(p['evidence'][0]['reading'],'assertion')
  self.assertTrue(all(not p.get('variation_id') for p in d['proposals']))
 def test_without_product_section_prose_remains_pending_but_labels_work(self):
  self.assertEqual(data('O material é aço.')['proposals'],[])
  self.assertEqual(data('Material: Aço')['proposals'][0]['value'],'Aço')
  self.assertEqual(data('Produto de teste\nMaterial: Aço')['proposals'][0]['value'],'Aço')
 def test_known_variant_value_dimension_or_id_scopes_persist(self):
  for heading in ['Azul','PRETO:','Cor: Azul','COLOR Azul','101','Variação 101','Variações','O tamanho é G.','Modelo exclusivo','10 x 20']:
   text='Características do produto\n'+heading+'\n\nO material é plástico.'
   with self.subTest(heading=heading):self.assertEqual(data(text)['proposals'],[])
 def test_unknown_heading_or_free_text_ends_common_section(self):
  for line in ['Oferta especial','Características da opção escolhida','Disponível nas opções abaixo','Outro acabamento']:
   self.assertEqual(data('Ficha técnica\n'+line+'\nO material é aço.')['proposals'],[])
   self.assertEqual(data(line+'\nFicha técnica\nO material é aço.')['proposals'],[])
 def test_generic_product_header_cannot_reset_variant_scope(self):
  for heading in ['Ficha técnica','Características do produto','Dados técnicos']:
   self.assertEqual(data('Azul\n\n'+heading+'\nO material é aço.')['proposals'],[])
 def test_explicit_shared_section_can_resume_after_variant_scope(self):
  for heading in ['Atributos comuns a todas as variações','Características comuns a todas as variações','Ficha técnica comum a todas as variações']:
   d=data('Azul\n\n'+heading+'\nO material é aço.');self.assertEqual(d['proposals'][0]['value'],'aço',heading)
 def test_variant_references_invalidate_conflicting_or_same_common_field(self):
  for line in ['Material: Plástico','O material é plástico.','Material: Aço','O material pode ser plástico.']:
   d=data('Ficha técnica\nO material é aço.\n\nAzul\n'+line)
   self.assertEqual(d['proposals'],[],line);self.assertIn('texto precisa de conferência',next(r for r in d['inventory']['rows'] if r['id']=='MATERIAL')['message'])
 def test_unrelated_variant_fact_does_not_invalidate_other_common_fields(self):
  d=data('Ficha técnica\nO material é aço.\n\nAzul\nA largura mede 10 cm.')
  self.assertEqual([p['id'] for p in d['proposals']],['MATERIAL'])
 def test_existing_main_na_and_variant_values_are_not_overwritten(self):
  for existing in [dict(value_name='Plástico'),dict(value_id='-1')]:
   d=analyze(facts(item=item(attributes=[dict(id='MATERIAL',**existing)]),definitions=definitions(),description='Ficha técnica\nO material é aço.'));self.assertEqual(d['proposals'],[])
  product=item();product['variations'][0]['attributes'].append(dict(id='MATERIAL',value_name='Aço'))
  self.assertEqual(analyze(facts(item=product,definitions=definitions(),description='Ficha técnica\nO material é aço.'))['proposals'],[])
 def test_official_values_units_and_ambiguity_gates_remain(self):
  for text in ['Ficha técnica\nA largura mede 12 kg.','Ficha técnica\nO material é aço ou plástico.','Ficha técnica\nO material é aço?','Ficha técnica\nMaterial: Plástico\nO material é aço.']:
   self.assertEqual(data(text)['proposals'],[],text)
  defs=definitions()
  next(r for r in defs if r['id']=='WIDTH')['allowed_units']=[dict(id='MB'),dict(id='Mb')]
  d=analyze(facts(item=item(),definitions=defs,description='Ficha técnica\nLargura: 12 MB\nA largura mede 12 Mb.'))
  self.assertEqual(d['proposals'],[]);self.assertIn('texto precisa de conferência',next(r for r in d['inventory']['rows'] if r['id']=='WIDTH')['message'])
 def test_missing_combination_names_values_or_structure_disable_new_prose(self):
  for change in ['name','value','missing','large']:
   product=item();defs=definitions()
   if change=='name':defs=[r for r in defs if r['id']!='COLOR']
   elif change=='value':product['variations'][0]['attribute_combinations'][0].pop('value_name')
   elif change=='missing':product['variations'][0]['attributes']=None
   else:product['variations']=[variant(i+1) for i in range(101)]
   self.assertEqual(analyze(facts(item=product,definitions=defs,description='Ficha técnica\nO material é aço.'))['proposals'],[],change)
 def test_reader_does_not_mutate_facts(self):
  f=facts(item=item(),definitions=definitions(),description='Ficha técnica\nO material é aço.');before=deepcopy(f);analyze(f);self.assertEqual(f,before)
 def test_writer_sends_common_attributes_only_and_rechecks_context(self):
  text='Ficha técnica\nO material é aço.';f=facts(item=item(),definitions=definitions(),description=text);d=analyze(f);plan=dict(state='ready',created_at=100,data=d)
  after=item(attributes=[dict(id='MATERIAL',value_name='aço')]);put=Mock(return_value=response({}));persist=Mock()
  get=reader(item=f['item'],definitions=definitions(),description=text,extra=[dict(id=123),after])
  apply(plan,['MATERIAL'],'private',123,'MLB123',get,put,persist,now=101)
  self.assertEqual(put.call_args.kwargs['json'],dict(attributes=[dict(id='MATERIAL',value_name='aço')]));self.assertEqual(persist.call_args.args[0],'confirmed')
  put=Mock();persist=Mock();apply(plan,['MATERIAL'],'private',123,'MLB123',reader(item=f['item'],definitions=definitions(),description=text+'\n\nAzul\nO material é plástico.'),put,persist,now=101);put.assert_not_called()
 def test_previous_reader_version_requires_new_review(self):
  d=data('Ficha técnica\nO material é aço.');d['extractor_version']=5;get=Mock();put=Mock();persist=Mock()
  apply(dict(state='ready',created_at=100,data=d),['MATERIAL'],'private',123,'MLB123',get,put,persist,now=101)
  get.assert_not_called();put.assert_not_called();self.assertEqual(persist.call_args.args[0],'stale')

 def test_inline_variant_references_do_not_become_common_values(self):
  for text in ['O material é aço na opção azul.','O material é aço para azul.','O material é aço nas versões azuis.','O material é aço na variante preta.','O material é aço modelo especial.','O material é aço azul.','Material: Aço para Azul','Material: Aço Azul']:
   with self.subTest(text=text):
    d=data('Ficha técnica\n'+text);self.assertEqual(d['proposals'],[])
    self.assertIn('texto precisa de conferência',next(r for r in d['inventory']['rows'] if r['id']=='MATERIAL')['message'])
 def test_inline_reference_in_later_paragraph_invalidates_prior_common_suggestion(self):
  self.assertEqual(data('Ficha técnica\nO material é aço.\n\nO material é aço na opção azul.')['proposals'],[])
