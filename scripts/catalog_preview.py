"""Render synthetic catalog pages through the real store shell, without database access."""
import ast
import html
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_listing_details import main_function
from listing_catalog import render_catalog
from visual_theme import VISUAL_CSS

now=int(time.time())
rows=[dict(item_id='MLB'+str(100000+i),titulo=['Kit organizador de cozinha com 6 peças','Jogo de utensílios em silicone premium','Garrafa térmica inox 1 litro'][i%3],sku='KEIPER-'+str(i),status='paused' if i%7==0 else 'active',quantidade=0 if i%5==0 else 2 if i%3==0 else 48,preco=69.9+i,fotos=i%10,clips=None if i%4==0 else i%2,vendidos=150+i*3,custo=35,atualizado_em=now,thumbnail='https://http2.mlstatic.com/catalog-test.jpg' if i==0 else None,full_metadata_json={'collected_at':now,'logistics':'fulfillment' if i%2==0 else 'other'},tags='["good_quality_picture"]') for i in range(45)]
tree=ast.parse(Path('main.py').read_text(encoding='utf-8'))
css=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CSS' for t in n.targets))
env=dict(session={'tipo':'admin'},esc=html.escape,CSS=css,VISUAL_CSS=VISUAL_CSS,SCRIPT='',img_logo=lambda size:'')
env['_store_nav_icon']=main_function('_store_nav_icon',env)
page=main_function('pagina_loja',env)
dest=Path('visual-qa');dest.mkdir(exist_ok=True)
for name,args in [('catalog',{}),('catalog-filtered',{'status':'active','estoque':'baixo','por_pagina':'10'})]:
    body=render_catalog(1,rows,args,refresh="<a href='/atualizar/anuncios/1'>Atualizar agora</a> · Última leitura disponível",now=now,admin=True)
    (dest/(name+'.html')).write_text(page('Anúncios',1,'Loja de demonstração','anuncios',body),encoding='utf-8')
print('Synthetic catalog previews rendered.')
