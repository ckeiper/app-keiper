"""Synthetic timeline fixtures using the production shell and renderer; no DB or API."""
import sys
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
# Existing preview initializes the shared shell without importing main.
from catalog_preview import page,dest
from listing_timeline import render
from listing_ranking import ranking_metrics
from investigation_evidence import build as build_evidence, render as render_evidence

end=date(2026,10,20)
covered=[(end-timedelta(days=i)).isoformat() for i in range(14)]
orders=[];items=[];visits=[];full=[];offers=[]
for i in range(14):
    day=end-timedelta(days=13-i)
    stamp=int(datetime(day.year,day.month,day.day,12,tzinfo=timezone(timedelta(hours=-3))).timestamp())
    orders.append(dict(conexao_id=1,pedido_id=str(i),status='paid',total=200-i*5,moeda='BRL',criado_em=day.isoformat()+'T12:00:00-03:00',pagamentos_json=[{'status':'approved'}],unidades=1))
    items.append(dict(conexao_id=1,pedido_id=str(i),item_id='MLB100000',quantidade=1,preco_unitario=200-i*5))
    if i%4:
        visits.append(dict(dia=day,visitas=40+i*3))
        full.append(dict(observed_at=stamp,logistics='fulfillment',state='empty' if i>10 else 'available'))
    if i>8:
        offers.extend([dict(observed_at=stamp-7200,price=80,promotion=True,confirmed=True),dict(observed_at=stamp+3600,price=100,promotion=False,confirmed=True)])
for name,args in [('timeline-visitas',{}),('timeline-preco',{'comparar_linha':'preco'}),('timeline-page2',{'comparar_linha':'preco','pagina_linha':'2'}),('timeline-short',{'comparar_linha':'preco','janela_linha':'7'})]:
    ranked=ranking_metrics(orders,items,covered,['MLB100000'],end=end,days=7)
    panel=render_evidence(build_evidence(ranked,'MLB100000',visits,full,[],end,offers=offers),1,end)
    body='<p>Dados fictícios para validação automática.</p>'+panel+render('MLB100000',orders,items,covered,full,visits,offers,end,args=args)
    (dest/(name+'.html')).write_text(page('Linha do tempo',1,'Loja de demonstração','desempenho',body),encoding='utf-8')
print('Synthetic timeline previews rendered.')
