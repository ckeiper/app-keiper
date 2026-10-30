import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from goal_observations import render
from test_listing_goals import goal,NOW
for mode in ('empty','history','page2'):
    rows=[] if mode=='empty' else [dict(evaluated_at=NOW+i,source_at=NOW if i%3 else 1,stock=None if i%3==0 else 0 if i%3==1 else 8,state='unknown' if i%3==0 else 'alert' if i%3==1 else 'met') for i in range(3 if mode=='page2' else 10)]
    data=dict(goal=goal(),rows=rows,total=0 if mode=='empty' else 13,page=2 if mode=='page2' else 1,pages=1 if mode=='empty' else 2)
    (dest/('goal-observations-'+mode+'.html')).write_text(page('Histórico da meta',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(1,'MLB1',data)))
