"""Isolated calendar fixtures, no production writes."""
import sys
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from listing_calendar import render
for mode in ('empty','ready','page2'):
    day=date(2026,10,26)
    rows=[] if mode=='empty' else [dict(id=i,title='Conferir conteúdo e oferta '+str(i),responsible='Equipe responsável',due_date=day,status='open') for i in range(1,11)]
    data=dict(first=day.replace(day=1),status='open',counts={} if mode=='empty' else {day:25},total=0 if mode=='empty' else 25,pages=1 if mode=='empty' else 3,page=2 if mode=='page2' else 1,rows=rows)
    (dest/('listing-calendar-'+mode+'.html')).write_text(page('Calendário do anúncio',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(1,'MLB123',dict(titulo='Produto de teste'),data,day)))
