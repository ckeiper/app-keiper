"""Synthetic documented-cost evidence inside the existing production priority cards."""
import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from test_profitability_priority import data,signals
from listing_priority_sources import listing_signals
from listing_priority_queue import prioritize,render

context,ranking,records=data(3)
# First card: documented negative contribution and margin decline.
# Second: changed sales basis, so no financial claim.
# Third: no documented costs, so no financial claim.
records[2]['sales_fingerprint']='b'*64
records=[r for r in records if r['item_id']!='MLB102']
now=time.time()
listings=[dict(item_id='MLB'+str(100+i),titulo=title,quantidade=20,atualizado_em=now)
          for i,title in enumerate(['Produto com contribuição negativa','Produto com base alterada','Produto aguardando custos'])]
source=listing_signals(listings,ranking,7,now=now)
for item_id,financial in signals(context,ranking,records).items():source[item_id].update(financial)
result=prioritize(ranking,verified_signals_by_item=source)
body=render(result,listings,42,days=7)
from financial_priority_queue import render as render_financial
from profitability_view import CSS
from datetime import date,timedelta
body += CSS+render_financial(source,listings,42,date(2026,10,17),date(2026,10,23))
(dest/'profitability-priorities.html').write_text(page('Prioridades dos anúncios',42,'Loja de demonstração','desempenho',body),encoding='utf-8')
print('Synthetic financial priority evidence rendered.')
