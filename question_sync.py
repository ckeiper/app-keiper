"""Bounded question reads and oldest-first status rechecks. Never sends answers."""
import re
import time
import requests

PAGE_SIZE = 50
SEARCH_PAGES = 2
RECHECKS = 2
FRESH_SECONDS = 6 * 3600
SOURCE = 'https://developers.mercadolivre.com.br/pt_br/perguntas-e-respostas'
STATUSES = {'UNANSWERED','ANSWERED','CLOSED_UNANSWERED','BANNED','DELETED','DISABLED','UNDER_REVIEW'}


class Unavailable(ValueError):
    def __init__(self, message, stop=False):
        super().__init__(message)
        self.stop = stop


def init_schema(conn, execute):
    for name, kind in [('consulta_em','BIGINT'), ('status_confirmado_em','BIGINT'),
                       ('consulta_estado','TEXT'), ('consulta_erro','TEXT'),
                       ('vendedor_confirmado','TEXT'), ('excluida_do_anuncio','BOOLEAN'),
                       ('em_espera','BOOLEAN'), ('resposta_status','TEXT')]:
        execute(conn, 'ALTER TABLE perguntas ADD COLUMN IF NOT EXISTS '+name+' '+kind)
    execute(conn, '''CREATE INDEX IF NOT EXISTS perguntas_revisao_status
        ON perguntas(conexao_id,consulta_em NULLS FIRST,pergunta_id)''')
    execute(conn, '''CREATE TABLE IF NOT EXISTS perguntas_coleta (
        conexao_id INTEGER PRIMARY KEY REFERENCES conexoes(id) ON DELETE CASCADE,
        vendedor_id TEXT NOT NULL, consultado_em BIGINT NOT NULL,
        estado TEXT NOT NULL, paginas INTEGER NOT NULL, lidas INTEGER NOT NULL,
        total_informado INTEGER, revisadas INTEGER NOT NULL, indisponiveis INTEGER NOT NULL,
        detalhe TEXT NOT NULL)''')


def read(token, path, params, request_get):
    try:
        response = request_get('https://api.mercadolibre.com'+path,
            headers={'Authorization':'Bearer '+token}, params=params,
            timeout=(3,8), allow_redirects=False)
        if response.status_code != 200:
            raise Unavailable('HTTP '+str(response.status_code), response.status_code in (401,403,429))
        payload = response.json()
        if not isinstance(payload, dict):
            raise Unavailable('Resposta não verificável.', True)
        return payload
    except (requests.RequestException, ValueError, TypeError) as exc:
        if isinstance(exc, Unavailable):
            raise
        raise Unavailable('Rede ou resposta não verificável.') from None


