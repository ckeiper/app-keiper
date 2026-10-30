"""Synthetic goal screens; no production writes."""
import sys
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_goal_view import render
from test_listing_goals import goal,shop,DAY,NOW
for mode in ('empty','alert','met','unknown','scheduled','ended','cancelled'):
    g=goal();s=shop()
    if mode=='met':s['quantidade']=9
    if mode=='unknown':s['atualizado_em']=1
    if mode=='scheduled':g['start_date']=DAY+timedelta(days=1)
    if mode=='ended':g.update(start_date=DAY-timedelta(days=30),end_date=DAY-timedelta(days=1))
    if mode=='cancelled':g.update(cancelled_at=NOW,cancelled_by=1)
    data=dict(rows=[] if mode=='empty' else [g],total=0 if mode=='empty' else 1,page=1,pages=1)
    (dest/('listing-goals-'+mode+'.html')).write_text(page('Metas de estoque',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(1,'MLB1',s,data,DAY,NOW,'token')))
