"""Presence evidence only: never certifies values, applicability or listing validity."""
from html import escape


def attributes(rows):
    if not isinstance(rows, list) or len(rows)>2000:
        return None
    result={}
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'].strip() or len(row['id'])>200 or row['id'] in result:
            return None
        result[row['id']]=row
    return result


def has_value(row):
    if row is None:
        return False
    # -1 is a declared not-applicable value, not proof of a required value.
    if str(row.get('value_id'))=='-1':
        return None
    if isinstance(row.get('value_name'),str) and row['value_name'].strip():
        return True
    value=row.get('value_id')
    if not isinstance(value,bool) and isinstance(value,(str,int)) and str(value).strip() and str(value) not in ('-1','0'):
        return True
    if row.get('values'):
        return None  # Complex values are not certified by this presence check.
    return False


def presence(code,item):
    main=attributes(item.get('attributes'))
    common=has_value(main.get(code)) if main is not None else None
    if common is True:
        return 'informed','Valor informado no anúncio principal'
    variants=item.get('variations')
    if not isinstance(variants,list) or len(variants)>1000:
        return 'unknown','Variações não verificadas'
    if not variants:
        if common is None:
            return 'unknown','Valor não verificável no anúncio principal'
        return 'review','Sem valor identificado no anúncio principal'
    identifiers=set();present=0;unknown=0
    for variant in variants:
        if not isinstance(variant,dict) or isinstance(variant.get('id'),bool) or not isinstance(variant.get('id'),(str,int)) or not str(variant['id']).strip() or str(variant['id']) in identifiers:
            return 'unknown','Variações inválidas ou repetidas na resposta'
        identifiers.add(str(variant['id']))
        groups=[attributes(variant.get(key)) for key in ('attributes','attribute_combinations')]
        states=[has_value(group.get(code)) if group is not None else None for group in groups]
        if True in states:present+=1
        elif None in states:unknown+=1
    total=len(variants)
    if present==total:
        return 'informed',f'Valor informado em {present} de {total} variações'
    detail=f'Valor identificado em {present} de {total} variações'
    if unknown or common is None:
        return 'unknown',detail+'; demais valores não verificáveis'
    return 'review',detail+'; conferir variações sem valor identificado'


def compare(payload,item):
    definitions=attributes(payload)
    if definitions is None:
        return dict(state='unknown',message='Atributos da categoria não verificáveis na resposta.')
    rows=[]
    for code,definition in definitions.items():
        tags=definition.get('tags')
        if not isinstance(tags,dict) or any(key in tags and type(tags[key]) is not bool for key in ('required','conditional_required')):
            return dict(state='unknown',message='Regras da categoria ausentes ou inválidas na resposta.')
        if not tags.get('required') and not tags.get('conditional_required'):
            continue
        name=definition.get('name')
        name=name if isinstance(name,str) and name.strip() and len(name)<=300 else code
        state,message=presence(code,item)
        conditional=tags.get('conditional_required') is True
        rows.append(dict(id=code,name=name,conditional=conditional,state=state,message=message))
    return dict(state='read',rows=rows[:100],total=len(rows))


def render(result):
    esc=lambda v:escape(str(v),quote=True)
    out='<section class="cs-required"><h4>Atributos exigidos pela categoria</h4><p>Conferência de presença dos campos marcados como obrigatórios ou condicionais na categoria consultada. Valor informado não comprova validade, aplicabilidade ou aprovação do anúncio.</p>'
    if result.get('state')!='read':
        return out+'<p role="status">Requisitos não verificados. '+esc(result.get('message','Consulta indisponível.'))+'</p></section>'
    if not result['rows']:
        out+='<p>Nenhum atributo marcado como obrigatório ou condicional nesta resposta. Isso não comprova que a ficha está completa.</p>'
    out+='<p>Categoria consultada: '+esc(result.get('category','Não informada'))+'.</p>'
    for row in result['rows']:
        label='Obrigatoriedade condicional · aplicabilidade não avaliada' if row['conditional'] else 'Obrigatório na categoria consultada'
        out+='<article class="cs-requirement" data-presence="'+esc(row['state'])+'"><h5>'+esc(row['name'])+'</h5><p>'+label+'</p><p>'+esc(row['message'])+'</p></article>'
    if result['total']>100:
        out+='<p>Exibidos 100 de '+str(result['total'])+' requisitos retornados.</p>'
    return out+'<p>Não executa validação de publicação ou regras condicionais e não aprova critérios do checklist. A categoria e o anúncio podem mudar após esta leitura.</p></section><style>.cs-requirement{border:1px solid #426184;border-radius:10px;padding:14px;margin:12px 0;overflow-wrap:anywhere}.cs-requirement h5{font:inherit;font-weight:700;margin:0 0 8px}</style>'
