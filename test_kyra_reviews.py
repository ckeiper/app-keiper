import unittest
from kyra_reviews import render_review


class KyraReviewTests(unittest.TestCase):
    def test_escapes_title_code_and_token(self):
        html = render_review(4, [{'code':'a"b', 'title':'<script>x</script>'}], {}, 'token"')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('a&quot;b', html)
        self.assertIn('token&quot;', html)

    def test_state_selected(self):
        html = render_review(2, [{'code':'roas', 'title':'ROAS'}], {'roas':'resolvido'}, 'x')
        self.assertIn('value="resolvido" selected', html)


if __name__ == '__main__':
    unittest.main()
