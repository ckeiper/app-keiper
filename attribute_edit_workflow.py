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
    from attribute_readback import field
    rows=[field(p,item,matches(p,item)) for p in proposals]
    from attribute_variations import preserved
    integrity=preserved(data,proposals,item)
    return dict(preserved=integrity,message='Atualização confirmada por nova leitura.' if all(r['confirmed'] for r in rows) and integrity else 'Envio sem confirmação integral. Confira os campos antes de qualquer nova tentativa.',fields=rows)


def apply(plan,codes,token,seller,item_id,get,put,persist,now=None,post=None):
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
        if data.get('manual_inputs') and data.get('manual_actor')!=plan.get('created_by'):raise ValueError('Responsável divergente.')
        facts=gather(token,seller,item_id,get);fresh=analyze(facts,data.get('manual_inputs'),plan.get('created_by'))
        if facts['fingerprint']!=data['fingerprint'] or facts['blocked'] or fresh.get('extractor_version')!=data.get('extractor_version'):
            previous = data.get('fingerprint_parts', {})
            current = facts.get('fingerprint_parts', {})
            labels = {'item': 'dados do anúncio', 'description': 'descrição', 'rules': 'regras da categoria',
                      'sheet': 'ficha técnica da categoria', 'scope': 'vínculo do anúncio'}
            labels.update({'item.'+key: 'anúncio ('+label+')' for key, label in {
                'attributes': 'atributos', 'variations': 'variações', 'tags': 'tags',
                'status': 'status', 'title': 'título', 'condition': 'condição',
                'category_id': 'categoria', 'catalog_listing': 'catálogo',
                'catalog_product_id': 'produto de catálogo', 'user_product_id': 'User Product',
                'family_id': 'família', 'family_name': 'nome da família',
                'id': 'identidade', 'seller_id': 'conta', 'site_id': 'site'}.items()})
            changed = [label for key, label in labels.items()
                       if key in previous and key in current and previous[key] != current[key]]
            reason = facts['blocked'] or ('Mudança detectada em: ' + ', '.join(changed) + '.' if changed
                                          else 'A base da análise mudou.')
            persist('stale',dict(message=reason+' Analise novamente antes de enviar.',changed_components=changed));return
        proposals=selected_proposals(fresh,codes)
        approved=selected_proposals(data,codes)
        if any(a['payload']!=b['payload'] or a['expected']!=b['expected'] or a.get('variation_id')!=b.get('variation_id') or a.get('attribute_id')!=b.get('attribute_id') for a,b in zip(approved,proposals)):
            persist('stale',dict(message='A sugestão mudou desde a revisão. Analise novamente antes de enviar.'));return
        if any(p.get('variation_id') for p in proposals) and data.get('variation_snapshot')!=fresh.get('variation_snapshot'):raise ValueError('Base das variações divergente.')
        from attribute_variations import payload
        update=payload(proposals,facts['item'])
    except (ContentUnavailable,ValueError):
        persist('rejected',dict(message='Não foi possível revalidar a análise. Nenhum envio foi realizado.'));return
    from attribute_conditional_review import review
    conditional=review(facts,update,token,post)
    extra={'conditional':conditional} if conditional['state']!='not_requested' else {}
    if not conditional['allow_send']:
        persist('rejected',dict(message=conditional['message'],**extra));return
    if extra:
        # Record the read-only query before the single marketplace write.
        persist('sending',dict(message='Condições consultadas; enviando campos selecionados.',**extra),selected=codes)
    try:
        response=put('https://api.mercadolibre.com/items/'+item_id,headers={'Authorization':'Bearer '+token},
                     json=update,timeout=(3,8),allow_redirects=False)
    except requests.RequestException:
        persist('uncertain',dict(message='A resposta do envio não chegou. Não houve reenvio automático; use Confirmar envio.',**extra));return
    if response.status_code!=200:
        persist('uncertain',dict(message='O Mercado Livre não confirmou o envio. Confira o resultado antes de reenviar.',http_status=int(response.status_code),**extra));return
    try:
        result=verification(data,codes,owned(token,seller,item_id,get))
    except ContentUnavailable:
        persist('uncertain',dict(message='Envio respondeu, mas a nova leitura não pôde confirmar a gravação. Use Confirmar envio.',**extra));return
    result.update(extra)
    persist('confirmed' if confirmed(result) else 'uncertain',result)


def confirmed(result):
    return bool(result.get('fields')) and all(r['confirmed'] for r in result['fields']) and result.get('preserved',True) is True
