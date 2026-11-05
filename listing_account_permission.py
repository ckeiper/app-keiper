"""Account-level listing permission from the already verified /users/me response."""
from html import escape


def normalize(account):
    status=account.get('status')
    listing=status.get('list') if isinstance(status,dict) else None
    listing=listing if isinstance(listing,dict) else {}
    allow=listing.get('allow')
    allow=allow if type(allow) is bool else None
    codes=listing.get('codes')
    valid=(isinstance(codes,list) and len(codes)<=100
           and all(isinstance(c,str) and 0<len(c)<=200 for c in codes))
    unique=list(dict.fromkeys(codes)) if valid else None
    return dict(allow=allow,codes=unique[:20] if unique is not None else None,
                limited=unique is not None and len(unique)>20)


def render(result):
    out='<section class="rr-account-permission"><h4>Permissão de publicação da conta</h4>'
    if result is None:return out+'<p>Não verificada nesta consulta.</p></section>'
    allow=result['allow']
    label='Não verificada'
    if allow is True:label='Permitida na conta'
    elif allow is False:label='Não permitida na conta'
    out+='<p role="status"><strong>'+label+'</strong></p>'
    if allow is False:out+='<p>Confira as pendências da conta no Mercado Livre antes de decidir sobre o anúncio.</p>'
    codes=result['codes']
    if codes is None:out+='<p>Códigos da permissão não verificáveis na resposta.</p>'
    elif not codes:out+='<p>Nenhum código retornado para essa permissão.</p>'
    else:
        out+='<details><summary>Códigos retornados pelo Mercado Livre</summary><ul>'
        out+=''.join('<li><code>'+escape(code,quote=True)+'</code></li>' for code in codes)
        out+='</ul></details>'
    if result['limited']:out+='<p>Exibidos os primeiros vinte códigos distintos.</p>'
    return out+'<p>A permissão da conta não garante elegibilidade ou reativação deste anúncio.</p></section>'
