"""Synthetic preview of the real Ads campaign renderer."""
import sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ads_campaign_detail import render

today=date(2026,10,22)
history=[dict(data=(today-timedelta(days=i)).isoformat(),gasto=cost,faturamento=revenue,
              vendas_atribuidas=[42,68,73,31,48,59,61][i],outras_vendas=[38,71,69,56,44,52,47][i])
         for i,(cost,revenue) in enumerate([(43.9,352.4),(79.66,683.64),(85.1,824.8),(48.2,298.7),(62.5,458.3),(71.8,649.9),(74.2,617.2)])]
shop={r['data']:r['faturamento']+789.5-(i*67) for i,r in enumerate(history)}
ads={r['data']:r['faturamento'] for r in history}
body=render(1,dict(campanha_id='10',nome='Campanha principal',status='active',orcamento=120,roas_objetivo=6),history,7,today,shop_daily=shop,ads_total_daily=ads)
Path('visual-qa').mkdir(exist_ok=True)
Path('visual-qa/ads-chart.html').write_text("<!doctype html><html lang='pt-BR'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><style>body{margin:0;background:#f3f6fb;font-family:Inter,'Segoe UI',sans-serif}.preview{max-width:1120px;margin:auto;padding:24px}@media(max-width:570px){.preview{padding:10px}}</style><div class='preview'>"+body+'</div></html>',encoding='utf-8')

