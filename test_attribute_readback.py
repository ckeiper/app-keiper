"""Read-back evidence and UI, using isolated fixtures only."""
from copy import deepcopy
import unittest
from unittest.mock import Mock
from attribute_readback import value,observed,render
from attribute_edit_workflow import verification,confirmed,apply
from test_attribute_completion import facts,analyze,listing,definition,reader,response


class ReadbackTests(unittest.TestCase):
    def data(self,**kwargs):return analyze(facts(**kwargs))
    def test_returns_actual_name_and_id_while_preserving_confirmation(self):
        data=self.data(definitions=[definition(value_type='list',values=[dict(id='1',name='Aço')])])
        original=deepcopy(data);item=listing(attributes=[dict(id='MATERIAL',value_id='1',value_name='Aço inoxidável')])
        result=verification(data,['MATERIAL'],item)
        self.assertTrue(confirmed(result));self.assertEqual(data,original)
        row=result['fields'][0];self.assertEqual(row['selected'],'Aço');self.assertEqual(row['observed']['text'],'Aço inoxidável');self.assertEqual(row['observed']['value_id'],'1')
    def test_mismatch_records_returned_value_without_confirming_or_retrying(self):
        plan=dict(state='ready',created_at=100,data=self.data());get=reader();get.side_effect=list(get.side_effect)+[response(dict(id=123)),response(listing(attributes=[dict(id='MATERIAL',value_name='Plástico')]))]
        persist=Mock();put=Mock(return_value=response({}))
        apply(plan,['MATERIAL'],'private',123,'MLB123',get,put,persist,now=101)
        self.assertEqual(get.call_count,7);self.assertEqual(put.call_count,1)
        self.assertEqual(persist.call_args.args[0],'uncertain');self.assertEqual(persist.call_args.args[1]['fields'][0]['observed']['text'],'Plástico')
    def test_missing_empty_na_and_malformed_are_distinct(self):
        data=self.data()
        for attrs,state in [([], 'missing'),([dict(id='MATERIAL')],'empty'),([dict(id='MATERIAL',value_id='-1')],'not_applicable'),(None,'unknown'),([dict(id='MATERIAL'),dict(id='MATERIAL')],'unknown')]:
            with self.subTest(state=state):
                r=verification(data,['MATERIAL'],listing(attributes=attrs));self.assertFalse(confirmed(r));self.assertEqual(r['fields'][0]['observed']['state'],state)
    def test_single_nested_value_struct_and_zero_not_lost(self):
        self.assertEqual(value(dict(values=[dict(id='0',name='Não')]))['value_id'],'0')
        self.assertEqual(value(dict(value_struct=dict(number=0,unit='cm')))['text'],'0 cm')
        self.assertEqual(value(dict(values=[dict(struct=dict(number=12.5,unit='cm'))]))['text'],'12.5 cm')
        self.assertEqual(value(dict(value_id='12'))['text'],'ID: 12')
        self.assertEqual(value(dict(value_name='12,50 cm'))['text'],'12,50 cm')
    def test_conflicting_or_multiple_values_are_not_certified(self):
        for row in [dict(value_name='Aço',values=[dict(name='Plástico')]),dict(values=[dict(name='Aço'),dict(name='Plástico')]),dict(values='bad'),dict(values={}),dict(values=0),dict(value_struct={})]:
            self.assertEqual(value(row)['state'],'unknown')
    def test_only_target_variation_is_displayed_never_common_fallback(self):
        from test_attribute_variations import variant,rule,manual
        data=analyze(facts(item=listing(variations=[variant(),variant(102)]),definitions=[rule()],description=''),[manual()],42)
        p=data['proposals'][0]
        item=listing(attributes=[dict(id='GTIN',value_name='COMMON')],variations=[dict(variant(),attributes=[dict(id='GTIN',value_name='789000001')]),dict(variant(102),attributes=[dict(id='GTIN',value_name='OTHER')])])
        self.assertEqual(observed(p,item)['text'],'789000001')
        item['variations'][0]['attributes']=[];self.assertEqual(observed(p,item)['state'],'missing')
        item['variations'].append(variant());self.assertEqual(observed(p,item)['state'],'unknown')
        item['variations']=None;self.assertEqual(observed(p,item)['state'],'unknown')
    def test_ui_escapes_all_display_values_and_handles_legacy_without_guessing(self):
        hostile='<script>window.injected=1</script>'
        html=render([dict(name=hostile,confirmed=False,before=dict(text=hostile),selected=hostile,observed=dict(text=hostile,value_id=hostile))])
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html);self.assertIn('Não confirmado',html)
        legacy=render([dict(name='Material',confirmed=True)])
        self.assertIn('Valor não registrado nesta análise',legacy);self.assertNotIn('Aço',legacy);self.assertIn('Confirmado',legacy)
    def test_display_is_bounded_and_does_not_mutate_response(self):
        row=dict(value_name='X'*2000);original=deepcopy(row)
        self.assertLessEqual(len(value(row)['text']),280);self.assertIn('[resumido]',value(row)['text']);self.assertEqual(row,original)
    def test_verification_does_not_change_existing_success_rules(self):
        data=self.data();p=data['proposals'][0]
        from attribute_completion import matches
        for row in [dict(value_name='Aço'),dict(value_name='Plástico'),dict(values=[dict(name='Aço')]),dict(value_id='-1'),dict(values=[dict(name='Aço'),dict(name='Plástico')])]:
            item=listing(attributes=[dict(id='MATERIAL',**row)])
            self.assertEqual(verification(data,['MATERIAL'],item)['fields'][0]['confirmed'],matches(p,item))
