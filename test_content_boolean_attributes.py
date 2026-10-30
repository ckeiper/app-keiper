import unittest
from copy import deepcopy
from content_boolean_attributes import check,compare,render
from listing_content_snapshot import inspect
from test_listing_content_snapshot import item,requester,NOW

def definition(**kw):return dict(dict(id='BLUETOOTH',name='Bluetooth',value_type='boolean',tags={},values=[dict(id='1',name='Não'),dict(id='2',name='Sim')]),**kw)
def value(identifier='2',**kw):return dict(dict(id='BLUETOOTH',value_id=identifier,value_name='Sim'),**kw)
class BooleanAttributeTests(unittest.TestCase):
 def test_exact_ids_no_text_inference_or_absence_errors(self):
    self.assertEqual(check(definition(),value())[0],'matched')
    self.assertEqual(check(definition(),value(1))[0],'matched')
    self.assertEqual(check(definition(),value('999'))[0],'review')
    for row in (value(None),value(False),value(''),value('-1'),value(values=[dict(id='1')]),value(values=[dict(id='2'),dict(id='1')])):
        self.assertEqual(check(definition(),row)[0],'unknown')
    self.assertEqual(check(definition(),value(values=[dict(id=2)]))[0],'matched')
    # Text does not override a known ID, nor certify semantic correctness.
    self.assertEqual(check(definition(),value(value_name='Texto personalizado'))[0],'matched')
 def test_unverifiable_metadata_never_confirms_validity(self):
    for values in (None,[],[dict(id='1')],[dict(id='1'),dict(id='1')],[dict(id=True),dict(id='2')],[dict(id='-1'),dict(id='2')]):
        self.assertEqual(check(definition(values=values),value())[0],'unknown')
 def test_optional_main_each_variation_group_and_immutable(self):
    data=dict(attributes=[value()],variations=[dict(id=1,attributes=[value('999')],attribute_combinations=[]),dict(id=2,attributes=[],attribute_combinations=[value(None)])])
    before=deepcopy(data);result=compare([definition()],data)
    self.assertEqual([r['state'] for r in result['rows']],['matched','review','unknown']);self.assertEqual(data,before)
    self.assertEqual(compare([definition(value_type='string')],data)['rows'],[])
 def test_invalid_variations_limits_and_escaped_managed_fields(self):
    data=dict(attributes=[],variations=[dict(id=1,attributes=[value()]),dict(id=1,attributes=[value()])])
    result=compare([definition()],data);self.assertTrue(result['variation_unknown']);self.assertEqual(result['rows'],[])
    data=dict(attributes=[],variations=[dict(id=i,attributes=[value()],attribute_combinations=[]) for i in range(150)])
    result=compare([definition()],data);self.assertTrue(result['truncated']);self.assertEqual(len(result['rows']),100)
    result=compare([definition(name='<script>',tags=dict(read_only=True))],dict(attributes=[value('<img>')],variations=[]))
    text=render(result);self.assertNotIn('<script>',text);self.assertNotIn('<img>',text);self.assertIn('Campo gerenciado',text);self.assertNotIn('Confira a opção',text)
    self.assertEqual(compare([definition(),definition()],data)['state'],'unknown')
 def test_snapshot_uses_same_four_requests_and_preserves_failures(self):
    data=item();data.update(category_id='MLB200',attributes=[value('999')],variations=[])
    get=requester([dict(id=123),data,{},[definition()]])
    result=inspect('synthetic',123,'MLB123',get,NOW)
    self.assertEqual(get.call_count,4);self.assertEqual(result['boolean_values']['rows'][0]['state'],'review')
    result=inspect('synthetic',123,'MLB123',requester([dict(id=123),data,{},{}]),NOW)
    self.assertEqual(result['boolean_values']['state'],'unknown')
