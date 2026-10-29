"""Synthetic actual store-shell previews; never touches production data."""
import time
from datetime import date
from catalog_preview import page,dest
from listing_kit_view import render,flatten
from listing_kits import validate,evidence
from test_listing_kits import form,row
now=int(time.time());today=date.today();c,key=validate(dict(form(),source_date=today.isoformat()),today)
ctx=dict(orders=[],items=[],coverage=[],pending=False)
record=dict(id=1,composition=c,created_at=now,created_by=1)
for mode in ['empty','ready','partial']:
    proof=evidence(c,ctx,[row(stamp=now if mode!='partial' else 1)],'MLB1',date.fromisoformat(c['start']),date.fromisoformat(c['end']),now)
    html=render(7,'MLB1','Kit <Teste>','csrf','k'*32,flatten(c) if mode!='empty' else {},record if mode!='empty' else None,proof if mode!='empty' else None,[record] if mode!='empty' else [],1,1)
    (dest/('listing-kits-'+mode+'.html')).write_text(page('Análise de kits',7,'Loja de demonstração','anuncios',html),encoding='utf-8')
print('Synthetic kit analysis previews rendered.')
