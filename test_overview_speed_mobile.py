import unittest

from sales_view import filters
from visual_theme import VISUAL_CSS


class OverviewSpeedAndMobileTests(unittest.TestCase):
    def test_mobile_filters_have_responsive_grid(self):
        html = filters(None, {}, action="/painel")
        self.assertIn("class='card period-filter'", html)
        self.assertIn("name='inicio'", html)
        self.assertIn("name='fim'", html)
        self.assertIn(".period-filter", VISUAL_CSS)
        self.assertIn("grid-template-columns:repeat(2,minmax(0,1fr))", VISUAL_CSS)


if __name__ == "__main__":
    unittest.main()
