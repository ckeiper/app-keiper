import unittest
from copy import deepcopy
from content_list_attributes import check,compare,render


def rule(**patch):
    return dict(dict(id='COLOR',name='Cor',value_type='list',tags={},values=[dict(id='1',name='Azul'),dict(id='2',name='Vermelho')]),**patch)


def item(**patch):
    return dict(dict(attributes=[dict(id='COLOR',value_id='1',value_name='Nome personalizado')],variations=[]),**patch)

class ListAttributeTests(unittest.TestCase):
    def test_ids_match_without_rejecting_custom_text_or_mutating(self):
        definitions=[rule()];listing=item();before=deepcopy((definitions,listing))
        r=compare(definitions,listing);self.assertEqual(r['rows'][0]['state'],'matched');self.assertEqual((definitions,listing),before)
        self.assertNotIn('Nome personalizado',str(r));self.assertEqual(check(rule(),dict(value_id=1))[0],'matched')
        self.assertEqual(check(rule(),dict(value_id='1',values=[dict(id='1',name='Outro texto')]))[0],'matched')

    def test_missing_not_applicable_malformed_and_compound_not_errors(self):
        for row in ({},dict(value_name='Azul'),dict(value_id=True),dict(value_id='-1'),dict(value_id='1',values=[dict(id='2')]),dict(value_id='1',values=[dict(id='1'),dict(id='2')]),dict(value_id='1',values={}),dict(value_id='1',values='bad')):
            self.assertEqual(check(rule(),row)[0],'unknown',row)

    def test_unlisted_id_is_only_opportunity_never_confirmed_error(self):
        state,message=check(rule(),dict(value_id='9'));self.assertEqual(state,'review');self.assertIn('não confirma erro',message)

    def test_invalid_category_option_lists_not_certified(self):
        for values in (None,[],[{}],[dict(id=True)],[dict(id='1'),dict(id='1')],[dict(id='-1')],[dict(id=str(i)) for i in range(2001)]):
            self.assertEqual(check(rule(values=values),dict(value_id='1'))[0],'unknown')
        self.assertEqual(compare(None,item())['state'],'unknown')
        self.assertEqual(compare([rule(),rule()],item())['state'],'unknown')

    def test_each_variation_is_checked_without_inheritance(self):
        listing=item(variations=[dict(id=10,attributes=[dict(id='COLOR',value_id='2')],attribute_combinations=[]),dict(id=11,attributes=[],attribute_combinations=[dict(id='COLOR',value_id='9')])])
        r=compare([rule()],listing);self.assertEqual([v['state'] for v in r['rows']],['matched','matched','review'])
        self.assertIn('Variação 11',r['rows'][2]['location'])
        listing['variations'][1]['attribute_combinations']=[dict(id='COLOR',value_name='Azul')]
        self.assertEqual(compare([rule()],listing)['rows'][-1]['state'],'unknown')

    def test_invalid_variations_discard_all_variation_conclusions(self):
        for variants in (None,[None],[dict(id=True)],[dict(id=10),dict(id='10')],[dict(id=i) for i in range(1001)]):
            r=compare([rule()],item(variations=variants));self.assertTrue(r['variation_unknown']);self.assertEqual(len(r['rows']),1)

    def test_only_list_types_managed_and_invalid_groups(self):
        for kind in ('boolean','string','number','number_unit',None):
            self.assertEqual(compare([rule(value_type=kind)],item())['rows'],[])
        r=compare([rule(tags={'fixed':True})],item());self.assertTrue(r['rows'][0]['managed']);self.assertIn('sem recomendar edição direta',render(r))
        self.assertEqual(compare([rule()],item(attributes=None))['rows'][0]['state'],'unknown')
        self.assertEqual(compare([rule()],item(attributes=[dict(id='COLOR'),dict(id='COLOR')]))['rows'][0]['state'],'unknown')

    def test_existing_content_read_reuses_requests_and_summarizes_list_findings(self):
        from listing_content_snapshot import inspect
        from content_action_summary import actions
        from test_listing_content_snapshot import requester,item as content_item,NOW
        listing=content_item();listing.update(category_id='MLB200',attributes=[dict(id='COLOR',value_id='9')])
        get=requester([dict(id=123),listing,{},[rule()]])
        result=inspect('x',123,'MLB123',get,NOW)
        self.assertEqual(get.call_count,4)
        self.assertEqual(result['list_values']['rows'][0]['state'],'review')
        self.assertTrue(any(row[0]=='review' and row[1]=='Cor · Anúncio principal' for row in actions(result)))
        self.assertIn('/categories/MLB200/attributes',get.call_args.args[0])

    def test_limits_and_escaping(self):
        definitions=[rule(id=str(i),name='<script>x</script>') for i in range(101)]
        listing=item(attributes=[dict(id=str(i),value_id='<img onerror=x>') for i in range(101)])
        r=compare(definitions,listing);self.assertTrue(r['truncated']);self.assertEqual(len(r['rows']),100)
        html=render(r);self.assertNotIn('<script>',html);self.assertNotIn('<img',html);self.assertIn('100 resultados',html)
        definitions=[rule(id='COLOR')];listing=item(attributes=[dict(id=str(i)) for i in range(2000)],variations=[dict(id=i,attributes=[dict(id=str(j)) for j in range(2000)],attribute_combinations=[]) for i in range(2)])
        self.assertTrue(compare(definitions,listing)['truncated'])

if __name__=='__main__':unittest.main()
