"""Synthetic Full screen fixtures; no database or marketplace requests."""
import sys
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from full_view import render_full
from test_full_report import observation,STAMP,ARGS,LISTING,START

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
    body='<p>Dados fictícios para validação automática.</p>'+render_full(1,args,LISTING,rows,[],[],coverage,first)
    (dest/('full-report-'+mode+'.html')).write_text(page('Full e vendas',1,'Loja de demonstração','full',body),encoding='utf-8')
print('Synthetic Full report previews rendered.')
