"""Bounded, on-demand content reading. Never writes listings or manual reviews."""
import re
import secrets
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

import requests
from flask import request, session
from profitability_view import CSS
from content_required_attributes import compare as compare_required, render as render_required
from content_conditional_attributes import evaluate as evaluate_conditional
from content_attribute_units import compare as compare_units, render as render_units
from content_technical_specs import compare as compare_specs, render as render_specs


class ContentUnavailable(ValueError):
    pass


class ContentRateLimited(ContentUnavailable):
    pass


def read(token, path, request_get, payload_type=dict):
    try:
        response = request_get('https://api.mercadolibre.com'+path,
            headers={'Authorization': 'Bearer '+token}, timeout=(3, 8), allow_redirects=False)
        if response.status_code == 429:
            raise ContentRateLimited('Limite de consultas atingido. Aguarde antes de tentar novamente.')
        if response.status_code != 200:
            raise ContentUnavailable('Leitura indisponível no Mercado Livre. Nenhuma ausência foi presumida.')
        payload = response.json()
        if not isinstance(payload, payload_type):
            raise ContentUnavailable('Resposta não verificável do Mercado Livre.')
        return payload
    except (requests.RequestException, ValueError, TypeError) as exc:
        if isinstance(exc, ContentUnavailable):
            raise
        raise ContentUnavailable('Falha de rede ou resposta inválida. Tente novamente mais tarde.') from None


def text(value, limit):
    return value.strip() if isinstance(value, str) and len(value) <= limit else None


def inspect(token, seller_id, item_id, request_get, now=None, request_post=None, include_specs=False):
    result = dict(state='unknown', checked_at=now or datetime.now(timezone.utc))
    if (not isinstance(token, str) or not token or
        isinstance(seller_id, bool) or not re.fullmatch(r'[1-9][0-9]{0,19}', str(seller_id)) or
        not isinstance(item_id, str) or not re.fullmatch(r'MLB[0-9]{1,20}', item_id)):
        return dict(result, message='Conexão ou anúncio não verificável para consulta.')
    try:
        account = read(token, '/users/me', request_get)
        if str(account.get('id')) != str(seller_id):
            raise ContentUnavailable('A autorização não corresponde à conta desta loja.')
        item = read(token, '/items/'+item_id, request_get)
        if item.get('id') != item_id or str(item.get('seller_id')) != str(seller_id) or item.get('site_id') != 'MLB':
            raise ContentUnavailable('O anúncio retornado não corresponde à conta e ao anúncio desta loja.')
    except ContentUnavailable as exc:
        return dict(result, message=str(exc))
    result.update(state='read', title=text(item.get('title'), 1000), description=None,
                  description_message='', photos=None, attributes=None, attribute_count=None,
                  variations=None)
    pictures = item.get('pictures')
    if isinstance(pictures, list) and all(isinstance(p, dict) and isinstance(p.get('id'), str) and p['id'].strip() for p in pictures):
        result['photos'] = len(pictures)
    variations = item.get('variations')
    if isinstance(variations, list) and all(isinstance(v, dict) and v.get('id') is not None for v in variations):
        result['variations'] = len(variations)
    attrs = item.get('attributes')
    if isinstance(attrs, list) and all(isinstance(a, dict) and text(a.get('id'), 200) for a in attrs):
        result['attribute_count'] = len(attrs)
        result['attributes'] = [dict(name=text(a.get('name'), 300) or a['id'],
            value=text(a.get('value_name'), 2000)) for a in attrs[:50]]
    rate_limited=False
    try:
        desc = read(token, '/items/'+item_id+'/description', request_get)
        result['description'] = text(desc.get('plain_text'), 200000)
        if result['description'] is None:
            result['description_message'] = 'Texto da descrição não verificável na resposta.'
    except ContentUnavailable as exc:
        result['description_message'] = str(exc)
        rate_limited=isinstance(exc,ContentRateLimited)
    result['requirements']=dict(state='unknown',message='Categoria do anúncio não verificável.')
    result['attribute_units']=dict(state='unknown',message='Categoria do anúncio não verificável.')
    if include_specs:result['technical_specs']=dict(state='unknown',message='Categoria do anúncio não verificável.')
    category_attributes=None
    category=item.get('category_id')
    if isinstance(category,str) and re.fullmatch(r'MLB[0-9]{1,20}',category):
        try:
            payload=read(token,'/categories/'+category+'/attributes',request_get,list)
            category_attributes=payload
            result['requirements']=dict(compare_required(payload,item),category=category)
            result['attribute_units']=compare_units(payload,item)
            if result['requirements'].get('state') == 'read' and any(r['conditional'] for r in result['requirements']['rows']):
                conditional=evaluate_conditional(token,category,item,result['description'],request_post)
                result['requirements']['conditional']=conditional
                rate_limited=rate_limited or conditional.get('rate_limited') is True
                if conditional['state']=='read':
                    for row in result['requirements']['rows']:
                        if row['conditional']:
                            row['conditional_confirmed']=row['id'] in conditional['required_ids']
        except ContentUnavailable as exc:
            result['requirements']=dict(state='unknown',message=str(exc))
            result['attribute_units']=dict(state='unknown',message=str(exc))
            rate_limited=rate_limited or isinstance(exc,ContentRateLimited)
        if include_specs and not rate_limited:
            try:
                specs=read(token,'/categories/'+category+'/technical_specs/input',request_get)
                result['technical_specs']=compare_specs(specs,category_attributes,item,result['requirements'].get('conditional'))
            except ContentUnavailable as exc:
                result['technical_specs']=dict(state='unknown',message=str(exc))
    if include_specs and rate_limited:
        result['technical_specs']=dict(state='unknown',message='Limite de consultas atingido. Aguarde antes de tentar novamente.')
    return result


