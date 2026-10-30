"""Real financial-view code with explicitly synthetic fixtures, no database or APIs."""
import sys,copy
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from test_kevia_finance import snapshot,CHECKED
from test_profitability_priority import data,END
from kevia_finance import build_snapshot,empty_snapshot
from keiper_ai import recommendations,render

ads=[dict(data=(END-timedelta(days=i)).isoformat(),gasto=0,faturamento=0,atualizado_em=CHECKED) for i in range(14)]
report=dict(eligible=True,reasons=[],current=dict(revenue=100,orders=1),previous=dict(revenue=200,orders=1))
public=recommendations(report,ads,END+timedelta(days=1),CHECKED)
context,_,records=data(2)
partial=build_snapshot(42,context,records[:2],END,CHECKED)
for kind,financial in [('ready',snapshot()),('partial',partial),('missing',empty_snapshot(END,CHECKED)),
                       ('failed',empty_snapshot(END,CHECKED,status='failed')),('pending',None),('client',snapshot())]:
    result=dict(public,financial=copy.deepcopy(financial))
    body="<p>PRÉVIA DE DESIGN · DADOS FICTÍCIOS PARA TESTE</p>"+render(result,END+timedelta(days=1),status='completed',cid=42,daily=ads,admin_financial=kind!='client')
    (dest/('kevia-finance-'+kind+'.html')).write_text(page('KEVIA',42,'Loja de demonstração','ia',body),encoding='utf-8')
print('Synthetic KEVIA financial snapshots rendered.')
