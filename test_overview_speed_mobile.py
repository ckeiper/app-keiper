import unittest

from overview_store import DAILY_SQL
from sales_view import filters
from visual_theme import VISUAL_CSS


class OverviewSpeedAndMobileTests(unittest.TestCase):
    def test_fast_date_projection_keeps_canonical_index_guard(self):
        self.assertIn(
            "((criado_em::timestamptz AT TIME ZONE 'America/Sao_Paulo')::date) AS dia",
            DAILY_SQL)
        self.assertIn("keiper_overview_day_v1(criado_em) IS NOT NULL", DAILY_SQL)
        self.assertIn("keiper_overview_day_v1(criado_em) BETWEEN %s AND %s", DAILY_SQL)
        self.assertNotIn("keiper_overview_day_v1(criado_em) AS dia", DAILY_SQL)

    def test_mobile_filters_have_responsive_grid(self):
        html = filters(None, {}, action="/painel")
        self.assertIn("class='card period-filter'", html)
        self.assertIn("name='inicio'", html)
        self.assertIn("name='fim'", html)
        self.assertIn(".period-filter", VISUAL_CSS)
        self.assertIn("grid-template-columns:repeat(2,minmax(0,1fr))", VISUAL_CSS)


if __name__ == "__main__":
    unittest.main()
