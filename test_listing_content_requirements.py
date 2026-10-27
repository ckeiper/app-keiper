import unittest
from copy import deepcopy
from unittest.mock import Mock
import requests
from content_required_attributes import compare,render
from listing_content_snapshot import inspect
from test_listing_content_snapshot import item,requester,NOW


def definitions():
    return [dict(id='BRAND',name='Marca',tags=dict(required=True)),
            dict(id='MODEL',name='Modelo',tags=dict(required=True)),
            dict(id='GTIN',name='Código universal',tags=dict(conditional_required=True)),
            dict(id='OTHER',tags={})]


def variant(identifier,**changes):
    return dict(id=identifier,attributes=[],attribute_combinations=[],**changes)


class RequiredAttributesTests(unittest.TestCase):
    def test_common_values_missing_and_conditional_are_distinct_without_mutation(self):
        value=item(); payload=definitions(); before=deepcopy((value,payload))
        result=compare(payload,value)
        self.assertEqual(result['total'],3); self.assertEqual(result['rows'][0]['state'],'informed')
        self.assertEqual(result['rows'][1]['state'],'review'); self.assertTrue(result['rows'][2]['conditional'])
        html=render(result); self.assertIn('aplicabilidade não avaliada',html)
        self.assertEqual((value,payload),before)

    def test_malformed_category_is_unknown_not_no_requirements(self):
        cases=[None,{},[None],[{}],definitions()+[dict(id='BRAND',tags={})],
               [dict(id='BRAND')],[dict(id='BRAND',tags=[])],
               [dict(id='BRAND',tags=dict(required='true'))],
               [dict(id='BRAND',tags=dict(conditional_required=1))]]
        for payload in cases:
            result=compare(payload,item()); self.assertEqual(result['state'],'unknown',payload)
            self.assertNotIn('Nenhum atributo marcado',render(result))
        self.assertEqual(compare([],item())['total'],0)
        self.assertIn('não comprova que a ficha está completa',render(compare([],item())))

    def test_absent_malformed_and_duplicate_item_attributes_remain_unknown(self):
        for rows in (None,{},[None],[{}],[dict(id='BRAND'),dict(id='BRAND')]):
            value=item();value['attributes']=rows
            self.assertEqual(compare(definitions(),value)['rows'][0]['state'],'unknown')

    def test_not_applicable_and_complex_values_are_not_certified_as_filled(self):
        for attr in (dict(id='BRAND',value_id='-1',value_name='Não se aplica'),
                     dict(id='BRAND',values=[dict(name='Marca')])):
            value=item();value['attributes']=[attr]
            self.assertEqual(compare(definitions(),value)['rows'][0]['state'],'unknown')
        value=item();value['attributes']=[dict(id='BRAND',value_id='123')]
        self.assertEqual(compare(definitions(),value)['rows'][0]['state'],'informed')

    def test_each_variation_is_counted_across_both_attribute_groups(self):
        value=item();value['attributes']=[]
        a=variant(1);a['attributes']=[dict(id='BRAND',value_name='Marca A')]
        b=variant(2);b['attribute_combinations']=[dict(id='BRAND',value_id='123')]
        value['variations']=[a,b]
        result=compare(definitions(),value)['rows'][0]
        self.assertEqual(result['state'],'informed');self.assertIn('2 de 2',result['message'])
        b['attribute_combinations']=[]
        result=compare(definitions(),value)['rows'][0]
        self.assertEqual(result['state'],'review');self.assertIn('1 de 2',result['message'])
        b.pop('attributes')
        self.assertEqual(compare(definitions(),value)['rows'][0]['state'],'unknown')

    def test_variation_details_remain_visible_when_main_attribute_is_filled(self):
        value=item();a=variant('1');b=variant('<2>');b['attributes']=[dict(id='BRAND',value_name='Marca')]
        value['variations']=[a,b]
        result=compare(definitions(),value)
        self.assertEqual(result['rows'][0]['state'],'informed')
        self.assertEqual([v['state'] for v in result['rows'][0]['variations']],['review','informed'])
        html=render(result)
        self.assertIn('Variação 1: Sem valor identificado',html)
        self.assertIn('Variação &lt;2&gt;: Valor informado',html)
        self.assertIn('não comprova erro',html)
        b.pop('attributes')
        self.assertEqual(compare(definitions(),value)['rows'][0]['variations'][1]['state'],'unknown')
        value['variations']=[a,a]
        self.assertIsNone(compare(definitions(),value)['rows'][0]['variations'])

    def test_incomplete_invalid_or_repeated_variations_do_not_prove_presence(self):
        for variants in (None,{},[None],[{}],[variant(1),variant(1)],[variant(True)]):
            value=item();value['attributes']=[];value['variations']=variants
            self.assertEqual(compare(definitions(),value)['rows'][0]['state'],'unknown',variants)

    def test_display_is_bounded_and_remote_names_are_escaped(self):
        payload=[dict(id=str(i),name='<script>nome</script>',tags=dict(required=True)) for i in range(120)]
        result=compare(payload,item());html=render(dict(result,category='<script>'))
        self.assertEqual(len(result['rows']),100);self.assertEqual(result['total'],120)
        self.assertIn('100 de 120',html);self.assertNotIn('<script>',html)

    def test_fourth_get_uses_only_the_verified_category(self):
        value=item();value['category_id']='MLB200';payload=[dict(id=123),value,dict(plain_text='Texto'),definitions()]
        before=deepcopy(payload);get=requester(payload)
        result=inspect('secret-token',123,'MLB123',get,NOW)
        self.assertEqual(get.call_count,4);self.assertEqual(result['requirements']['state'],'read')
        self.assertEqual(result['requirements']['category'],'MLB200')
        self.assertEqual(get.call_args.args[0],'https://api.mercadolibre.com/categories/MLB200/attributes')
        self.assertFalse(get.call_args.kwargs['allow_redirects']);self.assertEqual(get.call_args.kwargs['timeout'],(3,8))
        self.assertEqual(payload,before);self.assertNotIn('secret-token',str(result))

    def test_invalid_category_never_calls_category_api(self):
        for category in (None,False,'../users/me','MLA123','MLB1/attributes'):
            value=item();value['category_id']=category;get=requester([dict(id=123),value,dict(plain_text='Texto')])
            result=inspect('x',123,'MLB123',get)
            self.assertEqual(get.call_count,3);self.assertEqual(result['requirements']['state'],'unknown')

    def test_category_network_http_and_shape_errors_preserve_verified_content(self):
        for final in (requests.Timeout('secret-token'),Mock(status_code=429),Mock(status_code=404),
                      Mock(status_code=301),Mock(status_code=200,json=Mock(return_value={})),
                      Mock(status_code=200,json=Mock(side_effect=ValueError('secret-token')))):
            value=item();value['category_id']='MLB200'
            get=Mock(side_effect=[Mock(status_code=200,json=Mock(return_value=dict(id=123))),
                Mock(status_code=200,json=Mock(return_value=value)),
                Mock(status_code=200,json=Mock(return_value=dict(plain_text='Texto'))),final])
            result=inspect('secret-token',123,'MLB123',get)
            self.assertEqual(result['state'],'read');self.assertEqual(result['description'],'Texto')
            self.assertEqual(result['requirements']['state'],'unknown');self.assertEqual(get.call_count,4)
            self.assertNotIn('secret-token',str(result))

    def test_description_failure_does_not_block_the_category_check(self):
        value=item();value['category_id']='MLB200'
        get=Mock(side_effect=[Mock(status_code=200,json=Mock(return_value=dict(id=123))),
            Mock(status_code=200,json=Mock(return_value=value)),Mock(status_code=500),
            Mock(status_code=200,json=Mock(return_value=definitions()))])
        result=inspect('x',123,'MLB123',get)
        self.assertIsNone(result['description']);self.assertEqual(result['requirements']['state'],'read')
