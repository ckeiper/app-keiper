from datetime import timedelta
from decimal import Decimal
from catalog_preview import page,dest
from sales_goal_observations import render
from test_listing_sales_goals import goal,DAY
from test_sales_goal_observations import NOW
for state in ['empty','unknown','alert','met','progress']:
    rows=[] if state=='empty' else [dict(state=state,value=None if state=='unknown' else Decimal(0),evaluated_at=NOW,cutoff=DAY-timedelta(days=1))]
    model=dict(goal=goal(),rows=rows,total=len(rows),page=1,pages=1)
    (dest/('sales-goal-history-'+state+'.html')).write_text(page('Histórico de metas',7,'Loja teste','anuncios',render(7,'MLB1',model)))
