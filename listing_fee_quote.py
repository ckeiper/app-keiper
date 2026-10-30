"""On-demand Mercado Livre fee estimate. No historical costs or listing writes."""
import re
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import escape
from zoneinfo import ZoneInfo
import requests
from flask import request, session
from profitability_view import CSS
from freight_comparison import format_brl

API = 'https://api.mercadolibre.com'
LOGISTICS = {**{k: 'me2' for k in ('drop_off', 'cross_docking', 'xd_drop_off', 'self_service', 'turbo', 'fulfillment')},
             'default': 'me1', 'custom': 'custom', 'not_specified': 'not_specified'}


class QuoteUnavailable(ValueError):
    pass


def amount(value, positive=False):
    if isinstance(value, bool) or value is None:
        raise QuoteUnavailable('Valor monetário ausente ou inválido na resposta oficial.')
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise QuoteUnavailable('Valor monetário inválido na resposta oficial.') from None
    if not result.is_finite() or result < 0 or result > Decimal('999999.99') or result != result.quantize(Decimal('.01')):
        raise QuoteUnavailable('Valor monetário inválido na resposta oficial.')
    if positive and result == 0:
        raise QuoteUnavailable('Preço principal não verificável para cotação.')
    return result


def get(token, path, params, request_get):
    try:
        response = request_get(API+path, headers={'Authorization': 'Bearer '+token}, params=params,
                               timeout=(3, 8), allow_redirects=False)
        if response.status_code == 429:
            raise QuoteUnavailable('Limite de consultas do Mercado Livre. Aguarde antes de tentar novamente.')
        if response.status_code != 200:
            raise QuoteUnavailable('Consulta oficial indisponível. Nenhuma tarifa foi presumida.')
        return response.json()
    except (requests.RequestException, ValueError, TypeError) as exc:
        if isinstance(exc, QuoteUnavailable):
            raise
        raise QuoteUnavailable('Falha de rede ou resposta oficial inválida. Tente novamente mais tarde.') from None


def quote(token, seller_id, item_id, request_get, now=None):
    """At most three GETs, no retries/redirects, all paths fixed or validated."""
    now = now or datetime.now(timezone.utc)
    unknown = lambda message: dict(state='unknown', message=message, checked_at=now)
    if not isinstance(token, str) or not token or not re.fullmatch(r'MLB[0-9]{1,20}', item_id):
        return unknown('Conexão ou anúncio não verificável para cotação.')
    if isinstance(seller_id, bool) or not re.fullmatch(r'[1-9][0-9]{0,19}', str(seller_id)):
        return unknown('Conta da loja não verificável para cotação.')
    try:
        account = get(token, '/users/me', {}, request_get)
        if not isinstance(account, dict) or str(account.get('id')) != str(seller_id):
            raise QuoteUnavailable('A autorização não corresponde à conta desta loja.')
        item = get(token, '/items/'+item_id, {}, request_get)
        if not isinstance(item, dict) or item.get('id') != item_id or str(item.get('seller_id')) != str(seller_id):
            raise QuoteUnavailable('O anúncio consultado não corresponde à conta desta loja.')
        if item.get('site_id') != 'MLB' or item.get('currency_id') != 'BRL':
            raise QuoteUnavailable('Cotação disponível apenas para anúncios MLB em reais.')
        # The principal price cannot stand in for variant-specific prices.
        if not isinstance(item.get('variations'), list) or item['variations']:
            raise QuoteUnavailable('Preço por variação não coberto por esta cotação unitária.')
        price = amount(item.get('price'), positive=True)
        category, listing_type = item.get('category_id'), item.get('listing_type_id')
        if not isinstance(category, str) or not re.fullmatch(r'MLB[0-9]{1,20}', category) or listing_type not in ('free', 'gold_special', 'gold_pro'):
            raise QuoteUnavailable('Categoria ou modalidade do anúncio não verificável.')
        shipping = item.get('shipping')
        if not isinstance(shipping, dict):
            raise QuoteUnavailable('Contexto logístico ausente. A tarifa não será estimada sem ele.')
        logistic, mode = shipping.get('logistic_type'), shipping.get('mode')
        if not isinstance(logistic, str) or LOGISTICS.get(logistic) != mode:
            raise QuoteUnavailable('Contexto logístico ausente ou incompatível para cotação.')
        params = dict(price=format(price, '.2f'), category_id=category, listing_type_id=listing_type,
                      currency_id='BRL', logistic_type=logistic, shipping_mode=mode,
                      quantity=1, channel='marketplace')
        payload = get(token, '/sites/MLB/listing_prices', params, request_get)
        choices = payload if isinstance(payload, list) else [payload]
        choices = [r for r in choices if isinstance(r, dict) and r.get('currency_id') == 'BRL' and r.get('listing_type_id') == listing_type]
        if len(choices) != 1:
            raise QuoteUnavailable('Resposta sem uma cotação única na moeda e modalidade consultadas.')
        result = choices[0]
        total = amount(result.get('sale_fee_amount'))
        details = result.get('sale_fee_details')
        fixed = amount(details.get('fixed_fee')) if isinstance(details, dict) and details.get('fixed_fee') is not None else None
        if fixed is not None and fixed > total:
            raise QuoteUnavailable('Detalhe fixo incompatível com a tarifa total retornada.')
        # financing_add_on_fee is not treated as BRL: its unit is not certified here.
        return dict(state='quoted', checked_at=now, price=price, total=total, fixed=fixed,
                    category=category, listing_type=listing_type, logistic=logistic, mode=mode)
    except QuoteUnavailable as exc:
        return unknown(str(exc))


