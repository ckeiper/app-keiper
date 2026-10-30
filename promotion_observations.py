"""Append-only per-item promotion readings, never inferred participation periods."""
import hashlib
import json
from datetime import datetime,time,timedelta
from sales_metrics import SAO_PAULO


def init_schema(conn,execute):
    execute(conn,'SELECT pg_advisory_xact_lock(186144281)')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_promotion_readings(
        id BIGSERIAL PRIMARY KEY,conexao_id INTEGER NOT NULL,item_id TEXT NOT NULL,
        observed_at BIGINT NOT NULL,available BOOLEAN NOT NULL,reason TEXT NOT NULL,
        promotions JSONB NOT NULL,payload_hash TEXT NOT NULL,
        UNIQUE(conexao_id,item_id,observed_at,payload_hash))''')
    execute(conn,'''CREATE INDEX IF NOT EXISTS listing_promotion_readings_scope
        ON listing_promotion_readings(conexao_id,item_id,observed_at DESC,id DESC)''')


def snapshot(snap):
    stamp=snap.get('attempted_at') if snap.get('error') else snap.get('checked_at')
    if type(stamp) is not int or not 0<stamp<253402300799:return None
    if snap.get('error'):return dict(observed_at=stamp,available=False,reason='consulta_indisponivel',promotions=[])
    if snap.get('not_applicable'):return dict(observed_at=stamp,available=False,reason='nao_aplicavel',promotions=[])
    source=snap.get('promotions')
    if not isinstance(source,list) or len(source)>200:return dict(observed_at=stamp,available=False,reason='resposta_nao_verificavel',promotions=[])
    output=[]
    def short(v):
        return str(v)[:250] if isinstance(v,(str,int,float)) and not isinstance(v,bool) else None
    for row in source:
        if not isinstance(row,dict):return dict(observed_at=stamp,available=False,reason='resposta_nao_verificavel',promotions=[])
        raw=row.get('raw') if isinstance(row.get('raw'),dict) else {}
        output.append(dict(id=short(row.get('id')),type=short(row.get('type')),status=short(row.get('status')),
            start=short(row.get('start')),end=short(row.get('end')),price=short(row.get('price')),
            original=short(row.get('original')),variation_id=(short(row.get('variation_id')) or 'nao_verificavel') if row.get('variation_id') is not None else None,name=short(raw.get('name')),
            conditions={k:short(raw.get(k)) for k in ('offer_id','meli_percentage','seller_percentage','top_deal_price','sub_type') if raw.get(k) is not None}))
    return dict(observed_at=stamp,available=True,reason='consulta_item',promotions=output)


def record(conn,execute,cid,item,snap):
    data=snapshot(snap)
    if data is None:return
    # Preserve every condition/error transition and one unchanged reading per local day.
    # This keeps evidence without copying identical offer lists on every refresh.
    state={k:v for k,v in data.items() if k!='observed_at'}
    encoded=json.dumps(state,ensure_ascii=False,sort_keys=True,allow_nan=False)
    day_floor=int(datetime.fromtimestamp(data['observed_at'],SAO_PAULO).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
    digest=hashlib.sha256(encoded.encode()).hexdigest()
    execute(conn,'''INSERT INTO listing_promotion_readings(conexao_id,item_id,observed_at,available,reason,promotions,payload_hash)
        SELECT %s,%s,%s,%s,%s,%s::jsonb,%s WHERE NOT EXISTS (
            SELECT 1 FROM (SELECT payload_hash,observed_at FROM listing_promotion_readings
                WHERE conexao_id=%s AND item_id=%s ORDER BY observed_at DESC,id DESC LIMIT 1) last_reading
            WHERE last_reading.payload_hash=%s AND last_reading.observed_at >= %s
                AND last_reading.observed_at <= %s)
        ON CONFLICT(conexao_id,item_id,observed_at,payload_hash) DO NOTHING''',
        (cid,item,data['observed_at'],data['available'],data['reason'],json.dumps(data['promotions'],ensure_ascii=False),digest,
         cid,item,digest,day_floor,data['observed_at']))


def timestamp(raw):
    if not isinstance(raw,str) or len(raw)>80:return None
    try:
        value=datetime.fromisoformat(raw.replace('Z','+00:00'))
        return value.astimezone(SAO_PAULO) if value.tzinfo is not None else None
    except (ValueError,TypeError,OverflowError):return None


def periods(promotion,today,days=7):
    if type(days) is not int or days not in (7,30):return dict(available=False,reason='Selecione 7 ou 30 dias.')
    if promotion.get('type') not in ('PRICE_DISCOUNT','SELLER_CAMPAIGN','DEAL','MARKETPLACE_CAMPAIGN','DOD','LIGHTNING','SMART','PRICE_MATCHING','PRE_NEGOTIATED','UNHEALTHY_STOCK'):
        return dict(available=False,reason='Tipo de oferta sem regra de comparação por calendário validada; condições por quantidade, cupom ou pagamento não serão presumidas.')
    if promotion.get('variation_id') is not None:return dict(available=False,reason='Oferta por variação: não há vínculo de vendas por variação validado nesta comparação.')
    if promotion.get('status') not in ('active','started'):return dict(available=False,reason='A consulta selecionada não registrou participação ativa do item. Finished pode indicar remoção; candidato ou agendado não comprova participação.')
    start,end=timestamp(promotion.get('start')),timestamp(promotion.get('end'))
    if not start or not end:return dict(available=False,reason='Datas ausentes, inválidas ou sem fuso explícito: o intervalo não será presumido.')
    if end<=start:return dict(available=False,reason='Intervalo informado pela API inválido.')
    if start.date()<today-timedelta(days=366):return dict(available=False,reason='Comparação fora da janela permitida de 366 dias.')
    if start.date()>=today:return dict(available=False,reason='Aguardando dias inteiros encerrados dentro do calendário informado.')
    first=start.date()
    if start>datetime.combine(first,time.min,SAO_PAULO):first+=timedelta(days=1)
    last=first+timedelta(days=days-1)
    if datetime.combine(last+timedelta(days=1),time.min,SAO_PAULO)>end:
        return dict(available=False,reason='O calendário informado não contém '+str(days)+' dias inteiros para uma comparação equivalente.')
    if last>=today:return dict(available=False,reason='Aguardando '+str(days)+' dias inteiros encerrados dentro do calendário informado.')
    previous_end=start.date()-timedelta(days=1);previous_start=previous_end-timedelta(days=days-1)
    if previous_start<today-timedelta(days=366):return dict(available=False,reason='Comparação fora da janela permitida de 366 dias.')
    return dict(available=True,start=first,end=last,previous_start=previous_start,previous_end=previous_end,
                source_start=start,source_end=end,days=days)
