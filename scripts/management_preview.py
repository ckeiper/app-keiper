"""Synthetic screenshots of the actual store page renderer; never reads the database."""
import ast
import html
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_management import ManagementFactsTests
from test_listing_details import main_function
from management_view import render_management
from visual_theme import VISUAL_CSS

case=ManagementFactsTests()
case.setUp()
case.listings.extend([
    dict(case.listings[0],item_id='MLB1000002',titulo='Kit organizador de cozinha',status='paused',quantidade=0,fotos=7),
    dict(case.listings[0],item_id='MLB1000003',titulo='Jogo de utensílios em silicone',quantidade=12,fotos=2),
])
for index,qty in enumerate((2,4,3,5,4,3,6,2,3,4,3,5,4,5)):
    day=(case.today-__import__('datetime').timedelta(days=index+1)).isoformat()
    case.add_order('chart-'+str(index),day,qty)
report=case.build()
report['shop']['cliente']='Loja de demonstração'
body=render_management(1,report,{})
tree=ast.parse(Path('main.py').read_text(encoding='utf-8'))
css=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
         and any(isinstance(t,ast.Name) and t.id=='CSS' for t in n.targets))
env=dict(session={'tipo':'admin'},esc=html.escape,CSS=css,VISUAL_CSS=VISUAL_CSS,SCRIPT='',img_logo=lambda size:'')
env['_store_nav_icon']=main_function('_store_nav_icon',env)
page=main_function('pagina_loja',env)
destination=Path('visual-qa')
destination.mkdir(exist_ok=True)
(destination/'management-preview.html').write_text(page('Gestão da loja',1,'Loja de demonstração','resumo',body),encoding='utf-8')
print('Synthetic management preview rendered.')
