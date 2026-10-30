import unittest
from copy import deepcopy
from unittest.mock import Mock
import requests
from content_conditional_attributes import evaluate
from listing_content_snapshot import inspect, render
from test_listing_content_snapshot import item, requester
from test_listing_content_requirements import definitions


def complete_item():
    value = item()
    value.update(category_id='MLB200', price=100, currency_id='BRL', available_quantity=1,
                 buying_mode='buy_it_now', condition='new', listing_type_id='gold_special')
    return value


class ConditionalTests(unittest.TestCase):
    def test_official_result_uses_verified_item_without_mutating_it(self):
        value=complete_item(); before=deepcopy(value)
        post=Mock(return_value=Mock(status_code=200,json=Mock(return_value={'required_attributes':[{'id':'GTIN'}]})))
        result=inspect('secret',123,'MLB123',requester([{'id':123},value,{'plain_text':'Descrição'},definitions()]),request_post=post)
        row=result['requirements']['rows'][2]
        self.assertTrue(row['conditional_confirmed'])
        self.assertIn('Obrigatório na consulta condicional',render(1,'MLB123','Título','csrf',result))
        self.assertEqual(value,before); self.assertNotIn('secret',str(result))
        self.assertEqual(post.call_args.args[0],'https://api.mercadolibre.com/categories/MLB200/attributes/conditional')
        self.assertFalse(post.call_args.kwargs['allow_redirects']); self.assertEqual(post.call_args.kwargs['timeout'],(3,8))

    def test_incomplete_item_never_calls_endpoint(self):
        post=Mock(); value=complete_item(); del value['condition']
        self.assertEqual(evaluate('x','MLB200',value,'texto',post)['state'],'unknown')
        post.assert_not_called()

    def test_errors_and_malformed_results_are_unknown(self):
        for response in (Mock(status_code=429), Mock(status_code=500),
                Mock(status_code=200,json=Mock(return_value={})),
                Mock(status_code=200,json=Mock(return_value={'required_attributes':[{'id':'X'},{'id':'X'}]})),
                requests.Timeout('secret')):
            post=Mock(side_effect=response) if isinstance(response,Exception) else Mock(return_value=response)
            result=evaluate('secret','MLB200',complete_item(),'texto',post)
            self.assertEqual(result['state'],'unknown'); self.assertNotIn('secret',str(result))

    def test_empty_result_does_not_assert_validity(self):
        post=Mock(return_value=Mock(status_code=200,json=Mock(return_value={'required_attributes':[]})))
        result=inspect('x',123,'MLB123',requester([{'id':123},complete_item(),{'plain_text':'Texto'},definitions()]),request_post=post)
        self.assertFalse(result['requirements']['rows'][2]['conditional_confirmed'])
        self.assertIn('confira se os dados estão completos',render(1,'MLB123','Título','csrf',result))
