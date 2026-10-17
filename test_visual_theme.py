import unittest
from visual_theme import VISUAL_CSS


class DashboardVisualThemeTests(unittest.TestCase):
    def test_theme_has_responsive_mobile_layout(self):
        self.assertIn("@media(max-width:820px)", VISUAL_CSS)
        self.assertIn("overflow-x:auto", VISUAL_CSS)
        self.assertIn("flex-direction:column", VISUAL_CSS)

    def test_theme_preserves_status_colors_and_accessibility(self):
        self.assertIn("a:focus-visible", VISUAL_CSS)
        self.assertIn("prefers-reduced-motion:reduce", VISUAL_CSS)
        self.assertIn("@media print", VISUAL_CSS)
        self.assertNotIn(".tag.ativa", VISUAL_CSS)
        self.assertNotIn(".var.caiu", VISUAL_CSS)

    def test_theme_has_no_external_dependencies(self):
        self.assertNotIn("@import", VISUAL_CSS)
        self.assertNotIn("url(", VISUAL_CSS)
        self.assertTrue(VISUAL_CSS.startswith("\n<style>"))
        self.assertTrue(VISUAL_CSS.rstrip().endswith("</style>"))


if __name__ == "__main__":
    unittest.main()