def collect(cid, token, seller_id, bank, query, execute, request_get, error, now=None):
    from listing_questions import persist
    now = int(time.time()) if now is None else now
    seller = str(seller_id)
    if (isinstance(seller_id,bool) or not re.fullmatch(r'[1-9][0-9]{0,19}',seller)
            or not isinstance(token,str) or not token or type(now) is not int or now <= 0):
        error(cid,'perguntas','Conexão não verificável para a coleta.')
        return False
    seen = set();pages = 0;offset = 0;total = None;consistent = True
    metadata = True;ended = False;stop = False;failed = False;detail = ''
    revised = 0;unavailable = 0
    with bank() as conn:
        lock = query(conn, 'SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS acquired', ('question-sync:'+str(cid),))
        if not lock or lock[0].get('acquired') is not True:
            return True  # Another collector owns this store; no new reading is claimed.
        for _ in range(SEARCH_PAGES):
            try:
                payload = read(token, '/questions/search', dict(seller_id=seller, api_version=4,
                    limit=PAGE_SIZE, offset=offset, sort_fields='date_created', sort_types='DESC'), request_get)
                rows = payload.get('questions')
                if not isinstance(rows,list) or len(rows)>PAGE_SIZE:
                    raise Unavailable('Página de perguntas não verificável.', True)
                reported = payload.get('total')
                if type(reported) is not int or not 0 <= reported <= 2**31-1:
                    metadata = False
                elif total is None:
                    total = reported
                elif total != reported:
                    consistent = False
                filters = payload.get('filters')
                if (not isinstance(filters,dict) or type(filters.get('offset')) is not int
                        or filters['offset'] != offset or type(payload.get('limit')) is not int
                        or not 1 <= payload['limit'] <= PAGE_SIZE or len(rows)>payload['limit']):
                    metadata = False
                persist(conn, execute, cid, payload, now, expected_seller=seller)
                ids = {str(int(row['id'])) for row in rows}
                if seen.intersection(ids):
                    consistent = False
                seen.update(ids);pages += 1
                if not rows:
                    ended = True
                    if total is not None and len(seen) != total:
                        consistent = False
                    break
                offset += len(rows)
                if total is not None and offset >= total:
                    ended = True
                    break
            except (Unavailable, ValueError) as exc:
                failed = True
                stop = not isinstance(exc,Unavailable) or exc.stop
                detail = str(exc) if isinstance(exc,Unavailable) else 'Página de perguntas não verificável.'
                break
        if not stop:
            old = query(conn, '''SELECT pergunta_id,item_id FROM perguntas
                WHERE conexao_id=%s AND pergunta_id ~ '^[1-9][0-9]{0,19}$'
                AND (consulta_em IS NULL OR consulta_em < %s)
                ORDER BY consulta_em ASC NULLS FIRST,
                CASE WHEN status='UNANSWERED' THEN 0 ELSE 1 END,pergunta_id COLLATE "C" LIMIT %s''',
                (cid, now-FRESH_SECONDS, RECHECKS))
            for row in old:
                qid = str(row['pergunta_id'])
                if not re.fullmatch(r'[1-9][0-9]{0,19}',qid):
                    continue
                try:
                    payload = read(token,'/questions/'+qid,dict(api_version=4),request_get)
                    actual = payload.get('id')
                    if (isinstance(actual,bool) or not isinstance(actual,(str,int))
                            or str(actual) != qid or payload.get('item_id') != row['item_id']):
                        raise Unavailable('Pergunta retornada não corresponde ao registro.', True)
                    persist(conn,execute,cid,dict(questions=[payload]),now,expected_seller=seller)
                    if payload.get('status') in STATUSES:
                        revised += 1
                    else:
                        unavailable += 1
                except (Unavailable,ValueError) as exc:
                    unavailable += 1
                    message = str(exc) if isinstance(exc,Unavailable) else 'Pergunta não verificável nesta conta.'
                    execute(conn, '''UPDATE perguntas SET consulta_em=%s,consulta_estado='unknown',consulta_erro=%s
                        WHERE conexao_id=%s AND pergunta_id=%s''', (now,message,cid,qid))
                    if not isinstance(exc,Unavailable) or exc.stop:
                        failed = True;detail = message
                        break
        complete = pages > 0 and ended and metadata and consistent and total == len(seen) and not failed
        state = 'read' if complete else 'partial' if pages else 'unknown'
        if not detail and not complete:
            detail = 'Lote limitado ou paginação não confirmada; não certifica histórico integral.'
        execute(conn, '''INSERT INTO perguntas_coleta(conexao_id,vendedor_id,consultado_em,estado,paginas,lidas,
            total_informado,revisadas,indisponiveis,detalhe) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(conexao_id) DO UPDATE SET vendedor_id=EXCLUDED.vendedor_id,consultado_em=EXCLUDED.consultado_em,
            estado=EXCLUDED.estado,paginas=EXCLUDED.paginas,lidas=EXCLUDED.lidas,total_informado=EXCLUDED.total_informado,
            revisadas=EXCLUDED.revisadas,indisponiveis=EXCLUDED.indisponiveis,detalhe=EXCLUDED.detalhe''',
            (cid,seller,now,state,pages,len(seen),total,revised,unavailable,detail))
    if failed:
        error(cid,'perguntas',detail)
    return not failed


def pending_count(conn, query, cid, seller_id, now):
    return query(conn, '''SELECT COUNT(*) AS n FROM perguntas
        WHERE conexao_id=%s AND status='UNANSWERED' AND consulta_estado='read'
        AND status_confirmado_em BETWEEN %s AND %s AND vendedor_confirmado=%s
        AND excluida_do_anuncio IS FALSE AND em_espera IS FALSE''',
        (cid,now-FRESH_SECONDS,now,str(seller_id)))[0]['n']
