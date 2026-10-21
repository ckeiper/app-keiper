"""Synthetic previews of the real homepage shell and CRM fragment."""
import ast
import datetime as dt
import html
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import Flask, render_template_string
from client_home import render_client_home
from crm_home import HOME_WIDGET, SUMMARY
from test_listing_details import main_function
from visual_theme import VISUAL_CSS

source=ast.parse(Path('main.py').read_text())
css=next(ast.literal_eval(n.value) for n in source.body if isinstance(n,ast.Assign)
         and any(isinstance(t,ast.Name) and t.id=='CSS' for t in n.targets))
page=main_function('pagina',dict(esc=html.escape,CSS=css,VISUAL_CSS=VISUAL_CSS,SCRIPT='',img_logo=lambda size:''))
shops=[dict(id=1,cliente='ABM VEDAÇÕES',status='ativa'),dict(id=2,cliente='Copas Ind',status='ativa')]
output=Path('visual-qa');output.mkdir(exist_ok=True)
(output/'crm-home.html').write_text(page('Suas lojas',render_client_home(shops,admin=True)+HOME_WIDGET))
today=dt.date(2026,10,21)
leads=[dict(id=i,nome=name,data_followup=today-dt.timedelta(days=days),dados={'proxima_acao':action})
       for i,name,days,action in [(11,'Marina · Loja de cosméticos',2,'Retomar proposta de consultoria e combinar a próxima reunião.'),
                                (12,'Ricardo Fernandes',1,'Confirmar acesso aos indicadores da loja.'),
                                (13,'Ana <Loja Exemplo>',0,'Enviar a proposta com os próximos passos.')]]
with Flask('crm-preview').app_context():
    for name,rows,counts in [('populated',leads,dict(overdue=2,due=1,undated=4)),
                             ('empty',[],dict(overdue=0,due=0,undated=0))]:
        (output/f'crm-{name}.html').write_text(render_template_string(SUMMARY,leads=rows,today=today,**counts))
print('Synthetic CRM home and summary states rendered.')
