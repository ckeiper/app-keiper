"""Bounded, account-scoped product reviews. No persistence or marketplace writes."""
import hmac
import math
import re
import secrets
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from flask import request, session
from listing_content_snapshot import read, ContentUnavailable
from profitability_view import CSS

LIMIT = 5
MAX_OFFSET = 95  # Local safety limit, not an asserted Mercado Livre limit.
LEVELS = ('one_star', 'two_star', 'three_star', 'four_star', 'five_star')


def integer(value, maximum=10**10):
    return value if type(value) is int and 0 <= value <= maximum else None


def normalize(payload, item_id, product_id, offset):
    """Keep only published, correctly bound texts and independently valid aggregates."""
    paging = payload.get('paging')
    rows = payload.get('reviews')
    if (not isinstance(paging, dict) or not isinstance(rows, list) or len(rows) > LIMIT
            or integer(paging.get('offset')) != offset or paging.get('limit') != LIMIT
            or type(paging.get('limit')) is not int):
        raise ContentUnavailable('Página de avaliações não verificável. Nenhuma ausência foi presumida.')
    total = integer(paging.get('total'))
    pageable = integer(paging.get('total_pageable'))
    if total is not None and pageable is not None and pageable > total:
        pageable = None
    average = payload.get('rating_average')
    average = average if type(average) in (int, float) and math.isfinite(average) and 1 <= average <= 5 else None
    levels = payload.get('rating_levels')
    levels = [integer(levels.get(k)) for k in LEVELS] if isinstance(levels, dict) else [None]*5
    # Conflicting totals cannot establish a distribution.
    if all(v is not None for v in levels) and total is not None and sum(levels) != total:
        levels = [None]*5
    if total == 0:
        average = None
    kept, omitted, seen = [], 0, set()
    for row in rows:
        if not isinstance(row, dict):
            omitted += 1
            continue
        obj = row.get('reviewable_object')
        bound = isinstance(obj, dict) and ((obj.get('type') == 'item' and obj.get('id') == item_id)
            or (product_id and obj.get('type') == 'product' and obj.get('id') == product_id))
        rid = row.get('id')
        if (not bound or row.get('status') != 'published' or type(rid) is not int or rid <= 0
                or rid in seen or type(row.get('rate')) is not int or not 1 <= row['rate'] <= 5):
            omitted += 1
            continue
        seen.add(rid)
        title, content = row.get('title'), row.get('content')
        if (title is not None and not isinstance(title, str)) or (content is not None and not isinstance(content, str)):
            omitted += 1
            continue
        kept.append(dict(rate=row['rate'], title=(title or '')[:200], content=(content or '')[:4000],
                         truncated=len(title or '') > 200 or len(content or '') > 4000))
    return dict(total=total, pageable=pageable, average=average, levels=levels, rows=kept,
                omitted=omitted, received=len(rows), offset=offset,
                next_offset=offset+LIMIT if pageable is not None and len(rows)==LIMIT and offset+LIMIT < pageable and offset+LIMIT <= MAX_OFFSET else None,
                capped=pageable is not None and pageable > MAX_OFFSET+LIMIT,
                cross_site=payload.get('cross_site_enabled') is True)


def inspect(token, seller_id, item_id, request_get, offset=0, now=None):
    result = dict(state='unknown', checked_at=now or datetime.now(timezone.utc))
    if (not isinstance(token, str) or not token or type(seller_id) is bool
            or not re.fullmatch(r'[1-9][0-9]{0,19}', str(seller_id))
            or not isinstance(item_id, str) or not re.fullmatch(r'MLB[0-9]{1,20}', item_id)
            or type(offset) is not int or not 0 <= offset <= MAX_OFFSET or offset % LIMIT):
        return dict(result, message='Conexão, anúncio ou página não verificável.')
    try:
        account = read(token, '/users/me', request_get)
        if str(account.get('id')) != str(seller_id):
            raise ContentUnavailable('A autorização não corresponde à conta desta loja.')
        item = read(token, '/items/'+item_id, request_get)
        if item.get('id') != item_id or str(item.get('seller_id')) != str(seller_id) or item.get('site_id') != 'MLB':
            raise ContentUnavailable('O anúncio não corresponde à conta desta loja.')
        product = item.get('catalog_product_id')
        if product is not None and (not isinstance(product, str) or not re.fullmatch(r'MLB[0-9]{1,20}', product)):
            raise ContentUnavailable('Vínculo de catálogo não verificável.')
        if item.get('status') != 'active':
            raise ContentUnavailable('Anúncio sem status ativo verificável. Avaliações não consultadas; nenhuma ausência foi presumida.')
        if item.get('catalog_listing') is True and product is None:
            raise ContentUnavailable('Produto de catálogo não identificado. Avaliações não consultadas.')
        params = dict(limit=LIMIT, offset=offset)
        if product:
            params['catalog_product_id'] = product
        payload = read(token, '/reviews/item/'+item_id+'?'+urlencode(params), request_get)
        return dict(result, **normalize(payload, item_id, product, offset), state='read', product_id=product)
    except ContentUnavailable as exc:
        return dict(result, message=str(exc))


