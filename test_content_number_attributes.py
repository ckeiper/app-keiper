import unittest
from copy import deepcopy
from content_number_attributes import check,compare,render


def rule(**patch):return dict(dict(id='COUNT',name='Quantidade de programas',value_type='number',tags={},values=[dict(id='1',name='1')]),**patch)
def item(**patch):return dict(dict(attributes=[dict(id='COUNT',value_name='5')],variations=[]),**patch)

class NumberAttributeTests(unittest.TestCase):
    def test_simple_numbers_no_ranges_suggestion_restrictions_or_conversion(self):
        for value in ['0','-10','+5','1.23','1,23','1,234','1.234',' 7 ','9999999999999999999999999999']:
            self.assertEqual(check(rule(),dict(value_name=value))[0],'matched',value)
        definitions=[rule()];listing=item();before=deepcopy((definitions,listing));r=compare(definitions,listing)
        self.assertEqual(r['rows'][0]['state'],'matched');self.assertEqual((definitions,listing),before)
        self.assertNotIn('value_name',str(r))

    def test_missing_or_id_only_is_unknown_not_numeric_quantity(self):
        for row in [{},dict(value_id='5'),dict(value_id=False,value_name='5'),dict(value_name=''),dict(value_name=True),dict(value_name=5),dict(value_id='-1',value_name='4'),dict(value_name='9'*10001),dict(value_name='4',value_struct=dict(number=4))]:
            self.assertEqual(check(rule(),row)[0],'unknown')

    def test_unsupported_formats_only_prompt_review(self):
        for value in ['dez','10 unidades','1/2','1e3','1 000','1.234,56','NaN','Infinity','１２','<script>x</script>']:
            state,message=check(rule(),dict(value_name=value));self.assertEqual(state,'review');self.assertIn('não confirma erro',message)

    def test_single_consistent_representation_and_compounds(self):
        self.assertEqual(check(rule(),dict(value_name='4',values=[dict(id=None,name='4',struct=None)]))[0],'matched')
        for extra in ({},False,[dict(id=False,name='4')],[dict(name='5')],[dict(name='4'),dict(name='4')],[dict(id='9',name='4')],[dict(name='4',struct=dict(number=4))]):
            self.assertEqual(check(rule(),dict(value_name='4',values=extra))[0],'unknown')

    def test_variations_no_inheritance_ambiguous_sets_discarded(self):
        listing=item(variations=[dict(id=1,attributes=[dict(id='COUNT',value_name='2')],attribute_combinations=[]),dict(id=2,attributes=[],attribute_combinations=[dict(id='COUNT',value_name='dois')])])
        r=compare([rule()],listing);self.assertEqual([x['state'] for x in r['rows']],['matched','matched','review']);self.assertIn('Variação 2',r['rows'][-1]['location'])
        for variants in (None,[None],[dict(id=True)],[dict(id=1),dict(id='1')]):
            r=compare([rule()],item(variations=variants));self.assertTrue(r['variation_unknown']);self.assertEqual(len(r['rows']),1)

    def test_only_number_types_and_managed_attributes(self):
        for kind in ['string','list','boolean','number_unit',None]:self.assertEqual(compare([rule(value_type=kind)],item())['rows'],[])
        self.assertEqual(compare(None,item())['state'],'unknown')
        self.assertEqual(compare([rule(),rule()],item())['state'],'unknown')
        self.assertEqual(compare([rule()],item(attributes=None))['rows'][0]['state'],'unknown')
        r=compare([rule(tags={'inferred':True})],item());self.assertIn('sem recomendar edição direta',render(r))

    def test_limits_escape_and_unknown_render(self):
        r=compare([rule(id=str(i),name='<img onerror=x>') for i in range(101)],item(attributes=[dict(id=str(i),value_name='dois') for i in range(101)]))
        self.assertEqual(len(r['rows']),100);self.assertTrue(r['truncated']);self.assertNotIn('<img',render(r));self.assertIn('100 resultados',render(r))
        self.assertIn('não verificados',render(dict(state='unknown')))
        many=item(attributes=[dict(id=str(i)) for i in range(2000)],variations=[dict(id=i,attributes=[dict(id=str(j)) for j in range(2000)],attribute_combinations=[]) for i in range(2)])
        self.assertTrue(compare([rule()],many)['truncated'])
        self.assertTrue(compare([rule()],item(variations=[dict(id=i) for i in range(1001)]))['variation_unknown'])

    def test_existing_pipeline_reuses_four_gets_and_emits_action(self):
        from listing_content_snapshot import inspect
        from content_action_summary import actions
        from test_listing_content_snapshot import item as ci,requester,NOW
        listing=ci();listing.update(category_id='MLB200',attributes=[dict(id='COUNT',value_name='dez')])
        get=requester([dict(id=123),listing,{},[rule()]])
        r=inspect('x',123,'MLB123',get,NOW);self.assertEqual(get.call_count,4)
        self.assertEqual(r['number_values']['rows'][0]['state'],'review')
        self.assertTrue(any(x[0]=='review' and 'Quantidade' in x[1] for x in actions(r)))
