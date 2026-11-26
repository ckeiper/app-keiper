"""Local-only preview with controlled search records, never used in production."""
import ast
import html
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import Flask
from title_optimizer_routes import render
from visual_theme import VISUAL_CSS

tree=ast.parse(Path('main.py').read_text())
css=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CSS' for t in n.targets))
node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='pagina_loja')
node.decorator_list=[]
namespace=dict(session={'tipo':'admin'},esc=html.escape,CSS=css,VISUAL_CSS=VISUAL_CSS,SCRIPT='',img_logo=lambda size:'')
exec(compile(ast.Module(body=[node],type_ignores=[]),'main.py','exec'),namespace)
page=namespace['pagina_loja']
app=Flask(__name__,static_folder=str(Path('static').resolve()))
@app.get('/otimizador-titulos/1')
def preview():
    return page('Otimizador de Títulos',1,'Prévia local · dados controlados','otimizador',render())
if __name__=='__main__':app.run(host='0.0.0.0',port=8765,debug=False)
