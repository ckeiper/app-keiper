"""Read-only conditional query against a complete candidate, before any item PUT."""
from copy import deepcopy
from html import escape
from content_required_attributes import attributes
from content_technical_specs import PresenceIndex
from content_conditional_attributes import evaluate
from contextual_help import tip

HELP = 'Consulta das exigências condicionais de publicação retornadas pela categoria para o anúncio com os campos selecionados. Não valida integralmente uma atualização, o conteúdo dos valores ou a aplicabilidade de N/A. Presença incompleta ou não verificável pede conferência; não confirma erro do anúncio.'


def candidate(item, update):
    result = deepcopy(item)
    if set(update) - {'attributes', 'variations'}:
        raise ValueError('Atualização fora do escopo.')
    if 'attributes' in update:
        old, edits = attributes(item.get('attributes')), attributes(update['attributes'])
        if old is None or edits is None:
            raise ValueError('Atributos não verificáveis.')
        old.update(deepcopy(edits))
        if len(old) > 2000:
            raise ValueError('Atributos excedem o limite.')
        result['attributes'] = list(old.values())
    if 'variations' in update:
        variants = result.get('variations'); edits = update['variations']
        if not isinstance(variants,list) or not isinstance(edits,list) or len(variants)>100:
            raise ValueError('Variações não verificáveis.')
        by_id = {str(v['id']): v for v in variants}
        seen = set()
        for row in edits:
            if not isinstance(row,dict) or set(row)-{'id','attributes'}:
                raise ValueError('Variação fora do escopo.')
            code = str(row.get('id'))
            if code not in by_id or code in seen:
                raise ValueError('Destino de variação não verificado.')
            seen.add(code)
            if 'attributes' in row:
                if attributes(row['attributes']) is None:
                    raise ValueError('Atributos da variação inválidos.')
                by_id[code]['attributes'] = deepcopy(row['attributes'])
        if seen != set(by_id):
            raise ValueError('Base de variações incompleta.')
    return result


def review(facts, update, token, post):
    unknown = dict(state='unknown',allow_send=False,message='Consulta condicional não concluída. Nenhum envio foi realizado; faça nova análise antes de tentar novamente.')
    rules = facts['rules']; conditional = []
    for code, rule in rules.items():
        tags = rule.get('tags')
        if not isinstance(tags,dict) or ('conditional_required' in tags and type(tags['conditional_required']) is not bool):
            return unknown
        if tags.get('conditional_required') is True:
            conditional.append(code)
    if not conditional:
        return dict(state='not_requested',allow_send=True)
    try:
        item = candidate(facts['item'],update)
        index = PresenceIndex(item)
        if index.main is None or index.variants is None:
            return unknown
    except (ValueError,TypeError,KeyError):
        return unknown
    result = evaluate(token,item.get('category_id'),item,facts['description'],post)
    if result.get('state') != 'read':
        return dict(unknown,message='Limite de consultas do Mercado Livre atingido. Nenhum envio foi realizado; aguarde antes de fazer nova análise.') if result.get('rate_limited') else unknown
    required = result['required_ids']
    if any(code not in conditional for code in required):
        return dict(unknown,message='Resposta condicional divergente das regras consultadas. Nenhum envio foi realizado; faça nova análise.')
    fields = []; pending = 0
    for code in required:
        state, message, _ = index.evidence(code)
        if state != 'informed':
            pending += 1
        name = rules[code].get('name',code)
        name = name if isinstance(name,str) and 1 <= len(name) <= 300 else code
        fields.append(dict(id=code,name=name,state=state,message=message))
    fields.sort(key=lambda row: row['state']=='informed')
    return dict(state='review' if pending else 'read',allow_send=not pending,total=len(required),pending=pending,fields=fields[:50],
        message='A consulta condicional retornou campos para conferência. Nenhum envio foi realizado; confira os valores e faça nova análise.' if pending else 'Consulta condicional concluída; presença dos campos retornados conferida.')


def render(report):
    if not isinstance(report,dict) or report.get('state')=='not_requested':
        return ''
    esc=lambda value:escape(str(value),quote=True)
    out='<section class="ae-conditional"><h4>Conferência condicional'+tip('Conferência condicional',HELP)+'</h4><p role="status">'+esc(report.get('message','Consulta não verificada.'))+'</p>'
    fields=report.get('fields',[])
    if fields:
        out+='<details'+(' open' if report.get('pending') else '')+'><summary>'+str(report['total'])+(' campo retornado' if report['total']==1 else ' campos retornados')+' · '+str(report['pending'])+' para conferir</summary><ul>'
        for field in fields:out+='<li><strong>'+esc(field['name'])+'</strong> <small>'+esc(field['id'])+'</small><p>'+esc(field['message'])+'</p></li>'
        if len(fields)<report['total']:out+='<li>Exibidos os primeiros 50 campos; a conferência considera todos os retornados.</li>'
        out+='</ul></details>'
    return out+'</section>'
