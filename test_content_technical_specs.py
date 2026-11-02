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
    self.assertEqual(compare(specs(),[],item())['total'],0)
 def test_not_applicable_and_bad_variations_never_assume_errors(self):
    data=item();data.update(attributes=[dict(id='BRAND',value_id='-1')],variations=[])
    self.assertEqual(compare(specs(field()),rules(),data)['rows'][0]['state'],'unknown')
    data.update(attributes=[],variations=[dict(id=1,attributes=[dict(id='BRAND',value_name='X')],attribute_combinations=[]),dict(id=2,attributes=[],attribute_combinations=[])])
    result=compare(specs(field()),rules(),data)
    self.assertEqual(result['rows'][0]['state'],'review');self.assertEqual(len(result['rows'][0]['variation_states']),2)
    data['variations'][1]['id']=1
    self.assertEqual(compare(specs(field()),rules(),data)['rows'][0]['state'],'unknown')
 def test_managed_field_flag_escape_and_bounded_output(self):
    data=item();data.update(attributes=[],variations=[],tags=['incomplete_technical_specs'])
    result=compare(specs(field(name='<script>',tags=['required','read_only'])),rules(),data)
    text=render(result);self.assertEqual(text.count('<script>'),1);self.assertIn('<h5>&lt;script&gt;</h5>',text);self.assertIn('Campo gerenciado',text);self.assertNotIn('Confira o preenchimento',text);self.assertIn('retornou o sinal',text)
    result=compare(specs(*[field(str(i)) for i in range(110)]),[],data)
    self.assertEqual(len(result['rows']),110);self.assertEqual(result['total'],110);self.assertIn('1–50 de 110',render(result));self.assertEqual(render(result).count('class="cs-tech-row"'),50)
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

 def test_complementary_fields_are_included_without_inventing_requirement(self):
    data=item();data.update(attributes=[dict(id='EXTRA',value_name='Informado')],variations=[])
    result=compare(specs(field(),field('EXTRA',tags=[]),field('OPTIONAL',tags=[])),rules(),data)
    self.assertEqual(result['total'],5);self.assertEqual([r['required'] for r in result['rows']],[True,False,False,False,False])
    text=render(result);self.assertIn('Avaliar oportunidade de preenchimento',text);self.assertIn('2 complementares',text)
    self.assertIn('Complementar nesta ficha · sem exigência confirmada',text)
    self.assertEqual([r['state'] for r in result['rows']],['review','informed','review','review','review'])
 def test_variations_after_display_limit_still_affect_summary(self):
    data=item();data.update(attributes=[],variations=[dict(id=i,attributes=[dict(id='BRAND',value_name='X')] if i<100 else [],attribute_combinations=[]) for i in range(101)])
    result=compare(specs(field()),rules(),data)
    self.assertEqual(result['rows'][0]['state'],'review');self.assertIn('100 de 101',result['rows'][0]['message'])
    self.assertEqual(len(result['rows'][0]['variation_states']),100);self.assertIn('Exibidas 100 de 101',render(result))
 def test_presence_index_matches_existing_reader(self):
    from content_required_attributes import presence,variation_details
    from content_technical_specs import PresenceIndex
    from itertools import product
    choices=[[],None,[dict(id='BRAND',value_name='X')],[dict(id='BRAND',value_id='-1')],[dict(id='BRAND',value_struct=dict(number=12,unit='cm'))],[dict(id='BRAND',values=[dict(name='X')])]]
    for main,left,right in product(choices,repeat=3):
        data=dict(attributes=main,variations=[dict(id=1,attributes=left,attribute_combinations=right)])
        result=PresenceIndex(data).evidence('BRAND');self.assertEqual(result[:2],presence('BRAND',data))
        expected=variation_details('BRAND',data);self.assertEqual(result[2],''.join(dict(informed='i',review='r',unknown='u')[v['state']] for v in expected))
 def test_index_parses_groups_once_for_many_fields(self):
    from unittest.mock import patch
    from content_technical_specs import attributes as parse_attributes
    data=item();data.update(attributes=[],variations=[dict(id=i,attributes=[],attribute_combinations=[]) for i in range(10)])
    with patch('content_technical_specs.attributes',wraps=parse_attributes) as parsed:
        result=compare(specs(*[field(str(i),tags=[]) for i in range(110)]),[],data)
    self.assertEqual(result['total'],110);self.assertEqual(parsed.call_count,22)
 def test_script_breakout_is_encoded_in_json_and_html(self):
    import json,re
    data=item();data.update(attributes=[],variations=[])
    name='</script><script>window.injected=1</script>'
    text=render(compare(specs(field(name=name)),rules(),data))
    self.assertNotIn(name,text);self.assertIn('&lt;/script&gt;',text)
    payload=re.search(r'<script type="application/json" class="cs-tech-data">(.*?)</script>',text).group(1)
    self.assertEqual(json.loads(payload)['rows'][0]['name'],name)

 def test_structured_only_value_is_not_reported_as_missing(self):
    data=item();data.update(attributes=[dict(id='EXTRA',value_struct=dict(number=12,unit='cm'))],variations=[])
    result=compare(specs(field('EXTRA',tags=[])),[],data)
    self.assertEqual(result['rows'][0]['state'],'unknown');self.assertNotIn('Sem valor identificado',result['rows'][0]['message'])
    data.update(attributes=[],variations=[dict(id=1,attributes=[dict(id='EXTRA',value_struct=dict(number=12,unit='cm'))],attribute_combinations=[])])
    row=compare(specs(field('EXTRA',tags=[])),[],data)['rows'][0]
    self.assertEqual(row['state'],'unknown');self.assertEqual(row['variation_states'],'u')


