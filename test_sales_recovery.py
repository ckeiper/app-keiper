"""Regression: repeated API pages must not strand a reporting day."""
import unittest
from datetime import date, datetime, timedelta, timezone
from sales_sync import collect_day


class PaginationRecoveryTests(unittest.TestCase):
    day = date(2026, 10, 16)

    def api(self, mode='recover'):
        calls = []
        orders = [{'id': n, 'date_created': f'2026-10-16T{hour}-03:00'}
                  for n, hour in [(1, '00:00:00.000'), (2, '11:59:59.999'),
                                  (3, '12:00:00.000'), (4, '23:59:59.999')]]

        def get(token, path, params):
            calls.append(params)
            start = datetime.fromisoformat(params['order.date_created.from'])
            end = datetime.fromisoformat(params['order.date_created.to'])
            if (end-start).total_seconds() > 86000:
                total = 5 if mode == 'changing' and params['offset'] else 4
                return {'results': [orders[0]], 'paging': {'total': total}}, None
            if mode == 'rate-limit':
                return None, 'HTTP 429'
            if mode == 'ignores-filter':
                selected = orders
            elif mode == 'persistent':
                selected = [dict(orders[0], date_created=start.isoformat())]
                return {'results': selected, 'paging': {'total': 2}}, None
            elif mode == 'duplicate-across-windows':
                selected = [dict(orders[0], date_created=start.isoformat())]
            else:
                selected = [r for r in orders if start <= datetime.fromisoformat(r['date_created']) <= end]
            return {'results': selected, 'paging': {'total': len(selected)}}, None
        return get, calls

    def test_repeated_daily_page_recovers_all_orders_without_boundary_overlap(self):
        api, calls = self.api()
        rows, complete, _ = collect_day('token', 5, api, self.day)
        self.assertTrue(complete)
        self.assertEqual(set(rows), {'1', '2', '3', '4'})
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[2]['offset'], 0)
        self.assertEqual(calls[3]['offset'], 0)

    def test_unstable_total_uses_independently_verified_windows(self):
        api, _ = self.api('changing')
        rows, complete, _ = collect_day('token', 5, api, self.day)
        self.assertTrue(complete)
        self.assertEqual(len(rows), 4)

    def test_filter_ignored_is_not_accepted_as_complete(self):
        api, _ = self.api('ignores-filter')
        _, complete, reason = collect_day('token', 5, api, self.day)
        self.assertFalse(complete)
        self.assertIn('fora do intervalo', reason)

    def test_same_order_cannot_be_counted_in_both_windows(self):
        api, _ = self.api('duplicate-across-windows')
        _, complete, reason = collect_day('token', 5, api, self.day)
        self.assertFalse(complete)
        self.assertIn('duplicados entre intervalos', reason)

    def test_rate_limit_stops_recovery(self):
        api, calls = self.api('rate-limit')
        _, complete, reason = collect_day('token', 5, api, self.day)
        self.assertFalse(complete)
        self.assertEqual(reason, 'HTTP 429')
        self.assertEqual(len(calls), 3)

    def test_persistent_duplicates_are_bounded(self):
        api, calls = self.api('persistent')
        _, complete, _ = collect_day('token', 5, api, self.day)
        self.assertFalse(complete)
        self.assertLessEqual(len(calls), 80)

    def test_day_above_api_pagination_cap_is_recovered_without_losing_orders(self):
        start = datetime(2026, 10, 16, tzinfo=timezone(timedelta(hours=-3)))
        orders = [{'id': i+1, 'date_created': (start+timedelta(minutes=i)).isoformat()}
                  for i in range(1001)]
        calls = []

        def api(token, path, params):
            calls.append(params)
            lower = datetime.fromisoformat(params['order.date_created.from'])
            upper = datetime.fromisoformat(params['order.date_created.to'])
            selected = [r for r in orders if lower <= datetime.fromisoformat(r['date_created']) <= upper]
            offset = params['offset']
            return {'results': selected[offset:offset+50], 'paging': {'total': len(selected)}}, None

        rows, complete, _ = collect_day('token', 5, api, self.day)
        self.assertTrue(complete)
        self.assertEqual(set(rows), {str(i) for i in range(1, 1002)})
        self.assertLessEqual(len(calls), 80)

    def test_hour_precision_api_and_inclusive_boundary_recover_every_order(self):
        start = datetime(2026, 10, 16, tzinfo=timezone(timedelta(hours=-3)))
        # Include the final hour, exact split boundaries, and the next day's
        # orders returned by an inclusive hour-precision upper bound.
        orders = [{'id': i+1, 'date_created': (start+timedelta(minutes=15*i)).isoformat()}
                  for i in range(100)]
        calls = []
        def api(token, path, params):
            calls.append(params)
            lower = datetime.fromisoformat(params['order.date_created.from'])
            upper = datetime.fromisoformat(params['order.date_created.to'])
            self.assertEqual((lower.minute, lower.second, lower.microsecond), (0, 0, 0))
            self.assertEqual((upper.minute, upper.second, upper.microsecond), (0, 0, 0))
            selected = [r for r in orders if lower <= datetime.fromisoformat(r['date_created']) < upper+timedelta(hours=1)]
            if upper-lower > timedelta(hours=1):
                return {'results': selected[:1], 'paging': {'total': len(selected)}}, None
            return {'results': selected, 'paging': {'total': len(selected)}}, None
        rows, complete, reason = collect_day('token', 5, api, self.day)
        self.assertTrue(complete, reason)
        self.assertEqual(set(rows), {str(i) for i in range(1, 97)})
        self.assertLessEqual(len(calls), 80)

    def test_next_day_boundary_is_not_assigned_to_previous_day(self):
        orders = [{'id': 1, 'date_created': '2026-10-16T23:59:59.999-03:00'},
                  {'id': 2, 'date_created': '2026-10-17T00:00:00.000-03:00'}]
        rows, complete, _ = collect_day('token', 5, lambda *args:
            ({'results': orders, 'paging': {'total': 2}}, None), self.day)
        self.assertTrue(complete)
        self.assertEqual(set(rows), {'1'})

