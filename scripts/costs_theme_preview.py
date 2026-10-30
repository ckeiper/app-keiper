"""Render the actual costs route using synthetic records only."""
import ast, contextlib, html, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import Flask, request
from test_listing_details import main_function
from visual_theme import VISUAL_CSS

source=ast.parse(Path('main.py').read_text(encoding='utf-8'))
css=next(ast.literal_eval(n.value) for n in source.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CSS' for t in n.targets))
shell=main_function('pagina_loja',dict(session={'tipo':'admin'},esc=html.escape,CSS=css,VISUAL_CSS=VISUAL_CSS,SCRIPT='',img_logo=lambda size:''))
app=Flask('costs-preview')
for mode in ('ready','empty'):
    def query(conn,sql,params):
        if 'FROM conexoes' in sql: return [dict(cliente='Loja de demonstração',aliquota_imposto=5,comissao_pct=12)]
        if 'FROM anuncios' in sql: return [] if mode=='empty' else [dict(item_id='MLB1',titulo='Produto de teste',sku='SKU1',custo=10,preco=30)]
        raise AssertionError(sql)
    route=main_function('custos',dict(request=request,pode_ver_loja=lambda cid:cid==1,banco=lambda:contextlib.nullcontext(None),consultar=query,pagina_loja=shell,pagina=lambda t,b:b,barra_atualizar=lambda *a:'',ultima_atualizacao=lambda cid:None,esc=html.escape))
    with app.test_request_context('/custos/1'):
        output=route(1)
    Path('visual-qa').mkdir(exist_ok=True)
    Path('visual-qa/costs-theme-'+mode+'.html').write_text(output,encoding='utf-8')