def render(cid, item_id, title, csrf, result=None):
    esc = lambda value: escape(str(value), quote=True)
    path = '/anuncios/'+str(int(cid))+'/'+esc(item_id)+'/conteudo'
    out = CSS+'<div class="pf content-snapshot"><header class="pf-hero"><span class="pf-eyebrow">Anúncios 2.0 · Conferência de conteúdo</span><h2>Conteúdo atual do anúncio</h2><p>'+esc(title or item_id)+' · '+esc(item_id)+'</p><a href="'+path+'">← Voltar ao checklist de conteúdo</a><p>Consulte o que o Mercado Livre retorna agora para apoiar sua revisão. A leitura não aprova critérios nem mede qualidade ou impacto nas vendas.</p></header><section class="pf-card"><h3>Consultar no Mercado Livre</h3><p>Verifica a conta autorizada e a propriedade do anúncio. Não altera a oferta nem os pareceres registrados. A leitura aparece apenas nesta resposta; registre sua evidência no checklist.</p><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><button>Consultar conteúdo atual</button><button name="ficha_tecnica" value="1">Consultar conteúdo e ficha técnica</button></form></section>'
    if result:
        stamp = result['checked_at'].astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y às %H:%M:%S · Brasília')
        out += '<section class="pf-card" id="content-snapshot-result"><h3>Leitura consultada</h3><p>'+esc(stamp)+'</p>'
        if result['state'] != 'read':
            out += '<p role="status">Sem leitura verificável. '+esc(result['message'])+'</p>'
        else:
            def present(value):
                return 'Não verificado' if value is None else str(value)
            out += '<div class="pf-grid">'+''.join('<article class="pf-metric"><span>'+label+'</span><strong>'+present(value)+'</strong></article>' for label, value in [('Fotos retornadas',result['photos']),('Atributos no anúncio principal',result['attribute_count']),('Variações retornadas',result['variations'])])+'</div>'
            out += '<h4>Título retornado</h4><p class="cs-text">'+esc(result['title'] if result['title'] is not None else 'Não verificado')+'</p>'
            if result['title'] == '': out += '<p>Título vazio na resposta consultada.</p>'
            out += '<h4>Descrição retornada</h4>'
            description = result['description']
            if description is None:
                out += '<p role="status">Descrição não verificada. '+esc(result['description_message'])+'</p>'
            elif description == '':
                out += '<p>Descrição vazia na resposta consultada.</p>'
            else:
                out += '<details><summary>Ler descrição consultada</summary><p class="cs-text">'+esc(description[:12000])+'</p></details>'
                if len(description)>12000: out += '<p>Exibidos os primeiros 12.000 caracteres de '+str(len(description))+'. Confira o texto completo no anúncio.</p>'
            out += '<h4>Atributos do anúncio principal</h4><p>Lista retornada pela consulta. Os requisitos da categoria são conferidos abaixo, sem certificar a validade dos valores.</p>'
            if result['attributes'] is None:
                out += '<p>Atributos não verificados.</p>'
            elif not result['attributes']:
                out += '<p>Nenhum atributo retornado no anúncio principal.</p>'
            else:
                out += '<dl class="cs-attributes">'+''.join('<dt>'+esc(a['name'])+'</dt><dd>'+esc(a['value'] if a['value'] is not None else 'Valor não verificado')+'</dd>' for a in result['attributes'])+'</dl>'
                if result['attribute_count']>50: out += '<p>Exibidos 50 de '+str(result['attribute_count'])+' atributos retornados.</p>'
            out += '<p>Contagem de fotos não certifica legibilidade, medidas ou conteúdo das imagens. Clips e vídeo não foram consultados. Campos não verificados não significam ausência.</p>'
            out += render_required(result.get('requirements',{}))
            out += render_units(result.get('attribute_units',{}))
            if 'technical_specs' in result:out += render_specs(result['technical_specs'])
        out += '</section>'
    return out+'<section class="pf-card"><h3>Continuar a conferência</h3><p>Confira imagens, especificações, compatibilidade e dúvidas reais antes de registrar seu parecer. A oferta pode mudar depois desta leitura. Nenhum histórico de revisão foi substituído.</p><a href="'+path+'">Registrar evidências no checklist ↗</a></section></div><style>.cs-text{white-space:pre-wrap;overflow-wrap:anywhere}.cs-attributes{overflow-wrap:anywhere}.cs-attributes dt{font-weight:700;margin-top:12px}.cs-attributes dd{margin:4px 0 0}</style>'


