import unittest
from kyra_history import render_history


class KyraHistoryTests(unittest.TestCase):
    def test_empty(self):
        self.assertIn('Nenhuma análise registrada', render_history([]))

    def test_escapes_untrusted_titles(self):
        html = render_history([{'day': '2026-10-23', 'status': 'completed',
                                'result': {'recommendations': [{'title': '<script>x</script>'}],
                                           'quality': ['atraso']}}])
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('Com ressalvas', html)


if __name__ == '__main__':
    unittest.main()
