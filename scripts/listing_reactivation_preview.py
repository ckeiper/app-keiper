import sys
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog_preview import page,dest
from test_listing_reactivation import fixture,DAY,NOW
from listing_reactivation import render
from datetime import datetime, timezone
for mode in ('paused','active','stale','tasks','history','official','unknown','empty','error','moderation','moderation-empty','moderation-error','moderation-partial','account-allowed','account-blocked','account-unknown'):
    d=fixture()
    if mode=='active':d['shop']['status']='active'
    if mode=='stale':d['shop']['atualizado_em']=1
    if mode=='tasks':d.update(tasks=[dict(id=i,responsible='Equipe',due_date=DAY,status='open',description='Conferir o motivo informado no marketplace.') for i in range(1,11)],total=15,pages=2)
    if mode=='history':d['events']=[dict(before_value='paused',after_value='active',previous_at=NOW-60,observed_at=NOW)]
    official=None
    if mode in ('official','unknown','empty','error'):
        official=dict(state='read',checked_at=datetime.now(timezone.utc),status='paused',codes=['out_of_stock','<script>'])
        if mode=='unknown':official['codes']=None
        if mode=='empty':official['codes']=[]
        if mode=='error':official.update(state='unknown',message='Limite de consultas atingido.')
    if mode.startswith('moderation'):
        from listing_moderation import normalize
        from test_listing_moderation import sample
        official=dict(state='read',checked_at=datetime.now(timezone.utc),status='paused',codes=[])
        official['moderation']=normalize(sample())
        if mode=='moderation-empty':official['moderation']=normalize([])
        if mode=='moderation-error':official['moderation']=dict(state='unknown',message='Limite de consultas atingido.')
        if mode=='moderation-partial':official['moderation']=normalize([dict(name='CODIGO_NOVO',wordings=[dict(type='REASON',value='x'*3000),None])]*11)
    if mode.startswith('account-'):
        from listing_account_permission import normalize
        allow={'account-allowed':True,'account-blocked':False,'account-unknown':'false'}[mode]
        official=dict(state='read',checked_at=datetime.now(timezone.utc),status='paused',codes=[],account_permission=normalize(dict(status=dict(list=dict(allow=allow,codes=['rejected_by_regulations','<script>'] if mode=='account-blocked' else [])))))
    (dest/('listing-reactivation-'+mode+'.html')).write_text(page('Revisão de reativação',1,'Loja fictícia','anuncios','<p>Dados fictícios de teste.</p>'+render(1,'MLB1',d,DAY,NOW,'token',official=official)))
