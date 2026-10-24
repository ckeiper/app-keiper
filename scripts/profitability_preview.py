"""Synthetic financial evidence fixtures through the production store shell."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from test_profitability import summary,record,START,END
from profitability_store import result_for
from profitability_view import render

for name,entry in [('profitability-ready',record()),('profitability-missing',None),('profitability-stale',dict(record(),sales_fingerprint='b'*64))]:
    body=render(42,'MLB100','Produto de demonstração',START,END,summary(),result_for(summary(),entry),entry,[entry] if entry else [],'preview-only','x'*32)
    (dest/(name+'.html')).write_text(page('Rentabilidade por anúncio',42,'Loja de demonstração','anuncios',body),encoding='utf-8')
print('Synthetic profitability previews rendered.')
