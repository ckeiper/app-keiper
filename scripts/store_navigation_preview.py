"""Render the actual store shell with synthetic data and no app import."""
import ast
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual_theme import VISUAL_CSS

tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
css = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
           and any(isinstance(t, ast.Name) and t.id == 'CSS' for t in n.targets))
shell = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'pagina_loja')
env = dict(esc=html.escape, CSS=css, VISUAL_CSS=VISUAL_CSS, SCRIPT='', img_logo=lambda size: '')
exec(compile(ast.Module(body=[shell], type_ignores=[]), 'main.py', 'exec'), env)
destination = Path('visual-qa')
destination.mkdir(exist_ok=True)
for section in ('resumo', 'ads', 'custos', 'anuncios'):
    body = "<div class='card'><h2>Loja de demonstração</h2><p>Conferência da navegação.</p></div>"
    (destination / ('store-nav-'+section+'.html')).write_text(
        env['pagina_loja']('Navegação', 5, 'Loja de demonstração', section, body), encoding='utf-8')