class CombinedInventoryTests(unittest.TestCase):
 def test_api_only_fields_are_included_and_duplicates_keep_sheet_identity(self):
    data=dict(attributes=[],variations=[])
    definitions=[dict(id='BRAND',name='Marca API',tags=dict(required=True)),dict(id='HIDDEN',name='Detalhe',tags=dict(hidden=True))]
    original=deepcopy(definitions)
    result=compare(specs(field(name='Marca da ficha')),definitions,data)
    self.assertEqual(result['total'],2)
    brand,extra=result['rows']
    self.assertEqual((brand['name'],brand['source'],brand['publication']),('Marca da ficha','both','publication'))
    self.assertEqual((extra['source'],extra['required'],extra['hidden_tags']),('category',False,['hidden']))
    self.assertEqual(definitions,original)
    self.assertIn('1 somente na API',render(result))
    self.assertIn('1 ocultos',render(result))
    self.assertIn('0 complementares na ficha',render(result))
 def test_hidden_context_tags_keep_their_official_meaning(self):
    definitions=[dict(id='A',tags=dict(new_hidden=True,used_hidden=True)),dict(id='B',tags=dict(hidden=False)),dict(id='C',tags=dict(hidden='true'))]
    result=compare(specs(field('A',tags=['hidden'])),definitions,dict(attributes=[],variations=[]))
    self.assertEqual([r['hidden_tags'] for r in result['rows']],[['hidden','new_hidden','used_hidden'],[],[]])
    text=render(result)
    self.assertIn('Oculto para novos',text);self.assertIn('Oculto para usados',text)
    self.assertIn('Oculto na API',text)
 def test_api_only_required_and_conditional_are_not_sheet_requirements(self):
    definitions=[dict(id='A',tags=dict(required=True)),dict(id='B',tags=dict(conditional_required=True))]
    result=compare(specs(),definitions,dict(attributes=[],variations=[]),dict(state='read',required_ids=['B']))
    self.assertEqual([r['publication'] for r in result['rows']],['publication','conditional'])
    self.assertFalse(any(r['required'] for r in result['rows']))
    text=render(result)
    self.assertIn('0 complementares na ficha',text)
    self.assertIn('Obrigatório na consulta condicional',text)
 def test_hidden_managed_and_internal_fields_do_not_request_direct_edit(self):
    for tag in ('read_only','fixed','inferred','others'):
        result=compare(specs(),[dict(id='A',tags={tag:True,'hidden':True})],dict(attributes=[],variations=[]))
        self.assertTrue(result['rows'][0]['managed'])
        self.assertIn('Campo gerenciado pelo Mercado Livre',render(result))
        self.assertNotIn('Avaliar oportunidade de preenchimento',render(result))
 def test_api_only_variation_presence_and_na_are_not_confirmed_errors(self):
    result=compare(specs(),[dict(id='A',tags=dict(hidden=True))],dict(attributes=[],variations=[dict(id=1,attributes=[dict(id='A',value_name='X')],attribute_combinations=[]),dict(id=2,attributes=[dict(id='A',value_id='-1')],attribute_combinations=[])]))
    row=result['rows'][0]
    self.assertEqual((row['state'],row['variation_states']),('unknown','iu'))
    self.assertNotIn('erro',row['message'])
 def test_invalid_category_does_not_add_unverified_fields_and_union_is_bounded(self):
    result=compare(specs(field('A')), [dict(id='B'),dict(id='B')],dict(attributes=[],variations=[]))
    self.assertEqual(result['total'],1);self.assertEqual(result['rows'][0]['publication'],'unknown')
    payload=specs(*[field(str(i),tags=[]) for i in range(5000)])
    self.assertEqual(compare(payload,[dict(id='EXTRA')],dict(attributes=[],variations=[]))['state'],'unknown')
