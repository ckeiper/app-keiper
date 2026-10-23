"""Render the real shell with explicitly synthetic KYRA fixtures, no database."""
import ast
import html
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keiper_ai import recommendations, render
from test_listing_details import main_function
from visual_theme import VISUAL_CSS


def preview(kind='ready'):
    today = date(2026,10,23)
    rows = [dict(data=(today-timedelta(days=i)).isoformat(), gasto=45+i*3,
                 faturamento=[460,590,410,730,480,615,520,810,880,790,930,890,1020,970][i-1],
                 atualizado_em=1792760000) for i in range(1,15)]
    report = dict(eligible=True,reasons=[],current=dict(revenue=1600,orders=40),previous=dict(revenue=3400,orders=80))
    result = recommendations(report,rows,today,1792760000)
    if kind=='quality':
        result = recommendations(dict(report,eligible=False,reasons=['Erro de sincronização sem resolução confirmada']),[],today,1792760000)
        rows=[]
    if kind=='empty':
        result=None;rows=[]
    if kind=='clean':
        result=dict(result, recommendations=[],quality=[])
    budget=dict(used=Decimal('0'),limit=Decimal('50'),alert='Dentro do limite.',blocked=False)
    from test_kyra_campaigns import CampaignRulesTests
    campaign_fixture=CampaignRulesTests();campaign_fixture.setUp()
    campaign_fixture.add('waste',revenue=0)
    campaign_fixture.add('drop',revenue=600,old_revenue=1400)
    campaign_fixture.add('scale',revenue=1500,old_revenue=1400,sales=5)
    campaign_result=campaign_fixture.result()
    if kind=='quality':
        campaign_fixture.rows=[];campaign_result=campaign_fixture.result()
    if kind=='clean':
        campaign_result=dict(campaign_result,recommendations=[],flagged=0)
    campaign_run=dict(day=today,status='completed',result=campaign_result) if kind!='empty' else None
    body="<p style='color:#a8b0c6;font-size:11px'>PRÉVIA DE DESIGN · DADOS FICTÍCIOS PARA TESTE</p>"+render(result,today,'completed' if result else None,'desabilitada',budget,cid=1,daily=rows,campaign_run=campaign_run)
    tree=ast.parse(Path('main.py').read_text(encoding='utf-8'))
    css=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CSS' for t in n.targets))
    env=dict(session={'tipo':'admin'},esc=html.escape,CSS=css,VISUAL_CSS=VISUAL_CSS,SCRIPT='',img_logo=lambda size:'')
    return main_function('pagina_loja',env)('KYRA',1,'Loja de demonstração','ia',body)


if __name__=='__main__':
    target=Path('visual-qa');target.mkdir(exist_ok=True)
    for kind in ('ready','empty','quality','clean'):
        (target/('kyra-'+kind+'.html')).write_text(preview(kind),encoding='utf-8')
    print('KYRA previews rendered with synthetic data only.')
