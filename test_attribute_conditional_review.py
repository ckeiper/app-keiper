from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock
import requests
from attribute_completion import analyze
from attribute_conditional_review import review,candidate,render
from attribute_edit_workflow import apply
from test_attribute_completion import listing,definition,facts,reader,response


def item(**kw):
    return listing(price=100,currency_id='BRL',available_quantity=2,buying_mode='buy_it_now',listing_type_id='gold_special',pictures=[],**kw)


def definitions():
    return [definition(),definition('GTIN',tags=dict(conditional_required=True))]


def source(**kw):
    return facts(item=kw.pop('item',item()),definitions=kw.pop('definitions',definitions()),description='Material: Aço\nGTIN: 12345678',**kw)


def post(ids=None,status=200):
    return Mock(return_value=response(dict(required_attributes=[dict(id=x) for x in (['GTIN'] if ids is None else ids)]),status))


class ConditionalReviewTests(TestCase):
    def test_full_candidate_preserves_unselected_common_and_variation_context(self):
        original=item(attributes=[dict(id='BRAND',value_name='Marca'),dict(id='MATERIAL',value_name=None)],variations=[dict(id=1,attributes=[],attribute_combinations=[dict(id='COLOR',value_name='Azul')],price=20,picture_ids=['P']),dict(id=2,attributes=[],attribute_combinations=[],price=25)])
        before=deepcopy(original);p=post([])
        update=dict(attributes=[dict(id='MATERIAL',value_name='Aço')],variations=[dict(id=1,attributes=[dict(id='GTIN',value_name='123')]),dict(id=2)])
        result=review(source(item=original),update,'private-token',p)
        sent=p.call_args.kwargs['json']
        self.assertEqual(sent['attributes'],[dict(id='BRAND',value_name='Marca'),dict(id='MATERIAL',value_name='Aço')])
        self.assertEqual(sent['variations'][0]['attribute_combinations'],before['variations'][0]['attribute_combinations'])
        self.assertEqual(sent['variations'][0]['price'],20);self.assertEqual(sent['variations'][0]['picture_ids'],['P'])
        self.assertEqual(sent['variations'][1],before['variations'][1]);self.assertEqual(original,before)
        self.assertTrue(result['allow_send']);self.assertFalse(p.call_args.kwargs['allow_redirects'])
        self.assertTrue(p.call_args.args[0].endswith('/categories/MLB200/attributes/conditional'))
        self.assertNotIn('private-token',str(result))

    def test_only_selected_values_affect_query_and_missing_is_not_error(self):
        p=post();f=source();before=deepcopy(f)
        result=review(f,dict(attributes=[dict(id='MATERIAL',value_name='Aço')]),'private',p)
        self.assertFalse(result['allow_send']);self.assertEqual(result['fields'][0]['state'],'review')
        self.assertNotIn('erro',result['message'].lower());self.assertNotIn('GTIN',[a['id'] for a in p.call_args.kwargs['json']['attributes']])
        self.assertEqual(f,before)
        self.assertTrue(review(f,dict(attributes=[dict(id='GTIN',value_name='12345678')]),'private',post())['allow_send'])

    def test_unknown_response_rate_limit_and_incomplete_context_never_allow(self):
        for p in [post(status=429),post(status=503),Mock(side_effect=requests.Timeout()),Mock(return_value=response({})),post(['UNEXPECTED'])]:
            self.assertFalse(review(source(),{},'private',p)['allow_send']);self.assertEqual(p.call_count,1)
        for mutate in [lambda f:f.update(description=None),lambda f:f['item'].pop('price')]:
            f=source();mutate(f);p=post();self.assertFalse(review(f,{},'private',p)['allow_send']);p.assert_not_called()
        f=source();f['rules']['GTIN']['tags']['conditional_required']='true';p=post();self.assertFalse(review(f,{},'private',p)['allow_send']);p.assert_not_called()

    def test_absence_of_conditional_marks_does_not_add_a_request(self):
        p=post();result=review(source(definitions=[definition()]),{},'private',p)
        self.assertEqual(result['state'],'not_requested');self.assertTrue(result['allow_send']);p.assert_not_called()

    def test_na_structures_and_partial_variations_remain_for_conference(self):
        for current in [dict(id='GTIN',value_id='-1'),dict(id='GTIN',value_struct=dict(number=12,unit='cm'))]:
            result=review(source(item=item(attributes=[current])),{},'private',post())
            self.assertFalse(result['allow_send']);self.assertEqual(result['fields'][0]['state'],'unknown')
        variants=[dict(id=1,attributes=[dict(id='GTIN',value_name='123')],attribute_combinations=[]),dict(id=2,attributes=[],attribute_combinations=[])]
        self.assertFalse(review(source(item=item(variations=variants)),{},'private',post())['allow_send'])
        variants[1]['attributes']=[dict(id='GTIN',value_name='456')]
        self.assertTrue(review(source(item=item(variations=variants)),{},'private',post())['allow_send'])

    def test_candidate_refuses_partial_variation_base_and_unknown_keys(self):
        original=item(variations=[dict(id=1,attributes=[],attribute_combinations=[])])
        for update in [dict(price=1),dict(variations=[]),dict(variations=[dict(id=2)]),dict(variations=[dict(id=1),dict(id=1)]),dict(variations=[dict(id=1,attribute_combinations=[])])]:
            with self.assertRaises(ValueError):candidate(original,update)

    def test_many_requirements_are_all_checked_but_details_are_bounded_and_escaped(self):
        defs=[definition('FIELD_'+str(i),tags=dict(conditional_required=True),name='</strong><script>bad()</script>') for i in range(60)]
        f=source(definitions=defs);result=review(f,{},'private',post([d['id'] for d in defs]))
        self.assertEqual(result['total'],60);self.assertEqual(result['pending'],60);self.assertEqual(len(result['fields']),50)
        html=render(result);self.assertNotIn('<script>bad',html);self.assertIn('&lt;script&gt;',html);self.assertIn('primeiros 50',html)


