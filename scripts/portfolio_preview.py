import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_portfolio_view import PortfolioTests
from portfolio_view import combine,render
from theme_switcher import HEAD
p=Path('visual-qa');p.mkdir(exist_ok=True)
for mode in ('complete','partial'):
 ads=[dict(conexao_id=i,data='2026-10-30',gasto=10) for i in (1,2)] if mode=='complete' else []
 body=render(combine(PortfolioTests().data(),ads),{})
 (p/('portfolio-'+mode+'.html')).write_text('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'+HEAD+'</head><body style="margin:16px;background:#f3f6fb">'+'<div class="wrap"><div class="layout"><div class="conteudo">'+body+'</div></div></div></body></html>')
