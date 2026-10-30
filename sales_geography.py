"""Minimal destination collection: only UF and collection evidence, never addresses."""
import time
from sales_metrics import amount, created_day

STATES = dict(AC='Acre',AL='Alagoas',AP='Amapá',AM='Amazonas',BA='Bahia',CE='Ceará',DF='Distrito Federal',ES='Espírito Santo',GO='Goiás',MA='Maranhão',MT='Mato Grosso',MS='Mato Grosso do Sul',MG='Minas Gerais',PA='Pará',PB='Paraíba',PR='Paraná',PE='Pernambuco',PI='Piauí',RJ='Rio de Janeiro',RN='Rio Grande do Norte',RS='Rio Grande do Sul',RO='Rondônia',RR='Roraima',SC='Santa Catarina',SP='São Paulo',SE='Sergipe',TO='Tocantins')
API='https://api.mercadolibre.com'


def init_schema(conn, execute):
    execute(conn, '''CREATE TABLE IF NOT EXISTS vendas_destinos (
        conexao_id INTEGER NOT NULL, pedido_id TEXT NOT NULL,
        uf TEXT, motivo TEXT NOT NULL, tentado_em BIGINT NOT NULL,
        verificado_em BIGINT, PRIMARY KEY(conexao_id,pedido_id))''')


def destination(payload, seller):
    if isinstance(payload,dict):
        payload=payload.get('shipments')
    if not isinstance(payload,list) or not payload:
        return None, 'sem_envio'
    states=[]
    for shipment in payload:
        if not isinstance(shipment,dict):return None,'resposta_invalida'
        if shipment.get('type')!='forward' or shipment.get('status')=='cancelled':continue
        if str(shipment.get('sender_id'))!=str(seller):return None,'vendedor_nao_confirmado'
        dest=shipment.get('destination')
        if dest is not None and not isinstance(dest,dict):return None,'resposta_invalida'
        address=(dest or {}).get('shipping_address') or shipment.get('receiver_address')
        if not isinstance(address,dict):return None,'destino_indisponivel'
        country=address.get('country') or {}; state=address.get('state') or {}
        if not isinstance(country,dict) or not isinstance(state,dict):return None,'destino_indisponivel'
        code=state.get('id')
        if country.get('id')!='BR' or not isinstance(code,str) or not code.startswith('BR-') or code[3:] not in STATES:
            return None,'uf_nao_confirmada'
        states.append(code[3:])
    if not states:return None,'sem_envio_valido'
    if len(set(states))!=1:return None,'destinos_divergentes'
    return states[0],'confirmado'


def sync(cid, token, seller, bank, query, execute, get, now=None):
    """At most nine requests / 40 seconds per existing store-locked sales job.

    Confirmed destinations are rechecked after 30 days; unknown ones after a day.
    The oldest attempts are processed first so repeated API failures cannot starve
    the remaining historical orders. Nothing runs during a dashboard GET.
    """
    now=int(time.time()) if now is None else now
    deadline=time.monotonic()+40
    headers={'Authorization':'Bearer '+token,'X-New-Domain':'true','x-format-new':'true'}
    def read(path,params=None):
        response=get(API+path,headers=headers,params=params,timeout=(3,6),allow_redirects=False)
        return response.status_code, response.json() if response.status_code==200 else None
    try:status,account=read('/users/me')
    except (ValueError,TypeError,OSError):return False
    except Exception:return False
    if status!=200 or not isinstance(account,dict) or str(account.get('id'))!=str(seller):return False
    with bank() as conn:
        rows=query(conn,'''SELECT p.pedido_id FROM pedidos p
            LEFT JOIN vendas_destinos d ON d.conexao_id=p.conexao_id AND d.pedido_id=p.pedido_id
            WHERE p.conexao_id=%s AND p.status='paid' AND p.vendas_verificado_em IS NOT NULL
              AND (d.pedido_id IS NULL OR d.tentado_em < %s - CASE WHEN d.uf IS NULL THEN 86400 ELSE 2592000 END)
            ORDER BY COALESCE(d.tentado_em,0),p.criado_em DESC,p.pedido_id LIMIT 8''',(cid,now))
    for row in rows[:8]:
        if time.monotonic()+9>deadline:break
        oid=str(row['pedido_id'])
        if not oid.isascii() or not oid.isdigit() or len(oid)>25:continue
        status=0
        try:
            status,payload=read('/orders/'+oid+'/shipments',{'views':'destination'})
            uf,reason=destination(payload,seller) if status==200 else (None,'consulta_indisponivel')
        except Exception:uf,reason=None,'consulta_indisponivel'
        with bank() as conn:
            execute(conn,'''INSERT INTO vendas_destinos(conexao_id,pedido_id,uf,motivo,tentado_em,verificado_em)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(conexao_id,pedido_id) DO UPDATE SET
                uf=EXCLUDED.uf,motivo=EXCLUDED.motivo,tentado_em=EXCLUDED.tentado_em,verificado_em=EXCLUDED.verificado_em''',
                (cid,oid,uf,reason,now,now if uf else None))
        if status in (401,403,429):break
    return True


def summarize(rows,start,end,covered):
    result={uf:dict(orders=0,revenue=amount(0),units=0,unknown_units=0) for uf in STATES}
    missing=dict(orders=0,revenue=amount(0),units=0,unknown_units=0)
    seen=set(); invalid=0; unlocated=0
    for row in rows:
        oid=str(row['pedido_id'])
        if oid in seen:continue
        seen.add(oid)
        day=created_day(row.get('criado_em'))
        if day is None:unlocated+=1;continue
        if not start<=day<=end or row.get('status')!='paid':continue
        payments=row.get('pagamentos_json')
        if not isinstance(payments,list) or not payments or any(not isinstance(p,dict) or not p.get('status') for p in payments):invalid+=1;continue
        if not any(p['status']=='approved' for p in payments):continue
        value=amount(row.get('total'))
        if row.get('moeda')!='BRL' or value is None:invalid+=1;continue
        target=result.get(row.get('uf'),missing)
        target['orders']+=1;target['revenue']+=value
        if type(row.get('unidades')) is int and row['unidades']>0:target['units']+=row['unidades']
        else:target['unknown_units']+=1
    days=(end-start).days+1
    coverage=sum(1 for d in covered if start.isoformat()<=d<=end.isoformat())
    known=sum(r['orders'] for r in result.values()); total=known+missing['orders']
    return dict(states=result,missing=missing,known=known,total=total,invalid=invalid,unlocated=unlocated,days=days,covered=coverage,
                revenue=sum((r['revenue'] for r in result.values()),amount(0))+missing['revenue'])
