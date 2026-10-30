"""Exercise the actual Ads route and store shell with synthetic data only."""
import ast
import contextlib
import datetime
import html
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import Flask, request
from test_listing_details import main_function
from visual_theme import VISUAL_CSS

TODAY=datetime.date(2026,10,22)


def render_fixture(empty=False, args='', admin=True, campaign_updates=None):
    source=ast.parse(Path('main.py').read_text(encoding='utf-8'))
    css=next(ast.literal_eval(n.value) for n in source.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CSS' for t in n.targets))
    env=dict(session={'tipo':'admin' if admin else 'cliente'},esc=html.escape,CSS=css,VISUAL_CSS=VISUAL_CSS,SCRIPT='',img_logo=lambda size:'')
    shop_page=main_function('pagina_loja',env)
    rows=[dict(data=(TODAY-datetime.timedelta(days=i)).isoformat(),gasto=80+i*4,faturamento=650+i*81,impressoes=5800+i*400,cliques=102+i*11,atualizado_em=int(time.time())) for i in range(7)]
    campaigns=[dict(campanha_id='a',nome='KIT <5>',status='active',orcamento=100,roas_objetivo=4,gasto_periodo=560,fat_periodo=4800,gasto_hoje=120,hoje_atualizado=int(time.time()),gasto_ontem=80,fat_ontem=600,tem_ontem=1),
               dict(campanha_id='b',nome='Coleção verão',status='active',orcamento=200,roas_objetivo=6,gasto_periodo=320,fat_periodo=1900,gasto_hoje=80,hoje_atualizado=int(time.time()),gasto_ontem=70,fat_ontem=0,tem_ontem=1)]
    for campaign in campaigns:
        campaign.update((campaign_updates or {}).get(campaign['campanha_id'], {}))
    def query(conn,sql,params):
        if 'FROM conexoes' in sql:return [dict(id=1,cliente='Loja de demonstração')]
        if 'FROM ads_dia' in sql:return [] if empty else rows
        if 'AS dias_atual' in sql:return []  # No comparison coverage in this visual fixture.
        if 'FROM ads_campanha_dia' in sql:return [] if empty else campaigns
        raise AssertionError(sql)
    app=Flask('ads-design-preview')
    namespace=dict(datetime=datetime,json=json,time=time,esc=html.escape,request=request,app=app,
        pode_ver_loja=lambda cid:cid==1,banco=lambda:contextlib.nullcontext(None),consultar=query,
        pagina_loja=shop_page,pagina=lambda title,body:body)
    route=main_function('painel_ads',namespace)
    overview=dict(reports=[dict(current=dict(complete=True,invalid=[],unallocated_dates=[],revenue=12000))])
    with app.test_request_context('/ads/1?dias=7'+args),patch('sales_metrics.reporting_today',return_value=TODAY),patch('overview.load_overview',return_value=overview):
        return route(1)


if __name__=='__main__':
    output=Path('visual-qa');output.mkdir(exist_ok=True)
    for name,kwargs in [('ads-overview',{}),('ads-overview-empty',dict(empty=True)),('ads-overview-filtered',dict(args='&campanha=inexistente')),('ads-overview-client',dict(admin=False))]:
        result=render_fixture(**kwargs)
        assert isinstance(result,str),result
        (output/(name+'.html')).write_text(result,encoding='utf-8')
    print('Real Ads route rendered with synthetic store data.')
