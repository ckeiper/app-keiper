"""Versioned, tenant-scoped kit compositions and explicitly hypothetical economics."""
import hashlib
import json
import re
from datetime import date,timedelta
from decimal import Decimal,ROUND_HALF_UP
from profitability_scenarios import number
from listing_priority_sources import listing_signals
from listing_sales import listing_sales_summary

COSTS={'price':'Preço de venda de um kit','fee_pct':'Tarifa percentual (%)','fixed_fee':'Tarifa fixa por kit',
       'tax_pct':'Impostos (%)','shipping':'Frete do vendedor por kit','ads':'Publicidade por kit',
       'packaging':'Embalagem por kit','adjustments':'Outros custos por kit'}
CENT=Decimal('.01')


def init_schema(conn,execute):
    execute(conn,'SELECT pg_advisory_xact_lock(186144280)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_kit_analyses(
        id BIGSERIAL PRIMARY KEY,conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,
        composition JSONB NOT NULL,created_by INTEGER NOT NULL,created_at BIGINT NOT NULL,
        submission_key TEXT NOT NULL,payload_hash TEXT NOT NULL,
        UNIQUE(conexao_id,item_id,submission_key))''')
    execute(conn,'''CREATE INDEX IF NOT EXISTS listing_kit_analyses_scope
        ON listing_kit_analyses(conexao_id,item_id,id DESC)''')


def validate(form,today):
    if form.get('confirmed')!='yes':raise ValueError('Confirme a composição e as fontes das premissas informadas.')
    mode=form.get('mode')
    if mode not in ('proposal','existing'):raise ValueError('Identifique se é uma proposta ou um kit existente.')
    key=str(form.get('submission_key',''))
    if not re.fullmatch(r'[A-Za-z0-9_-]{24,80}',key):raise ValueError('Formulário expirado. Recarregue a análise.')
    source=str(form.get('source','')).strip()
    if not 10<=len(source)<=500:raise ValueError('Descreva a referência da composição e dos custos gerais (10 a 500 caracteres).')
    try:source_date=date.fromisoformat(form.get('source_date',''))
    except (ValueError,TypeError):raise ValueError('Informe uma data válida para as referências.') from None
    if source_date>today:raise ValueError('A data das referências não pode estar no futuro.')
    days=str(form.get('days',''))
    if days not in ('7','30'):raise ValueError('Selecione 7 ou 30 dias encerrados para o histórico.')
    components=[];seen=set();linked=set()
    for i in range(5):
        values={k:str(form.get(k+'_'+str(i),'')).strip() for k in ('label','item','qty','cost','reference')}
        if not any(values.values()):continue
        if not 3<=len(values['label'])<=100:raise ValueError('Identifique cada componente com 3 a 100 caracteres.')
        if not re.fullmatch(r'[1-9][0-9]{0,3}',values['qty']):raise ValueError('Use de 1 a 9.999 unidades inteiras por componente.')
        if values['label'].casefold() in seen:raise ValueError('Componente repetido: consolide a quantidade em uma linha.')
        seen.add(values['label'].casefold())
        iid=values['item'].upper()
        if iid and (not re.fullmatch(r'MLB[0-9]{1,20}',iid) or iid in linked):raise ValueError('Vínculo de anúncio inválido ou repetido entre os componentes.')
        if iid:linked.add(iid)
        if not 10<=len(values['reference'])<=300:raise ValueError('Informe a fonte do custo unitário de cada componente (10 a 300 caracteres).')
        cost=number(values['cost'],'o custo unitário do componente')
        components.append(dict(label=values['label'],item=iid or None,qty=int(values['qty']),cost=str(cost),reference=values['reference']))
    if not components or sum(c['qty'] for c in components)<2:raise ValueError('Um kit precisa de pelo menos duas unidades na composição.')
    costs={k:str(number(form.get(k),label,Decimal('100') if k.endswith('_pct') else Decimal('999999.99'))) for k,label in COSTS.items()}
    if Decimal(costs['price'])<=0:raise ValueError('Informe preço de venda do kit maior que zero.')
    end=today-timedelta(days=1);start=end-timedelta(days=int(days)-1)
    return dict(mode=mode,source=source,source_date=source_date.isoformat(),days=int(days),start=start.isoformat(),end=end.isoformat(),components=components,costs=costs),key


def economics(composition):
    costs={k:Decimal(v) for k,v in composition['costs'].items()}
    product=sum((Decimal(c['cost'])*c['qty'] for c in composition['components']),Decimal(0))
    fees=(costs['price']*costs['fee_pct']/100).quantize(CENT,rounding=ROUND_HALF_UP)+costs['fixed_fee']
    taxes=(costs['price']*costs['tax_pct']/100).quantize(CENT,rounding=ROUND_HALF_UP)
    total=product+fees+taxes+sum(costs[k] for k in ('shipping','ads','packaging','adjustments'))
    value=costs['price']-total
    return dict(price=costs['price'],products=product,fees=fees,taxes=taxes,total=total,contribution=value,margin=value*100/costs['price'])


def check_links(composition,rows,kit_item):
    known={r['item_id'] for r in rows}
    for component in composition['components']:
        if component['item'] and (component['item']==kit_item or component['item'] not in known):
            raise ValueError('Há componente não encontrado nesta loja ou vinculado ao próprio anúncio do kit.')


def save(conn,query,cid,item,composition,key,actor,now):
    payload=json.dumps(composition,sort_keys=True,ensure_ascii=False)
    digest=hashlib.sha256(payload.encode()).hexdigest()
    rows=query(conn,'''INSERT INTO listing_kit_analyses(conexao_id,item_id,composition,created_by,created_at,submission_key,payload_hash)
        VALUES(%s,%s,%s::jsonb,%s,%s,%s,%s) ON CONFLICT(conexao_id,item_id,submission_key) DO NOTHING RETURNING id''',
        (cid,item,payload,actor,now,key,digest))
    if rows:return rows[0]['id']
    old=query(conn,'''SELECT id,payload_hash FROM listing_kit_analyses
        WHERE conexao_id=%s AND item_id=%s AND submission_key=%s''',(cid,item,key))
    if not old or old[0]['payload_hash']!=digest:raise ValueError('Este formulário já foi usado com outros valores. Recarregue para criar outra versão.')
    return old[0]['id']


def evidence(composition,context,rows,kit_item,start,end,now):
    readings=listing_signals(rows,{},1,now=now)
    capacity=[];components=[]
    for component in composition['components']:
        iid=component['item'];signal=readings.get(iid,{})
        valid=bool(signal.get('stock_verified'))
        if not valid:capacity=None
        elif capacity is not None:capacity.append(int(signal['stock'])//component['qty'])
        report=listing_sales_summary(context['orders'],context['items'],context['coverage'],iid,end=end,days=(end-start).days+1) if iid else None
        if report and context['pending']:report.update(orders=None,units=None,gross_items=None,reason='Há pedidos antigos não verificados nesta loja.')
        components.append(dict(component=component,stock=signal.get('stock') if valid else None,sales=report))
    actual=listing_sales_summary(context['orders'],context['items'],context['coverage'],kit_item,end=end,days=(end-start).days+1)
    if context['pending']:actual.update(orders=None,units=None,gross_items=None,reason='Há pedidos antigos não verificados nesta loja.')
    return dict(components=components,capacity=min(capacity) if capacity else None,sales=actual)
