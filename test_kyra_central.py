import unittest
from kyra_central import central_rows, render_central


class KyraCentralTests(unittest.TestCase):
    def test_priority_and_missing_run(self):
        shops = [{'id': 1, 'cliente': 'Alfa'}, {'id': 2, 'cliente': 'Beta'}]
        runs = [{'conexao_id': 2, 'day': '2026-10-23', 'status': 'completed',
                 'result': {'recommendations': [{'priority': 90, 'title': 'Alerta', 'action': 'Revisar'}],
                            'quality': []}}]
        rows = central_rows(shops, runs)
        self.assertEqual([r['id'] for r in rows], [2, 1])
        self.assertEqual(rows[1]['findings'], [])

    def test_html_escaping(self):
        rows = central_rows([{'id': 4, 'cliente': '<script>alert(1)</script>'}], [])
        html = render_central(rows)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('/ia-keiper/4', html)


if __name__ == '__main__':
    unittest.main()
