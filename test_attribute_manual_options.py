import unittest
from html.parser import HTMLParser
from attribute_manual_options import choices
from attribute_manual_view import compact, render

class OptionsTests(unittest.TestCase):
 def test_exact_names_are_not_abbreviated_and_numbers_are_not_values(self):
  name='x'*150
  self.assertEqual(choices(dict(value_type='list',values=[{'name':name},{'name':name},{'name':'bad\nvalue'},{'name':'y'*1001}])),[name])
  self.assertEqual(choices(dict(value_type='number_unit',values=[{'name':'cm'}])),[])
  self.assertEqual(len(choices(dict(value_type='string',values=[{'name':str(i)} for i in range(12)]))),10)
 def test_both_forms_keep_blank_values_and_escape_official_options(self):
  field=dict(id='MATERIAL',name='Material',hidden=True,value_type='list',choices=['Aço','<img src=x onerror=bad()>'])
  html=compact([field],'csrf','plan','k'*24)
  self.assertIn('value=""',html)
  self.assertIn('list="ae-compact-options-0"',html)
  self.assertIn('value="Aço"',html)
  self.assertNotIn('<img',html)
  html=render([field],'csrf','plan','k'*24)
  self.assertIn('data-choices=',html)
  self.assertIn('datalist id="ae-manual-options-0"',html)
  self.assertNotIn('<img',html)

 def test_analysis_keeps_full_official_choices_separate_from_short_examples(self):
  from test_attribute_completion import facts,definition
  from attribute_completion import analyze
  name='Nome oficial '+('x'*140)
  data=analyze(facts(description='',definitions=[definition(value_type='list',values=[dict(id='1',name=name)])]))
  field=data['manual_fields'][0]
  self.assertEqual(field['choices'],[name])
  self.assertLess(len(field['examples'][0]),len(name))
  self.assertEqual(data['proposals'],[])
