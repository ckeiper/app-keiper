"""Read official item status signals, without inferring eligibility or writing offers."""
import re
from datetime import datetime, timezone
from html import escape
from sales_metrics import SAO_PAULO
from listing_content_snapshot import read, ContentUnavailable

SOURCE = 'https://developers.mercadolivre.com.br/pt_br/produto-sincronizacao-de-publicacoes'
REASONS = {
    'out_of_stock': ('Falta de estoque', 'Confira a disponibilidade real e a logística antes de decidir.'),
    'paused_by_seller': ('Pausa pelo vendedor', 'Confira o motivo interno da pausa antes de decidir no Mercado Livre.'),
    'waiting_for_patch': ('Correção pendente', 'Consulte a infração e a correção solicitada no Mercado Livre.'),
    'held': ('Em análise pelo Mercado Livre', 'Acompanhe a revisão no Mercado Livre.'),
    'pending_documentation': ('Documentação pendente', 'Confira os documentos solicitados no Mercado Livre.'),
    'forbidden': ('Restrição por moderação', 'Consulte a moderação no Mercado Livre antes de qualquer decisão.'),
    'picture_download_pending': ('Processamento de imagens pendente', 'Acompanhe o processamento das imagens no Mercado Livre.'),
    'picture_downloading_pending': ('Processamento de imagens pendente', 'Acompanhe o processamento das imagens no Mercado Livre.'),
}


def inspect(token, seller, item_id, request_get, include_moderation=False):
    result = dict(state='unknown', checked_at=datetime.now(timezone.utc))
    if (not isinstance(token, str) or not token or isinstance(seller, bool)
            or not re.fullmatch(r'[1-9][0-9]{0,19}', str(seller))):
        return dict(result, message='Conexão não verificável para consulta.')
    if not isinstance(item_id, str) or not re.fullmatch(r'MLB[0-9]{1,20}', item_id):
        return dict(result, message='Anúncio não verificável para consulta.')
    try:
        account = read(token, '/users/me', request_get)
        if str(account.get('id')) != str(seller):
            raise ContentUnavailable('A autorização não corresponde à conta desta loja.')
        item = read(token, '/items/'+item_id, request_get)
        if (item.get('id') != item_id or str(item.get('seller_id')) != str(seller)
                or item.get('site_id') != 'MLB'):
            raise ContentUnavailable('O anúncio retornado não corresponde a esta loja.')
    except ContentUnavailable as exc:
        return dict(result, message=str(exc))
    status = item.get('status')
    status = status if isinstance(status, str) and 0 < len(status) <= 100 else None
    codes = item.get('sub_status')
    verified = (isinstance(codes, list) and len(codes) <= 100
                and all(isinstance(c, str) and 0 < len(c) <= 200 for c in codes))
    from listing_account_permission import normalize as account_permission
    result.update(state='read', status=status,codes=list(dict.fromkeys(codes)) if verified else None,
                  account_permission=account_permission(account))
    if include_moderation:
        from listing_moderation import inspect as inspect_moderation
        result['moderation']=inspect_moderation(token,item_id,request_get)
    return result


def render(token, result=None):
    esc = lambda v: escape(str(v), quote=True)
    out = '<article class="rr-official"><h3>Motivos retornados pelo Mercado Livre</h3>'
    out += '<form method="post"><input type="hidden" name="_csrf" value="'+esc(token)+'"><button name="action" value="consultar_motivos">Consultar motivos atuais</button><button name="action" value="consultar_moderacao">Consultar motivos e moderação</button></form>'
    if result:
        out += '<p>Consulta: '+esc(result['checked_at'].astimezone(SAO_PAULO).strftime('%d/%m/%Y %H:%M:%S'))+' · Brasília</p>'
        if result['state'] != 'read':
            out += '<p role="status">Leitura não verificada. '+esc(result['message'])+'</p>'
        else:
            out += '<p>Status retornado: <strong>'+esc(result['status'] or 'Não verificado')+'</strong></p>'
            if result['codes'] is None:
                out += '<p>Substatus não verificáveis na resposta.</p>'
            elif not result['codes']:
                out += '<p>Nenhum substatus retornado. Isso não comprova ausência de restrições.</p>'
            for code in result['codes'] or []:
                label, guidance = REASONS.get(code, ('Código sem interpretação local', 'Confira o detalhe no Mercado Livre.'))
                out += '<p><strong>'+esc(label)+'</strong> · <code>'+esc(code)+'</code><br>'+esc(guidance)+'</p>'
    from listing_account_permission import render as render_account_permission
    out+=render_account_permission(result.get('account_permission') if result else None)
    from listing_moderation import render as render_moderation
    out+=render_moderation(result.get('moderation') if result else None)
    out += '<p>Fonte: status e substatus do anúncio na API. Moderação consultada somente pelo botão correspondente. Esta leitura não confirma elegibilidade nem altera a oferta.</p>'
    return out+'<a href="'+SOURCE+'" target="_blank" rel="noopener noreferrer">Documentação dos status</a></article>'