def render(cid, item_id, title, csrf, result=None):
    esc = lambda v: escape(str(v), quote=True)
    path = '/anuncios/'+str(int(cid))+'/'+esc(item_id)
    out = CSS+'''<div class="pf buyer-reviews"><header class="pf-hero"><span class="pf-eyebrow">Anúncios 2.0 · Voz do comprador</span><h2>Avaliações do produto</h2><p>'''+esc(title or item_id)+' · '+esc(item_id)+'''</p></header><section class="pf-card"><h3>Consultar avaliações</h3><p>Leitura sob demanda, sem armazenar comentários. Avaliações do produto não medem atendimento ou reputação desta loja.</p>'''
    def button(offset, label):
        return '<form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><input type="hidden" name="offset" value="'+str(offset)+'"><button>'+label+'</button></form>'
    out += button(0, 'Consultar avaliações no Mercado Livre')+'</section>'
    if result:
        stamp = result['checked_at'].astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y às %H:%M:%S · Brasília')
        out += '<section class="pf-card" id="buyer-review-result"><h3>Leitura consultada</h3><p>'+esc(stamp)+'</p>'
        if result['state'] != 'read':
            out += '<p role="status">Sem leitura verificável. '+esc(result['message'])+'</p>'
        else:
            out += '<p class="br-scope">'+('Produto de catálogo '+esc(result['product_id'])+' · avaliações compartilhadas do produto, que podem reunir compras de outros vendedores.' if result['product_id'] else 'Avaliações associadas ao anúncio consultado.')+'</p>'
            if result['cross_site']:out += '<p>A API informa compartilhamento de avaliações entre países.</p>'
            def value(v):return 'Não verificado' if v is None else esc(v)
            average = None if result['average'] is None else f"{result['average']:.1f}".replace('.', ',')+' / 5'
            out += '<div class="pf-grid">'+''.join('<article class="pf-metric"><span>'+k+'</span><strong>'+value(v)+'</strong></article>' for k,v in [('Média informada',average),('Avaliações informadas',result['total']),('Acessíveis por paginação',result['pageable'])])+'</div>'
            out += '<details><summary>Distribuição por estrelas</summary><dl class="br-levels">'+''.join('<dt>'+str(i)+' estrela'+('s' if i!=1 else '')+'</dt><dd>'+value(v)+'</dd>' for i,v in reversed(list(enumerate(result['levels'],1))))+'</dl></details>'
            out += '<h4>Comentários desta página</h4><p>Posição '+str(result['offset']+1)+' · até cinco registros por consulta. Textos são opiniões de compradores, sem confirmação das alegações.</p>'
            if not result['rows']:out += '<p>Nenhum comentário publicado verificável nesta página. Isso não comprova ausência de avaliações.</p>'
            for row in result['rows']:
                out += '<article class="br-review"><strong>'+str(row['rate'])+' / 5'+(' · '+esc(row['title']) if row['title'] else '')+'</strong><p>'+esc(row['content'] or 'Sem texto retornado.')+'</p>'+('<small>Texto abreviado para exibição.</small>' if row['truncated'] else '')+'</article>'
            if result['omitted']:out += '<p role="status">'+str(result['omitted'])+' registro(s) não exibido(s): publicação, vínculo ou formato não verificável.</p>'
            out += '<div class="br-pages">'
            if result['offset'] > 0:out += button(result['offset']-LIMIT,'Página anterior')
            if result['next_offset'] is not None:out += button(result['next_offset'],'Próxima página')
            out += '</div>'
            if result['capped']:out += '<p>Limite local de consulta: primeiras 100 posições. Não representa cobertura integral.</p>'
            out += '<details><summary>Como usar na consultoria</summary><p>Confira comentários e contexto antes de propor ajustes. Compare dúvidas com descrição e especificações; uma opinião isolada não confirma defeito ou impacto nas vendas. Totais e comentários disponíveis podem diferir e mudar entre páginas. Falhas e campos não verificados não significam zero.</p></details>'
        out += '</section>'
    return out+'<section class="pf-card"><h3>Continuar análise</h3><div class="br-links"><a href="'+path+'/conteudo">Checklist de conteúdo</a><a href="'+path+'/perguntas">Perguntas do anúncio</a></div></section></div><style>.buyer-reviews{min-width:0}.buyer-reviews :is(p,strong,a){overflow-wrap:anywhere}.br-review{padding:14px 0;border-bottom:1px solid var(--line,#7892aa)}.br-review p{white-space:pre-wrap}.br-pages,.br-links{display:flex;flex-wrap:wrap;gap:12px}.br-links a{padding:14px;border:1px solid #7892aa;border-radius:10px}.br-levels{display:grid;grid-template-columns:1fr 1fr;gap:8px}.br-levels dd{margin:0}.buyer-reviews form{margin:10px 0}.buyer-reviews button{white-space:normal;max-width:100%}</style>'


def register(app, login_required, can_view, bank, query, shop_page, resolve_token, request_get):
    @app.route('/anuncios/<int:cid>/<item_id>/avaliacoes', methods=['GET','POST'])
    @login_required
    def listing_buyer_reviews(cid,item_id):
        if session.get('tipo') != 'admin' or not can_view(cid):return 'Acesso restrito',403
        if not re.fullmatch(r'MLB[0-9]{1,20}',item_id):return 'Anúncio não encontrado',404
        csrf = session.setdefault('_csrf',secrets.token_urlsafe(32))
        if request.method == 'POST' and not hmac.compare_digest(csrf.encode(),request.form.get('_csrf','').encode()):
            return 'Formulário expirado. Recarregue a página.',400
        raw = request.form.get('offset','0')
        if not re.fullmatch(r'[0-9]{1,2}',raw) or int(raw)>MAX_OFFSET or int(raw)%LIMIT:
            return 'Página inválida.',400
        with bank() as conn:
            shops = query(conn,'''SELECT c.*,a.titulo FROM conexoes c JOIN anuncios a
                ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s''',(cid,item_id))
        if not shops:return 'Anúncio não encontrado nesta loja.',404
        result = inspect(resolve_token(shops[0]),shops[0]['user_id'],item_id,request_get,int(raw)) if request.method=='POST' else None
        return shop_page('Avaliações do produto',cid,shops[0]['cliente'],'anuncios',render(cid,item_id,shops[0]['titulo'],csrf,result),refresh=False)
