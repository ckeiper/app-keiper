from copy import deepcopy
import unittest
from unittest.mock import Mock
from content_technical_specs import compare,parse,render
from listing_content_snapshot import inspect
from test_listing_content_snapshot import item,requester,NOW

def specs(*rows):return dict(groups=[dict(id='MAIN',components=[dict(attributes=list(rows))])])
def field(code='BRAND',**kw):return dict(dict(id=code,name=code,tags=['required']),**kw)
def rules():return [dict(id='BRAND',tags=dict(required=True)),dict(id='GTIN',tags=dict(conditional_required=True)),dict(id='MODEL',tags={})]
class TechnicalSpecsTests(unittest.TestCase):
 def test_publication_technical_context_and_presence_separate(self):
    data=item();data.update(attributes=[dict(id='BRAND',value_name='Marca')],variations=[])
    original=deepcopy(data);result=compare(specs(field(),field('MODEL'),field('GTIN'),field('EXTRA')),rules(),data)
    self.assertEqual([r['publication'] for r in result['rows']],['publication','technical','context','technical'])
    self.assertEqual([r['state'] for r in result['rows']],['informed','review','review','review']);self.assertEqual(data,original)
    result=compare(specs(field('GTIN')),rules(),data,dict(state='read',required_ids=['GTIN']))
    self.assertEqual(result['rows'][0]['publication'],'conditional')
    result=compare(specs(field()),None,data);self.assertEqual(result['rows'][0]['publication'],'unknown')
 def test_invalid_shape_duplicates_and_limits_remain_unknown(self):
    for payload in ({},dict(groups=None),dict(groups=[{}]),specs(dict(id='A',tags={})),specs(field(),field()),specs(field(id='')),specs(field(tags=[True])),specs(*[field(str(i)) for i in range(5001)])):
        with self.subTest(payload_type=type(payload)):self.assertEqual(compare(payload,rules(),item())['state'],'unknown')
    self.assertEqual(compare(specs(),rules(),item())['total'],0)
 def test_not_applicable_and_bad_variations_never_assume_errors(self):
    data=item();data.update(attributes=[dict(id='BRAND',value_id='-1')],variations=[])
    self.assertEqual(compare(specs(field()),rules(),data)['rows'][0]['state'],'unknown')
    data.update(attributes=[],variations=[dict(id=1,attributes=[dict(id='BRAND',value_name='X')],attribute_combinations=[]),dict(id=2,attributes=[],attribute_combinations=[])])
    result=compare(specs(field()),rules(),data)
    self.assertEqual(result['rows'][0]['state'],'review');self.assertEqual(len(result['rows'][0]['variations']),2)
    data['variations'][1]['id']=1
    self.assertEqual(compare(specs(field()),rules(),data)['rows'][0]['state'],'unknown')
 def test_managed_field_flag_escape_and_bounded_output(self):
    data=item();data.update(attributes=[],variations=[],tags=['incomplete_technical_specs'])
    result=compare(specs(field(name='<script>',tags=['required','read_only'])),rules(),data)
    text=render(result);self.assertNotIn('<script>',text);self.assertIn('Campo gerenciado',text);self.assertNotIn('Confira o preenchimento',text);self.assertIn('retornou o sinal',text)
    result=compare(specs(*[field(str(i)) for i in range(110)]),[],data)
    self.assertEqual(len(result['rows']),100);self.assertEqual(result['total'],110);self.assertIn('Exibidos 100 de 110',render(result))
 def test_optional_fifth_get_scope_and_failed_specs_preserve_content(self):
    data=item();data.update(category_id='MLB200',attributes=[],variations=[])
    get=requester([dict(id=123),data,{},rules(),specs(field())])
    result=inspect('synthetic',123,'MLB123',get,NOW,include_specs=True)
    self.assertEqual(get.call_count,5);self.assertTrue(get.call_args.args[0].endswith('/categories/MLB200/technical_specs/input'));self.assertEqual(result['technical_specs']['state'],'read')
    get=requester([dict(id=123),data,{},rules()]);result=inspect('synthetic',123,'MLB123',get,NOW)
    self.assertEqual(get.call_count,4);self.assertNotIn('technical_specs',result)
    get=requester([dict(id=123),data,{},rules()]);get.side_effect=list(get.side_effect)+[Mock(status_code=429)]
    result=inspect('synthetic',123,'MLB123',get,NOW,include_specs=True)
    self.assertEqual(result['state'],'read');self.assertEqual(result['technical_specs']['state'],'unknown');self.assertEqual(result['requirements']['state'],'read')
 def test_ownership_and_invalid_category_stop_new_call(self):
    get=requester([dict(id=999)]);self.assertEqual(inspect('x',123,'MLB123',get,NOW,include_specs=True)['state'],'unknown');self.assertEqual(get.call_count,1)
    data=item();data['category_id']='https://evil.invalid'
    get=requester([dict(id=123),data,{}]);result=inspect('x',123,'MLB123',get,NOW,include_specs=True)
    self.assertEqual(get.call_count,3);self.assertEqual(result['technical_specs']['state'],'unknown')

 def test_rate_limit_stops_additional_sheet_request(self):
    from test_content_conditional_attributes import complete_item
    data=complete_item()
    get=requester([dict(id=123),data,dict(plain_text='Texto')]);get.side_effect=list(get.side_effect)+[Mock(status_code=429)]
    result=inspect('x',123,'MLB123',get,NOW,include_specs=True)
    self.assertEqual(get.call_count,4);self.assertEqual(result['technical_specs']['state'],'unknown')
    get=requester([dict(id=123),data,dict(plain_text='Texto'),rules()])
    post=Mock(return_value=Mock(status_code=429))
    result=inspect('x',123,'MLB123',get,NOW,request_post=post,include_specs=True)
    self.assertEqual(get.call_count,4);self.assertEqual(post.call_count,1);self.assertIn('Limite de consultas',result['technical_specs']['message'])