def render(cid, item_id, title, csrf, result=None):
    esc = lambda v: escape(str(v), quote=True)
    out = CSS+'<div class="pf fee-quote"><header class="pf-hero"><span class="pf-eyebrow">Anúncios 2.0 · Consulta sob demanda</span><h2>Cotação atual de tarifa</h2><p>'+esc(title or item_id)+' · '+esc(item_id)+'</p><a href="/anuncios/'+str(cid)+'/'+item_id+'/rentabilidade">← Rentabilidade do anúncio</a><p>Estimativa retornada pelo calculador do Mercado Livre para uma unidade, na modalidade e logística atuais. Não é cobrança confirmada de uma venda.</p></header><section class="pf-card"><h3>Consultar com o contexto do anúncio</h3><p>A consulta verifica a conta autorizada e o anúncio antes de solicitar a tarifa. Usa o preço principal retornado agora, categoria, moeda, modalidade, logística, modo de envio e quantidade 1. Anúncios com variações ou contexto incompleto ficam sem cotação.</p><form method="post"><input type="hidden" name="_csrf" value="'+esc(csrf)+'"><button>Consultar tarifa no Mercado Livre</button></form></section>'
    if result:
        stamp = result['checked_at'].astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y às %H:%M:%S · Brasília')
        out += '<section class="pf-card" id="fee-quote-result"><h3>Resultado da consulta</h3><p>'+esc(stamp)+'</p>'
        if result['state'] != 'quoted':
            out += '<p class="pf-alert" role="status">Sem cotação verificável. '+esc(result['message'])+'</p>'
        else:
            out += '<div class="pf-grid"><article class="pf-metric"><span>Preço principal consultado · 1 unidade</span><strong>'+format_brl(result['price'])+'</strong></article><article class="pf-metric"><span>Tarifa de venda estimada · sale_fee_amount</span><strong>'+format_brl(result['total'])+'</strong></article><article class="pf-metric"><span>Detalhe fixo incluído · fixed_fee</span><strong>'+(format_brl(result['fixed']) if result['fixed'] is not None else 'Não informado')+'</strong></article></div><p>O detalhe fixo já pertence à tarifa retornada; não some novamente. Campo ausente é desconhecido, inclusive quando o total é zero.</p><details><summary>Conferir contexto e fonte</summary><p>Fonte: API Mercado Livre · /sites/MLB/listing_prices · canal marketplace · BRL · quantidade 1.</p><p>Categoria: '+esc(result['category'])+' · modalidade: '+esc(result['listing_type'])+' · logística: '+esc(result['logistic'])+' · envio: '+esc(result['mode'])+'.</p></details>'
        out += '</section>'
    out += '<section class="pf-card"><h3>Limites da cotação</h3><p>A resposta pode mudar conforme condições comerciais e momento da consulta. Não representa todos os preços promocionais, compradores, variações ou quantidades. Não certifica opções de parcelamento e não converte financing_add_on_fee em reais.</p><p>Não inclui nem presume frete, impostos, publicidade, produto, repasse ou lucro. Não salva valores como custos históricos, não altera anúncios e não substitui documentos de cobrança.</p><p><a href="/anuncios/'+str(cid)+'/'+item_id+'/parcelamento">Comparar opções com premissas manuais ↗</a></p></section></div>'
    return out


def register(app, login_required, can_view, bank, query, shop_page, resolve_token, request_get):
    @app.route('/anuncios/<int:cid>/<item_id>/cotacao-tarifa', methods=['GET', 'POST'])
    @login_required
    def listing_current_fee_quote(cid, item_id):
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
        result = None
        if request.method == 'POST':
            token = resolve_token(shops[0])
            result = quote(token, shops[0]['user_id'], item_id, request_get)
        return shop_page('Cotação atual de tarifa', cid, shops[0]['cliente'], 'anuncios',
                         render(cid, item_id, shops[0]['titulo'], csrf, result))
