"""Local field filters preserve destination/value and never change submission."""
from html.parser import HTMLParser
import unittest
from werkzeug.datastructures import MultiDict
from attribute_manual_view import render


class Controls(HTMLParser):
 def __init__(self):super().__init__();self.controls=[]
 def handle_starttag(self,tag,attrs):
  if tag in ('input','select','option'):self.controls.append((tag,dict(attrs)))


class FieldSearchTests(unittest.TestCase):
 def fields(self):return [dict(id='MATERIAL',name='Material',hidden=False,value_type='string'),dict(id='v:101:GTIN',attribute_id='GTIN',variation_id='101',name='Variação 101 · Azul · Código de barras',hidden=True,value_type='string'),dict(id='v:102:GTIN',attribute_id='GTIN',variation_id='102',name='Variação 102 · Preto · Código de barras',hidden=True,value_type='string')]
 def page(self,values=None):return render(self.fields(),'csrf','plan','k'*24,values)
 def controls(self,html):p=Controls();p.feed(html);return p.controls
 def test_filters_are_unnamed_and_do_not_expand_posted_payload(self):
  controls=self.controls(self.page());search=[a for tag,a in controls if a.get('class')=='ae-field-search'];scope=[a for tag,a in controls if a.get('class')=='ae-field-scope']
  self.assertEqual(len(search),1);self.assertEqual(len(scope),1);self.assertNotIn('name',search[0]);self.assertNotIn('name',scope[0]);self.assertEqual(search[0]['maxlength'],'200')
  self.assertEqual({a['name'] for _,a in controls if 'name' in a},{'_csrf','action','plan','manual_key','manual_field','manual_value','manual_note'})
 def test_common_and_variation_options_have_explicit_scopes(self):
  options={a['value']:a for tag,a in self.controls(self.page()) if tag=='option' and 'data-scope' in a}
  self.assertEqual(options['MATERIAL']['data-scope'],'common');self.assertEqual(options['v:101:GTIN']['data-scope'],'101');self.assertEqual(options['v:102:GTIN']['data-scope'],'102')
 def test_recovery_keeps_separate_fields_and_all_values(self):
  values=MultiDict([('manual_field','MATERIAL'),('manual_value','Aço'),('manual_note','Fabricante'),('manual_field','v:102:GTIN'),('manual_value','789000001'),('manual_note','Fonte preta')])
  controls=self.controls(self.page(values));self.assertEqual(sum(a.get('class')=='ae-field-search' for _,a in controls),2)
  selected=[a['value'] for tag,a in controls if tag=='option' and 'selected' in a];self.assertEqual(selected,['MATERIAL','v:102:GTIN'])
  self.assertEqual([a['value'] for tag,a in controls if a.get('name')=='manual_value'],['Aço','789000001'])
 def test_untrusted_labels_and_scope_ids_are_escaped(self):
  fields=self.fields();fields[1]['name']='<script>window.injected=1</script>';fields[1]['variation_id']='"><img src=x onerror=bad()>'
  html=render(fields,'csrf','plan','k'*24);self.assertNotIn('<script>',html);self.assertNotIn('<img',html);self.assertIn('&lt;script&gt;',html)
 def test_variation_destinations_are_deduplicated(self):
  fields=self.fields()+[dict(self.fields()[1],id='v:101:WIDTH',attribute_id='WIDTH')]
  html=render(fields,'csrf','plan','k'*24);self.assertEqual(html.count('>Variação 101</option>'),1)
