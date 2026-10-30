import unittest
from copy import deepcopy
from listing_sku_evidence import snapshot, code_from_attributes


def attr(value='ABC', **kw):
    return dict(dict(id='SELLER_SKU', value_name=value), **kw)


def item(**kw):
    return dict(dict(id='MLB123', site_id='MLB', seller_id=7, attributes=[], variations=[]), **kw)


class SkuEvidenceTests(unittest.TestCase):
    def test_official_main_and_variation_do_not_inherit_or_use_custom_field(self):
        data = item(attributes=[attr(' A b ')], seller_custom_field='INTERNAL', variations=[
            dict(id=1, attributes=[attr('X')], seller_custom_field='OTHER'),
            dict(id=2, attributes=[]), dict(id=3, attributes=[attr('ABC')])])
        before = deepcopy(data)
        result = snapshot(data, 7, 'MLB123', 100)
        self.assertEqual(result['state'], 'read')
        self.assertEqual(result['entries'], [dict(code='A b', variation='principal'), dict(code='X', variation='1'), dict(code='ABC', variation='3')])
        self.assertEqual(data, before)

    def test_ambiguous_variations_discard_entire_variation_set(self):
        for variants in ([dict(id=1, attributes=[attr()]), dict(id='1', attributes=[attr()])], [None], [dict(id=True)], [dict(id=0)], None, [dict(id=i+1) for i in range(1001)]):
            result = snapshot(item(attributes=[attr()], variations=variants), 7, 'MLB123', 100)
            self.assertEqual(result['state'], 'partial')
            self.assertEqual(result['entries'], [dict(code='ABC', variation='principal')])

    def test_unknown_not_absent_and_known_subset_is_preserved(self):
        result = snapshot(item(attributes=None, variations=[dict(id=1, attributes=[attr()]), dict(id=2)]), 7, 'MLB123', 100)
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(result['entries'], [dict(code='ABC', variation='1')])
        self.assertEqual(snapshot(item(), 7, 'MLB123', 100)['entries'], [])

    def test_malformed_duplicate_and_compound_values_never_become_skus(self):
        for attrs in ([attr(), attr()], [None], None, [attr(True)], [attr('x'*201)], [attr('A\x00')], [attr(values=[dict(name='B')])]):
            self.assertEqual(code_from_attributes(attrs), (None, False))
        self.assertEqual(code_from_attributes([attr(values=[dict(name='ABC')])]), ('ABC', True))
        self.assertEqual(code_from_attributes([attr(' \t\n')]), (None, True))
        self.assertEqual(code_from_attributes([attr(None, values=[dict(name='ABC')])]), (None, False))

    def test_wrong_owner_item_or_site_never_leaks_evidence(self):
        for data in (item(seller_id=8), item(id='MLB999'), item(site_id='MLA'), item(seller_id=True)):
            self.assertEqual(snapshot(data, 7, 'MLB123', 100)['state'], 'unknown')
            self.assertEqual(snapshot(data, 7, 'MLB123', 100)['entries'], [])
        self.assertEqual(snapshot(item(), True, 'MLB123', 100)['state'], 'unknown')

class SkuSyncTests(unittest.TestCase):
    def test_existing_batch_writes_scoped_snapshot_without_extra_api_calls(self):
        import contextlib
        import json
        import time
        from types import SimpleNamespace
        from unittest.mock import Mock
        from test_listing_details import main_function
        from listing_details import registered_weights, legacy_weight
        from full_monitor import full_metadata
        data = item(attributes=[attr()], variations=[dict(id=1, attributes=[attr('VAR')])])
        api = Mock(side_effect=[(dict(results=['MLB123'], paging=dict(total=1)), None), ([dict(code=200, body=data)], None)])
        execute = Mock()
        env = dict(time=time, json=json, banco=lambda:contextlib.nullcontext(None), consultar=Mock(return_value=[]),
                   executar=execute, registrar_erro=Mock(), get_json=api, requests=SimpleNamespace(get=Mock()),
                   registered_weights=registered_weights, legacy_weight=legacy_weight, full_metadata=full_metadata)
        self.assertTrue(main_function('puxar_anuncios', env)(9, 'synthetic', 7))
        self.assertEqual(api.call_count, 2)
        self.assertEqual(api.call_args.args[2]['include_attributes'], 'all')
        writes = [call for call in execute.call_args_list if 'SET sku_metadata_json=' in call.args[1]]
        self.assertEqual(len(writes), 1)
        params = writes[0].args[2]
        self.assertEqual(params[1:], (9, 'MLB123'))
        self.assertEqual(json.loads(params[0])['entries'][1], dict(code='VAR', variation='1'))
        api.side_effect = [(None, 'HTTP 429')]
        execute.reset_mock()
        self.assertFalse(main_function('puxar_anuncios', env)(9, 'synthetic', 7))
        execute.assert_not_called()
