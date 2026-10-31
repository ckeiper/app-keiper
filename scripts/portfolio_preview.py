import sys
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_portfolio_view import PortfolioTests
from portfolio_view import combine,render
from theme_switcher import HEAD
p=Path('visual-qa');p.mkdir(exist_ok=True)
for mode in ('complete','partial'):
 data=PortfolioTests().data();data['bounds']=(date(2026,10,28),date(2026,10,30),date(2026,10,25),date(2026,10,27))
 for report in data['reports']:
  report['current']['daily']=[100,200,300];report['previous']['daily']=[90,210,250]
 ads=[dict(conexao_id=i,data='2026-10-'+str(d),gasto=10) for i in (1,2) for d in (28,29,30)] if mode=='complete' else []
 body=render(combine(data,ads),{})
 (p/('portfolio-'+mode+'.html')).write_text('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'+HEAD+'</head><body style="margin:16px;background:#f3f6fb">'+'<div class="wrap"><div class="layout"><div class="conteudo">'+body+'</div></div></div></body></html>')
