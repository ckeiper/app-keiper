import ast
import unittest
from pathlib import Path
from theme_switcher import HEAD, SCRIPT
from scripts.ads_overview_preview import render_fixture


class ThemeSwitcherTests(unittest.TestCase):
    def test_real_store_shell_has_one_control_script_and_early_preference(self):
        result = render_fixture()
        self.assertEqual(result.count(HEAD), 1)
        self.assertEqual(result.count(SCRIPT), 1)
        self.assertLess(result.index(HEAD), result.index('</head>'))
        self.assertLess(result.index(SCRIPT), result.index('</body>'))

    def test_both_shells_include_shared_theme(self):
        tree = ast.parse(Path('main.py').read_text())
        for name in ('pagina','pagina_loja'):
            node = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            source=ast.unparse(node)
            self.assertIn('from theme_switcher import',source)
            self.assertIn('theme_head',source)
            self.assertIn('theme_script',source)

    def test_appearance_stays_local_and_accessible(self):
        self.assertNotIn('fetch(', HEAD+SCRIPT)
        self.assertNotIn('document.cookie', HEAD+SCRIPT)
        self.assertIn('aria-checked', SCRIPT)
        self.assertNotIn('top.appendChild', SCRIPT)
        self.assertIn('focus-visible', HEAD)
        self.assertIn('storage', SCRIPT)
        self.assertIn('@media print', HEAD)
