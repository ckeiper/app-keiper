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
page=main_function('pagina_loja',env)
dest=Path('visual-qa');dest.mkdir(exist_ok=True)
for name,args in [('catalog',{}),('catalog-filtered',{'status':'active','estoque':'baixo','por_pagina':'10'})]:
    body=render_catalog(1,rows,args,refresh="<a href='/atualizar/anuncios/1'>Atualizar agora</a> · Última leitura disponível",now=now,admin=True)
    (dest/(name+'.html')).write_text(page('Anúncios',1,'Loja de demonstração','anuncios',body),encoding='utf-8')
print('Synthetic catalog previews rendered.')

from listing_diagnostic_design import hero,priorities
checks=[dict(priority='alta',title='Conferir disponibilidade',evidence='Leitura sintética de estoque zero.',action='Conferir reposição e a leitura mais recente.'),dict(priority='revisar',title='Revisar oferta',evidence='Alteração sintética de preço.',action='Conferir fontes e condições comerciais.')]
(dest/'diagnostic-navy.html').write_text(page('Diagnóstico do anúncio',1,'Loja de demonstração','anuncios',hero(dict(titulo='Produto de demonstração'),1,'MLB100',checks)+priorities(checks)),encoding='utf-8')

from test_catalog_price_order import snapshot
from test_listing_catalog import item as price_item,NOW as price_now
from unittest.mock import patch
with patch('listing_details.time.time',return_value=price_now):
    price_rows=[dict(price_item(1),preco=200,promocoes_json=snapshot()),dict(price_item(2),preco=100)]
    (dest/'catalog-price-sort.html').write_text(page('Catálogo por preço',1,'Loja de demonstração','anuncios',render_catalog(1,price_rows,dict(ordem='preco'),now=price_now)),encoding='utf-8')

from listing_comparison import render as render_comparison
from test_listing_comparison import sample as comparison_sample,END as comparison_end
for mode in ['two','four','pending']:
    ranking,listings=comparison_sample()
    args={f'comparar{i}':'MLB'+str(i) for i in range(1,3 if mode=='two' else 5)}
    if mode=='pending':ranking['available']=False
    body='<p>Dados fictícios para teste.</p>'+render_comparison(1,ranking,listings,args,comparison_end)
    (dest/('listing-comparison-'+mode+'.html')).write_text(page('Comparar anúncios',1,'Loja de demonstração','desempenho',body),encoding='utf-8')