def register(app, login_required, can_view, bank, query, shop_page, resolve_token, request_get, request_post=requests.post):
    @app.route('/anuncios/<int:cid>/<item_id>/conteudo-atual', methods=['GET', 'POST'])
    @login_required
    def listing_content_snapshot(cid, item_id):
        if session.get('tipo') != 'admin' or not can_view(cid):
            return 'Acesso restrito ao administrador.', 403
        if not re.fullmatch(r'MLB[0-9]{1,20}', item_id):
            return 'Anúncio não encontrado.', 404
        with bank() as conn:
            shops = query(conn, '''SELECT c.*,a.titulo FROM conexoes c JOIN anuncios a
                ON a.conexao_id=c.id WHERE c.id=%s AND a.item_id=%s''', (cid, item_id))
        if not shops:
            return 'Anúncio não encontrado nesta loja.', 404
        csrf = session.setdefault('_csrf', secrets.token_urlsafe(32))
        result = inspect(resolve_token(shops[0]), shops[0]['user_id'], item_id, request_get, request_post=request_post, include_specs=request.form.get('ficha_tecnica')=='1') if request.method == 'POST' else None
        return shop_page('Conteúdo atual do anúncio', cid, shops[0]['cliente'], 'anuncios',
                         render(cid, item_id, shops[0]['titulo'], csrf, result))