class ConditionalWriterTests(TestCase):
    def plan(self):
        return dict(state='ready',created_at=100,created_by=42,data=analyze(source()))

    def fresh(self,readback=False):
        r=reader(item=item(),definitions=definitions(),description='Material: Aço\nGTIN: 12345678')
        if readback:r.side_effect=list(r.side_effect)+[response(dict(id=123)),response(item(attributes=[dict(id='GTIN',value_name='12345678')]))]
        return r

    def test_blocked_conditional_never_puts_or_reads_back_and_keeps_report(self):
        for p in [post(),post(status=429),Mock(side_effect=requests.Timeout())]:
            put=Mock();get=self.fresh();persist=Mock()
            apply(self.plan(),['MATERIAL'],'private',123,'MLB123',get,put,persist,now=101,post=p)
            put.assert_not_called();self.assertEqual(get.call_count,5);self.assertEqual(p.call_count,1)
            self.assertEqual(persist.call_args.args[0],'rejected');self.assertIn('conditional',persist.call_args.args[1])

    def test_selected_field_is_queried_before_single_put_and_report_survives(self):
        events=[];p=post();p.side_effect=lambda *a,**kw:events.append('query') or response(dict(required_attributes=[dict(id='GTIN')]))
        put=Mock(side_effect=lambda *a,**kw:events.append('put') or response({}));persist=Mock()
        apply(self.plan(),['GTIN'],'private',123,'MLB123',self.fresh(True),put,persist,now=101,post=p)
        self.assertEqual(events,['query','put']);self.assertEqual(put.call_count,1)
        self.assertEqual(put.call_args.kwargs['json'],dict(attributes=[dict(id='GTIN',value_name='12345678')]))
        self.assertEqual(persist.call_args.args[0],'confirmed');self.assertEqual(persist.call_args.args[1]['conditional']['state'],'read')
        self.assertEqual(persist.call_args_list[-2].args[0],'sending')

    def test_persisting_query_evidence_failure_stops_the_write(self):
        put=Mock();persist=Mock(side_effect=[None,RuntimeError('storage')])
        with self.assertRaises(RuntimeError):apply(self.plan(),['GTIN'],'private',123,'MLB123',self.fresh(),put,persist,now=101,post=post())
        put.assert_not_called()

class ConditionalBudgetTests(TestCase):
    def test_get_and_post_share_remaining_query_budget(self):
        from unittest.mock import patch
        from attribute_editor import budgeted
        from listing_content_snapshot import ContentUnavailable
        get=Mock();p=Mock()
        with patch('attribute_editor.time.monotonic',return_value=16):
            budgeted(get,20)('https://api.mercadolibre.com/users/me')
        self.assertEqual(get.call_args.kwargs['timeout'],(3,4))
        with patch('attribute_editor.time.monotonic',return_value=19.5):
            with self.assertRaises(ContentUnavailable):budgeted(p,20)('https://api.mercadolibre.com/categories/MLB200/attributes/conditional')
        p.assert_not_called()
