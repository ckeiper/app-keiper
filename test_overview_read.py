from unittest import TestCase
from unittest.mock import MagicMock, patch

from overview_read import bounded_query, TIMEOUT_MESSAGE


class OverviewReadTests(TestCase):
    def test_budget_is_shared_between_queries(self):
        conn, query = MagicMock(), MagicMock(return_value=[])
        with patch('overview_read.time.monotonic', side_effect=[100, 101, 110, 113]):
            read = bounded_query(conn, query)
            read(conn, 'first', ())
            read(conn, 'second', ())
            with self.assertRaisesRegex(ValueError, 'Nenhum total parcial'):
                read(conn, 'third', ())
        self.assertEqual(query.call_count, 2)
        calls = conn.cursor.return_value.__enter__.return_value.execute.call_args_list
        self.assertEqual([c.args[1] for c in calls], [('11000',), ('2000',)])

    def test_database_cancellation_is_a_safe_visible_error(self):
        class Cancelled(Exception):
            pgcode = '57014'
        read = bounded_query(MagicMock(), MagicMock(side_effect=Cancelled('private SQL')))
        with self.assertRaises(ValueError) as error:
            read(None, 'slow', ())
        self.assertEqual(str(error.exception), TIMEOUT_MESSAGE)

    def test_other_errors_are_not_hidden(self):
        read = bounded_query(MagicMock(), MagicMock(side_effect=RuntimeError('broken')))
        with self.assertRaises(RuntimeError):
            read(None, 'query', ())
