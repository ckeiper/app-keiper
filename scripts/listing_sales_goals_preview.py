"""Synthetic goals rendered in the real shell, without database access."""
from datetime import timedelta
from catalog_preview import page,dest
from test_listing_sales_goals import DAY,goal
from listing_sales_goals import evaluate
from listing_sales_goal_view import render
for mode in ['empty','unknown','alert','met','progress','cancelled']:
    g=goal(end_date=DAY if mode=='progress' else DAY-timedelta(days=1),cancelled_at=1 if mode=='cancelled' else None)
    summary={} if mode=='unknown' else {'units':12 if mode=='met' else 0}
    model=dict(rows=[] if mode=='empty' else [g],page=1,pages=1,total=0 if mode=='empty' else 1,evaluations={1:evaluate(g,summary,DAY)})
    html=render(7,'MLB1',dict(titulo='Produto de teste'),model,DAY,0,'csrf')
    (dest/('listing-sales-goals-'+mode+'.html')).write_text(page('Metas de vendas',7,'Loja de teste','anuncios',html))
