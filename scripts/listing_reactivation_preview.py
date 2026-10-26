import sys
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from test_listing_reactivation import fixture,DAY,NOW
from listing_reactivation import render
for mode in ('paused','active','stale','tasks','history'):
    d=fixture()
    if mode=='active':d['shop']['status']='active'
    if mode=='stale':d['shop']['atualizado_em']=1
    if mode=='tasks':d.update(tasks=[dict(id=i,responsible='Equipe',due_date=DAY,status='open',description='Conferir o motivo informado no marketplace.') for i in range(1,11)],total=15,pages=2)
    if mode=='history':d['events']=[dict(before_value='paused',after_value='active',previous_at=NOW-60,observed_at=NOW)]
    (dest/('listing-reactivation-'+mode+'.html')).write_text(page('Revisão de reativação',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(1,'MLB1',d,DAY,NOW,'token')))
