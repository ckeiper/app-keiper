from copy import deepcopy
import unittest
from content_attribute_units import check,compare,render
from listing_content_snapshot import inspect
from test_listing_content_snapshot import item,requester,NOW

def definition(**kw):return dict(dict(id='WIDTH',name='Largura',value_type='number_unit',tags={},allowed_units=[dict(id='cm',name='cm'),dict(id='mm',name='mm')]),**kw)
def value(unit='cm',number=0,**kw):return dict(dict(id='WIDTH',value_name=str(number)+' '+unit,value_struct=dict(number=number,unit=unit)),**kw)
class ContentUnitTests(unittest.TestCase):
 def test_explicit_rules_only_zero_negative_and_unknown_units(self):
    for number in (0,-10,0.25):self.assertEqual(check(definition(),value(number=number))[0],'matched')
    self.assertEqual(check(definition(),value('kg'))[0],'review')
    for row in [value(value_struct=None),value(number=True),value(number=float('nan')),value(number='2'),value(value_id='-1'),value(values=[dict(name='2 cm')])]:
        self.assertEqual(check(definition(),row)[0],'unknown')
    for units in (None,[],[dict(name='cm')],[dict(id='cm'),dict(id='cm')]):self.assertEqual(check(definition(allowed_units=units),value())[0],'unknown')
    # Never infer cm from the text or silently convert a non-returned alias.
    self.assertEqual(check(definition(),value(value_name='2 cm',value_struct=None))[0],'unknown')
    self.assertEqual(check(definition(),value('CM'))[0],'review')
 def test_optional_main_and_each_variation_group(self):
    data=dict(attributes=[value()],variations=[dict(id=1,attributes=[value('kg')],attribute_combinations=[]),dict(id=2,attributes=[],attribute_combinations=[value('mm')])])
    original=deepcopy(data);result=compare([definition()],data)
    self.assertEqual([r['state'] for r in result['rows']],['matched','review','matched']);self.assertEqual(data,original)
    self.assertIn('Variação 2',result['rows'][2]['location'])
    self.assertEqual(compare([definition(value_type='string')],data)['rows'],[])
 def test_duplicate_variations_no_conclusions_and_limits(self):
    data=dict(attributes=[],variations=[dict(id=1,attributes=[value('kg')]),dict(id=1,attributes=[value('kg')])])
    result=compare([definition()],data);self.assertTrue(result['variation_unknown']);self.assertEqual(result['rows'],[])
    data=dict(attributes=[],variations=[dict(id=i,attributes=[value()],attribute_combinations=[]) for i in range(150)])
    result=compare([definition()],data);self.assertTrue(result['truncated']);self.assertEqual(len(result['rows']),100)
    self.assertEqual(compare([definition(),definition()],data)['state'],'unknown')
 def test_managed_fields_and_escape(self):
    result=compare([definition(name='<script>',tags=dict(read_only=True))],dict(attributes=[value('<img>')],variations=[]))
    text=render(result);self.assertNotIn('<script>',text);self.assertNotIn('<img>',text);self.assertIn('Campo gerenciado',text);self.assertNotIn('antes de corrigir',text)
 def test_snapshot_reuses_official_request_and_preserves_unknown(self):
    data=item();data.update(category_id='MLB200',attributes=[value('kg')],variations=[])
    get=requester([dict(id=123),data,dict(plain_text='Descrição'),[definition()]])
    result=inspect('synthetic',123,'MLB123',get,NOW)
    self.assertEqual(result['attribute_units']['rows'][0]['state'],'review');self.assertEqual(get.call_count,4)
    result=inspect('synthetic',123,'MLB123',requester([dict(id=123),data,{},{}]),NOW)
    self.assertEqual(result['attribute_units']['state'],'unknown')
