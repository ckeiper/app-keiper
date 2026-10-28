"""Synthetic Full screen fixtures; no database or marketplace requests."""
import sys
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from full_view import render_full
from test_full_report import observation,STAMP,ARGS,LISTING,START
import ast
source=ast.parse(Path('full_routes.py').read_text(encoding='utf-8'))
prefix=next(node.value for node in ast.walk(source) if isinstance(node,ast.Constant) and isinstance(node.value,str) and "<span class='full-page-theme'" in node.value)
shell=prefix+"<option value='1'>Loja de demonstração</option></select></label><button>Abrir loja</button></form><form class='card'><label>Anúncio <select><option>Produto de teste</option></select></label><button>Aplicar</button></form>"

coverage=[(START+timedelta(days=i)).isoformat() for i in range(30)]
for mode in ('ready','partial','empty','page2','variations'):
    rows=[observation(STAMP-i*60) for i in range(40)]
    args=dict(ARGS)
    if mode=='partial':
        rows[0]['state']='unknown';rows[0]['quantity']=None
        rows[0]['evidence']['partial']=True
        rows[0]['evidence']['inventories'][1].update(quantity=None,reason='Consulta não autorizada')
    if mode=='empty':rows=[]
    if mode=='page2':args.update(full_dias='2',full_consultas='2')
    if mode=='variations':
        row=rows[0];mapping=[];readings=[]
        for i in range(51):
            inventory='INV'+str(i)
            mapping.append(dict(inventory_id=inventory,variation_id=i+1))
            readings.append(dict(inventory_id=inventory,quantity=0 if i==0 else 3,reason=None))
        row['evidence']['metadata']['inventories']=mapping
        row['evidence']['inventories']=readings
        row['quantity']=150
        args['full_variacoes']='2'
    first=dict(first=min(r['observed_at'] for r in rows),first_known=min(r['observed_at'] for r in rows if r['state']!='unknown')) if rows else {}
    body=shell+render_full(1,args,LISTING,rows,[],[],coverage,first)
    (dest/('full-report-'+mode+'.html')).write_text(page('Full e vendas',1,'Loja de demonstração','full',body),encoding='utf-8')
print('Synthetic Full report previews rendered.')


from test_full_variation_history import reading
for mode in ('ready','gap','switched','shared','page2','limited'):
    rows=[reading(STAMP-7200,2),reading(STAMP-3600,0),reading(STAMP,3)]
    args=dict(ARGS,full_variacao='1')
    if mode=='gap':rows[1]=reading(STAMP-3600,None)
    if mode=='switched':rows[-1]=reading(STAMP,3,inventory='NEW')
    if mode=='shared':
        rows[-1]['evidence']['metadata']['inventories'][1]['inventory_id']='A'
        rows[-1]['evidence']['inventories']=rows[-1]['evidence']['inventories'][:1]
        rows[-1]['quantity']=3
    if mode in ('page2','limited'):
        rows=[reading(STAMP-i*30,i%4) for i in range(41 if mode=='page2' else 510)]
    if mode=='page2':args['full_historico_variacao']='2'
    first=dict(first=min(r['observed_at'] for r in rows),first_known=min(r['observed_at'] for r in rows))
    body='<p>Dados fictícios para validação automática.</p>'+render_full(1,args,LISTING,rows,[],[],coverage,first)
    (dest/('full-variation-history-'+mode+'.html')).write_text(page('Histórico da variação Full',1,'Loja de demonstração','full',body),encoding='utf-8')
