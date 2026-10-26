import sys
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from listing_review_report import render
from listing_content import CRITERIA
from test_listing_review_report import fixture
folder=Path('visual-qa');folder.mkdir(exist_ok=True)
for mode in ('empty','full'):
    d=fixture();d['shop']['cliente']='Loja fictícia para teste';d['shop']['titulo']='Produto de demonstração'
    if mode=='full':
        d['reviews']={code:dict(verdict='revise',created_at=123,created_by=1,note=('Evidência fictícia: conferir especificações e compatibilidade. '*25)[:1500]) for code in CRITERIA}
        d.update(tasks=[dict(id=i,title='Tarefa de demonstração '+str(i),responsible='Equipe de teste',due_date=date(2026,10,26),status='open') for i in range(10)],counts=[dict(status='open',n=15)],tasks_limited=True,questions=[dict(status='UNANSWERED',n=3)])
    (folder/('listing-review-report-'+mode+'.html')).write_text(render(1,'MLB1',d,123))
