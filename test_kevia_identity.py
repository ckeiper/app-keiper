import unittest
from keiper_ai_view import render
from kyra_central import render_central
from kyra_history import render_history


class KeviaIdentityTests(unittest.TestCase):
    def test_saved_analysis_views_share_current_public_identity(self):
        for output in [render({},cid=42),render_central([]),render_history([])]:
            with self.subTest(view=output[:60]):
                self.assertIn('KEVIA',output)
                self.assertNotIn('KYRA',output)
        # Stable links preserve existing bookmarks and stored history.
        self.assertIn('/ads/42',render({},cid=42))
