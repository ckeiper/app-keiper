"""One-shot writer with fresh evidence and read-back verification."""
import time
import requests
from attribute_completion import gather,analyze,owned,matches,EXTRACTOR_VERSION
from listing_content_snapshot import ContentUnavailable


def selected_proposals(data,codes):
    proposals={p['id']:p for p in data.get('proposals',[])}
    if not codes or len(codes)>50 or len(set(codes))!=len(codes) or any(c not in proposals for c in codes):raise ValueError('Selecione somente sugestões desta análise, sem repetições.')
    return [proposals[c] for c in codes]


def verification(data,codes,item):
    proposals=selected_proposals(data,codes)
    rows=[dict(id=p['id'],name=p['name'],confirmed=matches(p,item)) for p in proposals]
    return dict(message='Atualização confirmada por nova leitura.' if all(r['confirmed'] for r in rows) else 'Envio sem confirmação integral. Confira os campos antes de qualquer nova tentativa.',fields=rows)


def apply(plan,codes,token,seller,item_id,get,put,persist,now=None):
    data=plan['data'];selected_proposals(data,codes)
    if plan['state']!='ready':raise ValueError('Esta análise já foi usada. Consulte o resultado; nenhum reenvio automático será feito.')
    if data.get('blocked'):raise ValueError(data['blocked'])
    if (now or int(time.time()))-plan['created_at']>900:
        persist('stale',dict(message='Análise expirada. Faça uma nova leitura.'));return
    if data.get('extractor_version')!=EXTRACTOR_VERSION:
        persist('stale',dict(message='O leitor de sugestões foi atualizado. Analise novamente antes de enviar.'));return
    # Commit intent before any operation which might send to the marketplace.
    persist('sending',dict(message='Preparando envio; não repita a operação.'),selected=codes)
    try:
        facts=gather(token,seller,item_id,get);fresh=analyze(facts)
        if facts['fingerprint']!=data['fingerprint'] or facts['blocked'] or fresh.get('extractor_version')!=data.get('extractor_version'):
            persist('stale',dict(message='O anúncio, suas regras ou seus vínculos mudaram. Analise novamente antes de enviar.'));return
        proposals=selected_proposals(fresh,codes)
        approved=selected_proposals(data,codes)
        if any(a['payload']!=b['payload'] or a['expected']!=b['expected'] for a,b in zip(approved,proposals)):
            persist('stale',dict(message='A sugestão mudou desde a revisão. Analise novamente antes de enviar.'));return
    except (ContentUnavailable,ValueError):
        persist('rejected',dict(message='Não foi possível revalidar a análise. Nenhum envio foi realizado.'));return
    try:
        response=put('https://api.mercadolibre.com/items/'+item_id,headers={'Authorization':'Bearer '+token},
                     json={'attributes':[p['payload'] for p in proposals]},timeout=(3,8),allow_redirects=False)
    except requests.RequestException:
        persist('uncertain',dict(message='A resposta do envio não chegou. Não houve reenvio automático; use Confirmar envio.'));return
    if response.status_code!=200:
        persist('uncertain',dict(message='O Mercado Livre não confirmou o envio. Confira o resultado antes de reenviar.',http_status=int(response.status_code)));return
    try:
        result=verification(data,codes,owned(token,seller,item_id,get))
    except ContentUnavailable:
        persist('uncertain',dict(message='Envio respondeu, mas a nova leitura não pôde confirmar a gravação. Use Confirmar envio.'));return
    persist('confirmed' if all(r['confirmed'] for r in result['fields']) else 'uncertain',result)
