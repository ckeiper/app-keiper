"""Store-scoped exact official SKU candidates, including observed variations."""
from html import escape
from urllib.parse import urlencode, quote
from datetime import datetime
from sales_metrics import SAO_PAULO
from listing_calendar import STYLE

# Only locally produced, versioned snapshots. Internal seller_custom_field is never a fallback.
ENTRIES = '''WITH entries AS (
 SELECT a.item_id,a.titulo,a.status,a.atualizado_em,a.sku_metadata_json->>'collected_at' AS collected_at,
        a.sku_metadata_json->>'state' AS coverage,(e->>'code') COLLATE "C" AS code,e->>'variation' AS variation
 FROM anuncios a CROSS JOIN LATERAL jsonb_array_elements(
 CASE WHEN jsonb_typeof(a.sku_metadata_json->'entries')='array' THEN a.sku_metadata_json->'entries' ELSE '[]'::jsonb END) e
 WHERE a.conexao_id=%s AND a.sku_metadata_json->>'version'='1'
 AND a.sku_metadata_json->>'state' IN ('read','partial')
 AND jsonb_typeof(e->'code')='string' AND length(e->>'code') BETWEEN 1 AND 200
 AND (e->>'variation'='principal' OR e->>'variation' ~ '^[1-9][0-9]{0,19}$')
) '''


