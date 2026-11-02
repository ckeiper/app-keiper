from copy import deepcopy
import json
import re
import unittest

from content_current_values import describe
from content_technical_specs import compare, render


def sheet(*codes):
    return dict(groups=[dict(components=[dict(attributes=[dict(id=c,name=c,tags=[]) for c in codes])])])


class CurrentValuesTests(unittest.TestCase):
    def test_simple_name_id_zero_and_na_preserve_returned_evidence(self):
        self.assertEqual(describe(dict(value_name='Azul',value_id='52028')), 'Azul · ID 52028')
        self.assertEqual(describe(dict(value_name='0',value_id=0)), '0 · ID 0')
        self.assertIn('Não aplicável declarado',describe(dict(value_id='-1')))
        self.assertIn('texto divergente',describe(dict(value_id='-1',value_name='texto divergente')))
        self.assertNotIn('Não aplicável',describe(dict(value_id=-1.0)))

    def test_structured_and_multiple_values_are_displayed_without_validation(self):
        data=dict(attributes=[dict(id='SIZE',value_struct=dict(number=0,unit='cm')),dict(id='COLORS',values=[dict(id='1',name='Azul'),dict(name='Verde',struct=dict(number=12,unit='CM'))])],variations=[])
        result=compare(sheet('SIZE','COLORS'),[],data)
        self.assertEqual([r['state'] for r in result['rows']], ['unknown','unknown'])
        self.assertIn('Estruturado: 0 cm',render(result))
        self.assertIn('Valores: Azul · ID 1; Verde · Estruturado: 12 CM',render(result))

    def test_main_and_variation_groups_stay_distinct_and_item_is_unchanged(self):
        data=dict(attributes=[dict(id='COLOR',value_name='Geral')],variations=[dict(id=9,attributes=[dict(id='COLOR',value_name='Azul')],attribute_combinations=[dict(id='COLOR',value_name='Verde')]),dict(id=10,attributes=[],attribute_combinations=[])])
        original=deepcopy(data);result=compare(sheet('COLOR'),[],data)
        details=result['current_values']['details']['COLOR']
        self.assertEqual(details['main'],'Geral')
        self.assertEqual(details['variants']['0'],['Atributo da variação: Azul','Combinação: Verde'])
        self.assertNotIn('1',details['variants'])
        self.assertEqual(data,original)
        self.assertIn('No anúncio:</b> Geral',render(result))
        self.assertEqual(result['rows'][0]['variation_states'],'ir')

    def test_invalid_groups_do_not_leak_unverified_partial_values(self):
        data=dict(attributes=[dict(id='A',value_name='one'),dict(id='A',value_name='two')],variations=[dict(id=1,attributes=[dict(id='A',value_name='private')],attribute_combinations=[]),dict(id=1,attributes=[],attribute_combinations=[])])
        result=compare(sheet('A'),[],data)
        self.assertEqual(result['current_values']['details'],{})
        self.assertEqual(result['rows'][0]['state'],'unknown')

    def test_limits_are_explicit_and_presence_checks_all_variations(self):
        codes=[str(i) for i in range(11)]
        data=dict(attributes=[],variations=[dict(id=i,attributes=[dict(id=c,value_name='x') for c in codes],attribute_combinations=[]) for i in range(101)])
        data['variations'][-1]['attributes']=[]
        result=compare(sheet(*codes),[],data)
        self.assertTrue(result['current_values']['limited'])
        count=sum(len(values) for row in result['current_values']['details'].values() for values in row.get('variants',{}).values())
        self.assertEqual(count,1000)
        self.assertNotIn('100',result['current_values']['details']['0'].get('variants',{}))
        self.assertIn('1.000 valores próprios',render(result))
        self.assertEqual(result['rows'][0]['state'],'review')
        self.assertIn('100 de 101',result['rows'][0]['message'])

    def test_long_text_and_lists_are_bounded(self):
        result=describe(dict(value_name='A'*10000,values=[dict(name='B'*10000) for _ in range(20)]))
        self.assertLess(len(result),280);self.assertIn('[resumido]',result)
        self.assertIn('3 de 4 valores',describe(dict(values=[dict(name='X')]*4)))
        self.assertNotIn('True',describe(dict(value_name=True,value_id=False)))
        self.assertNotIn('nan',describe(dict(value_struct=dict(number=float('nan'),unit='cm'))))

    def test_script_breakout_in_main_and_variations_is_only_text(self):
        value='</script><script>window.currentValueInjected=1</script>'
        data=dict(attributes=[dict(id='A',value_name=value)],variations=[dict(id=1,attributes=[dict(id='A',value_name=value)],attribute_combinations=[])])
        output=render(compare(sheet('A'),[],data))
        self.assertNotIn(value,output);self.assertIn('&lt;/script&gt;',output)
        payload=json.loads(re.search(r'<script type="application/json" class="cs-tech-data">(.*?)</script>',output).group(1))
        self.assertEqual(payload['values']['A']['main'],value)

    def test_api_only_hidden_value_is_included(self):
        result=compare(sheet(),[dict(id='H',tags=dict(hidden=True))],dict(attributes=[dict(id='H',value_name='Detalhe real retornado')],variations=[]))
        self.assertEqual(result['rows'][0]['source'],'category')
        self.assertEqual(result['current_values']['details']['H']['main'],'Detalhe real retornado')
