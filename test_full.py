from contextlib import nullcontext
from datetime import date, datetime
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from full_monitor import full_metadata, observe, stock_response, sync_full, METADATA_MAX_AGE
from full_view import daily_comparison, render_full
from sales_metrics import SAO_PAULO

NOW = 100000


def metadata(**kwargs):
    data = dict(id='MLB1', seller_id=5, inventory_id='INV1', shipping={'logistic_type':'fulfillment'}, status='active')
    data.update(kwargs)
    return full_metadata(data,5,NOW)


class FullTests(unittest.TestCase):
    def test_full_logistics_do_not_prove_stock(self):
        meta = metadata(inventory_id=None)
        result = observe(meta,Mock(side_effect=AssertionError('no inventory')),NOW)
        self.assertEqual(result['state'],'unknown')
        self.assertEqual(result['logistics'],'fulfillment')

    def test_other_logistics_can_coexist_with_full_stock(self):
        result = observe(metadata(shipping={'logistic_type':'cross_docking'}),lambda i:(3,None),NOW)
        self.assertEqual(result['state'],'available')
        self.assertEqual(result['logistics'],'other')

    def test_inventory_response_must_match_and_be_nonnegative_integer(self):
        self.assertEqual(stock_response('A',dict(inventory_id='A',available_quantity=0)),0)
        for payload in (None,{},dict(inventory_id='B',available_quantity=1)):
            self.assertIsNone(stock_response('A',payload))
        for quantity in (True,-1,1.2,'2',None):
            self.assertIsNone(stock_response('A',dict(inventory_id='A',available_quantity=quantity)))

    def test_variations_use_distinct_inventory_not_general_quantity(self):
        meta = metadata(available_quantity=999,variations=[dict(id=1,inventory_id='A'),dict(id=2,inventory_id='B')])
        lookup = Mock(side_effect=[(0,None),(4,None)])
        result = observe(meta,lookup,NOW)
        self.assertEqual(result['quantity'],4)
        self.assertEqual(result['state'],'available')
        self.assertEqual(meta['inventories'][1]['variation_id'],2)

    def test_missing_variant_or_failed_request_cannot_prove_zero(self):
        meta = metadata(variations=[dict(id=1,inventory_id='A'),dict(id=2)])
        self.assertEqual(observe(meta,lambda i:(0,None),NOW)['state'],'unknown')
        positive = observe(meta,lambda i:(1,None),NOW)
        self.assertEqual(positive['state'],'available')
        self.assertIsNone(positive['quantity'])
        complete = metadata(variations=[dict(id=1,inventory_id='A'),dict(id=2,inventory_id='B')])
        self.assertEqual(observe(complete,Mock(side_effect=[(0,None),(None,'HTTP 403')]),NOW)['state'],'unknown')
        self.assertEqual(observe(complete,lambda i:(0,None),NOW)['state'],'empty')

    def test_duplicate_inventory_not_counted_twice(self):
        meta = metadata(variations=[dict(id=1,inventory_id='A'),dict(id=2,inventory_id='A')])
        lookup = Mock(return_value=(7,None))
        self.assertEqual(observe(meta,lookup,NOW)['quantity'],7)
        lookup.assert_called_once_with('A')

    def test_stale_metadata_and_wrong_seller_never_query_inventory(self):
        lookup = Mock(side_effect=AssertionError('no remote request'))
        for meta in (None,metadata(seller_id=6),metadata()):
            stamp = NOW+METADATA_MAX_AGE+1 if meta and meta.get('inventories') else NOW
            self.assertEqual(observe(meta,lookup,stamp)['state'],'unknown')

    def test_permission_and_rate_limit_stop_subsequent_calls_and_record_unknown(self):
        rows = [dict(item_id='MLB'+str(i),full_metadata_json=metadata(inventory_id='INV'+str(i))) for i in range(3)]
        for status in (401,403,429):
            execute = Mock()
            getter = Mock(return_value=SimpleNamespace(status_code=status))
            self.assertTrue(sync_full(7,'private',lambda:nullcontext(None),Mock(return_value=rows),execute,getter,
                                      clock=lambda:NOW,monotonic=lambda:0))
            self.assertEqual(getter.call_count,1)
            record = execute.call_args.args[2]
            self.assertEqual(record[:2],(7,'MLB0'))
            self.assertEqual(record[3],'unknown')
            self.assertIsNone(record[4])
            self.assertNotIn('private',record[6])
            self.assertIn('HTTP '+str(status),record[6])

    def test_failures_are_sanitized_and_budget_is_bounded(self):
        rows = [dict(item_id='MLB'+str(i),full_metadata_json=metadata(inventory_id='INV'+str(i))) for i in range(4)]
        execute, getter = Mock(), Mock(side_effect=RuntimeError('private token'))
        with patch('full_monitor.MAX_REQUESTS',2):
            sync_full(7,'secret',lambda:nullcontext(None),Mock(return_value=rows),execute,getter,
                      clock=lambda:NOW,monotonic=lambda:0)
        self.assertEqual(getter.call_count,2)
        self.assertEqual(execute.call_count,2)
        self.assertNotIn('private',str(execute.call_args_list))
        self.assertLessEqual(getter.call_args.kwargs['timeout'][1],8)

    def test_time_budget_does_not_create_unvisited_observations(self):
        execute = Mock()
        sync_full(7,'secret',lambda:nullcontext(None),Mock(return_value=[dict(item_id='A')]),execute,Mock(),
                  clock=lambda:NOW,monotonic=Mock(side_effect=[0,46]))
        execute.assert_not_called()

    def test_daily_gaps_are_unknown_and_sales_coverage_not_zero(self):
        day = date(2026,1,2)
        stamp = int(datetime(2026,1,2,12,tzinfo=SAO_PAULO).timestamp())
        observations = [dict(item_id='A',observed_at=stamp,state='available')]
        rows = daily_comparison('A',day,date(2026,1,3),observations,[],[],[day.isoformat()])
        self.assertEqual([r['state'] for r in rows],['available','unknown'])
        self.assertEqual([r['units'] for r in rows],[0,None])
        observations.append(dict(item_id='A',observed_at=stamp+60,state='empty'))
        self.assertEqual(daily_comparison('A',day,day,observations,[],[],[]) [0]['state'],'mixed')
        observations.append(dict(item_id='A',observed_at=stamp+120,state='unknown'))
        self.assertEqual(daily_comparison('A',day,day,observations,[],[],[])[0]['state'],'unknown')

    def test_verified_listing_sales_and_incomplete_mapping(self):
        day = date(2026,1,2)
        order = dict(conexao_id=1,pedido_id='O',criado_em='2026-01-02T12:00:00-03:00',status='paid',
                     moeda='BRL',total=10,pagamentos_json=[dict(status='approved')],unidades=3)
        items = [dict(conexao_id=1,pedido_id='O',item_id='A',quantidade=2,preco_unitario=3),
                 dict(conexao_id=1,pedido_id='O',item_id='B',quantidade=1,preco_unitario=4)]
        result = daily_comparison('A',day,day,[],[order],items,[day.isoformat()])[0]
        self.assertEqual(result['units'],2)
        result = daily_comparison('A',day,day,[],[order],items[:1],[day.isoformat()])[0]
        self.assertIsNone(result['units'])

    def test_html_escapes_listing_and_explains_no_backfill(self):
        view = render_full(1,dict(periodo='personalizado',inicio='2026-01-02',fim='2026-01-03'),
                           dict(item_id='A',titulo='<script>'),[],[],[],[],None)
        self.assertIn('&lt;script&gt;',view)
        self.assertIn('Ainda não há coletas Full',view)
        self.assertIn('nem preenchemos o intervalo',view)
        self.assertIn('viewBox=',view)
        self.assertNotIn('<script>',view)


if __name__ == '__main__':
    unittest.main()
