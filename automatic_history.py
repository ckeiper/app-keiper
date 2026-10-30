"""Automatic observed changes; no API calls, inferred execution time or actor."""
import json
from decimal import Decimal
from html import escape

FIELDS = {
 'titulo':('Título','conteudo'), 'fotos':('Fotos (imagens ou ordem)','conteudo'),
 'video':('Vídeo','conteudo'), 'status':('Status do anúncio','outro'),
 'disponibilidade':('Disponibilidade do anúncio','full'),
 'logistica':('Modalidade logística','entrega'), 'frete_gratis':('Frete grátis anunciado','entrega'),
 'preco_final':('Preço final público','preco'), 'promocao':('Promoção pública confirmada','preco'),
 'full':('Disponibilidade no Full','full'),
}


def init_schema(conn, execute):
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_change_baselines (
        conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        item_id TEXT NOT NULL, stream TEXT NOT NULL, observed_at BIGINT NOT NULL,
        payload JSONB NOT NULL, PRIMARY KEY(conexao_id,item_id,stream))''')
    execute(conn,'''CREATE TABLE IF NOT EXISTS listing_change_events (
        id BIGSERIAL PRIMARY KEY,
        conexao_id INTEGER NOT NULL REFERENCES conexoes(id) ON DELETE CASCADE,
        item_id TEXT NOT NULL, stream TEXT NOT NULL, field TEXT NOT NULL,
        event_date DATE NOT NULL, kind TEXT NOT NULL, note TEXT NOT NULL,
        previous_at BIGINT NOT NULL, observed_at BIGINT NOT NULL,
        before_value JSONB NOT NULL, after_value JSONB NOT NULL,
        UNIQUE(conexao_id,item_id,stream,field,observed_at))''')
    execute(conn,'''CREATE INDEX IF NOT EXISTS listing_change_events_item_date
        ON listing_change_events(conexao_id,item_id,event_date DESC,id DESC)''')
    # INSERT first serializes a new baseline too; FOR UPDATE serializes later
    # collectors. Strict timestamps prevent stale/replayed observations rewriting it.
    execute(conn,'''CREATE OR REPLACE FUNCTION public.record_listing_changes(
        cid INTEGER, item TEXT, channel TEXT, stamp BIGINT, snapshot JSONB)
        RETURNS VOID LANGUAGE plpgsql AS $body$
        DECLARE old RECORD; entry RECORD;
        BEGIN
          INSERT INTO public.listing_change_baselines(conexao_id,item_id,stream,observed_at,payload)
            VALUES(cid,item,channel,stamp,snapshot) ON CONFLICT DO NOTHING;
          SELECT * INTO old FROM public.listing_change_baselines
            WHERE conexao_id=cid AND item_id=item AND stream=channel FOR UPDATE;
          IF stamp <= old.observed_at THEN RETURN; END IF;
          FOR entry IN SELECT key,value FROM jsonb_each(snapshot) LOOP
            IF old.payload ? entry.key
              AND old.payload->entry.key->'value' IS NOT NULL
              AND old.payload->entry.key->'value' <> 'null'::jsonb
              AND entry.value->'value' IS NOT NULL
              AND entry.value->'value' <> 'null'::jsonb
              AND old.payload->entry.key->'value' IS DISTINCT FROM entry.value->'value' THEN
              INSERT INTO public.listing_change_events
                (conexao_id,item_id,stream,field,event_date,kind,note,previous_at,observed_at,before_value,after_value)
              VALUES(cid,item,channel,entry.key,(to_timestamp(stamp) AT TIME ZONE 'America/Sao_Paulo')::date,
                entry.value->>'kind',(entry.value->>'label')||' alterado nas coletas.',
                old.observed_at,stamp,old.payload->entry.key->'value',entry.value->'value')
              ON CONFLICT DO NOTHING;
            END IF;
          END LOOP;
          UPDATE public.listing_change_baselines SET observed_at=stamp,payload=snapshot
            WHERE conexao_id=cid AND item_id=item AND stream=channel;
        END $body$''')


def record(conn, execute, cid, item_id, stream, stamp, values):
    if type(stamp) is not int or stamp<=0:
        return
    payload={key:dict(value=value,label=FIELDS[key][0],kind=FIELDS[key][1])
             for key,value in values.items() if key in FIELDS}
    execute(conn,'SELECT public.record_listing_changes(%s,%s,%s,%s,%s::jsonb)',
            (cid,item_id,stream,stamp,json.dumps(payload,ensure_ascii=False)))


def listing_values(item, seller_id):
    if str(item.get('seller_id')) != str(seller_id):
        return {key:None for key in ('titulo','fotos','video','status','disponibilidade','logistica','frete_gratis')}
    photos=item.get('pictures')
    ids=([p['id'] for p in photos] if isinstance(photos,list) and
         all(isinstance(p,dict) and isinstance(p.get('id'),str) and p['id'] for p in photos) else None)
    shipping=item.get('shipping') if isinstance(item.get('shipping'),dict) else {}
    qty=item.get('available_quantity')
    return dict(titulo=item.get('title') if isinstance(item.get('title'),str) and item['title'].strip() else None,
        fotos=ids,video=item.get('video_id') if isinstance(item.get('video_id'),str) else None,
        status=item.get('status') if item.get('status') in ('active','paused','closed','under_review','inactive') else None,
        disponibilidade=('com estoque' if qty>0 else 'zerado') if type(qty) is int and qty>=0 else None,
        logistica=shipping.get('logistic_type') if isinstance(shipping.get('logistic_type'),str) and shipping['logistic_type'] else None,
        frete_gratis=shipping.get('free_shipping') if type(shipping.get('free_shipping')) is bool else None)


def full_values(result):
    return dict(full=result.get('state') if result.get('logistics')=='fulfillment' and result.get('state') in ('available','empty') else None)


def value_text(field,value):
    if field=='preco_final':
        from sales_drivers import money
        return money(Decimal(str(value)))
    if isinstance(value,bool):
        return 'Sim' if value else 'Não'
    if field=='fotos':
        return str(len(value))+' foto(s)' if isinstance(value,list) else 'Não confirmado'
    if field=='video':
        return 'Com vídeo' if value else 'Sem vídeo'
    return {'available':'Com estoque','empty':'Zerado','active':'Ativo','paused':'Pausado',
            'closed':'Encerrado','under_review':'Em análise','fulfillment':'Full'}.get(str(value),str(value))


def detail_html(row):
    if row.get('source')!='automatic':
        return ''
    from datetime import datetime
    from listing_interventions import BR
    out="<p class='iv-status'><b>Antes:</b> "+escape(value_text(row['field'],row['before_value']))+'<br><b>Depois:</b> '+escape(value_text(row['field'],row['after_value']))+'</p>'
    if row['field']=='fotos':
        out+='<p class="iv-meta">O conjunto ou a ordem das imagens mudou; a quantidade de fotos pode continuar igual.</p>'
    if row['field']=='video' and row['before_value'] and row['after_value']:
        out+='<p class="iv-meta">O identificador do vídeo mudou entre as consultas.</p>'
    out+='<p class="iv-meta">Observado entre '+datetime.fromtimestamp(row['previous_at'],BR).strftime('%d/%m/%Y %H:%M')+' e '+datetime.fromtimestamp(row['created_at'],BR).strftime('%d/%m/%Y %H:%M')+'. A data usada na comparação é a detecção; não identifica o horário exato nem o autor da alteração.</p>'
    return out


# Same history and comparison UI, with automatic entries always read-only.
HISTORY = """(SELECT id,conexao_id,item_id,event_date,kind,note,created_at,void_at,
    'manual'::text AS source,NULL::text AS field,NULL::bigint AS previous_at,
    NULL::jsonb AS before_value,NULL::jsonb AS after_value FROM listing_interventions
    UNION ALL SELECT id,conexao_id,item_id,event_date,kind,note,observed_at AS created_at,
    NULL::bigint AS void_at,'automatic'::text AS source,field,previous_at,before_value,after_value
    FROM listing_change_events) history"""


def seed_existing(conn, execute):
    """Reuse two weeks of actual observations; never reconstruct old listing edits."""
    execute(conn,'''DO $seed$ BEGIN
      IF NOT EXISTS(SELECT 1 FROM public.listing_change_events) THEN
        INSERT INTO public.listing_change_events
          (conexao_id,item_id,stream,field,event_date,kind,note,previous_at,observed_at,before_value,after_value)
        SELECT conexao_id,item_id,'price',field,(to_timestamp(observed_at) AT TIME ZONE 'America/Sao_Paulo')::date,
          'preco',label||' alterado nas coletas.',previous_at,observed_at,before_value,after_value
        FROM (
          SELECT *,lag(observed_at) OVER w AS previous_at,
            lag(confirmed) OVER w AS was_confirmed,lag(price) OVER w AS old_price,
            lag(promotion) OVER w AS old_promo
          FROM public.listing_offer_observations
          WHERE observed_at >= extract(epoch from now())::bigint-14*86400
          WINDOW w AS (PARTITION BY conexao_id,item_id ORDER BY observed_at)
        ) p CROSS JOIN LATERAL (VALUES
          ('preco_final','Preço final público',to_jsonb(old_price::text),to_jsonb(price::text)),
          ('promocao','Promoção pública confirmada',to_jsonb(old_promo),to_jsonb(promotion))
        ) v(field,label,before_value,after_value)
        WHERE confirmed AND was_confirmed AND before_value IS NOT NULL AND after_value IS NOT NULL
          AND before_value IS DISTINCT FROM after_value ON CONFLICT DO NOTHING;
        INSERT INTO public.listing_change_events
          (conexao_id,item_id,stream,field,event_date,kind,note,previous_at,observed_at,before_value,after_value)
        SELECT p.conexao_id,item_id,'full','full',(to_timestamp(observed_at) AT TIME ZONE 'America/Sao_Paulo')::date,
          'full','Disponibilidade no Full alterado nas coletas.',previous_at,observed_at,to_jsonb(old_state),to_jsonb(state)
        FROM (
          SELECT f.*,lag(observed_at) OVER w AS previous_at,lag(state) OVER w AS old_state,lag(logistics) OVER w AS old_logistics
          FROM public.full_observations f JOIN public.conexoes c ON c.id=f.conexao_id
          WHERE observed_at >= extract(epoch from now())::bigint-14*86400
          WINDOW w AS (PARTITION BY f.conexao_id,item_id ORDER BY observed_at)
        ) p WHERE logistics='fulfillment' AND old_logistics='fulfillment'
          AND state IN ('available','empty') AND old_state IN ('available','empty') AND state<>old_state
        ON CONFLICT DO NOTHING;
      END IF;
    END $seed$''')
    execute(conn,'''INSERT INTO public.listing_change_baselines(conexao_id,item_id,stream,observed_at,payload)
      SELECT DISTINCT ON(conexao_id,item_id) conexao_id,item_id,'price',observed_at,
        jsonb_build_object('preco_final',jsonb_build_object('value',CASE WHEN confirmed THEN price::text END,'label','Preço final público','kind','preco'),
        'promocao',jsonb_build_object('value',CASE WHEN confirmed THEN promotion END,'label','Promoção pública confirmada','kind','preco'))
      FROM public.listing_offer_observations ORDER BY conexao_id,item_id,observed_at DESC
      ON CONFLICT DO NOTHING''')
    execute(conn,'''INSERT INTO public.listing_change_baselines(conexao_id,item_id,stream,observed_at,payload)
      SELECT DISTINCT ON(f.conexao_id,item_id) f.conexao_id,item_id,'full',observed_at,
        jsonb_build_object('full',jsonb_build_object('value',CASE WHEN logistics='fulfillment' AND state IN ('available','empty') THEN state END,
          'label','Disponibilidade no Full','kind','full'))
      FROM public.full_observations f JOIN public.conexoes c ON c.id=f.conexao_id
      ORDER BY f.conexao_id,item_id,observed_at DESC ON CONFLICT DO NOTHING''')
    execute(conn,'''INSERT INTO public.listing_change_baselines(conexao_id,item_id,stream,observed_at,payload)
      SELECT a.conexao_id,a.item_id,'listing',a.atualizado_em,
        jsonb_build_object('titulo',jsonb_build_object('value',CASE WHEN btrim(a.titulo)<>'' THEN a.titulo END,'label','Título','kind','conteudo'),
          'status',jsonb_build_object('value',CASE WHEN a.status IN ('active','paused','closed','under_review','inactive') THEN a.status END,'label','Status do anúncio','kind','outro'),
          'disponibilidade',jsonb_build_object('value',CASE WHEN a.quantidade>0 THEN 'com estoque' WHEN a.quantidade=0 THEN 'zerado' END,'label','Disponibilidade do anúncio','kind','full'))
      FROM public.anuncios a JOIN public.conexoes c ON c.id=a.conexao_id
      WHERE a.atualizado_em>0 AND a.item_id IS NOT NULL ON CONFLICT DO NOTHING''')