def load(conn, query, cid, args):
    sku = str(args.get('sku', '')).strip(' \t\r\n')
    if len(sku) > 200 or '\x00' in sku:
        raise ValueError('O filtro de SKU aceita até 200 caracteres.')
    stats = query(conn, '''SELECT COUNT(*) AS total,
        COUNT(*) FILTER(WHERE sku_metadata_json->>'version'='1' AND sku_metadata_json->>'state'='read') AS read,
        COUNT(*) FILTER(WHERE sku_metadata_json->>'version'='1' AND sku_metadata_json->>'state'='partial') AS partial
        FROM anuncios WHERE conexao_id=%s''', (cid,))[0]
    where = ' WHERE code=%s' if sku else ''
    params = (cid, sku) if sku else (cid,)
    grouping = 'SELECT code,COUNT(DISTINCT item_id) AS n,COUNT(*) AS occurrences FROM entries'+where+' GROUP BY code HAVING COUNT(DISTINCT item_id)>1'
    total = query(conn, ENTRIES+'SELECT COUNT(*) AS n FROM ('+grouping+') grouped', params)[0]['n']
    pages = max(1, (total+9)//10)
    try:
        page = max(1, min(pages, int(args.get('pagina', '1'))))
    except (TypeError, ValueError):
        page = 1
    groups = query(conn, ENTRIES+grouping+' ORDER BY code COLLATE "C" LIMIT 10 OFFSET %s', params+((page-1)*10,))
    members = []
    if groups:
        members = query(conn, ENTRIES+'''SELECT * FROM (
          SELECT item_id,titulo,status,atualizado_em,collected_at,coverage,code,
             (array_agg(variation ORDER BY variation COLLATE "C"))[1:10] AS variations,COUNT(*) AS occurrences,
             ROW_NUMBER() OVER(PARTITION BY code ORDER BY item_id) AS rn
          FROM entries WHERE code=ANY(%s)
          GROUP BY item_id,titulo,status,atualizado_em,collected_at,coverage,code
        ) members WHERE rn<=10 ORDER BY code COLLATE "C",rn''', (cid, [r['code'] for r in groups]))
    return dict(stats=stats, total=total, groups=groups, members=members, page=page, pages=pages, sku=sku)


def render(cid, data, now):
    esc = lambda value: escape(str(value), quote=True)
    path = '/anuncios/'+str(int(cid))+'/skus-variacoes'
    out = STYLE+'''<style>.sv-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.sv-cards article,.sv-group{border:1px solid #426184;border-radius:12px;padding:14px;margin:14px 0;overflow-wrap:anywhere}.sv-cards{margin:16px 0}.sv-cards article{margin:0;font-size:13px;line-height:1.5}.sv-cards strong{font-size:24px;display:block;margin-bottom:4px}.sv-item{display:block;border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.sv-item span{display:block;margin-top:8px}.sv-item:hover{background:#244367}.sv-form label{flex:1;min-width:0}.sv-form input{min-width:0;max-width:100%;box-sizing:border-box}.sv-group code{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:700px){.sv-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>'''
    out += '<section class="lc sku-variations"><h2>SKUs oficiais e variações</h2><p><a href="/anuncios/'+str(int(cid))+'/skus-repetidos">Conferir campos internos do catálogo</a></p><p>Mesmo SKU em anúncios diferentes. Confira os produtos e as variações antes de concluir sobreposição.</p>'
    out += '<form method="get" class="sv-form"><label>SKU exato · opcional<input name="sku" maxlength="200" value="'+esc(data['sku'])+'"></label><button>Filtrar</button><a href="'+path+'">Limpar filtro</a></form>'
    stats = data['stats']
    out += '<div class="sv-cards">'+''.join('<article><strong>'+str(n)+'</strong><span>'+label+'</span></article>' for n, label in [(stats['total'], 'Anúncios no catálogo'), (stats['read'], 'Leituras completas'), (stats['partial'], 'Leituras parciais'), (data['total'], 'Grupos repetidos no filtro')])+'</div>'
    out += '<p>Sem leitura verificável: '+str(stats['total']-stats['read']-stats['partial'])+' anúncios. Preenchimento pela atualização habitual do catálogo.</p>'
    for group in data['groups']:
        out += '<section class="sv-group"><h3>SKU <code>'+esc(group['code'])+'</code></h3><p>'+str(group['n'])+' anúncios · '+str(group['occurrences'])+' ocorrências observadas no principal e variações.</p>'
        if group['n'] > 10:
            out += '<p>Exibidos os primeiros dez anúncios deste grupo.</p>'
        for row in data['members']:
            if row['code'] != group['code']:
                continue
            try:
                stamp = int(row['collected_at'])
                fresh = 0 < stamp <= now and now-stamp <= 21600
                label = datetime.fromtimestamp(stamp, SAO_PAULO).strftime('%d/%m/%Y %H:%M · Brasília')
            except (TypeError, ValueError, OverflowError, OSError):
                fresh = False
                label = 'não verificável'
            locations = ['anúncio principal' if v == 'principal' else 'variação '+v for v in row['variations']]
            out += '<a class="sv-item" href="/diagnostico/'+str(int(cid))+'/'+quote(str(row['item_id']), safe='')+'"><strong>'+esc(row.get('titulo') or row['item_id'])+'</strong><span>'+esc(row['item_id'])+'</span><span>'+esc(', '.join(locations))+'</span>'
            if row['occurrences'] > 10:
                out += '<span>Exibidas dez de '+str(row['occurrences'])+' ocorrências neste anúncio.</span>'
            out += '<span>Coleta: '+esc(label)+(' · leitura recente' if fresh else ' · atualidade não verificada')+(' · cobertura parcial' if row['coverage'] != 'read' else '')+'</span></a>'
        out += '</section>'
    if not data['groups']:
        out += '<p>Nenhum SKU oficial repetido neste filtro das leituras salvas. Isso não comprova ausência de sobreposição.</p>'
    out += '<details><summary>Critérios e cobertura da comparação</summary><p>Compara o SKU oficial retornado no anúncio e em cada variação, sem usar o campo interno como substituto. Um grupo é candidato à revisão, não prova de produto equivalente, concorrência interna ou perda de vendas.</p><p>A cobertura considera o catálogo inteiro; grupos respeitam o filtro. Leitura completa descreve a estrutura recebida, sem garantir atualidade ou cadastro completo no Mercado Livre.</p><p>Dez grupos por página, até dez anúncios por grupo e dez ocorrências por anúncio. Códigos preservam maiúsculas, acentos e espaços internos; apenas espaços, tabulações e quebras nas extremidades são removidos. Todos os status do catálogo salvo são considerados.</p></details><nav aria-label="Paginação de SKUs oficiais">Página '+str(data['page'])+' de '+str(data['pages'])
    for label, page in [('Anterior', data['page']-1), ('Próxima', data['page']+1)]:
        if 1 <= page <= data['pages']:
            out += ' <a href="'+esc(path+'?'+urlencode(dict(sku=data['sku'], pagina=page)))+'">'+label+'</a>'
    return out+'</nav></section>'


def register(app, login_required, can_view, bank, query, execute, shop_page):
    from flask import request, session
    import time
    @app.route('/anuncios/<int:cid>/skus-variacoes', methods=['GET'])
    @login_required
    def listing_official_sku_variations(cid):
        if session.get('tipo') != 'admin' or not can_view(cid):
            return 'Acesso restrito', 403
        try:
            with bank() as conn:
                execute(conn, 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                shops = query(conn, 'SELECT cliente FROM conexoes WHERE id=%s', (cid,))
                if not shops:
                    return 'Loja não encontrada', 404
                data = load(conn, query, cid, request.args)
        except ValueError as exc:
            return str(exc), 400
        return shop_page('SKUs oficiais e variações', cid, shops[0]['cliente'], 'anuncios', render(cid, data, int(time.time())))
