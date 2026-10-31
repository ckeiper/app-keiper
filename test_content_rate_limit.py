"""Sequential content requests must stop at every possible HTTP 429 boundary."""
import unittest
from unittest.mock import Mock
from listing_content_snapshot import inspect,render,RATE_LIMIT_MESSAGE
from test_listing_content_snapshot import NOW
from test_content_conditional_attributes import complete_item
from test_listing_content_requirements import definitions
from test_content_technical_specs import specs,field


def response(payload):return Mock(status_code=200,json=Mock(return_value=payload))

def responses():return [dict(id=123),complete_item(),dict(plain_text='Descrição preservada'),definitions(),specs(field())]

def requester(failure=None):
    values=responses()
    return Mock(side_effect=[response(value) for value in values] if failure is None else
                [response(value) for value in values[:failure]]+[Mock(status_code=429)])


def conditional(status=200):return Mock(return_value=Mock(status_code=status,json=Mock(return_value=dict(required_attributes=[dict(id='GTIN')]))))

class ContentRateLimitTests(unittest.TestCase):
    def test_every_get_boundary_stops_without_retry_and_preserves_prior_evidence(self):
        for failure in range(5):
            for include_specs in (False,True):
                if failure==4 and not include_specs:continue
                with self.subTest(failure=failure,include_specs=include_specs):
                    get=requester(failure);post=conditional()
                    result=inspect('secret-token',123,'MLB123',get,NOW,post,include_specs)
                    self.assertEqual(get.call_count,failure+1);self.assertTrue(result['rate_limited'])
                    self.assertEqual(post.call_count,1 if failure==4 else 0)
                    self.assertEqual(result['state'],'unknown' if failure<2 else 'read')
                    self.assertNotIn('secret-token',str(result))
                    if failure>=2:
                        self.assertEqual(result['title'],complete_item()['title'])
                        self.assertEqual(result['photos'],1)
                        self.assertEqual(result['requirements']['state'],'read' if failure==4 else 'unknown')
                        if include_specs:self.assertEqual(result['technical_specs']['state'],'unknown')
                    if failure==2:
                        self.assertIsNone(result['description']);self.assertEqual(result['description_message'],RATE_LIMIT_MESSAGE)
                        for key in ('requirements','attribute_units','boolean_values','list_values','number_values'):
                            self.assertEqual(result[key],dict(state='unknown',message=RATE_LIMIT_MESSAGE))
                    if failure>=3:self.assertEqual(result['description'],'Descrição preservada')

    def test_conditional_post_429_keeps_category_but_stops_sheet(self):
        get=Mock(side_effect=[response(v) for v in responses()[:4]]);post=conditional(429)
        r=inspect('secret-token',123,'MLB123',get,NOW,post,True)
        self.assertEqual(get.call_count,4);self.assertEqual(post.call_count,1);self.assertTrue(r['rate_limited'])
        self.assertEqual(r['requirements']['state'],'read');self.assertEqual(r['requirements']['conditional']['state'],'unknown')
        self.assertTrue(all(not x.get('conditional_confirmed') for x in r['requirements']['rows'] if x['conditional']))
        self.assertEqual(r['technical_specs']['message'],RATE_LIMIT_MESSAGE)
        self.assertEqual(r['description'],'Descrição preservada')

    def test_normal_and_other_endpoint_errors_do_not_get_rate_limited_label(self):
        get=requester();r=inspect('x',123,'MLB123',get,NOW,conditional(),True)
        self.assertEqual(get.call_count,5);self.assertFalse(r['rate_limited']);self.assertEqual(r['technical_specs']['state'],'read')
        for status in (404,500):
            get=Mock(side_effect=[response(responses()[0]),response(responses()[1]),Mock(status_code=status),response(definitions()),response(specs(field()))])
            post=conditional();r=inspect('x',123,'MLB123',get,NOW,post,True)
            self.assertEqual(get.call_count,5);post.assert_not_called();self.assertFalse(r['rate_limited'])
            self.assertEqual(r['requirements']['state'],'read');self.assertEqual(r['technical_specs']['state'],'read')

    def test_partial_banner_unknown_and_normal_render_are_distinct(self):
        r=inspect('x',123,'MLB123',requester(2),NOW,conditional(),True)
        html=render(1,'MLB123','Título','csrf',r)
        self.assertIn('Consulta parcial: limite',html);self.assertIn('dados já obtidos foram preservados',html)
        self.assertIn('Descrição não verificada',html);self.assertNotIn('Descrição vazia',html)
        r=inspect('x',123,'MLB123',requester(0),NOW,conditional(),True)
        html=render(1,'MLB123','Título','csrf',r)
        self.assertIn('Sem leitura verificável',html);self.assertNotIn('class="cs-rate-limit"',html)
        r=inspect('x',123,'MLB123',requester(),NOW,conditional(),True)
        self.assertNotIn('class="cs-rate-limit"',render(1,'MLB123','Título','csrf',r))
